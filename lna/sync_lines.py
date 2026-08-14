"""sync_lines -- cross-line union-merge of append-only store data.

Implements `lna/plans2/15-ENGINEER-PROPOSAL.md` SS5.6 ("One store discipline
extension"): the program split today into two long-lived git lines --
`main`/`lna-data` (the LNA program + shared core) and `engineer` (a new
product line, forked off `lna-data`). The lines are managed separately, but
their generated training data (`lna/datastore.py`'s tables) must still be
COMBINABLE -- a session on one line should be able to pull in rows a session
on the other line produced, without either line ever adopting the other's
code. This module is that combination path, and the ONLY sanctioned one: see
the root `.gitattributes` entry this module's docstring is cross-referenced
from, which turns off git's own text merge for these files precisely because
a 3-way line merge can interleave or duplicate appended JSONL lines and
silently break the byte-prefix a snapshot's sha256 pins.

`lna/datastore.py`'s top docstring states the contracts this tool must never
violate, restated here in the cross-checkout context:

  * **Append-only.** A table is a log; combining two logs must yield a log,
    never a rewrite. Concretely: the bytes that already existed in DEST
    before a sync run are byte-for-byte still there, at the same offset,
    afterward -- the only legal write is an append at the tail.
  * **Repeat-probe keys / no in-place edits.** Rows are written once and never
    edited (`append_l2`'s refuse-unless-repeat_probe rule, and there is no
    edit path at all for point/op rows). That is exactly what makes **line
    identity = exact byte equality of the JSON line** the correct dedupe key:
    no canonicalization, no key-order normalization, no semantic diffing --
    two lines are "the same row" iff they are the same bytes. Two DIFFERENT
    rows that happen to describe related work (e.g. a repeat-probe of the
    same (wl_hash, spec)) are, correctly, both kept: this tool merges tables,
    it does not adjudicate what belongs in them.
  * **Snapshots pin (line count, sha256 of the byte prefix).** `datastore.load`
    re-hashes a snapshot's pinned prefix on every read and raises if it does
    not match -- so this tool's prefix-preservation guarantee (above) is not
    a nicety, it is what keeps every snapshot anyone has ever taken on either
    line still valid after a merge.

Semantics (SOURCE -> DEST, one-way; the coordinator runs this twice, once in
each direction, to actually combine two lines):

  1. **Prefix preservation.** DEST's existing bytes are never reordered,
     edited, or interleaved. Verified after every write (assert, not assume):
     the bytes that existed in DEST before the call are an exact byte-prefix
     of DEST after it.
  2. **Line identity = exact byte equality** of the JSON line, trailing
     newline stripped and nothing else. A sha256 hash set of DEST's lines
     bounds memory (the point/op tables run to hundreds of MB); SOURCE lines
     not in that set are appended in SOURCE-file order, and each appended
     line's hash joins the set immediately -- so a line repeated within
     SOURCE itself lands in DEST exactly once, the same way it would if it
     had already been there.
  3. **Tables**: `topo_labels.jsonl`, `l1_labels.jsonl`, `sim_points.jsonl`,
     `op_points.jsonl` (point/op are gitignored -- filesystem sync across
     checkouts is exactly why this tool exists), `lna/playbook/edges.jsonl`
     (same union-append rule), and `lna/playbook/entries/*.json` (one file per
     id: SOURCE-only files are copied; a filename present on both sides with
     DIFFERENT bytes is a **conflict** -- reported, never overwritten, because
     silently picking a winner between two lines' playbook entries is a
     human/coordinator call, not this tool's to make).
  4. **`snapshots.json`** merges by name: an identical pin on both sides is a
     no-op; the SAME name with a DIFFERENT pin is a reported conflict, never
     silently resolved (never "last write wins"). SOURCE-only names are
     copied only with `--copy-snapshots` (default OFF): a snapshot pins THAT
     checkout's file state at a moment in time, and once two lines' tables
     have diverged, an imported snapshot name generally does not describe
     anything reproducible in the importing checkout -- `datastore.load`
     would just raise a sha256 mismatch the first time anyone tried to use
     it. Copying is opt-in for the rare case (e.g. right after a fork, before
     any divergence) where it still does describe something real.
  5. **Provenance.** Every run appends one record to `<dest>/sync_log.jsonl`:
     `{ts, source, dest, tables: {name: {lines_appended, lines_skipped_dup,
     conflicts}}, snapshots: {...}, git_sha, dry_run}` (`git_sha` reuses
     `datastore.git_sha()` -- the sync TOOL's own commit, i.e. which version
     of this merge logic produced the record, not either line's data commit).
     `--report PATH` writes the same record, pretty-printed, wherever asked.
  6. **`--check`** is a self-test in a tempdir: two synthetic stores with
     overlapping, disjoint, and (within one side) duplicate lines are synced
     both directions, and the run asserts prefix preservation, a complete
     union, exact dedupe, idempotence (a second identical run appends
     nothing), a detected playbook-entry conflict, and a detected snapshot
     conflict. Prints GREEN/FAIL like `lna/playbook.py --check` does.

Design notes (semantics not spelled out above, decided here):

  * `--source`/`--dest` accept a repo checkout root, an `lna/` directory, or
    an `lna/data` directory interchangeably -- whichever is convenient for
    the caller; all three resolve to the same `lna/` directory this module
    treats as the unit (its `data/` and `playbook/` subtrees).
  * `snapshots.json` is combined on every run regardless of `--tables`: it is
     not one of the append-only tables in item 3 above, it is the separate
     concern in item 4, and skipping it silently because a caller only asked
     to sync `sim_points` would be a surprising way to lose a conflict report.
  * `--dry-run` performs every read and every comparison (so its counts are
    exact) but no write anywhere -- not to a table, not to `sync_log.jsonl`.
    `--report` still writes (it is the caller asking to see the would-be
    result, not asking this tool to mutate the store).

Usage:
    python lna/sync_lines.py --source ../engineer-checkout --dest lna/data
    python lna/sync_lines.py --source . --dest . --dry-run   # identity check
    python lna/sync_lines.py --source X --tables topo_labels l1_labels
    python lna/sync_lines.py --source X --copy-snapshots --report out.json
    python lna/sync_lines.py --check
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import datastore as ds  # noqa: E402  (reuse git_sha() only -- this tool reads
                          # and writes raw files, not through the store API,
                          # because SOURCE/DEST are arbitrary checkouts, not
                          # necessarily "this" one)

JSONL_TABLES = {                      # table name -> filename under lna/data/
    "topo_labels": "topo_labels.jsonl",
    "l1_labels":   "l1_labels.jsonl",
    "sim_points":  "sim_points.jsonl",
    "op_points":   "op_points.jsonl",
}
PLAYBOOK_JSONL_TABLES = {             # table name -> filename under lna/playbook/
    "playbook_edges": "edges.jsonl",
}
ALL_TABLES = tuple(JSONL_TABLES) + ("playbook_entries",) + tuple(PLAYBOOK_JSONL_TABLES)
SNAPSHOTS_FILE = "snapshots.json"
SYNC_LOG_FILE = "sync_log.jsonl"


# --------------------------------------------------------------- path resolution
def _resolve_lna_dir(path):
    """Accept a repo checkout root, an `lna/` dir, or an `lna/data` dir; return
    the `lna/` dir every other path in this module is computed relative to."""
    path = os.path.abspath(path)
    base = os.path.basename(path)
    parent_base = os.path.basename(os.path.dirname(path))
    if base == "data" and parent_base == "lna":
        return os.path.dirname(path)
    if base == "lna":
        return path
    candidate = os.path.join(path, "lna")
    if os.path.isdir(candidate):
        return candidate
    return path        # already lna-shaped (has data/ and/or playbook/ under it)


def _dirs(lna_dir):
    return {"data": os.path.join(lna_dir, "data"),
            "playbook": os.path.join(lna_dir, "playbook")}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------- line io
def _read_lines_bytes(path):
    """Every line of `path` as bytes, trailing newline stripped and NOTHING
    else -- line identity is exact byte equality (datastore.py's rule), so no
    canonicalization happens here."""
    if not os.path.exists(path):
        return []
    with open(path, "rb") as fh:
        data = fh.read()
    if not data:
        return []
    lines = data.split(b"\n")
    if lines[-1] == b"":              # trailing "\n" produced an empty tail split
        lines = lines[:-1]
    return lines


def _line_hash(line):
    return hashlib.sha256(line).hexdigest()


def sync_jsonl(source_path, dest_path, dry_run=False):
    """Union-append SOURCE's lines onto DEST by exact line-byte identity, in
    SOURCE-file order. Returns {"lines_appended", "lines_skipped_dup",
    "conflicts"} -- a plain jsonl table never conflicts (rows are never
    edited in place), the key stays only for report-shape symmetry with the
    playbook/snapshot tables."""
    dest_before = b""
    if os.path.exists(dest_path):
        with open(dest_path, "rb") as fh:
            dest_before = fh.read()
    dest_lines = _read_lines_bytes(dest_path)
    seen = {_line_hash(ln) for ln in dest_lines}

    to_append = []
    skipped = 0
    for ln in _read_lines_bytes(source_path):
        h = _line_hash(ln)
        if h in seen:
            skipped += 1
            continue
        seen.add(h)                   # a line repeated within SOURCE lands once
        to_append.append(ln)

    stats = {"lines_appended": len(to_append), "lines_skipped_dup": skipped,
              "conflicts": 0}
    if dry_run or not to_append:
        return stats

    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    with open(dest_path, "ab") as fh:
        # A DEST missing its final newline (hand-edited, truncated write) would
        # otherwise get its last existing line silently concatenated with the
        # first appended one. Adding a bare separator only appends bytes -- it
        # never touches dest_before -- so the prefix assertion below still holds.
        if dest_before and not dest_before.endswith(b"\n"):
            fh.write(b"\n")
        for ln in to_append:
            fh.write(ln + b"\n")

    with open(dest_path, "rb") as fh:
        dest_after = fh.read()
    assert dest_after[:len(dest_before)] == dest_before, (
        "sync_jsonl prefix violation on %s: the %d line(s) that existed "
        "before this run were not byte-identical after it"
        % (dest_path, len(dest_lines)))

    return stats


# ------------------------------------------------------------- playbook entries
def sync_playbook_entries(source_dir, dest_dir, dry_run=False):
    """Copy SOURCE-only `entries/<id>.json` files into DEST. A filename present
    on both sides with different bytes is a conflict: reported, never
    overwritten. Returns (stats, conflicting_filenames)."""
    stats = {"lines_appended": 0, "lines_skipped_dup": 0, "conflicts": 0}
    conflicts = []
    if not os.path.isdir(source_dir):
        return stats, conflicts
    for name in sorted(os.listdir(source_dir)):
        if not name.endswith(".json"):
            continue
        sp = os.path.join(source_dir, name)
        dp = os.path.join(dest_dir, name)
        with open(sp, "rb") as fh:
            sbytes = fh.read()
        if os.path.exists(dp):
            with open(dp, "rb") as fh:
                dbytes = fh.read()
            if dbytes == sbytes:
                stats["lines_skipped_dup"] += 1
            else:
                stats["conflicts"] += 1
                conflicts.append(name)
            continue
        stats["lines_appended"] += 1
        if not dry_run:
            os.makedirs(dest_dir, exist_ok=True)
            shutil.copyfile(sp, dp)
    return stats, conflicts


# ------------------------------------------------------------------ snapshots
def sync_snapshots(source_data_dir, dest_data_dir, copy_snapshots=False,
                    dry_run=False):
    """Merge `snapshots.json` by name. Same-name-same-pin is a no-op;
    same-name-different-pin is a reported conflict, never silently resolved;
    SOURCE-only names are copied only when `copy_snapshots`. Returns (stats,
    conflicting_names)."""
    stats = {"copied": 0, "matched": 0, "skipped_source_only": 0, "conflicts": 0}
    conflicts = []
    sp = os.path.join(source_data_dir, SNAPSHOTS_FILE)
    if not os.path.exists(sp):
        return stats, conflicts
    with open(sp, "r", encoding="utf-8") as fh:
        source_snaps = json.load(fh)

    dp = os.path.join(dest_data_dir, SNAPSHOTS_FILE)
    dest_snaps = {}
    if os.path.exists(dp):
        with open(dp, "r", encoding="utf-8") as fh:
            dest_snaps = json.load(fh)

    merged = dict(dest_snaps)
    changed = False
    for name, pin in source_snaps.items():
        if name in dest_snaps:
            if dest_snaps[name] == pin:
                stats["matched"] += 1
            else:
                stats["conflicts"] += 1
                conflicts.append(name)
            continue
        if copy_snapshots:
            merged[name] = pin
            stats["copied"] += 1
            changed = True
        else:
            stats["skipped_source_only"] += 1

    if changed and not dry_run:
        os.makedirs(dest_data_dir, exist_ok=True)
        # Same on-disk shape as datastore.snapshot(): indent=2, sorted, LF.
        with open(dp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(merged, fh, indent=2, sort_keys=True)

    return stats, conflicts


# ------------------------------------------------------------------ provenance
def append_sync_log(dest_data_dir, record, dry_run=False):
    if dry_run:
        return
    os.makedirs(dest_data_dir, exist_ok=True)
    line = json.dumps(record, sort_keys=True, ensure_ascii=False)
    with open(os.path.join(dest_data_dir, SYNC_LOG_FILE), "a",
              encoding="utf-8", newline="\n") as fh:
        fh.write(line + "\n")


# --------------------------------------------------------------------- driver
def run_sync(source, dest=None, tables=None, dry_run=False,
             copy_snapshots=False, report_path=None):
    """Union-merge every selected table from SOURCE into DEST (semantics 1-5
    in the module docstring). Returns the same record appended to
    `<dest>/sync_log.jsonl` and, if `report_path`, written there too."""
    dest = dest or ds.DATA_DIR
    source_lna = _resolve_lna_dir(source)
    dest_lna = _resolve_lna_dir(dest)
    if not os.path.isdir(source_lna):
        raise FileNotFoundError(
            "--source %r does not resolve to an existing lna/ directory "
            "(resolved: %s)" % (source, source_lna))
    src = _dirs(source_lna)
    dst = _dirs(dest_lna)
    table_names = list(tables) if tables else list(ALL_TABLES)

    tables_out = {}
    conflicts = {}
    for t in table_names:
        if t in JSONL_TABLES:
            sp = os.path.join(src["data"], JSONL_TABLES[t])
            dp = os.path.join(dst["data"], JSONL_TABLES[t])
            tables_out[t] = sync_jsonl(sp, dp, dry_run=dry_run)
        elif t == "playbook_entries":
            stats, names = sync_playbook_entries(
                os.path.join(src["playbook"], "entries"),
                os.path.join(dst["playbook"], "entries"), dry_run=dry_run)
            tables_out[t] = stats
            if names:
                conflicts[t] = names
        elif t in PLAYBOOK_JSONL_TABLES:
            sp = os.path.join(src["playbook"], PLAYBOOK_JSONL_TABLES[t])
            dp = os.path.join(dst["playbook"], PLAYBOOK_JSONL_TABLES[t])
            tables_out[t] = sync_jsonl(sp, dp, dry_run=dry_run)
        else:
            raise ValueError("unknown table %r; know %s" % (t, sorted(ALL_TABLES)))

    # snapshots.json is item 4, not one of item 3's tables -- always combined,
    # independent of --tables (see "Design notes" in the module docstring).
    snap_stats, snap_names = sync_snapshots(
        src["data"], dst["data"], copy_snapshots=copy_snapshots, dry_run=dry_run)
    if snap_names:
        conflicts["snapshots"] = snap_names

    record = {
        "ts": _now(),
        "source": source_lna,
        "dest": dest_lna,
        "tables": tables_out,
        "snapshots": snap_stats,
        "git_sha": ds.git_sha(),
        "dry_run": bool(dry_run),
    }
    if conflicts:
        record["conflicts"] = conflicts

    append_sync_log(dst["data"], record, dry_run=dry_run)

    if report_path:
        with open(report_path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(record, fh, indent=2, sort_keys=True)

    return record


# ------------------------------------------------------------------ CLI paths
def cmd_sync(args):
    report = run_sync(args.source, dest=args.dest, tables=args.tables,
                      dry_run=args.dry_run, copy_snapshots=args.copy_snapshots,
                      report_path=args.report)
    print("[sync] %s -> %s%s" % (report["source"], report["dest"],
          " (dry-run)" if args.dry_run else ""))
    for t, s in sorted(report["tables"].items()):
        tag = " !%d conflict(s)" % s["conflicts"] if s["conflicts"] else ""
        print("  %-16s +%-4d appended  =%-4d dup%s"
              % (t, s["lines_appended"], s["lines_skipped_dup"], tag))
    ss = report["snapshots"]
    tag = " !%d conflict(s)" % ss["conflicts"] if ss["conflicts"] else ""
    print("  %-16s +%-4d copied    =%-4d matched  %d skipped (no --copy-snapshots)%s"
          % ("snapshots", ss["copied"], ss["matched"],
             ss["skipped_source_only"], tag))
    if report.get("conflicts"):
        print("[sync] CONFLICTS -- resolve by hand, nothing was overwritten:")
        for table, names in sorted(report["conflicts"].items()):
            print("  %s: %s" % (table, ", ".join(names)))
        return 1
    return 0


def _write_jsonl(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        for ln in lines:
            fh.write(ln + b"\n")


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)


def cmd_check(args):
    errs = []

    def _run(label, *a, **kw):
        try:
            return run_sync(*a, **kw)
        except Exception as exc:                                  # noqa: BLE001
            errs.append("%s raised %s: %s" % (label, type(exc).__name__, exc))
            return None

    with tempfile.TemporaryDirectory(prefix="sync_lines_check_") as tmp:
        a = os.path.join(tmp, "line_a", "lna")
        b = os.path.join(tmp, "line_b", "lna")

        # --- jsonl tables: overlapping, disjoint, and (within one side) a
        # duplicate line, per the self-test contract in the module docstring.
        shared   = b'{"kind":"L2","id":"shared"}'
        dup_line = b'{"kind":"L2","id":"dup-in-source"}'
        only_a   = b'{"kind":"L2","id":"only-a"}'
        only_b   = b'{"kind":"L2","id":"only-b"}'
        _write_jsonl(os.path.join(a, "data", "topo_labels.jsonl"),
                    [only_a, shared, dup_line, dup_line])
        _write_jsonl(os.path.join(b, "data", "topo_labels.jsonl"),
                    [shared, only_b])

        # --- playbook entries: agree / source-only / conflict
        agree = {"id": "agree", "rule": "same everywhere"}
        _write_json(os.path.join(a, "playbook", "entries", "agree.json"), agree)
        _write_json(os.path.join(b, "playbook", "entries", "agree.json"), agree)
        _write_json(os.path.join(a, "playbook", "entries", "only-in-a.json"),
                    {"id": "only-in-a"})
        _write_json(os.path.join(a, "playbook", "entries", "clash.json"),
                    {"id": "clash", "rule": "version from A"})
        _write_json(os.path.join(b, "playbook", "entries", "clash.json"),
                    {"id": "clash", "rule": "version from B"})

        # --- edges.jsonl: same union rule as any other jsonl table
        edge_shared = b'{"dst":"y","src":"x","type":"prevents"}'
        edge_only_a = b'{"dst":"q","src":"p","type":"derived_from"}'
        edge_only_b = b'{"dst":"n","src":"m","type":"contradicts"}'
        _write_jsonl(os.path.join(a, "playbook", "edges.jsonl"),
                    [edge_shared, edge_only_a])
        _write_jsonl(os.path.join(b, "playbook", "edges.jsonl"),
                    [edge_shared, edge_only_b])

        # --- snapshots: identical pin / conflicting pin / source-only
        _write_json(os.path.join(a, "data", "snapshots.json"), {
            "agree-snap": {"topo_labels": {"lines": 2, "sha256": "aaa"}},
            "clash-snap": {"topo_labels": {"lines": 3, "sha256": "from-a"}},
            "a-only-snap": {"topo_labels": {"lines": 1, "sha256": "zzz"}},
        })
        _write_json(os.path.join(b, "data", "snapshots.json"), {
            "agree-snap": {"topo_labels": {"lines": 2, "sha256": "aaa"}},
            "clash-snap": {"topo_labels": {"lines": 3, "sha256": "from-b"}},
        })

        b_topo = os.path.join(b, "data", "topo_labels.jsonl")
        with open(b_topo, "rb") as fh:
            b_before = fh.read()

        rep1 = _run("A->B sync", a, dest=os.path.join(b, "data"))
        if rep1 is None:
            print("[check] FAIL -- %d error(s):" % len(errs))
            for m in errs:
                print("  - " + m)
            return 1

        with open(b_topo, "rb") as fh:
            b_after = fh.read()
        if b_after[:len(b_before)] != b_before:
            errs.append("prefix preservation: dest topo_labels.jsonl bytes "
                        "that existed before the sync were changed by it")

        final_lines = _read_lines_bytes(b_topo)
        got_ids = {json.loads(ln)["id"] for ln in final_lines}
        want_ids = {"shared", "only-b", "only-a", "dup-in-source"}
        if got_ids != want_ids:
            errs.append("union incomplete: dest topo_labels ids %r != %r"
                        % (got_ids, want_ids))
        if len(final_lines) != 4:
            errs.append("dedupe not exact: dest topo_labels has %d physical "
                        "lines, want 4 (dup-in-source must land once)"
                        % len(final_lines))

        t1 = rep1["tables"]["topo_labels"]
        if t1["lines_appended"] != 2:
            errs.append("first-run topo_labels lines_appended = %d, want 2"
                        % t1["lines_appended"])

        pe1 = rep1["tables"]["playbook_entries"]
        if (pe1["lines_appended"], pe1["lines_skipped_dup"], pe1["conflicts"]) \
           != (1, 1, 1):
            errs.append("playbook_entries stats wrong on first run: %r" % pe1)
        if rep1.get("conflicts", {}).get("playbook_entries") != ["clash.json"]:
            errs.append("playbook conflict not reported: %r"
                        % rep1.get("conflicts"))
        with open(os.path.join(b, "playbook", "entries", "clash.json"),
                  "rb") as fh:
            clash_b = json.loads(fh.read())
        if clash_b["rule"] != "version from B":
            errs.append("playbook conflict was overwritten -- dest clash.json "
                        "must be untouched")

        if rep1.get("conflicts", {}).get("snapshots") != ["clash-snap"]:
            errs.append("snapshot conflict not reported: %r"
                        % rep1.get("conflicts"))
        with open(os.path.join(b, "data", "snapshots.json"),
                  "r", encoding="utf-8") as fh:
            b_snaps = json.load(fh)
        if b_snaps["clash-snap"]["topo_labels"]["sha256"] != "from-b":
            errs.append("snapshot conflict was silently resolved -- dest "
                        "clash-snap pin must be untouched")
        if "a-only-snap" in b_snaps:
            errs.append("source-only snapshot copied without --copy-snapshots")

        rep2 = _run("A->B re-sync (idempotence)", a, dest=os.path.join(b, "data"))
        if rep2 is not None:
            if any(s["lines_appended"] for s in rep2["tables"].values()) \
               or rep2["snapshots"]["copied"]:
                errs.append("idempotence violated: second identical run "
                            "appended something: %r" % rep2)

        # --- the other direction, and --copy-snapshots
        rep3 = _run("B->A sync", b, dest=os.path.join(a, "data"),
                   copy_snapshots=True)
        if rep3 is not None:
            a_edges = _read_lines_bytes(os.path.join(a, "playbook", "edges.jsonl"))
            if edge_only_b not in a_edges:
                errs.append("reverse-direction edges.jsonl union incomplete")
            with open(os.path.join(a, "data", "snapshots.json"),
                      "r", encoding="utf-8") as fh:
                a_snaps = json.load(fh)
            if a_snaps["clash-snap"]["topo_labels"]["sha256"] != "from-a":
                errs.append("reverse-direction snapshot conflict was resolved")

    if errs:
        print("[check] FAIL -- %d error(s):" % len(errs))
        for m in errs:
            print("  - " + m)
        return 1
    print("[check] GREEN -- prefix preserved, union complete, dedupe exact, "
          "idempotent, playbook conflict detected, snapshot conflict "
          "detected, source-only snapshot skipped without --copy-snapshots")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="sync_lines -- one-way union-merge of append-only store "
                    "data across git lines (plans2/15-ENGINEER-PROPOSAL.md SS5.6)")
    ap.add_argument("--source", metavar="DIR",
                    help="source repo checkout, lna/ dir, or lna/data dir "
                         "(required unless --check)")
    ap.add_argument("--dest", metavar="DIR", default=None,
                    help="dest repo checkout, lna/ dir, or lna/data dir "
                         "(default: this checkout's lna/data)")
    ap.add_argument("--tables", nargs="+", choices=ALL_TABLES, default=None,
                    help="subset of tables to sync (default: all). "
                         "snapshots.json always combines regardless.")
    ap.add_argument("--dry-run", action="store_true",
                    help="compute exact counts; write nothing")
    ap.add_argument("--copy-snapshots", action="store_true",
                    help="also copy source-only snapshot names (default: "
                         "off -- a snapshot pins THAT checkout's file state "
                         "and is generally not portable once lines diverge)")
    ap.add_argument("--report", metavar="JSON_PATH",
                    help="write the run's provenance record to this path too")
    ap.add_argument("--check", action="store_true",
                    help="self-test in a tempdir; ignores --source/--dest")
    args = ap.parse_args(argv)

    if args.check:
        return cmd_check(args)
    if not args.source:
        ap.error("--source is required unless --check")
    return cmd_sync(args)


if __name__ == "__main__":
    sys.exit(main())

"""Append-only label store for the learned-critic phase (plans2/01-DATA.md).

Every ngspice/ZOAF result the pipeline produces is training data; this module is
where it is kept. Three append-only JSONL tables plus a snapshots index, no new
dependencies (pure py-3.14 stack -- json/hashlib/os), so it loads in the same
torch-free analysis env as spec.py/size.py:

    lna/data/topo_labels.jsonl   L2 rows  -- one (topology, spec) sizing outcome  [in git]
    lna/data/l1_labels.jsonl     L1 rows  -- one topology bias/op-point sweep      [in git while small]
    lna/data/sim_points.jsonl    point rows -- one ngspice eval inside a ZOAF run  [gitignored]
    lna/data/snapshots.json      named snapshots: {name: {table: {lines, sha256}}}

Contracts that the rest of the phase relies on (00-OVERVIEW rules 4 + 01-DATA):

  * **Append-only.** Nothing is ever mutated or deleted in place; a re-label is a
    new row (repeat-probe) or a new snapshot, never an edit.
  * **Key = (wl_hash, spec) for L2.** `append_l2` refuses to write a key that
    already exists unless `repeat_probe=True` (the campaign's noise probes, §5),
    so the store never silently double-labels the same work.
  * **One split function.** `family_split` assigns whole WL-similarity families to
    train/val/test; every consumer uses it, nobody rolls their own -- the corpus
    is full of near-duplicates (median NN-sim 1.000 in P1/P2 arms) and a
    row-level random split would leak catastrophically (01-DATA §2, R2).
  * **Reproducible.** `snapshot(name)` pins line counts + sha256; a critic version
    records the snapshot it trained on, and `load(table, snapshot=name)` returns
    exactly those rows back.

Rows are assembled by the logging hooks in size.py (L2 + points) and bias.py
(L1); `row_l2`/`row_l1` here are the single source of the row schema so the
hooks stay thin.
"""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")

TABLES = {
    "topo_labels": "topo_labels.jsonl",   # L2 -- expensive, the prize
    "l1_labels":   "l1_labels.jsonl",     # L1 -- cheap, abundant
    "sim_points":  "sim_points.jsonl",    # point rows -- free byproduct, gitignored
}
SNAPSHOTS = "snapshots.json"

# Families are single-linkage clusters at WL-cosine >= this (01-DATA §2: the
# same 0.9 threshold used to call two graphs "the same topology family").
FAMILY_SIM = 0.9


# --------------------------------------------------------------- low-level io
def _path(table):
    if table not in TABLES:
        raise KeyError(f"unknown table {table!r}; know {sorted(TABLES)}")
    return os.path.join(DATA_DIR, TABLES[table])


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _jsonify(obj):
    """Coerce numpy scalars/arrays and other odds to plain JSON types."""
    if isinstance(obj, dict):
        return {k: _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonify(v) for v in obj]
    if hasattr(obj, "tolist"):            # numpy array / scalar
        return _jsonify(obj.tolist())
    if hasattr(obj, "item") and not isinstance(obj, (str, bytes)):
        try:
            return obj.item()             # numpy scalar -> python scalar
        except (ValueError, AttributeError):
            return obj
    return obj


def append(table, row):
    """Append one row (a dict) to a table as a single JSONL line. Returns the row."""
    _ensure_dir()
    line = json.dumps(_jsonify(row), separators=(",", ":"), sort_keys=True)
    # newline="\n": keep the on-disk form LF so it matches git's normalized blob
    # and snapshot sha256s stay reproducible across checkouts.
    with open(_path(table), "a", encoding="utf-8", newline="\n") as fh:
        fh.write(line + "\n")
    return row


def append_all(table, rows):
    for r in rows:
        append(table, r)
    return len(rows)


def load(table, snapshot=None):
    """All rows from a table (list of dicts). If `snapshot` is given, return
    exactly the rows pinned by that snapshot (first N lines) and verify the
    sha256 matches -- a mismatch means the append-only invariant was violated."""
    p = _path(table)
    if not os.path.exists(p):
        return []
    with open(p, "r", encoding="utf-8") as fh:
        raw = fh.readlines()
    if snapshot is not None:
        snap = load_snapshots().get(snapshot)
        if snap is None or table not in snap:
            raise KeyError(f"snapshot {snapshot!r} does not pin table {table!r}")
        n = snap[table]["lines"]
        raw = raw[:n]
        digest = hashlib.sha256("".join(raw).encode("utf-8")).hexdigest()
        if digest != snap[table]["sha256"]:
            raise ValueError(
                f"snapshot {snapshot!r} table {table!r}: sha256 mismatch -- the "
                f"first {n} lines have changed since the snapshot was taken "
                "(append-only invariant violated).")
    return [json.loads(ln) for ln in raw if ln.strip()]


# ------------------------------------------------------------------ L2 dedup
def l2_key(row):
    return (row.get("wl_hash"), row.get("spec"))


def existing_l2_keys():
    return {l2_key(r) for r in load("topo_labels")}


def append_l2(row, repeat_probe=False):
    """Append an L2 row, refusing to double-label an existing (wl_hash, spec)
    unless it is a designated repeat-probe. Returns ("appended"|"skipped", row)."""
    if not repeat_probe and l2_key(row) in existing_l2_keys():
        return "skipped", row
    if repeat_probe:
        row = dict(row, repeat_probe=True)
    append("topo_labels", row)
    return "appended", row


# ------------------------------------------------------------------ row schema
def git_sha():
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=HERE, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None
    except Exception:
        return None


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _scale(limit):
    """Constraint normalizer -- identical to spec.Spec._scale, reimplemented here
    so the store does not reach into spec's privates."""
    vals = [abs(limit[k]) for k in ("min", "max") if k in limit]
    return max(max(vals) if vals else 1.0, 1.0)


def margins_for(spec, metrics):
    """Per-metric {achieved, required_*, scale, margin, supported} for every hard
    constraint. `margin` is the signed normalized slack (>= 0 iff satisfied): for a
    `max` bound (m-val)/scale-flavoured, for a `min` bound (val-floor)/scale; when
    a metric is missing or unsupported it is flagged and margin is None. This is
    the learning target (00-OVERVIEW R1: predict post-sizing margins, not raw
    metrics), normalized on the same scales the ZOAF objective uses."""
    out = {}
    for name, c in spec.constraints.items():
        supported = c.get("status") != "unsupported"
        val = metrics.get(name) if metrics else None
        scale = _scale(c)
        margin = None
        if supported and val is not None:
            slacks = []
            if "max" in c:
                slacks.append((c["max"] - val) / scale)
            if "min" in c:
                slacks.append((val - c["min"]) / scale)
            margin = min(slacks) if slacks else None   # binding side
        out[name] = {
            "achieved": val,
            "required_min": c.get("min"),
            "required_max": c.get("max"),
            "scale": scale,
            "margin": margin,
            "supported": supported,
        }
    return out


def _graph_summary(topo):
    if topo is None:
        return {"tokens": None, "counts": None, "n_devices": None,
                "n_inductors": None, "inductor_ratio": None}
    return {
        "tokens": list(topo.tokens),
        "counts": topo.counts(),
        "n_devices": topo.n_devices,
        "n_inductors": topo.n_inductors,
        "inductor_ratio": round(topo.inductor_ratio, 6),
    }


def row_l2(spec, metrics, feasible, n_evals, best_x=None, best_params=None,
           best_obj=None, topo=None, wl_hash=None, provenance=None, zoaf_cfg=None):
    """Assemble one L2 row. `provenance` carries source_arm/seed/token_file/
    template_id; `wl_hash` is passed in (the caller already has it) or None for
    reference decks with no token topology."""
    row = {
        "kind": "L2",
        "wl_hash": wl_hash,
        "spec": spec.name,
        "provenance": provenance or {},
        "graph": _graph_summary(topo),
        "metrics": metrics,
        "margins": margins_for(spec, metrics) if metrics is not None else {},
        "feasible": bool(feasible),
        "n_evals": n_evals,
        "best_x": list(best_x) if best_x is not None else None,
        "best_params": best_params,
        "best_obj": best_obj,
        "zoaf_cfg": zoaf_cfg or {},
        "git_sha": git_sha(),
        "ts": _now(),
    }
    return _jsonify(row)


def row_l1(topo, rep, swept, provenance=None):
    """Assemble one L1 row from a bias report + feasibility sweep result."""
    op = (swept or {}).get("op", {}) or {}
    per = (swept or {}).get("per_device", {}) or {}
    row = {
        "kind": "L1",
        "wl_hash": None,   # filled by caller if it has computed it
        "graph": _graph_summary(topo),
        "provenance": provenance or {},
        "n_mos": rep.get("n_mos"),
        "bias_applied": rep.get("bias_applied"),
        "n_bias_nets": len(rep.get("bias_nets", {}) or {}),
        "best_vbg": (swept or {}).get("best_vbg"),
        "n_conducting": (swept or {}).get("n_conducting"),
        "all_conduct": (swept or {}).get("all_conduct"),
        "per_device": per,
        "op": op,                                    # {dev: {id, vds, vdsat, vgs}}
        "drains_no_dc_path": rep.get("drains_no_dc_path"),
        "sources_no_dc_path": rep.get("sources_no_dc_path"),
        "git_sha": git_sha(),
        "ts": _now(),
    }
    return _jsonify(row)


def row_point(wl_hash, spec_name, x, metrics):
    """One ngspice eval inside a ZOAF run (free byproduct)."""
    return _jsonify({"kind": "point", "wl_hash": wl_hash, "spec": spec_name,
                     "x": list(x), "metrics": metrics})


# ------------------------------------------------------------------ snapshots
def load_snapshots():
    p = os.path.join(DATA_DIR, SNAPSHOTS)
    if not os.path.exists(p):
        return {}
    with open(p, "r", encoding="utf-8") as fh:
        return json.load(fh)


def snapshot(name, tables=("topo_labels", "l1_labels")):
    """Pin the current line count + sha256 of each table under `name`, so a
    training set is reproducible. Overwrites a snapshot of the same name (naming
    a v1-train set twice is a user error worth catching loudly)."""
    _ensure_dir()
    snaps = load_snapshots()
    rec = {}
    for table in tables:
        p = _path(table)
        if not os.path.exists(p):
            rec[table] = {"lines": 0, "sha256": hashlib.sha256(b"").hexdigest()}
            continue
        with open(p, "r", encoding="utf-8") as fh:
            raw = fh.read()
        lines = raw.count("\n")
        rec[table] = {"lines": lines,
                      "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest()}
    snaps[name] = rec
    with open(os.path.join(DATA_DIR, SNAPSHOTS), "w", encoding="utf-8") as fh:
        json.dump(snaps, fh, indent=2, sort_keys=True)
    return rec


# ------------------------------------------------------------- family split
def _feature_of(row):
    """WL feature Counter for a row via its stored tokens; None if token-less
    (e.g. a reference-deck anchor row) -- such rows form singleton families."""
    toks = (row.get("graph") or {}).get("tokens")
    if not toks:
        return None
    sys.path.insert(0, HERE)
    from topology import Topology            # lazy: keeps `append` import-light
    from novelty import wl_features
    return wl_features(Topology(toks))[1]


def _families(rows, threshold=FAMILY_SIM):
    """Single-linkage clusters over rows at WL-cosine >= threshold. Returns a
    list of families, each a list of row indices. Token-less rows are singletons.

    Union pairs whose feature vectors exceed the threshold; the corpus is dense
    with near-duplicates so this is what keeps a topology and its 0.99-similar
    twin on the same side of the split (01-DATA §2)."""
    from novelty import wl_cosine
    feats = [_feature_of(r) for r in rows]
    parent = list(range(len(rows)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(len(rows)):
        if feats[i] is None:
            continue
        # exact-duplicate fast path first (cheap, and the common case here)
        for j in range(i + 1, len(rows)):
            if feats[j] is None:
                continue
            if rows[i].get("wl_hash") and rows[i]["wl_hash"] == rows[j].get("wl_hash"):
                union(i, j)
            elif wl_cosine(feats[i], feats[j]) >= threshold:
                union(i, j)
    groups = {}
    for i in range(len(rows)):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def family_split(k_holdout=0.3, table="topo_labels", rows=None,
                 threshold=FAMILY_SIM, seed=0):
    """Split rows into train/val/test by *whole WL-similarity family*.

    `k_holdout` sets the fraction of families held out (split evenly between val
    and test) when < 1, or an explicit family count when >= 1. Assignment is a
    deterministic hash of each family's canonical member (stable across runs and
    independent of row order), so the same store yields the same split.

    Returns {"train": [rows], "val": [rows], "test": [rows],
             "families": [[row,...], ...]} -- consumers get rows, never indices,
    so nobody has to know the table layout.
    """
    if rows is None:
        rows = load(table)
    fams = _families(rows, threshold=threshold)
    # deterministic order: sort families by a stable key, then hash-assign.
    def fam_key(members):
        keys = [str(rows[i].get("wl_hash") or rows[i].get("ts")) for i in members]
        return min(keys)
    fams_sorted = sorted(fams, key=fam_key)
    n_fam = len(fams_sorted)
    k = k_holdout if k_holdout >= 1 else max(1, round(k_holdout * n_fam)) if n_fam else 0
    k = int(min(k, n_fam))
    n_test = (k + 1) // 2
    # rank families by a seeded hash so holdout choice is deterministic but not
    # simply "the first alphabetically".
    def rank(members):
        h = hashlib.blake2b(f"{seed}:{fam_key(members)}".encode(), digest_size=8)
        return h.hexdigest()
    order = sorted(range(n_fam), key=lambda fi: rank(fams_sorted[fi]))
    test_f = set(order[:n_test])
    val_f = set(order[n_test:k])
    out = {"train": [], "val": [], "test": [], "families": []}
    for fi, members in enumerate(fams_sorted):
        frows = [rows[i] for i in members]
        out["families"].append(frows)
        bucket = "test" if fi in test_f else "val" if fi in val_f else "train"
        out[bucket].extend(frows)
    return out


# ------------------------------------------------------------------------ CLI
def _summary():
    print(f"label store at {DATA_DIR}")
    for table in TABLES:
        rows = load(table)
        print(f"  {table:<12} {len(rows):>6} rows  ({_path(table)})")
    l2 = load("topo_labels")
    if l2:
        feas = sum(1 for r in l2 if r.get("feasible"))
        specs = sorted({r.get("spec") for r in l2})
        keys = len(existing_l2_keys())
        print(f"  L2: {feas}/{len(l2)} feasible, {keys} unique (wl_hash,spec) keys, "
              f"specs={specs}")
    snaps = load_snapshots()
    if snaps:
        print(f"  snapshots: {sorted(snaps)}")


def main():
    import argparse
    ap = argparse.ArgumentParser(description="label store inspector")
    ap.add_argument("--summary", action="store_true", help="row counts per table")
    ap.add_argument("--snapshot", metavar="NAME", help="pin a named snapshot")
    ap.add_argument("--split", action="store_true",
                    help="show a family split of topo_labels (leakage check)")
    ap.add_argument("--k-holdout", type=float, default=0.3)
    args = ap.parse_args()
    if args.snapshot:
        rec = snapshot(args.snapshot)
        print(f"snapshot {args.snapshot!r}: " +
              ", ".join(f"{t}={v['lines']}" for t, v in rec.items()))
        return 0
    if args.split:
        sp = family_split(k_holdout=args.k_holdout)
        print(f"families: {len(sp['families'])}  "
              f"train/val/test rows: {len(sp['train'])}/{len(sp['val'])}/{len(sp['test'])}")
        sizes = sorted((len(f) for f in sp["families"]), reverse=True)
        print(f"family sizes (largest first): {sizes[:20]}")
        return 0
    _summary()
    return 0


if __name__ == "__main__":
    sys.exit(main())

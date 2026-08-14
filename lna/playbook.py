"""playbook v0 -- the machine-queryable engineering memory of this program.

Implements `lna/plans2/15-ENGINEER-PROPOSAL.md` SS4.1-N4 ("Memory distillation
v0"), adopting the two schemas SS2 found in the wild rather than inventing one:

  * arXiv:2603.23910 (AnalogAgent) SS2.2 item 1 -- the Self-Evolving-Memory entry
    format `Trigger -> Evidence -> Rule/Patch -> Applicability`, atomic entries,
    **admission-controlled**, **failure-first**, with **verbatim** simulator
    evidence preserved (their measured context-attrition finding: iterative
    refinement decays "singular matrix: check nodes vin and vin" into
    "sim failed" -- so this store never keeps only a summary when the corpus has
    a number or an exact message).
  * github.com/Arcadia-1/analog-agents SS2.1 -- the wiki upgrades: **typed edges**
    (`prevents` / `contradicts` / `derived_from` / `validated`) and the
    **confidence-escalation protocol** (`unverified` -> `verified` only when the
    lesson is re-observed independently).

Retrieval is keyed by (circuit family x analysis x **failure signature**), per
SS5.4 -- "failure-keyed memory collapses 'different circuit, same disease' into
one retrievable lesson" -- not by substring match over prose, and not by
embeddings: `--consult` is deterministic integer scoring so a query is
reproducible under the same frozen-protocol culture as every other number here.

Storage (all under `lna/playbook/`, stdlib JSON only -- no pyyaml):

    entries/<id>.json   one atomic entry per file, append-only in spirit
    edges.jsonl         one typed edge per line
    index.json          REBUILT by this module (`--reindex`); never hand-edited
    seed-v0.json        the distillation input that produced the v0 store
    README.md           schema + admission control + escalation protocol

Append-only spirit: a correction is a NEW entry plus an edge (`contradicts` /
`derived_from`), never a silent edit of an old one. The single sanctioned
mutation is `--escalate`, which promotes confidence `unverified -> verified` and
records the escalation inside the entry with the second, independent source.

Usage:
    python lna/playbook.py --check
    python lna/playbook.py --list [--type diagnosis] [--confidence verified]
    python lna/playbook.py --consult --failure-signature iip3-wall [--top 5]
    python lna/playbook.py --consult --family dhruva --analysis two-tone \\
                           --keywords oip3,swing [--json]
    python lna/playbook.py --add lna/playbook/seed-v0.json
    python lna/playbook.py --link SRC prevents DST [--note "..."]
    python lna/playbook.py --escalate ID --source "JOURNEY stage 41" \\
                           --evidence "<verbatim quote>" --why "..."
    python lna/playbook.py --reindex
"""
import argparse
import json
import os
import re
import sys

try:                                            # entry text is verbatim corpus
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # (dB minus signs,
except Exception:                               # section marks, ohms, ...)
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "playbook")
ENTRY_DIR = os.path.join(ROOT, "entries")
EDGES = os.path.join(ROOT, "edges.jsonl")
INDEX = os.path.join(ROOT, "index.json")

TYPES = ("anti-pattern", "strategy", "corner-lesson", "harness-rule", "diagnosis")
CONFIDENCE = ("unverified", "verified")
EDGE_TYPES = ("prevents", "contradicts", "derived_from", "validated")

ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Canonical on-disk field order (readability; `--check` does not depend on it).
FIELD_ORDER = ("id", "type", "trigger", "evidence", "rule", "applicability",
               "confidence", "sources", "created", "escalations")

# Controlled vocabulary for `trigger.failure_signature` (SS5.4: "failure
# signatures as first-class labels"). Unknown signatures are a NOTE from
# `--check`, not an error -- the program keeps discovering new named walls.
FAILURE_SIGNATURES = (
    "attribution-error", "band-match-wall", "bias-regulation", "copy-migration",
    "coverage-collapse", "device-budget", "era-mismatch", "harness-artefact",
    "iip3-wall", "imbalance", "instrument-perturbation", "label-domain-mismatch",
    "metric-blind-spot", "model-port-mismatch", "move-repertoire", "nf-wall",
    "node-name-drift", "novelty-collapse", "numerical-artefact",
    "objective-omission", "output-swing-wall", "replay-false-confidence",
    "s11-knife-edge", "selector-artefact", "spec-governance", "surrogate-era",
    "topology-exhaustion", "weak-inversion-blindness",
)

# `--consult` scoring weights. Integers on purpose: two runs of the same query
# rank identically, and ties break on id so the order is total.
W_FS_EXACT, W_FS_SUB = 10, 5
W_FAMILY_EXACT, W_FAMILY_ANY = 4, 1
W_ANALYSIS_EXACT, W_ANALYSIS_ANY = 3, 1
W_KW_EXACT, W_KW_SUB = 2, 1
W_TEXT = 1
W_VERIFIED = 1

ANY = "any"                                     # wildcard value inside a trigger


# ---------------------------------------------------------------- io helpers

def _read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")


def _write_entry(entry):
    ordered = {}
    for k in FIELD_ORDER:
        if k in entry:
            ordered[k] = entry[k]
    for k in sorted(entry):                     # anything unexpected still lands
        if k not in ordered:
            ordered[k] = entry[k]
    path = os.path.join(ENTRY_DIR, entry["id"] + ".json")
    os.makedirs(ENTRY_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(ordered, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return path


def entry_paths():
    if not os.path.isdir(ENTRY_DIR):
        return []
    return sorted(os.path.join(ENTRY_DIR, f) for f in os.listdir(ENTRY_DIR)
                  if f.endswith(".json"))


def load_entries():
    out = {}
    for p in entry_paths():
        e = _read_json(p)
        out[e.get("id", os.path.basename(p)[:-5])] = e
    return out


def load_edges():
    if not os.path.exists(EDGES):
        return []
    rows = []
    with open(EDGES, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def append_edge(edge):
    os.makedirs(ROOT, exist_ok=True)
    with open(EDGES, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(edge, ensure_ascii=False, sort_keys=True) + "\n")


def as_list(v):
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return list(v)


# ---------------------------------------------------------------- validation

def validate_entry(entry, stem=None):
    """Return a list of human-readable schema errors ([] == valid)."""
    errs = []

    def bad(msg):
        errs.append(msg)

    eid = entry.get("id")
    if not isinstance(eid, str) or not ID_RE.match(eid or ""):
        bad("id missing or not a kebab slug: %r" % (eid,))
        eid = eid or "<no-id>"
    if stem is not None and eid != stem:
        bad("%s: id does not match filename stem %r" % (eid, stem))

    if entry.get("type") not in TYPES:
        bad("%s: type %r not in %s" % (eid, entry.get("type"), list(TYPES)))

    trig = entry.get("trigger")
    if not isinstance(trig, dict):
        bad("%s: trigger must be an object" % eid)
    else:
        for k in ("family", "analysis", "failure_signature", "keywords"):
            if k not in trig:
                bad("%s: trigger.%s missing" % (eid, k))
        for k in ("family", "analysis", "failure_signature"):
            vals = as_list(trig.get(k))
            if not vals:
                bad("%s: trigger.%s is empty" % (eid, k))
            if any(not isinstance(v, str) or not v.strip() for v in vals):
                bad("%s: trigger.%s has a non-string/blank member" % (eid, k))
        kws = trig.get("keywords")
        if not isinstance(kws, list) or not kws:
            bad("%s: trigger.keywords must be a non-empty list" % eid)
        elif any(not isinstance(v, str) or not v.strip() for v in kws):
            bad("%s: trigger.keywords has a non-string/blank member" % eid)

    ev = entry.get("evidence")
    if not isinstance(ev, list) or not ev:
        bad("%s: evidence must be a non-empty list (failure-first: verbatim "
            "quotes, never a paraphrase where a number or message exists)" % eid)
    else:
        for i, item in enumerate(ev):
            if not isinstance(item, dict):
                bad("%s: evidence[%d] must be an object" % (eid, i))
                continue
            if not str(item.get("quote", "")).strip():
                bad("%s: evidence[%d].quote is empty" % (eid, i))
            if not str(item.get("source", "")).strip():
                bad("%s: evidence[%d].source is empty" % (eid, i))

    rule = entry.get("rule")
    if not isinstance(rule, str) or not rule.strip():
        bad("%s: rule must be a non-empty imperative string" % eid)

    app = entry.get("applicability")
    if not isinstance(app, dict):
        bad("%s: applicability must be an object" % eid)
    else:
        for k in ("applies", "not"):
            if not str(app.get(k, "")).strip():
                bad("%s: applicability.%s is empty" % (eid, k))

    conf = entry.get("confidence")
    if conf not in CONFIDENCE:
        bad("%s: confidence %r not in %s" % (eid, conf, list(CONFIDENCE)))

    src = entry.get("sources")
    if not isinstance(src, list) or not src:
        bad("%s: sources must be non-empty (every rule cites the stages/sims "
            "that ground it, or it poisons the loop)" % eid)
    elif any(not isinstance(s, str) or not s.strip() for s in src):
        bad("%s: sources has a non-string/blank member" % eid)
    elif conf == "verified" and len(set(src)) < 2:
        bad("%s: confidence=verified needs >=2 distinct sources (the "
            "escalation protocol: re-observed independently)" % eid)

    created = entry.get("created")
    if not isinstance(created, str) or not DATE_RE.match(created or ""):
        bad("%s: created must be YYYY-MM-DD, got %r" % (eid, created))

    esc = entry.get("escalations", [])
    if not isinstance(esc, list):
        bad("%s: escalations must be a list" % eid)
    else:
        for i, item in enumerate(esc):
            if not isinstance(item, dict) or not str(item.get("date", "")).strip():
                bad("%s: escalations[%d] needs a date" % (eid, i))

    return errs


def validate_edge(edge, ids, seen):
    errs = []
    src, dst, typ = edge.get("src"), edge.get("dst"), edge.get("type")
    if typ not in EDGE_TYPES:
        errs.append("edge type %r not in %s" % (typ, list(EDGE_TYPES)))
    if src not in ids:
        errs.append("edge src %r has no entry" % (src,))
    if dst not in ids:
        errs.append("edge dst %r has no entry" % (dst,))
    if src == dst:
        errs.append("self-edge on %r" % (src,))
    key = (src, typ, dst)
    if key in seen:
        errs.append("duplicate edge %s -%s-> %s" % (src, typ, dst))
    seen.add(key)
    return errs


# ---------------------------------------------------------------- the index

def build_index():
    entries = load_entries()
    edges = load_edges()
    idx = {
        "schema": "playbook-v0",
        "n_entries": len(entries),
        "n_edges": len(edges),
        "by_type": {},
        "by_confidence": {},
        "by_failure_signature": {},
        "by_family": {},
        "by_analysis": {},
        "by_keyword": {},
        "entries": {},
        "edges": [],
    }
    for eid in sorted(entries):
        e = entries[eid]
        trig = e.get("trigger", {})
        idx["by_type"].setdefault(e.get("type"), []).append(eid)
        idx["by_confidence"].setdefault(e.get("confidence"), []).append(eid)
        for fs in as_list(trig.get("failure_signature")):
            idx["by_failure_signature"].setdefault(fs, []).append(eid)
        for fam in as_list(trig.get("family")):
            idx["by_family"].setdefault(fam, []).append(eid)
        for an in as_list(trig.get("analysis")):
            idx["by_analysis"].setdefault(an, []).append(eid)
        for kw in as_list(trig.get("keywords")):
            idx["by_keyword"].setdefault(kw.lower(), []).append(eid)
        idx["entries"][eid] = {
            "type": e.get("type"),
            "confidence": e.get("confidence"),
            "rule": e.get("rule"),
            "trigger": trig,
            "sources": e.get("sources", []),
        }
    for ed in edges:
        idx["edges"].append({"src": ed.get("src"), "type": ed.get("type"),
                             "dst": ed.get("dst")})
    return idx


def write_index():
    idx = build_index()
    _write_json(INDEX, idx)
    return idx


# ---------------------------------------------------------------- operations

def cmd_add(args):
    doc = _read_json(args.add)
    if isinstance(doc, list):
        new_entries, new_edges = doc, []
    elif isinstance(doc, dict) and ("entries" in doc or "edges" in doc):
        new_entries, new_edges = doc.get("entries", []), doc.get("edges", [])
    elif isinstance(doc, dict):
        new_entries, new_edges = [doc], []
    else:
        print("[add] FAIL: %s is neither an entry, a list, nor {entries,edges}"
              % args.add)
        return 2

    existing = load_entries()
    errs, added, skipped = [], [], []
    staged = {}
    for e in new_entries:
        errs.extend(validate_entry(e))
        eid = e.get("id")
        if eid in staged:
            errs.append("%s: duplicate id inside %s" % (eid, args.add))
        staged[eid] = e
    if errs:
        print("[add] FAIL -- %d schema error(s), nothing written:" % len(errs))
        for m in errs:
            print("  - " + m)
        return 2

    for eid, e in sorted(staged.items()):
        if eid in existing:
            if json.dumps(existing[eid], sort_keys=True) == json.dumps(e, sort_keys=True):
                skipped.append(eid)
                continue
            print("[add] FAIL: %s already exists and differs. The store is "
                  "append-only: file a NEW entry plus a `contradicts`/"
                  "`derived_from` edge, or use --escalate." % eid)
            return 2
        _write_entry(e)
        added.append(eid)

    ids = set(load_entries())
    seen = {(x.get("src"), x.get("type"), x.get("dst")) for x in load_edges()}
    edge_errs, edges_added = [], []
    for ed in new_edges:
        if (ed.get("src"), ed.get("type"), ed.get("dst")) in seen:
            continue
        edge_errs.extend(validate_edge(ed, ids, seen))
        if not edge_errs:
            append_edge(ed)
            edges_added.append(ed)
    if edge_errs:
        print("[add] entries written; EDGE errors:")
        for m in edge_errs:
            print("  - " + m)
        write_index()
        return 2

    idx = write_index()
    print("[add] %s: +%d entries (%d already identical), +%d edges -> %d entries / "
          "%d edges" % (os.path.basename(args.add), len(added), len(skipped),
                        len(edges_added), idx["n_entries"], idx["n_edges"]))
    return 0


def score_entry(entry, q):
    """Deterministic integer score of `entry` against query dict `q`."""
    trig = entry.get("trigger", {})
    score, why = 0, []

    e_fs = [s.lower() for s in as_list(trig.get("failure_signature"))]
    for want in q["failure_signature"]:
        if want in e_fs:
            score += W_FS_EXACT
            why.append("fs=%s" % want)
        else:
            for have in e_fs:
                if have != ANY and (want in have or have in want):
                    score += W_FS_SUB
                    why.append("fs~%s" % have)
                    break

    e_fam = [s.lower() for s in as_list(trig.get("family"))]
    for want in q["family"]:
        if want in e_fam:
            score += W_FAMILY_EXACT
            why.append("family=%s" % want)
        elif ANY in e_fam:
            score += W_FAMILY_ANY
            why.append("family=any")

    e_an = [s.lower() for s in as_list(trig.get("analysis"))]
    for want in q["analysis"]:
        if want in e_an:
            score += W_ANALYSIS_EXACT
            why.append("analysis=%s" % want)
        elif ANY in e_an:
            score += W_ANALYSIS_ANY
            why.append("analysis=any")

    e_kw = [s.lower() for s in as_list(trig.get("keywords"))]
    blob = " ".join([entry.get("rule", "")] + e_kw + e_fs + e_fam + e_an).lower()
    for want in q["keywords"]:
        if want in e_kw:
            score += W_KW_EXACT
            why.append("kw=%s" % want)
        elif any(want in k for k in e_kw):
            score += W_KW_SUB
            why.append("kw~%s" % want)
        elif want in blob:
            score += W_TEXT
            why.append("text~%s" % want)

    if entry.get("confidence") == "verified":
        score += W_VERIFIED
    return score, why


def cmd_consult(args):
    q = {
        "failure_signature": [s.strip().lower()
                              for s in (args.failure_signature or "").split(",") if s.strip()],
        "family": [s.strip().lower() for s in (args.family or "").split(",") if s.strip()],
        "analysis": [s.strip().lower() for s in (args.analysis or "").split(",") if s.strip()],
        "keywords": [s.strip().lower() for s in (args.keywords or "").split(",") if s.strip()],
    }
    if not any(q.values()):
        print("[consult] give at least one of --failure-signature / --family / "
              "--analysis / --keywords")
        return 2

    hits = []
    for eid, e in sorted(load_entries().items()):
        if args.type and e.get("type") != args.type:
            continue
        if args.confidence and e.get("confidence") != args.confidence:
            continue
        s, why = score_entry(e, q)
        if s > (W_VERIFIED if e.get("confidence") == "verified" else 0):
            hits.append((-s, eid, e, why))
    hits.sort(key=lambda r: (r[0], r[1]))
    hits = hits[:args.top]

    if args.json:
        print(json.dumps([{
            "id": eid, "score": -ns, "matched": why, "type": e["type"],
            "confidence": e["confidence"], "rule": e["rule"],
            "applicability": e["applicability"], "sources": e["sources"],
            "evidence": e["evidence"],
        } for ns, eid, e, why in hits], ensure_ascii=False, indent=2))
        return 0

    print("[consult] query: " + "; ".join("%s=%s" % (k, ",".join(v))
                                          for k, v in sorted(q.items()) if v))
    if not hits:
        print("  (no entry matches -- this is a gap in the memory, not a "
              "licence to guess)")
        return 0
    for ns, eid, e, why in hits:
        print("\n  [%2d] %s  (%s, %s)" % (-ns, eid, e["type"], e["confidence"]))
        print("       matched: " + ", ".join(why))
        print("       RULE: " + e["rule"])
        print("       APPLIES: " + e["applicability"]["applies"])
        print("       NOT: " + e["applicability"]["not"])
        ev = e["evidence"][0]
        print("       EVIDENCE (%s): %s" % (ev["source"], ev["quote"]))
        print("       SOURCES: " + " | ".join(e["sources"]))
    return 0


def cmd_link(args):
    src, typ, dst = args.link
    edge = {"src": src, "type": typ, "dst": dst}
    if args.note:
        edge["note"] = args.note
    ids = set(load_entries())
    seen = {(x.get("src"), x.get("type"), x.get("dst")) for x in load_edges()}
    errs = validate_edge(edge, ids, seen)
    if errs:
        print("[link] FAIL:")
        for m in errs:
            print("  - " + m)
        return 2
    append_edge(edge)
    write_index()
    print("[link] %s -%s-> %s" % (src, typ, dst))
    return 0


def cmd_escalate(args):
    entries = load_entries()
    e = entries.get(args.escalate)
    if e is None:
        print("[escalate] FAIL: no entry %r" % args.escalate)
        return 2
    if e.get("confidence") == "verified":
        print("[escalate] FAIL: %s is already verified (escalation is "
              "one-way and one-time)" % args.escalate)
        return 2
    if not args.source:
        print("[escalate] FAIL: --source is required -- the whole protocol is "
              "that a second, INDEPENDENT observation is named")
        return 2
    if args.source in e.get("sources", []):
        print("[escalate] FAIL: %r is already a source of this entry; "
              "re-observation must be independent" % args.source)
        return 2
    if not args.evidence:
        print("[escalate] FAIL: --evidence is required and must be VERBATIM "
              "(a number or an exact message, never a summary)")
        return 2

    e.setdefault("evidence", []).append({"quote": args.evidence,
                                         "source": args.source})
    e.setdefault("sources", []).append(args.source)
    e.setdefault("escalations", []).append({
        "date": args.date, "to": "verified", "source": args.source,
        "why": args.why or "re-observed independently",
    })
    e["confidence"] = "verified"
    errs = validate_entry(e, stem=args.escalate)
    if errs:
        print("[escalate] FAIL -- result would be invalid:")
        for m in errs:
            print("  - " + m)
        return 2
    _write_entry(e)
    write_index()
    print("[escalate] %s: unverified -> verified (second source: %s)"
          % (args.escalate, args.source))
    return 0


def cmd_list(args):
    entries = load_entries()
    rows = []
    for eid in sorted(entries):
        e = entries[eid]
        if args.type and e.get("type") != args.type:
            continue
        if args.confidence and e.get("confidence") != args.confidence:
            continue
        rows.append((eid, e))
    by_type, by_conf = {}, {}
    for eid, e in rows:
        by_type[e.get("type")] = by_type.get(e.get("type"), 0) + 1
        by_conf[e.get("confidence")] = by_conf.get(e.get("confidence"), 0) + 1
    w = max([len(r[0]) for r in rows] + [4])
    for eid, e in rows:
        print("%-*s  %-13s %-10s %s" % (w, eid, e.get("type"),
                                        e.get("confidence"), e.get("rule")))
    print("\n%d entries | by type: %s | by confidence: %s | edges: %d"
          % (len(rows),
             ", ".join("%s %d" % kv for kv in sorted(by_type.items())),
             ", ".join("%s %d" % kv for kv in sorted(by_conf.items())),
             len(load_edges())))
    return 0


def cmd_check(args):
    errs, notes = [], []

    if not os.path.isdir(ENTRY_DIR):
        print("[check] FAIL: %s does not exist" % ENTRY_DIR)
        return 2

    seen_ids = {}
    entries = {}
    for p in entry_paths():
        stem = os.path.basename(p)[:-5]
        try:
            e = _read_json(p)
        except Exception as exc:                              # noqa: BLE001
            errs.append("%s: not valid JSON (%s)" % (stem, exc))
            continue
        errs.extend(validate_entry(e, stem=stem))
        eid = e.get("id")
        if eid in seen_ids:
            errs.append("duplicate id %r in %s and %s" % (eid, seen_ids[eid], stem))
        seen_ids[eid] = stem
        entries[eid] = e
        for fs in as_list(e.get("trigger", {}).get("failure_signature")):
            if fs not in FAILURE_SIGNATURES and fs != ANY:
                notes.append("%s: failure_signature %r is outside the "
                             "controlled vocabulary" % (eid, fs))

    ids, seen_edges = set(entries), set()
    edges = []
    try:
        edges = load_edges()
    except Exception as exc:                                  # noqa: BLE001
        errs.append("edges.jsonl: not valid JSONL (%s)" % exc)
    for ed in edges:
        errs.extend(validate_edge(ed, ids, seen_edges))

    # index must be a pure function of entries+edges
    if not os.path.exists(INDEX):
        errs.append("index.json missing (run --reindex)")
    else:
        want = build_index()
        have = _read_json(INDEX)
        if json.dumps(want, sort_keys=True, ensure_ascii=False) != \
           json.dumps(have, sort_keys=True, ensure_ascii=False):
            errs.append("index.json is stale (run --reindex)")

    # self-test of the retrieval path itself: the demo query in the README
    # must return the D5 wall entries, verified-first.
    if "iip3-output-swing-wall" in entries:
        q = {"failure_signature": ["iip3-wall"], "family": [], "analysis": [],
             "keywords": []}
        ranked = sorted(((-score_entry(e, q)[0], i) for i, e in entries.items()
                         if score_entry(e, q)[0] > 1))
        if not ranked or ranked[0][1] != "iip3-output-swing-wall":
            errs.append("retrieval self-test: failure_signature=iip3-wall did "
                        "not rank iip3-output-swing-wall first (got %r)"
                        % (ranked[0][1] if ranked else None))

    n_ver = sum(1 for e in entries.values() if e.get("confidence") == "verified")
    print("[check] %d entries (%d verified / %d unverified), %d edges, "
          "%d failure signatures in use"
          % (len(entries), n_ver, len(entries) - n_ver, len(edges),
             len({fs for e in entries.values()
                  for fs in as_list(e.get("trigger", {}).get("failure_signature"))})))
    for m in notes:
        print("  NOTE: " + m)
    if errs:
        print("[check] FAIL -- %d error(s):" % len(errs))
        for m in errs:
            print("  - " + m)
        return 1
    print("[check] GREEN -- schema valid, ids unique, edge endpoints exist, "
          "sources non-empty, index in sync, retrieval self-test passes")
    return 0


def cmd_reindex(args):
    idx = write_index()
    print("[reindex] %d entries, %d edges -> %s"
          % (idx["n_entries"], idx["n_edges"], os.path.relpath(INDEX, HERE)))
    return 0


# ---------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="playbook v0 -- machine-queryable engineering memory "
                    "(plans2/15-ENGINEER-PROPOSAL.md SS4.1-N4)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--add", metavar="FILE",
                   help="add entries (and optional edges) from a JSON file")
    g.add_argument("--consult", action="store_true",
                   help="query by trigger fields; deterministic integer scoring")
    g.add_argument("--link", nargs=3, metavar=("SRC", "TYPE", "DST"),
                   help="add a typed edge: %s" % "|".join(EDGE_TYPES))
    g.add_argument("--escalate", metavar="ID",
                   help="promote confidence unverified -> verified")
    g.add_argument("--list", action="store_true", help="list entries")
    g.add_argument("--check", action="store_true",
                   help="self-test / validate the whole store")
    g.add_argument("--reindex", action="store_true", help="rebuild index.json")

    ap.add_argument("--failure-signature", help="consult: comma-separated")
    ap.add_argument("--family", help="consult: comma-separated circuit families")
    ap.add_argument("--analysis", help="consult: comma-separated analysis kinds")
    ap.add_argument("--keywords", help="consult: comma-separated keywords")
    ap.add_argument("--top", type=int, default=6, help="consult: max hits")
    ap.add_argument("--json", action="store_true", help="consult: JSON output")
    ap.add_argument("--type", choices=TYPES, help="filter by entry type")
    ap.add_argument("--confidence", choices=CONFIDENCE, help="filter by confidence")
    ap.add_argument("--note", help="link: free-text note on the edge")
    ap.add_argument("--source", help="escalate: the second, independent source")
    ap.add_argument("--evidence", help="escalate: VERBATIM quote from it")
    ap.add_argument("--why", help="escalate: why it is independent")
    ap.add_argument("--date", default="2026-08-14", help="escalate: date stamp")

    args = ap.parse_args(argv)
    if args.add:
        return cmd_add(args)
    if args.consult:
        return cmd_consult(args)
    if args.link:
        return cmd_link(args)
    if args.escalate:
        return cmd_escalate(args)
    if args.list:
        return cmd_list(args)
    if args.check:
        return cmd_check(args)
    if args.reindex:
        return cmd_reindex(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())

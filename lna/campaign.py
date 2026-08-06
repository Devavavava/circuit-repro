"""Nightly labeling campaign (plans2/01-DATA §5).

Turns idle overnight compute into L2 labels. Picks a stratified quota, sizes each
`(topology, spec)` once, logs the row (dedup-aware), and writes a morning report.
The store is the product; this is the thing that fills it toward Gate C0's
"≥150 L2 rows, ≥25% stratum T, 3 nights unattended".

Strata (01-DATA §5), each a *source* of sizing tasks:

  T  templates / references  -- topology diversity + the feasible class. Right now:
                                the hand reference decks (ref24_tapped is the
                                gain-capable/matched archetype, Gate G4). The full
                                P5 `templates.py` archetype generator is the lever
                                that grows this to the 25% target -- not built yet.
  G  generated               -- P1/P2 arm topologies in lna/out/*/seq*.txt,
                                screen+L1-passing, WL-deduped vs the store. NOTE the
                                seq*.txt are gitignored, so in a fresh worktree they
                                are absent (regenerate via finetune.py --do sample,
                                or run the campaign in the main checkout).
  M  mutations               -- 1-edit variants of labeled topologies (03-SEARCH §3
                                move set). Not built yet; yields nothing today.
  R  repeat-probes           -- re-size already-labeled keys with a *fresh seed* to
                                measure ZOAF label noise sigma. sigma is the model's
                                accuracy floor and sets the rank-loss margin.

v1 is **sequential** (one ngspice at a time): robust and unattended-safe, no
concurrent-writer risk, ~3-5 min/label. Parallelism (per-job isolated stores +
merge) is the documented v2 speedup; a night of ~30 labels still fits overnight.

    python lna/campaign.py --dry-run            # show the pick, size nothing
    python lna/campaign.py --night --limit 4    # size a few (testing)
    python lna/campaign.py --night              # a full night's quota
"""
import argparse
import glob
import os
import statistics
import sys
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import datastore as ds  # noqa: E402

# default per-night quota (01-DATA §5); scaled down by --limit for testing.
QUOTA = {"T": 20, "G": 20, "M": 10, "R": 3}
REFERENCE_DECKS = ["ref24_tapped.cir", "ref24_csdeg.cir", "ref24_cg.cir"]
REPORT_DIR = os.path.join(HERE, "data", "reports")


# --------------------------------------------------------------- task sources
def _labeled_corpus_indices(spec_name):
    """Corpus indices already labeled vs spec (repeat-probe candidates)."""
    out = []
    for r in ds.load("topo_labels"):
        p = r.get("provenance") or {}
        if r.get("spec") == spec_name and p.get("source_arm") == "corpus" \
                and p.get("index") is not None:
            out.append(p["index"])
    return sorted(set(out))


def _generated_tasks(spec, spec_name, quota, done_keys, gen_glob):
    """Screen+novel+WL-unique generated topologies not yet labeled vs spec."""
    from topology import Topology, parse_arrow_file
    from novelty import wl_features, corpus_reference
    corpus_hashes, _ = corpus_reference()
    seen, tasks = set(), []
    for f in sorted(glob.glob(gen_glob)):
        try:
            topo = Topology(parse_arrow_file(f))
        except Exception:
            continue
        if not spec.structural_screen(topo)[0]:
            continue
        h = wl_features(topo)[0]
        if h in seen or h in corpus_hashes or (h, spec_name) in done_keys:
            continue
        seen.add(h)
        tasks.append({"stratum": "G", "kind": "topo", "ref": f, "index": None,
                      "spec": spec_name, "seed": 1, "repeat_probe": False})
        if len(tasks) >= quota:
            break
    return tasks


def pick_quota(spec_name="wifi24", quota=None, gen_glob=None):
    """Build the night's task list across strata, skipping already-labeled keys."""
    sys.path.insert(0, HERE)
    from spec import Spec
    spec = Spec.load(spec_name)
    quota = quota or QUOTA
    gen_glob = gen_glob or os.path.join(HERE, "out", "*", "seq*.txt")
    done = ds.existing_l2_keys()
    tasks = []

    # T -- reference decks not yet labeled vs spec
    for deck in REFERENCE_DECKS:
        if (f"ref:{deck}", spec_name) in done:
            continue
        tasks.append({"stratum": "T", "kind": "ref", "ref": deck, "index": None,
                      "spec": spec_name, "seed": 1, "repeat_probe": False})
        if sum(t["stratum"] == "T" for t in tasks) >= quota["T"]:
            break

    # G -- generated arms (empty if seq*.txt absent, e.g. fresh worktree)
    tasks += _generated_tasks(spec, spec_name, quota["G"], done, gen_glob)

    # M -- mutations: not built yet (03-SEARCH move set). Placeholder for the quota.

    # R -- repeat-probes: re-size labeled corpus keys with a fresh seed. Skip keys
    # already probed so re-running a night does not pile up duplicate repeats.
    probed = {(r.get("provenance") or {}).get("index")
              for r in ds.load("topo_labels")
              if (r.get("provenance") or {}).get("source_arm") == "campaign-R"}
    r_cands = [i for i in _labeled_corpus_indices(spec_name) if i not in probed]
    for i, idx in enumerate(r_cands[:quota["R"]]):
        tasks.append({"stratum": "R", "kind": "corpus", "ref": None, "index": idx,
                      "spec": spec_name, "seed": 2 + i, "repeat_probe": True})
    return tasks


# ------------------------------------------------------------------- sizing
def _size_task(t):
    """Size one task; return a result dict (metrics/feasible/n_evals) or None."""
    import size
    spec_sized = size._spec_for_sizing(t["spec"])
    if t["kind"] == "ref":
        sizable, fixed, recipe = _ref_sizing(t["ref"])
        feas, m = size._size_ref(t["ref"], sizable, fixed, t["spec"], recipe,
                                 f"campaign {t['ref']}", seed=t["seed"], log=True)
        return {"feasible": feas, "metrics": m}
    if t["kind"] == "corpus":
        from bias import topo_from_index
        topo = topo_from_index(t["index"])
    else:  # topo from a token file
        from topology import Topology, parse_arrow_file
        topo = Topology(parse_arrow_file(t["ref"]))
    prov = {"source_arm": "campaign-" + t["stratum"], "seed": t["seed"]}
    if t["index"] is not None:
        prov["index"] = t["index"]
    else:
        prov["token_file"] = os.path.relpath(t["ref"], HERE).replace("\\", "/")
    return size.size_topology(topo, spec_sized, seed=t["seed"], inductor_q=12,
                              provenance=prov, log=True,
                              repeat_probe=t["repeat_probe"])


def _ref_sizing(deck):
    """The sizable/fixed maps for a reference deck (mirrors size.py's wrappers)."""
    common = {"pL": "45n", "pRB": "10k", "pQ": "10", "pF0": "2.442e9",
              "pRq": "{2*3.14159265*pF0*pLd/pQ}"}
    if deck == "ref24_tapped.cir":
        return ({"pW": "W", "pLd": "L", "pCt2": "C", "pVB": "VB", "pVB2": "VB"},
                dict(common, pLs="1.35n", pLg="8n", pCex="440f", pCt1="0.3p"),
                "tapped-v1")
    if deck == "ref24_csdeg.cir":
        return ({"pW": "W", "pLs": "L", "pLg": "L", "pLd": "L", "pCex": "C",
                 "pCtnk": "C", "pVB": "VB", "pVB2": "VB"}, common, "anchor-v1")
    # ref24_cg.cir: common-gate match anchor. Gain is ~0 dB by construction
    # (50 ohm port caps a matched CG at gm*50; finding R2), so this labels as a
    # valid *infeasible* T row -- archetype diversity, not a G4 candidate. All of
    # the deck's non-sized params must be re-declared (body_of strips .param).
    return ({"pW": "W", "pVB": "VB"},
            {"pL": "45n", "pRL": "300", "pIB": "2.4m", "pF0": "2.442e9"}, "cg-v1")


# ------------------------------------------------------------------- report
def _sigma_from_repeats():
    """sigma(S21) over repeat-probe rows sharing a (wl_hash, spec) key."""
    by_key = defaultdict(list)
    for r in ds.load("topo_labels"):
        m = r.get("metrics") or {}
        if m.get("s21_db") is not None:
            by_key[(r.get("wl_hash"), r.get("spec"))].append(m["s21_db"])
    sigmas = [statistics.pstdev(v) for v in by_key.values() if len(v) >= 2]
    return (statistics.mean(sigmas), len(sigmas)) if sigmas else (None, 0)


def write_report(tasks, results, spec_name):
    os.makedirs(REPORT_DIR, exist_ok=True)
    path = os.path.join(REPORT_DIR, f"{date.today().isoformat()}.md")
    per = defaultdict(lambda: [0, 0, 0])   # stratum -> [attempted, sized, feasible]
    for t, res in zip(tasks, results):
        s = per[t["stratum"]]
        s[0] += 1
        if res and res.get("metrics"):
            s[1] += 1
            s[2] += int(res.get("feasible"))
    sigma, n_sig = _sigma_from_repeats()
    total = ds.load("topo_labels")
    lines = [f"# campaign {date.today().isoformat()} — spec {spec_name}", "",
             f"store now: **{len(total)} L2 rows**, "
             f"{sum(r['feasible'] for r in total)} feasible", "",
             "| stratum | attempted | sized | feasible |",
             "|---|---|---|---|"]
    for s in ("T", "G", "M", "R"):
        a, sz, fe = per.get(s, [0, 0, 0])
        lines.append(f"| {s} | {a} | {sz} | {fe} |")
    lines += ["",
              f"repeat-probe sigma(S21): "
              + (f"**{sigma:.3f} dB** over {n_sig} keys "
                 f"(expect ≲0.5; larger => label budget too small)"
                 if sigma is not None else "not enough repeats yet"),
              "",
              "notes: G empty here means no seq*.txt in this checkout (gitignored);"
              " full stratum T awaits templates.py (P5); M awaits the mutation"
              " move set (03-SEARCH §3)."]
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return path, sigma, n_sig


# ------------------------------------------------------------------------ CLI
def run_night(spec_name="wifi24", limit=None, dry_run=False, quota=None,
              gen_glob=None):
    tasks = pick_quota(spec_name, quota=quota, gen_glob=gen_glob)
    if limit:
        # keep the stratum mix under a small limit: round-robin by stratum
        by = defaultdict(list)
        for t in tasks:
            by[t["stratum"]].append(t)
        trimmed, i = [], 0
        while len(trimmed) < limit and any(by.values()):
            for s in ("T", "R", "G", "M"):
                if by[s]:
                    trimmed.append(by[s].pop(0))
                    if len(trimmed) >= limit:
                        break
        tasks = trimmed
    counts = defaultdict(int)
    for t in tasks:
        counts[t["stratum"]] += 1
    print(f"campaign {date.today().isoformat()} spec={spec_name}: "
          f"{len(tasks)} tasks {dict(counts)}")
    for t in tasks:
        tag = t["ref"] if t["kind"] != "corpus" else f"corpus {t['index']}"
        print(f"  [{t['stratum']}] {t['kind']:<6} {tag} seed={t['seed']}"
              + (" (repeat-probe)" if t["repeat_probe"] else ""))
    if dry_run:
        print("\n--dry-run: sized nothing.")
        return 0
    results = []
    for t in tasks:
        try:
            results.append(_size_task(t))
        except Exception as e:
            print(f"  [{t['stratum']}] FAILED: {e}")
            results.append(None)
    path, sigma, n_sig = write_report(tasks, results, spec_name)
    print(f"\nmorning report: {path}")
    if sigma is not None:
        print(f"repeat-probe sigma(S21) = {sigma:.3f} dB over {n_sig} keys")
    return 0


def main():
    ap = argparse.ArgumentParser(description="nightly labeling campaign (01-DATA §5)")
    ap.add_argument("--night", action="store_true", help="run a night's quota")
    ap.add_argument("--dry-run", action="store_true", help="print the pick, size nothing")
    ap.add_argument("--spec", default="wifi24")
    ap.add_argument("--limit", type=int, help="cap tasks (testing)")
    ap.add_argument("--gen-glob", help="override the generated-topology glob")
    args = ap.parse_args()
    if not (args.night or args.dry_run):
        ap.error("give --night or --dry-run")
    return run_night(args.spec, limit=args.limit, dry_run=args.dry_run,
                     gen_glob=args.gen_glob)


if __name__ == "__main__":
    sys.exit(main())

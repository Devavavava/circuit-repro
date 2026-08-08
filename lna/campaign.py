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
import json
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
TEMPLATE_DIR = os.path.join(HERE, "out", "templates")   # templates.py --emit-dir
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


def _template_tasks(spec_name, quota, done_keys, tmpl_dir=TEMPLATE_DIR):
    """P5 archetypes (templates.py) matching this spec, not yet labeled. Stratum T
    -- topology diversity + the near-feasible/gain-capable class (tapped family)."""
    metaf = os.path.join(tmpl_dir, "meta.json")
    if not os.path.exists(metaf):
        return []
    meta = json.load(open(metaf, encoding="utf-8")).get("meta", [])
    tasks = []
    for m in meta:
        if m.get("spec") != spec_name or (m.get("wl_hash"), spec_name) in done_keys:
            continue
        tasks.append({"stratum": "T", "kind": "topo",
                      "ref": os.path.join(tmpl_dir, m["file"]), "index": None,
                      "spec": spec_name, "seed": 1, "repeat_probe": False})
        if len(tasks) >= quota:
            break
    return tasks


def _generated_tasks(spec, spec_name, quota, done_keys, gen_glob):
    """Screen+novel+WL-unique generated topologies not yet labeled vs spec."""
    from topology import Topology, parse_arrow_file
    from novelty import wl_features, corpus_reference
    corpus_hashes, _ = corpus_reference()
    seen, tasks = set(), []
    for f in sorted(glob.glob(gen_glob)):
        if os.path.basename(os.path.dirname(f)) == "templates":
            continue                              # templates are stratum T, not G
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

    # T -- reference decks + P5 templates, not yet labeled vs spec
    for deck in REFERENCE_DECKS:
        if (f"ref:{deck}", spec_name) in done:
            continue
        tasks.append({"stratum": "T", "kind": "ref", "ref": deck, "index": None,
                      "spec": spec_name, "seed": 1, "repeat_probe": False})
    remaining_t = max(0, quota["T"] - sum(t["stratum"] == "T" for t in tasks))
    tasks += _template_tasks(spec_name, remaining_t, done)

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
def sigma_key(row):
    """The label-domain key a repeat-probe sigma may be averaged over.

    ⚠ This used to be just `(wl_hash, spec)`, and that was WRONG -- it pooled rows
    produced by *different recipes* (candidate-v1 / curated-v1 / polish-v1 /
    blind-v1 / the p5v5-p5v6 generator scans) and by *different NF gating*, which
    are deliberate label-domain differences, not seed noise. 81 of the 89 multi-row
    keys in the store are mixed that way, so the reported "sigma drift"
    0.32 -> 1.02 -> 1.27 was measuring recipe churn as if it were label noise.
    Conditioning on (recipe, nf_gated) is the same rule 01-DATA already applies to
    training: never pool two label domains silently."""
    z = row.get("zoaf_cfg") or {}
    return (row.get("wl_hash"), row.get("spec"), z.get("recipe"),
            bool(z.get("nf_gated")))


def _sigma_from_repeats(recipe=None, rows=None, snapshot=None):
    """sigma(S21) over rows sharing a full label-domain key (see `sigma_key`).

    `recipe` restricts to one recipe -- e.g. `candidate-v1` for the historical
    single-seed number, `candidate-v1+bo3` for the best-of-3 protocol (06-LAST-MILE
    §4). `snapshot` pins the population: an eval run against a snapshot must use
    the sigma measured *inside* that snapshot, or its rank-hinge margin (and hence
    its numbers) drift every time the store grows. Returns (mean sigma, n keys)."""
    by_key = defaultdict(list)
    for r in (ds.load("topo_labels", snapshot=snapshot) if rows is None else rows):
        m = r.get("metrics") or {}
        if m.get("s21_db") is None:
            continue
        k = sigma_key(r)
        if recipe is not None and k[2] != recipe:
            continue
        by_key[k].append(m["s21_db"])
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
    sigma, n_sig = _sigma_from_repeats(recipe="candidate-v1")
    sigma_bo, n_bo = _sigma_from_repeats(recipe="candidate-v1+bo3")
    total = ds.load("topo_labels")
    lines = [f"# campaign {date.today().isoformat()} — spec {spec_name}", "",
             f"store now: **{len(total)} L2 rows**, "
             f"{sum(r['feasible'] for r in total)} feasible", "",
             "| stratum | attempted | sized | feasible |",
             "|---|---|---|---|"]
    for s in ("T", "G", "M", "R"):
        a, sz, fe = per.get(s, [0, 0, 0])
        lines.append(f"| {s} | {a} | {sz} | {fe} |")
    notes = ["M awaits the mutation move set (03-SEARCH §3)"]
    if per.get("G", [0])[0] == 0:
        notes.insert(0, "stratum G had no tasks (no seq*.txt in this checkout — "
                        "gitignored; pass --gen-glob at the main checkout)")
    if not os.path.exists(os.path.join(TEMPLATE_DIR, "meta.json")):
        notes.insert(0, "stratum T thin (no templates.py output yet)")
    lines += ["",
              "repeat-probe sigma(S21), per label domain (recipes are never "
              "pooled -- see `sigma_key`):",
              f"- single-seed `candidate-v1`: "
              + (f"**{sigma:.3f} dB** over {n_sig} keys"
                 if sigma is not None else "not enough repeats yet"),
              f"- best-of-3 `candidate-v1+bo3`: "
              + (f"**{sigma_bo:.3f} dB** over {n_bo} keys (06-LAST-MILE §4 target "
                 "≲0.5)" if sigma_bo is not None else "not measured yet"),
              "", "notes: " + "; ".join(notes) + "."]
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return path, sigma, n_sig


# ------------------------------------------------------- sigma probe (06 §4)
def _probe_keys(spec_name, arms=("corpus", "campaign-R")):
    """The repeat-probe population: {wl_hash: corpus index} for keys that already
    carry >=2 single-seed `candidate-v1` labels, i.e. the exact keys the historical
    sigma(S21) was measured over."""
    seen = {}
    for r in ds.load("topo_labels"):
        p = r.get("provenance") or {}
        z = r.get("zoaf_cfg") or {}
        if (r.get("spec") == spec_name and p.get("source_arm") in arms
                and p.get("index") is not None and z.get("recipe") == "candidate-v1"):
            seen.setdefault(r["wl_hash"], p["index"])
    return seen


def _gen_probe_keys(spec_name, limit=None):
    """The *generated* probe population: {wl_hash: token file} for the near-feasible
    `campaign-G` rows, ranked by how close they got.

    The corpus keys measure label noise on circuits the pipeline did not design;
    these measure it where it actually costs -- the generated pool is the critic's
    source-shift test set and search's candidate stream, so its label noise caps
    every rho reported against it."""
    from spec import Spec
    sp = Spec.load(spec_name)
    best = {}
    for r in ds.load("topo_labels"):
        p, z = r.get("provenance") or {}, r.get("zoaf_cfg") or {}
        tf, m = p.get("token_file"), r.get("metrics")
        if (r.get("spec") != spec_name or p.get("source_arm") != "campaign-G"
                or not tf or not m or z.get("recipe") != "candidate-v1"):
            continue
        feas, viol = sp.feasible(m)
        v = sum(viol.values()) if viol else 0.0
        if r["wl_hash"] not in best or v < best[r["wl_hash"]][0]:
            best[r["wl_hash"]] = (v, os.path.join(HERE, tf))
    order = sorted(best.items(), key=lambda kv: kv[1][0])[:limit]
    return {h: f for h, (_v, f) in order}


def run_sigma_probe(spec_name="wifi24", k=3, reps=2, seed0=11, limit=None,
                    inductor_q=12, log=True, generated=False):
    """Measure sigma(S21) under the best-of-k label definition (06-LAST-MILE §4).

    For each repeat-probe key, run `reps` INDEPENDENT best-of-k labels on disjoint
    seed blocks (k*reps sizings). Two numbers come out of the same sims:

      sigma_single -- spread of all k*reps individual runs (the old label noise,
                      now measured on many more samples per key), and
      sigma_bo{k}  -- spread of the `reps` best-of-k labels: the noise the critic
                      actually sees once best-of-k *is* the label.

    Every best-of-k label is appended to the store (repeat-probe rows, recipe
    `candidate-v1+bo{k}`), so `_sigma_from_repeats('candidate-v1+bo3')` recomputes
    this from the store without re-simulating."""
    sys.path.insert(0, HERE)
    import size
    from bias import topo_from_index
    from topology import Topology, parse_arrow_file
    spec = size._spec_for_sizing(spec_name)
    if generated:
        items = list(_gen_probe_keys(spec_name, limit=limit).items())
    else:
        items = sorted(_probe_keys(spec_name).items(), key=lambda kv: kv[1])[:limit]
    print(f"sigma probe: spec={spec_name} stratum={'G' if generated else 'corpus'} "
          f"keys={len(items)} best-of-{k} x {reps} reps = {len(items) * k * reps} "
          f"sizings (nf_gated={size.nf_is_gated(spec)})")
    per_key = []
    for h, idx in items:
        topo = (Topology(parse_arrow_file(idx)) if generated
                else topo_from_index(idx))
        labels, allruns = [], []
        for rep in range(reps):
            seeds = tuple(seed0 + rep * k + i for i in range(k))
            prov = {"source_arm": "sigma-probe", "inductor_q": inductor_q,
                    "rep": rep, "stratum": "G" if generated else "corpus"}
            prov["token_file" if generated else "index"] = (
                os.path.relpath(idx, HERE).replace("\\", "/") if generated else idx)
            res = size.size_best_of_k(
                topo, spec, seeds=seeds, inductor_q=inductor_q, log=log,
                repeat_probe=True, provenance=prov)
            if not res:
                continue
            labels.append(res["metrics"]["s21_db"])
            allruns += res["seed_metrics"].get("s21_db", [])
        if len(allruns) >= 2:
            s_single = statistics.pstdev(allruns)
            s_bok = statistics.pstdev(labels) if len(labels) >= 2 else None
            per_key.append({"wl_hash": h, "index": str(idx), "sigma_single": s_single,
                            "sigma_bok": s_bok, "labels": labels, "runs": allruns})
            print(f"  {os.path.basename(str(idx)):>14}: single sd {s_single:5.3f} | bo{k} sd "
                  + (f"{s_bok:5.3f}" if s_bok is not None else "  n/a ")
                  + f" | labels {[round(x, 2) for x in labels]}")
    if not per_key:
        print("no keys probed")
        return None
    ms = statistics.mean([p["sigma_single"] for p in per_key])
    bo = [p["sigma_bok"] for p in per_key if p["sigma_bok"] is not None]
    mb = statistics.mean(bo) if bo else None
    print(f"\nsigma(S21) over {len(per_key)} keys: single-seed {ms:.3f} dB"
          + (f"  ->  best-of-{k} {mb:.3f} dB" if mb is not None else ""))
    return {"spec": spec_name, "k": k, "reps": reps, "n_keys": len(per_key),
            "sigma_single": ms, "sigma_bok": mb, "per_key": per_key}


# ------------------------------------------------------------------------ CLI
def run_night(spec_name="wifi24", limit=None, dry_run=False, quota=None,
              gen_glob=None, gen_quota=None, tmpl_quota=None):
    if gen_quota is not None or tmpl_quota is not None:
        quota = dict(quota or QUOTA)               # overnight: label many G or T
        if gen_quota is not None:
            quota["G"] = gen_quota
        if tmpl_quota is not None:
            quota["T"] = tmpl_quota
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
    ap.add_argument("--gen-quota", type=int,
                    help="stratum-G quota for one run (overnight: e.g. 300)")
    ap.add_argument("--tmpl-quota", type=int,
                    help="stratum-T quota for one run (label many templates)")
    ap.add_argument("--sigma-probe", action="store_true",
                    help="best-of-k label-noise probe (06-LAST-MILE §4)")
    ap.add_argument("--k", type=int, default=3, help="best-of-k (default 3)")
    ap.add_argument("--reps", type=int, default=2,
                    help="independent best-of-k labels per key (default 2)")
    ap.add_argument("--seed0", type=int, default=11,
                    help="first seed of the disjoint seed blocks (default 11)")
    ap.add_argument("--gen", action="store_true",
                    help="probe the GENERATED stratum instead of the corpus keys")
    ap.add_argument("--out", help="write the sigma-probe result JSON here")
    args = ap.parse_args()
    if args.sigma_probe:
        res = run_sigma_probe(args.spec, k=args.k, reps=args.reps,
                              seed0=args.seed0, limit=args.limit,
                              generated=args.gen)
        if res and args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                json.dump(res, fh, indent=1)
            print(f"wrote {args.out}")
        return 0 if res else 1
    if not (args.night or args.dry_run):
        ap.error("give --night, --dry-run or --sigma-probe")
    return run_night(args.spec, limit=args.limit, dry_run=args.dry_run,
                     gen_glob=args.gen_glob, gen_quota=args.gen_quota,
                     tmpl_quota=args.tmpl_quota)


if __name__ == "__main__":
    sys.exit(main())

"""Gate G4 by generation: boosted multi-seed sizing of the closest P5 candidates.

The all-params-free ZOAF found gain OR match on the top P5 samples, not both, so
none reached full feasibility. This spends more optimization effort on the few
closest candidates -- a larger ZOAF budget across several seeds (ZOAF is
stochastic; different seeds explore different basins), keeping the best per
candidate. If any clears S11<=-10 & S21>=12 & Idd<=5, that is the first
fully-feasible *generated* LNA (Gate G4 by generation).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))   # lna/ ; token_file is relative to it
sys.path.insert(0, HERE)
import datastore as ds
import size
from topology import Topology, parse_arrow_file

import argparse

BUDGET = dict(n_candidates=8, sgd_iters=8, cgd_iters=2)   # anchor-strength budget


def total_viol(spec, m):
    feas, viol = spec.feasible(m)
    return (0 if feas else 1, sum(viol.values()) if viol else 0.0)


def main():
    ap = argparse.ArgumentParser(description="G4-by-generation refinement")
    ap.add_argument("--top", type=int, default=6, help="how many closest candidates")
    ap.add_argument("--seeds", type=int, default=4, help="how many ZOAF seeds")
    ap.add_argument("--seed-start", type=int, default=1, help="first seed (use fresh)")
    ap.add_argument("--curated", action="store_true",
                    help="fix each candidate's input match at its prior best, size "
                         "the rest (06-LAST-MILE §1 -- the reliable path to feasible)")
    ap.add_argument("--polish", action="store_true",
                    help="after ZOAF, min-margin ascent from the best point "
                         "(07-EXIT §1c -- converts boundary near-misses)")
    args = ap.parse_args()
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    top_n = args.top
    spec = size._spec_for_sizing("wifi24")
    l2 = ds.load("topo_labels")
    # topologies already converted to feasible (this spec) -- don't re-polish them.
    # log_l2_result writes with repeat_probe=True (bypasses the store's dedup), so a
    # converted near-miss keeps its wl_hash and must be filtered here, not there.
    feasible_keys = {(r.get("wl_hash"), r.get("spec")) for r in l2 if r.get("feasible")}

    def tf(r):
        return (r.get("provenance") or {}).get("token_file", "")

    cands = []
    for r in l2:
        if "ft_p5" not in tf(r) or r.get("feasible"):   # incl. v1 + v2; skip done
            continue
        if (r.get("wl_hash"), r.get("spec")) in feasible_keys:   # already converted
            continue
        m = r.get("metrics")
        if not m:
            continue
        cands.append((total_viol(spec, m)[1], tf(r), m, r.get("best_params"),
                      (r.get("graph") or {}).get("tokens")))
    cands.sort(key=lambda c: c[0])
    top = cands[:top_n]
    modes = ("+".join(x for x in ("CURATED" if args.curated else "",
             "POLISH" if args.polish else "") if x)) or "all-free"
    print(f"top {len(top)} P5 candidates by closeness (total violation) [{modes}]:",
          flush=True)
    for tv, f, m, _bp, _tk in top:
        print(f"  {os.path.basename(f):<14} viol={tv:.3f}  S11={m['s11_db']:.1f} "
              f"S21={m['s21_db']:.1f} Idd={m.get('idd_ma') or 0:.2f}", flush=True)

    print(f"\nboosted sizing: {len(seeds)} seeds x budget {BUDGET}\n", flush=True)
    n_feasible = 0
    for tv0, f, m0, bp, toks in top:
        name = os.path.basename(f)
        if not toks:                              # need the row's own graph
            print(f"  {name}: no stored tokens, skip", flush=True)
            continue
        topo = Topology(toks)                     # from the SAME row as bp (not the file)
        if not size.replay_ok(topo, bp, spec, m0):   # provenance invariant (07-EXIT §1a)
            print(f"  {name}: replay check FAILED -- quarantined (bad provenance)",
                  flush=True)
            continue
        # (07-EXIT §1c) polish-first from the stored best point -- ~100 sims and it
        # converts boundary near-misses; ZOAF (curated/all-free) only if polish
        # doesn't close it. total_viol is a (infeasible?, sum) tuple -> feasible-first.
        m, params, feas, how = m0, bp, False, ""
        if args.polish:
            pol = size.polish(topo, spec, bp, budget=100)
            if pol and pol.get("metrics") and total_viol(spec, pol["metrics"]) < total_viol(spec, m):
                m, params, feas, how = pol["metrics"], pol["best_params"], pol["feasible"], "polish"
        if not feas:
            best = None
            for s in seeds:
                try:
                    res = size.size_topology(topo, spec, seed=s, inductor_q=12,
                                             log=False, curate=args.curated,
                                             prior_params=bp, **BUDGET)
                except Exception as e:
                    print(f"  {name} seed {s}: ERROR {e}", flush=True)
                    continue
                if res and res.get("metrics") and (
                        best is None or total_viol(spec, res["metrics"]) < best[0]):
                    best = (total_viol(spec, res["metrics"]), s, res["metrics"],
                            res["feasible"], res.get("best_params"))
            if best and best[0] < total_viol(spec, m):
                _, s, m, feas, params = best
                how = ("curated" if args.curated else "seed") + str(s)
                if args.polish and not feas:      # polish the ZOAF result too
                    pol = size.polish(topo, spec, params, budget=100)
                    if pol and pol.get("metrics") and total_viol(spec, pol["metrics"]) < total_viol(spec, m):
                        m, params, feas, how = pol["metrics"], pol["best_params"], pol["feasible"], how + "+polish"
        tag = "   <=== FEASIBLE  ***GATE G4 BY GENERATION***" if feas else ""
        print(f"  {name:<14} {(how or 'orig'):<14}: S11={m['s11_db']:.1f} "
              f"S21={m['s21_db']:.1f} Idd={m.get('idd_ma') or 0:.2f} "
              f"nf={m.get('nf_db') or 0:.1f} feasible={feas}{tag}", flush=True)
        if feas:                                  # log EVERY feasible design as-found
            n_feasible += 1
            recipe = ("polish-v1" if "polish" in how else
                      "curated-v1" if args.curated else "candidate-v1")
            prov = {"source_arm": "g4-generated", "how": how,
                    "token_file": f.replace("\\", "/"),
                    "curated": bool(args.curated), "polished": "polish" in how}
            size.log_l2_result(spec, topo, m, feas, params, prov, recipe, 100)

    if n_feasible:
        print(f"\n*** {n_feasible} FEASIBLE novel design(s) closed + logged this "
              f"pass (GATE G4 BY GENERATION). ***", flush=True)
    else:
        print("\nG4 not closed this pass; report the closest per-candidate above.",
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
    args = ap.parse_args()
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    top_n = args.top
    spec = size._spec_for_sizing("wifi24")
    l2 = ds.load("topo_labels")

    def tf(r):
        return (r.get("provenance") or {}).get("token_file", "")

    cands = []
    for r in l2:
        if "ft_p5" not in tf(r) or r.get("feasible"):   # incl. v1 + v2; skip done
            continue
        m = r.get("metrics")
        if not m:
            continue
        cands.append((total_viol(spec, m)[1], tf(r), m, r.get("best_params")))
    cands.sort(key=lambda c: c[0])
    top = cands[:top_n]
    print(f"top {len(top)} P5 candidates by closeness (total violation)"
          f"{' [CURATED: fix input match]' if args.curated else ''}:", flush=True)
    for tv, f, m, _bp in top:
        print(f"  {os.path.basename(f):<14} viol={tv:.3f}  S11={m['s11_db']:.1f} "
              f"S21={m['s21_db']:.1f} Idd={m.get('idd_ma') or 0:.2f}", flush=True)

    print(f"\nboosted sizing: {len(seeds)} seeds x budget {BUDGET}\n", flush=True)
    n_feasible = 0
    for tv0, f, m0, bp in top:
        name = os.path.basename(f)
        topo = Topology(parse_arrow_file(os.path.join(HERE, f)))
        best = None
        for s in seeds:
            try:
                res = size.size_topology(topo, spec, seed=s, inductor_q=12,
                                         log=False, curate=args.curated,
                                         prior_params=bp, **BUDGET)
            except Exception as e:
                print(f"  {name} seed {s}: ERROR {e}", flush=True)
                continue
            if not (res and res.get("metrics")):
                continue
            m = res["metrics"]
            key = total_viol(spec, m)
            if best is None or key < best[0]:
                best = (key, s, m, res["feasible"])
        if best is None:
            print(f"  {name}: all seeds failed to size", flush=True)
            continue
        _, s, m, feas = best
        tag = "   <=== FEASIBLE  ***GATE G4 BY GENERATION***" if feas else ""
        print(f"  {name:<14} best(seed {s}): S11={m['s11_db']:.1f} "
              f"S21={m['s21_db']:.1f} Idd={m.get('idd_ma') or 0:.2f} "
              f"nf={m.get('nf_db') or 0:.1f} feasible={feas}{tag}", flush=True)
        if feas:                                  # log EVERY feasible design found
            n_feasible += 1
            prov = {"source_arm": "g4-generated", "seed": s,
                    "token_file": f.replace("\\", "/"), "curated": bool(args.curated)}
            size.size_topology(topo, spec, seed=s, inductor_q=12, log=True,
                               provenance=prov, repeat_probe=True,
                               curate=args.curated, prior_params=bp, **BUDGET)

    if n_feasible:
        print(f"\n*** {n_feasible} FEASIBLE novel design(s) closed + logged this "
              f"pass (GATE G4 BY GENERATION). ***", flush=True)
    else:
        print("\nG4 not closed this pass; report the closest per-candidate above.",
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

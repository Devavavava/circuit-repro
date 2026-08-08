"""Gate-D3 push: NF-GATED labeling of the low-noise archetypes (WP-D3, blind-v1).

WP-D4 measured the whole feasible set collapsing under gated NF (3/13 survive, all
wifi24; the dhruva family misses by +5.4..+8.6 dB). This runs the two prongs of the
answer against specs whose nf_db is now a HARD constraint:

  --arch <prefix>   which archetype families to size (default: the blind-v1
                    low-noise ones, gmbcg_* / nccgcs_*)
  --spec <name>     the target spec (nf gated -- that is the whole point)
  --seeds N         multi-seed ZOAF; the co-optimum needs more than one start
  --polish          min-margin ascent from each seed's best (now NF-aware)

Every result is logged as an L2 row with recipe `blind-v1-nf` and
zoaf_cfg.nf_gated true, so the NF-gated domain never mixes with the tier-1 rows.
Chunk with --limit / --arch; reruns skip (wl_hash, spec) keys already logged
unless --repeat.

    python lna/d3_campaign.py --spec dhruva-s --seeds 2 --polish
    python lna/d3_campaign.py --spec wideband-sdr --arch gmbcg_wb,nccgcs_wb
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds          # noqa: E402
import size as S                # noqa: E402
import templates as T           # noqa: E402
from novelty import wl_features  # noqa: E402
from topology import Topology   # noqa: E402

RECIPE = "blind-v1-nf"


def run(spec_name, prefixes, seeds, do_polish, limit, budget, repeat, cls=None,
        match_first=True):
    spec = S._spec_for_sizing(spec_name)              # NF gated (WP-D1 default)
    assert S.nf_is_gated(spec), f"{spec_name} does not gate nf_db -- nothing to do"
    lim = (spec.constraints.get("nf_db") or {}).get("max")
    done = ds.existing_l2_keys()
    arche = [a for a in T.archetypes()
             if any(a["name"].startswith(p) for p in prefixes)
             and (cls is None or a["cls"] == cls)]
    print(f"D3 campaign vs {spec_name} (NF GATED <= {lim} dB): "
          f"{len(arche)} archetypes x {seeds} seed(s)"
          f"{' + polish' if do_polish else ''}\n")
    print(f"{'archetype':<24} {'seed':>4} {'sims':>5} {'S11*':>7} {'S21':>7} "
          f"{'Idd':>6} {'NF':>6} {'K_min':>7} {'viol':>7}  verdict")
    n_feas = best_overall = 0
    best_overall = None
    for a in arche[:limit] if limit else arche:
        topo = Topology(a["seq"])
        wl = wl_features(topo)[0]
        if not repeat and (wl, spec_name) in done:
            print(f"{a['name']:<24}   (already labeled vs {spec_name}, skip)")
            continue
        best = None
        for seed in range(1, seeds + 1):
            t0 = time.time()
            if match_first:
                res = S.size_match_first(topo, spec, seed=seed, inductor_q=12,
                                         budget=budget,
                                         polish_budget=400 if do_polish else 0)
            else:
                res = S.size_topology(topo, spec, seed=seed, inductor_q=12, log=False,
                                      n_candidates=budget, sgd_iters=budget,
                                      cgd_iters=2)
            if res is None or res.get("metrics") is None:
                print(f"{a['name']:<24} {seed:>4}     -   (bias/sim failed)")
                continue
            m, bp, ne = res["metrics"], res["best_params"], res["n_evals"]
            if do_polish and not match_first:
                pol = S.polish(topo, spec, bp, budget=400, inductor_q=12)
                if pol and pol.get("metrics") and pol["min_margin"] > -1e8:
                    if spec.objective(pol["metrics"]) < spec.objective(m):
                        m, bp, ne = pol["metrics"], pol["best_params"], ne + pol["n_evals"]
            feas, viol = spec.feasible(m)
            tot = sum(viol.values()) if viol else 0.0
            s11 = m.get("s11_max_db") if _wide(spec_name) else m.get("s11_db")
            print(f"{a['name']:<24} {seed:>4} {ne:>5} {s11:>7.1f} {m['s21_db']:>7.1f} "
                  f"{(m.get('idd_ma') or 0):>6.2f} "
                  f"{(m.get('nf_db') if m.get('nf_db') is not None else float('nan')):>6.2f} "
                  f"{(m.get('k_min') if m.get('k_min') is not None else float('nan')):>7.3g} "
                  f"{tot:>7.3f}  {'** FEASIBLE **' if feas else ''}"
                  f"  [{time.time()-t0:.0f}s]")
            if best is None or tot < best[0]:
                best = (tot, m, bp, ne, feas)
        if best is None:
            continue
        tot, m, bp, ne, feas = best
        n_feas += int(feas)
        if best_overall is None or tot < best_overall[0]:
            best_overall = (tot, a["name"], m)
        S.log_l2_result(spec, topo, m, feas, bp,
                        {"source_arm": "d3-lownoise", "archetype": a["name"],
                         "cls": a["cls"], "inductor_q": 12},
                        RECIPE, ne, inductor_q=12, repeat_probe=repeat)
    if best_overall:
        tot, name, m = best_overall
        print(f"\nbest vs {spec_name}: {name}  viol {tot:.3f}  "
              f"NF {m.get('nf_db')}  S21 {m.get('s21_db'):.1f}")
    print(f"{n_feas} feasible under gated NF")
    return n_feas


def _wide(spec_name):
    return spec_name.startswith(("dhruva", "wideband"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default="dhruva-s")
    ap.add_argument("--arch", default="gmbcg,nccgcs")
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--polish", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--budget", type=int, default=8, help="ZOAF n_candidates/sgd_iters")
    ap.add_argument("--repeat", action="store_true")
    ap.add_argument("--cls", choices=["nb", "wb"])
    ap.add_argument("--all-free", action="store_true",
                    help="skip the match-first stage (old all-free ZOAF)")
    a = ap.parse_args()
    return 0 if run(a.spec, a.arch.split(","), a.seeds, a.polish, a.limit,
                    a.budget, a.repeat, a.cls,
                    match_first=not a.all_free) >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())

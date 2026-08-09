"""Control-experiment sidecar: the *novel front* of a generator pool (FINDINGS §16).

NDL counts how many genuinely-new topologies a checkpoint produces. It says
nothing about whether those topologies are any GOOD. This measures the second
half: take a pool's genuinely-novel candidates (WL hash matching no
`templates.py` archetype, no corpus circuit and no existing store row), size the
best of them under one fixed protocol, and report the best violation / feasibility
reached. Run identically on the template-free control arm and on the adopted
P5-v3 baseline, it is the decisive number for "is the template scaffolding
load-bearing, or has the generator internalized the design space?".

Protocol (identical for every arm, deliberately cheap and fixed):
  1. structural screen vs the spec, WL-dedupe, novel-vs-ref-v2-and-store filter
  2. light all-free ZOAF scan of the first `--scan-limit` novel candidates
  3. **clamped** bounded polish (`size.polish`, box-clamped since 2026-08-08 --
     never the old unclamped ascent) from the scan's best point, on the top
     `--top` by total violation
  4. log the polished result as one L2 row, recipe `ctrl-v1`, arm in provenance

    python lna/_ctrl_front.py --pool lna/out/ft_ctrl_nb_s1337 --spec wifi24 \
        --arm ctrl-v1 --scan-limit 10 --top 4
"""
import argparse
import glob as globmod
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import datastore as ds  # noqa: E402
import size  # noqa: E402
from topology import Topology, parse_arrow_file  # noqa: E402

SCAN_BUDGET = dict(n_candidates=4, sgd_iters=5, cgd_iters=1)
RECIPE = "ctrl-v1"


def total_viol(spec, m):
    feas, viol = spec.feasible(m)
    return sum(viol.values()) if viol else 0.0


def fmt(m):
    s11 = m.get("s11_max_db")
    s11 = s11 if s11 is not None else m.get("s11_db")
    return (f"S11={None if s11 is None else round(s11, 1)} "
            f"S21={m.get('s21_db') and round(m['s21_db'], 1)} "
            f"Idd={m.get('idd_ma') and round(m['idd_ma'], 2)} "
            f"NF={m.get('nf_db') and round(m['nf_db'], 2)}")


def novel_candidates(pool, spec, exclude_store=True):
    """Screen-passing, WL-distinct samples matching nothing in ref-v2 and (by
    default) nothing already labelled in the store."""
    from novelty import ref_tag, reference, wl_features
    ref_hashes, _, ref_meta = reference()
    store = {r.get("wl_hash") for r in ds.load("topo_labels")} if exclude_store else set()
    seen, out, n_screen, n_arch_or_corpus, n_store = set(), [], 0, 0, 0
    for f in sorted(globmod.glob(os.path.join(pool, "seq*.txt"))):
        try:
            topo = Topology(parse_arrow_file(f))
        except Exception:
            continue
        if not spec.structural_screen(topo)[0]:
            continue
        n_screen += 1
        h = wl_features(topo)[0]
        if h in seen:
            continue
        seen.add(h)
        if h in ref_hashes:
            n_arch_or_corpus += 1
            continue
        if h in store:
            n_store += 1
            continue
        out.append((f, topo, h))
    return out, {"screen_passing": n_screen, "distinct": len(seen),
                 "ref_copies": n_arch_or_corpus, "already_in_store": n_store,
                 "novel_front": len(out), "novelty_ref": ref_tag(ref_meta)}


def run(args):
    spec = size._spec_for_sizing(args.spec, nf_gate=not args.no_nf_gate)
    gated = [k for k, c in spec.constraints.items() if c.get("status") != "unsupported"]
    cands, stats = novel_candidates(args.pool, spec,
                                    exclude_store=not args.allow_store)
    print(f"[{args.arm}] pool {args.pool} vs {args.spec}  gated={gated}")
    print(f"[{args.arm}] {json.dumps(stats)}", flush=True)
    cands = cands[:args.scan_limit]
    t0, sims = time.time(), 0
    scored = []
    for f, topo, h in cands:
        name = os.path.basename(f)
        try:
            res = size.size_topology(topo, spec, seed=args.seed, inductor_q=12,
                                     log=False, **SCAN_BUDGET)
        except Exception as e:
            print(f"  {name:<14} ERROR {e}", flush=True)
            continue
        if not res or not res.get("metrics"):
            print(f"  {name:<14} no metrics", flush=True)
            continue
        sims += res.get("n_evals") or 0
        tv = total_viol(spec, res["metrics"])
        scored.append((tv, name, f, topo, h, res))
        print(f"  {name:<14} viol={tv:7.3f} {fmt(res['metrics'])} "
              f"feas={res['feasible']} sims={res.get('n_evals')}", flush=True)
    scored.sort(key=lambda c: c[0])
    print(f"[{args.arm}] scan done: {len(scored)} sized, {sims} sims, "
          f"{time.time()-t0:.0f}s", flush=True)

    print(f"\n[{args.arm}] bounded polish (box-clamped) on top {args.top}:",
          flush=True)
    best_overall, n_feas, rows = None, 0, []
    for tv0, name, f, topo, h, res in scored[:args.top]:
        m, params, feas, how = res["metrics"], res["best_params"], res["feasible"], "scan"
        pol = size.polish(topo, spec, params, budget=args.polish_budget)
        if pol and pol.get("metrics") and \
                total_viol(spec, pol["metrics"]) < total_viol(spec, m):
            m, params, feas, how = (pol["metrics"], pol["best_params"],
                                    pol["feasible"], "bounded-polish")
            sims += pol.get("n_evals") or 0
        tv = total_viol(spec, m)
        n_feas += int(feas)
        rows.append({"seq": name, "wl": h, "viol": round(tv, 4), "how": how,
                     "feasible": bool(feas), "metrics": m})
        if best_overall is None or tv < best_overall[0]:
            best_overall = (tv, name, m, feas)
        print(f"  {name:<14} {how:<15} viol={tv:7.3f} {fmt(m)} "
              f"feasible={feas}{'   <=== FEASIBLE' if feas else ''}", flush=True)
        if not args.no_log:
            prov = {"source_arm": args.arm, "experiment": "ctrl-v1",
                    "how": how, "novel": True,
                    "novelty_ref": stats["novelty_ref"], "wl_hash": h,
                    "token_file": f.replace("\\", "/")}
            size.log_l2_result(spec, topo, m, feas, params, prov, RECIPE,
                               res.get("n_evals", 0) + (args.polish_budget if
                                                        how != "scan" else 0))
    summary = {"arm": args.arm, "spec": args.spec, "pool": args.pool,
               **stats, "sized": len(scored), "polished": len(rows),
               "feasible": n_feas, "sims": sims,
               "best_viol": None if best_overall is None else round(best_overall[0], 4),
               "best_seq": None if best_overall is None else best_overall[1],
               "rows": rows}
    print(f"\n[{args.arm}] SUMMARY {json.dumps({k: v for k, v in summary.items() if k != 'rows'})}",
          flush=True)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(summary, fh, indent=1)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pool", required=True)
    ap.add_argument("--spec", default="wifi24")
    ap.add_argument("--arm", default="ctrl-v1")
    ap.add_argument("--scan-limit", type=int, default=10)
    ap.add_argument("--top", type=int, default=4)
    ap.add_argument("--polish-budget", type=int, default=60)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--no-nf-gate", action="store_true",
                    help="tier-1 gating (S11/S21/Idd); NF measured, advisory")
    ap.add_argument("--allow-store", action="store_true",
                    help="do not exclude topologies already labelled in the store")
    ap.add_argument("--no-log", action="store_true")
    ap.add_argument("--out", default=None)
    return run(ap.parse_args())


if __name__ == "__main__":
    sys.exit(main())

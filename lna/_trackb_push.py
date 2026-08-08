"""Last-mile push on ONE candidate: repeated polish restarts + curated ZOAF from the
polished point, keeping the best. `trackb_g4.py --refine` polishes once at budget 100
and only logs a feasible result, so a 0.004-violation near-miss loses its improved
params; this re-derives them and keeps pushing from there.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import datastore as ds
import size
from topology import Topology
from _trackb_bpolish import bounded_polish, in_box


def tv(spec, m):
    feas, viol = spec.feasible(m)
    return (0 if feas else 1, sum(viol.values()) if viol else 0.0)


def show(spec, m):
    f, v = spec.feasible(m)
    return (f"S11max={m.get('s11_max_db')} S21={m.get('s21_db')} "
            f"Idd={m.get('idd_ma')} NF={m.get('nf_db')} viol={sum(v.values()) if v else 0:.5f} "
            f"feasible={f} binding={sorted(v, key=lambda k: -v[k]) if v else []}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", required=True)
    ap.add_argument("--spec", default="dhruva-l1")
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--budget", type=int, default=400)
    ap.add_argument("--seeds", type=int, default=0)
    ap.add_argument("--seed-start", type=int, default=61)
    ap.add_argument("--recipe", default="p5v6-gen-v1")
    ap.add_argument("--no-log", action="store_true")
    ap.add_argument("--unbounded", action="store_true",
                    help="use size.polish (escapes the device box) instead of bounded")
    a = ap.parse_args()
    spec = size._spec_for_sizing(a.spec, nf_gate=False)     # tier-1
    row = None
    for r in ds.load("topo_labels"):
        if r.get("spec") != a.spec:
            continue
        p = r.get("provenance") or {}
        if os.path.basename(p.get("token_file", "")) != a.seq or not p.get("trackb"):
            continue
        if row is None or tv(spec, r["metrics"]) < tv(spec, row["metrics"]):
            row = r
    if row is None:
        print(f"no store row for {a.seq}")
        return 1
    topo = Topology(row["graph"]["tokens"])
    params, m = row["best_params"], row["metrics"]
    print(f"{a.seq} wl={row.get('wl_hash')} start: {show(spec, m)}", flush=True)
    best = (tv(spec, m), m, params, "orig")
    for i in range(a.rounds):
        _pol = size.polish if a.unbounded else bounded_polish
        pol = _pol(topo, spec, best[2], budget=a.budget)
        if not (pol and pol.get("metrics")):
            print(f"  round {i}: polish returned nothing", flush=True)
            break
        t = tv(spec, pol["metrics"])
        print(f"  polish r{i} (budget {a.budget}): {show(spec, pol['metrics'])}",
              flush=True)
        if t < best[0]:
            best = (t, pol["metrics"], pol["best_params"], f"polish-r{i}")
        else:
            print("  (no further improvement -- restarts converged)", flush=True)
            break
        if t[0] == 0:
            break
    if best[0][0] != 0 and a.seeds:
        for s in range(a.seed_start, a.seed_start + a.seeds):
            try:
                res = size.size_topology(topo, spec, seed=s, inductor_q=12, log=False,
                                         curate=True, prior_params=best[2],
                                         n_candidates=8, sgd_iters=8, cgd_iters=2)
            except Exception as e:
                print(f"  seed {s}: ERROR {e}", flush=True)
                continue
            if not (res and res.get("metrics")):
                continue
            t = tv(spec, res["metrics"])
            print(f"  curated s{s}: {show(spec, res['metrics'])}", flush=True)
            if t < best[0]:
                best = (t, res["metrics"], res["best_params"], f"curated{s}")
                pol = (size.polish if a.unbounded else bounded_polish)(topo, spec, best[2], budget=a.budget)
                if pol and pol.get("metrics") and tv(spec, pol["metrics"]) < best[0]:
                    best = (tv(spec, pol["metrics"]), pol["metrics"],
                            pol["best_params"], f"curated{s}+polish")
                    print(f"  -> +polish: {show(spec, best[1])}", flush=True)
            if best[0][0] == 0:
                break
    feas = best[0][0] == 0
    import bias as _bias
    _nl, _, _rep, _ = _bias.insert_bias(topo, sweep=True, inductor_q=12)
    _sz, _ = size.classify_params(_nl)
    bad = in_box(best[2], _sz, spec)
    print(f"\nBEST [{best[3]}]: {show(spec, best[1])}", flush=True)
    if bad:
        print("  !! OUT-OF-BOX params: " + "; ".join(
            f"{n}({k})={v:.4g} not in [{lo:.4g},{hi:.4g}]" for n, k, v, lo, hi in bad),
            flush=True)
        feas = False
        print("  -> claim withdrawn: point violates the spec device box", flush=True)
    if feas:
        print("*** TIER-1 FEASIBLE (generated, novel) ***", flush=True)
    if feas and not a.no_log:
        prov = {"source_arm": "trackb-p5v6", "how": best[3], "trackb": True,
                "token_file": (row.get("provenance") or {}).get("token_file", ""),
                "wl_hash": row.get("wl_hash"), "curated": "curated" in best[3],
                "polished": "polish" in best[3], "nf_gated": False}
        size.log_l2_result(spec, topo, best[1], True, best[2], prov, a.recipe, 500)
    json.dump({"seq": a.seq, "wl": row.get("wl_hash"), "how": best[3],
               "metrics": best[1], "feasible": feas, "params": best[2]},
              open(f"lna/out/_push_{a.seq.replace('.txt','')}.json", "w"), indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())

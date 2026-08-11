"""WP-ATTRIB step 3 -- size the four arms' rung-0 picks at EQUAL budget.

Every arm gets the same protocol, per candidate:

    size.size_topology(seed=1, inductor_q=12, **search.SCAN_BUDGET)
        -> box-clamped size.polish(budget=search.POLISH_BUDGET)

which is the arm-comparison sizing protocol already used for FINDINGS 16's
novel-front comparison and 20.4's live rung-1 -- imported from search.py rather
than restated, so the two cannot drift apart. Harness is the current one:
multi-finger MOS (to_spice.W_FINGER), inductor_q=12, NF gated per the spec.

Selection is NOT made here: it is read from the single combined rank JSON, so
one critic ensemble and one scoring function order all four arms (plans2/10 1.3
step 5). This driver only spends SPICE on the top k per arm.

    python lna/_attrib_size.py --rank-json lna/out/_at/rank.json --k 10 \
        --out lna/out/_at/sized.json
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import search as S                                                # noqa: E402
import size                                                       # noqa: E402
from topology import Topology                                     # noqa: E402

RECIPE = "attrib-v1"


def select(rk, k):
    """Top-k per arm under the ONE shared critic score. Deterministic ties."""
    by_arm = {}
    for i, c in enumerate(rk["candidates"]):
        by_arm.setdefault(c["arm"], []).append(i)
    picks = {}
    for arm, idxs in by_arm.items():
        idxs.sort(key=lambda i: (-rk["candidates"][i]["score"],
                                 rk["candidates"][i]["wl"]))
        picks[arm] = idxs[:k]
    return picks


def run(rank_json, k, out, shard=None):
    with open(rank_json, encoding="utf-8") as fh:
        rk = json.load(fh)
    spec = size._spec_for_sizing(rk["spec"])
    cands = rk["candidates"]
    picks = select(rk, k)
    order = []
    for arm in sorted(picks):
        for r, i in enumerate(picks[arm]):
            order.append((arm, r, i))
    for arm in sorted(picks):
        want = len(picks[arm])
        print(f"  arm {arm:<7} qualifying "
              f"{sum(1 for c in cands if c['arm'] == arm):>3} -> sizing {want:>2}"
              + ("   ** SHORTFALL **" if want < k else ""))
    if shard:
        si, sn = (int(x) for x in shard.split("/"))
        order = [o for n, o in enumerate(order) if n % sn == si]
    print(f"WP-ATTRIB sizing: spec={rk['spec']} k={k} -> {len(order)} sizings"
          + (f" (shard {shard})" if shard else ""), flush=True)

    results, t_all = [], time.time()
    for n, (arm, rnk, i) in enumerate(order):
        c = cands[i]
        topo = Topology(c["tokens"])
        t0 = time.time()
        rec = {"arm": arm, "rank": rnk, "idx": i, "seq": c["seq"],
               "wl": c["wl"], "score": c["score"], "n_dev": c["n_dev"],
               "n_ind": c["n_ind"], "file": c["file"]}
        try:
            res = size.size_topology(topo, spec, seed=1, inductor_q=12,
                                     log=False, **S.SCAN_BUDGET)
        except Exception as e:                                    # noqa: BLE001
            res, rec["error"] = None, f"{type(e).__name__}: {e}"
        if not res or not res.get("metrics"):
            rec.update(ok=False, secs=round(time.time() - t0, 1),
                       n_evals=(res or {}).get("n_evals") or 0)
            results.append(rec)
            print(f"  [{n+1}/{len(order)}] {arm:<7} {c['seq']:<12} FAILED "
                  f"{rec.get('error', 'no metrics')}", flush=True)
            S._write(out, {"rank_json": rank_json, "k": k, "shard": shard,
                           "spec": rk["spec"], "recipe": RECIPE,
                           "results": results})
            continue
        m, params, feas = res["metrics"], res["best_params"], res["feasible"]
        n_ev, how = res.get("n_evals") or 0, "scan"
        pol = size.polish(topo, spec, params, budget=S.POLISH_BUDGET)
        if pol and pol.get("metrics"):
            n_ev += pol.get("n_evals") or 0
            if S._viol(spec, pol["metrics"]) < S._viol(spec, m):
                m, params, feas, how = (pol["metrics"], pol["best_params"],
                                        pol["feasible"], "bounded-polish")
        mar = S.realized_margins(spec, m)
        cols = rk.get("gated_cols") or [0, 1, 2, 3]
        rec.update(ok=True, how=how, feasible=bool(feas),
                   viol=round(S._viol(spec, m), 4), margins=mar,
                   near=S._near_feasible_vec([mar[j] for j in cols]),
                   metrics=m, n_evals=n_ev,
                   secs=round(time.time() - t0, 1))
        prov = {"source_arm": f"attrib-{arm}", "experiment": "wp-attrib",
                "how": how, "novel": True,
                "novelty_ref": rk.get("novelty_ref"), "wl_hash": c["wl"],
                "critic_snapshot": rk["critic"]["snapshot"],
                "critic_score": c["score"], "attrib_rank": rnk,
                "attrib_arm": arm, "port_src": True,
                "token_file": c["file"]}
        size.log_l2_result(spec, topo, m, feas, params, prov, RECIPE, n_ev,
                           repeat_probe=False)
        results.append(rec)
        print(f"  [{n+1}/{len(order)}] {arm:<7} {c['seq']:<12} {how:<15} "
              f"viol={rec['viol']:8.3f} near={rec['near']} feas={feas} "
              f"{S._fmt(m)} {rec['secs']:.0f}s", flush=True)
        S._write(out, {"rank_json": rank_json, "k": k, "shard": shard,
                       "spec": rk["spec"], "recipe": RECIPE,
                       "results": results})
    print(f"done: {len(results)} sizings, {(time.time()-t_all)/60:.1f} min wall")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rank-json", required=True)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--shard")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    return run(a.rank_json, a.k, a.out, shard=a.shard)


if __name__ == "__main__":
    sys.exit(main())

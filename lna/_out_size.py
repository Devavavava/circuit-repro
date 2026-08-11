"""WP-OUTCOME step 4 -- size every arm's rung-0 picks at EQUAL budget.

The protocol is imported, not restated, so it cannot drift from the comparison
it has to join (FINDINGS 16's novel front, 20.4's live rung-1, and WP-ATTRIB's
four-arm funnel all use it):

    size.size_topology(seed=1, inductor_q=12, **search.SCAN_BUDGET)
        -> box-clamped size.polish(budget=search.POLISH_BUDGET)

Harness is the current one: multi-finger MOS (`to_spice.W_FINGER`),
inductor_q=12, NF gated per the spec. Selection is read from the single combined
rank JSON, so ONE critic ensemble and ONE scoring function order every arm.

    python lna/_out_size.py --rank-json lna/out/_o/rank.json --k 10 \
        --out lna/out/_o/sized.json [--shard 0/2]
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

RECIPE = "outcome-v1"


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
        print("  arm %-6s qualifying %3d -> sizing %2d%s"
              % (arm, sum(1 for c in cands if c["arm"] == arm), want,
                 "   ** SHORTFALL **" if want < k else ""))
    if shard:
        si, sn = (int(x) for x in shard.split("/"))
        order = [o for n, o in enumerate(order) if n % sn == si]
    print("WP-OUTCOME sizing: spec=%s k=%d -> %d sizings%s"
          % (rk["spec"], k, len(order), " (shard %s)" % shard if shard else ""),
          flush=True)

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
            res, rec["error"] = None, "%s: %s" % (type(e).__name__, e)
        if not res or not res.get("metrics"):
            rec.update(ok=False, secs=round(time.time() - t0, 1),
                       n_evals=(res or {}).get("n_evals") or 0)
            results.append(rec)
            print("  [%d/%d] %-6s %-12s FAILED %s"
                  % (n + 1, len(order), arm, c["seq"],
                     rec.get("error", "no metrics")), flush=True)
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
                   metrics=m, n_evals=n_ev, secs=round(time.time() - t0, 1))
        prov = {"source_arm": "outcome-%s" % arm, "experiment": "wp-outcome",
                "how": how, "novel": True,
                "novelty_ref": rk.get("novelty_ref"), "wl_hash": c["wl"],
                "critic_snapshot": rk["critic"]["snapshot"],
                "critic_score": c["score"], "outcome_rank": rnk,
                "outcome_arm": arm, "port_src": True,
                "token_file": c["file"]}
        size.log_l2_result(spec, topo, m, feas, params, prov, RECIPE, n_ev,
                           repeat_probe=False)
        results.append(rec)
        print("  [%d/%d] %-6s %-12s %-15s viol=%8.3f near=%s feas=%s %s %.0fs"
              % (n + 1, len(order), arm, c["seq"], how, rec["viol"],
                 rec["near"], feas, S._fmt(m), rec["secs"]), flush=True)
        S._write(out, {"rank_json": rank_json, "k": k, "shard": shard,
                       "spec": rk["spec"], "recipe": RECIPE,
                       "results": results})
    print("done: %d sizings, %.1f min wall"
          % (len(results), (time.time() - t_all) / 60))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rank-json", required=True)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--shard")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    return run(a.rank_json, a.k, a.out, shard=a.shard)


if __name__ == "__main__":
    sys.exit(main())

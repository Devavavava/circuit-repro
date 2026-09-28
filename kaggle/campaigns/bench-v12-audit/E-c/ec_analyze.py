"""E-c analysis: per-cell table from candidates.jsonl + results.jsonl -> summary.json + table.md.

SPICE-minutes to first feasible:
  fixed  = sum of screen wall-secs (smoke_run time) of SIZED candidates in the fixed enumeration
           order up to and incl. the first screen-feasible one, /60.
  random = exact expectation under a uniformly random order of the sized candidates:
           E = sum_{infeasible i} c_i/(K+1) + mean_{feasible} c_j   (K = #feasible), /60.
  (Unsizable candidates -- smoke_run None -- are excluded; their cost is reported separately.)
"""
import json, os, sys
from collections import defaultdict

OUT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, OUT)
from ec_search import cells, anchor_key  # noqa: E402

cands = [json.loads(l) for l in open(f"{OUT}/candidates.jsonl")]
byanchor = defaultdict(list)
for c in cands:
    byanchor[c["anchor"]].append(c)
res = defaultdict(dict)       # (cell,cid) -> {(seed,phase): rec}
for l in open(f"{OUT}/results.jsonl"):
    r = json.loads(l)
    res[(r["cell"], r["cid"])][(r["seed"], r["phase"])] = r

summary = []
lines = ["| cell | gen | rt-valid | sizable | screen-feas | confirmed | conf. 3/3 seeds | conf. mu_min>=1 | feasible edits (seeds pass /3; * = mu_min<1) | "
         "SPICE-min first feas (fixed) | E[SPICE-min] random | exhaust SPICE-min | SEARCH-TRIVIAL |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for cell in cells():
    cl = sorted(byanchor[anchor_key(cell)], key=lambda c: c["order"])
    gen = len(cl)
    valid = [c for c in cl if c["rt_ok"]]
    screened = [(c, res[(cell, c["cid"])].get((1, "screen"))) for c in valid]
    missing = sum(1 for _c, r in screened if r is None)
    sized = [(c, r) for c, r in screened if r and r.get("sizable")]
    errs = [(c, r) for c, r in screened if r and r.get("sizable") is None]
    unsz = [(c, r) for c, r in screened if r and r.get("sizable") is False]
    feas = [(c, r) for c, r in sized if r.get("feasible")]
    # fixed-order cost
    fixed = None; acc = 0.0; fixed_calls = None
    for i, (c, r) in enumerate(sized):
        acc += r["secs"]
        if r.get("feasible"):
            fixed = acc / 60; fixed_calls = i + 1; break
    tot = sum(r["secs"] for _c, r in sized)
    K = len(feas)
    if K:
        inf_cost = sum(r["secs"] for _c, r in sized if not r.get("feasible"))
        exp = (inf_cost / (K + 1) + sum(r["secs"] for _c, r in feas) / K) / 60
    else:
        exp = None
    # load-independent: number of sizing calls (seed-1 x 2500) to first feasible
    exp_calls = ((len(sized) - K) / (K + 1) + 1) if K else None
    fe = []
    for c, r in feas:
        conf = {s: res[(cell, c["cid"])].get((s, "confirm")) for s in (1, 2, 3)}
        npass = sum(1 for s in (1, 2, 3) if conf[s] and conf[s].get("feasible"))
        ncomplete = sum(1 for s in (1, 2, 3) if conf[s])
        fe.append({"cid": c["cid"], "desc": c["desc"], "screen_worst": r.get("worst"),
                   "confirm_seed1": bool(conf[1] and conf[1].get("feasible")),
                   "seeds_pass": npass, "seeds_run": ncomplete,
                   "confirm_worst": {s: (conf[s] or {}).get("worst") for s in (1, 2, 3)},
                   "k_min": r["metrics"].get("k_min"), "mu_min": r["metrics"].get("mu_min"),
                   "stable_mu": (r["metrics"].get("mu_min") or 0) >= 1.0,
                   "adds_inductor": c["desc"].startswith("add L")})
    confirmed = [f for f in fe if f["confirm_seed1"]]
    # near misses: best 5 infeasible sized by worst margin
    nm = sorted([(r["worst"][1], c["desc"], r["worst"][0]) for c, r in sized
                 if not r.get("feasible") and r.get("worst")], reverse=True)[:5]
    trivial = len(confirmed) > 0
    conf_stable = [f for f in confirmed if f["stable_mu"]]
    conf_noL = [f for f in confirmed if not f["adds_inductor"]]
    conf_3of3 = [f for f in confirmed if f["seeds_pass"] == 3]
    rec = {"cell": cell, "generated": gen, "rt_valid": len(valid), "screen_missing": missing,
           "sizable": len(sized), "unsizable": len(unsz), "errors": len(errs),
           "screen_feasible": K, "confirmed": len(confirmed), "feasible_edits": fe,
           "spice_min_first_fixed": fixed, "spice_min_first_expected_random": exp,
           "spice_min_exhaust": tot / 60,
           "calls_first_fixed": fixed_calls, "calls_first_expected_random": exp_calls,
           "mean_secs_per_call": tot / len(sized) if sized else None,
           "unsizable_secs": sum(r.get("secs") or 0 for _c, r in unsz),
           "near_misses": nm, "search_trivial": trivial,
           "confirmed_stable_mu_ge_1": len(conf_stable), "confirmed_no_L_add": len(conf_noL),
           "confirmed_3of3": len(conf_3of3),
           "search_trivial_if_stability_required": len(conf_stable) > 0}
    summary.append(rec)
    fes = "; ".join(f"{f['desc']} ({f['seeds_pass']}/3){'' if f['stable_mu'] else '*'}" for f in fe) or "-"
    f2 = lambda v: "-" if v is None else f"{v:.1f}"
    lines.append(f"| {cell} | {gen} | {len(valid)} | {len(sized)} | {K} | {len(confirmed)} | {len(conf_3of3)} | {len(conf_stable)} | {fes} | "
                 f"{f2(fixed)} | {f2(exp)} | {tot/60:.0f} | {'YES' if trivial else 'no'} |")
json.dump(summary, open(f"{OUT}/summary.json", "w"), indent=1)
open(f"{OUT}/table.md", "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
print()
for s in summary:
    print(s["cell"], "near-misses:", [(round(w, 4), d, m) for w, d, m in s["near_misses"][:3]],
          "missing:", s["screen_missing"], "err:", s["errors"])

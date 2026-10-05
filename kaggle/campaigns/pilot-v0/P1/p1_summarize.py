#!/usr/bin/env python
"""pilot-v0 P1 tables (PREREG-PILOT-V0.md "Metrics and decision rule").

  p1_summarize.py [label ...]      -> score/summary.json + score/tables.md

Per task and model (label), over its 2 samples, scored at seeds 1,2,3 (rl-v1.2, 2500):
  solved            some valid sample is feasible at >= 1 seed
  solved_2of3       some valid sample is feasible at >= 2 of the 3 seeds
  validity          valid completions / completions (proposal.round_trip ok, local)
  SPICE-min to first feasible: sizing calls in the order a user would run them --
                    seed 1 (sample 1, sample 2), then seed 2, then seed 3; an invalid
                    sample or a repeat of an already-sized (tokens, seed) costs 0; the
                    wall seconds of each smoke_run (cache rows keep their own) summed up
                    to and including the first feasible call. Unsolved -> not defined
                    (the cost of exhausting all calls is reported separately).
  search bar        P0 eval/searchbar.json for the same task (E-c random-order cost).
  GPU-min/completion the llama-server timings (prompt + predicted ms) of the CAP path.
Tiers from pilot-v0/eval/tiers.json once P0 has written it; until then 'untiered'.
Decision rule (needs zs and sft1000): useful iff solved(sft1000) - solved(zs) >= 3 AND
validity(sft1000) >= validity(zs); the 100 -> 300 -> 1000 slope decides scale vs change.
"""
import json
import os
import statistics
import sys
from collections import OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PV0 = os.path.dirname(HERE)
SC = os.environ.get("P1_SCORE_DIR") or os.path.join(HERE, "score")
SEEDS = (1, 2, 3)


def rj(p):
    out = []
    if os.path.exists(p):
        for ln in open(p):
            if ln.strip():
                out.append(json.loads(ln))
    return out


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 2) if xs else None


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 2) if xs else None


def main(labels):
    idx = json.load(open(os.path.join(HERE, "prompts", "INDEX.json")))["items"]
    tiers_p = os.path.join(PV0, "eval", "tiers.json")
    bar_p = os.path.join(PV0, "eval", "searchbar.json")
    tiers = json.load(open(tiers_p))["items"] if os.path.exists(tiers_p) else {}
    if tiers and json.load(open(tiers_p)).get("partial"):
        tiers = {}
    bar = json.load(open(bar_p))["items"] if os.path.exists(bar_p) else {}
    score = {}
    for r in rj(os.path.join(SC, "score.jsonl")):
        score[(r["task"], r["key"], r["seed"])] = r
    if not labels:
        labels = sorted(d for d in os.listdir(SC) if os.path.isfile(os.path.join(SC, d, "completions.jsonl")))

    def tier_of(t):
        if idx[t].get("strict_cell"):
            return "T3"
        v = tiers.get(t)
        return v["tier"] if v and not v.get("excluded") else "untiered"

    per = OrderedDict()
    missing = 0
    for lab in labels:
        comps = rj(os.path.join(SC, lab, "completions.jsonl"))
        bytask = defaultdict(list)
        for c in comps:
            bytask[c["task"]].append(c)
        rows = OrderedDict()
        for t in idx:
            if idx[t].get("excluded"):
                continue
            cs = sorted(bytask.get(t, []), key=lambda c: c["sample"])
            feas = {}
            for c in cs:
                if c.get("valid"):
                    f = []
                    for s in SEEDS:
                        r = score.get((t, c["key"], s))
                        if r is None:
                            missing += 1
                        f.append(bool(r and r.get("feasible")))
                    feas[c["sample"]] = f
            solved = any(any(f) for f in feas.values())
            s23 = any(sum(f) >= 2 for f in feas.values())
            cost, sized, first = 0.0, set(), None
            for s in SEEDS:
                for c in cs:
                    if not c.get("valid") or (c["key"], s) in sized:
                        continue
                    sized.add((c["key"], s))
                    r = score.get((t, c["key"], s)) or {}
                    cost += r.get("secs") or 0.0
                    if r.get("feasible") and first is None:
                        first = (s, c["sample"], round(cost / 60, 2))
                if first:
                    break
            b = bar.get(t) or {}
            rows[t] = OrderedDict(
                tier=tier_of(t), family=idx[t]["family"], strict=bool(idx[t].get("strict_cell")),
                n_completions=len(cs), n_valid=sum(1 for c in cs if c.get("valid")),
                n_shown_anchor=sum(1 for c in cs if c.get("is_shown_anchor")),
                n_any_anchor=sum(1 for c in cs if c.get("is_any_anchor")),
                seeds_feasible={str(k): v for k, v in feas.items()}, solved=solved, solved_2of3=s23,
                spice_min_first_feasible=first[2] if first else None,
                first_feasible_at={"seed": first[0], "sample": first[1]} if first else None,
                spice_min_all_calls=round(sum((score.get((t, k, s)) or {}).get("secs") or 0.0
                                              for k, s in {(c["key"], s) for c in cs if c.get("valid")
                                                           for s in SEEDS}) / 60, 2),
                searchbar_spice_min=b.get("spice_min") if b.get("found") else None,
                searchbar_found=b.get("found"),
                gpu_min=[round((c.get("gpu_ms") or 0) / 60000, 3) for c in cs],
                think_tokens=[c.get("think_tokens") for c in cs])
        per[lab] = rows

    def agg(rows):
        rs = list(rows.values())
        nc = sum(r["n_completions"] for r in rs)
        g = [x for r in rs for x in r["gpu_min"]]
        sol = [r for r in rs if r["solved"]]
        return OrderedDict(
            n_tasks=len(rs), solved=len(sol), solved_2of3=sum(1 for r in rs if r["solved_2of3"]),
            completions=nc, valid=sum(r["n_valid"] for r in rs),
            validity=round(sum(r["n_valid"] for r in rs) / nc, 3) if nc else None,
            shown_anchor_repeats=sum(r["n_shown_anchor"] for r in rs),
            spice_min_first_feasible_median=med([r["spice_min_first_feasible"] for r in sol]),
            spice_min_first_feasible_mean=mean([r["spice_min_first_feasible"] for r in sol]),
            searchbar_median_same_tasks=med([r["searchbar_spice_min"] for r in sol]),
            searchbar_median_all_found=med([r["searchbar_spice_min"] for r in rs]),
            gpu_min_per_completion_mean=mean(g), gpu_min_per_completion_median=med(g),
            gpu_min_total=round(sum(g), 1))

    summary = OrderedDict(labels=labels, tiers_source=("pilot-v0/eval/tiers.json" if tiers else "none yet"),
                          missing_score_rows=missing, groups=OrderedDict(), per_task=per)
    groups = ["all", "T1", "T2", "T3", "untiered", "strict"]
    for lab, rows in per.items():
        summary["groups"][lab] = OrderedDict()
        for gname in groups:
            sel = OrderedDict((t, r) for t, r in rows.items()
                              if gname == "all" or (gname == "strict" and r["strict"])
                              or (gname not in ("all", "strict") and r["tier"] == gname))
            if sel:
                summary["groups"][lab][gname] = agg(sel)
    G = summary["groups"]
    if "zs" in G and "sft1000" in G:
        z, s = G["zs"]["all"], G["sft1000"]["all"]
        curve = [(n, G["sft%d" % n]["all"]["solved"]) for n in (100, 300, 1000) if "sft%d" % n in G]
        summary["decision"] = OrderedDict(
            delta_solved=s["solved"] - z["solved"], delta_solved_2of3=s["solved_2of3"] - z["solved_2of3"],
            validity_zs=z["validity"], validity_sft1000=s["validity"],
            useful=(s["solved"] - z["solved"] >= 3) and (s["validity"] >= z["validity"]),
            curve_solved=curve,
            slope=("positive" if len(curve) == 3 and curve[2][1] > curve[0][1] else
                   "flat/negative" if len(curve) == 3 else "incomplete"))
    json.dump(summary, open(os.path.join(SC, "summary.json"), "w"), indent=1)
    L = ["| model | group | tasks | solved | >=2/3 seeds | validity | anchor repeats | SPICE-min to 1st feasible (median / mean, solved) | search bar median (same tasks / all found) | GPU-min/compl (mean / median) | GPU-min total |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for lab in G:
        for gname, a in G[lab].items():
            L.append("| %s | %s | %d | %d | %d | %s (%d/%d) | %d | %s / %s | %s / %s | %s / %s | %s |" % (
                lab, gname, a["n_tasks"], a["solved"], a["solved_2of3"], a["validity"], a["valid"],
                a["completions"], a["shown_anchor_repeats"], a["spice_min_first_feasible_median"],
                a["spice_min_first_feasible_mean"], a["searchbar_median_same_tasks"],
                a["searchbar_median_all_found"], a["gpu_min_per_completion_mean"],
                a["gpu_min_per_completion_median"], a["gpu_min_total"]))
    if "decision" in summary:
        L.append("")
        L.append("Decision: " + json.dumps(summary["decision"]))
    open(os.path.join(SC, "tables.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    print("missing score rows:", missing)


if __name__ == "__main__":
    main(sys.argv[1:])

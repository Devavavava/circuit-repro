"""E-12 P3 aggregator -- builds the scored-campaign deliverable from per-cell
JSONs (P3 c1/c2 + fresh A/B under data/e12/p3_results/) and banked E-11 A/B/C
baselines (data/e11_results/) for DEV + G1''. ZERO sims; read-only.

    python e12_p3_agg.py
"""
import glob
import json
import os
import sys
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
P3 = os.path.join(HERE, "data", "e12", "p3_results")
E11 = os.path.join(HERE, "data", "e11_results")
EDIT_LOG = os.path.join(HERE, "data", "e11_edit_log", "edits.jsonl")

TIERS = {
    "G2pp": "DEV", "G13": "DEV", "G9": "DEV", "G7pp": "DEV", "G12": "DEV",
    "G1pp": "HELD-OUT", "H2": "HELD-OUT", "GN78": "FRESH",
}
GOAL_ORDER = ["G2pp", "G13", "G9", "G7pp", "G12", "G1pp", "H2", "GN78"]
GOAL_DELTA = {
    "G2pp": "s22<=-10 (dhruva-s)", "G13": "nf<=1.45 (dhruva-l2)",
    "G9": "ripple<=3 (dhruva-l5)", "G7pp": "idd<=9@s21>=22.3 (dhruva-l5)",
    "G12": "s11<=-15 (dhruva-l5)", "G1pp": "s21>=33 (dhruva-l1)",
    "H2": "nf<=1.25 (dhruva-l1)", "GN78": "nf<=1.6 (n78 3.4-3.6GHz)",
}
SEEDS = [1, 2, 3]


def load(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return None


def cell(goal, arm, seed, prefer_p3=True):
    """Load a cell. c1/c2 + fresh A/B live in P3; DEV/G1'' A/B/C are banked E-11.
    arm labels: a,b,c1,c2 (P3) or a,b,c (E-11 banked)."""
    if arm in ("c1", "c2"):
        return load(os.path.join(P3, f"cell_{goal}_{arm}_s{seed}.json"))
    # baseline arm a/b/c
    if goal in ("H2", "GN78") and arm in ("a", "b"):
        return load(os.path.join(P3, f"cell_{goal}_{arm}_s{seed}.json"))
    # banked E-11
    return load(os.path.join(E11, f"cell_{goal}_{arm}_s{seed}.json"))


def main():
    report = {"goals": {}, "headline": {}, "parity": {}, "falsifier": {},
              "edit_log": {}, "ngspice": {}, "pools": {}}

    # ---- per goal x arm ----
    all_arms = ["a", "b", "c1", "c2"]
    solves = collections.defaultdict(lambda: collections.defaultdict(int))
    ngspice_total = 0
    parity_fail = []
    n_cells_seen = 0
    baseline_solved = collections.defaultdict(set)   # goal -> set(arm in a,b) solved seeds

    for goal in GOAL_ORDER:
        gblock = {"tier": TIERS[goal], "delta": GOAL_DELTA[goal], "arms": {}}
        for arm in all_arms:
            # G1'' + DEV baseline arm c is banked as "c"; P3 has c1/c2 only.
            arm_solves = []
            first = {"evals": None, "spice": None, "seq": None, "seed": None,
                     "metrics": None}
            distinct_pool = []
            B_expected = None
            for s in SEEDS:
                d = cell(goal, arm, s)
                if d is None:
                    continue
                n_cells_seen += 1
                B_expected = d.get("B")
                ev = d.get("evals_spent")
                ng = d.get("ngspice_calls") or 0
                ngspice_total += ng
                # TOTAL == B parity (scoreboard: full B; no early stop)
                if ev != d.get("B"):
                    parity_fail.append((goal, arm, s, ev, d.get("B")))
                if arm != "a" and d.get("distinct_realized") is not None:
                    distinct_pool.append(d["distinct_realized"])
                if d.get("solved"):
                    arm_solves.append(s)
                    if arm in ("a", "b"):
                        baseline_solved[goal].add(s)
                    # earliest-to-feasible across seeds by evals_to_solve
                    e2s = d.get("evals_to_solve")
                    if e2s is not None and (first["evals"] is None
                                            or e2s < first["evals"]):
                        first = {"evals": e2s,
                                 "spice": d.get("spice_min_to_solve"),
                                 "seq": d.get("edit_seq"), "seed": s,
                                 "metrics": d.get("solve_metrics")}
            solves[goal][arm] = len(arm_solves)
            gblock["arms"][arm] = {
                "solved_seeds": arm_solves, "n_solved": len(arm_solves),
                "B": B_expected,
                "first_feasible": first if arm_solves else None,
                "distinct_realized_by_seed": distinct_pool or None,
                "distinct_realized_mean": (round(sum(distinct_pool)
                                                 / len(distinct_pool), 1)
                                           if distinct_pool else None),
            }
        report["goals"][goal] = gblock

    # ---- headline: solves per arm split by tier ----
    for arm in all_arms:
        d = {"DEV": 0, "HELD-OUT": 0, "FRESH": 0, "TOTAL": 0}
        for goal in GOAL_ORDER:
            n = solves[goal][arm]
            d[TIERS[goal]] += n
            d["TOTAL"] += n
        report["headline"][arm] = d

    # ---- falsifier (§8 verbatim application) ----
    # transfer bar: does C1 or C2 solve any HELD-OUT or FRESH goal its A/B
    # baselines leave unsolved?
    transfer_wins = []
    for goal in GOAL_ORDER:
        if TIERS[goal] in ("HELD-OUT", "FRESH"):
            ab_solved = baseline_solved[goal]   # seeds solved by a or b
            for arm in ("c1", "c2"):
                cseeds = set(report["goals"][goal]["arms"][arm]["solved_seeds"])
                new = cseeds - ab_solved
                # transfer win = the goal is solved by cX where A/B leave it
                # unsolved (goal-level, per §8 wording "solves any ... goal its
                # A/B baselines leave unsolved")
                if cseeds and not ab_solved:
                    transfer_wins.append((goal, arm, sorted(cseeds)))
                elif new:
                    transfer_wins.append((goal, arm, sorted(new)))
    report["falsifier"]["transfer_wins"] = transfer_wins
    dev_c_solves = sum(solves[g]["c1"] + solves[g]["c2"]
                       for g in GOAL_ORDER if TIERS[g] == "DEV")
    ho_fresh_c = sum(solves[g]["c1"] + solves[g]["c2"]
                     for g in GOAL_ORDER if TIERS[g] in ("HELD-OUT", "FRESH"))
    report["falsifier"]["dev_c_solves"] = dev_c_solves
    report["falsifier"]["heldout_fresh_c_solves"] = ho_fresh_c
    report["falsifier"]["MET"] = (len(transfer_wins) == 0)

    # ---- pools vs banked untrained arm-C (falsifier sub-reading) ----
    # banked untrained arm-C distinct_realized on the DEV/held-out goals:
    banked_c = {}
    for goal in GOAL_ORDER:
        vals = []
        for s in SEEDS:
            d = cell(goal, "c", s) if goal not in ("H2", "GN78") else None
            if d and d.get("distinct_realized") is not None:
                vals.append(d["distinct_realized"])
        if vals:
            banked_c[goal] = round(sum(vals) / len(vals), 1)
    report["pools"]["banked_untrained_armC_mean"] = banked_c
    report["pools"]["trained"] = {
        goal: {arm: report["goals"][goal]["arms"][arm]["distinct_realized_mean"]
               for arm in ("c1", "c2")}
        for goal in GOAL_ORDER}

    # ---- parity ----
    report["parity"]["all_cells_TOTAL_eq_B"] = (len(parity_fail) == 0)
    report["parity"]["violations"] = parity_fail
    report["parity"]["cells_seen"] = n_cells_seen

    # ---- edit log growth + per-cell distinct-pool ----
    camp = collections.Counter()
    total = 0
    for l in open(EDIT_LOG):
        total += 1
        try:
            camp[json.loads(l).get("campaign")] += 1
        except Exception:
            pass
    report["edit_log"]["total_rows"] = total
    report["edit_log"]["by_campaign"] = dict(camp)
    report["edit_log"]["e12_p3_rows"] = camp.get("e12-p3", 0)

    # ---- ngspice accounting ----
    report["ngspice"]["p3_ngspice_calls_sum"] = ngspice_total

    print(json.dumps(report, indent=1, default=str))
    return report


if __name__ == "__main__":
    sys.exit(0 if main() else 0)

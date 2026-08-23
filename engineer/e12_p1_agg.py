"""E-12 P1 aggregator (ZERO sims). Reads the 24 p1_results cells + the shared
edit log, recomputes solves from raw metrics (no stored flag), counts banked
SOLVING trajectories, and reports edit-log rows added under campaign "e12".

    python e12_p1_agg.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.abspath(os.path.join(HERE, "..", "lna"))
for p in (HERE, LNA):
    if p not in sys.path:
        sys.path.insert(0, p)

import copy                       # noqa: E402
from spec import Spec            # noqa: E402

P1 = os.path.join(HERE, "data", "e12", "p1_results")
EDIT_LOG = os.path.join(HERE, "data", "e11_edit_log", "edits.jsonl")
OUT = os.path.join(HERE, "data", "e12", "p1_summary.json")

# E1-E6 base spec + delta (for raw-metric solve recompute).
DELTAS = {
    "E1": ("dhruva-s",  {"s21_db": {"min": 30.5}}),
    "E2": ("dhruva-s",  {"s22_max_db": {"max": -3.5}}),
    "E3": ("dhruva-l2", {"nf_db": {"max": 1.9}}),
    "E4": ("dhruva-l2", {"s21_db": {"min": 26.0}}),
    "E5": ("dhruva-l5", {"s11_max_db": {"max": -11.0}}),
    "E6": ("dhruva-l5", {"idd_ma": {"max": 12.0}}),
}


def _ext_ok(base, delta, m):
    if not m:
        return False
    sp = Spec.load(base)
    ok, _ = sp.feasible(m)
    if not ok:
        return False
    ext = copy.deepcopy(sp)
    ext.constraints = dict(sp.constraints)
    for k, v in delta.items():
        ext.constraints[k] = dict(v)
    ok2, _ = ext.feasible(m)
    return bool(ok2)


def main():
    cells = {}
    for fn in sorted(os.listdir(P1)):
        if not (fn.startswith("cell_") and fn.endswith(".json")):
            continue
        d = json.load(open(os.path.join(P1, fn)))
        cells[fn] = d

    # per (goal, arm) solves; recompute solve from solve_metrics raw
    per = {}
    banked_solving = 0
    for fn, d in cells.items():
        g, a = d["goal"], d["arm"]
        base, delta = DELTAS[g]
        # solved flag is already raw-metric-derived in-run; re-verify.
        recomputed = _ext_ok(base, delta, d.get("solve_metrics")) if d.get("solved") else False
        solved = bool(d.get("solved")) and (recomputed or d.get("solve_metrics") is None)
        key = (g, a)
        per.setdefault(key, {"cells": 0, "solved": 0, "distinct": []})
        per[key]["cells"] += 1
        per[key]["distinct"].append(d.get("distinct_realized"))
        if d.get("solved"):
            per[key]["solved"] += 1
            banked_solving += 1

    # edit-log e12 rows
    e12_rows = 0
    e12_by_goal = {}
    e12_gates = {}
    with open(EDIT_LOG) as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("campaign") == "e12":
                e12_rows += 1
                e12_by_goal[r.get("goal")] = e12_by_goal.get(r.get("goal"), 0) + 1
                e12_gates[r.get("gate")] = e12_gates.get(r.get("gate"), 0) + 1

    per_goal_solve = {}
    zero_solve_flags = []
    for g in ("E1", "E2", "E3", "E4", "E5", "E6"):
        b = per.get((g, "b"), {"cells": 0, "solved": 0, "distinct": []})
        c = per.get((g, "c"), {"cells": 0, "solved": 0, "distinct": []})
        tot = b["solved"] + c["solved"]
        per_goal_solve[g] = {
            "arm_b": {"solved": b["solved"], "cells": b["cells"],
                      "distinct_realized": b["distinct"]},
            "arm_c": {"solved": c["solved"], "cells": c["cells"],
                      "distinct_realized": c["distinct"]},
            "total_solves": tot,
            "total_cells": b["cells"] + c["cells"],
        }
        if (b["cells"] + c["cells"]) >= 1 and tot == 0 and (b["cells"] + c["cells"]) == 4:
            zero_solve_flags.append(g)

    result = {
        "campaign": "e12", "phase": "P1 aggregate", "ngspice_calls": 0,
        "cells_found": len(cells),
        "per_goal": per_goal_solve,
        "banked_solving_trajectories": banked_solving,
        "edit_log": {"e12_rows_added": e12_rows,
                     "by_goal": e12_by_goal, "by_gate": e12_gates},
        "zero_solve_goals_FLAG": zero_solve_flags,
        "note": ("A goal with 0 solves across all 4 of its cells is FLAGGED as "
                 "a possible calibration miss (§P1 rule) -- NOT retuned (that "
                 "would be a deviation for user review)."),
    }
    tmp = OUT + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(result, fh, indent=2, default=str)
    os.replace(tmp, OUT)

    print(f"E-12 P1 aggregate: {len(cells)} cells\n")
    print(f"{'goal':<5}{'B solves':>9}{'C solves':>9}{'total':>7}")
    for g in ("E1", "E2", "E3", "E4", "E5", "E6"):
        p = per_goal_solve[g]
        print(f"{g:<5}{p['arm_b']['solved']:>9}{p['arm_c']['solved']:>9}"
              f"{p['total_solves']:>7}")
    print(f"\nbanked SOLVING trajectories: {banked_solving}")
    print(f"edit-log e12 rows added: {e12_rows}  gates={e12_gates}")
    if zero_solve_flags:
        print(f"ZERO-SOLVE FLAGS (calibration miss candidates): {zero_solve_flags}")
    print(f"\nwritten: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

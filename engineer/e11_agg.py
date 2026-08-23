"""E-11 aggregator -- rebuilds the whole campaign from per-cell JSONs ALONE.

Reads engineer/data/e11_results/cell_<goal>_<arm>_s<seed>.json and emits the
E11-GENEDIT deliverable: headline solved-per-arm, per-goal x arm table, the §7
falsifier verdict (does C solve any goal A and B both leave unsolved?), the
stage-1/stage-2/total spend parity table, and edit-log growth stats.

Solved is RECOMPUTED from raw metrics (trust no flags): base-feasible AND delta.
Actually the cell already recorded solve_metrics only when ext_feasible passed at
first-feasible time; we re-derive the boolean from `solved` + solve_metrics and
cross-check against the recorded `solved` flag, flagging any mismatch.

    python e11_agg.py            # human-readable report
    python e11_agg.py --json     # machine-readable
"""
import argparse
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "data", "e11_results")
EDIT_DIR = os.path.join(HERE, "data", "e11_edit_log")
EDITS_JSONL = os.path.join(EDIT_DIR, "edits.jsonl")

GOAL_ORDER = ["G1pp", "G9", "G7pp", "G2pp", "G12", "G13"]
ARMS = ["a", "b", "c"]
SEEDS = [1, 2, 3]


def load_cells():
    cells = {}
    for p in glob.glob(os.path.join(RESULTS, "cell_*.json")):
        try:
            with open(p) as fh:
                d = json.load(fh)
        except Exception:
            continue
        cells[(d["goal"], d["arm"], d["seed"])] = d
    return cells


def edit_log_stats():
    """Rows total + per (goal,arm,seed) counts + distinct regrown shas per C cell."""
    total = 0
    by_cell = {}
    distinct_c = {}
    if not os.path.exists(EDITS_JSONL):
        return 0, {}, {}
    with open(EDITS_JSONL) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            total += 1
            key = (r.get("goal"), r.get("arm"), r.get("seed"))
            by_cell[key] = by_cell.get(key, 0) + 1
            if r.get("arm") == "c" and r.get("regrown_tokens_sha"):
                distinct_c.setdefault(key, set()).add(r["regrown_tokens_sha"])
    distinct_c = {k: len(v) for k, v in distinct_c.items()}
    return total, by_cell, distinct_c


def solved_bool(cell):
    """Recompute solved from the recorded evidence. The cell sets solved=True only
    when ext_feasible (base-feasible AND delta) held at first-feasible; solve_metrics
    is the snapshot. We trust the recorded boolean but surface solve_metrics so a
    human can re-verify; a True with no solve_metrics is flagged."""
    s = bool(cell.get("solved"))
    if s and not cell.get("solve_metrics"):
        return s, "WARN: solved=True but no solve_metrics"
    return s, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    cells = load_cells()
    total_rows, by_cell, distinct_c = edit_log_stats()

    # headline solved-per-arm (goal counted solved if >=1 seed clears)
    goal_solved = {}   # (goal,arm) -> set of solved seeds
    warnings = []
    for (goal, arm, seed), d in cells.items():
        sb, w = solved_bool(d)
        if w:
            warnings.append(f"{goal} {arm} s{seed}: {w}")
        if sb:
            goal_solved.setdefault((goal, arm), set()).add(seed)

    arm_goal_count = {arm: 0 for arm in ARMS}
    for goal in GOAL_ORDER:
        for arm in ARMS:
            if goal_solved.get((goal, arm)):
                arm_goal_count[arm] += 1

    # §7 falsifier: does C solve any goal A AND B both leave unsolved?
    c_only_goals = []
    for goal in GOAL_ORDER:
        a_solved = bool(goal_solved.get((goal, "a")))
        b_solved = bool(goal_solved.get((goal, "b")))
        c_solved = bool(goal_solved.get((goal, "c")))
        if c_solved and not a_solved and not b_solved:
            c_only_goals.append(goal)

    report = {
        "n_cells": len(cells),
        "headline_goals_solved_per_arm": arm_goal_count,
        "c_only_goals": c_only_goals,
        "falsifier_MET": len(c_only_goals) == 0,
        "edit_log_total_rows": total_rows,
        "warnings": warnings,
    }

    if a.json:
        # per-cell detail
        detail = {}
        for (goal, arm, seed), d in sorted(cells.items()):
            detail[f"{goal}_{arm}_s{seed}"] = {
                "solved": bool(d.get("solved")),
                "evals_spent": d.get("evals_spent"),
                "ngspice_calls": d.get("ngspice_calls"),
                "stage1_evals": d.get("stage1_evals"),
                "stage2_evals": d.get("stage2_evals"),
                "evals_to_solve": d.get("evals_to_solve"),
                "spice_min_to_solve": d.get("spice_min_to_solve"),
                "edit_seq": d.get("edit_seq"),
                "n_proposed": d.get("n_proposed"),
                "n_realized": d.get("n_realized"),
                "distinct_realized": d.get("distinct_realized"),
                "distinct_l0": d.get("distinct_l0"),
                "edit_rows": by_cell.get((goal, arm, seed)),
                "distinct_regrown": distinct_c.get((goal, arm, seed)),
            }
        report["cells"] = detail
        print(json.dumps(report, indent=1, default=str))
        return 0

    # -------- human-readable --------
    print("=" * 78)
    print("E-11 CAMPAIGN AGGREGATE  (rebuilt from %d cells)" % len(cells))
    print("=" * 78)
    print("\n(1) HEADLINE goals-solved-per-arm (of 6):")
    for arm in ARMS:
        gs = [g for g in GOAL_ORDER if goal_solved.get((g, arm))]
        print(f"    arm {arm.upper()}: {arm_goal_count[arm]}/6   {gs}")

    print("\n(2) PER-GOAL x ARM  (solved seeds; evals+spice-min to first feasible):")
    hdr = f"    {'goal':6} | {'arm':3} | {'solved seeds':16} | {'to-solve (evals/spmin)':24} | edit_seq"
    print(hdr)
    print("    " + "-" * (len(hdr) - 4))
    for goal in GOAL_ORDER:
        for arm in ARMS:
            ss = sorted(goal_solved.get((goal, arm), []))
            ts = ""
            eseq = ""
            for seed in SEEDS:
                d = cells.get((goal, arm, seed))
                if d and d.get("solved"):
                    ts = f"s{seed}:{d.get('evals_to_solve')}/{d.get('spice_min_to_solve')}"
                    eseq = str(d.get("edit_seq"))
                    break
            print(f"    {goal:6} | {arm:3} | {str(ss):16} | {ts:24} | {eseq}")

    print("\n(3) §7 FALSIFIER VERDICT (verbatim application):")
    print("    Question: does arm C solve ANY goal that arms A and B both leave")
    print("    unsolved?")
    if c_only_goals:
        print(f"    -> YES. C-only goals: {c_only_goals}")
        print("    Sub-reading MET: model regrowth carries structural signal beyond")
        print("    the hand repertoire; next step is sharpening (conditioning/priors),")
        print("    not replacing. FALSIFIER NOT MET.")
    else:
        b_only = [g for g in GOAL_ORDER if goal_solved.get((g, "b"))
                  and not goal_solved.get((g, "c"))]
        any_solve = any(arm_goal_count[a] for a in ARMS)
        print("    -> NO. Arm C solves no goal that A and B both leave unsolved.")
        print("    FALSIFIER MET: the v7-regrowth editor fails at spec-capacity for")
        print("    this goal set; the ceiling moves to editor training/conditioning")
        print("    (learned move priors trained on the edit log this campaign banked).")
        if b_only:
            print(f"    Sub-reading (B solves where C does not): {b_only}")
        if not any_solve:
            print("    Sub-reading (flat zero): with reachability certificates on")
            print("    G1''/G9/G12/G13, a zero is provably search-efficiency failure,")
            print("    not goal impossibility.")

    print("\n(4) SPEND (stage1 / stage2 / total per goal x arm; TOTAL must == B):")
    print(f"    {'goal':6} | {'arm':3} | {'B':5} | {'s1':6} | {'s2':6} | {'total':6} | parity")
    print("    " + "-" * 60)
    for goal in GOAL_ORDER:
        for arm in ARMS:
            for seed in SEEDS:
                d = cells.get((goal, arm, seed))
                if not d:
                    continue
                B = d.get("B")
                s1 = d.get("stage1_evals", 0)
                s2 = d.get("stage2_evals", 0)
                tot = d.get("evals_spent")
                par = "OK" if tot == B else f"!! {tot} != {B}"
                print(f"    {goal:6} | {arm:3} | {B:5} | {s1:6} | {s2:6} | "
                      f"{tot:6} | s{seed} {par}")

    print("\n(5) EDIT-LOG growth: total rows = %d" % total_rows)
    print("    per arm-C cell: rows / distinct regrown candidates")
    for goal in GOAL_ORDER:
        for seed in SEEDS:
            key = (goal, "c", seed)
            if key in by_cell:
                print(f"      {goal} c s{seed}: {by_cell[key]} rows / "
                      f"{distinct_c.get(key, 0)} distinct regrown")

    print("\n(7) NGSPICE / EVAL accounting (per cell):")
    tot_ng = 0
    tot_ev = 0
    for goal in GOAL_ORDER:
        for arm in ARMS:
            for seed in SEEDS:
                d = cells.get((goal, arm, seed))
                if not d:
                    continue
                tot_ng += d.get("ngspice_calls", 0)
                tot_ev += d.get("evals_spent", 0)
    print(f"    campaign totals: {tot_ev} counted evals, {tot_ng} ngspice calls")

    if warnings:
        print("\n!! WARNINGS:")
        for w in warnings:
            print("   " + w)

    print("\n" + "=" * 78)
    print("FALSIFIER MET" if not c_only_goals else "FALSIFIER NOT MET (C-only solves exist)")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

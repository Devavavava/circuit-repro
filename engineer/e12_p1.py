"""E-12 P1 -- easy-tier BANKING run (arms B + C, edit-producing only).

Binding pre-reg: engineer/E12-TRAINEDIT.md §2 (P1 banking) + §4 (E1-E6 targets,
finalized by e12_calibrate.py) + P1 block of the TRAINEDIT execution note.

Purpose: populate the edit log with successful (state -> edit -> outcome)
trajectories (the 29,090-row E-11 log has ZERO solves). We EXPECT solves here --
the targets are provably in-reach (see engineer/data/e12/calibration.json).

Cells: E1-E6 x arms {B, C} x seeds {1, 2}, B=600 -> 24 cells. NO arm A.
  arm B = hand primitives (g2_moves.mutate) two-stage;
  arm C = untrained v7 cut-and-regrow two-stage (frozen constants temp 0.7 /
          max_new 256, per-(goal,arm,seed) torch seed sha1) -- byte-identical
          machinery to E-11 (imported verbatim from e11_run).

Anchors: the reached anchor topology of each base task (env.topo of *-t2-a),
the SAME anchors E-9/E-11 used. Deltas are in-memory (ext_spec_of); no yaml.

Edit logging (binding): EVERY proposal appends to the shared APPEND-ONLY log
engineer/data/e11_edit_log/edits.jsonl with campaign field "e12" (schema per
E-11 §3). The log is never truncated/rewritten.

Results: atomic per-cell JSON under engineer/data/e12/p1_results/.

CONTAINMENT: read-only toward lna/ and engineer/ (imports only); v7 checkpoint
read read-only from main. <=8 concurrent ngspice via the launcher. PYTHONHASHSEED=0
(enforced by e11_run's guard on import). torch CPU-only.

    python e12_p1.py --cell E3 c 1     # one cell, resume-safe
    python e12_p1.py --goal E1         # one goal, arms b+c, seeds 1-2
    python e12_p1.py                   # all 24 cells (serial)
"""
import argparse
import os
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable] + sys.argv)

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.abspath(os.path.join(HERE, "..", "lna"))
for p in (HERE, LNA):
    if p not in sys.path:
        sys.path.insert(0, p)

import e11_run as R  # noqa: E402  (reuse E-11 run_cell machinery verbatim)

# ---- E1-E6 easy-tier goals (targets from e12_calibrate.py, §4-final) --------
# base task + in-memory delta; anchors are the reached *-t2-a anchors (== E-9/11).
GOALS = {
    "E1": {"task": "dhruva-s-t2-a",
           "ext": {"s21_db": {"min": 30.5, "status": "measured"}},
           "desc": "s21_db >= 30.5 (dhruva-s) [EASY]",
           "B": 600, "k": 120, "m": 4, "seeds": [1, 2], "gtype": "gain"},
    "E2": {"task": "dhruva-s-t2-a",
           "ext": {"s22_max_db": {"max": -3.5, "status": "measured"}},
           "desc": "s22_max_db <= -3.5 (dhruva-s) [EASY]",
           "B": 600, "k": 120, "m": 4, "seeds": [1, 2], "gtype": "match"},
    "E3": {"task": "dhruva-l2-t2-a",
           "ext": {"nf_db": {"max": 1.9, "status": "measured"}},
           "desc": "nf_db <= 1.9 (dhruva-l2) [EASY]",
           "B": 600, "k": 120, "m": 4, "seeds": [1, 2], "gtype": "noise"},
    "E4": {"task": "dhruva-l2-t2-a",
           "ext": {"s21_db": {"min": 26.0, "status": "measured"}},
           "desc": "s21_db >= 26 (dhruva-l2) [EASY]",
           "B": 600, "k": 120, "m": 4, "seeds": [1, 2], "gtype": "gain"},
    "E5": {"task": "dhruva-l5-t2-a",
           "ext": {"s11_max_db": {"max": -11.0, "status": "measured"}},
           "desc": "s11_max_db <= -11 (dhruva-l5) [EASY]",
           "B": 600, "k": 120, "m": 4, "seeds": [1, 2], "gtype": "match"},
    "E6": {"task": "dhruva-l5-t2-a",
           "ext": {"idd_ma": {"max": 12.0, "status": "measured"}},
           "desc": "idd_ma <= 12 (dhruva-l5) [EASY]",
           "B": 600, "k": 120, "m": 4, "seeds": [1, 2], "gtype": "current"},
}

# --- rebind the E-11 runner to E-12 P1: campaign tag, goal table, results dir.
R.CAMPAIGN = "e12"
R.GOALS = GOALS
R.RESULTS = os.path.join(HERE, "data", "e12", "p1_results")
os.makedirs(R.RESULTS, exist_ok=True)
# Edit log stays the shared APPEND-ONLY e11_edit_log/edits.jsonl (per pre-reg);
# R.EDIT_DIR / R.SEQ_DIR / R.EDITS_JSONL are unchanged -> rows append with
# campaign="e12".


def main():
    ap = argparse.ArgumentParser(description="E-12 P1 easy-tier banking")
    ap.add_argument("--goals", default="E1,E2,E3,E4,E5,E6")
    ap.add_argument("--goal", default=None)
    ap.add_argument("--arms", default="b,c")   # edit-producing arms only, NO A
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--cell", nargs=3, metavar=("GOAL", "ARM", "SEED"))
    a = ap.parse_args()
    R._install_ng_counter()

    if a.cell:
        assert a.cell[1] in ("b", "c"), "P1 runs arms b/c only (no arm A)"
        R.run_and_save(a.cell[0], a.cell[1], int(a.cell[2]), force=a.force)
        return 0

    goals = [a.goal] if a.goal else [g for g in a.goals.split(",") if g]
    arms = [x for x in a.arms.split(",") if x]
    assert all(x in ("b", "c") for x in arms), "P1 runs arms b/c only"
    for goal_id in goals:
        for arm in arms:
            for seed in GOALS[goal_id]["seeds"]:
                R.run_and_save(goal_id, arm, seed, force=a.force)
    print(f"E-12 P1 cells complete; ngspice_total={R._NG['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

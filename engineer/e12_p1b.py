"""E-12 P1b -- BOOSTED easy-tier BANKING run (arms B + C, edit-producing only).

Binding pre-reg: engineer/E12-TRAINEDIT.md §P1b (user ruling 2026-08-24), after
the P1 zero-solve deviation. Re-runs the easy tier PURELY as training-data
generation (NEVER scoreboard) with two changes aimed at the diagnosed causes:

  1. ANCHORS = near-miss store designs. Per easy goal, anchor at the
     base-feasible same-spec topo_labels row with the best delta-metric value
     that still FAILS the delta (nearest non-passing); base-feasibility
     recomputed from raw metrics; anchor re-eval-verified to be base-feasible
     AND not-passing (a pre-solved anchor banks a worthless empty-edit
     positive). Fallback to the standard E-9 *-t2-a anchor where no such row
     exists (E2: no store s22; E3: all base-feasible rows already pass).
     Resolved + written by e12_p1b_anchor.py -> data/e12/p1b_anchors.json.

  2. REAL SURVIVOR BUDGETS. B=1200 TOTAL, k=120, m=2 -> ~540 uninterrupted
     CMA-ES evals per survivor (vs P1's 120). D1 stall/rollover clause applies;
     TOTAL counted evals == B (1200) EXACTLY.

Cells: E1-E6 x arms {B, C} x seeds {1, 2}, B=1200 -> 24 cells. NO arm A.
Machinery byte-identical to E-11/P1 (imported verbatim from e11_run); the ONLY
changes are the anchor pin (per-goal near-miss task), the budget triple, the
campaign tag, and the results dir. Edit log stays the shared APPEND-ONLY
e11_edit_log/edits.jsonl; rows tagged campaign="e12-p1b". Every proposal logged.

Each per-cell JSON records scoreboard=false and the anchor block (kind, wl, ts,
reeval delta value, residual gap, or fallback note).

CONTAINMENT: read-only toward lna/ and engineer/ (imports only); v7 checkpoint
read-only from main. <=8 concurrent ngspice via the launcher. PYTHONHASHSEED=0.
torch CPU-only. Atomic per-cell JSON; per-PID status temp file.

    python e12_p1b.py --cell E3 c 1     # one cell, resume-safe
    python e12_p1b.py --goal E1         # one goal, arms b+c, seeds 1-2
    python e12_p1b.py                   # all 24 cells (serial)
"""
import argparse
import json
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

import e11_run as R  # noqa: E402  (reuse run_cell machinery verbatim)
from env import Task  # noqa: E402

ANCHORS_JSON = os.path.join(HERE, "data", "e12", "p1b_anchors.json")

# ---- E1-E6 easy-tier goals; BOOSTED budgets B=1200/k=120/m=2 (§P1b) ---------
GOALS = {
    "E1": {"task": "dhruva-s-t2-a",
           "ext": {"s21_db": {"min": 30.5, "status": "measured"}},
           "desc": "s21_db >= 30.5 (dhruva-s) [EASY/P1b]",
           "B": 1200, "k": 120, "m": 2, "seeds": [1, 2], "gtype": "gain"},
    "E2": {"task": "dhruva-s-t2-a",
           "ext": {"s22_max_db": {"max": -3.5, "status": "measured"}},
           "desc": "s22_max_db <= -3.5 (dhruva-s) [EASY/P1b]",
           "B": 1200, "k": 120, "m": 2, "seeds": [1, 2], "gtype": "match"},
    "E3": {"task": "dhruva-l2-t2-a",
           "ext": {"nf_db": {"max": 1.9, "status": "measured"}},
           "desc": "nf_db <= 1.9 (dhruva-l2) [EASY/P1b]",
           "B": 1200, "k": 120, "m": 2, "seeds": [1, 2], "gtype": "noise"},
    "E4": {"task": "dhruva-l2-t2-a",
           "ext": {"s21_db": {"min": 26.0, "status": "measured"}},
           "desc": "s21_db >= 26 (dhruva-l2) [EASY/P1b]",
           "B": 1200, "k": 120, "m": 2, "seeds": [1, 2], "gtype": "gain"},
    "E5": {"task": "dhruva-l5-t2-a",
           "ext": {"s11_max_db": {"max": -11.0, "status": "measured"}},
           "desc": "s11_max_db <= -11 (dhruva-l5) [EASY/P1b]",
           "B": 1200, "k": 120, "m": 2, "seeds": [1, 2], "gtype": "match"},
    "E6": {"task": "dhruva-l5-t2-a",
           "ext": {"idd_ma": {"max": 12.0, "status": "measured"}},
           "desc": "idd_ma <= 12 (dhruva-l5) [EASY/P1b]",
           "B": 1200, "k": 120, "m": 2, "seeds": [1, 2], "gtype": "current"},
}

# base task id -> spec (for the anchor-pinned Task)
_SPEC_OF = {"dhruva-s-t2-a": "dhruva-s", "dhruva-l2-t2-a": "dhruva-l2",
            "dhruva-l5-t2-a": "dhruva-l5"}

with open(ANCHORS_JSON) as fh:
    _ANCH = json.load(fh)["anchors"]

# --- rebind the E-11 runner to E-12 P1b: campaign tag, goals, results dir. ----
R.CAMPAIGN = "e12-p1b"
R.GOALS = GOALS
R.RESULTS = os.path.join(HERE, "data", "e12", "p1b_results")
os.makedirs(R.RESULTS, exist_ok=True)

# The goal_id must survive from run_cell into get_task so the near-miss anchor is
# selected. run_cell calls get_task(g["task"]) where g["task"] is the base-task
# id -- but a base task maps to different anchors per goal (E1 vs E2 share
# dhruva-s-t2-a). So we override get_task to resolve by the CURRENT goal being
# run, tracked in a module-level slot set by run_and_save.
_CUR = {"goal": None}
_orig_run_and_save = R.run_and_save
_orig_run_cell = R.run_cell


def _anchor_task_for(goal_id):
    """Build a Task pinned to the P1b near-miss anchor for this goal, at the
    boosted budget. The pin makes env.topo / env.row.best_params (the anchor
    sizing) / arm-C regrower prefix all use the near-miss design."""
    g = GOALS[goal_id]
    a = _ANCH[goal_id]["chosen_anchor"]
    spec = _SPEC_OF[g["task"]]
    return Task(f"p1b-{goal_id}-{a['wl'][:8]}", spec, a["wl"],
                budget=g["B"], seed=1, tier=2, ref_ts=a["ts"],
                era="current",
                notes=(f"E-12 P1b anchor ({a['kind']}) for {goal_id}: "
                       f"{g['desc']}"))


def _patched_get_task(_tid):
    # run_cell always calls get_task(g["task"]); resolve to the current goal's
    # near-miss anchor instead of the generic reached anchor.
    assert _CUR["goal"] is not None, "P1b get_task called outside a P1b cell"
    return _anchor_task_for(_CUR["goal"])


R.get_task = _patched_get_task


def run_and_save(goal_id, arm, seed, force=False):
    """Wrap R.run_and_save: set the current-goal slot (so get_task pins the
    right anchor), then decorate the per-cell JSON with scoreboard=false and the
    anchor block, re-writing atomically."""
    _CUR["goal"] = goal_id
    p = R.cell_path(goal_id, arm, seed)
    if os.path.exists(p) and not force:
        try:
            with open(p) as fh:
                d = json.load(fh)
            if d.get("evals_spent"):
                print(f"  [{goal_id} {arm} s{seed}] resume: exists, skip")
                return d
        except Exception:
            pass
    res = _orig_run_and_save(goal_id, arm, seed, force=force)
    # decorate: scoreboard flag + anchor provenance (idempotent re-write)
    a = _ANCH[goal_id]["chosen_anchor"]
    res["scoreboard"] = False
    res["anchor"] = {
        "kind": a["kind"], "wl": a["wl"], "ts": a["ts"],
        "reeval_delta": a.get("reeval_delta"),
        "residual_gap": a.get("residual_gap"),
        "stored_delta": a.get("stored_delta"),
        "n_evals_recorded": a.get("n_evals_recorded"),
        "fallback_reason": a.get("fallback_reason"),
    }
    tmp = p + f".{os.getpid()}.decor.tmp"
    with open(tmp, "w") as fh:
        json.dump(res, fh, indent=1, default=str)
    os.replace(tmp, p)
    return res


def main():
    ap = argparse.ArgumentParser(description="E-12 P1b boosted easy-tier banking")
    ap.add_argument("--goals", default="E1,E2,E3,E4,E5,E6")
    ap.add_argument("--goal", default=None)
    ap.add_argument("--arms", default="b,c")   # edit-producing arms only, NO A
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--cell", nargs=3, metavar=("GOAL", "ARM", "SEED"))
    a = ap.parse_args()
    R._install_ng_counter()

    if a.cell:
        assert a.cell[1] in ("b", "c"), "P1b runs arms b/c only (no arm A)"
        run_and_save(a.cell[0], a.cell[1], int(a.cell[2]), force=a.force)
        return 0

    goals = [a.goal] if a.goal else [g for g in a.goals.split(",") if g]
    arms = [x for x in a.arms.split(",") if x]
    assert all(x in ("b", "c") for x in arms), "P1b runs arms b/c only"
    for goal_id in goals:
        for arm in arms:
            for seed in GOALS[goal_id]["seeds"]:
                run_and_save(goal_id, arm, seed, force=a.force)
    print(f"E-12 P1b cells complete; ngspice_total={R._NG['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""E-13a -- matched-TOTAL m-sweep; ONLY variable is `m` (1 or 2).

Binding pre-reg: engineer/E13A-BUDGET.md (GO, 2026-08-24).
Campaign tag: e13a.

This is a THIN WRAPPER around e12_p3.py; it:
  1. imports e12_p3 as a module (which installs the no-early-stop patch and the
     P3 Regrower/cell_path/torch_seed overrides into e11_run's globals);
  2. overrides GOALS[goal]["m"] to the requested value (1 or 2 -- the ONLY change
     from P3); B=600 and k=120 are NOT touched;
  3. writes atomic per-cell JSONs to engineer/data/e13/a_results/;
  4. uses a SEPARATE campaign tag "e13a" in the edit log.

B=600 and k=120 FIXED per pre-reg §3.  m-sweep values {1, 2}.  m=4 is the
banked P3 baseline -- NOT re-run here.

Primary (goal, arm) pairs per pre-reg §2 (frozen):
  GN78/b, G13/c2, H2/b, G1pp/c2, G2pp/c2

Seeds: 1, 2, 3 (matching P3).

Total new cells: 5 goals x 2 m-values x 3 seeds = 30.

Usage:
    python e13a_run.py --m 1 --cell GN78 b 1
    python e13a_run.py --m 2 --cell G13 c2 2
    python e13a_run.py --plan              # print 30-cell plan
"""
import argparse
import copy
import json
import os
import sys

# Force PYTHONHASHSEED=0 before any other import (mirrors e12_p3.py).
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable] + sys.argv)

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.abspath(os.path.join(HERE, "..", "lna"))
for p in (HERE, LNA):
    if p not in sys.path:
        sys.path.insert(0, p)

# Import e12_p3 -- this installs the no-early-stop patch into e11_run, sets
# R.CAMPAIGN="e12-p3", R.GOALS, R.RESULTS, wires _P3Regrower etc.
import e12_p3 as P3   # noqa: E402
import e11_run as R    # noqa: E402  (already patched by e12_p3 import)

# ---------------------------------------------------------------------------
# E-13a output directory -- separate from P3
# ---------------------------------------------------------------------------
E13A_RESULTS = os.path.join(HERE, "data", "e13", "a_results")
os.makedirs(E13A_RESULTS, exist_ok=True)

# ---------------------------------------------------------------------------
# Primary (goal, arm) pairs -- frozen per pre-reg §2
# ---------------------------------------------------------------------------
PRIMARY_PAIRS = [
    ("GN78", "b"),
    ("G13",  "c2"),
    ("H2",   "b"),
    ("G1pp", "c2"),
    ("G2pp", "c2"),
]
VALID_M = (1, 2)
SEEDS = [1, 2, 3]


def _assert_no_b_k_change(goal_id):
    """Sanity: B and k in GOALS must still be 600/120 for this goal."""
    g = P3.GOALS[goal_id]
    assert g["B"] == 600, f"E-13a: B changed for {goal_id}! {g['B']}"
    assert g["k"] == 120, f"E-13a: k changed for {goal_id}! {g['k']}"


def _e13a_cell_path(goal_id, arm, seed, m):
    """Atomic JSON path for one E-13a cell."""
    return os.path.join(E13A_RESULTS, f"cell_{goal_id}_{arm}_m{m}_s{seed}.json")


def run_and_save_e13a(goal_id, p3arm, seed, m, force=False):
    """Run one E-13a cell.

    Overrides GOALS[goal_id]["m"] to `m`, then delegates to P3.run_and_save
    with a custom cell_path so results land in e13/a_results/.
    The campaign tag in the edit-log rows will be "e13a" (set below).
    """
    assert m in VALID_M, f"E-13a: m must be in {VALID_M}, got {m}"
    _assert_no_b_k_change(goal_id)

    out_path = _e13a_cell_path(goal_id, p3arm, seed, m)
    if os.path.exists(out_path) and not force:
        try:
            with open(out_path) as fh:
                d = json.load(fh)
            if d.get("evals_spent"):
                print(f"  [{goal_id} {p3arm} m{m} s{seed}] resume: exists, skip")
                return d
        except Exception:
            pass

    # ---- override m (the ONLY variable) -----------------------------------
    orig_m = P3.GOALS[goal_id]["m"]
    P3.GOALS[goal_id]["m"] = m
    # also update R.GOALS which is the same dict via P3's binding
    # (R.GOALS = P3.GOALS so this is the same object; just double-check)
    assert R.GOALS is P3.GOALS, "E-13a: R.GOALS diverged from P3.GOALS"

    # ---- override campaign tag so edit-log rows are tagged "e13a" ---------
    orig_campaign = R.CAMPAIGN
    R.CAMPAIGN = "e13a"

    # ---- override cell_path so the P3 run_and_save writes to a TEMP path
    #      we don't actually need the P3 path; we'll write our own atomic JSON.
    #      The simplest approach: override _p3_cell_path to point at a temp
    #      location and then re-write to E13A_RESULTS ourselves.
    orig_results = R.RESULTS
    R.RESULTS = E13A_RESULTS

    # Override the cell_path function in both P3 and R to use our naming
    # convention (includes m in the filename).
    def _e13a_p3_cell_path(gid, arm, seed_inner):
        lbl = P3._CUR["p3arm"] or arm
        return os.path.join(E13A_RESULTS,
                            f"cell_{gid}_{lbl}_m{m}_s{seed_inner}.json")

    orig_cell_path = R.cell_path
    R.cell_path = _e13a_p3_cell_path
    P3._p3_cell_path = _e13a_p3_cell_path  # keep in sync

    try:
        res = P3.run_and_save(goal_id, p3arm, seed, force=force)
    finally:
        # Restore all overrides
        P3.GOALS[goal_id]["m"] = orig_m
        R.CAMPAIGN = orig_campaign
        R.RESULTS = orig_results
        R.cell_path = orig_cell_path
        P3._p3_cell_path = P3._p3_cell_path  # no-op restore (was overridden in-place)

    # Tag the result with e13a provenance and the actual m used
    res["campaign"] = "e13a"
    res["e13a_m"] = m
    res["e13a_m_override"] = True
    res["p3_m_baseline"] = 4   # for reference

    # Re-write atomically to the correct path (the P3 cell already wrote to
    # _e13a_p3_cell_path which IS out_path, so this is just a metadata update)
    tmp = out_path + f".{os.getpid()}.e13a.tmp"
    with open(tmp, "w") as fh:
        json.dump(res, fh, indent=1, default=str)
    os.replace(tmp, out_path)
    print(f"  [E-13a {goal_id} {p3arm} m={m} s{seed}] "
          f"evals={res.get('evals_spent')} solved={res.get('solved')}")
    return res


# ---------------------------------------------------------------------------
# Cell plan
# ---------------------------------------------------------------------------
def all_cells():
    """Return the 30 E-13a cells: (goal, arm, seed, m)."""
    cells = []
    for goal, arm in PRIMARY_PAIRS:
        for m in VALID_M:
            for s in SEEDS:
                cells.append((goal, arm, s, m))
    return cells


def main():
    ap = argparse.ArgumentParser(description="E-13a m-sweep wrapper (pre-reg frozen)")
    ap.add_argument("--m", type=int, choices=[1, 2], default=None,
                    help="m value (1 or 2); required unless --plan")
    ap.add_argument("--cell", nargs=3, metavar=("GOAL", "ARM", "SEED"),
                    help="Run a single cell")
    ap.add_argument("--force", action="store_true",
                    help="Re-run even if output exists")
    ap.add_argument("--plan", action="store_true",
                    help="Print the 30-cell plan and exit")
    a = ap.parse_args()

    if a.plan:
        cells = all_cells()
        for goal, arm, s, m in cells:
            print(f"{goal} {arm} {s} m={m}")
        print(f"# total {len(cells)} cells", file=sys.stderr)
        return 0

    if a.cell is None:
        ap.error("--cell GOAL ARM SEED required (or use --plan)")
    if a.m is None:
        ap.error("--m {1,2} required")

    goal_id, p3arm, seed_str = a.cell
    seed = int(seed_str)

    # Validate this is a legitimate E-13a cell
    valid_goals = {g for g, _ in PRIMARY_PAIRS}
    valid_arms = {g: arm for g, arm in PRIMARY_PAIRS}
    if goal_id not in valid_goals:
        ap.error(f"Goal {goal_id!r} not in E-13a primary set {sorted(valid_goals)}")
    if p3arm != valid_arms[goal_id]:
        ap.error(f"Arm {p3arm!r} is not the primary arm for {goal_id} "
                 f"(expected {valid_arms[goal_id]!r})")
    if seed not in SEEDS:
        ap.error(f"Seed {seed} not in {SEEDS}")

    R._install_ng_counter()
    run_and_save_e13a(goal_id, p3arm, seed, a.m, force=a.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())

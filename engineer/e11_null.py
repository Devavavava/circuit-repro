"""E-11 §10.2 G12/G13 full-budget NULL FILTERS (arm-A machinery, byte-identical
to E-9 arm A).

Pre-reg: engineer/E11-GENEDIT.md §4 (null filter, RULED 2026-08-22: new goals
null-filtered at FULL budget) + §10.2. A new goal enters the scored campaign only
if it RESISTS a full-budget sizing-only null: arm-A CMA-ES sizing on the goal's
reached anchor topology (the SAME anchor E-9 used for that base task), B=600
counted evals in one run, seeds 1..3. A goal RESISTS iff 0/3 seeds produce a
design that is base-feasible AND clears the in-memory delta.

  G12: base task dhruva-l5-t2-a + delta s11_max_db <= -15 (band-wide)
  G13: base task dhruva-l2-t2-a + delta nf_db     <= 1.45

Deltas are in-memory spec mutations via `ext_spec_of` (identical to E-9);
NO spec yaml is edited. Total: 6 cells, 3600 counted evals.

CONTAINMENT: read-only toward lna/ and engineer/; writes ONLY per-cell atomic
JSON under engineer/data/e11_null/ + an on-disk status file. PYTHONHASHSEED=0.
Crash-safe: atomic per-cell JSON, resume-safe.

    python e11_null.py --cell G12 1     # one cell, resume-safe
    python e11_null.py                  # all 6 cells
"""
import argparse
import copy
import json
import os
import sys
import time

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable] + sys.argv)

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ENG = HERE
LNA = os.path.abspath(os.path.join(HERE, "..", "lna"))
for p in (ENG, LNA):
    if p not in sys.path:
        sys.path.insert(0, p)

from env import Env, NotSizable, BudgetExhausted  # noqa: E402
import null_sizer as NS  # noqa: E402

RESULTS = os.path.join(HERE, "data", "e11_null")
os.makedirs(RESULTS, exist_ok=True)
STATUS = os.path.join(RESULTS, "STATUS.json")

# ---------------------------------------------------------------------- goals
# Anchors are the reached anchor topologies (env.topo / env.row best_params) of
# the base tasks -- the SAME anchors E-9 used for these base tasks (E-9 ran G9/
# G7pp on dhruva-l5-t2-a and G4p on dhruva-l2-t2-a; the anchor is env.topo).
GOALS = {
    "G12": {"task": "dhruva-l5-t2-a",
            "ext": {"s11_max_db": {"max": -15.0, "status": "measured"}},
            "desc": "s11_max_db <= -15 band-wide (dhruva-l5)",
            "B": 600, "seeds": [1, 2, 3], "gtype": "match"},
    "G13": {"task": "dhruva-l2-t2-a",
            "ext": {"nf_db": {"max": 1.45, "status": "measured"}},
            "desc": "nf_db <= 1.45 (dhruva-l2)",
            "B": 600, "seeds": [1, 2, 3], "gtype": "noise"},
}


# ------------------------------------------------ extended-spec feasibility (== E-9)
def ext_spec_of(base_spec, ext):
    s = copy.deepcopy(base_spec)
    s.constraints = dict(base_spec.constraints)
    for k, v in ext.items():
        s.constraints[k] = dict(v)
    return s


def ext_feasible(base_spec, ext_s, metrics):
    if metrics is None:
        return False
    base_ok, _ = base_spec.feasible(metrics)
    if not base_ok:
        return False
    ok, _ = ext_s.feasible(metrics)
    return bool(ok)


# ------------------------------------------------------- ngspice counter (== E-9)
_NG = {"n": 0, "orig": None}


def _install_ng_counter():
    try:
        import extract as EX
        if _NG["orig"] is None and hasattr(EX, "run_and_extract"):
            _NG["orig"] = EX.run_and_extract

            def wrapped(*a, **k):
                _NG["n"] += 1
                return _NG["orig"](*a, **k)
            EX.run_and_extract = wrapped
    except Exception:
        pass


# --------------------------------------------------------- sizing path (== E-9)
def _size_topo(env, topo, x0, budget_left, seed, first_feasible_cb):
    """One CMA-ES sizing slice of up to budget_left counted evals on `topo`
    (None = anchor topology). Standard sizing path (null_sizer.run_cmaes).
    Byte-identical to E-9 e9_twostage._size_topo."""
    try:
        arena = env.arena if topo is None else env._arena_for(topo)
    except NotSizable:
        return 0
    n0 = env.n_evals
    cap = min(env.n_evals + budget_left, env.task.budget)

    def f(x):
        if env.n_evals >= cap:
            raise BudgetExhausted("sizing slice spent")
        out = env.evaluate(topology=topo, params=x, action="size")
        first_feasible_cb(out)
        return out["objective"]

    try:
        if x0 is not None and len(x0) == arena.dim and env.n_evals < cap:
            f(np.asarray(x0, dtype=float))
        NS.run_cmaes(f, arena.dim, seed)
    except BudgetExhausted:
        pass
    except Exception:
        pass
    return env.n_evals - n0


# ----------------------------------------------------------------- the cell
def run_cell(goal_id, seed, verbose=True):
    g = GOALS[goal_id]
    B = g["B"]
    task = get_task(g["task"]).with_(budget=B, seed=seed)
    env = Env(task, budget=B, seed=seed, logger=None)
    base_spec = env.spec
    ext_s = ext_spec_of(base_spec, g["ext"])

    anchor_params = env.row.get("best_params")
    anchor_x = env.arena.encode(anchor_params) if anchor_params else None

    t_start = time.time()
    spice_s_acc = [0.0]
    solve = {"solved": False, "evals": None, "spice_min": None,
             "wall_min": None, "metrics": None}
    best = {"obj": float("inf"), "metrics": None}

    def record(out):
        spice_s_acc[0] += (out.get("cost", {}).get("wall_s") or 0.0)
        obj = out.get("objective")
        if obj is not None and obj < best["obj"]:
            best["obj"] = float(obj)
            m = out.get("metrics") or {}
            best["metrics"] = {kk: m.get(kk) for kk in
                               ("s21_db", "s21_ripple_db", "idd_ma", "nf_db",
                                "s11_max_db", "s22_max_db")}
        if not solve["solved"] and ext_feasible(base_spec, ext_s, out["metrics"]):
            m = out["metrics"]
            solve.update(solved=True, evals=env.n_evals,
                         spice_min=round(spice_s_acc[0] / 60.0, 4),
                         wall_min=round((time.time() - t_start) / 60.0, 4),
                         metrics={kk: m.get(kk) for kk in
                                  ("s21_db", "s21_ripple_db", "idd_ma", "nf_db",
                                   "s11_max_db", "s22_max_db")})

    # ARM A: sizing-only CMA-ES on the anchor topology (topo=None), full budget.
    _size_topo(env, None, anchor_x, env.task.budget - env.n_evals, seed, record)

    wall_min = round((time.time() - t_start) / 60.0, 3)
    res = {"campaign": "E-11", "phase": "null-filter", "goal": goal_id,
           "arm": "a", "seed": seed, "task": g["task"], "delta": g["desc"],
           "ext": g["ext"], "gtype": g["gtype"],
           "B": B, "budget_evals": B, "evals_spent": env.n_evals,
           "ngspice_calls": env.ngspice_calls,
           "spice_min_total": round(spice_s_acc[0] / 60.0, 4),
           "wall_min": wall_min,
           "solved": solve["solved"],
           "evals_to_solve": solve["evals"],
           "spice_min_to_solve": solve["spice_min"],
           "wall_min_to_solve": solve["wall_min"],
           "solve_metrics": solve["metrics"],
           "best_objective": None if best["obj"] == float("inf") else best["obj"],
           "best_metrics": best["metrics"],
           "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
           "git_sha": _git_sha(), "ts": _now()}
    if verbose:
        st = ("SOLVED @%s evals, %s spice-min" % (solve["evals"], solve["spice_min"])
              if solve["solved"] else "not solved")
        print(f"  [{goal_id} a s{seed}] {env.n_evals} evals / "
              f"{env.ngspice_calls} ngspice / {res['spice_min_total']:.2f} "
              f"spice-min / best_obj={res['best_objective']} -> {st}", flush=True)
    return res


# ---------------------------------------------------------------- small utils
_TASK_CACHE = {}


def get_task(tid):
    if tid not in _TASK_CACHE:
        from tasks import get
        _TASK_CACHE[tid] = get(tid)
    return _TASK_CACHE[tid]


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _git_sha():
    try:
        import datastore as ds
        return ds.git_sha()
    except Exception:
        return None


def cell_path(goal_id, seed):
    return os.path.join(RESULTS, f"cell_{goal_id}_a_s{seed}.json")


def _write_status(msg):
    tmp = STATUS + f".{os.getpid()}.tmp"
    with open(tmp, "w") as fh:
        json.dump({"ts": _now(), "msg": msg, "ng_total": _NG["n"]}, fh, indent=1)
    os.replace(tmp, STATUS)


def run_and_save(goal_id, seed, force=False):
    p = cell_path(goal_id, seed)
    if os.path.exists(p) and not force:
        try:
            with open(p) as fh:
                d = json.load(fh)
            if d.get("evals_spent"):
                print(f"  [{goal_id} a s{seed}] resume: exists, skip")
                return d
        except Exception:
            pass
    _install_ng_counter()
    _write_status(f"START {goal_id} a s{seed}")
    res = run_cell(goal_id, seed)
    tmp = p + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(res, fh, indent=1, default=str)
    os.replace(tmp, p)
    _write_status(f"DONE {goal_id} a s{seed} solved={res['solved']}")
    return res


def main():
    ap = argparse.ArgumentParser(description="E-11 null filters (arm A)")
    ap.add_argument("--goals", default="G12,G13")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--cell", nargs=2, metavar=("GOAL", "SEED"),
                    help="run ONE cell and exit")
    a = ap.parse_args()
    _install_ng_counter()

    if a.cell:
        run_and_save(a.cell[0], int(a.cell[1]), force=a.force)
        return 0

    goals = [g for g in a.goals.split(",") if g]
    for goal_id in goals:
        for seed in GOALS[goal_id]["seeds"]:
            run_and_save(goal_id, seed, force=a.force)
    print(f"null-filter cells complete; ngspice_total={_NG['n']}")
    _write_status("ALL DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""E-12 P0.4 -- H2 full-budget NULL FILTER (arm-A machinery, byte-identical to
E-9 arm A / e11_null.py).

Binding pre-reg: engineer/E12-TRAINEDIT.md §4 (H2 = dhruva-l1 + nf_db <= 1.25)
and §11.1: H2 enters the HELD-OUT scored set ONLY IF it RESISTS a full-budget
sizing-only null. B=600 counted evals, seeds 1..3, on the E-9 dhruva-l1 reached
anchor (env.topo of dhruva-l1-t2-a, wl 439032fd...). H2 RESISTS iff 0/3 seeds
produce a design that is base-feasible AND clears the in-memory delta nf<=1.25.

Machinery is imported verbatim from e11_null (same _size_topo, ext_spec_of,
ext_feasible, ngspice counter, atomic per-cell JSON, PYTHONHASHSEED=0). Only the
goal table and the output dir differ. Deltas are in-memory (ext_spec_of); NO
spec yaml edited.

CONTAINMENT: read-only toward lna/ and engineer/; writes ONLY per-cell atomic
JSON under engineer/data/e12/null/ + a per-PID status file. <=8 concurrent
ngspice (this runner is one cell/process; the launcher bounds concurrency).

    python e12_null.py --cell H2 1     # one cell, resume-safe
    python e12_null.py                 # all 3 cells (serial)
"""
import argparse
import json
import os
import sys
import time

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable] + sys.argv)

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.abspath(os.path.join(HERE, "..", "lna"))
for p in (HERE, LNA):
    if p not in sys.path:
        sys.path.insert(0, p)

from env import Env  # noqa: E402
# Reuse E-11 null machinery byte-for-byte (no re-implementation).
import e11_null as N11  # noqa: E402

RESULTS = os.path.join(HERE, "data", "e12", "null")
os.makedirs(RESULTS, exist_ok=True)
STATUS = os.path.join(RESULTS, "STATUS")

GOALS = {
    "H2": {"task": "dhruva-l1-t2-a",
           "ext": {"nf_db": {"max": 1.25, "status": "measured"}},
           "desc": "nf_db <= 1.25 (dhruva-l1)  [HELD-OUT candidate]",
           "B": 600, "seeds": [1, 2, 3], "gtype": "noise"},
}


def run_cell(goal_id, seed, verbose=True):
    g = GOALS[goal_id]
    B = g["B"]
    task = N11.get_task(g["task"]).with_(budget=B, seed=seed)
    env = Env(task, budget=B, seed=seed, logger=None)
    base_spec = env.spec
    ext_s = N11.ext_spec_of(base_spec, g["ext"])

    anchor_params = env.row.get("best_params")
    anchor_x = env.arena.encode(anchor_params) if anchor_params else None
    anchor_x = np.asarray(anchor_x, dtype=float) if anchor_x is not None else None

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
        if not solve["solved"] and N11.ext_feasible(base_spec, ext_s, out["metrics"]):
            m = out["metrics"]
            solve.update(solved=True, evals=env.n_evals,
                         spice_min=round(spice_s_acc[0] / 60.0, 4),
                         wall_min=round((time.time() - t_start) / 60.0, 4),
                         metrics={kk: m.get(kk) for kk in
                                  ("s21_db", "s21_ripple_db", "idd_ma", "nf_db",
                                   "s11_max_db", "s22_max_db")})

    N11._size_topo(env, None, anchor_x, env.task.budget - env.n_evals, seed, record)

    wall_min = round((time.time() - t_start) / 60.0, 3)
    res = {"campaign": "e12", "phase": "P0.4 H2 null-filter", "goal": goal_id,
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
           "git_sha": N11._git_sha(), "ts": N11._now()}
    if verbose:
        st = ("SOLVED @%s evals, %s spice-min" % (solve["evals"], solve["spice_min"])
              if solve["solved"] else "not solved (RESISTS)")
        print(f"  [{goal_id} a s{seed}] {env.n_evals} evals / "
              f"{env.ngspice_calls} ngspice / {res['spice_min_total']:.2f} "
              f"spice-min / best_obj={res['best_objective']} / "
              f"best_nf={(best['metrics'] or {}).get('nf_db')} -> {st}", flush=True)
    return res


def cell_path(goal_id, seed):
    return os.path.join(RESULTS, f"cell_{goal_id}_a_s{seed}.json")


def _write_status(msg):
    p = STATUS + f".{os.getpid()}.json"
    tmp = p + ".tmp"
    with open(tmp, "w") as fh:
        json.dump({"ts": N11._now(), "pid": os.getpid(), "msg": msg,
                   "ng_total": N11._NG["n"]}, fh, indent=1)
    os.replace(tmp, p)


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
    N11._install_ng_counter()
    _write_status(f"START {goal_id} a s{seed}")
    res = run_cell(goal_id, seed)
    tmp = p + f".{os.getpid()}.tmp"
    with open(tmp, "w") as fh:
        json.dump(res, fh, indent=1, default=str)
    os.replace(tmp, p)
    _write_status(f"DONE {goal_id} a s{seed} solved={res['solved']}")
    return res


def main():
    ap = argparse.ArgumentParser(description="E-12 H2 null filter (arm A)")
    ap.add_argument("--goals", default="H2")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--cell", nargs=2, metavar=("GOAL", "SEED"),
                    help="run ONE cell and exit")
    a = ap.parse_args()
    N11._install_ng_counter()
    if a.cell:
        run_and_save(a.cell[0], int(a.cell[1]), force=a.force)
        return 0
    for goal_id in [g for g in a.goals.split(",") if g]:
        for seed in GOALS[goal_id]["seeds"]:
            run_and_save(goal_id, seed, force=a.force)
    print(f"H2 null-filter cells complete; ngspice_total={N11._NG['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

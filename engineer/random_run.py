"""engineer/random_run.py -- the E-1 falsifier: a SECOND driver on the env API.

Charter §6 E-1's falsifier is "a second driver written against the API without
editing it". This is that driver: uniform random search in the [0,1]^d box, run
through `engineer/env.py`'s PUBLIC surface only -- `Env`, `Env.objective_fn`
(or `Env.evaluate`), `Env.best`, `Env.observe`, `Env.reference`, `Env.harness`,
`BudgetExhausted`, `TrajectoryLogger`. It touches no `_private` of `env.py` for
anything an optimizer must do; the only `EV._*` references are the shared result
plumbing `baseline_run.py` also uses (`_run_id`, `_now`, `_plain`, `DATA_DIR`),
never the evaluation path.

WHY RANDOM, AND WHY IT IS THE HONEST SECOND ARM
-----------------------------------------------
The charter's quality bar is "nulls first, always" (§4; survey conclusion 7).
CMA-ES (`baseline_run.py`) already runs through this env; random search is the
untuned null that any search claim is stated against -- and FINDINGS §43.2 ran it
at the matched 336-eval budget (0/5 feasible, best obj +1.00), so a random arm
here is directly readable against a published number. At the smoke's 150 evals it
is EXPECTED to finish infeasible, like the CMA-ES smoke; the point of this file is
the API, not the score.

    python engineer/random_run.py                      # wifi24-smoke, 150 evals
    python engineer/random_run.py --task wifi24-t2-a    # the matched budget
    python engineer/random_run.py --seed 3 --no-log
"""
import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import env as EV                                            # noqa: E402
from env import BudgetExhausted, Env, TrajectoryLogger      # noqa: E402
from tasks import REGISTRY, SMOKE, get                      # noqa: E402

import datastore as ds                                      # noqa: E402
import size as S                                            # noqa: E402

TRACE_EVERY = 10        # best-so-far sample rate, in evals -- baseline_run's

# The published null the smoke is read against (FINDINGS §43.2), quoted verbatim.
PUBLISHED = {
    "wifi24-t2-a": {
        "source": "lna/FINDINGS.md 43.2 (2026-08-14), 5 seeds/arm, budget 336",
        "arms": {"random": {"feasible": "0/5", "best_obj": 1.00, "median_obj": 1.66},
                 "cmaes": {"feasible": "4/5", "best_obj": -0.790, "median_obj": -0.649},
                 "zoaf": {"feasible": "1/5", "best_obj": -0.546, "median_obj": 1.22,
                          "stored_row_obj": -0.7324616666666666}},
    },
}
PUBLISHED[SMOKE] = dict(PUBLISHED["wifi24-t2-a"],
                        note="same (topology, spec) as wifi24-t2-a; the smoke "
                             "runs a REDUCED budget and is not comparable to it")


def run_random(objective_fn, dim, budget, seed=1, diag=None):
    """Uniform random search in [0,1]^d, budget-matched by construction.

    Draws one x per eval from a `default_rng(seed)`, calls the env's objective,
    tracks the best. Stops on `BudgetExhausted` (the env's own budget fence), so
    it spends exactly `budget` evals like every other arm -- the compute-match the
    benchmark rests on. The env is authoritative on the count; this loop's own
    `n` is a belt-and-braces guard, not the budget."""
    rng = np.random.default_rng(seed)
    best_f, n = float("inf"), 0
    try:
        while n < budget:
            x = rng.random(dim)
            f = objective_fn(x)
            best_f = min(best_f, f)
            n += 1
    except BudgetExhausted:
        pass
    if diag is not None:
        diag.update(sampler="uniform[0,1]^d", rng="numpy.default_rng",
                    seed=seed, draws=n)
    return best_f, n


def trace_of(envr, every=TRACE_EVERY):
    """Best-so-far every `every` evals, from the free points hook -- no re-sim."""
    best, out = float("inf"), []
    for i, (_x, m) in enumerate(envr.arena.points, start=1):
        f = S.SIM_FAIL_PENALTY if m is None else envr.spec.objective(m)
        best = min(best, float(f))
        if i % every == 0:
            out.append({"n": i, "best_obj": best, "feasible": bool(best < 0)})
    return out


def run(task_id=SMOKE, budget=None, seed=1, log=True, out=None, verbose=True,
        traj_path=None):
    task = get(task_id, seed=seed, **({"budget": budget} if budget else {}))
    run_id = EV._run_id(task)
    # traj_path: see baseline_run.run -- each parallel cell writes its own
    # trajectory file; default None keeps the canonical append path.
    logger = (TrajectoryLogger(run_id=run_id, meta={"algo": "random",
                                                    "driver": "random_run"},
                               **({"path": traj_path} if traj_path else {}))
              if log else None)
    envr = Env(task, logger=logger)
    if verbose:
        print(f"random_run: algo=random task={task.id}")
        print(f"  spec     {task.spec}  tier={task.tier}  era={task.era}")
        print(f"  task     ({task.wl_hash}) {envr.topo.n_devices} devices, "
              f"d={envr.dim} sizable params")
        print(f"  harness  inductor_q={envr.inductor_q} nf_gated={envr.nf_gated} "
              f"({2 if envr.nf_gated else 1} ngspice calls/eval), "
              f"deps {'rebound' if EV.BIND.get('rebound') else 'worktree-local'}")
        print(f"  budget   {task.budget} evals (pinned reference row: "
              f"{task.ref_evals} evals @ {task.ref_ts})")
        for note in envr.harness_notes:
            print(f"  [note]   {note}")

    diag, t0 = {}, time.time()
    run_random(envr.objective_fn(), envr.dim, envr.task.budget, seed, diag=diag)
    wall = time.time() - t0

    best_x, best_m = envr.best()
    feas, viol = (envr.spec.feasible(best_m) if best_m else (False, None))
    margins = ds.margins_for(envr.spec, best_m) if best_m else {}
    obs = envr.observe()
    res = {
        "kind": "engineer_baseline", "schema": "engineer-result-v0",
        "run_id": run_id, "algo": "random", "arm": "random-search",
        "arm_desc": "uniform random search in [0,1]^d (numpy.default_rng) -- the "
                    "untuned null, driven through env.py's public API only",
        "task": task.as_dict(), "seed": seed,
        "n_params": envr.dim, "param_names": envr.param_names,
        "budget_evals": task.budget, "n_evals": envr.n_evals,
        "ngspice_calls": envr.ngspice_calls, "n_sim_fail": envr.n_fail,
        "evals_to_best": envr.best_i, "best_obj": envr.best_f,
        "feasible": bool(feas),
        "viol": ({k: round(v, 6) for k, v in viol.items()} if viol else {}),
        "metrics": best_m, "margins": margins, "best_x": best_x,
        "best_params": (envr.arena.decode(best_x) if best_x is not None else None),
        "trace": trace_of(envr), "trace_every": TRACE_EVERY,
        "algo_diag": diag,
        "harness": envr.harness(),
        "reference_row": envr.reference(),
        "published": PUBLISHED.get(task.id),
        "op_state": {"n_devices": (obs["op"] or {}).get("n_devices"),
                     "subsample": envr.op_sink.subsample,
                     "kept_in_memory": len(envr.op_sink.recent),
                     "flushed_to_store": 0},
        "trajectory": {"path": (os.path.relpath(logger.path, HERE) if logger
                                else None),
                       "rows": (logger.n if logger else 0)},
        "wall_s": round(wall, 1),
        "s_per_eval": round(wall / max(envr.n_evals, 1), 4),
        "git_sha": ds.git_sha(), "ts": EV._now(),
    }
    if out is None:
        out = os.path.join(EV.DATA_DIR,
                           f"random_{task.id}_s{seed}_b{task.budget}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(EV._plain(res), fh, indent=1)

    if verbose:
        print(f"\n  {envr.n_evals} evals ({res['ngspice_calls']} ngspice calls) "
              f"in {res['wall_s']}s = {res['s_per_eval']}s/eval"
              + (f", {envr.n_fail} sim failures" if envr.n_fail else ""))
        print(f"  random   sampler={diag.get('sampler')} seed={diag.get('seed')} "
              f"draws={diag.get('draws')}")
        print(f"  best objective {envr.best_f:.4f} at eval {envr.best_i} -> "
              + ("FEASIBLE" if feas else f"infeasible {res['viol']}"))
        if best_m:
            print(envr.spec.report(best_m))
            print("  margins: " + EV.margin_str(margins))
        if logger:
            print(f"  trajectory {logger.n} rows -> "
                  f"{os.path.relpath(logger.path, HERE)}")
        print(f"  -> {os.path.relpath(out, HERE)}")
        _print_published(task, res)
    return res


def _print_published(task, res):
    pub = PUBLISHED.get(task.id)
    if not pub:
        return
    print(f"\n  READ AGAINST -- {pub['source']}")
    for arm, d in pub["arms"].items():
        print(f"    {arm:<8} feasible {d['feasible']:>4}  best {d['best_obj']:>7.3f}"
              f"  median {d['median_obj']:>7.3f}")
    if task.budget != task.ref_evals:
        print(f"    NOT COMPARABLE: this run spent {res['n_evals']} evals, the "
              f"table above spent {task.ref_evals}. "
              + (pub.get("note") or ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", default=SMOKE, choices=sorted(REGISTRY))
    ap.add_argument("--budget", type=int, default=0,
                    help="ngspice evals; 0 = the task's registry budget")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", help="result json (default engineer/data/random_*.json)")
    ap.add_argument("--no-log", action="store_true",
                    help="do not append trajectory rows")
    a = ap.parse_args()
    run(a.task, budget=(a.budget or None), seed=a.seed, log=not a.no_log,
        out=a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

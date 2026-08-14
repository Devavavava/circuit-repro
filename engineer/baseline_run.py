"""engineer/baseline_run.py -- the end-to-end smoke of the `engineer` line.

One optimizer, driven through `engineer/env.py`, on one registry task, at a
stated budget, writing a trajectory and a result JSON. It exists to prove the
seam, not to win anything: the environment binds to the real deck, the real
objective and the real ngspice; the budget is enforced; the trajectory lands in
the engineer line's own table and nowhere near `lna/data/`.

THE OPTIMIZER IS IMPORTED, NOT WRITTEN
--------------------------------------
`run_cmaes` comes from `lna/null_sizer.py` unmodified -- Hansen's purecmaes
defaults, box by clipping, restart on stagnation. Not re-implemented here for the
reason `null_sizer` itself gives for sharing everything that measures anything:
two implementations of a baseline are two baselines, and the comparison then
rests on the assumption that they agree. It is also the honest choice about
credit -- FINDINGS §43.2's "CMA-ES beats ZOAF at matched budget on the first task
tested" is a claim about *that* CMA-ES.

WHAT THE DEFAULT RUN IS AND IS NOT
----------------------------------
`wifi24-smoke` is the reference task `wifi24-t2-a` at 150 evals instead of its
matched 336 -- ~45% of the budget, ~15-20 s of simulation, so the seam can be
checked in the time it takes to read this paragraph. At that budget the search is
EXPECTED to finish infeasible: it is the same task, stopped early. The published
number for the task is the 336-eval one (FINDINGS §43.2, 5 seeds/arm: CMA-ES 4/5
feasible, best obj -0.790, median -0.649; ZOAF 1/5, stored row -0.7325; random
0/5), and this script prints it next to whatever the smoke got so the two are
never confused. A smoke result is not a benchmark result.

    python engineer/baseline_run.py                        # wifi24-smoke, 150
    python engineer/baseline_run.py --task wifi24-t2-a      # the matched budget
    python engineer/baseline_run.py --seed 3 --no-log
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import env as EV                                            # noqa: E402
from env import BudgetExhausted, Env, TrajectoryLogger      # noqa: E402
from tasks import REGISTRY, SMOKE, get                      # noqa: E402

import datastore as ds                                      # noqa: E402
import size as S                                            # noqa: E402
from null_sizer import run_cmaes                            # noqa: E402

TRACE_EVERY = 10        # best-so-far sample rate, in evals -- null_sizer's

# The published figures the smoke must be read against (FINDINGS §43.2), keyed by
# the scoring task they belong to. Quoted, not recomputed: this table is a
# citation, and a citation that drifts with the code is not one.
PUBLISHED = {
    "wifi24-t2-a": {
        # ASCII on purpose: this string is PRINTED, and a console codepage that
        # cannot encode a section sign must not be able to kill a results run.
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


def trace_of(envr, every=TRACE_EVERY):
    """Best-so-far every `every` evals, reconstructed from the free points hook.

    No simulation: `spec.objective(metrics)` on metrics the run already measured.
    A failed eval has no metric vector and scores `SIM_FAIL_PENALTY`, exactly as
    `make_objective` scored it live."""
    best, out = float("inf"), []
    for i, (_x, m) in enumerate(envr.arena.points, start=1):
        f = S.SIM_FAIL_PENALTY if m is None else envr.spec.objective(m)
        best = min(best, float(f))
        if i % every == 0:
            out.append({"n": i, "best_obj": best, "feasible": bool(best < 0)})
    return out


def run(task_id=SMOKE, budget=None, seed=1, algo="cmaes", log=True, out=None,
        verbose=True):
    task = get(task_id, seed=seed, **({"budget": budget} if budget else {}))
    run_id = EV._run_id(task)
    logger = (TrajectoryLogger(run_id=run_id, meta={"algo": algo,
                                                    "driver": "baseline_run"})
              if log else None)
    envr = Env(task, logger=logger)
    if verbose:
        print(f"baseline_run: algo={algo} task={task.id}")
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
    try:
        if algo == "cmaes":
            run_cmaes(envr.objective_fn(), envr.dim, seed, diag=diag)
        else:
            raise SystemExit(f"unknown algo {algo!r}; this smoke drives cmaes "
                             "(the null_sizer arm), by design")
    except BudgetExhausted:
        pass
    wall = time.time() - t0

    best_x, best_m = envr.best()
    feas, viol = (envr.spec.feasible(best_m) if best_m else (False, None))
    margins = ds.margins_for(envr.spec, best_m) if best_m else {}
    obs = envr.observe()
    res = {
        "kind": "engineer_baseline", "schema": "engineer-result-v0",
        "run_id": run_id, "algo": algo,
        "arm_desc": "CMA-ES (Hansen purecmaes defaults, box by clipping) -- "
                    "imported verbatim from lna/null_sizer.py",
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
        out = os.path.join(EV.DATA_DIR, f"baseline_{algo}_{task.id}_s{seed}_"
                                        f"b{task.budget}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(EV._plain(res), fh, indent=1)

    if verbose:
        print(f"\n  {envr.n_evals} evals ({res['ngspice_calls']} ngspice calls) "
              f"in {res['wall_s']}s = {res['s_per_eval']}s/eval"
              + (f", {envr.n_fail} sim failures" if envr.n_fail else ""))
        print(f"  cma-es   lam={diag.get('lam')} mu={diag.get('mu')} "
              f"sigma0={diag.get('sigma0')} gens={diag.get('gens')} "
              f"restarts={diag.get('restarts')} box={diag.get('box')}")
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
    """The number the result must be read against, printed WITH the result.

    Proposal §2.2 item 4 and the program's frozen-protocol culture: a figure
    quoted from a different budget, next to a figure measured at this one, with
    the difference named -- never one standing in for the other."""
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
    ap.add_argument("--algo", default="cmaes")
    ap.add_argument("--budget", type=int, default=0,
                    help="ngspice evals; 0 = the task's registry budget")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", help="result json (default engineer/data/baseline_*.json)")
    ap.add_argument("--no-log", action="store_true",
                    help="do not append trajectory rows")
    a = ap.parse_args()
    run(a.task, budget=(a.budget or None), seed=a.seed, algo=a.algo,
        log=not a.no_log, out=a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""engineer/e6_full.py -- the E-6 FULL-TIER in-house runner (E6-BUDGET.md §4.2).

Human-gated (GO given 2026-08-19). Runs the 7 in-house tier-2 scoring tasks at
their PINNED matched budgets (336/136/136/392/266/1050/1030 -- tasks.py registry),
N=10 seeds (1..10), both arms (incumbent A vs racing B), matched to the digit.

REUSE, NOT FORK: every cell is `e6_run.run_one(task, arm, seed, budget)` -- the
SAME per-cell function the pre-registered smoke used (arm A = baseline_run.run
cmaes = the E-3 cold arm; arm B = e6_racing.run_racing). The only thing this file
adds over `e6_run.py --smoke` is: pinned per-task budgets (not the 150 smoke cap)
and N=10. It writes the SAME per-cell result JSONs + per-cell trajectory files,
appends into E-6's OWN e6_trajectories.jsonl (canonical table byte-untouched), and
emits e6_full_v0.json. SERIAL, append-safe: a crash loses only the in-flight cell;
completed cells are on disk and skipped on resume (--resume).

    python engineer/e6_full.py                 # 7 tasks x 2 arms x 10 seeds @ pinned budgets
    python engineer/e6_full.py --seeds 2       # a 7x2x2 shakedown at pinned budgets
    python engineer/e6_full.py --resume        # skip cells whose result JSON already exists
"""
import argparse
import glob
import json
import os
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import env as EV                                              # noqa: E402
from tasks import SCORING, get                                # noqa: E402
import datastore as ds                                        # noqa: E402
import e6_racing as E6                                        # noqa: E402
import e6_run as R6                                           # noqa: E402

N_SEEDS = 10                                                  # E6-BUDGET.md §4.2
ARMS = ("incumbent", "racing")                               # E6-BUDGET.md §2
BOARD = os.path.join(EV.DATA_DIR, "e6_full_v0.json")


def _pinned_budget(task_id):
    """The task's pinned matched budget from the registry (E6-BUDGET.md §3)."""
    return int(get(task_id).budget)


def _cell_result_path(task_id, arm, seed, budget):
    return os.path.join(EV.DATA_DIR, f"e6_{arm}_{task_id}_s{seed}_b{budget}.json")


def _summary_from_result(task_id, arm, seed, budget):
    """Reconstruct the run_one cell summary from an existing result JSON + its
    trajectory (for --resume; avoids re-simulating a completed cell)."""
    out = _cell_result_path(task_id, arm, seed, budget)
    res = json.load(open(out, encoding="utf-8"))
    traj = os.path.join(R6.E6_TRAJ_DIR, f"{arm}_{task_id}_s{seed}_b{budget}.jsonl")
    trace = res.get("trace")
    sim_s, spice_ff = R6._cost_from_traj(traj, trace)
    total_s = float(res.get("wall_s") or 0.0)
    return {"task": task_id, "arm": arm, "seed": seed, "budget": budget,
            "n_evals": res["n_evals"], "ngspice_calls": res["ngspice_calls"],
            "n_sim_fail": res.get("n_sim_fail", 0),
            "feasible": bool(res["feasible"]), "best_obj": res["best_obj"],
            "evals_to_best": res.get("evals_to_best"),
            "evals_to_first_feasible": R6._first_feasible(trace),
            "spice_min_to_first_feasible": spice_ff,
            "trace": trace, "algo_diag": res.get("algo_diag"),
            "total_s": round(total_s, 3), "sim_s": round(sim_s, 3),
            "model_s": round(max(0.0, total_s - sim_s), 3),
            "result_json": os.path.relpath(out, HERE),
            "traj": os.path.relpath(traj, HERE)}


def _print_full_board(board):
    print("\n" + "=" * 104)
    print("E-6 FULL TIER  (in-house 7, pinned matched budgets, N=10)  "
          f"k={board['config']['k']} cull=top-{board['config']['cull_to']}  "
          f"seeds={board['config']['seeds']}  (prereg @ {board['prereg']['sha'][:12]})")
    print("=" * 104)
    hdr = (f"{'task':<20}{'arm':<11}{'feas':>6}{'obj median':>12}{'obj best':>11}"
           f"{'obj worst':>11}{'ev>feas':>9}{'sim_s':>9}   verdict")
    print(hdr)
    print("-" * len(hdr))
    for task_id, d in board["per_task"].items():
        for arm in ("incumbent", "racing"):
            a = d.get(arm)
            if not a:
                continue
            om = "-" if a["best_obj_median"] is None else f"{a['best_obj_median']:.4f}"
            ob = "-" if a["best_obj_best"] is None else f"{a['best_obj_best']:.4f}"
            ow = "-" if a["best_obj_worst"] is None else f"{a['best_obj_worst']:.4f}"
            ff = ("-" if a["evals_to_first_feasible_median"] is None
                  else f"{a['evals_to_first_feasible_median']:.0f}")
            v = d["verdict"] if arm == "racing" else ""
            print(f"{task_id:<20}{arm:<11}{a['feasible']:>6}{om:>12}{ob:>11}"
                  f"{ow:>11}{ff:>9}{a['sim_s_total']:>9.1f}   {v}")
    print("-" * len(hdr))
    mr = board["median_rank"]
    print("median rank (1=best; feasible-rate then median obj): "
          + "  ".join(f"{k}={v}" for k, v in sorted(mr.items(), key=lambda kv: kv[1])))
    bm = board["budget_match_check"]
    print(f"BUDGET MATCH: all {bm['n_pairs_checked']} (task,seed) pairs equal evals "
          f"across arms? {'YES' if bm['all_matched'] else 'NO -- ' + str(bm['mismatches'])}")
    c = board["cost"]
    print(f"cost: {c['n_cells']} cells, {c['total_evals']} evals, "
          f"{c['total_ngspice_calls']} ngspice calls, sim {c['sim_s_total']:.0f}s")
    print("=" * 104)


def _spawn_cell(task_id, arm, seed, budget):
    """Subprocess per cell -- the e6_run.py --cell entry point, reused verbatim."""
    cmd = [sys.executable, os.path.join(HERE, "e6_run.py"),
           "--cell", task_id, arm, str(seed), "--budget", str(budget)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"cell {arm}/{task_id}/s{seed} failed:\n{r.stderr[-3000:]}")
    line = [ln for ln in r.stdout.splitlines() if ln.strip()][-1]
    return json.loads(line)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=N_SEEDS)
    ap.add_argument("--tasks", nargs="+")
    ap.add_argument("--jobs", type=int, default=0)
    ap.add_argument("--resume", action="store_true",
                    help="skip cells whose result JSON already exists on disk")
    a = ap.parse_args()

    tasks = a.tasks or sorted(SCORING)
    seeds = list(range(1, a.seeds + 1))
    prereg_sha = R6._prereg_sha()
    plan = [(t, arm, s) for t in tasks for arm in ARMS for s in seeds]
    # Each cell is an independent subprocess writing its OWN result JSON the moment
    # it finishes (crash-safe: --resume skips completed cells). The pool only
    # governs concurrency; the E-6 trajectory append stays a single serial pass.
    jobs = a.jobs or min(len(plan), os.cpu_count() or 8)
    print(f"e6_full FULL TIER: {len(plan)} cells "
          f"({len(tasks)} tasks x {len(ARMS)} arms x {len(seeds)} seeds) "
          f"at PINNED matched budgets; pool={jobs}, per-cell JSON crash-safe.")
    print(f"  pre-registered @ {prereg_sha}")
    for t in tasks:
        print(f"    {t:<20} budget={_pinned_budget(t)}  r={E6.triage_evals(_pinned_budget(t))}")

    t0, cells = time.time(), []
    todo = []
    for (t, arm, s) in plan:
        budget = _pinned_budget(t)
        out = _cell_result_path(t, arm, s, budget)
        if a.resume and os.path.exists(out):
            c = _summary_from_result(t, arm, s, budget)
            cells.append(c)
            print(f"  [resume] {arm:<10} {t:<18} s{s}  SKIP "
                  f"obj={c['best_obj']:.4f}  {c['n_evals']}ev")
        else:
            todo.append((t, arm, s, budget))
    done = 0
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        futs = {ex.submit(_spawn_cell, t, arm, s, budget): (t, arm, s)
                for (t, arm, s, budget) in todo}
        for fut in as_completed(futs):
            t, arm, s = futs[fut]
            c = fut.result()
            cells.append(c)
            done += 1
            print(f"  [{done:>3}/{len(todo)}] {arm:<10} {t:<18} s{s}  "
                  f"{'FEASIBLE' if c['feasible'] else 'infeasible':<10} "
                  f"obj={c['best_obj']:.4f}  {c['n_evals']}ev sim={c['sim_s']:.1f}s  "
                  f"[{time.time()-t0:.0f}s wall]")
    print(f"  all {len(plan)} cells done in {time.time()-t0:.1f}s wall")

    board = R6.aggregate(cells, prereg_sha)
    board["kind"] = "engineer_e6_full"
    board["schema"] = "engineer-e6-full-v0"
    board["tier"] = ("FULL -- PROTOCOL v1.0 scoring config: 7 in-house tier-2 "
                     "tasks at pinned matched budgets, N=10 (E6-BUDGET.md §4.2)")
    board["config"]["seeds"] = a.seeds
    board["config"]["budgets"] = {t: _pinned_budget(t) for t in tasks}
    board["e6_trajectory_append"] = R6._append_to_e6_table(cells)
    with open(BOARD, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(EV._plain(board), fh, indent=1)
    _print_full_board(board)
    print(f"\n  -> {os.path.relpath(BOARD, HERE)}")
    ta = board["e6_trajectory_append"]
    print(f"  -> e6 trajectory: +{ta['rows_appended']} rows "
          f"({ta['bytes_before']} -> {ta['bytes_after']} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

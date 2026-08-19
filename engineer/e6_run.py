"""engineer/e6_run.py -- the E-6 paired runner: incumbent (A) vs racing (B).

Pre-registered in `engineer/E6-BUDGET.md` (committed alone, before this ran a
single eval). This runner READS the doc's constants (arms, k, r, cull, seeds); it
does not choose them.

WHAT IS REUSED, NOT FORKED (the E-1/E-3/score_run rule)
-------------------------------------------------------
- Arm A (incumbent) is `baseline_run.run(algo="cmaes")` IMPORTED and called -- the
  exact E-3 cold arm / registered `cmaes` null, unchanged (E6-BUDGET.md §2, §8).
- Arm B (racing) is `e6_racing.run_racing` on the same `env.py` budgeted interface.
- The subprocess-per-cell + per-cell-trajectory-file + serial-append plumbing is
  score_run.py's, reused; env.py's API is untouched.

SMOKE TIER (E6-BUDGET.md §4.1): the 7 in-house tasks at 150 evals/arm, 3 seeds.
A MECHANICS CHECK ONLY -- smoke can refute the harness, not confirm the hypothesis
(E6-BUDGET.md §7). The full tier (PROTOCOL v1.0 N=10 + externals) is gated on a
human check-in and is NOT run here.

    python engineer/e6_run.py --smoke                     # 7 tasks x 2 arms x 3 seeds @ 150
    python engineer/e6_run.py --smoke --seeds 1           # a fast shakedown
    python engineer/e6_run.py --cell wifi24-t2-a racing 1 --budget 150   # one cell (subprocess entry)
"""
import argparse
import glob
import json
import os
import statistics
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import env as EV                                              # noqa: E402
from env import Env, TrajectoryLogger                         # noqa: E402
from tasks import SCORING, get                                # noqa: E402
import datastore as ds                                        # noqa: E402
import size as S                                              # noqa: E402
from null_sizer import run_cmaes                              # noqa: E402
import e6_racing as E6                                        # noqa: E402
import baseline_run                                           # noqa: E402

SMOKE_BUDGET = 150                 # R-4 smoke convention (E6-BUDGET.md §4.1)
SMOKE_SEEDS = 3                    # E6-BUDGET.md §4.1
ARMS = ("incumbent", "racing")    # E6-BUDGET.md §2
TRACE_EVERY = 10                  # null_sizer's / baseline_run's
E6_TRAJ_DIR = os.path.join(EV.DATA_DIR, "_e6_traj")
E6_TRAJ_TABLE = os.path.join(EV.DATA_DIR, "e6_trajectories.jsonl")   # E-6's OWN table
SMOKE_BOARD = os.path.join(EV.DATA_DIR, "e6_smoke_v0.json")


def _trace_of(envr, every=TRACE_EVERY):
    """Best-so-far every `every` evals from the free points hook (no re-sim)."""
    best, out = float("inf"), []
    for i, (_x, m) in enumerate(envr.arena.points, start=1):
        f = S.SIM_FAIL_PENALTY if m is None else envr.spec.objective(m)
        best = min(best, float(f))
        if i % every == 0:
            out.append({"n": i, "best_obj": best, "feasible": bool(best < 0)})
    return out


def _first_feasible(trace):
    for pt in (trace or []):
        if pt.get("best_obj") is not None and float(pt["best_obj"]) < 0:
            return int(pt["n"])
    return None


def _spice_min_to_first_feasible(envr):
    """G0-FAIRNESS §4: SPICE-minutes (sum per-eval cost.wall_s / 60) to the first
    feasible best-so-far eval, censored (None) if never feasible. Derived from the
    points hook + the env's per-eval wall stamps in the trajectory -- no re-sim.
    Here computed from the arena points' running best crossing zero; wall per eval
    is taken from the cell's own trajectory file by the caller. Returns eval index
    of first feasible (or None); SPICE-min is summed by run_one from the traj."""
    best = float("inf")
    for i, (_x, m) in enumerate(envr.arena.points, start=1):
        f = S.SIM_FAIL_PENALTY if m is None else envr.spec.objective(m)
        best = min(best, float(f))
        if best < 0:
            return i
    return None


# --------------------------------------------------------------- one cell
def run_one(task_id, arm, seed, budget):
    """Run one (task, arm, seed) at `budget`; write result JSON + own trajectory.

    Arm A -> baseline_run.run (imported, the incumbent). Arm B -> e6_racing.run_racing.
    Both count every eval through the SAME env; the budget is matched to the digit."""
    os.makedirs(E6_TRAJ_DIR, exist_ok=True)
    traj = os.path.join(E6_TRAJ_DIR, f"{arm}_{task_id}_s{seed}_b{budget}.jsonl")
    if os.path.exists(traj):
        os.remove(traj)                    # a re-run of a cell owns its own file
    out = os.path.join(EV.DATA_DIR,
                       f"e6_{arm}_{task_id}_s{seed}_b{budget}.json")
    task = get(task_id, seed=seed, budget=budget)

    if arm == "incumbent":
        # The E-3 cold arm exactly, via the imported driver (E6-BUDGET.md §2, §8).
        res = baseline_run.run(task_id=task_id, budget=budget, seed=seed,
                               algo="cmaes", log=True, out=out, verbose=False,
                               traj_path=traj)
        n_evals = res["n_evals"]
        ngspice_calls = res["ngspice_calls"]
        n_fail = res["n_sim_fail"]
        best_obj = res["best_obj"]
        feasible = bool(res["feasible"])
        evals_to_best = res["evals_to_best"]
        trace = res.get("trace")
        diag = res.get("algo_diag")
        total_s = float(res.get("wall_s") or 0.0)
    else:
        # Racing arm B on the env, with its own trajectory logger + result writer.
        run_id = EV._run_id(task) + "-racing"
        logger = TrajectoryLogger(run_id=run_id,
                                  meta={"algo": "racing", "driver": "e6_run",
                                        "k": E6.K_STARTS,
                                        "r": E6.triage_evals(budget)},
                                  path=traj)
        envr = Env(task, logger=logger)
        diag, t0 = {}, time.time()
        try:
            E6.run_racing(envr, seed, diag=diag)
        except Exception:                              # noqa: BLE001
            raise
        total_s = time.time() - t0
        best_x, best_m = envr.best()
        feas, viol = (envr.spec.feasible(best_m) if best_m else (False, None))
        margins = ds.margins_for(envr.spec, best_m) if best_m else {}
        trace = _trace_of(envr)
        res = {
            "kind": "engineer_e6", "schema": "engineer-e6-result-v0",
            "run_id": run_id, "arm": "racing",
            "arm_desc": "racing: k triage starts, cull top-1, warm-resume survivor "
                        "-- e6_racing.run_racing, run_cmaes imported verbatim",
            "task": task.as_dict(), "seed": seed,
            "n_params": envr.dim, "param_names": envr.param_names,
            "budget_evals": budget, "n_evals": envr.n_evals,
            "ngspice_calls": envr.ngspice_calls, "n_sim_fail": envr.n_fail,
            "evals_to_best": envr.best_i, "best_obj": envr.best_f,
            "feasible": bool(feas),
            "viol": ({kk: round(v, 6) for kk, v in viol.items()} if viol else {}),
            "metrics": best_m, "margins": margins, "best_x": best_x,
            "best_params": (envr.arena.decode(best_x) if best_x is not None else None),
            "trace": trace, "trace_every": TRACE_EVERY,
            "algo_diag": diag,
            "harness": envr.harness(),
            "reference_row": envr.reference(),
            "wall_s": round(total_s, 1),
            "s_per_eval": round(total_s / max(envr.n_evals, 1), 4),
            "git_sha": ds.git_sha(), "ts": EV._now(),
        }
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(EV._plain(res), fh, indent=1)
        n_evals = envr.n_evals
        ngspice_calls = envr.ngspice_calls
        n_fail = envr.n_fail
        best_obj = envr.best_f
        feasible = bool(feas)
        evals_to_best = envr.best_i

    # sim_s from the per-eval stamps the env already wrote into the trajectory,
    # and the G0 time-to-competence SPICE-minutes derived from the same stamps.
    sim_s, spice_min_ff = _cost_from_traj(traj, trace)
    model_s = max(0.0, total_s - sim_s)
    return {"task": task_id, "arm": arm, "seed": seed, "budget": budget,
            "n_evals": n_evals, "ngspice_calls": ngspice_calls,
            "n_sim_fail": n_fail, "feasible": feasible, "best_obj": best_obj,
            "evals_to_best": evals_to_best,
            "evals_to_first_feasible": _first_feasible(trace),
            "spice_min_to_first_feasible": spice_min_ff,
            "trace": trace, "algo_diag": diag,
            "total_s": round(total_s, 3), "sim_s": round(sim_s, 3),
            "model_s": round(model_s, 3),
            "result_json": os.path.relpath(out, HERE),
            "traj": os.path.relpath(traj, HERE)}


def _cost_from_traj(traj, trace):
    """(sim_s, spice_min_to_first_feasible) from the cell's own trajectory file.

    sim_s = sum of per-eval cost.wall_s (PROTOCOL §6). spice_min_to_first_feasible
    (G0-FAIRNESS §4) = sum of wall_s/60 up to and including the first eval whose
    best-so-far went feasible; None if never feasible. Both derived from the stamps
    the env already wrote -- no re-simulation."""
    if not os.path.exists(traj):
        return 0.0, None
    walls = []
    with open(traj, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            walls.append(float(((row.get("cost") or {}).get("wall_s")) or 0.0))
    sim_s = sum(walls)
    # first feasible eval index from the trace (coarse to TRACE_EVERY); censor if none
    ff = _first_feasible(trace)
    if ff is None or ff > len(walls):
        return sim_s, None
    spice_min = sum(walls[:ff]) / 60.0
    return sim_s, round(spice_min, 4)


# ------------------------------------------------- subprocess plumbing
def _spawn_cell(task_id, arm, seed, budget):
    cmd = [sys.executable, os.path.join(HERE, "e6_run.py"),
           "--cell", task_id, arm, str(seed), "--budget", str(budget)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"cell {arm}/{task_id}/s{seed} failed:\n{r.stderr[-3000:]}")
    line = [ln for ln in r.stdout.splitlines() if ln.strip()][-1]
    return json.loads(line)


# ------------------------------------------------------------- aggregation
def _agg_arm(cells):
    n = len(cells)
    feas = [c for c in cells if c["feasible"]]
    objs = [c["best_obj"] for c in cells]
    ff = [c["evals_to_first_feasible"] for c in cells
          if c["evals_to_first_feasible"] is not None]
    smff = [c["spice_min_to_first_feasible"] for c in cells
            if c["spice_min_to_first_feasible"] is not None]
    return {
        "n_seeds": n, "feasible": f"{len(feas)}/{n}", "n_feasible": len(feas),
        "best_obj_median": round(statistics.median(objs), 6) if objs else None,
        "best_obj_best": round(min(objs), 6) if objs else None,
        "best_obj_worst": round(max(objs), 6) if objs else None,
        "evals_to_first_feasible_median": (round(statistics.median(ff), 1) if ff else None),
        "spice_min_to_first_feasible_median": (round(statistics.median(smff), 4) if smff else None),
        "n_seeds_first_feasible": len(ff),
        "sim_s_total": round(sum(c["sim_s"] for c in cells), 2),
        "model_s_total": round(sum(c["model_s"] for c in cells), 2),
        "evals_span": sorted({c["n_evals"] for c in cells}),
        "seeds": sorted(c["seed"] for c in cells),
    }


def _verdict(inc, rac):
    """Per-task smoke verdict: feasible-rate, tiebroken by median best-obj.
    (A mechanics label only -- smoke cannot confirm the hypothesis, E6-BUDGET.md §7.)"""
    if inc["n_feasible"] != rac["n_feasible"]:
        return "racing>incumbent" if rac["n_feasible"] > inc["n_feasible"] else "racing<incumbent"
    im, rm = inc["best_obj_median"], rac["best_obj_median"]
    if im is None or rm is None:
        return "tie"
    if abs(im - rm) <= 1e-6:
        return "tie"
    return "racing>incumbent" if rm < im else "racing<incumbent"


def _rank(per_task):
    from collections import defaultdict
    ranks = defaultdict(list)
    for _t, arms in per_task.items():
        order = sorted(arms.items(),
                       key=lambda kv: (-kv[1]["n_feasible"],
                                       (kv[1]["best_obj_median"]
                                        if kv[1]["best_obj_median"] is not None
                                        else float("inf"))))
        for i, (arm, _) in enumerate(order, start=1):
            ranks[arm].append(i)
    return {arm: round(statistics.median(rs), 2) for arm, rs in ranks.items()}


def _budget_match_check(cells):
    """The smoke's core pass/fail: for every (task, seed) BOTH arms spent EXACTLY
    the same number of env evals (the matched-budget claim, E6-BUDGET.md §3)."""
    from collections import defaultdict
    by = defaultdict(dict)
    for c in cells:
        by[(c["task"], c["seed"])][c["arm"]] = c["n_evals"]
    mism = []
    for (t, s), arms in by.items():
        if len(arms) == 2 and len(set(arms.values())) != 1:
            mism.append({"task": t, "seed": s, "evals": arms})
    return {"all_matched": not mism, "n_pairs_checked": len(by),
            "mismatches": mism}


def aggregate(cells, prereg_sha):
    from collections import defaultdict
    grouped = defaultdict(lambda: defaultdict(list))
    for c in cells:
        grouped[c["task"]][c["arm"]].append(c)
    per_task = {}
    for task_id in sorted(grouped):
        arms = {a: _agg_arm(sorted(g, key=lambda c: c["seed"]))
                for a, g in grouped[task_id].items()}
        if "incumbent" in arms and "racing" in arms:
            arms_verdict = _verdict(arms["incumbent"], arms["racing"])
        else:
            arms_verdict = "incomplete"
        per_task[task_id] = {**arms, "verdict": arms_verdict}
    sim_total = round(sum(c["sim_s"] for c in cells), 2)
    model_total = round(sum(c["model_s"] for c in cells), 2)
    return {
        "kind": "engineer_e6_smoke", "schema": "engineer-e6-smoke-v0",
        "tier": "SMOKE -- mechanics check only (E6-BUDGET.md §7); "
                "smoke can refute the harness, NOT confirm the hypothesis",
        "prereg": {"file": "engineer/E6-BUDGET.md", "sha": prereg_sha},
        "config": {"smoke_budget": SMOKE_BUDGET, "seeds": SMOKE_SEEDS,
                   "arms": list(ARMS), "k": E6.K_STARTS, "cull_to": E6.CULL_TO,
                   "r_smoke": E6.triage_evals(SMOKE_BUDGET),
                   "tasks": sorted({c["task"] for c in cells})},
        "per_task": per_task,
        "median_rank": _rank({t: {a: d[a] for a in ("incumbent", "racing") if a in d}
                              for t, d in per_task.items()}),
        "budget_match_check": _budget_match_check(cells),
        "cost": {"sim_s_total": sim_total, "model_s_total": model_total,
                 "wall_s_total": round(sim_total + model_total, 2),
                 "n_cells": len(cells),
                 "total_evals": sum(c["n_evals"] for c in cells),
                 "total_ngspice_calls": sum(c["ngspice_calls"] for c in cells)},
        "harness_git_sha": ds.git_sha(), "ts": EV._now(),
    }


# ------------------------------------------------ E-6 trajectory append
def _append_to_e6_table(cells):
    """Serial pass: append every cell's own trajectory file into E-6's OWN
    e6_trajectories.jsonl (NOT the canonical trajectories.jsonl, which is left
    byte-untouched -- append-only law, charter §3.2)."""
    before = os.path.getsize(E6_TRAJ_TABLE) if os.path.exists(E6_TRAJ_TABLE) else 0
    n_rows = 0
    os.makedirs(os.path.dirname(E6_TRAJ_TABLE), exist_ok=True)
    with open(E6_TRAJ_TABLE, "a", encoding="utf-8", newline="\n") as out:
        for c in sorted(cells, key=lambda c: (c["task"], c["arm"], c["seed"])):
            p = os.path.join(HERE, c["traj"])
            if not os.path.exists(p):
                continue
            with open(p, encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        out.write(line if line.endswith("\n") else line + "\n")
                        n_rows += 1
    after = os.path.getsize(E6_TRAJ_TABLE)
    return {"table": os.path.relpath(E6_TRAJ_TABLE, HERE),
            "bytes_before": before, "bytes_after": after, "rows_appended": n_rows}


# ------------------------------------------------------------- printout
def _print_board(board):
    print("\n" + "=" * 100)
    print(f"E-6 SMOKE  (MECHANICS CHECK ONLY)  k={board['config']['k']} "
          f"r={board['config']['r_smoke']} cull=top-{board['config']['cull_to']}  "
          f"budget={board['config']['smoke_budget']} seeds={board['config']['seeds']}  "
          f"(prereg @ {board['prereg']['sha'][:12]})")
    print("=" * 100)
    hdr = (f"{'task':<20}{'arm':<11}{'feas':>6}{'obj median':>12}{'obj best':>11}"
           f"{'obj worst':>11}{'ev>feas':>9}{'sim_s':>8}   verdict")
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
            ff = "-" if a["evals_to_first_feasible_median"] is None else f"{a['evals_to_first_feasible_median']:.0f}"
            v = d["verdict"] if arm == "racing" else ""
            print(f"{task_id:<20}{arm:<11}{a['feasible']:>6}{om:>12}{ob:>11}{ow:>11}{ff:>9}{a['sim_s_total']:>8.1f}   {v}")
    print("-" * len(hdr))
    mr = board["median_rank"]
    print("median rank (1=best; feasible then median obj): "
          + "  ".join(f"{k}={v}" for k, v in sorted(mr.items(), key=lambda kv: kv[1])))
    bm = board["budget_match_check"]
    print(f"\nBUDGET MATCH (the smoke's core check): all {bm['n_pairs_checked']} "
          f"(task,seed) pairs spent equal evals across arms? "
          f"{'YES' if bm['all_matched'] else 'NO -- ' + str(bm['mismatches'])}")
    c = board["cost"]
    print(f"cost: {c['n_cells']} cells, {c['total_evals']} evals, "
          f"{c['total_ngspice_calls']} ngspice calls, sim {c['sim_s_total']:.1f}s")
    print("NOTE: smoke can refute the harness, NOT confirm the hypothesis (E6-BUDGET.md §7).")
    print("=" * 100)


def _prereg_sha():
    try:
        r = subprocess.run(["git", "log", "--reverse", "--format=%H", "--",
                            "engineer/E6-BUDGET.md"], cwd=EV.ROOT,
                           capture_output=True, text=True, timeout=10)
        shas = [s for s in (r.stdout or "").split() if s]
        return shas[0] if shas else None
    except Exception:                                          # noqa: BLE001
        return None


def _load_existing(tasks, seeds, budget):
    cells = []
    for p in sorted(glob.glob(os.path.join(EV.DATA_DIR, "e6_*_s*_b*.json"))):
        with open(p, encoding="utf-8") as fh:
            res = json.load(fh)
        # reconstruct a cell summary from the result JSON + its trajectory
        t = res["task"]["id"] if isinstance(res.get("task"), dict) else res.get("task")
        if t not in tasks:
            continue
        cells.append(res)   # note: aggregate-only path is best-effort; smoke re-runs cheaply
    return cells


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cell", nargs=3, metavar=("TASK", "ARM", "SEED"),
                    help="run one (task, arm, seed) cell; prints its JSON summary")
    ap.add_argument("--budget", type=int, default=SMOKE_BUDGET)
    ap.add_argument("--smoke", action="store_true", help="the 7x2x3 smoke tier")
    ap.add_argument("--seeds", type=int, default=SMOKE_SEEDS)
    ap.add_argument("--jobs", type=int, default=0)
    ap.add_argument("--tasks", nargs="+")
    a = ap.parse_args()

    if a.cell:
        res = run_one(a.cell[0], a.cell[1], int(a.cell[2]), a.budget)
        print(json.dumps(EV._plain(res)))
        return 0

    if not a.smoke:
        ap.error("give --smoke (the full tier is gated on a human check-in and is "
                 "not run by this flag)")

    tasks = a.tasks or sorted(SCORING)
    seeds = list(range(1, a.seeds + 1))
    prereg_sha = _prereg_sha()
    plan = [(t, arm, s) for t in tasks for arm in ARMS for s in seeds]
    jobs = a.jobs or min(len(plan), os.cpu_count() or 8)
    print(f"e6_run SMOKE: {len(plan)} cells "
          f"({len(tasks)} tasks x {len(ARMS)} arms x {len(seeds)} seeds) @ {a.budget} evals, pool={jobs}")
    print(f"  pre-registered @ {prereg_sha}")
    t0, cells = time.time(), []
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        futs = {ex.submit(_spawn_cell, t, arm, s, a.budget): (t, arm, s)
                for (t, arm, s) in plan}
        done = 0
        for fut in as_completed(futs):
            t, arm, s = futs[fut]
            c = fut.result()
            cells.append(c)
            done += 1
            print(f"  [{done:>3}/{len(plan)}] {arm:<10} {t:<18} s{s}  "
                  f"{'FEASIBLE' if c['feasible'] else 'infeasible':<10} "
                  f"obj={c['best_obj']:.4f}  {c['n_evals']}ev sim={c['sim_s']:.1f}s")
    print(f"  all cells done in {time.time()-t0:.1f}s wall")

    board = aggregate(cells, prereg_sha)
    board["e6_trajectory_append"] = _append_to_e6_table(cells)
    os.makedirs(os.path.dirname(SMOKE_BOARD), exist_ok=True)
    with open(SMOKE_BOARD, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(EV._plain(board), fh, indent=1)
    _print_board(board)
    ta = board["e6_trajectory_append"]
    print(f"\n  -> {os.path.relpath(SMOKE_BOARD, HERE)}")
    print(f"  -> e6 trajectory: +{ta['rows_appended']} rows "
          f"({ta['bytes_before']} -> {ta['bytes_after']} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

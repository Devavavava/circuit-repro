"""engineer/score_run.py -- the E-2 scoring runner (PROTOCOL.md, committed first).

Drives the two null arms x N seeds x the 7 scoring tasks under `PROTOCOL.md`, and
emits the first result table produced under it. The protocol was pre-registered
(committed alone) BEFORE this file ran a single eval; that ordering is the E-2
falsifier's fence and this runner does nothing to loosen it -- it reads the
protocol's constants, it does not choose them.

WHAT IS REUSED, NOT FORKED
--------------------------
The per-cell work is `baseline_run.run` (CMA-ES arm) and `random_run.run` (random
arm), IMPORTED and called -- the optimizer and the reporting shape are theirs, not
re-implemented here (two implementations of a baseline are two baselines). The one
minimal shared-piece change both drivers needed was an optional `traj_path=` so a
parallel cell writes its OWN trajectory file; env.py's API is untouched.

CONCURRENCY AND THE APPEND-ONLY LAW  (charter 3.2)
--------------------------------------------------
Each (task, arm, seed) cell runs as its own subprocess (clean isolation; no shared
env/RNG/GIL surface) and writes (a) its result JSON via the driver's existing
naming and (b) its OWN trajectory file under data/_score_traj/. The canonical
`data/trajectories.jsonl` is NEVER written concurrently: after all cells finish,
this runner appends the per-cell trajectory files into it in ONE serial pass
(E-1's throwaway-path precedent), so the canonical table only ever grows and its
byte prefix is preserved. `--no-canon` skips that pass (leaves the per-cell files
in place) for a dry inspection.

MODELING TIME vs SIMULATION TIME  (PROTOCOL 6, AnalogGym/S11)
-------------------------------------------------------------
sim_s = sum of the per-eval `cost.wall_s` the env already stamped (recovered from
the cell's trajectory file); model_s = the cell's total wall - sim_s (the arm's
own compute + bookkeeping). Both are recorded per cell and summarised.

    python engineer/score_run.py                 # full 7x2x5, parallel, then aggregate
    python engineer/score_run.py --seeds 1       # a fast 7x2x1 shakedown
    python engineer/score_run.py --jobs 32       # cap the pool
    python engineer/score_run.py --cell wifi24-t2-a cmaes 1   # one cell (subprocess entry)
    python engineer/score_run.py --aggregate-only             # rebuild the scoreboard from existing JSONs
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
from tasks import SCORING, get                               # noqa: E402
import datastore as ds                                       # noqa: E402
import size as S                                             # noqa: E402

import baseline_run                                          # noqa: E402
import random_run                                            # noqa: E402

# ---- protocol constants, READ from PROTOCOL.md, not chosen here (PROTOCOL 4) ---
N_SEEDS = 10                      # PROTOCOL 4 §43.1 amendment: raised 5→10 (user ruling 2026-08-14)
ARMS = ("cmaes", "random")       # PROTOCOL 3: the two nulls
SCORE_TRAJ_DIR = os.path.join(EV.DATA_DIR, "_score_traj")
SCOREBOARD = os.path.join(EV.DATA_DIR, "scoreboard_v0.1.json")  # §43.1 amendment artifact
CANON_TRAJ = EV.TRAJ_TABLE

# FINDINGS 43.2, quoted verbatim -- the reproduction target (PROTOCOL 8).
PUBLISHED_432 = {
    "source": "lna/FINDINGS.md 43.2 (2026-08-14), 5 seeds/arm, budget 336",
    "cmaes": {"feasible": "4/5", "best_obj": -0.790, "median_obj": -0.649},
    "random": {"feasible": "0/5", "best_obj": 1.00, "median_obj": 1.66},
}


def _cell_out(task_id, arm, seed, budget):
    """The driver's own result-JSON path for a cell (existing naming)."""
    stem = ("baseline_cmaes" if arm == "cmaes" else "random")
    return os.path.join(EV.DATA_DIR, f"{stem}_{task_id}_s{seed}_b{budget}.json")


def _cell_traj(task_id, arm, seed):
    return os.path.join(SCORE_TRAJ_DIR, f"{arm}_{task_id}_s{seed}.jsonl")


# --------------------------------------------------------------- one cell
def run_cell(task_id, arm, seed):
    """Run a single (task, arm, seed) via the imported driver; return its result.

    Writes the driver's result JSON and this cell's OWN trajectory file. sim_s is
    recovered from that trajectory file (sum of per-eval cost.wall_s); model_s is
    the cell's total wall minus sim_s (PROTOCOL 6)."""
    task = get(task_id)
    os.makedirs(SCORE_TRAJ_DIR, exist_ok=True)
    traj = _cell_traj(task_id, arm, seed)
    if os.path.exists(traj):
        os.remove(traj)                    # a re-run of a cell owns its own file
    out = _cell_out(task_id, arm, seed, task.budget)
    driver = baseline_run.run if arm == "cmaes" else random_run.run
    kw = dict(task_id=task_id, seed=seed, log=True, out=out, verbose=False,
              traj_path=traj)
    if arm == "cmaes":
        kw["algo"] = "cmaes"
    res = driver(**kw)
    # sim_s from the per-eval stamps the env already wrote into the trajectory.
    sim_s = 0.0
    if os.path.exists(traj):
        with open(traj, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    sim_s += float(((json.loads(line) or {}).get("cost")
                                    or {}).get("wall_s") or 0.0)
    total_s = float(res.get("wall_s") or 0.0)
    model_s = max(0.0, total_s - sim_s)
    return {"task": task_id, "arm": arm, "seed": seed,
            "budget": task.budget, "n_evals": res["n_evals"],
            "ngspice_calls": res["ngspice_calls"], "n_sim_fail": res["n_sim_fail"],
            "feasible": bool(res["feasible"]), "best_obj": res["best_obj"],
            "evals_to_best": res["evals_to_best"],
            "evals_to_first_feasible": _first_feasible(res),
            "trace": res.get("trace"),
            "total_s": round(total_s, 3), "sim_s": round(sim_s, 3),
            "model_s": round(model_s, 3),
            "result_json": os.path.relpath(out, HERE),
            "traj": os.path.relpath(traj, HERE)}


def _first_feasible(res):
    """First eval index whose best-so-far became feasible, censored at budget.

    Reconstructed from the recorded trace (best-so-far every TRACE_EVERY evals):
    the first sampled point with best_obj < 0. Returns None if never feasible
    within budget (the censoring PROTOCOL 5.2 states). Coarse to TRACE_EVERY,
    which is honest about its own resolution and adds no simulation."""
    for pt in (res.get("trace") or []):
        if pt.get("best_obj") is not None and float(pt["best_obj"]) < 0:
            return int(pt["n"])
    return None


# ------------------------------------------------- subprocess plumbing
def _spawn_cell(task_id, arm, seed):
    """Run one cell in a fresh python -- clean process isolation per cell."""
    cmd = [sys.executable, os.path.join(HERE, "score_run.py"),
           "--cell", task_id, arm, str(seed)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"cell {arm}/{task_id}/s{seed} failed:\n{r.stderr[-2000:]}")
    # The cell prints its one-line JSON summary on stdout's last non-empty line.
    line = [ln for ln in r.stdout.splitlines() if ln.strip()][-1]
    return json.loads(line)


# ------------------------------------------------------------- aggregation
def _agg_arm(cells):
    """PROTOCOL 5.3 aggregates for one (task, arm) group of seed-cells."""
    n = len(cells)
    feas = [c for c in cells if c["feasible"]]
    objs = [c["best_obj"] for c in cells]
    ff = [c["evals_to_first_feasible"] for c in cells
          if c["evals_to_first_feasible"] is not None]
    return {
        "n_seeds": n,
        "feasible": f"{len(feas)}/{n}", "n_feasible": len(feas),
        "best_obj_median": round(statistics.median(objs), 6) if objs else None,
        "best_obj_best": round(min(objs), 6) if objs else None,
        "evals_to_first_feasible_median":
            (round(statistics.median(ff), 1) if ff else None),
        "n_seeds_first_feasible": len(ff),
        "sim_s_total": round(sum(c["sim_s"] for c in cells), 2),
        "model_s_total": round(sum(c["model_s"] for c in cells), 2),
        "seeds": sorted(c["seed"] for c in cells),
    }


def _rank_arms(per_task):
    """PROTOCOL 5.4: rank arms per task by (feasible-rate, then median best-obj);
    return {arm: median-rank-across-tasks}."""
    from collections import defaultdict
    ranks = defaultdict(list)
    for task_id, arms in per_task.items():
        order = sorted(arms.items(),
                       key=lambda kv: (-kv[1]["n_feasible"],
                                       (kv[1]["best_obj_median"]
                                        if kv[1]["best_obj_median"] is not None
                                        else float("inf"))))
        for i, (arm, _) in enumerate(order, start=1):
            ranks[arm].append(i)
    return {arm: round(statistics.median(rs), 2) for arm, rs in ranks.items()}


def _consistency_432(per_task):
    """PROTOCOL 8: read the scored wifi24-t2-a row against FINDINGS 43.2."""
    got = per_task.get("wifi24-t2-a")
    if not got:
        return {"checked": False, "note": "wifi24-t2-a not in scored set"}
    out = {"checked": True, "source": PUBLISHED_432["source"], "arms": {}}
    flags = []
    for arm in ("cmaes", "random"):
        pub = PUBLISHED_432[arm]
        g = got.get(arm)
        if not g:
            continue
        pub_n = int(pub["feasible"].split("/")[0])
        d_feas = g["n_feasible"] - pub_n
        drift = abs(d_feas) >= 2
        if drift:
            flags.append(f"{arm}: feasible {g['feasible']} vs published "
                         f"{pub['feasible']} (>=2 seeds apart -- FLAG)")
        out["arms"][arm] = {
            "scored_feasible": g["feasible"], "published_feasible": pub["feasible"],
            "scored_best_obj": g["best_obj_best"], "published_best_obj": pub["best_obj"],
            "scored_median_obj": g["best_obj_median"],
            "published_median_obj": pub["median_obj"],
            "feasible_seed_delta": d_feas, "flag": drift}
    out["flags"] = flags
    out["verdict"] = ("DRIFT -- investigate harness/store" if flags
                      else "consistent within seed noise")
    return out


def aggregate(cells, protocol_sha):
    """Build the scoreboard dict from all cell results."""
    from collections import defaultdict
    per_task = defaultdict(dict)
    grouped = defaultdict(list)
    for c in cells:
        grouped[(c["task"], c["arm"])].append(c)
    for (task_id, arm), group in grouped.items():
        per_task[task_id][arm] = _agg_arm(sorted(group, key=lambda c: c["seed"]))
    per_task = {k: per_task[k] for k in sorted(per_task)}
    sim_total = round(sum(c["sim_s"] for c in cells), 2)
    model_total = round(sum(c["model_s"] for c in cells), 2)
    return {
        "kind": "engineer_scoreboard", "schema": "engineer-scoreboard-v0.1",
        "protocol": {"file": "engineer/PROTOCOL.md",
                     "preregistration_sha": protocol_sha,
                     "amendment": "§43.1 user ruling 2026-08-14: N 5→10",
                     "n_seeds": N_SEEDS, "arms": list(ARMS),
                     "tasks": sorted({c["task"] for c in cells})},
        "per_task": per_task,
        "median_rank": _rank_arms(per_task),
        "consistency_432": _consistency_432(per_task),
        "cost": {"sim_s_total": sim_total, "model_s_total": model_total,
                 "wall_s_total": round(sim_total + model_total, 2),
                 "n_cells": len(cells),
                 "total_evals": sum(c["n_evals"] for c in cells),
                 "total_ngspice_calls": sum(c["ngspice_calls"] for c in cells),
                 "model_frac": round(model_total / max(sim_total + model_total, 1e-9), 4)},
        "harness_git_sha": ds.git_sha(), "ts": EV._now(),
    }


# ------------------------------------------------ canonical trajectory append
def _append_to_canon(cells):
    """Serial pass: append every cell's own trajectory file into the canonical
    trajectories.jsonl, preserving the prior byte prefix (append-only law)."""
    before = os.path.getsize(CANON_TRAJ) if os.path.exists(CANON_TRAJ) else 0
    n_rows = 0
    with open(CANON_TRAJ, "a", encoding="utf-8", newline="\n") as out:
        for c in sorted(cells, key=lambda c: (c["task"], c["arm"], c["seed"])):
            p = os.path.join(HERE, c["traj"])
            if not os.path.exists(p):
                continue
            with open(p, encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        out.write(line if line.endswith("\n") else line + "\n")
                        n_rows += 1
    after = os.path.getsize(CANON_TRAJ)
    return {"canon": os.path.relpath(CANON_TRAJ, HERE),
            "bytes_before": before, "bytes_after": after, "rows_appended": n_rows}


# ------------------------------------------------------------- printout
def _print_board(board):
    print("\n" + "=" * 78)
    print("SCOREBOARD v0.1  (§43.1 amendment N=10; pre-registered @ "
          f"{board['protocol']['preregistration_sha'][:12]})")
    print("=" * 78)
    hdr = (f"{'task':<20}{'arm':<8}{'feas':>6}{'obj median':>12}"
           f"{'obj best':>11}{'ev>feas':>9}{'sim_s':>8}{'model_s':>9}")
    print(hdr)
    print("-" * len(hdr))
    for task_id, arms in board["per_task"].items():
        for arm in ("cmaes", "random"):
            a = arms.get(arm)
            if not a:
                continue
            ff = ("-" if a["evals_to_first_feasible_median"] is None
                  else f"{a['evals_to_first_feasible_median']:.0f}")
            om = ("-" if a["best_obj_median"] is None
                  else f"{a['best_obj_median']:.4f}")
            ob = ("-" if a["best_obj_best"] is None
                  else f"{a['best_obj_best']:.4f}")
            print(f"{task_id:<20}{arm:<8}{a['feasible']:>6}{om:>12}{ob:>11}"
                  f"{ff:>9}{a['sim_s_total']:>8.1f}{a['model_s_total']:>9.1f}")
    print("-" * len(hdr))
    mr = board["median_rank"]
    print("median rank across tasks (1=best; feasible-rate then median obj): "
          + "  ".join(f"{k}={v}" for k, v in sorted(mr.items(), key=lambda kv: kv[1])))
    c = board["cost"]
    print(f"\ncost: {c['n_cells']} cells, {c['total_evals']} evals, "
          f"{c['total_ngspice_calls']} ngspice calls")
    print(f"      simulation {c['sim_s_total']:.1f}s  modeling "
          f"{c['model_s_total']:.1f}s  (modeling = {c['model_frac']*100:.2f}% of wall)")
    cc = board["consistency_432"]
    print(f"\n43.2 consistency check ({cc.get('source', '')}):")
    if cc.get("checked"):
        for arm, d in cc["arms"].items():
            print(f"  {arm:<7} scored {d['scored_feasible']:>4} "
                  f"(best {d['scored_best_obj']}, median {d['scored_median_obj']})"
                  f"  vs published {d['published_feasible']:>4} "
                  f"(best {d['published_best_obj']}, median {d['published_median_obj']})"
                  + ("  <-- FLAG" if d["flag"] else ""))
        print(f"  verdict: {cc['verdict']}")
    print("=" * 78)


# --------------------------------------------------------------------- main
def _protocol_sha():
    """The commit SHA that last touched PROTOCOL.md -- the pre-registration stamp."""
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%H", "--",
                            "engineer/PROTOCOL.md"], cwd=EV.ROOT,
                           capture_output=True, text=True, timeout=10)
        return (r.stdout or "").strip() or None
    except Exception:                                         # noqa: BLE001
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cell", nargs=3, metavar=("TASK", "ARM", "SEED"),
                    help="run one (task, arm, seed) cell; prints its JSON summary")
    ap.add_argument("--seeds", type=int, default=N_SEEDS,
                    help=f"number of seeds 1..S (default {N_SEEDS}, the protocol's)")
    ap.add_argument("--jobs", type=int, default=0,
                    help="parallel cells (0 = min(n_cells, cpu_count))")
    ap.add_argument("--tasks", nargs="+", help="restrict to these task ids")
    ap.add_argument("--no-canon", action="store_true",
                    help="do not append cell trajectories to the canonical table")
    ap.add_argument("--aggregate-only", action="store_true",
                    help="rebuild scoreboard from existing per-cell result JSONs")
    a = ap.parse_args()

    if a.cell:
        task_id, arm, seed = a.cell[0], a.cell[1], int(a.cell[2])
        res = run_cell(task_id, arm, seed)
        print(json.dumps(res))                 # last line = the cell summary
        return 0

    tasks = a.tasks or sorted(SCORING)
    seeds = list(range(1, a.seeds + 1))
    protocol_sha = _protocol_sha()

    if a.aggregate_only:
        cells = _load_existing_cells(tasks, seeds)
    else:
        plan = [(t, arm, s) for t in tasks for arm in ARMS for s in seeds]
        jobs = a.jobs or min(len(plan), os.cpu_count() or 8)
        print(f"score_run: {len(plan)} cells "
              f"({len(tasks)} tasks x {len(ARMS)} arms x {len(seeds)} seeds), "
              f"pool={jobs}")
        print(f"  protocol pre-registered @ {protocol_sha}")
        t0, cells = time.time(), []
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            futs = {ex.submit(_spawn_cell, t, arm, s): (t, arm, s)
                    for (t, arm, s) in plan}
            done = 0
            for fut in as_completed(futs):
                t, arm, s = futs[fut]
                c = fut.result()
                cells.append(c)
                done += 1
                print(f"  [{done:>3}/{len(plan)}] {arm:<6} {t:<18} s{s}  "
                      f"{c['feasible'] and 'FEASIBLE' or 'infeasible':<10} "
                      f"obj={c['best_obj']:.4f}  {c['n_evals']}ev "
                      f"sim={c['sim_s']:.1f}s")
        print(f"  all cells done in {time.time()-t0:.1f}s wall")

    board = aggregate(cells, protocol_sha)
    if not a.no_canon and not a.aggregate_only:
        board["canonical_trajectory_append"] = _append_to_canon(cells)
    os.makedirs(os.path.dirname(SCOREBOARD), exist_ok=True)
    with open(SCOREBOARD, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(EV._plain(board), fh, indent=1)
    _print_board(board)
    print(f"\n  -> {os.path.relpath(SCOREBOARD, HERE)}")
    if board.get("canonical_trajectory_append"):
        ca = board["canonical_trajectory_append"]
        print(f"  -> canonical trajectory: +{ca['rows_appended']} rows "
              f"({ca['bytes_before']} -> {ca['bytes_after']} bytes, prefix preserved)")
    return 0


def _load_existing_cells(tasks, seeds):
    """Reconstruct cell summaries from already-written result JSONs (aggregate-only)."""
    cells = []
    for t in tasks:
        task = get(t)
        for arm in ARMS:
            for s in seeds:
                p = _cell_out(t, arm, s, task.budget)
                if not os.path.exists(p):
                    continue
                with open(p, encoding="utf-8") as fh:
                    res = json.load(fh)
                traj = _cell_traj(t, arm, s)
                sim_s = 0.0
                if os.path.exists(traj):
                    with open(traj, encoding="utf-8") as fh:
                        for line in fh:
                            if line.strip():
                                sim_s += float(((json.loads(line) or {}).get("cost")
                                                or {}).get("wall_s") or 0.0)
                total_s = float(res.get("wall_s") or 0.0)
                cells.append({
                    "task": t, "arm": arm, "seed": s, "budget": task.budget,
                    "n_evals": res["n_evals"], "ngspice_calls": res["ngspice_calls"],
                    "n_sim_fail": res.get("n_sim_fail", 0),
                    "feasible": bool(res["feasible"]), "best_obj": res["best_obj"],
                    "evals_to_best": res["evals_to_best"],
                    "evals_to_first_feasible": _first_feasible(res),
                    "trace": res.get("trace"),
                    "total_s": round(total_s, 3), "sim_s": round(sim_s, 3),
                    "model_s": round(max(0.0, total_s - sim_s), 3),
                    "result_json": os.path.relpath(p, HERE),
                    "traj": os.path.relpath(traj, HERE)})
    return cells


if __name__ == "__main__":
    sys.exit(main())

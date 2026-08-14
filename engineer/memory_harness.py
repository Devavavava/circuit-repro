"""engineer/memory_harness.py -- E-3's cold/warm-memory measurement harness.

Charter 6 E-3: when this line claims "the playbook made the search better", the
cold-start control runs EXPLICITLY -- same tasks, same budget, same seeds, memory
store empty. This harness makes that control so cheap that skipping it is never
tempting, and STRUCTURALLY inseparable from the warm number: `run_pair` runs each
cell TWICE (warm store, then hermetic empty store) and the paired artifact schema
(`engineer-mempair-v0`) has a `warm` and a `cold` field and NO warm-only shape.
You cannot obtain a warm result from this harness without its cold twin.

Pre-registered in `engineer/E3-MEMORY.md` (committed BEFORE this file ran a single
eval). This runner reads that contract; it does not choose it.

HERMETICITY (charter hard constraint, proven, not asserted)
-----------------------------------------------------------
Cold is the `engineer/mem_playbook.py` sidecar pointing `playbook`'s module
attributes at an EMPTY temp store for the duration of the cold consult, restored
after. `lna/playbook.py` is never edited; `lna/playbook/`'s bytes are never
touched. Each cell records a `store_fingerprint`; the warm cell carries the real
store's sha256, the cold cell carries n_entries=0, and this runner asserts the
cold cell is genuinely empty. `--prove-hermetic` runs `git status lna/playbook`
before and after the whole run and refuses to report if it is not clean both times.

BUDGET / DETERMINISM
--------------------
Budget and N are inherited from PROTOCOL.md (10 seeds; the matched per-task
budgets). Warm and cold share the same seed and the same budget; the env's own
counter guarantees each spends EXACTLY `budget` evals (PROTOCOL 2). The env draws
no RNG, so `(task, warm|cold, seed)` fully determines the x-vector sequence.

    python engineer/memory_harness.py                       # full 7 tasks x 10 seeds, paired
    python engineer/memory_harness.py --seeds 2             # a fast shakedown
    python engineer/memory_harness.py --tasks wifi24-t2-a   # one task
    python engineer/memory_harness.py --cell dhruva-l1-t2-a 3   # one (task,seed) pair (subprocess entry)
    python engineer/memory_harness.py --aggregate-only      # rebuild from existing pair JSONs
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
from spec import Spec                                         # noqa: E402
import mem_arm as MA                                          # noqa: E402

N_SEEDS = 10                       # PROTOCOL 4 (amended 2026-08-14): the registered N
ARM = "pb-cmaes"                   # E3-MEMORY.md 2
TRACE_EVERY = 10
PAIR_DIR = os.path.join(EV.DATA_DIR, "_mem_pairs")
PAIR_ARTIFACT = os.path.join(EV.DATA_DIR, "mem_pairs_v0.json")
SCOREBOARD = os.path.join(EV.DATA_DIR, "scoreboard_v0.1.json")   # the registered nulls


# --------------------------------------------------------------- one side
def _trace_of(envr, every=TRACE_EVERY):
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


def _run_side(task, seed, cold, traj_path):
    """Run the pb-cmaes arm on one (task, seed) against the warm or cold store.

    Returns the side's result dict. `cold=True` uses the hermetic empty store."""
    spec = Spec.load(task.spec)
    consult = MA.consult_for_task(spec, cold=cold)
    run_id = EV._run_id(task) + ("-cold" if cold else "-warm")
    logger = TrajectoryLogger(
        run_id=run_id,
        meta={"algo": ARM, "driver": "memory_harness",
              "memory": ("cold" if cold else "warm"), "K": consult.k},
        path=traj_path)
    envr = Env(task, logger=logger)
    diag, t0 = {}, time.time()
    MA.run_pb_cmaes(envr, seed, consult, diag=diag)
    wall = time.time() - t0

    best_x, best_m = envr.best()
    feas, viol = (envr.spec.feasible(best_m) if best_m else (False, None))
    margins = ds.margins_for(envr.spec, best_m) if best_m else {}
    trace = _trace_of(envr)
    return {
        "memory": "cold" if cold else "warm",
        "K": consult.k, "consult": consult.as_dict(),
        "n_evals": envr.n_evals, "ngspice_calls": envr.ngspice_calls,
        "n_sim_fail": envr.n_fail,
        "feasible": bool(feas), "best_obj": envr.best_f,
        "evals_to_best": envr.best_i,
        "evals_to_first_feasible": _first_feasible(trace),
        "viol": ({k: round(v, 6) for k, v in viol.items()} if viol else {}),
        "trace": trace, "algo_diag": diag,
        "wall_s": round(wall, 3),
        "traj": os.path.relpath(traj_path, HERE),
    }


# --------------------------------------------------------------- one PAIR
def run_pair(task_id, seed):
    """THE structural fence: one call, both sides. Runs the arm warm then cold on
    the SAME (task, seed, budget) and returns a paired cell with `warm` and `cold`
    -- there is no code path here that returns a warm result alone."""
    task = get(task_id, seed=seed)
    os.makedirs(PAIR_DIR, exist_ok=True)
    warm_traj = os.path.join(PAIR_DIR, f"warm_{task_id}_s{seed}.jsonl")
    cold_traj = os.path.join(PAIR_DIR, f"cold_{task_id}_s{seed}.jsonl")
    for p in (warm_traj, cold_traj):
        if os.path.exists(p):
            os.remove(p)
    warm = _run_side(task, seed, cold=False, traj_path=warm_traj)
    cold = _run_side(task, seed, cold=True, traj_path=cold_traj)
    # hermeticity assertion: the cold side must have seen an EMPTY store.
    cold_fp = cold["consult"]["store_fingerprint"]
    if cold_fp["n_entries"] != 0:
        raise RuntimeError(f"COLD NOT HERMETIC: {task_id} s{seed} cold store had "
                           f"{cold_fp['n_entries']} entries (expected 0)")
    return {"kind": "engineer_mempair", "schema": "engineer-mempair-v0",
            "task": task_id, "seed": seed, "arm": ARM, "budget": task.budget,
            "warm": warm, "cold": cold}


# --------------------------------------------------------------- subprocess
def _spawn_pair(task_id, seed):
    cmd = [sys.executable, os.path.join(HERE, "memory_harness.py"),
           "--cell", task_id, str(seed)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"pair {task_id}/s{seed} failed:\n{r.stderr[-2000:]}")
    line = [ln for ln in r.stdout.splitlines() if ln.strip()][-1]
    return json.loads(line)


# --------------------------------------------------------------- aggregation
def _agg_side(cells, side):
    n = len(cells)
    sides = [c[side] for c in cells]
    feas = [s for s in sides if s["feasible"]]
    objs = [s["best_obj"] for s in sides]
    ff = [s["evals_to_first_feasible"] for s in sides
          if s["evals_to_first_feasible"] is not None]
    return {
        "n_seeds": n, "feasible": f"{len(feas)}/{n}", "n_feasible": len(feas),
        "best_obj_median": round(statistics.median(objs), 6) if objs else None,
        "best_obj_best": round(min(objs), 6) if objs else None,
        "evals_to_first_feasible_median": (round(statistics.median(ff), 1) if ff else None),
        "n_seeds_first_feasible": len(ff),
        "K": sorted({s["K"] for s in sides}),
        "wall_s_total": round(sum(s["wall_s"] for s in sides), 2),
    }


def _load_nulls():
    """Quote the registered `cmaes` and `random` nulls from scoreboard_v0.1.json
    (E3-MEMORY.md 3). A citation, not a recomputation."""
    if not os.path.exists(SCOREBOARD):
        return {}
    with open(SCOREBOARD, encoding="utf-8") as fh:
        board = json.load(fh)
    out = {}
    for task_id, arms in board.get("per_task", {}).items():
        out[task_id] = {}
        for arm in ("cmaes", "random"):
            a = arms.get(arm)
            if a:
                out[task_id][arm] = {
                    "feasible": a["feasible"], "n_feasible": a["n_feasible"],
                    "best_obj_median": a["best_obj_median"],
                    "best_obj_best": a["best_obj_best"]}
    return {"source": os.path.relpath(SCOREBOARD, HERE),
            "n_seeds": board.get("protocol", {}).get("n_seeds"), "per_task": out}


def _verdict(warm, cold):
    """The acceptance question (E3-MEMORY.md 4): did warm beat its own cold twin
    at matched budget? feasible-rate, tiebroken by median best-obj."""
    if warm["n_feasible"] != cold["n_feasible"]:
        return "warm>cold" if warm["n_feasible"] > cold["n_feasible"] else "warm<cold"
    wm, cm = warm["best_obj_median"], cold["best_obj_median"]
    if wm is None or cm is None:
        return "warm=cold"
    if abs(wm - cm) <= 1e-6:
        return "warm=cold"
    return "warm>cold" if wm < cm else "warm<cold"


def _median_rank(per_task, nulls):
    """Rank {warm, cold, cmaes-null} per task (feasible-rate, then median obj);
    return each arm's median rank across tasks (PROTOCOL 5.4)."""
    from collections import defaultdict
    ranks = defaultdict(list)
    for task_id, d in per_task.items():
        row = {"warm": d["warm"], "cold": d["cold"]}
        nt = (nulls.get("per_task") or {}).get(task_id, {})
        if "cmaes" in nt:
            row["cmaes-null"] = nt["cmaes"]
        order = sorted(row.items(),
                       key=lambda kv: (-kv[1]["n_feasible"],
                                       (kv[1]["best_obj_median"]
                                        if kv[1]["best_obj_median"] is not None
                                        else float("inf"))))
        for i, (arm, _) in enumerate(order, start=1):
            ranks[arm].append(i)
    return {arm: round(statistics.median(rs), 2) for arm, rs in ranks.items()}


def aggregate(cells, prereg_sha):
    from collections import defaultdict
    by_task = defaultdict(list)
    for c in cells:
        by_task[c["task"]].append(c)
    per_task = {}
    for task_id in sorted(by_task):
        group = sorted(by_task[task_id], key=lambda c: c["seed"])
        warm, cold = _agg_side(group, "warm"), _agg_side(group, "cold")
        per_task[task_id] = {"warm": warm, "cold": cold,
                             "verdict": _verdict(warm, cold),
                             "K_warm": warm["K"], "K_cold": cold["K"]}
    nulls = _load_nulls()
    verdicts = [d["verdict"] for d in per_task.values()]
    n_warm_gt = verdicts.count("warm>cold")
    n_warm_lt = verdicts.count("warm<cold")
    n_tie = verdicts.count("warm=cold")
    overall = ("warm beats cold" if n_warm_gt > n_warm_lt
               else "cold beats warm" if n_warm_lt > n_warm_gt
               else "warm ties cold")
    return {
        "kind": "engineer_mempairs", "schema": "engineer-mempair-board-v0",
        "prereg": {"file": "engineer/E3-MEMORY.md", "sha": prereg_sha},
        "arm": ARM, "n_seeds": N_SEEDS,
        "tasks": sorted(by_task),
        "per_task": per_task,
        "nulls": nulls,
        "median_rank": _median_rank(per_task, nulls),
        "acceptance": {
            "question": "does the warm arm beat its own cold control at matched budget?",
            "per_task_verdicts": {t: d["verdict"] for t, d in per_task.items()},
            "n_warm_gt_cold": n_warm_gt, "n_warm_lt_cold": n_warm_lt, "n_tie": n_tie,
            "overall": overall},
        "harness_git_sha": ds.git_sha(), "ts": EV._now(),
    }


# --------------------------------------------------------------- printout
def _print_board(board):
    print("\n" + "=" * 92)
    print(f"MEMORY PAIRS  arm={board['arm']}  N={board['n_seeds']}  "
          f"(prereg @ {board['prereg']['sha'][:12]})")
    print("=" * 92)
    hdr = (f"{'task':<20}{'side':<6}{'K':>4}{'feas':>7}{'obj median':>12}"
           f"{'obj best':>11}{'ev>feas':>9}   verdict")
    print(hdr)
    print("-" * len(hdr))
    nulls = (board.get("nulls") or {}).get("per_task", {})
    for task_id, d in board["per_task"].items():
        for side in ("warm", "cold"):
            a = d[side]
            om = "-" if a["best_obj_median"] is None else f"{a['best_obj_median']:.4f}"
            ob = "-" if a["best_obj_best"] is None else f"{a['best_obj_best']:.4f}"
            ff = "-" if a["evals_to_first_feasible_median"] is None else f"{a['evals_to_first_feasible_median']:.0f}"
            kk = ",".join(str(x) for x in a["K"])
            v = d["verdict"] if side == "warm" else ""
            print(f"{task_id:<20}{side:<6}{kk:>4}{a['feasible']:>7}{om:>12}{ob:>11}{ff:>9}   {v}")
        nt = nulls.get(task_id, {}).get("cmaes")
        if nt:
            om = "-" if nt["best_obj_median"] is None else f"{nt['best_obj_median']:.4f}"
            ob = "-" if nt["best_obj_best"] is None else f"{nt['best_obj_best']:.4f}"
            print(f"{'':<20}{'null':<6}{'-':>4}{nt['feasible']:>7}{om:>12}{ob:>11}{'-':>9}   (cmaes null, scoreboard)")
    print("-" * len(hdr))
    mr = board["median_rank"]
    print("median rank across tasks (1=best): "
          + "  ".join(f"{k}={v}" for k, v in sorted(mr.items(), key=lambda kv: kv[1])))
    ac = board["acceptance"]
    print(f"\nacceptance -- {ac['question']}")
    print(f"  warm>cold: {ac['n_warm_gt_cold']}   warm<cold: {ac['n_warm_lt_cold']}   "
          f"tie: {ac['n_tie']}   ->  OVERALL: {ac['overall'].upper()}")
    print("=" * 92)


# --------------------------------------------------------------- git guard
def _git_status_lna_playbook():
    r = subprocess.run(["git", "status", "--short", "lna/playbook"],
                       cwd=EV.ROOT, capture_output=True, text=True)
    return (r.stdout or "").strip()


def _prereg_sha():
    """The commit that FIRST added E3-MEMORY.md -- the pre-registration timestamp
    (the rule was fixed before any measurement number). A later commit tightened
    §2.2's phrasing while still pre-run; that is `_prereg_amend_sha`."""
    try:
        r = subprocess.run(["git", "log", "--reverse", "--format=%H", "--",
                            "engineer/E3-MEMORY.md"], cwd=EV.ROOT,
                           capture_output=True, text=True, timeout=10)
        shas = [s for s in (r.stdout or "").split() if s]
        return shas[0] if shas else None
    except Exception:                                          # noqa: BLE001
        return None


def _load_existing_pairs(tasks, seeds):
    cells = []
    for p in sorted(glob.glob(os.path.join(PAIR_DIR, "pair_*.json"))):
        with open(p, encoding="utf-8") as fh:
            c = json.load(fh)
        if c["task"] in tasks and c["seed"] in seeds:
            cells.append(c)
    return cells


# --------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cell", nargs=2, metavar=("TASK", "SEED"),
                    help="run one (task, seed) PAIR; prints its JSON summary")
    ap.add_argument("--seeds", type=int, default=N_SEEDS)
    ap.add_argument("--jobs", type=int, default=0)
    ap.add_argument("--tasks", nargs="+")
    ap.add_argument("--aggregate-only", action="store_true")
    ap.add_argument("--prove-hermetic", action="store_true", default=True,
                    help="assert git status lna/playbook is clean before and after")
    a = ap.parse_args()

    if a.cell:
        pair = run_pair(a.cell[0], int(a.cell[1]))
        os.makedirs(PAIR_DIR, exist_ok=True)
        with open(os.path.join(PAIR_DIR, f"pair_{a.cell[0]}_s{a.cell[1]}.json"),
                  "w", encoding="utf-8", newline="\n") as fh:
            json.dump(EV._plain(pair), fh, indent=1)
        # Emit the FULL pair as the last line so the parent gets warm+cold, not a
        # summary (the aggregator needs both sides).
        print(json.dumps(EV._plain(pair)))
        return 0

    tasks = a.tasks or sorted(SCORING)
    seeds = list(range(1, a.seeds + 1))
    prereg_sha = _prereg_sha()

    lna_before = _git_status_lna_playbook()
    if a.prove_hermetic and lna_before:
        print(f"[hermetic] REFUSING: lna/playbook is not clean before the run:\n{lna_before}")
        return 2

    if a.aggregate_only:
        cells = _load_existing_pairs(tasks, seeds)
    else:
        plan = [(t, s) for t in tasks for s in seeds]
        jobs = a.jobs or min(len(plan), os.cpu_count() or 8)
        print(f"memory_harness: {len(plan)} PAIRS "
              f"({len(tasks)} tasks x {len(seeds)} seeds), each = warm+cold, pool={jobs}")
        print(f"  pre-registered @ {prereg_sha}")
        t0, cells = time.time(), []
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            futs = {ex.submit(_spawn_pair, t, s): (t, s) for (t, s) in plan}
            done = 0
            for fut in as_completed(futs):
                t, s = futs[fut]
                pair = fut.result()
                cells.append(pair)
                done += 1
                w, c = pair["warm"], pair["cold"]
                print(f"  [{done:>3}/{len(plan)}] {t:<18} s{s}  "
                      f"warm K{w['K']} {'F' if w['feasible'] else '.'} {w['best_obj']:.4f}"
                      f"  cold K{c['K']} {'F' if c['feasible'] else '.'} {c['best_obj']:.4f}")
        print(f"  all pairs done in {time.time()-t0:.1f}s wall")

    lna_after = _git_status_lna_playbook()
    if a.prove_hermetic and lna_after:
        print(f"[hermetic] FAIL: lna/playbook changed during the run:\n{lna_after}")
        return 2

    board = aggregate(cells, prereg_sha)
    board["hermeticity"] = {"lna_playbook_clean_before": not lna_before,
                            "lna_playbook_clean_after": not lna_after,
                            "cold_stores_empty": all(
                                c["cold"]["consult"]["store_fingerprint"]["n_entries"] == 0
                                for c in cells)}
    os.makedirs(os.path.dirname(PAIR_ARTIFACT), exist_ok=True)
    with open(PAIR_ARTIFACT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(EV._plain(board), fh, indent=1)
    _print_board(board)
    print(f"\n  hermeticity: lna/playbook clean before={board['hermeticity']['lna_playbook_clean_before']} "
          f"after={board['hermeticity']['lna_playbook_clean_after']}  "
          f"cold-stores-empty={board['hermeticity']['cold_stores_empty']}")
    print(f"  -> {os.path.relpath(PAIR_ARTIFACT, HERE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

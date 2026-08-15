"""engineer/score_ext_ldo.py -- the LDO external calibration runner (PROTOCOL §EXT-LDO).

The LDO sibling of score_ext.py: drives the two null arms x N seeds x the
ngspice-runnable AnalogGym LDO family subset under PROTOCOL.md's §EXT-LDO appendix,
and emits `scoreboard_ext_ldo_v0.json`. The appendix is pre-registered (committed
alone) BEFORE this file runs a single eval -- the E-2 falsifier's fence. This runner
only READS the appendix's constants; it does not choose them.

Reuses, does not fork: the cmaes arm is `lna/null_sizer.run_cmaes`, imported
verbatim (via env.py's dep shim); the random arm is uniform `[0,1]^d`
(`numpy.default_rng(seed)`). Both drive `ext_ldo.ExtLdoEnv` through its public
`objective_fn()` -- the E-1 falsifier: the adapter is not edited to be scored, and
this runner is score_ext.py's shape with ext_gym swapped for ext_ldo.

    python engineer/score_ext_ldo.py                 # full 4x2x10, parallel
    python engineer/score_ext_ldo.py --seeds 1       # a 4x2x1 shakedown
    python engineer/score_ext_ldo.py --cell ldo_2 cmaes 1
    python engineer/score_ext_ldo.py --aggregate-only
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import warnings
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import env as EV                                               # noqa: E402 (binds deps)
import ext_ldo as L                                            # noqa: E402
import numpy as np                                             # noqa: E402
from null_sizer import run_cmaes                               # noqa: E402

# ---- appendix constants, READ from PROTOCOL.md §EXT-LDO, not chosen here -------
BUDGET = 1000                    # §EXT-LDO: same as §EXT.5 (AnalogGym's 1000-sim)
N_SEEDS = 10                     # §EXT-LDO: same N as the amp track
ARMS = ("cmaes", "random")       # §EXT-LDO: the same two nulls
TRACE_EVERY = 10
EXT_TRAJ_DIR = os.path.join(EV.DATA_DIR, "_ext_ldo_traj")
SCOREBOARD = os.path.join(EV.DATA_DIR, "scoreboard_ext_ldo_v0.json")
CANON_TRAJ = L.EXT_LDO_TRAJ_TABLE
FAMILIES = list(L.FAMILIES)


def _cell_out(fam, arm, seed, budget):
    return os.path.join(EV.DATA_DIR, f"ext_ldo_{arm}_{fam}_s{seed}_b{budget}.json")


def _cell_traj(fam, arm, seed):
    return os.path.join(EXT_TRAJ_DIR, f"{arm}_{fam}_s{seed}.jsonl")


def _trace_of(env, every=TRACE_EVERY):
    best, seen_feasible, out = float("inf"), False, []
    for i, (_x, m) in enumerate(env.arena.points, start=1):
        best = min(best, float(env.spec.objective(m)))
        if env.spec.feasible(m)[0]:
            seen_feasible = True
        if i % every == 0:
            out.append({"n": i, "best_obj": best, "feasible": seen_feasible})
    return out


def _run_random(env, seed):
    rng = np.random.default_rng(seed)
    f = env.objective_fn()
    try:
        while True:
            f(rng.random(env.dim))
    except L.BudgetExhausted:
        pass


def run_cell(fam, arm, seed):
    os.makedirs(EXT_TRAJ_DIR, exist_ok=True)
    traj = _cell_traj(fam, arm, seed)
    if os.path.exists(traj):
        os.remove(traj)
    task = L.LdoTask(fam, budget=BUDGET, seed=seed)
    logger = L.ExtLdoTrajectoryLogger(path=traj, run_id=L._run_id(task),
                                      meta={"arm": arm, "driver": "score_ext_ldo"})
    env = L.ExtLdoEnv(task, logger=logger)
    t0 = time.time()
    diag = {}
    try:
        if arm == "cmaes":
            run_cmaes(env.objective_fn(), env.dim, seed, diag=diag)
        else:
            _run_random(env, seed)
    except L.BudgetExhausted:
        pass
    total_s = time.time() - t0
    bx, bm = env.best()
    feas, viol = env.spec.feasible(bm) if bm else (False, {})
    trace = _trace_of(env)
    first_feasible = next((pt["n"] for pt in trace if pt["feasible"]), None)
    sim_s = sum(float(p or 0.0) for p in _sim_walls(traj))
    res = {
        "kind": "engineer_ext_ldo_result", "schema": "engineer-ext-ldo-result-v0",
        "fam": fam, "arm": arm, "seed": seed, "budget": BUDGET,
        "n_evals": env.n_evals, "ngspice_calls": env.ngspice_calls,
        "n_sim_fail": env.n_fail, "dim": env.dim,
        "feasible": bool(feas), "best_obj": env.best_f,
        "viol": {k: round(v, 6) for k, v in (viol or {}).items()},
        "evals_to_best": env.best_i, "evals_to_first_feasible": first_feasible,
        "best_metrics": bm, "best_x": bx, "trace": trace, "trace_every": TRACE_EVERY,
        "algo_diag": diag, "harness": env.harness(),
        "total_s": round(total_s, 3), "sim_s": round(sim_s, 3),
        "model_s": round(max(0.0, total_s - sim_s), 3),
        "ts": L._now(),
    }
    out = _cell_out(fam, arm, seed, BUDGET)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(L._plain(res), fh, indent=1)
    return {"fam": fam, "arm": arm, "seed": seed, "budget": BUDGET,
            "n_evals": env.n_evals, "ngspice_calls": env.ngspice_calls,
            "n_sim_fail": env.n_fail, "feasible": bool(feas),
            "best_obj": env.best_f, "evals_to_best": env.best_i,
            "evals_to_first_feasible": first_feasible, "trace": trace,
            "total_s": round(total_s, 3), "sim_s": round(sim_s, 3),
            "model_s": round(max(0.0, total_s - sim_s), 3),
            "result_json": os.path.relpath(out, HERE),
            "traj": os.path.relpath(traj, HERE)}


def _sim_walls(traj):
    if not os.path.exists(traj):
        return []
    out = []
    with open(traj, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                out.append(((json.loads(line) or {}).get("cost") or {}).get("wall_s")
                           or 0.0)
    return out


def _spawn_cell(fam, arm, seed):
    cmd = [sys.executable, os.path.join(HERE, "score_ext_ldo.py"),
           "--cell", fam, arm, str(seed)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"cell {arm}/{fam}/s{seed} failed:\n{r.stderr[-2000:]}")
    line = [ln for ln in r.stdout.splitlines() if ln.strip()][-1]
    return json.loads(line)


# ------------------------------------------------------------- aggregation
def _agg_arm(cells):
    n = len(cells)
    feas = [c for c in cells if c["feasible"]]
    objs = [c["best_obj"] for c in cells]
    ff = [c["evals_to_first_feasible"] for c in cells
          if c["evals_to_first_feasible"] is not None]
    return {
        "n_seeds": n, "feasible": f"{len(feas)}/{n}", "n_feasible": len(feas),
        "best_obj_median": round(statistics.median(objs), 6) if objs else None,
        "best_obj_best": round(min(objs), 6) if objs else None,
        "evals_to_first_feasible_median":
            (round(statistics.median(ff), 1) if ff else None),
        "n_seeds_first_feasible": len(ff),
        "sim_s_total": round(sum(c["sim_s"] for c in cells), 2),
        "model_s_total": round(sum(c["model_s"] for c in cells), 2),
        "seeds": sorted(c["seed"] for c in cells),
    }


def _rank_arms(per_fam):
    ranks = defaultdict(list)
    for fam, arms in per_fam.items():
        order = sorted(arms.items(),
                       key=lambda kv: (-kv[1]["n_feasible"],
                                       (kv[1]["best_obj_median"]
                                        if kv[1]["best_obj_median"] is not None
                                        else float("inf"))))
        for i, (arm, _) in enumerate(order, start=1):
            ranks[arm].append(i)
    return {arm: round(statistics.median(rs), 2) for arm, rs in ranks.items()}


def aggregate(cells, appendix_sha):
    per_fam = defaultdict(dict)
    grouped = defaultdict(list)
    for c in cells:
        grouped[(c["fam"], c["arm"])].append(c)
    for (fam, arm), group in grouped.items():
        per_fam[fam][arm] = _agg_arm(sorted(group, key=lambda c: c["seed"]))
    per_fam = {k: per_fam[k] for k in sorted(per_fam)}
    sim_total = round(sum(c["sim_s"] for c in cells), 2)
    model_total = round(sum(c["model_s"] for c in cells), 2)
    return {
        "kind": "engineer_ext_ldo_scoreboard",
        "schema": "engineer-ext-ldo-scoreboard-v0",
        "protocol": {"file": "engineer/PROTOCOL.md", "section": "§EXT-LDO appendix",
                     "preregistration_sha": appendix_sha,
                     "budget": BUDGET, "n_seeds": N_SEEDS, "arms": list(ARMS),
                     "families": sorted({c["fam"] for c in cells}),
                     "analoggym_sha": L._PINNED_SHA,
                     "adapter_sha256": L._self_sha256(),
                     "ext_gym_sha256": L.X._self_sha256(),
                     "ngspice_version": L._ngspice_version()},
        "per_fam": per_fam,
        "median_rank": _rank_arms(per_fam),
        "cost": {"sim_s_total": sim_total, "model_s_total": model_total,
                 "wall_s_total": round(sim_total + model_total, 2),
                 "n_cells": len(cells),
                 "total_evals": sum(c["n_evals"] for c in cells),
                 "total_ngspice_calls": sum(c["ngspice_calls"] for c in cells),
                 "model_frac": round(model_total / max(sim_total + model_total,
                                                       1e-9), 4)},
        "ts": L._now(),
    }


def _append_to_canon(cells):
    before = os.path.getsize(CANON_TRAJ) if os.path.exists(CANON_TRAJ) else 0
    n_rows = 0
    os.makedirs(os.path.dirname(CANON_TRAJ), exist_ok=True)
    with open(CANON_TRAJ, "a", encoding="utf-8", newline="\n") as out:
        for c in sorted(cells, key=lambda c: (c["fam"], c["arm"], c["seed"])):
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


def _print_board(board):
    print("\n" + "=" * 84)
    print("EXTERNAL LDO SCOREBOARD v0  (PROTOCOL §EXT-LDO; pre-registered @ "
          f"{(board['protocol']['preregistration_sha'] or '?')[:12]})")
    print(f"AnalogGym @ {board['protocol']['analoggym_sha'][:12]}  "
          f"ngspice {board['protocol'].get('ngspice_version','?')}")
    print("=" * 84)
    hdr = (f"{'family':<22}{'arm':<8}{'feas':>6}{'obj median':>14}"
           f"{'obj best':>14}{'ev>feas':>9}{'sim_s':>9}")
    print(hdr)
    print("-" * len(hdr))
    for fam, arms in board["per_fam"].items():
        for arm in ("cmaes", "random"):
            a = arms.get(arm)
            if not a:
                continue
            ff = ("-" if a["evals_to_first_feasible_median"] is None
                  else f"{a['evals_to_first_feasible_median']:.0f}")
            om = ("-" if a["best_obj_median"] is None
                  else f"{a['best_obj_median']:.2f}")
            ob = ("-" if a["best_obj_best"] is None
                  else f"{a['best_obj_best']:.2f}")
            print(f"{fam:<22}{arm:<8}{a['feasible']:>6}{om:>14}{ob:>14}"
                  f"{ff:>9}{a['sim_s_total']:>9.1f}")
    print("-" * len(hdr))
    mr = board["median_rank"]
    print("median rank across families (1=best; feasible-rate then median obj): "
          + "  ".join(f"{k}={v}" for k, v in sorted(mr.items(), key=lambda kv: kv[1])))
    c = board["cost"]
    print(f"\ncost: {c['n_cells']} cells, {c['total_evals']} evals, "
          f"{c['total_ngspice_calls']} ngspice calls")
    print(f"      simulation {c['sim_s_total']:.1f}s  modeling "
          f"{c['model_s_total']:.1f}s  (modeling = {c['model_frac']*100:.2f}% of wall)")
    print("=" * 84)


def _appendix_sha():
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%H", "--",
                            "engineer/PROTOCOL.md"], cwd=EV.ROOT,
                           capture_output=True, text=True, timeout=10)
        return (r.stdout or "").strip() or None
    except Exception:                                              # noqa: BLE001
        return None


def _load_existing(fams, seeds):
    cells = []
    for fam in fams:
        for arm in ARMS:
            for s in seeds:
                p = _cell_out(fam, arm, s, BUDGET)
                if not os.path.exists(p):
                    continue
                res = json.load(open(p, encoding="utf-8"))
                cells.append({"fam": fam, "arm": arm, "seed": s, "budget": BUDGET,
                              "n_evals": res["n_evals"],
                              "ngspice_calls": res["ngspice_calls"],
                              "n_sim_fail": res.get("n_sim_fail", 0),
                              "feasible": bool(res["feasible"]),
                              "best_obj": res["best_obj"],
                              "evals_to_best": res.get("evals_to_best"),
                              "evals_to_first_feasible":
                                  res.get("evals_to_first_feasible"),
                              "trace": res.get("trace"),
                              "total_s": res.get("total_s", 0.0),
                              "sim_s": res.get("sim_s", 0.0),
                              "model_s": res.get("model_s", 0.0),
                              "result_json": os.path.relpath(p, HERE),
                              "traj": os.path.relpath(_cell_traj(fam, arm, s), HERE)})
    return cells


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cell", nargs=3, metavar=("FAM", "ARM", "SEED"))
    ap.add_argument("--seeds", type=int, default=N_SEEDS)
    ap.add_argument("--jobs", type=int, default=0)
    ap.add_argument("--fams", nargs="+")
    ap.add_argument("--no-canon", action="store_true")
    ap.add_argument("--aggregate-only", action="store_true")
    a = ap.parse_args()

    if a.cell:
        fam, arm, seed = a.cell[0], a.cell[1], int(a.cell[2])
        print(json.dumps(run_cell(fam, arm, seed)))
        return 0

    fams = a.fams or list(FAMILIES)
    seeds = list(range(1, a.seeds + 1))
    appendix_sha = _appendix_sha()

    if a.aggregate_only:
        cells = _load_existing(fams, seeds)
    else:
        plan = [(fam, arm, s) for fam in fams for arm in ARMS for s in seeds]
        jobs = a.jobs or min(len(plan), os.cpu_count() or 8)
        print(f"score_ext_ldo: {len(plan)} cells ({len(fams)} families x "
              f"{len(ARMS)} arms x {len(seeds)} seeds), pool={jobs}, budget={BUDGET}")
        print(f"  appendix pre-registered @ {appendix_sha}")
        t0, cells = time.time(), []
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            futs = {ex.submit(_spawn_cell, fam, arm, s): (fam, arm, s)
                    for (fam, arm, s) in plan}
            done = 0
            for fut in as_completed(futs):
                fam, arm, s = futs[fut]
                c = fut.result()
                cells.append(c)
                done += 1
                print(f"  [{done:>3}/{len(plan)}] {arm:<6} {fam:<20} s{s}  "
                      f"{'FEASIBLE' if c['feasible'] else 'infeasible':<10} "
                      f"obj={c['best_obj']:.2f}  {c['n_evals']}ev "
                      f"sim={c['sim_s']:.0f}s")
        print(f"  all cells done in {time.time()-t0:.1f}s wall")

    board = aggregate(cells, appendix_sha)
    if not a.no_canon and not a.aggregate_only:
        board["canonical_trajectory_append"] = _append_to_canon(cells)
    os.makedirs(os.path.dirname(SCOREBOARD), exist_ok=True)
    with open(SCOREBOARD, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(L._plain(board), fh, indent=1)
    _print_board(board)
    print(f"\n  -> {os.path.relpath(SCOREBOARD, HERE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

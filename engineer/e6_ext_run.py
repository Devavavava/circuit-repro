"""engineer/e6_ext_run.py -- the E-6 FULL-TIER EXTERNAL runner (E6-BUDGET.md §4.2, §6).

Human-gated (GO 2026-08-19). The ROADMAP G1 falsifier binds on BOTH external
tracks (E6-BUDGET.md §6), so the full tier runs racing vs the incumbent on:
  - the 14 ngspice-runnable AnalogGym amplifiers (PROTOCOL §EXT, 1000 evals, N=10)
  - the 4 AnalogGym LDO families            (PROTOCOL §EXT-LDO, 1000 evals, N=10)

ARMS, matched to the digit at 1000 evals/cell:
  (A) incumbent = the registered `cmaes` null EXACTLY -- score_ext.run_cell(amp,
      "cmaes", seed) / score_ext_ldo.run_cell(fam, "cmaes", seed), IMPORTED and
      called, not re-implemented (the E-1/E-2 rule). This is arm A of §2 on the
      external env.
  (B) racing = e6_racing.run_racing on the SAME ExtEnv / ExtLdoEnv objective_fn()
      interface -- the pre-registered k=4 / r-schedule / cull-top-1 arm, verbatim
      (e6_racing.run_racing is env-agnostic; its budget-exhaustion catch already
      recognises the external BudgetExhausted, see e6_racing._BUDGET_EXC).

At 1000 evals: r = min(60, max(15, round(0.15*1000/4))) = 38, k*r = 152 triage,
survivor resume = 848 new evals -- the healthy unfragmented regime the arm exists
to test (E6-BUDGET.md §2.3).

Per-cell result JSONs `e6ext_{track}_{arm}_{cell}_s{seed}_b1000.json` + per-cell
trajectory files; a NEW E-6-owned table e6_ext_trajectories.jsonl is appended in
one serial pass (the canonical ext_trajectories.jsonl / ext_ldo_trajectories.jsonl
are left BYTE-UNTOUCHED -- append-only law). SERIAL, --resume-safe.

    python engineer/e6_ext_run.py --track amp    # 14 amps x 2 arms x 10 seeds
    python engineer/e6_ext_run.py --track ldo    # 4 families x 2 arms x 10 seeds
    python engineer/e6_ext_run.py --track both --resume
    python engineer/e6_ext_run.py --cell amp HoiLee_AFFC_Pin_3 racing 1   # one cell
"""
import argparse
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
import ext_gym as X                                           # noqa: E402
import ext_ldo as L                                           # noqa: E402
import e6_racing as E6                                        # noqa: E402
import score_ext as SX                                        # noqa: E402
import score_ext_ldo as SL                                    # noqa: E402

BUDGET = 1000                                                 # §EXT.5 / §EXT-LDO
N_SEEDS = 10                                                  # §EXT.5 / §EXT-LDO
ARMS = ("incumbent", "racing")
TRACE_EVERY = 10
E6_EXT_TRAJ_DIR = os.path.join(EV.DATA_DIR, "_e6_ext_traj")
E6_EXT_TRAJ_TABLE = os.path.join(EV.DATA_DIR, "e6_ext_trajectories.jsonl")
BOARD = os.path.join(EV.DATA_DIR, "e6_ext_v0.json")

# per-track plumbing: (module, task-ctor, env-ctor, logger-ctor, runnable-list)
TRACKS = {
    "amp": dict(mod=X, score=SX, Task=X.ExtTask, Env=X.ExtEnv,
                Logger=X.ExtTrajectoryLogger, cells=list(X.RUNNABLE), key="amp"),
    "ldo": dict(mod=L, score=SL, Task=L.LdoTask, Env=L.ExtLdoEnv,
                Logger=L.ExtLdoTrajectoryLogger, cells=list(L.FAMILIES), key="fam"),
}


def _cell_out(track, cell, arm, seed):
    return os.path.join(EV.DATA_DIR, f"e6ext_{track}_{arm}_{cell}_s{seed}_b{BUDGET}.json")


def _cell_traj(track, cell, arm, seed):
    return os.path.join(E6_EXT_TRAJ_DIR, f"{track}_{arm}_{cell}_s{seed}.jsonl")


def _trace_of(env, every=TRACE_EVERY):
    """Best-so-far + seen-feasible every `every` evals (the score_ext convention:
    feasibility is the real predicate, NOT the FoM sign)."""
    best, seen, out = float("inf"), False, []
    for i, (_x, m) in enumerate(env.arena.points, start=1):
        best = min(best, float(env.spec.objective(m)))
        if env.spec.feasible(m)[0]:
            seen = True
        if i % every == 0:
            out.append({"n": i, "best_obj": best, "feasible": seen})
    return out


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


def run_cell(track, cell, arm, seed):
    """One (track, cell, arm, seed) at BUDGET. Arm A -> the registered cmaes null
    via the imported score_ext[_ldo].run_cell. Arm B -> e6_racing.run_racing on the
    same ExtEnv objective_fn()."""
    T = TRACKS[track]
    if arm == "incumbent":
        # The registered cmaes null EXACTLY -- imported, not re-implemented.
        r = T["score"].run_cell(cell, "cmaes", seed)
        traj_src = os.path.join(HERE, r["traj"])
        # normalise into our schema/paths so aggregation is uniform
        sim_s = r["sim_s"]
        summary = {"track": track, "cell": cell, "arm": arm, "seed": seed,
                   "budget": BUDGET, "n_evals": r["n_evals"],
                   "ngspice_calls": r["ngspice_calls"], "n_sim_fail": r["n_sim_fail"],
                   "feasible": bool(r["feasible"]), "best_obj": r["best_obj"],
                   "evals_to_best": r["evals_to_best"],
                   "evals_to_first_feasible": r["evals_to_first_feasible"],
                   "trace": r["trace"], "total_s": r["total_s"], "sim_s": sim_s,
                   "model_s": r["model_s"],
                   "result_json": os.path.relpath(_cell_out(track, cell, arm, seed), HERE),
                   "traj_src": traj_src}
        # copy the incumbent's cmaes result JSON under our e6ext_ name for provenance
        with open(_cell_out(track, cell, arm, seed), "w", encoding="utf-8",
                  newline="\n") as fh:
            src = json.load(open(os.path.join(HERE, r["result_json"]), encoding="utf-8"))
            src["e6_arm"] = "incumbent"
            src["e6_note"] = ("arm A = registered cmaes null, produced by "
                              "score_ext[_ldo].run_cell(cell,'cmaes',seed) imported")
            json.dump(T["mod"]._plain(src), fh, indent=1)
        return summary

    # arm == racing
    os.makedirs(E6_EXT_TRAJ_DIR, exist_ok=True)
    traj = _cell_traj(track, cell, arm, seed)
    if os.path.exists(traj):
        os.remove(traj)
    task = T["Task"](cell, budget=BUDGET, seed=seed)
    logger = T["Logger"](path=traj, run_id=T["mod"]._run_id(task) + "-racing",
                         meta={"arm": "racing", "driver": "e6_ext_run",
                               "k": E6.K_STARTS, "r": E6.triage_evals(BUDGET)})
    env = T["Env"](task, logger=logger)
    diag, t0 = {}, time.time()
    E6.run_racing(env, seed, diag=diag)
    total_s = time.time() - t0
    bx, bm = env.best()
    feas, viol = env.spec.feasible(bm) if bm else (False, {})
    trace = _trace_of(env)
    first_feasible = next((pt["n"] for pt in trace if pt["feasible"]), None)
    sim_s = sum(float(p or 0.0) for p in _sim_walls(traj))
    res = {
        "kind": f"engineer_e6ext_{track}_result",
        "schema": f"engineer-e6ext-{track}-result-v0",
        "e6_arm": "racing", "track": track, "cell": cell, "arm": "racing",
        "arm_desc": "racing: k triage starts, cull top-1, warm-resume survivor "
                    "-- e6_racing.run_racing, run_cmaes imported verbatim",
        "seed": seed, "budget": BUDGET, "dim": env.dim,
        "n_evals": env.n_evals, "ngspice_calls": env.ngspice_calls,
        "n_sim_fail": env.n_fail, "feasible": bool(feas), "best_obj": env.best_f,
        "viol": {k: round(v, 6) for k, v in (viol or {}).items()},
        "evals_to_best": env.best_i, "evals_to_first_feasible": first_feasible,
        "best_metrics": bm, "best_x": bx, "trace": trace, "trace_every": TRACE_EVERY,
        "algo_diag": diag, "harness": env.harness(),
        "total_s": round(total_s, 3), "sim_s": round(sim_s, 3),
        "model_s": round(max(0.0, total_s - sim_s), 3), "ts": T["mod"]._now(),
    }
    with open(_cell_out(track, cell, arm, seed), "w", encoding="utf-8",
              newline="\n") as fh:
        json.dump(T["mod"]._plain(res), fh, indent=1)
    return {"track": track, "cell": cell, "arm": arm, "seed": seed, "budget": BUDGET,
            "n_evals": env.n_evals, "ngspice_calls": env.ngspice_calls,
            "n_sim_fail": env.n_fail, "feasible": bool(feas), "best_obj": env.best_f,
            "evals_to_best": env.best_i, "evals_to_first_feasible": first_feasible,
            "trace": trace, "total_s": round(total_s, 3), "sim_s": round(sim_s, 3),
            "model_s": round(max(0.0, total_s - sim_s), 3),
            "result_json": os.path.relpath(_cell_out(track, cell, arm, seed), HERE),
            "traj_src": traj}


def _spawn_cell(track, cell, arm, seed):
    cmd = [sys.executable, os.path.join(HERE, "e6_ext_run.py"),
           "--cell", track, cell, arm, str(seed)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"cell {track}/{arm}/{cell}/s{seed} failed:\n{r.stderr[-3000:]}")
    line = [ln for ln in r.stdout.splitlines() if ln.strip()][-1]
    return json.loads(line)


# ------------------------------------------------------------- aggregation
def _agg_arm(cells):
    n = len(cells)
    feas = [c for c in cells if c["feasible"]]
    objs = [c["best_obj"] for c in cells]
    ff = [c["evals_to_first_feasible"] for c in cells
          if c["evals_to_first_feasible"] is not None]
    return {"n_seeds": n, "feasible": f"{len(feas)}/{n}", "n_feasible": len(feas),
            "best_obj_median": round(statistics.median(objs), 6) if objs else None,
            "best_obj_best": round(min(objs), 6) if objs else None,
            "best_obj_worst": round(max(objs), 6) if objs else None,
            "evals_to_first_feasible_median": (round(statistics.median(ff), 1) if ff else None),
            "n_seeds_first_feasible": len(ff),
            "sim_s_total": round(sum(c["sim_s"] for c in cells), 2),
            "seeds": sorted(c["seed"] for c in cells)}


def _rank(per_cell):
    ranks = defaultdict(list)
    for _c, arms in per_cell.items():
        order = sorted(arms.items(),
                       key=lambda kv: (-kv[1]["n_feasible"],
                                       (kv[1]["best_obj_median"]
                                        if kv[1]["best_obj_median"] is not None
                                        else float("inf"))))
        for i, (arm, _) in enumerate(order, start=1):
            ranks[arm].append(i)
    return {arm: round(statistics.median(rs), 2) for arm, rs in ranks.items()}


def _budget_match_check(cells):
    by = defaultdict(dict)
    for c in cells:
        by[(c["track"], c["cell"], c["seed"])][c["arm"]] = c["n_evals"]
    mism = [{"cell": k, "evals": v} for k, v in by.items()
            if len(v) == 2 and len(set(v.values())) != 1]
    return {"all_matched": not mism, "n_pairs_checked": len(by), "mismatches": mism}


def aggregate(cells):
    per_track = {}
    ranks = {}
    for track in sorted({c["track"] for c in cells}):
        tc = [c for c in cells if c["track"] == track]
        grouped = defaultdict(lambda: defaultdict(list))
        for c in tc:
            grouped[c["cell"]][c["arm"]].append(c)
        per_cell = {}
        for cell in sorted(grouped):
            arms = {a: _agg_arm(sorted(g, key=lambda c: c["seed"]))
                    for a, g in grouped[cell].items()}
            per_cell[cell] = arms
        per_track[track] = per_cell
        ranks[track] = _rank(per_cell)
    return {"kind": "engineer_e6_ext", "schema": "engineer-e6-ext-v0",
            "tier": "FULL external tracks (E6-BUDGET.md §4.2, §6)",
            "config": {"budget": BUDGET, "arms": list(ARMS), "k": E6.K_STARTS,
                       "cull_to": E6.CULL_TO, "r": E6.triage_evals(BUDGET),
                       "tracks": sorted({c["track"] for c in cells})},
            "per_track": per_track, "median_rank_by_track": ranks,
            "budget_match_check": _budget_match_check(cells),
            "cost": {"n_cells": len(cells),
                     "total_evals": sum(c["n_evals"] for c in cells),
                     "total_ngspice_calls": sum(c["ngspice_calls"] for c in cells),
                     "sim_s_total": round(sum(c["sim_s"] for c in cells), 2)},
            "ts": EV._now()}


def _append_traj(cells):
    before = os.path.getsize(E6_EXT_TRAJ_TABLE) if os.path.exists(E6_EXT_TRAJ_TABLE) else 0
    n_rows = 0
    os.makedirs(os.path.dirname(E6_EXT_TRAJ_TABLE), exist_ok=True)
    with open(E6_EXT_TRAJ_TABLE, "a", encoding="utf-8", newline="\n") as out:
        for c in sorted(cells, key=lambda c: (c["track"], c["cell"], c["arm"], c["seed"])):
            p = c.get("traj_src")
            if not p or not os.path.exists(p):
                continue
            with open(p, encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        out.write(line if line.endswith("\n") else line + "\n")
                        n_rows += 1
    after = os.path.getsize(E6_EXT_TRAJ_TABLE)
    return {"table": os.path.relpath(E6_EXT_TRAJ_TABLE, HERE),
            "bytes_before": before, "bytes_after": after, "rows_appended": n_rows}


def _print_board(board):
    print("\n" + "=" * 92)
    print("E-6 EXTERNAL TRACKS  (FULL tier; racing vs registered cmaes incumbent)")
    print(f"  k={board['config']['k']} r={board['config']['r']} "
          f"cull=top-{board['config']['cull_to']} budget={board['config']['budget']} "
          f"N=10")
    print("=" * 92)
    for track, per_cell in board["per_track"].items():
        print(f"\n--- track: {track} ---")
        hdr = (f"{'cell':<24}{'arm':<11}{'feas':>6}{'obj median':>14}"
               f"{'obj best':>14}{'ev>feas':>9}")
        print(hdr)
        print("-" * len(hdr))
        for cell, arms in per_cell.items():
            for arm in ("incumbent", "racing"):
                a = arms.get(arm)
                if not a:
                    continue
                om = "-" if a["best_obj_median"] is None else f"{a['best_obj_median']:.3f}"
                ob = "-" if a["best_obj_best"] is None else f"{a['best_obj_best']:.3f}"
                ff = ("-" if a["evals_to_first_feasible_median"] is None
                      else f"{a['evals_to_first_feasible_median']:.0f}")
                print(f"{cell:<24}{arm:<11}{a['feasible']:>6}{om:>14}{ob:>14}{ff:>9}")
        print(f"median rank ({track}): "
              + "  ".join(f"{k}={v}" for k, v in
                          sorted(board['median_rank_by_track'][track].items(),
                                 key=lambda kv: kv[1])))
    bm = board["budget_match_check"]
    print(f"\nBUDGET MATCH: all {bm['n_pairs_checked']} (cell,seed) pairs equal "
          f"evals across arms? {'YES' if bm['all_matched'] else 'NO ' + str(bm['mismatches'])}")
    c = board["cost"]
    print(f"cost: {c['n_cells']} cells, {c['total_evals']} evals, "
          f"{c['total_ngspice_calls']} ngspice calls, sim {c['sim_s_total']:.0f}s")
    print("=" * 92)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cell", nargs=4, metavar=("TRACK", "CELL", "ARM", "SEED"))
    ap.add_argument("--track", choices=["amp", "ldo", "both"], default="both")
    ap.add_argument("--seeds", type=int, default=N_SEEDS)
    ap.add_argument("--cells", nargs="+", help="restrict to these cells")
    ap.add_argument("--jobs", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()

    if a.cell:
        track, cell, arm, seed = a.cell[0], a.cell[1], a.cell[2], int(a.cell[3])
        print(json.dumps(TRACKS[track]["mod"]._plain(run_cell(track, cell, arm, seed))))
        return 0

    tracks = ["amp", "ldo"] if a.track == "both" else [a.track]
    seeds = list(range(1, a.seeds + 1))
    plan = []
    for track in tracks:
        cells_list = a.cells or TRACKS[track]["cells"]
        for cell in cells_list:
            for arm in ARMS:
                for s in seeds:
                    plan.append((track, cell, arm, s))
    jobs = a.jobs or min(len(plan), os.cpu_count() or 8)
    print(f"e6_ext_run FULL: {len(plan)} cells "
          f"(tracks={tracks}, {len(seeds)} seeds, budget={BUDGET}); pool={jobs}, "
          f"per-cell JSON crash-safe.")

    t0, cells, todo = time.time(), [], []
    for (track, cell, arm, s) in plan:
        out = _cell_out(track, cell, arm, s)
        if a.resume and os.path.exists(out):
            res = json.load(open(out, encoding="utf-8"))
            traj = _cell_traj(track, cell, arm, s)
            summ = {"track": track, "cell": cell, "arm": arm, "seed": s,
                    "budget": BUDGET, "n_evals": res["n_evals"],
                    "ngspice_calls": res["ngspice_calls"],
                    "n_sim_fail": res.get("n_sim_fail", 0),
                    "feasible": bool(res["feasible"]), "best_obj": res["best_obj"],
                    "evals_to_best": res.get("evals_to_best"),
                    "evals_to_first_feasible": res.get("evals_to_first_feasible"),
                    "trace": res.get("trace"), "total_s": res.get("total_s", 0.0),
                    "sim_s": res.get("sim_s", 0.0), "model_s": res.get("model_s", 0.0),
                    "traj_src": traj if os.path.exists(traj) else None}
            cells.append(summ)
            print(f"  [resume] {track} {arm:<10} {cell:<22} s{s}  SKIP "
                  f"obj={summ['best_obj']:.3f}")
        else:
            todo.append((track, cell, arm, s))
    done = 0
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        futs = {ex.submit(_spawn_cell, track, cell, arm, s): (track, cell, arm, s)
                for (track, cell, arm, s) in todo}
        for fut in as_completed(futs):
            track, cell, arm, s = futs[fut]
            c = fut.result()
            cells.append(c)
            done += 1
            print(f"  [{done:>3}/{len(todo)}] {track} {arm:<10} {cell:<22} s{s}  "
                  f"{'FEASIBLE' if c['feasible'] else 'infeasible':<10} "
                  f"obj={c['best_obj']:.3f}  {c['n_evals']}ev  [{time.time()-t0:.0f}s]")
    print(f"  all {len(plan)} cells done in {time.time()-t0:.1f}s wall")

    board = aggregate(cells)
    board["e6_ext_trajectory_append"] = _append_traj(cells)
    with open(BOARD, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(EV._plain(board), fh, indent=1)
    _print_board(board)
    print(f"\n  -> {os.path.relpath(BOARD, HERE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

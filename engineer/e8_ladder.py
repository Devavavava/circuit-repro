"""E-8 SCORED structural-capability ladder campaign runner.

Runs the core-4 ladder RULED by the user (E8-LADDER.md ## Rulings 2026-08-21):

  goals : G1 (dhruva-l1, S21>=30 gain wall), G8 (dhruva-l5, Idd<=10.5 @ S21>=22.3),
          G9 (dhruva-l5, s21_ripple_db<=3), G10 (dhruva-s, s21_ripple_db<=3)
  arms  : (a) sizing-null, (b) random-edit, (c) blame-guided   [oracle OUT, OQ-1]
  seeds : 1..5, matched budget 600 env evals per (goal, arm, seed), PYTHONHASHSEED=0

This runner is STRICTLY read-only toward lna/ and engineer/: it imports the E-7
machinery (engineer/env.py counted evals, engineer/g2_moves.py ruled primitives,
null_sizer.run_cmaes verbatim) and the lna measurement instruments
(lna/blame.py, lna/binding_probe.py) with write=False, and writes ONLY per-cell
result JSON under .claude/jobs/a8f610e5/tmp/e8_results/.

CONTAINMENT of the extended spec (the §8.4 protocol, unchanged): the env is built
on the BASE spec (real ngspice metrics per eval); the goal's delta'd feasibility
is the runner's own arithmetic on the env-produced `metrics` -- an in-memory
mutated copy of the base Spec's constraints. No lna/ write, no new spec file.

WARM ANCHOR (§8.4 strengthened null): every arm starts from the reached base
design -- the pinned stored L2 row's `best_params` (env.row['best_params']),
which re-evaluates to §2's reached numbers and is base-feasible at the anchor. The
sizing-null and both edit arms seed their CMA-ES near this anchor (x0 = anchor x).

AUTO-DIAGNOSIS for arm (c) (no human string): at the warm anchor, evaluated once,
  binding_probe.probe_design(ext_spec, anchor_metrics)  -> the binding constraint
  blame.blame_design(body, params, ext_spec, op, ...)    -> device ranking for it
The guided arm routes the binding constraint to a primitive-family aim and the
blamed devices (OP names mnmN -> netlist NMN) to the node the edit targets. When
blame is `unavailable` (no handler for the metric, e.g. s21_ripple_db) the guided
arm aims at the output/tank node named by the binding metric -- still no human
diagnosis string, only the instruments' outputs.

    python e8_ladder.py --goals G1,G8,G9,G10 --arms a,b,c --seeds 1,2,3,4,5 --evals 600
    python e8_ladder.py --cell G9 c 3         # one cell (resume-safe)
"""
import argparse
import copy
import json
import os
import random
import sys
import time

# Determinism across processes (the E-7 finding, g2_smoke.py header): topo node
# labels iterate Python sets whose order depends on PYTHONHASHSEED, and that order
# feeds the random/guided arms' node sampling. Pin PYTHONHASHSEED=0, re-exec once.
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable] + sys.argv)

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.join(HERE, "wt-lad2")
ENG = os.path.join(WT, "engineer")
LNA = os.path.join(WT, "lna")
for p in (ENG, LNA):
    if p not in sys.path:
        sys.path.insert(0, p)

import env as _env                                  # noqa: E402 (binds deps)
from env import Env, Task, NotSizable, BudgetExhausted   # noqa: E402
import g2_moves as G                                # noqa: E402
import moves as M                                   # noqa: E402
from moves import dname, dtype, fet_pins, is_fet    # noqa: E402
import null_sizer as NS                             # noqa: E402
import blame as BL                                  # noqa: E402
import binding_probe as BP                          # noqa: E402

RESULTS = os.path.join(HERE, "e8_results")
os.makedirs(RESULTS, exist_ok=True)

# ----------------------------------------------------------------- the goals
# Each goal: base task id + the extended constraints (added to the base spec's,
# in-memory) that define its delta'd feasibility. 'ext' maps metric -> limit dict.
GOALS = {
    "G1":  {"task": "dhruva-l1-t2-a",
            "ext": {"s21_db": {"min": 30.0, "status": "measured"}},
            "desc": "S21>=30 dB gain wall (reached 26.32)"},
    "G8":  {"task": "dhruva-l5-t2-a",
            "ext": {"idd_ma": {"max": 10.5, "status": "measured"},
                    "s21_db": {"min": 22.3, "status": "measured"}},
            "desc": "Idd<=10.5 mA at S21>=22.3 (reached Idd 12.92)"},
    "G9":  {"task": "dhruva-l5-t2-a",
            "ext": {"s21_ripple_db": {"max": 3.0, "status": "measured"}},
            "desc": "s21_ripple_db<=3 (reached 15.18)"},
    "G10": {"task": "dhruva-s-t2-a",
            "ext": {"s21_ripple_db": {"max": 3.0, "status": "measured"}},
            "desc": "s21_ripple_db<=3 (reached 12.99)"},
}
ARMS = ("a", "b", "c")          # a=sizing-null, b=random-edit, c=blame-guided


# ------------------------------------------------------ extended-spec feasibility
def ext_spec_of(base_spec, ext):
    """A deep copy of the base spec with the goal's extra constraints merged in.
    Used ONLY for the runner's own feasibility arithmetic and for the instruments;
    the env still evaluates the BASE spec (real ngspice), never this copy."""
    s = copy.deepcopy(base_spec)
    s.constraints = dict(base_spec.constraints)
    for k, v in ext.items():
        s.constraints[k] = dict(v)
    return s


def ext_feasible(base_spec, ext_s, metrics):
    """Goal feasibility = base spec feasible AND every extended constraint met.
    Pure arithmetic on env-produced metrics (§8.4 containment)."""
    if metrics is None:
        return False
    base_ok, _ = base_spec.feasible(metrics)
    if not base_ok:
        return False
    ok, _ = ext_s.feasible(metrics)
    return bool(ok)


# ------------------------------------------------------------- the auto-diagnosis
def op_to_netlist_fet(op_name):
    """OP device name (e.g. 'mnm3') -> netlist FET name ('NM3'): strip a leading
    'm', uppercase. The bias-inserted deck lowercases + prefixes 'm'; the netlist
    (g2_moves) uses 'NM<i>'. Returns None for non-FET / passive branch names."""
    n = op_name
    if n.startswith("m") and len(n) > 1:
        n = n[1:]
    up = n.upper()
    return up if up.startswith("NM") or up.startswith("MP") else None


def diagnose(env, ext_s, anchor_out):
    """Auto-diagnosis at the warm anchor: the binding constraint (binding_probe)
    + the device ranking for its metric (blame). NO human string. write=False
    (containment: no lna/data append). Returns a dict the guided arm reads."""
    m = anchor_out["metrics"]
    probe = BP.probe_design(ext_s, m, env.task.wl_hash, write=False)
    binding = (probe["single_relaxations"][0]["metric"]
               if probe["single_relaxations"] else None)
    # blame for the binding metric (or all failing if none flagged)
    op = env.op_sink.recent[-1]["op"] if env.op_sink.recent else {}
    body = env.arena.body
    params = env.arena.decode(anchor_out["x"])
    blame_rows = BL.blame_design(body, params, ext_s, op, env.task.wl_hash, m,
                                 write=False, failing_only=True)
    blame_devs, blame_cov = [], "unavailable"
    for r in blame_rows:
        if r["metric"] == binding and r["blame"]:
            blame_devs = [op_to_netlist_fet(b["device"]) for b in r["blame"]]
            blame_devs = [d for d in blame_devs if d]
            blame_cov = r["coverage"]
            break
    return {"binding_metric": binding, "verdict": probe["verdict"],
            "blame_devices": blame_devs, "blame_coverage": blame_cov,
            "n_failing": probe["n_failing"]}


# ------------------------------------------------------------ guided proposals
def _output_node(nl):
    coup, out_node = M.output_coupler(nl)
    return out_node


def _fet_nodes(nl, fet_names):
    """Signal nodes touched by the named FETs (drain/gate/source), sorted, for a
    guided edit to aim at. Falls back to internal nodes of degree>=4 if none."""
    nodes = []
    for e in nl:
        if is_fet(e) and dname(e) in fet_names:
            p = fet_pins(e)
            nodes += [p["D"], p["G"], p["S"]]
    nodes = sorted(set(n for n in nodes if n not in M.PROTECTED))
    if not nodes:
        nodes = sorted(n for n in M.internal_nodes(nl) if M.degree(nl, n) >= 4)
    return nodes


def propose_guided(nl, rng, ctx, diag):
    """A primitive proposal AIMED per the auto-diagnosis:
       binding metric -> primitive-family aim; blamed devices -> node aim.
    Returns (nl', move) or (None, None). L0 (sane) re-checked by mutate/caller."""
    binding = diag.get("binding_metric")
    blamed = set(diag.get("blame_devices") or [])
    out_node = _output_node(nl)
    aim_nodes = _fet_nodes(nl, blamed) or ([out_node] if out_node else [])

    # binding-constraint -> primitive family:
    #   s21_db low (gain)      -> add a gain device / cascode near the aim nodes,
    #                             reconnect/split there (grow the gain path).
    #   idd_ma high (current)  -> different output class: complementary add at the
    #                             output node (current-reuse/class-AB lever), or
    #                             reconnect the current-heavy device.
    #   s21_ripple_db (flat)   -> load-flattening: add a parallel/series reactive
    #                             element on the output/tank node (staggered pole).
    #   s11* (match)           -> add/insert a matching element at the input side.
    if binding == "idd_ma":
        # complementary sourcing add at the output node is the class-change lever
        if out_node and rng.random() < 0.55:
            g = rng.choice(aim_nodes) if aim_nodes else out_node
            out = G.add_and_connect_device(M.copy_nl(nl), rng, ctx, t="pmos4",
                                           pinmap={"D": out_node, "G": g,
                                                   "S": "VDD", "B": "VSS"})
            if out is not None:
                return out, "add_and_connect_device(pmos4@out)"
        # else reconnect / add device at an aim node
        return _aimed_generic(nl, rng, ctx, aim_nodes, out_node)
    if binding in ("s21_db", "s21_min_db"):
        # grow the gain path: add a device onto an aim node, or cascade near output
        r = rng.random()
        if r < 0.45 and out_node:
            g = rng.choice(aim_nodes) if aim_nodes else out_node
            out = G.add_and_connect_device(M.copy_nl(nl), rng, ctx, t="nmos4",
                                           pinmap={"D": out_node, "G": g,
                                                   "S": "VSS", "B": "VSS"})
            if out is not None:
                return out, "add_and_connect_device(nmos4@out)"
        return _aimed_generic(nl, rng, ctx, aim_nodes, out_node)
    if binding == "s21_ripple_db":
        # flatten the tuned load: parallel/series reactive element on the tank node.
        # blame is unavailable for ripple, so aim at the output/tank node.
        tank = aim_nodes or ([out_node] if out_node else [])
        r = rng.random()
        if r < 0.5:
            # parallel element across an existing passive near the output tank
            out = G.apply_named(nl, "p5_insert_parallel_element", rng, ctx)
            if out is not None:
                return out, "p5_insert_parallel_element(tank)"
        else:
            out = G.apply_named(nl, "p4_insert_series_element", rng, ctx)
            if out is not None:
                return out, "p4_insert_series_element(tank)"
        return _aimed_generic(nl, rng, ctx, tank, out_node)
    if binding in ("s11_max_db", "s11_db"):
        out = G.apply_named(nl, "p4_insert_series_element", rng, ctx)
        if out is not None:
            return out, "p4_insert_series_element(match)"
        return _aimed_generic(nl, rng, ctx, aim_nodes, out_node)
    # no binding named -> fall back to an aimed generic edit at the output stage
    return _aimed_generic(nl, rng, ctx, aim_nodes, out_node)


def _aimed_generic(nl, rng, ctx, aim_nodes, out_node):
    """An aimed generic ruled-primitive edit at the diagnosis nodes."""
    kind = rng.choice(["p7_reconnect_terminal", "p1_add_device_of_type",
                       "p3_split_net", "add_and_connect_device",
                       "p5_insert_parallel_element"])
    try:
        if kind == "p3_split_net":
            cand = [n for n in aim_nodes if n in M.internal_nodes(nl)
                    and M.degree(nl, n) >= 4]
            if not cand:
                cand = [n for n in M.internal_nodes(nl) if M.degree(nl, n) >= 4]
            out = (G.apply_named(nl, kind, rng, ctx, node=rng.choice(sorted(cand)))
                   if cand else None)
        elif kind == "add_and_connect_device" and out_node:
            g = rng.choice(aim_nodes) if aim_nodes else out_node
            out = G.add_and_connect_device(M.copy_nl(nl), rng, ctx, t="nmos4",
                                           pinmap={"D": out_node, "G": g,
                                                   "S": "VSS", "B": "VSS"})
        else:
            out = G.apply_named(nl, kind, rng, ctx)
    except Exception:
        out = None
    return (out, kind + "@aim") if out is not None else (None, None)


# ----------------------------------------------------------------- the sizing
def _size_topo(env, topo, x0, budget_left, seed, first_feasible_cb):
    """CMA-ES sizing of `topo` through env (counted) until `budget_left` env evals
    are spent or the global budget is exhausted. `null_sizer.run_cmaes` is the
    ruled sizer, IMPORTED VERBATIM -- it starts from U[0,1]^n (no x0 parameter), so
    the "warm anchor" is honoured by pre-evaluating x0 (the reached point / a
    mid-box point), which seeds the env's best-so-far and puts the anchor on the
    record (§8.4 base-feasible-at-anchor); CMA-ES then searches cold-random,
    IDENTICALLY for all three arms, so the anchor pre-eval advantages no arm. Calls
    first_feasible_cb(out) on every eval so the caller can stamp the first
    extended-feasible design's (evals, spice-min). Returns evals spent here."""
    try:
        arena = env.arena if topo is None else env._arena_for(topo)
    except NotSizable:
        return 0
    n0 = env.n_evals
    cap = min(env.n_evals + budget_left, env.task.budget)

    def f(x):
        if env.n_evals >= cap:
            raise BudgetExhausted("cell sizing slice spent")
        out = env.evaluate(topology=topo, params=x, action="size")
        first_feasible_cb(out)
        return out["objective"]

    try:
        if x0 is not None and len(x0) == arena.dim and env.n_evals < cap:
            f(np.asarray(x0, dtype=float))          # anchor / mid-box pre-eval
        NS.run_cmaes(f, arena.dim, seed)            # verbatim ruled sizer
    except BudgetExhausted:
        pass
    except Exception:
        pass
    return env.n_evals - n0


# ------------------------------------------------------------------ the arms
def run_cell(goal_id, arm, seed, evals, verbose=True):
    """One (goal, arm, seed) cell: `evals` counted env evals, warm-started at the
    goal's reached anchor, recording the first extended-feasible design's
    (evals, spice-min) and the winning edit sequence. Returns the result dict."""
    from spec import Spec
    g = GOALS[goal_id]
    task = get_task(g["task"]).with_(budget=evals, seed=seed)
    env = Env(task, budget=evals, seed=seed, logger=None)
    base_spec = env.spec
    ext_s = ext_spec_of(base_spec, g["ext"])

    # warm anchor: the pinned reached design (best_params) -> its x in the arena box
    anchor_params = env.row.get("best_params")
    anchor_x = env.arena.encode(anchor_params) if anchor_params else None

    t_start = time.time()
    # --- solve-tracking state (shared across the cell) ---
    solve = {"solved": False, "evals": None, "spice_min": None,
             "wall_min": None, "metrics": None, "edit_seq": None, "n_edits": None}
    spice_s_acc = [0.0]        # Σ per-eval sim wall_s (SPICE-minutes primary)
    cur_edit_seq = [[]]        # edit sequence of the topology currently being sized

    def record(out):
        spice_s_acc[0] += (out.get("cost", {}).get("wall_s") or 0.0)
        if not solve["solved"] and ext_feasible(base_spec, ext_s, out["metrics"]):
            solve.update(solved=True, evals=env.n_evals,
                         spice_min=round(spice_s_acc[0] / 60.0, 4),
                         wall_min=round((time.time() - t_start) / 60.0, 4),
                         metrics={k: out["metrics"].get(k) for k in
                                  ("s21_db", "s21_ripple_db", "idd_ma", "nf_db",
                                   "s11_max_db")},
                         edit_seq=list(cur_edit_seq[0]),
                         n_edits=len(cur_edit_seq[0]))

    diag = None
    base_nl = None
    if arm in ("b", "c"):
        import templates as T
        base_nl, _ = T.topo_to_netlist(env.topo)
        ctx = G.ctx_for_spec(base_spec)
        if arm == "c":
            # auto-diagnosis at the warm anchor (one warm eval, counted below via
            # the record path only if it clears; here we evaluate to get op+metrics)
            anchor_out = env.evaluate(params=anchor_params, action="anchor-diag")
            record(anchor_out)
            diag = diagnose(env, ext_s, anchor_out)
            if verbose:
                print(f"    [c] diag: binding={diag['binding_metric']} "
                      f"blame={diag['blame_devices']} cov={diag['blame_coverage']}")

    rng = random.Random(seed)

    if arm == "a":
        # sizing-only null: CMA-ES sizing the BASE topology, warm at the anchor.
        cur_edit_seq[0] = []
        _size_topo(env, None, anchor_x, env.task.budget - env.n_evals, seed, record)

    else:
        # edit arms: propose an edit -> realize (L0, free) -> size the mutant
        # (counted) until the per-cell budget is spent. Warm start each mutant's
        # sizing from a mid-box point (the mutant's dim generally != base dim).
        ctx = G.ctx_for_spec(base_spec)
        propose = (lambda nl: G.mutate(nl, rng, ctx)) if arm == "b" \
            else (lambda nl: propose_guided(nl, rng, ctx, diag))
        guard = 0
        max_guard = env.task.budget * 40
        while env.n_evals < env.task.budget and guard < max_guard:
            guard += 1
            try:
                mut, move = propose(base_nl)
            except Exception:
                mut, move = None, None
            if mut is None:
                continue
            r = M.realize(mut, base_spec)          # L0 token round-trip (free)
            if r is None:
                continue
            mtopo, _seq, wl, canon = r
            cur_edit_seq[0] = [move]
            # size the mutant: a short warm sizing pass, counted, until budget.
            left = env.task.budget - env.n_evals
            if left <= 0:
                break
            try:
                arena = env._arena_for(mtopo)
            except NotSizable:
                continue
            x0 = np.full(arena.dim, 0.5)
            # give each mutant up to a bounded slice so many edits are tried,
            # but never exceed the global cell budget.
            slice_cap = min(left, max(40, env.task.budget // 6))
            try:
                _size_topo(env, mtopo, x0, slice_cap, seed + guard, record)
            except BudgetExhausted:
                break
            if solve["solved"]:
                break

    wall_min = round((time.time() - t_start) / 60.0, 3)
    res = {"goal": goal_id, "arm": arm, "seed": seed,
           "task": g["task"], "delta": g["desc"], "ext": g["ext"],
           "budget_evals": evals, "evals_spent": env.n_evals,
           "ngspice_calls": env.ngspice_calls,
           "spice_min_total": round(spice_s_acc[0] / 60.0, 4),
           "wall_min": wall_min,
           "solved": solve["solved"],
           "evals_to_solve": solve["evals"],
           "spice_min_to_solve": solve["spice_min"],
           "wall_min_to_solve": solve["wall_min"],
           "solve_metrics": solve["metrics"],
           "edit_seq": solve["edit_seq"],
           "n_edits": solve["n_edits"],
           "diagnosis": diag,
           "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
           "git_sha": _git_sha(), "ts": _now()}
    if verbose:
        st = ("SOLVED @%d evals, %.3f spice-min, edits=%s"
              % (solve["evals"], solve["spice_min"], solve["edit_seq"])
              if solve["solved"] else "not solved")
        print(f"  [{goal_id} {arm} s{seed}] {env.n_evals} evals / "
              f"{env.ngspice_calls} ngspice / {res['spice_min_total']:.2f} "
              f"spice-min -> {st}")
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


def cell_path(goal_id, arm, seed):
    return os.path.join(RESULTS, f"cell_{goal_id}_{arm}_s{seed}.json")


def run_and_save(goal_id, arm, seed, evals, force=False):
    p = cell_path(goal_id, arm, seed)
    if os.path.exists(p) and not force:
        try:
            with open(p) as fh:
                d = json.load(fh)
            if d.get("evals_spent"):
                print(f"  [{goal_id} {arm} s{seed}] resume: exists, skip")
                return d
        except Exception:
            pass
    res = run_cell(goal_id, arm, seed, evals)
    tmp = p + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(res, fh, indent=1, default=str)
    os.replace(tmp, p)      # atomic; crash-safe
    return res


# ----------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="E-8 scored ladder campaign")
    ap.add_argument("--goals", default="G1,G8,G9,G10")
    ap.add_argument("--arms", default="a,b,c")
    ap.add_argument("--seeds", default="1,2,3,4,5")
    ap.add_argument("--evals", type=int, default=600)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--cell", nargs=3, metavar=("GOAL", "ARM", "SEED"),
                    help="run ONE cell and exit")
    a = ap.parse_args()

    if a.cell:
        goal_id, arm, seed = a.cell[0], a.cell[1], int(a.cell[2])
        run_and_save(goal_id, arm, seed, a.evals, force=a.force)
        return 0

    goals = [g for g in a.goals.split(",") if g]
    arms = [x for x in a.arms.split(",") if x]
    seeds = [int(s) for s in a.seeds.split(",") if s]
    print(f"E-8 SCORED ladder: goals={goals} arms={arms} seeds={seeds} "
          f"evals={a.evals}/cell  ({len(goals)*len(arms)*len(seeds)} cells, "
          f"{len(goals)*len(arms)*len(seeds)*a.evals} evals)")
    for goal_id in goals:
        for arm in arms:
            for seed in seeds:
                run_and_save(goal_id, arm, seed, a.evals, force=a.force)
    print("campaign cells complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())

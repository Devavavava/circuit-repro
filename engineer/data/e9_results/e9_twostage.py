"""E-9 TWO-STAGE structural-experiment runner.

Binding pre-reg: engineer/E9-TWOSTAGE.md (committed d244fe6, BEFORE any scored
eval). Splits the budget by JOB:
  stage 1  cheap structural search: propose+screen k edit candidates, each at
           1 counted L1 eval (L0/realize = 0 sims), cull to top-m by objective.
  stage 2  each of the m survivors gets its OWN uninterrupted CMA-ES sizing run of
           (B-k)/m counted evals (the standard sizing path).
TOTAL counted evals per (goal,arm) = B, matched across arms (parity axis).

Arms: (a) sizing-only continued (== E-8 v2 arm a, baseline), (b) random two-stage,
(c) blame-guided two-stage.  N=3 seeds (G11'' N=2).  PYTHONHASHSEED=0.

Reuses E-8 v2 machinery verbatim where possible (ext_spec_of / ext_feasible /
diagnose / propose_guided / measure_iip3 / _size_topo).  CONTAINMENT: read-only
toward lna/ and engineer/ (write=False); writes ONLY per-cell JSON under
tmp/e9_results/.  No spec yaml edited.  Crash-safe: atomic per-cell JSON; the
aggregator reconstructs from cells alone.

    python e9_twostage.py --cell G2p b 1     # one cell, resume-safe
    python e9_twostage.py                     # whole campaign
"""
import argparse
import copy
import json
import os
import random
import sys
import time

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable] + sys.argv)

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.join(HERE, "wt-e9")
ENG = os.path.join(WT, "engineer")
LNA = os.path.join(WT, "lna")
for p in (ENG, LNA):
    if p not in sys.path:
        sys.path.insert(0, p)

import env as _env  # noqa: E402,F401
from env import Env, NotSizable, BudgetExhausted  # noqa: E402
import g2_moves as G  # noqa: E402
import moves as M  # noqa: E402
from moves import dname, fet_pins, is_fet  # noqa: E402
import null_sizer as NS  # noqa: E402
import blame as BL  # noqa: E402
import binding_probe as BP  # noqa: E402
import size as SZ  # noqa: E402

RESULTS = os.path.join(HERE, "e9_results")
os.makedirs(RESULTS, exist_ok=True)

# ---------------------------------------------------------------------- goals
# Definitions carried forward VERBATIM from E8-LADDER-V2 §Scored (the six
# survivors). Per E9-TWOSTAGE.md §2/§3.1: N=3 (G11'' N=2); k/m per goal.
GOALS = {
    "G2p": {"task": "dhruva-s-t2-a",
            "ext": {"s22_max_db": {"max": -10.0, "status": "measured"}},
            "desc": "s22_max_db <= -10 band-wide (dhruva-s); anchor -0.30",
            "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "match"},
    "G4p": {"task": "dhruva-l2-t2-a",
            "ext": {"s11_max_db": {"max": -14.5, "status": "measured"}},
            "desc": "s11_max_db <= -14.5 band-wide (dhruva-l2)",
            "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "match"},
    "G9": {"task": "dhruva-l5-t2-a",
           "ext": {"s21_ripple_db": {"max": 3.0, "status": "measured"}},
           "desc": "s21_ripple_db <= 3 (dhruva-l5); anchor 15.18",
           "B": 1200, "k": 200, "m": 5, "seeds": [1, 2, 3], "gtype": "band-shape"},
    "G1pp": {"task": "dhruva-l1-t2-a",
             "ext": {"s21_db": {"min": 33.0, "status": "measured"}},
             "desc": "s21_db >= 33 (dhruva-l1); anchor 26.32",
             "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "gain"},
    "G7pp": {"task": "dhruva-l5-t2-a",
             "ext": {"idd_ma": {"max": 9.0, "status": "measured"},
                     "s21_db": {"min": 22.3, "status": "measured"}},
             "desc": "idd_ma <= 9.0 @ s21 >= 22.3 (dhruva-l5); anchor 12.92",
             "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "current"},
    "G11pp": {"task": "dhruva-l5-t2-a",
              "ext": {"iip3_dbm": {"min": -7.4, "status": "measured"}},
              "iip3": True,
              "desc": "iip3_dbm >= -7.4 dBm TASK-LEVEL tier-3 (dhruva-l5); anchor -17.18",
              "B": 600, "k": 60, "m": 3, "seeds": [1, 2], "gtype": "linearity"},
}
ARMS = ("a", "b", "c")
IIP3_STRIDE = 25   # coarse-stride IIP3 probe on best-so-far (bounded tier-3 cost)


# ----------------------------------------------- extended-spec feasibility (== v2)
def ext_spec_of(base_spec, ext):
    s = copy.deepcopy(base_spec)
    s.constraints = dict(base_spec.constraints)
    for k, v in ext.items():
        s.constraints[k] = dict(v)
    return s


def ext_feasible(base_spec, ext_s, metrics):
    if metrics is None:
        return False
    base_ok, _ = base_spec.feasible(metrics)
    if not base_ok:
        return False
    ok, _ = ext_s.feasible(metrics)
    return bool(ok)


# ------------------------------------------------------ auto-diagnosis (== v2)
def op_to_netlist_fet(op_name):
    n = op_name
    if n.startswith("m") and len(n) > 1:
        n = n[1:]
    up = n.upper()
    return up if up.startswith("NM") or up.startswith("MP") else None


_NG = {"n": 0, "orig": None}


def _install_ng_counter():
    try:
        import extract as EX
        if _NG["orig"] is None and hasattr(EX, "run_and_extract"):
            _NG["orig"] = EX.run_and_extract

            def wrapped(*a, **k):
                _NG["n"] += 1
                return _NG["orig"](*a, **k)
            EX.run_and_extract = wrapped
    except Exception:
        pass


def _ng_count():
    return _NG["n"]


def diagnose(env, ext_s, anchor_out):
    m = anchor_out["metrics"]
    probe = BP.probe_design(ext_s, m, env.task.wl_hash, write=False)
    binding = (probe["single_relaxations"][0]["metric"]
               if probe["single_relaxations"] else None)
    op = env.op_sink.recent[-1]["op"] if env.op_sink.recent else {}
    body = env.arena.body
    params = env.arena.decode(anchor_out["x"])
    ng_before = _ng_count()
    blame_rows = BL.blame_design(body, params, ext_s, op, env.task.wl_hash, m,
                                 write=False, failing_only=True)
    blame_extra = max(0, _ng_count() - ng_before)
    blame_devs, blame_cov = [], "unavailable"
    for r in blame_rows:
        if r["metric"] == binding and r["blame"]:
            blame_devs = [op_to_netlist_fet(b["device"]) for b in r["blame"]]
            blame_devs = [d for d in blame_devs if d]
            blame_cov = r["coverage"]
            break
    if blame_cov == "unavailable":
        for r in blame_rows:
            if r["metric"] == binding:
                blame_cov = r.get("coverage", "unavailable")
                break
    return ({"binding_metric": binding, "verdict": probe["verdict"],
             "blame_devices": blame_devs, "blame_coverage": blame_cov,
             "n_failing": probe["n_failing"]}, blame_extra)


# ------------------------------------------------------ guided proposals (== v2)
def _output_node(nl):
    coup, out_node = M.output_coupler(nl)
    return out_node


def _fet_nodes(nl, fet_names):
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
    binding = diag.get("binding_metric")
    blamed = set(diag.get("blame_devices") or [])
    out_node = _output_node(nl)
    aim_nodes = _fet_nodes(nl, blamed) or ([out_node] if out_node else [])

    if binding == "idd_ma":
        if out_node and rng.random() < 0.55:
            g = rng.choice(aim_nodes) if aim_nodes else out_node
            out = G.add_and_connect_device(M.copy_nl(nl), rng, ctx, t="pmos4",
                                           pinmap={"D": out_node, "G": g,
                                                   "S": "VDD", "B": "VSS"})
            if out is not None:
                return out, "add_and_connect_device(pmos4@out)"
        return _aimed_generic(nl, rng, ctx, aim_nodes, out_node)
    if binding in ("s21_db", "s21_min_db"):
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
        tank = aim_nodes or ([out_node] if out_node else [])
        r = rng.random()
        if r < 0.5:
            out = G.apply_named(nl, "p5_insert_parallel_element", rng, ctx)
            if out is not None:
                return out, "p5_insert_parallel_element(tank)"
        else:
            out = G.apply_named(nl, "p4_insert_series_element", rng, ctx)
            if out is not None:
                return out, "p4_insert_series_element(tank)"
        return _aimed_generic(nl, rng, ctx, tank, out_node)
    if binding in ("s11_max_db", "s11_db", "s22_max_db", "s22_db"):
        out = G.apply_named(nl, "p4_insert_series_element", rng, ctx)
        if out is not None:
            return out, "p4_insert_series_element(match)"
        return _aimed_generic(nl, rng, ctx, aim_nodes, out_node)
    if binding == "iip3_dbm":
        r = rng.random()
        if r < 0.5 and out_node:
            g = rng.choice(aim_nodes) if aim_nodes else out_node
            out = G.add_and_connect_device(M.copy_nl(nl), rng, ctx, t="nmos4",
                                           pinmap={"D": out_node, "G": g,
                                                   "S": "VSS", "B": "VSS"})
            if out is not None:
                return out, "add_and_connect_device(nmos4@out.lin)"
        return _aimed_generic(nl, rng, ctx, aim_nodes, out_node)
    return _aimed_generic(nl, rng, ctx, aim_nodes, out_node)


def _aimed_generic(nl, rng, ctx, aim_nodes, out_node):
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


# --------------------------------------------------------- sizing path (== v2)
def _size_topo(env, topo, x0, budget_left, seed, first_feasible_cb):
    """One CMA-ES sizing slice of up to budget_left counted evals on `topo`
    (None = anchor topology). Standard sizing path (null_sizer.run_cmaes)."""
    try:
        arena = env.arena if topo is None else env._arena_for(topo)
    except NotSizable:
        return 0
    n0 = env.n_evals
    cap = min(env.n_evals + budget_left, env.task.budget)

    def f(x):
        if env.n_evals >= cap:
            raise BudgetExhausted("stage-2 sizing slice spent")
        out = env.evaluate(topology=topo, params=x, action="size")
        first_feasible_cb(out)
        return out["objective"]

    try:
        if x0 is not None and len(x0) == arena.dim and env.n_evals < cap:
            f(np.asarray(x0, dtype=float))
        NS.run_cmaes(f, arena.dim, seed)
    except BudgetExhausted:
        pass
    except Exception:
        pass
    return env.n_evals - n0


# ----------------------------------------------------------------- the cell
def run_cell(goal_id, arm, seed, verbose=True):
    g = GOALS[goal_id]
    B, k, m = g["B"], g["k"], g["m"]
    is_iip3 = g.get("iip3", False)
    task = get_task(g["task"]).with_(budget=B, seed=seed)
    env = Env(task, budget=B, seed=seed, logger=None)
    base_spec = env.spec
    ext_s = ext_spec_of(base_spec, g["ext"])

    anchor_params = env.row.get("best_params")
    anchor_x = env.arena.encode(anchor_params) if anchor_params else None

    t_start = time.time()
    solve = {"solved": False, "evals": None, "spice_min": None,
             "wall_min": None, "metrics": None, "edit_seq": None, "n_edits": None,
             "stage": None}
    spice_s_acc = [0.0]
    # per-stage spend breakdown
    stage_spend = {"s1_evals": 0, "s1_spice_s": 0.0,
                   "s2_evals": 0, "s2_spice_s": 0.0}
    cur_stage = ["s2"]           # arm a is all "s2"-equivalent sizing
    cur_edit_seq = [[]]
    iip3_extra_s = [0.0]
    n_iip3_probes = [0]

    # IIP3 tier-3 plumbing (G11'')
    body_iip3 = [None]
    if is_iip3:
        prep = SZ.prepared_body(env.topo, inductor_q=12)
        body_iip3[0] = prep[0] if prep else None

    def measure_iip3(params):
        if body_iip3[0] is None:
            return None
        tt = time.time()
        r = SZ.measure_iip3_tier3(body_iip3[0], params, ext_s, verbose=False)
        iip3_extra_s[0] += time.time() - tt
        n_iip3_probes[0] += 1
        if r and r.get("ok"):
            return r.get("iip3_dbm")
        return None

    best = {"f": float("inf"), "x": None}
    next_probe = [IIP3_STRIDE]

    def record(out):
        w = (out.get("cost", {}).get("wall_s") or 0.0)
        spice_s_acc[0] += w
        if cur_stage[0] == "s1":
            stage_spend["s1_evals"] += 1
            stage_spend["s1_spice_s"] += w
        else:
            stage_spend["s2_evals"] += 1
            stage_spend["s2_spice_s"] += w
        if is_iip3:
            if out["objective"] < best["f"]:
                best["f"] = out["objective"]
                best["x"] = list(out["x"])
            if (not solve["solved"] and cur_stage[0] == "s2"
                    and env.n_evals >= next_probe[0]):
                next_probe[0] += IIP3_STRIDE
                bp = env.arena.decode(np.asarray(best["x"], dtype=float))
                base_ok, _ = base_spec.feasible(out["metrics"])
                ii = measure_iip3(bp)
                if base_ok and ii is not None and ii >= -7.4:
                    solve.update(solved=True, evals=env.n_evals,
                                 spice_min=round(spice_s_acc[0] / 60.0, 4),
                                 wall_min=round((time.time() - t_start) / 60.0, 4),
                                 metrics={"iip3_dbm": ii},
                                 edit_seq=list(cur_edit_seq[0]),
                                 n_edits=len(cur_edit_seq[0]),
                                 stage=cur_stage[0])
            return
        if not solve["solved"] and ext_feasible(base_spec, ext_s, out["metrics"]):
            solve.update(solved=True, evals=env.n_evals,
                         spice_min=round(spice_s_acc[0] / 60.0, 4),
                         wall_min=round((time.time() - t_start) / 60.0, 4),
                         metrics={kk: out["metrics"].get(kk) for kk in
                                  ("s21_db", "s21_ripple_db", "idd_ma", "nf_db",
                                   "s11_max_db", "s22_max_db")},
                         edit_seq=list(cur_edit_seq[0]),
                         n_edits=len(cur_edit_seq[0]),
                         stage=cur_stage[0])

    diag = None
    blame_extra = 0
    base_nl = None
    survivors_info = []

    # ============================================================= ARM A
    if arm == "a":
        cur_stage[0] = "s2"
        cur_edit_seq[0] = []
        _size_topo(env, None, anchor_x, env.task.budget - env.n_evals, seed, record)

    # ============================================================= ARM B / C
    else:
        import templates as T
        base_nl, _ = T.topo_to_netlist(env.topo)
        ctx = G.ctx_for_spec(base_spec)
        if arm == "c":
            cur_stage[0] = "s1"       # anchor diag is part of stage-1 setup
            anchor_out = env.evaluate(params=anchor_params, action="anchor-diag")
            record(anchor_out)
            if is_iip3:
                ai = measure_iip3(anchor_params)
                anchor_out["metrics"] = dict(anchor_out["metrics"])
                anchor_out["metrics"]["iip3_dbm"] = ai
            diag, blame_extra = diagnose(env, ext_s, anchor_out)
            if verbose:
                print(f"    [c] diag: binding={diag['binding_metric']} "
                      f"blame={diag['blame_devices']} cov={diag['blame_coverage']} "
                      f"extra_sims={blame_extra}")

        rng = random.Random(seed)
        propose = (lambda nl: G.mutate(nl, rng, ctx)) if arm == "b" \
            else (lambda nl: propose_guided(nl, rng, ctx, diag))

        # ---------------- STAGE 1: screen k candidates, cull to top-m ----------
        # Bound proposal ATTEMPTS (not just L1 evals): the aimed edit families are
        # narrow (~50-60 distinct topologies), so requiring exactly k UNIQUE
        # candidates would spin forever on duplicates. We attempt up to
        # max_guard proposals and stop early on a long stall (no NEW unique
        # candidate for stall_lim consecutive attempts). Any stage-1 budget left
        # unspent (fewer unique candidates than k) ROLLS INTO stage-2 -- the
        # matched TOTAL budget B is preserved by stage-2 using the full remainder.
        cur_stage[0] = "s1"
        s1_cap = min(k, env.task.budget)   # counted evals reserved for screening
        candidates = []       # list of dicts: {topo, wl, move, obj, metrics, x}
        seen_wl = set()
        guard = 0
        max_guard = max(600, s1_cap * 10)
        stall = 0
        stall_lim = max(400, s1_cap * 6)
        while (stage_spend["s1_evals"] < s1_cap and env.n_evals < env.task.budget
               and guard < max_guard and stall < stall_lim):
            guard += 1
            try:
                mut, move = propose(base_nl)
            except Exception:
                mut, move = None, None
            if mut is None:
                continue
            r = M.realize(mut, base_spec)        # L0: 0 sims
            if r is None:
                continue
            mtopo, _seq, wl, canon = r
            if wl in seen_wl:
                stall += 1
                continue
            seen_wl.add(wl)
            stall = 0
            try:
                arena = env._arena_for(mtopo)
            except NotSizable:
                continue
            if env.n_evals >= env.task.budget:
                break
            # L1: exactly ONE counted eval (DC operating point + metrics @ x0=0.5)
            x0 = np.full(arena.dim, 0.5)
            cur_edit_seq[0] = [move]
            try:
                out = env.evaluate(topology=mtopo, params=x0, action="l1-screen")
            except BudgetExhausted:
                break
            record(out)
            candidates.append({"topo": mtopo, "wl": wl, "move": move,
                               "obj": float(out["objective"]),
                               "dim": arena.dim})
            if solve["solved"]:   # L1 already feasible (rare) -> done
                break

        # cull to top-m by L1 objective (lower = closer to feasible)
        candidates.sort(key=lambda c: c["obj"])
        survivors = candidates[:m]
        survivors_info = [{"wl": c["wl"], "move": c["move"],
                           "s1_obj": round(c["obj"], 5)} for c in survivors]

        # ---------------- STAGE 2: full per-survivor sizing --------------------
        cur_stage[0] = "s2"
        if survivors and not solve["solved"]:
            remaining = env.task.budget - env.n_evals
            per = max(1, remaining // len(survivors))
            for i, c in enumerate(survivors):
                if solve["solved"] or env.n_evals >= env.task.budget:
                    break
                cur_edit_seq[0] = [c["move"]]
                # last survivor mops up any remainder so total spend == B
                budget_left = (env.task.budget - env.n_evals
                               if i == len(survivors) - 1 else per)
                if budget_left <= 0:
                    break
                x0 = np.full(c["dim"], 0.5)
                try:
                    _size_topo(env, c["topo"], x0, budget_left, seed + 100 + i,
                               record)
                except BudgetExhausted:
                    break

    wall_min = round((time.time() - t_start) / 60.0, 3)
    res = {"goal": goal_id, "arm": arm, "seed": seed,
           "task": g["task"], "delta": g["desc"], "ext": g["ext"],
           "gtype": g.get("gtype"),
           "B": B, "k": k, "m": m,
           "budget_evals": B, "evals_spent": env.n_evals,
           "ngspice_calls": env.ngspice_calls,
           "spice_min_total": round(spice_s_acc[0] / 60.0, 4),
           "stage1_evals": stage_spend["s1_evals"],
           "stage1_spice_min": round(stage_spend["s1_spice_s"] / 60.0, 4),
           "stage2_evals": stage_spend["s2_evals"],
           "stage2_spice_min": round(stage_spend["s2_spice_s"] / 60.0, 4),
           "n_candidates_screened": len(survivors_info) if arm == "a" else None,
           "survivors": survivors_info,
           "blame_extra_sims": blame_extra,
           "iip3_extra_sim_s": round(iip3_extra_s[0], 2),
           "n_iip3_probes": n_iip3_probes[0],
           "wall_min": wall_min,
           "solved": solve["solved"],
           "solved_stage": solve["stage"],
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
        st = ("SOLVED @%s evals (%s), %s spice-min, edits=%s"
              % (solve["evals"], solve["stage"], solve["spice_min"],
                 solve["edit_seq"])
              if solve["solved"] else "not solved")
        print(f"  [{goal_id} {arm} s{seed}] {env.n_evals} evals "
              f"(s1={stage_spend['s1_evals']} s2={stage_spend['s2_evals']}) / "
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


def run_and_save(goal_id, arm, seed, force=False):
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
    _install_ng_counter()
    res = run_cell(goal_id, arm, seed)
    tmp = p + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(res, fh, indent=1, default=str)
    os.replace(tmp, p)
    return res


# ----------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="E-9 two-stage experiment")
    ap.add_argument("--goals", default="G2p,G4p,G9,G1pp,G7pp,G11pp")
    ap.add_argument("--arms", default="a,b,c")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--cell", nargs=3, metavar=("GOAL", "ARM", "SEED"),
                    help="run ONE cell and exit")
    a = ap.parse_args()

    if a.cell:
        goal_id, arm, seed = a.cell[0], a.cell[1], int(a.cell[2])
        run_and_save(goal_id, arm, seed, force=a.force)
        return 0

    goals = [g for g in a.goals.split(",") if g]
    arms = [x for x in a.arms.split(",") if x]
    for goal_id in goals:
        for arm in arms:
            for seed in GOALS[goal_id]["seeds"]:
                run_and_save(goal_id, arm, seed, force=a.force)
    print("campaign cells complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())

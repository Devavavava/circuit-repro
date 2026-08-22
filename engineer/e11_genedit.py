"""E-11 GENERATOR-AS-EDITOR two-stage runner.

Binding pre-reg: engineer/E11-GENEDIT.md (committed BEFORE any counted scoring).

Same two-stage / matched-TOTAL-budget mechanics as E-9 (engineer/e9_twostage.py):
  stage 1  cheap structural search: propose+screen k candidates, each at 1 counted
           L1 eval (L0/realize = 0 sims), cull to top-m by L1 objective.
  stage 2  each of m survivors gets its own uninterrupted CMA-ES sizing run of
           (B-k)/m counted evals (standard sizing path).
TOTAL counted evals per (goal,arm,seed) = B, matched across arms.

Arms:
  A  sizing-only  (== E-9 arm A; the null filter AT scored budget).
  B  primitive-edit two-stage  (== E-9 arm B: random generic primitive edits from
     the E-7 repertoire, g2_moves.mutate).
  C  generator-as-editor two-stage: proposals come from regrowing a segment of the
     parent's Eulerian token sequence with the adopted checkpoint ft_p5v7_v2.pth
     (engineer/e11_regrow.py). Same k/m/budget as B.

EDIT LOG (first-class deliverable): append-only JSONL
engineer/data/edit_log/e11_edits.jsonl -- one row per PROPOSAL (arms B and C,
including decode/screen failures). Schema in the pre-reg.

CONTAINMENT: read-only toward lna/ and engineer/ (write=False); writes ONLY per-cell
JSON under tmp/e11_results/ and appends to the edit log. No spec yaml edited.
Crash-safe: atomic per-cell JSON; aggregator reconstructs from cells alone.

    python e11_genedit.py --cell GA a 1     # one cell, resume-safe
    python e11_genedit.py                    # whole campaign
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
WT = os.path.dirname(HERE)
LNA = os.path.join(WT, "lna")
for p in (HERE, LNA):
    if p not in sys.path:
        sys.path.insert(0, p)

from env import Env, NotSizable, BudgetExhausted  # noqa: E402
import g2_moves as G  # noqa: E402
import moves as M  # noqa: E402
import null_sizer as NS  # noqa: E402
import e11_regrow as RG  # noqa: E402

RESULTS = os.path.join("/home/dpatni/.claude/jobs/a8f610e5/tmp", "e11_results")
os.makedirs(RESULTS, exist_ok=True)
EDIT_LOG_DIR = os.path.join(HERE, "data", "edit_log")
os.makedirs(EDIT_LOG_DIR, exist_ok=True)
EDIT_LOG = os.path.join(EDIT_LOG_DIR, "e11_edits.jsonl")

# ---------------------------------------------------------------------- goals
# KEEPS: cited to E-10 amendment (A.4). Reachability PROVEN in store (existence
# proof only; arms start COLD from the task's standard start -- never warm-start).
# FRESH: authored by store arithmetic (contamination ledger in the pre-reg): new
# limit = best-in-store base-feasible single-point value, tightened by ~1.5x the
# E-10 near-miss threshold (S11/gain 2.0->3.0 dB, NF 0.5->0.75 dB).
GOALS = {
    # ---- keeps (B=600 / 1200, N=3) ----
    "G1pp": {"task": "dhruva-l1-t2-a",
             "ext": {"s21_db": {"min": 33.0, "status": "measured"}},
             "desc": "s21_db >= 33 (dhruva-l1); store wl ace8383c passes (37.53)",
             "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "gain",
             "kind": "keep"},
    "G9": {"task": "dhruva-l5-t2-a",
           "ext": {"s21_ripple_db": {"max": 3.0, "status": "measured"}},
           "desc": "s21_ripple_db <= 3 (dhruva-l5); store wl 439032fd passes (2.989)",
           "B": 1200, "k": 200, "m": 5, "seeds": [1, 2, 3], "gtype": "band-shape",
           "kind": "keep"},
    "G7pp": {"task": "dhruva-l5-t2-a",
             "ext": {"idd_ma": {"max": 9.0, "status": "measured"},
                     "s21_db": {"min": 22.3, "status": "measured"}},
             "desc": "idd_ma <= 9.0 @ s21 >= 22.3 (dhruva-l5); store wl 998ff3a1 "
                     "fails only s11 by 0.74 dB",
             "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "current",
             "kind": "keep"},
    # ---- fresh (B=600, N=3) ----
    # Placement rule: new limit = best-in-store BASE-FEASIBLE single point,
    # tightened by 1.5x the E-10 near-miss threshold (NF 0.75, S11/gain 3.0 dB).
    # All three KEPT after the Arm-A-at-B=600 null-filter pre-check (§2.4): sizing
    # the cold-start anchor leaves each unsolved. 3 distinct bands (S/L1/L2),
    # 3 distinct metric families (NF / S11 / gain-at-edge), none duplicating a
    # keep's binding metric.
    # GA: NF tightening. dhruva-s best-in-store base-feasible NF = 1.288 dB;
    # -> <= 0.538 dB. (band: S, 18 dev.) Arm-A null-filter best 2.719 (unsolved).
    "GA": {"task": "dhruva-s-t2-a",
           "ext": {"nf_db": {"max": 0.538, "status": "measured"}},
           "desc": "nf_db <= 0.538 (dhruva-s); placement: best-in-store 1.288 - 0.75",
           "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "nf",
           "kind": "fresh"},
    # GB: S11 tightening. dhruva-l1 best-in-store base-feasible s11_max = -10.019 dB;
    # -> <= -13.019 dB. (band: L1, 18 dev.) Arm-A null-filter best -10.019 (unsolved).
    "GB": {"task": "dhruva-l1-t2-a",
           "ext": {"s11_max_db": {"max": -13.019, "status": "measured"}},
           "desc": "s11_max_db <= -13.019 (dhruva-l1); placement: best-in-store "
                   "-10.019 - 3.0",
           "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "match",
           "kind": "fresh"},
    # GC: gain-at-band-edge (s21_min_db, distinct from keeps' mid-band s21_db).
    # dhruva-l2 best-in-store base-feasible s21_min_db = 34.926 dB; -> >= 37.926 dB.
    # (band: L2, 18 dev.) Arm-A null-filter best 22.328 (unsolved).
    "GC": {"task": "dhruva-l2-t2-a",
           "ext": {"s21_min_db": {"min": 37.926, "status": "measured"}},
           "desc": "s21_min_db >= 37.926 (dhruva-l2); placement: best-in-store "
                   "34.926 + 3.0",
           "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "gain-edge",
           "kind": "fresh"},
}
ARMS = ("a", "b", "c")
ERA = "e11-p5v7_v2"

# regrow knobs (generic only): cut fraction range, temperature, length cap
REGROW_TEMP = 1.0
REGROW_CUT_MIN = 0.10
REGROW_CUT_MAX = 0.90
REGROW_MAXNEW = 256


# ----------------------------------------------- extended-spec feasibility (== E-9)
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


# --------------------------------------------------------- sizing path (== E-9)
def _size_topo(env, topo, x0, budget_left, seed, first_feasible_cb):
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


# ------------------------------------------------------------- edit-log writer
_EDIT_BUF = []


def edit_row(**kw):
    kw.setdefault("ts", _now())
    kw.setdefault("campaign", "e11")
    kw.setdefault("era", ERA)
    _EDIT_BUF.append(kw)


def flush_edit_log():
    if not _EDIT_BUF:
        return 0
    n = len(_EDIT_BUF)
    with open(EDIT_LOG, "a") as fh:
        for r in _EDIT_BUF:
            fh.write(json.dumps(r, default=str) + "\n")
    _EDIT_BUF.clear()
    return n


# ----------------------------------------------------------------- the cell
def run_cell(goal_id, arm, seed, verbose=True):
    g = GOALS[goal_id]
    B, k, m = g["B"], g["k"], g["m"]
    task = get_task(g["task"]).with_(budget=B, seed=seed)
    env = Env(task, budget=B, seed=seed, logger=None)
    base_spec = env.spec
    ext_s = ext_spec_of(base_spec, g["ext"])

    anchor_params = env.row.get("best_params")
    anchor_x = env.arena.encode(anchor_params) if anchor_params else None

    t_start = time.time()
    gen_s_acc = [0.0]         # generation wall-time (arm C), reported separately
    solve = {"solved": False, "evals": None, "spice_min": None,
             "wall_min": None, "metrics": None, "edit_seq": None, "stage": None}
    spice_s_acc = [0.0]
    stage_spend = {"s1_evals": 0, "s1_spice_s": 0.0,
                   "s2_evals": 0, "s2_spice_s": 0.0}
    cur_stage = ["s2"]
    cur_edit_seq = [[]]

    def record(out):
        w = (out.get("cost", {}).get("wall_s") or 0.0)
        spice_s_acc[0] += w
        if cur_stage[0] == "s1":
            stage_spend["s1_evals"] += 1
            stage_spend["s1_spice_s"] += w
        else:
            stage_spend["s2_evals"] += 1
            stage_spend["s2_spice_s"] += w
        if not solve["solved"] and ext_feasible(base_spec, ext_s, out["metrics"]):
            solve.update(solved=True, evals=env.n_evals,
                         spice_min=round(spice_s_acc[0] / 60.0, 4),
                         wall_min=round((time.time() - t_start) / 60.0, 4),
                         metrics={kk: out["metrics"].get(kk) for kk in
                                  ("s21_db", "s21_min_db", "s21_ripple_db",
                                   "idd_ma", "nf_db", "s11_max_db")},
                         edit_seq=list(cur_edit_seq[0]),
                         stage=cur_stage[0])

    survivors_info = []
    n_props_logged = [0]

    # ============================================================= ARM A
    if arm == "a":
        cur_stage[0] = "s2"
        cur_edit_seq[0] = []
        _size_topo(env, None, anchor_x, env.task.budget - env.n_evals, seed, record)

    # ============================================================= ARM B / C
    else:
        import templates as T
        base_nl, _ = T.topo_to_netlist(env.topo)
        parent_toks = list(env.topo.tokens)
        parent_wl = env.task.wl_hash
        ctx = G.ctx_for_spec(base_spec)
        cls = "nb" if env.topo.n_inductors >= 1 else "wb"

        model = stoi = None
        if arm == "c":
            model, stoi = RG.load_model("cpu")

        rng = random.Random(seed)

        # ---------------- STAGE 1: screen k candidates, cull to top-m ----------
        cur_stage[0] = "s1"
        s1_cap = min(k, env.task.budget)
        candidates = []
        seen_wl = set()
        guard = 0
        # arm C generation is ~100x a primitive edit and the distinct-child pool
        # per parent is small (smoke: 17-44). A high duplicate-stall bound would
        # spin the generator uselessly, so arm C stalls far sooner (in duplicate
        # PROPOSALS, not generation batches). Unspent stage-1 rolls into stage-2
        # (E-9 D1); matched TOTAL budget B is preserved. Arm B keeps E-9's bound.
        max_guard = max(600, s1_cap * 10)
        stall = 0
        stall_lim = (max(60, s1_cap) if arm == "c" else max(400, s1_cap * 6))

        def screen_child(mtopo, wl, mech_str, parent_wl_used, l1_from_regrow=None):
            """L1-screen a realized child (1 counted eval). Logs an edit row."""
            try:
                arena = env._arena_for(mtopo)
            except NotSizable:
                edit_row(goal=goal_id, arm=arm, seed=seed,
                         parent_wl=parent_wl_used,
                         proposal_mechanism=mech_str, child_wl=wl,
                         decode_ok=True, l0_pass=True, l0_score=None,
                         l1_objective=None, survived_cull=False,
                         stage2_best_obj=None, stage2_solved=False,
                         note="not-sizable")
                return None
            if env.n_evals >= env.task.budget:
                return "budget"
            x0 = np.full(arena.dim, 0.5)
            cur_edit_seq[0] = [mech_str]
            try:
                out = env.evaluate(topology=mtopo, params=x0, action="l1-screen")
            except BudgetExhausted:
                return "budget"
            record(out)
            obj = float(out["objective"])
            candidates.append({"topo": mtopo, "wl": wl, "move": mech_str,
                               "obj": obj, "dim": arena.dim,
                               "parent_wl": parent_wl_used})
            edit_row(goal=goal_id, arm=arm, seed=seed, parent_wl=parent_wl_used,
                     proposal_mechanism=mech_str, child_wl=wl,
                     decode_ok=True, l0_pass=True, l0_score=None,
                     l1_objective=round(obj, 6), survived_cull=None,
                     stage2_best_obj=None, stage2_solved=False)
            n_props_logged[0] += 1
            return "ok"

        if arm == "b":
            while (stage_spend["s1_evals"] < s1_cap
                   and env.n_evals < env.task.budget
                   and guard < max_guard and stall < stall_lim):
                guard += 1
                try:
                    mut, move = G.mutate(base_nl, rng, ctx)
                except Exception:
                    mut, move = None, None
                if mut is None:
                    edit_row(goal=goal_id, arm=arm, seed=seed, parent_wl=parent_wl,
                             proposal_mechanism="primitive:none", child_wl=None,
                             decode_ok=False, l0_pass=False, l0_score=None,
                             l1_objective=None, survived_cull=False,
                             stage2_best_obj=None, stage2_solved=False,
                             note="propose-returned-none")
                    continue
                r = M.realize(mut, base_spec)
                if r is None:
                    edit_row(goal=goal_id, arm=arm, seed=seed, parent_wl=parent_wl,
                             proposal_mechanism="primitive:" + str(move),
                             child_wl=None, decode_ok=True, l0_pass=False,
                             l0_score=None, l1_objective=None, survived_cull=False,
                             stage2_best_obj=None, stage2_solved=False,
                             note="realize-failed")
                    continue
                mtopo, _seq, wl, _canon = r
                if wl in seen_wl:
                    stall += 1
                    continue
                seen_wl.add(wl)
                stall = 0
                st = screen_child(mtopo, wl, "primitive:" + str(move), parent_wl)
                if st == "budget":
                    break
                if solve["solved"]:
                    break

        else:  # arm == "c": generator regrow
            # regrow in batches of cut points; each batch is one generation call.
            # Generation is CPU token-sampling (~100x a primitive edit) and the
            # distinct-child pool per parent is small (smoke: 17-44), so stage-1 is
            # bounded by a GENERATION-BATCH cap and a wall-clock cap in ADDITION to
            # the eval/guard/stall bounds -- otherwise stage-1 spins generating
            # duplicates. Unspent stage-1 rolls into stage-2 (E-9 D1); matched
            # TOTAL budget B is preserved. These caps are generic (not per-goal).
            batch = 16
            gen_batch_cap = 20          # hard ceiling on generation calls: 20*16=
            #                             320 proposals harvests the full distinct-
            #                             child pool (smoke: 17-44 per parent) while
            #                             bounding gen wall-time. k=120 is a screen
            #                             CEILING; the distinct pool is the real cap.
            gen_wall_cap_s = 480        # <= 8 min generation per stage-1 cell
            empty_batch_lim = 4         # stop after 4 consecutive batches with no
            #                             NEW distinct valid child (the distinct-
            #                             child pool per parent is small, ~17-44;
            #                             once it is exhausted, generating more is
            #                             wasted CPU). Unspent stage-1 -> stage-2.
            n_gen_batches = 0
            empty_batches = 0
            t_stage1 = time.time()
            while (stage_spend["s1_evals"] < s1_cap
                   and env.n_evals < env.task.budget
                   and n_gen_batches < gen_batch_cap
                   and empty_batches < empty_batch_lim
                   and (time.time() - t_stage1) < gen_wall_cap_s):
                n_gen_batches += 1
                n_screened_before = stage_spend["s1_evals"]
                cuts = RG._cut_points(len(parent_toks), rng, batch,
                                      min_frac=REGROW_CUT_MIN,
                                      max_frac=REGROW_CUT_MAX)
                tgen = time.time()
                props = RG.regrow_batch(parent_toks, cls, cuts, REGROW_TEMP,
                                        model, stoi, max_new_tokens=REGROW_MAXNEW,
                                        device="cpu")
                gen_s_acc[0] += time.time() - tgen
                guard += len(props)
                for p in props:
                    if (stage_spend["s1_evals"] >= s1_cap
                            or env.n_evals >= env.task.budget
                            or stall >= stall_lim):
                        break
                    mech = ("regrow:{cut_index:%d,cut_frac:%.4f,temperature:%.2f,"
                            "n_new_tokens:%d}" % (p["cut_index"], p["cut_frac"],
                                                  p["temperature"], p["n_new_tokens"]))
                    if not p["decode_ok"] or not p["completed_toks"]:
                        edit_row(goal=goal_id, arm=arm, seed=seed,
                                 parent_wl=parent_wl, proposal_mechanism=mech,
                                 child_wl=None, decode_ok=False, l0_pass=False,
                                 l0_score=None, l1_objective=None,
                                 survived_cull=False, stage2_best_obj=None,
                                 stage2_solved=False, note="no-truncate")
                        continue
                    topo = RG.decode_to_topo(p["completed_toks"])
                    if topo is None:
                        edit_row(goal=goal_id, arm=arm, seed=seed,
                                 parent_wl=parent_wl, proposal_mechanism=mech,
                                 child_wl=None, decode_ok=True, l0_pass=False,
                                 l0_score=None, l1_objective=None,
                                 survived_cull=False, stage2_best_obj=None,
                                 stage2_solved=False, note="topo-invalid")
                        continue
                    r = RG.realize_topo(topo, base_spec)
                    if r is None:
                        edit_row(goal=goal_id, arm=arm, seed=seed,
                                 parent_wl=parent_wl, proposal_mechanism=mech,
                                 child_wl=None, decode_ok=True, l0_pass=False,
                                 l0_score=None, l1_objective=None,
                                 survived_cull=False, stage2_best_obj=None,
                                 stage2_solved=False, note="realize/screen-failed")
                        continue
                    mtopo, _seq, wl, _canon = r
                    if wl in seen_wl:
                        stall += 1
                        # log duplicate as a decode-ok/L0-pass proposal (no L1)
                        edit_row(goal=goal_id, arm=arm, seed=seed,
                                 parent_wl=parent_wl, proposal_mechanism=mech,
                                 child_wl=wl, decode_ok=True, l0_pass=True,
                                 l0_score=None, l1_objective=None,
                                 survived_cull=False, stage2_best_obj=None,
                                 stage2_solved=False, note="duplicate-wl")
                        continue
                    seen_wl.add(wl)
                    stall = 0
                    st = screen_child(mtopo, wl, mech, parent_wl)
                    if st == "budget":
                        break
                    if solve["solved"]:
                        break
                # generation-aware stall: count consecutive batches that produced
                # no NEW screened (distinct valid) child
                if stage_spend["s1_evals"] == n_screened_before:
                    empty_batches += 1
                else:
                    empty_batches = 0
                if solve["solved"] or env.n_evals >= env.task.budget:
                    break

        # cull to top-m by L1 objective
        candidates.sort(key=lambda c: c["obj"])
        survivors = candidates[:m]
        surv_wls = {c["wl"] for c in survivors}
        survivors_info = [{"wl": c["wl"], "move": c["move"],
                           "s1_obj": round(c["obj"], 5),
                           "parent_wl": c["parent_wl"]} for c in survivors]
        # mark survived_cull in the edit buffer for the screened candidates
        for r in _EDIT_BUF:
            if (r.get("goal") == goal_id and r.get("arm") == arm
                    and r.get("seed") == seed
                    and r.get("l1_objective") is not None
                    and r.get("survived_cull") is None):
                r["survived_cull"] = r.get("child_wl") in surv_wls

        # ---------------- STAGE 2: full per-survivor sizing --------------------
        cur_stage[0] = "s2"
        if survivors and not solve["solved"]:
            per = max(1, (env.task.budget - env.n_evals) // len(survivors))
            for i, c in enumerate(survivors):
                if solve["solved"] or env.n_evals >= env.task.budget:
                    break
                cur_edit_seq[0] = [c["move"]]
                budget_left = (env.task.budget - env.n_evals
                               if i == len(survivors) - 1 else per)
                if budget_left <= 0:
                    break
                x0 = np.full(c["dim"], 0.5)
                best_before = env.best_f
                try:
                    _size_topo(env, c["topo"], x0, budget_left, seed + 100 + i,
                               record)
                except BudgetExhausted:
                    pass
                # update this survivor's edit rows with stage2 outcome
                s2_solved = bool(solve["solved"] and
                                 solve.get("edit_seq") == [c["move"]])
                for r in _EDIT_BUF:
                    if (r.get("goal") == goal_id and r.get("arm") == arm
                            and r.get("seed") == seed
                            and r.get("child_wl") == c["wl"]
                            and r.get("l1_objective") is not None):
                        r["stage2_best_obj"] = round(float(env.best_f), 6)
                        r["stage2_solved"] = s2_solved

    wall_min = round((time.time() - t_start) / 60.0, 3)
    res = {"goal": goal_id, "arm": arm, "seed": seed,
           "task": g["task"], "delta": g["desc"], "ext": g["ext"],
           "gtype": g.get("gtype"), "kind": g.get("kind"),
           "B": B, "k": k, "m": m,
           "budget_evals": B, "evals_spent": env.n_evals,
           "ngspice_calls": env.ngspice_calls,
           "spice_min_total": round(spice_s_acc[0] / 60.0, 4),
           "gen_min_total": round(gen_s_acc[0] / 60.0, 4),
           "stage1_evals": stage_spend["s1_evals"],
           "stage1_spice_min": round(stage_spend["s1_spice_s"] / 60.0, 4),
           "stage2_evals": stage_spend["s2_evals"],
           "stage2_spice_min": round(stage_spend["s2_spice_s"] / 60.0, 4),
           "n_proposals_logged": n_props_logged[0],
           "survivors": survivors_info,
           "wall_min": wall_min,
           "solved": solve["solved"],
           "solved_stage": solve["stage"],
           "evals_to_solve": solve["evals"],
           "spice_min_to_solve": solve["spice_min"],
           "wall_min_to_solve": solve["wall_min"],
           "solve_metrics": solve["metrics"],
           "edit_seq": solve["edit_seq"],
           "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
           "git_sha": _git_sha(), "ts": _now()}
    if verbose:
        st = ("SOLVED @%s evals (%s), %s spice-min, edit=%s"
              % (solve["evals"], solve["stage"], solve["spice_min"],
                 solve["edit_seq"])
              if solve["solved"] else "not solved")
        print(f"  [{goal_id} {arm} s{seed}] {env.n_evals} evals "
              f"(s1={stage_spend['s1_evals']} s2={stage_spend['s2_evals']}) / "
              f"{res['spice_min_total']:.2f} spice-min / "
              f"{res['gen_min_total']:.2f} gen-min -> {st}", flush=True)
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
    _EDIT_BUF.clear()
    res = run_cell(goal_id, arm, seed)
    n_edits = flush_edit_log()
    res["edit_log_rows_appended"] = n_edits
    tmp = p + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(res, fh, indent=1, default=str)
    os.replace(tmp, p)
    return res


def main():
    ap = argparse.ArgumentParser(description="E-11 generator-as-editor experiment")
    ap.add_argument("--goals", default="G1pp,G9,G7pp,GA,GB,GC")
    ap.add_argument("--arms", default="a,b,c")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--cell", nargs=3, metavar=("GOAL", "ARM", "SEED"))
    a = ap.parse_args()

    if a.cell:
        run_and_save(a.cell[0], a.cell[1], int(a.cell[2]), force=a.force)
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

"""E-11 SCORED CAMPAIGN runner -- generator-as-editor two-stage.

Binding pre-reg: engineer/E11-GENEDIT.md (FROZEN, user GO 2026-08-23). 54 cells
(6 goals x 3 arms x seeds 1-3), matched TOTAL budget B per cell (G9: B=1200).

Machinery held fixed from E-9 (engineer/data/e9_results/e9_twostage.py):
  arm A  sizing-only CMA-ES on the reached anchor (byte-identical to E-9 arm A).
  arm B  primitive two-stage (g2_moves.mutate uniform; == E-9 arm B).
  arm C  generator-as-editor two-stage -- stage-1 proposals ONLY from the v7
         cut-and-regrow (frozen constants; per-(goal,arm,seed) torch seed);
         gates identical to B: sane() L0 (0 sim) -> realize() (0 sim) -> 1 counted
         L1 eval per candidate; cull to top-m by L1 objective; stage-2 =
         per-survivor uninterrupted CMA-ES warm-started at the stage-1 point.

Stage split, k/m/B, and the D1 stall/rollover clause carried over from E-9 §3.1:
  B=600  -> k=120, m=4, 120 evals/survivor.   B=1200 -> k=200, m=5, 200/survivor.
Unspent stage-1 budget rolls into stage-2; TOTAL counted evals == B exactly.

EDIT LOGGING (binding ruling): EVERY proposal in arms B and C -- whatever gate it
dies at -- appends to engineer/data/e11_edit_log/edits.jsonl in the §3 schema.
Arm B uses move/args in place of regrown_*; token sequences are content-addressed
under seqs/<sha>.txt. Append-only; never truncated.

CONTAINMENT: read-only toward lna/ and engineer/ (imports only); the v7 checkpoint
is read from the main checkout read-only. Writes ONLY under
engineer/data/e11_results/ (atomic per-cell JSON), engineer/data/e11_edit_log/
(append-only), and a per-PID STATUS temp file. <= 8 concurrent ngspice via the
process-level fan-out (this runner is single-threaded per cell). PYTHONHASHSEED=0;
torch CPU-only.

    python e11_run.py --cell G2pp c 1     # one cell, resume-safe
    python e11_run.py --goal G1pp         # one goal, all arms/seeds
    python e11_run.py                      # whole campaign (serial)
"""
import argparse
import copy
import hashlib
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
ENG = HERE
LNA = os.path.abspath(os.path.join(HERE, "..", "lna"))
for p in (ENG, LNA):
    if p not in sys.path:
        sys.path.insert(0, p)

from env import Env, NotSizable, BudgetExhausted  # noqa: E402
import null_sizer as NS  # noqa: E402

RESULTS = os.path.join(HERE, "data", "e11_results")
EDIT_DIR = os.path.join(HERE, "data", "e11_edit_log")
SEQ_DIR = os.path.join(EDIT_DIR, "seqs")
EDITS_JSONL = os.path.join(EDIT_DIR, "edits.jsonl")
os.makedirs(RESULTS, exist_ok=True)
os.makedirs(SEQ_DIR, exist_ok=True)

# ---------------------------------------------------------------------- goals
# Base tasks + in-memory deltas from E11-GENEDIT §4. Anchors are the reached
# anchor topologies (env.topo / env.row best_params) -- the SAME anchors E-9
# used for these base tasks, NOT the store-best certificates (§4).
GOALS = {
    "G1pp": {"task": "dhruva-l1-t2-a",
             "ext": {"s21_db": {"min": 33.0, "status": "measured"}},
             "desc": "s21_db >= 33 (dhruva-l1)",
             "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "gain"},
    "G9": {"task": "dhruva-l5-t2-a",
           "ext": {"s21_ripple_db": {"max": 3.0, "status": "measured"}},
           "desc": "s21_ripple_db <= 3 (dhruva-l5)",
           "B": 1200, "k": 200, "m": 5, "seeds": [1, 2, 3], "gtype": "band-shape"},
    "G7pp": {"task": "dhruva-l5-t2-a",
             "ext": {"idd_ma": {"max": 9.0, "status": "measured"},
                     "s21_db": {"min": 22.3, "status": "measured"}},
             "desc": "idd_ma <= 9.0 @ s21 >= 22.3 (dhruva-l5)",
             "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "current"},
    "G2pp": {"task": "dhruva-s-t2-a",
             "ext": {"s22_max_db": {"max": -10.0, "status": "measured"}},
             "desc": "s22_max_db <= -10 band-wide (dhruva-s)",
             "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "match"},
    "G12": {"task": "dhruva-l5-t2-a",
            "ext": {"s11_max_db": {"max": -15.0, "status": "measured"}},
            "desc": "s11_max_db <= -15 band-wide (dhruva-l5)",
            "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "match"},
    "G13": {"task": "dhruva-l2-t2-a",
            "ext": {"nf_db": {"max": 1.45, "status": "measured"}},
            "desc": "nf_db <= 1.45 (dhruva-l2)",
            "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "noise"},
}
ARMS = ("a", "b", "c")

# narrowband vs wideband class token for arm-C conditioning (§10.3: dhruva-s is
# narrowband/3-inductor -> <LNA_NB>). Determined per base task by inductor count.
CAMPAIGN = "E-11"

# ---- FROZEN arm-C sampling constants (E11-GENEDIT §10.3, GO-frozen) ----------
CKPT = "/home/dpatni/circuit-repro/lna/out/ft_p5v7_v2.pth"   # main-adopted P5-v7
ARM_TAG = "p5"
TEMPERATURE = 0.7
MAX_NEW_TOKENS = 256
CONTAM = {"generator_checkpoint": "ft_p5v7_v2.pth (cross-line import, main-adopted)",
          "arm": ARM_TAG, "temperature": TEMPERATURE,
          "max_new_tokens": MAX_NEW_TOKENS,
          "cut_rule": "uniform over {0} U device-token positions (c=tokens kept)"}


# ------------------------------------------------ extended-spec feasibility (== E-9)
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


# ------------------------------------------------------- ngspice counter (== E-9)
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


# --------------------------------------------------------- sizing path (== E-9)
def _size_topo(env, topo, x0, budget_left, seed, first_feasible_cb):
    """One CMA-ES sizing slice of up to budget_left counted evals on `topo`
    (None = anchor topology). Byte-identical to E-9 e9_twostage._size_topo."""
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


# ------------------------------------------------------- edit-log helpers (§3)
def _sha(tokens):
    return hashlib.sha1("->".join(str(t) for t in tokens).encode()).hexdigest()


def _store_seq(tokens):
    sha = _sha(tokens)
    p = os.path.join(SEQ_DIR, f"{sha}.txt")
    if not os.path.exists(p):
        tmp = p + f".{os.getpid()}.tmp"
        with open(tmp, "w") as fh:
            fh.write("->".join(str(t) for t in tokens) + "->")
        os.replace(tmp, p)
    return sha


def _log_edit(fh, rec):
    """Append one §3 edit record (line-buffered; append-only)."""
    fh.write(json.dumps(rec, default=str) + "\n")


# --------------------------------------------------- arm-C generator (§2, §10.3)
class Regrower:
    """v7 cut-and-regrow proposal source. Loaded once per cell. Deterministic
    per-(goal,arm,seed) torch seed so seeds differ but reproduce."""

    def __init__(self, env, base_spec, class_token, torch_seed):
        import torch
        # Bound per-process torch threads for the parallel fan-out (avoids
        # 6+ cells x 64 threads thrashing 128 cores). Sampling is sequential-
        # decode bound; a modest thread count is as fast and far more scalable.
        # Deterministic result is unaffected (fixed torch seed, CPU, temp 0.7).
        _t = os.environ.get("E11_TORCH_THREADS")
        if _t:
            try:
                torch.set_num_threads(int(_t))
            except Exception:
                pass
        import finetune as FT
        import genie_common as GC
        from genie_common import VOCAB_SIZE, TRUNCATE_ID
        import templates as T
        self._torch = torch
        self._GC = GC
        self._VOCAB_SIZE = VOCAB_SIZE
        self._TRUNCATE_ID = TRUNCATE_ID
        FT.ckpt_path = lambda arm, winners=False, tag=None: CKPT
        _devs, stoi, _vsz = FT.ext_vocab(ARM_TAG)
        self._stoi = stoi
        torch.manual_seed(torch_seed)
        self._model = FT.load_ft(ARM_TAG, "cpu", winners=True)
        self._cls_id = stoi[class_token]
        self.class_token = class_token
        self.torch_seed = torch_seed

        anchor_nl, _ = T.topo_to_netlist(env.topo)
        self.anchor_seq = [str(t) for t in T.emit_sequence(anchor_nl)]
        self.anchor_seq_sha = _store_seq(self.anchor_seq)
        self.base_spec = base_spec
        dev_budget = base_spec.topology.get("device_budget", [3, 16])
        self.min_dev, self.max_dev = dev_budget[0], dev_budget[1]

        def is_dev_tok(tk):
            return ("_" not in tk) and tk not in ("VSS", "VDD", "TRUNCATE")
        self.dev_positions = [i for i, tk in enumerate(self.anchor_seq)
                              if is_dev_tok(tk)]
        self.cut_choices = [0] + self.dev_positions
        try:
            from novelty import wl_features
            self.anchor_wl = wl_features(env.topo)[0]
        except Exception:
            self.anchor_wl = None

    def propose(self, rng):
        """Return (cut_depth, regrown_toks, regrown_len, regrown_sha, nl_or_None,
        realize_result_or_None, gate). 0 sims. `nl` is the L0-passing netlist (or
        None); realize_result is (topo, seq, wl, canon) or None."""
        import templates as T
        import moves as M
        from topology import Topology
        torch = self._torch
        GC = self._GC
        c = rng.choice(self.cut_choices)
        prefix_ids = [self._cls_id] + [self._stoi[t] for t in self.anchor_seq[:c]]
        try:
            rows, _steps = GC.generate_batch(
                self._model, [prefix_ids], max_new_tokens=MAX_NEW_TOKENS,
                temperature=TEMPERATURE, device="cpu")
        except Exception:
            return c, None, None, None, None, None, "sample_error"
        ids = [int(x) for x in rows[0].tolist()]
        ids = [x for x in ids if x < self._VOCAB_SIZE]
        circ = (ids[:ids.index(self._TRUNCATE_ID)]
                if self._TRUNCATE_ID in ids else ids)
        toks = [GC.ITOS[i] for i in circ]
        regrown_len = len(toks) - c
        regrown_sha = _store_seq(toks)
        nl = None
        try:
            topo = Topology(toks)
            if topo.valid:
                nl0, _ = T.topo_to_netlist(topo)
                if nl0 is not None and M.sane(nl0, max_dev=self.max_dev,
                                              min_dev=self.min_dev):
                    nl = nl0
        except Exception:
            nl = None
        if nl is None:
            return c, toks, regrown_len, regrown_sha, None, None, "L0"
        try:
            r = M.realize(nl, self.base_spec)
        except Exception:
            r = None
        gate = "realize" if r is not None else "L0"
        return c, toks, regrown_len, regrown_sha, nl, r, gate


def _class_token_for(env):
    """Narrowband (<=3 inductors) -> <LNA_NB>, else <LNA_WB> (§10.3 rule)."""
    import templates as T
    nl, _ = T.topo_to_netlist(env.topo)
    n_ind = 0
    for e in nl:
        name = e[0] if isinstance(e, (list, tuple)) else str(e)
        if str(name).lower().startswith("l") or str(name).lower().startswith("ind"):
            n_ind += 1
    return "<LNA_NB>" if n_ind <= 3 else "<LNA_WB>"


def _torch_seed(goal, arm, seed):
    h = hashlib.sha1(f"{goal}|{arm}|{seed}".encode()).hexdigest()
    return int(h[:8], 16)


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
    solve = {"solved": False, "evals": None, "spice_min": None,
             "wall_min": None, "metrics": None, "edit_seq": None, "n_edits": None,
             "stage": None}
    spice_s_acc = [0.0]
    stage_spend = {"s1_evals": 0, "s1_spice_s": 0.0,
                   "s2_evals": 0, "s2_spice_s": 0.0}
    cur_stage = ["s2"]           # arm a is all "s2"-equivalent sizing
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
                                  ("s21_db", "s21_ripple_db", "idd_ma", "nf_db",
                                   "s11_max_db", "s22_max_db")},
                         edit_seq=list(cur_edit_seq[0]),
                         n_edits=len(cur_edit_seq[0]),
                         stage=cur_stage[0])

    survivors_info = []
    # editor-distribution diagnostics (§6)
    n_proposed = 0            # total proposal ATTEMPTS
    n_realized = 0            # proposals that passed realize()
    distinct_realized = set()  # distinct realized WL-hashes
    distinct_l0 = set()       # arm C only: distinct L0-passing regrown shas
    cut_hist = {}             # arm C only
    regrown_lens = []         # arm C only
    regrower = None
    class_token = None
    torch_seed = None
    log_fh = None

    if arm in ("b", "c"):
        log_fh = open(EDITS_JSONL, "a", buffering=1)

    try:
        # ============================================================= ARM A
        if arm == "a":
            cur_stage[0] = "s2"
            cur_edit_seq[0] = []
            _size_topo(env, None, anchor_x, env.task.budget - env.n_evals,
                       seed, record)

        # ============================================================= ARM B / C
        else:
            import templates as T
            import g2_moves as G
            import moves as M
            base_nl, _ = T.topo_to_netlist(env.topo)
            ctx = G.ctx_for_spec(base_spec)
            rng = random.Random(seed)

            if arm == "c":
                class_token = _class_token_for(env)
                torch_seed = _torch_seed(goal_id, arm, seed)
                regrower = Regrower(env, base_spec, class_token, torch_seed)
                anchor_wl = regrower.anchor_wl
                anchor_seq_sha = regrower.anchor_seq_sha
            else:
                try:
                    from novelty import wl_features
                    anchor_wl = wl_features(env.topo)[0]
                except Exception:
                    anchor_wl = None
                anchor_seq_sha = _store_seq([str(t)
                                            for t in T.emit_sequence(base_nl)])

            # ---------------- STAGE 1: screen k candidates, cull to top-m ------
            # D1 stall/rollover clause (== E-9): bound proposal ATTEMPTS; unspent
            # stage-1 budget rolls into stage-2 so TOTAL == B.
            cur_stage[0] = "s1"
            s1_cap = min(k, env.task.budget)
            candidates = []
            seen_wl = set()
            guard = 0
            max_guard = max(600, s1_cap * 10)
            stall = 0
            stall_lim = max(400, s1_cap * 6)
            while (stage_spend["s1_evals"] < s1_cap
                   and env.n_evals < env.task.budget
                   and guard < max_guard and stall < stall_lim):
                guard += 1
                n_proposed += 1

                # ----- propose (arm B: primitives; arm C: v7 regrowth) --------
                if arm == "b":
                    try:
                        mut, move = G.mutate(base_nl, rng, ctx)
                    except Exception:
                        mut, move = None, None
                    if mut is None:
                        _log_edit(log_fh, {
                            "campaign": CAMPAIGN, "goal": goal_id, "arm": arm,
                            "seed": seed, "anchor_wl": anchor_wl,
                            "anchor_seq_sha": anchor_seq_sha, "move": None,
                            "args": None, "gate": "propose_fail",
                            "realized_wl": None, "l1_objective": None,
                            "stage2": None, "era": CAMPAIGN, "ts": _now()})
                        continue
                    r = M.realize(mut, base_spec)      # L0 + round-trip: 0 sims
                    if r is None:
                        _log_edit(log_fh, {
                            "campaign": CAMPAIGN, "goal": goal_id, "arm": arm,
                            "seed": seed, "anchor_wl": anchor_wl,
                            "anchor_seq_sha": anchor_seq_sha, "move": move,
                            "args": None, "gate": "L0", "realized_wl": None,
                            "l1_objective": None, "stage2": None,
                            "era": CAMPAIGN, "ts": _now()})
                        continue
                    mtopo, _seq, wl, canon = r
                    edit_meta = {"move": move, "args": None}
                    log_base = {"campaign": CAMPAIGN, "goal": goal_id, "arm": arm,
                                "seed": seed, "anchor_wl": anchor_wl,
                                "anchor_seq_sha": anchor_seq_sha, "move": move,
                                "args": None}
                else:  # arm C
                    (c, toks, rlen, rsha, nl, r, gate) = regrower.propose(rng)
                    log_base = {"campaign": CAMPAIGN, "goal": goal_id, "arm": arm,
                                "seed": seed, "anchor_wl": anchor_wl,
                                "anchor_seq_sha": anchor_seq_sha,
                                "cut_depth": c, "regrown_tokens_sha": rsha,
                                "regrown_len": rlen}
                    if gate == "sample_error":
                        _log_edit(log_fh, {**log_base, "gate": "sample_error",
                                           "realized_wl": None,
                                           "l1_objective": None, "stage2": None,
                                           "era": CAMPAIGN, "ts": _now()})
                        continue
                    if nl is not None:
                        distinct_l0.add(rsha)
                        cut_hist[c] = cut_hist.get(c, 0) + 1
                        regrown_lens.append(rlen)
                    if r is None:
                        _log_edit(log_fh, {**log_base, "gate": "L0",
                                           "realized_wl": None,
                                           "l1_objective": None, "stage2": None,
                                           "era": CAMPAIGN, "ts": _now()})
                        continue
                    mtopo, _seq, wl, canon = r
                    edit_meta = {"move": f"regrow(c={c},len={rlen})",
                                 "cut_depth": c, "regrown_tokens_sha": rsha,
                                 "regrown_len": rlen}

                # ----- realize passed; dedup on WL (D1) ----------------------
                n_realized += 1
                distinct_realized.add(wl)
                if wl in seen_wl:
                    stall += 1
                    _log_edit(log_fh, {**log_base, "gate": "realize",
                                       "realized_wl": wl, "l1_objective": None,
                                       "stage2": None, "duplicate": True,
                                       "era": CAMPAIGN, "ts": _now()})
                    continue
                seen_wl.add(wl)
                stall = 0
                try:
                    arena = env._arena_for(mtopo)
                except NotSizable:
                    _log_edit(log_fh, {**log_base, "gate": "realize",
                                       "realized_wl": wl, "l1_objective": None,
                                       "stage2": None, "not_sizable": True,
                                       "era": CAMPAIGN, "ts": _now()})
                    continue
                if env.n_evals >= env.task.budget:
                    break

                # ----- L1: exactly ONE counted eval @ x0=0.5 -----------------
                x0 = np.full(arena.dim, 0.5)
                cur_edit_seq[0] = [edit_meta["move"]]
                try:
                    out = env.evaluate(topology=mtopo, params=x0,
                                       action="l1-screen")
                except BudgetExhausted:
                    _log_edit(log_fh, {**log_base, "gate": "realize",
                                       "realized_wl": wl, "l1_objective": None,
                                       "stage2": None, "budget_exhausted": True,
                                       "era": CAMPAIGN, "ts": _now()})
                    break
                record(out)
                l1_obj = float(out["objective"])
                candidates.append({"topo": mtopo, "wl": wl,
                                   "move": edit_meta["move"], "obj": l1_obj,
                                   "dim": arena.dim, "meta": edit_meta})
                _log_edit(log_fh, {**log_base, "gate": "L1",
                                   "realized_wl": wl, "l1_objective": l1_obj,
                                   "stage2": None, "era": CAMPAIGN,
                                   "ts": _now()})
                if solve["solved"]:
                    break

            # cull to top-m by L1 objective (lower = closer to feasible)
            candidates.sort(key=lambda c: c["obj"])
            survivors = candidates[:m]
            survivors_info = [{"wl": c["wl"], "move": c["move"],
                               "s1_obj": round(c["obj"], 5),
                               "dim": c["dim"]} for c in survivors]

            # ---------------- STAGE 2: full per-survivor sizing --------------
            cur_stage[0] = "s2"
            surv_stage2 = {}   # wl -> {evals, best_objective, feasible}
            if survivors and not solve["solved"]:
                remaining = env.task.budget - env.n_evals
                per = max(1, remaining // len(survivors))
                for i, c in enumerate(survivors):
                    if solve["solved"] or env.n_evals >= env.task.budget:
                        break
                    cur_edit_seq[0] = [c["move"]]
                    budget_left = (env.task.budget - env.n_evals
                                   if i == len(survivors) - 1 else per)
                    if budget_left <= 0:
                        break
                    x0 = np.full(c["dim"], 0.5)
                    n_before = env.n_evals
                    best_before = solve["solved"]
                    surv_best = {"obj": float("inf")}

                    def _cb(out, _sb=surv_best):
                        record(out)
                        o = out.get("objective")
                        if o is not None and o < _sb["obj"]:
                            _sb["obj"] = float(o)
                    try:
                        _size_topo(env, c["topo"], x0, budget_left,
                                   seed + 100 + i, _cb)
                    except BudgetExhausted:
                        pass
                    surv_stage2[c["wl"]] = {
                        "evals": env.n_evals - n_before,
                        "best_objective": (None if surv_best["obj"] == float("inf")
                                           else round(surv_best["obj"], 5)),
                        "feasible": bool(solve["solved"] and not best_before)}
            # attach stage-2 outcome into survivors_info + log survivor rows
            for si in survivors_info:
                si["stage2"] = surv_stage2.get(si["wl"])
            if arm in ("b", "c"):
                for c in survivors:
                    row = {"campaign": CAMPAIGN, "goal": goal_id, "arm": arm,
                           "seed": seed, "anchor_wl": anchor_wl,
                           "anchor_seq_sha": anchor_seq_sha,
                           "move": c["move"], "gate": "survivor",
                           "realized_wl": c["wl"],
                           "l1_objective": round(c["obj"], 5),
                           "stage2": surv_stage2.get(c["wl"]),
                           "era": CAMPAIGN, "ts": _now()}
                    if arm == "c":
                        row["cut_depth"] = c["meta"].get("cut_depth")
                        row["regrown_tokens_sha"] = c["meta"].get(
                            "regrown_tokens_sha")
                        row["regrown_len"] = c["meta"].get("regrown_len")
                    _log_edit(log_fh, row)
    finally:
        if log_fh is not None:
            log_fh.close()

    wall_min = round((time.time() - t_start) / 60.0, 3)
    res = {"campaign": CAMPAIGN, "goal": goal_id, "arm": arm, "seed": seed,
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
           "survivors": survivors_info,
           # editor-distribution diagnostics (§6)
           "n_proposed": n_proposed if arm != "a" else None,
           "n_realized": n_realized if arm != "a" else None,
           "distinct_realized": len(distinct_realized) if arm != "a" else None,
           "distinct_l0": (len(distinct_l0) if arm == "c" else None),
           "cut_depth_histogram": (dict(sorted(cut_hist.items()))
                                   if arm == "c" else None),
           "regrown_len_stats": ({
               "n": len(regrown_lens),
               "min": min(regrown_lens) if regrown_lens else None,
               "max": max(regrown_lens) if regrown_lens else None,
               "mean": (round(sum(regrown_lens) / len(regrown_lens), 2)
                        if regrown_lens else None),
           } if arm == "c" else None),
           "arm_c_class_token": class_token,
           "arm_c_torch_seed": torch_seed,
           "contamination": (CONTAM if arm == "c" else None),
           "wall_min": wall_min,
           "solved": solve["solved"],
           "solved_stage": solve["stage"],
           "evals_to_solve": solve["evals"],
           "spice_min_to_solve": solve["spice_min"],
           "wall_min_to_solve": solve["wall_min"],
           "solve_metrics": solve["metrics"],
           "edit_seq": solve["edit_seq"],
           "n_edits": solve["n_edits"],
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
              f"spice-min -> {st}", flush=True)
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


def _write_status(msg):
    p = os.path.join(RESULTS, f"STATUS.{os.getpid()}.json")
    tmp = p + ".tmp"
    with open(tmp, "w") as fh:
        json.dump({"ts": _now(), "pid": os.getpid(), "msg": msg,
                   "ng_total": _NG["n"]}, fh, indent=1)
    os.replace(tmp, p)


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
    _write_status(f"START {goal_id} {arm} s{seed}")
    res = run_cell(goal_id, arm, seed)
    tmp = p + f".{os.getpid()}.tmp"
    with open(tmp, "w") as fh:
        json.dump(res, fh, indent=1, default=str)
    os.replace(tmp, p)
    _write_status(f"DONE {goal_id} {arm} s{seed} solved={res['solved']}")
    return res


# ----------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="E-11 scored campaign")
    ap.add_argument("--goals", default="G1pp,G9,G7pp,G2pp,G12,G13")
    ap.add_argument("--goal", default=None, help="single goal, all arms/seeds")
    ap.add_argument("--arms", default="a,b,c")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--cell", nargs=3, metavar=("GOAL", "ARM", "SEED"),
                    help="run ONE cell and exit")
    a = ap.parse_args()
    _install_ng_counter()

    if a.cell:
        run_and_save(a.cell[0], a.cell[1], int(a.cell[2]), force=a.force)
        return 0

    goals = [a.goal] if a.goal else [g for g in a.goals.split(",") if g]
    arms = [x for x in a.arms.split(",") if x]
    for goal_id in goals:
        for arm in arms:
            for seed in GOALS[goal_id]["seeds"]:
                run_and_save(goal_id, arm, seed, force=a.force)
    print(f"campaign cells complete; ngspice_total={_NG['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

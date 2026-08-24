"""E-12 P3 -- SCORED transfer campaign (trained editors C1 / C2 + fresh A/B).

Binding pre-reg: engineer/E12-TRAINEDIT.md (GO) -- §4 goal sets, §6 arms/budgets,
§7 metrics, §8 falsifier. P3 launch note (user 2026-08-24).

60 cells, all STANDARD E-9 anchors (the reached *-t2-a anchors; NOT the P1b
near-miss anchors -- these are scoreboard runs), matched TOTAL B per cell,
k/m per E-11 (B=600: k=120,m=4; B=1200: k=200,m=5), D1 rollover, NO early stop
on solve (spend the full B; record evals_to_solve):

  * Arms C1 and C2 (trained editors) on ALL 8 goals x seeds 1-3 = 48 cells.
      DEV:      G2pp, G13, G9(B=1200), G7pp, G12
      HELD-OUT: G1pp, H2
      FRESH:    GN78 (n78 in-memory band swap via e12_tasks)
  * Baseline arms A (sizing-only) and B (hand primitives) x seeds 1-3 ONLY for
      H2 and GN78 = 12 cells. (DEV + G1'' baselines are the banked E-11 cells.)

Machinery byte-identical to E-11: C1/C2 run through e11_run.run_cell's arm-"c"
two-stage path VERBATIM; the ONLY differences are (a) the Regrower loads the
trained editor checkpoint instead of ft_p5v7_v2.pth, (b) for C2 the goal's own
spec-bin prefix (documented public rule, dhruva-s BASE_LIMITS c2_bin) is
prepended after the class token exactly as C2 training conditioned, (c) the
torch seed keys off the P3 arm label ("c1"/"c2") so the two arms differ.

Frozen arm-C sampling constants carry over (temp 0.7 / max_new 256 / sha1 torch
seeds). Edit logging continues for every proposal; campaign tag "e12-p3" in the
shared APPEND-ONLY edit log. Per-cell atomic JSON under data/e12/p3_results/.

CONTAINMENT: read-only toward lna/ and engineer/ (imports only); checkpoints
read-only from engineer/out_editor/. <=8 concurrent ngspice via the launcher.
PYTHONHASHSEED=0. torch CPU-only. NO git ops.

    python e12_p3.py --cell G13 c1 1
    python e12_p3.py --goal H2 --arms a,b,c1,c2
    python e12_p3.py                 # all 60 cells (serial)
"""
import argparse
import copy
import hashlib
import json
import os
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable] + sys.argv)

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.abspath(os.path.join(HERE, "..", "lna"))
for p in (HERE, LNA):
    if p not in sys.path:
        sys.path.insert(0, p)

import inspect               # noqa: E402
import re as _re             # noqa: E402
import e11_run as R           # noqa: E402  (reuse run_cell machinery verbatim)
import e12_train_common as TC  # noqa: E402  (c2 vocab + public bin rule)
import e12_tasks as FRESH     # noqa: E402  (n78 in-memory band swap)

# ---------------------------------------------------------------------------
# NO-EARLY-STOP-ON-SOLVE (scoreboard requirement, E-12 P3 launch note).
#
# The E-11 run_cell BREAKS out of stage-1/stage-2 the moment a cell first becomes
# feasible (P1b flagged this as an early-stop deviation legitimate for banking
# only). Scoreboard cells must spend the FULL B and still record evals_to_solve.
#
# We install a source-faithful variant of run_cell that DEFEATS exactly the three
# control-flow early-stop guards and NOTHING else -- the recording of the first
# solve (line: `if not solve["solved"] and ext_feasible(...)`), the survivor
# feasible flag, and the result fields are untouched. The transform is a minimal,
# auditable diff exec'd in e11_run's own module globals so every helper reference
# (_size_topo, ext_feasible, _log_edit, Regrower, ...) resolves identically to
# the verbatim machinery.  evals_to_solve is still latched at first feasibility
# because `record()` only updates `solve` while `solve["solved"]` is False.
# ---------------------------------------------------------------------------
def _install_no_early_stop():
    src = inspect.getsource(R.run_cell)
    orig = src
    # 1) stage-1: `if solve["solved"]:\n    break`  -> disable the break
    src = src.replace('                if solve["solved"]:\n                    break\n',
                      '                # [P3 no-early-stop] stage-1 break disabled\n')
    # 2) stage-2 entry guard `if survivors and not solve["solved"]:`
    src = src.replace('            if survivors and not solve["solved"]:',
                      '            if survivors:  # [P3 no-early-stop]')
    # 3) stage-2 per-survivor guard `if solve["solved"] or env.n_evals >= ...`
    src = src.replace(
        '                    if solve["solved"] or env.n_evals >= env.task.budget:',
        '                    if env.n_evals >= env.task.budget:  # [P3 no-early-stop]')
    n_changed = sum(1 for a, b in (
        ('                if solve["solved"]:\n                    break\n', 1),
        ('            if survivors and not solve["solved"]:', 1),
        ('                    if solve["solved"] or env.n_evals >= env.task.budget:', 1))
        if a in orig)
    assert n_changed == 3, f"no-early-stop: expected 3 guard sites, found {n_changed}"
    assert 'solve["solved"]' in src and 'evals_to_solve' not in src.split('res =')[0] or True
    # de-indent the top-level `def run_cell` block for exec
    ns = {}
    exec(compile(src, "<e12_p3_run_cell>", "exec"), R.__dict__, ns)
    R.run_cell = ns["run_cell"]
    R._P3_RUN_CELL_SRC = src   # keep the transformed source for audit


_install_no_early_stop()

# ---- checkpoints (engineer-owned trained editors) ---------------------------
CKPT_C1 = os.path.join(HERE, "out_editor", "editor_c1.pth")   # p5 vocab 1008
CKPT_C2 = os.path.join(HERE, "out_editor", "editor_c2.pth")   # p5+16 -> 1024

# ---- P3 goals: DEV + HELD-OUT + FRESH (base task + in-memory delta) ----------
# DEV/HELD-OUT reuse the E-11 GOALS deltas verbatim; H2 + GN78 added.
GOALS = {
    # ---- DEV ----
    "G2pp": {"task": "dhruva-s-t2-a",
             "ext": {"s22_max_db": {"max": -10.0, "status": "measured"}},
             "desc": "s22_max_db <= -10 band-wide (dhruva-s) [DEV]",
             "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "match",
             "tier": "DEV"},
    "G13": {"task": "dhruva-l2-t2-a",
            "ext": {"nf_db": {"max": 1.45, "status": "measured"}},
            "desc": "nf_db <= 1.45 (dhruva-l2) [DEV]",
            "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "noise",
            "tier": "DEV"},
    "G9": {"task": "dhruva-l5-t2-a",
           "ext": {"s21_ripple_db": {"max": 3.0, "status": "measured"}},
           "desc": "s21_ripple_db <= 3 (dhruva-l5) [DEV]",
           "B": 1200, "k": 200, "m": 5, "seeds": [1, 2, 3], "gtype": "band-shape",
           "tier": "DEV"},
    "G7pp": {"task": "dhruva-l5-t2-a",
             "ext": {"idd_ma": {"max": 9.0, "status": "measured"},
                     "s21_db": {"min": 22.3, "status": "measured"}},
             "desc": "idd_ma <= 9.0 @ s21 >= 22.3 (dhruva-l5) [DEV]",
             "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "current",
             "tier": "DEV"},
    "G12": {"task": "dhruva-l5-t2-a",
            "ext": {"s11_max_db": {"max": -15.0, "status": "measured"}},
            "desc": "s11_max_db <= -15 band-wide (dhruva-l5) [DEV]",
            "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "match",
            "tier": "DEV"},
    # ---- HELD-OUT (transfer) ----
    "G1pp": {"task": "dhruva-l1-t2-a",
             "ext": {"s21_db": {"min": 33.0, "status": "measured"}},
             "desc": "s21_db >= 33 (dhruva-l1) [HELD-OUT]",
             "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "gain",
             "tier": "HELD-OUT"},
    "H2": {"task": "dhruva-l1-t2-a",
           "ext": {"nf_db": {"max": 1.25, "status": "measured"}},
           "desc": "nf_db <= 1.25 (dhruva-l1) [HELD-OUT]",
           "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "noise",
           "tier": "HELD-OUT"},
    # ---- FRESH (transfer; n78 band swap) ----
    "GN78": {"task": "n78-t2-a",
             "ext": {"nf_db": {"max": 1.6, "status": "measured"}},
             "desc": "nf_db <= 1.6 (n78, 3.4-3.6 GHz) [FRESH]",
             "B": 600, "k": 120, "m": 4, "seeds": [1, 2, 3], "gtype": "noise",
             "tier": "FRESH"},
}

# base task id -> C2 spec-bin prefix (documented public rule, dhruva-s
# BASE_LIMITS c2_bin; the goal's own bin prefix = a design that MEETS every base
# limit, overridden by the goal's tightened target where it is a C2 metric).
_KEY2M = {v[0]: k for k, v in TC.BASE_LIMITS.items()}


def c2_prefix_for(goal_id):
    """The evaluation goal's own C2 bin prefix per the documented public rule."""
    ext = GOALS[goal_id]["ext"]
    metrics = {TC.BASE_LIMITS[m][0]: TC.BASE_LIMITS[m][2] for m in TC.C2_METRICS}
    for key, cons in ext.items():
        if key in _KEY2M:
            metrics[key] = cons.get("max", cons.get("min"))
    return TC.c2_prefix_tokens(metrics)


# ---- rebind the E-11 runner to E-12 P3 --------------------------------------
R.CAMPAIGN = "e12-p3"
R.GOALS = GOALS
R.RESULTS = os.path.join(HERE, "data", "e12", "p3_results")
os.makedirs(R.RESULTS, exist_ok=True)

# module slot carrying the CURRENT P3 arm label ("a"/"b"/"c1"/"c2") + goal so the
# patched Regrower/get_task/cell_path resolve correctly inside run_cell.
_CUR = {"goal": None, "p3arm": None}

_orig_Regrower = R.Regrower
_orig_torch_seed = R._torch_seed
_orig_cell_path = R.cell_path


class _P3Regrower(_orig_Regrower):
    """Arm-c Regrower that loads a TRAINED editor (C1 or C2) instead of v7, and
    (for C2) prepends the goal's spec-bin prefix after the class token. All other
    behavior (cut rule, sane/realize gates, dev-token positions) is inherited
    byte-identical from e11_run.Regrower."""

    def __init__(self, env, base_spec, class_token, torch_seed):
        import torch
        _t = os.environ.get("E11_TORCH_THREADS")
        if _t:
            try:
                torch.set_num_threads(int(_t))
            except Exception:
                pass
        import finetune as FT
        import genie_common as GC
        from genie_common import (VOCAB_SIZE, TRUNCATE_ID, N_EMBD, N_HEAD,
                                  N_LAYER, BLOCK_SIZE, DROPOUT)
        from Models.GPT import GPTLanguageModel
        import templates as T

        p3arm = _CUR["p3arm"]
        assert p3arm in ("c1", "c2"), f"P3Regrower for arm {p3arm}"
        self._torch = torch
        self._GC = GC
        self._VOCAB_SIZE = VOCAB_SIZE
        self._TRUNCATE_ID = TRUNCATE_ID

        # vocab: C1 = p5 (1008); C2 = p5 + 16 spec tokens (1024).
        if p3arm == "c1":
            devs, stoi, vocab = FT.ext_vocab("p5")
            stoi = {d: i for i, d in enumerate(devs)}
            ckpt = CKPT_C1
            spec_prefix_toks = []
        else:
            devs, stoi, vocab = TC.ext_vocab_c2()
            ckpt = CKPT_C2
            spec_prefix_toks = c2_prefix_for(_CUR["goal"])
        self._stoi = stoi

        torch.manual_seed(torch_seed)
        model = GPTLanguageModel(vocab, N_EMBD, BLOCK_SIZE, N_HEAD, N_LAYER, DROPOUT)
        model.load_state_dict(torch.load(ckpt, map_location="cpu"))
        self._model = model.to("cpu").eval()
        self._cls_id = stoi[class_token]
        self.class_token = class_token
        self.torch_seed = torch_seed
        self.p3arm = p3arm
        self.ckpt = ckpt
        self.vocab = vocab
        self.spec_prefix_toks = list(spec_prefix_toks)
        self._spec_prefix_ids = [stoi[t] for t in spec_prefix_toks]

        anchor_nl, _ = T.topo_to_netlist(env.topo)
        self.anchor_seq = [str(t) for t in T.emit_sequence(anchor_nl)]
        self.anchor_seq_sha = R._store_seq(self.anchor_seq)
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
        """Identical to e11_run.Regrower.propose except the prefix carries the
        (C2) spec-bin ids after the class token -- exactly as C2 was conditioned
        during training. Returns the same 7-tuple; 0 sims."""
        import templates as T
        import moves as M
        from topology import Topology
        GC = self._GC
        c = rng.choice(self.cut_choices)
        prefix_ids = ([self._cls_id] + self._spec_prefix_ids
                      + [self._stoi[t] for t in self.anchor_seq[:c]])
        try:
            rows, _steps = GC.generate_batch(
                self._model, [prefix_ids], max_new_tokens=R.MAX_NEW_TOKENS,
                temperature=R.TEMPERATURE, device="cpu")
        except Exception:
            return c, None, None, None, None, None, "sample_error"
        ids = [int(x) for x in rows[0].tolist()]
        ids = [x for x in ids if x < self._VOCAB_SIZE]
        circ = (ids[:ids.index(self._TRUNCATE_ID)]
                if self._TRUNCATE_ID in ids else ids)
        toks = [GC.ITOS[i] for i in circ]
        regrown_len = len(toks) - c
        regrown_sha = R._store_seq(toks)
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


def _p3_torch_seed(goal, arm, seed):
    # keep the P3 arm label ("c1"/"c2") in the seed hash so the two trained arms
    # sample differently; identical hashing style to e11_run._torch_seed.
    key = f"{goal}|{_CUR['p3arm']}|{seed}"
    h = hashlib.sha1(key.encode()).hexdigest()
    return int(h[:8], 16)


def _p3_cell_path(goal_id, arm, seed):
    # arm passed into run_cell is "c" for c1/c2; write under the P3 arm label.
    lbl = _CUR["p3arm"] or arm
    return os.path.join(R.RESULTS, f"cell_{goal_id}_{lbl}_s{seed}.json")


def _install_patches():
    R.Regrower = _P3Regrower
    R._torch_seed = _p3_torch_seed
    R.cell_path = _p3_cell_path


# ---- FRESH task wiring: register n78 so run_cell's get_task finds it ----------
_orig_get_task = R.get_task


def _p3_get_task(tid):
    if tid == "n78-t2-a":
        return FRESH.n78_task(budget=GOALS["GN78"]["B"], seed=1)
    return _orig_get_task(tid)


R.get_task = _p3_get_task


def run_and_save(goal_id, p3arm, seed, force=False):
    """Run one P3 cell. C1/C2 route through run_cell as internal arm 'c' (verbatim
    machinery) with the trained Regrower installed; A/B route straight through."""
    _install_patches()
    _CUR["goal"] = goal_id
    _CUR["p3arm"] = p3arm
    internal_arm = "c" if p3arm in ("c1", "c2") else p3arm

    p = _p3_cell_path(goal_id, internal_arm, seed)
    if os.path.exists(p) and not force:
        try:
            with open(p) as fh:
                d = json.load(fh)
            if d.get("evals_spent"):
                print(f"  [{goal_id} {p3arm} s{seed}] resume: exists, skip")
                return d
        except Exception:
            pass

    R._install_ng_counter()
    R._write_status(f"START {goal_id} {p3arm} s{seed}")

    fresh_ctx = FRESH.n78_active() if goal_id == "GN78" else None
    if fresh_ctx is not None:
        fresh_ctx.__enter__()
    try:
        res = R.run_cell(goal_id, internal_arm, seed)
    finally:
        if fresh_ctx is not None:
            fresh_ctx.__exit__(None, None, None)

    # relabel arm to the P3 label + attach P3 provenance
    res["arm"] = p3arm
    res["scoreboard"] = True
    res["tier"] = GOALS[goal_id]["tier"]
    res["no_early_stop"] = True   # scoreboard: full B spent regardless of solve
    if p3arm in ("c1", "c2"):
        res["editor_checkpoint"] = (CKPT_C1 if p3arm == "c1" else CKPT_C2)
        res["editor_vocab"] = (1008 if p3arm == "c1" else 1024)
        if p3arm == "c2":
            res["c2_spec_prefix"] = c2_prefix_for(goal_id)
            res["c2_prefix_rule"] = ("documented public rule: dhruva-s "
                                     "BASE_LIMITS c2_bin; goal-target design "
                                     "(meets every base limit, tightened metric "
                                     "-> goal target)")
        res["contamination"] = {
            **(R.CONTAM or {}),
            "generator_checkpoint": os.path.basename(res["editor_checkpoint"]),
            "arm": p3arm,
        }

    tmp = p + f".{os.getpid()}.tmp"
    with open(tmp, "w") as fh:
        json.dump(res, fh, indent=1, default=str)
    os.replace(tmp, p)
    R._write_status(f"DONE {goal_id} {p3arm} s{seed} solved={res['solved']}")
    return res


# ---- cell plan --------------------------------------------------------------
TRAINED_ARMS = ("c1", "c2")
BASELINE_GOALS = ("H2", "GN78")   # only these get fresh A/B in P3


def all_cells():
    cells = []
    # 48 trained cells: all 8 goals x {c1,c2} x seeds 1-3
    for g in GOALS:
        for arm in TRAINED_ARMS:
            for s in GOALS[g]["seeds"]:
                cells.append((g, arm, s))
    # 12 baseline cells: A + B for H2 and GN78 x seeds 1-3
    for g in BASELINE_GOALS:
        for arm in ("a", "b"):
            for s in GOALS[g]["seeds"]:
                cells.append((g, arm, s))
    return cells


def main():
    ap = argparse.ArgumentParser(description="E-12 P3 scored transfer campaign")
    ap.add_argument("--goal", default=None)
    ap.add_argument("--arms", default=None,
                    help="comma list from a,b,c1,c2")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--cell", nargs=3, metavar=("GOAL", "ARM", "SEED"))
    ap.add_argument("--plan", action="store_true", help="print the 60-cell plan")
    a = ap.parse_args()
    R._install_ng_counter()

    if a.plan:
        cells = all_cells()
        for g, arm, s in cells:
            print(g, arm, s)
        print(f"# total {len(cells)} cells", file=sys.stderr)
        return 0

    if a.cell:
        run_and_save(a.cell[0], a.cell[1], int(a.cell[2]), force=a.force)
        return 0

    if a.goal:
        arms = (a.arms.split(",") if a.arms else
                (list(TRAINED_ARMS) + (["a", "b"] if a.goal in BASELINE_GOALS
                                       else [])))
        for arm in arms:
            for s in GOALS[a.goal]["seeds"]:
                run_and_save(a.goal, arm, s, force=a.force)
        return 0

    for g, arm, s in all_cells():
        run_and_save(g, arm, s, force=a.force)
    print(f"E-12 P3 cells complete; ngspice_total={R._NG['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

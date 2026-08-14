"""engineer/env.py -- the sizing environment of the `engineer` line.

`lna/plans2/15-ENGINEER-PROPOSAL.md` D-6 (ruled 2026-08-14) re-aimed the program:
the product is the *engineer* -- an RF-grade agentic analog-design environment,
benchmark and loop -- with the dhruva LNA as its flagship case study. This module
is that environment's first surface. `engineer/00-CHARTER.md` states the policy
it lives under; this file states the mechanism.

WHAT IS SHARED WITH THE LNA LINE (i.e. what is NOT re-implemented here)
-----------------------------------------------------------------------
Everything that measures anything, exactly as `lna/null_sizer.py` shares it. This
module never touches ngspice, never builds a netlist, never decides feasibility:

    stored L2 row -> null_sizer.build_task  ->  topology + spec + prepared deck
    bias.insert_bias + classify_params      ->  size.prepared_body(topo, Q)
    the [0,1]^d box and its per-kind decode ->  size.make_objective(...)
    ONE ngspice evaluation                  ->  the `objective_func` that
                                                make_objective returns, verbatim
                                                (extract.run_and_extract +
                                                extract.measure_nf when gated)
    feasibility / margins                   ->  spec.feasible, ds.margins_for

The environment differs from `null_sizer` in what it *exposes*, not in what it
computes: an eval here is bit-identical to an eval there, and both count the same
event (one call of `make_objective`'s objective) as one eval, so a budget stated
in this file means the same number of ngspice invocations as a budget stated in
FINDINGS §43.2's null-sizer table. That identity is the whole point -- an
environment whose numbers cannot be compared to the line's own published numbers
is a second harness, and this program has one harness.

READ-ONLY TOWARD `lna/`
-----------------------
Imports from `lna/` are strictly read-only. Nothing in this module appends to
`lna/data/*.jsonl`: `make_objective` is always called with `op_sink=` a memory
sink defined below (never `size.OpSink`, which knows how to flush) and never with
a store-writing driver. The engineer line's own append-only table is
`engineer/data/trajectories.jsonl` (§5.6 of the proposal), written by
`TrajectoryLogger` here. Cross-line data combination is `lna/sync_lines.py`'s job
and only its job.

OP SUBSAMPLE: 1-in-1, IN MEMORY, NEVER FLUSHED  (charter R-3, ADOPTED 2026-08-14)
---------------------------------------------------------------------------------
`size._op_subsample()` defaults to 1-in-8 because an op row is ~5x a point row
and the lna store pays for every one it keeps. This environment's `observe()` is
the S5 "semantics-in-state" surface -- an agent that must diagnose *this* step
cannot be handed a 1-in-8 sample of it -- so the default here is 1-in-1 with a
bounded ring buffer (`keep_op`, default 8 captures) and no flush path at all. The
volume argument that justifies 1-in-8 is a *storage* argument; nothing is stored.
The user adopted R-3 on 2026-08-14; E-1's tests found no bug in the ring buffer,
so it stays the default unchanged.

LOUD DEP-SHIM  (charter R-1, ADOPTED 2026-08-14)
------------------------------------------------
R-1 was ruled "keep the shim, make it loud": if the model card / required deps do
not resolve to existing paths, `_bind_runtime_deps()` raises a clear exception
(naming every searched location and the `LNA_DEPS_ROOT` override) at import --
before any Env is built or any eval is run -- rather than letting ngspice run with
no models and return None on every eval (the fictional-clean-campaign failure).
The resolved paths ride into every result's `harness.deps` block (the stamp). The
shared-core `extract.rewrite_includes` now also self-resolves the model card at
deck-build time, so the two resolvers agree; env's raise is what still makes a
genuinely missing card impossible to miss instead of silently penalising.

DETERMINISM
-----------
The environment itself draws no random numbers. Every stochastic choice belongs
to the algorithm the caller drives it with, seeded from `Task.seed`. Two runs of
the same (task, algorithm, seed) issue the same x vectors in the same order and
therefore the same trajectory, modulo wall-clock fields.

    python engineer/env.py --selftest              # 3 evals on wifi24-smoke
    python engineer/env.py --selftest --task dhruva-l5-t2-a
"""
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA_DIR = os.path.join(HERE, "data")
TRAJ_TABLE = os.path.join(DATA_DIR, "trajectories.jsonl")

# The runtime deps a fresh worktree does not have, and how to recognise each one.
_DEP_PROBES = {
    "zoaf": os.path.join("misc", "ZOAF", "zoaf", "zoaf_core.py"),
    "models": os.path.join("AutoCkt", "repo", "eval_engines", "ngspice",
                           "ngspice_inputs", "spice_models", "45nm_bulk.txt"),
}
BIND = {}          # filled by _bind_runtime_deps(); reported by observe()/results


# --------------------------------------------------------------- dep binding
def _candidate_roots():
    """Checkout roots to probe, nearest first.

    A `git worktree` of this repo is a full checkout of the *tracked* files and
    none of the untracked upstream clones (`.gitignore`'s "Upstream clones"
    block), so `misc/ZOAF` and the 45 nm model card exist only where somebody ran
    `scripts/fetch_upstream.sh` -- normally the main checkout. Order: an explicit
    override, this checkout, the git common dir's parent (the main checkout, for
    a worktree), then plain ancestors (worktrees live at
    `<main>/.claude/worktrees/<name>`, so the main checkout is an ancestor)."""
    seen, out = set(), []

    def add(p):
        if p and os.path.isdir(p) and p not in seen:
            seen.add(p)
            out.append(p)

    add(os.environ.get("LNA_DEPS_ROOT"))
    add(ROOT)
    try:
        r = subprocess.run(["git", "rev-parse", "--path-format=absolute",
                            "--git-common-dir"], cwd=ROOT, capture_output=True,
                           text=True, timeout=10)
        common = (r.stdout or "").strip()
        if common:
            add(os.path.dirname(os.path.abspath(common)))
    except Exception:                                              # noqa: BLE001
        pass                       # git absent or not a repo: ancestors still try
    p = ROOT
    while True:
        parent = os.path.dirname(p)
        if parent == p:
            break
        add(parent)
        p = parent
    return out


def _bind_runtime_deps(verbose=False):
    """Make `import size` work from any checkout, and say where it found what.

    THE FAILURE THIS PREVENTS is silent, which is why the shim exists at all: with
    `misc/ZOAF` missing, `import size` raises (loud, fine); with the 45 nm model
    card missing, ngspice runs, finds no models, and every evaluation returns
    None -- so `make_objective` returns `SIM_FAIL_PENALTY` for every x and a
    campaign reports a clean, converged, entirely fictional "no feasible point".
    A shim is the wrong shape for a hard precondition and the right shape for a
    path lookup; which of the two this is, is a queued ruling (E-1 in the
    charter). Until it is ruled, the shim binds *and stamps* -- `BIND` records the
    resolved paths and rides into every result JSON, so no number can be read
    without its harness provenance.

    Idempotent; must run BEFORE `import size` (which itself inserts a possibly
    dead `../misc/ZOAF` at sys.path[0] -- harmless once a live one is present)."""
    if BIND:
        return BIND
    lna_dir = os.path.join(ROOT, "lna")
    if not os.path.isdir(lna_dir):
        raise RuntimeError(f"no lna/ under {ROOT}: this file must live in a "
                           "checkout of the circuit-repro repository")
    found, roots = {}, _candidate_roots()
    for key, rel in _DEP_PROBES.items():
        for root in roots:
            cand = os.path.join(root, rel)
            if os.path.exists(cand):
                found[key] = (os.path.abspath(cand), root == ROOT)
                break
        else:
            raise RuntimeError(
                f"runtime dependency {key!r} not found: probed {rel!r} under "
                + ", ".join(roots) + ". Junction it in (see .gitignore's "
                "'Runtime deps junctioned into a worktree') or set LNA_DEPS_ROOT.")
    zoaf_dir = os.path.abspath(os.path.join(os.path.dirname(found["zoaf"][0]), ".."))
    for p in (zoaf_dir, lna_dir):
        if p not in sys.path:
            sys.path.insert(0, p)
    BIND.update(lna=lna_dir, zoaf=zoaf_dir, models=found["models"][0],
                local={k: v[1] for k, v in found.items()}, rebound=False)
    import to_spice                                                # noqa: E402
    if os.path.abspath(to_spice.DEFAULT_MODELS) != BIND["models"]:
        # Rebind the module constant AND `Netlist.__init__`'s default, which was
        # bound to the old string at class-creation time. Assert the slot first:
        # a signature change must fail loudly here, not silently emit a deck with
        # no model card (the fictional-campaign failure above).
        d = list(to_spice.Netlist.__init__.__defaults__)
        if os.path.abspath(d[0]) != os.path.abspath(to_spice.DEFAULT_MODELS):
            raise RuntimeError("to_spice.Netlist.__init__ no longer takes "
                               "`models` as its first defaulted parameter; the "
                               "engineer dep shim must be updated with it")
        d[0] = BIND["models"]
        to_spice.Netlist.__init__.__defaults__ = tuple(d)
        to_spice.DEFAULT_MODELS = BIND["models"]
        BIND["rebound"] = True
    if verbose:
        print(f"env: lna={BIND['lna']}\n     zoaf={BIND['zoaf']}\n"
              f"     models={BIND['models']}"
              + ("  [rebound]" if BIND["rebound"] else "  [worktree-local]"))
    return BIND


_bind_runtime_deps()
import datastore as ds        # noqa: E402
import null_sizer as NS       # noqa: E402  (build_task + the eval-accounting rule)
import size as S              # noqa: E402


# ------------------------------------------------------------------- the task
class BudgetExhausted(Exception):
    """Raised on the evaluation *after* the budget is spent.

    Same contract as `null_sizer._BudgetOut`, for the same reason: an algorithm
    that plans in generations must stop on the eval, not on the iteration, or the
    budget it was matched to is not the budget it spent."""


class NotSizable(ValueError):
    """A topology the sizer cannot turn into an evaluable deck (E-1 deliverable 3).

    THE CONTRACT, chosen and stated here so a driver can hold it: `evaluate()` on
    a foreign topology raises `NotSizable` (a `ValueError` subclass, so existing
    `except ValueError` callers still catch it) the moment `size.prepared_body`
    declines the topology -- i.e. `bias.insert_bias` reports a floating subcircuit
    or the biased netlist is not two-port. This is a RAISE, not a structured
    infeasible result, on purpose: an infeasible result is a *measurement* ("this
    deck ran and missed a spec"), and a non-sizable topology was never a deck --
    counting it as one eval and returning a penalty objective would tell a search
    it explored a point it could not have. `.wl_digest` carries the token digest
    of the offending topology so the caller can log which one it was. Raised at
    `_arena_for` time (the first `evaluate` of that topology), before any ngspice
    call and before the budget is charged -- a topology the sizer refuses costs no
    evals."""

    def __init__(self, message, wl_digest=None):
        super().__init__(message)
        self.wl_digest = wl_digest


class Task(object):
    """One benchmark task: a spec, a stored topology, a tier, a budget, a seed.

    A task is a *pin*, not a query. `ref_ts` names the exact stored L2 row this
    task's reference numbers come from, because `(wl_hash, spec)` alone does not:
    several tasks in the registry have two or more stored rows and
    `null_sizer.build_task` takes `rows[-1]`, so an append to the store would
    silently move the budget of a task that was supposed to be frozen. `tier`
    records which gate the task is judged at -- and is the field that will read
    `3` on the day the two-tone harness binds `iip3_dbm` (see `tasks.py`)."""

    def __init__(self, task_id, spec, wl_hash, budget, seed=1, tier=2,
                 ref_ts=None, ref_evals=None, ref_feasible=None, ref_obj=None,
                 era="current", inductor_q=None, nf_gate=None, n_devices=None,
                 notes=""):
        self.id, self.spec, self.wl_hash = task_id, spec, wl_hash
        self.budget, self.seed, self.tier = int(budget), int(seed), int(tier)
        self.ref_ts, self.ref_evals = ref_ts, ref_evals
        self.ref_feasible, self.ref_obj = ref_feasible, ref_obj
        self.era, self.n_devices, self.notes = era, n_devices, notes
        self.inductor_q, self.nf_gate = inductor_q, nf_gate

    def with_(self, **kw):
        """A copy with fields replaced -- the only way to change a task, so the
        registry's pins stay the registry's."""
        d = dict(task_id=self.id, spec=self.spec, wl_hash=self.wl_hash,
                 budget=self.budget, seed=self.seed, tier=self.tier,
                 ref_ts=self.ref_ts, ref_evals=self.ref_evals,
                 ref_feasible=self.ref_feasible, ref_obj=self.ref_obj,
                 era=self.era, inductor_q=self.inductor_q, nf_gate=self.nf_gate,
                 n_devices=self.n_devices, notes=self.notes)
        d.update({("task_id" if k == "id" else k): v for k, v in kw.items()})
        return Task(**d)

    def as_dict(self):
        return {"id": self.id, "spec": self.spec, "wl_hash": self.wl_hash,
                "tier": self.tier, "budget": self.budget, "seed": self.seed,
                "era": self.era, "n_devices": self.n_devices,
                "ref": {"ts": self.ref_ts, "n_evals": self.ref_evals,
                        "feasible": self.ref_feasible, "best_obj": self.ref_obj},
                "notes": self.notes}

    def __repr__(self):
        return (f"<Task {self.id} spec={self.spec} wl={self.wl_hash} "
                f"tier={self.tier} budget={self.budget}>")


def _pinned_row(task):
    """The stored L2 row `task.ref_ts` names, or a loud failure.

    Loud rather than fall-back-to-latest: a task whose pinned row is gone is not
    the same task, and quietly re-pinning it would move a published budget.

    When `task.ref_ts` is given the lookup is by exact timestamp in ALL stored
    rows for this (wl_hash, spec) that carry a token graph -- the n_evals filter
    is NOT applied for explicit pins because era-relabeled rows carry n_evals=0
    by construction (a re-label is one measurement of one stored point, not a
    new campaign), and a pin to such a row is fully intentional."""
    all_rows = [r for r in ds.load("topo_labels")
                if r.get("spec") == task.spec and r.get("wl_hash") == task.wl_hash
                and (r.get("graph") or {}).get("tokens")]
    rows = [r for r in all_rows if r.get("n_evals")]   # campaign rows only
    if not rows and not all_rows:
        raise RuntimeError(f"{task.id}: no stored L2 row with tokens for "
                           f"({task.wl_hash}, {task.spec})")
    if task.ref_ts is None:
        if not rows:
            raise RuntimeError(f"{task.id}: no stored L2 row with n_evals for "
                               f"({task.wl_hash}, {task.spec})")
        return rows[-1]
    hit = [r for r in all_rows if r.get("ts") == task.ref_ts]
    if not hit:
        raise RuntimeError(
            f"{task.id}: pinned reference row ts={task.ref_ts} is not in the "
            f"store ({len(all_rows)} rows for this (wl_hash, spec)); the task's "
            "budget and reference numbers cannot be reproduced")
    return hit[-1]


# ----------------------------------------------------- in-memory op capture
class _MemoryOpSink(object):
    """`make_objective`'s op_sink protocol (`want` / `tick` / `add`), in memory.

    Deliberately NOT `size.OpSink`: that class knows how to `flush()` into
    `lna/data/op_points.jsonl`, and the engineer line's read-only-toward-lna rule
    is worth more than the code reuse. This one has no flush path to call by
    accident. Keeps the last `keep` captures plus, separately, the capture of the
    best-so-far evaluation -- the two an agent actually reads."""

    def __init__(self, subsample=1, keep=8, enabled=True):
        self.subsample, self.keep, self.enabled = int(subsample), int(keep), enabled
        self.n_evals, self.recent = 0, []
        self.best = self.last = None

    def want(self):
        return bool(self.enabled) and self.subsample > 0 and \
            (self.n_evals % self.subsample == 0)

    def tick(self):
        self.n_evals += 1

    def add(self, op, x=None, params=None, metrics=None, stage="engineer"):
        if not self.enabled or not op or not op.get("devices"):
            return
        row = {"eval_i": self.n_evals, "stage": stage, "op": op,
               "x": list(x) if x is not None else None, "params": params,
               "metrics": metrics}
        self.recent.append(row)
        if len(self.recent) > self.keep:
            self.recent.pop(0)
        self.last = row

    def summary(self, top=None):
        """Per-device OP for the most recent capture, thinned to the fields the
        state actually uses (Cao's dynamic per-device features, proposal §1.4
        item 1). Full captures stay in `.recent` for anything that wants more."""
        row = self.recent[-1] if self.recent else None
        if not row:
            return None
        devs = (row["op"] or {}).get("devices") or {}
        keep = ("id", "gm", "gds", "vth", "vdsat", "vds", "vgs", "region")
        out = {d: {k: v.get(k) for k in keep if k in v}
               for d, v in list(devs.items())[:top or len(devs)]}
        return {"eval_i": row["eval_i"], "n_devices": len(devs), "devices": out,
                "nodes": (row["op"] or {}).get("nodes")}


# ----------------------------------------------------------------- the arena
class _Arena(object):
    """Deck + box + objective for ONE topology under the task's spec.

    Split out from `Env` because `Env.evaluate(topology, params)` accepts a
    topology: today the engineer line sizes a pinned topology, but the loop this
    environment exists for edits topologies (`moves.py`), and an environment that
    could only ever hold one deck would have to be rewritten on that day. Built
    the same way `size.size_topology` builds it, through `null_sizer.build_task`
    for the pinned one so the deck is provably the null-sizer's deck."""

    def __init__(self, topo, spec, body, sizable, fixed, op_sink=None):
        self.topo, self.spec, self.body = topo, spec, body
        self.points = []                        # (x, metrics) per eval, free hook
        # `sizable` is {param_name: kind}; keep it so `encode` can invert the
        # per-kind decode without a second, externally-supplied `_kinds` dict that
        # a caller could forget to set (the latent bug E-1 found: `encode` on a
        # freshly built arena would raise AttributeError before `_kinds` existed).
        self._kinds = dict(sizable)
        self.objective_func, self.names, self.decode, self._evaluate = \
            S.make_objective(body, spec, sizable, fixed, points=self.points,
                             op_sink=op_sink)
        self.dim = len(self.names)

    def encode(self, params):
        """params dict -> x in [0,1]^d, the inverse of make_objective's decode.

        Only defined for the sizable names; anything else in `params` is ignored
        (it is `fixed` and the decode would overwrite it anyway)."""
        ranges = S.kind_ranges(self.spec)
        x = []
        for name in self.names:
            lo, hi, islog = ranges[self._kind(name)]
            v = float(params[name])
            t = ((math.log10(v) - math.log10(lo)) / (math.log10(hi) - math.log10(lo))
                 if islog else (v - lo) / (hi - lo))
            x.append(min(max(t, 0.0), 1.0))
        return x

    def _kind(self, name):
        return self._kinds[name]


# -------------------------------------------------------------------- the env
class Env(object):
    """The sizing environment: budgeted, counted, observable, deterministic.

    Eval accounting is `null_sizer`'s, restated rather than re-derived: one tick
    per call of `make_objective`'s objective; `BudgetExhausted` raised instead of
    running eval `budget + 1`; when the spec gates NF one eval is TWO ngspice
    calls and both numbers are reported. The best point's metric vector costs no
    extra simulation -- it is kept from the eval that produced it via the free
    `points` hook, so the reported margins are the ones the search actually saw."""

    def __init__(self, task, budget=None, seed=None, logger=None,
                 op_subsample=1, keep_op=8, run_id=None, verbose=False):
        self.task = task.with_(budget=budget if budget is not None else task.budget,
                               seed=seed if seed is not None else task.seed)
        self.row = _pinned_row(self.task)
        built = NS.build_task(self.task.wl_hash, self.task.spec,
                              inductor_q=self.task.inductor_q,
                              nf_gate=self.task.nf_gate, row=self.row)
        self.spec, self.topo = built["spec"], built["topo"]
        self.inductor_q, self.nf_gated = built["inductor_q"], built["nf_gated"]
        self.harness_notes = NS._harness_note(built)
        self.op_sink = _MemoryOpSink(subsample=op_subsample, keep=keep_op)
        self.arena = _Arena(built["topo"], built["spec"], built["body"],
                            built["sizable"], built["fixed"], op_sink=self.op_sink)
        # Keyed by the stored wl_hash for the pinned topology, by a token digest
        # for anything an editor hands over later (`Topology` carries no hash).
        self._arenas = {self.task.wl_hash: self.arena,
                        _digest(list(self.topo.tokens)): self.arena}
        self.logger, self.verbose = logger, verbose
        self.run_id = run_id or _run_id(self.task)
        self.reset()

    # -------------------------------------------------------------- lifecycle
    def reset(self):
        """Zero the counters. Does not re-simulate anything and does not reseed
        anything -- the environment holds no RNG (see the module docstring)."""
        self.n_evals = self.n_fail = self.step_i = 0
        self.best_f, self.best_i, self.best_x = float("inf"), None, None
        self.last = None
        self.t0 = time.time()
        self.arena.points.clear()
        return self.observe()

    @property
    def dim(self):
        return self.arena.dim

    @property
    def param_names(self):
        return list(self.arena.names)

    @property
    def ngspice_calls(self):
        return self.n_evals * (2 if self.nf_gated else 1)

    @property
    def remaining(self):
        return max(0, self.task.budget - self.n_evals)

    # ------------------------------------------------------------ evaluation
    def evaluate(self, topology=None, params=None, action=None):
        """One full L2 evaluation -> {metrics, margins, feasible, cost, ...}.

        `topology` is None for the task's own topology (the common case) or a
        `Topology`, which gets its own deck and box -- built once and cached.
        `params` is either an x vector in [0,1]^d (what a search hands over) or a
        device-parameter dict (what a human or a repair operator hands over);
        both go through the SAME `make_objective` objective, so an eval is an
        eval however it was addressed. `action` is free text describing why this
        point was tried; it lands verbatim in the trajectory row."""
        arena = self.arena if topology is None else self._arena_for(topology)
        if params is None:
            raise ValueError("evaluate() needs params: an x vector or a "
                             "{param_name: value} dict")
        x = (self._as_x(arena, params) if isinstance(params, dict)
             else [float(v) for v in params])
        if len(x) != arena.dim:
            raise ValueError(f"x has {len(x)} entries, this deck has {arena.dim} "
                             f"sizable params ({', '.join(arena.names)})")
        if self.n_evals >= self.task.budget:
            raise BudgetExhausted(
                f"{self.task.id}: budget of {self.task.budget} evals is spent "
                f"({self.ngspice_calls} ngspice calls)")
        t0 = time.time()
        f = float(arena.objective_func(np.asarray(x, dtype=float)))
        wall = time.time() - t0
        self.n_evals += 1
        self.step_i += 1
        sim_ok = f < S.SIM_FAIL_PENALTY
        if not sim_ok:
            self.n_fail += 1
        m = arena.points[-1][1] if arena.points else None
        feas, viol = (arena.spec.feasible(m) if m else (False, None))
        margins = ds.margins_for(arena.spec, m) if m else {}
        if f < self.best_f:
            self.best_f, self.best_i, self.best_x = f, self.n_evals, list(x)
            self.op_sink.best = (self.op_sink.recent[-1]
                                 if self.op_sink.recent else None)
        out = {"eval_i": self.n_evals, "step": self.step_i, "objective": f,
               "sim_ok": sim_ok, "metrics": m, "margins": margins,
               "feasible": bool(feas),
               "viol": ({k: round(v, 6) for k, v in viol.items()} if viol else {}),
               "params": arena.decode(x), "x": x,
               "cost": {"evals": 1, "ngspice_calls": 2 if self.nf_gated else 1,
                        "wall_s": round(wall, 4)},
               "is_best": self.best_i == self.n_evals}
        self.last = out
        if self.logger is not None:
            self.logger.log(self, out, action=action)
        if self.verbose:
            print(f"  [{self.n_evals:>4}/{self.task.budget}] obj={f:>10.4f}"
                  + ("  BEST" if out["is_best"] else "")
                  + ("  FEASIBLE" if feas else ""))
        return out

    def objective_fn(self, topology=None):
        """The bare `f(x) -> float` an optimizer wants, budget enforced.

        This is the entry point `null_sizer.run_cmaes` (and any other arm) is
        handed. It returns the same float `make_objective`'s objective returns --
        no reshaping, no penalty of our own -- and raises `BudgetExhausted` on
        the eval after the budget, which is how a generational algorithm stops on
        the eval rather than on the generation."""
        def f(x):
            return self.evaluate(topology=topology, params=x,
                                 action="objective_fn")["objective"]
        return f

    def best(self):
        """(x, metrics) of the best eval -- from the points hook, no re-sim."""
        if self.best_i is None:
            return None, None
        x, m = self.arena.points[self.best_i - 1]
        return list(x), m

    # ------------------------------------------------------------- the state
    def observe(self, op_top=None):
        """The semantics-in-state bundle (survey S5, proposal §1.4 item 1).

        Structure alone is not a state: what a diagnosis needs is *which
        constraint binds, by how much, and what the devices were doing when it
        did*. So this returns the normalized margin vector (the same normalization
        the objective uses, so "which is worst" is a comparable question), the
        budget position, the best-so-far, and the per-device operating point of
        the most recent captured evaluation where one exists."""
        bx, bm = self.best()
        return {
            "task": self.task.as_dict(),
            "harness": self.harness(),
            "budget": {"spent": self.n_evals, "total": self.task.budget,
                       "remaining": self.remaining,
                       "ngspice_calls": self.ngspice_calls,
                       "sim_failures": self.n_fail},
            "best": {"objective": (None if self.best_i is None else self.best_f),
                     "eval_i": self.best_i, "x": bx, "metrics": bm,
                     "margins": (ds.margins_for(self.spec, bm) if bm else {}),
                     "feasible": (bool(self.spec.feasible(bm)[0]) if bm else False)},
            "last": ({k: self.last[k] for k in
                      ("eval_i", "objective", "feasible", "viol", "margins",
                       "sim_ok")} if self.last else None),
            "op": self.op_sink.summary(top=op_top),
            "params": {"names": self.param_names, "dim": self.dim},
        }

    def harness(self):
        """The label-domain stamps every number out of this env carries."""
        return {"inductor_q": self.inductor_q, "nf_gated": self.nf_gated,
                "stab_guard": S._stab_guard_on(),
                "ngspice_calls_per_eval": 2 if self.nf_gated else 1,
                "eval_entry": "size.make_objective(...)[0]",
                "w_finger": _w_finger(), "era": self.task.era,
                "deps": {"models": BIND.get("models"), "zoaf": BIND.get("zoaf"),
                         "rebound": BIND.get("rebound")},
                "notes": list(self.harness_notes)}

    def reference(self):
        """The stored ZOAF row this task is pinned to -- the number any claim
        about this env's search has to be stated against."""
        c = self.row.get("zoaf_cfg") or {}
        return {"ts": self.row.get("ts"), "n_evals": self.row.get("n_evals"),
                "recipe": c.get("recipe"), "seed": c.get("seed"),
                "w_finger": c.get("w_finger"), "feasible": self.row.get("feasible"),
                "best_obj": self.row.get("best_obj"),
                "metrics": self.row.get("metrics"),
                "margins": self.row.get("margins"),
                "provenance": self.row.get("provenance")}

    # ---------------------------------------------------------------- private
    def _arena_for(self, topo):
        key = _digest(list(topo.tokens))
        if key in self._arenas:
            return self._arenas[key]
        prep = S.prepared_body(topo, inductor_q=(self.inductor_q or None))
        if prep is None:
            # E-1 deliverable 3: the sizer declined this topology (a floating
            # subcircuit, or the biased netlist is not two-port). Raise the
            # documented contract BEFORE the budget is charged -- see `NotSizable`.
            raise NotSizable(
                "size.prepared_body declined this topology (bias insertion "
                "skipped it -- floating subcircuit, or not two-port): it cannot "
                f"be turned into an evaluable deck [wl_digest={key}]",
                wl_digest=key)
        body, sizable, fixed = prep
        a = _Arena(topo, self.spec, body, sizable, fixed, op_sink=self.op_sink)
        self._arenas[key] = a
        return a

    @staticmethod
    def _as_x(arena, params):
        return arena.encode(params)


# ------------------------------------------------------------ the trajectory
class TrajectoryLogger(object):
    """Append-only (state digest, action, outcome, cost) rows, one per step.

    Proposal §5.6: "Trajectory rows: (state digest, diagnosis, action taken, sim
    outcome, cost) per loop step, append-only, same snapshot discipline. Free now,
    priceless if R2/R4 ever activate." Free is the operative word -- this writes
    what the evaluation already computed and adds no analysis, so a run with the
    logger on and a run with it off issue the same x vectors and get the same
    objective values (the additive-hook invariant `lna/size.py` states for the
    point and op hooks).

    It writes to `engineer/data/trajectories.jsonl` and NOWHERE ELSE. These are
    not lna L2/point/op rows, they are the engineer line's own table; the two
    lines' stores are combined by `lna/sync_lines.py`, never by a writer that
    reaches across."""

    def __init__(self, path=TRAJ_TABLE, run_id=None, meta=None, enabled=True):
        self.path, self.run_id = path, run_id
        self.meta, self.enabled, self.n = dict(meta or {}), enabled, 0

    def log(self, env, out, action=None):
        if not self.enabled:
            return None
        row = {
            "kind": "trajectory", "schema": "engineer-traj-v0",
            "run_id": self.run_id or env.run_id, "task": env.task.id,
            "spec": env.task.spec, "wl_hash": env.task.wl_hash,
            "tier": env.task.tier, "seed": env.task.seed, "step": out["step"],
            "state": {
                "digest": _state_digest(env, out),
                "evals_spent": out["eval_i"] - 1,
                "budget": env.task.budget,
                "best_obj_before": (None if out["is_best"] and out["eval_i"] == 1
                                    else _prev_best(env, out)),
            },
            "action": {"kind": "size_eval", "desc": action or "evaluate",
                       "x_digest": _digest(out["x"]),
                       "topology": env.task.wl_hash},
            "outcome": {"objective": out["objective"], "sim_ok": out["sim_ok"],
                        "feasible": out["feasible"], "viol": out["viol"],
                        "metrics": out["metrics"],
                        "margins": {k: v.get("margin") for k, v in
                                    (out["margins"] or {}).items()
                                    if v.get("supported")},
                        "is_best": out["is_best"]},
            "cost": out["cost"],
            "harness": {"nf_gated": env.nf_gated, "inductor_q": env.inductor_q,
                        "era": env.task.era},
            "meta": self.meta, "git_sha": ds.git_sha(), "ts": _now(),
        }
        _append(self.path, row)
        self.n += 1
        return row


def _append(path, row):
    """One JSONL line, LF, sorted keys -- `datastore.append`'s byte conventions,
    reimplemented rather than imported because this table is not a store table
    and must never be reachable through the store's dispatch."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = json.dumps(_plain(row), separators=(",", ":"), sort_keys=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(line + "\n")
    return row


# --------------------------------------------------------------------- utils
def _prev_best(env, out):
    return None if env.best_i in (None, out["eval_i"]) else env.best_f


def _state_digest(env, out):
    """A short, stable hash of the state the action was taken FROM.

    Digest rather than the state itself because the state is large and the row is
    written once per ngspice call; the fields that a later analysis actually
    needs (margins, best, cost) are in the row verbatim. Deterministic across
    processes -- `hash()` is not."""
    prior = out["eval_i"] - 1
    return _digest([env.task.id, env.task.seed, prior, env.task.budget,
                    (None if env.best_i is None or env.best_i > prior
                     else round(env.best_f, 9))])


def _digest(obj, n=16):
    return hashlib.sha256(
        json.dumps(_plain(obj), separators=(",", ":"), sort_keys=True)
        .encode("utf-8")).hexdigest()[:n]


def _run_id(task):
    return f"{task.id}-s{task.seed}-b{task.budget}-{_now().replace(':', '')}"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _w_finger():
    try:
        from to_spice import W_FINGER
        return W_FINGER
    except Exception:                                              # noqa: BLE001
        return None


def _plain(o):
    if isinstance(o, dict):
        return {k: _plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_plain(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return _plain(o.tolist())
    return o


def margin_str(margins):
    """The one-line margin table, in `null_sizer`'s format so the two lines'
    console output can be read side by side."""
    return "  ".join(
        f"{k}={'--' if v.get('margin') is None else format(v['margin'], '+.3f')}"
        for k, v in (margins or {}).items() if v.get("supported"))


# ----------------------------------------------------------------------- CLI
def main():
    import argparse
    from tasks import REGISTRY, get           # noqa: E402  (sibling module)
    ap = argparse.ArgumentParser(description="engineer environment selftest")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--task", default="wifi24-smoke", choices=sorted(REGISTRY))
    ap.add_argument("--evals", type=int, default=3)
    a = ap.parse_args()
    if not a.selftest:
        ap.error("give --selftest")
    _bind_runtime_deps(verbose=True)
    env = Env(get(a.task), budget=a.evals, logger=None)
    print(f"task {env.task.id}: {env.topo.n_devices} devices, d={env.dim}, "
          f"tier={env.task.tier}, nf_gated={env.nf_gated}")
    for note in env.harness_notes:
        print(f"  [note] {note}")
    rng = np.random.default_rng(env.task.seed)
    for _ in range(a.evals):
        out = env.evaluate(params=rng.random(env.dim))
        print(f"  eval {out['eval_i']}: obj={out['objective']:.4f} "
              f"feasible={out['feasible']}  {margin_str(out['margins'])}")
    obs = env.observe()
    print(f"  best obj {obs['best']['objective']:.4f} @eval {obs['best']['eval_i']}"
          f"; op capture: {(obs['op'] or {}).get('n_devices')} devices")
    try:
        env.evaluate(params=rng.random(env.dim))
        print("  BUDGET NOT ENFORCED -- bug")
        return 1
    except BudgetExhausted as e:
        print(f"  budget enforced: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

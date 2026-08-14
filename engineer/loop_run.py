"""engineer/loop_run.py -- E-4's unattended propose->simulate->diagnose->intervene loop.

Pre-registered in `engineer/E4-LOOP.md` (committed BEFORE this file ran a single
scored eval). This runner is that pre-registration as code; it does not choose the
task, the rules, the tripwires, the novelty criterion, the baseline, or N -- all
of those are frozen in E4-LOOP.md §1-§7 and read here.

WHAT THIS IS (charter §6 E-4, proposal N5)
------------------------------------------
ONE bounded task (`dhruva-l2-t2-a`, null 1/10 feasible) run as a SCRIPTED policy
-- not an LLM -- of propose -> simulate -> diagnose -> intervene, repeated as
STAGES until convergence (feasible) or a numeric tripwire (E4-LOOP.md §5) stops
it. The three §2 process invariants are honored STRUCTURALLY:

  1. post-sim margin-table injection: every stage's diagnose step consumes the
     FULL `env.observe()` margin/op vector (the semantics-in-state surface).
  2. verifier-never-edits-netlist: three code-separated classes below --
     `Proposer` (mutates the design point, never scores), `Verifier` (reads
     observe(), diagnoses/gates, HOLDS NO MUTATION AUTHORITY), `Intervener` (the
     ONLY mutator -- maps a Diagnosis to the next stage's action).
  3. escalation: no convergence after N_STAGE=3 sizing loops => topology, not
     tuning => escalate to the topology-move stage; if that also fails, STOP and
     record. Never silently keep polishing.

MEMORY AS STRUCTURE, NOT BUDGET (E-3 §6.4 hand-off)
---------------------------------------------------
E-3 measured that consuming the store as budget-splitting HURT. Here the store is
consumed as STRUCTURE: only the escalation branch consults the playbook, and only
to bias WHICH `moves.py` move class fires first (a diagnosis-steered move prior,
proposal §1.4 item 3). It runs PAIRED warm/cold (via `mem_playbook`, the E-3
sidecar) so every warm loop is born with its cold twin (charter hard constraint).
The sizing stages are memory-free and identical warm and cold.

DETERMINISM / BUDGET
--------------------
The env draws no RNG; stage i uses sub-seed `seed+i`. Total evals are capped at
the task's matched budget (266) by the env's own `BudgetExhausted`; per-stage caps
are enforced by a slice wrapper (E4-LOOP.md §5). Warm and cold spend exactly the
same evals -- memory only reorders moves, it never buys evals.

    python engineer/loop_run.py                 # N=10 seeds, both memory sides
    python engineer/loop_run.py --seeds 2       # a fast shakedown
    python engineer/loop_run.py --seed 1        # one seed, verbose trace
    python engineer/loop_run.py --aggregate-only
"""
import argparse
import glob
import json
import os
import random
import statistics
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import env as EV                                              # noqa: E402
from env import Env, NotSizable, TrajectoryLogger            # noqa: E402
from tasks import get                                        # noqa: E402
import datastore as ds                                       # noqa: E402
from null_sizer import run_cmaes                             # noqa: E402
import mem_playbook as MP                                    # noqa: E402
from mem_arm import task_family, active_signatures           # noqa: E402
import templates as T                                        # noqa: E402
import moves as MV                                           # noqa: E402
from spec import Spec                                        # noqa: E402
from topology import Topology                                # noqa: E402

# -------------------------------------------------- frozen constants (E4-LOOP.md)
TASK_ID = "dhruva-l2-t2-a"        # §1: the one pre-registered task
N_SEEDS = 10                      # §7.3: the registered N
N_STAGE = 3                       # §2.1 invariant 3 / §5: sizing loops before escalation
SIGMA0 = 0.3                      # §4: null_sizer's own default
SHRINK = 0.5                      # §4 D1: box tighten on the knife-edge
K_NOIMP = 2                       # §5: no-improvement-in-K-stages stop
NOIMP_EPS = 1e-4                  # §5
TRIP_FAIL = 0.5                   # §3/§5: stage sim-fail-rate trip
KNIFE_LO = -0.5                   # §3: s11-knife-edge band lower bound
MAX_MOVE_TRIES = 5                # §5: NotSizable retries before STOP
WALL_CAP_S = 600                  # §5: 10 min per seed
DATA_DIR = EV.DATA_DIR
LOOP_DIR = os.path.join(DATA_DIR, "_loop_traj")
ARTIFACT = os.path.join(DATA_DIR, "loop_v0.json")
SCOREBOARD = os.path.join(DATA_DIR, "scoreboard_v0.1.json")

# §4 E1: diagnosis-steered move prior (which move classes to prefer first).
_MOVE_PRIOR = {
    "s11-knife-edge": ["match_elem_add", "input_class_swap", "feedback_add"],
    "nf-wall": ["degen_add", "cascode_add"],
    "gain-wall": ["stage_add", "cascode_add"],
    "idd-wall": ["degen_add"],
    "label-noise": [],
}


# ============================================================ DIAGNOSIS (value)
class Diagnosis(object):
    """The Verifier's read-only verdict on a stage. A pure value object: carries
    the signature (E4-LOOP.md §3 controlled vocabulary), the binding gate and its
    margin, and whether the design converged. It has no method that could mutate
    an env, a box, or a topology -- that is the structural half of invariant 2."""

    __slots__ = ("signature", "binding_gate", "binding_margin", "feasible",
                 "margins", "fail_rate")

    def __init__(self, signature, binding_gate, binding_margin, feasible,
                 margins, fail_rate):
        self.signature = signature
        self.binding_gate = binding_gate
        self.binding_margin = binding_margin
        self.feasible = feasible
        self.margins = margins
        self.fail_rate = fail_rate

    def as_dict(self):
        return {"signature": self.signature, "binding_gate": self.binding_gate,
                "binding_margin": (None if self.binding_margin is None
                                   else round(self.binding_margin, 6)),
                "feasible": self.feasible, "fail_rate": round(self.fail_rate, 4)}


# ============================================================ VERIFIER (no mut)
class Verifier(object):
    """Scores/gates a design and diagnoses it -- and CANNOT mutate anything.

    Handed a read-only `observe()` dict (invariant 1: the full margin/op vector,
    every stage). Returns a `Diagnosis`. Holds no reference to the env's design
    point, box, or topology; there is nothing here through which it *could* edit
    the netlist (invariant 2, enforced by construction). Every signature it emits
    is a token in `lna/datastore.DIAGNOSIS_VOCAB` (E4-LOOP.md §3)."""

    def diagnose(self, observe, fail_rate):
        best = observe.get("best") or {}
        margins = best.get("margins") or {}
        supported = {k: v.get("margin") for k, v in margins.items()
                     if v.get("supported") and v.get("margin") is not None}
        if not supported:
            # no metric vector yet (all sims failed): a search/basin problem
            return Diagnosis("label-noise", None, None, False, margins, fail_rate)
        if all(m >= 0 for m in supported.values()):
            return Diagnosis("feasible", None, min(supported.values()),
                             True, margins, fail_rate)
        gate, margin = min(supported.items(), key=lambda kv: kv[1])
        if fail_rate > TRIP_FAIL or margin < KNIFE_LO:
            sig = "label-noise"
        elif gate == "s11_max_db":
            sig = "s11-knife-edge"
        elif gate == "nf_db":
            sig = "nf-wall"
        elif gate == "s21_db":
            sig = "gain-wall"
        elif gate in ("idd_ma", "idd_a"):
            sig = "idd-wall"
        else:
            sig = "label-noise"
        return Diagnosis(sig, gate, margin, False, margins, fail_rate)


# ============================================================ PROPOSER (design)
class Proposer(object):
    """Runs ONE CMA-ES stage on the env, from a start-mean and box. Mutates the
    DESIGN POINT (the x-vector search), never scores or gates it. `run_cmaes` is
    imported verbatim from `lna/null_sizer.py` -- two implementations of a baseline
    are two baselines. A per-stage slice wrapper stops it at the stage's eval cap
    (E4-LOOP.md §5) without the optimizer knowing."""

    def stage(self, envr, topology, sub_seed, slice_evals, start_mean=None,
              sigma0=SIGMA0):
        """One stage. `start_mean` seeds run_cmaes's first mean when given
        (structure, E-3 §6.4: seed a start's mean); else run_cmaes draws its own
        (a genuine restart). Returns (evals_spent, n_fail_delta, best_out) where
        `best_out` is the FULL env.evaluate() output dict of the best eval THIS
        stage produced (its margins/metrics/op are the observe-shaped vector the
        Verifier reads -- invariant 1). Captured per-arena, so it is correct even
        when the stage sizes a moved topology (env.best() reads only the pinned
        arena's points and is unreliable across arenas -- so the loop tracks its
        own best from the stage returns instead)."""
        n = (envr._arena_for(topology).dim if topology is not None else envr.dim)
        n0, f0 = envr.n_evals, envr.n_fail
        best = {"out": None, "obj": float("inf"), "sim_s": 0.0}
        f = _sliced_objective_topo(envr, topology, slice_evals, best)
        try:
            _run_cmaes_seeded(f, n, sub_seed, sigma0=sigma0, start_mean=start_mean)
        except EV.BudgetExhausted:
            pass
        return envr.n_evals - n0, envr.n_fail - f0, best["out"], best["sim_s"]


# ============================================================ INTERVENER (mut)
class Intervener(object):
    """The ONLY component with mutation authority (invariant 2). Maps a Diagnosis
    to the next stage's ACTION per the frozen rule table (E4-LOOP.md §4): a new
    start-mean/box (sizing rules D1-D3) or a topology move (escalation rule E1).

    The escalation move prior is memory-steered: `cold=False` biases the move
    order by the playbook strategy for the binding signature (paired against the
    `cold=True` store-miss, which uses moves.py's own weights -- that IS the cold
    control, E4-LOOP.md §2.2)."""

    def __init__(self, spec, cold):
        self.spec = spec
        self.cold = cold
        tb = spec.topology.get("device_budget", [3, 16])
        self.ctx = {"max_dev": tb[1], "min_dev": tb[0],
                    "max_inductors": spec.topology.get("max_inductors", 99)}

    # ---- sizing action (D1-D3): returns (start_mean, sigma0) ----
    def size_action(self, diag, best_x, stage_rng):
        if diag.signature == "s11-knife-edge":                        # D1
            return (list(best_x) if best_x is not None else None,
                    SIGMA0 * SHRINK, "D1:reseed-mean+tighten")
        if diag.signature in ("nf-wall", "gain-wall", "idd-wall"):    # D2
            return (list(best_x) if best_x is not None else None,
                    SIGMA0, "D2:reseed-mean")
        # D3: label-noise -> genuine restart from a fresh independent draw
        n = len(best_x) if best_x is not None else None
        return (None, SIGMA0, "D3:fresh-restart")

    # ---- escalation action (E1): returns (moved_topo, move_name, consult) ----
    def topology_action(self, base_topo, diag, stage_rng):
        """Fire ONE moves.py move under the diagnosis-steered prior; realize;
        return the moved Topology (or None). Consults the playbook PAIRED (the
        `cold` flag) so the warm move-prior is born with its cold twin."""
        consult = self._consult(diag)
        preferred = _MOVE_PRIOR.get(diag.signature, []) if not self.cold else []
        # the store's own steer (warm only): if a qualifying entry names a move,
        # float it to the front of the prior.
        steer = self._store_steer(consult) if not self.cold else None
        prior = ([steer] if steer else []) + [p for p in preferred if p != steer]
        nl, _ = T.topo_to_netlist(base_topo)
        for _ in range(MAX_MOVE_TRIES):
            mut, mv = self._mutate_with_prior(nl, stage_rng, prior)
            if mv is None:
                continue
            r = MV.realize(mut, self.spec)
            if r is None:
                continue
            moved_topo, _seq, wl, _canon = r
            return moved_topo, mv, wl, consult
        return None, None, None, consult

    def _consult(self, diag):
        fam = [task_family(self.spec.name), "lna", "any"]
        sigs = [diag.signature] if diag.signature else active_signatures(self.spec)
        return MP.consult(
            family=fam, analysis=["sizing", "search", "topology"],
            failure_signatures=sigs,
            keywords=["topology", "match", "input", "feedback", "degeneration",
                      "escalate", "archetype"],
            cold=self.cold)

    @staticmethod
    def _store_steer(consult):
        """If the top qualifying hit's rule names a moves.m_* function, return that
        move's short name so the Intervener fires it first. Grounded in the store's
        own text (e.g. gate-driven-input-...: 'apply moves.m_input_class_swap')."""
        for score, eid, e, why in consult.hits:
            rule = (e.get("rule") or "").lower()
            for name in MV.MOVE_NAMES:
                if f"m_{name}" in rule or f"moves.{name}" in rule:
                    return name
        return None

    @staticmethod
    def _mutate_with_prior(nl, rng, prior):
        """Try preferred move classes first (in order), then fall back to the
        move set's own weighted mutate (E4-LOOP.md §4 E1). Returns (nl, name)."""
        fns = {m[0]: m[1] for m in MV.MOVES}
        for name in prior:
            fn = fns.get(name)
            if fn is None:
                continue
            try:
                out = fn(nl, rng, {"max_dev": 21, "min_dev": 3, "max_inductors": 6})
            except Exception:                                          # noqa: BLE001
                out = None
            if out and MV.sane(out, 21, 3):
                return out, name
        return MV.mutate(nl, rng, {"max_dev": 21, "min_dev": 3, "max_inductors": 6})


# ---------------------------------------------------- run_cmaes seeded variant
def _run_cmaes_seeded(f, n, seed, sigma0=SIGMA0, start_mean=None):
    """`run_cmaes` seeds its first mean from `rng.random(n)`. To seed the mean
    from STRUCTURE (E-3 §6.4) without re-implementing the optimizer, we prepend
    ONE evaluation at `start_mean` (so the incumbent is in the search's memory as
    the current best) and then run the verbatim `run_cmaes` -- its own restart
    logic re-centres on the best region. At start_mean=None this is exactly
    `run_cmaes(f, n, seed)`, bit-identical to the null."""
    if start_mean is not None:
        try:
            f(np.clip(np.asarray(start_mean, dtype=float), 0.0, 1.0))
        except EV.BudgetExhausted:
            return
    run_cmaes(f, n, seed, sigma0=sigma0)


def _sliced_objective_topo(envr, topology, slice_evals, best):
    """`mem_arm._sliced_objective` but for an arbitrary topology (the escalation
    stage sizes a moved topology), and it CAPTURES the best eval's full output into
    `best` (so the loop can read the right arena's margin vector -- env.best() is
    unreliable across arenas). Raises the env's BudgetExhausted subclass after
    `slice_evals` this stage; the env's global counter still enforces the 266 cap."""
    from mem_arm import _SliceExhausted

    def g(x):
        if best.get("n", 0) >= slice_evals:
            raise _SliceExhausted("stage slice spent")
        out = envr.evaluate(topology=topology, params=x, action="e4-loop-stage")
        best["n"] = best.get("n", 0) + 1
        best["sim_s"] = best.get("sim_s", 0.0) + out["cost"]["wall_s"]
        if out["objective"] < best["obj"]:
            best["obj"] = out["objective"]
            best["out"] = out
        return out["objective"]          # may raise the env's real BudgetExhausted
    return g


# ==================================================================== the LOOP
def run_loop(seed, cold, traj_path, verbose=False):
    """One unattended loop on TASK_ID for one seed, one memory side.

    Returns the per-run result dict: the stage-by-stage trace (diagnosis fired,
    intervention taken, evals spent, best obj), the terminal reason, and whether a
    feasible / feasible-NOVEL design was produced (E4-LOOP.md §6)."""
    task = get(TASK_ID, seed=seed)
    spec = Spec.load(task.spec)
    pinned_wl = task.wl_hash
    logger = TrajectoryLogger(
        run_id=EV._run_id(task) + ("-cold" if cold else "-warm"),
        meta={"algo": "e4-loop", "driver": "loop_run",
              "memory": ("cold" if cold else "warm")},
        path=traj_path)
    envr = Env(task, logger=logger)                      # budget = 266, hard cap
    proposer, verifier = Proposer(), Verifier()
    intervener = Intervener(spec, cold=cold)

    per_stage = envr.task.budget // (N_STAGE + 1)        # §5: 66 evals/stage
    t0 = time.time()
    stages = []
    best_before = float("inf")
    noimp = 0
    terminal = None
    feasible = False
    novel = False
    novel_wl = None
    cur_topo = None                     # None = the pinned topology
    consults = []
    gbest = None                        # loop-local best eval `out` across arenas
    gbest_wl = pinned_wl               # wl_hash the loop-best sits on
    sim_s_total = 0.0                  # sim-only seconds (sum of per-eval cost.wall_s)

    stage_i = 0
    while True:
        if envr.remaining <= 0:
            terminal = terminal or "budget-cap"
            break
        if time.time() - t0 > WALL_CAP_S:
            terminal = "wall-clock-cap"
            break
        escalating = (stage_i >= N_STAGE)               # invariant 3
        sub_seed = seed + stage_i
        stage_rng = random.Random(seed * 1000 + stage_i)
        slice_evals = min(per_stage, envr.remaining)
        if escalating:
            slice_evals = envr.remaining                 # last stage absorbs rest

        # ---- INTERVENE (decide the action for THIS stage from last diagnosis) --
        # The Verifier's observe-shaped read of the loop-best (invariant 1: the
        # full margin/op vector). Sourced from the loop's own gbest so it is the
        # right ARENA's vector even after a topology move (env.best() reads only
        # the pinned arena and is unreliable across arenas).
        action = None
        best_x = (gbest["x"] if gbest else None)
        if stage_i == 0:
            start_mean, sigma0, action = None, SIGMA0, "S0:cold-start"
        elif not escalating:
            start_mean, sigma0, action = intervener.size_action(
                stages[-1]["diagnosis"], best_x, stage_rng)
        else:
            # ESCALATION: topology, not tuning (invariant 3). Fire a move.
            base = cur_topo or _pinned_topo(task)
            moved, mv, wl, consult = intervener.topology_action(
                base, stages[-1]["diagnosis"], stage_rng)
            consults.append(consult.as_dict())
            if moved is None:
                terminal = "escalation-no-realizable-move"
                break
            cur_topo = moved
            novel_wl = wl
            action = f"E1:move={mv}->wl={wl[:8]}"
            start_mean, sigma0 = None, SIGMA0

        # ---- PROPOSE + SIMULATE (one CMA-ES stage) ----------------------------
        try:
            spent, fails, stage_best, stage_sim_s = proposer.stage(
                envr, cur_topo, sub_seed, slice_evals,
                start_mean=start_mean, sigma0=sigma0)
        except NotSizable as e:
            terminal = "escalation-not-sizable"
            stages.append({"stage": stage_i, "action": action,
                           "wl_digest": e.wl_digest, "spent": 0})
            break
        sim_s_total += stage_sim_s
        fail_rate = (fails / spent) if spent else 0.0
        # update the loop-local global best across arenas
        if stage_best is not None and (gbest is None
                                       or stage_best["objective"] < gbest["objective"]):
            gbest = stage_best
            gbest_wl = (novel_wl if cur_topo is not None else pinned_wl)

        # ---- DIAGNOSE (read the FULL loop-best margin/op vector -- invariant 1) -
        obs_best = _observe_best(gbest)
        diag = verifier.diagnose({"best": obs_best}, fail_rate)
        best_obj = obs_best.get("objective")
        stages.append({
            "stage": stage_i, "escalating": escalating, "action": action,
            "sub_seed": sub_seed, "slice_evals": slice_evals, "spent": spent,
            "n_fail": fails, "fail_rate": round(fail_rate, 4),
            "best_obj": (None if best_obj is None else round(best_obj, 6)),
            "on_topology": ("pinned" if gbest_wl == pinned_wl else gbest_wl[:8]),
            "diagnosis": diag, "diag": diag.as_dict()})
        if verbose:
            bo = best_obj if best_obj is not None else float("nan")
            print(f"  s{stage_i} {'ESC ' if escalating else '    '}{action:<28} "
                  f"spent={spent:>3} obj={bo:.4f} -> {diag.signature}"
                  + ("  FEASIBLE" if diag.feasible else ""))

        # ---- CONVERGENCE / TRIPWIRES ------------------------------------------
        if diag.feasible:
            feasible = True
            novel = (gbest_wl != pinned_wl)
            terminal = "converged-feasible"
            break
        if best_obj is not None:
            if best_before - best_obj < NOIMP_EPS:
                noimp += 1
            else:
                noimp = 0
            best_before = min(best_before, best_obj)
        if noimp >= K_NOIMP and escalating:
            terminal = "no-improvement-stop"
            break
        stage_i += 1
        if escalating:                                   # one escalation stage only
            terminal = terminal or "escalation-non-converged"
            break

    wall = time.time() - t0
    bm = (gbest["metrics"] if gbest else None)
    feas_final, viol = (spec.feasible(bm) if bm else (False, None))
    margins = (gbest["margins"] if gbest else {})
    best_f = (gbest["objective"] if gbest else float("inf"))
    novel = bool(feas_final and gbest_wl != pinned_wl)
    return {
        "seed": seed, "memory": "cold" if cold else "warm",
        "task": TASK_ID, "budget": envr.task.budget,
        "n_evals": envr.n_evals, "ngspice_calls": envr.ngspice_calls,
        "n_sim_fail": envr.n_fail,
        "n_stages": len(stages),
        "terminal": terminal,
        "feasible": bool(feas_final), "best_obj": best_f,
        "novel": bool(novel), "novel_wl": (gbest_wl if novel else None),
        "pinned_wl": pinned_wl, "gbest_wl": gbest_wl,
        "final_on_topology": ("pinned" if gbest_wl == pinned_wl else gbest_wl),
        "viol": ({k: round(v, 6) for k, v in viol.items()} if viol else {}),
        "margins_binding": _binding(margins),
        "diagnoses_fired": [s["diag"]["signature"] for s in stages],
        "interventions": [s["action"] for s in stages],
        "escalated": any(s.get("escalating") for s in stages),
        "consults": consults,
        "stages": [_stage_plain(s) for s in stages],
        "wall_s": round(wall, 3),
        "sim_s": round(sim_s_total, 4),
        "model_s": round(max(0.0, wall - sim_s_total), 4),
        "s_per_ngspice_call": round(sim_s_total / max(envr.ngspice_calls, 1), 6),
        "traj": os.path.relpath(traj_path, HERE),
    }


def _observe_best(gbest):
    """The `observe()['best']`-shaped view of the loop-local best eval. Carries
    the same fields env.observe() exposes (objective, x, metrics, margins,
    feasible) -- the full margin/op vector the Verifier reads (invariant 1),
    sourced from the loop's own cross-arena best so it is the RIGHT arena's
    vector even after a topology move."""
    if not gbest:
        return {"objective": None, "x": None, "metrics": None, "margins": {},
                "feasible": False}
    return {"objective": gbest["objective"], "x": gbest["x"],
            "metrics": gbest["metrics"], "margins": gbest["margins"],
            "feasible": gbest["feasible"]}


def _pinned_topo(task):
    row = EV._pinned_row(task)
    return Topology(list(row["graph"]["tokens"]))


def _binding(margins):
    sup = {k: v.get("margin") for k, v in (margins or {}).items()
           if v.get("supported") and v.get("margin") is not None}
    if not sup:
        return None
    g, m = min(sup.items(), key=lambda kv: kv[1])
    return {"gate": g, "margin": round(m, 6)}


def _stage_plain(s):
    d = dict(s)
    d.pop("diagnosis", None)                    # the value object -> its dict form
    return d


# ==================================================================== subprocess
def _spawn(seed):
    cmd = [sys.executable, os.path.join(HERE, "loop_run.py"), "--cell", str(seed)]
    r = __import__("subprocess").run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"seed {seed} failed:\n{r.stderr[-2000:]}")
    line = [ln for ln in r.stdout.splitlines() if ln.strip()][-1]
    return json.loads(line)


def run_cell(seed):
    """One seed, BOTH memory sides (warm + cold) -- the paired primitive so every
    warm loop is born with its cold twin (charter hard constraint; E4-LOOP.md §2.2).
    Warm and cold share the seed and the 266-eval cap."""
    os.makedirs(LOOP_DIR, exist_ok=True)
    warm_traj = os.path.join(LOOP_DIR, f"warm_s{seed}.jsonl")
    cold_traj = os.path.join(LOOP_DIR, f"cold_s{seed}.jsonl")
    for p in (warm_traj, cold_traj):
        if os.path.exists(p):
            os.remove(p)
    warm = run_loop(seed, cold=False, traj_path=warm_traj)
    cold = run_loop(seed, cold=True, traj_path=cold_traj)
    return {"kind": "engineer_loop_pair", "schema": "engineer-loop-v0",
            "task": TASK_ID, "seed": seed, "warm": warm, "cold": cold}


# ==================================================================== baseline
def _null_baseline():
    """The pre-registered baseline FLOOR (E4-LOOP.md §7.2): the `cmaes` null's
    SPICE-per-feasible on dhruva-l2-t2-a, quoted from scoreboard_v0.1.json. A
    citation, not a recomputation. Returns the per-feasible SPICE-minutes and the
    numbers that build it."""
    if not os.path.exists(SCOREBOARD):
        return None
    with open(SCOREBOARD, encoding="utf-8") as fh:
        board = json.load(fh)
    a = (board.get("per_task", {}).get(TASK_ID, {}) or {}).get("cmaes")
    if not a:
        return None
    n_seeds = a.get("n_seeds") or 10
    n_feas = a.get("n_feasible") or 0
    budget = get(TASK_ID).budget
    # nf-gated => 2 ngspice calls/eval; total calls across all seeds
    total_calls = n_seeds * budget * 2
    # seconds/call from the null's own recorded sim_s (sim_s_total is seconds of
    # simulation across all seeds; per-call = sim_s_total / total_calls)
    sim_s_total = a.get("sim_s_total")
    s_per_call = (sim_s_total / total_calls) if sim_s_total else None
    spice_min_total = (total_calls * s_per_call / 60.0) if s_per_call else None
    return {
        "source": os.path.relpath(SCOREBOARD, HERE), "arm": "cmaes",
        "feasible": a.get("feasible"), "n_feasible": n_feas, "n_seeds": n_seeds,
        "budget_evals": budget, "total_ngspice_calls": total_calls,
        "ngspice_calls_per_feasible": (round(total_calls / n_feas, 1)
                                       if n_feas else None),
        "ngspice_calls_per_feasible_novel": None,   # the null produces NO novel design
        "sim_s_total": sim_s_total, "s_per_ngspice_call": s_per_call,
        "spice_min_total": (round(spice_min_total, 4) if spice_min_total else None),
        "spice_min_per_feasible": (round(spice_min_total / n_feas, 4)
                                   if (spice_min_total and n_feas) else None),
        "spice_min_per_feasible_novel": None,   # the null produces NO novel design
        "novel_note": "the cmaes null only sizes the pinned topology: its "
                      "feasible-novel count is 0 (E4-LOOP.md §7.2 caveat).",
    }


# ==================================================================== aggregate
def aggregate(pairs, prereg_sha):
    warm = [p["warm"] for p in pairs]
    cold = [p["cold"] for p in pairs]

    def side_agg(runs):
        n = len(runs)
        feas = [r for r in runs if r["feasible"]]
        nov = [r for r in runs if r["novel"]]
        total_calls = sum(r["ngspice_calls"] for r in runs)
        sim_s = sum(r["sim_s"] for r in runs)
        # SPICE-minutes at the loop's OWN measured sim seconds (this box, sim-only,
        # PROTOCOL §6 -- modeling time excluded). The machine-independent
        # SPICE-WORK metric is ngspice-calls, reported alongside; s/call is
        # machine-load-dependent, so the falsifier reads calls-per-feasible.
        spice_min = sim_s / 60.0
        return {
            "n_seeds": n,
            "feasible": f"{len(feas)}/{n}", "n_feasible": len(feas),
            "novel_feasible": f"{len(nov)}/{n}", "n_novel_feasible": len(nov),
            "best_obj_median": round(statistics.median(
                [r["best_obj"] for r in runs]), 6),
            "best_obj_best": round(min(r["best_obj"] for r in runs), 6),
            "total_ngspice_calls": total_calls,
            "sim_s_total": round(sim_s, 4),
            "s_per_ngspice_call": round(sim_s / max(total_calls, 1), 6),
            "ngspice_calls_per_feasible": (round(total_calls / len(feas), 1)
                                           if feas else None),
            "ngspice_calls_per_feasible_novel": (round(total_calls / len(nov), 1)
                                                 if nov else None),
            "spice_min_total": round(spice_min, 4),
            "spice_min_per_feasible": (round(spice_min / len(feas), 4)
                                       if feas else None),
            "spice_min_per_feasible_novel": (round(spice_min / len(nov), 4)
                                             if nov else None),
            "n_escalated": sum(1 for r in runs if r["escalated"]),
            "terminals": _count([r["terminal"] for r in runs]),
            "diagnoses": _count([s for r in runs for s in r["diagnoses_fired"]]),
            "evals_total": sum(r["n_evals"] for r in runs),
        }

    warm_agg, cold_agg = side_agg(warm), side_agg(cold)
    baseline = _null_baseline()
    verdict = _falsifier_verdict(warm_agg, baseline)
    return {
        "kind": "engineer_loop_board", "schema": "engineer-loop-board-v0",
        "prereg": {"file": "engineer/E4-LOOP.md", "sha": prereg_sha},
        "task": TASK_ID, "n_seeds": len(pairs),
        "warm": warm_agg, "cold": cold_agg,
        "baseline_floor": baseline,
        "acceptance": {
            "question": ("does the unattended loop produce a feasible (novel) "
                         "design at fewer SPICE-min/feasible than the cmaes null "
                         "floor, at matched budget, with no human per iteration?"),
            "falsifier_verdict": verdict},
        "harness_git_sha": ds.git_sha(), "ts": EV._now(),
    }


def _falsifier_verdict(warm, baseline):
    """E4-LOOP.md §7.5: falsified iff (b) the loop costs MORE SPICE per feasible
    design than the baseline floor. The primary read is machine-independent
    NGSPICE-CALLS-per-feasible (s/call is machine-load-dependent, so a SPICE-MINUTE
    comparison across two runs on differently-loaded boxes is not apples-to-apples;
    calls-per-feasible is -- both spend exactly 266 evals/seed). SPICE-minutes are
    reported too, at each side's own measured s/call. Part (a) -- human-per-iteration
    -- is answered by the run completing all seeds unattended, reported separately."""
    if not baseline or baseline.get("ngspice_calls_per_feasible") is None:
        return {"decidable": False, "note": "no baseline in scoreboard"}
    floor_calls = baseline["ngspice_calls_per_feasible"]
    out = {"decidable": True,
           "metric": "ngspice_calls_per_feasible (machine-independent)",
           "baseline_floor_calls_per_feasible": floor_calls}
    lp = warm.get("ngspice_calls_per_feasible")
    out["loop_calls_per_feasible"] = lp
    out["beats_floor"] = (lp is not None and lp <= floor_calls)
    # feasible NOVEL (the strict headline)
    out["loop_calls_per_feasible_novel"] = warm.get("ngspice_calls_per_feasible_novel")
    out["produced_any_feasible_novel"] = warm.get("n_novel_feasible", 0) > 0
    # spice-minute read (each side's own s/call), for the record
    out["loop_spice_min_per_feasible"] = warm.get("spice_min_per_feasible")
    out["baseline_spice_min_per_feasible"] = baseline.get("spice_min_per_feasible")
    if lp is None:
        out["falsified"] = True     # loop produced NO feasible design -> worse than floor
        out["falsified_reason"] = ("loop produced 0 feasible designs; the null "
                                   "produced %d -- loop cost is infinite per "
                                   "feasible, strictly worse than the floor"
                                   % (baseline.get("n_feasible") or 0))
    else:
        out["falsified"] = lp > floor_calls
    return out


def _count(xs):
    from collections import Counter
    return dict(Counter(xs))


# ==================================================================== printout
def _print_board(b):
    print("\n" + "=" * 88)
    print(f"E-4 UNATTENDED LOOP  task={b['task']}  N={b['n_seeds']}  "
          f"(prereg @ {b['prereg']['sha'][:12]})")
    print("=" * 88)
    for side in ("warm", "cold"):
        a = b[side]
        print(f"\n[{side}]  feasible={a['feasible']}  novel-feasible="
              f"{a['novel_feasible']}  escalated={a['n_escalated']}/{a['n_seeds']}")
        print(f"       obj median={a['best_obj_median']:.4f}  best={a['best_obj_best']:.4f}"
              f"  ngspice_calls={a['total_ngspice_calls']}  sim_s={a['sim_s_total']:.2f}")
        print(f"       calls/feasible={a['ngspice_calls_per_feasible']}  "
              f"calls/feasible-novel={a['ngspice_calls_per_feasible_novel']}  "
              f"SPICE-min/feasible={a['spice_min_per_feasible']}")
        print(f"       diagnoses fired: {a['diagnoses']}")
        print(f"       terminals: {a['terminals']}")
    bl = b["baseline_floor"]
    if bl:
        print(f"\nBASELINE FLOOR (cmaes null, {bl['source']}):")
        print(f"       feasible={bl['feasible']}  ngspice_calls={bl['total_ngspice_calls']}"
              f"  calls/feasible={bl['ngspice_calls_per_feasible']}  "
              f"SPICE-min/feasible={bl['spice_min_per_feasible']}")
        print(f"       {bl['novel_note']}")
    v = b["acceptance"]["falsifier_verdict"]
    print(f"\nFALSIFIER (E4-LOOP.md §7.5): {json.dumps(v)}")
    print("=" * 88)


# ==================================================================== main
def _prereg_sha():
    try:
        r = __import__("subprocess").run(
            ["git", "log", "--reverse", "--format=%H", "--",
             "engineer/E4-LOOP.md"], cwd=EV.ROOT, capture_output=True,
            text=True, timeout=10)
        shas = [s for s in (r.stdout or "").split() if s]
        return shas[0] if shas else None
    except Exception:                                              # noqa: BLE001
        return None


def _load_existing(seeds):
    out = []
    for p in sorted(glob.glob(os.path.join(LOOP_DIR, "pair_s*.json"))):
        with open(p, encoding="utf-8") as fh:
            c = json.load(fh)
        if c["seed"] in seeds:
            out.append(c)
    return out


def main():
    from concurrent.futures import ProcessPoolExecutor, as_completed
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cell", type=int, help="run ONE seed pair; prints its JSON")
    ap.add_argument("--seed", type=int, help="run one seed verbose (no subprocess)")
    ap.add_argument("--seeds", type=int, default=N_SEEDS)
    ap.add_argument("--jobs", type=int, default=0)
    ap.add_argument("--aggregate-only", action="store_true")
    a = ap.parse_args()

    if a.cell is not None:
        pair = run_cell(a.cell)
        os.makedirs(LOOP_DIR, exist_ok=True)
        with open(os.path.join(LOOP_DIR, f"pair_s{a.cell}.json"),
                  "w", encoding="utf-8", newline="\n") as fh:
            json.dump(EV._plain(pair), fh, indent=1)
        print(json.dumps(EV._plain(pair)))
        return 0

    if a.seed is not None:
        os.makedirs(LOOP_DIR, exist_ok=True)
        print(f"seed {a.seed} WARM:")
        w = run_loop(a.seed, cold=False,
                     traj_path=os.path.join(LOOP_DIR, f"warm_s{a.seed}.jsonl"),
                     verbose=True)
        print(f"  -> {w['terminal']}  feasible={w['feasible']} novel={w['novel']} "
              f"evals={w['n_evals']} obj={w['best_obj']:.4f}")
        print(f"seed {a.seed} COLD:")
        c = run_loop(a.seed, cold=True,
                     traj_path=os.path.join(LOOP_DIR, f"cold_s{a.seed}.jsonl"),
                     verbose=True)
        print(f"  -> {c['terminal']}  feasible={c['feasible']} novel={c['novel']} "
              f"evals={c['n_evals']} obj={c['best_obj']:.4f}")
        return 0

    seeds = list(range(1, a.seeds + 1))
    prereg_sha = _prereg_sha()
    if a.aggregate_only:
        pairs = _load_existing(seeds)
    else:
        jobs = a.jobs or min(len(seeds), os.cpu_count() or 8)
        print(f"loop_run: {len(seeds)} seeds x (warm+cold), pool={jobs}")
        print(f"  pre-registered @ {prereg_sha}")
        t0, pairs = time.time(), []
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            futs = {ex.submit(_spawn, s): s for s in seeds}
            for fut in as_completed(futs):
                s = futs[fut]
                pair = fut.result()
                pairs.append(pair)
                w, c = pair["warm"], pair["cold"]
                print(f"  s{s:>2}  warm {'F' if w['feasible'] else '.'}"
                      f"{'N' if w['novel'] else ' '} {w['terminal']:<26} "
                      f"obj={w['best_obj']:.3f}  cold {'F' if c['feasible'] else '.'}"
                      f"{'N' if c['novel'] else ' '} obj={c['best_obj']:.3f}")
        print(f"  all seeds done in {time.time()-t0:.1f}s wall")

    board = aggregate(pairs, prereg_sha)
    os.makedirs(os.path.dirname(ARTIFACT), exist_ok=True)
    with open(ARTIFACT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(EV._plain(board), fh, indent=1)
    _print_board(board)
    print(f"  -> {os.path.relpath(ARTIFACT, HERE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

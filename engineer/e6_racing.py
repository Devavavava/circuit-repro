"""engineer/e6_racing.py -- the E-6 racing arm (B): triage k short starts, cull to
top-1, warm-resume the survivor on the whole remaining budget.

Pre-registered in `engineer/E6-BUDGET.md` §2 (committed BEFORE this file ran a
single eval). This file is that rule as code and nothing more; it does not choose
k, r, or the culling rule -- they are the doc's numbers.

THE MECHANISM (E6-BUDGET.md §2.1), and why a VERBATIM `run_cmaes` can express it
--------------------------------------------------------------------------------
`lna/null_sizer.run_cmaes` takes NO injectable start-mean (each restart begins at
`rng.random(n)`); E-3 §2.2 hit the same wall. But `run_cmaes(f, n, seed)` is
DETERMINISTIC in the seed, and a longer-budget run is a bit-identical PREFIX
superset of a shorter run with the same seed (verified pre-reg). So:

  1. TRIAGE: for i in 0..k-1, run sub-seed seed+i for exactly r env-evals (stopped
     by the E-3 `_sliced_objective` per-start wrapper -> env's own BudgetExhausted,
     transparent to run_cmaes). Cache each start's (x, objective) triage points.
  2. CULL: survivor = the sub-seed with the best (lowest) objective in its r evals.
     Rule: TOP-1 (E6-BUDGET.md §2.2 -- top-2 would halve the survivor budget and
     re-fragment, the exact E-3/E-4 failure).
  3. WARM-RESUME: re-invoke run_cmaes(seed+winner) with an objective that REPLAYS
     the winner's r cached triage points (NO ngspice, NO env eval) for its first r
     calls and forwards to the real env after. The replayed prefix is bit-identical
     (deterministic seed), so the survivor's search continues PAST eval r into the
     remaining budget as ONE continuous CMA-ES trajectory -- a faithful warm resume.

BUDGET (E6-BUDGET.md §3, matched to the incumbent EXACTLY): triage spends k*r env
evals; resume adds (budget - k*r) NEW env evals; the survivor's first r evals are
cache-replayed, NOT re-simulated, so they are counted ONCE (as triage). Total env
evals = k*r + (budget - k*r) = budget. The env's own counter raises
BudgetExhausted on the eval after budget, so exactly `budget` evals are spent.

At k=1 the arm reduces to run_cmaes(f, n, seed) -- the incumbent (arm A), bit for
bit (the E-3 K=1 discipline).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import env as EV                                              # noqa: E402
from env import BudgetExhausted                               # noqa: E402
from null_sizer import run_cmaes                              # noqa: E402


# --------------------------------------------------- the frozen k/r/cull rule
K_STARTS = 4                       # E6-BUDGET.md §2.3
CULL_TO = 1                        # top-1 (E6-BUDGET.md §2.2)


def triage_evals(budget, k=K_STARTS):
    """r = min(60, max(15, round(0.15*budget/k))) -- E6-BUDGET.md §2.3, frozen."""
    return int(min(60, max(15, round(0.15 * budget / k))))


# ------------------------------------------------ per-start budget slicing
class _SliceExhausted(BudgetExhausted):
    """Raised by the per-start wrapper when a start has spent its r-eval slice.

    Subclasses the env's own BudgetExhausted so run_cmaes (which catches nothing)
    stops the SAME way it stops on the real budget -- transparent to the imported
    optimizer. Same shape as E-3's `mem_arm._SliceExhausted`."""


def _triage_objective(envr, slice_evals, cache):
    """The env objective, capped at `slice_evals` THIS start, caching (x, f) of
    every eval it makes so the survivor's prefix can be replayed later. Forwards
    the env's real BudgetExhausted too. The env's global counter/best are the
    env's own -- this only adds the per-start cap + the cache."""
    f = envr.objective_fn()
    state = {"n": 0}

    def g(x):
        if state["n"] >= slice_evals:
            raise _SliceExhausted("triage slice spent")
        val = f(x)                        # may raise the env's real BudgetExhausted
        cache.append((list(map(float, x)), float(val)))
        state["n"] += 1
        return val
    return g


def _resume_objective(envr, replay):
    """The env objective for the warm-resume, replaying the survivor's cached
    triage points for the first len(replay) calls (NO env eval, NO ngspice) then
    forwarding to the real env. The replayed x-sequence is bit-identical to what
    the survivor already did (deterministic seed), so the CMA-ES trajectory is
    continuous across the triage/resume boundary. Asserts the replayed x matches
    the cached x to the digit -- a mismatch means the prefix property broke and is
    a harness bug, raised loudly, never absorbed."""
    f = envr.objective_fn()
    state = {"n": 0}

    def g(x):
        i = state["n"]
        state["n"] += 1
        if i < len(replay):
            cx, cf = replay[i]
            xl = [float(v) for v in x]
            if any(abs(a - b) > 1e-12 for a, b in zip(xl, cx)):
                raise RuntimeError(
                    f"E-6 resume replay MISMATCH at eval {i}: the survivor's "
                    f"re-run x diverged from its cached triage x (prefix-property "
                    f"broken -> harness bug). cached={cx} replay={xl}")
            return cf                     # served from cache: no env eval spent
        return f(x)                       # may raise the env's real BudgetExhausted
    return g


# --------------------------------------------------------- the racing arm
def run_racing(envr, seed, diag=None, k=K_STARTS):
    """Racing arm B on `envr` (E6-BUDGET.md §2). Returns envr.best_f.

    Triage k sub-seeds (seed..seed+k-1) for r evals each; cull to top-1; warm-resume
    the survivor on the whole remaining budget. Exactly `budget` env evals total."""
    diag = {} if diag is None else diag
    n = envr.dim
    k = max(1, int(k))
    budget = envr.task.budget
    r = triage_evals(budget, k)
    diag.update(arm="racing", K=k, r=r, cull_to=CULL_TO, budget=budget,
                triage_budget=k * r, starts=[])

    # ---- Phase 1: triage. Each start gets exactly r evals; cache its points. ----
    caches = []
    for i in range(k):
        sub = seed + i
        cache = []
        d = {}
        try:
            run_cmaes(_triage_objective(envr, r, cache), n, sub, diag=d)
        except BudgetExhausted:                    # triage slice OR real budget
            pass
        best_f = min((f for _x, f in cache), default=float("inf"))
        best_i = (min(range(len(cache)), key=lambda j: cache[j][1])
                  if cache else None)
        caches.append(cache)
        diag["starts"].append({"sub_seed": sub, "triage_evals": len(cache),
                               "triage_best": (None if best_i is None else best_f),
                               "triage_best_eval": best_i,
                               "gens": d.get("gens")})
        if envr.remaining <= 0:                    # budget already gone (tiny task)
            break

    # ---- Phase 2: cull to top-1. Survivor = lowest triage-best objective. ----
    scored = [(s["triage_best"], idx) for idx, s in enumerate(diag["starts"])
              if s["triage_best"] is not None]
    if not scored:                                 # no start produced a point
        diag.update(winner=None, resume_evals=0)
        return envr.best_f
    winner = min(scored)[1]
    diag.update(winner=int(winner), winner_sub_seed=int(seed + winner),
                winner_triage_best=scored[[i for _f, i in scored].index(winner)][0]
                if False else min(scored)[0])

    # ---- Phase 3: warm-resume the survivor on the whole remaining budget. ----
    replay = caches[winner]
    resume_before = envr.n_evals
    try:
        run_cmaes(_resume_objective(envr, replay), n, seed + winner)
    except BudgetExhausted:
        pass
    diag["resume_evals"] = envr.n_evals - resume_before
    diag["n_evals_total"] = envr.n_evals
    return envr.best_f

"""engineer/mem_arm.py -- the `pb-cmaes` arm: playbook-informed multi-start CMA-ES.

The simplest honest memory-consuming arm defensible against what the v0 store
ACTUALLY contains (40 qualitative engineering entries, not numeric priors). Its
rule is pre-registered in `engineer/E3-MEMORY.md` 2.2; this file is that rule as
code and nothing more.

WHAT IT CONSUMES FROM MEMORY
----------------------------
One question, asked once at initialization: does the store hold a sizing/search
strategy that prescribes a SEEDED, MULTI-START initialization? The store's own
answer is `search-must-be-seeded-from-physics` (*"Seed a multi-start search ...
use best-of-all-coordinates rather than first-improvement descent"*). A qualifying
hit's retrieval score maps (E3-MEMORY.md 2.2) to a start count K in {2,4,6}; a
store-miss maps to K=1.

THE ARM = K-START CMA-ES, REDUCING EXACTLY TO THE NULL AT K=1
------------------------------------------------------------
K CMA-ES starts, each given an EQUAL slice of the task budget (floor(budget/K)
evals, the remainder handed to the last start so the full budget is always spent),
each seeded from a distinct sub-seed derived from the base seed; the env keeps the
GLOBAL best across all starts ("best-of-all-coordinates"). Each start is
`lna/null_sizer.run_cmaes`, IMPORTED verbatim -- never re-implemented (two
implementations of a baseline are two baselines) -- stopped at its slice boundary
by a per-start budget wrapper that raises the env's own `BudgetExhausted`. At
**K=1 the slice is the whole budget and the arm is a single
`run_cmaes(f, n, seed)` -- bit-identical to the registered `cmaes` null**. So the
cold twin (empty store => no qualifying hit => K=1) reduces to the plain null by
construction; that reduction IS the cold control.

Budget is compute-matched (PROTOCOL 2): the env's own counter raises
`BudgetExhausted` on the eval after the budget, so warm (K starts) and cold (1
start) each spend EXACTLY `budget` evals -- memory must earn its multi-start cost
inside the same envelope.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import env as EV                                              # noqa: E402
from env import BudgetExhausted                               # noqa: E402
from null_sizer import run_cmaes                              # noqa: E402
import mem_playbook as MP                                     # noqa: E402


# --------------------------------------------------------- family / signatures
_FAMILY_ALIASES = {"gps-l1": "gps", "gps": "gps"}


def task_family(spec_name):
    """Spec name -> the family token the playbook indexes on."""
    base = spec_name.split("-")[0] if spec_name.startswith("dhruva") else spec_name
    if spec_name.startswith("dhruva"):
        return "dhruva"
    return _FAMILY_ALIASES.get(spec_name, spec_name)


def active_signatures(spec):
    """The task's ACTIVE failure signatures, derived from its gated constraints
    (E3-MEMORY.md 2.1). Only signatures in playbook.py's controlled vocabulary."""
    sigs = []
    cons = spec.constraints

    def gated(name):
        c = cons.get(name)
        return bool(c) and c.get("status") != "unsupported"

    if gated("nf_db"):
        sigs.append("nf-wall")
    if gated("s11_db"):
        sigs.append("s11-knife-edge")
    if gated("idd_ma") or gated("idd_a"):
        sigs.append("bias-regulation")
    return sigs


# --------------------------------------------------------- the consult + K
def consult_for_task(spec, cold=False):
    """Consult the playbook for this task (E3-MEMORY.md 2.1). Returns a Consult."""
    fam = [task_family(spec.name), "lna", "any"]
    return MP.consult(
        family=fam,
        analysis=["sizing", "search"],
        failure_signatures=active_signatures(spec),
        keywords=["multi-start", "seed", "coordinate", "descent", "idd"],
        cold=cold,
    )


# --------------------------------------------------------- the search itself
class _SliceExhausted(BudgetExhausted):
    """Raised by the per-start wrapper when a start has spent its budget SLICE.

    Subclasses the env's own BudgetExhausted so run_cmaes (which catches nothing
    -- baseline_run/random_run catch it) stops the SAME way it stops on the real
    budget: the wrapper is transparent to the imported optimizer."""


def _sliced_objective(envr, slice_evals):
    """A view of the env objective that raises _SliceExhausted after `slice_evals`
    evals THIS start, and forwards the env's real BudgetExhausted too. The env's
    global counter/best are untouched -- only the per-start cap is added."""
    f = envr.objective_fn()
    state = {"n": 0}

    def g(x):
        if state["n"] >= slice_evals:
            raise _SliceExhausted("start slice spent")
        val = f(x)                      # may raise the env's real BudgetExhausted
        state["n"] += 1
        return val
    return g


def run_pb_cmaes(envr, seed, consult, diag=None):
    """K-start CMA-ES on `envr` (E3-MEMORY.md 2.2). K = consult.k.

    Each start gets an equal slice floor(budget/K) of evals (the last start gets
    the remainder so the full budget is always spent); starts use sub-seeds
    seed, seed+1, ..., seed+K-1; the env keeps the GLOBAL best across every start.
    At K=1 the slice is the whole budget and the single sub-seed is `seed`, so the
    arm is bit-identical to run_cmaes(f, n, seed) -- the `cmaes` null."""
    diag = {} if diag is None else diag
    n = envr.dim
    k = max(1, int(consult.k))
    budget = envr.task.budget
    base_slice = budget // k
    diag.update(K=k, qualifying=(consult.qualifying or None),
                store_n_entries=consult.fingerprint["n_entries"],
                store_sha256=consult.fingerprint["sha256"], cold=consult.cold,
                base_slice=base_slice, starts=[])
    for i in range(k):
        sub = seed + i
        # the last start absorbs the remainder so exactly `budget` evals are spent
        this_slice = (budget - envr.n_evals) if i == k - 1 else base_slice
        if this_slice <= 0:
            break
        d = {}
        try:
            run_cmaes(_sliced_objective(envr, this_slice), n, sub, diag=d)
        except BudgetExhausted:                    # slice OR real budget
            pass
        diag["starts"].append({"sub_seed": sub, "slice": this_slice,
                               "gens": d.get("gens"), "restarts": d.get("restarts")})
        if envr.remaining <= 0:
            break
    diag["n_starts_run"] = len(diag["starts"])
    return envr.best_f

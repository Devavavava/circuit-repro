"""Sim-health observability golden: the failure channel COUNTS and NAMES.

Why this exists (2026-09-03, sim-health observability landing): ngspice sim
failures were swallowed by SIM_FAIL_PENALTY inside the sizing objective (a
bptm45-era robustness choice), campaign rows carried no sim-failure channel, and
the funnel golden gates COMPLETION only (it merely prints `fails=`). On sky130
~every sizing eval was a fatal BSIM4-binning abort, yet the loop recorded only
"0/24 infeasible" -- the record could not tell an ENVIRONMENT wall from a DESIGN
wall. The binning is fixed; this observability channel is the commissioned fix.

This golden gates the OBSERVABILITY MECHANISM (not any campaign outcome), at the
cheapest level -- the objective wrapper `size.make_objective` returns:

  A. FATAL DECK -> the channel fires. A deck that references a missing model
     card (every eval a fatal ngspice abort) drives a `SimHealth` sink to
     n_sim_fail == n_evals > 0 AND captures ONE VERBATIM ngspice error line
     (extract.first_error_line), so a failure is both COUNTED and NAMED.

  B. ADDITIVE-HOOK INVARIANT. The same objective, evaluated with the sink
     attached and without it, returns BYTE-IDENTICAL values at every point --
     the sink only reads the pass/fail the objective already decided, so it
     cannot move the search, the score, or any existing number.

  C. HEALTHY DECK -> the channel stays quiet. A real bptm45 sizing objective
     (the funnel corpus topology) records n_sim_fail == 0 and sim_error == None,
     so the channel does not cry wolf on a working environment.

It does NOT change any existing golden's gating (funnel `fails=` stays a print,
not a gate -- that would be a behavior change). Exit 0 iff GREEN.

    python lna/ref/check_simhealth.py            # exit 0 iff GREEN
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(LNA, ".."))
for _p in (LNA, os.path.join(ROOT, "misc", "ZOAF")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                        # noqa: E402
import extract as E                       # noqa: E402
import size as S                          # noqa: E402
import solve_spec as SS                   # noqa: E402
from spec import Spec                     # noqa: E402
from topology import Topology             # noqa: E402

# A fatal but well-formed sizable deck: a single MOS on a model card that does
# not exist, so ngspice aborts on the .include before any analysis. Every eval
# fails identically -- the deterministic fatal case the channel must catch.
_FATAL_BODY = (
    ".include /nonexistent/obs_simhealth_missing_models.txt\n"
    "M1 outnode gnode 0 0 nch_missing w={pM1W} l=45n\n"
    "R1 innode gnode {pR1V}\n"
)
_FATAL_SIZABLE = {"pM1W": "W", "pR1V": "R"}
_XS = [np.array([0.3, 0.4]), np.array([0.6, 0.5]), np.array([0.9, 0.1])]


def _check_fatal(spec):
    """A: a fatal deck fires the channel (counted) AND names it (verbatim)."""
    health = S.SimHealth()
    obj, _names, _dec, _ev = S.make_objective(
        _FATAL_BODY, spec, _FATAL_SIZABLE, {}, sim_health=health)
    for x in _XS:
        obj(x)
    d = health.as_dict()
    ok = (d["n_evals"] == len(_XS) and d["n_sim_fail"] == len(_XS)
          and isinstance(d["sim_error"], str) and d["sim_error"])
    print("  [A] fatal deck: n_evals=%s n_sim_fail=%s   sim_error=%r"
          % (d["n_evals"], d["n_sim_fail"], d["sim_error"]))
    print("      -> %s (failure both COUNTED and NAMED)" % ("ok" if ok else "FAIL"))
    return ok


def _check_invariant(spec):
    """B: the objective is byte-identical with the sink attached and without."""
    health = S.SimHealth()
    obj_h, _n, _d, _e = S.make_objective(
        _FATAL_BODY, spec, _FATAL_SIZABLE, {}, sim_health=health)
    obj_n, _n2, _d2, _e2 = S.make_objective(
        _FATAL_BODY, spec, _FATAL_SIZABLE, {})
    vh = [obj_h(x) for x in _XS]
    vn = [obj_n(x) for x in _XS]
    ok = vh == vn
    print("  [B] additive-hook invariant: sink=%s  no-sink=%s" % (vh, vn))
    print("      -> %s (objective value unchanged by the sink)"
          % ("ok" if ok else "FAIL"))
    return ok


def _check_healthy(spec):
    """C: a real bptm45 sizing objective records no sim failures (no false alarm).

    Uses the funnel-golden corpus topology on bptm45 (always present -- the 45 nm
    card is resolved by extract.resolve_models), a few evals through the same
    make_objective + SimHealth path the loop uses."""
    wl, topo, _toks = _easiest_corpus_topology()
    prep = S.prepared_body(topo, inductor_q=SS.INDUCTOR_Q, pdk="bptm45")
    if prep is None:
        print("  [C] SKIP: bptm45 bias-insert skipped for corpus topology %s" % wl[:8])
        return True                       # not a failure of the channel
    body, sizable, fixed = prep
    if not sizable:
        print("  [C] SKIP: no sizable params for corpus topology %s" % wl[:8])
        return True
    health = S.SimHealth()
    obj, names, _dec, _ev = S.make_objective(
        body, spec, sizable, fixed, sim_health=health)
    rng = np.random.default_rng(1)
    for _ in range(6):
        obj(rng.random(len(names)))
    d = health.as_dict()
    ok = d["n_sim_fail"] == 0 and d["sim_error"] is None and d["n_evals"] == 6
    print("  [C] healthy bptm45 deck (%s): n_evals=%s n_sim_fail=%s sim_error=%r"
          % (wl[:8], d["n_evals"], d["n_sim_fail"], d["sim_error"]))
    print("      -> %s (channel silent on a working environment)"
          % ("ok" if ok else "FAIL"))
    return ok


def _easiest_corpus_topology():
    """The fewest-device stored corpus topology (same pick as the funnel golden)."""
    best = None
    for wl in SS.CORPUS:
        try:
            toks = SS.tokens_for(wl)
        except SystemExit:
            continue
        topo = Topology(list(toks))
        if best is None or topo.n_devices < best[1].n_devices:
            best = (wl, topo, list(toks))
    if best is None:
        raise SystemExit("no CORPUS topology resolved (missing topo_labels?)")
    return best


def main():
    spec = Spec.load(os.path.join(ROOT, "lna", "specs", "wifi24.yaml"))
    print("check_simhealth: sim-health observability channel")
    results = [_check_fatal(spec), _check_invariant(spec), _check_healthy(spec)]
    ok = all(results)
    print("\ncheck_simhealth: %s" % ("GREEN" if ok else "RED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

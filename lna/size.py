"""ZOAF sizing loop (WP-SIZE, plans/05-SIZING.md).

Per candidate topology (post-bias, L1-conducting), turn the .param surface into a
vector x in [0,1]^d, and let ZOAF drive ngspice toward the spec's objective:

    x  --(log/linear map per param kind)-->  device values
       --> extract.run_and_extract --> metrics --> spec.objective (feasibility-first)

ZOAF MAXIMISES, so the driver maximises `-spec.objective`: every feasible point
(objective < 0) beats every infeasible one (objective >= 1), and among feasible
points more objective improvement wins. Params are normalised to [0,1]^d and
mapped log-scale for W/R/C/L, linear for bias voltages.

The headline test (§3.1) is the anchor re-derivation: strip the stage-B reference
to defaults, hand the sizer its topology + wifi24, and check ZOAF reaches
feasibility near the hand-tuned numbers -- it validates extract.py, the objective
encoding, and ZOAF's budget at once on a circuit whose answer is known.

    python lna/size.py --anchor            # re-derive the stage-B reference vs wifi24

NF is treated as `unsupported` here (the port-source noise reference is unreliable
with gain -- WORKLOG R3); the sizer gates on S11 / S21 / Idd, which extract.py
measures solidly. Enable finite inductor Q in the deck for physical inductors.
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "misc", "ZOAF")))
import extract as E  # noqa: E402
from spec import Spec  # noqa: E402
from zoaf.zoaf_core import ZOAF  # noqa: E402  (generic core; the *param variants pull PySpice)

# spec.objective is minimised feasibility-first (>=1 infeasible, <0 feasible), so a
# failed simulation must score worse than any infeasible point.
SIM_FAIL_PENALTY = 1e3


def kind_ranges(spec):
    # PyYAML parses exponentials without a decimal point (20e3, 10e-12) as
    # strings, so coerce every bound to float.
    sz, topo = spec.sizing, spec.topology
    f = float
    return {   # kind: (lo, hi, log?)
        "W":  (f(sz["w_um"][0]) * 1e-6, f(sz["w_um"][1]) * 1e-6, True),
        "L":  (f(topo.get("l_min", 0.3e-9)), f(topo.get("l_max", 12e-9)), True),
        "R":  (f(sz["r_ohm"][0]), f(sz["r_ohm"][1]), True),
        "C":  (f(sz["c_f"][0]), f(sz["c_f"][1]), True),
        "VB": (f(sz["vb_v"][0]), f(sz["vb_v"][1]), False),
    }


def make_objective(body, spec, sizable, fixed):
    """sizable: {param_name: kind}; fixed: {param_name: literal}. Returns
    (objective_func for ZOAF, names, decode(x)->metrics helper)."""
    names = list(sizable)
    ranges = kind_ranges(spec)

    def decode(x):
        params = dict(fixed)
        for xi, name in zip(x, names):
            lo, hi, islog = ranges[sizable[name]]
            xi = float(min(max(xi, 0.0), 1.0))
            v = (10 ** (math.log10(lo) + xi * (math.log10(hi) - math.log10(lo)))
                 if islog else lo + xi * (hi - lo))
            params[name] = f"{v:.6g}"
        return params

    def evaluate(x):
        return E.run_and_extract(body, decode(x), spec)

    def objective_func(x):
        m = evaluate(x)
        return SIM_FAIL_PENALTY if m is None else spec.objective(m)

    return objective_func, names, decode, evaluate


def run_zoaf(objective_func, names, seed=1, n_candidates=8, sgd_iters=8, cgd_iters=2):
    bounds = np.array([[0.0, 1.0]] * len(names))   # x normalised; decode maps to values
    opt = ZOAF(objective_func, bounds, maximize=False, n_candidates=n_candidates,
               n_starts=4, sampling="hybrid", sgd_iterations=sgd_iters,
               sgd_K=2, sgd_lr=0.3, sgd_mu=0.1, cgd_iterations=cgd_iters,
               cgd_lr=0.5, cgd_mu=0.3, seed=seed)
    res = opt.optimize()
    return res.x_best, res.f_best, res.n_evals


def size_anchor(spec_name="wifi24", seed=1):
    spec = Spec.load(spec_name)
    # NF gate off (harness gap, WORKLOG R3): treat as unsupported for sizing
    if "nf_db" in spec.constraints:
        spec.constraints["nf_db"]["status"] = "unsupported"
        print("note: nf_db treated as unsupported (port-noise harness gap); "
              "gating on S11/S21/Idd.")

    body = E.body_of(os.path.join(HERE, "ref", "ref24_csdeg.cir"))
    sizable = {"pW": "W", "pLs": "L", "pLg": "L", "pLd": "L",
               "pCex": "C", "pCtnk": "C", "pVB": "VB", "pVB2": "VB"}
    fixed = {"pL": "45n", "pRB": "10k", "pQ": "10", "pF0": "2.442e9",
             "pRq": "{2*3.14159265*pF0*pLd/pQ}"}

    obj, names, decode, evaluate = make_objective(body, spec, sizable, fixed)
    print(f"anchor re-derivation vs {spec_name}: {len(names)} params, "
          f"ZOAF (feasibility-first).")
    best_x, best_obj, n_evals = run_zoaf(obj, names, seed=seed)

    m = evaluate(best_x)
    feas, viol = spec.feasible(m)
    print(f"\nZOAF: {n_evals} sims, best objective {best_obj:.4f}")
    print(spec.report(m))
    print("\nsized values:")
    for k, v in decode(best_x).items():
        if k in sizable:
            print(f"    {k:<7} {v}")
    print(f"\n=> {'FEASIBLE' if feas else 'infeasible: ' + str({k: round(v,3) for k,v in viol.items()})}"
          "  [anchor re-derivation]")
    return feas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchor", action="store_true",
                    help="run the stage-B anchor re-derivation test")
    ap.add_argument("--spec", default="wifi24")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    if args.anchor:
        ok = size_anchor(args.spec, seed=args.seed)
        return 0 if ok else 1
    ap.error("give --anchor (candidate sizing not wired yet)")


if __name__ == "__main__":
    sys.exit(main())

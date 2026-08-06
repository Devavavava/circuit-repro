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


def classify_params(nl):
    """From a bias-inserted Netlist, split .param names into sizable (kind) and
    fixed (literal). Widths/R/C/L values and inserted bias voltages are sized;
    channel length, bias-feed R, supplies stay fixed."""
    from topology import base_of
    sizable, fixed = {}, {}
    for d in sorted(nl.t.devices):
        b = base_of(d)
        if b in ("NM", "PM"):
            sizable[f"p{d}W"] = "W"
            fixed[f"p{d}L"] = "45n"
        elif b == "R":
            sizable[f"p{d}V"] = "R"
        elif b == "C":
            sizable[f"p{d}V"] = "C"
        elif b == "L":
            sizable[f"p{d}V"] = "L"
    for p, v in nl.extra_params.items():
        (sizable.__setitem__(p, "VB") if p.startswith("pVBG")
         else fixed.__setitem__(p, v))
    fixed["pVDD"] = "1.1"
    fixed["pVB"] = "0.5"
    return sizable, fixed


def size_topology(topo, spec, seed=1, n_candidates=6, sgd_iters=6, cgd_iters=1):
    """Bias-insert, then ZOAF-size a generated topology against `spec`."""
    import bias
    nl, inserter, rep, swept = bias.insert_bias(topo, sweep=True)
    if rep.get("skipped") or not nl.two_port:
        return None
    body = E.body_of(nl.emit())
    sizable, fixed = classify_params(nl)
    if not sizable:
        return None
    obj, names, decode, evaluate = make_objective(body, spec, sizable, fixed)
    best_x, best_obj, n_evals = run_zoaf(obj, names, seed=seed,
                                         n_candidates=n_candidates,
                                         sgd_iters=sgd_iters, cgd_iters=cgd_iters)
    m = evaluate(best_x)
    if m is None:
        return {"metrics": None, "feasible": False, "n_evals": n_evals}
    feas, viol = spec.feasible(m)
    return {"metrics": m, "feasible": feas, "viol": viol, "n_evals": n_evals,
            "best_obj": best_obj, "n_params": len(names)}


def _spec_for_sizing(name):
    """Load a spec with nf_db gated off (port-noise harness gap, WORKLOG R3)."""
    spec = Spec.load(name)
    if "nf_db" in spec.constraints:
        spec.constraints["nf_db"]["status"] = "unsupported"
    return spec


def scoreboard(directory, spec_name="wifi24", seed=1, max_candidates=4):
    """Size the top spec-passing candidates in a generation dir end-to-end.

    The program's headline: spec in, novel generated topology -> bias -> ZOAF
    sized -> scored. (NF gated off pending the harness fix.)"""
    import glob
    from topology import Topology, parse_arrow_file
    from novelty import corpus_reference, wl_features
    spec = _spec_for_sizing(spec_name)
    corpus_hashes, _ = corpus_reference()

    cands = []
    for f in sorted(glob.glob(os.path.join(directory, "seq*.txt"))):
        topo = Topology(parse_arrow_file(f))
        if not spec.structural_screen(topo)[0]:
            continue
        novel = wl_features(topo)[0] not in corpus_hashes
        cands.append((os.path.basename(f), topo, novel))
        if len(cands) >= max_candidates:
            break

    print(f"sizing {len(cands)} spec-passing candidates from {directory} vs "
          f"{spec_name} (nf gated off)\n")
    print(f"{'candidate':<12} {'novel':>5} {'dev':>3} {'sims':>5} "
          f"{'S11':>7} {'S21':>7} {'Idd':>6} {'feasible':>9}")
    n_feas = 0
    for name, topo, novel in cands:
        res = size_topology(topo, spec, seed=seed)
        if res is None or res["metrics"] is None:
            print(f"{name:<12} {str(novel):>5} {topo.n_devices:>3}   "
                  f"{'-':>5}  (bias/sim failed)")
            continue
        m = res["metrics"]
        n_feas += int(res["feasible"])
        print(f"{name:<12} {str(novel):>5} {topo.n_devices:>3} {res['n_evals']:>5} "
              f"{m['s11_db']:>7.1f} {m['s21_db']:>7.1f} {m.get('idd_ma') or 0:>6.2f} "
              f"{'FEASIBLE' if res['feasible'] else 'no':>9}")
    print(f"\n{n_feas}/{len(cands)} feasible (Gate G4 needs >=1 novel + feasible; "
          "S21 ceiling is the topology, finding #10)")
    return n_feas


def size_anchor(spec_name="wifi24", seed=1):
    spec = _spec_for_sizing(spec_name)
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
    ap.add_argument("--scoreboard", metavar="DIR",
                    help="size the top spec-passing candidates in a generation dir")
    ap.add_argument("--spec", default="wifi24")
    ap.add_argument("--n", type=int, default=4, help="max candidates for --scoreboard")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    if args.anchor:
        return 0 if size_anchor(args.spec, seed=args.seed) else 1
    if args.scoreboard:
        scoreboard(args.scoreboard, args.spec, seed=args.seed, max_candidates=args.n)
        return 0
    ap.error("give --anchor or --scoreboard DIR")


if __name__ == "__main__":
    sys.exit(main())

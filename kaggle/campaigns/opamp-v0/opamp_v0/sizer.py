"""opamp-v0 sizer: seeded deterministic CMA-ES over W/L/R/C/IREF with matched groups.

The optimizer is REUSED BY IMPORT, unmodified: `lna/null_sizer.py::run_cmaes`
(Hansen purecmaes defaults, [0,1]^n box by clipping, restart on stagnation, numpy
PCG64 seeded) driven through `null_sizer._Budget` (the repo's one-tick-per-eval
counter that hard-stops on the budget). This is the same CMA-ES the LNA path's
`kaggle/bench_anchor_prep.smoke_run` calls; `smoke_run` itself cannot be driven for
an op-amp (its measurement is the LNA S-parameter path), so only the optimizer and
the counter are reused (README D-O1).

Objective modes (minimised; CMA-ES is rank-based, so only the order matters):
  margin   feasible iff every hard constraint is met (and the design is valid);
           infeasible  f = 1 + sum of normalized violations,
           feasible    f = -1 - worst normalized margin  (maximise the worst margin)
  max:M    maximise metric M subject to the hard constraints;
           infeasible  f = 1 + sum of normalized violations (as above),
           feasible    f = -1 - (pi/2 + atan(M))           (monotone in M, < -1)
  invalid designs (testbench flags, testbench.INVALID_FLAGS) rank below every valid
  design: f = 100 + 10 * n_flags + sum_viol / 10; a failed simulation is 1e3
  (lna/size.SIM_FAIL_PENALTY, which _Budget counts as a failure).
Normalized margin of a constraint (repo convention, lna/datastore.margins_for):
  min bound (val - min)/scale, max bound (max - val)/scale, scale = max(|limit|, 1).
"""
import math
import os
import resource
import sys
import time

from . import dialect as DL
from . import testbench as TB

sys.path.insert(0, os.path.join(TB.REPO, "lna"))
import null_sizer as NS   # noqa: E402  (read-only reuse: run_cmaes, _Budget, _BudgetOut)

PROFILE = "opamp-v0"
SIM_FAIL = NS.S.SIM_FAIL_PENALTY      # 1e3
RANGES = {                             # (lo, hi) SI, log-scaled
    "W": (0.5e-6, 50e-6),
    "L": (45e-9, 1e-6),
    "R": (10.0, 100e3),
    "C": (0.05e-12, 20e-12),
    "IREF": (1e-6, 100e-6),
}
DEFAULT_EVALS = 2500
VIOL_CAP = 98.0


def tb_from_spec(spec):
    vdd = float(spec.get("vdd", TB.VDD_DEFAULT))
    return {"vdd": vdd, "vcm": float(spec.get("vcm", vdd / 2.0)),
            "cl_pf": float(spec.get("cl_pf", 2.0)), "temp_c": float(spec.get("temp_c", 27.0))}


def decode(x, names, space):
    """x in [0,1]^n -> {param: float}; values are rounded to the 6 significant digits
    the deck writes, so the reported parameters ARE the simulated ones."""
    p = {}
    for xi, name in zip(x, names):
        lo, hi = RANGES[space[name]]
        xi = min(max(float(xi), 0.0), 1.0)
        v = 10 ** (math.log10(lo) + xi * (math.log10(hi) - math.log10(lo)))
        p[name] = float(TB.fmt(v))
    return p


def encode(params, names, space):
    x = []
    for name in names:
        lo, hi = RANGES[space[name]]
        v = min(max(float(params[name]), lo), hi)
        x.append((math.log10(v) - math.log10(lo)) / (math.log10(hi) - math.log10(lo)))
    return x


def _scale(c):
    vals = [abs(c[k]) for k in ("min", "max") if k in c]
    return max(max(vals) if vals else 1.0, 1.0)


def margins(spec, m):
    """{constraint metric: signed normalized margin (>= 0 iff met), None if missing}."""
    out = {}
    for name, c in spec.get("constraints", {}).items():
        val = m.get(name) if m else None
        if val is None:
            out[name] = None
            continue
        s = _scale(c)
        sl = []
        if "min" in c:
            sl.append((val - c["min"]) / s)
        if "max" in c:
            sl.append((c["max"] - val) / s)
        out[name] = min(sl)
    return out


def violation(spec, m):
    tot = 0.0
    for name, mg in margins(spec, m).items():
        if mg is None:
            tot += 1.0
        elif mg < 0:
            tot += min(-mg, 100.0)
    return tot


def feasible(spec, m):
    if not m or not m.get("valid"):
        return False
    mg = margins(spec, m)
    return all(v is not None and v >= 0 for v in mg.values())


def objective_value(spec, m, objective):
    if m is None or "sim_fail" in m.get("flags", []):
        return SIM_FAIL
    viol = violation(spec, m)
    if not m.get("valid"):
        nf = sum(1 for f in m["flags"] if f in TB.INVALID_FLAGS)
        return 100.0 + 10.0 * nf + min(viol, VIOL_CAP) / 10.0
    if viol > 0:
        return 1.0 + min(viol, VIOL_CAP)
    if objective == "margin":
        mg = [v for v in margins(spec, m).values() if v is not None]
        worst = min(mg) if mg else 0.0
        return -1.0 - min(worst, 1e6)
    metric = objective.split(":", 1)[1]
    val = m.get(metric)
    if val is None or not math.isfinite(val):
        return 1.0 + 1.0
    return -1.0 - (math.pi / 2 + math.atan(val))


def _needs(spec, objective):
    keys = set(spec.get("constraints", {}))
    if objective.startswith("max:"):
        keys.add(objective.split(":", 1)[1])
    icmr = bool(keys & {"icmr_v", "icmr_lo", "icmr_hi"})
    full = bool(keys & {"cmrr_db", "psrr_db"})
    slew = bool(keys & {"slew_vus", "slew_rise_vus", "slew_fall_vus"})
    return icmr, full, slew


def _stab(spec):
    """Opt-in small-step stability gate (README D-O16): spec["stability"] == "ss_tran"."""
    st = spec.get("stability")
    if st not in (None, "ss_tran"):
        raise ValueError("spec stability must be absent or 'ss_tran'")
    return st == "ss_tran"


# ------------------------------------------------------------------ robustness gate (D-O33)
# Opt-in per spec: spec["robust"] == "pvt_mm" (absent => no corner is ever simulated and every
# result is bit-identical to the pre-D1-prep verifier). The design must stay FEASIBLE (valid,
# every hard constraint met, and the small-step stability gate passed if the spec has it) at
# each corner below; the ideal IREF and CL are unchanged at every corner.
#   vdd_lo   VDD x 0.9   (Vcm = the spec's vcm if given, else the corner's VDD/2)
#   vdd_hi   VDD x 1.1   (same rule)
#   t_cold   -40 C       (nominal VDD)
#   t_hot    +125 C      (nominal VDD)
#   mm1..mm4 Vth mismatch at nominal VDD / temperature: every matched MOS group with >= 2
#            members (D-O4) gets a 10 mV difference between its first member (sorted names;
#            e.g. M1a) and the other member(s): BSIM4 delvto = +s*5 mV on the first, -s*5 mV on
#            the rest (pure mismatch, no common shift). Sign s per group k (groups sorted by name):
#              mm1 s = +1 for all groups;  mm2 s = -1 for all;
#              mm3 s = +1 for even k, -1 for odd k;  mm4 = -mm3.
#            For <= 2 groups this is every sign combination; identical vectors are dropped (one
#            group => mm1, mm2 only; no group => no mismatch corner). <= 8 corners in all.
ROBUST_MODES = ("pvt_mm",)
ROB_VDD = (0.9, 1.1)
ROB_TEMPS = (-40.0, 125.0)
ROB_DVT = 0.010


def _robust(spec):
    rb = spec.get("robust")
    if rb not in (None,) + ROBUST_MODES:
        raise ValueError("spec robust must be absent or one of %s" % (ROBUST_MODES,))
    return rb


def mm_groups(devs):
    """Matched MOS groups with >= 2 members: [(group, [member names sorted])], groups sorted."""
    g = {}
    for d in devs:
        if d.is_mos:
            g.setdefault(DL.group_of(d.name), []).append(d.name)
    return [(k, sorted(v)) for k, v in sorted(g.items()) if len(v) >= 2]


def mm_vectors(devs):
    groups = mm_groups(devs)
    if not groups:
        return []
    pats = [("mm1", [1] * len(groups)), ("mm2", [-1] * len(groups)),
            ("mm3", [1 if k % 2 == 0 else -1 for k in range(len(groups))]),
            ("mm4", [-1 if k % 2 == 0 else 1 for k in range(len(groups))])]
    out, seen = [], set()
    for name, signs in pats:
        if tuple(signs) in seen:
            continue
        seen.add(tuple(signs))
        dvt = {}
        for (_g, mem), s in zip(groups, signs):
            dvt[mem[0]] = s * ROB_DVT / 2.0
            for o in mem[1:]:
                dvt[o] = -s * ROB_DVT / 2.0
        out.append((name, dvt))
    return out


def corners(spec, devs):
    """[(corner name, testbench dict)] in the fixed evaluation order."""
    vdd = float(spec.get("vdd", TB.VDD_DEFAULT))
    out = []
    for name, k in (("vdd_lo", ROB_VDD[0]), ("vdd_hi", ROB_VDD[1])):
        sp = dict(spec, vdd=vdd * k)
        out.append((name, tb_from_spec(sp)))
    for name, t in (("t_cold", ROB_TEMPS[0]), ("t_hot", ROB_TEMPS[1])):
        out.append((name, tb_from_spec(dict(spec, temp_c=t))))
    for name, dvt in mm_vectors(devs):
        tb = tb_from_spec(spec)
        tb["dvt"] = dvt
        out.append((name, tb))
    return out


ROB_KEYS = ("gain_db", "ugf_mhz", "pm_deg", "idd_ua", "swing_vpp", "icmr_v", "fom_mhzpf_ma",
            "offset_mv", "ss_ripple_rel")


def _corner_row(name, spec, m):
    mg = margins(spec, m)
    vals = [v for v in mg.values() if v is not None]
    valid = bool(m.get("valid"))
    wm = min(vals) if (valid and vals and len(vals) == len(mg)) else None
    wc = min((k for k, v in mg.items() if v is not None), key=lambda k: mg[k]) if vals else None
    return {"corner": name, "feasible": feasible(spec, m), "valid": valid,
            "flags": [f for f in m.get("flags", []) if f in TB.INVALID_FLAGS],
            "worst_margin": wm, "worst_constraint": wc if valid else None, "margins": mg,
            "metrics": {k: m.get(k) for k in ROB_KEYS}}


def robust_check(devs, params, spec, early_exit=False, objective="margin"):
    """Evaluate the robustness corners (README D-O33). Each corner is measured exactly like an
    in-loop point (the analyses the spec needs; stability gate if the spec has it, lazily).
    Returns {mode, pass, n_corners, n_checked, corners: [row], worst_corner, worst_margin,
    shortfall}. early_exit stops at the first infeasible corner (in-loop use); `shortfall` is
    then the loop grade: (K - i) + s with i the failing corner's index and s in [0, 0.99] its
    capped violation (0.99 if invalid); 0 if every corner passes."""
    icmr, fl, slew = _needs(spec, objective)
    stab = _stab(spec)
    cs = corners(spec, devs)
    rows, short = [], 0.0
    for i, (name, tb) in enumerate(cs):
        m = TB.measure(devs, params, tb, icmr=icmr, full=fl, slew=slew)
        if stab and m.get("valid") and violation(spec, m) == 0:
            TB.apply_ss(devs, params, tb, m)
        row = _corner_row(name, spec, m)
        rows.append(row)
        if not row["feasible"]:
            if not short:
                s = min(violation(spec, m), 0.99) if row["valid"] else 0.99
                short = (len(cs) - i) + s
            if early_exit:
                break
    bad = [r for r in rows if not r["feasible"]]
    pool = bad or rows

    def wkey(r):
        return (-math.inf if r["worst_margin"] is None else r["worst_margin"])
    worst = min(pool, key=wkey) if pool else None
    return {"mode": spec.get("robust"), "pass": (not bad) and len(rows) == len(cs),
            "n_corners": len(cs), "n_checked": len(rows), "corners": rows,
            "worst_corner": worst["corner"] if worst else None,
            "worst_margin": worst["worst_margin"] if worst else None,
            "worst_invalid": bool(worst and not worst["valid"]), "shortfall": short}


def robust_evaluate(netlist_text, params, spec):
    """Robustness corners of one sized design (no sizing): the D-O33 report."""
    devs = DL.parse(netlist_text)
    return robust_check(devs, params, dict(spec, robust=spec.get("robust") or "pvt_mm"))


def _cpu():
    ch = resource.getrusage(resource.RUSAGE_CHILDREN)
    return time.process_time() + ch.ru_utime + ch.ru_stime


def evaluate(netlist_text, params, spec, full=True):
    """Measure one sized design. params: {param: float} (missing IREF etc. -> KeyError)."""
    devs = DL.parse(netlist_text)
    ok, why = DL.prefilter(devs)
    if not ok:
        return {"valid": False, "flags": ["prefilter"], "prefilter": why}
    icmr, fl, slew = _needs(spec, "margin")
    m = TB.measure(devs, params, tb_from_spec(spec), icmr=True if full else icmr,
                   full=full or fl, slew=slew, stab=_stab(spec))
    if _robust(spec):                       # D-O33 report attached; m["valid"] stays nominal
        m["robust"] = robust_check(devs, params, spec)
    return m


def size(netlist_text, spec, seed=1, evals=DEFAULT_EVALS, objective="margin", x0=None,
         keep_points=False):
    """Size `netlist_text` (opamp-v0 dialect) against `spec`.

    spec: {"vdd", "vcm", "cl_pf", "temp_c" (testbench; defaults 1.1, vdd/2, 2.0, 27),
           "constraints": {metric: {"min": a} | {"max": b} | both}}
    objective: "margin" or "max:<metric>".
    Returns a dict: feasible, valid, metrics (full re-measure of the best point),
    margins, worst_margin, target (max mode), params, secs, cpu_s, evals, n_fail,
    best_eval, profile, prefilter, netlist (canonical), objective, seed, trace."""
    t0, c0 = time.time(), _cpu()
    if not (objective == "margin" or objective.startswith("max:")):
        raise ValueError("objective must be 'margin' or 'max:<metric>'")
    devs = DL.parse(netlist_text)
    canon = DL.format_netlist(devs)
    ok, why = DL.prefilter(devs)
    base = {"profile": PROFILE, "objective": objective, "seed": seed, "budget": evals,
            "netlist": canon, "prefilter": {"ok": ok, "why": why}}
    if not ok:
        base.update(feasible=False, valid=False, metrics=None, margins=None, worst_margin=None,
                    target=None, params=None, evals=0, n_fail=0, best_eval=None,
                    secs=time.time() - t0, cpu_s=_cpu() - c0, infeasible_reason="prefilter")
        return base
    tb = tb_from_spec(spec)
    space = DL.param_space(devs)
    names = list(space)
    icmr, fl, slew = _needs(spec, objective)
    stab = _stab(spec)
    robust = _robust(spec)
    points = []

    def obj(x):
        p = decode(x, names, space)
        m = TB.measure(devs, p, tb, icmr=icmr, full=fl, slew=slew)
        if stab and m.get("valid") and violation(spec, m) == 0:
            TB.apply_ss(devs, p, tb, m)      # lazy gate: only on otherwise-feasible points
        if robust and m.get("valid") and violation(spec, m) == 0:
            # lazy robustness gate (D-O33): only on otherwise-feasible points; a point that
            # fails a corner ranks between every feasible-robust point (< -1) and every
            # nominally infeasible one (> 1): f = r / (1 + r) in (0.5, 1), r = shortfall
            rb = robust_check(devs, p, spec, early_exit=True, objective=objective)
            m["robust_loop"] = {"pass": rb["pass"], "n_checked": rb["n_checked"],
                                "shortfall": rb["shortfall"]}
            if not rb["pass"]:
                points.append(([float(v) for v in x], m))
                r = rb["shortfall"]
                return r / (1.0 + r)
            if objective == "margin":      # margin mode: worst margin over nominal + corners
                mg = [v for v in margins(spec, m).values() if v is not None]
                worst = min(mg + [rb["worst_margin"]]) if mg else rb["worst_margin"]
                points.append(([float(v) for v in x], m))
                return -1.0 - min(worst, 1e6)
        points.append(([float(v) for v in x], m))
        return objective_value(spec, m, objective)

    bud = NS._Budget(obj, evals, points)
    diag = {}
    try:
        NS.run_cmaes(bud, len(names), seed, diag=diag, x0=x0)
    except NS._BudgetOut:
        pass
    bx, _bm = bud.best()
    params = decode(bx, names, space) if bx is not None else None
    full_m = (TB.measure(devs, params, tb, icmr=True, full=True, slew=True, stab=stab)
              if params else None)
    mg = margins(spec, full_m) if full_m else None
    vals = [v for v in (mg or {}).values() if v is not None]
    feas = feasible(spec, full_m)
    target = None
    if objective.startswith("max:") and full_m:
        target = full_m.get(objective.split(":", 1)[1])
    base.update(
        feasible=feas, valid=bool(full_m and full_m.get("valid")), metrics=full_m, margins=mg,
        worst_margin=(min(vals) if vals and len(vals) == len(mg) else None),
        target=target if feas else None, target_raw=target,
        params=params, evals=bud.n, n_fail=bud.n_fail, best_eval=bud.best_i,
        best_obj=bud.best_f, cmaes=diag, trace=bud.trace,
        secs=time.time() - t0, cpu_s=_cpu() - c0)
    if robust:
        # always on the final result (D-O33): all corners, no early exit
        rb = robust_check(devs, params, spec, objective=objective) if params else None
        base["feasible_nominal"] = feas
        base["robust"] = rb
        base["feasible"] = bool(feas and rb and rb["pass"])
        wn = base["worst_margin"]
        base["worst_margin_robust"] = (min(wn, rb["worst_margin"]) if (rb and rb["pass"]
                                       and wn is not None) else None)
        base["target"] = target if base["feasible"] else None
        base["cpu_s"] = _cpu() - c0
        base["secs"] = time.time() - t0
    if keep_points:
        base["points"] = points
    return base

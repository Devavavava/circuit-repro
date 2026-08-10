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

NF: as of WP-D1 the sizer GATES nf_db whenever the spec asks it to (see
`_spec_for_sizing` / `nf_is_gated`). The measurement is the golden-validated
series-Rs one (`extract.measure_nf`), taken inside the loop -- one extra ~0.07 s
ngspice call per evaluation -- because a supported-but-missing metric counts as
fully violated and would flatten the objective. Everything logged BEFORE that is
a tier-1 (S11/S21/Idd) claim; `zoaf_cfg.nf_gated` separates the two label
domains. Enable finite inductor Q in the deck for physical inductors.
"""
import argparse
import math
import os
import random
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "misc", "ZOAF")))
import extract as E  # noqa: E402
import datastore as ds  # noqa: E402  (append-only label store, 01-DATA)
from spec import Spec  # noqa: E402
from zoaf.zoaf_core import ZOAF  # noqa: E402  (generic core; the *param variants pull PySpice)

# spec.objective is minimised feasibility-first (>=1 infeasible, <0 feasible), so a
# failed simulation must score worse than any infeasible point.
SIM_FAIL_PENALTY = 1e3

# sentinel: 'argument not supplied' (None is a MEANINGFUL value for w_finger)
_UNSET = object()


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


def nf_is_gated(spec):
    """Does this spec gate nf_db as a hard constraint? (WP-D1 step 4.)

    When it does, NF must be measured INSIDE the sizing loop, not enriched once at
    the end: spec.feasible() counts a missing supported metric as fully violated,
    so an unmeasured NF would make every point infeasible and flatten the
    objective. Costs one extra ngspice call per evaluation (~0.07 s, same order as
    the op/sp call)."""
    c = spec.constraints.get("nf_db")
    return bool(c) and c.get("status") != "unsupported"


def eval_metrics(body, params, spec, nf_gated=None):
    """One full L2 evaluation: op/sp/stability, plus the series-Rs NF when gated."""
    m = E.run_and_extract(body, params, spec)
    if m is None:
        return None
    if nf_is_gated(spec) if nf_gated is None else nf_gated:
        nf = E.measure_nf(body, params, spec)
        m = dict(m, nf_db=nf, nf_method="series_rs" if nf is not None else None)
    return m


def make_objective(body, spec, sizable, fixed, points=None):
    """sizable: {param_name: kind}; fixed: {param_name: literal}. Returns
    (objective_func for ZOAF, names, decode(x)->metrics helper).

    If `points` (a list) is given, every ngspice eval appends `(x, metrics)` to
    it -- the free point-row byproduct (01-DATA §1). This only *reads* x and the
    metrics the objective already computed, so the returned objective value is
    byte-for-byte unchanged (the additive-hook invariant)."""
    names = list(sizable)
    ranges = kind_ranges(spec)
    nf_gated = nf_is_gated(spec)

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
        return eval_metrics(body, decode(x), spec, nf_gated=nf_gated)

    def objective_func(x):
        m = evaluate(x)
        if points is not None:
            points.append(([float(v) for v in x], m))
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
    # Finite-Q constants (pINDQ/pINDW0) are emitted into the netlist's own .param
    # block by to_spice, but E.body_of() strips every .param line, so they must be
    # re-declared here as fixed or the RQ series-R expression evaluates undefined
    # ("Undefined parameter [pindw0]"). Recompute w0 exactly as to_spice.emit does.
    if nl.inductor_q:
        lo, hi = nl.freq[0], nl.freq[1]
        f0 = (lo * hi) ** 0.5
        fixed["pINDQ"] = str(nl.inductor_q)
        fixed["pINDW0"] = f"{2 * math.pi * f0:g}"
    return sizable, fixed


def _zoaf_cfg(seed, n_candidates, sgd_iters, cgd_iters, recipe="anchor-v1",
             inductor_q=None, spec=None):
    """The fixed label budget (01-DATA §5): labels are only comparable at equal
    ZOAF budget, so the knobs that define it are stamped on every row. inductor_q
    is a deck/harness setting that changes the metrics, so it is stamped too --
    and so is `nf_gated` (WP-D1 step 4), which changes what the optimizer is even
    solving. Rows with nf_gated true/false are DIFFERENT label domains; every row
    written before WP-D1 is implicitly nf_gated:false (tier-1)."""
    cfg = {"recipe": recipe, "seed": seed, "n_candidates": n_candidates,
           "n_starts": 4, "sgd_iters": sgd_iters, "cgd_iters": cgd_iters,
           "inductor_q": inductor_q}
    if spec is not None:
        cfg["nf_gated"] = nf_is_gated(spec)
    # MOS gate geometry (2026-08-10 cutover, FINDINGS §26/§27). Emitting
    # single-finger devices put 26-40% of the excess noise factor into BSIM4's
    # gate-electrode resistance, so NF numbers before and after the cutover are
    # NOT comparable. Stamped from to_spice's own default so a row is honest
    # about its geometry no matter which driver produced it.
    try:
        from to_spice import Netlist as _NL, W_FINGER as _WF
        cfg["w_finger"] = _WF
        cfg["mos_fingers"] = "ceil(W/w_finger)" if _WF else 1
    except Exception:
        pass
    return cfg


def _enrich_nf(body, params, spec, m):
    """Replace the port-based (unphysical, finding #7) nf_db with the series-Rs NF
    measured at the sized point. Additive: NF is `unsupported` in the sizing spec,
    so this changes only the logged metric, never sizing/feasibility/objective.
    One extra ~1 s ngspice call per label; defensive (keeps the old value on
    failure)."""
    if m is None:
        return m
    try:
        nf = E.measure_nf(body, params, spec)
        if nf is not None:
            return dict(m, nf_db=nf, nf_method="series_rs")
    except Exception:
        pass
    return m


def _noise_budget_row(body, params, spec, top=6):
    """Compact per-element noise budget for an L2 row (WP-L5 phase 1).

    `nf_db` says how much noise a design has; this says WHOSE, which is the part
    a model can actually learn from -- the same NF can come from a dominant input
    device (fixable by sizing) or from a lossy match (fixable only by topology).
    Stored as INPUT FEATURES for the critic, never as a gated metric.

    Kept small on purpose: the top-`top` contributors by share of the excess
    noise factor (F-1), plus the mechanism split aggregated over all MOSFETs, so
    the row stays a few hundred bytes. One extra ngspice call per label
    (~0.15 s), and entirely defensive -- a failure logs nothing and changes
    nothing else."""
    try:
        b = E.measure_noise_budget(body, params, spec)
    except Exception:
        return None
    if not b or not b.get("elements") or not b.get("p_source"):
        return None
    mech = {}
    for e in b["elements"].values():
        for k, v in (e.get("mech") or {}).items():
            mech[k] = mech.get(k, 0.0) + v
    tot_mech = sum(mech.values()) or 1.0
    rows = sorted(b["elements"].items(),
                  key=lambda kv: -(kv[1].get("excess_frac") or 0.0))
    return {
        "f_hz": b["f"],
        "nf_db_shares": b.get("nf_db_from_shares"),
        "sum_closure": b.get("sum_closure"),
        "source_frac": (b["elements"].get("rns") or {}).get("frac"),
        "top": [{"elem": n, "kind": e.get("kind"),
                 "frac_out": round(e.get("frac") or 0.0, 5),
                 "frac_excess": round(e.get("excess_frac") or 0.0, 5)}
                for n, e in rows[:top] if n != "rns"],
        "mos_mech_frac": {k: round(v / tot_mech, 5)
                          for k, v in sorted(mech.items(), key=lambda kv: -kv[1])[:6]},
    }


def _log_l2(spec, metrics, feasible, n_evals, points, best_x, best_params,
            best_obj, topo, wl_hash, provenance, zoaf_cfg, repeat_probe=False):
    """Append an L2 row (+ its point rows) to the label store. Logging must never
    break a sizing run, so any failure is warned and swallowed."""
    try:
        row = ds.row_l2(spec, metrics, feasible, n_evals, best_x=best_x,
                        best_params=best_params, best_obj=best_obj, topo=topo,
                        wl_hash=wl_hash, provenance=provenance, zoaf_cfg=zoaf_cfg)
        status, _ = ds.append_l2(row, repeat_probe=repeat_probe)
        if status == "appended" and points:
            ds.append_all("sim_points",
                          [ds.row_point(wl_hash, spec.name, x, m) for x, m in points])
        extra = f" +{len(points)} points" if status == "appended" and points else ""
        print(f"  [log] L2 {status}: ({wl_hash}, {spec.name}){extra}")
        return status
    except Exception as e:                       # logging is additive, never fatal
        print(f"  [log] WARN: L2 logging failed: {e}")
        return "error"


def match_devices(topo):
    """Input-match passives (06-LAST-MILE §1): 2-terminal R/C/L on the path from the
    input port to the first MOS gate, plus the input device's source (degeneration)
    and gate-source passives. Fixing these -- not sizing them free -- is what let the
    tapped reference reach feasibility (all-free ZOAF lands gain OR match, not both).
    Returns (set of match device tokens, input device token or None)."""
    from collections import defaultdict, deque
    from topology import base_of, PIN_RE
    pin2root = {m: r for r, members in topo.nodes.items() for m in members}
    net2root = {m: r for r, members in topo.nodes.items()
                for m in members if m in topo.nets}
    devpin = defaultdict(dict)
    for p in topo.pins:
        mm = PIN_RE.match(p)
        if mm and p in pin2root:
            devpin[mm.group("dev")][mm.group("pin")] = pin2root[p]
    adj = defaultdict(list)                       # passive adjacency over nodes
    for d in topo.devices:
        if base_of(d) in ("R", "C", "L"):
            pp = devpin.get(d, {})
            if "P" in pp and "N" in pp:
                adj[pp["P"]].append((d, pp["N"]))
                adj[pp["N"]].append((d, pp["P"]))
    gate_node = {devpin[d].get("G"): d for d in topo.devices
                 if base_of(d) in ("NM", "PM")}
    vin = next((n for n in sorted(topo.nets) if n.startswith("VIN")), None)
    start, match, input_dev = net2root.get(vin), set(), None
    if start is not None:
        seen, dq = {start}, deque([start])
        while dq:
            u = dq.popleft()
            for dev, v in adj[u]:
                match.add(dev)                    # passive on the input path
                if v in gate_node and input_dev is None:
                    input_dev = gate_node[v]
                if v not in seen and v not in gate_node:
                    seen.add(v)
                    dq.append(v)
    if input_dev:                                 # + source-degen / gate-source
        snode = devpin[input_dev].get("S")
        for d in topo.devices:
            if base_of(d) in ("R", "C", "L") and snode in devpin.get(d, {}).values():
                match.add(d)
    return match, input_dev


def _curate(topo, sizable, fixed, prior_params):
    """Move the input-match passives from sizable to fixed at their prior best
    values (06-LAST-MILE §1). Returns the match device set actually fixed."""
    mdevs, _ = match_devices(topo)
    fixed_now = set()
    for d in mdevs:
        p = f"p{d}V"                              # passive value param (R/C/L)
        if p in sizable and prior_params and p in prior_params:
            fixed[p] = prior_params[p]
            del sizable[p]
            fixed_now.add(d)
    return fixed_now


def replay_ok(topo, best_params, spec, stored_metrics, sigma=1.0, inductor_q=12):
    """Replay invariant (07-EXIT §1a): re-evaluating a stored `best_params` on the
    topology reconstructed from the *same* row's tokens must reproduce the stored
    metrics within label noise. It fails when a (topo, params) pair is inconsistent
    -- e.g. a token_file re-parsed from a different arm's same-named seq (the bug
    that stalled polish). Such rows are quarantined, not sized. Returns bool."""
    import bias
    if not (best_params and stored_metrics):
        return False
    kw = {"inductor_q": inductor_q} if inductor_q else {}
    nl, _, rep, _ = bias.insert_bias(topo, sweep=True, **kw)
    if rep.get("skipped") or not nl.two_port:
        return False
    m = E.run_and_extract(E.body_of(nl.emit()), best_params, spec)
    if m is None:
        return False
    s = max(sigma, 0.5)
    return (abs((m.get("s21_db") or -1e9) - (stored_metrics.get("s21_db") or 1e9)) <= s
            and abs((m.get("s11_db") or -1e9) - (stored_metrics.get("s11_db") or 1e9)) <= 2.0)


def polish(topo, spec, prior_params, budget=80, inductor_q=12, exclude=()):
    """Boundary polish (06-LAST-MILE §2): coordinate pattern search from the stored
    best point that maximizes the **minimum normalized margin** -- which, unlike the
    feasibility-first scalar, has a gradient right at the boundary (it trades a
    near-miss's slack on a passing constraint for the one it violates). Perturbs
    only the sizable device/bias params (match held via prior values); ~budget sims.
    Returns {metrics, feasible, best_params, n_evals, min_margin} or None."""
    import bias
    from datastore import margins_for
    kw = {"inductor_q": inductor_q} if inductor_q else {}
    nl, _, rep, _ = bias.insert_bias(topo, sweep=True, **kw)
    if rep.get("skipped") or not nl.two_port:
        return None
    body = E.body_of(nl.emit())
    sizable, _ = classify_params(nl)
    if exclude:                       # e.g. hold a solved input match fixed
        sizable = {k: v for k, v in sizable.items() if k not in set(exclude)}
    nf_gated = nf_is_gated(spec)
    # ascend the minimum margin over every SUPPORTED hard constraint -- so when a
    # spec gates NF, polish trades gain slack for noise instead of ignoring it.
    keys = [n for n, c in spec.constraints.items() if c.get("status") != "unsupported"]

    def min_margin(p):
        m = eval_metrics(body, p, spec, nf_gated=nf_gated)
        if m is None:
            return -1e9, None
        mg = margins_for(spec, m)
        vals = [(mg.get(k) or {}).get("margin") for k in keys]
        vals = [v for v in vals if v is not None]
        if len(vals) < len(keys):        # a supported constraint went unmeasured
            return -1e9, m
        return (min(vals) if vals else -1e9), m

    # BOX CLAMP (bug found by Track B, 2026-08-08). This ascent scales each value by
    # (1 +/- step); before the clamp it never consulted kind_ranges, so polish could
    # -- and did -- walk parameters OUTSIDE the spec's declared device box (a
    # dhruva-l1 candidate reached L = 18.1 nH against topology.l_max = 15 nH). ZOAF
    # searches inside the box, so only polish-derived points were ever affected, and
    # any "feasible" it produced out-of-box was an overstated claim. Every trial is
    # now clamped, the incoming point is clamped before the first evaluation, and a
    # coordinate already sitting on a bound cannot step further out.
    rng = kind_ranges(spec)

    def clamp(name, val):
        kind = sizable.get(name)
        if kind not in rng:
            return val
        lo, hi = rng[kind][0], rng[kind][1]
        return min(max(val, lo), hi)

    params = {k: v for k, v in (prior_params or {}).items()}
    for nm in list(sizable):
        if nm in params:
            try:
                params[nm] = f"{clamp(nm, float(params[nm])):.6g}"
            except (TypeError, ValueError):
                pass
    best_mm, best_m = min_margin(params)
    n, step = 1, 0.15
    while n < budget and step > 0.02:
        improved = False
        for name in list(sizable):
            if name not in params:
                continue
            try:
                base = float(params[name])
            except (TypeError, ValueError):
                continue
            for factor in (1 - step, 1 + step):
                cand = clamp(name, base * factor)
                if abs(cand - base) <= 1e-18:     # already pinned at a bound
                    continue
                trial = dict(params)
                trial[name] = f"{cand:.6g}"
                mm, m = min_margin(trial)
                n += 1
                if mm > best_mm:
                    best_mm, best_m, params, improved = mm, m, trial, True
                if n >= budget:
                    break
            if n >= budget:
                break
        if not improved:
            step *= 0.6
    feas = best_m is not None and spec.feasible(best_m)[0]
    return {"metrics": best_m, "feasible": feas, "best_params": params,
            "n_evals": n, "min_margin": best_mm}


def prepared_body(topo, inductor_q=12, w_finger=_UNSET):
    """(body, sizable, fixed) for a topology, bias inserted -- or None if biasing
    skips it. Factored out of polish/size_topology so a driver can pay the
    bias-insert cost once and then run many searches on the same deck.

    `w_finger` defaults to to_spice's own default (multi-finger since the
    2026-08-10 cutover); pass None to reproduce a pre-cutover single-finger
    deck, which is what the relabel tool's replay fence needs."""
    import bias
    kw = {"inductor_q": inductor_q} if inductor_q else {}
    if w_finger is not _UNSET:
        kw["w_finger"] = w_finger
    nl, _, rep, _ = bias.insert_bias(topo, sweep=True, **kw)
    if rep.get("skipped") or not nl.two_port:
        return None
    sizable, fixed = classify_params(nl)
    return E.body_of(nl.emit()), sizable, fixed


def constrained_descent(topo, spec, prior_params, target=("nf_db", "min"),
                        keep=None, budget=240, inductor_q=12, floor=0.0,
                        seed=0, jitter=0.0, exclude=(), prepared=None,
                        trace=None):
    """Optimize ONE metric inside a hard trust region of the others (WP-NF / D3).

    `polish` ascends the *minimum* normalized margin over every gated constraint.
    That is the right move at a feasibility boundary, and the wrong one when a
    design is tier-1 clean and misses on exactly one constraint by a lot: the
    minimum IS the violated constraint, so polish optimizes it anyway -- while
    valuing a 4.9 dB gain surplus and a 1.2 mA current surplus at exactly zero,
    because raising a non-binding margin cannot raise the minimum. Slack is
    currency only if something is allowed to spend it.

    So: minimize (or maximize) `target` directly, and refuse any step that pushes
    a *kept* constraint's normalized margin below `floor`. Scoring is
    lexicographic -- (total kept-constraint shortfall, target value) -- so an
    infeasible start is first walked into the region and only then descended.

      target  (metric, "min"|"max")
      keep    {metric: {"max": v} | {"min": v}}; defaults to every gated
              constraint except the target (i.e. the tier-1 box, plus NF when
              the target is gain).
      floor   required normalized margin on kept constraints (0.0 = the boundary;
              use e.g. 0.02 to keep a design off the cliff edge).
      jitter  fractional log-uniform perturbation of the start point (multi-seed
              diversity); the jittered start is used only if it stays in region.

    Returns {metrics, feasible, best_params, n_evals, target, shortfall} or None.
    """
    prep = prepared or prepared_body(topo, inductor_q=inductor_q)
    if prep is None:
        return None
    body, sizable, _fixed = prep
    if exclude:
        sizable = {k: v for k, v in sizable.items() if k not in set(exclude)}
    nf_gated = nf_is_gated(spec)
    tname, tdir = target
    tsign = 1.0 if tdir == "min" else -1.0
    if keep is None:
        keep = {n: {k: c[k] for k in ("min", "max") if k in c}
                for n, c in spec.constraints.items()
                if c.get("status") != "unsupported" and n != tname}
    scales = {n: spec._scale(c) for n, c in keep.items()}
    rng = kind_ranges(spec)
    rand = random.Random(seed)

    def clamp(name, val):
        kind = sizable.get(name)
        if kind not in rng:
            return val
        lo, hi = rng[kind][0], rng[kind][1]
        return min(max(val, lo), hi)

    def score(p):
        """(kept-constraint shortfall, signed target). Lower is better."""
        m = eval_metrics(body, p, spec, nf_gated=nf_gated)
        if m is None:
            return (1e9, 1e9), None
        short = 0.0
        for n, c in keep.items():
            v = m.get(n)
            if v is None:                 # unmeasurable kept constraint
                short += 1.0 + floor
                continue
            s = scales[n]
            if "max" in c:
                short += max(0.0, (v - c["max"]) / s + floor)
            if "min" in c:
                short += max(0.0, (c["min"] - v) / s + floor)
        t = m.get(tname)
        return (short, 1e9 if t is None else tsign * t), m

    params = {k: v for k, v in (prior_params or {}).items()}
    for nm in list(sizable):
        if nm in params:
            try:
                params[nm] = f"{clamp(nm, float(params[nm])):.6g}"
            except (TypeError, ValueError):
                pass
    best_s, best_m = score(params)
    n = 1
    if jitter > 0:
        trial = dict(params)
        for nm in list(sizable):
            if nm not in trial:
                continue
            try:
                base = float(trial[nm])
            except (TypeError, ValueError):
                continue
            trial[nm] = f"{clamp(nm, base * math.exp(rand.uniform(-jitter, jitter))):.6g}"
        s, m = score(trial)
        n += 1
        if s[0] <= best_s[0]:             # keep the jitter only if still in region
            best_s, best_m, params = s, m, trial

    order = [k for k in sizable if k in params]

    def rand_dir(step_):
        """A joint multiplicative move on 2-4 coordinates. Noise cancellation is a
        condition on a *ratio* (aux gm vs CG gm, load vs load), so the descent
        direction that matters is rarely axis-aligned; a coordinate sweep alone
        stalls on the diagonal."""
        pick = rand.sample(order, min(len(order), rand.randint(2, 4)))
        trial = dict(params)
        for nm in pick:
            try:
                base = float(trial[nm])
            except (TypeError, ValueError):
                continue
            trial[nm] = f"{clamp(nm, base * (1 + step_ * rand.choice((-1.0, 1.0)))):.6g}"
        return trial

    step = 0.30
    while n < budget and step > 0.015:
        rand.shuffle(order)
        improved = False
        for _ in range(max(2, len(order) // 3)):     # random-direction probes
            if n >= budget:
                break
            trial = rand_dir(step)
            s, m = score(trial)
            n += 1
            if s < best_s:
                best_s, best_m, params, improved = s, m, trial, True
        for name in order:
            try:
                base = float(params[name])
            except (TypeError, ValueError):
                continue
            for factor in ((1 + step, 1 - step) if rand.random() < 0.5
                           else (1 - step, 1 + step)):
                cand = clamp(name, base * factor)
                if abs(cand - base) <= 1e-18:
                    continue
                trial = dict(params)
                trial[name] = f"{cand:.6g}"
                s, m = score(trial)
                n += 1
                if s < best_s:
                    best_s, best_m, params, improved = s, m, trial, True
                    base = cand
                if n >= budget:
                    break
            if n >= budget:
                break
        if trace is not None:
            trace.append({"n": n, "step": step, "shortfall": best_s[0],
                          "target": tsign * best_s[1] if best_s[1] < 1e8 else None})
        if not improved:
            step *= 0.55
    feas = best_m is not None and spec.feasible(best_m)[0]
    return {"metrics": best_m, "feasible": feas, "best_params": params,
            "n_evals": n, "target": (tsign * best_s[1] if best_s[1] < 1e8 else None),
            "shortfall": best_s[0]}


def match_param_names(topo, sizable):
    """The parameters that set the INPUT MATCH, for a match-first search.

    `match_devices` finds the passives on the input path (Cin/Lg/Ls/Cex...), which
    is the right set for a CS-degenerated input, where the match is purely passive
    AND the input reaches a transistor GATE. It is blind to a COMMON-GATE input:
    there the signal arrives at a transistor SOURCE, `match_devices` finds no input
    device at all, and -- fatally -- Rin = 1/gm is set by that device's WIDTH, which
    then never enters the match search. (Measured: the gm-boosted CG archetypes had
    only {pCinV, pLinV} as match params and stalled at s11_max ~ -3 dB.)

    So this walks the input net over 2-terminal passives itself and collects:
      * every passive on that path (the DC block, gate/source inductors, Cex);
      * every FET touching the reached nodes at its GATE **or its SOURCE** -> its W;
      * for a gm-boosted CG, the auxiliary amplifier -- any FET whose gate sits on
        the input node -- and the passives on that amp's drain, since the boost
        gain (1+A) is what divides Rin.
    Returns the subset that is actually sizable."""
    from collections import defaultdict, deque
    from topology import base_of, PIN_RE
    pin2root = {m: r for r, members in topo.nodes.items() for m in members}
    net2root = {m: r for r, members in topo.nodes.items()
                for m in members if m in topo.nets}
    devpin = defaultdict(dict)
    for p in topo.pins:
        mm = PIN_RE.match(p)
        if mm and p in pin2root:
            devpin[mm.group("dev")][mm.group("pin")] = pin2root[p]
    adj = defaultdict(list)
    for d in topo.devices:
        if base_of(d) in ("R", "C", "L"):
            pp = devpin.get(d, {})
            if "P" in pp and "N" in pp:
                adj[pp["P"]].append((d, pp["N"]))
                adj[pp["N"]].append((d, pp["P"]))
    fets = [d for d in topo.devices if base_of(d) in ("NM", "PM")]
    touch = {}                       # node -> [(dev, pin)] for G/S pins of FETs
    for d in fets:
        for pin in ("G", "S"):
            n = devpin[d].get(pin)
            if n is not None:
                touch.setdefault(n, []).append((d, pin))

    vin = next((n for n in sorted(topo.nets) if n.startswith("VIN")), None)
    start = net2root.get(vin)
    names, in_dev = set(), None
    if start is None:
        return set()
    seen, dq = {start}, deque([start])
    reached = {start}
    while dq:
        u = dq.popleft()
        for dev, v in adj[u]:
            names.add(f"p{dev}V")                     # passive on the input path
            for d, pin in touch.get(v, []):
                names.add(f"p{d}W")                   # gate- OR source-driven input FET
                if in_dev is None:
                    in_dev = d
            if v not in seen and v not in touch:
                seen.add(v)
                reached.add(v)
                dq.append(v)
    for d, pin in touch.get(start, []):               # FET right on the input net
        names.add(f"p{d}W")
        in_dev = in_dev or d
    # supply rails are shared by every load in the circuit -- expanding through them
    # would drag the whole netlist into the "match" set.
    rails = {net2root.get(n) for n in ("VDD", "VSS") if net2root.get(n) is not None}
    if in_dev:                                        # degeneration / gate-source passives
        for pin in ("S", "G"):
            nd = devpin[in_dev].get(pin)
            if nd is None or nd in rails:
                continue
            for e in topo.devices:
                if base_of(e) in ("R", "C", "L") and nd in devpin.get(e, {}).values():
                    names.add(f"p{e}V")
        # gm-boost auxiliary amp: a FET whose GATE is on the input node, plus its load
        for d in fets:
            if d == in_dev or devpin[d].get("G") not in reached:
                continue
            names.add(f"p{d}W")
            dn = devpin[d].get("D")
            if dn is not None and dn not in rails:
                for e in topo.devices:
                    if base_of(e) in ("R", "C", "L") and dn in devpin.get(e, {}).values():
                        names.add(f"p{e}V")
    return {n for n in names if n in sizable}


def size_match_first(topo, spec, seed=1, inductor_q=12, budget=8,
                     match_budget=10, polish_budget=400):
    """Two-stage sizing: solve the INPUT MATCH first, freeze it, then optimize the
    rest (06-LAST-MILE's curated idea, but self-starting -- no prior solution).

    All-free ZOAF reliably lands gain OR match, never both: the feasibility-first
    scalar is dominated by whichever constraint is furthest off, and the match is a
    narrow basin in a 10-20 dimensional space. Stage 1 therefore optimizes ONLY the
    match parameters against a pure match objective (worst-case S11 over the band,
    saturating at -15 dB so it stops trading), with everything else pinned at the
    middle of its range. Stage 2 freezes those and hands the remaining parameters
    the real spec objective -- including NF when the spec gates it. Stage 3 is the
    NF-aware min-margin polish over the non-match parameters.

    Returns the same dict shape as size_topology (or None)."""
    import bias
    kw = {"inductor_q": inductor_q} if inductor_q else {}
    nl, _, rep, _ = bias.insert_bias(topo, sweep=True, **kw)
    if rep.get("skipped") or not nl.two_port:
        return None
    body = E.body_of(nl.emit())
    sizable, fixed = classify_params(nl)
    mnames = match_param_names(topo, sizable)
    if not mnames or len(mnames) == len(sizable):
        return size_topology(topo, spec, seed=seed, inductor_q=inductor_q, log=False,
                             n_candidates=budget, sgd_iters=budget, cgd_iters=2)

    # --- stage 1: match only, everything else at mid-range
    rest = {k: v for k, v in sizable.items() if k not in mnames}
    _, rnames, rdecode, _ = make_objective(body, spec, rest, {})
    mid = rdecode([0.5] * len(rnames))
    msizable = {k: v for k, v in sizable.items() if k in mnames}
    mfixed = dict(fixed)
    mfixed.update(mid)
    _, m_names, m_decode, _ = make_objective(body, spec, msizable, mfixed)

    def match_obj(x):
        m = E.run_and_extract(body, m_decode(x), spec)
        if m is None:
            return SIM_FAIL_PENALTY
        v = m.get("s11_max_db")
        return SIM_FAIL_PENALTY if v is None else max(v, -15.0)

    mx, mbest, n1 = run_zoaf(match_obj, m_names, seed=seed,
                             n_candidates=match_budget, sgd_iters=match_budget,
                             cgd_iters=2)
    match_vals = {k: v for k, v in m_decode(mx).items() if k in mnames}

    # --- stage 2: freeze the match, optimize the rest on the real objective
    fixed2 = dict(fixed)
    fixed2.update(match_vals)
    obj, names2, decode2, evaluate2 = make_objective(body, spec, rest, fixed2)
    x2, best_obj, n2 = run_zoaf(obj, names2, seed=seed, n_candidates=budget,
                                sgd_iters=budget, cgd_iters=2)
    params = decode2(x2)
    m = evaluate2(x2)
    n_evals = n1 + n2

    # --- stage 3: NF-aware min-margin polish, match held
    if polish_budget:
        pol = polish(topo, spec, params, budget=polish_budget, inductor_q=inductor_q,
                     exclude=mnames)
        if pol and pol.get("metrics") and (m is None
                                           or spec.objective(pol["metrics"]) < spec.objective(m)):
            m, params, n_evals = pol["metrics"], pol["best_params"], n_evals + pol["n_evals"]
    if m is None:
        return None
    feas, viol = spec.feasible(m)
    return {"metrics": m, "feasible": feas, "viol": viol, "n_evals": n_evals,
            "best_obj": spec.objective(m), "best_params": params,
            "match_s11_max": mbest, "n_match_params": len(mnames)}


def size_topology(topo, spec, seed=1, n_candidates=6, sgd_iters=6, cgd_iters=1,
                  provenance=None, log=True, repeat_probe=False, inductor_q=None,
                  curate=False, prior_params=None, enrich_nf=None):
    """Bias-insert, then ZOAF-size a generated topology against `spec`.

    With `log=True` (default for CLI paths) the completed sizing run is appended
    to the label store as one L2 row; pass `log=False` for throwaway experiments
    (`size.py --no-log`) and from callers that only want the score. `inductor_q`
    (default None = ideal, unchanged) gives inductors finite Q so real
    inductor-bearing topologies do not hit the ideal-branch singularity that
    finding #10 / R1 flagged -- HANDOVER-EXEC §6.1's "size with inductor_q=12"."""
    import bias
    from novelty import wl_features
    kw = {"inductor_q": inductor_q} if inductor_q else {}
    nl, inserter, rep, swept = bias.insert_bias(topo, sweep=True, **kw)
    if rep.get("skipped") or not nl.two_port:
        return None
    body = E.body_of(nl.emit())
    sizable, fixed = classify_params(nl)
    recipe = "candidate-v1"
    if curate:
        _curate(topo, sizable, fixed, prior_params)   # fix input match at prior best
        recipe = "curated-v1"
    if not sizable:
        return None
    points = [] if log else None
    obj, names, decode, evaluate = make_objective(body, spec, sizable, fixed,
                                                  points=points)
    best_x, best_obj, n_evals = run_zoaf(obj, names, seed=seed,
                                         n_candidates=n_candidates,
                                         sgd_iters=sgd_iters, cgd_iters=cgd_iters)
    m = evaluate(best_x)
    # `enrich_nf` defaults to `log` (unchanged behaviour); pass True to get the
    # physical NF on a throwaway run too (benchmark cells, best-of-k seeds).
    if log if enrich_nf is None else enrich_nf:
        m = _enrich_nf(body, decode(best_x), spec, m)   # physical NF for the row
    feas, viol = (spec.feasible(m) if m is not None else (False, None))
    if log:
        _log_l2(spec, m, feas, n_evals, points, best_x, decode(best_x), best_obj,
                topo, wl_features(topo)[0], provenance,
                _zoaf_cfg(seed, n_candidates, sgd_iters, cgd_iters, recipe,
                          inductor_q=inductor_q, spec=spec),
                repeat_probe=repeat_probe)
    if m is None:
        return {"metrics": None, "feasible": False, "n_evals": n_evals}
    return {"metrics": m, "feasible": feas, "viol": viol, "n_evals": n_evals,
            "best_obj": best_obj, "n_params": len(names),
            "best_params": decode(best_x)}   # so callers can polish/curate from here


def size_best_of_k(topo, spec, seeds=(1, 2, 3), provenance=None, log=True,
                   repeat_probe=False, **kw):
    """Best-of-k ZOAF label (06-LAST-MILE §4) -- the low-noise label definition.

    Single-seed all-free ZOAF is multimodal: the same (topology, spec) resized with
    a fresh seed lands in a different basin, which is the whole of the repeat-probe
    sigma(S21). Best-of-k runs k seeds and keeps the run with the best
    feasibility-first objective (`spec.objective`, minimised), which is both a
    *better* label (never worse than single-seed) and a *quieter* one. Measured on
    the 19 wifi24 repeat-probe keys (FINDINGS §14.1): sigma(S21) **1.478 -> 0.726
    dB** for k=3, i.e. 2.0x quieter for 3x the sim cost -- short of 06-LAST-MILE's
    <=0.5 dB bar, so k=5 or a warm start is the next lever if that bar must hold.

    The logged row carries:
      * `zoaf_cfg.recipe` bumped with `+bo3` (k=3) / `+bo<k>` -- best-of-k and
        single-seed labels are DIFFERENT label domains and must never be pooled
        silently (01-DATA rule, same as curated-v1 vs candidate-v1);
      * `zoaf_cfg.seeds` -- every seed tried, so the run is reproducible;
      * `label_sigma` -- the per-key seed spread (population stdev over the k runs)
        of each metric, so training can downweight by 1/sigma or drop spread>1 dB
        rows without re-simulating.

    Returns the winning `size_topology` result dict, with `label_sigma`,
    `seed_metrics` and `winning_seed` added; None if every seed failed.
    """
    import statistics
    from novelty import wl_features
    runs = []
    for s in seeds:
        try:
            r = size_topology(topo, spec, seed=s, log=False, enrich_nf=True, **kw)
        except Exception as e:
            print(f"  [bo{len(seeds)}] seed {s} FAILED: {e}")
            continue
        if r and r.get("metrics"):
            runs.append((s, r))
    if not runs:
        return None
    # feasibility-first: spec.objective is minimised (>=1 infeasible, <0 feasible)
    seed_best, best = min(runs, key=lambda sr: spec.objective(sr[1]["metrics"]))
    spread, seed_metrics = {}, {}
    for name in ("s11_db", "s11_max_db", "s21_db", "idd_ma", "nf_db"):
        vals = [r["metrics"].get(name) for _, r in runs]
        vals = [v for v in vals if v is not None]
        seed_metrics[name] = vals
        if len(vals) >= 2:
            spread[name] = statistics.pstdev(vals)
    best = dict(best, label_sigma=spread, seed_metrics=seed_metrics,
                winning_seed=seed_best, n_seeds=len(runs))
    if log:
        cfg = _zoaf_cfg(seed_best, kw.get("n_candidates", 6), kw.get("sgd_iters", 6),
                        kw.get("cgd_iters", 1), f"candidate-v1+bo{len(seeds)}",
                        inductor_q=kw.get("inductor_q"), spec=spec)
        cfg["seeds"] = list(seeds)
        # n_evals is the label's true SPICE cost: every seed, not just the winner
        n_ev = sum(r["n_evals"] for _, r in runs)
        try:
            row = ds.row_l2(spec, best["metrics"], best["feasible"], n_ev,
                            best_x=None, best_params=best["best_params"],
                            best_obj=best.get("best_obj"), topo=topo,
                            wl_hash=wl_features(topo)[0], provenance=provenance,
                            zoaf_cfg=cfg)
            row["label_sigma"] = spread
            status, _ = ds.append_l2(row, repeat_probe=repeat_probe)
            print(f"  [log] L2 {status} (bo{len(seeds)}, winner seed {seed_best})")
        except Exception as e:                   # logging is additive, never fatal
            print(f"  [log] WARN: bo{len(seeds)} logging failed: {e}")
    return best


def _nf_gate_default():
    """Global default for NF gating. True since WP-D1; set LNA_NF_GATE=0 in the
    environment to run a whole session under the old tier-1 gating (an escape
    hatch for reproducing/continuing a tier-1 campaign without editing code)."""
    return os.environ.get("LNA_NF_GATE", "1").strip().lower() not in ("0", "false", "no")


def _spec_for_sizing(name, nf_gate=None):
    """Load a spec for the sizing loop.

    HISTORY / LABEL DOMAIN (important when comparing rows): until WP-D1 this
    function *forced* nf_db to `unsupported`, because the only NF the harness had
    was the port-referred one that finding #7 retired. Every feasibility claim
    logged before then -- the wifi24 six, the two gps-l1 generated feasibles, the
    dhruva 4-band family -- is therefore a **tier-1** claim (S11/S21/Idd only)
    and stays valid on its own terms.

    Now that `extract.measure_nf` is golden-validated, nf_gate=True (the default)
    honours whatever the YAML says, so NF is a real hard constraint. Pass
    nf_gate=False to reproduce a tier-1 result exactly under the old gating --
    that is history, not a fallback to be used for new labels."""
    if nf_gate is None:
        nf_gate = _nf_gate_default()
    spec = Spec.load(name)
    if not nf_gate and "nf_db" in spec.constraints:
        spec.constraints["nf_db"]["status"] = "unsupported"
    return spec


def scoreboard(directory, spec_name="wifi24", seed=1, max_candidates=4, log=True):
    """Size the top spec-passing candidates in a generation dir end-to-end.

    The program's headline: spec in, novel generated topology -> bias -> ZOAF
    sized -> scored. (NF gated off pending the harness fix.) Every candidate's
    sizing run is logged as an L2 row unless `log=False` (--no-log).

    ⚠ `novel` is judged against the **versioned reference** (`ref-v2` = the 41
    corpus circuits + every `templates.py` archetype), not the corpus alone: a
    P5-era sample that regenerates a training archetype verbatim is a copy, and
    the old corpus-only test logged it as a discovery (FINDINGS §14.5). The
    reference tag is stamped into each row's provenance."""
    import glob
    from topology import Topology, parse_arrow_file
    from novelty import ref_tag, reference, wl_features
    spec = _spec_for_sizing(spec_name)
    ref_hashes, _, ref_meta = reference()
    novelty_ref = ref_tag(ref_meta)

    cands = []
    for f in sorted(glob.glob(os.path.join(directory, "seq*.txt"))):
        topo = Topology(parse_arrow_file(f))
        if not spec.structural_screen(topo)[0]:
            continue
        novel = wl_features(topo)[0] not in ref_hashes
        cands.append((f, topo, novel))
        if len(cands) >= max_candidates:
            break

    arm = os.path.basename(os.path.normpath(directory))
    print(f"sizing {len(cands)} spec-passing candidates from {directory} vs "
          f"{spec_name} (nf gated off; novelty vs {novelty_ref})\n")
    print(f"{'candidate':<12} {'novel':>5} {'dev':>3} {'sims':>5} "
          f"{'S11':>7} {'S21':>7} {'Idd':>6} {'feasible':>9}")
    n_feas = 0
    for f, topo, novel in cands:
        name = os.path.basename(f)
        prov = {"source_arm": arm, "seed": seed, "novel": bool(novel),
                "novelty_ref": novelty_ref,
                "token_file": os.path.relpath(f, HERE).replace("\\", "/")}
        res = size_topology(topo, spec, seed=seed, provenance=prov, log=log)
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


def log_l2_result(spec, topo, metrics, feasible, best_params, provenance, recipe,
                  n_evals, inductor_q=12, repeat_probe=True):
    """Append an already-computed sizing result (curated ZOAF or polish) as one L2
    row without re-sizing -- so a boundary/polish win is recorded exactly as found.
    Reconstructs the body only to enrich the physical NF."""
    import bias
    from novelty import wl_features
    kw = {"inductor_q": inductor_q} if inductor_q else {}
    nl, _, rep, _ = bias.insert_bias(topo, sweep=True, **kw)
    m = metrics
    prov = provenance
    if not rep.get("skipped") and nl.two_port:
        body = E.body_of(nl.emit())
        m = _enrich_nf(body, best_params, spec, metrics)
        if nf_is_gated(spec) and (m or {}).get("nf_db") is not None:
            nb = _noise_budget_row(body, best_params, spec)
            if nb:                       # input features for the critic (WP-L5)
                prov = dict(provenance or {}, noise_budget=nb)
    _log_l2(spec, m, feasible, n_evals, None, None, best_params, None, topo,
            wl_features(topo)[0], prov,
            _zoaf_cfg(0, 0, 0, 0, recipe, inductor_q=inductor_q, spec=spec),
            repeat_probe=repeat_probe)
    return m


def backfill_corpus(spec_name="wifi24", indices=None, seed=1, inductor_q=12,
                    limit=None, log=True):
    """Backfill L2 rows for the in-scope corpus LNAs (01-DATA §4 item 1).

    Sizes every screen-passing corpus LNA vs `spec` and logs one L2 row each.
    Idempotent: a (wl_hash, spec) key already in the store is skipped, so an
    interrupted run resumes cleanly on relaunch. Inductors get finite Q by
    default (real corpus LNAs need it -- HANDOVER-EXEC §6.1)."""
    from bias import topo_from_index, REPO
    from novelty import wl_features
    spec = _spec_for_sizing(spec_name)
    if indices is None:
        indices = list(range(461, 493)) + list(range(1081, 1091))
    done = ds.existing_l2_keys()
    print(f"corpus L2 backfill vs {spec_name} (inductor_q={inductor_q}, nf gated "
          f"off): {len(indices)} candidate indices\n")
    print(f"{'idx':>5} {'scr':>4} {'dev':>3} {'sims':>5} {'S11':>7} {'S21':>7} "
          f"{'Idd':>6} {'feasible':>9}")
    n_sized = n_feas = n_skip = 0
    for i in indices:
        p = os.path.join(REPO, "Dataset", str(i), f"Sequence_total{i}.npy")
        if not os.path.exists(p):
            continue
        topo = topo_from_index(i)
        if not spec.structural_screen(topo)[0]:
            print(f"{i:>5} {'no':>4} {topo.n_devices:>3}   (screen reject)")
            continue
        if (wl_features(topo)[0], spec.name) in done:
            n_skip += 1
            print(f"{i:>5} {'yes':>4} {topo.n_devices:>3}   (already labeled, skip)")
            continue
        res = size_topology(topo, spec, seed=seed, inductor_q=inductor_q, log=log,
                            provenance={"source_arm": "corpus", "index": i,
                                        "inductor_q": inductor_q})
        n_sized += 1
        if res is None or res["metrics"] is None:
            print(f"{i:>5} {'yes':>4} {topo.n_devices:>3}   {'-':>5}  (bias/sim failed)")
        else:
            m = res["metrics"]
            n_feas += int(res["feasible"])
            print(f"{i:>5} {'yes':>4} {topo.n_devices:>3} {res['n_evals']:>5} "
                  f"{m['s11_db']:>7.1f} {m['s21_db']:>7.1f} {m.get('idd_ma') or 0:>6.2f} "
                  f"{'FEASIBLE' if res['feasible'] else 'no':>9}")
        if limit and n_sized >= limit:
            print(f"  (limit {limit} reached)")
            break
    print(f"\nsized {n_sized} new, {n_feas} feasible, {n_skip} already-present")
    return n_sized


def _size_ref(deck, sizable, fixed, spec_name, recipe, label, seed=1, log=True):
    """Size a hand-written reference deck vs a spec with ZOAF and (optionally) log
    the L2 row. Shared by the stage-B anchor re-derivation and the tapped-C
    gain-capable reference; returns (feasible, metrics)."""
    spec = _spec_for_sizing(spec_name)
    print("note: nf_db treated as unsupported (port-noise harness gap); "
          "gating on S11/S21/Idd.")
    body = E.body_of(os.path.join(HERE, "ref", deck))
    points = [] if log else None
    obj, names, decode, evaluate = make_objective(body, spec, sizable, fixed,
                                                  points=points)
    print(f"{label} vs {spec_name}: {len(names)} params, ZOAF (feasibility-first).")
    best_x, best_obj, n_evals = run_zoaf(obj, names, seed=seed)
    m = evaluate(best_x)
    prov = {"source_arm": recipe.split("-")[0], "ref_deck": deck, "seed": seed}
    # reference decks have no token topology, so key them by deck name -- otherwise
    # every ref row hashes to (None, spec) and they collide.
    if m is None:
        print(f"\nZOAF: {n_evals} sims -- sizing FAILED (no metrics; deck params?)")
        if log:
            _log_l2(spec, None, False, n_evals, points, best_x, decode(best_x),
                    best_obj, None, f"ref:{deck}", prov,
                    _zoaf_cfg(seed, 8, 8, 2, recipe, spec=spec))
        return False, None
    if log:
        m = _enrich_nf(body, decode(best_x), spec, m)   # physical NF for the row
    feas, viol = spec.feasible(m)
    if log:
        _log_l2(spec, m, feas, n_evals, points, best_x, decode(best_x), best_obj,
                None, f"ref:{deck}", prov, _zoaf_cfg(seed, 8, 8, 2, recipe,
                                                    spec=spec))
    print(f"\nZOAF: {n_evals} sims, best objective {best_obj:.4f}")
    print(spec.report(m))
    print("\nsized values:")
    for k, v in decode(best_x).items():
        if k in sizable:
            print(f"    {k:<7} {v}")
    print(f"\n=> {'FEASIBLE' if feas else 'infeasible: ' + str({k: round(v,3) for k,v in viol.items()})}"
          f"  [{label}]")
    return feas, m


def size_anchor(spec_name="wifi24", seed=1, log=True):
    sizable = {"pW": "W", "pLs": "L", "pLg": "L", "pLd": "L",
               "pCex": "C", "pCtnk": "C", "pVB": "VB", "pVB2": "VB"}
    fixed = {"pL": "45n", "pRB": "10k", "pQ": "10", "pF0": "2.442e9",
             "pRq": "{2*3.14159265*pF0*pLd/pQ}"}
    feas, _ = _size_ref("ref24_csdeg.cir", sizable, fixed, spec_name,
                        "anchor-v1", "anchor re-derivation", seed=seed, log=log)
    return feas


def size_tapped(spec_name="wifi24", seed=1, log=True):
    """Size the tapped-C gain-capable reference (Stage-0 day 3). The tapped
    transformer decouples gain from the 50 ohm load, so this is the deck expected
    to reach S21 >= 12 -- the first *feasible* label (Gate G4 by hand).

    The input match (Ls/Lg/Cex) and the series tap cap Ct1 are FIXED at the
    reference's known-good values -- the cascode isolates the input from the
    output tank, so the match does not need re-tuning per output-gain point, and
    freezing them keeps ZOAF out of the degenerate 'collapse the transformer'
    basin (Ct1->max, gain->0) it fell into when everything was free. ZOAF sizes
    the gain/bias/transform knobs {W, Ld, Ct2, VB, VB2}."""
    sizable = {"pW": "W", "pLd": "L", "pCt2": "C", "pVB": "VB", "pVB2": "VB"}
    fixed = {"pL": "45n", "pRB": "10k", "pQ": "10", "pF0": "2.442e9",
             "pRq": "{2*3.14159265*pF0*pLd/pQ}",
             "pLs": "1.35n", "pLg": "8n", "pCex": "440f", "pCt1": "0.3p"}
    feas, _ = _size_ref("ref24_tapped.cir", sizable, fixed, spec_name,
                        "tapped-v1", "tapped-C gain reference", seed=seed, log=log)
    return feas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchor", action="store_true",
                    help="run the stage-B anchor re-derivation test")
    ap.add_argument("--tapped", action="store_true",
                    help="size the tapped-C gain-capable reference (Gate G4 by hand)")
    ap.add_argument("--scoreboard", metavar="DIR",
                    help="size the top spec-passing candidates in a generation dir")
    ap.add_argument("--corpus-l2", action="store_true",
                    help="backfill L2 rows for the in-scope corpus LNAs (01-DATA §4)")
    ap.add_argument("--spec", default="wifi24")
    ap.add_argument("--n", type=int, default=0,
                    help="max candidates (--scoreboard, default 4) / max new "
                         "labels (--corpus-l2, default all)")
    ap.add_argument("--inductor-q", type=int, default=12,
                    help="finite inductor Q for --corpus-l2 sizing (0 = ideal)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--no-log", action="store_true",
                    help="do not append L2/point rows to the label store")
    args = ap.parse_args()
    log = not args.no_log
    if args.anchor:
        return 0 if size_anchor(args.spec, seed=args.seed, log=log) else 1
    if args.tapped:
        return 0 if size_tapped(args.spec, seed=args.seed, log=log) else 1
    if args.scoreboard:
        scoreboard(args.scoreboard, args.spec, seed=args.seed,
                   max_candidates=(args.n or 4), log=log)
        return 0
    if args.corpus_l2:
        backfill_corpus(args.spec, seed=args.seed, log=log,
                        inductor_q=(args.inductor_q or None),
                        limit=(args.n or None))
        return 0
    ap.error("give --anchor, --scoreboard DIR, or --corpus-l2")


if __name__ == "__main__":
    sys.exit(main())

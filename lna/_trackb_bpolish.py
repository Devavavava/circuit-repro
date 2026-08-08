"""Bounds-respecting polish (Track B sidecar).

`size.polish` is a coordinate pattern search that scales each sizable parameter by
(1 +/- step) and **never clamps to `size.kind_ranges(spec)`** -- so it can and does
walk parameters outside the spec's declared device box (measured: it sized a
`dhruva-l1` candidate with L = 18.1 nH and 15.6 nH against `topology.l_max = 15 nH`).
ZOAF (`size.size_topology`) searches inside that box, so only polish-derived points
are affected.

This is a byte-for-byte copy of `size.polish`'s ascent with one change: every trial
value is clamped into its kind's [lo, hi] range, and a coordinate whose base already
sits on a bound cannot step outward. Track B's concurrency contract forbids editing
`size.py`, so the fix lives here and the finding is reported for Track A to land.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract as E
import size


def in_box(params, sizable, spec):
    """-> list of (name, kind, value, lo, hi) for params outside their box."""
    rng = size.kind_ranges(spec)
    bad = []
    for name, kind in sizable.items():
        if name not in params or kind not in rng:
            continue
        try:
            v = float(params[name])
        except (TypeError, ValueError):
            continue
        lo, hi = rng[kind][0], rng[kind][1]
        if v < lo * (1 - 1e-9) or v > hi * (1 + 1e-9):
            bad.append((name, kind, v, lo, hi))
    return bad


def bounded_polish(topo, spec, prior_params, budget=400, inductor_q=12, exclude=()):
    import bias
    from datastore import margins_for
    kw = {"inductor_q": inductor_q} if inductor_q else {}
    nl, _, rep, _ = bias.insert_bias(topo, sweep=True, **kw)
    if rep.get("skipped") or not nl.two_port:
        return None
    body = E.body_of(nl.emit())
    sizable, _ = size.classify_params(nl)
    if exclude:
        sizable = {k: v for k, v in sizable.items() if k not in set(exclude)}
    nf_gated = size.nf_is_gated(spec)
    keys = [n for n, c in spec.constraints.items() if c.get("status") != "unsupported"]
    rng = size.kind_ranges(spec)

    def clamp(name, val):
        kind = sizable.get(name)
        if kind not in rng:
            return val
        lo, hi = rng[kind][0], rng[kind][1]
        return min(max(val, lo), hi)

    def min_margin(p):
        m = size.eval_metrics(body, p, spec, nf_gated=nf_gated)
        if m is None:
            return -1e9, None
        mg = margins_for(spec, m)
        vals = [(mg.get(k) or {}).get("margin") for k in keys]
        vals = [v for v in vals if v is not None]
        if len(vals) < len(keys):
            return -1e9, m
        return (min(vals) if vals else -1e9), m

    # start strictly inside the box: clamp the incoming point first
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
                if abs(cand - base) <= 1e-18:       # already pinned at the bound
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

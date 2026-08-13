"""WP-SENS -- SENSITIVITY sweep on the Gate-D4-SIM point (FINDINGS SS39).

Named a *sensitivity* sweep on purpose: the 45 nm behavioral BSIM4 include has
NO process-corner cards (no fast/slow devices), so fab corners cannot be
simulated at this fidelity. What CAN be measured is how the shipped design
point moves under environment and component perturbations:

    temp      circuit temperature (.temp card appended to the deck body)
    vdd       supply scaling (pVDD override -- the .param mechanism the
              shipped flow already uses: build_deck appends params AFTER the
              body defaults, so the last definition wins)
    passives  ALL R/C/L values scaled globally by one factor (the two Q-loss
              resistors RQL* = pINDW0*pLV/pINDQ follow their inductors
              automatically, so a +10% L carries its loss up with it)
    q         inductor Q (pINDQ override; nominal 12)
    combo     the worst mandated setting of the two most damaging axes at once

Under each perturbation the FOUR-band simultaneous gates (recreate.py --cross
protocol) are re-measured at the FIXED dhruva-l5 params of `ace8383c2fa68d03`.
Nothing is resized, nothing is tuned; the deliverable is fragility -- which
constraint flips first, at what perturbation size, per axis.

Honest scope notes:
  * NF at swept temperature: the series-Rs harness references 4kT*Rs at the
    program's frozen 300 K constant while the simulated circuit (source
    resistor included) sits at the swept temperature -- so hot sweeps slightly
    overstate NF vs the strict fixed-T0-source definition, cold sweeps
    slightly understate it. Stated, not corrected: the frozen NF metric is not
    redefined here.
  * `.temp 27` is run as an invariance control (ngspice's default nominal
    temperature) and must reproduce the unperturbed baseline exactly -- the
    proof that the injection mechanism itself changes nothing. No shared file
    is edited by this driver at all.

Usage (torch-free python; each axis is its own invocation so runs stay short):
    python lna/corners.py --axis baseline|temp|vdd|passives|q|combo|report
    python lna/corners.py --axis all          # everything incl. report
Results accumulate in lna/out/_sens_d4sim.json (gitignored via lna/out).
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import size as S                    # noqa: E402  (read-only use)
from topology import Topology       # noqa: E402

REPRO = os.path.join(HERE, "repro", "dhruva-best")
BANDS = {"s": "dhruva-s", "l1": "dhruva-l1", "l2": "dhruva-l2", "l5": "dhruva-l5"}
POINT = "l5"                        # the designated D4-SIM sizing (FINDINGS SS35.3)
VDD_NOM = None                      # None = the point's own pVDD; else override (V)
OUT = os.path.join(HERE, "out", "_sens_d4sim.json")

# one-at-a-time grids; mandated extremes plus inner points so the flip SIZE is
# resolved, not just the flip existence
TEMP_GRID = [-40, -20, 0, 40, 60, 85]           # degC (nominal 27)
VDD_FACT = [0.90, 0.95, 0.975, 0.99, 1.01, 1.025, 1.05, 1.10]
PASS_FACT = [0.90, 0.95, 0.98, 0.99, 1.01, 1.02, 1.05, 1.10]
Q_GRID = [8, 10, 16, 20]                        # nominal 12
# mandated extremes per axis, used for the combo pick
MANDATED = {"temp": [-40, 85], "vdd": [0.90, 1.10], "passives": [0.90, 1.10],
            "q": [8, 20]}


def load_point():
    tok = json.load(open(os.path.join(REPRO, "tokens.json"), encoding="utf-8"))
    prep = S.prepared_body(Topology(tok), inductor_q=12)
    if prep is None:
        raise SystemExit("bias insert skipped")
    body, sizable, fixed = prep
    params = json.load(open(os.path.join(REPRO, f"dhruva-{POINT}.params.json"),
                            encoding="utf-8"))
    if VDD_NOM is not None:
        params["pVDD"] = f"{float(VDD_NOM):.6g}"   # sweep runs around this nominal
    specs = {t: S._spec_for_sizing(n) for t, n in BANDS.items()}
    return body, sizable, params, specs


def perturb(body, params, sizable, temp=None, vdd_f=None, pass_f=None, q=None):
    b, p = body, dict(params)
    if temp is not None:
        b = body.rstrip() + f"\n.temp {temp:g}\n"
    if vdd_f is not None:
        p["pVDD"] = f"{float(params['pVDD']) * vdd_f:.6g}"
    if pass_f is not None:
        for k, kind in sizable.items():
            if kind in ("R", "C", "L") and k in p:
                p[k] = f"{float(p[k]) * pass_f:.6g}"
    if q is not None:
        p["pINDQ"] = f"{q:g}"
    return b, p


def margins(m, spec):
    """Positive = pass, in the constraint's own unit (dB / mA)."""
    c = spec.constraints
    return {
        "s11": float(c["s11_max_db"]["max"]) - m["s11_max_db"],
        "s21": m["s21_db"] - float(c["s21_db"]["min"]),
        "idd": float(c["idd_ma"]["max"]) - m["idd_ma"],
        "nf": float(c["nf_db"]["max"]) - m["nf_db"],
    }


def eval_point(body, params, specs, tag):
    """One perturbation -> 4 band evals -> worst (simultaneous) margins."""
    worst, per_spec, kmin = {}, {}, None
    for sx, spec in specs.items():
        m = S.eval_metrics(body, params, spec, nf_gated=True)
        if m is None or m.get("nf_db") is None:
            print(f"  {tag:<26} {BANDS[sx]}: SIM FAILED")
            per_spec[sx] = None
            worst = None
            break
        g = margins(m, spec)
        per_spec[sx] = dict(g, s11_max=m["s11_max_db"], s21=m["s21_db"],
                            idd=m["idd_ma"], nf=m["nf_db"], k_min=m["k_min"])
        kmin = m["k_min"] if kmin is None else min(kmin, m["k_min"])
        for k, v in g.items():
            worst[k] = v if k not in worst else min(worst[k], v)
    if worst is not None:
        fails = [k for k, v in worst.items() if v < 0]
        print(f"  {tag:<26} S11m={worst['s11']:+8.4f}  S21m={worst['s21']:+7.3f}  "
              f"Iddm={worst['idd']:+7.3f}  NFm={worst['nf']:+7.3f}  "
              f"Kmin={kmin:7.3f}  {'PASS' if not fails else 'FAIL ' + ','.join(fails)}")
    return dict(tag=tag, worst=worst, k_min=kmin, per_spec=per_spec)


def _load_out():
    if os.path.exists(OUT):
        return json.load(open(OUT, encoding="utf-8"))
    return {}


def _save_out(d):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1)


def run_axis(axis):
    body, sizable, params, specs = load_point()
    res = _load_out()
    rows = []
    if axis == "baseline":
        rows.append(eval_point(body, params, specs, "baseline"))
        b, p = perturb(body, params, sizable, temp=27)
        r = eval_point(b, p, specs, "temp=27 (invariance)")
        base = rows[0]["worst"]
        drift = (max(abs(r["worst"][k] - base[k]) for k in base)
                 if r["worst"] and base else float("nan"))
        print(f"  invariance |drift| = {drift:g} (must be ~0)")
        rows[-1:] = [r]
        rows.insert(0, rows.pop())  # keep order: baseline, invariance
        rows = rows[::-1]
    elif axis == "temp":
        for t in TEMP_GRID:
            b, p = perturb(body, params, sizable, temp=t)
            rows.append(dict(eval_point(b, p, specs, f"temp={t:+d}C"), x=t))
    elif axis == "vdd":
        for f in VDD_FACT:
            b, p = perturb(body, params, sizable, vdd_f=f)
            rows.append(dict(eval_point(b, p, specs, f"vdd x{f:g}"), x=f))
    elif axis == "passives":
        for f in PASS_FACT:
            b, p = perturb(body, params, sizable, pass_f=f)
            rows.append(dict(eval_point(b, p, specs, f"passives x{f:g}"), x=f))
    elif axis == "q":
        for q in Q_GRID:
            b, p = perturb(body, params, sizable, q=q)
            rows.append(dict(eval_point(b, p, specs, f"indQ={q:g}"), x=q))
    elif axis == "combo":
        picks = _combo_picks(res)
        kw = {}
        for ax, setting in picks:
            kw.update({"temp": setting} if ax == "temp" else
                      {"vdd_f": setting} if ax == "vdd" else
                      {"pass_f": setting} if ax == "passives" else
                      {"q": setting})
        b, p = perturb(body, params, sizable, **kw)
        tag = "combo " + "+".join(f"{a}={s:g}" for a, s in picks)
        rows.append(dict(eval_point(b, p, specs, tag), picks=picks))
    res[axis] = rows
    _save_out(res)


def _degradation(res, axis, setting):
    """min-margin drop vs baseline at one mandated setting (NF+S21+S11+Idd
    aggregated as the worst per-constraint margin)."""
    base = res["baseline"][-1]["worst"]
    for r in res.get(axis, []):
        if r.get("x") == setting and r.get("worst"):
            return min(r["worst"][k] - base[k] for k in base)
    return 0.0


def _combo_picks(res):
    if "baseline" not in res:
        raise SystemExit("run --axis baseline (and the four axes) first")
    scored = []
    for ax, settings in MANDATED.items():
        cand = min(settings, key=lambda s: _degradation(res, ax, s))
        scored.append((_degradation(res, ax, cand), ax, cand))
    scored.sort()
    return [(ax, s) for _, ax, s in scored[:2]]


def report():
    res = _load_out()
    base = res["baseline"][-1]["worst"]
    print("\n=== flip table (per axis: first constraint to fail, at what size) ===")
    need = dict(base)  # running max degradation per constraint
    for ax in ("temp", "vdd", "passives", "q", "combo"):
        first = None
        for r in res.get(ax, []):
            if not r.get("worst"):
                continue
            for k in base:
                need[k] = min(need[k], base[k] - (base[k] - r["worst"][k]))
            fails = sorted((k for k, v in r["worst"].items() if v < 0),
                           key=lambda k: r["worst"][k])
            if fails and first is None:
                first = (r["tag"], fails)
        # smallest-|perturbation| flip: rows are evaluated in grid order, so
        # re-scan by |distance from nominal| for the honest "first"
        rows = [r for r in res.get(ax, []) if r.get("worst")]
        nomin = {"temp": 27, "vdd": 1.0, "passives": 1.0, "q": 12}.get(ax)
        if nomin is not None:
            rows.sort(key=lambda r: abs(r.get("x", nomin) - nomin))
        flip = next(((r["tag"], [k for k, v in r["worst"].items() if v < 0])
                     for r in rows if any(v < 0 for v in r["worst"].values())),
                    None)
        print(f"  {ax:<9} " + (f"first flip: {flip[0]} -> {','.join(flip[1])}"
                               if flip else "no flip anywhere on the grid"))
    print("\n=== implied margins a hardened point needs (survive the full sweep) ===")
    for k in base:
        worst_seen = min((r["worst"][k] for ax in res for r in res[ax]
                          if isinstance(r, dict) and r.get("worst")), default=base[k])
        print(f"  {k:<4} baseline {base[k]:+8.4f}  worst-under-sweep {worst_seen:+8.4f}"
              f"  -> needs >= {base[k] - worst_seen:+8.4f} of margin at nominal")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--axis", required=True,
                    choices=["baseline", "temp", "vdd", "passives", "q",
                             "combo", "report", "all"])
    ap.add_argument("--point", default="l5",
                    help="which repro sizing to sweep: dhruva-<point>.params.json")
    ap.add_argument("--vdd-nominal", type=float, default=None,
                    help="override the point's pVDD nominal (V) for the whole sweep")
    a = ap.parse_args()
    POINT = a.point
    VDD_NOM = a.vdd_nominal
    if a.point != "l5" or a.vdd_nominal is not None:
        tag = a.point + (f"_v{a.vdd_nominal:g}" if a.vdd_nominal is not None else "")
        OUT = os.path.join(HERE, "out", f"_sens_d4sim_{tag}.json")
    if a.axis == "all":
        for ax in ("baseline", "temp", "vdd", "passives", "q", "combo"):
            print(f"--- axis: {ax} ---")
            run_axis(ax)
        report()
    elif a.axis == "report":
        report()
    else:
        run_axis(a.axis)

"""Validate the two-port stability harness, and audit the dhruva winners (WP-D4b).

The pipeline had NO stability check at all: a 3-stage feedback amplifier can size
to 37.8 dB of gain and a beautiful S11 while being an oscillator, and nothing in
the harness would notice. `extract.control_block` now derives the full stability
set from the S-matrix the `sp` analysis already computes (so it is FREE -- no
extra ngspice call): Rollett K, |Delta|, mu (load plane) and mu_src (source
plane), each at f0 and at its worst point over the sweep band.

Three kinds of check here:

  1. ANALYTIC GOLDEN (exact). For a series impedance R between two 50 ohm ports,
     S11 = S22 = R/(R+100) and S21 = S12 = 100/(R+100), from which K, |Delta| and
     mu follow in closed form. We hand ngspice that circuit and require the
     measured factors to match the closed form. This is a *boundary* golden: a
     reciprocal resistive two-port sits exactly at K = mu = 1, so any sign or
     normalization error in the formula shows up immediately.
  2. QUALITATIVE GOLDENS. A matched unilateral amplifier (S12 = 0) must read
     unconditionally stable with |Delta| ~ 0; a negative-resistance input
     (|S11| > 1) must read conditionally stable / potentially unstable. These
     pin the two ends of the verdict function.
  3. REAL CIRCUITS. The three reference decks and the Gate-D1/D2 dhruva 4-band
     winner, per band -- in-band (the spec's own sweep) and over a WIDE audit
     window, because feedback amplifiers oscillate out of band, where no spec
     constraint is ever evaluated.

    python lna/ref/check_stab.py
    python lna/ref/check_stab.py --wide-lo 1e8 --wide-hi 4e10
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.dirname(HERE)
sys.path.insert(0, LNA)
import extract as E               # noqa: E402
import size                       # noqa: E402
import bias                       # noqa: E402
import templates as T             # noqa: E402
from topology import Topology     # noqa: E402

REPRO = os.path.join(LNA, "repro")
ARCH = "rfbcs3_tank_cc21_bf0"
BANDS = ["dhruva-l5", "dhruva-l2", "dhruva-l1", "dhruva-s"]
TOL = 0.02          # relative tolerance on the analytic golden


def _series_r_body(r):
    return "\n".join([
        f"* stability golden: series R = {r} ohm between two 50 ohm ports",
        "Vp1 p1 0 dc 0 ac 1 portnum 1 z0 50",
        f"Rser p1 p2 {r:g}",
        "Vp2 p2 0 dc 0 ac 0 portnum 2 z0 50",
        ".option rshunt=1e12"])


def _series_r_closed_form(r, z0=50.0):
    """K, |Delta|, mu for a series impedance R between two z0 ports (real, so all
    S-params are real and the algebra is exact)."""
    s11 = s22 = r / (r + 2 * z0)
    s21 = s12 = 2 * z0 / (r + 2 * z0)
    delta = s11 * s22 - s12 * s21
    k = (1 - s11 ** 2 - s22 ** 2 + delta ** 2) / (2 * abs(s12 * s21))
    mu = (1 - s11 ** 2) / (abs(s22 - delta * s11) + abs(s12 * s21))
    return k, abs(delta), mu


def analytic_golden():
    print("== 1. analytic golden: series R between two 50 ohm ports ==")
    print(f"   {'R':>8} {'K meas':>9} {'K calc':>9} {'|D| meas':>9} {'|D| calc':>9} "
          f"{'mu meas':>9} {'mu calc':>9}")
    ok = True
    for r in (10.0, 50.0, 200.0, 1000.0):
        m = E.measure_stability(_series_r_body(r), None, 2e9, 1e9, 3e9, npts=11)
        kc, dc, muc = _series_r_closed_form(r)
        if m is None:
            print(f"   {r:>8g}   (measurement failed)")
            ok = False
            continue
        km, dm, mum = m["k_f0"], m["delta_f0"], m["mu_f0"]
        good = (abs(km - kc) <= TOL * max(abs(kc), 1)
                and abs(dm - dc) <= TOL * max(abs(dc), 1)
                and abs(mum - muc) <= TOL * max(abs(muc), 1))
        ok = ok and good
        print(f"   {r:>8g} {km:>9.4f} {kc:>9.4f} {dm:>9.4f} {dc:>9.4f} "
              f"{mum:>9.4f} {muc:>9.4f}   [{'ok' if good else 'MISMATCH'}]")
    print(f"   -> {'PASS' if ok else 'FAIL'} (tol {TOL:.0%})\n")
    return ok


def qualitative_goldens():
    print("== 2. qualitative goldens: unilateral-matched vs negative-resistance ==")
    uni = "\n".join([
        "* matched unilateral gain-10 amp: S12 = 0, S11 = S22 = 0",
        "Vp1 p1 0 dc 0 ac 1 portnum 1 z0 50",
        "Rin p1 0 50", "Eamp x 0 p1 0 10", "Rout x p2 50",
        "Vp2 p2 0 dc 0 ac 0 portnum 2 z0 50", ".option rshunt=1e12"])
    neg = "\n".join([
        "* negative-resistance input (|S11| > 1) behind a unilateral buffer",
        "Vp1 p1 0 dc 0 ac 1 portnum 1 z0 50",
        "Rneg p1 0 -100", "Ebuf x 0 p1 0 1", "Rout x p2 50",
        "Vp2 p2 0 dc 0 ac 0 portnum 2 z0 50", ".option rshunt=1e12"])
    ok = True
    for label, body, want in (("unilateral matched", uni, "unconditional"),
                              ("negative-resistance in", neg, "conditional")):
        m = E.measure_stability(body, None, 2e9, 1e9, 3e9, npts=11)
        if m is None:
            print(f"   {label:<24} (measurement failed)")
            ok = False
            continue
        got, why = E.stability_verdict(dict(m, k_min=m["k_min"], delta_max=m["delta_max"]))
        good = got == want
        ok = ok and good
        print(f"   {label:<24} K={m['k_f0']:>11.4g} |D|={m['delta_f0']:>8.4g} "
              f"mu={m['mu_f0']:>11.4g}  -> {got} (want {want}) "
              f"[{'ok' if good else 'MISMATCH'}]")
    print(f"   -> {'PASS' if ok else 'FAIL'}\n")
    return ok


def _report(label, m, target_note=""):
    v, why = E.stability_verdict(m)
    lo, hi = m.get("stab_band", [0, 0])
    print(f"   {label:<26} K_f0={m['k_f0']:>9.3g} K_min={m['k_min']:>9.3g} "
          f"mu_min={m['mu_min']:>8.3g} mu_src_min={m['mu_src_min']:>8.3g} "
          f"|D|max={m['delta_max']:>7.3g}  [{lo/1e9:.2f}-{hi/1e9:.2f} GHz]  "
          f"{v.upper()}{target_note}")
    return v


def ref_decks():
    print("== 3. reference decks (in-band, the deck's own sweep) ==")
    out = {}
    for deck, band in (("ref24_cg.cir", "wifi24"), ("ref24_csdeg.cir", "wifi24"),
                       ("ref24_tapped.cir", "wifi24")):
        p = os.path.join(HERE, deck)
        if not os.path.exists(p):
            continue
        spec = size._spec_for_sizing(band, nf_gate=False)
        body = E.body_of(p)
        params = _deck_params(p)
        m = E.run_and_extract(body, params, spec)
        if m is None or m.get("k_min") is None:
            print(f"   {deck:<26} (simulation failed)")
            continue
        out[deck] = _report(deck, m)
    print()
    return out


def _deck_params(path):
    """Pull the deck's own .param assignments back out (body_of strips them)."""
    params = {}
    for ln in open(path, encoding="utf-8"):
        s = ln.strip()
        if not s.lower().startswith(".param"):
            continue
        for mark in (";", "$"):          # strip inline comments: they contain '='
            if mark in s:
                s = s.split(mark, 1)[0]
        for tok in s.split()[1:]:
            if "=" in tok:
                k, v = tok.split("=", 1)
                if k and v:
                    params[k] = v
    return params or None


def dhruva_winner(wide_lo, wide_hi):
    """The Gate-D1/D2 winner, per band: in-band and over a wide audit window."""
    print("== 4. Gate-D1/D2 dhruva 4-band winner (rfbcs3_tank_cc21_bf0) ==")
    pf = os.path.join(REPRO, "dhruva-4band.params.json")
    if not os.path.exists(pf):
        print("   (dhruva-4band.params.json missing)")
        return {}
    allp = json.load(open(pf))
    a = next(a for a in T.archetypes() if a["name"] == ARCH)
    topo = Topology(a["seq"])
    nl, _, rep, _ = bias.insert_bias(topo, sweep=True, inductor_q=12)
    body = E.body_of(nl.emit())
    out = {}
    for band in BANDS:
        entry = allp.get(band) or {}
        params = entry.get("best_params")
        if params is None:
            print(f"   {band:<26} (no stored params)")
            continue
        spec = size._spec_for_sizing(band, nf_gate=False)
        f0 = float(spec.band["f0"])
        m = E.run_and_extract(body, params, spec)
        if m is None or m.get("k_min") is None:
            print(f"   {band:<26} (simulation failed)")
            continue
        v_in = _report(f"{band} in-band", m,
                       f"  (S21 {m['s21_db']:.1f} dB)")
        w = E.measure_stability(body, params, f0, wide_lo, wide_hi, npts=401)
        v_wide = _report(f"{band} WIDE", w) if w else "unknown"
        out[band] = {"in_band": v_in, "wide": v_wide, "metrics": m, "wide_metrics": w}
    print()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wide-lo", type=float, default=1e8)
    ap.add_argument("--wide-hi", type=float, default=2e10)
    a = ap.parse_args()
    ok = analytic_golden()
    ok = qualitative_goldens() and ok
    ref_decks()
    res = dhruva_winner(a.wide_lo, a.wide_hi)
    bad = [b for b, r in res.items()
           if r["in_band"] != "unconditional" or r["wide"] != "unconditional"]
    print(f"check_stab: harness {'GREEN' if ok else 'RED'}; "
          + ("dhruva winner unconditionally stable on every band, in-band and wide"
             if res and not bad else
             f"dhruva winner NOT unconditionally stable: {bad}" if res else
             "dhruva winner not evaluated"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

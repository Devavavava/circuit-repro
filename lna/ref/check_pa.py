"""Golden for the PA large-signal harness (lna/pa_harness.py, circuit_class pa).

Program rule (same as check_iip3): no PA number is quoted until this is GREEN.
The reference is a MEMORYLESS behavioral amplifier y = g1*x - g3*x^3 (a B-source
-- no BSIM, no PDK, no fitting) whose 1 dB compression point is exact and closed
form, plus a PAE sanity on an ideal class-A stage.

REFERENCE ALGEBRA -- P1dB of y = g1*x - g3*x^3
----------------------------------------------
Drive node x with a single tone x = A*cos(wt). Expand:

    y = g1*A*cos - g3*A^3*cos^3
      = g1*A*cos - g3*A^3*( (3/4)cos + (1/4)cos(3wt) )

The FUNDAMENTAL output amplitude is therefore

    Yfund(A) = g1*A - (3/4)*g3*A^3                    (g3 > 0 => compressive)

Small-signal gain is g1 (the A->0 slope of Yfund/A). The 1 dB compression point
is the A at which the large-signal gain has dropped 1 dB below g1:

    20*log10( Yfund(A)/(g1*A) ) = -1
    1 - (3/4)*(g3/g1)*A^2 = 10^(-1/20) = 0.8912509...
    (3/4)*(g3/g1)*A^2_1dB = 1 - 0.8912509 = 0.1087490
    A^2_1dB = (0.1087490 * 4/3) * (g1/g3) = 0.1449987 * (g1/g3)

THE MEASUREMENT NETWORK (refers the port back to node x)
-------------------------------------------------------
The harness drives an AVAILABLE power Pav = Vemf^2/(8*Z0) behind a 50 ohm
source into a 50 ohm shunt Rin at x, so v(x) = Vemf/2 (H = 1/2, purely
resistive -- no reactance, so the integrator adds nothing to the compression
arithmetic). Thus at node x the tone amplitude is A = Vemf/2, and

    Pav = Vemf^2/(8*Z0) = (2A)^2/(8*Z0) = A^2/(2*Z0)

so the INPUT-referred P1dB in dBm is

    P1dB_in = 10*log10( A^2_1dB / (2*Z0) * 1e3 )                     [dBm]

The output B-source is ideal (zero output impedance), so v(y) = Yfund into the
50 ohm load and the OUTPUT-referred P1dB is

    P1dB_out = 10*log10( Yfund(A_1dB)^2 / (2*Z0) * 1e3 )            [dBm]
             = P1dB_in + gain_ss - 1                                (identity check)

with gain_ss = 20*log10(g1) (v(y)/v(x) at small signal, both across 50 ohm, so
power gain = voltage gain here).

CHECKS (tolerances stated BEFORE the run)
-----------------------------------------
  P1  two (g1, g3) pairs: measured input-P1dB within 0.3 dB of closed form,
      output-P1dB within 0.3 dB, small-signal gain within 0.1 dB.
  P2  the identity P1dB_out == P1dB_in + gain_ss - 1 holds in the MEASURED
      numbers to 0.05 dB (internal consistency of the interpolator).
  P3  PAE sanity on an ideal class-A point: a linear stage (g3->0 tiny) with a
      KNOWN Idd and Vdd has drain efficiency = Pout/Pdc and PAE = (Pout-Pin)/Pdc;
      we set Pdc so the numbers are exact and require the harness's pae_pct /
      drain_pct to match within 1 %-point.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.dirname(HERE)
sys.path.insert(0, LNA)

import iip3 as I                       # noqa: E402
import pa_harness as PA                # noqa: E402

Z0 = 50.0
F0 = 1.5e9                             # on-grid RF; the method must not care

TOL_P1DB = 0.30       # dB, vs closed form
TOL_GAIN = 0.10       # dB
TOL_IDENT = 0.05      # dB, internal identity
TOL_PAE = 1.0         # %-points


def _amp_body(g1, g3, vemf, f1, idd_src=None, vdd=None):
    """y = g1*v(x) - g3*v(x)^3, 50-ohm drive into 50-ohm Rin at x, 50-ohm load.

    If idd_src is given, add a supply Vdd with a resistor drawing a KNOWN dc
    current so Pdc = Vdd*Idd is exactly controllable for the PAE golden. The
    supply node is not connected to the signal path (pure DC), so it does not
    perturb the AM-AM measurement."""
    lines = ["* PA golden: memoryless y = g1 x - g3 x^3, 50-ohm terminations",
             PA.single_tone_drive("x", vemf, f1),
             "Rin x 0 50",
             f"Bnl y 0 V = {g1:.10g}*v(x) - {g3:.10g}*v(x)*v(x)*v(x)",
             "Rload y 0 50",
             ".option reltol=1e-5"]
    if idd_src is not None and vdd is not None:
        # a DC load drawing exactly idd_src amps from Vdd: R = Vdd/Idd.
        lines += [f"Vsup VDD 0 dc {vdd:g}",
                  f"Rdc VDD 0 {vdd / idd_src:.10g}"]
    return "\n".join(lines), "y"


def analytic_p1db(g1, g3):
    """(P1dB_in dBm, P1dB_out dBm, gain_ss dB) -- closed form (see docstring)."""
    a2 = 0.1087490 * (4.0 / 3.0) * (g1 / g3)
    a = math.sqrt(a2)
    yfund = g1 * a - 0.75 * g3 * a ** 3
    p1_in = 10 * math.log10(a2 / (2 * Z0) * 1e3)
    p1_out = 10 * math.log10(yfund ** 2 / (2 * Z0) * 1e3)
    gain = 20 * math.log10(g1)
    return p1_in, p1_out, gain


def _body_fn(g1, g3, **extra):
    f1 = I.snap(F0)
    return (lambda vemf, _f1, g1=g1, g3=g3: _amp_body(g1, g3, vemf, _f1, **extra))


def p_pair(g1, g3, pins):
    ana_in, ana_out, ana_gain = analytic_p1db(g1, g3)
    print(f"    g1={g1:g} g3={g3:g}: analytic P1dB_in = {ana_in:+.3f} dBm, "
          f"P1dB_out = {ana_out:+.3f} dBm, gain = {ana_gain:+.3f} dB")
    # a vdd/idd pair so pae fields are populated (not checked here; P3 checks it)
    fn = _body_fn(g1, g3, idd_src=10e-3, vdd=1.8)
    res = PA.pa_sweep(fn, F0, pins, vdd=1.8, verbose=False)
    if not res["ok"]:
        print(f"    RED: {res['why']}")
        return False
    if res["p1db_in"] is None:
        print(f"    RED: sweep never reached 1 dB compression "
              f"(widen pins; gain_ss={res['gain_ss']:.2f})")
        return False
    d_in = res["p1db_in"] - ana_in
    d_out = res["p1db_out"] - ana_out
    d_gain = res["gain_ss"] - ana_gain
    ident = res["p1db_out"] - (res["p1db_in"] + res["gain_ss"] - 1.0)
    ok = (abs(d_in) <= TOL_P1DB and abs(d_out) <= TOL_P1DB
          and abs(d_gain) <= TOL_GAIN and abs(ident) <= TOL_IDENT)
    print(f"      measured P1dB_in = {res['p1db_in']:+.3f} (D {d_in:+.3f}, tol {TOL_P1DB})   "
          f"P1dB_out = {res['p1db_out']:+.3f} (D {d_out:+.3f})")
    print(f"      gain_ss = {res['gain_ss']:.3f} (D {d_gain:+.3f})   "
          f"identity resid {ident:+.4f} dB   psat={res['psat_dbm']:+.2f} "
          f"({'lower bound' if res['psat_is_bound'] else 'saturated'})   "
          f"{'GREEN' if ok else 'RED'}")
    return ok


def p3_pae():
    print("P3  PAE / drain efficiency sanity (ideal ~class-A, known Pdc)")
    # a mildly compressive stage that DOES reach P1dB within the sweep, so the
    # pae/drain fields are populated at a real compression point; a known
    # Idd=10 mA at Vdd=1.8 V => Pdc = 18 mW. The efficiency arithmetic (not the
    # device model) is what P3 certifies, so it is recomputed from the harness's
    # OWN P1dB Pout and the known Pdc.
    g1, g3 = 4.0, 0.5     # analytic P1dB_in ~ +10.6 dBm (same as pair 1)
    fn = _body_fn(g1, g3, idd_src=10e-3, vdd=1.8)
    pins = [-2, 2, 5, 8, 9.5, 10.5, 11.5, 13, 16]
    res = PA.pa_sweep(fn, F0, pins, vdd=1.8, verbose=False)
    if not res["ok"] or res["p1db_in"] is None or res["pae_pct"] is None:
        print(f"    RED: {res.get('why', 'no P1dB / no PAE')}")
        return False
    # recompute the expected efficiencies from the harness's OWN P1dB point and
    # the known Pdc -- this checks the pae/drain arithmetic, not the model.
    pdc = 1.8 * 10e-3
    pout_w = 10 ** (res["p1db_out"] / 10.0) * 1e-3
    pin_w = 10 ** (res["p1db_in"] / 10.0) * 1e-3
    exp_drain = pout_w / pdc * 100.0
    exp_pae = (pout_w - pin_w) / pdc * 100.0
    d_drain = res["drain_pct"] - exp_drain
    d_pae = res["pae_pct"] - exp_pae
    ok = abs(d_drain) <= TOL_PAE and abs(d_pae) <= TOL_PAE
    print(f"    at P1dB: Pout={res['p1db_out']:+.2f} dBm, Pdc={pdc*1e3:.1f} mW")
    print(f"    drain eff measured {res['drain_pct']:.2f}% vs expected "
          f"{exp_drain:.2f}% (D {d_drain:+.3f})")
    print(f"    PAE       measured {res['pae_pct']:.2f}% vs expected "
          f"{exp_pae:.2f}% (D {d_pae:+.3f})   {'GREEN' if ok else 'RED'}")
    return ok


def main():
    I.private_tmp()
    ok = True
    print("P1/P2  P1dB closed form + internal identity")
    # Pins must straddle each pair's analytic P1dB_in (+10.6 / +7.6 dBm), with a
    # small step near the crossing so the linear interpolation is tight.
    ok &= p_pair(4.0, 0.5, [-6, -2, 2, 5, 8, 9.5, 10.5, 11.5, 13, 16])
    ok &= p_pair(8.0, 2.0, [-8, -4, 0, 3, 6, 7, 8, 9, 11, 14])
    ok &= p3_pae()
    print("check_pa:", "GREEN" if ok else "RED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

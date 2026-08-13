"""Golden for the two-tone transient IIP3 harness (lna/iip3.py) -- WP-IIP3.

Program rule: no design number is quoted until this is GREEN. The reference is
a memoryless polynomial "amplifier" y = a1*x + a3*x^3 (a B-source -- no BSIM,
no PDK, no fitting anywhere) whose IIP3 is exact and closed form.

REFERENCE ALGEBRA
-----------------
With two equal tones of amplitude A at the nonlinearity's input node x:

    fund out  = a1*A + (9/4)*a3*A^3        (the compression term)
    IM3 out   = (3/4)*|a3|*A^3
    A_IP3^2   = (4/3) * a1/|a3|            (amplitude AT NODE x)

The harness reports *available* power at the port, Pav = Vemf^2/(8*50), so the
reference must be referred back through whatever linear network sits between
the port and node x. Let H(f) = v(x)/Vemf. Then Vemf_IP3 = A_IP3/|H| and

    IIP3_dBm = 10*log10( A_IP3^2 / (|H|^2 * 400) * 1e3 )
    gain_dB  = 20*log10( 2 * |H| * a1 * |H_out| )      (small signal)

TWO REFERENCE NETWORKS, on purpose
----------------------------------
R  "resistive": Rsrc 50 -> x, Rin 50 -> gnd, measured at the B-source node.
   H = 1/2, H_out = 1. Purely ALGEBRAIC -- no reactance, so ngspice's
   integrator contributes nothing. This isolates the extraction arithmetic
   (tone plan, DFT bins, slope-intercept fit) from the simulator.

C  "reactive": the same, plus a shunt Cin at x and an Rout/Cout/Rload
   divider after the B-source. Now every quantity the harness measures has
   been through trapezoidal integration on a nonuniform timestep grid and
   then through the linear resampler -- i.e. exactly the numerical path the
   LNA measurement takes. Both transfers stay closed form:

       H(f)     = 0.5 / (1 + j*2*pi*f*Rth*Cin),   Rth = 50||50 = 25
       H_out(f) = 0.5 / (1 + j*2*pi*f*Rth*Cout)

   The analytic value is evaluated at f0 while the tones sit at f0 +/- dF/2;
   |H| slopes by ~1e-3 dB over that offset, three orders below the tolerance.

CHECKS (tolerances stated here BEFORE the run; nothing is tuned to pass)
-----------------------------------------------------------------------
  G1  numeric floor: a3 = 0 on network C, so the IM3 bins can contain nothing
      but numerical distortion. Require floor <= -110 dBc. This check EARNED
      ITS KEEP: at the harness's original tmax = 10 ps default it returns
      -104.9 dBc and FAILS, and the fix was to converge the method (tmax ->
      5 ps, where the numerical IM3 drops into the broadband floor and stops
      moving) rather than to move the bar. See `lna/_iip3_floor.py` and the
      TMAX note in `lna/iip3.py`.
  G2  network R, two (a1, a3) pairs: slope-intercept IIP3 within 0.25 dB of
      analytic, free-fit IM3 slope 3 +/- 0.1, gain within 0.1 dB.
  G3  network C, two (a1, a3) pairs: same three tolerances -- this is the one
      that certifies the integrator + resampler.
  G4  timestep convergence on network C: re-run at 2x finer tmax, require
      |dIM3| < 0.5 dB (the harness's own `--conv` proof, run on a circuit
      whose right answer is known).
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import iip3 as I                                      # noqa: E402

F0 = 1.5e9          # arbitrary on-grid RF; the method must not care
RTH = 25.0          # 50 || 50, the Thevenin resistance seen by Cin / Cout
CIN = 2e-12         # pole at 3.183 GHz -> |H| is 0.871 dB down at 1.5 GHz
COUT = 1e-12        # pole at 6.366 GHz

TOL_IIP3 = 0.25     # dB, vs the closed-form value
TOL_SLOPE = 0.10    # dB/dB, vs 3
TOL_GAIN = 0.10     # dB, vs the closed-form small-signal gain
TOL_FLOOR_DBC = -110.0
TOL_CONV = 0.50     # dB IM3 shift at 2x finer timestep


def _lp(f, c):
    """|0.5 / (1 + j 2 pi f Rth C)| -- one shunt cap behind a 50||50 divider."""
    return 0.5 / math.hypot(1.0, 2 * math.pi * f * RTH * c)


def body_resistive(a1, a3, vemf, f1, f2):
    return "\n".join([
        "* IIP3 golden R: memoryless y = a1 x + a3 x^3, 50-ohm terminations",
        I.two_tone_drive("x", vemf, f1, f2),
        "Rin x 0 50",
        f"Bnl y 0 V = {a1:.10g}*v(x) + {a3:.10g}*v(x)*v(x)*v(x)",
        "Rload y 0 50",
        ".option reltol=1e-5",
    ]), "y"


def body_reactive(a1, a3, vemf, f1, f2):
    return "\n".join([
        "* IIP3 golden C: the same nonlinearity behind/into first-order RC",
        I.two_tone_drive("x", vemf, f1, f2),
        "Rin x 0 50",
        f"Cin x 0 {CIN:.10g}",
        f"Bnl y 0 V = {a1:.10g}*v(x) + {a3:.10g}*v(x)*v(x)*v(x)",
        "Rout y z 50",
        f"Cout z 0 {COUT:.10g}",
        "Rload z 0 50",
        ".option reltol=1e-5",
    ]), "z"


NETS = {                       # tag -> (body_fn, |H(f0)|, |H_out(f0)|)
    "R": (body_resistive, 0.5, 1.0),
    "C": (body_reactive, _lp(F0, CIN), _lp(F0, COUT)),
}


def analytic(tag, a1, a3):
    """(IIP3 dBm, small-signal gain dB) -- closed form, see module docstring."""
    _, h, hout = NETS[tag]
    a_ip3_sq = (4.0 / 3.0) * (a1 / abs(a3))
    return (10 * math.log10(a_ip3_sq / (h * h * 400.0) * 1e3),
            20 * math.log10(2 * h * a1 * hout))


def g1_floor():
    print(f"G1  numeric floor (network C, a3 = 0, Pin = -20 dBm; require "
          f"<= {TOL_FLOOR_DBC:.0f} dBc)")
    f0s, f1, f2, fl, fh = I.tone_plan(F0)
    body, node = body_reactive(10.0, 0.0, I.pav_dbm_to_vemf(-20.0), f1, f2)
    m, err = I.measure_point(body, node, f0s, f1, f2, fl, fh)
    if m is None:
        print(f"    RED: sim failed ({err})")
        return False
    dbc = m["pim3"] - m["pfund"]
    ok = dbc <= TOL_FLOOR_DBC
    print(f"    Pfund = {m['pfund']:+.2f} dBm, worst IM3 bin = "
          f"{m['pim3']:+.1f} dBm  ->  {dbc:.1f} dBc   "
          f"{'GREEN' if ok else 'RED'}")
    return ok


def g_pair(tag, a1, a3, pins):
    ana_iip3, ana_gain = analytic(tag, a1, a3)
    fn = NETS[tag][0]
    print(f"    a1={a1:g} a3={a3:g}: analytic IIP3 = {ana_iip3:+.3f} dBm, "
          f"gain = {ana_gain:+.3f} dB")
    res = I.iip3_sweep(lambda ve, f1, f2: fn(a1, a3, ve, f1, f2), F0, pins,
                       verbose=False)
    if not res["ok"]:
        print(f"    RED: {res['why']}")
        return False
    d_iip3 = res["iip3_dbm"] - ana_iip3
    d_gain = res["gain_ss"] - ana_gain
    d_slope = res["slope"] - 3.0
    ok = (abs(d_iip3) <= TOL_IIP3 and abs(d_slope) <= TOL_SLOPE
          and abs(d_gain) <= TOL_GAIN)
    print(f"      measured IIP3 = {res['iip3_dbm']:+.3f} dBm  "
          f"(D {d_iip3:+.3f}, tol {TOL_IIP3})   slope = {res['slope']:.4f} "
          f"(D {d_slope:+.4f})   gain D = {d_gain:+.4f} dB")
    print(f"      fit resid {res['im3_fit_resid_db']:.4f} dB, {res['kept']} "
          f"pts kept, per-point median {res['iip3_pt_median']:+.3f} "
          f"(spread {res['iip3_pt_spread']:.3f})   "
          f"{'GREEN' if ok else 'RED'}")
    return ok


def g4_convergence():
    print(f"G4  timestep convergence (network C, 2x finer tmax; require "
          f"|dIM3| < {TOL_CONV} dB)")
    fn = NETS["C"][0]
    c = I.convergence(lambda ve, f1, f2: fn(10.0, -200.0, ve, f1, f2),
                      F0, -24.0)
    if not c["ok"]:
        print(f"    RED: {c['why']}")
        return False
    ok = abs(c["d_im3_db"]) < TOL_CONV
    print(f"    -> dIM3 = {c['d_im3_db']:+.4f} dB, dIIP3 = "
          f"{c['d_iip3_db']:+.4f} dB   {'GREEN' if ok else 'RED'}")
    return ok


if __name__ == "__main__":
    I.private_tmp()
    ok = g1_floor()
    # Pin ranges sit well below each pair's compression; the harness's own
    # compression + SNR guards are what decide which points enter the fit.
    print("G2  network R (algebraic -- isolates the extraction arithmetic)")
    ok &= g_pair("R", 10.0, -200.0, [-30, -28, -26, -24, -22, -20])
    ok &= g_pair("R", 4.0, -50.0, [-28, -26, -24, -22, -20, -18])
    print("G3  network C (reactive -- certifies integrator + resampler)")
    ok &= g_pair("C", 10.0, -200.0, [-30, -28, -26, -24, -22, -20])
    ok &= g_pair("C", 4.0, -50.0, [-28, -26, -24, -22, -20, -18])
    ok &= g4_convergence()
    print("check_iip3:", "GREEN" if ok else "RED")
    sys.exit(0 if ok else 1)

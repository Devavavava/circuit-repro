"""Golden for the active-mixer harness (lna/mixer_harness.py, circuit_class mixer).

Program rule: no mixer number is quoted until this is GREEN. The reference is an
IDEAL MULTIPLIER built from a B-source product v(rf)*v(lo) -- no BSIM, no PDK, no
fitting -- whose conversion gain, LO isolation and IIP3 are exact / closed form.

REFERENCE ALGEBRA -- ideal multiplier IF = k * v(rf) * v(lo)
-----------------------------------------------------------
Drive the RF node with A_rf*cos(w_rf t) and the LO node with A_lo*cos(w_lo t).
The product's IF-band term (difference frequency) is, by cos*cos:

    k * A_rf*cos(w_rf t) * A_lo*cos(w_lo t)
        = k*(A_rf*A_lo/2)*[ cos((w_rf-w_lo)t) + cos((w_rf+w_lo)t) ]

so the IF amplitude at |f_rf - f_lo| is exactly

    V_if = k * A_rf * A_lo / 2

The harness refers conversion gain to the AVAILABLE RF source amplitude
V_rf_avail = vemf/2 (the amplitude a matched 50 ohm load sees). The RF drive is
50 ohm into a 50 ohm shunt at the RF node, so the actual node amplitude is also
A_rf = vemf/2 = V_rf_avail. Therefore

    conv_gain = 20*log10( V_if / V_rf_avail )
              = 20*log10( k * A_lo / 2 )                         [exact]

Sanity anchors from that identity:
    k=1, A_lo=2  -> conv_gain =  0.00 dB
    k=1, A_lo=1  -> conv_gain = -6.02 dB   (= 20*log10(1/2), the brief's number)

LO ISOLATION. The ideal multiplier has NO direct LO->RF or LO->IF path (the LO
enters only through the product), so both isolations are at the numerical floor
(very large positive dB). We assert they clear a high bar rather than an exact
value (a leakage path would show up as a finite number).

IIP3. Add a weak cube on the RF port before the mix: iF = k*v(lo)*(v(rf) -
a3*v(rf)^3). The RF cube's IM3 down-converts to IF +/- 3dF/2 with the SAME
memoryless-cubic algebra check_iip3 uses; input-referred IIP3 is
A_IP3^2 = (4/3)*(1/a3) at the RF node, referred through H=1/2 to the port:

    IIP3_dBm = 10*log10( A_IP3^2 / (H^2 * 400) * 1e3 ),  H = 1/2

(the LO factor k*A_lo/2 is common to fundamental and IM3, so it cancels out of
IIP3 exactly -- IIP3 is a property of the RF-port nonlinearity, independent of
conversion gain. We still assert it to close the loop on the reused iip3 path.)

CHECKS (tolerances stated BEFORE the run)
-----------------------------------------
  M1  conversion gain, two (k, A_lo) points: within 0.1 dB of 20log10(k*A_lo/2).
  M2  LO->RF and LO->IF isolation both > 80 dB (ideal multiplier: no leakage).
  M3  mixer IIP3 within 0.4 dB of the closed form; free-fit IM3 slope 3 +/- 0.15.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.dirname(HERE)
sys.path.insert(0, LNA)

import iip3 as I                       # noqa: E402
import mixer_harness as MX             # noqa: E402

Z0 = 50.0
F_RF = 2.400e9        # on-grid RF
F_LO = 2.000e9        # on-grid LO -> IF = 400 MHz (on grid)

TOL_CG = 0.10         # dB
ISO_BAR = 80.0        # dB
TOL_IIP3 = 0.40       # dB
TOL_SLOPE = 0.15


def _mult_body(k, a3=0.0):
    """Ideal multiplier deck as a to_spice-style body with portnum 1 (RF), 2
    (IF) and 3 (LO). The harness rewrites port-1 -> RF drive, port-2 -> IF load,
    port-3 -> LO drive. Rrf/Rlo shunts give the matched divider (H = 1/2 at RF,
    LO node driven hard). IF = k*v(lo)*(v(rf) - a3*v(rf)^3)."""
    nl = f"{k:.10g}*v(lo)*v(rf)"
    if a3:
        nl = f"{k:.10g}*v(lo)*(v(rf) - {a3:.10g}*v(rf)*v(rf)*v(rf))"
    return "\n".join([
        "* mixer golden: ideal multiplier IF = k*v(lo)*v(rf)",
        "Vp1 rf 0 dc 0 ac 1 portnum 1 z0 50",     # RF port -> becomes RF drive
        "Rrf rf 0 50",                            # matched shunt: H = 1/2 at rf
        "Vp3 lo 0 dc 0 ac 0 portnum 3 z0 50",     # LO port -> becomes LO drive
        f"Bif if 0 V = {nl}",
        "Vp2 if 0 dc 0 ac 0 portnum 2 z0 50",     # IF port -> becomes 50 ohm load
        "Rload if 0 50",
        ".option reltol=1e-5",
    ])


def m1_conv_gain():
    print("M1  conversion gain (ideal multiplier, exact 20log10(k*A_lo/2))")
    ok = True
    for k, a_lo in ((1.0, 2.0), (1.0, 1.0)):
        want = 20 * math.log10(k * a_lo / 2.0)
        m, err = MX.measure_conv_gain(_mult_body(k), "lo", a_lo, F_RF, F_LO,
                                      p_rf_dbm=-30.0)
        if m is None:
            print(f"    k={k} A_lo={a_lo}: RED sim failed ({err})")
            ok = False
            continue
        d = m["conv_gain_db"] - want
        good = abs(d) <= TOL_CG
        ok &= good
        print(f"    k={k} A_lo={a_lo}: measured {m['conv_gain_db']:+.3f} dB  "
              f"want {want:+.3f} dB  (D {d:+.4f}, tol {TOL_CG})  "
              f"[IF={m['f_if']/1e6:.0f} MHz]  {'ok' if good else 'FAIL'}")
    print(f"    -> {'GREEN' if ok else 'RED'}")
    return ok


def m2_isolation():
    print("M2  LO isolation (ideal multiplier: no LO->RF / LO->IF path)")
    m, err = MX.measure_conv_gain(_mult_body(1.0), "lo", 1.0, F_RF, F_LO,
                                  p_rf_dbm=-30.0)
    if m is None:
        print(f"    RED sim failed ({err})")
        return False
    good = m["lo_rf_iso_db"] > ISO_BAR and m["lo_if_iso_db"] > ISO_BAR
    print(f"    LO->RF isolation {m['lo_rf_iso_db']:.1f} dB, "
          f"LO->IF isolation {m['lo_if_iso_db']:.1f} dB  (> {ISO_BAR})  "
          f"{'ok' if good else 'FAIL'}")
    print(f"    -> {'GREEN' if good else 'RED'}")
    return good


def m3_iip3():
    print("M3  mixer IIP3 (RF-port cubic, IM3 down-converted to IF)")
    a3 = 200.0                            # strong cube -> low IIP3, easy to see
    h = 0.5
    a_ip3_sq = (4.0 / 3.0) * (1.0 / a3)
    want = 10 * math.log10(a_ip3_sq / (h * h * 400.0) * 1e3)
    print(f"    a3={a3:g}: analytic IIP3 = {want:+.3f} dBm")
    res = MX.measure_mixer_iip3(_mult_body(1.0, a3=a3), "lo", 1.0, F_RF, F_LO,
                                [-46, -44, -42, -40, -38, -36], verbose=False)
    if not res["ok"]:
        print(f"    RED: {res['why']}")
        return False
    d = res["iip3_dbm"] - want
    d_slope = res["slope"] - 3.0
    good = abs(d) <= TOL_IIP3 and abs(d_slope) <= TOL_SLOPE
    print(f"    measured IIP3 = {res['iip3_dbm']:+.3f} dBm  (D {d:+.3f}, tol {TOL_IIP3})   "
          f"IM3 slope = {res['slope']:.4f} (D {d_slope:+.4f})   "
          f"{res['kept']} pts   {'GREEN' if good else 'RED'}")
    return good


def main():
    I.private_tmp()
    ok = True
    ok &= m1_conv_gain()
    ok &= m2_isolation()
    ok &= m3_iip3()
    print("check_mixer:", "GREEN" if ok else "RED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

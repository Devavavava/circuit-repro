"""Golden for the balun / differential-output harness (lna/balun_harness.py,
circuit_class balun-lna).

Program rule: no balun number is quoted until this is GREEN. The reference is an
IDEAL CENTER-TAPPED behavioral balun -- two VCVS of gain -/+ 0.5 off the same
input node -- so imbalance is exactly 0 dB / 0 deg, the differential gain is
closed form, the common-mode gain is at the numerical floor, and CMRR is huge.
No BSIM, no PDK. The balun_harness reuses diff3's mixed-mode algebra (itself
golden-checked by check_diff.py); this golden certifies the CLASS FACADE:
Scs21, CMRR, and the as_metrics() name mapping balun_harness adds on top.

REFERENCE ALGEBRA
-----------------
Construction (identical shape to check_diff's golden balun, gain +/-0.5):
    Vp1 p1 0 ... portnum 1 z0 50 ;  Rt p1 0 50          (matched input)
    E2 e2 0 p1 0 -0.5 ; R2 e2 out2 50 ; port2 <- out2   (inverting leg)
    E3 e3 0 p1 0 +0.5 ; R3 e3 out3 50 ; port3 <- out3   (non-inverting leg)

Each leg is a VCVS of gain G=0.5 behind a 50 ohm series R into a 50 ohm port,
matched-driven, so its single-ended S-parameter is |S21| = |S31| = G/2 = 0.25:

    per-leg gain   = 20*log10(G/2)       = 20*log10(0.25) = -12.041 dB
    Sds21          = 20*log10|(S21-S31)/sqrt2|
                   = per-leg + 20*log10(sqrt2) = -12.041 + 3.0103 = -9.031 dB
    (S21 = -0.25, S31 = +0.25, so S21-S31 = -0.5, /sqrt2 = 0.3536 -> -9.031 dB)
    Scs21          = 20*log10|(S21+S31)/sqrt2| : S21+S31 = 0 EXACTLY
                   -> common-mode gain at the -600 dB floor (perfect balun)
    CMRR           = Sds21 - Scs21  -> huge (limited only by the 1e-30 floor)
    imbalance mag  = 20*log10|S21/S31| = 20*log10(1) = 0 dB   (equal magnitudes)
    imbalance phase= arg(-(S21/S31)) = arg(-(-0.25/0.25)) = arg(+1) = 0 deg
                     (the -() is diff3's inverting-leg convention)

CHECKS (tolerances stated BEFORE the run)
-----------------------------------------
  B1  per-leg gain = -12.041 dB, Sds21 = -9.031 dB (both +/- 1e-3 dB).
  B2  imbalance exactly 0 dB / 0 deg (+/- 1e-4 dB, +/- 1e-3 deg).
  B3  Scs21 at the floor (< -100 dB) and CMRR > 90 dB (perfect common-mode
      rejection of a center-tapped balun).
  B4  as_metrics() maps the numbers to the spec metric names (sds21_db,
      scs21_db, cmrr_db, imbalance_amp_db, imbalance_phase_deg) intact.
  B5  A DELIBERATELY IMBALANCED balun (legs -0.5 / +0.6) reads a NON-zero
      imbalance matching 20*log10(0.6/0.5) and a finite CMRR -- proving the
      metrics are not hard-wired to the ideal case.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.dirname(HERE)
sys.path.insert(0, LNA)

import balun_harness as B              # noqa: E402

F_LO, F_HI = 1.1e9, 2.5e9
F0 = 1.8e9                             # exactly on the 141-point lin grid


def _balun_body(g2=-0.5, g3=0.5):
    """Ideal center-tapped balun; g2 = inverting leg gain, g3 = non-inverting."""
    return "\n".join([
        "* balun golden: center-tapped, legs g2/g3 via 50R into 50R ports",
        "Vp1 p1 0 dc 0 ac 1 portnum 1 z0 50",
        "Rt p1 0 50",
        f"E2 e2 0 p1 0 {g2:+g}",
        "R2 e2 out2 50",
        f"E3 e3 0 p1 0 {g3:+g}",
        "R3 e3 out3 50",
        "Vp2 out2 0 dc 0 ac 0 portnum 2 z0 50",
        "Vp3 out3 0 dc 0 ac 0 portnum 3 z0 50",
        "Vsup VDD 0 dc 1.1"])           # balun_harness needs a supply for Idd


def main():
    ok = True

    def check(name, val, want, tol):
        nonlocal ok
        good = val is not None and abs(val - want) <= tol
        ok &= good
        print(f"  {name:<28} {val if val is not None else 'MISSING':>13} "
              f"(want {want:g} +/- {tol:g})  {'ok' if good else 'FAIL'}")
        return good

    print("[B1/B2/B3] ideal center-tapped balun (legs -0.5 / +0.5)")
    r = B.measure_balun(_balun_body(), None, [F0], F_LO, F_HI)
    if r is None:
        print("  SIM FAILED"); return 1
    b = r["bands"][0]
    leg = -12.041199827
    check("per-leg gain (dB)", b["s21p_db"], leg, 1e-3)
    check("Sds21 (dB)", b["sd21_db"], leg + 20 * math.log10(math.sqrt(2)), 1e-3)
    check("imbalance amp (dB)", b["imb_mag_db"], 0.0, 1e-4)
    check("imbalance phase (deg)", b["imb_phase_deg"], 0.0, 1e-3)
    # Scs21 floor + CMRR
    good_scs = b["scs21_db"] is not None and b["scs21_db"] < -100
    ok &= good_scs
    print(f"  {'Scs21 floor (dB)':<28} {b['scs21_db']:>13.2f} (< -100)  "
          f"{'ok' if good_scs else 'FAIL'}")
    good_cmrr = b["cmrr_db"] is not None and b["cmrr_db"] > 90
    ok &= good_cmrr
    print(f"  {'CMRR (dB)':<28} {b['cmrr_db']:>13.2f} (> 90)  "
          f"{'ok' if good_cmrr else 'FAIL'}")

    print("[B4] as_metrics() -> spec metric names")
    m = B.as_metrics(r)
    for k in ("sds21_db", "scs21_db", "cmrr_db", "imbalance_amp_db",
              "imbalance_phase_deg"):
        present = k in m and m[k] is not None
        ok &= present
        print(f"  {k:<28} {m.get(k)!s:>13}  {'ok' if present else 'FAIL'}")
    # amp/phase imbalance in as_metrics are magnitudes -> 0 here
    check("as_metrics imbalance_amp", m["imbalance_amp_db"], 0.0, 1e-4)

    print("[B5] deliberately imbalanced balun (legs -0.5 / +0.6)")
    r2 = B.measure_balun(_balun_body(g2=-0.5, g3=0.6), None, [F0], F_LO, F_HI)
    if r2 is None:
        print("  SIM FAILED"); return 1
    b2 = r2["bands"][0]
    want_imb = 20 * math.log10(0.5 / 0.6)   # |S21/S31| = 0.25/0.30
    check("imbalance amp (dB)", b2["imb_mag_db"], want_imb, 5e-3)
    # phase still 0 (both real, opposite sign -> -(neg/pos) = +)
    check("imbalance phase (deg)", b2["imb_phase_deg"], 0.0, 1e-2)
    # common mode is now non-zero (legs don't cancel): CMRR finite, not huge
    finite_cmrr = (b2["cmrr_db"] is not None and b2["cmrr_db"] < 90
                   and b2["scs21_db"] is not None and b2["scs21_db"] > -100)
    ok &= finite_cmrr
    print(f"  {'Scs21 (dB)':<28} {b2['scs21_db']:>13.3f}   "
          f"{'CMRR':<6}{b2['cmrr_db']:>8.3f} dB (finite)  "
          f"{'ok' if finite_cmrr else 'FAIL'}")

    print("check_balun:", "GREEN" if ok else "RED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

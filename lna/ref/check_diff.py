"""Golden checks for the 3-port differential harness (lna/diff3.py, WP-DIFF).

Five closed-form references, all device-model-free (E-sources + R/C only), all
run through diff3's OWN code paths (run_diff / measure_diff_nf), not through
hand decks:

  A. IDEAL BALUN -- legs driven by E-sources gain -2/+2 through 50 ohm into
     50-ohm ports, input terminated in 50 ohm. Closed form: each leg exactly
     0 dB, imbalance exactly 0 dB / 0 deg, differential gain exactly
     +3.0103 dB (= leg + 20*log10(sqrt(2))), S11 at the -600 dB floor.
  B. RC-SKEWED BALUN -- the non-inverting leg reads the input through a
     50-ohm/C low-pass, so at frequency f (x = 2*pi*f*R*C):
         imb_mag_db  = +10*log10(1 + x^2)
         imb_phase   = +atan(x)                 [degrees]
     Both compared against the analytic value at the measured grid point.
  C. POLARITY TRIP-WIRE -- an IN-PHASE splitter (both legs +2, no inversion
     anywhere) must read a phase imbalance near 180 deg, NOT near zero: a
     circuit that merely splits without balancing cannot fake a pass. (A
     perfect balun with ports 2/3 swapped is still a perfect balun -- the
     ratio r is invariant under that swap, which is why the trip-wire is the
     splitter, not the swap.)
  D. DIFFERENTIAL NF -- ideal differential amp (gain +/-10) with source
     Rs = 50 (noisy, series) and one equal 50-ohm input resistor:
     NF = 10*log10(1 + Rn/Rs) = 3.0103 dB, read via `noise v(n2,n3)`.
     The 50-ohm leg loads sit directly across ideal E outputs, so they add
     nothing -- same construction as extract.nf_selftest, differential.
  E. BAND-WIDE WORST CASE -- the same RC-skewed balun, but checking the
     max-over-sweep reduction the claims actually use: the skew is monotonic
     in frequency, so both worst cases must equal the closed form at f_hi.

    python lna/ref/check_diff.py        # exit 0 iff everything is GREEN
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import diff3 as D                     # noqa: E402

F_LO, F_HI = 1.1e9, 2.5e9
F0 = 1.8e9                            # exactly on the 141-point lin grid


def _balun_body(inphase=False, skew_c=None):
    """The golden balun. port2 <- inverting leg (gain -2 via 50R), port3 <-
    non-inverting (+2 via 50R). `inphase` makes BOTH legs +2 (a splitter, not
    a balun -- golden C's trip-wire); `skew_c` inserts the 50R/C low-pass in
    front of the non-inverting leg (golden B)."""
    p2, p3 = "out2", "out3"
    lines = ["* diff3 golden balun",
             "Vp1 p1 0 dc 0 ac 1 portnum 1 z0 50",
             "Rt p1 0 50",
             f"E2 e2 0 p1 0 {'+2' if inphase else '-2'}",
             "R2 e2 out2 50"]
    src3 = "p1"
    if skew_c is not None:
        lines += [f"Rsk p1 nph 50", f"Csk nph 0 {skew_c:g}"]
        src3 = "nph"
    lines += [f"E3 e3 0 {src3} 0 2",
              "R3 e3 out3 50",
              f"Vp2 {p2} 0 dc 0 ac 0 portnum 2 z0 50",
              f"Vp3 {p3} 0 dc 0 ac 0 portnum 3 z0 50",
              "Vsup VDD 0 dc 1.1"]     # diff3 needs a supply name for Idd
    return "\n".join(lines)


def _nf_body():
    return "\n".join([
        "* diff3 golden differential-NF reference",
        "Vp1 p1 0 dc 0 ac 1 portnum 1 z0 50",
        "Rn p1 b 50",
        "Eamp1 o2 0 b 0 -10",
        "Eamp2 o3 0 b 0 10",
        "Vp2 o2 0 dc 0 ac 0 portnum 2 z0 50",
        "Vp3 o3 0 dc 0 ac 0 portnum 3 z0 50",
        "Vsup VDD 0 dc 1.1"])


def main():
    ok = True

    def check(name, val, want, tol):
        nonlocal ok
        good = val is not None and abs(val - want) <= tol
        ok &= good
        print(f"  {name:<26} {val if val is not None else 'MISSING':>12} "
              f"(want {want:g} +/- {tol:g})  {'ok' if good else 'FAIL'}")
        return good

    print("[A] ideal balun")
    r = D.run_diff(_balun_body(), None, [F0], F_LO, F_HI)
    if r is None:
        print("  SIM FAILED"); return 1
    b = r["bands"][0]
    check("leg2 gain (dB)", b["s21p_db"], 0.0, 1e-3)
    check("leg3 gain (dB)", b["s21n_db"], 0.0, 1e-3)
    check("imb mag (dB)", b["imb_mag_db"], 0.0, 1e-4)
    check("imb phase (deg)", b["imb_phase_deg"], 0.0, 1e-3)
    check("diff - leg (dB)", b["sd21_db"] - b["s21p_db"], 20 * math.log10(math.sqrt(2)), 1e-3)
    good_s11 = r["s11_max_db"] is not None and r["s11_max_db"] < -100
    ok &= good_s11
    print(f"  {'S11_max floor':<26} {r['s11_max_db']:>12} (< -100)  "
          f"{'ok' if good_s11 else 'FAIL'}")

    print("[B] RC-skewed balun (closed form)")
    C = 0.31e-12
    x = 2 * math.pi * F0 * 50 * C
    r = D.run_diff(_balun_body(skew_c=C), None, [F0], F_LO, F_HI)
    if r is None:
        print("  SIM FAILED"); return 1
    b = r["bands"][0]
    check("imb mag (dB)", b["imb_mag_db"], 10 * math.log10(1 + x * x), 0.02)
    check("imb phase (deg)", b["imb_phase_deg"], math.degrees(math.atan(x)), 0.2)

    print("[C] polarity trip-wire (in-phase splitter)")
    r = D.run_diff(_balun_body(inphase=True), None, [F0], F_LO, F_HI)
    if r is None:
        print("  SIM FAILED"); return 1
    ph = abs(r["bands"][0]["imb_phase_deg"])
    good = ph > 170
    ok &= good
    print(f"  {'|imb phase| (deg)':<26} {ph:>12.4f} (> 170)  "
          f"{'ok' if good else 'FAIL'}")

    print("[D] differential NF (series-Rs)")
    nf = D.measure_diff_nf(_nf_body(), None, [F0], F_LO, F_HI)
    check("NF (dB)", None if nf is None else nf.get(F0), 3.0103, 0.05)

    # E. BAND-WIDE AGGREGATION. Every claim this harness makes about imbalance
    # is a WORST-CASE over 1.1-2.5 GHz, not a value at one f0, so the max-over-
    # sweep reduction (`meas sp ... max`) needs its own closed form. The RC
    # skew of golden B is monotonic in frequency, so both worst cases must land
    # exactly on the f_hi end of the sweep -- and that also proves the sweep
    # really spans the band rather than collapsing onto one point.
    print("[E] band-wide worst case (monotonic skew -> must land at f_hi)")
    xh = 2 * math.pi * F_HI * 50 * C
    r = D.run_diff(_balun_body(skew_c=C), None, [F0], F_LO, F_HI)
    if r is None:
        print("  SIM FAILED"); return 1
    check("worst |imb mag| (dB)", r["imb_mag_wc_db"],
          10 * math.log10(1 + xh * xh), 0.02)
    check("worst |imb phase| (deg)", r["imb_phase_wc_deg"],
          math.degrees(math.atan(xh)), 0.2)

    print("check_diff:", "GREEN" if ok else "RED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

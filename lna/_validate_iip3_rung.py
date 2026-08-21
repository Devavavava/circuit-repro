"""Validation of the IIP3 tier-3 rung wiring -- S44 replay fence.

Runs the two-tone transient harness (transient-v1) on the stored flagship
point (dhruva-simul) at the D6 out-bank S3 (min-gain) condition, 1.2 V rail,
l5 band, to reproduce FINDINGS §44.2's number within tolerance.

FINDINGS §44.2 reference:
  D6 min-gain S3, pVDD = 1.2 V:
    l5: IIP3 = −34.19 dBm, gain = 20.93 dB, OIP3 = −13.25 dBm

Tolerance: ±0.5 dB (the harness's own replay spread is 0.000 dB;
0.5 dB leaves room for any minor environmental delta while still
being tight enough to catch a mis-wired measurement).

The min-gain S3 deck uses a re-driven Pin window [-68,-64,-60,-56,-52] dBm
(§44.3: the default [-80…-40] dBm window fails the slope fence at min-gain
because the IM3 products fall below the harness's numerical floor at low drive).

Usage: python lna/_validate_iip3_rung.py
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import iip3 as I3

REPRO = os.path.join(HERE, "repro", "dhruva-best")
DECK = os.path.join(REPRO, "dhruva-simul_min_v1p2.sp")

# FINDINGS §44.2 reference (D6 S3 min-gain, 1.2 V, l5 band)
REF_IIP3_DBM = -34.19
REF_GAIN_DB = 20.93
REF_OIP3_DBM = -13.25
TOL_DB = 0.5   # replay tolerance

# §44.3: re-driven Pin window for min-gain (IM3 above the floor)
PINS_MIN = [-68.0, -64.0, -60.0, -56.0, -52.0]

# §44.2 audited S21 at l5, min-gain, 1.2 V (from _lin_baseline.audited_s21)
# Re-pointed so the gain cross-check does not trip on the simul sizing.
S21_REF_L5_MIN = 20.93


def run():
    if not os.path.exists(DECK):
        print(f"DECK MISSING: {DECK}")
        print("Run: python lna/_lin_baseline.py --emit-deck --vdd 1.2")
        return False

    I3.private_tmp()
    # Re-point the harness at the simul-min deck (the D-9 sidecar pattern):
    orig_deck_for = I3.deck_for
    orig_s21 = dict(I3.S21_REF_DB)
    orig_des = I3.DESIGNATED
    I3.DESIGNATED = "simul"
    I3.deck_for = lambda tag, sizing=I3.DESIGNATED, _d=DECK: _d
    # Re-point the S21 cross-check at the min-gain audited value for l5.
    I3.S21_REF_DB = dict(I3.S21_REF_DB, l5=S21_REF_L5_MIN)
    try:
        res = I3.measure_band("l5", PINS_MIN, sizing="simul", verbose=True)
    finally:
        I3.deck_for = orig_deck_for
        I3.S21_REF_DB = orig_s21
        I3.DESIGNATED = orig_des

    print()
    if not res.get("ok"):
        print(f"RESULT: NO RESULT -- {res.get('why')}")
        return False

    iip3 = res["iip3_dbm"]
    gain = res.get("gain_ss", float("nan"))
    oip3 = iip3 + gain if gain is not None else float("nan")
    d_iip3 = iip3 - REF_IIP3_DBM
    d_gain = gain - REF_GAIN_DB if gain is not None else float("nan")
    d_oip3 = oip3 - REF_OIP3_DBM if oip3 is not None else float("nan")

    ok = abs(d_iip3) <= TOL_DB
    print("=== S44 replay fence (D6 min-gain S3, 1.2 V, l5 band) ===")
    print(f"  IIP3:  measured = {iip3:+.3f} dBm   "
          f"ref = {REF_IIP3_DBM:+.2f} dBm   delta = {d_iip3:+.3f} dB  "
          f"  {'PASS' if ok else 'FAIL'} (tol ±{TOL_DB} dB)")
    print(f"  gain:  measured = {gain:+.3f} dB    ref = {REF_GAIN_DB:+.2f} dB   "
          f"delta = {d_gain:+.3f} dB")
    print(f"  OIP3:  measured = {oip3:+.3f} dBm   ref = {REF_OIP3_DBM:+.2f} dBm   "
          f"delta = {d_oip3:+.3f} dB")
    print(f"  harness: transient-v1, tmax={I3.TMAX:g} s, DF={I3.DF/1e6:g} MHz, "
          f"T_WIN={I3.T_WIN*1e6:.0f} us")
    print(f"  pins: {PINS_MIN} dBm  kept={res.get('kept')} pts "
          f"slope={res.get('slope', float('nan')):.3f}")
    print(f"  => {'GREEN' if ok else 'RED'}")
    return ok


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)

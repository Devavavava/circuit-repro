"""Balun / differential-output harness (circuit_class: balun-lna).

Formalizes the differential-output measurements the D7 lineage already
implements in lna/diff3.py, and REUSES that module verbatim rather than
re-deriving the mixed-mode algebra (which is sound and golden-checked by
lna/ref/check_diff.py). This file is the class-level facade: it presents the
balun metrics in the constraint-metric names spec.py recognizes and adds the
common-mode gain + CMRR that diff3 did not surface.

DUT convention (diff3's, unchanged):
    portnum 1 : single-ended RF input   (z0 50)
    portnum 2 : INVERTING output leg    (z0 50)
    portnum 3 : NON-INVERTING output leg (z0 50)

Metrics (per f0 and band-wide worst-case):
    sds21_db          differential-mode forward gain 20log10|(S21-S31)/sqrt2|
                      (diff3's `sd21_db`; the standard mixed-mode Sds21)
    scs21_db          COMMON-mode forward gain 20log10|(S21+S31)/sqrt2|  -- NEW
                      here (diff3 measured only the differential leg); computed
                      by the same 3-port sp run, see measure_balun().
    cmrr_db           common-mode rejection = Sds21 - Scs21  (dB)          -- NEW
    imbalance_amp_db  amplitude imbalance = 20log10|S21/S31|  (diff3 imb_mag_db)
    imbalance_phase_deg phase imbalance = arg(-(S21/S31)) in deg (diff3 imb_phase_deg)

The single-ended-in / differential-out mixed-mode reduction (Sds21, Scs21) is
exactly the reduction diff3._mixed_mode_lets documents; Scs21 is added with the
same sqrt(2) normalization so Sds21 - Scs21 is a proper mixed-mode CMRR.

Golden: lna/ref/check_balun.py -- an ideal center-tapped behavioral balun (two
VCVS +/-0.5) gives exactly 0 dB / 0 deg imbalance and a known Sds21; the golden
asserts those plus the Scs21 floor and the CMRR. No number quoted until GREEN.

RUNTIME: one 3-port sp run (diff3.run_diff, ~1 s) + an optional differential-NF
run; measure_balun does the sp run and one extra sp for Scs21's band-wide max
(the common-mode `let` is added to the same deck here). ~1-2 s per call.
"""
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import diff3 as D                      # noqa: E402  (the mixed-mode engine, reused)
import extract as E                    # noqa: E402

DEG = D.DEG


def _balun_control_block(f0s, f_lo, f_hi, supply, npts=141):
    """diff3's control block PLUS the common-mode gain Scs21 and its band-wide
    max / per-f0 find. Everything diff3.diff_control_block emits is kept
    verbatim so the differential numbers are byte-identical to diff3's; the
    common-mode lets are ADDED, not substituted."""
    base = D.diff_control_block(f0s, f_lo, f_hi, supply, npts=npts)
    # splice the common-mode measurements in before .endc
    cm_lets = [
        "let scsdb = db(mag((S_2_1 + S_3_1)/sqrt(2))+1e-30)",
        f"meas sp m_scs_min min scsdb from={f_lo:g} to={f_hi:g}",
        f"meas sp m_scs_max max scsdb from={f_lo:g} to={f_hi:g}",
    ]
    for i, f0 in enumerate(f0s):
        cm_lets.append(f"meas sp m_b{i}_scs find scsdb at={f0:g}")
    lines = base.splitlines()
    out = []
    for ln in lines:
        if ln.strip() == ".endc":
            out.extend(cm_lets)
        out.append(ln)
    return "\n".join(out)


def _build_balun_deck(body, params, f0s, f_lo, f_hi, supply=None, npts=141):
    supply = supply or E._supply_name(body)
    lines = [body.rstrip()]
    if params:
        lines.append(".param " + " ".join(f"{k}={v}" for k, v in params.items()))
    lines.append(_balun_control_block(f0s, f_lo, f_hi, supply, npts=npts))
    return "\n".join(lines) + "\n"


def measure_balun(body, params, f0s, f_lo, f_hi, npts=141, with_nf=False):
    """The balun measurement: differential + common-mode + CMRR + imbalance.

    Returns diff3.run_diff's dict, extended with per-band `scs21_db`, `cmrr_db`
    and top-level `scs21_min_db`/`scs21_max_db`. One ngspice run (the diff3
    metrics and the common-mode metrics share the single sp sweep). Optionally a
    second run for differential NF (diff3.measure_diff_nf, verbatim)."""
    deck = _build_balun_deck(body, params, f0s, f_lo, f_hi, npts=npts)
    out = E.run_deck(deck, "balun_", "b.cir", timeout=120)
    if out is None or "singular matrix" in out.lower():
        return None

    def g(name):
        m = re.search(rf"{name}\s*=\s*{D._NUM}", out, re.IGNORECASE)
        try:
            return float(m.group(1)) if m else None
        except ValueError:
            return None

    idd = g("idd")
    res = {"idd_ma": abs(idd) * 1e3 if idd is not None else None,
           "s11_max_db": g("m_s11_max"), "sd21_min_db": g("m_sd_min"),
           "imb_mag_wc_db": g("m_imbmag_wc"), "imb_phase_wc_deg": g("m_imbph_wc"),
           "mm_k_min": g("m_mmk_min"), "mm_delta_max": g("m_mmdlt_max"),
           "scs21_min_db": g("m_scs_min"), "scs21_max_db": g("m_scs_max"),
           "bands": []}
    for i, f0 in enumerate(f0s):
        sd = g(f"m_b{i}_sd")
        scs = g(f"m_b{i}_scs")
        b = {"f0": f0, "s11_db": g(f"m_b{i}_s11"), "s21p_db": g(f"m_b{i}_s21p"),
             "s21n_db": g(f"m_b{i}_s21n"), "sd21_db": sd, "scs21_db": scs,
             "imb_mag_db": g(f"m_b{i}_im"), "imb_phase_deg": g(f"m_b{i}_ip"),
             # CMRR = differential gain over common-mode gain (dB subtraction)
             "cmrr_db": (sd - scs) if (sd is not None and scs is not None) else None}
        if b["sd21_db"] is None:
            return None
        res["bands"].append(b)
    if res["s11_max_db"] is None:
        return None
    if with_nf:
        nf = D.measure_diff_nf(body, params, f0s, f_lo, f_hi, npts=npts)
        for b in res["bands"]:
            b["nf_db"] = None if nf is None else nf.get(b["f0"])
    return res


def as_metrics(res, band_index=0):
    """Flatten a measure_balun result into the spec.py constraint-metric names,
    at one band (default the first f0). This is the bridge between a balun
    measurement and spec.feasible()/report(): the names here are exactly the ones
    spec.py's _ALLOWED-agnostic constraints block gates on.

        sds21_db, scs21_db, cmrr_db, imbalance_amp_db, imbalance_phase_deg,
        s11_max_db, idd_ma  (+ band-wide imbalance worst-cases)
    """
    if res is None:
        return {}
    b = res["bands"][band_index]
    return {
        "sds21_db": b["sd21_db"],
        "scs21_db": b["scs21_db"],
        "cmrr_db": b["cmrr_db"],
        "imbalance_amp_db": abs(b["imb_mag_db"]) if b["imb_mag_db"] is not None else None,
        "imbalance_phase_deg": abs(b["imb_phase_deg"]) if b["imb_phase_deg"] is not None else None,
        # band-wide worst cases, for a spec that wants to gate over the band
        "imbalance_amp_wc_db": res["imb_mag_wc_db"],
        "imbalance_phase_wc_deg": res["imb_phase_wc_deg"],
        "s11_max_db": res["s11_max_db"],
        "idd_ma": res["idd_ma"],
    }


if __name__ == "__main__":
    print(__doc__)

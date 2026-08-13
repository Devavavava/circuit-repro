"""3-port differential-output harness (WP-DIFF, Gate D7 ladder step).

The paper target's output is differential (single-ended RF in, balanced out,
imbalance <= 0.22 dB / <= 0.9 deg) -- tier-3, unmeasurable by the 2-port
harness in extract.py. This module measures it, for bodies that declare THREE
S-parameter ports:

    portnum 1 : single-ended RF input (z0 50)
    portnum 2 : the INVERTING output leg (z0 50)
    portnum 3 : the NON-INVERTING output leg (z0 50)

Definitions (mixed-mode, single-ended-in differential-out):
    per-leg gain      s21p = db|S21|, s21n = db|S31|
    differential gain sd21 = db|(S21 - S31)/sqrt(2)|   (100-ohm differential
                      reference implied by the two 50-ohm legs; for an ideal
                      balun sd21 = leg + 3.0103 dB -- the check_diff golden
                      asserts this identity to 1e-3 dB)
    imbalance ratio   r = -(S21/S31); ideal balun -> r = 1 at 0 deg, so
                      imb_mag_db = db|r| and imb_phase_deg = arg(r) read the
                      deviation directly with no 360-deg wrap headache. The
                      port-2-is-inverting convention is what makes arg(r)
                      small instead of ~180; a body wired backwards shows up
                      as imb_phase_deg near +/-180 rather than as a fake pass.
    NF                series-Rs source (the extract.py finding-#7 fix,
                      verbatim), noise read DIFFERENTIALLY: noise v(n2,n3).

Stability here is ADVISORY and is the (input, differential-output) 2-port
reduction of the 3-port S-matrix:
    Sdd22 = (S22 - S23 - S32 + S33)/2,  Ssd21 = (S21-S31)/sqrt(2),
    Sds12 = (S12-S13)/sqrt(2),          K over {S11, Sds12; Ssd21, Sdd22}.
The common-mode response is not in that matrix (it IS physically loaded by the
two 50-ohm legs during the sweep); a full 3-port stability theory is not
attempted. Same spirit as extract's K: advisory, never gated.

Every ngspice entry point is extract.run_deck (self-deleting scratch).
Golden: lna/ref/check_diff.py -- ideal balun (exact 0 dB / 0 deg / +3.0103 dB
identity), a closed-form RC-skewed balun (analytic imbalance), and the
3.0103 dB differential-NF reference. No measurement from this file is trusted
until that is green.
"""
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import extract as E                    # noqa: E402

_NUM = E._NUM
DEG = 57.29577951308232


# ------------------------------------------------------------------ deck build
def _port_nodes(body):
    """{1: node, 2: node, 3: node} from the body's `portnum` lines. The node is
    the source's positive terminal -- same detection extract.build_noise_deck
    uses, extended to port 3."""
    nodes = {}
    for ln in body.splitlines():
        toks = ln.split()
        m = re.search(r"portnum\s+(\d)", ln.lower())
        if m and len(toks) >= 2:
            nodes[int(m.group(1))] = toks[1]
    return nodes


def _mixed_mode_lets():
    """Mixed-mode (se-in, diff-out) 2-port reduction + Rollett K, advisory."""
    return [
        "let sdd22 = (S_2_2 - S_2_3 - S_3_2 + S_3_3)/2",
        "let ssd21 = (S_2_1 - S_3_1)/sqrt(2)",
        "let sds12 = (S_1_2 - S_1_3)/sqrt(2)",
        "let mm11 = mag(S_1_1)", "let mm22 = mag(sdd22)",
        "let mm1221 = mag(sds12*ssd21)",
        "let mdlt = S_1_1*sdd22 - sds12*ssd21",
        "let mdltm = mag(mdlt)",
        "let mkk = (1 - mm11*mm11 - mm22*mm22 + mdltm*mdltm)/(2*mm1221 + 1e-30)",
    ]


def diff_control_block(f0s, f_lo, f_hi, supply, npts=141):
    """op + Idd + one 3-port sp sweep + per-f0 measurements for EVERY f0 in
    `f0s` (all four dhruva bands read from a single sweep)."""
    lines = [".control", "op", f"let idd = -i({supply})", "print idd",
             f"sp lin {npts:d} {f_lo:g} {f_hi:g} 1",
             "let s11db = db(mag(S_1_1)+1e-30)",
             "let s21pdb = db(mag(S_2_1)+1e-30)",
             "let s21ndb = db(mag(S_3_1)+1e-30)",
             "let sddb = db(mag((S_2_1 - S_3_1)/sqrt(2))+1e-30)",
             "let rimb = -(S_2_1/(S_3_1 + 1e-30))",
             "let imbmag = db(mag(rimb)+1e-30)",
             f"let imbph = ph(rimb)*{DEG:.14g}",
             "let aimbmag = abs(imbmag)", "let aimbph = abs(imbph)",
             f"meas sp m_s11_max max s11db from={f_lo:g} to={f_hi:g}",
             f"meas sp m_sd_min min sddb from={f_lo:g} to={f_hi:g}",
             f"meas sp m_imbmag_wc max aimbmag from={f_lo:g} to={f_hi:g}",
             f"meas sp m_imbph_wc max aimbph from={f_lo:g} to={f_hi:g}"]
    for i, f0 in enumerate(f0s):
        lines += [f"meas sp m_b{i}_s11 find s11db at={f0:g}",
                  f"meas sp m_b{i}_s21p find s21pdb at={f0:g}",
                  f"meas sp m_b{i}_s21n find s21ndb at={f0:g}",
                  f"meas sp m_b{i}_sd find sddb at={f0:g}",
                  f"meas sp m_b{i}_im find imbmag at={f0:g}",
                  f"meas sp m_b{i}_ip find imbph at={f0:g}"]
    lines += _mixed_mode_lets()
    lines += [f"meas sp m_mmk_min min mkk from={f_lo:g} to={f_hi:g}",
              f"meas sp m_mmdlt_max max mdltm from={f_lo:g} to={f_hi:g}",
              ".endc", ".end"]
    return "\n".join(lines)


def build_diff_deck(body, params, f0s, f_lo, f_hi, supply=None, npts=141):
    supply = supply or E._supply_name(body)
    lines = [body.rstrip()]
    if params:
        lines.append(".param " + " ".join(f"{k}={v}" for k, v in params.items()))
    lines.append(diff_control_block(f0s, f_lo, f_hi, supply, npts=npts))
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ sp metrics
def run_diff(body, params, f0s, f_lo, f_hi, npts=141):
    """One ngspice run -> dict (or None):
       {idd_ma, s11_max_db, sd21_min_db, imb_mag_wc_db, imb_phase_wc_deg,
        mm_k_min, mm_delta_max,
        bands: [{f0, s11_db, s21p_db, s21n_db, sd21_db, imb_mag_db,
                 imb_phase_deg} ...]}"""
    deck = build_diff_deck(body, params, f0s, f_lo, f_hi, npts=npts)
    out = E.run_deck(deck, "diff3_", "d.cir", timeout=120)
    if out is None or "singular matrix" in out.lower():
        return None

    def g(name):
        m = re.search(rf"{name}\s*=\s*{_NUM}", out, re.IGNORECASE)
        try:
            return float(m.group(1)) if m else None
        except ValueError:
            return None

    idd = g("idd")
    res = {"idd_ma": abs(idd) * 1e3 if idd is not None else None,
           "s11_max_db": g("m_s11_max"), "sd21_min_db": g("m_sd_min"),
           "imb_mag_wc_db": g("m_imbmag_wc"), "imb_phase_wc_deg": g("m_imbph_wc"),
           "mm_k_min": g("m_mmk_min"), "mm_delta_max": g("m_mmdlt_max"),
           "bands": []}
    for i, f0 in enumerate(f0s):
        b = {"f0": f0, "s11_db": g(f"m_b{i}_s11"), "s21p_db": g(f"m_b{i}_s21p"),
             "s21n_db": g(f"m_b{i}_s21n"), "sd21_db": g(f"m_b{i}_sd"),
             "imb_mag_db": g(f"m_b{i}_im"), "imb_phase_deg": g(f"m_b{i}_ip")}
        if b["sd21_db"] is None:
            return None
        res["bands"].append(b)
    return res if res["s11_max_db"] is not None else None


# ------------------------------------------------------------------ diff NF
def build_diff_noise_deck(body, params, f_lo, f_hi, rs=50.0, rl=50.0, npts=141):
    """Series-Rs rewrite of a 3-port body (finding-#7 fix, verbatim mechanics):
    port-1 source -> Vnz + Rns(50); port-2/3 sources -> 50-ohm loads; noise is
    read DIFFERENTIALLY across the two leg nodes: `noise v(n2,n3) Vnz`.
    Returns (deck, n2, n3) or (None, None, None)."""
    pn = _port_nodes(body)
    if set(pn) < {1, 2, 3}:
        return None, None, None
    lines = []
    for ln in body.splitlines():
        low = ln.lower()
        toks = ln.split()
        if "portnum" in low and len(toks) >= 2:
            node = toks[1]
            if re.search(r"portnum\s+1\b", low):
                lines.append("Vnz nz 0 dc 0 ac 1")
                lines.append(f"Rns nz {node} {rs:g}")
                continue
            if re.search(r"portnum\s+2\b", low):
                lines.append(f"Rnl2 {node} 0 {rl:g}")
                continue
            if re.search(r"portnum\s+3\b", low):
                lines.append(f"Rnl3 {node} 0 {rl:g}")
                continue
        lines.append(ln)
    deck = ["\n".join(lines)]
    if params:
        deck.append(".param " + " ".join(f"{k}={v}" for k, v in params.items()))
    deck += [".control", "op",
             f"noise v({pn[2]},{pn[3]}) Vnz lin {npts:d} {f_lo:g} {f_hi:g}",
             "setplot noise1",
             f"let nfv = 10*log10((inoise_spectrum*inoise_spectrum)/{E.K4TRS:.6e})",
             "print nfv", ".endc", ".end"]
    return "\n".join(deck) + "\n", pn[2], pn[3]


def measure_diff_nf(body, params, f0s, f_lo, f_hi, rs=50.0, npts=141):
    """{f0: nf_db} at every requested f0 from ONE noise run (nearest grid
    point of the lin sweep; <= (f_hi-f_lo)/(npts-1)/2 off-grid, ~5 MHz at the
    default -- same tolerance class as extract.measure_nf's 51-point grid)."""
    deck, _n2, _n3 = build_diff_noise_deck(body, params, f_lo, f_hi, rs=rs,
                                           npts=npts)
    if deck is None:
        return None
    out = E.run_deck(deck, "diffnf_", "n.cir", timeout=120)
    if out is None or "singular matrix" in out.lower():
        return None
    vals = {}
    # `print nfv` dumps an indexed table; collect index -> value.
    tab = {}
    for m in re.finditer(rf"^\s*(\d+)\s+{_NUM}\s+{_NUM}\s*$", out, re.MULTILINE):
        tab[int(m.group(1))] = float(m.group(3))
    if not tab:
        return None
    for f0 in f0s:
        idx = round((f0 - f_lo) / (f_hi - f_lo) * (npts - 1)) if f_hi > f_lo else 0
        idx = max(0, min(npts - 1, idx))
        vals[f0] = tab.get(idx)
    return vals


def measure_diff3(body, params, f0s, f_lo, f_hi, with_nf=True, npts=141):
    """The one-shot: sp metrics + (optionally) differential NF. Two ngspice
    runs total. Returns the run_diff dict with per-band `nf_db` filled in."""
    res = run_diff(body, params, f0s, f_lo, f_hi, npts=npts)
    if res is None:
        return None
    if with_nf:
        nf = measure_diff_nf(body, params, f0s, f_lo, f_hi, npts=npts)
        for b in res["bands"]:
            b["nf_db"] = None if nf is None else nf.get(b["f0"])
    return res


if __name__ == "__main__":
    print(__doc__)

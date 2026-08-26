"""Active-mixer harness (circuit_class: mixer).

Down-conversion measurements on a sized mixer deck, reusing iip3.py's coherent
transient + tone-extraction machinery. The deck is expected to carry:

    portnum 1 : RF input   (z0 50)          -- becomes a Thevenin RF drive
    portnum 2 : IF output  (z0 50)          -- becomes a 50 ohm load
  and a NAMED LO port, either a `portnum 3` line OR a body node the caller
  identifies, driven by a large-signal LO SIN source (the LO is not a small-
  signal port; it is a switching drive).

Everything sits on the coherent 1 MHz grid (iip3.GRID_HZ): f_rf, f_lo and the IF
= |f_rf - f_lo| are all snapped so each lands dead-centre in a DFT bin
(rectangular window, zero leakage), exactly as the IIP3 harness does.

Measures:
    conv_gain_db   conversion gain = 20*log10( V_if(IF) / V_rf_avail_referred )
                   reported as delivered voltage-conversion gain into the 50 ohm
                   IF load referred to the available RF input (the same "voltage
                   gain adopted as gain into 50 ohm" convention the LNA harness
                   uses; documented in the roadmap).
    lo_rf_iso_db   LO-to-RF isolation = -20*log10( V_lo@RFport / V_lo_drive )
    lo_if_iso_db   LO-to-IF isolation = -20*log10( V_lo@IFport / V_lo_drive )
    iip3_dbm       input-referred IIP3 from TWO RF tones: IM3 products fall at
                   IF +/- dF and mix down to the IF band; slope-intercept on the
                   down-converted IM3, reusing iip3.extract().

OUT OF SCOPE v0 (documented in kaggle/HARNESS-ROADMAP.md):
  * MIXER NOISE FIGURE. ngspice has no PSS/pnoise (periodic steady-state noise),
    and a mixer's NF is a cyclostationary / SSB-vs-DSB question that transient
    "noise" cannot answer credibly (the LO is a large periodic drive; small-
    signal `.noise` linearizes around a DC op that is the WRONG operating
    trajectory). We therefore do NOT report mixer NF -- reporting a transient-
    noise number here would be a lie, so it is named as future work (PSS via a
    different engine) rather than faked.

Golden: lna/ref/check_mixer.py -- an IDEAL multiplier (B-source product) with an
exactly computable conversion gain (cos*cos gives IF amplitude A_rf*A_lo/2, so
voltage conversion gain = A_lo/2; derived there). No number quoted until GREEN.

RUNTIME: conversion-gain / isolation is ONE transient (~single IIP3 point,
~0.5-1 s on this box for a behavioral deck, a few seconds for a device deck).
IIP3 is a Pin sweep (N transients), same budget as iip3.iip3_sweep.
"""
import math
import os
import re
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import extract as E                    # noqa: E402
import iip3 as I                       # noqa: E402

Z0 = I.Z0


def lo_drive(node, vlo, flo):
    """Large-signal LO: a SIN EMF directly on `node` (the LO is a hard drive,
    not a 50 ohm-terminated small-signal port). Snapped f is the caller's job."""
    return f"Vlo {node} 0 dc 0 sin(0 {vlo:.10g} {flo:.10g})"


def rf_drive(node, vemf, frf):
    """Single RF tone behind 50 ohm into `node` (available power Pav =
    vemf^2/(8*Z0)), matching the sp port-1 termination. The series resistor is
    `Rmxsrc` (a name no DUT body uses) so it never collides with a DUT element."""
    return (f"Vrf mx_rf_a 0 dc 0 sin(0 {vemf:.10g} {frf:.10g})\n"
            f"Rmxsrc mx_rf_a {node} {Z0:g}")


def rf_two_tone(node, vemf, f1, f2):
    """Two equal RF tones behind 50 ohm -- the IIP3 drive (iip3.two_tone_drive
    idiom, renamed sources/nodes so they never collide with the LO or DUT)."""
    return (f"Vr1 mx_rf_a 0 dc 0 sin(0 {vemf:.10g} {f1:.10g})\n"
            f"Vr2 mx_rf_b mx_rf_a dc 0 sin(0 {vemf:.10g} {f2:.10g})\n"
            f"Rmxsrc mx_rf_b {node} {Z0:g}")


# --------------------------------------------------------------- deck surgery
def _find_ports(body):
    """(rf_node, if_node, lo_node) from portnum 1/2/3 lines; lo_node None if the
    body has only 2 ports (caller must then supply lo_node explicitly)."""
    pn = {}
    for ln in body.splitlines():
        m = re.search(r"portnum\s+(\d)", ln.lower())
        toks = ln.split()
        if m and len(toks) >= 2:
            pn[int(m.group(1))] = toks[1]
    return pn.get(1), pn.get(2), pn.get(3)


def build_mixer_body(base_body, rf_src, lo_node, vlo, flo, keep_if_load=True):
    """Replace port-1 with `rf_src` (a drive string), port-2 with a 50 ohm IF
    load, and add the LO drive on `lo_node`. If the body has a `portnum 3` LO
    port, that source line is replaced by the LO drive; otherwise the LO drive
    is appended on the caller-named `lo_node`.

    Returns (body, rf_node, if_node, lo_node)."""
    rf_node, if_node, lo_port = _find_ports(base_body)
    if rf_node is None or if_node is None:
        raise ValueError("build_mixer_body: need portnum 1 (RF) and 2 (IF)")
    lo_node = lo_node or lo_port
    if lo_node is None:
        raise ValueError("build_mixer_body: no LO node (no portnum 3 and none given)")
    lines = []
    for ln in base_body.splitlines():
        low = ln.lower()
        if re.search(r"portnum\s+1\b", low):
            lines.append(rf_src)
            continue
        if re.search(r"portnum\s+2\b", low) and keep_if_load:
            lines.append(f"Rif {if_node} 0 {Z0:g}")
            continue
        if re.search(r"portnum\s+3\b", low):
            # port-3 becomes the LO drive
            lines.append(lo_drive(lo_node, vlo, flo))
            continue
        lines.append(ln)
    if lo_port is None:
        # no port-3 in the body: append the LO drive on the named node
        lines.append(lo_drive(lo_node, vlo, flo))
    return "\n".join(lines), rf_node, if_node, lo_node


# --------------------------------------------------------------- run + extract
def _run_tran(body, probe_nodes, timeout=1800, tmax=I.TMAX, t_win=I.T_WIN):
    """Transient, writing v() of each node in `probe_nodes`; returns
    (t, {node: v}, err). One wrdata per node keeps columns unambiguous."""
    t_stop = I.T_SETTLE + t_win + 5e-9
    t_start = I.T_SETTLE - 20e-9
    with E.scratch("mix_") as d:
        wr = []
        for i, nd in enumerate(probe_nodes):
            f = os.path.join(d, f"n{i}.dat").replace("\\", "/")
            wr.append((nd, f))
        wlines = "\n".join(f"wrdata {f} v({nd})" for nd, f in wr)
        deck = (body.rstrip() + "\n.control\nop\n"
                f"tran {2 * tmax:g} {t_stop:g} {t_start:g} {tmax:g}\n"
                f"{wlines}\n.endc\n.end\n")
        p = os.path.join(d, "mix.cir")
        with open(p, "w") as fh:
            fh.write(deck)
        try:
            r = subprocess.run([E.NGSPICE, "-b", p], capture_output=True,
                               text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None, None, "timeout"
        out = (r.stdout or "") + (r.stderr or "")
        res = {}
        t = None
        for nd, f in wr:
            if not os.path.exists(f):
                return None, None, out[-2000:]
            arr = np.loadtxt(f)
            if arr.ndim != 2 or arr.shape[0] < 1000:
                return None, None, "short/empty wrdata"
            t = arr[:, 0]
            res[nd] = arr[:, 1]
    return t, res, None


def measure_conv_gain(base_body, lo_node, vlo, f_rf, f_lo, p_rf_dbm=-30.0,
                      **kw):
    """Conversion gain + LO feedthrough from ONE transient.

    All frequencies snapped to the coherent grid; IF = |f_rf - f_lo|. Reads the
    IF-band amplitude at the IF node, the LO amplitude at the RF and IF nodes
    (feedthrough), and the RF amplitude at the RF node (for the referred gain).
    """
    frf, flo = I.snap(f_rf), I.snap(f_lo)
    fif = abs(frf - flo)
    if fif < I.GRID_HZ:
        raise ValueError("IF below one grid step; choose f_rf, f_lo further apart")
    vemf = I.pav_dbm_to_vemf(p_rf_dbm)
    body, rf_node, if_node, lo_node = build_mixer_body(
        base_body, rf_drive("RFN", vemf, frf), lo_node, vlo, flo)
    # the drive string names its own series-R target; substitute the actual node
    body = body.replace("RFN", rf_node)
    t, vs, err = _run_tran(body, [rf_node, if_node], **kw)
    if t is None:
        return None, err
    b_if = I.coherent_bins(t, vs[if_node], [fif, flo], T=kw.get("t_win", I.T_WIN))
    b_rf = I.coherent_bins(t, vs[rf_node], [frf, flo], T=kw.get("t_win", I.T_WIN))
    v_if = b_if[fif]                      # IF-band signal amplitude at IF node
    v_lo_if = b_if[flo]                   # LO leakage at IF node
    v_lo_rf = b_rf[flo]                   # LO leakage at RF node
    v_rf_in = b_rf[frf]                   # actual RF amplitude at the RF node
    # available RF voltage referred: vemf/2 is the amplitude a matched 50 ohm
    # load would see; conversion gain is the standard "gain into 50 ohm"
    # convention -> referred to the available-source amplitude vemf/2.
    v_rf_avail = vemf / 2.0
    conv_gain_db = 20 * math.log10(max(v_if, 1e-300) / v_rf_avail)
    # LO isolation referred to the LO drive amplitude vlo
    lo_rf_iso = -20 * math.log10(max(v_lo_rf, 1e-300) / vlo)
    lo_if_iso = -20 * math.log10(max(v_lo_if, 1e-300) / vlo)
    return dict(f_rf=frf, f_lo=flo, f_if=fif, p_rf_dbm=p_rf_dbm,
                v_if=v_if, v_rf_in=v_rf_in, v_rf_avail=v_rf_avail,
                conv_gain_db=conv_gain_db,
                lo_rf_iso_db=lo_rf_iso, lo_if_iso_db=lo_if_iso,
                v_lo_rf=v_lo_rf, v_lo_if=v_lo_if, vlo=vlo), None


# --------------------------------------------------------------- mixer IIP3
def measure_mixer_iip3(base_body, lo_node, vlo, f_rf, f_lo, pins_dbm,
                       df=I.DF, verbose=True, **kw):
    """Input-referred IIP3 via two RF tones, IM3 extracted AT THE IF.

    Two RF tones at f_rf +/- dF/2 down-convert to IF +/- dF/2; their IM3
    products (2f1-f2, 2f2-f1) down-convert to IF +/- 3dF/2. We build an
    iip3.iip3_sweep body_fn that measures at the IF centre with the tone plan
    shifted to IF, reusing iip3's slope-intercept fit and floor logic verbatim.
    """
    frf, flo = I.snap(f_rf), I.snap(f_lo)
    fif = abs(frf - flo)

    def body_fn(vemf, f1, f2):
        # f1, f2 are IF-band tones from iip3.tone_plan(fif); map them back to RF
        # by adding flo (high-side) so the down-converted products land on the
        # SAME IF grid iip3 expects. The IF-referred tone plan is what iip3
        # measures at, so measurement stays at IF while the drive is at RF.
        rf1, rf2 = f1 + flo, f2 + flo
        body, rf_node, if_node, ln = build_mixer_body(
            base_body, rf_two_tone("RFN", vemf, rf1, rf2), lo_node, vlo, flo)
        body = body.replace("RFN", rf_node)
        return body, if_node

    res = I.iip3_sweep(body_fn, fif, pins_dbm, df=df, verbose=verbose, **kw)
    res["f_rf"], res["f_lo"], res["f_if"] = frf, flo, fif
    return res


if __name__ == "__main__":
    print(__doc__)

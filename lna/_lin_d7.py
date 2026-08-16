"""D-7 MEASURE -- the output-reference-impedance lever, quantified.
(user ruling 2026-08-16; pre-registered in plans2/19-D7-MEASURE.md.)

The question (16-WP-LIN.md §7 D-7 / §2.2): |Z_ac| -- the AC load MNM6 drives --
is pR4V=434 ohm SHUNTED by the 50 ohm output port through the coupling caps, so
the design gives away its load resistor. Raising the OUTPUT port R un-shunts it,
raising |Z_ac| toward the resistor limit; the wall is Iq*|Z_ac| and §44.4
measured OIP3 tracking that product dB-for-dB (rho=1.0). This sidecar measures
OIP3/IIP3 (+ the S11/S21/NF/K/Idd/D6-span consequences) at output reference
impedance R in {50 (control), 100, 200, 400} ohm.

★ D-7 changes the OUTPUT leg ONLY. The input port stays 50 ohm (the antenna
reference does not move -- available input power and Rsrc are unchanged). So:
  * Rload (port 2) -> R            (the physical load that sets |Z_ac|)
  * vout_to_dbm -> power into R    (OIP3 = power delivered to the new reference)
  * pav_dbm_to_vemf / Rsrc -> 50   (UNCHANGED -- input side)
IIP3 = OIP3 - G with G the small-signal gain into the new load.

SIDECAR (16-WP-LIN.md D-9): reuses rung 0's machinery (`_lin_baseline`) verbatim
-- its base_body, min-gain S3 body/params builder (structural role resolution,
§42.2/§6.7), deck emission, and the iip3.py re-point pattern (deck_for +
S21_REF_DB, never disable, never edit the shared file). The output-port override
is a MODULE-ATTRIBUTE monkeypatch of iip3.vout_to_dbm + iip3.lna_two_tone_body;
the shared harness file is never edited. The S-param consequence run rewrites the
port-2 z0 in the deck body (a string edit on a copy, never by literal node name).

Spec-READING: the spec YAMLs are UNTOUCHED; the recorded reference stays 50 ohm.

Modes:
  --iip3    OIP3/IIP3 vs R, per state, per band, replay-fenced (the D5 margin)
  --conseq  S11 (both references) / S21 / NF / K_min / Idd / D6 span vs R
  --hb      the HB cross-check at the owed impedance (default 400 ohm)
  --predict just print the predicted-curve table (no SPICE)

Usage:
  python lna/_lin_d7.py --iip3 --state min,max --bands l5 --R 50,100,200,400
  python lna/_lin_d7.py --conseq --R 50,100,200,400
  python lna/_lin_d7.py --hb --R 400 --state min
"""
import argparse
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import extract as E          # noqa: E402
import size as S             # noqa: E402
import iip3 as I3            # noqa: E402
import _lin_baseline as B    # noqa: E402

REPRO = B.REPRO
OUT = B.OUT
RECIPE = "wplin-v1"
SOURCE_ARM = "wplin-d7"
BANDS = B.BANDS
F0 = B.F0

# §2.2 output coupling: CC6 (pC6V) in series with Cp2 (10 pF), shunting pR4V.
CP2 = 10e-12
PR4V = 434.067

PINS_MIN = [-68.0, -64.0, -60.0, -56.0, -52.0]
PINS_MAX = [-80.0, -72.0, -64.0, -56.0, -48.0, -40.0]

# §44.2 baseline (50 ohm) min/max OIP3+IIP3 at 1.2 V, for the predicted curve.
BASE_MIN_OIP3 = {"l5": -13.25, "l2": -13.19, "l1": -12.97, "s": -13.05}
BASE_MIN_IIP3 = {"l5": -34.19, "l2": -34.28, "l1": -34.67, "s": -34.46}
BASE_MAX_OIP3 = {"l5": -1.35, "l2": -1.36, "l1": -1.46, "s": -1.82}


# ----------------------------------------------------------- the physics
def z_ac_mag(R, f0, c6=1e-11):
    """|Z_ac| at MNM6's drain with output port impedance R (§2.2 construction,
    generalised from _lin_baseline.z_ac_mag: the 50 is now the variable R)."""
    cser = c6 * CP2 / (c6 + CP2)
    w = 2 * math.pi * f0
    zc = 1.0 / (1j * w * cser)
    zport = zc + R
    return abs(1.0 / (1.0 / PR4V + 1.0 / zport))


def predict(bands, Rs):
    print("\n=== PREDICTED OIP3/IIP3 vs output port R (min-gain S3, 1.2 V) ===")
    print("  (OIP3 tracks |Z_ac| dB-for-dB per §44.4 rho=1.0; off the §44.2 baseline)")
    rows = {}
    for band in bands:
        f0 = F0[band]
        z50 = z_ac_mag(50, f0)
        print(f"\n  {band} (f0={f0/1e6:.1f} MHz, |Z_ac|@50={z50:.1f} ohm, "
              f"tgt IIP3>={I3.IIP3_TARGET_DBM[band]:+.1f}):")
        print(f"    {'R':>5}{'|Z_ac|':>8}{'dOIP3':>7}{'predOIP3':>9}"
              f"{'predIIP3':>9}{'margin':>8}")
        rows[band] = {}
        for R in Rs:
            z = z_ac_mag(R, f0)
            d = 20 * math.log10(z / z50)
            po = BASE_MIN_OIP3[band] + d
            pi = BASE_MIN_IIP3[band] + d
            m = pi - I3.IIP3_TARGET_DBM[band]
            rows[band][R] = dict(z_ac=z, d_oip3=d, oip3=po, iip3=pi, margin=m)
            print(f"    {R:>5}{z:>8.1f}{d:>+7.2f}{po:>+9.2f}{pi:>+9.2f}{m:>+8.2f}")
    return rows


# ------------------------------------------------ output-port override
def _output_port_override(R):
    """Return (restore_fn) after monkeypatching iip3 so the OUTPUT port is R and
    the INPUT port stays 50 ohm. vout_to_dbm reads power into R; lna_two_tone_body
    writes Rload=R while leaving the Thevenin Rsrc=50 drive untouched."""
    orig_vout = I3.vout_to_dbm
    orig_body = I3.lna_two_tone_body

    def vout_to_dbm_R(a_pk, _R=float(R)):
        # peak voltage across the R load -> power in dBm (Pout = Vpk^2/(2R))
        return 10 * math.log10(max(a_pk, 1e-300) ** 2 / (2 * _R) * 1e3)

    def body_R(deck_path, vemf, f1, f2, _R=float(R)):
        # reuse the shared surgery, then swap ONLY the port-2 Rload value.
        # The shared body writes "Rload <n_out> 0 50"; retarget it to R.
        text, n_out = orig_body(deck_path, vemf, f1, f2)
        text = re.sub(rf"(?m)^Rload\s+{re.escape(n_out)}\s+0\s+[\d.eE+-]+\s*$",
                      f"Rload {n_out} 0 {_R:g}", text)
        return text, n_out

    I3.vout_to_dbm = vout_to_dbm_R
    I3.lna_two_tone_body = body_R

    def restore():
        I3.vout_to_dbm = orig_vout
        I3.lna_two_tone_body = orig_body
    return restore


# ------------------------------------------------ audited S21 into R
def audited_s21_R(state, vdd, R, bands):
    """This config's small-signal gain into the R load -- the reference the
    re-pointed §37.4 cross-check uses. Measured on a fresh small-signal two-tone
    run at the lowest drive with the OUTPUT port set to R (so the cross-check
    stays valid as the load changes; §4.0 item 3, never disabled)."""
    deck = os.path.join(REPRO, B.deck_name(state, vdd))
    if not os.path.exists(deck):
        B.emit_deck(state, vdd)
    restore = _output_port_override(R)
    ref = {}
    try:
        for tag in bands:
            f0 = F0[tag]
            f0s, f1, f2, fl, fh = I3.tone_plan(f0)
            body, node = I3.lna_two_tone_body(deck, I3.pav_dbm_to_vemf(-80.0), f1, f2)
            m, err = I3.measure_point(body, node, f0s, f1, f2, fl, fh)
            if m is None:
                raise SystemExit(f"_lin_d7: S21 ref sim failed {tag}/{state}/{R}: {err}")
            ref[tag] = m["pfund"] - (-80.0)      # gain = Pfund - Pin at SS drive
    finally:
        restore()
    return ref


# ------------------------------------------------ the two-tone vs R
def measure_iip3(state, vdd, R, bands, replay=3):
    deck = os.path.join(REPRO, B.deck_name(state, vdd))
    if not os.path.exists(deck):
        B.emit_deck(state, vdd)
    pins = PINS_MIN if state == "min" else PINS_MAX
    ref = audited_s21_R(state, vdd, R, bands)

    restore = _output_port_override(R)
    I3.S21_REF_DB = dict(ref)
    I3.DESIGNATED = "simul"
    orig_deck_for = I3.deck_for
    I3.deck_for = lambda tag, sizing=I3.DESIGNATED, _d=deck: _d
    I3.private_tmp()
    try:
        reps = []
        for r in range(replay):
            per = {}
            for tag in bands:
                per[tag] = I3.measure_band(tag, pins, sizing="simul", verbose=(r == 0))
            reps.append(per)
    finally:
        I3.deck_for = orig_deck_for
        restore()

    def gq(res):
        return dict(iip3=res.get("iip3_dbm"),
                    oip3=(res.get("iip3_dbm", 0) + res.get("gain_ss", 0)) if res.get("ok") else None,
                    gain=res.get("gain_ss"), slope=res.get("slope"))
    spreads = {}
    for tag in bands:
        vals = [gq(rp[tag]) for rp in reps]
        spreads[tag] = {k: (max(v[k] for v in vals) - min(v[k] for v in vals))
                        if all(v[k] is not None for v in vals) else None
                        for k in vals[0]}
    return reps[0], spreads, ref


def cmd_iip3(states, bands, Rs, replay=3):
    pred = predict(bands, Rs)
    out = {"recipe": RECIPE, "source_arm": SOURCE_ARM,
           "diagnosis": "output-swing-current-limit",
           "point": "dhruva-simul (baseline, no candidate)",
           "nominal_vdd": 1.2, "predicted": pred, "results": {}}
    print("\n########## D-7: OIP3/IIP3 vs OUTPUT reference impedance ##########")
    for state in states:
        for R in Rs:
            print(f"\n===== state={state}, R={R} ohm, 1.2 V =====")
            first, spreads, ref = measure_iip3(state, "1.2", R, bands, replay)
            cfg = {}
            for tag in bands:
                res = first[tag]
                oip3 = (res.get("iip3_dbm") + res.get("gain_ss")) if res.get("ok") else None
                tgt = I3.IIP3_TARGET_DBM[tag]
                iip3 = res.get("iip3_dbm")
                cfg[tag] = dict(
                    iip3_dbm=iip3, oip3_dbm=oip3, gain_ss=res.get("gain_ss"),
                    target_dbm=tgt,
                    margin_db=(iip3 - tgt) if iip3 is not None else None,
                    passed=bool(res.get("ok") and iip3 is not None and iip3 >= tgt),
                    slope=res.get("slope"), slope_ok=res.get("slope_ok"),
                    d_s21_db=res.get("d_s21_db"), s21_ok=res.get("s21_ok"),
                    s21_ref=ref[tag], worst_snr_db=res.get("worst_snr_db"),
                    im3_fit_resid_db=res.get("im3_fit_resid_db"),
                    iip3_pt_spread=res.get("iip3_pt_spread"),
                    kept=res.get("kept"), ok=res.get("ok"),
                    z_ac=z_ac_mag(R, F0[tag]),
                    replay_spread=spreads[tag])
            out["results"][f"{state}::R{R}"] = dict(state=state, R=R, bands=cfg)
            for tag in bands:
                c = cfg[tag]
                if not c["ok"]:
                    print(f"    {tag}: NO RESULT ({first[tag].get('why')})")
                    continue
                p = pred[tag][R]
                print(f"    {tag}: OIP3={c['oip3_dbm']:+.3f} (pred {p['oip3']:+.2f}, "
                      f"Δ{c['oip3_dbm']-p['oip3']:+.2f})  IIP3={c['iip3_dbm']:+.3f}  "
                      f"G={c['gain_ss']:.2f}  tgt={c['target_dbm']:+.1f}  "
                      f"margin={c['margin_db']:+.2f}  slope={c['slope']:.3f}"
                      f"{'' if c['slope_ok'] else '[!]'}  "
                      f"dS21={c['d_s21_db']:+.3f}({'ok' if c['s21_ok'] else 'MISS'})  "
                      f"replay={c['replay_spread']['iip3']:.4f}  "
                      f"{'PASS' if c['passed'] else 'FAIL'}")
    _curve_verdict(out, states, bands, Rs)
    path = os.path.join(OUT, "_lin_d7_iip3.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=float)
    print(f"\nwrote {path}")
    return out


def _curve_verdict(out, states, bands, Rs):
    if "min" not in states:
        return
    print("\n===== D-7 CURVE VERDICT (min-gain, ruled condition) vs Q1/Q2 =====")
    worst_dev = 0.0
    for tag in bands:
        r50 = out["results"].get(f"min::R{Rs[0]}", {}).get("bands", {}).get(tag)
        if not (r50 and r50["ok"]):
            continue
        print(f"\n  {tag}: OIP3(50)={r50['oip3_dbm']:+.2f}  tgt IIP3 {r50['target_dbm']:+.1f}")
        base_oip3 = r50["oip3_dbm"]
        for R in Rs:
            c = out["results"].get(f"min::R{R}", {}).get("bands", {}).get(tag)
            if not (c and c["ok"]):
                continue
            gain_db = c["oip3_dbm"] - base_oip3
            pred_gain = 20 * math.log10(z_ac_mag(R, F0[tag]) / z_ac_mag(Rs[0], F0[tag]))
            dev = gain_db - pred_gain
            worst_dev = max(worst_dev, abs(dev))
            verdict = "PASS" if c["passed"] else f"FAIL by {-c['margin_db']:.1f}"
            print(f"    R={R:>4}: OIP3={c['oip3_dbm']:+.2f} (Δvs50 {gain_db:+.2f}, "
                  f"pred {pred_gain:+.2f}, curve-dev {dev:+.2f})  "
                  f"IIP3 margin {c['margin_db']:+.2f}  D5 {verdict}")
    out["curve_worst_dev_db"] = worst_dev
    out["Q1_falsifier_3dB_tripped"] = worst_dev >= 3.0
    print(f"\n  worst curve deviation from the dB-for-dB prediction: {worst_dev:.2f} dB "
          f"(falsifier 3 dB {'TRIPPED' if worst_dev >= 3.0 else 'not tripped'})")


# ------------------------------------------------ consequences vs R
def _rewrite_port2_z0(body, R):
    """Rewrite the port-2 (portnum 2) z0 to R for the S-param run. String edit on
    a copy; the port-2 element is found by its 'portnum 2' token, not by node
    name (§42.2). Port 1 (the antenna) keeps z0 50."""
    def repl(m):
        return re.sub(r"z0\s+[\d.eE+-]+", f"z0 {R:g}", m.group(0))
    return re.sub(r"(?im)^V\w+\s+\S+\s+\S+\s+dc\s+0\s+ac\s+0\s+portnum\s+2\s+z0\s+[\d.eE+-]+\s*$",
                  repl, body)


def _sparams_at_R(body, params, spec, R):
    """S11/S21/K/Idd with port 2 renormalized to R. Returns the metrics dict
    (s11_max_db is band-wide; k_min from the stability meas)."""
    b = _rewrite_port2_z0(body, R) if R != 50 else body
    m = S.eval_metrics(b, params, spec, nf_gated=True)
    return m


def cmd_conseq(states, bands, Rs):
    """The concession columns: S11 (renormalized to R AND at fixed 50 antenna),
    S21, NF, K_min, Idd per R; and the D6 span (S0..S3) per R."""
    out = {"recipe": RECIPE, "source_arm": SOURCE_ARM, "consequences": {}, "span": {}}
    # spec = the wide-band spec; use l5's (worst NF band) for the gated NF read,
    # but S11/K are band-wide over 1.1-2.5 GHz already.
    print("\n########## D-7 consequences: S11/S21/NF/K/Idd vs R ##########")
    for state in ("max",):        # D4-SIM gates are judged at max gain (§6.3)
        body, sizable, fixed = B.base_body()
        params = B.simul_params("1.2")
        if state == "min":
            body, params = B.min_gain_body_params(body, params)
        for tag in bands:
            spec = S._spec_for_sizing(BANDS[tag])
            print(f"\n  -- band {tag} ({state} gain, 1.2 V) --")
            print(f"    {'R':>5}{'S11@R':>9}{'S11@50':>9}{'S21':>8}{'NF':>7}"
                  f"{'K_min':>9}{'Idd':>8}")
            for R in Rs:
                m_R = _sparams_at_R(body, params, spec, R)      # S11 renorm to R
                m_50 = _sparams_at_R(body, params, spec, 50)    # antenna 50 ref
                row = dict(
                    s11_max_R=m_R.get("s11_max_db"), s11_max_50=m_50.get("s11_max_db"),
                    s21_db=m_R.get("s21_db"), nf_db=m_R.get("nf_db"),
                    k_min=m_R.get("k_min"), idd_ma=m_R.get("idd_ma"))
                out["consequences"].setdefault(tag, {})[R] = row
                km = row["k_min"]
                print(f"    {R:>5}{_f(row['s11_max_R']):>9}{_f(row['s11_max_50']):>9}"
                      f"{_f(row['s21_db']):>8}{_f(row['nf_db']):>7}"
                      f"{_f(km):>9}{_f(row['idd_ma']):>8}")
    # D6 span per R (the §42.5 S0..S3 states)
    _span_vs_R(out, Rs)
    path = os.path.join(OUT, "_lin_d7_conseq.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=float)
    print(f"\nwrote {path}")
    return out


def _f(x, nd=2):
    return f"{x:.{nd}f}" if isinstance(x, (int, float)) else "--"


def _span_vs_R(out, Rs):
    """The D6 span (S0 max-gain state minus S3 min-gain state gain) at each R,
    per band -- how the output-side gain-control span moves as the port changes."""
    rep = json.load(open(B.PGAIN_S3, encoding="utf-8"))
    print("\n  -- D6 span (S0 gain - S3 gain) vs R, per band --")
    print(f"    {'band':>5}{'R':>6}{'S0(max)':>9}{'S3(min)':>9}{'span':>8}")
    for tag in BANDS:
        spec = S._spec_for_sizing(BANDS[tag])
        for R in Rs:
            # S0 = max-gain state (base body); S3 = min-gain (out-bank switch bank).
            b0, s, f = B.base_body()
            p0 = B.simul_params("1.2")
            b3, p3 = B.min_gain_body_params(b0, dict(p0))
            b0r = _rewrite_port2_z0(b0, R) if R != 50 else b0
            b3r = _rewrite_port2_z0(b3, R) if R != 50 else b3
            m0 = S.eval_metrics(b0r, p0, spec, nf_gated=False)
            m3 = S.eval_metrics(b3r, p3, spec, nf_gated=False)
            g0 = m0.get("s21_db") if m0 else None
            g3 = m3.get("s21_db") if m3 else None
            span = (g0 - g3) if (g0 is not None and g3 is not None) else None
            out["span"].setdefault(tag, {})[R] = dict(s0=g0, s3=g3, span=span)
            print(f"    {tag:>5}{R:>6}{_f(g0):>9}{_f(g3):>9}{_f(span):>8}")


# ------------------------------------------------ HB cross-check
def cmd_hb(state, R, bands):
    """HB cross-check at the owed impedance. Reuses _lin_hb's port45 machinery,
    re-pointed to the R load. The HB deck's port-2 z0 is rewritten to R (string
    edit on a copy), then port45 converts it; the transient OIP3 at R is the
    reference for the cross-method delta."""
    sys.path.insert(0, os.path.join(HERE, "hb"))
    import _lin_hb as HBSIDE  # noqa: E402
    import hb_iip3 as H       # noqa: E402
    import port45             # noqa: E402
    import tempfile

    deck0 = HBSIDE._deck_for(state, "1.2")
    # emit an R-load copy of the deck (rewrite port-2 z0 -> R)
    text = open(deck0, encoding="utf-8").read()
    text_R = _rewrite_port2_z0(text, R)
    fd, deckR = tempfile.mkstemp(suffix=".sp", prefix=f"lin_d7_hb_R{R}_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text_R)

    pins = HBSIDE.PINS_MIN if state == "min" else HBSIDE.PINS_MAX
    deck_of = lambda band, _d=deckR: _d
    orig_convert, orig_nodes = port45.convert, port45.nodes_of
    if HBSIDE._needs_switch_wrap(deckR):
        port45.convert = HBSIDE._convert_with_switches
        port45.nodes_of = lambda dp=deckR, mp=None: HBSIDE._convert_with_switches(dp, mp)[3]
    out = {"recipe": RECIPE, "source_arm": SOURCE_ARM, "state": state, "R": R, "hb": {}}
    try:
        root = tempfile.mkdtemp(prefix=f"lin_d7_hb_{state}_R{R}_")
        for band in bands:
            band_full = BANDS[band]
            one = H.cmd_iip3(root, [band_full], deck_of,
                             df=HBSIDE._df_for(band_full, state), pins=pins, verbose=True)
            r = one[band_full]
            out["hb"][band] = dict(iip3_dbm=r["iip3_dbm"], oip3_dbm=r["oip3_dbm"],
                                   gain_ss=r["gain_ss"], slope=r["slope"],
                                   kept=r["kept"], target_dbm=r["target_dbm"])
    finally:
        port45.convert, port45.nodes_of = orig_convert, orig_nodes
        os.unlink(deckR)
    # cross-method vs the transient result at the same R
    tr = None
    trp = os.path.join(OUT, "_lin_d7_iip3.json")
    if os.path.exists(trp):
        d = json.load(open(trp, encoding="utf-8"))
        tr = d["results"].get(f"{state}::R{R}", {}).get("bands", {})
    print(f"\n  -- HB cross-check at R={R} ({state}) vs transient --")
    print(f"    {'band':>5}{'HB OIP3':>9}{'tr OIP3':>9}{'|Δ|':>7}")
    worst = 0.0
    for band in bands:
        hb_o = out["hb"][band]["oip3_dbm"]
        tr_o = (tr or {}).get(band, {}).get("oip3_dbm")
        d = abs(hb_o - tr_o) if tr_o is not None else None
        if d is not None:
            worst = max(worst, d)
        out["hb"][band]["tr_oip3"] = tr_o
        out["hb"][band]["d_oip3"] = d
        print(f"    {band:>5}{hb_o:>+9.3f}"
              f"{(tr_o if tr_o is not None else float('nan')):>+9.3f}"
              f"{(d if d is not None else float('nan')):>7.3f}")
    out["worst_cross_method_db"] = worst
    print(f"\n  worst cross-method |Δ(OIP3)| = {worst:.3f} dB (precedent 0.08 dB)")
    path = os.path.join(OUT, f"_lin_d7_hb_R{R}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=float)
    print(f"wrote {path}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iip3", action="store_true")
    ap.add_argument("--conseq", action="store_true")
    ap.add_argument("--hb", action="store_true")
    ap.add_argument("--predict", action="store_true")
    ap.add_argument("--state", default="min,max")
    ap.add_argument("--bands", default="l5")
    ap.add_argument("--R", default="50,100,200,400")
    ap.add_argument("--replay", type=int, default=3)
    a = ap.parse_args()
    states = [x.strip() for x in a.state.split(",") if x.strip()]
    bands = list(BANDS) if a.bands == "all" else [x.strip() for x in a.bands.split(",")]
    Rs = [int(x) for x in a.R.split(",")]
    if a.predict:
        predict(bands, Rs)
    if a.iip3:
        cmd_iip3(states, bands, Rs, a.replay)
    if a.conseq:
        cmd_conseq(states, bands, Rs)
    if a.hb:
        cmd_hb(states[0], Rs[0] if len(Rs) == 1 else Rs[-1], bands)


if __name__ == "__main__":
    main()

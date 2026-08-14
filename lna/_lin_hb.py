"""WP-LIN rung 0 -- the HARMONIC-BALANCE half of the baseline.

The transient half (FINDINGS §44, sidecar `lna/_lin_baseline.py`) measured the
designated `dhruva-simul` point's first-ever IIP3/OIP3 on ngspice two-tone
transient, at max gain and the D6 out-bank S3 min-gain state, both rails --
and, per §7 D-8, reported every D5 number as reached-by-transient and *owed an
HB cross-check* because VACASK HB was blocked on this box (Windows path baked
into `check_hb.py`, `VACASK_HOME` unset). VACASK is now built and its golden is
GREEN; this sidecar pays the debt.

It measures the SAME four emitted decks the transient half used
(`repro/dhruva-best/dhruva-simul{,_v1p2,_min_v1p1,_min_v1p2}.sp`) in VACASK
harmonic balance via the READ-ONLY `lna/hb/hb_iip3.py` harness, per WP §4.0
item 4 (4 bands x 8 drives per configuration). It then reports, per band, the
cross-method |Δ(IIP3)| / |Δ(OIP3)| against §44's transient numbers, against the
program's 0.08 dB precedent (§37.6 / §40.3).

This is a SIDECAR (16-WP-LIN.md D-9): the read-only harness is imported and
re-pointed by MODULE-ATTRIBUTE assignment, never edited.

Two overrides the HB harness needs to measure `dhruva-simul` instead of its
hard-wired `dhruva-l5`:
  (a) The deck. `hb_iip3.cmd_iip3` takes a `deck_of(band)` callable; we pass one
      that returns the single simul deck for the chosen (state, rail) at every
      band (the fixed-sizing claim, as the transient side did).
  (b) The port45 converter. `port45.convert` (read-only) handles the max deck as
      shipped, but raises `unhandled card` on the D6 min-gain deck's switch-gate
      DC sources (`VSWGOB{1,2,3} nswc 0 dc {pVSWGOB}`). We wrap `convert` so
      those extra DC sources become VACASK `vsource dc=` cards -- the switch-gate
      bias is a real, load-bearing circuit element (it drives the MNM6-shunt
      switch gates through 10k), so it MUST be present in the HB netlist, not
      dropped. The wrap touches only cards port45 does not already emit; every
      device port45 does handle is left to port45 verbatim, so the max-deck path
      is byte-identical to the golden's.

§42.2 / §6.7 node-name warning: no element here is inserted by literal node
name. The switch bank is already baked into the emitted min decks by the
transient side's `_pgain_mech.build("out-bank", body)` (structural role
resolution, cross-checked -- FINDINGS §44.1); this sidecar reads those decks
verbatim and only re-expresses their existing V-source cards for VACASK.

Modes:
  --iip3   HB IIP3/OIP3, 4 configs (max/min x 1.1/1.2 V), 4 bands, 8 drives,
           replay-fenced, with the cross-method delta table vs §44.
  --gain   single-tone HB gain vs live ngspice S21 on each config (sanity).

Usage:
  python lna/_lin_hb.py --iip3 --replay 2
  python lna/_lin_hb.py --iip3 --state max --vdd 1.2      # one config
"""
import argparse
import json
import os
import re
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "hb"))

import port45  # noqa: E402
import hb_iip3 as H  # noqa: E402

REPRO = os.path.join(HERE, "repro", "dhruva-best")
OUT = os.path.join(HERE, "out")
RECIPE = "wplin-v1"

# The four rung-0 configurations, mapped to the emitted decks (transient side).
DECKS = {
    ("max", "1.1"): "dhruva-simul.sp",
    ("max", "1.2"): "dhruva-simul_v1p2.sp",
    ("min", "1.1"): "dhruva-simul_min_v1p1.sp",
    ("min", "1.2"): "dhruva-simul_min_v1p2.sp",
}

# §44.2 transient reference (this box, ngspice two-tone), by (state, rail, band):
# IIP3 / OIP3 in dBm. The cross-method bar (§37.6 / §40.3) is checked against it.
TRANSIENT = {
    ("max", "1.1"): {"dhruva-l5": (-33.459, -1.963), "dhruva-l2": (-33.589, -1.945),
                     "dhruva-l1": (-34.310, -2.033), "dhruva-s": (-34.461, -2.469)},
    ("max", "1.2"): {"dhruva-l5": (-34.532, -1.353), "dhruva-l2": (-34.678, -1.363),
                     "dhruva-l1": (-35.340, -1.464), "dhruva-s": (-35.260, -1.818)},
    ("min", "1.1"): {"dhruva-l5": (-33.205, -13.992), "dhruva-l2": (-33.280, -13.906),
                     "dhruva-l1": (-33.693, -13.622), "dhruva-s": (-33.668, -13.751)},
    ("min", "1.2"): {"dhruva-l5": (-34.188, -13.254), "dhruva-l2": (-34.278, -13.193),
                     "dhruva-l1": (-34.674, -12.966), "dhruva-s": (-34.458, -13.050)},
}

# Drive windows. Max-gain: the harness default (§40, -75..-40, 8 drives). Min-gain:
# the D6 S3 state attenuates ~12 dB OUTPUT-side, dropping the IM3 products toward
# the numerical floor -- the transient side re-drove min at -68..-52 to keep IM3
# above floor and below compression (§44.3). HB has the same signal-to-floor
# geometry, so min gets a matched, higher window of 8 drives.
PINS_MAX = list(H.PINS)                              # -75..-40
PINS_MIN = [-68.0, -66.0, -64.0, -62.0, -60.0, -58.0, -56.0, -54.0]

# Tone spacing per (band, state). Default = the sibling harness's 2 MHz (H.DF).
# EXCEPTION, documented not smoothed (§40.5 precedent): the D6 min-gain deck's
# dhruva-l2 spectrum triggers the VACASK 0.3.4.rc1 (f0, 2 MHz, nharm) construction
# pathology that §40.5 records -- it does not converge at 2 MHz for any nharm in
# reasonable time once the switch bank is present. It converges cleanly at the
# next spacing up; we use 3 MHz (the smallest that clears, closest to 2 MHz). The
# spacing dependence is ~0.4 dB/decade and monotone (§40.5 --fence), so the l2-min
# HB IIP3 carries a small, known, recorded spacing offset vs the 2 MHz rows.
DF_L2_MIN = 3e6


def _df_for(band, state):
    if state == "min" and band == "dhruva-l2":
        return DF_L2_MIN
    return H.DF


# nharm: §40.5's --fence proves IIP3 constant to <=0.001 dB over nharm 4..8, so
# nharm is a convergence knob, not a metric. nharm=5 converges for every
# (band, state) here EXCEPT l2-min-at-2MHz (handled by the spacing above); we keep
# the harness's own (5,6,7) ladder so any residual hard point still steps up.
_XM_BAR = 0.1                                        # cross-method investigate bar


# ---------------------------------------------------- port45 wrap (min decks)
_extra_re = re.compile(r"^\s*(v\w+)\s+(\S+)\s+(\S+)\s+dc\s+(\S+)", re.I)

# capture the genuine port45.convert ONCE, so the wrapper never calls itself
# after `port45.convert` has been re-pointed at the wrapper (recursion guard).
_ORIG_CONVERT = port45.convert


def _convert_with_switches(deck_path, model_path=None):
    """port45.convert + the deck's extra DC voltage sources (switch gates).

    port45.convert drops/handles vsup and the S-param ports and raises on any
    other V card. The D6 min deck adds `VSWGOB{1,2,3} nswc 0 dc {pVSWGOB}`. We
    let port45 do everything it can (feeding it a copy with those lines removed,
    so it never hits the `unhandled card` raise) and append the switch sources
    ourselves as VACASK `vsource dc=` cards, plus an rshunt on each new node so
    the DC path matches port45's own rshunt convention.
    """
    with open(deck_path, encoding="utf-8") as f:
        text = f.read()
    params = port45.read_params(text)
    body = text.split(".control")[0]

    extra_lines, extra_nodes, stripped = [], set(), []
    for raw in body.splitlines():
        ln = raw.strip()
        low = ln.lower()
        m = _extra_re.match(ln)
        # only intercept EXTRA V-dc cards -- never vsup, never the ports
        if m and not (low.startswith("vsup") or low.startswith("vp")):
            name, n1, n2, expr = m.group(1).lower(), m.group(2), m.group(3), m.group(4)
            dc = port45.val(expr, params)
            a, b = n1.lower(), n2.lower()
            extra_lines.append(f"{name} ({a} {b}) vsource dc={dc!r}")
            for n in (a, b):
                if n != "0":
                    extra_nodes.add(n)
            continue
        stripped.append(raw)

    # hand port45 a deck with the extra V-dc cards removed so it converts clean
    fd, tmp = tempfile.mkstemp(suffix=".sp", prefix="lin_hb_conv_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(stripped) + "\n")
        lines, p2, card, nodes = _ORIG_CONVERT(tmp, model_path=model_path)
    finally:
        os.unlink(tmp)

    # add the switch sources + an rshunt on any node port45 did not already see
    known = set(nodes)
    for n in sorted(extra_nodes):
        if n not in known:
            lines.append(f"rsh_{n} ({n} 0) resistor r=1e12")
            known.add(n)
    lines += extra_lines
    return lines, p2, card, sorted(known)


def _needs_switch_wrap(deck_path):
    with open(deck_path, encoding="utf-8") as f:
        body = f.read().split(".control")[0]
    for raw in body.splitlines():
        ln = raw.strip()
        low = ln.lower()
        if _extra_re.match(ln) and not (low.startswith("vsup") or low.startswith("vp")):
            return True
    return False


# ---------------------------------------------------------------- measurement
def _deck_for(state, vdd):
    p = os.path.join(REPRO, DECKS[(state, vdd)])
    if not os.path.exists(p):
        raise SystemExit(f"_lin_hb: emit the deck first ({p} missing) -- "
                         f"run `python lna/_lin_baseline.py --emit-deck`")
    return p


def measure_config(state, vdd, replay=2, pins=None):
    """HB IIP3/OIP3 over four bands for one (state, rail), replay-fenced.

    Returns (results, replay_spread) where results is the first-pass per-band
    dict from hb_iip3.cmd_iip3 and replay_spread is the worst in-process spread
    on every gated quantity across `replay` full re-runs (HB precedent 0.000 dB,
    §40.3 / §6.7 replay fence)."""
    deck = _deck_for(state, vdd)
    pins = pins or (PINS_MIN if state == "min" else PINS_MAX)
    deck_of = lambda band, _d=deck: _d          # fixed-sizing: one deck, all bands

    # (b) re-point the read-only converter for the min deck's switch sources
    orig_convert = port45.convert
    orig_nodes_of = port45.nodes_of
    if _needs_switch_wrap(deck):
        port45.convert = _convert_with_switches
        port45.nodes_of = lambda dp=deck, mp=None: _convert_with_switches(dp, mp)[3]
    try:
        reps = []
        for r in range(replay):
            root = tempfile.mkdtemp(prefix=f"lin_hb_{state}_{vdd}_{r}_")
            try:
                # measure band-by-band so each can carry its own tone spacing
                # (l2-min needs 3 MHz, see DF_L2_MIN); all other harness logic
                # -- compression keep, 3:1 slope, median IIP3 -- is untouched.
                res = {}
                for band in sorted(H.BANDS):
                    one = H.cmd_iip3(root, [band], deck_of, df=_df_for(band, state),
                                     pins=pins, verbose=(r == 0))
                    res[band] = one[band]
            finally:
                import shutil
                shutil.rmtree(root, ignore_errors=True)
            reps.append(res)
    finally:
        port45.convert = orig_convert
        port45.nodes_of = orig_nodes_of

    # replay spread on every gated quantity
    spreads = {}
    for band in sorted(H.BANDS):
        for key in ("iip3_dbm", "oip3_dbm", "gain_ss", "slope"):
            vals = [rp[band].get(key) for rp in reps]
            vals = [v for v in vals if v is not None]
            spreads.setdefault(band, {})[key] = (max(vals) - min(vals)) if vals else None
    return reps[0], spreads


def cmd_iip3(states, vdds, replay=2):
    payload = {"recipe": RECIPE, "diagnosis": "output-swing-current-limit",
               "source": "wplin-rung0-hb", "method": "vacask-hb-0.3.4.rc1",
               "configs": {}, "cross_method": {}}
    worst_xm = 0.0
    for vdd in vdds:
        for st in states:
            key = f"{st}_{vdd}"
            print(f"\n########## HB IIP3: state={st}, pVDD={vdd} V, "
                  f"deck {DECKS[(st, vdd)]} ##########")
            first, spreads = measure_config(st, vdd, replay=replay)
            cfg = {}
            for band in sorted(H.BANDS):
                r = first[band]
                cfg[band] = dict(
                    iip3_dbm=r["iip3_dbm"], oip3_dbm=r["oip3_dbm"],
                    gain_ss=r["gain_ss"], slope=r["slope"],
                    slope_ok=r["slope_ok"], kept=r["kept"],
                    iip3_spread=r["iip3_spread"], target_dbm=r["target_dbm"],
                    df_hz=_df_for(band, st), verdict=r["verdict"],
                    replay_spread=spreads[band])
            payload["configs"][key] = cfg

            # cross-method deltas vs §44 transient
            xm = {}
            ref = TRANSIENT[(st, vdd)]
            print(f"\n  -- cross-method vs §44 transient ({st}/{vdd} V) --")
            print(f"    {'band':<10}{'HB IIP3':>9}{'tr IIP3':>9}{'|Δ|':>7}"
                  f"{'HB OIP3':>9}{'tr OIP3':>9}{'|Δ|':>7}")
            for band in sorted(H.BANDS):
                tr_iip3, tr_oip3 = ref[band]
                hb = cfg[band]
                d_iip3 = abs(hb["iip3_dbm"] - tr_iip3)
                d_oip3 = abs(hb["oip3_dbm"] - tr_oip3)
                worst_xm = max(worst_xm, d_iip3, d_oip3)
                flag = "" if max(d_iip3, d_oip3) <= _XM_BAR else "  [!] > 0.1 dB"
                xm[band] = dict(hb_iip3=hb["iip3_dbm"], tr_iip3=tr_iip3,
                                d_iip3=d_iip3, hb_oip3=hb["oip3_dbm"],
                                tr_oip3=tr_oip3, d_oip3=d_oip3)
                print(f"    {band:<10}{hb['iip3_dbm']:>+9.2f}{tr_iip3:>+9.2f}"
                      f"{d_iip3:>7.3f}{hb['oip3_dbm']:>+9.2f}{tr_oip3:>+9.2f}"
                      f"{d_oip3:>7.3f}{flag}")
            payload["cross_method"][key] = xm

            print(f"\n  -- {st}-gain / {vdd} V HB summary --")
            for band in sorted(H.BANDS):
                c = cfg[band]
                rs = c["replay_spread"]
                print(f"    {band}: IIP3={c['iip3_dbm']:+.3f}  "
                      f"OIP3={c['oip3_dbm']:+.3f}  G={c['gain_ss']:.2f}  "
                      f"slope={c['slope']:.3f}{'' if c['slope_ok'] else '[!]'}  "
                      f"kept={c['kept']}  replaySpread(iip3)={rs['iip3_dbm']:.4f}  "
                      f"{c['verdict']}")

    payload["worst_cross_method_db"] = worst_xm
    payload["cross_method_bar_db"] = _XM_BAR
    payload["vacask_retries"] = H._RETRY_LOG
    print(f"\n=== worst cross-method |Δ| over all configs/bands/metrics: "
          f"{worst_xm:.3f} dB (bar {_XM_BAR}, precedent 0.08 dB) ===")
    if H._RETRY_LOG:
        print(f"[note] {len(H._RETRY_LOG)} VACASK retries: {H._RETRY_LOG}")
    jp = os.path.join(OUT, "_lin_hb_baseline.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, default=float)
    print(f"wrote {jp}")
    return payload


def cmd_gain(states, vdds):
    for vdd in vdds:
        for st in states:
            deck = _deck_for(st, vdd)
            orig_convert, orig_nodes = port45.convert, port45.nodes_of
            if _needs_switch_wrap(deck):
                port45.convert = _convert_with_switches
                port45.nodes_of = lambda dp=deck, mp=None: _convert_with_switches(dp, mp)[3]
            root = tempfile.mkdtemp(prefix=f"lin_hb_gain_{st}_{vdd}_")
            try:
                print(f"\n## single-tone HB gain vs ngspice S21: {st}/{vdd} V, "
                      f"{DECKS[(st, vdd)]} ##")
                H.cmd_gain(root, sorted(H.BANDS), deck)
            finally:
                import shutil
                shutil.rmtree(root, ignore_errors=True)
                port45.convert, port45.nodes_of = orig_convert, orig_nodes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iip3", action="store_true")
    ap.add_argument("--gain", action="store_true")
    ap.add_argument("--state", default="max,min")
    ap.add_argument("--vdd", default="1.1,1.2")
    ap.add_argument("--replay", type=int, default=2)
    a = ap.parse_args()
    if not os.path.exists(H.VACASK):
        raise SystemExit(f"vacask not found at {H.VACASK} (set VACASK_HOME)")
    states = [x.strip() for x in a.state.split(",")]
    vdds = [x.strip() for x in a.vdd.split(",")]
    if a.gain:
        cmd_gain(states, vdds)
    if a.iip3 or not a.gain:
        cmd_iip3(states, vdds, replay=a.replay)


if __name__ == "__main__":
    main()

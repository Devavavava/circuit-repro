"""WP-LIN rungs 2/3 -- the designed two-tone sweep (l5 f0) and the real
two-tone verification at the D6 min-gain state.

SIDECAR (D-9): reuses rung 0's machinery (`_lin_baseline.py`) verbatim -- its
deck emission, its min-gain S3 body/params builder (structural role resolution,
§42.2/§6.7), and its `iip3.py` override pattern (re-point deck_for + S21_REF_DB,
never disable, never edit the shared file). Nothing here edits `iip3.py`,
`size.py`, `_pgain_mech.py`.

A "candidate" is the designated `dhruva-simul` params with a few named .param
values changed IN BOX (the rung-1 B-survivor family: pNM6W up, pNM4W down). No
node names are touched; the D6 switch bank is inserted by
`_pgain_mech.build("out-bank", body)` exactly as rung 0 did.

Modes:
  --sweep       Rung 2 designed sweep: two-tone IIP3/OIP3 at dhruva-l5 f0 only,
                4 drive levels, for the in-box candidate family -- the real
                labels §5.2 designs. Answers directly: does the rung-1 +1.1 dB
                swing-product gain actually buy IIP3 on the designated point?
  --two-tone    Rung 3 verification: the top candidates at the D6 min-gain state
                (out-bank S3), 1.2 V, four bands, full §37.3 fences, replay-
                fenced. Anything claiming a pass is re-measured in HB.

Surrogate note (§5.1, absolute): the IIP3 label supply is 16 numbers over 4
sizings of one topology, none on a candidate mechanism, none at 1.2 V/D6. A
5-seed ensemble on that is a MEMORISER; §5.4 forbids any surrogate number in a
claim regardless. So rung 2's surrogate outcome is: SAY SO, and rank the
rung-1 survivors by the measured swing proxy + these real l5 labels instead.
No surrogate model is trained. This is the pre-registered §5.1 fallback.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import extract as E          # noqa: E402
import size as S             # noqa: E402
import iip3 as I3            # noqa: E402
import _lin_baseline as B    # noqa: E402
import _pgain_mech as M      # noqa: E402

REPRO = B.REPRO
OUT = B.OUT
RECIPE = "wplin-v1"
SOURCE_ARM = "wplin-verify"
BANDS = B.BANDS
F0 = B.F0

# The rung-1 B-survivor family (in-box), ranked by Iq*|Z_ac| (FINDINGS: screen).
# Each is a dict of param OVERRIDES on dhruva-simul at pVDD=1.2.
def _base_params(vdd="1.2"):
    return B.simul_params(vdd)


def candidate_params(name, vdd="1.2"):
    p = _base_params(vdd)
    W6 = float(p["pNM6W"])
    W4 = float(p["pNM4W"])
    fams = {
        "baseline":      {},
        "B_NM6x2.0":     {"pNM6W": str(W6 * 2.0)},
        "B_NM6x2.0_NM4x0.8": {"pNM6W": str(W6 * 2.0), "pNM4W": str(W4 * 0.8)},
        "B_NM6x1.5":     {"pNM6W": str(W6 * 1.5)},
        "B_NM6x1.5_NM4x0.85": {"pNM6W": str(W6 * 1.5), "pNM4W": str(W4 * 0.85)},
    }
    if name not in fams:
        raise SystemExit(f"unknown candidate {name}; have {list(fams)}")
    p.update(fams[name])
    return p


CANDIDATES = ["baseline", "B_NM6x2.0", "B_NM6x2.0_NM4x0.8",
              "B_NM6x1.5", "B_NM6x1.5_NM4x0.85"]


# ------------------------------------------------------------ deck emission
def emit_candidate_deck(name, state, vdd):
    """Emit a runnable .sp for a candidate at (state, rail). Reuses rung 0's
    base_body + min-gain S3 builder; only the core .params differ."""
    body, sizable, fixed = B.base_body()
    params = candidate_params(name, vdd)
    if state == "min":
        body, params = B.min_gain_body_params(body, params)
    deck = E.build_deck(body, params, F0["l5"], 1.1e9, 2.5e9)
    safe = name.replace(".", "p").replace("/", "_")
    v = f"{float(vdd):.1f}".replace(".", "p")
    path = os.path.join(REPRO, f"_lin_cand_{safe}_{state}_v{v}.sp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(deck)
    return path, body, params


def audited_s21_for(name, state, vdd, bands=None):
    """This candidate's own per-band audited S21 at (state, rail) -- the
    reference the re-pointed §37.4 cross-check uses (never disabled)."""
    body, sizable, fixed = B.base_body()
    params = candidate_params(name, vdd)
    if state == "min":
        body, params = B.min_gain_body_params(body, params)
    ref = {}
    for tag in (bands or BANDS):
        spec = S._spec_for_sizing(BANDS[tag])
        m = S.eval_metrics(body, params, spec, nf_gated=False)
        if m is None:
            raise SystemExit(f"_lin_verify: S21 ref sim failed {tag}/{name}/{state}")
        ref[tag] = m["s21_db"]
    return ref


def measure_candidate(name, state, vdd, pins, bands=None, replay=3):
    """Replay-fenced two-tone IIP3/OIP3 for one candidate over `bands` at
    (state, rail). Re-points iip3 at this candidate's deck + audited S21."""
    bands = bands or list(BANDS)
    path, _b, _p = emit_candidate_deck(name, state, vdd)
    ref = audited_s21_for(name, state, vdd, bands)

    I3.S21_REF_DB = dict(ref)
    I3.DESIGNATED = "simul"
    orig_deck_for = I3.deck_for
    I3.deck_for = lambda tag, sizing=I3.DESIGNATED, _p=path: _p
    I3.private_tmp()
    try:
        reps = []
        for r in range(replay):
            per = {}
            for tag in bands:
                res = I3.measure_band(tag, pins, sizing="simul", verbose=(r == 0))
                per[tag] = res
            reps.append(per)
    finally:
        I3.deck_for = orig_deck_for

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


def _oip3(res):
    return (res["iip3_dbm"] + res["gain_ss"]) if res.get("ok") else None


# ------------------------------------------------------------ rung 2 sweep
def cmd_sweep(vdd="1.2"):
    """Designed sweep: two-tone IIP3/OIP3 at dhruva-l5 f0 only, 4 drives, for the
    in-box candidate family, at MAX gain (the sweep's l5-only design, §5.2)."""
    pins = [-80.0, -68.0, -56.0, -44.0]          # 4 drives spanning the lever
    print(f"\n########## RUNG 2 DESIGNED SWEEP (l5 f0, max gain, {vdd} V) ##########")
    print("does the rung-1 +1.1 dB swing-product gain buy IIP3 on this point?\n")
    out = {"recipe": RECIPE, "source_arm": SOURCE_ARM,
           "diagnosis": "output-swing-current-limit",
           "surrogate_status": "MEMORISER -- not trained (§5.1); ranking by "
           "measured swing proxy + these real l5 labels instead",
           "band": "dhruva-l5", "state": "max", "vdd": vdd, "candidates": {}}
    base_oip3 = None
    print(f"{'candidate':<22}{'IIP3':>9}{'OIP3':>9}{'G':>8}{'slope':>7}"
          f"{'dOIP3 vs base':>14}")
    for name in CANDIDATES:
        first, spreads, ref = measure_candidate(name, "max", vdd, pins,
                                                bands=["l5"], replay=3)
        res = first["l5"]
        oip3 = _oip3(res)
        if name == "baseline":
            base_oip3 = oip3
        doip = (oip3 - base_oip3) if (oip3 is not None and base_oip3 is not None) else None
        out["candidates"][name] = dict(
            iip3_dbm=res.get("iip3_dbm"), oip3_dbm=oip3, gain_ss=res.get("gain_ss"),
            slope=res.get("slope"), slope_ok=res.get("slope_ok"),
            d_s21_db=res.get("d_s21_db"), s21_ok=res.get("s21_ok"),
            kept=res.get("kept"), ok=res.get("ok"),
            doip3_vs_base=doip, replay_spread=spreads["l5"])
        if res.get("ok"):
            print(f"{name:<22}{res['iip3_dbm']:>+9.3f}{oip3:>+9.3f}"
                  f"{res['gain_ss']:>8.2f}{res['slope']:>7.3f}"
                  f"{(doip if doip is not None else 0):>+14.3f}")
        else:
            print(f"{name:<22}  NO RESULT ({res.get('why')})")
    path = os.path.join(OUT, "_lin_sweep.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=float)
    print(f"\nwrote {path}")
    return out


# ------------------------------------------------------------ rung 3 verify
def cmd_two_tone(names, vdd="1.2", replay=3):
    """Rung 3: real two-tone at the D6 min-gain state (out-bank S3), 1.2 V, four
    bands, full §37.3 fences, replay-fenced. The min-gain drive window follows
    §44.3 (-68..-52) since the output-side S3 attenuates ~12 dB."""
    pins = [-68.0, -64.0, -60.0, -56.0, -52.0]   # §44.3 min-gain window
    print(f"\n########## RUNG 3 TWO-TONE @ D6 min-gain S3, {vdd} V ##########")
    out = {"recipe": RECIPE, "source_arm": SOURCE_ARM,
           "diagnosis": "output-swing-current-limit",
           "state": "min", "vdd": vdd, "candidates": {}}
    for name in names:
        print(f"\n===== candidate {name} =====")
        first, spreads, ref = measure_candidate(name, "min", vdd, pins,
                                                bands=list(BANDS), replay=replay)
        cfg = {}
        for tag in BANDS:
            res = first[tag]
            tgt = res.get("target_dbm")
            passed = bool(res.get("ok") and res.get("iip3_dbm") is not None
                          and tgt is not None and res["iip3_dbm"] >= tgt)
            cfg[tag] = dict(
                iip3_dbm=res.get("iip3_dbm"), oip3_dbm=_oip3(res),
                gain_ss=res.get("gain_ss"), target_dbm=tgt,
                margin_db=(res.get("iip3_dbm") - tgt) if (res.get("iip3_dbm") is not None and tgt is not None) else None,
                slope=res.get("slope"), slope_ok=res.get("slope_ok"),
                d_s21_db=res.get("d_s21_db"), s21_ok=res.get("s21_ok"),
                worst_snr_db=res.get("worst_snr_db"),
                iip3_pt_spread=res.get("iip3_pt_spread"),
                im3_fit_resid_db=res.get("im3_fit_resid_db"),
                kept=res.get("kept"), ok=res.get("ok"),
                passed=passed, replay_spread=spreads[tag])
            if res.get("ok"):
                print(f"  {tag}: IIP3={res['iip3_dbm']:+.3f} OIP3={_oip3(res):+.3f} "
                      f"G={res['gain_ss']:.2f} tgt={tgt:+.1f} "
                      f"margin={cfg[tag]['margin_db']:+.2f} slope={res['slope']:.3f}"
                      f"{'' if res.get('slope_ok') else '[!]'} "
                      f"dS21={res.get('d_s21_db'):+.3f} "
                      f"{'PASS' if passed else 'FAIL'}  "
                      f"replaySpread(iip3)={spreads[tag]['iip3']:.4f}")
            else:
                print(f"  {tag}: NO RESULT ({res.get('why')})")
        n_pass = sum(1 for tag in BANDS if cfg[tag]["passed"])
        out["candidates"][name] = dict(bands=cfg, n_pass=n_pass)
        print(f"  --> {name}: {n_pass}/4 bands pass D5 at the D6 min-gain state")
    path = os.path.join(OUT, "_lin_twotone.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=float)
    print(f"\nwrote {path}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--two-tone", action="store_true")
    ap.add_argument("--state", default="min")
    ap.add_argument("--vdd", default="1.2")
    ap.add_argument("--cands", default=",".join(CANDIDATES))
    ap.add_argument("--replay", type=int, default=3)
    a = ap.parse_args()
    if a.sweep:
        cmd_sweep(a.vdd)
    if a.two_tone:
        names = [x.strip() for x in a.cands.split(",") if x.strip()]
        cmd_two_tone(names, a.vdd, a.replay)
    if not (a.sweep or a.two_tone):
        ap.error("--sweep or --two-tone")


if __name__ == "__main__":
    main()

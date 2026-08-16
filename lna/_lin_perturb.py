"""WP-LIN closure -- the never-measured baseline-IIP3-under-perturbation set
(16-WP-LIN.md §1.3 item 5 / §4.4's reduced set; pre-registered in
plans2/18-WPLIN-CLOSURE.md).

No candidate survived rungs 1-4 (FINDINGS §45.5), so §4.4 applies to the
BASELINE designated point. This measures whether the D5 wall itself is stable
under perturbation -- the prior underneath the candidate-N record. §2.2's
current-swing diagnosis predicts ~1 dB of motion (registered as Q1); a wall
that moved >=5 dB would qualify the N record and must be reported loudly.

SIDECAR (D-9): reuses rung 0's machinery (`_lin_baseline.py`) verbatim -- its
base_body, its min-gain S3 body/params builder (structural role resolution,
§42.2/§6.7), and its iip3.py override pattern (re-point deck_for + S21_REF_DB,
never disable, never edit the shared file). The perturbation injection reuses
`corners.perturb`'s mechanism EXACTLY: pVDD scaled for VDD, a `.temp` card
appended to the body for temperature -- never by literal node name.

The reduced set (18-WPLIN-CLOSURE.md §1):
  P0  invariance control   .temp 27 @ nominal 1.2 V   (must reproduce §44.2)
  P1  VDD x0.9  (1.080 V)
  P2  VDD x1.1  (1.320 V)
  P3  temp 85 C
  P4  combo     VDD x0.9 + 85 C   (the two OIP3-reducing extremes at once)

States: D6 min-gain S3 (the ruled condition, primary) AND max gain.
Bands:  dhruva-l5 required; all four if cheap (--bands l5 | all).

Usage:
  python lna/_lin_perturb.py --sens-iip3 --state min,max --bands all --replay 3
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

REPRO = B.REPRO
OUT = B.OUT
RECIPE = "wplin-v1"
SOURCE_ARM = "wplin-sens-iip3"
BANDS = B.BANDS
F0 = B.F0

# The reduced perturbation set (18-WPLIN-CLOSURE.md §1). Each is
# (label, vdd_factor, temp_C).  vdd_factor multiplies the 1.2 V nominal;
# temp None means the ngspice default (27 C, no .temp card except P0's control).
PERTURBATIONS = [
    ("P0_nominal_control", 1.00, 27),    # invariance control -- reproduces §44.2
    ("P1_vdd_x0.9",        0.90, None),
    ("P2_vdd_x1.1",        1.10, None),
    ("P3_temp_85C",        1.00, 85),
    ("P4_combo_vdd0.9_85C", 0.90, 85),   # worst two-axis combo (§2.2 ordering)
]

# Min-gain drive window (§44.3, output-side S3 attenuates ~12 dB) and max-gain.
PINS_MIN = [-68.0, -64.0, -60.0, -56.0, -52.0]
PINS_MAX = [-80.0, -72.0, -64.0, -56.0, -48.0, -40.0]


def perturbed_body_params(state, vdd_factor, temp):
    """Baseline dhruva-simul at (state) with the perturbation applied.

    Reuses B.base_body + B.min_gain_body_params (structural roles, §42.2), then
    applies corners.perturb's mechanism: pVDD scaled, .temp appended to the body.
    Nominal rail is 1.2 V; vdd_factor multiplies it."""
    body, sizable, fixed = B.base_body()
    params = B.simul_params("1.2")
    if state == "min":
        body, params = B.min_gain_body_params(body, params)
    # pVDD scaling (the corners.perturb mechanism: last .param definition wins)
    params = dict(params)
    params["pVDD"] = f"{float(params['pVDD']) * vdd_factor:.6g}"
    # temperature card appended to the body (corners.perturb: `.temp`).
    if temp is not None:
        body = body.rstrip() + f"\n.temp {temp:g}\n"
    return body, params


def audited_s21(body, params, bands):
    """This perturbed config's own per-band audited S21 -- the reference the
    re-pointed §37.4 cross-check uses (never disabled). Measured on the SAME
    perturbed body/params, so the cross-check stays valid under perturbation."""
    ref = {}
    for tag in bands:
        spec = S._spec_for_sizing(BANDS[tag])
        m = S.eval_metrics(body, params, spec, nf_gated=False)
        if m is None:
            raise SystemExit(f"_lin_perturb: S21 ref sim failed {tag}")
        ref[tag] = m["s21_db"]
    return ref


def emit_perturbed_deck(label, state, body, params):
    safe = label.replace(".", "p").replace("+", "").replace(" ", "")
    deck = E.build_deck(body, params, F0["l5"], 1.1e9, 2.5e9)
    path = os.path.join(REPRO, f"_lin_sens_{safe}_{state}.sp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(deck)
    return path


def _oip3(res):
    return (res["iip3_dbm"] + res["gain_ss"]) if res.get("ok") else None


def measure(label, state, vdd_factor, temp, bands, pins, replay=3):
    """Replay-fenced two-tone IIP3/OIP3 over `bands` for one (perturbation,
    state). Re-points iip3 at this config's perturbed deck + audited S21."""
    body, params = perturbed_body_params(state, vdd_factor, temp)
    path = emit_perturbed_deck(label, state, body, params)
    ref = audited_s21(body, params, bands)

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
        return dict(iip3=res.get("iip3_dbm"), oip3=_oip3(res),
                    gain=res.get("gain_ss"), slope=res.get("slope"))
    spreads = {}
    for tag in bands:
        vals = [gq(rp[tag]) for rp in reps]
        spreads[tag] = {k: (max(v[k] for v in vals) - min(v[k] for v in vals))
                        if all(v[k] is not None for v in vals) else None
                        for k in vals[0]}
    return reps[0], spreads, ref, float(params["pVDD"])


def cmd_sens(states, bands, replay=3):
    print("\n########## WP-LIN CLOSURE: baseline IIP3 under perturbation "
          "(§1.3 item 5 / §4.4) ##########")
    print("Q1 prior (§2.2): the wall moves <=~1 dB/axis, <=~2 dB combo; "
          "falsifier: any >=5 dB move.\n")
    out = {"recipe": RECIPE, "source_arm": SOURCE_ARM,
           "diagnosis": "output-swing-current-limit",
           "point": "dhruva-simul (baseline, no candidate)",
           "nominal_vdd": 1.2, "results": {}}
    # nominal-per-state baselines (the P0 control) for the ΔIIP3 stability read
    nominal = {}
    for state in states:
        pins = PINS_MIN if state == "min" else PINS_MAX
        for label, vf, temp in PERTURBATIONS:
            first, spreads, ref, vdd_v = measure(label, state, vf, temp,
                                                 bands, pins, replay)
            cfg = {}
            for tag in bands:
                res = first[tag]
                tgt = res.get("target_dbm")
                iip3 = res.get("iip3_dbm")
                passed = bool(res.get("ok") and iip3 is not None
                              and tgt is not None and iip3 >= tgt)
                cfg[tag] = dict(
                    iip3_dbm=iip3, oip3_dbm=_oip3(res), gain_ss=res.get("gain_ss"),
                    target_dbm=tgt,
                    margin_db=(iip3 - tgt) if (iip3 is not None and tgt is not None) else None,
                    slope=res.get("slope"), slope_ok=res.get("slope_ok"),
                    d_s21_db=res.get("d_s21_db"), s21_ok=res.get("s21_ok"),
                    s21_ref=ref[tag], worst_snr_db=res.get("worst_snr_db"),
                    iip3_pt_spread=res.get("iip3_pt_spread"),
                    im3_fit_resid_db=res.get("im3_fit_resid_db"),
                    kept=res.get("kept"), ok=res.get("ok"), passed=passed,
                    replay_spread=spreads[tag])
            key = f"{state}::{label}"
            out["results"][key] = dict(state=state, label=label, vdd_v=vdd_v,
                                       temp_C=(temp if temp is not None else 27),
                                       bands=cfg)
            if label == "P0_nominal_control":
                nominal[state] = cfg
            # print with ΔIIP3 vs this state's nominal control
            base = nominal.get(state)
            print(f"-- {state} / {label}  (pVDD={vdd_v:.3f} V, "
                  f"T={temp if temp is not None else 27} C) --")
            for tag in bands:
                c = cfg[tag]
                if not c["ok"]:
                    print(f"    {tag}: NO RESULT ({first[tag].get('why')})")
                    continue
                dib = (c["iip3_dbm"] - base[tag]["iip3_dbm"]) if (base and base[tag]["ok"]) else None
                dob = (c["oip3_dbm"] - base[tag]["oip3_dbm"]) if (base and base[tag]["ok"]) else None
                dstr = (f" dIIP3={dib:+.3f} dOIP3={dob:+.3f}"
                        if dib is not None else " (control)")
                print(f"    {tag}: IIP3={c['iip3_dbm']:+.3f} OIP3={c['oip3_dbm']:+.3f} "
                      f"G={c['gain_ss']:.2f} tgt={c['target_dbm']:+.1f} "
                      f"margin={c['margin_db']:+.2f} slope={c['slope']:.3f}"
                      f"{'' if c['slope_ok'] else '[!]'} "
                      f"dS21={c['d_s21_db']:+.3f} replay={c['replay_spread']['iip3']:.4f}"
                      f"{dstr}  {'PASS' if c['passed'] else 'FAIL'}")
            print()

    # stability verdict on the ruled (min-gain) condition vs Q1
    if "min" in states and "min" in nominal:
        _verdict(out, "min")
    tag = "".join(sorted(bands)) if set(bands) != set(BANDS) else "all"
    fn = "_lin_sens_iip3.json" if bands == ["l5"] else f"_lin_sens_iip3_{tag}.json"
    path = os.path.join(OUT, fn)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=float)
    print(f"wrote {path}")
    return out


def _verdict(out, state):
    base = None
    for k, v in out["results"].items():
        if v["state"] == state and v["label"] == "P0_nominal_control":
            base = v["bands"]
    if base is None:
        return
    worst = 0.0
    worst_where = None
    print(f"===== STABILITY VERDICT ({state}-gain, ruled condition) vs Q1 =====")
    print(f"{'perturbation':<24}{'band':>5}{'dIIP3':>9}{'dOIP3':>9}")
    for k, v in out["results"].items():
        if v["state"] != state or v["label"] == "P0_nominal_control":
            continue
        for tag, c in v["bands"].items():
            if not (c["ok"] and base[tag]["ok"]):
                continue
            d = c["iip3_dbm"] - base[tag]["iip3_dbm"]
            do = c["oip3_dbm"] - base[tag]["oip3_dbm"]
            if abs(d) > abs(worst):
                worst, worst_where = d, f"{v['label']}/{tag}"
            print(f"{v['label']:<24}{tag:>5}{d:>+9.3f}{do:>+9.3f}")
    out["stability"] = dict(worst_abs_dIIP3=worst, worst_where=worst_where,
                            Q1_bar_1dB_axis=True,
                            Q1_falsifier_5dB=abs(worst) >= 5.0)
    print(f"\n  worst |dIIP3| = {abs(worst):.3f} dB at {worst_where}")
    if abs(worst) >= 5.0:
        print("  *** Q1 FALSIFIER TRIPPED: wall moves >=5 dB -- QUALIFIES the N "
              "record, report LOUDLY ***")
    elif abs(worst) <= 1.5:
        print("  Q1 CONFIRMED: the wall is stable to ~1 dB -- N's verdict is "
              "robust, not a nominal artefact")
    else:
        print(f"  Q1 partially: worst move {abs(worst):.2f} dB (>1.5, <5) -- "
              "recorded as measured")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sens-iip3", action="store_true")
    ap.add_argument("--state", default="min,max")
    ap.add_argument("--bands", default="all",
                    help="'l5' | 'all' | a comma list e.g. l2,l1,s")
    ap.add_argument("--replay", type=int, default=3)
    a = ap.parse_args()
    if not a.sens_iip3:
        ap.error("--sens-iip3")
    states = [x.strip() for x in a.state.split(",") if x.strip()]
    if a.bands == "l5":
        bands = ["l5"]
    elif a.bands == "all":
        bands = list(BANDS)
    else:
        bands = [x.strip() for x in a.bands.split(",") if x.strip()]
    cmd_sens(states, bands, a.replay)


if __name__ == "__main__":
    main()

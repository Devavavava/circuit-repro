"""Recreate / re-verify the WP-DHRUVA "best solution" — the four-band Gate D3
design `ace8383c2fa68d03` (FINDINGS.md SS25/SS27, JOURNEY.md stages 22/23).

One topology (215 AnalogGenie tokens, 20 devices / 2 inductors), sized
independently per band under `constrained_descent` with NF as the descent
target. Rebuilt fresh here from `tokens.json` + the four `dhruva-<band>.params.json`
files -- nothing is read back from the label store (`lna/data/topo_labels.jsonl`)
at run time, so this script is the whole reproduction surface.

Modes:
  --replay           (default) rebuild the netlist, re-run S11-over-band / S21@f0 /
                      Idd / NF(series-Rs) / K(in-band) at each band's stored
                      params. Prints a table next to the FINDINGS SS27.4 claim.
  --audit            --replay, plus: N repeats (label-noise check), in-box param
                      check, wide 0.1-20 GHz stability sweep, novelty check
                      (the same ladder as lna/_nf_gate_d3.py).
  --noise-budget     per-element noise budget (extract.measure_noise_budget) for
                      one band -- "whose noise", not just "how much".
  --band {s,l1,l2,l5,all}   restrict to one band (default: all)
  --resize BAND      re-derive a band's sizing from scratch (constrained_descent
                      on NF, starting from THIS design's own dhruva-s point) --
                      demonstrates the sizing recipe, does not overwrite the
                      shipped params.

    python lna/repro/dhruva-best/recreate.py --audit
    python lna/repro/dhruva-best/recreate.py --band s --noise-budget
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, LNA)

import extract as E                 # noqa: E402
import size as S                    # noqa: E402
from topology import Topology       # noqa: E402
from novelty import reference, wl_features, nn_similarity  # noqa: E402

WL_HASH = "ace8383c2fa68d03"
PARENT_HASH = "6f0d080f91dfc642"
BANDS = {"s": "dhruva-s", "l1": "dhruva-l1", "l2": "dhruva-l2", "l5": "dhruva-l5"}
GATED = ("s11_max_db", "s21_db", "idd_ma", "nf_db")

# FINDINGS SS27.4 -- the claim this script re-verifies, not trusts.
CLAIMED = {
    "dhruva-s":  dict(s11_max=-10.001, s21=36.473, idd=13.000, nf=1.288, target_nf=3.5,
                       k_in=54.6, k_wide=21.5),
    "dhruva-l1": dict(s11_max=-10.000, s21=36.824, idd=12.997, nf=1.220, target_nf=2.7,
                       k_in=17.3, k_wide=9.7),
    "dhruva-l2": dict(s11_max=-10.002, s21=35.773, idd=12.989, nf=1.506, target_nf=2.5,
                       k_in=14.4, k_wide=9.6),
    "dhruva-l5": dict(s11_max=-10.001, s21=35.961, idd=12.963, nf=1.253, target_nf=2.5,
                       k_in=19.9, k_wide=10.3),
}


def topo_of():
    tok = json.load(open(os.path.join(HERE, "tokens.json"), encoding="utf-8"))
    return Topology(tok)


def params_of(band_tag):
    return json.load(open(os.path.join(HERE, f"dhruva-{band_tag}.params.json"),
                           encoding="utf-8"))


def build_body():
    """The shared (topology, bias, geometry) body -- identical across all four
    bands, since only device VALUES differ by band, not the circuit. Default
    kwargs = to_spice's own current default: multi-finger MOS, w_finger=2um,
    inductor_q=12 (the honest, post-2026-08-10-cutover harness)."""
    prep = S.prepared_body(topo_of(), inductor_q=12)
    if prep is None:
        raise SystemExit("bias insert was skipped -- topology/bias mismatch")
    return prep  # (body, sizable, fixed)


def write_deck(band_tag, body, params, spec):
    """Emit the full runnable .sp deck for one band (device values substituted,
    S-param + stability control block appended) -- the artifact under
    lna/repro/dhruva-best/dhruva-<band>.sp."""
    band = spec.band
    deck = E.build_deck(body, params, float(band["f0"]), float(band["f_lo"]),
                         float(band["f_hi"]))
    path = os.path.join(HERE, f"dhruva-{band_tag}.sp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(deck)
    return path


def replay_one(band_tag, body, sizable, repeats=1, nf_gated=True):
    spec = S._spec_for_sizing(BANDS[band_tag])
    params = params_of(band_tag)
    runs = []
    for _ in range(repeats):
        m = S.eval_metrics(body, params, spec, nf_gated=nf_gated)
        if m is None:
            continue
        runs.append(m)
    return spec, params, runs


def in_box(params, sizable, spec):
    rng = S.kind_ranges(spec)
    oob = []
    for k, v in params.items():
        kind = sizable.get(k)
        if kind not in rng:
            continue
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        lo, hi = rng[kind][0], rng[kind][1]
        if x < lo * (1 - 1e-9) or x > hi * (1 + 1e-9):
            oob.append((k, x, lo, hi))
    return oob


def cmd_replay(bands, audit=False, repeats=5):
    body, sizable, fixed = build_body()
    print(f"topology: {topo_of().n_devices} devices, {topo_of().n_inductors} "
          f"inductors, wl_hash prefix expected {WL_HASH}")
    hashes, feats, meta = reference()
    hh, feat = wl_features(topo_of())
    print(f"novelty vs {meta.get('version')} ({meta.get('n_hashes')} hashes): "
          f"in reference={hh in hashes}  nearest={nn_similarity(feat, feats)}")
    print()
    header = (f"{'band':<10}{'S11_max':>9}{'S21':>9}{'Idd':>8}{'NF':>8}"
              f"{'target':>8}{'margin':>9}{'K_in':>9}{'K_wide':>9}{'verdict':>10}")
    print(header)
    print("-" * len(header))
    results = {}
    for tag in bands:
        n = repeats if audit else 1
        spec, params, runs = replay_one(tag, body, sizable, repeats=n)
        if not runs:
            print(f"{tag:<10}SIM FAILED")
            continue
        m = runs[0]
        feas, viol = spec.feasible(m)
        wide = E.measure_stability(body, params, float(spec.band["f0"]), 1e8, 2e10,
                                    npts=401)
        oob = in_box(params, sizable, spec) if audit else []
        spread = None
        if audit and len(runs) > 1:
            spread = {k: max(r[k] for r in runs) - min(r[k] for r in runs)
                      for k in GATED}
        target_nf = spec.constraints["nf_db"]["max"]
        margin = target_nf - m["nf_db"]
        verdict = "PASS" if feas else "FAIL"
        print(f"{BANDS[tag]:<10}{m['s11_max_db']:>9.3f}{m['s21_db']:>9.3f}"
              f"{m['idd_ma']:>8.3f}{m['nf_db']:>8.3f}{target_nf:>8.2f}"
              f"{margin:>9.3f}{m['k_min']:>9.4g}"
              f"{(wide['k_min'] if wide else float('nan')):>9.4g}{verdict:>10}")
        results[tag] = dict(metrics=m, feasible=feas, wide_k_min=(wide or {}).get("k_min"),
                            spread=spread, oob=oob, s21_min=m.get("s21_min_db"),
                            s21_ripple=m.get("s21_ripple_db"))
        if audit:
            print(f"    replay x{n}: all feasible={all(spec.feasible(r)[0] for r in runs)}"
                  + (f"  spread(max-min): " + ", ".join(f"{k}={v:.4g}" for k, v in spread.items())
                     if spread else ""))
            print(f"    in-box: {not oob}" + (f"  violations={oob}" if oob else
                                              f"  ({len(params)} params all inside)"))
            print(f"    s21_min={m.get('s21_min_db'):.3f} dB  s21_ripple={m.get('s21_ripple_db'):.3f} dB"
                  f"  (over {float(spec.band['f_lo']):.3g}-{float(spec.band['f_hi']):.3g} Hz)")
    print()
    print("vs FINDINGS SS27.4 claim (fresh - claimed):")
    for tag in bands:
        if tag not in results:
            continue
        c = CLAIMED[BANDS[tag]]
        m = results[tag]["metrics"]
        d_s11 = m["s11_max_db"] - c["s11_max"]
        d_s21 = m["s21_db"] - c["s21"]
        d_idd = m["idd_ma"] - c["idd"]
        d_nf = m["nf_db"] - c["nf"]
        print(f"  {BANDS[tag]:<10} dS11={d_s11:+.4f}  dS21={d_s21:+.4f}  "
              f"dIdd={d_idd:+.4f}  dNF={d_nf:+.4f}")
    return results


def cmd_noise_budget(band_tag):
    body, sizable, fixed = build_body()
    spec = S._spec_for_sizing(BANDS[band_tag])
    params = params_of(band_tag)
    nb = E.measure_noise_budget(body, params, spec)
    if nb is None:
        raise SystemExit("noise budget measurement failed")
    print(f"=== noise budget: {BANDS[band_tag]} @ f={nb['f']:.6g} Hz ===")
    print(f"NF (from shares) = {nb['nf_db_from_shares']:.4f} dB   "
          f"NF (inoise, cross-check) = {nb['nf_db_inoise']:.4f} dB   "
          f"sum-closure = {nb['sum_closure']:.6f}")
    rows = []
    p_src = nb["p_source"]
    for name, e in nb["elements"].items():
        if name == "rns":
            continue
        rows.append((name, e["kind"], e["frac"], e.get("excess_frac")))
    rows.sort(key=lambda r: -(r[3] or 0))
    print(f"{'element':<10}{'kind':<6}{'%out':>8}{'%(F-1)':>9}")
    for name, kind, frac, exc in rows[:10]:
        print(f"{name:<10}{kind:<6}{frac*100:>7.2f}%{(exc or 0)*100:>8.2f}%")
    return nb


def cmd_build_decks(bands):
    body, sizable, fixed = build_body()
    for tag in bands:
        spec = S._spec_for_sizing(BANDS[tag])
        params = params_of(tag)
        path = write_deck(tag, body, params, spec)
        print(f"wrote {path}")


def cmd_cross():
    """The Gate-D4-SIM matrix (FINDINGS SS35): every shipped per-band sizing
    evaluated against ALL FOUR band specs -- does one FIXED sizing meet every
    band's tier-1+tier-2 gates simultaneously? 16 cells, nothing resized."""
    body, sizable, fixed = build_body()
    specs = {t: S._spec_for_sizing(n) for t, n in BANDS.items()}
    all_ok = True
    for px in BANDS:
        params = params_of(px)
        row_ok = True
        for sx in BANDS:
            m = S.eval_metrics(body, params, specs[sx], nf_gated=True)
            if m is None:
                print(f"sizing={px:<3} spec={BANDS[sx]:<10} SIM FAILED")
                row_ok = False
                continue
            feas, viol = specs[sx].feasible(m)
            row_ok &= bool(feas)
            tnf = specs[sx].constraints["nf_db"]["max"]
            print(f"sizing={px:<3} spec={BANDS[sx]:<10} "
                  f"S11max={m['s11_max_db']:>8.3f}  S21={m['s21_db']:>7.3f}  "
                  f"Idd={m['idd_ma']:>6.3f}  NF={m['nf_db']:>6.3f} (<= {tnf})  "
                  f"{'PASS' if feas else 'FAIL viol=%.3f' % viol}")
        print(f"  -> sizing '{px}' simultaneous on all four bands: "
              f"{'YES' if row_ok else 'no'}")
        print()
        all_ok &= row_ok
    return all_ok


def cmd_resize(band_tag, seed=0, budget=400):
    """Re-derive a band's sizing from scratch via the same recipe that found
    it: constrained_descent minimizing nf_db, starting from THIS design's own
    dhruva-s point (the s11idd trust region), NOT a random start -- this
    demonstrates the sizing recipe end-to-end, it is not a fresh search."""
    body, sizable, fixed = build_body()
    spec = S._spec_for_sizing(BANDS[band_tag])
    start = params_of("s")
    res = S.constrained_descent(topo_of(), spec, start, target=("nf_db", "min"),
                                keep="s11idd", budget=budget, inductor_q=12,
                                seed=seed, prepared=(body, sizable, fixed))
    m = res["metrics"]
    feas = res["feasible"]
    print(f"RESIZE {BANDS[band_tag]} (seed {seed}, budget {budget}): "
          f"s11_max={m['s11_max_db']:.3f} S21={m['s21_db']:.3f} "
          f"Idd={m['idd_ma']:.3f} NF={m.get('nf_db')}  feasible={feas}")
    return feas


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--band", default="all", choices=["s", "l1", "l2", "l5", "all"])
    ap.add_argument("--audit", action="store_true", help="full evidence ladder (repeats, in-box, wide stability, novelty)")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--noise-budget", action="store_true", help="per-element noise budget for one band")
    ap.add_argument("--build-decks", action="store_true", help="(re)write the dhruva-<band>.sp files from tokens+params")
    ap.add_argument("--resize", metavar="BAND", choices=["s", "l1", "l2", "l5"],
                    help="re-derive a band's sizing from scratch via constrained_descent")
    ap.add_argument("--cross", action="store_true",
                    help="Gate-D4-SIM matrix: every sizing vs every band spec (FINDINGS SS35)")
    a = ap.parse_args()

    bands = list(BANDS) if a.band == "all" else [a.band]

    if a.cross:
        sys.exit(0 if cmd_cross() else 1)
    if a.resize:
        sys.exit(0 if cmd_resize(a.resize) else 1)
    if a.build_decks:
        cmd_build_decks(bands)
        sys.exit(0)
    if a.noise_budget:
        cmd_noise_budget(bands[0] if a.band != "all" else "s")
        sys.exit(0)

    results = cmd_replay(bands, audit=a.audit, repeats=a.repeats)
    ok = all(r["feasible"] for r in results.values())
    sys.exit(0 if ok else 1)

"""WP-HARDEN -- margin-hardening resize of the Gate-D4-SIM point (Session 9).

plans2/14-DHRUVA-SIMUL.md SS4 upgrade #1: one FIXED sizing of `ace8383c2fa68d03`
that keeps tier-1+tier-2 on all four dhruva bands simultaneously while pushing
the S11 band-wide margin off its 0.001 dB cliff (goal S11_max <= -10.5 dB,
stretch -11), paying with the D4-SIM point's NF/gain slack.

Objective (a 4-spec generalization of `size.constrained_descent`, implemented
here as a sidecar because size.py is owned by a concurrent agent this wave):

    minimize  s11_max_db                      (band-wide, common to all specs)
    s.t.      NF@f0(spec)  <= nf_limit(spec) - nf_floor     for all 4 specs
              S21@f0(spec) >= s21_target(spec) + s21_floor  for all 4 specs
              Idd          <= 13 mA
              K_min(in-band) >= k_floor       (stability IN the objective --
                                               polish walked designs into K<1
                                               historically, FINDINGS SS14/SS15)

Scoring is lexicographic (total floor shortfall, then s11_max), exactly the
`constrained_descent` rule, so a step never trades a kept floor for match.
Every candidate is clamped to `kind_ranges` -- in-box by construction.

Modes:
  --run    descent from the shipped dhruva-l5 params (budget scores; 1 score =
           4 ngspice evaluations, one per band spec). Writes lna/out/_harden/.
  --audit  evidence ladder on the saved best point: 5x replay per spec,
           in-box, in-band + 0.1-20 GHz stability, 4-spec cross matrix.
  --emit   write lna/repro/dhruva-best/dhruva-simul.{params,meta}.json from
           the audited best point (never overwrites the shipped per-band files).
"""
import argparse
import json
import math
import os
import random
import sys
import time

LNA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, LNA)

import extract as E                  # noqa: E402
import size as S                     # noqa: E402
from topology import Topology        # noqa: E402
from moves import private_tmp        # noqa: E402

REPRO = os.path.join(LNA, "repro", "dhruva-best")
OUT = os.path.join(LNA, "out", "_harden")
BANDS = {"s": "dhruva-s", "l1": "dhruva-l1", "l2": "dhruva-l2", "l5": "dhruva-l5"}
GATED = ("s11_max_db", "s21_db", "idd_ma", "nf_db")
WL_HASH = "ace8383c2fa68d03"


def load_shared():
    tok = json.load(open(os.path.join(REPRO, "tokens.json"), encoding="utf-8"))
    topo = Topology(tok)
    prep = S.prepared_body(topo, inductor_q=12)
    if prep is None:
        raise SystemExit("bias insert skipped")
    specs = {t: S._spec_for_sizing(n) for t, n in BANDS.items()}
    lo = {float(sp.band["f_lo"]) for sp in specs.values()}
    hi = {float(sp.band["f_hi"]) for sp in specs.values()}
    assert len(lo) == 1 and len(hi) == 1, "specs no longer share the S11 window"
    return topo, prep, specs


def score_point(body, specs, params, nf_floor, s21_floor, k_floor,
                target="s11", s11_floor=-10.5):
    """((shortfall, target-value), per-spec metrics) -- lower tuple is better.

    target="s11": minimize band-wide s11_max (Idd kept <= 13 only).
    target="idd": minimize Idd, with s11_max <= s11_floor as a kept floor --
    the WP-SENS follow-up (FINDINGS SS39): Idd is co-fragile with S11 on the
    shipped point, so once S11 clears the sweep-derived -10.44 dB requirement,
    the remaining slack buys current headroom, not more match."""
    short, s11, idd, mets = 0.0, None, None, {}
    for tag, sp in specs.items():
        m = S.eval_metrics(body, params, sp, nf_gated=True)
        if m is None:
            return (1e9, 1e9), None
        mets[tag] = m
        nf_lim = sp.constraints["nf_db"]["max"]
        s21_t = sp.constraints["s21_db"]["min"]
        if m.get("nf_db") is None:
            return (1e9, 1e9), None
        short += max(0.0, m["nf_db"] - (nf_lim - nf_floor))          # dB scale
        short += max(0.0, (s21_t + s21_floor) - m["s21_db"])         # dB scale
        short += max(0.0, m["idd_ma"] - 13.0)                        # mA scale
        km = m.get("k_min")
        short += max(0.0, k_floor - km) if km is not None else 1.0
        s11 = m["s11_max_db"] if s11 is None else max(s11, m["s11_max_db"])
        idd = m["idd_ma"] if idd is None else max(idd, m["idd_ma"])
    if target == "idd":
        short += max(0.0, s11 - s11_floor)                            # dB scale
        return (short, idd), mets
    return (short, s11), mets


def descend(budget=240, seed=0, nf_floor=1.0, s21_floor=0.3, k_floor=1.0,
            jitter=0.0, start=None, target="s11", s11_floor=-10.5):
    topo, (body, sizable, _fixed), specs = load_shared()
    rng = S.kind_ranges(specs["l5"])
    rand = random.Random(seed)

    def clamp(name, val):
        kind = sizable.get(name)
        if kind not in rng:
            return val
        lo, hi = rng[kind][0], rng[kind][1]
        return min(max(val, lo), hi)

    params = dict(start or json.load(
        open(os.path.join(REPRO, "dhruva-l5.params.json"), encoding="utf-8")))
    for nm in list(sizable):
        if nm in params:
            try:
                params[nm] = f"{clamp(nm, float(params[nm])):.6g}"
            except (TypeError, ValueError):
                pass
    if jitter > 0:
        for nm in list(sizable):
            if nm not in params:
                continue
            try:
                base = float(params[nm])
            except (TypeError, ValueError):
                continue
            params[nm] = f"{clamp(nm, base * math.exp(rand.uniform(-jitter, jitter))):.6g}"

    t0 = time.time()
    best_s, best_m = score_point(body, specs, params, nf_floor, s21_floor,
                                 k_floor, target=target, s11_floor=s11_floor)
    n = 1
    print(f"start: shortfall={best_s[0]:.4f}  {target}={best_s[1]:.3f}  "
          f"({time.time()-t0:.1f}s/score)")
    order = [k for k in sizable if k in params]
    trace = [{"n": n, "step": None, "shortfall": best_s[0], "best": best_s[1]}]

    def rand_dir(step_):
        pick = rand.sample(order, min(len(order), rand.randint(2, 4)))
        trial = dict(params)
        for nm in pick:
            try:
                base = float(trial[nm])
            except (TypeError, ValueError):
                continue
            trial[nm] = f"{clamp(nm, base * (1 + step_ * rand.choice((-1.0, 1.0)))):.6g}"
        return trial

    step = 0.30
    while n < budget and step > 0.015:
        rand.shuffle(order)
        improved = False
        for _ in range(max(2, len(order) // 3)):
            if n >= budget:
                break
            trial = rand_dir(step)
            s, m = score_point(body, specs, trial, nf_floor, s21_floor,
                                k_floor, target=target, s11_floor=s11_floor)
            n += 1
            if s < best_s:
                best_s, best_m, params, improved = s, m, trial, True
        for name in order:
            try:
                base = float(params[name])
            except (TypeError, ValueError):
                continue
            for factor in ((1 + step, 1 - step) if rand.random() < 0.5
                           else (1 - step, 1 + step)):
                cand = clamp(name, base * factor)
                if abs(cand - base) <= 1e-18:
                    continue
                trial = dict(params)
                trial[name] = f"{cand:.6g}"
                s, m = score_point(body, specs, trial, nf_floor, s21_floor,
                                k_floor, target=target, s11_floor=s11_floor)
                n += 1
                if s < best_s:
                    best_s, best_m, params, improved = s, m, trial, True
                    base = cand
                if n >= budget:
                    break
            if n >= budget:
                break
        trace.append({"n": n, "step": step, "shortfall": best_s[0],
                      "s11_max": best_s[1]})
        print(f"  n={n:>4}  step={step:.3f}  shortfall={best_s[0]:.4f}  "
              f"{target}={best_s[1]:.3f}  ({(time.time()-t0)/n:.1f}s/score avg)")
        if not improved:
            step *= 0.55
    return dict(best_params=params, score=best_s, metrics=best_m, n_scores=n,
                trace=trace, seed=seed, budget=budget, nf_floor=nf_floor,
                s21_floor=s21_floor, k_floor=k_floor, jitter=jitter,
                target=target, s11_floor=s11_floor)


def margins_of(mets, specs):
    rows = {}
    for tag, m in mets.items():
        sp = specs[tag]
        rows[tag] = dict(
            s11_max=m["s11_max_db"], s21=m["s21_db"], idd=m["idd_ma"],
            nf=m["nf_db"], k_min=m.get("k_min"),
            nf_margin=sp.constraints["nf_db"]["max"] - m["nf_db"],
            s21_margin=m["s21_db"] - sp.constraints["s21_db"]["min"],
            s11_margin=-10.0 - m["s11_max_db"], idd_margin=13.0 - m["idd_ma"])
    return rows


def cmd_audit(best_path, repeats=5):
    topo, (body, sizable, _fixed), specs = load_shared()
    best = json.load(open(best_path, encoding="utf-8"))
    params = best["best_params"]
    print(f"=== audit: {best_path} ===")
    ok = True
    all_mets = {}
    for tag, sp in specs.items():
        runs = [S.eval_metrics(body, params, sp, nf_gated=True)
                for _ in range(repeats)]
        runs = [r for r in runs if r is not None]
        if len(runs) < repeats:
            print(f"{BANDS[tag]}: {repeats - len(runs)} SIM FAILURES")
            ok = False
            continue
        spread = {k: max(r[k] for r in runs) - min(r[k] for r in runs)
                  for k in GATED}
        feas = all(sp.feasible(r)[0] for r in runs)
        ok &= feas
        m = runs[0]
        all_mets[tag] = m
        wide = E.measure_stability(body, params, float(sp.band["f0"]),
                                   1e8, 2e10, npts=401)
        print(f"{BANDS[tag]:<10} replay {len(runs)}/{repeats} feasible={feas}  "
              f"spread=" + ",".join(f"{k}={v:.4g}" for k, v in spread.items())
              + f"  K_in={m.get('k_min'):.4g} K_wide={(wide or {}).get('k_min'):.4g}")
        kw = (wide or {}).get("k_min")
        ok &= (m.get("k_min") or 0) > 1 and (kw or 0) > 1
    # in-box (audit against the tightest common box = any one spec's ranges;
    # all four dhruva specs share sizing ranges)
    rng = S.kind_ranges(specs["l5"])
    oob = []
    for k, v in params.items():
        kind = sizable.get(k)
        if kind not in rng:
            continue
        lo, hi = rng[kind][0], rng[kind][1]
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        if x < lo * (1 - 1e-9) or x > hi * (1 + 1e-9):
            oob.append((k, x, lo, hi))
    n_sz = sum(1 for k in params if sizable.get(k) in rng)
    print(f"in-box: {n_sz - len(oob)}/{n_sz} sizable params inside"
          + (f"  VIOLATIONS={oob}" if oob else ""))
    ok &= not oob
    if all_mets:
        rows = margins_of(all_mets, specs)
        worst = {k: min(r[k] for r in rows.values())
                 for k in ("s11_margin", "s21_margin", "nf_margin", "idd_margin")}
        print("worst-case margins:", {k: round(v, 3) for k, v in worst.items()})
    print("AUDIT", "PASS" if ok else "FAIL")
    return ok


def cmd_vdd_check(best_path):
    """WP-SENS follow-up: the harness nominal is pVDD=1.1 V while the spec text
    says 1.2 V -- a pending USER decision. Evaluate the point at BOTH so the
    numbers exist whichever nominal is picked. Returns {vdd: {band: metrics}}."""
    topo, (body, sizable, _fixed), specs = load_shared()
    best = json.load(open(best_path, encoding="utf-8"))
    rows = {}
    for vdd in ("1.1", "1.2"):
        params = dict(best["best_params"], pVDD=vdd)
        rows[vdd] = {}
        print(f"--- pVDD = {vdd} V ---")
        for tag, sp in specs.items():
            m = S.eval_metrics(body, params, sp, nf_gated=True)
            if m is None:
                print(f"{BANDS[tag]}: SIM FAILED"); rows[vdd][tag] = None; continue
            feas, viol = sp.feasible(m)
            rows[vdd][tag] = {k: m.get(k) for k in
                              ("s11_max_db", "s21_db", "idd_ma", "nf_db", "k_min")}
            rows[vdd][tag]["feasible"] = bool(feas)
            print(f"{BANDS[tag]:<10} S11max={m['s11_max_db']:>8.3f}  S21={m['s21_db']:>7.3f}  "
                  f"Idd={m['idd_ma']:>6.3f}  NF={m['nf_db']:>6.3f}  Kmin={m.get('k_min'):>7.4g}  "
                  f"{'PASS' if feas else 'FAIL viol=%.3f' % viol}")
    out = best_path.replace(".json", ".vdd.json")
    json.dump(rows, open(out, "w", encoding="utf-8"), indent=1)
    print(f"wrote {out}")
    return rows


def cmd_emit_vdd_source(best):
    return best.get("_vdd_rows_path")


def cmd_emit(best_path):
    best = json.load(open(best_path, encoding="utf-8"))
    best["_vdd_rows_path"] = best_path.replace(".json", ".vdd.json")
    params = best["best_params"]
    pj = os.path.join(REPRO, "dhruva-simul.params.json")
    mj = os.path.join(REPRO, "dhruva-simul.meta.json")
    json.dump(params, open(pj, "w", encoding="utf-8"), indent=1)
    meta = {
        "wl_hash": WL_HASH,
        "spec": "dhruva-simul (all four dhruva bands at one fixed sizing)",
        "recipe": "mf2-v1+harden-v1",
        "provenance": {
            "parent_point": "dhruva-l5.params.json (recipe mf2-v1, the Gate-D4-SIM designated point of FINDINGS SS35)",
            "how": "lna/_harden_simul.py multi-spec constrained descent: minimize band-wide s11_max subject to per-band NF/S21 floors, Idd<=13, K_min>=1 (stability in the objective)",
            "seed": best.get("seed"), "budget": best.get("budget"),
            "n_scores": best.get("n_scores"),
            "floors": {"nf_margin_db": best.get("nf_floor"),
                        "s21_margin_db": best.get("s21_floor"),
                        "k_min": best.get("k_floor")},
        },
        "harness": {"inductor_q": 12, "w_finger": 2e-6, "nf_gated": True,
                     "nf_method": "series_rs"},
        "final_score": {"shortfall": best["score"][0],
                         "target": best.get("target", "s11"),
                         "value": best["score"][1]},
    }
    vddp = os.path.join(OUT, os.path.basename(a_best_vdd)) if False else None
    vdd_path = cmd_emit_vdd_source(best)
    if vdd_path and os.path.exists(vdd_path):
        meta["dual_vdd_eval"] = json.load(open(vdd_path, encoding="utf-8"))
    json.dump(meta, open(mj, "w", encoding="utf-8"), indent=1)
    print(f"wrote {pj}\nwrote {mj}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--budget", type=int, default=240)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--jitter", type=float, default=0.0)
    ap.add_argument("--nf-floor", type=float, default=1.0)
    ap.add_argument("--s21-floor", type=float, default=0.3)
    ap.add_argument("--k-floor", type=float, default=1.0)
    ap.add_argument("--best", default=os.path.join(OUT, "best.json"))
    ap.add_argument("--target", default="s11", choices=["s11", "idd"])
    ap.add_argument("--s11-floor", type=float, default=-10.5)
    ap.add_argument("--start-best", default=None,
                    help="descend from an existing best.json's params")
    ap.add_argument("--vdd-check", action="store_true")
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    private_tmp(os.path.join(OUT, "tmp"))

    if a.run:
        start = None
        if a.start_best:
            start = json.load(open(a.start_best, encoding="utf-8"))["best_params"]
        res = descend(budget=a.budget, seed=a.seed, nf_floor=a.nf_floor,
                      s21_floor=a.s21_floor, k_floor=a.k_floor, jitter=a.jitter,
                      start=start, target=a.target, s11_floor=a.s11_floor)
        out = a.best if a.seed == 0 else a.best.replace(".json", f".s{a.seed}.json")
        json.dump(res, open(out, "w", encoding="utf-8"), indent=1)
        print(f"wrote {out}  final: shortfall={res['score'][0]:.4f} "
              f"{a.target}={res['score'][1]:.3f}")
    if a.vdd_check:
        cmd_vdd_check(a.best)
    if a.audit:
        sys.exit(0 if cmd_audit(a.best) else 1)
    if a.emit:
        cmd_emit(a.best)

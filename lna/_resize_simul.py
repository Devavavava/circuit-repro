"""_resize_simul.py — §49 margin-hardening resize from the flagship point.

plans2/14-DHRUVA-SIMUL.md §4 item 1 (second attempt): starting from the
designated `dhruva-simul` point (S11 already at -11.484 dB @ 1.2 V per §36),
maximize the worst-case normalized margin across all four dhruva specs
simultaneously, subject to:

  S11max      <= s11_floor (trust-region: keep the existing match, default -10.5 dB)
  Idd         <= 13 mA
  NF@f0       <= NF_target(spec) for all 4 specs        (kept constraints)
  S21@f0      >= S21_target(spec) for all 4 specs        (kept constraints)
  K_min       >= 1.0                                     (stability guard, always on)

The descent target is the normalized worst-case margin (maximize min over all
4 specs of min over all gated constraints of (limit - value) / scale), i.e.
the "polish" objective extended to four specs simultaneously. This is the
natural opposite of the §36 run, which minimized S11; here we spend S11/Idd
slack on NF/S21 margin robustness.

Modes:
  --run      descent from dhruva-simul.params.json (budget scores; 1 score =
             4 ngspice evaluations). Writes lna/out/_resize_simul/best.json.
  --cross    16-cell matrix (every per-band sizing vs every band spec) for the
             best saved point -- identical protocol to recreate.py --cross.
  --report   tabulate before/after margins per band from a saved best.json.

Usage:
  python lna/_resize_simul.py --run --budget 200
  python lna/_resize_simul.py --cross
  python lna/_resize_simul.py --report
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
sys.path.insert(0, os.path.abspath(os.path.join(LNA, "..", "misc", "ZOAF")))

import extract as E       # noqa: E402
import size as S          # noqa: E402
from topology import Topology  # noqa: E402
from moves import private_tmp  # noqa: E402

REPRO = os.path.join(LNA, "repro", "dhruva-best")
OUT = os.path.join(LNA, "out", "_resize_simul")
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
    return topo, prep, specs


def worst_margin(body, specs, params, s11_floor=-10.5, idd_limit=13.0, k_floor=1.0):
    """Compute (shortfall, -worst_case_margin) for lexicographic minimization.

    shortfall > 0 means a trust-region constraint is violated (S11, Idd, K_min).
    worst_case_margin = min over all four specs of min_normalized_margin.
    We MINIMIZE (shortfall, -margin) so lower tuple = better point.
    """
    all_margins = []
    short = 0.0
    s11_max_seen = None
    for tag, sp in specs.items():
        m = S.eval_metrics(body, params, sp, nf_gated=True)
        if m is None:
            return (1e9, 1e9), None
        # trust-region constraints (kept hard):
        s11v = m.get("s11_max_db")
        if s11v is None:
            return (1e9, 1e9), None
        s11_max_seen = max(s11_max_seen, s11v) if s11_max_seen is not None else s11v
        short += max(0.0, s11v - s11_floor)
        short += max(0.0, m.get("idd_ma", 0.0) - idd_limit)
        km = m.get("k_min")
        short += max(0.0, k_floor - km) if km is not None else 1.0

        # margin contribution from this spec (normalized):
        # S11 margin: how far below s11_floor (generous -- we keep S11 tight)
        s11_margin = (s11_floor - s11v) / 10.0   # normalize by 10 dB
        # NF margin: (target - value) / target
        nf_lim = sp.constraints["nf_db"]["max"]
        nf_val = m.get("nf_db")
        if nf_val is None:
            return (1e9, 1e9), None
        nf_margin = (nf_lim - nf_val) / nf_lim
        # S21 margin: (value - target) / target
        s21_t = sp.constraints["s21_db"]["min"]
        s21_val = m.get("s21_db", 0.0)
        s21_margin = (s21_val - s21_t) / abs(s21_t)
        # Idd margin: (13 - value) / 13
        idd_margin = (idd_limit - m.get("idd_ma", 0.0)) / idd_limit

        spec_worst = min(s11_margin, nf_margin, s21_margin, idd_margin)
        all_margins.append(spec_worst)

    worst = min(all_margins) if all_margins else -1e9
    return (short, -worst), None  # return None for metrics (retrieved separately)


def score_point(body, specs, params, s11_floor=-10.5, idd_limit=13.0, k_floor=1.0):
    """Returns ((shortfall, -worst_margin), {tag: metrics}) for a parameter set."""
    all_margins = []
    short = 0.0
    all_mets = {}
    for tag, sp in specs.items():
        m = S.eval_metrics(body, params, sp, nf_gated=True)
        if m is None:
            return (1e9, 1e9), None
        all_mets[tag] = m
        s11v = m.get("s11_max_db", 0.0)
        short += max(0.0, s11v - s11_floor)
        short += max(0.0, m.get("idd_ma", 0.0) - idd_limit)
        km = m.get("k_min")
        short += max(0.0, k_floor - km) if km is not None else 1.0

        nf_lim = sp.constraints["nf_db"]["max"]
        nf_val = m.get("nf_db")
        if nf_val is None:
            return (1e9, 1e9), None
        s21_t = sp.constraints["s21_db"]["min"]
        s21_val = m.get("s21_db", 0.0)
        idd_v = m.get("idd_ma", 0.0)

        s11_margin = (s11_floor - s11v) / 10.0
        nf_margin = (nf_lim - nf_val) / nf_lim
        s21_margin = (s21_val - s21_t) / abs(s21_t)
        idd_margin = (idd_limit - idd_v) / idd_limit

        spec_worst = min(s11_margin, nf_margin, s21_margin, idd_margin)
        all_margins.append(spec_worst)

    worst = min(all_margins) if all_margins else -1e9
    return (short, -worst), all_mets


def descend(budget=200, seed=0, s11_floor=-10.5, idd_limit=13.0, k_floor=1.0,
            start_path=None):
    topo, (body, sizable, _fixed), specs = load_shared()
    rng = S.kind_ranges(specs["l5"])
    rand = random.Random(seed)

    def clamp(name, val):
        kind = sizable.get(name)
        if kind not in rng:
            return val
        lo, hi = rng[kind][0], rng[kind][1]
        return min(max(val, lo), hi)

    # Start from dhruva-simul (the designated flagship point)
    start_file = start_path or os.path.join(REPRO, "dhruva-simul.params.json")
    params = dict(json.load(open(start_file, encoding="utf-8")))
    for nm in list(sizable):
        if nm in params:
            try:
                params[nm] = f"{clamp(nm, float(params[nm])):.6g}"
            except (TypeError, ValueError):
                pass

    t0 = time.time()
    best_s, best_m = score_point(body, specs, params,
                                  s11_floor=s11_floor, idd_limit=idd_limit,
                                  k_floor=k_floor)
    n = 1
    print(f"start: shortfall={best_s[0]:.4f}  worst_margin={-best_s[1]:.4f}  "
          f"({time.time()-t0:.1f}s/score)")
    if best_m is None:
        raise SystemExit("Start point simulation failed")

    # Print per-band starting metrics
    for tag, sp in specs.items():
        m = best_m[tag]
        nf_lim = sp.constraints["nf_db"]["max"]
        s21_t = sp.constraints["s21_db"]["min"]
        print(f"  {BANDS[tag]:<12} S11max={m['s11_max_db']:>8.3f}  "
              f"S21={m['s21_db']:>7.3f}  Idd={m['idd_ma']:>6.3f}  "
              f"NF={m['nf_db']:>6.3f} (<={nf_lim})  "
              f"K={m.get('k_min'):>6.2f}")

    order = [k for k in sizable if k in params]
    trace = [{"n": n, "shortfall": best_s[0], "worst_margin": -best_s[1]}]

    # Stability guard: use size._stab_ok which checks K_min >= 1 -> < 1 transitions
    # We need per-band K_min; use the worst one across specs
    def best_k_min(mets):
        if mets is None:
            return None
        ks = [m.get("k_min") for m in mets.values() if m is not None]
        ks = [k for k in ks if k is not None]
        return min(ks) if ks else None

    def stab_ok(cur_mets, new_mets):
        """Refuse step that takes worst K_min from >= 1 to < 1."""
        if not S._stab_guard_on():
            return True
        if cur_mets is None or new_mets is None:
            return True
        kc = best_k_min(cur_mets)
        kn = best_k_min(new_mets)
        if kc is None or kn is None:
            return True
        if kc >= 1.0 and kn < 1.0:
            return False
        return True

    def rand_dir(step_):
        """Joint multiplicative move on 2-4 coordinates."""
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
    n_refused = 0
    while n < budget and step > 0.015:
        rand.shuffle(order)
        improved = False
        # Random-direction probes
        for _ in range(max(2, len(order) // 3)):
            if n >= budget:
                break
            trial = rand_dir(step)
            s, m = score_point(body, specs, trial,
                               s11_floor=s11_floor, idd_limit=idd_limit,
                               k_floor=k_floor)
            n += 1
            if s < best_s:
                if stab_ok(best_m, m):
                    best_s, best_m, params, improved = s, m, trial, True
                else:
                    n_refused += 1
        # Coordinate sweep
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
                s, m = score_point(body, specs, trial,
                                   s11_floor=s11_floor, idd_limit=idd_limit,
                                   k_floor=k_floor)
                n += 1
                if s < best_s:
                    if stab_ok(best_m, m):
                        best_s, best_m, params, improved = s, m, trial, True
                        base = cand
                    else:
                        n_refused += 1
                if n >= budget:
                    break
            if n >= budget:
                break
        trace.append({"n": n, "step": step, "shortfall": best_s[0],
                      "worst_margin": -best_s[1]})
        print(f"  n={n:>4}  step={step:.3f}  shortfall={best_s[0]:.4f}  "
              f"worst_margin={-best_s[1]:.4f}  "
              f"({(time.time()-t0)/n:.2f}s/score avg)  refused={n_refused}")
        if not improved:
            step *= 0.55

    print(f"\nFinal: shortfall={best_s[0]:.4f}  worst_margin={-best_s[1]:.4f}  "
          f"n_scores={n}  n_refused={n_refused}")
    if best_m:
        print("Final per-band metrics:")
        for tag, sp in specs.items():
            m = best_m[tag]
            nf_lim = sp.constraints["nf_db"]["max"]
            s21_t = sp.constraints["s21_db"]["min"]
            feas, _ = sp.feasible(m)
            print(f"  {BANDS[tag]:<12} S11max={m['s11_max_db']:>8.3f}  "
                  f"S21={m['s21_db']:>7.3f}  Idd={m['idd_ma']:>6.3f}  "
                  f"NF={m['nf_db']:>6.3f} (<={nf_lim})  "
                  f"K={m.get('k_min'):>6.2f}  {'PASS' if feas else 'FAIL'}")

    # Extract representative metrics for the saved result (use l5 spec)
    rep_mets = best_m.get("l5") if best_m else None
    return dict(
        best_params=params,
        score=best_s,
        metrics=rep_mets,
        all_band_metrics={t: m for t, m in (best_m or {}).items()},
        n_scores=n,
        n_refused=n_refused,
        trace=trace,
        seed=seed,
        budget=budget,
        s11_floor=s11_floor,
        idd_limit=idd_limit,
        k_floor=k_floor,
        start_file=start_file,
        final_worst_margin=-best_s[1],
        final_shortfall=best_s[0],
    )


def cmd_cross(params):
    """16-cell matrix: every per-band sizing vs every band spec."""
    topo, (body, sizable, _fixed), specs = load_shared()
    all_ok = True
    from recreate import params_of, BANDS as RBANDS
    for px in RBANDS:
        p = params_of(px) if params is None else params
        row_ok = True
        for sx in RBANDS:
            sp = specs[sx]
            m = S.eval_metrics(body, p, sp, nf_gated=True)
            if m is None:
                print(f"sizing={px:<3} spec={BANDS[sx]:<12} SIM FAILED")
                row_ok = False
                continue
            feas, viol = sp.feasible(m)
            row_ok &= bool(feas)
            tnf = sp.constraints["nf_db"]["max"]
            print(f"sizing={px:<3} spec={BANDS[sx]:<12} "
                  f"S11max={m['s11_max_db']:>8.3f}  S21={m['s21_db']:>7.3f}  "
                  f"Idd={m['idd_ma']:>6.3f}  NF={m['nf_db']:>6.3f} (<= {tnf})  "
                  f"{'PASS' if feas else 'FAIL viol=%.3f' % viol}")
        print(f"  -> sizing '{px}' simultaneous on all four bands: "
              f"{'YES' if row_ok else 'no'}")
        print()
        all_ok &= row_ok
        if params is not None:
            # only one sizing when called with a specific params dict
            break
    return all_ok


def cmd_cross_simul(params):
    """16-cell matrix for the resized simul point against all four specs."""
    topo, (body, sizable, _fixed), specs = load_shared()
    all_ok = True
    # The simul point is ONE sizing; test it against all 4 specs in a 1×4 matrix
    # plus compare against the stored per-band sizings for a true 16-cell view
    print("=== Resized simul point: 1×4 matrix (one sizing, four specs) ===")
    for sx, sp_tag in BANDS.items():
        sp = specs[sx]
        m = S.eval_metrics(body, params, sp, nf_gated=True)
        if m is None:
            print(f"spec={sp_tag:<12} SIM FAILED")
            all_ok = False
            continue
        feas, viol = sp.feasible(m)
        all_ok &= bool(feas)
        tnf = sp.constraints["nf_db"]["max"]
        print(f"spec={sp_tag:<12} "
              f"S11max={m['s11_max_db']:>8.3f}  S21={m['s21_db']:>7.3f}  "
              f"Idd={m['idd_ma']:>6.3f}  NF={m['nf_db']:>6.3f} (<= {tnf})  "
              f"K={m.get('k_min'):>6.2f}  "
              f"{'PASS' if feas else 'FAIL viol=%.3f' % viol}")
    return all_ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="run descent from dhruva-simul")
    ap.add_argument("--cross", action="store_true",
                    help="16-cell matrix on the saved best (or dhruva-simul if no best)")
    ap.add_argument("--report", action="store_true",
                    help="print before/after margin table")
    ap.add_argument("--budget", type=int, default=200,
                    help="number of score evaluations (1 score = 4 ngspice calls)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--s11-floor", type=float, default=-10.5,
                    help="S11 trust-region floor (dB, e.g. -10.5 or -11.0)")
    ap.add_argument("--idd-limit", type=float, default=13.0)
    ap.add_argument("--k-floor", type=float, default=1.0)
    ap.add_argument("--best", default=os.path.join(OUT, "best.json"))
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    private_tmp(os.path.join(OUT, "tmp"))

    if a.run:
        res = descend(budget=a.budget, seed=a.seed,
                      s11_floor=a.s11_floor, idd_limit=a.idd_limit,
                      k_floor=a.k_floor)
        out_path = a.best if a.seed == 0 else a.best.replace(".json", f".s{a.seed}.json")
        json.dump(res, open(out_path, "w", encoding="utf-8"), indent=1)
        print(f"wrote {out_path}")

    if a.cross:
        params = None
        if os.path.exists(a.best):
            best = json.load(open(a.best, encoding="utf-8"))
            params = best["best_params"]
            print(f"Using params from {a.best}")
        else:
            params = json.load(open(os.path.join(REPRO, "dhruva-simul.params.json"),
                                    encoding="utf-8"))
            print("Using dhruva-simul.params.json (no best.json yet)")
        ok = cmd_cross_simul(params)
        print(f"\nSimul sizing on all four bands simultaneously: {'YES' if ok else 'NO'}")
        sys.exit(0 if ok else 1)

    if a.report:
        best_path = a.best
        if not os.path.exists(best_path):
            print(f"No best.json at {best_path}")
            sys.exit(1)
        best = json.load(open(best_path, encoding="utf-8"))
        topo, (body, sizable, _fixed), specs = load_shared()

        # Before: dhruva-simul baseline
        before_params = json.load(open(os.path.join(REPRO, "dhruva-simul.params.json"),
                                        encoding="utf-8"))
        after_params = best["best_params"]

        print("=== Before (dhruva-simul) vs After (resized) ===")
        print(f"{'band':<12}  {'S11_before':>12}  {'S11_after':>10}  "
              f"{'NF_before':>10}  {'NF_after':>9}  "
              f"{'S21_before':>11}  {'S21_after':>10}  "
              f"{'Idd_before':>11}  {'Idd_after':>10}  "
              f"{'K_before':>9}  {'K_after':>8}")
        print("-" * 140)
        for tag, sp_tag in BANDS.items():
            sp = specs[tag]
            mb = S.eval_metrics(body, before_params, sp, nf_gated=True)
            ma = S.eval_metrics(body, after_params, sp, nf_gated=True)
            if mb is None or ma is None:
                print(f"{sp_tag:<12}  SIM FAILED")
                continue
            print(f"{sp_tag:<12}  {mb['s11_max_db']:>12.3f}  {ma['s11_max_db']:>10.3f}  "
                  f"{mb['nf_db']:>10.3f}  {ma['nf_db']:>9.3f}  "
                  f"{mb['s21_db']:>11.3f}  {ma['s21_db']:>10.3f}  "
                  f"{mb['idd_ma']:>11.3f}  {ma['idd_ma']:>10.3f}  "
                  f"{mb.get('k_min',0):>9.2f}  {ma.get('k_min',0):>8.2f}")

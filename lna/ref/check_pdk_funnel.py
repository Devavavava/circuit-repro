"""Per-PDK FUNNEL golden: the WHOLE design funnel runs on every fetched PDK.

check_pdk.py proves the emitter's byte-identity + static wiring; check_pdk_live.py
proves each fetched device MODEL loads and conducts in a trivial hand-built amp.
This file closes the gap between those two: it drives ONE stored corpus topology
through the ACTUAL funnel the campaign uses --

    bias.insert_bias (rails from the adapter)      -> a conducting DC point
      -> to_spice emission (adapter device lines)  -> a runnable body
      -> extract deck assembly (OSDI pre-load for IHP)
      -> a real tiny CMA-ES sizing (budget ~50, 1 seed, the same
         size.make_objective / null_sizer._Budget the funnel uses)
      -> extract.run_and_extract / measure_nf

-- per PDK, and asserts the run COMPLETES with FINITE S21 and NF numbers and
ZERO ngspice model-load errors (the combined stdout+stderr is scanned verbatim
for 'unknown model' / 'could not find' / 'unable to find' / osdi failures at the
best sized point). It does NOT assert feasibility: a single corpus topology at a
50-eval budget is a mechanism check, not a design result. The measured numbers
are PRINTED per PDK so a reader sees exactly what each process produced.

WHY THIS MATTERS FOR FAIRNESS (the pre-reg question): if a PDK cannot even
conduct + size a stored topology at all, that is a FINDING to state in the
pre-registration -- honestly, up front -- not something to discover mid-campaign
on GPU. A PDK that completes here can be compared on equal footing; one that
skips-with-note (files absent) or fails loudly here is flagged before any quota
is spent.

Every PDK SKIPS-WITH-NOTE (not a failure) when its model files are absent on
this host, so a clone with no `.env/pdks/` stays green -- exactly like
check_pdk_live.py's clone-safety.

    python lna/ref/check_pdk_funnel.py          # exit 0 iff GREEN
    python lna/ref/check_pdk_funnel.py --budget 80 --spec <name-or-path>
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(LNA, ".."))
for _p in (LNA, os.path.join(ROOT, "misc", "ZOAF")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import extract as E                       # noqa: E402
import pdk                                # noqa: E402
import size as S                          # noqa: E402
import solve_spec as SS                   # noqa: E402
import null_sizer as N                    # noqa: E402
from topology import Topology             # noqa: E402

# The four PDKs the campaign spans, in bring-up order.
PDKS = ("bptm45", "sky130", "gf180mcu", "ihp_sg13g2")

# The default spec: a loose E-tier ladder rung (any process should at least
# conduct/size it). Its numeric targets are PDK-agnostic (the rail is the
# adapter's, not the spec's) -- see kaggle/CAMPAIGN-PDK-V0.md.
DEFAULT_SPEC = os.path.join(ROOT, "kaggle", "specs-ladder", "cap-e01-wifi.yaml")

# ngspice log substrings that mean a model/device did NOT load -- any of these in
# the VERBATIM combined output at the sized point is a hard fail even if a number
# came out. Same set check_pdk_live.py scans for. NOTE: bare "osdi" is NOT here
# on purpose -- the IHP driver ECHOES its `osdi <file>` load commands (a success
# path), so the scan matches only osdi *failure* phrases, not the word.
_MODEL_ERRORS = ("unknown model", "could not find", "unable to find",
                 "no such model", "specify .model", "unknown subckt",
                 "cannot find", "unknown model type",
                 "can't open osdi", "error loading osdi", "osdi load failed",
                 "failed to load")


def _easiest_corpus_topology():
    """The wifi24 --corpus path's easiest stored topology (fewest devices).

    solve_spec.CORPUS is the varied known-good set the arm-A / --corpus path
    sizes; the fewest-device member is the least likely to stall biasing, so it
    is the fairest single mechanism probe across processes."""
    best = None
    for wl in SS.CORPUS:
        try:
            toks = SS.tokens_for(wl)
        except SystemExit:
            continue
        topo = Topology(list(toks))
        if best is None or topo.n_devices < best[1].n_devices:
            best = (wl, topo, list(toks))
    if best is None:
        raise SystemExit("no CORPUS topology resolved (missing topo_labels?)")
    return best


def _model_error(log):
    low = (log or "").lower()
    return next((s for s in _MODEL_ERRORS if s in low), None)


def _raw_run_at(body, params, spec, pdk_name):
    """Re-run the sized best point capturing the VERBATIM ngspice output, so the
    model-load-error scan sees exactly what ngspice printed (the sizing loop
    swallows it). Returns the combined stdout+stderr string (or '')."""
    band = spec.band
    f0 = float(band.get("f0", 2.442e9))
    f_lo = float(band.get("f_lo", f0 * 0.98))
    f_hi = float(band.get("f_hi", f0 * 1.02))
    osdi = E.osdi_lines_for(pdk_name)
    if osdi:
        deck, extra = E.build_deck_split(body, params, f0, f_lo, f_hi, osdi)
    else:
        deck, extra = E.build_deck(body, params, f0, f_lo, f_hi), None
    return E.run_deck(deck, "funnel_", "c.cir", extra_files=extra) or ""


def run_pdk(pdk_name, topo, spec_ref, budget=50, seed=1):
    """Drive one topology through the full funnel on `pdk_name`.

    Returns None (skip) when the PDK is not fetched, else a result dict
    {ok, metrics, n_evals, n_fail, model_err, why}."""
    # clone-safety: skip-with-note when the models are not on this host.
    if pdk_name != "bptm45" and pdk.pdk_root(pdk_name) is None:
        print(f"  [{pdk_name}] not fetched (.env/pdks/{pdk_name} absent) -- "
              f"SKIP (not a failure)")
        return None

    spec = S._spec_for_sizing(spec_ref, nf_gate=None, pdk=pdk_name)
    prep = S.prepared_body(topo, inductor_q=SS.INDUCTOR_Q, pdk=pdk_name)
    if prep is None:
        print(f"  [{pdk_name}] bias insertion SKIPPED this topology "
              f"(no two-port / floating) -- FUNNEL CANNOT START")
        return {"ok": False, "metrics": None, "n_evals": 0, "n_fail": 0,
                "model_err": None, "why": "bias-insert skipped"}
    body, sizable, fixed = prep
    if not sizable:
        print(f"  [{pdk_name}] no sizable parameters -- FUNNEL CANNOT SIZE")
        return {"ok": False, "metrics": None, "n_evals": 0, "n_fail": 0,
                "model_err": None, "why": "no sizable params"}

    # a real tiny sizing: the exact make_objective the funnel uses, driven by
    # null_sizer's budget-counting CMA-ES (same objective callable ZOAF gets).
    points = []
    obj, names, decode, _ = S.make_objective(body, spec, sizable, fixed,
                                             points=points)
    bud = N._Budget(obj, budget, points)
    try:
        N.run_cmaes(bud, len(names), seed)
    except N._BudgetOut:
        pass
    best_x, m = bud.best()
    if m is None:
        print(f"  [{pdk_name}] sizing produced NO finite metrics in {bud.n} "
              f"evals ({bud.n_fail} sim failures) -- FUNNEL DID NOT COMPLETE")
        return {"ok": False, "metrics": None, "n_evals": bud.n,
                "n_fail": bud.n_fail, "model_err": None,
                "why": "no finite metrics"}

    # verbatim model-load scan at the actual sized point.
    log = _raw_run_at(body, decode(best_x), spec, pdk_name)
    merr = _model_error(log)

    s21 = m.get("s21_db")
    nf = m.get("nf_db")
    s11 = m.get("s11_db")
    idd = m.get("idd_ma")
    import math
    finite = (s21 is not None and math.isfinite(s21)
              and nf is not None and math.isfinite(nf))
    ok = finite and merr is None
    nf_s = f"{nf:.2f}" if nf is not None else "None"
    print(f"  [{pdk_name}] S21={s21:>8.2f} dB  S11={s11 if s11 is not None else 0:>7.2f} dB  "
          f"NF={nf_s:>7} dB  Idd={idd if idd is not None else 0:>7.3f} mA   "
          f"(d={len(names)} evals={bud.n} fails={bud.n_fail})   "
          f"finite:{finite} model-err:{merr or 'none'}   "
          f"[{'ok' if ok else 'FAIL'}]")
    return {"ok": ok, "metrics": m, "n_evals": bud.n, "n_fail": bud.n_fail,
            "model_err": merr, "why": None if ok else "non-finite or model-err"}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--budget", type=int, default=50,
                    help="CMA-ES evals per PDK (default 50 -- a mechanism probe)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--spec", default=DEFAULT_SPEC,
                    help="spec name/path the funnel sizes against (default a loose "
                         "E-tier ladder rung); the rail is the adapter's, not this")
    args = ap.parse_args()

    wl, topo, _toks = _easiest_corpus_topology()
    print(f"per-PDK funnel golden: corpus topology {wl[:12]} "
          f"({topo.n_devices} devices, {topo.n_inductors} inductors), "
          f"spec {os.path.basename(args.spec)}, budget {args.budget}, "
          f"seed {args.seed}")
    print("(a mechanism check: asserts the funnel COMPLETES with finite S21/NF "
          "and no model-load errors, NOT feasibility)")

    results = []
    for name in PDKS:
        results.append((name, run_pdk(name, topo, args.spec,
                                      budget=args.budget, seed=args.seed)))

    ran = [(n, r) for n, r in results if r is not None]
    n_pass = sum(1 for _, r in ran if r["ok"])
    n_skip = len(results) - len(ran)
    ok = all(r["ok"] for _, r in ran) if ran else True
    print(f"\ncheck_pdk_funnel: {'GREEN' if ok else 'RED'} "
          f"({n_pass}/{len(ran)} fetched PDK funnel(s) completed, "
          f"{n_skip} skipped)")
    if not ok:
        for n, r in ran:
            if not r["ok"]:
                print(f"  RED {n}: {r['why']}"
                      + (f" (model-err: {r['model_err']})" if r["model_err"] else ""))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

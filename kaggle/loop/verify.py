"""verify.py -- final-verdict INSTRUMENT for the capability-v0 campaign.

Given a sized best design (tokens + params + spec), take the advisory
measurements the sizing loop does NOT gate on, so a campaign row can report
them alongside the feasibility verdict:

  (a) two-tone IIP3           -- lna/iip3.py via size.measure_iip3_tier3()
  (b) band-wide S11/S21/S22   -- extract.run_and_extract() (the spec's own sweep)
  (c) K / mu / mu_s stability -- same extract call (free from the `sp` matrix)
  (d) S12 reverse isolation   -- already carried by the S-matrix (extract's
                                 `s12_db`); NO lna/ edit needed (audited: the
                                 metrics dict from run_and_extract already has
                                 `s12_db` = db|S_1_2| at f0).

DESIGN RULES (house law):
  * ADVISORY ONLY. Nothing here ever gates a campaign result. The campaign's
    feasible/infeasible verdict comes from the sizing loop; this module adds
    columns, never a pass/fail.
  * NEVER FATAL. Every measurement is wrapped in try/except with the error
    text captured verbatim into the verdict dict. A verify failure must not
    kill a campaign row -- `verify_design()` always returns a dict.
  * REUSE, not reimplementation. The IIP3 harness is size.measure_iip3_tier3
    (which itself drives lna/iip3.py at the WP-LIN-validated settings); the
    S-parameters/stability come from extract.run_and_extract. This file owns
    only the orchestration + the verdict shape.
  * The body+params are reconstructed exactly as the sizer saw them:
    size.prepared_body(topo) -> the same portnum-1/2 body size_tokens sized,
    and the design's own best_params. So the IIP3/S-params are measured on the
    identical deck the feasibility verdict was computed on.

stdlib + numpy/scipy (via the repo funnel) only. Resolves lna/ off
LNA_DEPS_ROOT exactly like driver.py.

    # unit smoke on the box (real ngspice; ~15-20 s for IIP3):
    source env.sh && export LNA_DEPS_ROOT=$PWD
    python kaggle/loop/verify.py --spec wifi24 --topology d6c0e6fc6dc1adaa \
        --seed 1 --budget 80
"""
import argparse
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("LNA_DEPS_ROOT") or os.path.abspath(
    os.path.join(HERE, "..", ".."))
LNA = os.path.join(ROOT, "lna")
for _p in (LNA, os.path.join(ROOT, "misc", "ZOAF"), HERE):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)


def _err(exc):
    """Verbatim, bounded error capture (house rule: never a bare 'failed')."""
    return {"error_verbatim": "".join(
        traceback.format_exception_only(type(exc), exc)).strip()[:2000]}


def _prepared(tokens, inductor_q=12):
    """Reconstruct (body, sizable, fixed) for a token list -- the exact deck the
    sizer used. Returns (prep_or_None, error_or_None)."""
    try:
        import size as S
        from topology import Topology
        prep = S.prepared_body(Topology(list(tokens)), inductor_q=inductor_q)
        if prep is None:
            return None, "prepared_body returned None (topology not biasable)"
        return prep, None
    except Exception as e:                                        # noqa: BLE001
        return None, _err(e)["error_verbatim"]


def measure_iip3(body, params, spec, verbose=False):
    """Advisory two-tone IIP3 at the spec's f0 (size.measure_iip3_tier3).

    Runs regardless of the spec's iip3 `status` -- this is the advisory path,
    not the gated tier-3 path. ~14-20 s (6-point Pin sweep, tmax=5 ps).
    Returns a dict: {ok, iip3_dbm, oip3_dbm, gain_ss_db, slope, kept, ...}
    or {ok:False, why|error_verbatim}."""
    t0 = time.time()
    try:
        import size as S
        r = S.measure_iip3_tier3(body, params, spec, verbose=verbose)
        if r is None:
            return {"ok": False,
                    "why": "harness returned None (no port 1/2 in body, or "
                           "spec has no f0)",
                    "seconds": round(time.time() - t0, 2)}
        r = dict(r)
        r["seconds"] = round(time.time() - t0, 2)
        return r
    except Exception as e:                                        # noqa: BLE001
        d = {"ok": False, "seconds": round(time.time() - t0, 2)}
        d.update(_err(e))
        return d


# advisory S-matrix / stability keys extract.run_and_extract already produces.
_SPARAM_KEYS = ("s11_db", "s11_max_db", "s21_db", "s21_min_db", "s21_ripple_db",
                "s22_db", "s22_max_db", "s12_db",
                "k_f0", "k_min", "mu_f0", "mu_min", "mu_src_f0", "mu_src_min",
                "delta_f0", "delta_max", "stab_band", "idd_ma", "nf_db")


def measure_sparams(body, params, spec):
    """Band-wide S11/S21/S22 + K/mu stability + S12 reverse isolation at the
    spec's own sweep band, from a single extract.run_and_extract() call.

    S12 (reverse isolation) is ALREADY in that dict as `s12_db` -- audited, no
    lna/ change needed. Adds a `stability_verdict` string (unconditional /
    conditional / unknown) from extract.stability_verdict()."""
    t0 = time.time()
    try:
        import extract as E
        m = E.run_and_extract(body, params, spec)
        if m is None:
            return {"ok": False,
                    "why": "run_and_extract returned None (singular matrix / "
                           "ngspice failure)",
                    "seconds": round(time.time() - t0, 2)}
        out = {"ok": True, "seconds": round(time.time() - t0, 2)}
        for k in _SPARAM_KEYS:
            if k in m:
                out[k] = m[k]
        try:
            verdict, why = E.stability_verdict(m)
            out["stability"] = verdict
            out["stability_why"] = why
        except Exception as e:                                   # noqa: BLE001
            out["stability"] = "unknown"
            out["stability_why"] = _err(e)["error_verbatim"]
        # S12 presence is load-bearing for the audit -- flag it explicitly.
        out["s12_extracted"] = ("s12_db" in m and m["s12_db"] is not None)
        return out
    except Exception as e:                                        # noqa: BLE001
        d = {"ok": False, "seconds": round(time.time() - t0, 2)}
        d.update(_err(e))
        return d


def wide_stability(body, params, spec, f_lo=1e8, f_hi=2e10, npts=201):
    """OPTIONAL out-of-band stability audit over a wide window (0.1-20 GHz by
    default). Feedback amps oscillate out of band, so the narrow-band K/mu from
    measure_sparams can be optimistic. Off by default in the campaign row (one
    extra ~1 s ngspice call); exposed for the final-point add-on."""
    t0 = time.time()
    try:
        import extract as E
        f0 = float((spec.band or {}).get("f0", 2.442e9))
        r = E.measure_stability(body, params, f0, f_lo, f_hi, npts=npts)
        if r is None:
            return {"ok": False, "why": "measure_stability returned None",
                    "seconds": round(time.time() - t0, 2)}
        v, why = E.stability_verdict(r)
        r = dict(r, ok=True, stability=v, stability_why=why,
                 seconds=round(time.time() - t0, 2), wide_band=[f_lo, f_hi])
        return r
    except Exception as e:                                        # noqa: BLE001
        d = {"ok": False, "seconds": round(time.time() - t0, 2)}
        d.update(_err(e))
        return d


def verify_design(tokens, params, spec, inductor_q=12, do_iip3=True,
                  do_sparams=True, do_wide_stability=False, verbose=False):
    """Run the advisory instrument on ONE sized design. ALWAYS returns a dict.

    Shape:
      {
        "ok": bool,                 # did the deck reconstruct at all
        "iip3": {...} | None,       # measure_iip3 result (advisory)
        "iip3_dbm": float | None,   # convenience: the headline advisory number
        "sparams": {...} | None,    # measure_sparams result (advisory)
        "wide_stability": {...} | None,
        "prepare_error": str | None,
        "seconds": float,
      }
    Never raises. A prepare/deck failure yields ok:False with the reason and
    null measurements -- a campaign row records it and moves on."""
    t0 = time.time()
    verdict = {"ok": False, "iip3": None, "iip3_dbm": None, "sparams": None,
               "wide_stability": None, "prepare_error": None}
    prep, perr = _prepared(tokens, inductor_q=inductor_q)
    if prep is None:
        verdict["prepare_error"] = perr
        verdict["seconds"] = round(time.time() - t0, 2)
        return verdict
    body, _sizable, _fixed = prep
    verdict["ok"] = True
    if do_iip3:
        verdict["iip3"] = measure_iip3(body, params, spec, verbose=verbose)
        if verdict["iip3"].get("ok"):
            verdict["iip3_dbm"] = verdict["iip3"].get("iip3_dbm")
    if do_sparams:
        verdict["sparams"] = measure_sparams(body, params, spec)
    if do_wide_stability:
        verdict["wide_stability"] = wide_stability(body, params, spec)
    verdict["seconds"] = round(time.time() - t0, 2)
    return verdict


# --------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True, help="spec name in lna/specs/ or a path")
    ap.add_argument("--topology", help="stored wl_hash to size + verify")
    ap.add_argument("--design", help="a solve_spec designs/<spec>/ dir to verify "
                    "(reads tokens.json + design.params.json); skips sizing")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--budget", type=int, default=120)
    ap.add_argument("--no-iip3", action="store_true")
    ap.add_argument("--no-sparams", action="store_true")
    ap.add_argument("--wide-stability", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--json", help="write the verdict dict here")
    args = ap.parse_args(argv)

    from spec import Spec
    spec = Spec.load(args.spec)

    if args.design:
        toks = json.load(open(os.path.join(args.design, "tokens.json")))
        params = json.load(open(os.path.join(args.design, "design.params.json")))
    elif args.topology:
        import solve_spec as SS
        toks = SS.tokens_for(args.topology)
        r = SS.size_tokens(list(toks), spec.source, args.seed, args.budget)
        if r is None:
            sys.exit("sizing produced no result for that topology/spec")
        params = r["best_params"]
        print("sized: feasible=%s obj=%s" % (r["feasible"], r["best_obj"]),
              flush=True)
    else:
        ap.error("give --topology <wl_hash> or --design <dir>")

    v = verify_design(toks, params, spec, do_iip3=not args.no_iip3,
                      do_sparams=not args.no_sparams,
                      do_wide_stability=args.wide_stability,
                      verbose=args.verbose)
    print(json.dumps(v, indent=2, default=float))
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(v, fh, indent=2, default=float)
        print("wrote %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())

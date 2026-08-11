"""Validate the WP-OBSERVE operating-point capture (plans2/09-WP-OBSERVE.md).

A logging instrument nobody validated is worse than none: a wrong `gm` in a
million rows is worse than no `gm` at all, because it will be believed. So this
runs the same kind of check `check_ref`/`check_nf`/`check_stab`/`check_bjt` run
for their own harnesses, on the reference deck whose answer is already known:

  1. DECK       -- with no probe requested the deck is byte-unchanged, and the
                   probe itself contains no `save` (gotcha N1: a `save` before
                   `sp` restricts the saved set and silently kills S-params).
  2. INVARIANCE -- the metric vector is bit-identical (`repr`-level) with the
                   probe present and absent. The probe must not be able to move
                   the circuit; this is what proves "passive" rather than
                   asserting it.
  3. GOLDEN     -- every device's Id/gm captured passively out of the full
                   op+sp+stability run equals an INDEPENDENT bare-`op` probe of
                   the same body and params, to relative 1e-6. That probe shares
                   no code path with the capture beyond `run_deck`: its deck has
                   no `sp`, no `meas`, no stability expressions.
  4. DECK PARITY -- the op read from the series-Rs NOISE deck equals the op read
                   from the sizing deck. `build_noise_deck` has always claimed
                   the two share a DC solution; nobody had ever measured it, and
                   `size.log_l2_result` now depends on it.

Run:  python lna/ref/check_op.py [--overhead] [--verbose]
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

import extract as E                                       # noqa: E402
from spec import Spec                                     # noqa: E402

DECK = os.path.join(HERE, "ref24_tapped.cir")
# the deck's own hand-feasible starting point (its .param block, which body_of
# strips); sizing these is size.size_tapped's job, reproducing them is ours.
PARAMS = {"pW": "30u", "pL": "45n", "pVB": "0.40", "pVB2": "0.8",
          "pLs": "1.35n", "pLg": "8.0n", "pCex": "440f", "pRB": "10k",
          "pLd": "10n", "pQ": "10", "pF0": "2.442e9",
          "pRq": "{2*3.14159265*pF0*pLd/pQ}", "pCt1": "0.3p", "pCt2": "0.5p"}
TOL = 1e-6


def _rel(a, b):
    if a is None or b is None:
        return None
    d = max(abs(a), abs(b))
    return 0.0 if d == 0 else abs(a - b) / d


def independent_op(body, params):
    """A bare `op` probe, built HERE and not through control_block/build_deck.

    This is the whole point of the golden: it has to be able to disagree. One
    analysis, print the device parameters, stop -- no `sp`, no `meas`, none of
    the stability expressions the capture path runs alongside."""
    mos, bjt = E.op_devices(body)
    vecs = [f"@{d}[{p}]" for d in mos
            for p in ("id", "gm", "gds", "vgs", "vds", "vth", "vdsat")]
    vecs += [f"@{d}[{p}]" for d in bjt for p in ("ic", "ib", "vbe", "gm")]
    ctrl = [".control", "op"]
    ctrl += ["print " + " ".join(vecs[i:i + 8]) for i in range(0, len(vecs), 8)]
    ctrl += [".endc", ".end"]
    lines = [body.rstrip()]
    if params:
        lines.append(".param " + " ".join(f"{k}={v}" for k, v in params.items()))
    lines.append("\n".join(ctrl))
    out = E.run_deck("\n".join(lines) + "\n", "opgold_", "g.cir")
    return E.parse_op(out or "")


def check(verbose=False):
    spec = Spec.load("wifi24")
    body = E.body_of(DECK)
    ok = True

    band = spec.band
    f0 = float(band["f0"])
    f_lo, f_hi = float(band.get("f_lo", f0)), float(band.get("f_hi", f0))
    plain = E.build_deck(body, PARAMS, f0, f_lo, f_hi)
    probe = E.op_probe_lines(body)
    probed = E.build_deck(body, PARAMS, f0, f_lo, f_hi, op_probe=probe)
    added = len(probed.splitlines()) - len(plain.splitlines())
    clean = "save" not in "\n".join(probe).lower()
    untouched = "op_nodes_begin" not in plain
    print("== 1. the deck ==")
    print(f"   default deck unchanged by the feature      : "
          f"{'YES' if untouched else 'NO'}")
    print(f"   probe = {added} print-only lines, no `save` : "
          f"{'YES' if clean else 'NO'}   (gotcha N1)")
    ok = ok and untouched and clean

    m_off = E.run_and_extract(body, PARAMS, spec)
    cap = {}
    m_on = E.run_and_extract(body, PARAMS, spec, op_capture=cap)
    if m_off is None or m_on is None:
        print("   ngspice FAILED -- cannot validate")
        return False
    diffs = [k for k in m_off if repr(m_off[k]) != repr(m_on.get(k))]
    print("== 2. passive: metrics with the probe vs without ==")
    print(f"   {len(m_off)} metrics compared at repr precision, "
          f"{len(diffs)} differ" + (f": {diffs}" if diffs else ""))
    for k in ("s11_db", "s21_db", "idd_ma", "k_min"):
        print(f"     {k:<10} {m_off.get(k)!r}")
    ok = ok and not diffs

    gold = independent_op(body, PARAMS)
    print("== 3. golden: captured op vs an independent bare-`op` probe ==")
    print(f"   {'device':<8} {'Id (A)':>13} {'gm (S)':>13} {'rel(Id)':>9} "
          f"{'rel(gm)':>9} {'region':>7}")
    n_dev = 0
    for name in sorted(cap.get("devices", {})):
        a = cap["devices"][name]
        b = (gold.get("devices") or {}).get(name, {})
        rid, rgm = _rel(a.get("id"), b.get("id")), _rel(a.get("gm"), b.get("gm"))
        bad = (rid is None or rid > TOL) or (rgm is None or rgm > TOL)
        ok = ok and not bad
        n_dev += 1
        nan = float("nan")
        print(f"   {name:<8} {a.get('id'):>13.6e} {a.get('gm'):>13.6e} "
              f"{(rid if rid is not None else nan):>9.1e} "
              f"{(rgm if rgm is not None else nan):>9.1e} "
              f"{a.get('region', '?'):>7}" + ("   MISMATCH" if bad else ""))
    if not n_dev:
        print("   no devices captured -- FAIL")
        ok = False
    print(f"   nodes {len(cap.get('nodes', {}))}, "
          f"branch currents {len(cap.get('branches', {}))}, "
          f"schema {cap.get('schema')}, deck {cap.get('deck')!r}")
    if verbose:
        print(f"   nodes: {cap.get('nodes')}")
        print(f"   branches: {cap.get('branches')}")

    capn = {}
    nf = E.measure_nf(body, PARAMS, spec, op_capture=capn)
    print("== 4. deck parity: series-Rs noise deck vs sizing deck ==")
    worst, worst_k = 0.0, None
    for name, a in cap.get("devices", {}).items():
        b = (capn.get("devices") or {}).get(name, {})
        for p in ("id", "gm", "gds", "vgs", "vds", "vth", "vdsat"):
            r = _rel(a.get(p), b.get(p))
            if r is not None and r > worst:
                worst, worst_k = r, f"{name}.{p}"
    print(f"   NF = {nf} dB; worst relative op difference over "
          f"{len(cap.get('devices', {}))} devices x 7 params: {worst:.2e}"
          + (f" at {worst_k}" if worst_k else ""))
    parity = worst <= TOL and bool(capn.get("devices"))
    print(f"   the two decks share a DC solution: "
          f"{'YES' if parity else 'NO'} (tol {TOL:g})")
    ok = ok and parity

    print(f"\ncheck_op: {'GREEN' if ok else 'FAILED'}")
    return ok


def overhead(n=20, deck=None, params=None):
    """evals/sec with and without capture on a fixed benchmark (plans2/09 4.5).

    Three arms, because two would hide where any cost lives: the bare
    evaluation, the evaluation with the print probe in the deck, and the same
    plus assembling + serializing the store row (the part that scales with
    device count).

    The arms are INTERLEAVED and reported as medians. This machine runs other
    agents; a block-A-then-block-B timing on it measures whatever else was
    running, not the feature -- an early sequential run of this same benchmark
    swung from -1% to +33% on the identical code. Interleaving makes the load a
    common-mode term and the median throws away the samples where something else
    grabbed a core."""
    import json
    import statistics
    import datastore as ds
    spec = Spec.load("wifi24")
    body = E.body_of(deck or DECK)
    par = params or PARAMS
    arms = ("capture off", "capture on", "capture + row")
    samples = {k: [] for k in arms}
    nbytes = 0
    E.run_and_extract(body, par, spec)                      # warm the model cache
    for _ in range(n):
        for label in arms:
            t0 = time.perf_counter()
            cap = {} if label != "capture off" else None
            m = E.run_and_extract(body, par, spec, op_capture=cap)
            if label == "capture + row":
                row = ds.row_op("ref:bench", spec.name, cap, metrics=m,
                                params=par, stage="bench",
                                harness={"recipe": "bench"})
                nbytes = len(json.dumps(row, separators=(",", ":"),
                                        sort_keys=True))
            samples[label].append(time.perf_counter() - t0)
    med = {k: statistics.median(v) for k, v in samples.items()}
    a = med["capture off"]
    print(f"\n== overhead ({n} interleaved evaluations of "
          f"{os.path.basename(deck or DECK)}, medians) ==")
    for k in arms:
        v = med[k]
        print(f"   {k:<14} {v * 1e3:8.2f} ms/eval  {1.0 / v:7.2f} evals/s  "
              f"{(v - a) / a * 100:+6.2f}%   "
              f"[min {min(samples[k]) * 1e3:.1f} max {max(samples[k]) * 1e3:.1f}]")
    cap = {}
    E.run_and_extract(body, par, spec, op_capture=cap)
    print(f"   serialized row: {nbytes} bytes "
          f"({len(cap.get('devices', {}))} devices, "
          f"{len(cap.get('nodes', {}))} nodes)")
    eff = (med["capture + row"] - a) / a
    sub = int(os.environ.get("LNA_OP_SUBSAMPLE", "8") or 0)
    print(f"   per-captured-evaluation overhead {eff * 100:+.2f}%; at the default "
          f"1-in-{sub} inner sampling that is {eff / sub * 100:+.2f}% of a "
          f"sizing run   (target < 5%)")
    return eff


if __name__ == "__main__":
    if "--overhead" in sys.argv:
        overhead()
        sys.exit(0)
    sys.exit(0 if check(verbose="--verbose" in sys.argv) else 1)

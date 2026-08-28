"""parity_dump.py -- full-precision golden measurements for the goldens-parity
ruling (label-domain rule: kaggle/PLAYBOOK.md, kaggle/schemas/README.md).

The question the dump answers: does a DIFFERENT machine (its ngspice build, its
libm, its BLAS) reproduce this repo's golden measurements digit for digit? Two
machines that do are candidates for ONE label domain (pool their measurement
rows); two that don't stay separate domains forever. The ruling itself is the
user's; this file only produces the evidence, on whatever host runs it.

What it measures (read-only, deterministic, no store writes):

  1. ref_decks  -- the two check_ref reference decks, every extracted FIELD at
     full float precision (not check_ref's rounded prints, and NO tolerance:
     raw values only).
  2. funnel_eval -- ONE fixed-parameter evaluation through the ACTUAL campaign
     measurement path (bias-inserted corpus topology d6c0e6fc..., spec
     cap-e01-wifi, pdk bptm45, every sizable param at the exact decode midpoint
     x=0.5): exercises to_spice emission + extract's sp/noise analyses end to
     end. Fixed params, so it is deterministic per host -- unlike a CMA run,
     whose trajectory diverges chaotically on any last-bit difference.

Each measurement runs REPEATS times (default 3, the replay-fence norm): the
in-host spread must be exactly 0.0 before a cross-host comparison means
anything, and the dump records the spread so the report can prove it.

    python lna/ref/parity_dump.py --out parity-<host>.json

Compare two dumps field by field with:  python lna/ref/parity_dump.py --diff a.json b.json
"""
import argparse
import datetime
import json
import os
import platform
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.dirname(HERE)
ROOT = os.path.dirname(LNA)
for _p in (LNA, os.path.join(ROOT, "misc", "ZOAF")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPEATS = 3
FUNNEL_TOPO = "d6c0e6fc6dc1adaa"          # solve_spec.CORPUS[0], the funnel-golden topology
FUNNEL_SPEC = os.path.join(ROOT, "kaggle", "specs-ladder", "cap-e01-wifi.yaml")


def fingerprint():
    import numpy
    ng = os.environ.get("NGSPICE", "ngspice")
    try:
        p = subprocess.run([ng, "--version"], capture_output=True, text=True, timeout=30)
        ng_ver = next((ln.strip() for ln in (p.stdout + p.stderr).splitlines()
                       if "ngspice" in ln.lower()), "unknown")
    except Exception as e:                                         # noqa: BLE001
        ng_ver = "unavailable: %s" % e
    try:
        git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             text=True, cwd=ROOT, timeout=30).stdout.strip() or "unknown"
    except Exception:                                              # noqa: BLE001
        git = "unknown"
    return {
        "utc": datetime.datetime.utcnow().isoformat() + "Z",
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "numpy": numpy.__version__,
        "ngspice": ng_ver,
        "ngspice_path": ng,
        "git_commit": git,
    }


def _spread(runs):
    """Per scalar field: max-min across runs (0.0 == replay-fence clean)."""
    out = {}
    for k in runs[0]:
        vals = [r.get(k) for r in runs]
        if all(isinstance(v, (int, float)) for v in vals):
            out[k] = max(vals) - min(vals)
    return out


def measure_ref_decks(repeats):
    import check_ref as CR
    out = {}
    for deck in CR.DECKS:
        runs = [CR.run_deck(deck) for _ in range(repeats)]
        out[deck] = {"runs": runs, "max_spread": _spread(runs)}
    return out


def measure_funnel_eval(repeats):
    import numpy as np
    import size as S
    import solve_spec as SS
    from topology import Topology
    spec = S._spec_for_sizing(FUNNEL_SPEC, nf_gate=None, pdk="bptm45")
    toks = SS.tokens_for(FUNNEL_TOPO)
    prep = S.prepared_body(Topology(list(toks)), inductor_q=SS.INDUCTOR_Q,
                           pdk="bptm45")
    if prep is None:
        return {"error": "bias insertion skipped the funnel topology"}
    body, sizable, fixed = prep
    _obj, names, decode, evaluate = S.make_objective(body, spec, sizable, fixed)
    x_mid = np.full(len(names), 0.5)
    params = decode(x_mid)
    runs = []
    for _ in range(repeats):
        m = evaluate(x_mid)
        runs.append({k: v for k, v in (m or {}).items()
                     if isinstance(v, (int, float))})
    return {"topo": FUNNEL_TOPO, "spec": os.path.basename(FUNNEL_SPEC),
            "pdk": "bptm45", "n_sizable": len(names), "params": params,
            "runs": runs, "max_spread": _spread(runs) if runs and runs[0] else {}}


def diff(path_a, path_b):
    a, b = (json.load(open(p)) for p in (path_a, path_b))
    print("A:", a["fingerprint"]["ngspice"], "| git", a["fingerprint"]["git_commit"][:8])
    print("B:", b["fingerprint"]["ngspice"], "| git", b["fingerprint"]["git_commit"][:8])
    n_exact = n_close = n_diff = 0
    rows = []
    for section in ("ref_decks", "funnel_eval"):
        sa, sb = a.get(section), b.get(section)
        if sa is None or sb is None:
            continue
        blocks = (sa.items() if section == "ref_decks" else [("funnel_eval", sa)])
        blocks_b = dict(sb.items()) if section == "ref_decks" else {"funnel_eval": sb}
        for name, blk in blocks:
            blk_b = blocks_b.get(name)
            if not blk_b or not blk.get("runs") or not blk_b.get("runs"):
                continue
            ra, rb = blk["runs"][0], blk_b["runs"][0]
            for k in sorted(set(ra) & set(rb)):
                va, vb = ra[k], rb[k]
                if not isinstance(va, (int, float)) or not isinstance(vb, (int, float)):
                    continue
                if va == vb:
                    n_exact += 1
                    verdict = "EXACT"
                else:
                    rel = abs(va - vb) / max(abs(va), abs(vb), 1e-30)
                    verdict = "close(rel=%.3g)" % rel if rel < 1e-9 else "DIFF(rel=%.3g)" % rel
                    if rel < 1e-9:
                        n_close += 1
                    else:
                        n_diff += 1
                rows.append((name, k, repr(va), repr(vb), verdict))
    w = max(len(r[0]) for r in rows) if rows else 0
    for name, k, va, vb, verdict in rows:
        print(f"  {name:<{w}}  {k:<16} {va:<24} {vb:<24} {verdict}")
    print(f"\nfields: {n_exact} exact, {n_close} within 1e-9 relative, {n_diff} differ")
    return 0 if n_diff == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="parity.json")
    ap.add_argument("--repeats", type=int, default=REPEATS)
    ap.add_argument("--diff", nargs=2, metavar=("A.json", "B.json"),
                    help="compare two dumps instead of measuring")
    args = ap.parse_args()
    if args.diff:
        sys.exit(diff(*args.diff))
    doc = {"fingerprint": fingerprint(),
           "ref_decks": measure_ref_decks(args.repeats),
           "funnel_eval": measure_funnel_eval(args.repeats)}
    with open(args.out, "w") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
    print("parity dump ->", args.out)
    for deck, blk in doc["ref_decks"].items():
        print(" ", deck, "spread:", blk["max_spread"])
    fe = doc["funnel_eval"]
    if "max_spread" in fe:
        nz = {k: v for k, v in fe["max_spread"].items() if v}
        print("  funnel_eval spread:", nz or "all 0.0")


if __name__ == "__main__":
    main()

"""C-grid diagnostic: locate a wide-mu notch the verifier's 1001-point grid misses.
Sweeps mu over the rl-v1.1 window at 4x (the R-c grid) and 16x, reports the minimum,
its frequency, the -to-1 crossing width, and the verifier-grid points around it.
usage: mu_notch.py [--scan] <out.json> <raw.json or 'glob'> ...
  --scan: every verifier-passing design, 16x grid only; zoom only where mu < 1 (resumable)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ex_lib as X  # noqa: E402
import r4_sim as S  # noqa: E402


def main(out, files, scan=False):
    res = {}
    if scan and os.path.exists(out):
        res = json.load(open(out))
    with X.rl_window():
        lo, hi, n = X.PREP.stab_window()
    for f in files:
        try:
            r = json.load(open(f))
        except Exception:                                        # noqa: BLE001
            continue
        did = r.get("sid") or r.get("did")
        if did in res or not r.get("verifier_pass") or not r.get("params"):
            continue
        row = {}
        grids = (("x16", 16 * (n - 1) + 1),) if scan else (("x1", n), ("x4", 4 * (n - 1) + 1),
                                                            ("x16", 16 * (n - 1) + 1))
        for k, m in grids:
            c = S.mu_curve(r["body"], r["params"], f"lin {m} {lo:g} {hi:g}")
            if not c:
                row[k] = None
                continue
            fm, mm = min(c, key=lambda t: t[1])
            below = [fq for fq, mu in c if mu < 1]
            row[k] = {"n": m, "mu_min": mm, "f_min": fm,
                      "f_below_1": [min(below), max(below)] if below else None,
                      "n_below_1": len(below)}
        if not row.get("x16") or (scan and row["x16"]["mu_min"] >= 1):
            res[did] = row
            if len(res) % 50 == 0:
                json.dump(res, open(out, "w"))
            continue
        # zoom around the 16x minimum
        f0 = row["x16"]["f_min"]
        step = (hi - lo) / (n - 1)
        z = S.mu_curve(r["body"], r["params"],
                       f"lin 2001 {max(lo, f0 - step):g} {min(hi, f0 + step):g}")
        below = [fq for fq, mu in z if mu < 1]
        row["zoom"] = {"mu_min": min((m for _, m in z), default=None), "width_below_1_hz":
                       (max(below) - min(below)) if below else 0.0,
                       "verifier_grid_step_hz": step}
        res[did] = row
        print(did, json.dumps(row), flush=True)
        json.dump(res, open(out, "w"))
    json.dump(res, open(out, "w"))


if __name__ == "__main__":
    import glob
    a = sys.argv[1:]
    scan = a[0] == "--scan"
    a = a[1:] if scan else a
    main(a[0], [f for x in a[1:] for f in (sorted(glob.glob(x)) if "*" in x else [x])], scan)

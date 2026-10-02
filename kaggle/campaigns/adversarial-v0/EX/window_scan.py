"""Diagnosis for the R-b classes: the verifier's mu over the rl-v1.1 window
(10 MHz - 50 GHz) vs just OUTSIDE it (50-100 GHz lin 1001; 1-10 MHz lin 101), for
every verifier-passing design. No verdicts change; this explains R-b failures
(above-window instability vs internal instability with mu >= 1 everywhere).
usage: window_scan.py <out.json> <raw.json files ...>"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ex_lib as X  # noqa: E402,F401
import r4_sim as S  # noqa: E402


def main(out, files):
    res = {}
    if os.path.exists(out):
        res = json.load(open(out))
    for i, f in enumerate(files):
        try:
            r = json.load(open(f))
        except Exception:                                        # noqa: BLE001
            continue
        did = r.get("sid") or r.get("did")
        if not r.get("verifier_pass") or not r.get("params") or did in res:
            continue
        hi = S.mu_curve(r["body"], r["params"], "lin 1001 5e10 1e11")
        lo = S.mu_curve(r["body"], r["params"], "lin 101 1e6 1e7")
        mh = min(hi, key=lambda t: t[1]) if hi else None
        ml = min(lo, key=lambda t: t[1]) if lo else None
        lin = ((r.get("summary") or {}).get("Rb") or {}).get("linear_osc") or []
        res[did] = {"mu_min_50_100G": mh, "mu_min_1_10M": ml, "rb_linear": bool(lin),
                    "rb_r50": "r50/r50" in lin}
        if i % 50 == 0:
            json.dump(res, open(out, "w"))
    json.dump(res, open(out, "w"), indent=0)
    n = len(res)
    above = [k for k, v in res.items() if v["mu_min_50_100G"] and v["mu_min_50_100G"][1] < 1]
    below = [k for k, v in res.items() if v["mu_min_1_10M"] and v["mu_min_1_10M"][1] < 1]
    print(n, "designs; mu<1 at 50-100 GHz:", len(above), "; mu<1 at 1-10 MHz:", len(below))
    for k in sorted(set(above) | set(below) | {k for k, v in res.items() if v["rb_linear"]}):
        print(k, res[k])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])

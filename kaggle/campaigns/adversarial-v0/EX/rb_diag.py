"""R-b failure diagnosis: for every verifier-passing design whose R-b check found a
LINEAR oscillation, measure f_osc (1 uA kick, 500-600 ns mean crossings), confirm
with gear integration and a 4x finer time step, and read the verifier's mu around
f_osc (sp lin over f_osc +/- 20 %, 801 points) and over the rl-v1.1 window.
usage: rb_diag.py <out.json> <raw.json files ...>"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ex_lib as X  # noqa: E402


def main(out, files):
    import r4_sim as S
    res = {}
    if os.path.exists(out):
        res = json.load(open(out))
    for f in files:
        r = json.load(open(f))
        s = r.get("summary") or {}
        lin = (s.get("Rb") or {}).get("linear_osc") or []
        did = r.get("sid") or r.get("did")
        if not r.get("verifier_pass") or not lin or did in res:
            continue
        term = "r50/r50" if "r50/r50" in lin else lin[0]
        d = X.osc_diag(r["body"], r["params"], term)
        fo = d.get("f_osc_hz")
        near = None
        if fo:
            curve = S.mu_curve(r["body"], r["params"], f"lin 801 {0.8 * fo:g} {1.2 * fo:g}")
            near = min((m for _f, m in curve), default=None)
        with X.rl_window():
            lo, hi, n = X.PREP.stab_window()
        wide = S.mu_curve(r["body"], r["params"], f"lin {n} {lo:g} {hi:g}")
        wmin = min(wide, key=lambda t: t[1]) if wide else None
        res[did] = {"spec": r["spec"], "n_terms_linear": len(lin), "terms": lin,
                    "diag": {k: v for k, v in d.items() if k not in ("gear_amp", "fine_amp")},
                    "mu_min_near_fosc": near, "mu_min_window": wmin,
                    "idd_nominal_mA": ((r.get("res") or {}).get("metrics") or {}).get("idd_ma"),
                    "idd_late_mA_r50": -1e3 * ((((r.get("checks") or {}).get("Rb") or {})
                                                .get("rows") or {}).get("r50/r50") or {})
                    .get("amp", {}).get("iddl", 0.0)}
        print(did, term, fo, d["pp_v"], d["gear_verdict"], d["fine_step_verdict"], near, wmin,
              flush=True)
        json.dump(res, open(out, "w"), indent=1)
    json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])

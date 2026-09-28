"""Diagnostic: WHERE in 0.1-20 GHz is the wide mu minimum of a gated winner?

usage: mu_curve.py <cell> <cand> <seed> <out.json>
Re-runs smoke_run on the stability-enabled spec (deterministic), captures the
(body, params) the gate audits for the winner, and dumps mu(f) on the gate's
exact grid (1e8..2e10, 401 lin) plus the spec band edges.
"""
import sys, os, json, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stab_drv as S                                     # noqa: E402  (sets sys.path)
import bench_anchor_prep as PREP                         # noqa: E402
import extract as E                                      # noqa: E402

cell, cand, seed, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
cap = []
_orig = PREP.wide_stability


def _cap(spec, body, params):
    cap.append((spec, body, dict(params)))
    return _orig(spec, body, params)


PREP.wide_stability = _cap
sp = S.spec_for(cell, "stab")
r = PREP.smoke_run(list(S.tokens_for(cell, cand)), sp, seed, S.BUDGET, S.PDK)
spec, body, params = cap[0]                              # the winner's audit
f0 = float(spec.band["f0"])
lines = [body.rstrip(), ".param " + " ".join(f"{k}={v}" for k, v in params.items()),
         "\n".join([".control", "op", "sp lin 401 1e8 2e10 1"] + E._stability_lets()
                   + ["print mul", ".endc", ".end"])]
txt = E.run_deck("\n".join(lines) + "\n", "stabc_", "s.cir", timeout=120) or ""
pts = []
for ln in txt.splitlines():
    t = ln.split()
    if len(t) == 3 and re.match(r"^\d+$", t[0]):
        try:
            pts.append((float(t[1]), float(t[2])))
        except ValueError:
            pass
bad = [(f, m) for f, m in pts if m < 1.0]
res = {"cell": cell, "cand": cand, "seed": seed, "band": [spec.band["f_lo"], spec.band["f_hi"]],
       "mu_min_inband": (r["metrics"] or {}).get("mu_min"), "mu_min_wide": r.get("mu_min_wide"),
       "n_pts": len(pts), "n_pts_mu_lt_1": len(bad),
       "argmin": min(pts, key=lambda p: p[1]) if pts else None,
       "unstable_freqs_hz": [f for f, _m in bad]}
json.dump(res, open(out, "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "unstable_freqs_hz"}),
      "unstable span:", (bad[0][0], bad[-1][0]) if bad else None)

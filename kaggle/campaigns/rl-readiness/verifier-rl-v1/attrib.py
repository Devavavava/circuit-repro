"""Static attribution: which rl-v1 check does each BASELINE winner fail?

usage: attrib.py <out.json>

Baseline winners = R4 results.json rows with captured final params:
  tag s1 : every S-1 in-loop final-feasible wb winner (template + E-c edits),
  tag nb : R4's nb template / anchor a1 / E-c `add L VIN1-n1` in-loop runs
           (stab spec, STAB_WIDE_INLOOP=1, 0.1-20 GHz window).
Each SAME design (body + params, no re-sizing) is re-checked against the
rl-v1 pieces one at a time:
  topo   : Spec.structural_screen of the rl-v1-form spec (W1: wb max_inductors 2)
  struct : bench_anchor_prep.structural_degeneracy
  metrics: SZ.eval_metrics on the rl-v1-form spec -> per-constraint violations
           (nf_max_db = W5 band NF, s11_max_db = W6 band S11, the rest as before)
  wide   : wide_stability over the rl-v1 window 1e7..5e10, 1001 points
"""
import sys, os, json
REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop"):
    sys.path.insert(0, p)
os.environ["STAB_WIDE_WINDOW"] = "1e7,5e10,1001"
import bench_anchor_prep as PREP                              # noqa: E402
from topology import Topology                                 # noqa: E402
from spec import Spec                                         # noqa: E402

R4 = REPO + "/kaggle/campaigns/rl-readiness/R4/results.json"
LIB = REPO + "/kaggle/editcap-lib-v12-45nm"


def main(outp):
    od = os.path.join(os.environ.get("TMPDIR", "/tmp"), "specs", str(os.getpid()))
    out = []
    for r in json.load(open(R4))["rows"]:
        if r["tag"] not in ("s1", "nb") or not r.get("params_win"):
            continue
        res = r.get("result") or {}
        spec = PREP.SZ._spec_for_sizing(PREP.rl_v1_spec(f"{LIB}/{r['cell']}/spec.yaml",
                                                        out_dir=od), pdk="bptm45")
        topo = Topology(list(r["tokens"]))
        tl = PREP.topo_limits(spec, topo)
        st = PREP.structural_degeneracy(topo)
        m = PREP.SZ.eval_metrics(r["body"], r["params_win"], spec) or {}
        feas, viol = spec.feasible(m) if m else (False, {"<sim fail>": 1.0})
        ws, wok = PREP.wide_stability(spec, r["body"], r["params_win"])
        fails = []
        if not tl["ok"]:
            fails.append("topo:" + ",".join(tl["failed"]))
        if st:
            fails.append("struct:" + ",".join(st))
        fails += [f"spec:{k}" for k in viol]
        if not wok:
            fails.append("wide_mu(0.01-50GHz)")
        rec = {"tag": r["tag"], "cell": r["cell"], "cand": r["cand"], "seed": r["seed"],
               "baseline_final_feasible": bool(res.get("feasible")),
               "rlv1_pass": not fails, "rlv1_fails": fails,
               "violations": {k: round(v, 5) for k, v in viol.items()},
               "nf_db_f0": m.get("nf_db"), "nf_max_db": m.get("nf_max_db"),
               "s11_db_f0": m.get("s11_db"), "s11_max_db": m.get("s11_max_db"),
               "mu_min_wide_rlv1": (ws or {}).get("mu_min"),
               "mu_min_wide_baseline": res.get("mu_min_wide"),
               "n_inductors": topo.n_inductors, "n_devices": topo.n_devices}
        out.append(rec)
        print(rec["tag"], rec["cell"], rec["cand"], rec["seed"],
              "base=", rec["baseline_final_feasible"], "rlv1=", rec["rlv1_pass"], fails, flush=True)
    json.dump(out, open(outp, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1])

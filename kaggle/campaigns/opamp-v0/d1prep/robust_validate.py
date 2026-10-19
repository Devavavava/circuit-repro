"""Validation of the robustness gate (README D-O33/D-O34). From the worktree root via the wrapper:

  goldens          the 8 Stage-2 goldens AS SIZED (stored parameters) at their golden specs + the
                   gate; evaluated twice in this process and once more in a child process ->
                   identical reports required (as-sized determinism) -> results/rv_goldens.json
  fragile          the deliberately fragile positive-feedback OTA (circuits/pf_ota.net): sized with
                   the gate OFF at FRAGILE_SPEC (margin, seed 1, 2,500 evals) -> must be nominally
                   feasible and FAIL the gate; then sized with the gate ON (same spec/seed/budget)
                   -> results/rv_fragile.json
  det              gate-ON sizing determinism: two_stage_rz at its golden spec + gate, margin,
                   seed 1, 2,500 evals, in 3 processes -> one digest; also shows whether the
                   textbook anchor can be sized robust -> results/rv_det.json
"""
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CAMPAIGN = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CAMPAIGN)
sys.path.insert(0, os.path.join(CAMPAIGN, "stage2"))
os.environ.setdefault("OPAMP_V0_TMP", "/home/dpatni/.claude/jobs/7cd7ffc3/tmp/opamp")
import opamp_v0 as O          # noqa: E402
import s2common as S2         # noqa: E402

RESULTS = os.path.join(HERE, "results")
GOLDENS = ("ota5t", "two_stage_rz", "telescopic", "folded_cascode", "three_stage_nmc",
           "W-R1", "W-R23", "W-R4")
DROP = ("secs", "cpu_s")
# one stage cannot reach 40 dB without positive feedback (5T ceiling ~29 dB, README V3).
# (A first try at gain >= 45 dB / UGF >= 10 MHz ended nominally infeasible at 52.8 dB / 9.6 MHz,
# so the gate never ran; the UGF floor was lowered to R4's 5 MHz and the gain floor to 40 dB.)
FRAGILE_SPEC = {"name": "fragile-pf", "cl_pf": 2.0, "stability": "ss_tran", "constraints": {
    "gain_db": {"min": 40.0}, "ugf_mhz": {"min": 5.0}, "pm_deg": {"min": 60.0},
    "idd_ua": {"max": 200.0}}}


def rob(spec):
    return dict(spec, robust="pvt_mm", name=spec["name"] + "+robust")


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=repr).encode()).hexdigest()


def golden_reports():
    out = {}
    for g in GOLDENS:
        rec = json.load(open(os.path.join(S2.RESULTS, "golden-%s.json" % g)))
        out[g] = O.robust_evaluate(rec["netlist"], rec["params"], rob(S2.GOLDEN_SPECS[g]))
    return out


def summary_row(rb):
    bad = [c for c in rb["corners"] if not c["feasible"]]
    return {"pass": rb["pass"], "n_corners": rb["n_corners"],
            "failing": [c["corner"] for c in bad],
            "worst_corner": rb["worst_corner"], "worst_margin": rb["worst_margin"],
            "worst_invalid": rb["worst_invalid"],
            "per_corner": {c["corner"]: (None if not c["valid"] else
                                         [c["worst_constraint"], c["worst_margin"]])
                           if c["valid"] else ["invalid"] + c["flags"] for c in rb["corners"]}}


def ph_goldens():
    a = golden_reports()
    b = golden_reports()
    p = subprocess.run([sys.executable, os.path.abspath(__file__), "goldens-child"],
                       stdout=subprocess.PIPE)
    dc = p.stdout.decode().strip().splitlines()[-1]
    res = {"digest_run1": digest(a), "digest_run2": digest(b), "digest_child": dc,
           "deterministic": digest(a) == digest(b) == dc,
           "goldens": {g: dict(summary_row(a[g]), spec=S2.GOLDEN_SPECS[g]["constraints"])
                       for g in GOLDENS},
           "n_pass": sum(1 for g in GOLDENS if a[g]["pass"]), "reports": a}
    json.dump(res, open(os.path.join(RESULTS, "rv_goldens.json"), "w"), indent=1, sort_keys=True,
              default=str)
    for g in GOLDENS:
        s = res["goldens"][g]
        print("%-16s pass=%s failing=%s worst=%s %s" % (g, s["pass"], s["failing"],
                                                        s["worst_corner"], s["worst_margin"]))
    print("deterministic", res["deterministic"], "n_pass", res["n_pass"])


def _sz(text, spec):
    r = O.size(text, spec, seed=1, evals=2500, objective="margin")
    m = r["metrics"] or {}
    return r, {"feasible": r["feasible"], "feasible_nominal": r.get("feasible_nominal"),
               "worst_margin": r["worst_margin"], "worst_margin_robust": r.get("worst_margin_robust"),
               "gain_db": m.get("gain_db"), "ugf_mhz": m.get("ugf_mhz"), "pm_deg": m.get("pm_deg"),
               "idd_ua": m.get("idd_ua"), "flags": m.get("flags"), "params": r["params"],
               "cpu_s": r["cpu_s"], "n_fail": r["n_fail"]}


def ph_fragile():
    text = open(os.path.join(HERE, "circuits", "pf_ota.net")).read()
    r0, s0 = _sz(text, FRAGILE_SPEC)
    rb = O.robust_evaluate(text, r0["params"], rob(FRAGILE_SPEC)) if r0["params"] else None
    gains = {c["corner"]: c["metrics"]["gain_db"] for c in rb["corners"]} if rb else None
    r1, s1 = _sz(text, rob(FRAGILE_SPEC))
    g1 = ({c["corner"]: c["metrics"]["gain_db"] for c in r1["robust"]["corners"]}
          if r1.get("robust") else None)
    res = {"spec": FRAGILE_SPEC, "gate_off": s0, "gate_off_robust": summary_row(rb) if rb else None,
           "gate_off_corner_gain_db": gains, "gate_on": s1,
           "gate_on_robust": summary_row(r1["robust"]) if r1.get("robust") else None,
           "gate_on_corner_gain_db": g1,
           "fragile_fails_gate": bool(s0["feasible"] and rb and not rb["pass"])}
    json.dump(res, open(os.path.join(RESULTS, "rv_fragile.json"), "w"), indent=1, sort_keys=True,
              default=str)
    print(json.dumps({k: v for k, v in res.items() if k != "spec"}, indent=1, default=str))


def det_child(k):
    r = O.size(S2.circuit_text("two_stage_rz"), rob(S2.GOLDEN_SPECS["two_stage_rz"]), seed=1,
               evals=2500, objective="margin")
    body = {kk: v for kk, v in r.items() if kk not in DROP}
    m = r["metrics"] or {}
    print(json.dumps({"digest": digest(body), "feasible": r["feasible"],
                      "feasible_nominal": r.get("feasible_nominal"),
                      "worst_margin": r["worst_margin"],
                      "worst_margin_robust": r.get("worst_margin_robust"),
                      "robust_worst_corner": (r.get("robust") or {}).get("worst_corner"),
                      "gain_db": m.get("gain_db"), "ugf_mhz": m.get("ugf_mhz"),
                      "pm_deg": m.get("pm_deg"), "idd_ua": m.get("idd_ua"),
                      "swing_vpp": m.get("swing_vpp"), "cpu_s": r["cpu_s"], "n_fail": r["n_fail"],
                      "best_eval": r["best_eval"]}, sort_keys=True))


def ph_det():
    procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__), "det-child", str(k)],
                              stdout=subprocess.PIPE) for k in (1, 2, 3)]
    outs = [json.loads(p.communicate()[0].decode().strip().splitlines()[-1]) for p in procs]
    res = {"case": "two_stage_rz golden spec + robust pvt_mm, margin, seed 1, 2500 evals",
           "spec": rob(S2.GOLDEN_SPECS["two_stage_rz"]), "runs": outs,
           "bit_identical_3_processes": len({o["digest"] for o in outs}) == 1}
    json.dump(res, open(os.path.join(RESULTS, "rv_det.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    ph = sys.argv[1]
    if ph == "goldens":
        ph_goldens()
    elif ph == "goldens-child":
        print(digest(golden_reports()))
    elif ph == "fragile":
        ph_fragile()
    elif ph == "det":
        ph_det()
    elif ph == "det-child":
        det_child(sys.argv[2])
    else:
        raise SystemExit(__doc__)

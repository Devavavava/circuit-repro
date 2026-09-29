#!/usr/bin/env python
"""bench-v2 smoke checks (run via envrun.sh after the smoke pipeline):

  1. PROFILE/FLAGS: every sized result row carries result["verifier"] with
     profile rl-v1, the exact rl-v1 flag set, no env overrides, and a conforming
     rl-v1 spec (spec_rl_v1_issues == []).
  2. DETERMINISM: re-run recorded calls from scratch (fresh worker, fresh TMP)
     and compare the full result dict (only wall-clock keys excluded).
  3. KNOWN-UNSTABLE REJECTED: (a) R4 gate-rejected wideband template winner
     (spec-feasible, wide mu 0.35): PREP.wide_stability on its stored body/params
     -> not ok; (b) the E-c "add R VIN1-VOUT1" design, feasible under the lib
     spec but wide-unstable (R4 (b)), re-sized under the rl-v1 verifier on its
     cell's rl-v1 spec -> infeasible; (c) no smoke row that is spec-feasible but
     wide-unstable was planted, accepted, or used as a witness.
Writes smoke/smoke_checks.json.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bv2  # noqa: E402

RD = f"{HERE}/smoke/run"
R4 = f"{bv2.REPO}/kaggle/campaigns/rl-readiness/R4/results.json"


def strip(r):
    r = json.loads(json.dumps(r, default=repr))
    if isinstance(r, dict) and isinstance(r.get("stab_inloop"), dict):
        r["stab_inloop"].pop("wide_secs", None)
    return r


def main():
    import bench_anchor_prep as PREP
    out = {}
    rows = [json.loads(l) for l in open(f"{RD}/results.jsonl")]
    # ---- 1
    want = {k: PREP.VERIFIER_PROFILES["rl-v1"].get(k) for k in PREP.VERIFIER_FLAGS}
    bad = []
    n = 0
    for r in rows:
        res = r.get("res")
        if not res:
            continue
        n += 1
        v = res.get("verifier") or {}
        if (v.get("profile") != "rl-v1" or v.get("flags") != want or v.get("env_overrides")
                or v.get("spec_rl_v1_issues") or not v.get("stab_gate_on")
                or r.get("profile") != "rl-v1" or not r.get("era")):
            bad.append(r["jid"])
    out["profile_flags"] = {"rows_checked": n, "bad": bad, "pass": n > 0 and not bad}
    # ---- 2
    sized = [r for r in rows if r.get("res") and (r["res"].get("n_evals") or 0) > 0]
    pick = [r for r in sized if r["res"].get("feasible")][:2] + \
        [r for r in sized if not r["res"].get("feasible")][:2]
    det = []
    for r in pick:
        tokens = None
        spec = f"{bv2.REPO}/{r['spec']}"
        # tokens: recover from candidates / anchors via the tok hash
        for src in ("candidates.jsonl",):
            for l in open(f"{RD}/{src}"):
                c = json.loads(l)
                if c.get("tok") == r["tok"]:
                    tokens = c["tokens"]
                    break
        if tokens is None:
            for a in bv2.anchor_data().values():
                if a["tok"] == r["tok"]:
                    tokens = a["tokens"]
        if tokens is None:
            continue
        td = tempfile.mkdtemp(prefix="bv2det_", dir=os.environ.get("TMPDIR", "/tmp"))
        jf, of = f"{td}/j.json", f"{td}/o.json"
        json.dump({"jid": r["jid"], "tokens": tokens, "spec": spec, "seed": r["seed"],
                   "budget": r["budget"]}, open(jf, "w"))
        subprocess.run([sys.executable, f"{HERE}/bv2.py", "worker", jf, of], check=True,
                       capture_output=True)
        new = json.load(open(of))
        same = strip(new["res"]) == strip(r["res"])
        det.append({"jid": r["jid"], "kind": r["kind"], "feasible": r["res"]["feasible"],
                    "identical": same})
    out["determinism"] = {"rerun": det, "pass": bool(det) and all(d["identical"] for d in det)}
    # ---- 3a
    r4 = json.load(open(R4))["rows"]
    row = r4[74]
    sp = PREP.stability_spec(f"{bv2.REPO}/kaggle/editcap-lib-v12-45nm/{row['cell']}/spec.yaml")
    import size as SZ
    spec = SZ._spec_for_sizing(sp, nf_gate=None, pdk="bptm45")
    params = row.get("params_win") or row["params_bx"]
    st, ok = PREP.wide_stability(spec, row["body"], params)
    out["unstable_a_R4_template_gate_row74"] = {
        "cell": row["cell"], "recorded_spec_feasible": row["result"]["spec_feasible"],
        "recorded_mu_min_wide": row["result"]["mu_min_wide"],
        "recheck_mu_min_wide": (st or {}).get("mu_min"), "wide_ok": ok, "pass": ok is False}
    # ---- 3b
    row = r4[1]
    sp = PREP.rl_v1_spec(f"{bv2.REPO}/kaggle/editcap-lib-v12-45nm/{row['cell']}/spec.yaml")
    res = PREP.smoke_run(list(row["tokens"]), sp, 1, 2500, "bptm45", profile="rl-v1")
    out["unstable_b_Ec_R_VIN1_VOUT1"] = {
        "cell": row["cell"], "lib_mode_feasible": row["result"]["feasible"],
        "rlv1_feasible": res["feasible"], "rlv1_spec_feasible": res.get("spec_feasible"),
        "rlv1_mu_min_wide": res.get("mu_min_wide"), "pass": res["feasible"] is False}
    # ---- 3c
    unstable = {r["jid"] for r in rows if r.get("res") and r["res"].get("spec_feasible")
                and not r["res"].get("stab_wide_ok")}
    leaked = []
    for l in open(f"{RD}/candidates.jsonl"):
        c = json.loads(l)
        if c.get("jid") in unstable and c.get("feasible"):
            leaked.append(c["cid"])
    out["unstable_c_not_planted"] = {"spec_feasible_but_wide_unstable_rows": len(unstable),
                                     "marked_feasible": leaked, "pass": not leaked}
    out["all_pass"] = all(v.get("pass") for v in out.values() if isinstance(v, dict))
    json.dump(out, open(f"{HERE}/smoke/smoke_checks.json", "w"), indent=1, default=repr)
    print(json.dumps(out, indent=1, default=repr))


if __name__ == "__main__":
    main()

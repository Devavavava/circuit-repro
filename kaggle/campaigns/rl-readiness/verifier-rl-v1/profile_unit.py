"""Unit tests of the VERIFIER_PROFILE switch (no full sizing).  usage: profile_unit.py <out.json>

  1. resolve_verifier: rl-v1 flag set; env override (set -> wins, even "0");
     kwarg beats env; profile="" forces none; unknown profile raises.
  2. rl_v1_spec: the exact YAML diff vs the library spec for every bench-v1.2
     cell; rl_v1_issues == [] on the output and non-empty on the source.
  3. End-to-end pre-sizing reject under the profile (0 evals, fast): the R4
     wb_tank_out mutant (3 inductors > rl-v1 max 2) -> infeasible, reason,
     result["verifier"] recorded, os.environ restored after the call.
"""
import sys, os, json, copy
REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop"):
    sys.path.insert(0, p)
import yaml                                                    # noqa: E402
import bench_anchor_prep as PREP                               # noqa: E402
import proposal as P                                           # noqa: E402
from spec import Spec                                          # noqa: E402

LIB = REPO + "/kaggle/editcap-lib-v12-45nm"
R4 = REPO + "/kaggle/campaigns/rl-readiness/R4/"


def main(outp):
    for k in PREP.VERIFIER_FLAGS + ("VERIFIER_PROFILE",):
        os.environ.pop(k, None)
    t = {}
    t["none"] = PREP.resolve_verifier()
    t["kwarg_rl_v1"] = PREP.resolve_verifier("rl-v1")
    os.environ["VERIFIER_PROFILE"] = "rl-v1"
    t["env_rl_v1"] = PREP.resolve_verifier()
    t["env_rl_v1_kwarg_empty"] = PREP.resolve_verifier("")
    os.environ["VERIFY_INERT_COUNT"] = "0"
    os.environ["VERIFY_ROBUST"] = "10"
    t["env_rl_v1_override_inert0_robust10"] = PREP.resolve_verifier()
    for k in ("VERIFY_INERT_COUNT", "VERIFY_ROBUST", "VERIFIER_PROFILE"):
        os.environ.pop(k)
    try:
        PREP.resolve_verifier("rl-v9")
        t["unknown_raises"] = False
    except ValueError:
        t["unknown_raises"] = True
    checks = {
        "none_is_empty": t["none"] == (None, {}, []),
        "rl_v1_flags_exact": t["kwarg_rl_v1"][1] == {
            "STAB_WIDE_INLOOP": "1", "STAB_WIDE_WINDOW": "1e7,5e10,1001",
            "VERIFY_TOPO_LIMITS": "1", "VERIFY_STRUCT": "1", "VERIFY_FINITE": "1",
            "VERIFY_INERT_COUNT": "1"},
        "env_equals_kwarg": t["env_rl_v1"] == t["kwarg_rl_v1"],
        "kwarg_empty_forces_none": t["env_rl_v1_kwarg_empty"] == (None, {}, []),
        "override_wins": (t["env_rl_v1_override_inert0_robust10"][1]["VERIFY_INERT_COUNT"] == "0"
                          and t["env_rl_v1_override_inert0_robust10"][1]["VERIFY_ROBUST"] == "10"
                          and t["env_rl_v1_override_inert0_robust10"][2] == ["VERIFY_INERT_COUNT"]),
        "unknown_raises": t["unknown_raises"],
    }
    od = os.path.join(os.environ.get("TMPDIR", "/tmp"), "specs", str(os.getpid()))
    specs = {}
    for c in sorted(d for d in os.listdir(LIB) if d.startswith("v12-")):
        src = f"{LIB}/{c}/spec.yaml"
        out = PREP.rl_v1_spec(src, out_dir=od)
        a, b = yaml.safe_load(open(src)), yaml.safe_load(open(out))
        diff = {}
        for sect in ("constraints", "topology"):
            for k in set(a.get(sect, {})) | set(b.get(sect, {})):
                if a[sect].get(k) != b[sect].get(k):
                    diff[f"{sect}.{k}"] = [a[sect].get(k), b[sect].get(k)]
        oa = [o["metric"] for o in a.get("objectives", [])]
        ob = [o["metric"] for o in b.get("objectives", [])]
        if oa != ob:
            diff["objectives"] = [oa, ob]
        rest_same = all(a.get(k) == b.get(k) for k in set(a) | set(b)
                        if k not in ("constraints", "topology", "objectives"))
        specs[c] = {"diff": diff, "rest_identical": rest_same,
                    "issues_src": PREP.rl_v1_issues(Spec.load(src)),
                    "issues_out": PREP.rl_v1_issues(Spec.load(out))}
    checks["all_specs_rl_v1_form"] = all(not s["issues_out"] and s["rest_identical"]
                                         for s in specs.values())
    tok = P.round_trip(json.load(open(R4 + "mutations.json"))["wb_tank_out"])["tokens"]
    before = dict(os.environ)
    r = PREP.smoke_run(tok, PREP.rl_v1_spec(f"{LIB}/v12-wb-s11n10-g10-b0824/spec.yaml",
                                            out_dir=od), 1, 2500, "bptm45", profile="rl-v1")
    checks["reject_topo_infeasible"] = (r["feasible"] is False and r["n_evals"] == 0
                                        and "max_inductors" in r["infeasible_reason"])
    checks["reject_has_verifier"] = r.get("verifier", {}).get("profile") == "rl-v1"
    checks["env_restored"] = dict(os.environ) == before
    res = {"checks": checks, "all_ok": all(checks.values()),
           "resolve": {k: list(v) if isinstance(v, tuple) else v for k, v in t.items()},
           "rl_v1_specs": specs, "reject_result": r}
    json.dump(res, open(outp, "w"), indent=1, default=repr)
    print(json.dumps(checks, indent=1), "all_ok=", res["all_ok"])


if __name__ == "__main__":
    main(sys.argv[1])

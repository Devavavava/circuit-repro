"""(a) Regression: no profile -> byte-identical vs RECORDED rows; profile via env
== profile via kwarg.   usage: reg_check.py <rawdir> <out.json>

Compared with json.dumps(sort_keys=True). Rows:
  E-a  nb-f15-g12 template d0 s1 and wb-s11n10-g10-b0824 template d0 s1 (lib spec;
       the wb one gates nf_db -> exercises extract.measure_nf): E-a stored
       metrics/feasible/n_evals/n_sim_fail/sim_error/winner_reeval_ungated.
  E-c  wb-s11n10-g10-b0530 ec:72945e70a2a1:131 s1 (lib): the keys E-c stored.
  stability-gate nb-f15-g14 template stab s1 (gate only): FULL result dict.
  S-1  wb-s11n10-g10-b0824 template inloop s1 (STAB_WIDE_INLOOP=1 set -> a flag is
       set, so result["verifier"] is ADDED): full dict minus stab_inloop.wide_secs
       and minus the new `verifier` key (reported separately).
  profile env vs kwarg: nb-f15-g16 template rl-v1 s1, full dict minus wide_secs.
"""
import sys, os, json
AUD = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/bench-v12-audit/"


def norm(r, drop=()):
    r = json.loads(json.dumps(r, default=repr))
    if isinstance(r, dict):
        if isinstance(r.get("stab_inloop"), dict):
            r["stab_inloop"].pop("wide_secs", None)
        for k in drop:
            r.pop(k, None)
    return json.dumps(r, sort_keys=True)


def raw(rawdir, tag, cell, cand, mode, seed):
    fn = f"{rawdir}/{tag}__{cell}__{cand.replace(':', '_')}__{mode}__s{seed}.json"
    return json.load(open(fn)) if os.path.exists(fn) else None


def keys_same(new, old, keys):
    return {k: json.dumps(new.get(k), sort_keys=True) == json.dumps(old.get(k), sort_keys=True)
            for k in keys}


def main(rawdir, out):
    res = []
    ea = json.load(open(AUD + "E-a/results.json"))["rows"]
    for cell in ("v12-nb-f15-g12", "v12-wb-s11n10-g10-b0824"):
        old = [x for x in ea if x["cell"] == cell and x["cand"] == "template"
               and x["delta"] == 0.0 and x["seed"] == 1][0]
        new = raw(rawdir, "reg", cell, "template", "lib", 1)["result"]
        ks = ("metrics", "feasible", "n_evals", "n_sim_fail", "sim_error", "winner_reeval_ungated")
        same = keys_same(new, old, ks)
        res.append({"row": f"E-a {cell} template d0 s1 (lib, no profile)", "compared": list(ks),
                    "per_key": same, "identical": all(same.values()),
                    "verifier_key_present": "verifier" in new})
    ec = [json.loads(l) for l in open(AUD + "E-c/results.jsonl")
          if '"v12-wb-s11n10-g10-b0530"' in l and '"72945e70a2a1:131"' in l][0]
    new = raw(rawdir, "reg", "v12-wb-s11n10-g10-b0530", "ec:72945e70a2a1:131", "lib", 1)["result"]
    nm = dict(new)
    nm["metrics"] = {k: v for k, v in new["metrics"].items() if k in ec["metrics"]}
    ks = ("metrics", "feasible", "n_evals", "n_sim_fail", "sim_error")
    same = keys_same(nm, ec, ks)
    res.append({"row": "E-c wb-s11n10-g10-b0530 ec:72945e70a2a1:131 s1 (lib, no profile)",
                "compared": list(ks) + ["(metrics restricted to the keys E-c stored)"],
                "metrics_keys_not_recorded_by_E-c": sorted(set(new["metrics"]) - set(ec["metrics"])),
                "per_key": same, "identical": all(same.values()),
                "verifier_key_present": "verifier" in new})
    sg = [x for x in json.load(open(AUD + "stability-gate/results.json"))["rows"]
          if x["cell"] == "v12-nb-f15-g14" and x["cand"] == "template"
          and x["specmode"] == "stab" and x["seed"] == 1][0]
    new = raw(rawdir, "reg", "v12-nb-f15-g14", "template", "gate", 1)["result"]
    res.append({"row": "stability-gate nb-f15-g14 template stab gate s1 (no profile)",
                "compared": "FULL result dict", "identical": norm(new) == norm(sg["result"]),
                "verifier_key_present": "verifier" in new,
                "keys_new_minus_old": sorted(set(new) - set(sg["result"])),
                "keys_old_minus_new": sorted(set(sg["result"]) - set(new))})
    s1 = [x for x in json.load(open(AUD + "S-1-stab-inloop/results.json"))["rows"]
          if x["cell"] == "v12-wb-s11n10-g10-b0824" and x["cand"] == "template"
          and x["mode"] == "inloop" and x["seed"] == 1 and x["exp"] != "regress"][0]
    new = raw(rawdir, "reg", "v12-wb-s11n10-g10-b0824", "template", "inloop", 1)["result"]
    res.append({"row": "S-1 wb-s11n10-g10-b0824 template inloop s1 (flag STAB_WIDE_INLOOP=1, no profile)",
                "compared": "full dict minus stab_inloop.wide_secs and the added `verifier` key",
                "identical": norm(new, ("verifier",)) == norm(s1["result"]),
                "keys_new_minus_old": sorted(set(new) - set(s1["result"])),
                "verifier": new.get("verifier")})
    a = raw(rawdir, "reg", "v12-nb-f15-g16", "template", "rlv1env", 1)
    b = raw(rawdir, "diff", "v12-nb-f15-g16", "template", "rlv1", 1)
    if a and b:
        res.append({"row": "rl-v1 via env VERIFIER_PROFILE vs via smoke_run(profile=) nb-f15-g16 template s1",
                    "compared": "full dict minus stab_inloop.wide_secs",
                    "identical": norm(a["result"]) == norm(b["result"]),
                    "verifier": a["result"].get("verifier")})
    json.dump(res, open(out, "w"), indent=1, default=repr)
    for x in res:
        print(x["identical"], x["row"])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

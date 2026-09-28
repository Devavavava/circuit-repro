"""Flags-off byte-identity of the (edited) smoke_run vs RECORDED rows, and the
guards' on/off behavior.  usage: regress_check.py <rawdir> <out.json>

Tag `reg`  = run after the topology-limit + post-hoc guard edits;
tag `reg2` = run after VERIFY_STRUCT + STAB_WIDE_WINDOW + VERIFY_BAND_METRICS were added;
tag `reg3` = the three recorded rows again on the FINAL committed code.
Compared with json.dumps(sort_keys=True) of the complete result dict; the only
key excluded is stab_inloop.wide_secs (wall-clock timing). E-c's recorder kept
only metrics/feasible/n_evals/n_sim_fail/sim_error and dropped the list-valued
metrics["stab_band"], so that row is compared on those keys.
"""
import sys, os, json
AUD = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/bench-v12-audit/"
GUARD_KEYS = ("topo_limits_ok", "topo_limits", "structural_degeneracy")


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


def main(rawdir, out):
    res = []
    ec = [json.loads(l) for l in open(AUD + "E-c/results.jsonl")
          if '"v12-wb-s11n10-g10-b0530"' in l and '"72945e70a2a1:131"' in l][0]
    sg = [x for x in json.load(open(AUD + "stability-gate/results.json"))["rows"]
          if x["cell"] == "v12-nb-f15-g14" and x["cand"] == "template"
          and x["specmode"] == "stab" and x["seed"] == 1][0]
    s1 = json.load(open(AUD + "S-1-stab-inloop/results.json"))["rows"]
    for tag in ("reg", "reg2", "reg3"):
        r = raw(rawdir, tag, "v12-wb-s11n10-g10-b0530", "ec:72945e70a2a1:131", "lib", 1)
        if r:
            rr = dict(r["result"])
            dropped = sorted(set(rr["metrics"]) - set(ec["metrics"]))
            rr["metrics"] = {k: v for k, v in rr["metrics"].items() if k in ec["metrics"]}
            same = all(json.dumps(rr[k], sort_keys=True) == json.dumps(ec[k], sort_keys=True)
                       for k in ("metrics", "feasible", "n_evals", "n_sim_fail", "sim_error"))
            res.append({"tag": tag, "row": "E-c lib wb-s11n10-g10-b0530 add L n1-n5 s1",
                        "compared": "metrics,feasible,n_evals,n_sim_fail,sim_error (all E-c keeps)",
                        "metrics_keys_not_recorded_by_E-c": dropped, "identical": same})
        r = raw(rawdir, tag, "v12-nb-f15-g14", "template", "gate", 1)
        if r:
            res.append({"tag": tag, "row": "stability-gate nb-f15-g14 template stab gate s1",
                        "compared": "full result dict",
                        "identical": norm(r["result"]) == norm(sg["result"])})
    for f in sorted(os.listdir(rawdir)):
        if not f.startswith(("s1__", "reg__", "reg2__", "reg3__")) or "__inloop__" not in f:
            continue
        r = json.load(open(os.path.join(rawdir, f)))
        m = [x for x in s1 if x["cell"] == r["cell"] and x["cand"] == r["cand"]
             and x["mode"] == "inloop" and x["seed"] == r["seed"] and x["exp"] != "regress"]
        if m:
            res.append({"tag": r["tag"],
                        "row": f"S-1 {r['cell']} {r['cand']} inloop s{r['seed']}",
                        "compared": "full result dict minus stab_inloop.wide_secs",
                        "identical": norm(r["result"]) == norm(m[0]["result"])})
    off = raw(rawdir, "nb", "v12-nb-f15-g16", "template", "inloop", 1)
    for tag, mode in (("reg", "topo"), ("reg2", "struct")):
        on = raw(rawdir, tag, "v12-nb-f15-g16", "template", mode, 1)
        if on and off:
            res.append({"tag": tag, "row": f"guard {mode} ON, clean nb-f15-g16 template s1 vs flags-off",
                        "compared": "full dict minus guard keys and wide_secs",
                        "identical": norm(on["result"], GUARD_KEYS) == norm(off["result"]),
                        "added": {k: on["result"].get(k) for k in GUARD_KEYS if k in on["result"]}})
    for tag, cell, cand, mode, what in (
            ("reg", "v12-wb-s11n10-g10-b0824", "template", "topo", "guard topo ON, wb template (2 L > max 1)"),
            ("reg2", "v12-nb-f15-g16", "net:nb_dead_mos", "struct", "guard struct ON, dead MOS mutant"),
            ("reg2", "v12-nb-f15-g16", "template", "all", "ALL guards ON, nb template"),
            ("reg2", "v12-nb-f15-g16", "net:nb_bleeder", "all", "ALL guards ON, bleeder-R mutant")):
        on = raw(rawdir, tag, cell, cand, mode, 1)
        if on:
            rr = on["result"]
            res.append({"tag": tag, "row": what, "feasible": rr.get("feasible"),
                        "infeasible_reason": rr.get("infeasible_reason"),
                        "n_evals": rr.get("n_evals"), "secs": on["secs"],
                        "extra": {k: rr.get(k) for k in ("nf_band_max_db", "inert_devices",
                                                         "robust_frac", "nonfinite_metrics",
                                                         "structural_degeneracy") if k in rr}})
    json.dump(res, open(out, "w"), indent=1, default=repr)
    for x in res:
        print(x["tag"], x["row"], x.get("identical", (x.get("feasible"), x.get("infeasible_reason"))))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

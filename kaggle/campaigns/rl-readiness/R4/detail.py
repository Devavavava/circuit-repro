"""Detail numbers for the README (band excesses, window failures).
usage: detail.py <out.json>"""
import sys, os, json, statistics as st
import yaml
HERE = os.path.dirname(os.path.abspath(__file__))
LIB = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/editcap-lib-v12-45nm"
P = json.load(open(HERE + "/post.json"))["designs"]
out = {"nb_s11_band_excess_db": [], "nb_nf_band_excess_db": [], "wb_nf_band_excess_db": [],
       "win_window_failures": {}, "inert_by_kind": {}}
for d in P:
    if d["role"] != "win" or d["mode"] != "inloop" or d["tag"] not in ("s1", "nb", "ed"):
        continue
    c = yaml.safe_load(open(f"{LIB}/{d['cell']}/spec.yaml"))["constraints"]
    m = d["metrics"]
    if "-nb-" in d["cell"]:
        out["nb_s11_band_excess_db"].append(round(m["s11_max_db"] - c["s11_db"]["max"], 3))
        out["nb_nf_band_excess_db"].append(round(d["nf_band_max_db"] - c["nf_db"]["max"], 3))
    else:
        out["wb_nf_band_excess_db"].append(round(d["nf_band_max_db"] - c["nf_db"]["max"], 3))
    bad = {k: [round(v["mu_min"], 5), v["argmin_hz"]] for k, v in d["windows"].items()
           if v and v["mu_min"] < 1}
    if bad:
        out["win_window_failures"][d["id"]] = bad
    for p in d["inert_passives"]:
        k = p[1]
        out["inert_by_kind"][k] = out["inert_by_kind"].get(k, 0) + 1
for k in ("nb_s11_band_excess_db", "nb_nf_band_excess_db", "wb_nf_band_excess_db"):
    v = sorted(out[k])
    out[k] = {"n": len(v), "median": st.median(v), "min": v[0], "max": v[-1],
              "n_positive": sum(1 for x in v if x > 0)}
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(json.dumps(out, indent=1))

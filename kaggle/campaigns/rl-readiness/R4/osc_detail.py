"""Which designs oscillate (600-ns confirmed) and their wide-window mu; also the
long-run amplitudes. usage: osc_detail.py <out.json>"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
TL = json.load(open(HERE + "/tran_long.json"))
P = {d["id"]: d for d in json.load(open(HERE + "/post.json"))["designs"]}
out = []
for k, v in TL.items():
    if v["long_verdict"] != "oscillates":
        continue
    d = P[v["id"]]
    w = {n: (round(x["mu_min"], 4), x["argmin_hz"], x["unstable_span_hz"])
         for n, x in d["windows"].items() if x}
    out.append({"id": v["id"], "term": v["term"], "role": v["role"], "tag": d["tag"],
                "late_pp_v": v["amp"].get("lout"), "idd0": v["amp"].get("idd0"),
                "iddl": v["amp"].get("iddl"), "windows": w})
json.dump(out, open(sys.argv[1], "w"), indent=1)
for o in out:
    print(o["role"], o["id"], o["term"], o["late_pp_v"], o["windows"].get("w0p01_50"))

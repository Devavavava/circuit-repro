"""regress_check.py <rawdir> <out.json>: flags-off byte-identity.

Every S-1 run with mode=gate (STAB_WIDE_INLOOP unset) -- and every lib-spec run
(gate off, so the in-loop flag must be inert) -- is compared to the row the
stability-gate campaign recorded for the same (cell, cand, specmode, seed):
json.dumps of the COMPLETE smoke_run result dict must be equal."""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
REC = os.path.join(HERE, "..", "stability-gate", "results.json")

raw, out = sys.argv[1], sys.argv[2]
rec = {}
for r in json.load(open(REC))["rows"]:
    rec.setdefault((r["cell"], r["cand"], r["specmode"], r["seed"]), r)
rows = []
for f in sorted(os.listdir(raw)):
    if not f.endswith(".json"):
        continue
    r = json.load(open(os.path.join(raw, f)))
    if r["mode"] != "gate" and r["specmode"] != "lib":
        continue
    k = (r["cell"], r["cand"], r["specmode"], r["seed"])
    o = rec.get(k)
    if o is None:
        continue
    a = json.dumps(o.get("result"), sort_keys=True, default=repr)
    b = json.dumps(r.get("result"), sort_keys=True, default=repr)
    rows.append({"exp": r["exp"], "cell": r["cell"], "cand": r["cand"],
                 "specmode": r["specmode"], "mode": r["mode"], "seed": r["seed"],
                 "recorded_exp": o["exp"], "identical_full_result": a == b,
                 "feasible_new_rec": [r["feasible"], o["feasible"]]})
json.dump({"n": len(rows), "n_identical": sum(x["identical_full_result"] for x in rows),
           "rows": rows}, open(out, "w"), indent=1)
for x in rows:
    print(x["exp"], x["cell"], x["cand"], x["specmode"], x["mode"], x["seed"],
          "identical=", x["identical_full_result"])
print("identical", sum(x["identical_full_result"] for x in rows), "/", len(rows))

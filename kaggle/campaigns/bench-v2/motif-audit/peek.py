"""Inspect accepted bench-v2 cells (read-only)."""
import json, sys
RUN = "kaggle/campaigns/bench-v2/run/"
rows = [json.loads(l) for l in open(RUN + "cells.jsonl")]
acc = [r for r in rows if r.get("status") == "accepted"]
print("n accepted:", len(acc))
for r in acc:
    sc = " ; ".join(f"{s['op']}:{s.get('t','')}:{s.get('name','')}:{','.join(s.get('nets',[]))}" for s in r["script"])
    print(r["name"], r["anchor"], r.get("era_tag"), r.get("selectable"), r["cls"], "|", sc)
p = json.load(open(RUN + "progress.json"))
b = p.get("bench", {})
print(json.dumps({k: v for k, v in b.items()}, indent=0)[:2500])
if len(sys.argv) > 1:
    for r in acc:
        if r["name"] == sys.argv[1]:
            print(json.dumps({k: v for k, v in r.items() if k != "netlist"}, indent=1))
            print(r["netlist"])

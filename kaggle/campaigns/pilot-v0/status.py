#!/usr/bin/env python
"""one-screen status of a pilot-v0 run dir: status.py [run|smoke]"""
import json
import sys
from collections import Counter

HERE = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/pilot-v0"
rd = f"{HERE}/{sys.argv[1] if len(sys.argv) > 1 else 'run'}"
p = json.load(open(f"{rd}/progress.json"))
print(p["ts"], "status", p["status"], "pid", p["pid"], "load1", p["load1"], "limit", p["proc_limit"],
      "running", p["running"], "(P0", str(p["running_p0"]) + ")", "pending", p["pending"])
print("calls", p["calls"])
P0 = p["P0"]
print("P0 done", P0["done"], "/", P0["n_tasks"], "tiers", P0["tiers_so_far"], "stage", P0["stage"],
      "built", P0["built"], "eta_h", P0["eta_h"], "->", P0["eta_finish"])
if P0["in_f2"]:
    print("  in F2:", P0["in_f2"])
b = p["P0b"]
print("P0b gen", b["gen"], "planted", b["new_planted"], b["new_planted_per_point"])
print("    tasks", b["train_status"], "ok", b["ok_training_side"], "/", b["target_ok"],
      "est examples", b["est_examples"], "/", b["target_examples_est"], "fence", b["fence"])
print("ETA all", p["eta"])
kinds = Counter()
try:
    for ln in open(f"{rd}/results.jsonl"):
        r = json.loads(ln)
        kinds[(r["kind"], bool(r.get("inproc_reject")))] += 1
except FileNotFoundError:
    pass
print("rows", dict(kinds))

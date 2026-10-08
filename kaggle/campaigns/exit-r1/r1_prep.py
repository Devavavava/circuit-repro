#!/usr/bin/env python
"""exit-r1 step-1 preparation (local, read-only on pilot-v0).

  r1_prep.py tasks
      gen/TASKS.json: every training-side task that has a pilot-v0 prompt (= every task of
      pilot-v0/data/train-all.jsonl; the 677 ok training-side tasks minus the 36 for which
      pilot-v0 built no example/prompt), held-out families asserted absent, in a seeded
      random order (ORDER_SEED) -- the generation kernels run tasks in this order (task-major),
      so a deadline cut is a uniformly random subsample of tasks (the pre-reg's fallback).
      Per task: family, band_type, difficulty label, sha of the prompt messages.
"""
import hashlib
import json
import os
import random
import sys
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PV0 = os.path.join(REPO, "kaggle", "campaigns", "pilot-v0")
DATA = os.path.join(PV0, "data", "train-all.jsonl")
ORDER_SEED = 20261008
sys.path.insert(0, HERE)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def cmd_tasks():
    import r1_gen
    split = json.load(open(os.path.join(PV0, "eval", "split.json")))
    held = set(split["heldout_families"])
    tasks = OrderedDict()
    for ln in open(DATA):
        if not ln.strip():
            continue
        e = json.loads(ln)
        assert e["family"] not in held and e["task"] not in set(split["heldout_tasks"]), e["id"]
        t = tasks.setdefault(e["task"], {"task": e["task"], "family": e["family"], "band_type": e["band_type"],
                                         "difficulty": e["difficulty"], "task_origin": e["task_origin"],
                                         "messages_sha": r1_gen.msg_sha(e["messages"]), "n_examples": 0})
        assert t["messages_sha"] == r1_gen.msg_sha(e["messages"]), e["id"]
        t["n_examples"] += 1
    names = sorted(tasks)
    random.Random(ORDER_SEED).shuffle(names)
    tt = [json.loads(l) for l in open(os.path.join(PV0, "run", "train_tasks.jsonl")) if l.strip()] \
        if os.path.exists(os.path.join(PV0, "run", "train_tasks.jsonl")) else []
    ok = {r["name"] for r in tt if r.get("status") == "ok"}
    rec = OrderedDict(
        prereg="kaggle/PREREG-EXIT-R1.md (573a21a89) step 1",
        data="kaggle/campaigns/pilot-v0/data/train-all.jsonl", data_sha256=sha256_file(DATA),
        heldout_families_excluded=sorted(held), order_seed=ORDER_SEED, n_tasks=len(names),
        n_ok_training_side=len(ok) or None,
        ok_without_prompt=sorted(ok - set(names)) if ok else None,
        by_family=dict(Counter(tasks[n]["family"] for n in names)),
        by_band_type=dict(Counter(tasks[n]["band_type"] for n in names)),
        by_difficulty=dict(Counter(tasks[n]["difficulty"] for n in names)),
        by_origin=dict(Counter(tasks[n]["task_origin"] for n in names)),
        tasks=[tasks[n] for n in names])
    os.makedirs(os.path.join(HERE, "gen"), exist_ok=True)
    json.dump(rec, open(os.path.join(HERE, "gen", "TASKS.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in rec.items() if k not in ("tasks", "ok_without_prompt")}, indent=1))


if __name__ == "__main__":
    {"tasks": cmd_tasks}[sys.argv[1]]()

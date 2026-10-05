#!/usr/bin/env python
"""pilot-v0 P1 data plumbing (local; reads pilot-v0/data/ read-only).

  build_sft.py rat-input --data DIR [--out DIR] [--shards 2] [--subsets FILE]
        the examples of the largest nested subset (normally "1000"; it contains 100 and
        300), priority order 100 -> 300\\100 -> 1000\\300, dealt round-robin into
        <out>/rat-input-<a|b>.jsonl (one rationalize kernel per shard) + INPUT.json.
  build_sft.py sft --data DIR --rat DIR[,DIR..] [--out DIR] [--subsets FILE]
        for each example the FIRST kept trace (lowest attempt) of the rationalize
        kernels, LOCALLY re-verified: proposal.round_trip(trace netlist) token hash ==
        the example's verified target_tok, reasoning re-derived from the raw content and
        identical, 1..512 tokens (server count), no leak phrase; fence re-checked (no
        held-out family / task / strict cell, target WL/token hash not in pv0's fence
        set). Writes <out>/sft-<N>.jsonl = the nested subset N filtered to kept traces
        (same order), rows {id, task, messages, think, answer}; answer = the example's
        verified `completion` (fenced netlist). + STATS.json.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
PV0 = os.path.dirname(HERE)
sys.path.insert(0, PV0)
sys.path.insert(0, HERE)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load(data, subsets_file=None):
    exs = OrderedDict()
    for ln in open(os.path.join(data, "train-all.jsonl")):
        if ln.strip():
            e = json.loads(ln)
            exs[e["id"]] = e
    sub = json.load(open(subsets_file or os.path.join(data, "subsets.json")))["subsets"]
    sizes = sorted(sub, key=int)
    for a, b in zip(sizes[:-1], sizes[1:]):
        assert set(sub[a]) <= set(sub[b]), (a, b)
    return exs, sub, sizes


def cmd_rat_input(a):
    exs, sub, sizes = load(a.data, a.subsets)
    order, seen = [], set()
    for n in sizes:
        for i in sub[n]:
            if i not in seen:
                seen.add(i)
                order.append(i)
    os.makedirs(a.out, exist_ok=True)
    names = "abcdefgh"[: a.shards]
    fhs = {s: open(os.path.join(a.out, "rat-input-%s.jsonl" % s), "w") for s in names}
    cnt = Counter()
    for k, i in enumerate(order):
        e = exs[i]
        s = names[k % a.shards]
        fhs[s].write(json.dumps({k2: e[k2] for k2 in ("id", "task", "family", "band_type", "difficulty",
                                                      "source", "messages", "target_netlist",
                                                      "completion", "target_tok", "target_wl")}) + "\n")
        cnt[s] += 1
    for fh in fhs.values():
        fh.close()
    rec = OrderedDict(data=os.path.relpath(os.path.abspath(a.data), os.path.dirname(os.path.dirname(os.path.dirname(PV0)))),
                      train_all_sha256=sha256_file(os.path.join(a.data, "train-all.jsonl")),
                      subsets_file=a.subsets or "subsets.json", subset_sizes={n: len(sub[n]) for n in sizes},
                      n_examples_all=len(exs), n_to_rationalize=len(order), shards=dict(cnt),
                      order="priority 100 -> 300\\100 -> 1000\\300, round-robin over shards")
    json.dump(rec, open(os.path.join(a.out, "INPUT.json"), "w"), indent=1)
    print(json.dumps(rec))


def cmd_sft(a):
    import pv0
    B = pv0.B
    exs, sub, sizes = load(a.data, a.subsets)
    split = pv0.load_split()
    held_fam = set(split["heldout_families"])
    held_tasks = set(split["heldout_tasks"]) | set(pv0.STRICT)
    # fence sets exactly as pv0 (bench-v2 planted cells any status + held-out witnesses)
    if not a.no_runner_fence:
        import build_prompts as BP
        R = BP.runner()
        fence_wl, fence_tok = R.fence_wl, R.fence_tok
    else:                                   # mock test only
        fence_wl, fence_tok = set(), set()
    # import order: the bv2/pv0 module paths (Runner) first, then editcap_run (via p1_gen),
    # whose sys.path inserts must not shadow already-imported repo modules
    import proposal as P
    import p1_gen as G
    rows = []
    for d in a.rat.split(","):
        p = os.path.join(d, "rationalize.jsonl")
        for ln in open(p):
            if ln.strip():
                r = json.loads(ln)
                r["_file"] = p
                rows.append(r)
    by = {}
    for r in sorted(rows, key=lambda r: (r["id"], r["attempt"])):
        by.setdefault(r["id"], []).append(r)
    kept, why = OrderedDict(), Counter()
    att_hist, rtoks = Counter(), []
    for i in sub[sizes[-1]]:
        e = exs[i]
        assert e["family"] not in held_fam and e["task"] not in held_tasks, i
        assert e["target_wl"] not in fence_wl and e["target_tok"] not in fence_tok, i
        rs = by.get(i) or []
        if not rs:
            why["not_rationalized"] += 1
            continue
        ok = [r for r in rs if r.get("ok")]
        if not ok:
            why["no_kept_trace:" + (rs[-1].get("why") or "?")] += 1
            continue
        r = ok[0]
        # local re-verification of the kernel's verdict
        content = re.sub(r"<think>.*?</think>", "", r["content"], flags=re.S).strip()
        blocks = G.ER._parse_edits_from_raw(content)
        reasoning = content[:content.find("```")].strip()
        info = P.round_trip(blocks[0]) if len(blocks) == 1 else {"ok": False}
        good = (len(blocks) == 1 and info["ok"] and B.tokhash(info["tokens"]) == e["target_tok"]
                and reasoning == r["reasoning"] and reasoning
                and 0 < (r.get("reasoning_tokens") or 0) <= G.RAT_MAX_REASONING_TOKENS
                and not G.LEAK_RE.search(reasoning))
        if not good:
            why["local_reverify_failed"] += 1
            continue
        att_hist[r["attempt"]] += 1
        rtoks.append(r["reasoning_tokens"])
        kept[i] = {"id": i, "task": e["task"], "messages": e["messages"], "think": reasoning,
                   "answer": e["completion"]}
    os.makedirs(a.out, exist_ok=True)
    stats = OrderedDict(data_train_all_sha256=sha256_file(os.path.join(a.data, "train-all.jsonl")),
                        rat_files=sorted({os.path.relpath(r["_file"], pv0.REPO) for r in rows}),
                        n_rat_calls=len(rows), kept_by_attempt=dict(att_hist),
                        dropped=dict(why), reasoning_tokens=None, subsets={})
    if rtoks:
        rs = sorted(rtoks)
        stats["reasoning_tokens"] = {"mean": round(sum(rs) / len(rs), 1), "median": rs[len(rs) // 2],
                                     "max": rs[-1], "min": rs[0]}
    for n in sizes:
        ids = [i for i in sub[n] if i in kept]
        p = os.path.join(a.out, "sft-%s.jsonl" % n)
        with open(p, "w") as fh:
            for i in ids:
                fh.write(json.dumps(kept[i]) + "\n")
        stats["subsets"][n] = {"n_subset": len(sub[n]), "n_kept": len(ids),
                               "n_tasks": len({kept[i]["task"] for i in ids}),
                               "by_stratum": dict(Counter("%s/%s" % (exs[i]["band_type"], exs[i]["difficulty"])
                                                          for i in ids)),
                               "sha256": sha256_file(p)}
    for x, y in zip(sizes[:-1], sizes[1:]):
        sx = {json.loads(l)["id"] for l in open(os.path.join(a.out, "sft-%s.jsonl" % x))}
        sy = {json.loads(l)["id"] for l in open(os.path.join(a.out, "sft-%s.jsonl" % y))}
        assert sx <= sy, (x, y)
    json.dump(stats, open(os.path.join(a.out, "STATS.json"), "w"), indent=1)
    print(json.dumps(stats["subsets"]), json.dumps(stats["dropped"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["rat-input", "sft"])
    ap.add_argument("--data", required=True)
    ap.add_argument("--subsets", default=None)
    ap.add_argument("--rat", default="")
    ap.add_argument("--out", default=None)
    ap.add_argument("--shards", type=int, default=2)
    ap.add_argument("--no-runner-fence", action="store_true")
    a = ap.parse_args()
    if a.cmd == "rat-input":
        a.out = a.out or os.path.join(HERE, "rat")
        cmd_rat_input(a)
    else:
        a.out = a.out or os.path.join(HERE, "sft-data")
        cmd_sft(a)

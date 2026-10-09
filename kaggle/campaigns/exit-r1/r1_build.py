#!/usr/bin/env python
"""exit-r1 step 3: round-1 SFT data (kaggle/PREREG-EXIT-R1.md step 3). Local, read-only on
pilot-v0 / pilot-v1 / verify outputs.

  r1_build.py build [--policies sft1000,sft300] [--out DIR]

Pool
  * pilot-v0's 1,013 verified examples (data/train-all.jsonl) with their existing rationale:
    the first kept trace of pilot-v0's rat-a/rat-b and pilot-v1's rat-mix, locally
    re-verified exactly as pilot-v0 build_sft.py (token hash == target_tok, reasoning ==
    recorded, 1..512 tokens, no leak phrase). An example with no kept trace is unavailable.
  * new positives: every generated completion (verify/<policy>/completions.jsonl) whose
    valid edit is feasible under rl-v1.2-rl at seed 1 AND seed 2 (verify/verify.jsonl),
    whose trace passes pilot-v0's P1 filters (D-Q2/D-Q3): exactly one fenced netlist block,
    reasoning (= its think text) 1..512 tokens (llama-server /tokenize count, recorded in the
    kernel), no leak phrase; plus: the think closed by itself (no budget closer), not recovered
    from the reasoning, no LLM error. Target = the model's own completion: think = its
    reasoning, answer = its verified netlist in one fenced ```netlist block (prose dropped, D-Q2).
  * dedupe by (task, target WL): pilot-v0 examples first, then new positives in (policy order,
    task, sample) order.
Mix (fixed seed MIX_SEED)
  * strata = band type x difficulty label; within a stratum the examples are shuffled (seed).
  * every non-anchor target WL <= 3 examples (global; strata in sorted order).
  * anchor-target answers (target WL == a library anchor a1..a5) <= 40 % of the mix.
  * size N = min(1200, |non-anchor| + min(|anchor pool|, floor(2/3 |non-anchor|))); anchors
    A = min(|anchor pool|, floor(0.4 N)), non-anchor N - A; each part allocated over strata
    proportionally to its pool (largest remainder), taken in stratum order.
  * fence re-check (pilot-v0's sets): no held-out family / task / strict cell; target WL and
    token hash not in pv0's fence (bench-v2 planted cells any status + held-out witnesses).
Outputs: <out>/sft-r1.jsonl rows {id, task, messages, think, answer} (sft_train.py format),
<out>/MIX.json (composition), <out>/ids.json.
"""
import argparse
import hashlib
import json
import math
import os
import random
import re
import sys
from collections import Counter, OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PV0 = os.path.join(REPO, "kaggle", "campaigns", "pilot-v0")
P1 = os.path.join(PV0, "P1")
PV1 = os.path.join(REPO, "kaggle", "campaigns", "pilot-v1")
DATA = os.path.join(PV0, "data", "train-all.jsonl")
RAT_DIRS = [os.path.join(P1, "kernels", "rat-a", "rat"), os.path.join(P1, "kernels", "rat-b", "rat"),
            os.path.join(PV1, "kernels", "rat-mix", "rat")]
VD = os.environ.get("R1_VERIFY_DIR") or os.path.join(HERE, "verify")
MIX_SEED = 20261008
WL_CAP = 3
ANCHOR_FRAC = 0.40
N_MAX = 1200
sys.path.insert(0, P1)
sys.path.insert(0, PV0)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rj(p):
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def largest_remainder(total, sizes):
    keys = sorted(sizes)
    N = sum(sizes.values())
    if not N or not total:
        return {k: 0 for k in keys}
    q = {k: total * sizes[k] / N for k in keys}
    al = {k: min(sizes[k], int(math.floor(q[k]))) for k in keys}
    for k in sorted(keys, key=lambda k: (-(q[k] - al[k]), k)):
        if sum(al.values()) >= total:
            break
        if al[k] < sizes[k]:
            al[k] += 1
    while sum(al.values()) < total:              # a stratum ran out: give the rest to others
        k = next(k for k in keys if al[k] < sizes[k])
        al[k] += 1
    return al


def pv0_traces(exs, G, P, B):
    """id -> rationale, pilot-v0 build_sft.py's local re-verification verbatim."""
    rows = []
    for d in RAT_DIRS:
        rows += rj(os.path.join(d, "rationalize.jsonl"))
    by = defaultdict(list)
    for r in sorted(rows, key=lambda r: (r["id"], r["attempt"])):
        by[r["id"]].append(r)
    kept, why = {}, Counter()
    for i, e in exs.items():
        ok = [r for r in by.get(i, []) if r.get("ok")]
        if not ok:
            why["not_rationalized" if not by.get(i) else "no_kept_trace"] += 1
            continue
        r = ok[0]
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
        kept[i] = reasoning
    return kept, why


def new_positives(policies, by_task_msgs, G, P, B, gen_dirs):
    ver = {(r["task"], r["key"], r["seed"]): r for r in rj(os.path.join(VD, "verify.jsonl"))}
    out, why = [], Counter()
    for pol in policies:
        for c in rj(os.path.join(VD, pol, "completions.jsonl")):
            if not c.get("valid"):
                why["invalid"] += 1
                continue
            r1, r2 = ver.get((c["task"], c["key"], 1)), ver.get((c["task"], c["key"], 2))
            if r1 is None:
                why["UNSIZED_seed1"] += 1
                continue
            if not r1.get("feasible"):
                why["infeasible_seed1"] += 1
                continue
            if r2 is None:
                why["UNSIZED_seed2"] += 1
                continue
            if not r2.get("feasible"):
                why["infeasible_seed2"] += 1
                continue
            why["positive"] += 1
            d = os.path.join(gen_dirs[pol], "s%d" % c["sample"], c["task"])
            raw = open(os.path.join(d, "raw_output.txt"), errors="replace").read()
            reasoning = open(os.path.join(d, "reasoning.txt"), errors="replace").read().strip()
            edit = open(os.path.join(d, "edit0.net"), errors="replace").read()
            blocks = G.ER._parse_edits_from_raw(raw)
            info = P.round_trip(edit)
            f = None
            if c.get("llm_error") or c.get("recovered_from_reasoning"):
                f = "recovered_or_error"
            elif c.get("think_stop") not in ("word", "eos") or not c.get("think_closed_naturally", True):
                f = "think_not_closed"
            elif len(blocks) != 1:
                f = "n_blocks=%d" % len(blocks)
            elif not info["ok"] or B.tokhash(info["tokens"]) != c["key"]:
                f = "round_trip_mismatch"
            elif not reasoning:
                f = "empty_reasoning"
            elif not (0 < (c.get("reasoning_tokens") or 0) <= G.RAT_MAX_REASONING_TOKENS):
                f = "reasoning_too_long"
            elif G.LEAK_RE.search(reasoning):
                f = "leak_phrase"
            if f:
                why["pos_filtered:" + f] += 1
                continue
            why["pos_kept"] += 1
            net = edit.rstrip("\n") + "\n"
            out.append({"id": "%s:r1:%s:s%d" % (c["task"], pol, c["sample"]), "task": c["task"],
                        "policy": pol, "sample": c["sample"], "messages": by_task_msgs[c["task"]],
                        "think": reasoning, "answer": "```netlist\n" + net + "```",
                        "target_wl": c["wl"], "target_tok": c["key"], "novel": bool(c.get("novel")),
                        "copy_own_target": bool(c.get("copy_own_target")), "anchor": c.get("anchor"),
                        "reasoning_tokens": c.get("reasoning_tokens"), "band_type": c["band_type"],
                        "difficulty": c["difficulty"], "family": c["family"],
                        "verification": {"profile": "rl-v1.2-rl", "seed1_jid": r1["jid"],
                                         "seed2_jid": r2["jid"], "feasible_seeds": [1, 2]}})
    return out, why


def cmd_build(a):
    import pv0
    B = pv0.B
    import build_prompts as BP
    R = BP.runner()
    fence_wl, fence_tok = R.fence_wl, R.fence_tok
    import proposal as P
    import p1_gen as G
    split = pv0.load_split()
    held_fam = set(split["heldout_families"])
    held_tasks = set(split["heldout_tasks"]) | set(pv0.STRICT)
    anch = B.anchor_data()
    anchor_wl = {A["wl"]: k for k, A in anch.items()}
    exs = OrderedDict((e["id"], e) for e in rj(DATA))
    msgs = {}
    for e in exs.values():
        msgs.setdefault(e["task"], e["messages"])
    traces, why_pv0 = pv0_traces(exs, G, P, B)
    policies = [p for p in a.policies.split(",") if p]
    gen_dirs = {p: os.path.join(HERE, "kernels", "gen-" + p, "gen") for p in policies}
    newp, why_new = new_positives(policies, msgs, G, P, B, gen_dirs)
    # ---- pool + dedupe by (task, target WL)
    pool, seen, dup = [], set(), Counter()
    for i, e in exs.items():
        if i not in traces:
            continue
        k = (e["task"], e["target_wl"])
        assert k not in seen
        seen.add(k)
        pool.append({"id": i, "task": e["task"], "band_type": e["band_type"], "difficulty": e["difficulty"],
                     "family": e["family"], "target_wl": e["target_wl"], "target_tok": e["target_tok"],
                     "anchor": anchor_wl.get(e["target_wl"]), "origin": "pilot-v0",
                     "source": e["source"].split(":")[0], "novel": False,
                     "row": {"id": i, "task": e["task"], "messages": e["messages"], "think": traces[i],
                             "answer": e["completion"]}})
    pol_rank = {p: n for n, p in enumerate(policies)}
    for x in sorted(newp, key=lambda x: (pol_rank[x["policy"]], x["task"], x["sample"])):
        k = (x["task"], x["target_wl"])
        if k in seen:
            dup["pilot-v0_or_earlier" if k in {(p["task"], p["target_wl"]) for p in pool if p["origin"] == "pilot-v0"}
                else "new_dup"] += 1
            continue
        seen.add(k)
        pool.append({"id": x["id"], "task": x["task"], "band_type": x["band_type"], "difficulty": x["difficulty"],
                     "family": x["family"], "target_wl": x["target_wl"], "target_tok": x["target_tok"],
                     "anchor": anchor_wl.get(x["target_wl"]), "origin": "self:" + x["policy"],
                     "source": "self", "novel": x["novel"], "reasoning_tokens": x["reasoning_tokens"],
                     "row": {"id": x["id"], "task": x["task"], "messages": x["messages"], "think": x["think"],
                             "answer": x["answer"]}})
    # ---- fence
    for p in pool:
        assert p["family"] not in held_fam and p["task"] not in held_tasks, p["id"]
        assert p["target_wl"] not in fence_wl and p["target_tok"] not in fence_tok, p["id"]
    # ---- mix
    rng = random.Random(MIX_SEED)
    strata = defaultdict(list)
    for p in sorted(pool, key=lambda p: p["id"]):
        strata[(p["band_type"], p["difficulty"])].append(p)
    for key in sorted(strata):
        rng.shuffle(strata[key])
    wl = Counter()
    NA, AP = defaultdict(list), defaultdict(list)
    wl_dropped = 0
    for key in sorted(strata):
        for p in strata[key]:
            if p["anchor"]:
                AP[key].append(p)
            elif wl[p["target_wl"]] < WL_CAP:
                wl[p["target_wl"]] += 1
                NA[key].append(p)
            else:
                wl_dropped += 1
    nN, nA = sum(len(v) for v in NA.values()), sum(len(v) for v in AP.values())
    N = min(N_MAX, nN + min(nA, int(math.floor(2 * nN / 3 + 1e-9))))
    A = min(nA, int(math.floor(ANCHOR_FRAC * N + 1e-9)))
    if N - A > nN:
        N = nN + A
    allocN = largest_remainder(N - A, {k: len(v) for k, v in NA.items()})
    allocA = largest_remainder(A, {k: len(v) for k, v in AP.items()})
    sel = []
    for key in sorted(set(NA) | set(AP)):
        sel += NA.get(key, [])[: allocN.get(key, 0)]
        sel += AP.get(key, [])[: allocA.get(key, 0)]
    n_anchor = sum(1 for p in sel if p["anchor"])
    assert len(sel) <= N_MAX and n_anchor <= ANCHOR_FRAC * len(sel) + 1e-9
    tw = Counter(p["target_wl"] for p in sel if not p["anchor"])
    assert not tw or max(tw.values()) <= WL_CAP
    os.makedirs(a.out, exist_ok=True)
    fn = os.path.join(a.out, "sft-r1.jsonl")
    with open(fn, "w") as fh:
        for p in sel:
            fh.write(json.dumps(p["row"]) + "\n")
    json.dump([{"id": p["id"], "task": p["task"], "target_wl": p["target_wl"], "origin": p["origin"],
                "anchor": p["anchor"], "stratum": "%s/%s" % (p["band_type"], p["difficulty"])} for p in sel],
              open(os.path.join(a.out, "ids.json"), "w"), indent=0)
    pv0_wl = {e["target_wl"] for e in exs.values()}
    allw = Counter(p["target_wl"] for p in sel)
    rt = sorted(p.get("reasoning_tokens") or 0 for p in sel if p["origin"] != "pilot-v0")
    mix = OrderedDict(
        prereg="kaggle/PREREG-EXIT-R1.md (573a21a89) step 3", seed=MIX_SEED, policies=policies,
        n=len(sel), n_tasks=len({p["task"] for p in sel}),
        pool=OrderedDict(pilot_v0_examples=len(exs), pilot_v0_with_trace=len(traces),
                         pilot_v0_unavailable=dict(why_pv0), new_completion_funnel=dict(why_new),
                         new_positives_kept=len(newp), dedupe_dropped=dict(dup), pool_after_dedupe=len(pool),
                         pool_by_origin=dict(Counter(p["origin"] for p in pool)),
                         non_anchor_after_wl_cap=nN, wl_cap_dropped=wl_dropped, anchor_pool=nA),
        size_rule="N=min(1200, nonanchor + min(anchor_pool, floor(2/3 nonanchor))); A=min(anchor_pool, floor(0.4 N))",
        N=N, A=A, anchor_share=round(n_anchor / max(1, len(sel)), 4),
        by_origin=dict(Counter(p["origin"] for p in sel)),
        by_source=dict(Counter(p["source"] for p in sel)),
        by_anchor=dict(Counter(p["anchor"] or "-" for p in sel)),
        by_stratum=dict(Counter("%s/%s" % (p["band_type"], p["difficulty"]) for p in sel)),
        by_band_type=dict(Counter(p["band_type"] for p in sel)),
        by_difficulty=dict(Counter(p["difficulty"] for p in sel)),
        by_family=dict(Counter(p["family"] for p in sel)),
        novel_target_examples=sum(1 for p in sel if p["target_wl"] not in pv0_wl),
        novel_target_wls=len({p["target_wl"] for p in sel if p["target_wl"] not in pv0_wl}),
        distinct_target_wl=len(allw), max_per_nonanchor_wl=max(tw.values()) if tw else 0,
        per_nonanchor_wl_hist=dict(Counter(tw.values())),
        new_reasoning_tokens=({"n": len(rt), "min": rt[0], "median": rt[len(rt) // 2], "max": rt[-1],
                               "lt20": sum(1 for x in rt if x < 20)} if rt else None),
        alloc_nonanchor=allocN and {"%s/%s" % k: v for k, v in allocN.items()},
        alloc_anchor=allocA and {"%s/%s" % k: v for k, v in allocA.items()},
        fence=("asserted: no held-out family/task/strict cell; target WL/token hash not in pv0's fence "
               "(bench-v2 planted cells any status + held-out witnesses); %d WLs / %d token hashes"
               % (len(fence_wl), len(fence_tok))),
        sft_file=os.path.relpath(fn, REPO), sft_sha256=sha256_file(fn),
        train_all_sha256=sha256_file(DATA))
    json.dump(mix, open(os.path.join(a.out, "MIX.json"), "w"), indent=1)
    print(json.dumps(mix, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("--policies", default="sft1000,sft300")
    ap.add_argument("--out", default=os.path.join(HERE, "sft-data"))
    a = ap.parse_args()
    cmd_build(a)

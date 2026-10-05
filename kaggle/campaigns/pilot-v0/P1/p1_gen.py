#!/usr/bin/env python
"""pilot-v0 P1 generation driver (kaggle/PREREG-PILOT-V0.md P1). Runs INSIDE the Kaggle
kernels from the pinned repo clone (LNA_DEPS_ROOT = clone), against a llama-server.

  heldout      held-out eval: every prompts/<task>.json (pre-built arm-B k=1 prompts,
               no few-shot) x S samples, through editcap_run._LiveLLM(k=1).complete_edit
               -- the exact editcap path, with EDITCAP_THINK_BUDGET=1024 (CAP-1024
               two-phase thinking) + EDITCAP_RECOVER_REASONING=1 as rl-readiness R2 CAP.
               GEN-ONLY: no sizing in the kernel; the first fenced netlist is archived
               and round-tripped (validity recorded); scoring is local (rl-v1.2).
               Order: sample 1 over all tasks, then sample 2 (a truncated run leaves a
               complete sample 1). Resumable (skips (sample, task) with a row).
  rationalize  STaR-style rationalization of training examples: given the training
               prompt + the verified answer, the model (thinking OFF via the Qwen3
               '/no_think' soft switch) writes a <= 512-token reasoning ending in that
               netlist. Kept iff (a) exactly one fenced netlist block, (b) its
               proposal.round_trip tokens == the verified target's tokens, (c) the
               reasoning is 1..512 tokens (llama-server /tokenize), (d) no answer-leak
               phrases (it must read as a derivation). Up to --attempts tries per example
               (fresh draws), parallel requests over the server's slots.

usage:
  p1_gen.py heldout --prompts DIR --out DIR [--samples 2] [--deadline-epoch T]
  p1_gen.py rationalize --examples FILE --out DIR [--attempts 3] [--parallel 4]
"""
import argparse
import glob
import json
import os
import re
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

# editcap_run from THIS file's checkout (in the kernel: the pinned clone == LNA_DEPS_ROOT)
KAGGLE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, KAGGLE_DIR)
import editcap_run as ER  # noqa: E402

P = ER.P

EVAL_ENV = {"EDITCAP_THINK_BUDGET": "1024", "EDITCAP_RECOVER_REASONING": "1",
            "EDITCAP_GEN_ONLY": "1"}
EVAL_ENV_UNSET = ("EDITCAP_FEWSHOT", "EDITCAP_NO_THINK")
MAX_TOKENS = 8192
TEMPERATURE = 0.7

RAT_MAX_TOKENS = 1280          # reasoning (<= 512 kept) + netlist (~100) + slack
RAT_MAX_REASONING_TOKENS = 512
LEAK_RE = re.compile(r"\bverified\b|\b(provided|given|shown|reference|target|verified) "
                     r"(solution|netlist|answer|design)\b|\bsolution netlist\b|"
                     r"\b(solution|netlist) (shown |given )?(above|below)\b|\bcopied\b", re.I)


def jdump(o):
    return json.dumps(o, default=float)


def append(path, row, lock=None):
    s = jdump(row) + "\n"
    if lock:
        with lock:
            with open(path, "a") as fh:
                fh.write(s)
                fh.flush()
                os.fsync(fh.fileno())
    else:
        with open(path, "a") as fh:
            fh.write(s)
            fh.flush()
            os.fsync(fh.fileno())


def read_rows(path):
    if not os.path.exists(path):
        return []
    out = []
    for ln in open(path):
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except ValueError:
                pass
    return out


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


# =================================================================== eval
def cmd_eval(a):
    for k, v in EVAL_ENV.items():
        if os.environ.get(k) != v:
            sys.exit("eval: env %s must be %r (got %r)" % (k, v, os.environ.get(k)))
    for k in EVAL_ENV_UNSET:
        if os.environ.get(k):
            sys.exit("eval: env %s must be unset" % k)
    files = sorted(f for f in glob.glob(os.path.join(a.prompts, "*.json"))
                   if not os.path.basename(f).startswith(("INDEX", "COMPARE")))
    prompts = [json.load(open(f)) for f in files]
    if a.limit:                         # pipeline smoke only
        prompts = prompts[: a.limit]
    assert prompts and all(p["arm"] == "B" and p["k"] == 1 and not p["fewshot"] for p in prompts)
    os.makedirs(a.out, exist_ok=True)
    res_path = os.path.join(a.out, "results.jsonl")
    done = {(r["sample"], r["task"]) for r in read_rows(res_path)}
    llm = ER._LiveLLM(a.llm_url, model=a.model_id, k=1, temperature=TEMPERATURE,
                      max_tokens=MAX_TOKENS)
    n_new = 0
    for s in range(1, a.samples + 1):
        for p in prompts:
            task = p["task"]
            if (s, task) in done:
                continue
            if a.deadline_epoch and time.time() > a.deadline_epoch:
                print("[p1_gen] deadline reached; stop before s%d %s" % (s, task), flush=True)
                return 0
            d = os.path.join(a.out, "s%d" % s, task)
            t0 = time.time()
            llm_error = None
            llm.last_meta = None
            try:
                raw, diag, edits = llm.complete_edit(p["messages"], "B")
            except ER.D.LLMError as e:
                llm_error, raw, diag, edits = str(e), "LLM ERROR: %s" % e, None, []
            wall = time.time() - t0
            meta = getattr(llm, "last_meta", None) or {}
            write(os.path.join(d, "raw_output.txt"), raw)
            write(os.path.join(d, "completion.meta.json"), json.dumps(meta, indent=2, default=float))
            write(os.path.join(d, "diagnosis.txt"), diag or "")
            row = {"task": task, "sample": s, "model_id": a.model_id, "n_edits": len(edits),
                   "llm_error": llm_error, "client_wall_s": round(wall, 3),
                   "finish_reason": meta.get("finish_reason"), "usage": meta.get("usage"),
                   "recovered_from_reasoning": meta.get("recovered_from_reasoning"),
                   "ts": time.time()}
            r2 = meta.get("r2") or {}
            tim = r2.get("timings") or {}
            row["gpu_ms"] = ((tim.get("prompt_ms") or 0) + (tim.get("predicted_ms") or 0)) if tim else None
            ph = r2.get("phases") or {}
            row["think_tokens"] = ph.get("think_tokens")
            row["think_stop"] = ph.get("think_stop")
            row["answer_tokens"] = ph.get("answer_tokens")
            if edits:
                write(os.path.join(d, "edit0.net"), edits[0])
                info = P.round_trip(edits[0])
                row.update(valid=bool(info["ok"]), wl_hash=info.get("wl_hash"),
                           rt_error=info.get("error"), tokens=info.get("tokens"))
            else:
                row.update(valid=False, wl_hash=None, rt_error="no fenced netlist", tokens=None)
            append(res_path, row)
            n_new += 1
            print("[p1_gen] s%d %-24s edits=%d valid=%s gpu_s=%.1f wall=%.1f think=%s/%s" % (
                s, task, len(edits), row["valid"], (row["gpu_ms"] or 0) / 1000, wall,
                row["think_tokens"], row["think_stop"]), flush=True)
    print("[p1_gen] eval done: %d new completions" % n_new, flush=True)
    return 0


# ============================================================ rationalize
RAT_INSTR = (
    "\n\n=== VERIFIED SOLUTION (use it to write your reasoning) ===\n"
    "A downstream SPICE sizer has verified that the following netlist MEETS every "
    "gated constraint of this spec:\n"
    "```netlist\n%s```\n\n"
    "YOUR TASK NOW: write the concise reasoning a careful analog designer would give to "
    "arrive at exactly this netlist starting from the failed anchor above: diagnose what "
    "physically limits the binding constraint, then explain which structural change(s) "
    "this netlist makes relative to the anchor and why they address the failure. Write it "
    "as your own derivation, in the first person and present tense; do NOT say that a "
    "solution was given, shown, provided or verified. At most 300 words. Then end your "
    "reply with that netlist copied EXACTLY, line for line, in ONE fenced ```netlist "
    "block, and write nothing after the block.")


def rat_messages(ex):
    msgs = [dict(m) for m in ex["messages"]]
    assert msgs[-1]["role"] == "user"
    msgs[-1]["content"] = msgs[-1]["content"] + (RAT_INSTR % ex["target_netlist"]) + ER.NO_THINK_SUFFIX
    return msgs


def _post(url, body, timeout=900):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def n_tokens(root, text):
    return len(_post(root + "/tokenize", {"content": text}).get("tokens") or [])


def check_trace(root, content, target_tokens):
    """-> dict(pass, why, reasoning, netlist, reasoning_tokens, ...)."""
    # an empty Qwen3 think block may be left in `content` by the server under /no_think
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.S).strip()
    blocks = ER._parse_edits_from_raw(content)
    out = {"n_blocks": len(blocks), "reasoning": None, "netlist": None, "reasoning_tokens": None,
           "rt_ok": None, "tok_match": None, "wl_match": None, "leak": None, "tail_chars": None}
    if len(blocks) != 1:
        out.update(ok=False, why="n_blocks=%d" % len(blocks))
        return out
    fence = content.find("```")
    reasoning = content[:fence].strip()
    tail = re.split(r"```(?:netlist|spice|text)?\s*\n.*?```", content, flags=re.S | re.I)[-1].strip()
    out["tail_chars"] = len(tail)
    out["reasoning"] = reasoning
    out["netlist"] = blocks[0]
    info = P.round_trip(blocks[0])
    out["rt_ok"] = bool(info["ok"])
    out["tok_match"] = bool(info["ok"]) and list(info["tokens"]) == list(target_tokens)
    out["wl_hash"] = info.get("wl_hash")
    m = LEAK_RE.search(reasoning)
    out["leak"] = m.group(0) if m else None
    out["reasoning_tokens"] = n_tokens(root, reasoning) if reasoning else 0
    why = None
    if not out["rt_ok"]:
        why = "round_trip_fail"
    elif not out["tok_match"]:
        why = "tokens_differ"
    elif not reasoning:
        why = "empty_reasoning"
    elif out["reasoning_tokens"] > RAT_MAX_REASONING_TOKENS:
        why = "reasoning_too_long"
    elif out["leak"]:
        why = "leak_phrase"
    out.update(ok=why is None, why=why)
    return out


def cmd_rationalize(a):
    exs = read_rows(a.examples)
    if a.limit:
        exs = exs[: a.limit]
    os.makedirs(a.out, exist_ok=True)
    res_path = os.path.join(a.out, "rationalize.jsonl")
    prev = read_rows(res_path)
    tries = {}
    passed = set()
    for r in prev:
        tries[r["id"]] = max(tries.get(r["id"], 0), r["attempt"])
        if r.get("ok"):
            passed.add(r["id"])
    root = a.llm_url[:-3] if a.llm_url.endswith("/v1") else a.llm_url
    client = ER.D.ChatClient(a.llm_url, model=a.model_id, timeout=900)
    lock = threading.Lock()
    stats = {"done": 0, "ok": 0}
    t_start = time.time()

    def work(ex):
        eid = ex["id"]
        if eid in passed:
            return
        tgt = P.round_trip(ex["target_netlist"])
        assert tgt["ok"], eid
        msgs = rat_messages(ex)
        for att in range(tries.get(eid, 0) + 1, a.attempts + 1):
            if a.deadline_epoch and time.time() > a.deadline_epoch:
                return
            t0 = time.time()
            err = None
            try:
                resp = client.complete(msgs, temperature=TEMPERATURE, max_tokens=RAT_MAX_TOKENS, n=1)
            except Exception as e:                                   # noqa: BLE001
                resp, err = {}, repr(e)[:500]
            ch = (resp.get("choices") or [{}])[0]
            msg = ch.get("message") or {}
            content = msg.get("content") or ""
            chk = check_trace(root, content, tgt["tokens"]) if not err else \
                {"ok": False, "why": "llm_error"}
            row = {"id": eid, "task": ex.get("task"), "attempt": att, "ok": chk["ok"],
                   "why": chk["why"], "content": content,
                   "reasoning_content_chars": len(msg.get("reasoning_content") or ""),
                   "finish_reason": ch.get("finish_reason"), "usage": resp.get("usage"),
                   "timings": resp.get("timings"), "wall_s": round(time.time() - t0, 2),
                   "llm_error": err, "target_tok_n": len(tgt["tokens"]), "ts": time.time()}
            row.update({k: v for k, v in chk.items() if k not in ("ok", "why")})
            append(res_path, row, lock)
            with lock:
                stats["done"] += 1
                if chk["ok"]:
                    stats["ok"] += 1
                el = (time.time() - t_start) / 60
                print("[rat %5.1fm] %s a%d ok=%s why=%s rtok=%s calls=%d ok=%d" % (
                    el, eid, att, chk["ok"], chk["why"], chk.get("reasoning_tokens"),
                    stats["done"], stats["ok"]), flush=True)
            if chk["ok"]:
                return

    with ThreadPoolExecutor(max_workers=a.parallel) as ex:
        list(ex.map(work, exs))
    rows = read_rows(res_path)
    ok = {r["id"] for r in rows if r.get("ok")}
    print("[p1_gen] rationalize done: %d/%d examples kept, %d calls" % (
        len(ok & {e["id"] for e in exs}), len(exs), len(rows)), flush=True)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["heldout", "rationalize"])
    ap.add_argument("--prompts")
    ap.add_argument("--examples")
    ap.add_argument("--out", required=True)
    ap.add_argument("--samples", type=int, default=2)
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--llm-url", default="http://127.0.0.1:8080/v1")
    ap.add_argument("--model-id", default="qwen3-14b-q4km")
    ap.add_argument("--deadline-epoch", type=float, default=0.0)
    a = ap.parse_args(argv)
    return cmd_eval(a) if a.cmd == "heldout" else cmd_rationalize(a)


if __name__ == "__main__":
    sys.exit(main())

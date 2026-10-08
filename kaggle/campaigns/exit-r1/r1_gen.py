#!/usr/bin/env python
"""exit-r1 generation driver (kaggle/PREREG-EXIT-R1.md step 1). Runs INSIDE the Kaggle
gen kernels from the pinned clone (LNA_DEPS_ROOT = clone) against a llama-server.

Same completion path as pilot-v0's `p1_gen.py heldout` (editcap_run._LiveLLM(k=1)
.complete_edit, CAP-1024 two-phase thinking, EDITCAP_RECOVER_REASONING=1, arm B k=1, no
few-shot, temperature 0.7, 8192-token cap; same env checks), on the TRAINING-side prompts
(pilot-v0/data/train-all.jsonl `messages`, one per task; task list + order in TASKS.json).
Differences (exit-r1 README D-R1/D-R2):
  * the think text (reasoning_content of the two-phase call) is ARCHIVED (reasoning.txt)
    with its llama-server /tokenize count, because a new positive's SFT target is the
    model's own reasoning + verified netlist;
  * task-major order over a seeded permutation (TASKS.json), both samples of a task
    before the next task, so a deadline cut leaves a uniformly random subset of tasks;
  * --parallel N worker threads (one _LiveLLM per thread) over N llama-server slots.
Resumable: (sample, task) with a row in results.jsonl are skipped.

usage: r1_gen.py --tasks TASKS.json --data train-all.jsonl --out DIR [--samples 2]
                 [--parallel 4] [--deadline-epoch T] [--limit N]
"""
import argparse
import hashlib
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.join(os.path.dirname(HERE), "pilot-v0", "P1")
sys.path.insert(0, P1)
import p1_gen as G  # noqa: E402  (imports editcap_run from this checkout)

ER, P = G.ER, G.P


def msg_sha(msgs):
    return hashlib.sha256(json.dumps(msgs, sort_keys=True).encode("utf-8")).hexdigest()[:16]


class LLM(ER._LiveLLM):
    """_LiveLLM unchanged, except that the two-phase response (with reasoning_content)
    is kept on the instance so the driver can archive the think text."""

    def _complete_think_budget(self, messages, budget):
        resp = super()._complete_think_budget(messages, budget)
        self.last_resp = resp
        return resp


def load_prompts(tasks_file, data_file):
    T = json.load(open(tasks_file))
    msgs = {}
    for ln in open(data_file):
        if ln.strip():
            e = json.loads(ln)
            msgs.setdefault(e["task"], e["messages"])
    out = []
    for t in T["tasks"]:
        m = msgs[t["task"]]
        assert msg_sha(m) == t["messages_sha"], ("prompt drift", t["task"])
        out.append({"task": t["task"], "messages": m})
    return T, out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--samples", type=int, default=2)
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--llm-url", default="http://127.0.0.1:8080/v1")
    ap.add_argument("--model-id", default="local")
    ap.add_argument("--deadline-epoch", type=float, default=0.0)
    a = ap.parse_args(argv)
    for k, v in G.EVAL_ENV.items():
        if os.environ.get(k) != v:
            sys.exit("gen: env %s must be %r (got %r)" % (k, v, os.environ.get(k)))
    for k in G.EVAL_ENV_UNSET:
        if os.environ.get(k):
            sys.exit("gen: env %s must be unset" % k)
    T, prompts = load_prompts(a.tasks, a.data)
    if a.limit:
        prompts = prompts[: a.limit]
    os.makedirs(a.out, exist_ok=True)
    res_path = os.path.join(a.out, "results.jsonl")
    done = {(r["sample"], r["task"]) for r in G.read_rows(res_path)}
    jobs = [(s, p) for p in prompts for s in range(1, a.samples + 1) if (s, p["task"]) not in done]
    root = a.llm_url[:-3] if a.llm_url.endswith("/v1") else a.llm_url
    lock = threading.Lock()
    tl = threading.local()
    st = {"n": 0, "valid": 0, "stopped": False}
    t_start = time.time()

    def llm():
        if not hasattr(tl, "llm"):
            tl.llm = LLM(a.llm_url, model=a.model_id, k=1, temperature=G.TEMPERATURE,
                         max_tokens=G.MAX_TOKENS)
        return tl.llm

    def work(job):
        s, p = job
        task = p["task"]
        if a.deadline_epoch and time.time() > a.deadline_epoch:
            with lock:
                if not st["stopped"]:
                    print("[r1_gen] deadline reached; no new completion starts", flush=True)
                st["stopped"] = True
            return
        L = llm()
        d = os.path.join(a.out, "s%d" % s, task)
        t0 = time.time()
        err = None
        L.last_meta, L.last_resp = None, None
        try:
            raw, diag, edits = L.complete_edit(p["messages"], "B")
        except ER.D.LLMError as e:
            err, raw, diag, edits = str(e), "LLM ERROR: %s" % e, None, []
        wall = time.time() - t0
        meta = getattr(L, "last_meta", None) or {}
        resp = getattr(L, "last_resp", None) or {}
        msg = ((resp.get("choices") or [{}])[0].get("message") or {})
        reasoning = msg.get("reasoning_content") or ""
        G.write(os.path.join(d, "raw_output.txt"), raw)
        G.write(os.path.join(d, "reasoning.txt"), reasoning)
        G.write(os.path.join(d, "completion.meta.json"), json.dumps(meta, indent=2, default=float))
        row = {"task": task, "sample": s, "model_id": a.model_id, "n_edits": len(edits),
               "llm_error": err, "client_wall_s": round(wall, 3),
               "finish_reason": meta.get("finish_reason"), "usage": meta.get("usage"),
               "recovered_from_reasoning": meta.get("recovered_from_reasoning"), "ts": time.time()}
        r2 = meta.get("r2") or {}
        tim = r2.get("timings") or {}
        row["gpu_ms"] = ((tim.get("prompt_ms") or 0) + (tim.get("predicted_ms") or 0)) if tim else None
        ph = r2.get("phases") or {}
        row.update(think_tokens=ph.get("think_tokens"), think_stop=ph.get("think_stop"),
                   think_closed_naturally=ph.get("think_closed_naturally"),
                   answer_tokens=ph.get("answer_tokens"), answer_stop=ph.get("answer_stop"))
        # D-Q2/D-Q3 trace-filter inputs (decided locally after verification)
        rs = reasoning.strip()
        row["reasoning_chars"] = len(rs)
        try:
            row["reasoning_tokens"] = G.n_tokens(root, rs) if rs else 0
        except Exception as e:                                       # noqa: BLE001
            row["reasoning_tokens"] = None
            row["tokenize_error"] = repr(e)[:200]
        m = G.LEAK_RE.search(rs)
        row["leak"] = m.group(0) if m else None
        row["n_blocks"] = len(ER._parse_edits_from_raw(raw)) if not err else 0
        if edits:
            G.write(os.path.join(d, "edit0.net"), edits[0])
            info = P.round_trip(edits[0])
            row.update(valid=bool(info["ok"]), wl_hash=info.get("wl_hash"),
                       rt_error=info.get("error"), tokens=info.get("tokens"))
        else:
            row.update(valid=False, wl_hash=None, rt_error="no fenced netlist", tokens=None)
        G.append(res_path, row, lock)
        with lock:
            st["n"] += 1
            st["valid"] += int(bool(row["valid"]))
            print("[r1_gen %5.1fm] %d/%d s%d %-24s valid=%s think=%s/%s rtok=%s gpu_s=%.1f" % (
                (time.time() - t_start) / 60, st["n"], len(jobs), s, task, row["valid"],
                row["think_tokens"], row["think_stop"], row["reasoning_tokens"],
                (row["gpu_ms"] or 0) / 1000), flush=True)

    print("[r1_gen] %d tasks x %d samples, %d jobs to run (%d done), parallel %d, order seed %s"
          % (len(prompts), a.samples, len(jobs), len(done), a.parallel, T.get("order_seed")), flush=True)
    with ThreadPoolExecutor(max_workers=a.parallel) as ex:
        list(ex.map(work, jobs))
    print("[r1_gen] done: %d new completions (%d valid)" % (st["n"], st["valid"]), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

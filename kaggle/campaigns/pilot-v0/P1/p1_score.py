#!/usr/bin/env python
"""pilot-v0 P1 local scorer (rl-v1.2, bptm45, 2500 evals, seeds 1,2,3).

  p1_score.py enumerate <label> <gen_dir>
        reads a kernel's gen/ output (results.jsonl + s<N>/<task>/edit0.net), re-does
        proposal.round_trip LOCALLY on every archived netlist (validity of record), writes
        score/<label>/completions.jsonl and adds every valid (task, token-seq) to
        score/cand.json (shared across models: one sizing per unique key).
  p1_score.py run [nproc<=4] [label,label..]
        sizes every unique (task, tokens) x seeds 1,2,3 through bv2's worker (the exact
        P0 engine: bench_anchor_prep.smoke_run(tokens, spec, seed, 2500, "bptm45",
        profile="rl-v1.2")), spec = P1/specs/<task>.yaml (content == the task spec, so the
        bv2 job id is the P0 cache key). Exact-key hits in the pilot-v0 / AMENDMENT-3
        rl-v1.2 caches (read-only) are reused, not re-sized. Appends score/score.jsonl
        (resumable). In-process pre-rejects (topology limits, degeneracy, port-DC
        pre-filter) are sized by smoke_run itself and cost ~0 s, as in P0.
Run through an env wrapper (crenv vars; LNA_DEPS_ROOT as the P0 job).
"""
import json
import os
import subprocess
import sys
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
PV0 = os.path.dirname(HERE)
sys.path.insert(0, PV0)
import pv0  # noqa: E402

B = pv0.B
SC = os.environ.get("P1_SCORE_DIR") or os.path.join(HERE, "score")
SEEDS = (1, 2, 3)
PROF = "rl-v1.2"
RAW = os.path.join(os.environ.get("TMPDIR", "/tmp"), "p1-score-raw")


def P():
    import proposal
    return proposal


def prompts():
    idx = json.load(open(os.path.join(HERE, "prompts", "INDEX.json")))["items"]
    return {n: v for n, v in idx.items() if not v.get("excluded")}


def enumerate_gen(label, gen_dir):
    items = prompts()
    anch = B.anchor_data()
    rows = B.read_jsonl(os.path.join(gen_dir, "results.jsonl"))
    seen = OrderedDict()
    for r in rows:                      # last row per (sample, task) wins (resume safety)
        seen[(r["sample"], r["task"])] = r
    os.makedirs(os.path.join(SC, label), exist_ok=True)
    cp = os.path.join(SC, "cand.json")
    cand = json.load(open(cp)) if os.path.exists(cp) else {}
    out = []
    for (s, task), r in sorted(seen.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        assert task in items, task
        p = os.path.join(gen_dir, "s%d" % s, task, "edit0.net")
        rec = {"label": label, "task": task, "sample": s, "llm_error": r.get("llm_error"),
               "gpu_ms": r.get("gpu_ms"), "client_wall_s": r.get("client_wall_s"),
               "think_tokens": r.get("think_tokens"), "think_stop": r.get("think_stop"),
               "answer_tokens": r.get("answer_tokens"), "finish_reason": r.get("finish_reason"),
               "recovered_from_reasoning": r.get("recovered_from_reasoning"),
               "kernel_valid": r.get("valid"), "has_netlist": os.path.exists(p)}
        if os.path.exists(p):
            info = P().round_trip(open(p, errors="replace").read())
            ok = bool(info["ok"])
            rec.update(valid=ok, rt_error=info.get("error"), wl=info.get("wl_hash"))
            if ok:
                k = B.tokhash(info["tokens"])
                rec["key"] = k
                rec["is_shown_anchor"] = k == anch[items[task]["shown_anchor"]]["tok"]
                rec["is_any_anchor"] = any(k == A["tok"] for A in anch.values())
                ck = "%s|%s" % (task, k)
                c = cand.setdefault(ck, {"task": task, "key": k, "tokens": info["tokens"], "labels": []})
                if label not in c["labels"]:
                    c["labels"].append(label)
        else:
            rec.update(valid=False, rt_error="no fenced netlist")
        if rec["kernel_valid"] is not None and rec["kernel_valid"] != rec["valid"]:
            rec["validity_mismatch_kernel_vs_local"] = True
        out.append(rec)
    with open(os.path.join(SC, label, "completions.jsonl"), "w") as fh:
        for rec in out:
            fh.write(json.dumps(rec) + "\n")
    B.atomic_write(cp, json.dumps(cand))
    nv = sum(1 for x in out if x["valid"])
    print("%s: %d completions, %d valid, %d unique keys total in cand.json; kernel/local "
          "validity mismatches %d" % (label, len(out), nv, len(cand),
                                      sum(1 for x in out if x.get("validity_mismatch_kernel_vs_local"))))


def caches():
    c = {}
    for p in (f"{PV0}/run/results.jsonl", f"{PV0}/smoke/results.jsonl",
              f"{pv0.A3}/run/results.jsonl", f"{pv0.A3}/smoke/results.jsonl"):
        for r in B.read_jsonl(p):
            if r.get("profile") == PROF and not r.get("error") and r.get("jid") and r["jid"] not in c:
                r["_src"] = os.path.relpath(p, pv0.REPO)
                c[r["jid"]] = r
    return c


def summ(r):
    res = r.get("res") or {}
    pd = res.get("port_dc")
    return {"feasible": B.feasible(r), "secs": r.get("secs"), "n_evals": res.get("n_evals"),
            "mu_min_wide": res.get("mu_min_wide"), "infeasible_reason": res.get("infeasible_reason"),
            "port_dc_pass": pd.get("pass") if isinstance(pd, dict) else None,
            "metrics": {k: v for k, v in (res.get("metrics") or {}).items() if isinstance(v, (int, float))},
            "verifier": (res.get("verifier") or {}).get("profile"), "error": r.get("error")}


def run(nproc=4, labels=None):
    nproc = min(4, int(nproc))
    os.makedirs(RAW, exist_ok=True)
    cand = json.load(open(os.path.join(SC, "cand.json")))
    if labels:
        cand = {k: v for k, v in cand.items() if set(v["labels"]) & set(labels)}
    sp = os.path.join(SC, "score.jsonl")
    cache = caches()
    done = {(r["task"], r["key"], r["seed"]) for r in B.read_jsonl(sp)}
    jobs = []
    for ck, v in sorted(cand.items()):
        spec = os.path.join(HERE, "specs", v["task"] + ".yaml")
        for s in SEEDS:
            if (v["task"], v["key"], s) in done:
                continue
            jobs.append((v["task"], v["key"], s, B.job_id(v["tokens"], spec, s, B.BUDGET, PROF),
                         v["tokens"], spec))
    jobs.sort(key=lambda j: j[3] not in cache)          # exact-key cache hits first (free)
    if os.environ.get("P1_SCORE_MAX_JOBS"):              # mock test only
        jobs = jobs[: int(os.environ["P1_SCORE_MAX_JOBS"])]
    print("score: %d jobs to run (%d done)" % (len(jobs), len(done)), flush=True)
    era = B.era_stamp()

    def work(j):
        task, key, seed, jid, tokens, spec = j
        if jid in cache:
            r = cache[jid]
            return dict(task=task, key=key, seed=seed, jid=jid, source="cache:" + r["_src"],
                        **summ(r))
        jf, of = os.path.join(RAW, jid + ".job.json"), os.path.join(RAW, jid + ".out.json")
        if not os.path.exists(of):
            json.dump({"jid": jid, "tokens": tokens, "spec": spec, "seed": seed,
                       "budget": B.BUDGET, "profile": PROF}, open(jf, "w"))
            with open(os.path.join(RAW, jid + ".err"), "w") as ef:
                subprocess.run([sys.executable, pv0.BV2_PY, "worker", jf, of],
                               stdout=subprocess.DEVNULL, stderr=ef)
        if not os.path.exists(of):
            return dict(task=task, key=key, seed=seed, jid=jid, source="sized", crashed=True,
                        feasible=False, secs=None,
                        stderr_tail=open(os.path.join(RAW, jid + ".err")).read()[-600:])
        r = json.load(open(of))
        return dict(task=task, key=key, seed=seed, jid=jid, source="sized", era=era, **summ(r))

    t0 = time.time()
    n = 0
    with ThreadPoolExecutor(max_workers=nproc) as ex, open(sp, "a") as fh:
        futs = [ex.submit(work, j) for j in jobs]
        for f in as_completed(futs):
            rec = f.result()
            rec["ts"] = pv0.now()
            fh.write(json.dumps(rec, default=repr) + "\n")
            fh.flush()
            n += 1
            el = (time.time() - t0) / 60
            print("[score %d/%d %.1fmin] %s %s s%d feas=%s secs=%s src=%s" % (
                n, len(jobs), el, rec["task"], rec["key"], rec["seed"], rec.get("feasible"),
                rec.get("secs"), rec.get("source")), flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "enumerate":
        enumerate_gen(a[1], os.path.abspath(a[2]))
    elif a[0] == "run":
        run(int(a[1]) if len(a) > 1 else 4, a[2].split(",") if len(a) > 2 else None)

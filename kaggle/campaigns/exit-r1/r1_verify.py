#!/usr/bin/env python
"""exit-r1 step 2: local verification of the generated training-side completions
(kaggle/PREREG-EXIT-R1.md step 2), and the rl-v1.2-rl (kick) column of step 5.

  r1_verify.py enumerate <policy> <gen_dir>
        every completion of a gen kernel (results.jsonl + s<N>/<task>/edit0.net): local
        proposal.round_trip (validity of record), key = token hash, WL; flags: shown anchor,
        any library anchor, copy of one of the task's own pilot-v0 targets, novel (target WL
        not among pilot-v0 data's target WLs); trace-filter inputs (think text, its token
        count, leak phrase, fenced-block count). -> verify/<policy>/completions.jsonl and
        verify/cand.json (unique (task, key) shared over policies).
  r1_verify.py run <nproc<=8> <policy[,policy..]>
        profile rl-v1.2-rl, bptm45, 2500 evals: seed 1 for every valid unique (task, key);
        then seed 2 for every key feasible at seed 1. positive = feasible at seeds 1 AND 2.
        Spec = the task's pilot-v0 example spec_file (content sha == example spec_sha).
        Worker = pilot-v0's (bv2 worker -> bench_anchor_prep.smoke_run(..., profile)).
        <= nproc processes, 4 while load1 > 22; D32 disk robustness (bv2.SafeAppender,
        no launch below 5 GB free on the verify fs or 1 GB in $TMPDIR, a worker that left
        no result during disk trouble is re-queued); resumable on exact keys.
  r1_verify.py kick <nproc<=8> <score_dir> <label[,label..]> [<out.jsonl>]
        step-5 secondary column: for every (task, key, seed) of <score_dir>/score.jsonl
        (pv1_score.py rows, rl-v1.2) that is FEASIBLE and whose key belongs to the labels,
        the same sizing under rl-v1.2-rl (kick can only turn feasible -> infeasible; an
        rl-v1.2-infeasible row is rl-v1.2-rl-infeasible, VERIFIER-RL-V1 T4 consistency)
        -> <out.jsonl> (default <score_dir>/kick.jsonl).
"""
import json
import os
import subprocess
import sys
import threading
import time
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PV0 = os.path.join(REPO, "kaggle", "campaigns", "pilot-v0")
P1 = os.path.join(PV0, "P1")
sys.path.insert(0, P1)
sys.path.insert(0, PV0)
import pv0  # noqa: E402

B = pv0.B
VD = os.environ.get("R1_VERIFY_DIR") or os.path.join(HERE, "verify")
PROF_RL = "rl-v1.2-rl"
RAW = os.path.join(os.environ.get("TMPDIR", "/tmp"), "r1-verify-raw")
LOAD_HI = 22.0
DATA = os.path.join(PV0, "data", "train-all.jsonl")


def P():
    import proposal
    return proposal


def train_index():
    ex = [json.loads(l) for l in open(DATA) if l.strip()]
    by_task = OrderedDict()
    for e in ex:
        t = by_task.setdefault(e["task"], {"spec_file": e["spec_file"], "spec_sha": e["spec_sha"],
                                           "shown_anchor": e["shown_anchor"], "target_wl": [],
                                           "difficulty": e["difficulty"], "band_type": e["band_type"],
                                           "family": e["family"]})
        t["target_wl"].append(e["target_wl"])
    return ex, by_task


def enumerate_gen(policy, gen_dir):
    P()                         # repo modules first (as build_sft.py), then editcap_run via p1_gen
    import p1_gen as G
    ex, by_task = train_index()
    all_wl = {e["target_wl"] for e in ex}
    anch = B.anchor_data()
    anchor_wl = {A["wl"]: a for a, A in anch.items()}
    rows = B.read_jsonl(os.path.join(gen_dir, "results.jsonl"))
    seen = OrderedDict()
    for r in rows:
        seen[(r["sample"], r["task"])] = r
    os.makedirs(os.path.join(VD, policy), exist_ok=True)
    cp = os.path.join(VD, "cand.json")
    cand = json.load(open(cp)) if os.path.exists(cp) else {}
    out = []
    for (s, task), r in sorted(seen.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        t = by_task[task]
        d = os.path.join(gen_dir, "s%d" % s, task)
        p = os.path.join(d, "edit0.net")
        raw = open(os.path.join(d, "raw_output.txt"), errors="replace").read() \
            if os.path.exists(os.path.join(d, "raw_output.txt")) else ""
        reasoning = open(os.path.join(d, "reasoning.txt"), errors="replace").read() \
            if os.path.exists(os.path.join(d, "reasoning.txt")) else ""
        rs = reasoning.strip()
        lk = G.LEAK_RE.search(rs)
        rec = {"policy": policy, "task": task, "sample": s, "family": t["family"],
               "band_type": t["band_type"], "difficulty": t["difficulty"],
               "llm_error": r.get("llm_error"), "gpu_ms": r.get("gpu_ms"),
               "think_tokens": r.get("think_tokens"), "think_stop": r.get("think_stop"),
               "think_closed_naturally": r.get("think_closed_naturally"),
               "answer_tokens": r.get("answer_tokens"), "finish_reason": r.get("finish_reason"),
               "recovered_from_reasoning": r.get("recovered_from_reasoning"),
               "reasoning_tokens": r.get("reasoning_tokens"), "reasoning_chars": len(rs),
               "leak": lk.group(0) if lk else None,
               "n_blocks": len(G.ER._parse_edits_from_raw(raw)) if raw and not r.get("llm_error") else 0,
               "kernel_valid": r.get("valid"), "has_netlist": os.path.exists(p)}
        if os.path.exists(p):
            info = P().round_trip(open(p, errors="replace").read())
            ok = bool(info["ok"])
            rec.update(valid=ok, rt_error=info.get("error"), wl=info.get("wl_hash"))
            if ok:
                k = B.tokhash(info["tokens"])
                rec["key"] = k
                rec["is_shown_anchor"] = k == anch[t["shown_anchor"]]["tok"]
                rec["anchor"] = anchor_wl.get(info.get("wl_hash"))
                rec["copy_own_target"] = info.get("wl_hash") in set(t["target_wl"])
                rec["novel"] = info.get("wl_hash") not in all_wl
                ck = "%s|%s" % (task, k)
                c = cand.setdefault(ck, {"task": task, "key": k, "tokens": info["tokens"],
                                         "wl": info.get("wl_hash"), "labels": []})
                if policy not in c["labels"]:
                    c["labels"].append(policy)
        else:
            rec.update(valid=False, rt_error="no fenced netlist")
        if rec["kernel_valid"] is not None and rec["kernel_valid"] != rec["valid"]:
            rec["validity_mismatch_kernel_vs_local"] = True
        out.append(rec)
    with open(os.path.join(VD, policy, "completions.jsonl"), "w") as fh:
        for rec in out:
            fh.write(json.dumps(rec) + "\n")
    B.atomic_write(cp, json.dumps(cand))
    nv = sum(1 for x in out if x["valid"])
    print("%s: %d completions (%d tasks), %d valid, %d unique keys in cand.json; novel valid %d; "
          "kernel/local validity mismatches %d" % (
              policy, len(out), len({x["task"] for x in out}), nv, len(cand),
              sum(1 for x in out if x.get("novel")),
              sum(1 for x in out if x.get("validity_mismatch_kernel_vs_local"))))


# ------------------------------------------------------------------ engine
def summ(r):
    res = r.get("res") or {}
    pd = res.get("port_dc")
    kick = res.get("kick")
    return {"feasible": B.feasible(r), "secs": r.get("secs"), "n_evals": res.get("n_evals"),
            "mu_min_wide": res.get("mu_min_wide"), "infeasible_reason": res.get("infeasible_reason"),
            "port_dc_pass": pd.get("pass") if isinstance(pd, dict) else None,
            "kick": ({k: kick.get(k) for k in ("pass", "verdict", "growing", "error", "secs")}
                     if isinstance(kick, dict) else None),
            "metrics": {k: v for k, v in (res.get("metrics") or {}).items() if isinstance(v, (int, float))},
            "verifier": (res.get("verifier") or {}).get("profile"), "error": r.get("error")}


def caches(profile):
    c = {}
    for p in (f"{PV0}/run/results.jsonl", f"{PV0}/smoke/results.jsonl",
              f"{pv0.A3}/run/results.jsonl", f"{pv0.A3}/smoke/results.jsonl"):
        for r in B.read_jsonl(p):
            if r.get("profile") == profile and not r.get("error") and r.get("jid") and r["jid"] not in c:
                r["_src"] = os.path.relpath(p, REPO)
                c[r["jid"]] = r
    return c


def free_gb(p):
    try:
        st = os.statvfs(p)
        return st.f_bavail * st.f_frsize / 1e9
    except OSError:
        return None


def disk_ok(path):
    a, b = free_gb(path), free_gb(RAW)
    low = (a is not None and a < B.DISK_MIN_FREE_GB) or (b is not None and b < B.TMP_MIN_FREE_GB)
    return not low and not B.DISK.paused() and not B.DISK.backoff_active()


def cap(nproc):
    try:
        l1 = os.getloadavg()[0]
    except OSError:
        l1 = 0.0
    return min(nproc, 4) if l1 > LOAD_HI else nproc


def execute(js, stage, nproc, out_path, profile, cache):
    """js: list of dicts with task, key, seed, jid, tokens, spec (+ extra fields copied)."""
    os.makedirs(RAW, exist_ok=True)
    out = B.SafeAppender(out_path)
    lock = threading.Lock()
    era = B.era_stamp()
    queue = sorted(js, key=lambda j: j["jid"] not in cache)
    active = [0]
    t0 = time.time()
    n = [0]
    print("[r1 %s] %s: %d jobs" % (profile, stage, len(queue)), flush=True)

    def work(j):
        base = {k: j[k] for k in j if k not in ("tokens", "spec")}
        jid = j["jid"]
        if jid in cache:
            r = cache[jid]
            return dict(base, source="cache:" + r["_src"], profile=profile, **summ(r))
        jf, of = os.path.join(RAW, jid + ".job.json"), os.path.join(RAW, jid + ".out.json")
        if not os.path.exists(of):
            json.dump({"jid": jid, "tokens": j["tokens"], "spec": j["spec"], "seed": j["seed"],
                       "budget": B.BUDGET, "profile": profile}, open(jf, "w"))
            with open(os.path.join(RAW, jid + ".err"), "w") as ef:
                subprocess.run([sys.executable, pv0.BV2_PY, "worker", jf, of],
                               stdout=subprocess.DEVNULL, stderr=ef)
        if not os.path.exists(of):
            if not disk_ok(os.path.dirname(out_path)):
                return None
            return dict(base, source="sized", profile=profile, crashed=True, feasible=False, secs=None,
                        stderr_tail=open(os.path.join(RAW, jid + ".err")).read()[-600:])
        r = json.load(open(of))
        return dict(base, source="sized", profile=profile, era=era, **summ(r))

    def runner(j):
        try:
            rec = work(j)
        except Exception as e:                                       # noqa: BLE001
            rec = dict({k: j[k] for k in j if k not in ("tokens", "spec")}, source="sized",
                       profile=profile, crashed=True, feasible=False, secs=None, error=repr(e)[:300])
        with lock:
            active[0] -= 1
            if rec is None:
                queue.append(j)
                return
            rec["ts"] = pv0.now()
            out.write(json.dumps(rec, default=repr) + "\n")
            n[0] += 1
            print("[r1 %s %d/%d %.1fmin] %s %s s%d feas=%s secs=%s src=%s" % (
                stage, n[0], len(js), (time.time() - t0) / 60, rec["task"], rec["key"], rec["seed"],
                rec.get("feasible"), rec.get("secs"), rec.get("source")), flush=True)
    threads = []
    while True:
        with lock:
            busy, left = active[0], len(queue)
        if not left and not busy:
            break
        if left and busy < cap(nproc):
            with lock:
                j = queue.pop(0)
            hit = j["jid"] in cache
            if not hit and not disk_ok(os.path.dirname(out_path)):
                with lock:
                    queue.insert(0, j)
                out.flush()
                time.sleep(30)
                continue
            with lock:
                active[0] += 1
            th = threading.Thread(target=runner, args=(j,), daemon=True)
            th.start()
            threads.append(th)
            if hit:
                th.join()
            continue
        out.flush()
        time.sleep(0.5 if left else 2)
    for th in threads:
        th.join()
    while out.pending():
        out.flush()
        time.sleep(5)


def spec_for(task, by_task):
    sp = os.path.join(P1, "specs", task + ".yaml")
    if task in by_task:
        t = by_task[task]
        sp = os.path.join(REPO, t["spec_file"])
        assert B.spec_sha(sp) == t["spec_sha"], ("spec drift", task)
    assert os.path.exists(sp), sp
    return sp


def run(nproc, policies):
    nproc = max(1, min(8, int(nproc)))
    _, by_task = train_index()
    cand = json.load(open(os.path.join(VD, "cand.json")))
    cand = {k: v for k, v in cand.items() if set(v["labels"]) & set(policies)}
    sp = os.path.join(VD, "verify.jsonl")
    cache = caches(PROF_RL)
    specs = {}

    def jobs(seeds_of):
        done = {(r["task"], r["key"], r["seed"]): r for r in B.read_jsonl(sp)}
        js = []
        for ck, v in sorted(cand.items()):
            if v["task"] not in specs:
                specs[v["task"]] = spec_for(v["task"], by_task)
            for s in seeds_of(v, done):
                if (v["task"], v["key"], s) in done:
                    continue
                js.append({"task": v["task"], "key": v["key"], "seed": s,
                           "jid": B.job_id(v["tokens"], specs[v["task"]], s, B.BUDGET, PROF_RL),
                           "tokens": v["tokens"], "spec": specs[v["task"]]})
        return js
    execute(jobs(lambda v, d: (1,)), "seed1", nproc, sp, PROF_RL, cache)

    def confirm(v, d):
        r = d.get((v["task"], v["key"], 1))
        return (2,) if r and r.get("feasible") else ()
    execute(jobs(confirm), "seed2", nproc, sp, PROF_RL, cache)


def kick(nproc, score_dir, labels, out_path=None):
    nproc = max(1, min(8, int(nproc)))
    cand = json.load(open(os.path.join(score_dir, "cand.json")))
    keys = {(v["task"], v["key"]): v for v in cand.values() if set(v["labels"]) & set(labels)}
    rows = [r for r in B.read_jsonl(os.path.join(score_dir, "score.jsonl"))
            if r.get("feasible") and (r["task"], r["key"]) in keys]
    kp = out_path or os.path.join(score_dir, "kick.jsonl")
    done = {(r["task"], r["key"], r["seed"]) for r in B.read_jsonl(kp)}
    js, seen = [], set()
    for r in rows:
        k3 = (r["task"], r["key"], r["seed"])
        if k3 in done or k3 in seen:
            continue
        seen.add(k3)
        spec = spec_for(r["task"], {})
        v = keys[(r["task"], r["key"])]
        js.append({"task": r["task"], "key": r["key"], "seed": r["seed"],
                   "jid": B.job_id(v["tokens"], spec, r["seed"], B.BUDGET, PROF_RL),
                   "tokens": v["tokens"], "spec": spec, "rl_v12_jid": r["jid"]})
    execute(js, "kick", nproc, kp, PROF_RL, caches(PROF_RL))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "enumerate":
        enumerate_gen(a[1], os.path.abspath(a[2]))
    elif a[0] == "run":
        run(int(a[1]), a[2].split(","))
    elif a[0] == "kick":
        kick(int(a[1]), os.path.abspath(a[2]), a[3].split(","), os.path.abspath(a[4]) if len(a) > 4 else None)
    else:
        sys.exit(__doc__)

#!/usr/bin/env python
"""pilot-v1 local scorer (rl-v1.2, bptm45, 2500 evals; kaggle/PREREG-PILOT-V1.md).

  pv1_score.py enumerate <label> <gen_dir>
        pilot-v0's p1_score.enumerate_gen (local round-trip of every archived netlist,
        validity of record) into pilot-v1/score/ (P1_SCORE_DIR), shared cand.json.
  pv1_score.py run <nproc<=8> <policy> <label[,label..]>
        policy 'h1'  : seed 1 for every valid unique (task, tokens) of the labels; then
                       seeds 2 and 3 for every key feasible at seed 1 (H1 confirmation).
        policy 'all3': seeds 1, 2, 3 for every key (pilot-v0's M1 / P1 scoring).
        Worker = pilot-v0's (bv2 worker -> bench_anchor_prep.smoke_run(tokens, spec, seed,
        2500, "bptm45", profile="rl-v1.2")), spec = pilot-v0/P1/specs/<task>.yaml. Exact-key
        reuse (read-only) of the pilot-v0 / AMENDMENT-3 rl-v1.2 caches and of the pilot-v0
        P1 score rows. <= nproc processes, 4 while load1 > 22. D32 disk robustness: rows
        appended through bv2.SafeAppender (ENOSPC-safe), no launch while the score dir's
        filesystem has < 5 GB or $TMPDIR < 1 GB free, a worker that left no result while
        the disk was in trouble is re-queued (never recorded). Resumable (exact keys).
"""
import json
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SC = os.environ.get("PV1_SCORE_DIR") or os.path.join(HERE, "score")     # override: tests only
os.environ["P1_SCORE_DIR"] = SC
P1 = os.path.join(REPO, "kaggle", "campaigns", "pilot-v0", "P1")
sys.path.insert(0, P1)
import p1_score as PS  # noqa: E402

pv0, B = PS.pv0, PS.B
PROF = PS.PROF
RAW = os.path.join(os.environ.get("TMPDIR", "/tmp"), "pv1-score-raw")
LOAD_HI = 22.0


def caches():
    c = PS.caches()
    for r in B.read_jsonl(os.path.join(P1, "score", "score.jsonl")):
        if r.get("jid") and r["jid"] not in c and not r.get("crashed") and r.get("secs") is not None:
            c[r["jid"]] = dict(r, _p1row=True)
    return c


def free_gb(p):
    try:
        st = os.statvfs(p)
        return st.f_bavail * st.f_frsize / 1e9
    except OSError:
        return None


def disk_ok():
    a, b = free_gb(SC), free_gb(RAW)
    low = (a is not None and a < B.DISK_MIN_FREE_GB) or (b is not None and b < B.TMP_MIN_FREE_GB)
    return not low and not B.DISK.paused() and not B.DISK.backoff_active()


def cap(nproc):
    try:
        l1 = os.getloadavg()[0]
    except OSError:
        l1 = 0.0
    return min(nproc, 4) if l1 > LOAD_HI else nproc


def run(nproc, policy, labels):
    nproc = max(1, min(8, int(nproc)))
    os.makedirs(RAW, exist_ok=True)
    cand = json.load(open(os.path.join(SC, "cand.json")))
    cand = {k: v for k, v in cand.items() if set(v["labels"]) & set(labels)}
    sp = os.path.join(SC, "score.jsonl")
    cache = caches()
    era = B.era_stamp()
    out = B.SafeAppender(sp)
    lock = threading.Lock()

    def done_map():
        return {(r["task"], r["key"], r["seed"]): r for r in B.read_jsonl(sp)}

    def jobs_for(seeds_of):
        done = done_map()
        js = []
        for ck, v in sorted(cand.items()):
            spec = os.path.join(P1, "specs", v["task"] + ".yaml")
            for s in seeds_of(v, done):
                if (v["task"], v["key"], s) in done:
                    continue
                js.append((v["task"], v["key"], s, B.job_id(v["tokens"], spec, s, B.BUDGET, PROF),
                           v["tokens"], spec))
        js.sort(key=lambda j: j[3] not in cache)
        return js

    def work(j):
        task, key, seed, jid, tokens, spec = j
        if jid in cache:
            r = cache[jid]
            if r.get("_p1row"):
                d = {k: v for k, v in r.items() if k not in ("_p1row", "ts", "task", "key", "seed", "jid",
                                                             "source", "era")}
                return dict(task=task, key=key, seed=seed, jid=jid,
                            source="cache:kaggle/campaigns/pilot-v0/P1/score/score.jsonl", **d)
            return dict(task=task, key=key, seed=seed, jid=jid, source="cache:" + r["_src"], **PS.summ(r))
        jf, of = os.path.join(RAW, jid + ".job.json"), os.path.join(RAW, jid + ".out.json")
        if not os.path.exists(of):
            json.dump({"jid": jid, "tokens": tokens, "spec": spec, "seed": seed,
                       "budget": B.BUDGET, "profile": PROF}, open(jf, "w"))
            with open(os.path.join(RAW, jid + ".err"), "w") as ef:
                subprocess.run([sys.executable, pv0.BV2_PY, "worker", jf, of],
                               stdout=subprocess.DEVNULL, stderr=ef)
        if not os.path.exists(of):
            if not disk_ok():
                return None                         # disk trouble: re-queue, never record
            return dict(task=task, key=key, seed=seed, jid=jid, source="sized", crashed=True,
                        feasible=False, secs=None,
                        stderr_tail=open(os.path.join(RAW, jid + ".err")).read()[-600:])
        r = json.load(open(of))
        return dict(task=task, key=key, seed=seed, jid=jid, source="sized", era=era, **PS.summ(r))

    def execute(js, stage):
        queue = list(js)
        active = [0]
        t0 = time.time()
        n = [0]
        print("[pv1 score] %s: %d jobs" % (stage, len(queue)), flush=True)

        def runner(j):
            try:
                rec = work(j)
            except Exception as e:                                   # noqa: BLE001
                rec = dict(task=j[0], key=j[1], seed=j[2], jid=j[3], source="sized", crashed=True,
                           feasible=False, secs=None, error=repr(e)[:300])
            with lock:
                active[0] -= 1
                if rec is None:
                    queue.append(j)
                    return
                rec["ts"] = pv0.now()
                out.write(json.dumps(rec, default=repr) + "\n")
                n[0] += 1
                print("[pv1 score %s %d/%d %.1fmin] %s %s s%d feas=%s secs=%s src=%s" % (
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
                hit = j[3] in cache
                if not hit and not disk_ok():
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

    if policy == "all3":
        execute(jobs_for(lambda v, d: (1, 2, 3)), "all3")
    elif policy == "h1":
        execute(jobs_for(lambda v, d: (1,)), "seed1")

        def confirm(v, d):
            r = d.get((v["task"], v["key"], 1))
            return (2, 3) if r and r.get("feasible") else ()
        execute(jobs_for(confirm), "confirm23")
    else:
        sys.exit("policy must be h1 or all3")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "enumerate":
        os.makedirs(SC, exist_ok=True)
        PS.enumerate_gen(a[1], os.path.abspath(a[2]))
    elif a[0] == "run":
        run(int(a[1]), a[2], a[3].split(","))

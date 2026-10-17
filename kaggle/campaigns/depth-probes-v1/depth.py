#!/usr/bin/env python
"""depth-probes-v1 (kaggle/PREREG-DEPTH-PROBES-V1.md, frozen 8b9a5ca08): corner margin + IIP3 of
within-one-edit (A) vs beyond-one-edit (B) feasible designs on the 35 non-T1 held-out tasks.

  depth.py collect
        pools per task from CACHED rl-v1.2 rows at the ORIGINAL spec (0 sims):
          A = library a1-a5 + single edits of the shown anchor (pilot-v0 P0 tiering rows /
              AMENDMENT-3 rows; exact keys as bench-v3 a0.py), feasible at seed 1;
          B = planted witness (seed 1 if feasible, else its seed-2 row) + every other design of
              baselines-v1 GA (ga/run), exit-r1 r1-8 / r2-8, pilot-v1 h1-sft300 / h1-sft1000,
              pilot-v0 P1, baselines-v1 opus-4 that is feasible at seed 1 and whose token key is
              NOT in A's enumerated space (anchors + shown-anchor single edits);
          cap 6 per pool per task by highest cached original worst margin (ties by key).
        -> pools.json (hashes/margins only) + state/pools-tokens.json (gitignored, EVAL-ONLY)
  depth.py run [--nproc 8] [--deadline EPOCH] [--kill-at EPOCH] [--ntasks N] [--sanity]
        per design: S = re-size (seed of its row, rl-v1.2, 2500, bptm45; EX sized_run capture of
        the final winner's params, smoke_run verbatim), then without re-sizing
        C = nominal re-eval + EX corner_eval at -40 C, +85 C, VDD x0.9, x1.1, and
        I = size.measure_iip3_tier3 (lna/iip3.py two-tone harness, default settings) at spec f0.
        Tasks in seeded random order (README D-P), stages prioritized by task order.
        Box-wide cap 8 heavy processes (other jobs' `bv2.py worker` counted from /proc), 4 while
        load1 > 22; no launch below the bv2 disk floors. NO job is launched at/after --deadline;
        running workers are killed at --kill-at (no row written -> re-run on resume).
        Exact-key resume through run/{sizing,corners,iip3}.jsonl.
        --sanity: only the top-ranked B design of each of the first --ntasks tasks.
  depth.py summarize   -> depth-designs.jsonl, depth-tasks.jsonl, depth-summary.json, depth-tables.md
  depth.py status      -> progress counts
  depth.py worker STAGE JOB OUT   (internal)

Run via the env wrapper. Temp files: DEPTH_TMPDIR (default ~/.claude/jobs/7cd7ffc3/tmp/depth/tmp).
Witness netlists/tokens/bodies are EVAL-ONLY: persisted only under state/ in this directory
(gitignored, never committed, never shown to any LLM); every committed output carries hashes only.
"""
import json
import os
import random
import resource
import signal
import subprocess
import sys
import threading
import time
import traceback
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CAMP = os.path.join(REPO, "kaggle", "campaigns")
STATE = os.path.join(HERE, "state")
SIZED = os.path.join(STATE, "sized")
RAWJ = os.path.join(STATE, "raw")
RUN = os.path.join(HERE, "run")
_T = os.environ.get("DEPTH_TMPDIR") or os.path.expanduser("~/.claude/jobs/7cd7ffc3/tmp/depth/tmp")
os.makedirs(_T, exist_ok=True)
os.environ["A0_TMPDIR"] = _T          # a0 -> ga: GA_TMPDIR/TMPDIR (ngspice scratch) under _T
os.environ["TMPDIR"] = _T
PREREG = "kaggle/PREREG-DEPTH-PROBES-V1.md (8b9a5ca08)"
PROF = "rl-v1.2"
CAP_POOL = 6
ORDER_SEED = "depth-probes-v1"
BOX_MAX, LOAD_HI = 8, 22.0
TIMEOUT = {"S": 3600, "C": 1800, "I": 3600}
CORNERS = (("T-40", {"temp": -40}), ("T85", {"temp": 85}), ("V0.9", {"vdd_scale": 0.9}),
           ("V1.1", {"vdd_scale": 1.1}))
CORNER_DELTA, IIP3_DELTA = 0.10, 3.0
LLM_SRC = (("baselines-v1/opus/score", ("opus-4",)),
           ("exit-r1/score", ("r1-8", "r2-8")),
           ("pilot-v1/score", ("h1-sft300", "h1-sft1000")),
           ("pilot-v0/P1/score", None))          # None = every label of pilot-v0 P1
GA_RUN = os.path.join(CAMP, "baselines-v1", "ga", "run")
EXTRA_CACHE = (os.path.join(GA_RUN, "results.jsonl"), os.path.join(CAMP, "baselines-v1", "opus", "score",
                                                                     "score.jsonl"))


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def rel(p):
    return os.path.relpath(p, REPO)


def jdump(o, **k):
    return json.dumps(o, default=repr, **k)


def _lib():
    """heavy imports for the scheduler side (bench-v3 a0 loading code, read-only reuse)."""
    sys.path.insert(0, os.path.join(CAMP, "bench-v3"))
    import a0  # noqa: E402
    return a0


# ------------------------------------------------------------------ collect
def llm_cands(B):
    out = {}
    for d, labels in LLM_SRC:
        cj = json.load(open(os.path.join(CAMP, d, "cand.json")))
        for ck, v in cj.items():
            labs = [x for x in v["labels"] if labels is None or x in labels]
            if not labs:
                continue
            assert B.tokhash(v["tokens"]) == v["key"], ck
            e = out.setdefault(v["task"], OrderedDict()).setdefault(v["key"], {"tokens": v["tokens"], "src": []})
            e["src"] += ["%s:%s" % (d.split("/")[0] if not d.startswith("pilot-v0") else "pilot-v0/P1", x)
                         for x in labs]
    return out


def ga_designs(B, ga, anch):
    """every SIZED baselines-v1 GA call (seed 1) with its tokens: `found` carries them; the
    others are replayed from the recorded origin (parent key + edit descs, ga.edit_space) and
    verified against the recorded token key."""
    out, stat = {}, Counter()
    for r in B.read_jsonl(os.path.join(GA_RUN, "runs.jsonl")):
        text = {A["tok"]: A["text"] for A in anch.values()}
        toks = {A["tok"]: A["tokens"] for A in anch.values()}
        for c in r["calls"]:
            if c.get("prereject") or not c.get("i"):
                continue
            o = c["origin"]
            if "anchor" in o:
                k = anch[o["anchor"]]["tok"]
            else:
                t = text[o["parent"]]
                for desc in o["edits"]:
                    m = [x for x in ga.edit_space(t) if x["desc"] == desc]
                    assert len(m) == 1, (r["task"], c["key"], desc, len(m))
                    t = m[0]["netlist"]
                rt = ga.round_trip(t)
                assert rt["ok"] and B.tokhash(rt["tokens"]) == c["key"], ("GA replay mismatch", r["task"], c["key"])
                k = c["key"]
                text[k], toks[k] = t, rt["tokens"]
                stat["replayed"] += 1
            if c.get("feasible"):
                out.setdefault(r["task"], OrderedDict())[k] = {"tokens": toks[k], "src": ["ga:run%d" % r["ga_seed"]]}
                stat["feasible_calls"] += 1
        if r.get("found"):
            assert B.tokhash(r["found"]["tokens"]) == r["found"]["key"]
            assert r["found"]["key"] in out.get(r["task"], {})
    return out, stat


def collect():
    a0 = _lib()
    ga, pv0, B = a0.ga, a0.pv0, a0.B
    T, el = a0.eligible_tasks()
    anch = B.anchor_data()
    f2 = pv0.load_f2space(a0.PV0_RUN, anch)
    cache = ga.load_caches(list(EXTRA_CACHE))
    llm = llm_cands(B)
    gad, gstat = ga_designs(B, ga, anch)
    tasks, toks = OrderedDict(), {}
    for task, it in el.items():
        sp, pr = a0.spec_for(task)
        shown = it["shown_anchor"]
        cnt = Counter()
        aspace = OrderedDict(("lib:" + an, A["tokens"]) for an, A in anch.items())
        aspace.update(("edit:%s:%d:%s" % (shown, x["idx"], x["desc"]), x["tokens"]) for x in f2[shown] if x["rt_ok"])
        akeys = {B.tokhash(tk) for tk in aspace.values()}

        def row_of(tk, seed):
            jid = B.job_id(tk, sp, seed, B.BUDGET, PROF)
            return jid, cache.get(jid)

        def design(pool, did, tk, seed, src, r, jid):
            k = B.tokhash(tk)
            toks[jid] = {"tokens": tk, "spec": sp, "seed": seed}
            return OrderedDict(task=task, pool=pool, id=did, key=k, jid=jid, seed=seed, src=src,
                               orig_worst=pv0.Runner.margin(sp, r), orig_feasible=bool(r.get("feasible")),
                               orig_row_source=r.get("source"))
        A, seen = [], set()
        for did, tk in aspace.items():
            k = B.tokhash(tk)
            if k in seen:
                cnt["A_dup_key"] += 1
                continue
            seen.add(k)
            jid, r = row_of(tk, 1)
            if r is None:
                cnt["A_missing_row"] += 1
            elif not r.get("n_evals"):
                cnt["A_unsized"] += 1
            elif not r.get("feasible"):
                cnt["A_infeasible_s1"] += 1
            else:
                A.append(design("A", did, tk, 1, [did.split(":")[0]], r, jid))
        Bp = []
        wtk = a0.witness_tokens(task, it)
        wk = B.tokhash(wtk)
        W = OrderedDict(key=wk, in_A_space=wk in akeys)
        jid1, r1 = row_of(wtk, 1)
        W["s1_feasible"] = bool(r1 and r1.get("feasible"))
        if W["in_A_space"]:
            W["used"] = "no (in A space)"
        elif W["s1_feasible"]:
            Bp.append(design("B", "witness", wtk, 1, ["witness"], r1, jid1))
            W["used"] = "seed 1"
        else:
            jid2, r2 = row_of(wtk, 2)
            W["s2_feasible"] = bool(r2 and r2.get("feasible"))
            if W["s2_feasible"]:
                Bp.append(design("B", "witness", wtk, 2, ["witness(seed-2 row)"], r2, jid2))
                W["used"] = "seed 2 (infeasible at seed 1)"
            else:
                W["used"] = "no (infeasible at seeds 1 and 2)"
        other = OrderedDict()
        for srcmap in (gad.get(task, {}), llm.get(task, {})):
            for k, v in srcmap.items():
                e = other.setdefault(k, {"tokens": v["tokens"], "src": []})
                e["src"] += v["src"]
        for k, v in other.items():
            if k in akeys:
                cnt["B_in_A_space"] += 1
                continue
            if k == wk:
                cnt["B_is_witness"] += 1
                if Bp and Bp[0]["id"] == "witness":
                    Bp[0]["src"] = Bp[0]["src"] + v["src"]
                continue
            jid, r = row_of(v["tokens"], 1)
            if r is None:
                cnt["B_missing_s1_row"] += 1
            elif not r.get("n_evals"):
                cnt["B_unsized_s1"] += 1
            elif not r.get("feasible"):
                cnt["B_infeasible_s1"] += 1
            else:
                Bp.append(design("B", "other", v["tokens"], 1, sorted(set(v["src"])), r, jid))
        cnt["A_feasible"], cnt["B_feasible"] = len(A), len(Bp)
        sel = {}
        for name, pool in (("A", A), ("B", Bp)):
            pool.sort(key=lambda d: (-(d["orig_worst"] if d["orig_worst"] is not None else -9), d["key"]))
            for i, d in enumerate(pool):
                d["rank"] = i + 1
            sel[name] = pool[:CAP_POOL]
        W["selected"] = any(d["id"] == "witness" for d in sel["B"])
        tasks[task] = OrderedDict(task=task, tier=it["tier"], family=it["family"], band_type=it["band_type"],
                                  shown_anchor=shown, spec=rel(sp), spec_sha=pr["spec_sha"],
                                  n_A_space=len(akeys), counts=dict(cnt), witness=W,
                                  A=sel["A"], B=sel["B"],
                                  A_unselected=[{k: d[k] for k in ("id", "key", "orig_worst")} for d in A[CAP_POOL:]],
                                  B_unselected=[{k: d[k] for k in ("id", "key", "src", "orig_worst")}
                                                for d in Bp[CAP_POOL:]])
        print("%-24s %s A feas %3d sel %d | B feas %3d sel %d | witness %s%s" % (
            task, it["tier"], len(A), len(sel["A"]), len(Bp), len(sel["B"]), W["used"],
            "" if W["selected"] else " (not in top 6)"), flush=True)
    order = list(tasks)
    random.Random(ORDER_SEED).shuffle(order)
    out = OrderedDict(prereg=PREREG, built=now(), verifier=PROF, budget=B.BUDGET, pdk=B.PDK,
                      cap_per_pool=CAP_POOL, order_seed=ORDER_SEED, task_order=order, ga_replay=dict(gstat),
                      n_tasks=len(tasks), n_designs=sum(len(t["A"]) + len(t["B"]) for t in tasks.values()),
                      tasks=tasks)
    B.atomic_write(os.path.join(HERE, "pools.json"), jdump(out, indent=1))
    os.makedirs(STATE, exist_ok=True)
    B.atomic_write(os.path.join(STATE, "pools-tokens.json"), jdump(toks))
    print("tasks %d, designs %d (A %d, B %d), tasks with non-empty A and B: %d; GA replay %s" % (
        len(tasks), out["n_designs"], sum(len(t["A"]) for t in tasks.values()),
        sum(len(t["B"]) for t in tasks.values()),
        sum(1 for t in tasks.values() if t["A"] and t["B"]), dict(gstat)))


# ------------------------------------------------------------------ worker (subprocess)
def _cpu():
    a, b = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    return a.ru_utime + a.ru_stime + b.ru_utime + b.ru_stime


def _margins_signed(spec, m, mu_in, mu_wide):
    """signed normalized margins (MS._margins definitions; EX: a missing/NaN constrained metric or
    a failed sim counts as -1.0) + stability mu - 1 (in-band, wide)."""
    out = OrderedDict()
    for name, c in spec.constraints.items():
        if c.get("status") == "unsupported" or name == "mu_min":
            continue
        v = (m or {}).get(name)
        if not isinstance(v, (int, float)) or v != v:
            out[name] = -1.0
            continue
        sc = spec._scale(c)
        out[name] = (v - c["min"]) / sc if "min" in c else (c["max"] - v) / sc if "max" in c else None
    out = OrderedDict((k, v) for k, v in out.items() if v is not None)
    out["mu_inband-1"] = (mu_in - 1.0) if isinstance(mu_in, (int, float)) else -1.0
    out["mu_wide-1"] = (mu_wide - 1.0) if isinstance(mu_wide, (int, float)) else -1.0
    return out


def worker(stage, jobf, outf):
    t0, c0 = time.time(), _cpu()
    job = json.load(open(jobf))
    sys.path.insert(0, os.path.join(CAMP, "adversarial-v0", "EX"))
    import ex_lib as X                      # EX path, read-only reuse (rl-v1.1 window == rl-v1.2's)
    assert X.RL_WINDOW == X.PREP.VERIFIER_PROFILES[PROF]["STAB_WIDE_WINDOW"]
    rec = {"stage": stage, "jid": job["jid"], "error": None}
    try:
        if stage == "S":
            s = X.sized_run_v11(job["tokens"], job["spec"], int(job["seed"]), profile=PROF)
            res = s["res"]
            rec["res"] = res
            body = s.get("body")
            if body is not None and s.get("params") is not None:
                body = X.PREP.cp_ideal_body(body)[0]   # rl-v1.2 VERIFY_CP_IDEAL: the in-loop body
                st = {"jid": job["jid"], "spec": job["spec"], "seed": job["seed"], "body": body,
                      "params": s["params"]}
                p = os.path.join(SIZED, job["jid"] + ".json")
                with open(p + ".tmp", "w") as fh:
                    json.dump(st, fh)
                os.replace(p + ".tmp", p)
                rec["has_params"] = True
            else:
                rec["has_params"] = False
        else:
            st = json.load(open(os.path.join(SIZED, job["jid"] + ".json")))
            spec = X.load_spec(st["spec"])
            body, params = st["body"], st["params"]
            if stage == "C":
                nom = X.full_eval(body, params, spec)
                rec["nominal"] = {"metrics": nom.get("metrics"), "mu_inband": nom.get("mu_inband"),
                                  "mu_wide": nom.get("mu_wide"), "ok": nom.get("ok")}
                rec["corners"] = OrderedDict()
                for name, kw in CORNERS:
                    try:
                        r = X.corner_eval(body, params, spec, **kw)
                        rec["corners"][name] = {
                            "metrics": r.get("metrics"), "mu_inband": r.get("mu_inband"),
                            "mu_wide": r.get("mu_wide"), "perf_worst_viol": r.get("perf_worst"),
                            "perf_within_cushion": r.get("perf_within_cushion"), "stable": r.get("stable"),
                            "sim_fail": bool(r.get("sim_fail")), "error": r.get("error")}
                    except Exception:                                    # noqa: BLE001
                        rec["corners"][name] = {"metrics": None, "sim_fail": True,
                                                "error": traceback.format_exc()[-800:]}
            elif stage == "I":
                import iip3 as I3
                I3.OUT = _T                     # private_tmp() scratch under the job temp dir, not lna/out
                import size as SZ
                r = SZ.measure_iip3_tier3(body, params, spec, verbose=False)
                rec["iip3"] = r
                # per-Pin rows for the sanity check (re-run of the same sweep is NOT done; the tier-3
                # wrapper does not return rows, so record what it returns)
    except Exception:                                                    # noqa: BLE001
        rec["error"] = traceback.format_exc()[-3000:]
    rec["secs"] = round(time.time() - t0, 2)
    rec["cpu_s"] = round(_cpu() - c0, 2)
    with open(outf + ".tmp", "w") as fh:
        json.dump(rec, fh, default=repr)
    os.replace(outf + ".tmp", outf)


# ------------------------------------------------------------------ scheduler
CHILDREN = set()


def _kill_children():
    for pid in list(CHILDREN):
        try:
            os.killpg(pid, signal.SIGKILL)
        except OSError:
            pass


def _term(signum, _frame):
    _kill_children()
    os._exit(128 + signum)


class Runner:
    def __init__(self, nproc, deadline, kill_at):
        a0 = _lib()
        self.a0, self.ga, self.pv0, self.B, self.PS = a0, a0.ga, a0.pv0, a0.B, a0.PS
        self.nproc = max(1, min(BOX_MAX, nproc))
        self.deadline, self.kill_at = deadline, kill_at
        for d in (STATE, SIZED, RAWJ, RUN):
            os.makedirs(d, exist_ok=True)
        self.files = {s: os.path.join(RUN, f) for s, f in
                      (("S", "sizing.jsonl"), ("C", "corners.jsonl"), ("I", "iip3.jsonl"))}
        self.done = {s: {} for s in self.files}
        for s, p in self.files.items():
            for r in self.B.read_jsonl(p):
                self.done[s][r["jid"]] = r
        self.out = {s: self.B.SafeAppender(p) for s, p in self.files.items()}
        self.lock = threading.Lock()
        self.inflight = {}                     # (stage, jid) -> pid or None
        self.results = []
        self.era = self.B.era_stamp()
        self.n_new, self.cpu_new = Counter(), Counter()
        self._oth = (0.0, 0)
        self.t0 = time.time()

    def others(self):
        if time.time() - self._oth[0] < 5:
            return self._oth[1]
        n = 0
        for d in os.listdir("/proc"):
            if not d.isdigit():
                continue
            try:
                with open("/proc/%s/cmdline" % d, "rb") as fh:
                    cl = fh.read()
            except OSError:
                continue
            if b"bv2.py" in cl and b"worker" in cl:
                n += 1
            elif b"depth.py" in cl and b"worker" in cl and int(d) not in CHILDREN:
                try:                     # another runner's depth worker (ours are in CHILDREN)
                    st = open("/proc/%s/stat" % d).read().rsplit(")", 1)[1].split()
                    if int(st[1]) != os.getpid():
                        n += 1
                except (OSError, IndexError, ValueError):
                    pass
        self._oth = (time.time(), n)
        return n

    def cap(self):
        try:
            l1 = os.getloadavg()[0]
        except OSError:
            l1 = 0.0
        total = 4 if l1 > LOAD_HI else BOX_MAX
        return max(0, min(self.nproc, total - self.others()))

    def disk_ok(self):
        a, b = self.ga.free_gb(HERE), self.ga.free_gb(_T)
        low = (a is not None and a < self.B.DISK_MIN_FREE_GB) or (b is not None and b < self.B.TMP_MIN_FREE_GB)
        return not low and not self.B.DISK.paused() and not self.B.DISK.backoff_active()

    def _thread(self, stage, d, tok):
        jid = d["jid"]
        jf, of, ef = (os.path.join(RAWJ, "%s.%s.job.json" % (stage, jid)),
                      os.path.join(RAWJ, "%s.%s.out.json" % (stage, jid)),
                      os.path.join(RAWJ, "%s.%s.err" % (stage, jid)))
        t0 = time.time()
        job = {"jid": jid}
        if stage == "S":
            job.update(tokens=tok["tokens"], spec=tok["spec"], seed=tok["seed"])
        json.dump(job, open(jf, "w"))
        killed = False
        with open(ef, "w") as efh:
            p = subprocess.Popen([sys.executable, os.path.abspath(__file__), "worker", stage, jf, of],
                                 stdout=subprocess.DEVNULL, stderr=efh, start_new_session=True)
            with self.lock:
                CHILDREN.add(p.pid)
                self.inflight[(stage, jid)] = p.pid
            to = max(10, min(TIMEOUT[stage], (self.kill_at or 1e18) - time.time()))
            try:
                p.wait(timeout=to)
            except subprocess.TimeoutExpired:
                killed = time.time() >= (self.kill_at or 1e18) - 1
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except OSError:
                    pass
                p.wait()
            with self.lock:
                CHILDREN.discard(p.pid)
        row = None
        if os.path.exists(of):
            rec = json.load(open(of))
            row = self.row_of(stage, d, rec)
        elif not killed:
            err = open(ef).read()[-800:] if os.path.exists(ef) else ""
            row = {"stage": stage, "jid": jid, "crashed": True, "secs": round(time.time() - t0, 1),
                   "stderr_tail": err}
        for f in (jf, of, ef):
            try:
                os.remove(f)
            except OSError:
                pass
        with self.lock:
            self.inflight.pop((stage, jid), None)
            if row is not None:            # killed at --kill-at: no row (re-run on resume)
                self.results.append((stage, jid, row))

    def row_of(self, stage, d, rec):
        base = OrderedDict(stage=stage, jid=d["jid"], task=d["task"], pool=d["pool"], key=d["key"], seed=d["seed"],
                           secs=rec.get("secs"), cpu_s=rec.get("cpu_s"), error=(rec.get("error") or None),
                           era=self.era, ts=now())
        if stage == "S":
            r = {"jid": d["jid"], "secs": rec.get("secs"), "res": rec.get("res"), "error": rec.get("error")}
            s = self.ga.norm_summ(self.PS.summ(r))
            spec = os.path.join(REPO, d["spec"])
            base.update(s, has_params=rec.get("has_params"),
                        worst=self.pv0.Runner.margin(spec, rec.get("res") or {}) if s.get("n_evals") else None,
                        stab_winner_replaced=(rec.get("res") or {}).get("stab_winner_replaced"))
            base["secs"], base["error"] = rec.get("secs"), rec.get("error")
        elif stage == "C":
            base.update(nominal=rec.get("nominal"), corners=rec.get("corners"))
        else:
            base.update(iip3=rec.get("iip3"))
        return base

    def drain(self):
        with self.lock:
            res, self.results = self.results, []
        for stage, jid, row in res:
            self.out[stage].write(jdump(row) + "\n")
            self.done[stage][jid] = row
            self.n_new[stage] += 1
            self.cpu_new[stage] += row.get("cpu_s") or row.get("secs") or 0.0

    def run(self, designs, toks):
        """designs: priority-ordered list. S first; C and I once S has sized params."""
        last = 0.0
        while True:
            self.drain()
            t = time.time()
            if self.kill_at and t >= self.kill_at:
                with self.lock:
                    n = len(self.inflight)
                _kill_children()
                time.sleep(2)
                self.drain()
                print("[depth %s] KILL-AT reached: killed %d running workers (no rows; re-run on resume)" % (
                    now(), n), flush=True)
                break
            launch_ok = not (self.deadline and t >= self.deadline)
            todo = []
            for d in designs:
                jid = d["jid"]
                if jid not in self.done["S"]:
                    todo.append(("S", d))
                    continue
                srow = self.done["S"][jid]
                if not srow.get("has_params") or not os.path.exists(os.path.join(SIZED, jid + ".json")):
                    continue
                for st in ("C", "I"):
                    if jid not in self.done[st]:
                        todo.append((st, d))
            with self.lock:
                todo = [(s, d) for s, d in todo if (s, d["jid"]) not in self.inflight]
                active = len(self.inflight)
            if not todo and active == 0:
                print("[depth %s] all stages done" % now(), flush=True)
                break
            if not launch_ok and active == 0:
                print("[depth %s] DEADLINE reached: no new launches; %d stage jobs pending (resume to finish)"
                      % (now(), len(todo)), flush=True)
                break
            if launch_ok and todo:
                c = self.cap()
                started = 0
                for s, d in todo:
                    if active + started >= c:
                        break
                    if not self.disk_ok():
                        time.sleep(30)
                        break
                    with self.lock:
                        self.inflight[(s, d["jid"])] = None
                    threading.Thread(target=self._thread, args=(s, d, toks[d["jid"]]), daemon=True).start()
                    started += 1
            for o in self.out.values():
                o.flush()
            if time.time() - last > 300:
                last = time.time()
                print("[depth %s] active %d (cap %d, other workers %d), todo %d, new S/C/I %d/%d/%d, new CPU %.2f h,"
                      " wall %.1f min, load1 %.1f" % (
                          now(), active, self.cap(), self.others(), len(todo), self.n_new["S"], self.n_new["C"],
                          self.n_new["I"], sum(self.cpu_new.values()) / 3600, (time.time() - self.t0) / 60,
                          os.getloadavg()[0]), flush=True)
            time.sleep(0.5)
        for o in self.out.values():
            while o.pending():
                o.flush()
                time.sleep(2)
        print("[depth %s] exit: new S/C/I %d/%d/%d, new CPU %.2f h (S %.2f, C %.2f, I %.2f), wall %.1f min" % (
            now(), self.n_new["S"], self.n_new["C"], self.n_new["I"], sum(self.cpu_new.values()) / 3600,
            self.cpu_new["S"] / 3600, self.cpu_new["C"] / 3600, self.cpu_new["I"] / 3600,
            (time.time() - self.t0) / 60), flush=True)


def ordered_designs(pools, ntasks=None, sanity=False):
    out = []
    order = pools["task_order"][:ntasks] if ntasks else pools["task_order"]
    for task in order:
        t = pools["tasks"][task]
        ds = ([t["B"][0]] if t["B"] else []) if sanity else (t["A"] + t["B"])
        for d in ds:
            out.append(dict(d, spec=t["spec"]))
    return out


def run(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--nproc", type=int, default=8)
    ap.add_argument("--deadline", type=float, default=None, help="epoch: no job launched at/after it")
    ap.add_argument("--kill-at", type=float, default=None, help="epoch: running workers killed")
    ap.add_argument("--ntasks", type=int, default=None)
    ap.add_argument("--sanity", action="store_true")
    a = ap.parse_args(argv)
    if a.deadline and a.kill_at is None:
        a.kill_at = a.deadline + 12 * 60
    if a.deadline and time.time() >= a.deadline:
        print("deadline already passed; nothing launched")
        return
    signal.signal(signal.SIGTERM, _term)
    signal.signal(signal.SIGINT, _term)
    pools = json.load(open(os.path.join(HERE, "pools.json")))
    toks = json.load(open(os.path.join(STATE, "pools-tokens.json")))
    designs = ordered_designs(pools, a.ntasks, a.sanity)
    R = Runner(a.nproc, a.deadline, a.kill_at)
    print("[depth %s] %d designs (%s tasks%s), done S/C/I %d/%d/%d, nproc %d, deadline %s, kill-at %s" % (
        now(), len(designs), a.ntasks or "all", ", sanity" if a.sanity else "",
        sum(d["jid"] in R.done["S"] for d in designs), sum(d["jid"] in R.done["C"] for d in designs),
        sum(d["jid"] in R.done["I"] for d in designs), R.nproc,
        time.strftime("%H:%M:%S", time.localtime(a.deadline)) if a.deadline else "-",
        time.strftime("%H:%M:%S", time.localtime(a.kill_at)) if a.kill_at else "-"), flush=True)
    R.run(designs, toks)


# ------------------------------------------------------------------ summarize
def corner_summary(spec, crow):
    """corner worst margin = min over the 4 corners of the signed worst normalized margin
    (performance) and mu - 1 (in-band, wide); per-corner detail."""
    per = OrderedDict()
    for name, _kw in CORNERS:
        c = (crow.get("corners") or {}).get(name) or {}
        if c.get("sim_fail") or not c.get("metrics"):
            per[name] = {"worst": -1.0, "binding": "sim_fail"}
            continue
        mg = _margins_signed(spec, c["metrics"], c.get("mu_inband"), c.get("mu_wide"))
        b = min(mg, key=mg.get)
        per[name] = {"worst": mg[b], "binding": b, "perf_within_cushion_EX": c.get("perf_within_cushion"),
                     "stable_EX": c.get("stable")}
    w = min(per, key=lambda k: per[k]["worst"])
    nom = crow.get("nominal") or {}
    nmg = (_margins_signed(spec, nom.get("metrics"), nom.get("mu_inband"), nom.get("mu_wide"))
           if nom.get("metrics") else None)
    return per[w]["worst"], w, per, (min(nmg.values()) if nmg else None)


def _f(x, n=3):
    return "-" if x is None else ("%.*f" % (n, x))


def summarize():
    a0 = _lib()
    B = a0.B
    sys.path.insert(0, os.path.join(REPO, "kaggle"))
    sys.path.insert(0, os.path.join(REPO, "lna"))
    from spec import Spec
    import size as SZ
    pools = json.load(open(os.path.join(HERE, "pools.json")))
    done = {}
    for s, f in (("S", "sizing.jsonl"), ("C", "corners.jsonl"), ("I", "iip3.jsonl")):
        done[s] = {}
        for r in B.read_jsonl(os.path.join(RUN, f)):
            done[s][r["jid"]] = r
    drows, trows = [], []
    for task in pools["task_order"]:
        t = pools["tasks"][task]
        spec = SZ._spec_for_sizing(os.path.join(REPO, t["spec"]), nf_gate=None, pdk=B.PDK)
        _ = Spec
        best = {}
        for pool in ("A", "B"):
            pr = []
            for d in t[pool]:
                s, c, i = done["S"].get(d["jid"]), done["C"].get(d["jid"]), done["I"].get(d["jid"])
                o = OrderedDict(task=task, tier=t["tier"], family=t["family"], pool=pool, id=d["id"],
                                key=d["key"], jid=d["jid"], seed=d["seed"], source=",".join(d["src"]),
                                orig_worst=d["orig_worst"])
                o["resized"] = s is not None
                if s:
                    o["resized_feasible"], o["resized_worst"] = s.get("feasible"), s.get("worst")
                    o["resize_reproduces"] = bool(s.get("feasible") == d["orig_feasible"] and s.get("worst") is not None
                                                  and d["orig_worst"] is not None
                                                  and abs(s["worst"] - d["orig_worst"]) < 1e-4)
                    o["has_params"] = s.get("has_params")
                    o["S_cpu_s"] = s.get("cpu_s")
                if c:
                    cw, cwhich, per, nomw = corner_summary(spec, c)
                    o["nominal_reeval_worst"] = nomw
                    o["corner_worst"], o["corner_worst_at"] = cw, cwhich
                    o["corners"] = per
                    o["C_cpu_s"] = c.get("cpu_s")
                if i:
                    r = i.get("iip3") or {}
                    o["iip3_ok"] = bool(r.get("ok"))
                    o["iip3_dbm"] = r.get("iip3_dbm") if r.get("ok") else None
                    o["iip3_slope"], o["iip3_slope_ok"] = r.get("slope"), r.get("slope_ok")
                    o["iip3_kept"], o["iip3_gain_ss_db"] = r.get("kept"), r.get("gain_ss_db")
                    o["iip3_why"] = r.get("why") or (i.get("error") or "")[-200:] or None
                    o["I_cpu_s"] = i.get("cpu_s")
                o["usable"] = bool(s and s.get("feasible") and s.get("has_params"))
                pr.append(o)
                drows.append(o)
            u = [o for o in pr if o["usable"]]
            cc = [o for o in u if o.get("corner_worst") is not None]
            ii = [o for o in u if o.get("iip3_dbm") is not None]
            best[pool] = {"n_sel": len(t[pool]), "n_usable": len(u),
                          "n_done_C": len(cc), "n_done_I": len(ii),
                          "complete": all(o.get("resized") for o in pr) and
                          all(("corner_worst" in o and "iip3_ok" in o) for o in pr if o.get("has_params")),
                          "best_corner": max(cc, key=lambda o: o["corner_worst"]) if cc else None,
                          "best_iip3": max(ii, key=lambda o: o["iip3_dbm"]) if ii else None,
                          "any_corner_pass": any(o["corner_worst"] >= 0 for o in cc)}
        r = OrderedDict(task=task, tier=t["tier"], family=t["family"], nA=len(t["A"]), nB=len(t["B"]),
                        witness=t["witness"]["used"], witness_selected=t["witness"]["selected"],
                        complete=best["A"]["complete"] and best["B"]["complete"])
        for pool in ("A", "B"):
            b = best[pool]
            r[pool + "_usable"] = b["n_usable"]
            r[pool + "_corner"] = b["best_corner"]["corner_worst"] if b["best_corner"] else None
            r[pool + "_corner_id"] = (b["best_corner"]["id"] + ":" + b["best_corner"]["key"]) if b["best_corner"] else None
            r[pool + "_iip3"] = b["best_iip3"]["iip3_dbm"] if b["best_iip3"] else None
            r[pool + "_iip3_id"] = (b["best_iip3"]["id"] + ":" + b["best_iip3"]["key"]) if b["best_iip3"] else None
            r[pool + "_any_corner_pass"] = b["any_corner_pass"]
        ca, cb = r["A_corner"], r["B_corner"]
        r["eligible_corner"] = bool(t["A"] and t["B"] and ca is not None and cb is not None and r["complete"])
        r["depth_corner"] = bool(r["eligible_corner"] and (cb >= ca + CORNER_DELTA or (cb >= 0 and ca < 0)))
        r["reverse_corner"] = bool(r["eligible_corner"] and (ca >= cb + CORNER_DELTA or (ca >= 0 and cb < 0)))
        ia, ib = r["A_iip3"], r["B_iip3"]
        r["eligible_iip3"] = bool(t["A"] and t["B"] and ia is not None and ib is not None and r["complete"])
        r["depth_iip3"] = bool(r["eligible_iip3"] and ib >= ia + IIP3_DELTA)
        r["reverse_iip3"] = bool(r["eligible_iip3"] and ia >= ib + IIP3_DELTA)
        trows.append(r)
    with open(os.path.join(HERE, "depth-designs.jsonl"), "w") as fh:
        for o in drows:
            fh.write(jdump(o) + "\n")
    with open(os.path.join(HERE, "depth-tasks.jsonl"), "w") as fh:
        for o in trows:
            fh.write(jdump(o) + "\n")

    def verdict(n):
        return "gives depth (>= 10)" if n >= 10 else "weak (5-9)" if n >= 5 else "no depth (< 5)"
    nonempty = [r for r in trows if r["nA"] and r["nB"]]
    rd = OrderedDict()
    for m in ("corner", "iip3"):
        el = [r for r in trows if r["eligible_" + m]]
        nd, nr = sum(r["depth_" + m] for r in el), sum(r["reverse_" + m] for r in el)
        rd[m] = OrderedDict(n_tasks_eligible=len(el), B_beats_A=nd, A_beats_B=nr,
                            fraction_B_beats_A=round(nd / len(el), 3) if el else None,
                            verdict=verdict(nd) + ("" if nd > nr else " -- BUT B > A not more often than A > B "
                                                   "(control fails: no depth)"),
                            depth=bool(nd >= 10 and nd > nr),
                            tasks_B_beats_A=[r["task"] for r in el if r["depth_" + m]],
                            tasks_A_beats_B=[r["task"] for r in el if r["reverse_" + m]])
    cpu = Counter()
    for s in done:
        for r in done[s].values():
            cpu[s] += r.get("cpu_s") or r.get("secs") or 0.0
    us = [o for o in drows if o.get("resized")]
    summ = OrderedDict(
        prereg=PREREG, built=now(), verifier=PROF, task_order_seed=ORDER_SEED,
        n_tasks=len(trows), n_tasks_nonempty_A_and_B=len(nonempty),
        n_tasks_complete=sum(r["complete"] for r in trows),
        n_tasks_complete_nonempty=sum(r["complete"] for r in nonempty),
        n_designs_selected=len(drows), n_designs_resized=len(us),
        n_resize_reproduces=sum(bool(o.get("resize_reproduces")) for o in us),
        n_resize_infeasible=sum(not o.get("resized_feasible") for o in us),
        n_corner_done=sum("corner_worst" in o for o in drows),
        n_iip3_done=sum("iip3_ok" in o for o in drows), n_iip3_ok=sum(bool(o.get("iip3_ok")) for o in drows),
        n_iip3_slope_ok=sum(bool(o.get("iip3_slope_ok")) for o in drows if o.get("iip3_ok")),
        n_corner_pass_all=sum(1 for o in drows if (o.get("corner_worst") or -1) >= 0),
        readings=rd, cpu_h={k: round(v / 3600, 3) for k, v in cpu.items()},
        cpu_h_total=round(sum(cpu.values()) / 3600, 3))
    B.atomic_write(os.path.join(HERE, "depth-summary.json"), jdump(summ, indent=1))
    B.atomic_write(os.path.join(HERE, "depth-tables.md"), tables_md(trows, drows, summ))
    print(jdump({k: summ[k] for k in ("n_tasks_nonempty_A_and_B", "n_tasks_complete", "n_designs_resized",
                                       "n_resize_reproduces", "n_iip3_ok", "readings", "cpu_h_total")}, indent=1))


def tables_md(trows, drows, s):
    L = ["# depth-probes-v1 -- tables", "",
         "Pre-reg %s. Built %s by `depth.py summarize`. Tasks listed in the seeded run order (`%s`)." % (
             s["prereg"], s["built"], s["task_order_seed"]), "",
         "## Readings (tasks with non-empty A and B and complete measurements)", "",
         "| metric | eligible tasks | B beats A | A beats B (control) | fraction B>A | verdict |",
         "|---|---|---|---|---|---|"]
    for m, lab in (("corner", "corner worst margin (B >= A + 0.10, or B passes all corners and no A does)"),
                   ("iip3", "IIP3 (B >= A + 3 dB)")):
        r = s["readings"][m]
        L.append("| %s | %d | %d | %d | %s | %s |" % (lab, r["n_tasks_eligible"], r["B_beats_A"], r["A_beats_B"],
                                                      _f(r["fraction_B_beats_A"]), r["verdict"]))
    L += ["", "Designs: %d selected, %d re-sized (%d reproduce the cached row's feasibility and worst margin "
          "within 1e-4; %d re-sized infeasible), corners done %d, IIP3 done %d (ok %d, slope within 3 +/- 0.3: %d). "
          "Designs passing all 4 corners: %d. CPU %.2f h (%s)." % (
              s["n_designs_selected"], s["n_designs_resized"], s["n_resize_reproduces"], s["n_resize_infeasible"],
              s["n_corner_done"], s["n_iip3_done"], s["n_iip3_ok"], s["n_iip3_slope_ok"], s["n_corner_pass_all"],
              s["cpu_h_total"], ", ".join("%s %.2f" % kv for kv in s["cpu_h"].items())), "",
          "## Per task (best-A vs best-B)", "",
          "Corner value = best over the pool of the corner worst margin (min over -40 C, +85 C, VDD x0.9, x1.1 of "
          "the signed worst normalized spec margin and mu - 1). IIP3 = best in-band IIP3 (dBm).", "",
          "| task | tier | family | nA | nB | witness | A corner | B corner | B-A | depth? | reverse? | A IIP3 | "
          "B IIP3 | B-A dB | depth? | reverse? | complete |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in trows:
        dc = (r["B_corner"] - r["A_corner"]) if r["A_corner"] is not None and r["B_corner"] is not None else None
        di = (r["B_iip3"] - r["A_iip3"]) if r["A_iip3"] is not None and r["B_iip3"] is not None else None
        L.append("| %s | %s | %s | %d | %d | %s%s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["task"], r["tier"], r["family"], r["nA"], r["nB"], r["witness"],
            "" if r["witness_selected"] else " (not top 6)", _f(r["A_corner"]), _f(r["B_corner"]), _f(dc),
            "**yes**" if r["depth_corner"] else "no", "yes" if r["reverse_corner"] else "no",
            _f(r["A_iip3"], 2), _f(r["B_iip3"], 2), _f(di, 2), "**yes**" if r["depth_iip3"] else "no",
            "yes" if r["reverse_iip3"] else "no", "yes" if r["complete"] else "**no**"))
    L += ["", "## Per design", "",
          "| task | pool | id | key | source | orig worst | re-sized worst | corner worst (at) | T-40 | T85 | V0.9 | "
          "V1.1 | IIP3 dBm | slope |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for o in drows:
        per = o.get("corners") or {}
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            o["task"], o["pool"], o["id"].replace("|", "/"), o["key"], o["source"].replace("|", "/")[:60],
            _f(o["orig_worst"], 4), _f(o.get("resized_worst"), 4),
            ("%s (%s)" % (_f(o.get("corner_worst")), o.get("corner_worst_at"))) if "corner_worst" in o else "-",
            *[("%s %s" % (_f(per[k]["worst"]), per[k]["binding"])) if k in per else "-"
              for k in ("T-40", "T85", "V0.9", "V1.1")],
            _f(o.get("iip3_dbm"), 2) if o.get("iip3_ok") else ("fail" if "iip3_ok" in o else "-"),
            _f(o.get("iip3_slope"), 2)))
    return "\n".join(L) + "\n"


def status():
    a0 = _lib()
    B = a0.B
    pools = json.load(open(os.path.join(HERE, "pools.json")))
    designs = ordered_designs(pools)
    c = Counter()
    for s, f in (("S", "sizing.jsonl"), ("C", "corners.jsonl"), ("I", "iip3.jsonl")):
        d = {r["jid"] for r in B.read_jsonl(os.path.join(RUN, f))}
        c[s] = sum(x["jid"] in d for x in designs)
    print("designs %d; done S %d, C %d, I %d" % (len(designs), c["S"], c["C"], c["I"]))


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "worker":
        worker(a[1], a[2], a[3])
    elif a[0] == "collect":
        collect()
    elif a[0] == "run":
        run(a[1:])
    elif a[0] == "summarize":
        summarize()
    elif a[0] == "status":
        status()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()

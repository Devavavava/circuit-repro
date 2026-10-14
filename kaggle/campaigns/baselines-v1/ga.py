#!/usr/bin/env python
"""baselines-v1 part G: mutation-only GA at equal SPICE budget (kaggle/PREREG-BASELINES-V1.md, b8fbcf20a).

  ga.py run <nproc<=8> [--out DIR] [--tasks t1,t2,..] [--seeds 1,2,3] [--bmax 64]
            [--extra-cache results.jsonl[,..]]
        one GA run per (task, GA seed) over the held-out 58 (keys of pilot-v0/eval/searchbar.json):
          gen 0   the 5 library anchors a1-a5 in a seeded random order, sized one by one
                  (seed 1), stop at the first feasible;
          then    (mu+lambda), mu = 4, lambda = 4: parents = the mu best sized designs by
                  fitness (= best mu of everything sized so far: equivalent for mu+lambda);
                  child = size-2 tournament parent + 1 random edit, or 2 random edits with
                  probability 0.5; edit = uniform over bv2's E-c single-edit enumeration
                  (pilot-v0 pv0.f2_cands == bv2.Pipeline.f2space_build: add R/C/L on every
                  unordered net pair, delete any element) of the parent's netlist; a child that
                  does not round-trip, is pre-rejected (topology limits / structural degeneracy /
                  port-DC pre-filter, pv0.Runner.pre_reject, 0 calls) or already seen (token
                  hash) is redrawn, <= 50 tries per slot;
          fitness pv0.Runner.margin (worst normalized margin incl. mu_wide - 1) at the task spec,
                  seed 1; unsized / pre-rejected = -1e6;
          stop    first seed-1-feasible sized call, or B_max = 64 sized calls.
        then seeds 2 and 3 for every found design (confirmation).
        Worker = pilot-v0's (bv2 worker -> bench_anchor_prep.smoke_run(tokens, spec, seed, 2500,
        "bptm45", profile="rl-v1.2")); spec = pilot-v0/P1/specs/<task>.yaml (sha == the eval
        prompt's spec_sha). Exact-key reuse (read-only) of the pilot-v0 / AMENDMENT-3 rl-v1.2 caches,
        the pilot-v0 P1, pilot-v1 and exit-r1 score rows (+ --extra-cache); a reused row counts
        as a call with its recorded seconds. <= nproc processes and <= 8 sizing workers on the BOX in
        total (4 while load1 > 22), other jobs' bv2 workers counted from /proc. D32 disk
        robustness (bv2.SafeAppender rows, no launch below 5 GB free on the output fs or 1 GB in
        $TMPDIR, a worker that left no result during disk trouble is re-queued, never recorded).
        Resumable: results.jsonl is an exact-key (jid) cache, finished runs are in runs.jsonl,
        an unfinished run is replayed deterministically through the cache.
  ga.py summarize [--out DIR]
        -> ga-summary.json, ga-tables.md next to this file (run dir = default --out).
"""
import argparse
import hashlib
import json
import os
import random
import signal
import statistics
import subprocess
import sys
import threading
import time
from collections import Counter, OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CAMP = os.path.join(REPO, "kaggle", "campaigns")
PV0D = os.path.join(CAMP, "pilot-v0")
P1 = os.path.join(PV0D, "P1")
EVAL = os.path.join(PV0D, "eval")
# temp files (worker job/out files, ngspice scratch) never in /tmp: GA_TMPDIR > TMPDIR > job tmp
_T = os.environ.get("GA_TMPDIR") or os.environ.get("TMPDIR") \
    or os.path.expanduser("~/.claude/jobs/7cd7ffc3/tmp/ga/tmp")
os.makedirs(_T, exist_ok=True)
os.environ["TMPDIR"] = _T
sys.path.insert(0, P1)
sys.path.insert(0, PV0D)
sys.path.insert(0, os.path.join(CAMP, "pilot-v1"))
import pv0  # noqa: E402
import p1_score as PS  # noqa: E402

B = pv0.B
PROF = "rl-v1.2"
RAW = os.path.join(_T, "ga-raw")
LOAD_HI = 22.0
MU, LAM = 4, 4
BMAX = 64
TRIES = 50
P_TWO = 0.5
ANCH = ("a1", "a2", "a3", "a4", "a5")
WORKER_TIMEOUT_S = 3600
BOX_MAX = 8                       # box-wide sizing-process cap (shared with other jobs' workers)
NEG = -1e6
DEF_OUT = os.path.join(HERE, "ga", "run")
BS = (1, 2, 4, 8, 16, 32, 64)
KS = (1, 2, 4, 8)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def rel(p):
    return os.path.relpath(p, REPO)


# ------------------------------------------------------------------ inputs
def tasks_and_tiers():
    sb = json.load(open(os.path.join(EVAL, "searchbar.json")))["items"]
    ti = json.load(open(os.path.join(EVAL, "tiers.json")))["items"]
    return OrderedDict((t, ti[t]["tier"]) for t in sorted(sb))


def spec_of(task):
    sp = os.path.join(P1, "specs", task + ".yaml")
    pr = json.load(open(os.path.join(EVAL, "prompts", task + ".json")))
    assert B.spec_sha(sp) == pr["spec_sha"] == B.spec_sha(os.path.join(EVAL, pr["spec_file"])), \
        ("spec drift", task)
    return sp


def norm_summ(d):
    keep = ("feasible", "secs", "n_evals", "mu_min_wide", "infeasible_reason", "port_dc_pass",
            "metrics", "verifier", "error", "crashed")
    return {k: d.get(k) for k in keep if k in d}


def load_caches(extra=()):
    """exact-key (jid) caches, read-only: raw rl-v1.2 rows of pilot-v0 / AMENDMENT-3 (p1_score.caches)
    and the summarized score rows of pilot-v0 P1, pilot-v1, exit-r1 (+ extra results files)."""
    c = {}
    for jid, r in PS.caches().items():
        c[jid] = dict(norm_summ(PS.summ(r)), source="cache:" + r["_src"])
    for p in [os.path.join(P1, "score", "score.jsonl"), os.path.join(CAMP, "pilot-v1", "score", "score.jsonl"),
              os.path.join(CAMP, "exit-r1", "score", "score.jsonl")] + list(extra):
        for r in B.read_jsonl(p):
            if not r.get("jid") or r["jid"] in c or r.get("crashed") or r.get("secs") is None:
                continue
            if r.get("verifier") not in (None, PROF) or r.get("profile") not in (None, PROF):
                continue
            c[r["jid"]] = dict(norm_summ(r), source="cache:" + rel(p))
    return c


# ------------------------------------------------------------------ design ops
_RT = {}


def round_trip(text):
    k = hashlib.sha256(text.encode()).hexdigest()
    if k not in _RT:
        import proposal as P
        rt = P.round_trip(text)
        _RT[k] = {"ok": bool(rt.get("ok")), "tokens": rt.get("tokens"), "wl": rt.get("wl_hash"),
                  "error": rt.get("error")}
    return _RT[k]


def elem_names(text):
    out = set()
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s[0] in "#*":
            continue
        p = s.split()
        if len(p) > 1:
            out.add(p[1])
    return out


def edit_space(text):
    """bv2 E-c single-edit enumeration of `text` (pv0.f2_cands == bv2.Pipeline.f2space_build).
    D-G2: an added element whose fixed name `{T}x` already exists in the parent (an earlier GA
    add) is renamed `{T}x2`, `{T}x3`, ... (names do not enter the token sequence)."""
    cands = pv0.f2_cands({"text": text})
    names = elem_names(text)
    for c in cands:
        if c["kind"] != "add":
            continue
        typ = c["desc"].split()[1]
        nm = typ + "x"
        if nm in names:
            n = 2
            while "%sx%d" % (typ, n) in names:
                n += 1
            nl = c["netlist"].rstrip("\n").split("\n")
            parts = nl[-1].split()
            assert parts[0] == typ and parts[1] == nm, nl[-1]
            parts[1] = "%sx%d" % (typ, n)
            nl[-1] = " ".join(parts)
            c["netlist"] = "\n".join(nl) + "\n"
    return cands


_PR = pv0.Runner.__new__(pv0.Runner)


def pre_reject(tokens, spec):
    return _PR.pre_reject(tokens, spec)


def fitness(spec, row):
    if not row or row.get("crashed") or not row.get("n_evals"):
        return NEG
    w = pv0.Runner.margin(spec, {"metrics": row.get("metrics") or {}, "mu_min_wide": row.get("mu_min_wide")})
    return NEG if w is None else float(w)


def sized(row):
    """a SIZED call (counts against the budget): the sizer ran (n_evals > 0) or the worker crashed."""
    return bool(row.get("crashed") or row.get("n_evals"))


# ------------------------------------------------------------------ one GA run
def ga_run(task, tier, gseed, spec, anch, bmax, out):
    """generator: yields lists of job dicts, receives the list of result rows; fills `out`."""
    rng = random.Random("baselines-v1/ga|%s|%d" % (task, gseed))
    seen = set()
    designs = []                       # sized designs: dict(key, text, tokens, fit, i)
    calls = []                         # every sizer job (sized or not), in budget order
    stats = Counter()
    n = [0]
    found = [None]

    def job(tokens, key):
        return {"task": task, "key": key, "seed": 1, "tokens": tokens, "spec": spec,
                "jid": B.job_id(tokens, spec, 1, B.BUDGET, PROF)}

    def record(gen, slot, d, row, origin):
        rec = OrderedDict(gen=gen, slot=slot, key=d["key"], wl=d.get("wl"), origin=origin,
                          jid=d["jid"], source=row.get("source"), n_evals=row.get("n_evals"),
                          crashed=bool(row.get("crashed")), feasible=bool(row.get("feasible")),
                          secs=row.get("secs"), fit=None, i=None)
        if sized(row):
            n[0] += 1
            rec["i"] = n[0]
            rec["fit"] = fitness(spec, row)
            designs.append(dict(key=d["key"], text=d["text"], tokens=d["tokens"], fit=rec["fit"], i=n[0]))
            if rec["feasible"] and found[0] is None:
                found[0] = dict(i=n[0], key=d["key"], wl=d.get("wl"), tokens=d["tokens"], text=d["text"],
                                origin=origin, jid=d["jid"])
        else:
            stats["unsized_worker"] += 1
        calls.append(rec)

    # ---- gen 0: library anchors, seeded random order, one by one
    order = list(ANCH)
    rng.shuffle(order)
    for a in ANCH:
        seen.add(anch[a]["tok"])
    for a in order:
        A = anch[a]
        if pre_reject(A["tokens"], spec):
            stats["gen0_prereject"] += 1
            calls.append(OrderedDict(gen=0, slot=None, key=A["tok"], origin={"anchor": a}, prereject=True))
            continue
        j = job(A["tokens"], A["tok"])
        (row,) = yield [j]
        record(0, None, dict(j, text=A["text"], wl=A["wl"]), row, {"anchor": a})
        if found[0] or n[0] >= bmax:
            break
    # ---- (mu + lambda)
    gen = 0
    status = None
    while not found[0] and n[0] < bmax:
        gen += 1
        par = sorted(designs, key=lambda d: (-d["fit"], d["i"]))[:MU]
        if not par:
            status = "no_sized_parent"
            break
        kids = []
        for slot in range(min(LAM, bmax - n[0])):
            kid = None
            for _t in range(TRIES):
                stats["draws"] += 1
                if len(par) >= 2:
                    p1, p2 = rng.sample(par, 2)
                    p = p1 if (p1["fit"], -p1["i"]) >= (p2["fit"], -p2["i"]) else p2
                else:
                    p = par[0]
                ne = 2 if rng.random() < P_TWO else 1
                text, descs = p["text"], []
                for _e in range(ne):
                    c = rng.choice(edit_space(text))
                    text = c["netlist"]
                    descs.append(c["desc"])
                rt = round_trip(text)
                if not rt["ok"]:
                    stats["redraw_roundtrip"] += 1
                    continue
                k = B.tokhash(rt["tokens"])
                if k in seen:
                    stats["redraw_seen"] += 1
                    continue
                seen.add(k)
                if pre_reject(rt["tokens"], spec):
                    stats["redraw_prereject"] += 1
                    continue
                kid = dict(job(rt["tokens"], k), text=text, wl=rt["wl"],
                           origin={"parent": p["key"], "parent_i": p["i"], "edits": descs})
                break
            if kid is None:
                stats["slot_exhausted"] += 1
                continue
            kids.append((slot, kid))
        if not kids:
            status = "stalled"
            break
        rows = yield [k for _s, k in kids]
        for (slot, k), row in zip(kids, rows):
            record(gen, slot, k, row, k["origin"])
        # stop at the first feasible: calls after it in this generation are recorded but not counted
    ff = found[0]
    spice = None
    if ff:
        spice = sum((c.get("secs") or 0.0) for c in calls if c.get("i") and c["i"] <= ff["i"]) / 60.0
    out.update(OrderedDict(
        task=task, tier=tier, ga_seed=gseed, gen0_order=order, n_gens=gen,
        status=status or ("found" if ff else "budget"), first_feasible_call=ff["i"] if ff else None,
        calls_counted=ff["i"] if ff else n[0], sized_calls_total=n[0],
        spice_min_to_first=round(spice, 3) if spice is not None else None,
        spice_min_total=round(sum((c.get("secs") or 0.0) for c in calls if c.get("i")) / 60.0, 3),
        new_sized_secs=round(sum((c.get("secs") or 0.0) for c in calls
                                 if c.get("i") and c.get("source") == "sized"), 1),
        found=ff, stats=dict(stats), calls=calls, ts=now()))


# ------------------------------------------------------------------ scheduler
CHILDREN = set()


def _term(signum, _frame):
    """stop: kill our running workers (their jobs leave no row and are re-run on resume)."""
    for pid in list(CHILDREN):
        try:
            os.killpg(pid, signal.SIGKILL)
        except OSError:
            pass
    os._exit(128 + signum)


def free_gb(p):
    try:
        st = os.statvfs(p)
        return st.f_bavail * st.f_frsize / 1e9
    except OSError:
        return None


class Sched:
    def __init__(self, out_dir, nproc, cache):
        self.od = out_dir
        self.nproc = max(1, min(8, int(nproc)))
        self.cache = cache
        self.rp = os.path.join(out_dir, "results.jsonl")
        for r in B.read_jsonl(self.rp):          # own rows win (resume)
            r["_own"] = True
            self.cache[r["jid"]] = r
        self.out = B.SafeAppender(self.rp)
        self.lock = threading.Lock()
        self.pending = []                         # (prio, seq, job)
        self.inflight = set()
        self.queued = set()
        self.active = 0
        self.seq = 0
        self.era = B.era_stamp()
        self.n_new = 0
        self.cpu_new = 0.0
        self.t0 = time.time()
        self.requeued = Counter()
        self._oth = (0.0, 0)

    def disk_ok(self):
        a, b = free_gb(self.od), free_gb(RAW)
        low = (a is not None and a < B.DISK_MIN_FREE_GB) or (b is not None and b < B.TMP_MIN_FREE_GB)
        return not low and not B.DISK.paused() and not B.DISK.backoff_active()

    def others(self):
        """sizing workers of OTHER jobs on this box (bv2.py worker processes not under our RAW dir),
        re-counted at most every 5 s: the 8-process cap is a BOX total shared with e.g. pv1_score."""
        if time.time() - self._oth[0] < 5:
            return self._oth[1]
        n = 0
        mine = RAW.encode()
        for d in os.listdir("/proc"):
            if not d.isdigit():
                continue
            try:
                with open("/proc/%s/cmdline" % d, "rb") as fh:
                    cl = fh.read()
            except OSError:
                continue
            if b"bv2.py" in cl and b"worker" in cl and mine not in cl:
                n += 1
        self._oth = (time.time(), n)
        return n

    def cap(self):
        """box total 8 (4 while load1 > 22) minus other jobs' sizing workers, and <= nproc."""
        try:
            l1 = os.getloadavg()[0]
        except OSError:
            l1 = 0.0
        total = 4 if l1 > LOAD_HI else BOX_MAX
        return max(0, min(self.nproc, total - self.others()))

    def write(self, row):
        self.out.write(json.dumps(row, default=repr) + "\n")

    def submit(self, jobs, prio):
        for j in jobs:
            if j["jid"] in self.cache:
                c = self.cache[j["jid"]]
                if not c.get("_written") and not c.get("_own"):
                    # record the reused row in this run's results.jsonl (exact key, audit)
                    row = dict({k: j[k] for k in ("task", "key", "seed", "jid")}, **norm_summ(c),
                               source=c["source"], ts=now())
                    self.write(row)
                    c["_written"] = True
                continue
            if j["jid"] in self.queued:
                continue
            self.queued.add(j["jid"])
            self.seq += 1
            self.pending.append((prio, self.seq, j))
        self.pending.sort(key=lambda x: (x[0], x[1]))

    def work(self, j):
        jid = j["jid"]
        jf, of, ef = (os.path.join(RAW, jid + ".job.json"), os.path.join(RAW, jid + ".out.json"),
                      os.path.join(RAW, jid + ".err"))
        t0 = time.time()
        if not os.path.exists(of):
            json.dump({"jid": jid, "tokens": j["tokens"], "spec": j["spec"], "seed": j["seed"],
                       "budget": B.BUDGET, "profile": PROF}, open(jf, "w"))
            with open(ef, "w") as efh:
                p = subprocess.Popen([sys.executable, pv0.BV2_PY, "worker", jf, of],
                                     stdout=subprocess.DEVNULL, stderr=efh, start_new_session=True)
                CHILDREN.add(p.pid)
                try:
                    p.wait(timeout=WORKER_TIMEOUT_S)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(p.pid, signal.SIGKILL)
                    except OSError:
                        pass
                    p.wait()
                CHILDREN.discard(p.pid)
        base = {k: j[k] for k in ("task", "key", "seed", "jid")}
        if not os.path.exists(of):
            if not self.disk_ok() and self.requeued[jid] < 5:
                return None                     # disk trouble: re-queue, never record
            err = open(ef).read()[-600:] if os.path.exists(ef) else ""
            return dict(base, source="sized", crashed=True, feasible=False, secs=round(time.time() - t0, 2),
                        stderr_tail=err, era=self.era)
        r = json.load(open(of))
        row = dict(base, source="sized", era=self.era, **norm_summ(PS.summ(r)))
        for f in (jf, of, ef):
            try:
                os.remove(f)
            except OSError:
                pass
        return row

    def runner(self, j):
        try:
            row = self.work(j)
        except Exception as e:                                       # noqa: BLE001
            row = dict({k: j[k] for k in ("task", "key", "seed", "jid")}, source="sized", crashed=True,
                       feasible=False, secs=None, error=repr(e)[:300])
        with self.lock:
            self.active -= 1
            self.inflight.discard(j["jid"])
            if row is None:
                self.requeued[j["jid"]] += 1
                self.pending.insert(0, (-1, 0, j))
                return
            row["ts"] = now()
            self.write(row)
            row["_own"] = True
            self.cache[j["jid"]] = row
            self.n_new += 1
            self.cpu_new += row.get("secs") or 0.0

    def launch_some(self):
        while True:
            with self.lock:
                if not self.pending or self.active >= self.cap():
                    return
            if not self.disk_ok():
                self.out.flush()
                time.sleep(30)
                return
            with self.lock:
                _p, _s, j = self.pending.pop(0)
                self.active += 1
                self.inflight.add(j["jid"])
            threading.Thread(target=self.runner, args=(j,), daemon=True).start()

    def drive(self, gens, label):
        """gens: list of [name, generator, prio]; runs them to completion."""
        live = []
        for name, g, prio, fin in gens:
            st = [name, g, prio, None, fin]
            try:
                jobs = next(g)
                st[3] = [j["jid"] for j in jobs]
                with self.lock:
                    self.submit(jobs, prio)
                live.append(st)
            except StopIteration:
                fin()
        last = 0.0
        while live:
            progressed = False
            for st in list(live):
                with self.lock:
                    ready = all(jid in self.cache for jid in st[3])
                if not ready:
                    continue
                progressed = True
                rows = [self.cache[jid] for jid in st[3]]
                try:
                    jobs = st[1].send(rows)
                    st[3] = [j["jid"] for j in jobs]
                    with self.lock:
                        self.submit(jobs, st[2])
                except StopIteration:
                    live.remove(st)
                    st[4]()
            self.launch_some()
            self.out.flush()
            if time.time() - last > 300:
                last = time.time()
                print("[ga %s %s] live runs %d, active %d (cap %d, other workers %d), pending %d, new sized "
                      "%d (%.1f CPU-h), wall %.1f min, load1 %.1f" % (
                          label, now(), len(live), self.active, self.cap(), self.others(), len(self.pending),
                          self.n_new, self.cpu_new / 3600, (time.time() - self.t0) / 60, os.getloadavg()[0]),
                      flush=True)
            if not progressed:
                time.sleep(0.5)
        while self.out.pending():
            self.out.flush()
            time.sleep(5)


def run(a):
    od = os.path.abspath(a.out)
    os.makedirs(od, exist_ok=True)
    os.makedirs(RAW, exist_ok=True)
    signal.signal(signal.SIGTERM, _term)
    signal.signal(signal.SIGINT, _term)
    tt = tasks_and_tiers()
    tasks = a.tasks.split(",") if a.tasks else list(tt)
    seeds = [int(s) for s in a.seeds.split(",")]
    anch = B.anchor_data()
    specs = {t: spec_of(t) for t in tasks}
    cache = load_caches([os.path.abspath(p) for p in (a.extra_cache.split(",") if a.extra_cache else [])])
    S = Sched(od, a.nproc, cache)
    runs_p = os.path.join(od, "runs.jsonl")
    done = {(r["task"], r["ga_seed"]) for r in B.read_jsonl(runs_p)}
    runs_out = B.SafeAppender(runs_p)
    meta = OrderedDict(prereg="kaggle/PREREG-BASELINES-V1.md (b8fbcf20a) G", started=now(), nproc=S.nproc,
                       tasks=len(tasks), seeds=seeds, bmax=a.bmax, mu=MU, lam=LAM, tries=TRIES, p_two=P_TWO,
                       verifier=PROF, budget=B.BUDGET, pdk=B.PDK, era=S.era,
                       cache_rows=len(cache), extra_cache=a.extra_cache)
    with open(os.path.join(od, "meta.jsonl"), "a") as fh:
        fh.write(json.dumps(meta) + "\n")
    print("[ga] %d tasks x seeds %s, %d done runs, cache %d rows, out %s" % (
        len(tasks), seeds, len(done), len(cache), rel(od)), flush=True)
    gens = []
    n_done = [len(done)]
    prio = 0
    for gs in seeds:
        for t in tasks:
            if (t, gs) in done:
                continue
            out = {}

            def fin(out=out):
                out = dict(out)
                runs_out.write(json.dumps(out, default=repr) + "\n")
                n_done[0] += 1
                print("[ga run %d] %s s%d %s first=%s calls=%s spice_min=%s new_cpu_min=%.1f" % (
                    n_done[0], out["task"], out["ga_seed"], out["status"], out["first_feasible_call"],
                    out["calls_counted"], out["spice_min_to_first"], out["new_sized_secs"] / 60), flush=True)
            gens.append(["%s|%d" % (t, gs), ga_run(t, tt[t], gs, specs[t], anch, a.bmax, out), prio, fin])
            prio += 1
    S.drive(gens, "ga")
    while runs_out.pending():
        runs_out.flush()
        time.sleep(5)
    # ---- confirmation: seeds 2, 3 for every found design
    found = OrderedDict()
    for r in B.read_jsonl(runs_p):
        if r["task"] in specs and r["ga_seed"] in seeds and r.get("found"):
            f = r["found"]
            found[(r["task"], f["key"])] = f["tokens"]

    def conf_gen(task, key, tokens):
        jobs = [{"task": task, "key": key, "seed": s, "tokens": tokens, "spec": specs[task],
                 "jid": B.job_id(tokens, specs[task], s, B.BUDGET, PROF)} for s in (2, 3)]
        yield jobs
    cg = [["conf|%s|%s" % tk, conf_gen(tk[0], tk[1], tok), i, (lambda: None)]
          for i, (tk, tok) in enumerate(found.items())]
    print("[ga] confirmation: %d found designs x seeds 2,3" % len(cg), flush=True)
    S.drive(cg, "confirm")
    print("[ga] done: new sized calls %d, %.2f CPU-h, wall %.1f min" % (
        S.n_new, S.cpu_new / 3600, (time.time() - S.t0) / 60), flush=True)


# ------------------------------------------------------------------ summary
def passk(n, c, k):
    from math import comb
    if n < k:
        return None
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def med(xs):
    return round(statistics.median(xs), 3) if xs else None


def summarize(a):
    od = os.path.abspath(a.out)
    tt = tasks_and_tiers()
    runs = OrderedDict()
    for r in B.read_jsonl(os.path.join(od, "runs.jsonl")):
        runs[(r["task"], r["ga_seed"])] = r
    res = {}
    for r in B.read_jsonl(os.path.join(od, "results.jsonl")):
        res[r["jid"]] = r
    seeds = sorted({s for _t, s in runs})
    tasks = [t for t in tt if any((t, s) in runs for s in seeds)]
    complete = all((t, s) in runs for t in tt for s in seeds)
    groups = ("all", "T1", "T2", "T3")
    S = OrderedDict(prereg="kaggle/PREREG-BASELINES-V1.md (b8fbcf20a) G", run_dir=rel(od),
                    n_tasks=len(tasks), ga_seeds=seeds, n_runs=len(runs), complete_58x3=complete)
    # confirmation of each run's found design
    conf = {}
    for (t, s), r in runs.items():
        f = r.get("found")
        if not f:
            continue
        sp = os.path.join(P1, "specs", t + ".yaml")
        r2, r3 = (res.get(B.job_id(f["tokens"], sp, x, B.BUDGET, PROF)) for x in (2, 3))
        conf[(t, s)] = OrderedDict(seed2=None if r2 is None else bool(r2.get("feasible")),
                                   seed3=None if r3 is None else bool(r3.get("feasible")))
    G = OrderedDict()
    for g in groups:
        tl = [t for t in tasks if g == "all" or tt[t] == g]
        rl = [runs[(t, s)] for t in tl for s in seeds if (t, s) in runs]
        d = OrderedDict(n_tasks=len(tl), n_runs=len(rl))
        for b in BS:
            d["solve@%d" % b] = round(sum(1 for r in rl if r["first_feasible_call"] and
                                          r["first_feasible_call"] <= b) / len(rl), 4) if rl else None
        for b in BS:
            d["coverage@%d" % b] = sum(1 for t in tl if any(
                (t, s) in runs and runs[(t, s)]["first_feasible_call"] and runs[(t, s)]["first_feasible_call"] <= b
                for s in seeds))
        sol = [r for r in rl if r["first_feasible_call"]]
        d["n_solved_runs"] = len(sol)
        d["median_calls_to_first"] = med([r["first_feasible_call"] for r in sol])
        d["median_spice_min_to_first"] = med([r["spice_min_to_first"] for r in sol])
        d["mean_spice_min_to_first"] = round(statistics.mean([r["spice_min_to_first"] for r in sol]), 2) \
            if sol else None
        # censored medians: an unsolved run counts as > B_max (inf)
        cc = sorted([r["first_feasible_call"] or float("inf") for r in rl])
        mc = statistics.median(cc) if rl else None
        d["median_calls_censored"] = (">%d" % BMAX) if mc == float("inf") else mc
        cs = [conf[(r["task"], r["ga_seed"])] for r in sol if (r["task"], r["ga_seed"]) in conf]
        d["confirmed_runs"] = sum(1 for c in cs if c["seed2"] or c["seed3"])
        d["confirmed_both_runs"] = sum(1 for c in cs if c["seed2"] and c["seed3"])
        d["confirmation_rate"] = round(d["confirmed_runs"] / len(sol), 4) if sol else None
        d["confirm_rows_missing"] = sum(1 for c in cs if c["seed2"] is None or c["seed3"] is None) + \
            (len(sol) - len(cs))
        d["confirmed_solve@64"] = round(d["confirmed_runs"] / len(rl), 4) if rl else None
        d["spice_min_total_mean"] = round(statistics.mean([r["spice_min_total"] for r in rl]), 2) if rl else None
        G[g] = d
    S["ga"] = G
    # sft-r1 pass@k (exit-r1 r1-summary per_item_h1, seed-1 feasible = c of n)
    r1 = json.load(open(os.path.join(CAMP, "exit-r1", "score", "r1-summary.json")))["per_item_h1"]["sft-r1"]
    SF = OrderedDict()
    for g in groups:
        it = [v for t, v in r1.items() if t in tt and (g == "all" or tt[t] == g)]
        d = OrderedDict(n_items=len(it))
        for k in KS:
            vals = [passk(v["n"], v["c"], k) for v in it]
            vals = [x for x in vals if x is not None]
            d["pass@%d" % k] = round(sum(vals) / len(vals), 4) if vals else None
        d["coverage@8"] = sum(1 for v in it if v["c"] > 0)
        SF[g] = d
    S["sft_r1"] = SF
    sb = json.load(open(os.path.join(EVAL, "searchbar.json")))
    S["blind_bar"] = OrderedDict(aggregate=sb["aggregate"], method=sb["method"])
    # GA per item vs bar
    per = OrderedDict()
    for t in tasks:
        rr = [runs.get((t, s)) for s in seeds]
        per[t] = OrderedDict(tier=tt[t], first_feasible=[r["first_feasible_call"] if r else "missing" for r in rr],
                             spice_min=[r["spice_min_to_first"] if r else None for r in rr],
                             status=[r["status"] if r else None for r in rr],
                             found_origin=[(r.get("found") or {}).get("origin") if r else None for r in rr],
                             confirm=[conf.get((t, s)) for s in seeds],
                             bar_calls=sb["items"][t].get("calls"), bar_spice_min=sb["items"][t].get("spice_min"),
                             sft_r1_c_of_n="%d/%d" % (r1[t]["c"], r1[t]["n"]))
    S["per_item"] = per
    # cost
    S["cost"] = OrderedDict(
        new_sized_cpu_h=round(sum(r["new_sized_secs"] for r in runs.values()) / 3600, 2),
        sized_calls_total=sum(r["sized_calls_total"] for r in runs.values()),
        sized_calls_cache=sum(1 for r in runs.values() for c in r["calls"]
                              if c.get("i") and str(c.get("source", "")).startswith("cache:")),
        stats=dict(sum((Counter(r["stats"]) for r in runs.values()), Counter())),
        status=dict(Counter(r["status"] for r in runs.values())))
    # reading (pre-declared)
    a8, a64 = G["all"]["solve@8"], G["all"]["solve@64"]
    t2_64 = G["T2"]["solve@64"]
    rd = []
    if a8 is not None:
        if a8 >= 0.793:
            rd.append("GA solve@8 %.3f >= sft-r1 pass@8 .793 => at equal SPICE budget a simple search matches "
                      "the fine-tuned LLM; this bench cannot show LLM design capability and further RL on it "
                      "is not justified." % a8)
        elif a64 is not None and a64 >= 0.95:
            rd.append("GA solve@8 %.3f < .793 but solve@64 %.3f >= .95 => the LLM is a SPICE-budget saver only "
                      "(break-even below)." % (a8, a64))
        else:
            rd.append("GA solve@8 %.3f < .793 and solve@64 %s < .95: neither of the first two pre-declared "
                      "readings applies." % (a8, a64))
        if t2_64 is not None and t2_64 < 0.9:
            rd.append("GA T2 solve@64 %.3f is well below 1 => the bench is harder for search than the blind "
                      "bar suggests (re-examine)." % t2_64)
    S["reading"] = rd
    js = os.path.join(HERE, "ga-summary.json") if not a.dest else os.path.join(a.dest, "ga-summary.json")
    md = os.path.join(HERE, "ga-tables.md") if not a.dest else os.path.join(a.dest, "ga-tables.md")
    B.atomic_write(js, json.dumps(S, indent=1, default=repr))
    L = ["# baselines-v1 G — GA tables (`ga.py summarize`, run dir `%s`)" % rel(od), "",
         "Runs %d (tasks %d x GA seeds %s; complete 58x3: %s). Solved at B = first seed-1-feasible sized call "
         "<= B (rl-v1.2, bptm45, 2500 evals). sft-r1 = exit-r1 H1 (8 samples/item, one sample = one sized "
         "call at most), unbiased pass@k." % (len(runs), len(tasks), seeds, complete), "",
         "## Solve rate at budget B (mean over task x GA seed) vs sft-r1 pass@k (k = B)", "",
         "| group | runs | " + " | ".join("GA@%d" % b for b in BS) + " | " +
         " | ".join("sft-r1 p@%d" % k for k in KS) + " |",
         "|---|---|" + "---|" * (len(BS) + len(KS))]
    for g in groups:
        d, s = G[g], SF[g]
        L.append("| %s | %d | " % (g, d["n_runs"]) + " | ".join(str(d["solve@%d" % b]) for b in BS) + " | " +
                 " | ".join(str(s["pass@%d" % k]) for k in KS) + " |")
    L += ["", "## Coverage at B (tasks solved by >= 1 of the GA seeds) vs sft-r1 coverage@8", "",
          "| group | tasks | " + " | ".join("cov@%d" % b for b in BS) + " | sft-r1 cov@8 |",
          "|---|---|" + "---|" * (len(BS) + 1)]
    for g in groups:
        d = G[g]
        L.append("| %s | %d | " % (g, d["n_tasks"]) + " | ".join(str(d["coverage@%d" % b]) for b in BS) +
                 " | %s |" % SF[g]["coverage@8"])
    L += ["", "## Cost to the first feasible design, confirmation", "",
          "| group | solved runs | median calls | median calls (censored, unsolved = inf) | median SPICE-min | "
          "mean SPICE-min | blind bar median calls | blind bar median SPICE-min | confirmed (seed 2 or 3) | "
          "confirmed both | confirmation rate |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for g in groups:
        d = G[g]
        bb = (sb["aggregate"].get(g) or {}) if g in ("T1", "T2") else {}
        L.append("| %s | %d | %s | %s | %s | %s | %s | %s | %d | %d | %s |" % (
            g, d["n_solved_runs"], d["median_calls_to_first"], d["median_calls_censored"],
            d["median_spice_min_to_first"], d["mean_spice_min_to_first"], bb.get("median_calls", "-"),
            bb.get("median_spice_min", "-"), d["confirmed_runs"], d["confirmed_both_runs"],
            d["confirmation_rate"]))
    L += ["", "Blind bar = pilot-v0/eval/searchbar.json (E-c expected cost, random order: T1 over the library "
          "anchors, T2 over the shown anchor's single edits; T3 has no bar).", "",
          "Cost: %s" % json.dumps(S["cost"]), "", "## Pre-declared reading", ""] + ["- " + x for x in rd]
    L += ["", "## Per item", "", "| task | tier | GA first feasible call (s1,s2,s3) | SPICE-min | blind bar calls | "
          "sft-r1 c/n |", "|---|---|---|---|---|---|"]
    for t, v in per.items():
        L.append("| %s | %s | %s | %s | %s | %s |" % (t, v["tier"], v["first_feasible"], v["spice_min"],
                                                       v["bar_calls"], v["sft_r1_c_of_n"]))
    B.atomic_write(md, "\n".join(L) + "\n")
    print("\n".join(L[:40]))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run")
    r.add_argument("nproc", type=int)
    r.add_argument("--out", default=DEF_OUT)
    r.add_argument("--tasks")
    r.add_argument("--seeds", default="1,2,3")
    r.add_argument("--bmax", type=int, default=BMAX)
    r.add_argument("--extra-cache")
    s = sp.add_parser("summarize")
    s.add_argument("--out", default=DEF_OUT)
    s.add_argument("--dest")
    a = ap.parse_args()
    if a.cmd == "run":
        run(a)
    else:
        summarize(a)


if __name__ == "__main__":
    main()

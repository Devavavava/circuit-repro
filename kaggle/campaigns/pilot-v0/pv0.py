#!/usr/bin/env python
"""pilot-v0 P0 + P0b (kaggle/PREREG-PILOT-V0.md, commit 137ea060a). Local CPU only.

  split   hold out whole spec families (band x flavor) of kaggle/train-pool-v2,
          ~20-25 % of the 272 tasks, one wideband + one narrowband family
          (deterministic rule, see README); writes eval/split.json + .sha256.
          Refuses to change an existing split.

  run     ONE detached scheduler (resumable, bv2 D32 disk robustness, <= 8 worker
          processes in total, 4 while load1 > 22) driving both phases:
    P0  (eval, priority; 5 of 8 slots while P0b has work)  per held-out task, rl-v1.2:
          E-TF1  a1-a5 x seed 1 (exact-key cache hits on the AMENDMENT-3 T-F1 rows),
                 then seed 2 if no anchor is feasible at seed 1      -> T1
          E-F2   every round-trip-valid single edit of the SHOWN anchor (bv2 / E-c
                 space) x seed 1 (full enumeration, no early kill), then seed 2 for
                 the candidates whose worst margin (incl. wide mu - 1) is >= -0.1
                                                                      -> T2 / T3
    P0b (training data; >= 3 of 8 slots while it has work)
          GEN    the bv2 training stream extended (bv2.Pipeline.make_generation /
                 candidate_from_script / process_candidate / plant: same generator,
                 gen size 4/point, loose probes, D2 seed-2 confirmation, 2 % cushion)
                 on the 8 TRAINING-side grid points only, in a fresh RNG namespace,
                 archive = earlier training candidates of training-side points;
                 rl-v1.2 throughout. Quota per point Q (existing ok + new planted);
                 when every point is at Q and all tasks are finished, Q += 5 until
                 >= 600 ok training-side tasks AND >= 1050 estimated examples.
          T-wit  witness at the planted spec, seed 1, then 2      (>= 1 of {1,2})
          T-F1   a1-a5 x seed 1 at the task spec (library positives + shown-anchor
                 evidence)
          T-SE   one recorded rl-v1.2 single-edit design (bench F2 rows, same band)
                 meeting the limits, re-verified at the task spec (seed 1, then 2)
  build-eval / build-data   (also run automatically when each phase completes)
          eval/{tiers.json, searchbar.json, prompts/, specs/, README via ../README.md}
          data/{train-all.jsonl, subsets.json, manifest.json, stats.json,
                fence_check.json}

usage (via ../bench-v2/envrun.sh, BV2_TMPDIR=/tmp/cr-pv0):
  pv0.py split
  pv0.py run [--run-dir D] [--eval-limit N] [--f2-limit K] [--no-gen] [--gen-max-new N]
             [--max-procs 8]
  pv0.py build-eval | build-data [--run-dir D] [--partial]
  pv0.py plan     (F2 space sizes per held-out task, no sims)
"""
import argparse
import hashlib
import json
import math
import os
import random
import shutil
import signal
import statistics
import subprocess
import sys
import time
from collections import Counter, OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
BV2D = f"{REPO}/kaggle/campaigns/bench-v2"
sys.path.insert(0, BV2D)
import bv2 as B  # noqa: E402

PROF = "rl-v1.2"
B.CUR_PROFILE = PROF
PHASE = "pilot-v0"
SRC = f"{BV2D}/run"                       # finished bench-v2 run (read-only)
A3 = f"{BV2D}/amend3"                     # AMENDMENT-3 re-check (read-only)
TP = f"{REPO}/kaggle/train-pool-v2"
EVAL = f"{HERE}/eval"
DATA = f"{HERE}/data"
BV2_PY = f"{BV2D}/bv2.py"
WORKER_TIMEOUT_S = 3600
NEAR = 0.1                                # seed-2 F2 re-try: worst margin >= -NEAR
STRICT = ["v2b-wb0824-gain-188", "v2b-wb1020-noise-217"]
PRIO = {"E-TF1": 0, "E-F2": 1, "search": 2, "confirm": 2, "T-wit": 3, "T-F1": 4, "T-SE": 5}
P0_KINDS = ("E-TF1", "E-F2")
# P0b generation targets (README D-P4)
TARGET_OK = 600
TARGET_EX = 1050
Q0, QSTEP, QMAX = 85, 5, 130
MAX_POS = 3
SUBSET_SEED = 20261005
GEN_NS = "pilot-v0"


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def body_lines(text):
    """netlist text -> dialect lines (comments / blanks stripped)."""
    return "\n".join(ln.strip() for ln in text.splitlines()
                     if ln.strip() and not ln.lstrip().startswith(("*", "#"))) + "\n"


def bt_of(band):
    return B.BANDS[band][0]


# ====================================================================== split
def compute_split():
    idx = json.load(open(f"{TP}/INDEX.json"))
    tasks = idx["tasks"]
    fam = defaultdict(list)
    for n, v in tasks.items():
        fam[f"{v['band']}-{v['flavor']}"].append(n)
    N = len(tasks)
    lo, hi = math.ceil(0.20 * N), math.floor(0.25 * N)
    nonlib = {f: sum(1 for n in ns if tasks[n]["difficulty"] != "library-solvable")
              for f, ns in fam.items()}
    bt = {f: bt_of(f.split("-")[0]) for f in fam}
    cands = []
    for w in sorted(fam):
        for nb in sorted(fam):
            if bt[w] == "wideband" and bt[nb] == "narrowband":
                tot = len(fam[w]) + len(fam[nb])
                cands.append({"families": [w, nb], "n": tot,
                              "n_not_library": nonlib[w] + nonlib[nb],
                              "in_range": lo <= tot <= hi})
    ok = [c for c in cands if c["in_range"]]
    ok.sort(key=lambda c: (-c["n_not_library"], -c["n"], c["families"]))
    pick = ok[0]["families"]
    held = sorted(n for f in pick for n in fam[f])
    train = sorted(n for n in tasks if n not in set(held))
    return OrderedDict(
        version=1, prereg="kaggle/PREREG-PILOT-V0.md (137ea060a)", created=now(),
        source_index="kaggle/train-pool-v2/INDEX.json",
        source_index_sha256=sha256_file(f"{TP}/INDEX.json"),
        verifier=PROF, n_pool=N,
        rule=("hold out exactly one wideband and one narrowband spec family (band x "
              "flavor grid point) whose task total is within [ceil(0.20 N), "
              "floor(0.25 N)]; among those pairs pick the one with the most tasks not "
              "labelled library-solvable in the rl-v1.2 pool INDEX (the eval needs "
              "T2/T3 items), ties -> more tasks -> lexicographic"),
        range=[lo, hi],
        heldout_families=pick,
        heldout_frac=round(len(held) / N, 4),
        heldout_tasks=held,
        train_families=sorted(f for f in fam if f not in pick),
        train_tasks=train,
        extra_eval_cells=STRICT,
        family_counts={f: {"n": len(ns), "n_not_library": nonlib[f], "band_type": bt[f]}
                       for f, ns in sorted(fam.items())},
        candidates=sorted(cands, key=lambda c: c["families"]))


def cmd_split(_a):
    os.makedirs(EVAL, exist_ok=True)
    p = f"{EVAL}/split.json"
    if os.path.exists(p):
        old = json.load(open(p))
        new = compute_split()
        same = all(old[k] == new[k] for k in ("heldout_families", "heldout_tasks",
                                               "train_tasks", "source_index_sha256"))
        h = sha256_file(p)
        rec = open(f"{p}.sha256").read().split()[0]
        print(f"split exists (sha256 {h}, recorded {rec}, match={h == rec}); "
              f"recomputation identical={same}. NOT rewritten.")
        return
    s = compute_split()
    B.atomic_write(p, json.dumps(s, indent=1))
    h = sha256_file(p)
    B.atomic_write(f"{p}.sha256", f"{h}  split.json\n")
    print(f"split: held out {s['heldout_families']} = {len(s['heldout_tasks'])}/{s['n_pool']} "
          f"({s['heldout_frac']:.1%}); train {len(s['train_tasks'])}; sha256 {h}")


def load_split():
    p = f"{EVAL}/split.json"
    s = json.load(open(p))
    rec = open(f"{p}.sha256").read().split()[0]
    assert sha256_file(p) == rec, "split.json changed after it was frozen"
    return s


# ==================================================================== F2 space
def f2_cands(A):
    """bv2.Pipeline.f2space_build's exact enumeration, with the netlist text kept."""
    import itertools as IT
    lines = A["text"].splitlines()
    elems = []
    for i, raw in enumerate(lines):
        s = raw.strip()
        if not s or s[0] in "#*":
            continue
        p = s.split()
        elems.append((i, p[0].upper(), p[1], p[2:]))
    nets = sorted({n for _i, _t, _n, ns in elems for n in ns})
    body = "\n".join(lines)
    cands = []
    for x, y in IT.combinations(nets, 2):
        for typ in ("R", "C", "L"):
            cands.append({"kind": "add", "desc": f"add {typ} {x}-{y}",
                          "netlist": body.rstrip("\n") + f"\n{typ} {typ}x {x} {y}\n"})
    for i, typ, name, ns in elems:
        kept = [ln for k, ln in enumerate(lines) if k != i]
        cands.append({"kind": "del", "desc": f"del {typ} {name} ({' '.join(ns)})",
                      "netlist": "\n".join(kept) + "\n"})
    return cands


class Dummy:
    def __init__(self, anch):
        self.anch, self.f2space = anch, {}

    def log(self, m):
        pass

    def round_trip(self, text):
        import proposal as P
        rt = P.round_trip(text)
        return {"ok": bool(rt.get("ok")), "error": rt.get("error"),
                "tokens": rt.get("tokens"), "wl_hash": rt.get("wl_hash"),
                "n_devices": rt.get("n_devices")}


def load_f2space(rd, anch):
    p = f"{rd}/f2space.json"
    if os.path.exists(p):
        sp = json.load(open(p))
    else:
        d = Dummy(anch)
        B.Pipeline.f2space_build(d)
        sp = d.f2space
        B.atomic_write(p, json.dumps(sp))
    for a, A in anch.items():
        cc = f2_cands(A)
        assert len(cc) == len(sp[a]) and all(c["desc"] == x["desc"] for c, x in zip(cc, sp[a]))
        for c, x in zip(cc, sp[a]):
            x["netlist"] = c["netlist"]
    return sp


# ============================================================= P0b generator
class Gen(B.Pipeline):
    """bv2's training-stream generator, state only (no bv2 scheduler): the exact
    make_generation / candidate_from_script / process_candidate / plant code paths
    with a pilot-v0 RNG namespace, training-side points, rl-v1.2."""

    def __init__(self, R, train_points, f2space, old_cands, cal_rows):   # noqa: D401
        self.R = R
        self.mode = "pilot-v0"
        self.cfg = dict(B.CONFIGS["full"])
        self.cfg.update(
            stream_seed={"bench": None, "train": f"{GEN_NS}:{B.CONFIGS['full']['stream_seed']['train']}"},
            gen_size={"bench": 0, "train": 4},
            grid_only={"bench": [], "train": [list(g) for g in train_points]},
            train_quota_per_point=Q0, profile=PROF, amend2=False)
        self.amend2 = False
        self.phase = PHASE
        self.rd = R.rd
        self.era = R.era
        self.cache = R.cache
        self.anch = R.anch
        self.anchor_wls = {a["wl"] for a in self.anch.values()}
        self.f2space = f2space
        self.f2_wls = {c["wl"] for a in f2space for c in f2space[a] if c["rt_ok"]}
        self.rtcache = {}
        rp = f"{self.rd}/rtcache.jsonl"
        for r in B.read_jsonl(rp):
            self.rtcache[r["k"]] = r["v"]
        self.rt_fh = B.SafeAppender(rp, dry=R.dry)
        self.fh = {"candidates.jsonl": R.fh["candidates.jsonl"]}
        self.res_fh = R.fh["results.jsonl"]
        self.archive = {"bench": defaultdict(list), "train": defaultdict(list)}
        self.seen_wl = {"bench": defaultdict(set), "train": defaultdict(set)}
        self.search_stats = {s: Counter() for s in ("bench", "train")}
        self.n_cand = Counter()
        self.cls_accepted = Counter()
        self.pdc = Counter()
        self.pool_cal = defaultdict(list)
        self.probe = {}
        self.train_points = [tuple(g) for g in train_points]
        for g in self.train_points:
            bt = B.BANDS[g[0]][0]
            self.probe[g] = B.write_spec(
                f"{self.rd}/specs/probe-{B.gkey(g)}.yaml",
                B.make_spec(g, B.PROBE[bt], f"probe-{B.gkey(g)}",
                            f"bench-v2 loose probe spec {B.gkey(g)}"))
            # same content as bench-v2's probe file (same job keys)
            assert B.spec_sha(self.probe[g]) == B.spec_sha(f"{SRC}/specs/probe-{B.gkey(g)}.yaml")
        tp = set(self.train_points)
        gmax = -1
        for c in old_cands:
            g = tuple(c["g"].split("-"))
            self.seen_wl["train"][g].add(c["wl"])
            gmax = max(gmax, int(c.get("gen", 0)))
            if g not in tp or c.get("score") is None or not c.get("tokens"):
                continue
            if not self.prefilter(c["tokens"])["pass"]:
                self.pdc["archive_dropped_prefilter"] += 1
                continue
            self.archive["train"][g].append(c)
            self.pdc["archive_kept"] += 1
        self.gen0 = gmax + 1
        for r in cal_rows:          # bv2 calibration designs (dominance score only)
            b = r["meta"]["g"].split("-")[0]
            self.add_pool(self.pool_cal[b], r, f"cal:{r['meta']['g']}:{r['meta']['anchor']}:s{r['seed']}")
        self.Q = Q0
        self.new_planted = Counter()

    def log(self, msg):
        self.R.log(msg)

    def event(self, kind, **kw):
        self.R.event(kind, **kw)

    def train_have(self, g):
        return self.R.train_have.get(B.gkey(g), 0) + self.new_planted[B.gkey(g)]

    def make_generation(self, stream, gen):
        self.cfg["train_quota_per_point"] = self.Q
        return B.Pipeline.make_generation(self, stream, gen)

    def plant_train(self, c, g, bt):
        R = self.R
        if self.train_have(g) >= self.Q:
            self.event("train_plant_skipped", cid=c["cid"], why="point_quota")
            return
        if c["wl"] in R.fence_wl or c["tok"] in R.fence_tok:
            self.event("train_fenced", cid=c["cid"], why="bench / held-out witness hash")
            R.fence_stats["gen_fenced_hash"] += 1
            return
        lim = B.planted_limits(bt, c["planted_from"])
        # D-P15: the extension continues the train-pool-v2 stream's naming and spec
        # description (seq from 1000), so training and held-out prompts share format
        seq = R.next_seq
        name = f"t2-{g[0]}-{g[1]}-{seq:04d}"
        spec_path = B.write_spec(f"{self.rd}/specs/{name}.yaml", B.make_spec(
            g, lim, name, f"train-pool-v2 planted task ({g[0]}, {g[1]} objective) "
            f"from search witness {c['cid']}"))
        if B.spec_sha(spec_path) in R.fence_spec:
            self.event("train_fenced", cid=c["cid"], why="spec equals a bench / held-out spec")
            R.fence_stats["gen_fenced_spec"] += 1
            return
        R.next_seq += 1
        self.new_planted[B.gkey(g)] += 1
        t = {"name": name, "seq": seq, "g": B.gkey(g), "band": g[0], "flavor": g[1],
             "bt": bt, "cid": c["cid"], "gen": c.get("gen"), "anchor": c["anchor"],
             "wl": c["wl"], "tok": c["tok"], "tokens": c["tokens"], "netlist": c["netlist"],
             "script": c["script"], "repairs": c["repairs"], "cls": c["cls"],
             "label": c["label"], "limits": lim, "spec": spec_path, "status": "running",
             "origin": "pilot-v0"}
        R.new_tasks[name] = t
        R.spawn(f"trainnew:{name}", R.task_train(t, new=True))


# ===================================================================== runner
class Runner:
    def __init__(self, a):
        self.a = a
        self.rd = a.run_dir
        os.makedirs(f"{self.rd}/jobs", exist_ok=True)
        os.makedirs(f"{self.rd}/specs", exist_ok=True)
        self.t0 = time.time()
        self.era = B.era_stamp()
        try:
            self.era["md5"]["kaggle/campaigns/pilot-v0/pv0.py"] = hashlib.md5(
                open(__file__, "rb").read()).hexdigest()[:10]
        except OSError:
            pass
        if a.cmd == "run":
            stamp = time.strftime("%Y%m%d-%H%M%S")
            for f in ("candidates.jsonl", "events.jsonl", "eval_tasks.jsonl", "train_tasks.jsonl"):
                p = f"{self.rd}/{f}"
                if os.path.exists(p) and os.path.getsize(p):
                    os.makedirs(f"{self.rd}/logs/prev-{stamp}", exist_ok=True)
                    os.replace(p, f"{self.rd}/logs/prev-{stamp}/{f}")
        # build-* / plan replay through the cache: nothing appended to the records
        self.dry = a.cmd != "run"
        self.fh = {n: B.SafeAppender(f"{self.rd}/{n}", dry=self.dry) for n in
                   ("results.jsonl", "events.jsonl", "eval_tasks.jsonl", "train_tasks.jsonl",
                    "candidates.jsonl", "sched.log")}
        self.n_adv = 0
        self.cache = {}
        self.cache_src = {}            # jid -> results file (repo-relative) it came from
        extra = [f"{A3}/run/results.jsonl", f"{A3}/smoke/results.jsonl"] + list(a.extra_cache or [])
        for p in [f"{self.rd}/results.jsonl"] + extra:
            for r in B.read_jsonl(p):
                if p == f"{self.rd}/results.jsonl":
                    self.cache[r["jid"]] = r
                    self.cache_src[r["jid"]] = os.path.relpath(p, REPO)
                elif r.get("profile") == PROF and not r.get("error") and r["jid"] not in self.cache:
                    self.cache[r["jid"]] = r
                    self.cache_src[r["jid"]] = os.path.relpath(p, REPO)
        self.n_cached_start = len(self.cache)
        self.pending, self.running, self.queued = [], {}, set()
        self.tasks = []
        self.stop = False
        self.n_new, self.cpu_new, self.recent = 0, 0.0, []
        self.last_progress = self.last_disk = 0.0
        self.anch = B.anchor_data()
        self.requeued = Counter()
        self.seq = 0
        self.eval_out, self.train_out = OrderedDict(), OrderedDict()
        self.new_tasks = OrderedDict()
        self.fence_stats = Counter()
        self.eval_built = self.data_built = False
        self.gen_state = {"status": "not started"}

    # ------------------------------------------------------------------ io
    def log(self, msg):
        line = f"{now()} {msg}"
        print(line, flush=True)
        self.fh["sched.log"].write(line + "\n")

    def event(self, kind, **kw):
        self.fh["events.jsonl"].write(B.jdump(dict(ts=now(), kind=kind, **kw)) + "\n")

    # --------------------------------------------------------------- inputs
    def load_inputs(self):
        a = self.a
        self.split = load_split()
        held = list(self.split["heldout_tasks"])
        if a.eval_limit:
            held = held[: a.eval_limit]
        self.heldout_fam = set(self.split["heldout_families"])
        src_tasks = B.load_jsonl_last(f"{SRC}/train.jsonl", "name")
        a3t = B.load_jsonl_last(f"{A3}/run/train_amend3.jsonl", "name")
        pool_idx = json.load(open(f"{TP}/INDEX.json"))["tasks"]
        need = {src_tasks[n]["cid"] for n in pool_idx}
        toks = {}
        old_cands = []
        for p in (f"{SRC}/pre-amendment/candidates.jsonl",
                  f"{SRC}/amendment-1-record/candidates.jsonl", f"{SRC}/candidates.jsonl"):
            for r in B.read_jsonl(p):
                if r.get("cid") in need and r.get("tokens"):
                    toks.setdefault(r["cid"], r["tokens"])
                if r.get("stream") == "train" and r.get("g"):
                    old_cands.append(r)
        self.pool = OrderedDict()
        for n in pool_idx:
            t = dict(src_tasks[n])
            tk = toks.get(t["cid"])
            if tk is None or B.tokhash(tk) != t["tok"]:
                import proposal as P
                tk = P.round_trip(t["netlist"]).get("tokens")
            assert tk is not None and B.tokhash(tk) == t["tok"], n
            t["tokens"] = tk
            t["a3"] = a3t[n]
            assert a3t[n]["status"] == "ok", n
            t["difficulty_pool"] = pool_idx[n]["difficulty"]
            t["origin"] = "train-pool-v2"
            self.pool[n] = t
        self.eval_tasks = [self.pool[n] for n in held]
        self.train_old = [self.pool[n] for n in self.split["train_tasks"]]
        assert all(t["g"] not in self.heldout_fam for t in self.train_old)
        self.train_have = Counter(t["g"] for t in self.train_old)
        self.next_seq = 1000
        # F2 space of every anchor (bv2 / E-c enumeration)
        self.f2space = load_f2space(self.rd, self.anch)
        self.f2_live = {}
        for t in self.eval_tasks:
            sp = [x for x in self.f2space[t["anchor"]] if x["rt_ok"]]
            if a.f2_limit:
                sp = sp[: a.f2_limit]
            self.f2_live[t["name"]] = sum(1 for x in sp if not self.pre_reject(x["tokens"], t["spec"]))
        # fence: every bench-v2 planted cell (any era / status; witness, stripped
        # and original), every held-out task witness, the 2 strict cells; specs too
        cells = B.load_jsonl_last(f"{SRC}/cells.jsonl", "name")
        self.cells = cells
        fw, ft, fs = set(), set(), set()
        for c in cells.values():
            for k in (None, "witness_original", "witness_original_amend1"):
                d = c if k is None else (c.get(k) or {})
                if d.get("wl"):
                    fw.add(d["wl"])
                if d.get("tok"):
                    ft.add(d["tok"])
            sp = c.get("spec")
            if sp:
                sp = sp if os.path.exists(sp) else f"{SRC}/specs/{os.path.basename(sp)}"
                if os.path.exists(sp):
                    fs.add(B.spec_sha(sp))
        self.bench_wl, self.bench_tok, self.bench_spec = set(fw), set(ft), set(fs)
        for n in self.split["heldout_tasks"]:
            t = self.pool[n]
            fw.add(t["wl"])
            ft.add(t["tok"])
            fs.add(B.spec_sha(t["spec"]))
        self.fence_wl, self.fence_tok, self.fence_spec = fw, ft, fs
        # rl-v1.2 single-edit designs of the bench F2 runs (AMENDMENT 3): positives
        # "where known" for training tasks (re-verified at the task spec)
        cell_anchor = {n: c["anchor"] for n, c in cells.items()}
        self.se_pool = defaultdict(list)
        seen = set()
        for p in (f"{A3}/run/results.jsonl", f"{A3}/smoke/results.jsonl"):
            for r in B.read_jsonl(p):
                if r.get("profile") != PROF or r.get("kind") != "F2" or r["jid"] in seen:
                    continue
                seen.add(r["jid"])
                res = r.get("res") or {}
                m = res.get("metrics") or {}
                meta = r.get("meta") or {}
                if not m:
                    continue
                an = cell_anchor.get(meta.get("cell"))
                sp = self.f2space.get(an) or []
                i = meta.get("idx")
                if not (isinstance(i, int) and 0 <= i < len(sp) and sp[i]["desc"] == meta.get("edit")):
                    continue
                pd, pf = res.get("port_dc"), res.get("port_dc_prefilter")
                pdc = bool(pd.get("pass")) if isinstance(pd, dict) else bool((pf or {}).get("pass"))
                self.se_pool[meta.get("band")].append({
                    "id": f"F2:{meta.get('cell')}:{meta.get('edit')}:s{r['seed']}", "anchor": an,
                    "idx": i, "desc": sp[i]["desc"], "wl": sp[i]["wl"], "tokens": sp[i]["tokens"],
                    "metrics": {k: v for k, v in m.items() if isinstance(v, (int, float))},
                    "stab_ok": bool(res.get("stab_wide_ok")), "pdc_ok": pdc})
        for lst in self.se_pool.values():
            lst.sort(key=lambda d: d["id"])
        self.old_cands = old_cands
        self.log(f"inputs: split {self.split['heldout_families']} -> {len(self.eval_tasks)} eval "
                 f"tasks (+{len(STRICT)} strict cells), {len(self.train_old)} training-side pool "
                 f"tasks; cache {self.n_cached_start} rows; f2 live per eval task "
                 f"{sum(self.f2_live.values())} total; se_pool "
                 f"{ {k: len(v) for k, v in self.se_pool.items()} }; old train cands {len(old_cands)}")

    def cal_rows(self):
        out = []
        with open(f"{SRC}/results.jsonl") as fh:
            for ln in fh:
                if '"kind": "cal"' not in ln:
                    continue
                try:
                    r = json.loads(ln)
                except Exception:                                # noqa: BLE001
                    continue
                if r.get("kind") == "cal" and r.get("profile") == B.PROFILE:
                    out.append(r)
        return out

    # ---------------------------------------------------------------- jobs
    def job(self, kind, tokens, spec, seed, **meta):
        meta.update(stage=kind)
        return B.Job(kind, "pv0", tokens, spec, seed, meta=meta, profile=PROF)

    _pr_memo = {}

    def pre_reject(self, tokens, spec_path):
        k = (B.tokhash(tokens), B.spec_sha(spec_path))
        if k not in self._pr_memo:
            import bench_anchor_prep as PREP
            from topology import Topology
            sp = B.sizing_spec(spec_path)
            topo = Topology(list(tokens))
            v = (not PREP.topo_limits(sp, topo)["ok"]) or bool(PREP.structural_degeneracy(topo)) \
                or not PREP.port_dc_prefilter(list(tokens))["pass"]
            self._pr_memo[k] = v
        return self._pr_memo[k]

    def inproc(self, j):
        if j.jid in self.cache:
            return self.cache[j.jid]
        import bench_anchor_prep as PREP
        r = PREP.smoke_run(j.tokens, j.spec, j.seed, j.budget, B.PDK, profile=j.profile)
        assert r is not None and r.get("n_evals") == 0, "inproc job was not a pre-reject"
        rec = {"jid": j.jid, "secs": 0.0, "load1": B.load1(), "sizable": True, "res": r,
               "error": None, "inproc_reject": True}
        return self._store(j, rec)

    def _store(self, j, rec):
        rec.update(kind=j.kind, seed=j.seed, budget=j.budget,
                   spec=os.path.relpath(j.spec, REPO), tok=B.tokhash(j.tokens), meta=j.meta,
                   era=self.era, profile=j.profile, phase=PHASE, ts=now())
        self.fh["results.jsonl"].write(B.jdump(rec) + "\n")
        self.cache[j.jid] = rec
        self.cache_src[j.jid] = os.path.relpath(f"{self.rd}/results.jsonl", REPO)
        return rec

    def submit(self, jobs):
        for j in jobs:
            if j.jid in self.cache or j.jid in self.queued:
                continue
            if j.meta.get("inproc"):
                self.inproc(j)
                continue
            self.queued.add(j.jid)
            self.seq += 1
            self.pending.append((PRIO.get(j.kind, 9), self.seq, j))
        self.pending.sort(key=lambda x: (x[0], x[1]))

    def launch(self, j):
        jf, of, ef = (f"{self.rd}/jobs/{j.jid}.job.json", f"{self.rd}/jobs/{j.jid}.out.json",
                      f"{self.rd}/jobs/{j.jid}.err")
        try:
            if not B.atomic_write(jf, B.jdump({"jid": j.jid, "tokens": j.tokens, "spec": j.spec,
                                               "seed": j.seed, "budget": j.budget,
                                               "profile": j.profile}), critical=False):
                return False
            efh = open(ef, "w")
        except OSError as e:
            if not B.is_nospace(e):
                raise
            B.DISK.note_nospace("launch", e)
            return False
        with efh:
            p = subprocess.Popen([sys.executable, BV2_PY, "worker", jf, of],
                                 stdout=subprocess.DEVNULL, stderr=efh, start_new_session=True)
        self.running[j.jid] = (p, j, time.time())
        return True

    def disk_trouble(self, window=900.0):
        D = B.DISK
        return D.full_since is not None or bool(
            D.pauses and D.pauses[-1][0] == "enospc" and time.time() - D.pauses[-1][2] < window)

    def reap(self):
        for jid, (p, j, t0) in list(self.running.items()):
            rc = p.poll()
            if rc is None and (time.time() - t0 < WORKER_TIMEOUT_S or self.disk_trouble(600)):
                continue
            if rc is None:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except Exception:                                # noqa: BLE001
                    pass
                p.wait()
            del self.running[jid]
            of, ef = f"{self.rd}/jobs/{jid}.out.json", f"{self.rd}/jobs/{jid}.err"
            rec = None
            if os.path.exists(of):
                try:
                    rec = json.load(open(of))
                except Exception:                                # noqa: BLE001
                    rec = None
            if rec is None:
                err = open(ef).read()[-2000:] if os.path.exists(ef) else ""
                if self.stop or (rc != -signal.SIGKILL and self.requeued[jid] < 3 and (
                        "No space left" in err or "Errno 28" in err or "Disk quota" in err
                        or self.disk_trouble())):
                    self.requeued[jid] += 1
                    self.queued.discard(jid)
                    if not self.stop:
                        self.log(f"worker {jid} rc={rc} left no result: re-queued, not cached")
                        self.submit([j])
                    continue
                rec = {"jid": jid, "secs": round(time.time() - t0, 2), "sizable": None,
                       "res": None, "error": f"worker rc={rc}: {err}"}
            self._store(j, rec)
            for f in (of, ef, f"{self.rd}/jobs/{jid}.job.json"):
                try:
                    os.remove(f)
                except OSError:
                    pass
            self.queued.discard(jid)
            self.n_new += 1
            self.cpu_new += rec.get("secs") or 0
            self.recent.append((time.time(), rec.get("secs") or 0))

    # ---------------------------------------------------------------- tasks
    def spawn(self, name, gen):
        self.tasks.append([name, gen, None, False])
        self.advance(self.tasks[-1], None)

    def advance(self, t, recs):
        try:
            jobs = t[1].send(recs) if recs is not None else next(t[1])
        except StopIteration:
            t[3] = True
            self.n_adv += 1
            return
        if jobs or recs:
            self.n_adv += 1          # real progress (not an idle `yield []` wait)
        self.submit(jobs)
        t[2] = [j.jid for j in jobs]

    def step_tasks(self):
        for t in list(self.tasks):
            if t[3] or t[2] is None:
                continue
            if all(j in self.cache for j in t[2]):
                self.advance(t, [self.cache[j] for j in t[2]])

    @staticmethod
    def margin(spec, res):
        """worst normalized margin incl. the wide-mu shortfall (mu_wide - 1)."""
        m = (res or {}).get("metrics") or {}
        if not m:
            return None
        _rows, worst = B.worst_margin(spec, m)
        w = worst[1] if worst else None
        mw = (res or {}).get("mu_min_wide")
        if isinstance(mw, (int, float)):
            w = (mw - 1.0) if w is None else min(w, mw - 1.0)
        return w

    def summ(self, r, seed, spec, **extra):
        res = r.get("res") or {}
        pd = res.get("port_dc")
        d = {"seed": seed, "jid": r["jid"], "feasible": B.feasible(r), "secs": r.get("secs"),
             "n_evals": res.get("n_evals"), "mu_min_wide": res.get("mu_min_wide"),
             "worst": self.margin(spec, res) if res.get("n_evals") else None,
             "infeasible_reason": res.get("infeasible_reason"),
             "port_dc_pass": pd.get("pass") if isinstance(pd, dict) else None,
             "inproc_reject": bool(r.get("inproc_reject")),
             "error": (r.get("error") or "")[:200] or None}
        d.update(extra)
        return d

    def tf1_jobs(self, kind, t, seed, **meta):
        jobs = []
        for an, A in self.anch.items():
            jobs.append(self.job(kind, A["tokens"], t["spec"], seed, task=t["name"],
                                 band=t["band"], anchor=an,
                                 inproc=self.pre_reject(A["tokens"], t["spec"]), **meta))
        return jobs

    # ---- P0: eval tiering
    def task_eval(self, t):
        name, spec = t["name"], t["spec"]
        out = OrderedDict(name=name, g=t["g"], band=t["band"], bt=t["bt"],
                          parent_anchor=t["anchor"], status="running", stage="TF1-s1",
                          profile=PROF)
        self.eval_out[name] = out
        tf1 = []
        for s in (1, 2):
            jobs = self.tf1_jobs("E-TF1", t, s)
            recs = yield jobs
            tf1 += [self.summ(r, s, spec, anchor=j.meta["anchor"]) for j, r in zip(jobs, recs)]
            out["TF1"] = tf1
            sol = [f"{x['anchor']}@s{x['seed']}" for x in tf1 if x["feasible"]]
            if sol:
                out.update(tier="T1", tier_seed=s, solvers=sol, status="done", stage="done", ts=now())
                self.fh["eval_tasks.jsonl"].write(B.jdump(out) + "\n")
                return
            out["stage"] = "TF1-s2"
        # shown anchor = parent (fails at seed 1 here by construction)
        an = t["anchor"]
        space = [x for x in self.f2space[an] if x["rt_ok"]]
        if self.a.f2_limit:
            space = space[: self.a.f2_limit]
            out["f2_SMOKE_SUBSET"] = self.a.f2_limit
        out["stage"] = "F2-s1"
        f2 = []
        live = []
        for x in space:
            j = self.job("E-F2", x["tokens"], spec, 1, task=name, band=t["band"], anchor=an,
                         edit=x["desc"], idx=x["idx"], inproc=self.pre_reject(x["tokens"], spec))
            if j.meta["inproc"]:
                f2.append(self.summ(self.inproc(j), 1, spec, edit=x["desc"], idx=x["idx"]))
            else:
                live.append(j)
        out["f2_progress"] = f"0/{len(live)}"
        recs = yield live
        f2 += [self.summ(r, 1, spec, edit=j.meta["edit"], idx=j.meta["idx"]) for j, r in zip(live, recs)]
        near = [x for x in f2 if not x["feasible"] and not x["inproc_reject"]
                and x["worst"] is not None and x["worst"] >= -NEAR]
        out["stage"] = "F2-s2"
        out["f2_near"] = len(near)
        if near:
            byidx = {x["idx"]: x for x in space}
            jobs = [self.job("E-F2", byidx[x["idx"]]["tokens"], spec, 2, task=name, band=t["band"],
                             anchor=an, edit=x["edit"], idx=x["idx"]) for x in near]
            recs = yield jobs
            f2 += [self.summ(r, 2, spec, edit=j.meta["edit"], idx=j.meta["idx"])
                   for j, r in zip(jobs, recs)]
        s1 = [x for x in f2 if x["seed"] == 1 and x["feasible"]]
        s2 = [x for x in f2 if x["seed"] == 2 and x["feasible"]]
        out["F2"] = f2
        out["f2_n_space"] = len(space)
        out["f2_n_sized_s1"] = len(live)
        out["f2_solving"] = [f"{x['edit']}@s{x['seed']}" for x in s1 + s2]
        out.update(tier="T2" if (s1 or s2) else "T3", status="done", stage="done", ts=now())
        self.fh["eval_tasks.jsonl"].write(B.jdump(out) + "\n")

    # ---- P0b: training tasks
    def task_train(self, t, new):
        name, spec = t["name"], t["spec"]
        out = OrderedDict(name=name, g=t["g"], band=t["band"], bt=t["bt"], anchor=t["anchor"],
                          origin=t["origin"], status="running", profile=PROF)
        self.train_out[name] = out
        if new:
            wit = []
            for s in (1, 2):
                (r,) = yield [self.job("T-wit", t["tokens"], spec, s, task=name, band=t["band"])]
                wit.append(self.summ(r, s, spec))
                if wit[-1]["feasible"]:
                    break
            out["witness"] = wit
            if not any(x["feasible"] for x in wit):
                out.update(status="unproved", ts=now())
                t["status"] = "unproved"
                self.fh["train_tasks.jsonl"].write(B.jdump(self.trec(t, out)) + "\n")
                return
            jobs = self.tf1_jobs("T-F1", t, 1)
            recs = yield jobs
            out["T-F1"] = [self.summ(r, 1, spec, anchor=j.meta["anchor"]) for j, r in zip(jobs, recs)]
        else:
            a3 = t["a3"]
            out["witness"] = [dict(x) for x in a3["witness"]]
            out["T-F1"] = [dict(x) for x in a3["T-F1"]]
            for x in out["witness"] + out["T-F1"]:
                assert x["jid"] in self.cache, (name, x["jid"])
                x["worst"] = self.margin(spec, (self.cache[x["jid"]].get("res") or {})) \
                    if x.get("n_evals") else None
        npos = 1 + sum(1 for x in out["T-F1"] if x["feasible"])
        out["se"] = None
        if npos < MAX_POS:
            cand = self.se_candidate(t, out)
            if cand is not None:
                ses = []
                for s in (1, 2):
                    (r,) = yield [self.job("T-SE", cand["tokens"], spec, s, task=name,
                                           band=t["band"], anchor=cand["anchor"],
                                           edit=cand["desc"], idx=cand["idx"], src=cand["id"])]
                    ses.append(self.summ(r, s, spec))
                    if ses[-1]["feasible"]:
                        break
                out["se"] = {"candidate": {k: cand[k] for k in ("id", "anchor", "idx", "desc", "wl")},
                             "runs": ses, "verified": any(x["feasible"] for x in ses)}
        out.update(status="ok", ts=now())
        t["status"] = "ok"
        self.fh["train_tasks.jsonl"].write(B.jdump(self.trec(t, out)) + "\n")

    @staticmethod
    def trec(t, out):
        d = {k: v for k, v in t.items() if k not in ("tokens", "a3", "stages", "amend1_stages",
                                                     "amend2", "evidence")}
        d["pv0"] = out
        return d

    def se_candidate(self, t, out):
        """first (by id) recorded rl-v1.2 single-edit design of the same band meeting
        the task's limits (port-DC OK, wide-stable), whose topology differs from the
        witness and every anchor."""
        for d in self.se_pool.get(t["band"], []):
            if d["wl"] == t["wl"] or d["wl"] in {A["wl"] for A in self.anch.values()}:
                continue
            if d["pdc_ok"] and B.satisfies(d["metrics"], d["stab_ok"], t["bt"], t["limits"]):
                return d
        return None

    # ---- P0b: generation
    def n_ok_train(self):
        return sum(1 for o in self.train_out.values() if o["status"] == "ok")

    def est_examples(self):
        n = 0
        for o in self.train_out.values():
            if o["status"] != "ok":
                continue
            tf1 = o.get("T-F1") or []
            fails = [x for x in tf1 if not x["feasible"] and not x.get("inproc_reject")
                     and x.get("n_evals")]
            if not fails:
                continue
            n += min(MAX_POS, 1 + sum(1 for x in tf1 if x["feasible"])
                     + (1 if (o.get("se") or {}).get("verified") else 0))
        return n

    def task_gen(self):
        G = self.G
        gen = G.gen0
        empty = 0
        self.gen_state = {"status": "running", "gen": gen, "Q": G.Q}
        n_gen_new = 0
        while True:
            if self.a.gen_max_new is not None and n_gen_new >= self.a.gen_max_new:
                self.log(f"gen: SMOKE cap of {self.a.gen_max_new} planted tasks reached")
                break
            cands = G.make_generation("train", gen)
            self.event("gen_start", gen=gen, n=len(cands), Q=G.Q)
            self.gen_state.update(gen=gen, Q=G.Q, last_gen_n=len(cands))
            if not cands:
                at_q = all(G.train_have(g) >= G.Q for g in G.train_points)
                if not at_q:
                    empty += 1
                    if empty >= 3:
                        self.log(f"gen: exhausted (no admissible candidates) at gen {gen}")
                        break
                    gen += 1
                    continue
                # every point at its quota: wait for all planted tasks, then decide
                self.gen_state["status"] = "waiting for planted tasks"
                while any(o["status"] == "running" for o in self.train_out.values()):
                    yield []
                nok, est = self.n_ok_train(), self.est_examples()
                self.log(f"gen: all points at Q={G.Q}; ok training-side tasks {nok}, "
                         f"est. examples {est}")
                if nok >= TARGET_OK and est >= TARGET_EX:
                    break
                if G.Q >= QMAX:
                    self.log(f"gen: QMAX {QMAX} reached, stopping short of the target")
                    break
                G.Q += QSTEP
                self.event("quota_up", Q=G.Q, ok=nok, est_examples=est)
                self.gen_state["status"] = "running"
                empty = 0
                gen += 1
                continue
            empty = 0
            jobs = [B.Job("search", "train", c["tokens"], G.probe[tuple(c["g"].split("-"))], 1,
                          meta={"cid": c["cid"], "stream": "train", "stage": "search"},
                          profile=PROF) for c in cands]
            recs = yield jobs
            for c, j, r in zip(cands, jobs, recs):
                G.process_candidate("train", c, j, r)
            feas = [c for c in cands if c["feasible"]]
            if feas:
                cj = [B.Job("confirm", "train", c["tokens"], G.probe[tuple(c["g"].split("-"))], 2,
                            meta={"cid": c["cid"], "stream": "train", "stage": "confirm"},
                            profile=PROF) for c in feas]
                crecs = yield cj
                before = len(self.new_tasks)
                for c, r in zip(feas, crecs):
                    G.plant("train", c, r)
                n_gen_new += len(self.new_tasks) - before
            gen += 1
        self.gen_state["status"] = "done"
        while any(o["status"] == "running" for o in self.train_out.values()):
            yield []
        self.log(f"gen: finished at gen {gen}; Q={G.Q}; new planted {len(self.new_tasks)}; "
                 f"ok training-side {self.n_ok_train()}; est. examples {self.est_examples()}")

    # ------------------------------------------------------------- progress
    def eta_calls(self):
        p0 = sum(1 for _p, _s, j in self.pending if j.kind in P0_KINDS) + \
            sum(1 for _p, j, _t in self.running.values() if j.kind in P0_KINDS)
        for t in self.eval_tasks:
            o = self.eval_out.get(t["name"]) or {}
            st = o.get("stage")
            if st == "TF1-s2":
                p0 += self.f2_live.get(t["name"], 0) * 1.15
            elif st == "F2-s1":
                p0 += self.f2_live.get(t["name"], 0) * 0.15
        p0b = sum(1 for _p, _s, j in self.pending if j.kind not in P0_KINDS) + \
            sum(1 for _p, j, _t in self.running.values() if j.kind not in P0_KINDS)
        for o in self.train_out.values():         # later stages of running tasks
            if o["status"] == "running":
                p0b += 0.5 if "T-F1" in o else 4.5
        if self.gen_state.get("status") not in ("done", "not started"):
            nok = self.n_ok_train()
            need = max(0, TARGET_OK - nok, int((TARGET_EX - self.est_examples()) / 1.8))
            p0b += need * 7.5          # ~search 1.7 + confirm 1 + wit 1.2 + T-F1 3.5
        return int(p0), int(p0b)

    def progress(self, final=False, status=None):
        rec = [s for t, s in self.recent if time.time() - t < 3600]
        med = statistics.median(rec) if rec else (statistics.median(
            [s for _t, s in self.recent]) if self.recent else 90.0)
        lim = self.limit()
        p0, p0b = self.eta_calls()
        eta_p0 = p0 * med / max(1, lim - (self.reserve(lim) if p0b else 0)) / 3600.0
        eta_all = (p0 + p0b) * med / max(1, lim) / 3600.0
        tiers = Counter(o.get("tier") for o in self.eval_out.values() if o.get("status") == "done")
        G = getattr(self, "G", None)
        p = {"ts": now(), "pid": os.getpid(), "run_dir": self.rd, "profile": PROF,
             "phase": PHASE, "era": self.era,
             "status": status or ("final" if final else B.DISK.state() if B.DISK.paused()
                                  else "running"),
             "started": B.iso(self.t0), "elapsed_h": round((time.time() - self.t0) / 3600, 3),
             "load1": B.load1(), "proc_limit": lim, "running": len(self.running),
             "running_p0": sum(1 for _p, j, _t in self.running.values() if j.kind in P0_KINDS),
             "pending": len(self.pending),
             "calls": {"new_this_session": self.n_new, "cache_rows_at_start": self.n_cached_start,
                       "cpu_h_this_session": round(self.cpu_new / 3600, 2),
                       "median_secs_last_hour": round(med, 1)},
             "disk": {"state": B.DISK.state(), "free_gb": B.DISK.free_gb,
                      "tmp_free_gb": B.DISK.tmp_free_gb, "failed_writes": B.DISK.n_errors,
                      "pauses": B.DISK.pauses},
             "P0": {"n_tasks": len(self.eval_tasks),
                    "done": sum(1 for o in self.eval_out.values() if o.get("status") == "done"),
                    "tiers_so_far": dict(tiers),
                    "stage": dict(Counter(o.get("stage") for o in self.eval_out.values())),
                    "in_f2": {n: o.get("f2_progress") for n, o in self.eval_out.items()
                              if str(o.get("stage", "")).startswith("F2")},
                    "built": self.eval_built,
                    "eta_remaining_calls": p0, "eta_h": round(eta_p0, 2),
                    "eta_finish": B.iso(time.time() + eta_p0 * 3600)},
             "P0b": {"gen": self.gen_state, "Q": getattr(G, "Q", None),
                     "new_planted": len(self.new_tasks),
                     "new_planted_per_point": dict(getattr(G, "new_planted", {}) or {}),
                     "train_status": dict(Counter(o["status"] for o in self.train_out.values())),
                     "ok_training_side": self.n_ok_train(), "target_ok": TARGET_OK,
                     "est_examples": self.est_examples(), "target_examples_est": TARGET_EX,
                     "search_stats": dict(G.search_stats["train"]) if G else None,
                     "fence": dict(self.fence_stats), "built": self.data_built,
                     "eta_remaining_calls_est": p0b},
             "eta": {"remaining_calls_est": p0 + p0b, "hours_est": round(eta_all, 2),
                     "finish_est": B.iso(time.time() + eta_all * 3600)}}
        for o in self.eval_out.values():
            if str(o.get("stage", "")).startswith("F2") and o.get("f2_progress"):
                pass
        B.atomic_write(f"{self.rd}/progress.json", json.dumps(p, indent=1, default=repr),
                       critical=False)
        self.last_progress = time.time()

    def limit(self):
        return self.a.max_procs if B.load1() <= 22.0 else min(self.a.max_procs, 4)

    @staticmethod
    def reserve(lim):
        return 3 if lim >= 8 else (1 if lim >= 2 else 0)

    def pick(self, lim):
        """P0 first, but >= reserve(lim) slots stay for P0b while it has work."""
        has_b = any(j.kind not in P0_KINDS for _p, _s, j in self.pending)
        run_p0 = sum(1 for _p, j, _t in self.running.values() if j.kind in P0_KINDS)
        cap_p0 = lim - (self.reserve(lim) if has_b else 0)
        for i, (_pr, _sq, j) in enumerate(self.pending):
            if j.kind in P0_KINDS and run_p0 >= cap_p0:
                continue
            return i
        return None

    def update_f2_progress(self):
        for t in self.eval_tasks:
            o = self.eval_out.get(t["name"])
            if o and o.get("stage") == "F2-s1":
                live = int(str(o.get("f2_progress", "0/0")).split("/")[1])
                tk = [x for x in self.tasks if x[0] == f"eval:{t['name']}"]
                if tk and tk[0][2]:
                    done = sum(1 for j in tk[0][2] if j in self.cache)
                    o["f2_progress"] = f"{done}/{live}"

    def disk_tick(self):
        t = time.time()
        D = B.DISK
        if D.full_since is not None and not D.backoff_active():
            ok = all([a.flush() for a in self.fh.values()])
            if ok and B.atomic_write(f"{self.rd}/.disk_probe", f"{t}\n", critical=False):
                t0 = D.full_since
                D.clear()
                self.event("disk_resume", pause="enospc", paused_s=round(t - t0, 1))
        if t - self.last_disk < 30:
            return
        self.last_disk = t
        for a in self.fh.values():
            a.flush()
        if getattr(self, "G", None):
            self.G.rt_fh.flush()

        def free_gb(p):
            try:
                v = os.statvfs(p)
                return round(v.f_bavail * v.f_frsize / 1e9, 2)
            except OSError:
                return None
        D.free_gb, D.tmp_free_gb = free_gb(self.rd), free_gb(os.environ.get("TMPDIR") or "/tmp")
        low = ((D.free_gb is not None and D.free_gb < B.DISK_MIN_FREE_GB) or
               (D.tmp_free_gb is not None and D.tmp_free_gb < B.TMP_MIN_FREE_GB))
        if low and not D.low:
            D.low, D.low_since = True, t
            self.log(f"LOW DISK: {D.free_gb} GB free (TMPDIR {D.tmp_free_gb} GB): pausing launches")
            self.event("disk_pause", free_gb=D.free_gb, tmp_free_gb=D.tmp_free_gb)
        elif not low and D.low:
            D.pauses.append(["low_disk", D.low_since, t])
            self.log(f"DISK OK again ({D.free_gb} GB free): resuming launches")
            self.event("disk_resume", pause="low_disk", paused_s=round(t - D.low_since, 1))
            D.low, D.low_since = False, None

    def sigterm(self, *_a):
        self.log("SIGTERM: stopping (running workers killed; a restart re-runs them)")
        self.stop = True
        for _jid, (p, _j, _t) in list(self.running.items()):
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except Exception:                                    # noqa: BLE001
                pass

    def close(self, max_wait_s=600.0):
        fhs = list(self.fh.values()) + ([self.G.rt_fh] if getattr(self, "G", None) else [])
        t_end = time.time() + max_wait_s
        while any(a.pending() for a in fhs) and time.time() < t_end:
            if not all([a.flush() for a in fhs]):
                time.sleep(max(1.0, min(B.DISK.delay, t_end - time.time())))
        for a in fhs:
            p = a.spill(os.path.join(os.environ.get("TMPDIR") or "/tmp", "pv0-spill"))
            if p:
                print(f"DISK FULL AT EXIT: rows of {a.path} spilled to {p}", file=sys.stderr)

    # ------------------------------------------------------------------ run
    def setup(self):
        self.load_inputs()
        for t in self.eval_tasks:
            self.spawn(f"eval:{t['name']}", self.task_eval(t))
        if not self.a.no_gen:
            self.G = Gen(self, sorted({tuple(t["g"].split("-")) for t in self.train_old}),
                         self.f2space, self.old_cands, self.cal_rows())
            self.next_seq = 1000
            self.log(f"gen: start gen {self.G.gen0}, Q0 {Q0}, archive kept "
                     f"{self.G.pdc['archive_kept']} (dropped {self.G.pdc['archive_dropped_prefilter']}), "
                     f"cal pool {sum(len(v) for v in self.G.pool_cal.values())}")
            for t in (self.train_old if not self.a.train_limit else self.train_old[: self.a.train_limit]):
                self.spawn(f"trainold:{t['name']}", self.task_train(t, new=False))
            self.spawn("gen", self.task_gen())

    def run(self):
        signal.signal(signal.SIGTERM, self.sigterm)
        B.atomic_write(f"{self.rd}/sched.pid", f"{os.getpid()}\n")
        st = {"t_start": now(), "args": vars(self.a), "era": self.era,
              "prereg": "kaggle/PREREG-PILOT-V0.md (137ea060a)", "profile": PROF}
        B.atomic_write(f"{self.rd}/start.{int(self.t0)}.json", json.dumps(st, indent=1, default=repr))
        self.setup()
        self.progress()
        while not self.stop:
            self.reap()
            self.step_tasks()
            self.disk_tick()
            lim = self.limit()
            if not B.DISK.paused():
                while len(self.running) < lim and self.pending:
                    i = self.pick(lim)
                    if i is None:
                        break
                    pr, sq, j = self.pending.pop(i)
                    if j.jid in self.cache:
                        self.queued.discard(j.jid)
                        continue
                    if not self.launch(j):
                        self.pending.insert(i, (pr, sq, j))
                        break
            if not self.eval_built and self.eval_tasks and all(
                    (self.eval_out.get(t["name"]) or {}).get("status") == "done" for t in self.eval_tasks):
                self.log("P0 tiering complete -> build-eval")
                try:
                    build_eval(self)
                    self.eval_built = True
                except Exception as e:                           # noqa: BLE001
                    import traceback
                    self.log(f"build-eval FAILED: {e!r}\n{traceback.format_exc()}")
                    self.eval_built = "failed"
            if time.time() - self.last_progress > 30:
                self.update_f2_progress()
                self.progress()
            if not self.running and not self.pending and all(t[3] for t in self.tasks):
                break
            time.sleep(1.0)
        if self.stop:
            while self.running:
                self.reap()
                time.sleep(0.5)
            self.progress(status="stopped")
            self.close()
            return
        if not self.a.no_gen:
            self.log("P0b complete -> build-data")
            try:
                build_data(self)
                self.data_built = True
            except Exception as e:                               # noqa: BLE001
                import traceback
                self.log(f"build-data FAILED: {e!r}\n{traceback.format_exc()}")
        self.progress(final=True)
        self.log("exit")
        self.close()


# ===================================================================== build
def ec_stage_cost(stages):
    """E-c random-order expectation, stage-wise: stages = [[(feasible, secs), ...], ...]
    over SIZED calls only. A stage with no feasible call is paid in full; inside the
    first stage with K >= 1 feasible: calls (N-K)/(K+1)+1, seconds
    sum_infeasible/(K+1) + mean_feasible."""
    calls, secs = 0.0, 0.0
    for st in stages:
        K = sum(1 for f, _s in st if f)
        if K == 0:
            calls += len(st)
            secs += sum(s for _f, s in st)
            continue
        N = len(st)
        calls += (N - K) / (K + 1) + 1
        secs += sum(s for f, s in st if not f) / (K + 1) + statistics.mean(s for f, s in st if f)
        return {"calls": round(calls, 2), "spice_min": round(secs / 60, 2), "found": True}
    return {"calls": round(calls, 2), "spice_min": round(secs / 60, 2), "found": False}


def shown_anchor(t, tf1_s1):
    """parent anchor if it is sized and infeasible at seed 1, else the first sized,
    infeasible anchor in the band's parent order (README D-P2); None if none fails."""
    by = {x["anchor"]: x for x in tf1_s1}
    order = [t["anchor"]] + [a for a in B.PARENTS[t["bt"]] if a != t["anchor"]]
    for a in order:
        x = by.get(a)
        if x and x.get("n_evals") and not x["feasible"] and not x.get("inproc_reject"):
            return a
    return None


def prompt_for(R, spec_path, an, ev):
    os.environ.pop("EDITCAP_FEWSHOT", None)
    os.environ.pop("EDITCAP_NO_THINK", None)
    sys.path.insert(0, f"{REPO}/kaggle")
    import editcap_run as ER
    from spec import Spec
    A = R.anch[an]
    anchor_net = open(f"{REPO}/{A['net_file']}").read()
    msgs, text = ER.build_prompt_B(Spec.load(spec_path), anchor_net, ev, k=1)
    return msgs, text


def evidence_for(R, t, an, seed_rows):
    c = {"name": t["name"]}
    return B.make_evidence(c, t["spec"], seed_rows, R.anch[an])


def build_eval(R, partial=False):
    import yaml  # noqa: F401
    out_dir = (f"{R.rd}/eval-partial" if partial else EVAL if R.rd == f"{HERE}/run"
               else f"{R.rd}/eval-out")              # smoke / test run dirs never touch eval/
    os.makedirs(f"{out_dir}/prompts", exist_ok=True)
    os.makedirs(f"{out_dir}/specs", exist_ok=True)
    tiers, bar = OrderedDict(), OrderedDict()
    for t in R.eval_tasks:
        o = R.eval_out.get(t["name"]) or {}
        if o.get("status") != "done":
            continue
        n = t["name"]
        tf1 = o["TF1"]
        s1 = [x for x in tf1 if x["seed"] == 1]
        an = shown_anchor(t, s1)
        if an is None:
            tiers[n] = {"tier": o["tier"], "excluded": "no anchor fails at seed 1 (no shown anchor)"}
            continue
        row = [R.cache[x["jid"]] for x in s1 if x["anchor"] == an][0]
        ev = evidence_for(R, t, an, [(1, row)])
        assert not ev["feasible"]
        msgs, text = prompt_for(R, t["spec"], an, ev)
        shutil.copy(t["spec"], f"{out_dir}/specs/{n}.yaml")
        B.atomic_write(f"{out_dir}/prompts/{n}.json", json.dumps(OrderedDict(
            task=n, kind="held-out training-pool task", family=t["g"], band_type=t["bt"],
            spec_file=f"specs/{n}.yaml", spec_sha=B.spec_sha(t["spec"]), shown_anchor=an,
            shown_anchor_family=R.anch[an]["family"], arm="B", k=1, fewshot=False,
            messages=msgs, prompt_text=text, evidence=ev), indent=1, default=float))
        sized = lambda xs: [(x["feasible"], x["secs"] or 0.0) for x in xs  # noqa: E731
                            if not x.get("inproc_reject") and x.get("n_evals")]
        lib_st = [sized([x for x in tf1 if x["seed"] == s]) for s in (1, 2)
                  if any(x["seed"] == s for x in tf1)]
        lib_cost = ec_stage_cost(lib_st)
        rec = OrderedDict(tier=o["tier"], family=t["g"], band_type=t["bt"],
                          parent_anchor=t["anchor"], shown_anchor=an,
                          pool_label_amend3=t["difficulty_pool"],
                          witness={"wl": t["wl"], "tok": t["tok"], "EVAL_ONLY": True,
                                   "file": f"kaggle/train-pool-v2/{n}/witness/witness.net"},
                          library_solvers=o.get("solvers") or [],
                          tf1_calls=[{k: x[k] for k in ("anchor", "seed", "feasible", "worst", "secs",
                                                        "inproc_reject", "jid")} for x in tf1])
        b = OrderedDict(tier=o["tier"])
        if o["tier"] == "T1":
            b["search"] = "random order over the library anchors' sizing calls (seed 1, then seed 2)"
            b.update(lib_cost)
            b["n_sized"] = sum(len(s) for s in lib_st)
            b["n_feasible"] = sum(1 for s in lib_st for f, _ in s if f)
        else:
            f2 = o["F2"]
            f2s1 = sized([x for x in f2 if x["seed"] == 1])
            f2s2 = sized([x for x in f2 if x["seed"] == 2])
            rec.update(f2_n_space=o["f2_n_space"], f2_n_sized_s1=len(f2s1),
                       f2_n_prereject=sum(1 for x in f2 if x.get("inproc_reject")),
                       f2_n_near_s2=len(f2s2), f2_solving=o["f2_solving"])
            exhaust_min = round((sum(s for _f, s in lib_st[0] + (lib_st[1] if len(lib_st) > 1 else []))
                                 + sum(s for _f, s in f2s1 + f2s2)) / 60, 2)
            if o["tier"] == "T2":
                c = ec_stage_cost([f2s1, f2s2])
                b["search"] = ("random order over the shown anchor's single edits (seed 1; then "
                               "seed 2 over the near-feasible ones), E-c method")
                b.update(c)
                b["n_sized"] = len(f2s1) + len(f2s2)
                b["n_feasible_s1"] = sum(1 for f, _ in f2s1 if f)
                b["n_feasible_s2"] = sum(1 for f, _ in f2s2 if f)
                cl = ec_stage_cost([s for s in lib_st] + [f2s1, f2s2])
                b["incl_failed_library_stage"] = {"calls": cl["calls"], "spice_min": cl["spice_min"]}
            else:
                b["search"] = ">F2 space"
                b["F2_space_exhausted"] = {"calls": len(f2s1) + len(f2s2),
                                           "spice_min": round(sum(s for _f, s in f2s1 + f2s2) / 60, 2)}
                b["library_stage"] = {"calls": sum(len(s) for s in lib_st),
                                      "spice_min": lib_cost["spice_min"]}
            b["exhaust_library_plus_f2_spice_min"] = exhaust_min
        tiers[n] = rec
        bar[n] = b
    # ---- the 2 strict bench-v2 cells (T3, eval-only)
    cells3 = B.load_jsonl_last(f"{A3}/run/cells_amend3.jsonl", "name")
    a3cache = {}
    for r in B.read_jsonl(f"{A3}/run/results.jsonl"):
        a3cache[r["jid"]] = r
    strict_checks = OrderedDict()
    for cn in STRICT:
        o = cells3[cn]
        c = R.cells[cn]
        chk = OrderedDict()
        chk["status_pass"] = o["status"] == "pass" and o["why"] == "all_filters_pass_rl_v1_2"
        bad = []
        for stg, v in o["stages"].items():
            for x in v["runs"]:
                r = a3cache.get(x["jid"])
                if r is None or r.get("profile") != PROF or B.feasible(r) != x["feasible"]:
                    bad.append(f"{stg}:{x['jid']}")
        chk["rows_rl_v1_2_and_consistent"] = not bad
        chk["bad_rows"] = bad
        st = o["stages"]
        chk["A1"] = sum(x["feasible"] for x in st["A1"]["runs"]) >= 2
        chk["A2"] = any(x["feasible"] for x in st["A2"]["runs"])
        chk["A3"] = any(x["feasible"] for x in st["A3"]["runs"])
        chk["F1_none_feasible_s1_s2"] = (not any(x["feasible"] for x in st["F1"]["runs"])
                                         and {x["seed"] for x in st["F1"]["runs"]} == {1, 2})
        chk["F2_none_feasible_s1_s2"] = (not any(x["feasible"] for x in st["F2"]["runs"])
                                         and {x["seed"] for x in st["F2"]["runs"]} == {1, 2}
                                         and st["F2"]["n_space"] == len(
                                             [x for x in R.f2space[c["anchor"]] if x["rt_ok"]]))
        wt = json.load(open(f"{SRC}/cells/{cn}/witness/witness.tokens.json"))
        chk["witness_tok_matches"] = B.tokhash(wt) == c["tok"]
        chk["all_pass"] = all(v for k, v in chk.items() if k != "bad_rows")
        strict_checks[cn] = chk
        spec = c["spec"] if os.path.exists(c["spec"]) else f"{SRC}/specs/{os.path.basename(c['spec'])}"
        row = [a3cache[x["jid"]] for x in st["F1"]["runs"] if x["anchor"] == c["anchor"] and x["seed"] == 1][0]
        tt = {"name": cn, "spec": spec}
        ev = evidence_for(R, tt, c["anchor"], [(1, row)])
        msgs, text = prompt_for(R, spec, c["anchor"], ev)
        shutil.copy(spec, f"{out_dir}/specs/{cn}.yaml")
        B.atomic_write(f"{out_dir}/prompts/{cn}.json", json.dumps(OrderedDict(
            task=cn, kind="bench-v2 strict cell (AMENDMENT 3 pass)", family=c["g"],
            band_type=c["bt"], spec_file=f"specs/{cn}.yaml", spec_sha=B.spec_sha(spec),
            shown_anchor=c["anchor"], shown_anchor_family=R.anch[c["anchor"]]["family"], arm="B",
            k=1, fewshot=False, messages=msgs, prompt_text=text, evidence=ev),
            indent=1, default=float))
        f1 = [(x["feasible"], x["secs"] or 0.0) for x in st["F1"]["runs"]
              if not x.get("inproc_reject") and x.get("n_evals")]
        f2 = [(x["feasible"], x["secs"] or 0.0) for x in st["F2"]["runs"]
              if not x.get("inproc_reject") and x.get("n_evals")]
        tiers[cn] = OrderedDict(tier="T3", family=c["g"], band_type=c["bt"], parent_anchor=c["anchor"],
                                shown_anchor=c["anchor"], source="bench-v2 strict cell",
                                witness={"wl": c["wl"], "tok": c["tok"], "EVAL_ONLY": True,
                                         "file": f"kaggle/campaigns/bench-v2/run/cells/{cn}/witness/witness.net"},
                                core_signature=c.get("cls"), primary_atom=c.get("primary_atom"),
                                rl_v1_2_check=chk)
        bar[cn] = OrderedDict(tier="T3", search=">F2 space",
                              F2_space_exhausted={"calls": len(f2), "spice_min": round(sum(s for _f, s in f2) / 60, 2),
                                                  "seeds": [1, 2]},
                              library_stage={"calls": len(f1), "spice_min": round(sum(s for _f, s in f1) / 60, 2)},
                              exhaust_library_plus_f2_spice_min=round(sum(s for _f, s in f1 + f2) / 60, 2))
    hist = Counter(v["tier"] for v in tiers.values() if not v.get("excluded"))
    by_fam = defaultdict(Counter)
    for v in tiers.values():
        if not v.get("excluded"):
            by_fam[v["family"]][v["tier"]] += 1

    def agg(tier):
        xs = [b for b in bar.values() if b["tier"] == tier and b.get("found")]
        if not xs:
            return None
        return {"n": len(xs), "median_calls": statistics.median(x["calls"] for x in xs),
                "median_spice_min": statistics.median(x["spice_min"] for x in xs),
                "mean_spice_min": round(statistics.mean(x["spice_min"] for x in xs), 2)}
    tj = OrderedDict(prereg="kaggle/PREREG-PILOT-V0.md (137ea060a)", verifier=PROF, pdk=B.PDK,
                     budget=B.BUDGET, split_sha256=open(f"{EVAL}/split.json.sha256").read().split()[0],
                     partial=partial, n_items=len([v for v in tiers.values() if not v.get("excluded")]),
                     tier_hist=dict(hist), per_family={k: dict(v) for k, v in by_fam.items()},
                     definitions={
                         "T1": "some library anchor a1-a5 is feasible at the task spec at seed 1 "
                               "(AMENDMENT-3 T-F1 rows) or, if none, at seed 2",
                         "T2": "not T1; some single edit of the shown anchor is feasible at seed 1 "
                               "(full enumeration) or at seed 2 (re-tried when its seed-1 worst "
                               "margin incl. wide mu-1 is >= -0.1)",
                         "T3": "neither; a verified witness exists (EVAL-ONLY)"},
                     strict_cells_check=strict_checks, items=tiers)
    B.atomic_write(f"{out_dir}/tiers.json", json.dumps(tj, indent=1, default=repr))
    bj = OrderedDict(prereg="kaggle/PREREG-PILOT-V0.md (137ea060a)", verifier=PROF,
                     method=("E-c (kaggle/campaigns/bench-v12-audit/E-c): expected cost to the first "
                             "feasible design for blind search in uniformly random order over SIZED "
                             "calls (in-process pre-rejects cost 0 and are excluded); calls = "
                             "(N-K)/(K+1)+1, SPICE-min = (sum_infeasible secs/(K+1) + "
                             "mean_feasible secs)/60, stage-wise (a stage without a feasible call "
                             "is paid in full). Seconds are smoke_run wall seconds under the shared "
                             "load at run time (cached rows reused)."),
                     aggregate={"T1": agg("T1"), "T2": agg("T2")}, items=bar)
    B.atomic_write(f"{out_dir}/searchbar.json", json.dumps(bj, indent=1, default=repr))
    R.log(f"build-eval -> {out_dir}: tiers {dict(hist)}; strict checks "
          f"{ {k: v['all_pass'] for k, v in strict_checks.items()} }")


def anchor_target(R, an):
    return body_lines(open(f"{REPO}/{R.anch[an]['net_file']}").read())


def vrec(R, r, spec, source):
    res = r.get("res") or {}
    pd = res.get("port_dc")
    return OrderedDict(verifier=res.get("verifier", {}).get("profile"), pdk=B.PDK,
                       budget=r.get("budget"), seed=r.get("seed"), jid=r["jid"],
                       spec_sha=B.spec_sha(spec), feasible=bool(res.get("feasible")),
                       metrics={k: v for k, v in (res.get("metrics") or {}).items()
                                if isinstance(v, (int, float))},
                       worst_margin=R.margin(spec, res), mu_min_wide=res.get("mu_min_wide"),
                       stab_wide_ok=res.get("stab_wide_ok"),
                       port_dc_pass=pd.get("pass") if isinstance(pd, dict) else None,
                       n_evals=res.get("n_evals"), era=r.get("era"), source=source,
                       results_file=R.cache_src.get(r["jid"]))


def build_data(R, partial=False):
    out_dir = (f"{R.rd}/data-partial" if partial else DATA if R.rd == f"{HERE}/run"
               else f"{R.rd}/data-out")
    os.makedirs(out_dir, exist_ok=True)
    # rl-v1.2 anchor pool for difficulty labels (AMENDMENT-3 F1/T-F1 + P0b T-F1; never P0 rows)
    anch_pool = defaultdict(list)
    for r in R.cache.values():
        if r.get("profile") != PROF or r.get("kind") not in ("F1", "T-F1"):
            continue
        res = r.get("res") or {}
        m = res.get("metrics") or {}
        if not m:
            continue
        pd, pf = res.get("port_dc"), res.get("port_dc_prefilter")
        pdc = bool(pd.get("pass")) if isinstance(pd, dict) else bool((pf or {}).get("pass"))
        anch_pool[(r.get("meta") or {}).get("band")].append(
            {"metrics": {k: v for k, v in m.items() if isinstance(v, (int, float))},
             "stab_ok": bool(res.get("stab_wide_ok")), "pdc_ok": pdc})
    tasks = OrderedDict()
    for t in R.train_old:
        tasks[t["name"]] = t
    for n, t in R.new_tasks.items():
        tasks[n] = t
    examples, skipped, labels = [], Counter(), {}
    held_fam = set(R.split["heldout_families"])
    for n, t in tasks.items():
        o = R.train_out.get(n)
        if not o or o["status"] != "ok":
            skipped["not_ok"] += 1
            continue
        assert t["g"] not in held_fam
        spec = t["spec"]
        tf1 = o["T-F1"]
        lib = [x["anchor"] for x in tf1 if x["feasible"]]
        se_ok = bool((o.get("se") or {}).get("verified"))
        if lib:
            lab = "library-solvable"
        elif any(d["pdc_ok"] and B.satisfies(d["metrics"], d["stab_ok"], t["bt"], t["limits"])
                 for d in anch_pool.get(t["band"], [])):
            lab = "library-solvable"
        elif se_ok or R.se_candidate(t, o) is not None:
            lab = "single-edit-solvable"
        else:
            lab = "witness-only"
        labels[n] = lab
        an = shown_anchor(t, tf1)
        if an is None:
            skipped["no_failing_anchor"] += 1
            continue
        row = [R.cache[x["jid"]] for x in tf1 if x["anchor"] == an][0]
        ev = evidence_for(R, t, an, [(1, row)])
        assert not ev["feasible"]
        msgs, text = prompt_for(R, spec, an, ev)
        pos = []
        wj = [x for x in o["witness"] if x["feasible"]][0]
        pos.append(("witness", body_lines(t["netlist"]), t["wl"], t["tok"],
                    R.cache[wj["jid"]], {"cid": t.get("cid"), "script": t.get("script"),
                                         "repairs": t.get("repairs"), "parent_anchor": t["anchor"]}))
        libs = sorted(lib, key=lambda a: (a != t["anchor"], a))
        if libs:
            a0 = libs[0]
            x = [x for x in tf1 if x["anchor"] == a0][0]
            pos.append((f"library:{a0}", anchor_target(R, a0), R.anch[a0]["wl"], R.anch[a0]["tok"],
                        R.cache[x["jid"]], {"anchor": a0, "family": R.anch[a0]["family"]}))
        if se_ok:
            se = o["se"]
            cand = se["candidate"]
            spx = R.f2space[cand["anchor"]][cand["idx"]]
            rj = [x for x in se["runs"] if x["feasible"]][0]
            pos.append((f"single-edit:{cand['anchor']}:{cand['desc']}", body_lines(spx["netlist"]),
                        spx["wl"], B.tokhash(spx["tokens"]), R.cache[rj["jid"]],
                        {"anchor": cand["anchor"], "edit": cand["desc"], "pool_design": cand["id"]}))
        for a0 in libs[1:]:
            x = [x for x in tf1 if x["anchor"] == a0][0]
            pos.append((f"library:{a0}", anchor_target(R, a0), R.anch[a0]["wl"], R.anch[a0]["tok"],
                        R.cache[x["jid"]], {"anchor": a0, "family": R.anch[a0]["family"]}))
        seen_wl = set()
        k = 0
        for src, net, wl, tok, r, extra in pos:
            if wl in seen_wl:
                skipped["dup_topology_in_task"] += 1
                continue
            if wl == R.anch[an]["wl"]:
                skipped["equals_shown_anchor"] += 1
                continue
            if k >= MAX_POS:
                skipped["over_max_pos"] += 1
                continue
            seen_wl.add(wl)
            k += 1
            assert B.feasible(r)
            examples.append(OrderedDict(
                id=f"{n}:{k}", task=n, task_origin=t["origin"], family=t["g"], band=t["band"],
                band_type=t["bt"], difficulty=lab, shown_anchor=an, source=src,
                messages=msgs, prompt_text=text, target_netlist=net,
                completion="```netlist\n" + net + "```", target_wl=wl, target_tok=tok,
                target_info=extra, spec_file=os.path.relpath(spec, REPO), spec_sha=B.spec_sha(spec),
                limits=t["limits"], verification=vrec(R, r, spec, src)))
    # ---- fence check (+ negative control)
    held_spec = {B.spec_sha(R.pool[n]["spec"]) for n in R.split["heldout_tasks"]}
    held_wl = {R.pool[n]["wl"] for n in R.split["heldout_tasks"]}
    held_tok = {R.pool[n]["tok"] for n in R.split["heldout_tasks"]}

    def fence(ex):
        v = []
        if ex["family"] in held_fam:
            v.append("heldout_family")
        if ex["target_wl"] in R.bench_wl or ex["target_tok"] in R.bench_tok:
            v.append("bench_witness_hash")
        if ex["target_wl"] in held_wl or ex["target_tok"] in held_tok:
            v.append("heldout_witness_hash")
        if ex["spec_sha"] in R.bench_spec or ex["spec_sha"] in held_spec:
            v.append("bench_or_heldout_spec")
        return v
    viol = [(e["id"], fence(e)) for e in examples if fence(e)]
    neg = []
    hn = R.split["heldout_tasks"][0]
    ht = R.pool[hn]
    neg.append(fence({"family": ht["g"], "target_wl": ht["wl"], "target_tok": ht["tok"],
                      "spec_sha": B.spec_sha(ht["spec"])}))
    bc = R.cells[STRICT[0]]
    neg.append(fence({"family": "x", "target_wl": bc["wl"], "target_tok": bc["tok"],
                      "spec_sha": "x"}))
    fc = OrderedDict(rc=1 if viol else 0, n_examples=len(examples), violations=viol,
                     checks=["no held-out spec family", "no bench-v2 witness WL/token hash (all "
                             "planted cells, any status, incl. original/stripped)",
                             "no held-out task witness WL/token hash",
                             "no bench-v2 / held-out spec (content sha)"],
                     negative_control={"heldout_task_as_example": neg[0],
                                       "strict_cell_witness_as_target": neg[1],
                                       "pass": bool(neg[0]) and bool(neg[1])},
                     n_bench_wl=len(R.bench_wl), n_bench_tok=len(R.bench_tok),
                     n_bench_spec=len(R.bench_spec))
    B.atomic_write(f"{out_dir}/fence_check.json", json.dumps(fc, indent=1))
    examples = [e for e in examples if not fence(e)]
    # ---- nested subsets (stratified by band type x difficulty, task-spread)
    rng = random.Random(SUBSET_SEED)
    strata = defaultdict(list)
    for e in examples:
        strata[(e["band_type"], e["difficulty"])].append(e)
    order = {}
    for key in sorted(strata):
        es = strata[key]
        tnames = sorted({e["task"] for e in es})
        rng.shuffle(tnames)
        rank = {tn: i for i, tn in enumerate(tnames)}
        es.sort(key=lambda e: (int(e["id"].rsplit(":", 1)[1]), rank[e["task"]]))
        order[key] = es
    N = len(examples)

    def alloc(n):
        q = {k: n * len(v) / N for k, v in order.items()}
        base = {k: int(math.floor(x)) for k, x in q.items()}
        rem = n - sum(base.values())
        for k in sorted(q, key=lambda k: (-(q[k] - base[k]), k))[:rem]:
            base[k] += 1
        return base
    subsets = OrderedDict()
    prev = None
    for n in (100, 300, 1000):
        if n > N:
            continue
        al = alloc(n)
        if prev:
            for k in al:
                al[k] = max(al[k], prev[k])
            while sum(al.values()) > n:       # restore the size, never below prev
                k = max((k for k in al if al[k] > prev[k]), key=lambda k: al[k] - n * len(order[k]) / N)
                al[k] -= 1
        subsets[str(n)] = [e["id"] for k in sorted(order) for e in order[k][: al[k]]]
        prev = al
    for a_, b_ in zip(list(subsets)[:-1], list(subsets)[1:]):
        assert set(subsets[a_]) <= set(subsets[b_])
    # ---- write
    p_all = f"{out_dir}/train-all.jsonl"
    with open(p_all + ".tmp", "w") as fh:
        for e in examples:
            fh.write(json.dumps(e, default=float) + "\n")
    os.replace(p_all + ".tmp", p_all)
    B.atomic_write(f"{out_dir}/subsets.json", json.dumps(OrderedDict(
        seed=SUBSET_SEED, stratified_by=["band_type", "difficulty"],
        method=("per stratum: tasks shuffled (seed), examples ordered by (positive rank within "
                "task, task rank) so subsets spread over tasks; largest-remainder proportional "
                "allocation, nested (100 within 300 within 1000)"),
        subsets=subsets), indent=1))
    ex_by = {e["id"]: e for e in examples}
    stats = OrderedDict(
        n_examples=N, n_tasks_with_examples=len({e["task"] for e in examples}),
        n_training_side_tasks_ok=sum(1 for n in tasks if (R.train_out.get(n) or {}).get("status") == "ok"),
        n_new_tasks_planted=len(R.new_tasks),
        n_new_tasks_ok=sum(1 for n in R.new_tasks if (R.train_out.get(n) or {}).get("status") == "ok"),
        skipped=dict(skipped),
        by_source=dict(Counter(e["source"].split(":")[0] for e in examples)),
        by_family=dict(Counter(e["family"] for e in examples)),
        by_band_type=dict(Counter(e["band_type"] for e in examples)),
        by_difficulty=dict(Counter(e["difficulty"] for e in examples)),
        per_task=dict(Counter(Counter(e["task"] for e in examples).values())),
        task_labels=dict(Counter(labels.values())),
        distinct_target_wl=len({e["target_wl"] for e in examples}),
        subsets={k: {"n": len(v), "by_stratum": dict(Counter(
            f"{ex_by[i]['band_type']}/{ex_by[i]['difficulty']}" for i in v))}
            for k, v in subsets.items()},
        fence_rc=fc["rc"])
    B.atomic_write(f"{out_dir}/stats.json", json.dumps(stats, indent=1))
    man = OrderedDict(prereg="kaggle/PREREG-PILOT-V0.md (137ea060a)", verifier=PROF, ts=now(),
                      split_sha256=open(f"{EVAL}/split.json.sha256").read().split()[0],
                      era=R.era, files={})
    for f in ("train-all.jsonl", "subsets.json", "stats.json", "fence_check.json"):
        man["files"][f] = {"sha256": sha256_file(f"{out_dir}/{f}"),
                           "bytes": os.path.getsize(f"{out_dir}/{f}")}
    B.atomic_write(f"{out_dir}/manifest.json", json.dumps(man, indent=1))
    R.log(f"build-data -> {out_dir}: {N} examples from {stats['n_tasks_with_examples']} tasks; "
          f"subsets { {k: len(v) for k, v in subsets.items()} }; fence rc {fc['rc']}")


# ====================================================================== main
def replay(R):
    """rebuild every task's state from the cache (no launches)."""
    R.setup()
    for _ in range(20000):
        before = R.n_adv
        R.step_tasks()
        if all(t[3] for t in R.tasks) or R.n_adv == before:
            break


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["split", "run", "build-eval", "build-data", "plan"])
    ap.add_argument("--run-dir", default=f"{HERE}/run")
    ap.add_argument("--eval-limit", type=int, default=None)
    ap.add_argument("--f2-limit", type=int, default=None)
    ap.add_argument("--train-limit", type=int, default=None)
    ap.add_argument("--no-gen", action="store_true")
    ap.add_argument("--gen-max-new", type=int, default=None)
    ap.add_argument("--max-procs", type=int, default=8)
    ap.add_argument("--extra-cache", action="append", default=[])
    ap.add_argument("--partial", action="store_true")
    a = ap.parse_args()
    a.run_dir = os.path.abspath(a.run_dir)
    if a.cmd == "split":
        return cmd_split(a)
    R = Runner(a)
    if a.cmd == "run":
        return R.run()
    if a.cmd == "plan":
        R.load_inputs()
        for t in R.eval_tasks:
            print(t["name"], t["anchor"], R.f2_live[t["name"]])
        return
    a.no_gen = a.no_gen or a.cmd == "build-eval"
    replay(R)
    if a.cmd == "build-eval":
        build_eval(R, partial=a.partial)
    else:
        build_data(R, partial=a.partial)
    R.close()


if __name__ == "__main__":
    main()

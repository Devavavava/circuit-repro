#!/usr/bin/env python
"""bench-v2 AMENDMENT 3 (kaggle/PREREG-BENCH-V2.md, commit 0d03751cc): end-of-run
re-check of the FINISHED bench-v2 run under verifier rl-v1.2 (rl-v1.1 + ideal port
coupling G-CP1 in-loop; bench_anchor_prep VERIFY_CP_IDEAL). Detached, resumable.

  BENCH  every ACCEPTED, selectable (amendment-1 re-accepted / amendment-2) cell of
         bench-v2/run/cells.jsonl, specs UNCHANGED, the cell's archived witness
         (witness/witness.tokens.json, == the cell's tok hash):
           A1  witness re-sized at seeds {1,2} (+3 if they split), >= 2 feasible
           A2  tightened-2 % spec (mu not tightened), >= 1 of {1,2,3}
           A3  fresh seeds, >= 1 of {4,5,6}
           F1  library a1-a5 x seed 1, then seed 2: any feasible kills
           F2  every single edit of the SHOWN anchor (bv2 f2space, E-c space) x seed 1,
               then seed 2, chunks of 16, kill on the first feasible
         early kill on the first failing stage; a failing cell is tagged amend3-cp1
         (kept on record, not selectable). Classes (core / primary atom) are the
         rl-v1.1 ABL's (not re-run: AMENDMENT 3 item 2 lists A1-A3, F1, F2).
  TRAIN  every `ok` training task: witness at seed 1, seed 2 if needed (>= 1 of
         {1,2}); if both fail, ONE re-size attempt at seed 3 (D39); still failing ->
         tagged amend3-cp1. Passing tasks: T-F1 (a1-a5 x seed 1 at the task spec,
         every task -- order-independent). Labels re-derived at the end from
         rl-v1.2 rows only: own T-F1 feasible or any rl-v1.2 anchor design (bench
         F1 + all T-F1, same band) meeting the limits -> library-solvable; else an
         rl-v1.2 single edit (bench F2, same band) -> single-edit-solvable; else
         witness-only.
  FINAL  selection over the passing cells (class rule (b) primary atom <= 25 %,
         parent <= 40 %, narrowband >= 25 %, bv2.select_cells) -> kaggle/editcap-lib-v2/
         (selected cells, witnesses EVAL-ONLY, rl-v1.2 results/evidence), training
         pool -> kaggle/train-pool-v2/, fence check, amend3/summary.json.

Every sizing call is one `bv2.py worker` subprocess (smoke_run ... profile="rl-v1.2");
results cached in <run>/results.jsonl keyed by bv2.job_id(..., "rl-v1.2"), so a
restart replays through the cache (deterministic). Disk robustness = bv2 D32
(SafeAppender, fsync'd atomic_write, launch pause on a full / < 5 GB disk, workers
dying without a result during disk trouble are re-queued, never cached).
<= max_procs workers (8), 4 while load1 > 22.

usage (via ../envrun.sh):
  a3run.py run   [--run-dir D] [--cells N1,N2] [--f2-limit K] [--train-limit K]
                 [--no-train] [--lib DIR --tp DIR] [--max-procs 8]
  a3run.py final [--run-dir D] ...        (re-run only the FINAL step)
"""
import argparse
import json
import math
import os
import shutil
import signal
import statistics
import subprocess
import sys
import time
from collections import Counter, OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CAMP = os.path.dirname(HERE)
sys.path.insert(0, CAMP)
import bv2 as B  # noqa: E402

REPO = B.REPO
PROF = "rl-v1.2"
B.CUR_PROFILE = PROF                 # make_evidence / write_cell_dir record rl-v1.2
PHASE = "amendment-3"
TAG = "amend3-cp1"
SRC = f"{CAMP}/run"                  # the FINISHED bench-v2 run (read-only)
BV2_PY = f"{CAMP}/bv2.py"
CFG = dict(B.CONFIGS["full"])        # selection quotas / class rule (b) primary_atom
WORKER_TIMEOUT_S = 3600
PRIO = {"A1": 0, "A2": 0, "A3": 0, "F1": 1, "F2": 2, "T-wit": 3, "T-F1": 4}


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class Dummy:
    """minimal self for bv2.Pipeline.f2space_build (exact same edit space)."""

    def __init__(self, anch, log):
        self.anch, self.f2space, self.log = anch, {}, log

    def round_trip(self, text):
        import proposal as P
        rt = P.round_trip(text)
        return {"ok": bool(rt.get("ok")), "error": rt.get("error"),
                "tokens": rt.get("tokens"), "wl_hash": rt.get("wl_hash"),
                "n_devices": rt.get("n_devices")}


class Runner:
    def __init__(self, a):
        self.a = a
        self.rd = a.run_dir
        os.makedirs(f"{self.rd}/jobs", exist_ok=True)
        self.t0 = time.time()
        self.era = B.era_stamp()
        self.fh = {n: B.SafeAppender(f"{self.rd}/{n}") for n in
                   ("results.jsonl", "events.jsonl", "cells_amend3.jsonl",
                    "train_amend3.jsonl", "sched.log")}
        self.cache = {}
        for p in [f"{self.rd}/results.jsonl"] + list(a.extra_cache or []):
            for r in B.read_jsonl(p):
                if r.get("profile") == PROF and not r.get("error"):
                    self.cache.setdefault(r["jid"], r)
                elif p == f"{self.rd}/results.jsonl":
                    self.cache[r["jid"]] = r
        self.n_cached_start = len(self.cache)
        self.pending, self.running, self.queued = [], {}, set()
        self.tasks = []                    # [name, gen, waiting jids, done]
        self.stop = False
        self.n_new, self.cpu_new, self.recent = 0, 0.0, []
        self.last_progress = self.last_disk = 0.0
        self.anch = B.anchor_data()
        self.cells_out, self.train_out = OrderedDict(), OrderedDict()
        self.requeued = Counter()
        self.seq = 0

    # ------------------------------------------------------------------ io
    def log(self, msg):
        line = f"{now()} {msg}"
        print(line, flush=True)
        self.fh["sched.log"].write(line + "\n")

    def event(self, kind, **kw):
        self.fh["events.jsonl"].write(B.jdump(dict(ts=now(), kind=kind, **kw)) + "\n")

    # --------------------------------------------------------------- inputs
    def load_inputs(self):
        cells = B.load_jsonl_last(f"{SRC}/cells.jsonl", "name")
        acc = [c for c in cells.values() if c["status"] == "accepted"
               and c.get("era_tag") in B.POST_ERAS and c.get("selectable", True)]
        acc.sort(key=lambda c: c["seq"])
        if self.a.cells:
            want = self.a.cells.split(",")
            acc = [c for c in acc if c["name"] in want]
        for c in acc:
            t = json.load(open(f"{SRC}/cells/{c['name']}/witness/witness.tokens.json"))
            assert B.tokhash(t) == c["tok"], c["name"]
            c["tokens"] = t
        self.cells = acc
        self.all_cells = cells
        tasks = B.load_jsonl_last(f"{SRC}/train.jsonl", "name")
        ok = [t for t in tasks.values() if t["status"] == "ok"]
        ok.sort(key=lambda t: t["seq"])
        if self.a.no_train:
            ok = []
        elif self.a.train_limit:
            ok = ok[: self.a.train_limit]
        toks = {}
        need = {t["cid"] for t in ok}
        for p in (f"{SRC}/candidates.jsonl", f"{SRC}/amendment-1-record/candidates.jsonl",
                  f"{SRC}/pre-amendment/candidates.jsonl"):
            if not os.path.exists(p):
                continue
            for ln in open(p):
                try:
                    r = json.loads(ln)
                except Exception:                                # noqa: BLE001
                    continue
                if r.get("cid") in need and r.get("tokens"):
                    toks.setdefault(r["cid"], r["tokens"])
        for t in ok:
            tk = toks.get(t["cid"])
            if tk is None or B.tokhash(tk) != t["tok"]:
                import proposal as P
                rt = P.round_trip(t["netlist"])
                tk = rt.get("tokens")
            assert tk is not None and B.tokhash(tk) == t["tok"], t["name"]
            t["tokens"] = tk
        self.tasks_in = ok
        self.all_tasks = tasks
        # F2 spaces of the shown anchors actually needed (bv2's exact code)
        sp_path = f"{self.rd}/f2space.json"
        if os.path.exists(sp_path):
            self.f2space = json.load(open(sp_path))
        else:
            d = Dummy(OrderedDict((k, v) for k, v in self.anch.items()
                                  if k in {c["anchor"] for c in B.load_jsonl_last(
                                      f"{SRC}/cells.jsonl", "name").values()
                                      if c["status"] == "accepted"}), self.log)
            B.Pipeline.f2space_build(d)
            self.f2space = d.f2space
            B.atomic_write(sp_path, json.dumps(self.f2space))
        # live (to be sized) F2 edits per cell, for the ETA only
        self.f2_live = {}
        for c in self.cells:
            sp = [x for x in self.f2space[c["anchor"]] if x["rt_ok"]]
            if self.a.f2_limit:
                sp = sp[: self.a.f2_limit]
            self.f2_live[c["name"]] = sum(1 for x in sp if not self.pre_reject(x["tokens"], c["spec"]))
        self.log(f"inputs: {len(self.cells)} cells, {len(self.tasks_in)} training tasks, "
                 f"cache {self.n_cached_start} rows; f2space "
                 + ", ".join(f"{k}={sum(x['rt_ok'] for x in v)}" for k, v in self.f2space.items()))

    # ---------------------------------------------------------------- jobs
    def job(self, kind, tokens, spec, seed, **meta):
        meta.update(stage=kind)
        return B.Job(kind, "a3", tokens, spec, seed, meta=meta, profile=PROF)

    def pre_reject(self, tokens, spec_path):
        import bench_anchor_prep as PREP
        from topology import Topology
        sp = B.sizing_spec(spec_path)
        topo = Topology(list(tokens))
        if not PREP.topo_limits(sp, topo)["ok"] or PREP.structural_degeneracy(topo):
            return True
        return not PREP.port_dc_prefilter(list(tokens))["pass"]

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
                    # D32: no result during disk trouble / shutdown -> NOT a sizing
                    # outcome: never cached, re-queued
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
            return
        self.submit(jobs)
        t[2] = [j.jid for j in jobs]

    def step_tasks(self):
        for t in self.tasks:
            if t[3] or t[2] is None:
                continue
            if all(j in self.cache for j in t[2]):
                self.advance(t, [self.cache[j] for j in t[2]])

    @staticmethod
    def summ(r, seed, **extra):
        res = r.get("res") or {}
        pd = res.get("port_dc")
        d = {"seed": seed, "jid": r["jid"], "feasible": B.feasible(r), "secs": r.get("secs"),
             "n_evals": res.get("n_evals"), "mu_min_wide": res.get("mu_min_wide"),
             "infeasible_reason": res.get("infeasible_reason"),
             "port_dc_pass": pd.get("pass") if isinstance(pd, dict) else None,
             "error": (r.get("error") or "")[:200] or None}
        d.update(extra)
        return d

    def task_cell(self, c):
        tok, spec, tight, name = c["tokens"], c["spec"], c["tight_spec"], c["name"]
        out = OrderedDict(name=name, band=c["band"], bt=c["bt"], anchor=c["anchor"],
                          primary_atom=c.get("primary_atom"), cls=c["cls"],
                          era_tag=c.get("era_tag"), seq=c["seq"], status="running",
                          stage="A1", stages=OrderedDict(), profile=PROF, ts=None)
        self.cells_out[name] = out
        st = out["stages"]

        def J(kind, tokens, sp, seed, **meta):
            return self.job(kind, tokens, sp, seed, cell=name, band=c["band"], **meta)

        def finish(status, why, stage=None):
            out.update(status=status, why=why, failed_stage=stage, ts=now(),
                       tag=TAG if status != "pass" else None)
            self.fh["cells_amend3.jsonl"].write(B.jdump(out) + "\n")
            self.event("cell_verdict", cell=name, status=status, why=why)
            self.log(f"cell {name}: {status} ({why})")

        def killed(why, stage):
            """SMOKE --smoke-force: record the would-be kill and keep going so every
            stage (and the library write-out) is exercised; never set in the full run."""
            if self.a.smoke_force:
                lst = out.setdefault("SMOKE_FORCED_would_kill", [])
                if why not in lst:
                    lst.append(why)
                return False
            finish("fail", why, stage)
            return True

        # A1
        recs = yield [J("A1", tok, spec, 1), J("A1", tok, spec, 2)]
        a1 = [self.summ(r, s) for r, s in zip(recs, (1, 2))]
        nf = sum(x["feasible"] for x in a1)
        if nf == 1:
            (r,) = yield [J("A1", tok, spec, 3)]
            a1.append(self.summ(r, 3))
            nf += a1[-1]["feasible"]
        st["A1"] = {"runs": a1, "n_feasible": nf, "pass": nf >= 2}
        if nf < 2:
            if killed("A1_witness_not_2of3", "A1"):
                return
        # A2 tightened >= 1 of {1,2,3}
        out["stage"] = "A2"
        a2 = []
        for s in (1, 2, 3):
            (r,) = yield [J("A2", tok, tight, s)]
            a2.append(self.summ(r, s))
            if a2[-1]["feasible"]:
                break
        st["A2"] = {"runs": a2, "pass": any(x["feasible"] for x in a2)}
        if not st["A2"]["pass"]:
            if killed("A2_tightened_fails", "A2"):
                return
        # A3 fresh seeds >= 1 of {4,5,6}
        out["stage"] = "A3"
        a3 = []
        for s in (4, 5, 6):
            (r,) = yield [J("A3", tok, spec, s)]
            a3.append(self.summ(r, s))
            if a3[-1]["feasible"]:
                break
        st["A3"] = {"runs": a3, "pass": any(x["feasible"] for x in a3)}
        if not st["A3"]["pass"]:
            if killed("A3_fresh_seeds_fail", "A3"):
                return
        # F1 library null
        out["stage"] = "F1"
        f1 = []
        for s in (1, 2):
            jobs = []
            for an, A in self.anch.items():
                inp = self.pre_reject(A["tokens"], spec)
                jobs.append(J("F1", A["tokens"], spec, s, anchor=an, inproc=inp))
            recs = yield jobs
            f1 += [self.summ(r, s, anchor=j.meta["anchor"], inproc_reject=j.meta["inproc"])
                   for j, r in zip(jobs, recs)]
            if any(x["feasible"] for x in f1):
                st["F1"] = {"runs": f1, "pass": False,
                            "solvers": [f"{x['anchor']}@s{x['seed']}" for x in f1 if x["feasible"]]}
                if killed("F1_library_solves", "F1"):
                    return
        st["F1"] = {"runs": f1, "pass": not any(x["feasible"] for x in f1),
                    "solvers": [f"{x['anchor']}@s{x['seed']}" for x in f1 if x["feasible"]]}
        # F2 single-edit null of the SHOWN anchor
        out["stage"] = "F2"
        space = [x for x in self.f2space[c["anchor"]] if x["rt_ok"]]
        if self.a.f2_limit:
            space = space[: self.a.f2_limit]
            out["f2_SMOKE_SUBSET"] = self.a.f2_limit
        f2 = []
        for s in (1, 2):
            live = []
            for x in space:
                j = J("F2", x["tokens"], spec, s, edit=x["desc"], idx=x["idx"],
                      inproc=self.pre_reject(x["tokens"], spec))
                if j.meta["inproc"]:
                    r = self.inproc(j)
                    f2.append(self.summ(r, s, edit=x["desc"], inproc_reject=True))
                else:
                    live.append(j)
            for k in range(0, len(live), 16):
                chunk = live[k:k + 16]
                recs = yield chunk
                f2 += [self.summ(r, s, edit=j.meta["edit"]) for j, r in zip(chunk, recs)]
                out["f2_progress"] = (f"{sum(1 for x in f2 if not x.get('inproc_reject'))}/"
                                      f"{2 * self.f2_live.get(name, 0)}")
                if any(x["feasible"] for x in f2):
                    st["F2"] = {"runs": f2, "pass": False,
                                "solving_edits": [f"{x['edit']}@s{x['seed']}" for x in f2
                                                  if x["feasible"]]}
                    if killed("F2_single_edit_solves", "F2"):
                        return
        st["F2"] = {"runs": f2, "pass": not any(x["feasible"] for x in f2), "n_space": len(space),
                    "solving_edits": [f"{x['edit']}@s{x['seed']}" for x in f2 if x["feasible"]],
                    "n_sized": sum(1 for x in f2 if not x.get("inproc_reject")),
                    "n_prereject": sum(1 for x in f2 if x.get("inproc_reject"))}
        out["stage"] = "done"
        if out.get("SMOKE_FORCED_would_kill"):
            return finish("pass", "SMOKE_FORCED(would kill: "
                          + ",".join(out["SMOKE_FORCED_would_kill"]) + ")")
        return finish("pass", "all_filters_pass_rl_v1_2")

    def task_train(self, t):
        tok, spec, name = t["tokens"], t["spec"], t["name"]
        out = OrderedDict(name=name, band=t["band"], bt=t["bt"], anchor=t["anchor"],
                          status="running", label_before=t.get("difficulty"), profile=PROF)
        self.train_out[name] = out

        def J(kind, tokens, seed, **meta):
            return self.job(kind, tokens, spec, seed, task=name, band=t["band"], **meta)
        wit = []
        for s in (1, 2, 3):
            (r,) = yield [J("T-wit", tok, s)]
            wit.append(self.summ(r, s, resize_attempt=(s == 3)))
            if wit[-1]["feasible"]:
                break
        out["witness"] = wit
        if not any(x["feasible"] for x in wit):
            out.update(status=TAG, why="witness infeasible under rl-v1.2 at seeds 1,2 "
                                       "and the seed-3 re-size", ts=now())
            self.fh["train_amend3.jsonl"].write(B.jdump(out) + "\n")
            return
        out["witness_seed"] = wit[-1]["seed"]
        jobs = []
        for an, A in self.anch.items():
            jobs.append(J("T-F1", A["tokens"], 1, anchor=an,
                          inproc=self.pre_reject(A["tokens"], spec)))
        recs = yield jobs
        out["T-F1"] = [self.summ(r, 1, anchor=j.meta["anchor"]) for j, r in zip(jobs, recs)]
        out.update(status="ok", ts=now())
        self.fh["train_amend3.jsonl"].write(B.jdump(out) + "\n")

    # ------------------------------------------------------------- progress
    def eta_calls(self):
        """rough upper-ish estimate of sizing calls still to run."""
        n = len(self.pending) + len(self.running)
        for c in self.cells:
            o = self.cells_out.get(c["name"]) or {}
            if o.get("status") not in (None, "running"):
                continue
            st = o.get("stage", "A1")
            nsp = self.f2_live.get(c["name"], 0)
            f1 = 6 if c["bt"] == "wideband" else 10
            # upper bound: every stage passes (F2 = both seeds of every live edit)
            rest = {"A1": 2.5 + 1 + 1 + f1 + 2 * nsp, "A2": 1 + 1 + f1 + 2 * nsp,
                    "A3": 1 + f1 + 2 * nsp, "F1": f1 / 2 + 2 * nsp,
                    "F2": 2 * nsp - int(str(o.get("f2_progress") or "0/0").split("/")[0])
                    }.get(st, 0)
            n += rest
        for t in self.tasks_in:
            o = self.train_out.get(t["name"]) or {}
            if o.get("status") not in (None, "running"):
                continue
            n += (1.3 if "witness" not in o else 0) + (5 if t["bt"] == "narrowband" else 3)
        return int(n)

    def progress(self, final=False, status=None):
        rec = [s for t, s in self.recent if time.time() - t < 3600]
        med = statistics.median(rec) if rec else (statistics.median(
            [s for _t, s in self.recent]) if self.recent else 100.0)
        lim = self.limit()
        ncalls = self.eta_calls()
        eta_h = ncalls * med / max(1, lim) / 3600.0
        cs = Counter(o.get("status") for o in self.cells_out.values())
        ts = Counter(o.get("status") for o in self.train_out.values())
        p = {"ts": now(), "pid": os.getpid(), "run_dir": self.rd, "profile": PROF,
             "phase": PHASE, "era": self.era,
             "status": status or ("final" if final else B.DISK.state() if B.DISK.paused()
                                  else "running"),
             "started": B.iso(self.t0), "elapsed_h": round((time.time() - self.t0) / 3600, 3),
             "load1": B.load1(), "proc_limit": lim, "running": len(self.running),
             "pending": len(self.pending),
             "calls": {"new_this_session": self.n_new, "cache_rows_at_start": self.n_cached_start,
                       "cpu_h_this_session": round(self.cpu_new / 3600, 2),
                       "median_secs_last_hour": round(med, 1)},
             "disk": {"state": B.DISK.state(), "free_gb": B.DISK.free_gb,
                      "tmp_free_gb": B.DISK.tmp_free_gb, "failed_writes": B.DISK.n_errors,
                      "pauses": B.DISK.pauses},
             "bench": {"n_cells": len(self.cells), "status": dict(cs),
                       "cells": {n: {"status": o.get("status"), "stage": o.get("stage"),
                                     "why": o.get("why"), "f2_progress": o.get("f2_progress")}
                                 for n, o in self.cells_out.items()}},
             "train": {"n_tasks": len(self.tasks_in), "status": dict(ts),
                       "witness_done": sum(1 for o in self.train_out.values() if "witness" in o)},
             "eta": {"remaining_calls_est": ncalls, "hours_est": round(eta_h, 2),
                     "finish_est": B.iso(time.time() + eta_h * 3600)}}
        B.atomic_write(f"{self.rd}/progress.json", json.dumps(p, indent=1, default=repr),
                       critical=False)
        self.last_progress = time.time()

    def limit(self):
        return self.a.max_procs if B.load1() <= 22.0 else min(self.a.max_procs, 4)

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
        t_end = time.time() + max_wait_s
        while any(a.pending() for a in self.fh.values()) and time.time() < t_end:
            if not all([a.flush() for a in self.fh.values()]):
                time.sleep(max(1.0, min(B.DISK.delay, t_end - time.time())))
        for a in self.fh.values():
            p = a.spill(os.path.join(os.environ.get("TMPDIR") or "/tmp", "a3-spill"))
            if p:
                print(f"DISK FULL AT EXIT: rows of {a.path} spilled to {p}", file=sys.stderr)

    # ------------------------------------------------------------------ run
    def run(self):
        signal.signal(signal.SIGTERM, self.sigterm)
        B.atomic_write(f"{self.rd}/sched.pid", f"{os.getpid()}\n")
        self.load_inputs()
        st = {"t_start": now(), "args": vars(self.a), "era": self.era,
              "prereg": "kaggle/PREREG-BENCH-V2.md AMENDMENT 3 (0d03751cc)", "profile": PROF}
        B.atomic_write(f"{self.rd}/start.{int(self.t0)}.json", json.dumps(st, indent=1, default=repr))
        for c in self.cells:
            self.spawn(f"cell:{c['name']}", self.task_cell(c))
        for t in self.tasks_in:
            self.spawn(f"train:{t['name']}", self.task_train(t))
        self.progress()
        while not self.stop:
            self.reap()
            self.step_tasks()
            self.disk_tick()
            lim = self.limit()
            if not B.DISK.paused():
                while len(self.running) < lim and self.pending:
                    pr, sq, j = self.pending.pop(0)
                    if j.jid in self.cache:
                        self.queued.discard(j.jid)
                        continue
                    if not self.launch(j):
                        self.pending.insert(0, (pr, sq, j))
                        break
            if time.time() - self.last_progress > 30:
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
        self.log("re-check complete -> final")
        self.progress(status="finalizing")
        final(self)
        self.progress(final=True)
        self.log("exit")
        self.close()


# ==================================================================== FINAL
def rl12_pools(cache):
    """rl-v1.2 recorded designs: anchor designs (F1 / T-F1) and single edits (F2),
    per band, bv2.add_pool semantics (port DC: own behavioural verdict, else the
    pre-filter verdict)."""
    anch, se = defaultdict(list), defaultdict(list)
    for r in cache.values():
        if r.get("profile") != PROF or r.get("kind") not in ("F1", "T-F1", "F2"):
            continue
        res = r.get("res") or {}
        m = res.get("metrics") or {}
        if not m:
            continue
        pd, pf = res.get("port_dc"), res.get("port_dc_prefilter")
        pdc = bool(pd.get("pass")) if isinstance(pd, dict) else bool((pf or {}).get("pass"))
        meta = r.get("meta") or {}
        d = {"id": f"{r['kind']}:{meta.get('cell') or meta.get('task')}:"
                   f"{meta.get('anchor') or meta.get('edit')}:s{r['seed']}",
             "metrics": {k: v for k, v in m.items() if isinstance(v, (int, float))},
             "stab_ok": bool(res.get("stab_wide_ok")), "pdc_ok": pdc,
             "feasible": bool(res.get("feasible"))}
        (se if r["kind"] == "F2" else anch)[meta.get("band")].append(d)
    for lst in list(anch.values()) + list(se.values()):
        lst.sort(key=lambda d: d["id"])
    return anch, se


def final(R):
    """labels, selection, library + training pool write-out, fence check, summary."""
    import yaml  # noqa: F401
    a = R.a
    cache = R.cache
    # ---- bench verdicts
    cells_src = {c["name"]: c for c in R.cells}
    passing = [cells_src[n] for n, o in R.cells_out.items() if o.get("status") == "pass"]
    srep, sel = B.selection_report(passing, CFG, era=B.POST_ERAS)
    # ---- training labels (rl-v1.2 rows only)
    anch_pool, se_pool = rl12_pools(cache)
    tasks_src = {t["name"]: t for t in R.tasks_in}
    relabel = Counter()
    for n, o in R.train_out.items():
        t = tasks_src[n]
        if o.get("status") != "ok":
            continue
        lab, why = None, None
        sol = [x["anchor"] for x in o.get("T-F1", []) if x["feasible"]]
        if sol:
            lab, why = "library-solvable", f"anchor(s) {sol} feasible at seed 1 (rl-v1.2)"
        if lab is None:
            for d in anch_pool.get(t["band"], []):
                if d["pdc_ok"] and B.satisfies(d["metrics"], d["stab_ok"], t["bt"], t["limits"]):
                    lab, why = "library-solvable", f"recorded rl-v1.2 anchor design {d['id']}"
                    break
        if lab is None:
            for d in se_pool.get(t["band"], []):
                if d["pdc_ok"] and B.satisfies(d["metrics"], d["stab_ok"], t["bt"], t["limits"]):
                    lab, why = "single-edit-solvable", f"recorded rl-v1.2 single edit {d['id']}"
                    break
        if lab is None:
            lab, why = "witness-only", "no anchor feasible at seed 1; no known rl-v1.2 single edit"
        o["label_after"], o["label_why"] = lab, why
        relabel[f"{o['label_before']}->{lab}"] += 1
    # ---- library
    lib, tp = a.lib, a.tp
    os.makedirs(lib, exist_ok=True)
    for d in os.listdir(lib):
        if d.startswith("v2") and os.path.isdir(f"{lib}/{d}"):
            shutil.rmtree(f"{lib}/{d}")
    index = OrderedDict(
        prereg="kaggle/PREREG-BENCH-V2.md (+ AMENDMENT 1, AMENDMENT 2, AMENDMENT 3)",
        verifier=PROF, pdk=B.PDK, budget=B.BUDGET, mode="amend3-recheck",
        n_rechecked=len(R.cells_out), n_pass_rl_v1_2=len(passing), n_selected=len(sel),
        shortfall=max(0, CFG["bench_min"] - len(sel)),
        floors={m: {"side": sd, "limit": F} for m, (sd, F) in B.FLOORS.items()},
        selection=srep, recheck={n: {k: o.get(k) for k in ("status", "why", "failed_stage", "tag")}
                                 for n, o in R.cells_out.items()},
        cells=OrderedDict())
    for c in sel:
        o = R.cells_out[c["name"]]
        dst = f"{lib}/{c['name']}"
        shutil.copytree(f"{SRC}/cells/{c['name']}", dst)
        runs = {}
        for stg in ("A1", "A2", "A3"):
            for x in o["stages"][stg]["runs"]:
                rec = cache.get(x["jid"]) or {}
                runs[f"{stg}_seed{x['seed']}"] = {
                    "seed": x["seed"], "budget": B.BUDGET,
                    "spec": "spec.yaml" if stg != "A2" else "tightened (limits below)",
                    "result": rec.get("res"), "era": rec.get("era")}
        os.replace(f"{dst}/witness/results.json", f"{dst}/witness/results_rl_v1_1.json")
        B.atomic_write(f"{dst}/witness/results.json", json.dumps(
            {"verifier": PROF, "pdk": B.PDK, "budget": B.BUDGET,
             "tight_limits": c["tight_limits"], "limits": c["limits"], "runs": runs},
            indent=1, default=repr))
        parent = [(x["seed"], cache[x["jid"]]) for x in o["stages"]["F1"]["runs"]
                  if x["anchor"] == c["anchor"]]
        if os.path.exists(f"{dst}/evidence.json"):
            os.replace(f"{dst}/evidence.json", f"{dst}/evidence_rl_v1_1.json")
        ev = B.make_evidence(c, c["spec"], parent, R.anch[c["anchor"]])
        B.atomic_write(f"{dst}/evidence.json", json.dumps(ev, indent=1, default=float))
        with open(f"{dst}/witness/README", "a") as fh:
            fh.write("AMENDMENT 3: this witness was re-checked under verifier rl-v1.2 (ideal "
                     "port coupling, G-CP1): A1/A2/A3 re-sized, F1/F2 re-run; results.json "
                     "holds the rl-v1.2 runs, results_rl_v1_1.json the earlier record. "
                     "original/ (if present) keeps its rl-v1.1 record.\n")
        meta = json.load(open(f"{dst}/cell.json"))
        meta["amendment3"] = {"verifier": PROF, "status": o["status"], "why": o["why"],
                              "stages": {k: {kk: vv for kk, vv in v.items() if kk != "runs"}
                                         | {"n_runs": len(v.get("runs", []))}
                                         for k, v in o["stages"].items()}}
        B.atomic_write(f"{dst}/cell.json", json.dumps(meta, indent=1, default=repr))
        index["cells"][c["name"]] = {
            "band": c["band"], "flavor": c["flavor"], "band_type": c["bt"],
            "move_class": c["cls"], "core_signature": c["cls"],
            "primary_atom": c.get("primary_atom"), "legacy_class": c.get("legacy_class"),
            "parent_anchor": c["anchor"], "witness_wl": c["wl"], "witness_tok": c["tok"],
            "limits": c["limits"], "strip": ((c.get("core") or {}).get("strip") or {}).get("flag"),
            "floor_violations": B.floor_violations(c["limits"]), "verifier": PROF}
    B.atomic_write(f"{lib}/INDEX.json", json.dumps(index, indent=1, default=repr))
    # ---- training pool (bv2.finalize's write-out with the rl-v1.2 status / labels)
    fcells = [c for c in R.all_cells.values() if c["status"] == "accepted"] + [
        c for c in R.all_cells.values() if c.get("era_tag") in B.POST_ERAS
        and c["status"] != "accepted"]
    wkeys = ("witness_original", "witness_original_amend1")
    bench_wl = {c["wl"] for c in fcells} | {(c.get(k) or {}).get("wl")
                                            for c in fcells for k in wkeys} - {None}
    bench_tok = {c["tok"] for c in fcells} | {(c.get(k) or {}).get("tok")
                                              for c in fcells for k in wkeys} - {None}
    bench_specs = {json.dumps(c["limits"], sort_keys=True) + c["g"] for c in fcells}
    os.makedirs(tp, exist_ok=True)
    for d in os.listdir(tp):
        if d.startswith("t2-") and os.path.isdir(f"{tp}/{d}"):
            shutil.rmtree(f"{tp}/{d}")
    tindex = OrderedDict(prereg="kaggle/PREREG-BENCH-V2.md (+ AMENDMENT 3)", verifier=PROF,
                         mode="amend3-recheck",
                         fence="no bench-v2 spec, witness WL hash or witness token hash",
                         tasks=OrderedDict(), fenced_out=[],
                         tagged_amend3=[n for n, o in R.train_out.items() if o["status"] == TAG])
    for n, o in R.train_out.items():
        if o.get("status") != "ok":
            continue
        t = R.all_tasks[n]
        if t["wl"] in bench_wl or t["tok"] in bench_tok or \
                (json.dumps(t["limits"], sort_keys=True) + t["g"]) in bench_specs:
            tindex["fenced_out"].append(n)
            continue
        d = f"{tp}/{n}"
        os.makedirs(f"{d}/witness", exist_ok=True)
        shutil.copy(t["spec"], f"{d}/spec.yaml")
        A = R.anch[t["anchor"]]
        shutil.copy(f"{REPO}/{A['net_file']}", f"{d}/anchor.net")
        shutil.copy(f"{REPO}/{A['tokens_file']}", f"{d}/anchor.tokens.json")
        par = [(1, cache[x["jid"]]) for x in o.get("T-F1", []) if x["anchor"] == t["anchor"]]
        ev = B.make_evidence(t, t["spec"], par, A) if par else None
        if ev:
            B.atomic_write(f"{d}/evidence.json", json.dumps(ev, indent=1, default=float))
        B.atomic_write(f"{d}/witness/witness.net", "* train-pool-v2 witness (search-found)\n"
                       + t["netlist"])
        B.atomic_write(f"{d}/witness/edit_script.json", json.dumps(
            {"parent_anchor": A["family"], "script": t["script"], "repairs": t["repairs"],
             "move_class": t["cls"], "wl_hash": t["wl"], "tok_hash": t["tok"]}, indent=1))
        tj = {k: v for k, v in t.items() if k not in ("netlist", "evidence", "tokens")}
        tj.update(difficulty=o["label_after"], difficulty_why=o["label_why"],
                  amend3={"verifier": PROF, "witness": o["witness"], "T-F1": o.get("T-F1"),
                          "label_before": o["label_before"], "label_after": o["label_after"]})
        B.atomic_write(f"{d}/task.json", json.dumps(tj, indent=1, default=repr))
        tindex["tasks"][n] = {"band": t["band"], "flavor": t["flavor"],
                              "difficulty": o["label_after"], "move_class": t["cls"],
                              "parent_anchor": t["anchor"], "witness_wl": t["wl"],
                              "witness_tok": t["tok"]}
    tindex["difficulty_hist"] = dict(Counter(v["difficulty"] for v in tindex["tasks"].values()))
    tindex["relabel"] = dict(relabel)
    B.atomic_write(f"{tp}/INDEX.json", json.dumps(tindex, indent=1))
    rc = subprocess.run([sys.executable, f"{CAMP}/fence_check.py", "--bench", lib, "--train", tp,
                         "--cells-jsonl", f"{SRC}/cells.jsonl"], capture_output=True, text=True)
    B.atomic_write(f"{R.rd}/fence_check.txt", rc.stdout + rc.stderr)
    # ---- summary
    rows = list(cache.values())
    sized = [r for r in rows if r.get("profile") == PROF and not r.get("inproc_reject")
             and r.get("phase") == PHASE]
    summ = OrderedDict(
        prereg="kaggle/PREREG-BENCH-V2.md AMENDMENT 3 (0d03751cc)", verifier=PROF,
        ts=now(), run_dir=os.path.relpath(R.rd, REPO), lib=os.path.relpath(lib, REPO),
        train_pool=os.path.relpath(tp, REPO),
        bench={"n_rechecked": len(R.cells_out),
               "pass": [n for n, o in R.cells_out.items() if o["status"] == "pass"],
               "tagged_amend3_cp1": {n: {"stage": o.get("failed_stage"), "why": o.get("why")}
                                     for n, o in R.cells_out.items() if o["status"] != "pass"},
               "per_cell": {n: {"status": o["status"], "why": o["why"],
                                "stages": {k: {"pass": v.get("pass"),
                                               "n_runs": len(v.get("runs", [])),
                                               "n_feasible": sum(1 for x in v.get("runs", [])
                                                                 if x["feasible"])}
                                           for k, v in o["stages"].items()}}
                            for n, o in R.cells_out.items()}},
        selection={"n_selected": len(sel), "names": [c["name"] for c in sel],
                   "shortfall_vs_20": max(0, CFG["bench_min"] - len(sel)),
                   "per_primary_atom": dict(Counter(c.get("primary_atom") for c in sel)),
                   "per_parent": dict(Counter(c["anchor"] for c in sel)),
                   "per_band_type": dict(Counter(c["bt"] for c in sel)),
                   "nb_quota_binding": srep["nb_quota_binding"],
                   "report": srep},
        train={"n_rechecked": len(R.train_out),
               "status": dict(Counter(o["status"] for o in R.train_out.values())),
               "witness_seed": dict(Counter(str(o.get("witness_seed")) for o in R.train_out.values()
                                            if o["status"] == "ok")),
               "label_hist_before": dict(Counter(o["label_before"] for o in R.train_out.values())),
               "label_hist_after": tindex["difficulty_hist"], "relabel": dict(relabel),
               "fenced_out": tindex["fenced_out"], "n_written": len(tindex["tasks"])},
        fence_check_rc=rc.returncode,
        compute={"sized_calls": len(sized),
                 "cpu_h": round(sum(r.get("secs") or 0 for r in sized) / 3600, 2),
                 "error_rows": sum(1 for r in sized if r.get("error"))})
    B.atomic_write(f"{HERE}/{a.summary_name}", json.dumps(summ, indent=1, default=repr))
    R.log(f"FINAL: {len(passing)}/{len(R.cells_out)} cells pass rl-v1.2, {len(sel)} selected -> "
          f"{lib}; training {len(tindex['tasks'])} written (tagged {len(tindex['tagged_amend3'])}); "
          f"fence rc={rc.returncode}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "final"])
    ap.add_argument("--run-dir", default=f"{HERE}/run")
    ap.add_argument("--cells", default=None)
    ap.add_argument("--f2-limit", type=int, default=None)
    ap.add_argument("--train-limit", type=int, default=None)
    ap.add_argument("--no-train", action="store_true")
    ap.add_argument("--max-procs", type=int, default=8)
    ap.add_argument("--extra-cache", action="append", default=[])
    ap.add_argument("--lib", default=f"{REPO}/kaggle/editcap-lib-v2")
    ap.add_argument("--tp", default=f"{REPO}/kaggle/train-pool-v2")
    ap.add_argument("--summary-name", default="summary.json")
    ap.add_argument("--smoke-force", action="store_true")     # SMOKE ONLY (see killed())
    a = ap.parse_args()
    a.run_dir = os.path.abspath(a.run_dir)
    R = Runner(a)
    if a.cmd == "run":
        R.run()
    else:
        # FINAL only: replay the tasks through the cache (no launches allowed)
        R.load_inputs()
        for c in R.cells:
            R.spawn(f"cell:{c['name']}", R.task_cell(c))
        for t in R.tasks_in:
            R.spawn(f"train:{t['name']}", R.task_train(t))
        R.step_tasks()
        for _ in range(50):
            R.step_tasks()
        assert not R.pending and all(t[3] for t in R.tasks), "final: re-check not complete"
        final(R)
        R.close()


if __name__ == "__main__":
    main()

"""Stage 3 (D0 depth test) shared definitions: tasks, calibrated specs, design sets, job keys,
a disk-robust append-only result store, and a throttled resumable process pool.

PREREG-OPAMP-V0-D0.md Stage 3 + Amendment 1 (stability gate on in every spec). README D-O23+.
Run through the env wrapper from the worktree root:
  ~/.claude/jobs/7cd7ffc3/tmp/run_cr.sh kaggle/campaigns/opamp-v0/stage3/d0.py <phase> [procs]
"""
import copy
import errno
import hashlib
import json
import math
import multiprocessing as mp
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CAMPAIGN = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CAMPAIGN)
sys.path.insert(0, os.path.join(CAMPAIGN, "stage2"))
import opamp_v0 as O          # noqa: E402
import s2common as S2         # noqa: E402  (REGIMES, LIB, WITNESSES, circuit_text; read-only)

RESULTS = os.path.join(HERE, "results")
os.makedirs(RESULTS, exist_ok=True)
JOBS_FILE = os.path.join(RESULTS, "jobs.jsonl")
TMP = "/home/dpatni/.claude/jobs/7cd7ffc3/tmp/opamp"

REGIME_ORDER = ("R1", "R23", "R4")
ANCHORS = S2.ANCHORS                       # ("ota5t", "two_stage_rz")
TASKS = [(a, r) for r in REGIME_ORDER for a in ANCHORS]
WITNESS = {"R1": "W-R1", "R23": "W-R23", "R4": "W-R4"}
F1 = tuple(S2.LIB)                         # ota5t two_stage_rz telescopic folded_cascode three_stage_nmc
SEEDS = (1, 2, 3)
EVALS_FULL, EVALS_SCREEN = 2500, 300
TOP_F2, TOP_TE, TOP_CONF = 20, 20, 5
# minimum gap (pre-reg step 2): absolute for R1 (dB) and R4 (V), relative for R23
MIN_GAP = {"R1": ("abs", 6.0), "R23": ("rel", 0.25), "R4": ("abs", 0.15)}
MAX_CALIB = 2
CPU_STOP_H = 38.0                          # refuse new launches beyond this (40 CPU-h ask line)
PROCS_MAX, PROCS_LOADED, LOAD_HI = 8, 4, 22.0
DISK_MIN_GB, TMP_MIN_GB = 5.0, 1.0


# ------------------------------------------------------------------ specs
def regime_M(reg):
    return S2.REGIMES[reg]["M"]


def calib_spec(reg, step):
    """Pre-reg calibration ladder: step k multiplies UGF min by 0.5^k, PM min -5k deg,
    Idd max x1.5^k (constraints absent from the regime are left absent)."""
    sp = copy.deepcopy(S2.REGIMES[reg]["spec"])
    c = sp["constraints"]
    if step:
        if "ugf_mhz" in c:
            c["ugf_mhz"]["min"] *= 0.5 ** step
        if "pm_deg" in c:
            c["pm_deg"]["min"] -= 5.0 * step
        if "idd_ua" in c:
            c["idd_ua"]["max"] *= 1.5 ** step
        sp["name"] = "%s-calib%d" % (sp["name"], step)
    assert sp.get("stability") == "ss_tran"          # Amendment 1
    return sp


def confirm_spec(reg, step, thr):
    sp = calib_spec(reg, step)
    sp["constraints"][regime_M(reg)] = {"min": float(thr)}
    sp["name"] = sp["name"] + "+confirm"
    return sp


def m_scale(thr):
    """Normalisation scale of the M constraint (repo convention max(|limit|, 1))."""
    return max(abs(float(thr)), 1.0)


# ------------------------------------------------------------------ designs
def _jsonl(path):
    out = []
    with open(path) as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


def f2_designs(anchor):
    """Pre-filtered F2' of the anchor (Stage 2 output), in enumeration order."""
    return _jsonl(os.path.join(S2.RESULTS, "f2_%s.jsonl" % anchor))


def te_designs(anchor):
    """The 500 two-edit designs of seed 1 (Stage 2 output)."""
    return _jsonl(os.path.join(S2.RESULTS, "two_edit_%s_s1.jsonl" % anchor))


def design_text(did):
    """did: 'F1:<name>' | 'W:<name>' | 'F2:<anchor>:<i>' | 'TE:<anchor>:<j>'."""
    p = did.split(":")
    if p[0] in ("F1", "W"):
        return S2.circuit_text(p[1])
    rows = f2_designs(p[1]) if p[0] == "F2" else te_designs(p[1])
    fld = "i" if p[0] == "F2" else "j"
    for r in rows:
        if r[fld] == int(p[2]):
            return r["netlist"]
    raise KeyError(did)


# ------------------------------------------------------------------ jobs
def job_key(netlist, spec, objective, seed, evals):
    canon = O.format_netlist(O.parse(netlist))
    blob = json.dumps({"n": canon, "c": spec["constraints"], "cl": spec.get("cl_pf"),
                       "st": spec.get("stability"), "vcm": spec.get("vcm"), "vdd": spec.get("vdd"),
                       "t": spec.get("temp_c"), "o": objective, "s": seed, "e": evals},
                      sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:20]


def make_job(phase, did, netlist, spec, objective, seed, evals, **meta):
    j = dict(phase=phase, design=did, spec=spec, objective=objective, seed=seed, evals=evals,
             netlist=netlist)
    j.update(meta)
    j["key"] = job_key(netlist, spec, objective, seed, evals)
    return j


def _r(v):
    if isinstance(v, float):
        return float("%.7g" % v) if math.isfinite(v) else str(v)
    return v


SUM_KEYS = ("gain_db", "ugf_mhz", "pm_deg", "idd_ua", "swing_vpp", "icmr_v", "icmr_lo", "icmr_hi",
            "fom_mhzpf_ma", "slew_vus", "cmrr_db", "psrr_db", "vout_dc", "ss_ripple_rel", "ss_settle_err_rel", "flags",
            "valid")


def run_one(job):
    """Worker: throttle (load / disk), size, return a compact record (no file I/O)."""
    rank = (mp.current_process()._identity or (1,))[0]
    while True:                                   # load rule: > LOAD_HI -> only 4 active
        if rank > PROCS_LOADED and os.getloadavg()[0] > LOAD_HI:
            time.sleep(30)
            continue
        if disk_low():
            time.sleep(30)
            continue
        break
    os.environ["OPAMP_V0_TMP"] = TMP
    try:
        r = O.size(job["netlist"], job["spec"], seed=job["seed"], evals=job["evals"],
                   objective=job["objective"])
    except Exception as e:                        # not cached; retried on the next run
        return {"key": job["key"], "error": "%s: %s" % (type(e).__name__, e)}
    m = r.get("metrics") or {}
    rec = {k: v for k, v in job.items() if k not in ("netlist", "spec")}
    rec.update(spec_name=job["spec"]["name"], constraints=job["spec"]["constraints"],
               feasible=r["feasible"], valid=r["valid"], target=r.get("target"),
               target_raw=r.get("target_raw"), worst_margin=r.get("worst_margin"),
               margins=r.get("margins"), best_obj=r.get("best_obj"), best_eval=r.get("best_eval"),
               n_evals=r.get("evals"), n_fail=r.get("n_fail"), cpu_s=r.get("cpu_s"),
               secs=r.get("secs"), params=r.get("params"),
               metrics={k: m.get(k) for k in SUM_KEYS}, n_params=len(r.get("params") or {}),
               n_devices=len(O.parse(r["netlist"])), prefilter=r["prefilter"]["ok"])
    if job["evals"] >= EVALS_FULL:
        rec["op"] = m.get("op")
    return json.loads(json.dumps(rec, default=str), parse_float=lambda s: _r(float(s)))


# ------------------------------------------------------------------ disk-robust store (D32-lite)
def disk_low():
    try:
        free = shutil.disk_usage(RESULTS).free / 1e9
        tfree = shutil.disk_usage(TMP if os.path.isdir(TMP) else "/tmp").free / 1e9
    except OSError:
        return True
    return free < DISK_MIN_GB or tfree < TMP_MIN_GB


class Appender:
    """Append one json row per call, fsync'd; on ENOSPC/EDQUOT truncate back to the last good
    size (no torn line) and retry with back-off (5 s doubling to 5 min). Never drops a row."""

    def __init__(self, path):
        self.path = path

    def write(self, row):
        data = (json.dumps(row, sort_keys=True) + "\n").encode()
        back = 5.0
        while True:
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
            good = os.fstat(fd).st_size
            try:
                if good:
                    with open(self.path, "rb") as fh:
                        fh.seek(good - 1)
                        if fh.read(1) != b"\n":       # torn tail of an earlier crash
                            data = b"\n" + data
                n = 0
                while n < len(data):
                    n += os.write(fd, data[n:])
                os.fsync(fd)
                return
            except OSError as e:
                if e.errno not in (errno.ENOSPC, errno.EDQUOT):
                    raise
                try:
                    os.ftruncate(fd, good)
                except OSError:
                    pass
                print("disk full writing %s; retry in %.0fs" % (self.path, back), flush=True)
                time.sleep(back)
                back = min(back * 2, 300.0)
            finally:
                os.close(fd)


def load_results(path=JOBS_FILE):
    """key -> record (torn / non-json lines are skipped; the first record of a key wins)."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path) as fh:
        for ln in fh:
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if "key" in r and "error" not in r:
                out.setdefault(r["key"], r)
    return out


def cpu_total_h(res=None):
    res = load_results() if res is None else res
    return sum(r.get("cpu_s") or 0.0 for r in res.values()) / 3600.0


def run_jobs(jobs, procs=PROCS_MAX, label=""):
    """Run jobs not yet in JOBS_FILE (exact key), append each result as it arrives.
    Stops launching (returns False) if the CPU total would pass CPU_STOP_H."""
    done = load_results()
    seen, todo = set(done), []
    for j in jobs:
        if j["key"] not in seen:
            seen.add(j["key"])
            todo.append(j)
    cpu0 = cpu_total_h(done)
    print("[%s] %d jobs, %d cached, %d to run; CPU so far %.2f h" % (
        label, len(jobs), len(jobs) - len(todo), len(todo), cpu0), flush=True)
    if not todo:
        return True
    if cpu0 > CPU_STOP_H:
        print("CPU budget guard: %.2f h > %.1f h; nothing launched" % (cpu0, CPU_STOP_H), flush=True)
        return False
    app = Appender(JOBS_FILE)
    cpu, ok, n, t0 = cpu0 * 3600.0, True, 0, time.time()
    procs = max(1, min(procs, PROCS_MAX))
    with mp.Pool(procs) as pool:   # fixed workers: ranks 1..procs (load rule)
        it = pool.imap_unordered(run_one, todo, chunksize=1)
        for rec in it:
            n += 1
            if "error" in rec:
                print("ERROR %s %s" % (rec["key"], rec["error"]), flush=True)
                continue
            app.write(rec)
            cpu += rec.get("cpu_s") or 0.0
            if n % 25 == 0 or n == len(todo) or rec["evals"] >= EVALS_FULL:
                print("[%s] %d/%d  %s s%d %s feas=%s tgt=%s  cpu=%.0fs  total %.2f CPU-h  "
                      "wall %.0fs  load %.1f" % (label, n, len(todo), rec["design"], rec["seed"],
                                                 rec["spec_name"], rec["feasible"], rec["target"],
                                                 rec["cpu_s"] or 0, cpu / 3600.0, time.time() - t0,
                                                 os.getloadavg()[0]), flush=True)
            if cpu / 3600.0 > CPU_STOP_H:
                print("CPU budget guard hit (%.2f h): terminating the pool" % (cpu / 3600.0),
                      flush=True)
                pool.terminate()
                ok = False
                break
    return ok


def median_inf(vals):
    """Median over seeds with infeasible (None) = -inf."""
    v = sorted(-math.inf if x is None else float(x) for x in vals)
    return v[len(v) // 2] if len(v) % 2 else 0.5 * (v[len(v) // 2 - 1] + v[len(v) // 2])

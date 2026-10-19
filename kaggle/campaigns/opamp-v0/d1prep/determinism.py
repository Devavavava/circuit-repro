"""D1-prep determinism checks for the CPU-time-limit fix (README D-O32).

Modes (run from the worktree root through the env wrapper):
  nmc <tag> [seed]   the D0 case that diverged under load: R23 three-stage NMC, max:fom_mhzpf_ma,
                     seed 1 (default), 2,500 evals, R23 hard constraints + stability gate.
                     Writes results/nmc_<tag>.json (digest, target, n_fail, params) and logs every
                     ngspice run with cpu or wall >= 2 s to results/simlog_nmc_<tag>.jsonl.
  v1child <tag> <k>  one V1 process (both V1 cases, exactly as gates/v1_determinism.py child) ->
                     results/v1_<tag>_proc<k>.json (digest only + summary).
  loaded [nburn]     start nburn (default 8) CPU burners (`yes > /dev/null`), run 3 V1 processes
                     and the NMC seed-1 case concurrently, kill the burners (verified with ps),
                     sample the load average every 10 s, write results/loaded.json.
The digest is computed exactly as V1's: SHA-256 of json.dumps(result without secs/cpu_s,
sort_keys=True, default=repr).
"""
import hashlib
import json
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CAMPAIGN = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CAMPAIGN)
sys.path.insert(0, os.path.join(CAMPAIGN, "gates"))
sys.path.insert(0, os.path.join(CAMPAIGN, "stage2"))
RESULTS = os.path.join(HERE, "results")
os.makedirs(RESULTS, exist_ok=True)
TMP = "/home/dpatni/.claude/jobs/7cd7ffc3/tmp/opamp"
os.environ.setdefault("OPAMP_V0_TMP", TMP)
DROP = ("secs", "cpu_s")
NMC_QUIET_TARGET = 18146          # Stage 2 / quiet-box value (D-O30), MHz pF/mA, rounded
V1_DIGEST = "178ad097a49acbdae1999fc7d008d2b213e01446865164cdd21ea2a3ab6bc94a"


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=repr).encode()).hexdigest()


def nmc(tag, seed=1):
    import s2common as S2
    import opamp_v0 as O
    os.environ["OPAMP_V0_SIMLOG"] = os.path.join(RESULTS, "simlog_nmc_%s.jsonl" % tag)
    R = S2.REGIMES["R23"]
    r = O.size(S2.circuit_text("three_stage_nmc"), R["spec"], seed=seed, evals=2500,
               objective="max:" + R["M"])
    body = {k: v for k, v in r.items() if k not in DROP}
    out = {"case": "R23 three_stage_nmc max:fom_mhzpf_ma seed %d 2500 evals" % seed, "tag": tag,
           "digest": digest(body), "feasible": r["feasible"], "target": r["target"],
           "target_raw": r["target_raw"], "n_fail": r["n_fail"], "best_eval": r["best_eval"],
           "params": r["params"], "cpu_s": r["cpu_s"], "secs": r["secs"],
           "load_end": os.getloadavg()}
    with open(os.path.join(RESULTS, "nmc_%s.json" % tag), "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps({k: out[k] for k in ("digest", "target", "n_fail", "cpu_s", "secs")}))


def v1child(tag, k):
    import v1_determinism as V1
    import opamp_v0 as O
    from common import circuit
    os.environ["OPAMP_V0_SIMLOG"] = os.path.join(RESULTS, "simlog_v1_%s.jsonl" % tag)
    out, summ = {}, {}
    for name, (net, spec, seed, obj) in sorted(V1.CASES.items()):
        r = O.size(circuit(net), spec, seed=seed, evals=2500, objective=obj)
        out[name] = {kk: v for kk, v in r.items() if kk not in DROP}
        summ[name] = {"target": r["target"], "worst_margin": r["worst_margin"],
                      "n_fail": r["n_fail"], "cpu_s": r["cpu_s"], "secs": r["secs"]}
    blob = json.dumps(out, sort_keys=True, default=repr)
    d = hashlib.sha256(blob.encode()).hexdigest()
    with open(os.path.join(RESULTS, "v1_%s_proc%s.json" % (tag, k)), "w") as fh:
        json.dump({"digest": d, "cases": summ}, fh, indent=1, sort_keys=True)
    print(d)


def _alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    # a zombie still answers kill(0); check its state
    try:
        with open("/proc/%d/stat" % pid) as fh:
            return fh.read().split()[2] != "Z"
    except OSError:
        return False


def loaded(nburn=8):
    me = os.path.abspath(__file__)
    burners, procs, loads = [], [], []
    stop = threading.Event()

    def sampler():
        while not stop.is_set():
            loads.append((round(time.time(), 1), os.getloadavg()[0]))
            stop.wait(10)
    th = threading.Thread(target=sampler, daemon=True)
    t0 = time.time()
    try:
        for _ in range(nburn):
            burners.append(subprocess.Popen(["yes"], stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL))
        th.start()
        time.sleep(5)
        for k in (1, 2, 3):
            procs.append(subprocess.Popen([sys.executable, me, "v1child", "loaded", str(k)],
                                          stdout=subprocess.PIPE))
        procs.append(subprocess.Popen([sys.executable, me, "nmc", "loaded"], stdout=subprocess.PIPE))
        outs = [p.communicate()[0].decode().strip() for p in procs]
    finally:
        for b in burners:
            b.kill()
        for b in burners:
            b.wait()
        stop.set()
    time.sleep(1)
    still = [b.pid for b in burners if _alive(b.pid)]
    ps = subprocess.run(["ps", "-u", str(os.getuid()), "-o", "pid=,comm="], stdout=subprocess.PIPE)
    yes_left = [ln.strip() for ln in ps.stdout.decode().splitlines()
                if ln.split() and ln.split()[-1] == "yes"]
    v1 = [json.load(open(os.path.join(RESULTS, "v1_loaded_proc%d.json" % k))) for k in (1, 2, 3)]
    nm = json.load(open(os.path.join(RESULTS, "nmc_loaded.json")))
    quiet = None
    qp = os.path.join(RESULTS, "nmc_quiet.json")
    if os.path.exists(qp):
        quiet = json.load(open(qp))
    lv = [x[1] for x in loads]
    res = {"nburn": nburn, "wall_s": time.time() - t0, "load1_samples": loads,
           "load1_min": min(lv) if lv else None, "load1_median": sorted(lv)[len(lv) // 2] if lv else None,
           "load1_max": max(lv) if lv else None,
           "v1_digests": [x["digest"] for x in v1], "v1_cases": [x["cases"] for x in v1],
           "v1_bit_identical": len({x["digest"] for x in v1}) == 1,
           "v1_equals_stage1_digest": all(x["digest"] == V1_DIGEST for x in v1),
           "nmc": {k: nm[k] for k in ("digest", "target", "n_fail", "cpu_s", "secs", "best_eval")},
           "nmc_target_rounded": round(nm["target"]) if nm["target"] is not None else None,
           "nmc_equals_quiet_value": (nm["target"] is not None
                                      and round(nm["target"]) == NMC_QUIET_TARGET),
           "nmc_digest_equals_quiet_run": (quiet is not None and quiet["digest"] == nm["digest"]),
           "burner_pids": [b.pid for b in burners], "burners_alive_after_kill": still,
           "ps_yes_processes_after": yes_left, "child_stdout": outs}
    res["pass"] = bool(res["v1_bit_identical"] and res["v1_equals_stage1_digest"]
                       and res["nmc_equals_quiet_value"] and not still and not yes_left)
    for k in (1, 2, 3):
        os.remove(os.path.join(RESULTS, "v1_loaded_proc%d.json" % k))
    with open(os.path.join(RESULTS, "loaded.json"), "w") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    print(json.dumps({k: v for k, v in res.items() if k not in ("load1_samples", "v1_cases")},
                     indent=1))


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "nmc":
        nmc(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1)
    elif mode == "v1child":
        v1child(sys.argv[2], sys.argv[3])
    elif mode == "loaded":
        loaded(int(sys.argv[2]) if len(sys.argv) > 2 else 8)
    else:
        raise SystemExit(__doc__)

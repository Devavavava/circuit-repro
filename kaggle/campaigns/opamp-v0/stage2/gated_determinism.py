"""V1-style determinism of the stability-gated path (D-O16): the same gated (netlist, spec, seed)
sized in 3 separate processes must give bit-identical results, and equal the stored Stage-2 result.
Case: three_stage_nmc, R1 hard constraints + gate, max:gain_db, seed 3 (a run in which the gate fires).
Writes results/gated_determinism.json. Usage: gated_determinism.py [--child K]"""
import hashlib
import json
import os
import subprocess
import sys

import s2common as C

TAG = "max-R1-three_stage_nmc-s3"
DROP = ("secs", "cpu_s")


def child(k):
    os.environ.setdefault("OPAMP_V0_TMP", "/home/dpatni/.claude/jobs/7cd7ffc3/tmp/opamp")
    R = C.REGIMES["R1"]
    r = C.O.size(C.circuit_text("three_stage_nmc"), R["spec"], seed=3, evals=2500,
                 objective="max:" + R["M"])
    blob = json.dumps({kk: v for kk, v in r.items() if kk not in DROP}, sort_keys=True, default=repr)
    m = r["metrics"] or {}
    print(json.dumps({"digest": hashlib.sha256(blob.encode()).hexdigest(), "gain_db": m.get("gain_db"),
                      "flags": m.get("flags"), "feasible": r["feasible"],
                      "params": r["params"]}, sort_keys=True))


def main():
    procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__), "--child", str(k)],
                              stdout=subprocess.PIPE) for k in (1, 2, 3)]
    outs = [json.loads(p.communicate()[0].decode().strip().splitlines()[-1]) for p in procs]
    stored = json.load(open(os.path.join(C.RESULTS, TAG + ".json")))
    same = len({o["digest"] for o in outs}) == 1
    match = all(o["params"] == stored["params"] for o in outs)
    res = {"case": TAG, "digests": [o["digest"] for o in outs], "bit_identical_3_processes": same,
           "params_equal_stored_result": match, "gain_db": outs[0]["gain_db"], "flags": outs[0]["flags"],
           "feasible": outs[0]["feasible"], "pass": same and match}
    with open(os.path.join(C.RESULTS, "gated_determinism.json"), "w") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        child(sys.argv[2])
    else:
        main()

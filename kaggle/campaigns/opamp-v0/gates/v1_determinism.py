"""V1 determinism: the same (netlist, spec, seed) gives bit-identical results in 3 separate
processes. Two cases (the in-loop swing and ICMR paths are both exercised):
  A two_stage_rz, R1 hard constraints (swing/UGF/PM/Idd), objective max:gain_db, seed 1
  B ota5t, base constraints + icmr_v >= 0.3 V, objective margin, seed 2
Each child writes a canonical JSON of everything except wall/CPU time; the parent compares
SHA-256 digests. Usage: v1_determinism.py [evals]   (child: v1_determinism.py --child K evals)"""
import hashlib
import json
import os
import subprocess
import sys

from common import RESULTS, circuit, dump
import opamp_v0 as O

CASES = {
    "A": ("two_stage_rz.net", {"name": "v1-A", "cl_pf": 2.0, "constraints": {
        "swing_vpp": {"min": 0.6}, "ugf_mhz": {"min": 10.0}, "pm_deg": {"min": 60.0},
        "idd_ua": {"max": 200.0}}}, 1, "max:gain_db"),
    "B": ("ota5t.net", {"name": "v1-B", "cl_pf": 2.0, "constraints": {
        "icmr_v": {"min": 0.3}, "ugf_mhz": {"min": 10.0}, "pm_deg": {"min": 60.0},
        "idd_ua": {"max": 200.0}}}, 2, "margin"),
}
DROP = ("secs", "cpu_s")


def child(k, evals):
    out = {}
    for name, (net, spec, seed, obj) in sorted(CASES.items()):
        r = O.size(circuit(net), spec, seed=seed, evals=evals, objective=obj)
        out[name] = {kk: v for kk, v in r.items() if kk not in DROP}
    blob = json.dumps(out, sort_keys=True, default=repr)
    with open(os.path.join(RESULTS, "v1_proc%s.json" % k), "w") as fh:
        fh.write(blob)
    print(hashlib.sha256(blob.encode()).hexdigest())


def main():
    evals = int(sys.argv[1]) if len(sys.argv) > 1 else 2500
    procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__), "--child", str(k),
                               str(evals)], stdout=subprocess.PIPE) for k in (1, 2, 3)]
    digs = [p.communicate()[0].decode().strip() for p in procs]
    blobs = [json.load(open(os.path.join(RESULTS, "v1_proc%d.json" % k))) for k in (1, 2, 3)]
    ok = len(set(digs)) == 1 and all(p.returncode == 0 for p in procs)
    summ = {}
    for name in sorted(CASES):
        r = blobs[0][name]
        mm = r["metrics"] or {}
        summ[name] = {"circuit": CASES[name][0], "objective": CASES[name][3], "seed": CASES[name][2],
                      "feasible": r["feasible"], "target": r["target"], "worst_margin": r["worst_margin"],
                      "evals": r["evals"], "best_eval": r["best_eval"],
                      "gain_db": mm.get("gain_db"), "ugf_mhz": mm.get("ugf_mhz"),
                      "pm_deg": mm.get("pm_deg"), "idd_ua": mm.get("idd_ua"),
                      "swing_vpp": mm.get("swing_vpp"), "icmr_v": mm.get("icmr_v")}
    dump("v1.json", {"gate": "V1", "pass": ok, "evals": evals, "sha256": digs, "cases": summ})
    for k in (1, 2, 3):
        os.remove(os.path.join(RESULTS, "v1_proc%d.json" % k))
    print(json.dumps(summ, indent=1))
    print("digests", digs)
    print("V1", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        child(sys.argv[2], int(sys.argv[3]))
    else:
        main()

"""V4(b') check of the small-step stability gate (README D-O16).

Re-evaluates every pre-gate Stage-2 design (results/pre_stability/{golden,max}-*.json: sized
WITHOUT the gate) with the gate on, and compares the gate's verdict with the independent
diagnostic of stability_check.py (results/pre_stability/stability_*.json: 1 mV follower step,
ripple > 5 %). Also times the gate. Writes results/stability_gate_check.json.
"""
import glob
import json
import os
import time

import s2common as C
from opamp_v0 import sizer as SZ, dialect as DL, testbench as TB

PRE = os.path.join(C.RESULTS, "pre_stability")


def main():
    os.environ.setdefault("OPAMP_V0_TMP", "/home/dpatni/.claude/jobs/7cd7ffc3/tmp/opamp")
    diag = {}
    for p in glob.glob(os.path.join(PRE, "stability_*.json")):
        for r in json.load(open(p)):
            diag[r["tag"]] = r
    rows = []
    for p in sorted(glob.glob(os.path.join(PRE, "*.json"))):
        tag = os.path.basename(p)[:-5]
        if not (tag.startswith("golden-") or tag.startswith("max-")):
            continue
        r = json.load(open(p))
        if not r.get("params"):
            continue
        devs = DL.parse(r["netlist"])
        tb = SZ.tb_from_spec(r["job"]["spec"])
        t0 = time.time()
        m0 = TB.measure(devs, r["params"], tb, icmr=False, full=False, slew=False, stab=False)
        t1 = time.time()
        m1 = TB.measure(devs, r["params"], tb, icmr=False, full=False, slew=False, stab=True)
        t2 = time.time()
        d = diag.get(tag, {})
        rec = {"tag": tag, "feasible_pre": r["summary"]["feasible"], "pm_deg": r["summary"]["pm_deg"],
               "gate_unstable": "ss_unstable" in m1["flags"], "ss_checked": m1.get("ss_checked"),
               "ss_ripple_rel": m1.get("ss_ripple_rel"), "ss_settle_err_rel": m1.get("ss_settle_err_rel"),
               "diag_oscillates": d.get("small_signal_oscillates"),
               "loop_eval_ms_without": (t1 - t0) * 1e3, "loop_eval_ms_with": (t2 - t1) * 1e3}
        rec["agree"] = (rec["diag_oscillates"] is None or not rec["ss_checked"]
                        or rec["diag_oscillates"] == rec["gate_unstable"])
        rows.append(rec)
        print(json.dumps(rec, sort_keys=True), flush=True)
    chk = [r for r in rows if r["ss_checked"] and r["diag_oscillates"] is not None]
    out = {"rows": rows, "n": len(rows), "n_compared": len(chk),
           "n_agree": sum(1 for r in chk if r["agree"]),
           "n_gate_unstable_among_feasible_pre": sum(1 for r in rows if r["feasible_pre"] and r["gate_unstable"]),
           "tags_gate_unstable": [r["tag"] for r in rows if r["gate_unstable"]],
           "median_ms_without": sorted(r["loop_eval_ms_without"] for r in rows)[len(rows) // 2],
           "median_ms_with": sorted(r["loop_eval_ms_with"] for r in rows)[len(rows) // 2]}
    with open(os.path.join(C.RESULTS, "stability_gate_check.json"), "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print({k: v for k, v in out.items() if k != "rows"})


if __name__ == "__main__":
    main()

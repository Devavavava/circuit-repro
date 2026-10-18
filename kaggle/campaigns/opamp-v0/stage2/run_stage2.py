"""Run every Stage-2 sizing job in one pool (goldens, max-<R> seed 1, preview seeds 2-3),
then write results/table_all.json. Resumable (existing result files are reused).
Usage: run_stage2.py [procs=4]
"""
import json
import os
import sys

import s2common as C
import goldens
import preview_seeds as PS


def main():
    procs = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    jobs = goldens.jobs("all")
    for seed in (2, 3):
        for reg, n in PS.PAIRS:
            R = C.REGIMES[reg]
            jobs.append(dict(tag="max-%s-%s-s%d" % (reg, n, seed), circuit=n, spec=R["spec"],
                             objective="max:" + R["M"], seed=seed, evals=2500))
    # longest first (witnesses / three-stage) for a better pool packing
    order = {"W-R23": 0, "W-R4": 1, "W-R1": 2, "three_stage_nmc": 3}
    jobs.sort(key=lambda j: (order.get(j["circuit"], 9), j["tag"]))
    recs = C.run_jobs(jobs, procs)
    table = {r["job"]["tag"]: dict(r["summary"], spec=r["job"]["spec"]["name"],
                                   objective=r["job"]["objective"], seed=r["job"]["seed"])
             for r in recs}
    with open(os.path.join(C.RESULTS, "table_all.json"), "w") as fh:
        json.dump(table, fh, indent=1, sort_keys=True, default=str)
    print("total cpu_s", sum(r["summary"]["cpu_s"] for r in recs))


if __name__ == "__main__":
    main()

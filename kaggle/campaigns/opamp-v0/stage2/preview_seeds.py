"""PREVIEW (not D0): seeds 2 and 3 of the max:M runs for each witness and for the best F1
circuit of its regime at seed 1, so witness feasibility at 3 seeds (Stage 3's calibration
question) and seed spread are visible before Stage 3. Writes results/max-<R>-<circuit>-s<seed>.json.
Usage: preview_seeds.py [procs]
"""
import sys

import s2common as C

PAIRS = [("R1", "W-R1"), ("R1", "three_stage_nmc"), ("R23", "W-R23"), ("R23", "three_stage_nmc"),
         ("R4", "W-R4"), ("R4", "two_stage_rz")]


def main():
    procs = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    jobs = []
    for seed in (2, 3):
        for reg, n in PAIRS:
            R = C.REGIMES[reg]
            jobs.append(dict(tag="max-%s-%s-s%d" % (reg, n, seed), circuit=n, spec=R["spec"],
                             objective="max:" + R["M"], seed=seed, evals=2500))
    C.run_jobs(jobs, procs)


if __name__ == "__main__":
    main()

"""pool.py <P> <jobsfile> <logfile> : run each job line via one.sh, P at a time
(resume-capable: s1_drv.py run skips a job whose raw file exists)."""
import sys, subprocess
from concurrent.futures import ThreadPoolExecutor
ONE = ("/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/"
       "campaigns/bench-v12-audit/S-1-stab-inloop/one.sh")
P, jf, lf = int(sys.argv[1]), sys.argv[2], sys.argv[3]
jobs = [ln.split() for ln in open(jf) if ln.strip()]
log = open(lf, "a")


def go(j):
    p = subprocess.run([ONE] + j, capture_output=True, text=True)
    out = (p.stdout.strip().splitlines() or [""])[-1]
    msg = out if p.returncode == 0 else \
        f"FAIL rc={p.returncode} {' '.join(j)} {p.stderr[-800:]}"
    print(msg, file=log, flush=True)


with ThreadPoolExecutor(P) as ex:
    list(ex.map(go, jobs))
print("done", len(jobs), file=log, flush=True)

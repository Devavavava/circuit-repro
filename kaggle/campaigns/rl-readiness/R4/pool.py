"""pool.py <P> <jobsfile> <logfile> [script] : run each job line via <script>
(default one.sh), P at a time. Resume-capable (the run step skips existing raw)."""
import sys, subprocess, os
from concurrent.futures import ThreadPoolExecutor
D = os.path.dirname(os.path.abspath(__file__))
P, jf, lf = int(sys.argv[1]), sys.argv[2], sys.argv[3]
ONE = os.path.join(D, sys.argv[4] if len(sys.argv) > 4 else "one.sh")
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

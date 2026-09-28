"""pool.py <P> <jobsfile> <logfile> : run each job line via one.sh, at most P at
a time, and at most 4 while the 1-min load average is above 22 (shared box).
Resume-capable: v1_drv.py run skips a job whose raw file exists."""
import sys, os, time, threading, subprocess
from concurrent.futures import ThreadPoolExecutor
ONE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "one.sh")
P, jf, lf = int(sys.argv[1]), sys.argv[2], sys.argv[3]
jobs = [ln.split() for ln in open(jf) if ln.strip()]
log = open(lf, "a")
lock, active = threading.Lock(), [0]


def go(j):
    while True:
        with lock:
            cap = 4 if os.getloadavg()[0] > 22 else P
            if active[0] < cap:
                active[0] += 1
                break
        time.sleep(20)
    try:
        p = subprocess.run([ONE] + j, capture_output=True, text=True)
    finally:
        with lock:
            active[0] -= 1
    out = (p.stdout.strip().splitlines() or [""])[-1]
    msg = out if p.returncode == 0 else f"FAIL rc={p.returncode} {' '.join(j)} {p.stderr[-800:]}"
    print(msg, file=log, flush=True)


with ThreadPoolExecutor(P) as ex:
    list(ex.map(go, jobs))
print("done", len(jobs), file=log, flush=True)

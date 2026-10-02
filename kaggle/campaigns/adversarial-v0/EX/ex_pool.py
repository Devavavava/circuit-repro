"""Load-aware process pool with CPU accounting.

  pool.py <cmds.txt> <log.jsonl>       each line: <out_path>\t<command...>
A job whose out_path exists is skipped (resume-safe). At most 4 processes; at
most 2 while the 1-min load average is above 22 (shared box). Each finished job
appends {out, rc, wall_s, cpu_s (user+sys of the child tree)} to the log.
"""
import json
import os
import shlex
import subprocess
import sys
import time

MAXP, MAXP_HIGH, LOAD_HIGH = 4, 2, 22.0


def load1():
    try:
        return float(open("/proc/loadavg").read().split()[0])
    except Exception:                                            # noqa: BLE001
        return 0.0


def run(jobs, log, maxp=MAXP, quiet=False, capfile="ex_maxp"):
    """jobs: [(out_path, argv list)]. Blocks until all done."""
    todo = [j for j in jobs if not os.path.exists(j[0])]
    running = {}
    with open(log, "a") as lf:
        while todo or running:
            cap = MAXP_HIGH if load1() > LOAD_HIGH else maxp
            try:            # runtime cap (e.g. 3 while another EX job holds a slot)
                cap = min(cap, int(open(os.path.join(os.environ.get("TMPDIR", "/tmp"),
                                                     capfile)).read().strip()))
            except (OSError, ValueError):
                pass
            while todo and len(running) < cap:
                out, argv = todo.pop(0)
                errf = open(out + ".err", "w")
                p = subprocess.Popen(argv, stdout=errf, stderr=subprocess.STDOUT)
                running[p.pid] = (p, out, time.time(), errf)
            pid, status, ru = os.wait4(-1, 0)
            if pid not in running:
                continue
            p, out, t0, errf = running.pop(pid)
            errf.close()
            rc = os.waitstatus_to_exitcode(status)
            p.returncode = rc
            rec = {"out": out, "rc": rc, "wall_s": round(time.time() - t0, 1),
                   "cpu_s": round(ru.ru_utime + ru.ru_stime, 1),
                   "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "load1": load1()}
            lf.write(json.dumps(rec) + "\n")
            lf.flush()
            if rc == 0 and os.path.exists(out + ".err") and os.path.getsize(out + ".err") < 4096:
                pass
            if not quiet:
                print(json.dumps(rec), flush=True)


def main(cmds, log, maxp=MAXP, capfile="ex_maxp"):
    jobs = []
    for ln in open(cmds):
        ln = ln.rstrip("\n")
        if not ln.strip():
            continue
        out, cmd = ln.split("\t", 1)
        jobs.append((out, shlex.split(cmd)))
    run(jobs, log, maxp=maxp, capfile=capfile)


if __name__ == "__main__":
    # optional: <maxp> <cap file name under $TMPDIR> (a second pool sharing the box)
    main(sys.argv[1], sys.argv[2], *([int(sys.argv[3])] if len(sys.argv) > 3 else []),
         *(sys.argv[4:5]))

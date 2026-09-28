"""watch.py <logfile> : print one line on FAIL / high load (>22) / pool done, then exit
(or keep going on high load). Polls every 60 s."""
import sys, time
lf = sys.argv[1]
warned = False
while True:
    txt = open(lf).read() if __import__("os").path.exists(lf) else ""
    load = float(open("/proc/loadavg").read().split()[0])
    if load > 22 and not warned:
        print(f"LOAD HIGH {load}", flush=True)
        warned = True
    if load <= 18:
        warned = False
    nf = sum(1 for l in txt.splitlines() if l.startswith("FAIL"))
    if nf:
        print(f"FAILS {nf}", flush=True)
        break
    if any(l.startswith("done") for l in txt.splitlines()):
        print(f"POOL DONE {len(txt.splitlines())} lines", flush=True)
        break
    time.sleep(60)

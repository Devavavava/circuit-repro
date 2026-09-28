"""E-c (PREREG-BENCH-V12-AUDIT.md): brute-force single-edit search on bench-v1.2.

Search space per cell = SHOWN anchor (<cell>/anchor.net) + exactly one primitive edit:
  (i)  add one R/C/L between any unordered pair of distinct anchor nets (incl. rails/ports),
  (ii) delete any one existing element line.
Screen: seed 1 x 2500 (every valid candidate). Confirm: seeds 1,2,3 x 2500 for each
screen-feasible candidate.

Usage:
  python ec_search.py gen                      # enumerate + round-trip -> candidates.jsonl
  python ec_search.py run [NPROC]              # screen (wb cells first, then nb) then confirm
  python ec_search.py worker CELL CID SEED     # one sizing call (subprocess), prints JSON
Resume-capable: results.jsonl is appended per call; finished (cell,cid,seed) are skipped.

Fixed enumeration order (per anchor): nets sorted by Python str sort; unordered pairs via
itertools.combinations over that list; per pair element types R, C, L; new element named
Rx/Cx/Lx and written "TYPE name a b" with a<b in that sort; THEN deletions in anchor
line order.
"""
import sys, os, json, time, itertools, subprocess, hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
LIB = f"{REPO}/kaggle/editcap-lib-v12-45nm"
OUT = f"{REPO}/kaggle/campaigns/bench-v12-audit/E-c"
CAND = f"{OUT}/candidates.jsonl"
RES = f"{OUT}/results.jsonl"
BUDGET = 2500
TIMEOUT_S = 1800

for p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop"):
    if p not in sys.path:
        sys.path.insert(0, p)


def cells():
    cs = sorted(os.listdir(LIB))
    wb = [c for c in cs if "-wb-" in c]
    nb = [c for c in cs if "-nb-" in c]
    return wb + nb                      # wideband first (task instruction)


def anchor_key(cell):
    return hashlib.md5(open(f"{LIB}/{cell}/anchor.net", "rb").read()).hexdigest()[:12]


def enumerate_edits(text):
    lines = text.splitlines()
    elems = []                          # (line_index, TYPE, name, nets)
    for i, raw in enumerate(lines):
        s = raw.strip()
        if not s or s[0] in "#*":
            continue
        parts = s.split()
        elems.append((i, parts[0].upper(), parts[1], parts[2:]))
    nets = sorted({n for _i, _t, _n, ns in elems for n in ns})
    names = {e[2] for e in elems}
    body = "\n".join(lines)
    cands = []
    for a, b in itertools.combinations(nets, 2):
        for typ in ("R", "C", "L"):
            nm = typ + "x"
            assert nm not in names
            cands.append({"kind": "add", "desc": f"add {typ} {a}-{b}",
                          "netlist": body.rstrip("\n") + f"\n{typ} {nm} {a} {b}\n"})
    for i, typ, name, ns in elems:
        kept = [l for j, l in enumerate(lines) if j != i]
        cands.append({"kind": "del", "desc": f"del {typ} {name} ({' '.join(ns)})",
                      "netlist": "\n".join(kept) + "\n"})
    return nets, elems, cands


def gen():
    import proposal as P
    seen = {}
    out = []
    for cell in cells():
        k = anchor_key(cell)
        if k in seen:
            continue
        text = open(f"{LIB}/{cell}/anchor.net").read()
        nets, elems, cands = enumerate_edits(text)
        seen[k] = cell
        for idx, c in enumerate(cands):
            rt = P.round_trip(c["netlist"])
            out.append({"anchor": k, "anchor_first_cell": cell, "order": idx,
                        "cid": f"{k}:{idx:03d}", "kind": c["kind"], "desc": c["desc"],
                        "rt_ok": bool(rt.get("ok")), "rt_error": rt.get("error"),
                        "n_devices": rt.get("n_devices"), "wl_hash": rt.get("wl_hash"),
                        "tokens": rt.get("tokens"), "netlist": c["netlist"]})
        print(f"anchor {k} ({cell}): nets={len(nets)} {nets} elems={len(elems)} "
              f"cands={len(cands)} rt_ok={sum(o['rt_ok'] for o in out if o['anchor']==k)}")
    with open(CAND, "w") as f:
        for o in out:
            f.write(json.dumps(o) + "\n")


def load_cands():
    return [json.loads(l) for l in open(CAND)]


def worker(cell, cid, seed):
    import bench_anchor_prep as PREP, mysolve as MS
    from spec import Spec
    c = next(x for x in load_cands() if x["cid"] == cid)
    sp = f"{LIB}/{cell}/spec.yaml"
    spec = Spec.load(sp)
    t0 = time.time()
    r = PREP.smoke_run(list(c["tokens"]), sp, seed, BUDGET, "bptm45")
    dt = time.time() - t0
    rec = {"cell": cell, "cid": cid, "seed": seed, "budget": BUDGET, "secs": dt,
           "sizable": r is not None}
    if r is not None:
        rows, worst = MS._margins(spec, r.get("metrics") or {})
        rec.update(feasible=bool(r["feasible"]), worst=worst,
                   margins={n: mg for n, _a, _c, mg, _s in rows},
                   metrics={k: v for k, v in (r.get("metrics") or {}).items()
                            if isinstance(v, (int, float, str, bool)) or v is None},
                   n_evals=r.get("n_evals"), n_sim_fail=r.get("n_sim_fail"),
                   sim_error=r.get("sim_error"))
    else:
        rec["feasible"] = False
    print("@@REC@@" + json.dumps(rec, default=repr))


def _done():
    """{(cell, cid, seed, phase): rec} of finished calls (last record wins)."""
    d = {}
    if os.path.exists(RES):
        for l in open(RES):
            try:
                r = json.loads(l)
            except Exception:
                continue
            d[(r["cell"], r["cid"], r["seed"], r["phase"])] = r
    return d


def _call(era, cell, cid, seed, phase):
    t0 = time.time()
    env = dict(os.environ)
    try:
        p = subprocess.run([sys.executable, __file__, "worker", cell, cid, str(seed)],
                           capture_output=True, text=True, timeout=TIMEOUT_S, env=env)
        line = [l for l in p.stdout.splitlines() if l.startswith("@@REC@@")]
        if line:
            rec = json.loads(line[-1][7:])
        else:
            rec = {"cell": cell, "cid": cid, "seed": seed, "sizable": None, "feasible": False,
                   "error": "worker_crash rc=%s: %s" % (p.returncode, p.stderr[-1500:])}
    except subprocess.TimeoutExpired:
        rec = {"cell": cell, "cid": cid, "seed": seed, "sizable": None, "feasible": False,
               "error": f"timeout>{TIMEOUT_S}s"}
    rec.update(phase=phase, era=era, wall_total=time.time() - t0,
               ts=time.strftime("%Y-%m-%dT%H:%M:%S"))
    return rec


def confirm_only(nproc, era, which):
    """Confirm phase only, restricted to wb/nb/all cells (used to finish wideband fully
    before narrowband when the projected runtime exceeded 7 h)."""
    done = _done()
    ctasks = []
    for (cell, cid, seed, phase), r in sorted(done.items()):
        if which != "all" and f"-{which}-" not in cell:
            continue
        if phase == "screen" and r.get("feasible"):
            for s in (1, 2, 3):
                if (cell, cid, s, "confirm") not in done:
                    ctasks.append((cell, cid, s, "confirm"))
    print(f"confirm-only ({which}) tasks pending: {len(ctasks)}", flush=True)
    _execute(ctasks, nproc, era)


def run(nproc, era):
    cands = load_cands()
    byanchor = {}
    for c in cands:
        byanchor.setdefault(c["anchor"], []).append(c)
    done = _done()
    tasks = []
    for cell in cells():
        for c in byanchor[anchor_key(cell)]:
            if c["rt_ok"] and (cell, c["cid"], 1, "screen") not in done:
                tasks.append((cell, c["cid"], 1, "screen"))
    print(f"screen tasks pending: {len(tasks)}", flush=True)
    _execute(tasks, nproc, era)
    done = _done()
    ctasks = []
    for (cell, cid, seed, phase), r in sorted(done.items()):
        if phase == "screen" and r.get("feasible"):
            # confirm seeds 1,2,3 (seed-1 rerun doubles as a determinism check)
            for s in (1, 2, 3):
                if (cell, cid, s, "confirm") not in done:
                    ctasks.append((cell, cid, s, "confirm"))
    print(f"confirm tasks pending: {len(ctasks)}", flush=True)
    _execute(ctasks, nproc, era)


def _execute(tasks, nproc, era):
    n = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=nproc) as ex, open(RES, "a") as f:
        futs = {ex.submit(_call, era, *t): t for t in tasks}
        for fu in as_completed(futs):
            rec = fu.result()
            f.write(json.dumps(rec, default=repr) + "\n"); f.flush()
            n += 1
            if n % 20 == 0 or rec.get("feasible"):
                el = time.time() - t0
                print(f"[{n}/{len(tasks)} {el/60:.1f}min eta {el/n*(len(tasks)-n)/60:.0f}min] "
                      f"{rec['cell']} {rec['cid']} s{rec['seed']} feas={rec.get('feasible')} "
                      f"worst={rec.get('worst')} secs={rec.get('secs')}", flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "gen":
        gen()
    elif cmd == "worker":
        worker(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    elif cmd == "run":
        nproc = int(sys.argv[2]) if len(sys.argv) > 2 else 8
        era = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True,
                             text=True).stdout.strip()
        era = os.environ.get("EC_ERA", era)
        run(nproc, era)
    elif cmd == "confirm":
        nproc = int(sys.argv[2]); which = sys.argv[3]
        era = os.environ.get("EC_ERA") or subprocess.run(
            ["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        confirm_only(nproc, era, which)

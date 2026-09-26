"""bench-v12-audit E-d scorer (PREREG-BENCH-V12-AUDIT.md, E-d).

usage (run through envrun.sh so the crenv vars + TMPDIR are set):
  ed_score.py enumerate            -> edits.jsonl, completions.jsonl, cand.json
  ed_score.py run [nproc]          -> sizes every unique (cell, token-seq) x seeds 1,2,3
                                      (2500 evals, bptm45); appends score.jsonl
                                      incrementally; resumable (skips done keys)
  ed_score.py one <cell> <key> <seed> <out.json>   (worker; one subprocess per job)
  (tables: ed_summarize.py)

Engine (matched to the template calibration / E-a / E-b):
  bench_anchor_prep.smoke_run(tokens, <lib>/<cell>/spec.yaml, seed, 2500, "bptm45"),
  feasible = result["feasible"], worst margin = mysolve._margins (normalized).
Every edit netlist archived by the kernels (editcap/<COND>-s<N>/adjudication/<cell>/B/
edit<i>.net) goes through proposal.round_trip; invalid ones are recorded, valid ones
are deduped per cell on the exact token sequence (sized once, credited to every edit
carrying it), INCLUDING edits identical to the anchor or to an earlier edit (the kernel
skipped those as WL-dups; locally they are sized anyway so every valid edit is scored).
"""
import sys, os, json, time, glob, hashlib, re, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop"):
    if p not in sys.path:
        sys.path.insert(0, p)
ED = REPO + "/kaggle/campaigns/bench-v12-audit/E-d"
LIB = REPO + "/kaggle/editcap-lib-v12-45nm"
AUD = REPO + "/kaggle/campaigns/bench-v12-audit"
BUDGET, SEEDS, PDK = 2500, (1, 2, 3), "bptm45"
ERA = os.environ.get("ED_ERA", "a0e4edcc6ac10ee030730bbe0e40f958c5fc42be")
# (download dir, model id) ; conditions/samples discovered from editcap/<COND>-s<N>
MODELS = (("32b-zs", "qwen3-32b-q4ks"), ("32b-fs", "qwen3-32b-q4ks"),
          ("14b", "qwen3-14b-q4km"))
RAW = os.path.join(os.environ.get("TMPDIR", "/tmp"), "ed-raw")


def cells():
    return sorted(d for d in os.listdir(LIB) if d.startswith("v12-"))


def labels():
    eb = json.load(open(AUD + "/E-b/verdicts.json"))
    ea = json.load(open(AUD + "/E-a/verdicts.json"))
    lab = {}
    for c in cells():
        lab[c] = {"retrieval": bool(eb[c]["retrieval"]),
                  "edge": bool(ea[c]["edge"]),
                  "band": "wb" if "-wb-" in c else "nb"}
    return lab


def tokkey(tokens):
    return hashlib.sha1(json.dumps(list(tokens)).encode()).hexdigest()[:16]


# ------------------------------------------------------------- topology detectors
def _load_topo_module():
    """Exec only the DEFINITIONS of analyze_qwen_vs_claude_topo.py (the file runs a
    report at import time; everything from `WB=sorted(` on is that report)."""
    src = open(REPO + "/kaggle/analyze_qwen_vs_claude_topo.py").read()
    ns = {}
    exec(compile(src.split("\nWB=sorted(")[0], "analyze_qwen_vs_claude_topo.py",
                 "exec"), ns)
    return ns


_T = None


def topo_flags(text):
    """narrow  = analyze_qwen_vs_claude_topo.has_shunt_feedback (R between a
                 non-diode signal drain and a non-diode signal gate, no supply end)
    wide    = pre-reg widened detector: any R between an INPUT-transistor gate net
              and any drain / tank / output net. Input transistors = MOS whose gate
              net is reachable from VIN1 through C/L elements only (no supplies, not
              through a non-diode drain). Targets = non-diode MOS drain nets, nets
              touched by both an L and a C (tank), and VOUT1; minus every net of the
              VIN1 C/L component (so an input-side damping R, e.g. across the input
              series L, is NOT counted as feedback).
    wide_vin = same, but the input side is the whole VIN1 C/L component (so an R
              from VIN1 or an AC-coupled input node to a drain/output also counts).
    cascode / tank = analyze_qwen_vs_claude_topo.has_cascode / has_tank."""
    global _T
    if _T is None:
        _T = _load_topo_module()
    devs = _T["parse"](text)
    SUP = {"VDD", "VSS", "0"}
    mos = [d for d in devs if d[0] in ("NMOS", "PMOS")]
    drains = {D for _t, _n, D, G, S, B in mos if D != G} - SUP
    gates_of = {}
    for _t, _n, D, G, S, B in mos:
        gates_of.setdefault(G, []).append(_n)
    lnodes, cnodes = set(), set()
    adj = {}
    for d in devs:
        if d[0] in ("L", "C"):
            a, b = d[2], d[3]
            (lnodes if d[0] == "L" else cnodes).update((a, b))
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
    comp, stack = {"VIN1"}, ["VIN1"]
    while stack:
        n = stack.pop()
        if n in drains and n != "VIN1":
            continue
        for m in adj.get(n, ()):
            if m in SUP or m in comp:
                continue
            comp.add(m)
            stack.append(m)
    in_gates = {n for n in comp if n in gates_of and n not in drains}
    tank = (lnodes & cnodes) - SUP
    tgt = (drains | tank | {"VOUT1"}) - SUP
    wide = wide_vin = False
    for d in devs:
        if d[0] != "R":
            continue
        a, b = d[2], d[3]
        if a in SUP or b in SUP or a == b:
            continue
        for x, y in ((a, b), (b, a)):
            if x in in_gates and y in (tgt - comp):
                wide = True
            if x in comp and y in (tgt - comp):
                wide_vin = True
    return {"narrow_fb": bool(_T["has_shunt_feedback"](devs)), "wide_fb": wide,
            "wide_vin_fb": wide_vin, "cascode": bool(_T["has_cascode"](devs)),
            "tank": bool(_T["has_tank"](devs)), "n_dev": len(devs)}


# ------------------------------------------------------------- enumerate
def _server_timings(logpath):
    """Sequential (single-slot) llama-server print_timing triples, in order."""
    out, cur = [], {}
    if not os.path.exists(logpath):
        return out
    for ln in open(logpath, errors="replace"):
        m = re.search(r"prompt eval time =\s*([\d.]+) ms /\s*(\d+) tokens", ln)
        if m:
            cur = {"prompt_ms": float(m.group(1)), "prompt_tokens": int(m.group(2))}
            continue
        m = re.search(r"\beval time =\s*([\d.]+) ms /\s*(\d+) tokens", ln)
        if m and "prompt" not in ln:
            cur["eval_ms"], cur["eval_tokens"] = float(m.group(1)), int(m.group(2))
            continue
        m = re.search(r"total time =\s*([\d.]+) ms", ln)
        if m:
            cur["total_ms"] = float(m.group(1))
            out.append(cur)
            cur = {}
    return out


def enumerate_edits():
    import proposal as P
    lab = labels()
    anchor_key, anchor_flags = {}, {}
    for c in cells():
        txt = open(f"{LIB}/{c}/anchor.net").read()
        anchor_key[c] = tokkey(P.round_trip(txt)["tokens"])
        anchor_flags[c] = topo_flags(txt)
    edits, comps, cand = [], [], {}
    for d, model in MODELS:
        root = f"{ED}/{d}/editcap"
        man = f"{root}/KERNEL-MANIFEST.json"
        if not os.path.exists(man):
            continue
        manj = json.load(open(man))
        timings = _server_timings(f"{ED}/{d}/llama-server.log")
        ti = 0
        for run in manj.get("runs", []):
            cond, samp = run["cond"], run["sample"]
            rdir = f"{root}/{cond}-s{samp}"
            rpath = f"{rdir}/results-B.jsonl"
            if not os.path.exists(rpath):
                continue
            rows = [json.loads(l) for l in open(rpath) if l.strip()]
            for r in rows:
                cell = r["spec"]
                adj = f"{rdir}/adjudication/{cell}/B"
                cm = {}
                if os.path.exists(adj + "/completion.meta.json"):
                    cm = json.load(open(adj + "/completion.meta.json"))
                ctoks = (cm.get("usage") or {}).get("completion_tokens")
                tim = None
                if r.get("llm_error") is None and ti < len(timings):
                    tim = timings[ti]
                    ti += 1
                    if ctoks is not None and tim.get("eval_tokens") not in (ctoks, ctoks - 1, ctoks + 1):
                        tim = dict(tim, mismatch=True)
                raw = open(adj + "/raw_output.txt", errors="replace").read() \
                    if os.path.exists(adj + "/raw_output.txt") else ""
                nets = sorted(glob.glob(adj + "/edit*.net"),
                              key=lambda p: int(re.search(r"edit(\d+)\.net$", p).group(1)))
                inkf = {e["index"]: e for e in r.get("edits") or []}
                comps.append({
                    "model": model, "dir": d, "cond": cond, "sample": samp, "cell": cell,
                    "finish_reason": cm.get("finish_reason"),
                    "completion_tokens": ctoks,
                    "prompt_tokens": (cm.get("usage") or {}).get("prompt_tokens"),
                    "content_chars": cm.get("content_chars"),
                    "reasoning_chars": cm.get("reasoning_chars"),
                    "recovered_from_reasoning": cm.get("recovered_from_reasoning"),
                    "llm_error": r.get("llm_error"),
                    "empty_content": (not raw.strip()),
                    "n_edits": len(nets),
                    "inkernel_feasible": bool(r.get("feasible")),
                    "timing": tim})
                for p in nets:
                    i = int(re.search(r"edit(\d+)\.net$", p).group(1))
                    txt = open(p, errors="replace").read()
                    info = P.round_trip(txt)
                    k = tokkey(info["tokens"]) if info["ok"] else None
                    ik = inkf.get(i, {})
                    rec = {"model": model, "dir": d, "cond": cond, "sample": samp,
                           "cell": cell, "edit": i,
                           "path": os.path.relpath(p, REPO),
                           "valid": bool(info["ok"]),
                           "error": info.get("error"), "wl_hash": info.get("wl_hash"),
                           "key": k, "is_anchor": (k == anchor_key[cell]) if k else False,
                           "inkernel": {"valid": ik.get("valid"), "dup": ik.get("dup"),
                                        "fence_outcome": ik.get("fence_outcome"),
                                        "sized_feasible": ik.get("sized_feasible"),
                                        "feasible": ik.get("feasible"),
                                        "worst_margin": ik.get("worst_margin")},
                           "topo": topo_flags(txt),
                           "anchor_topo": anchor_flags[cell]}
                    edits.append(rec)
                    if k and (cell, k) not in cand:
                        cand[(cell, k)] = info["tokens"]
        comps_d = [c for c in comps if c["dir"] == d]
        print(d, "completions", len(comps_d), "server timings", len(timings),
              "consumed", ti, file=sys.stderr)
    with open(ED + "/edits.jsonl", "w") as fh:
        for e in edits:
            fh.write(json.dumps(e, default=repr) + "\n")
    with open(ED + "/completions.jsonl", "w") as fh:
        for c in comps:
            fh.write(json.dumps(c, default=repr) + "\n")
    json.dump({f"{c}|{k}": t for (c, k), t in cand.items()},
              open(ED + "/cand.json.tmp", "w"))
    os.replace(ED + "/cand.json.tmp", ED + "/cand.json")
    print("edits", len(edits), "valid", sum(e["valid"] for e in edits),
          "unique (cell,tokens)", len(cand))


# ------------------------------------------------------------- sizing
def one(cell, key, seed, out):
    import bench_anchor_prep as PREP, mysolve as MS
    from spec import Spec
    tok = json.load(open(ED + "/cand.json"))[f"{cell}|{key}"]
    sp = f"{LIB}/{cell}/spec.yaml"
    seed = int(seed)
    rec = {"cell": cell, "key": key, "seed": seed, "budget": BUDGET, "pdk": PDK,
           "era": ERA}
    t0 = time.time()
    try:
        r = PREP.smoke_run(list(tok), sp, seed, BUDGET, PDK)
        err = None
    except Exception as e:                                        # noqa: BLE001
        r, err = None, repr(e)
    rec["secs"] = round(time.time() - t0, 1)
    if r is None:
        rec.update(sizable=False if err is None else None, error=err, feasible=False,
                   worst=None, binding=None, margins=None, metrics=None)
    else:
        rows, worst = MS._margins(Spec.load(sp), r.get("metrics") or {})
        m = r.get("metrics") or {}
        rec.update(sizable=True, error=None, feasible=bool(r["feasible"]),
                   worst=(worst[1] if worst else None),
                   binding=(worst[0] if worst else None),
                   margins={n: mg for n, _a, _c, mg, _s in rows},
                   mu_min=m.get("mu_min"), metrics=m, n_evals=r.get("n_evals"),
                   n_sim_fail=r.get("n_sim_fail"), sim_error=r.get("sim_error"),
                   winner_reeval_ungated=r.get("winner_reeval_ungated"))
    json.dump(rec, open(out, "w"), default=repr)


def run(nproc=6):
    os.makedirs(RAW, exist_ok=True)
    cand = json.load(open(ED + "/cand.json"))
    lab = labels()
    done = set()
    sp = ED + "/score.jsonl"
    if os.path.exists(sp):
        for l in open(sp):
            if l.strip():
                j = json.loads(l)
                done.add((j["cell"], j["key"], j["seed"]))
    # synthesis cells first, then retrieval; seed-major inside
    order = sorted(cand, key=lambda ck: (lab[ck.split("|")[0]]["retrieval"], ck))
    jobs = [(ck.split("|")[0], ck.split("|")[1], s) for s in SEEDS for ck in order
            if (ck.split("|")[0], ck.split("|")[1], s) not in done]
    print(f"{len(jobs)} jobs to run ({len(done)} done)", flush=True)
    t0 = time.time()

    def work(job):
        cell, key, seed = job
        out = f"{RAW}/{cell}__{key}__s{seed}.json"
        subprocess.run([sys.executable, __file__, "one", cell, key, str(seed), out],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(out):
            return json.load(open(out))
        return {"cell": cell, "key": key, "seed": seed, "era": ERA, "crashed": True,
                "feasible": False, "sizable": None}

    n = 0
    with ThreadPoolExecutor(max_workers=int(nproc)) as ex, open(sp, "a") as fh:
        futs = [ex.submit(work, j) for j in jobs]
        for f in as_completed(futs):
            rec = f.result()
            fh.write(json.dumps(rec, default=repr) + "\n")
            fh.flush()
            n += 1
            el = (time.time() - t0) / 60
            print(f"[{n}/{len(jobs)} {el:.1f}min eta {el / n * (len(jobs) - n):.0f}min] "
                  f"{rec['cell']} {rec['key']} s{rec['seed']} feas={rec.get('feasible')} "
                  f"worst={rec.get('binding')},{rec.get('worst')} secs={rec.get('secs')}",
                  flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "enumerate":
        enumerate_edits()
    elif a[0] == "run":
        run(int(a[1]) if len(a) > 1 else 6)
    elif a[0] == "one":
        one(*a[1:5])

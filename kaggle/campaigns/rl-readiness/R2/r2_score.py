"""rl-readiness R2 scorer (PREREG-RL-READINESS.md, R2) -- E-d scoring logic, reused.

usage (through envrun.sh):
  r2_score.py enumerate           -> edits.jsonl, completions.jsonl, cand.json
  r2_score.py run <mode> [nproc] [cond,cond..]
        mode = plain  : <lib>/<cell>/spec.yaml                          (== E-d)
               gate   : bench_anchor_prep.stability_spec(spec) (mu_min>=1, wide
                        0.1-20 GHz audit of the winner; gate-only, no in-loop term)
               inloop : same spec + STAB_WIDE_INLOOP=1 (S-1 in-loop stability term)
        sizes every unique (cell, token-seq) of the chosen conditions x seeds 1,2,3
        (2500 evals, bptm45); appends score-<mode>.jsonl; resumable.
        plain mode first imports the E-d rows (kaggle/campaigns/bench-v12-audit/
        E-d/score.jsonl) for identical (cell, token key) -- same engine, same
        seeds/budget; those rows keep era=E-d.
  r2_score.py one <mode> <cell> <key> <seed> <out.json>   (worker)

Conditions: BASE = E-d 14B FS (thinking on, archived kernel output in E-d/14b),
CAP = think budget 1024, NT = /no_think (this campaign's kernel output in kernel/).
Enumeration / validity / dedup / topology flags = ed_score.py functions verbatim.
"""
import sys, os, json, time, glob, re, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop",
          REPO + "/kaggle/campaigns/bench-v12-audit/E-d"):
    if p not in sys.path:
        sys.path.insert(0, p)
import ed_score as E                                             # noqa: E402

R2 = REPO + "/kaggle/campaigns/rl-readiness/R2"
ED = E.ED
LIB = E.LIB
BUDGET, SEEDS, PDK = 2500, (1, 2, 3), "bptm45"
ERA = os.environ.get("R2_ERA", "unset")
RAW = os.path.join(os.environ.get("TMPDIR", "/tmp"), "r2-raw")
# (cond label, kernel root, llama-server log, run cond name in manifest)
SOURCES = (("BASE", ED + "/14b", "FS"), ("CAP", R2 + "/kernel", "CAP"),
           ("NT", R2 + "/kernel", "NT"))


def enumerate_edits():
    import proposal as P
    anchor_key = {}
    for c in E.cells():
        anchor_key[c] = E.tokkey(P.round_trip(open(f"{LIB}/{c}/anchor.net").read())["tokens"])
    edits, comps, cand = [], [], {}
    base_tim = E._server_timings(ED + "/14b/llama-server.log")   # E-d order: ZS1 FS1 ZS2 FS2
    for label, root, rcond in SOURCES:
        man = f"{root}/editcap/KERNEL-MANIFEST.json"
        if not os.path.exists(man):
            print("missing", man, file=sys.stderr)
            continue
        manj = json.load(open(man))
        ti = 0
        for run in manj.get("runs", []):
            cond, samp = run["cond"], run["sample"]
            rdir = f"{root}/editcap/{cond}-s{samp}"
            rpath = f"{rdir}/results-B.jsonl"
            rows = [json.loads(l) for l in open(rpath) if l.strip()] \
                if os.path.exists(rpath) else []
            for r in rows:
                cell = r["spec"]
                adj = f"{rdir}/adjudication/{cell}/B"
                cm = {}
                if os.path.exists(adj + "/completion.meta.json"):
                    cm = json.load(open(adj + "/completion.meta.json"))
                tim = None
                if label == "BASE" and r.get("llm_error") is None and ti < len(base_tim):
                    tim = base_tim[ti]          # consumed for EVERY 14b run (ZS too)
                    ti += 1
                if cond != rcond:
                    continue
                u = cm.get("usage") or {}
                r2 = cm.get("r2") or {}
                ph = r2.get("phases") or {}
                if label == "BASE":
                    gpu_ms = tim.get("total_ms") if tim else None
                else:
                    t = r2.get("timings") or {}
                    gpu_ms = (t.get("prompt_ms") or 0) + (t.get("predicted_ms") or 0) \
                        if t else None
                raw = open(adj + "/raw_output.txt", errors="replace").read() \
                    if os.path.exists(adj + "/raw_output.txt") else ""
                nets = sorted(glob.glob(adj + "/edit*.net"),
                              key=lambda p: int(re.search(r"edit(\d+)\.net$", p).group(1)))
                comps.append({
                    "cond": label, "sample": samp, "cell": cell,
                    "finish_reason": cm.get("finish_reason"),
                    "completion_tokens": u.get("completion_tokens"),
                    "reasoning_tokens": u.get("reasoning_tokens"),
                    "answer_tokens": u.get("answer_tokens"),
                    "prompt_tokens": u.get("prompt_tokens"),
                    "content_chars": cm.get("content_chars"),
                    "reasoning_chars": cm.get("reasoning_chars"),
                    "think_stop": ph.get("think_stop"),
                    "think_closed_naturally": ph.get("think_closed_naturally"),
                    "recovered_from_reasoning": cm.get("recovered_from_reasoning"),
                    "llm_error": r.get("llm_error"),
                    "empty_content": (not raw.strip()),
                    "n_edits": len(nets),
                    "gpu_ms": gpu_ms,
                    "client_wall_s": r2.get("client_wall_s")})
                for p in nets:
                    i = int(re.search(r"edit(\d+)\.net$", p).group(1))
                    txt = open(p, errors="replace").read()
                    info = P.round_trip(txt)
                    k = E.tokkey(info["tokens"]) if info["ok"] else None
                    edits.append({"cond": label, "sample": samp, "cell": cell, "edit": i,
                                  "path": os.path.relpath(p, REPO),
                                  "valid": bool(info["ok"]), "error": info.get("error"),
                                  "key": k,
                                  "is_anchor": (k == anchor_key[cell]) if k else False,
                                  "topo": E.topo_flags(txt)})
                    if k and (cell, k) not in cand:
                        cand[(cell, k)] = {"tokens": info["tokens"], "conds": []}
                    if k and label not in cand[(cell, k)]["conds"]:
                        cand[(cell, k)]["conds"].append(label)
    with open(R2 + "/edits.jsonl", "w") as fh:
        for e in edits:
            fh.write(json.dumps(e, default=repr) + "\n")
    with open(R2 + "/completions.jsonl", "w") as fh:
        for c in comps:
            fh.write(json.dumps(c, default=repr) + "\n")
    json.dump({f"{c}|{k}": v for (c, k), v in cand.items()}, open(R2 + "/cand.json.tmp", "w"))
    os.replace(R2 + "/cand.json.tmp", R2 + "/cand.json")
    for lab in ("BASE", "CAP", "NT"):
        ee = [e for e in edits if e["cond"] == lab]
        print(lab, "completions", sum(c["cond"] == lab for c in comps), "edits", len(ee),
              "valid", sum(e["valid"] for e in ee))
    print("unique (cell,tokens)", len(cand))


def _spec_for(mode, cell):
    src = f"{LIB}/{cell}/spec.yaml"
    if mode == "plain":
        return src
    import bench_anchor_prep as PREP
    return PREP.stability_spec(src, out_dir=os.path.join(
        os.environ.get("TMPDIR", "/tmp"), "stab-specs"))


def one(mode, cell, key, seed, out):
    import bench_anchor_prep as PREP, mysolve as MS
    from spec import Spec
    if mode == "inloop":
        assert os.environ.get("STAB_WIDE_INLOOP") == "1"
    else:
        assert not os.environ.get("STAB_WIDE_INLOOP")
    tok = json.load(open(R2 + "/cand.json"))[f"{cell}|{key}"]["tokens"]
    sp = _spec_for(mode, cell)
    spec = Spec.load(sp)
    if mode != "plain":         # S-1 race guard: the loaded spec must be complete
        base = Spec.load(f"{LIB}/{cell}/spec.yaml")
        assert set(spec.constraints) == set(base.constraints) | {"mu_min"}, sp
    seed = int(seed)
    rec = {"mode": mode, "cell": cell, "key": key, "seed": seed, "budget": BUDGET,
           "pdk": PDK, "era": ERA, "n_constraints": len(spec.constraints)}
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
        rows, worst = MS._margins(spec, r.get("metrics") or {})
        m = r.get("metrics") or {}
        rec.update(sizable=True, error=None, feasible=bool(r["feasible"]),
                   worst=(worst[1] if worst else None),
                   binding=(worst[0] if worst else None),
                   margins={n: mg for n, _a, _c, mg, _s in rows},
                   mu_min=m.get("mu_min"), metrics=m, n_evals=r.get("n_evals"),
                   n_sim_fail=r.get("n_sim_fail"), sim_error=r.get("sim_error"),
                   winner_reeval_ungated=r.get("winner_reeval_ungated"))
        for k2 in ("spec_feasible", "mu_min_wide", "k_min_wide", "delta_max_wide",
                   "stab_wide_ok", "stab_points_checked", "stab_winner_replaced",
                   "stab_window", "stab_inloop"):
            if k2 in r:
                rec[k2] = r[k2]
    json.dump(rec, open(out, "w"), default=repr)


def _import_ed_plain(cand, sp):
    """plain mode: copy E-d rows for identical (cell, key) (same engine/seeds)."""
    have = set()
    if os.path.exists(sp):
        for l in open(sp):
            if l.strip():
                j = json.loads(l)
                have.add((j["cell"], j["key"], j["seed"]))
    n = 0
    with open(sp, "a") as fh:
        for l in open(ED + "/score.jsonl"):
            if not l.strip():
                continue
            j = json.loads(l)
            ck = f"{j['cell']}|{j['key']}"
            if ck in cand and (j["cell"], j["key"], j["seed"]) not in have:
                j["mode"], j["imported_from"] = "plain", "E-d/score.jsonl"
                fh.write(json.dumps(j) + "\n")
                have.add((j["cell"], j["key"], j["seed"]))
                n += 1
    print("imported", n, "E-d plain rows")


def run(mode, nproc=4, conds=None):
    os.makedirs(RAW, exist_ok=True)
    cand = json.load(open(R2 + "/cand.json"))
    if conds:
        cand = {ck: v for ck, v in cand.items() if set(v["conds"]) & set(conds)}
    lab = E.labels()
    sp = R2 + f"/score-{mode}.jsonl"
    if mode == "plain":
        _import_ed_plain(cand, sp)
    done = set()
    if os.path.exists(sp):
        for l in open(sp):
            if l.strip():
                j = json.loads(l)
                done.add((j["cell"], j["key"], j["seed"]))
    order = sorted(cand, key=lambda ck: (lab[ck.split("|")[0]]["retrieval"], ck))
    jobs = [(ck.split("|")[0], ck.split("|")[1], s) for s in SEEDS for ck in order
            if (ck.split("|")[0], ck.split("|")[1], s) not in done]
    print(f"[{mode}] {len(jobs)} jobs to run ({len(done)} done)", flush=True)
    env = dict(os.environ)
    env.pop("STAB_WIDE_INLOOP", None)
    if mode == "inloop":
        env["STAB_WIDE_INLOOP"] = "1"
    t0 = time.time()

    def work(job):
        cell, key, seed = job
        out = f"{RAW}/{mode}__{cell}__{key}__s{seed}.json"
        errp = out + ".err"
        with open(errp, "w") as ef:
            subprocess.run([sys.executable, __file__, "one", mode, cell, key, str(seed), out],
                           stdout=subprocess.DEVNULL, stderr=ef, env=env)
        if os.path.exists(out):
            return json.load(open(out))
        return {"mode": mode, "cell": cell, "key": key, "seed": seed, "era": ERA,
                "crashed": True, "feasible": False, "sizable": None,
                "stderr_tail": open(errp).read()[-600:]}

    n = 0
    with ThreadPoolExecutor(max_workers=int(nproc)) as ex, open(sp, "a") as fh:
        futs = [ex.submit(work, j) for j in jobs]
        for f in as_completed(futs):
            rec = f.result()
            fh.write(json.dumps(rec, default=repr) + "\n")
            fh.flush()
            n += 1
            el = (time.time() - t0) / 60
            print(f"[{mode} {n}/{len(jobs)} {el:.1f}min eta {el / n * (len(jobs) - n):.0f}min] "
                  f"{rec['cell']} {rec['key']} s{rec['seed']} feas={rec.get('feasible')} "
                  f"worst={rec.get('binding')},{rec.get('worst')} secs={rec.get('secs')}",
                  flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "enumerate":
        enumerate_edits()
    elif a[0] == "run":
        run(a[1], int(a[2]) if len(a) > 2 else 4,
            a[3].split(",") if len(a) > 3 else None)
    elif a[0] == "one":
        one(*a[1:6])

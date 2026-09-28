"""rl-readiness R1 -- cheap-reward fidelity (kaggle/PREREG-RL-READINESS.md, R1).

usage (always through envrun.sh: crenv vars + TMPDIR=/tmp/cr-7cd7ffc3-r1):
  r1_drv.py sample              -> sample.json (population, main sample, completion
                                   subset, stability subsample; seeded, deterministic)
  r1_drv.py run [nproc]         -> every job not yet in results.jsonl, appended one
                                   line per finished call (resumable checkpoint)
  r1_drv.py one <uid> <mode> <seed> <budget> <out.json>   (worker, own subprocess)
  (tables/verdict: r1_analyze.py)

Engine (identical to E-a/E-c/E-d): bench_anchor_prep.smoke_run(tokens, spec, seed,
budget, "bptm45"); feasible = result["feasible"]; worst margin = mysolve._margins
(normalized, vs the spec that was sized against).
  mode "lib"  : spec = kaggle/editcap-lib-v12-45nm/<cell>/spec.yaml (no stability gate)
  mode "stab" : spec = bench_anchor_prep.stability_spec(lib spec) (mu_min >= 1 in-band
                + the opt-in wide 0.1-20 GHz gate, GATE-ONLY: STAB_WIDE_INLOOP is never
                set -- forced unset in the worker env).
Unit of analysis = (cell, exact token sequence) ("uid" = cell|sha1(json(tokens))[:16],
the E-d key); E-c single edits and E-d Qwen edits are merged on it.
"""
import sys, os, json, time, hashlib, random, subprocess, threading, queue, collections

REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop"):
    if p not in sys.path:
        sys.path.insert(0, p)
R1 = REPO + "/kaggle/campaigns/rl-readiness/R1"
AUD = REPO + "/kaggle/campaigns/bench-v12-audit"
LIB = REPO + "/kaggle/editcap-lib-v12-45nm"
PDK = "bptm45"
SAMPLE = R1 + "/sample.json"
RES = R1 + "/results.jsonl"
RAW = os.path.join(os.environ.get("TMPDIR", "/tmp"), "r1-raw")
STABDIR = os.path.join(os.environ.get("TMPDIR", "/tmp"), "stab-specs")
SEED = 20260928
TIMEOUT_S = 1800
LOAD_HI, NPROC_LO = 22.0, 4          # caller rule: load > 22 -> 4 processes


def tokkey(tokens):
    return hashlib.sha1(json.dumps(list(tokens)).encode()).hexdigest()[:16]


def _w(x):
    return x[1] if isinstance(x, list) else x


# ------------------------------------------------------------------ population
def population():
    """{uid: unit} with every recorded 2500-eval verdict of E-c and E-d."""
    units = {}
    ecc = {c["cid"]: c for c in map(json.loads, open(AUD + "/E-c/candidates.jsonl"))}
    for r in map(json.loads, open(AUD + "/E-c/results.jsonl")):
        c = ecc[r["cid"]]
        k = tokkey(c["tokens"])
        uid = f"{r['cell']}|{k}"
        u = units.setdefault(uid, {"uid": uid, "cell": r["cell"], "key": k,
                                   "tokens": c["tokens"], "src": set(), "full": {}})
        u["src"].add("ec:" + c["cid"] + ":" + c["desc"])
        s = r["seed"]
        # E-c seed 1 has a screen and (for feasible ones) a bit-identical confirm
        if s not in u["full"] or r.get("phase") == "screen":
            u["full"][s] = {"feasible": bool(r["feasible"]), "worst": _w(r.get("worst")),
                            "sizable": r.get("sizable"),
                            "mu_min": (r.get("metrics") or {}).get("mu_min"),
                            "secs": r.get("secs"), "from": "E-c"}
    edc = json.load(open(AUD + "/E-d/cand.json"))
    for r in map(json.loads, open(AUD + "/E-d/score.jsonl")):
        uid = f"{r['cell']}|{r['key']}"
        u = units.setdefault(uid, {"uid": uid, "cell": r["cell"], "key": r["key"],
                                   "tokens": edc[uid], "src": set(), "full": {}})
        u["src"].add("ed")
        rec = {"feasible": bool(r["feasible"]), "worst": r.get("worst"),
               "sizable": r.get("sizable"), "mu_min": r.get("mu_min"),
               "secs": r.get("secs"), "from": "E-d"}
        if r["seed"] in u["full"] and u["full"][r["seed"]]["feasible"] != rec["feasible"]:
            u.setdefault("conflict", []).append(r["seed"])
        u["full"].setdefault(r["seed"], rec)      # E-c first (seed-1 identical engine)
    for u in units.values():
        u["src"] = sorted(u["src"])
        u["band"] = "wb" if "-wb-" in u["cell"] else "nb"
        f1 = u["full"].get(1, {})
        u["sizable"] = bool(f1.get("sizable"))
        u["w1"] = f1.get("worst")
        u["any_feas"] = any(v["feasible"] for v in u["full"].values())
        u["seeds_known"] = sorted(u["full"])
    return units


def wbin(w):
    if w is None:
        return "none"
    if w >= 0:
        return "feas"
    if w >= -0.1:
        return "A[-0.1,0)"
    if w >= -0.3:
        return "B[-0.3,-0.1)"
    if w >= -1:
        return "C[-1,-0.3)"
    return "D(<-1)"


def _strat(rng, pool, n, key):
    """Draw n from pool, balanced over key(u) (round-robin over strata)."""
    by = collections.defaultdict(list)
    for u in sorted(pool, key=lambda u: u["uid"]):
        by[key(u)].append(u)
    for v in by.values():
        rng.shuffle(v)
    out, ks = [], sorted(by)
    while len(out) < n and any(by[k] for k in ks):
        for k in ks:
            if by[k] and len(out) < n:
                out.append(by[k].pop())
    return out


def make_sample():
    rng = random.Random(SEED)
    U = population()
    siz = [u for u in U.values() if u["sizable"]]
    pos = [u for u in siz if u["any_feas"]]
    neg = [u for u in siz if not u["any_feas"]]
    neg_ed = [u for u in neg if "ed" in u["src"]]                 # Qwen edits: census
    neg_ec = [u for u in neg if "ed" not in u["src"]]
    a_ec = [u for u in neg_ec if wbin(u["w1"]) == "A[-0.1,0)"]    # near-miss: census
    target_neg = 3 * len(pos) + 30
    rest = target_neg - len(neg_ed) - len(a_ec)
    alloc = {"B[-0.3,-0.1)": round(rest * 0.40), "C[-1,-0.3)": round(rest * 0.35)}
    alloc["D(<-1)"] = rest - sum(alloc.values())
    drawn = []
    for b, n in alloc.items():
        drawn += _strat(rng, [u for u in neg_ec if wbin(u["w1"]) == b], n,
                        key=lambda u: u["cell"])
    main = pos + neg_ed + a_ec + drawn
    # completion (seeds 2,3 x 2500, lib) for sampled E-c-only negatives: all near-miss
    # A + 20 random from each of B, C, D (checks the "far => infeasible" assumption)
    comp = list(a_ec)
    for b in ("B[-0.3,-0.1)", "C[-1,-0.3)", "D(<-1)"):
        comp += _strat(rng, [u for u in drawn if wbin(u["w1"]) == b], 20,
                       key=lambda u: u["cell"])
    comp = [u for u in comp if u["seeds_known"] == [1]]
    # stability subsample: 60 full-feasible (in-band mu>=1 at any seed first, then
    # balanced by cell; nb included) + 60 infeasible (wb near-miss, nb, E-d, far)
    def mu_any(u):
        return max((v.get("mu_min") or -9) for v in u["full"].values())
    ps = sorted(pos, key=lambda u: u["uid"])
    p_stable = [u for u in ps if mu_any(u) >= 1.0]
    p_nb = [u for u in ps if u["band"] == "nb" and u not in p_stable]
    st_pos = list(p_stable)[:44] + _strat(rng, p_nb, 6, key=lambda u: u["cell"])
    st_pos += _strat(rng, [u for u in ps if u not in st_pos], 60 - len(st_pos),
                     key=lambda u: u["cell"])
    st_neg = (_strat(rng, [u for u in a_ec if u["band"] == "wb"], 25, key=lambda u: u["cell"])
              + _strat(rng, [u for u in drawn if u["band"] == "nb"
                             and wbin(u["w1"]) == "B[-0.3,-0.1)"], 10, key=lambda u: u["cell"])
              + _strat(rng, [u for u in neg_ed if wbin(u["w1"]) in ("A[-0.1,0)", "B[-0.3,-0.1)")],
                       15, key=lambda u: u["cell"])
              + _strat(rng, [u for u in drawn if wbin(u["w1"]) in ("C[-1,-0.3)", "D(<-1)")],
                       10, key=lambda u: u["cell"]))
    stab = st_pos + st_neg

    def slim(u):
        return {k: u[k] for k in ("uid", "cell", "key", "band", "src", "w1", "any_feas",
                                  "seeds_known", "tokens", "full")}
    out = {"seed": SEED,
           "population": {"units": len(U), "sizable": len(siz), "pos": len(pos),
                          "neg": len(neg), "neg_ed": len(neg_ed), "neg_ec": len(neg_ec),
                          "neg_ec_A": len(a_ec), "conflicts": [u["uid"] for u in U.values()
                                                              if u.get("conflict")]},
           "alloc_ec_far": alloc,
           "main": [u["uid"] for u in main],
           "completion": [u["uid"] for u in comp],
           "stab": [u["uid"] for u in stab],
           "units": {u["uid"]: slim(u) for u in main + stab}}
    json.dump(out, open(SAMPLE, "w"))
    c = collections.Counter((u["band"], "pos" if u["any_feas"] else "neg", wbin(u["w1"]),
                             "ed" if "ed" in u["src"] else "ec") for u in main)
    for k in sorted(c):
        print(k, c[k])
    print("main", len(main), "pos", len(pos), "neg", len(main) - len(pos),
          "completion", len(comp), "stab", len(stab), "(pos", len(st_pos), ")")
    print(out["population"])


def topup(n):
    """Added after the completion runs relabelled ~20 E-c near-miss negatives as
    positives (feasible at seed 2/3), which pushed neg/pos below the pre-registered 3x:
    draw n more E-c-only far negatives (bins B/C/D, 40/35/25 split, balanced by cell,
    seeded) not yet in the sample; appended to main (cheap levels only; labelled on the
    seed-1 verdict like the other uncompleted far negatives)."""
    rng = random.Random(SEED + 1)
    S = json.load(open(SAMPLE))
    if S.get("topup"):
        print("topup already drawn:", len(S["topup"]))
        return
    U = population()
    have = set(S["main"])
    pool = [u for u in U.values() if u["sizable"] and not u["any_feas"]
            and "ed" not in u["src"] and u["uid"] not in have]
    alloc = {"B[-0.3,-0.1)": round(n * 0.40), "C[-1,-0.3)": round(n * 0.35)}
    alloc["D(<-1)"] = n - sum(alloc.values())
    add = []
    for b, k in alloc.items():
        add += _strat(rng, [u for u in pool if wbin(u["w1"]) == b], k,
                      key=lambda u: u["cell"])
    for u in add:
        S["units"][u["uid"]] = {k: u[k] for k in ("uid", "cell", "key", "band", "src", "w1",
                                                  "any_feas", "seeds_known", "tokens", "full")}
    S["topup"] = [u["uid"] for u in add]
    S["topup_alloc"] = alloc
    S["main"] = S["main"] + S["topup"]
    tmp = SAMPLE + ".tmp"
    json.dump(S, open(tmp, "w"))
    os.replace(tmp, SAMPLE)
    print("topup", len(add), alloc)


# ------------------------------------------------------------------ jobs
def jobs():
    S = json.load(open(SAMPLE))
    J = []
    for b in (600, 1200):
        J += [(uid, "lib", 1, b) for uid in S["main"]]
    J += [(uid, "lib", s, 2500) for uid in S["completion"] for s in (2, 3)]
    for b, seeds in ((600, (1,)), (1200, (1,)), (2500, (1, 2, 3))):
        J += [(uid, "stab", s, b) for uid in S["stab"] for s in seeds]
    # added mid-run (orchestrator 2026-09-28: final verifier = gate + STAB_WIDE_INLOOP=1,
    # committed f3677bb08): the same stability subsample under the final config
    for b, seeds in ((600, (1,)), (1200, (1,)), (2500, (1, 2, 3))):
        J += [(uid, "stabil", s, b) for uid in S["stab"] for s in seeds]
    return J


def jkey(uid, mode, seed, budget):
    return f"{uid}|{mode}|s{seed}|b{budget}"


def spec_path(cell, mode):
    src = f"{LIB}/{cell}/spec.yaml"
    if mode == "lib":
        return src
    mp = os.path.join(STABDIR, "map.json")
    m = json.load(open(mp)) if os.path.exists(mp) else {}
    if cell not in m:                    # only reached from run() (single process)
        import bench_anchor_prep as PREP
        m[cell] = PREP.stability_spec(src, out_dir=os.path.join(STABDIR, cell))
        json.dump(m, open(mp, "w"))
    return m[cell]


def one(uid, mode, seed, budget, out):
    if mode == "stabil":
        os.environ["STAB_WIDE_INLOOP"] = "1"          # final verifier (S-1)
    else:
        os.environ.pop("STAB_WIDE_INLOOP", None)      # lib / gate-only
    import bench_anchor_prep as PREP, mysolve as MS
    from spec import Spec
    S = json.load(open(SAMPLE))
    u = S["units"][uid]
    seed, budget = int(seed), int(budget)
    sp = spec_path(u["cell"], mode)
    rec = {"uid": uid, "cell": u["cell"], "mode": mode, "seed": seed, "budget": budget,
           "pdk": PDK, "era": os.environ.get("R1_ERA", "unknown"),
           "load_start": os.getloadavg()[0]}
    t0 = time.time()
    try:
        r = PREP.smoke_run(list(u["tokens"]), sp, seed, budget, PDK)
        err = None
    except Exception as e:                                    # noqa: BLE001
        r, err = None, repr(e)
    rec["secs"] = round(time.time() - t0, 2)
    rec["load_end"] = os.getloadavg()[0]
    if r is None:
        rec.update(sizable=(False if err is None else None), error=err, feasible=False,
                   worst=None, binding=None)
    else:
        m = r.get("metrics") or {}
        rows, worst = MS._margins(Spec.load(sp), m)
        rec.update(sizable=True, error=None, feasible=bool(r["feasible"]),
                   worst=(worst[1] if worst else None),
                   binding=(worst[0] if worst else None),
                   margins={n: mg for n, _a, _c, mg, _s in rows},
                   mu_min=m.get("mu_min"), n_evals=r.get("n_evals"),
                   n_sim_fail=r.get("n_sim_fail"),
                   metrics={k: v for k, v in m.items()
                            if isinstance(v, (int, float, str, bool)) or v is None})
        for k in ("spec_feasible", "mu_min_wide", "k_min_wide", "stab_wide_ok",
                  "stab_points_checked", "stab_winner_replaced", "stab_inloop"):
            if k in r:
                rec[k] = r[k]
    json.dump(rec, open(out, "w"), default=repr)


def run(nproc=6):
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(STABDIR, exist_ok=True)
    S = json.load(open(SAMPLE))
    for cell in sorted({S["units"][u]["cell"] for u in S["stab"]}):
        spec_path(cell, "stab")                  # pre-write (no worker races)
    done = set()
    if os.path.exists(RES):
        for l in open(RES):
            if l.strip():
                j = json.loads(l)
                if not j.get("crashed"):
                    done.add(jkey(j["uid"], j["mode"], j["seed"], j["budget"]))
    J = [j for j in jobs() if jkey(*j) not in done]
    print(f"{len(J)} jobs to run ({len(done)} done)", flush=True)
    q = queue.Queue()
    for j in J:
        q.put(j)
    lock = threading.Lock()
    t0 = time.time()
    cnt = [0]
    fh = open(RES, "a")

    def worker(slot):
        while True:
            # caller rule: <= 6 processes; if box load > 22, only 4
            while slot >= NPROC_LO and os.getloadavg()[0] > LOAD_HI:
                time.sleep(30)
            try:
                uid, mode, seed, budget = q.get_nowait()
            except queue.Empty:
                return
            safe = uid.replace("|", "__")
            out = f"{RAW}/{safe}__{mode}__s{seed}__b{budget}.json"
            if os.path.exists(out):
                os.remove(out)
            env = dict(os.environ)
            env.pop("STAB_WIDE_INLOOP", None)
            try:
                subprocess.run([sys.executable, __file__, "one", uid, mode, str(seed),
                                str(budget), out], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=TIMEOUT_S, env=env)
            except subprocess.TimeoutExpired:
                pass
            if os.path.exists(out):
                rec = json.load(open(out))
            else:
                rec = {"uid": uid, "mode": mode, "seed": seed, "budget": budget,
                       "crashed": True, "feasible": False}
            rec["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            with lock:
                fh.write(json.dumps(rec, default=repr) + "\n")
                fh.flush()
                cnt[0] += 1
                el = (time.time() - t0) / 60
                n = cnt[0]
                print(f"[{n}/{len(J)} {el:.1f}min eta {el / n * (len(J) - n):.0f}min "
                      f"load {os.getloadavg()[0]:.1f}] {mode} b{budget} s{seed} {uid} "
                      f"feas={rec.get('feasible')} worst={rec.get('worst')} "
                      f"secs={rec.get('secs')}", flush=True)

    th = [threading.Thread(target=worker, args=(i,)) for i in range(int(nproc))]
    for t in th:
        t.start()
    for t in th:
        t.join()
    fh.close()


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "sample":
        make_sample()
    elif a[0] == "topup":
        topup(int(a[1]))
    elif a[0] == "run":
        run(int(a[1]) if len(a) > 1 else 6)
    elif a[0] == "one":
        one(*a[1:6])

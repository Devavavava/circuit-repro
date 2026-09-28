"""stability-gate test driver (bench_anchor_prep.smoke_run opt-in wide gate).

usage:
  stab_drv.py equiv  <budget>                         old(HEAD~ smoke_run) vs new, no mu_min
  stab_drv.py jobs   <regress|negctl|tpl|anchors>     one job per line
  stab_drv.py run    <exp> <cell> <cand> <specmode> <seed> <rawdir>
  stab_drv.py collect <rawdir> <out.json>

cand     : template | lna-a1..a5 family name | ec:<E-c cid>
specmode : lib  = the untouched library spec (no mu_min -> gate OFF)
           stab = bench_anchor_prep.stability_spec(lib) (adds mu_min >= 1 -> gate ON)
Engine: bench_anchor_prep.smoke_run(tokens, spec, seed, 2500, "bptm45") -- the
same call E-a/E-b/E-c made.
"""
import sys, os, json, time
REPO = os.environ.get("CR_REPO",
                      "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180")
for p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop"):
    sys.path.insert(0, p)

LIB = REPO + "/kaggle/editcap-lib-v12-45nm"
TPL = REPO + "/kaggle/claude-solutions/templates/"
EC = REPO + "/kaggle/campaigns/bench-v12-audit/E-c/candidates.jsonl"
BUDGET, SEEDS, PDK = 2500, (1, 2, 3), "bptm45"
NEG_CID = "d0be8b9bc6d6:032"          # nb anchor (a5 CG) + `add L VIN1-n1`
ANCH = ("lna-a1-inddegen-cascode", "lna-a2-current-reuse",
        "lna-a3-shunt-feedback", "lna-a4-twostage", "lna-a5-commongate")
# regression rows: (exp, cell, cand, seed, source file of the recorded row)
REGRESS = [
    ("E-a", "v12-wb-s11n10-g10-b0530", "template", 1),
    ("E-b", "v12-wb-s11n10-g10-b0824", "lna-a1-inddegen-cascode", 1),
    ("E-b", "v12-nb-f15-g16", "lna-a1-inddegen-cascode", 1),
    ("E-c", "v12-nb-f15-g16", "ec:" + NEG_CID, 1),
]


def cells():
    return sorted(d for d in os.listdir(LIB) if d.startswith("v12-"))


def tokens_for(cell, cand):
    import proposal as P
    if cand == "template":
        net = TPL + ("wideband_shunt_feedback.net" if "-wb-" in cell
                     else "narrowband_cascode_tank.net")
        return P.round_trip(open(net).read())["tokens"]
    if cand.startswith("ec:"):
        cid = cand[3:]
        for ln in open(EC):
            c = json.loads(ln)
            if c["cid"] == cid:
                return c["tokens"]
        raise KeyError(cid)
    m = json.load(open(REPO + "/kaggle/bench-anchors/MANIFEST.json"))
    tf = m["classes"]["lna"]["families"][cand]["tokens_file"]
    return json.load(open(REPO + "/" + tf))


def spec_for(cell, mode):
    import bench_anchor_prep as PREP
    src = f"{LIB}/{cell}/spec.yaml"
    return src if mode == "lib" else PREP.stability_spec(src)


def jobs(kind):
    if kind == "regress":
        return [f"regress {c} {cand} lib {s}" for _e, c, cand, s in REGRESS]
    if kind == "negctl":
        return [f"negctl v12-nb-f15-g16 ec:{NEG_CID} {m} {s}"
                for m in ("lib", "stab") for s in SEEDS]
    if kind == "tpl":
        return [f"tpl {c} template stab {s}" for c in cells() for s in SEEDS]
    if kind == "anchors":
        return [f"anchors {c} {a} stab {s}" for c in cells() if "-nb-" in c
                for a in ANCH for s in SEEDS]
    raise SystemExit(kind)


def run(exp, cell, cand, mode, seed, rawdir):
    import bench_anchor_prep as PREP, mysolve as MS
    from spec import Spec
    seed = int(seed)
    # time every wide-stability sim the gate makes (wrapper, no behavior change)
    tstat = {"n": 0, "secs": 0.0}
    _orig = PREP.wide_stability

    def _timed(*a, **k):
        t = time.time()
        try:
            return _orig(*a, **k)
        finally:
            tstat["n"] += 1
            tstat["secs"] += time.time() - t
    PREP.wide_stability = _timed
    tok = tokens_for(cell, cand)
    sp = spec_for(cell, mode)
    t0 = time.time()
    r = PREP.smoke_run(list(tok), sp, seed, BUDGET, PDK)
    rec = {"exp": exp, "cell": cell, "cand": cand, "specmode": mode, "seed": seed,
           "budget": BUDGET, "pdk": PDK, "spec": os.path.basename(sp),
           "era": os.environ.get("AUDIT_ERA", "unknown"),
           "secs": round(time.time() - t0, 1),
           "wide_sims": tstat["n"], "wide_secs": round(tstat["secs"], 2)}
    if r is None:
        rec.update(not_sizable=True, feasible=False)
    else:
        rows, worst = MS._margins(Spec.load(sp), r.get("metrics") or {})
        m = r.get("metrics") or {}
        rec.update(not_sizable=False, feasible=bool(r["feasible"]),
                   spec_feasible=r.get("spec_feasible"),
                   mu_min=m.get("mu_min"), k_min=m.get("k_min"),
                   mu_min_wide=r.get("mu_min_wide"), k_min_wide=r.get("k_min_wide"),
                   delta_max_wide=r.get("delta_max_wide"),
                   stab_wide_ok=r.get("stab_wide_ok"),
                   stab_points_checked=r.get("stab_points_checked"),
                   stab_winner_replaced=r.get("stab_winner_replaced"),
                   worst=worst, margins={n: mg for n, _a, _c, mg, _s in rows},
                   result=r)
    fn = f"{rawdir}/{exp}__{cell}__{cand.replace(':', '_')}__{mode}__s{seed}.json"
    json.dump(rec, open(fn, "w"), indent=1, default=repr)
    print(exp, cell, cand, mode, seed, "feas=", rec["feasible"],
          "spec_feas=", rec.get("spec_feasible"), "mu=", rec.get("mu_min"),
          "mu_wide=", rec.get("mu_min_wide"), "chk=", rec.get("stab_points_checked"),
          "repl=", rec.get("stab_winner_replaced"), "secs=", rec["secs"], flush=True)


def equiv(budget):
    """Old smoke_run (HEAD copy saved at $TMPDIR/old_bap.py) vs new, lib specs
    (no mu_min): full result dicts must be identical (json text equality)."""
    import importlib.util
    import bench_anchor_prep as NEW
    p = os.path.join(os.environ["TMPDIR"], "old_bap.py")
    spec_ = importlib.util.spec_from_file_location("old_bap", p)
    OLD = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(OLD)
    out = []
    for _e, cell, cand, seed in REGRESS:
        tok = tokens_for(cell, cand)
        sp = f"{LIB}/{cell}/spec.yaml"
        a = OLD.smoke_run(list(tok), sp, seed, int(budget), PDK)
        b = NEW.smoke_run(list(tok), sp, seed, int(budget), PDK)
        ja, jb = (json.dumps(a, sort_keys=True, default=repr),
                  json.dumps(b, sort_keys=True, default=repr))
        out.append({"cell": cell, "cand": cand, "seed": seed, "budget": int(budget),
                    "identical": ja == jb, "keys_old": sorted(a or {}),
                    "keys_new": sorted(b or {}), "feasible": (b or {}).get("feasible")})
        print(cell, cand, "identical=", ja == jb, flush=True)
    return out


def collect(rawdir, out):
    rows = [json.load(open(os.path.join(rawdir, f)))
            for f in sorted(os.listdir(rawdir)) if f.endswith(".json")]
    json.dump({"n_rows": len(rows), "rows": rows}, open(out, "w"), indent=1,
              default=repr)
    print("collected", len(rows))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "jobs":
        print("\n".join(jobs(a[1])))
    elif a[0] == "run":
        run(*a[1:7])
    elif a[0] == "equiv":
        res = equiv(a[1])
        json.dump(res, open(a[2], "w"), indent=1)
    elif a[0] == "collect":
        collect(a[1], a[2])

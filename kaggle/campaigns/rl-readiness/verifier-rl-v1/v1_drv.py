"""verifier rl-v1 test driver (kaggle/VERIFIER-RL-V1.md).

usage:
  v1_drv.py jobs <reg|diff|loop>                   one job per line
  v1_drv.py run <tag> <cell> <cand> <mode> <seed> <rawdir>
  v1_drv.py collect <rawdir> <out.json>

cand : template | anchor:<family> | ec:<E-c cid> | net:<R4 mutation name>
mode : lib      library spec, NO profile, no flags        (historical smoke_run)
       gate     stability_spec(lib), no flags              (stability-gate config)
       inloop   stability_spec(lib) + STAB_WIDE_INLOOP=1   (S-1 config)
       rlv1     rl_v1_spec(lib) + smoke_run(..., profile="rl-v1")   THE rl-v1 verifier
       rlv1env  rl_v1_spec(lib) + env VERIFIER_PROFILE=rl-v1 (no kwarg)
Engine: bench_anchor_prep.smoke_run(tokens, spec, seed, 2500, "bptm45").
Every verifier env var is cleared before a run, so a mode is exactly its
definition. SZ.make_objective is wrapped for CAPTURE only (the objective and
evaluate are returned unchanged) so the final winner's body/params are stored.
"""
import sys, os, json, time
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop"):
    sys.path.insert(0, p)

LIB = REPO + "/kaggle/editcap-lib-v12-45nm"
TPL = REPO + "/kaggle/claude-solutions/templates/"
AUD = REPO + "/kaggle/campaigns/bench-v12-audit/"
R4 = REPO + "/kaggle/campaigns/rl-readiness/R4/"
BUDGET, PDK, SEEDS = 2500, "bptm45", (1, 2, 3)
S1_SOLVED = ("v12-wb-s11n10-g10-b0824", "v12-wb-s11n11-g10-b0824",
             "v12-wb-s11n8-g10-b0530", "v12-wb-s11n9-g10-b0530")
MUT_CELLS = {"wb": ("v12-wb-s11n10-g10-b0824", "v12-wb-s11n8-g10-b0530"),
             "nb": ("v12-nb-f15-g16", "v12-nb-f24-g12")}


def cells():
    return sorted(d for d in os.listdir(LIB) if d.startswith("v12-"))


def tokens_for(cell, cand):
    import proposal as P
    if cand == "template":
        net = TPL + ("wideband_shunt_feedback.net" if "-wb-" in cell
                     else "narrowband_cascode_tank.net")
        return P.round_trip(open(net).read())["tokens"]
    if cand.startswith("ec:"):
        for ln in open(AUD + "E-c/candidates.jsonl"):
            c = json.loads(ln)
            if c["cid"] == cand[3:]:
                return c["tokens"]
        raise KeyError(cand)
    if cand.startswith("anchor:"):
        m = json.load(open(REPO + "/kaggle/bench-anchors/MANIFEST.json"))
        return json.load(open(REPO + "/" + m["classes"]["lna"]["families"][cand[7:]]["tokens_file"]))
    if cand.startswith("net:"):
        rt = P.round_trip(json.load(open(R4 + "mutations.json"))[cand[4:]])
        if not rt["ok"]:
            raise RuntimeError(rt["error"])
        return rt["tokens"]
    raise KeyError(cand)


def spec_for(cell, mode):
    import bench_anchor_prep as PREP
    src = f"{LIB}/{cell}/spec.yaml"
    od = os.path.join(os.environ.get("TMPDIR", "/tmp"), "specs", str(os.getpid()))
    if mode == "lib":
        return src
    if mode in ("gate", "inloop"):
        return PREP.stability_spec(src, out_dir=od)
    return PREP.rl_v1_spec(src, out_dir=od)


def s1_ec_picks():
    """The S-1 E-c edits (minus `add R n1-n2` == template) on the 4 S-1-solved cells."""
    s1 = json.load(open(AUD + "S-1-stab-inloop/results.json"))
    return {c: [p for p in s1["ec_picks"][c] if p["desc"] != "add R n1-n2"]
            for c in S1_SOLVED}


def run(tag, cell, cand, mode, seed, rawdir):
    fn = f"{rawdir}/{tag}__{cell}__{cand.replace(':', '_')}__{mode}__s{seed}.json"
    if os.path.exists(fn):
        print("skip (exists)", fn)
        return
    import bench_anchor_prep as PREP
    for k in PREP.VERIFIER_FLAGS + ("VERIFIER_PROFILE",):
        os.environ.pop(k, None)
    kw = {}
    if mode == "inloop":
        os.environ["STAB_WIDE_INLOOP"] = "1"
    elif mode == "rlv1":
        kw = {"profile": "rl-v1"}
    elif mode == "rlv1env":
        os.environ["VERIFIER_PROFILE"] = "rl-v1"
    import mysolve as MS
    from spec import Spec
    cap = {"evals": []}
    _mk = PREP.SZ.make_objective

    def _cap_mk(body, spec, sizable, fixed, **k2):
        obj, names, decode, evaluate = _mk(body, spec, sizable, fixed, **k2)
        cap.update(body=body, sizable=dict(sizable), names=list(names), decode=decode)

        def ev(x, *a, **k):
            cap["evals"].append([float(v) for v in x])
            return evaluate(x, *a, **k)
        return obj, names, decode, ev
    PREP.SZ.make_objective = _cap_mk
    seed = int(seed)
    tok = tokens_for(cell, cand)
    sp = spec_for(cell, mode)
    t0 = time.time()
    r = PREP.smoke_run(list(tok), sp, seed, BUDGET, PDK, **kw)
    secs = time.time() - t0
    rec = {"tag": tag, "cell": cell, "cand": cand, "mode": mode, "seed": seed,
           "budget": BUDGET, "pdk": PDK, "spec": os.path.basename(sp),
           "secs": round(secs, 1), "tokens": list(tok), "result": r}
    if r is not None:
        spec = Spec.load(sp)
        rows, worst = MS._margins(spec, r.get("metrics") or {})
        rec["worst"] = worst
        rec["spec_violations"] = spec.feasible(r.get("metrics") or {})[1] if r.get("metrics") else None
        if "decode" in cap and cap["evals"]:
            rep = r.get("stab_replacement")
            x_win = rep["x"] if (r.get("stab_winner_replaced") and rep) else cap["evals"][0]
            rec.update(body=cap["body"], sizable=cap["sizable"],
                       params_win=cap["decode"](x_win))
    json.dump(rec, open(fn, "w"), indent=1, default=repr)
    r = r or {}
    print(tag, cell, cand, mode, seed, "feas=", r.get("feasible"),
          "spec_feas=", r.get("spec_feasible"), "mu_wide=", r.get("mu_min_wide"),
          "why=", r.get("infeasible_reason"), "inert=", r.get("n_inert_devices"),
          "secs=", rec["secs"], flush=True)


def jobs(kind):
    out = []
    if kind == "reg":       # (a) no profile vs RECORDED rows; + profile env/kwarg equivalence
        out += ["reg v12-nb-f15-g12 template lib 1",                       # E-a row
                "reg v12-wb-s11n10-g10-b0824 template lib 1",              # E-a row (NF-gated wb)
                "reg v12-wb-s11n10-g10-b0530 ec:72945e70a2a1:131 lib 1",   # E-c row
                "reg v12-nb-f15-g14 template gate 1",                      # stability-gate row
                "reg v12-wb-s11n10-g10-b0824 template inloop 1",           # S-1 row
                "reg v12-nb-f15-g16 template rlv1env 1"]                   # == diff rlv1 kwarg
    elif kind == "diff":    # (b) difficulty re-check under rl-v1
        for c in cells():
            if "-nb-" in c:
                out += [f"diff {c} {cand} rlv1 {s}" for cand in
                        ("template", "anchor:lna-a1-inddegen-cascode") for s in SEEDS]
            else:
                out += [f"diff {c} template rlv1 {s}" for s in SEEDS]
        for c, ps in s1_ec_picks().items():
            out += [f"diff {c} ec:{p['cid']} rlv1 {s}" for p in ps for s in SEEDS]
    elif kind == "loop":    # (c) R4 junk add-on mutations, 2 cells per band, seed 1
        for name in json.load(open(R4 + "mutations.json")):
            for c in MUT_CELLS[name[:2]]:
                out.append(f"loop {c} net:{name} rlv1 1")
    else:
        raise SystemExit(kind)
    return out


def collect(rawdir, out):
    rows = [json.load(open(os.path.join(rawdir, f)))
            for f in sorted(os.listdir(rawdir)) if f.endswith(".json")]
    json.dump({"n_rows": len(rows), "s1_ec_picks": s1_ec_picks(), "rows": rows},
              open(out, "w"), indent=1, default=repr)
    print("collected", len(rows))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "jobs":
        print("\n".join(jobs(a[1])))
    elif a[0] == "run":
        run(*a[1:7])
    elif a[0] == "collect":
        collect(a[1], a[2])

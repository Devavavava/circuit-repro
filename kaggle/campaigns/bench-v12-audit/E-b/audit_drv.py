"""bench-v12-audit E-a / E-b driver (PREREG-BENCH-V12-AUDIT.md).

usage:
  audit_drv.py jobs <E-a|E-b>                       -> prints one job per line
  audit_drv.py run  <exp> <cell> <cand> <delta> <seed> <rawdir>
  audit_drv.py collect <exp> <rawdir> <out.json>

cand: "template" (E-a) or an anchor family name lna-a1..a5 (E-b).
delta: E-a tightening (0 = untightened lib spec); E-b always 0.
Engine: bench_anchor_prep.smoke_run(tokens, spec_path, seed, 2500, "bptm45"),
feasible = result["feasible"], margins = mysolve._margins (normalized).
Tightening: every supported constraint limit moved inward by delta*Spec._scale(c)
(scale of the ORIGINAL limit), written to a temp YAML (lib never modified).
"""
import sys, os, json, time, copy
REPO = os.environ.get("CR_REPO",
                      "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180")
for p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop"):
    sys.path.insert(0, p)

LIB = REPO + "/kaggle/editcap-lib-v12-45nm"
TPL = REPO + "/kaggle/claude-solutions/templates/"
BUDGET, SEEDS, PDK = 2500, (1, 2, 3), "bptm45"
DELTAS = (0.0, 0.02, 0.05, 0.10)


def cells():
    return sorted(d for d in os.listdir(LIB) if d.startswith("v12-"))


def anchors():
    m = json.load(open(REPO + "/kaggle/bench-anchors/MANIFEST.json"))
    return m["classes"]["lna"]["families"]


def jobs(exp):
    out = []
    if exp == "E-a":
        for c in cells():
            for d in DELTAS:
                for s in SEEDS:
                    out.append(f"{c} template {d} {s}")
    else:
        for c in cells():
            for fam in sorted(anchors()):
                for s in SEEDS:
                    out.append(f"{c} {fam} 0 {s}")
    return out


def tightened_spec(cell, delta):
    import yaml
    from spec import Spec
    src = f"{LIB}/{cell}/spec.yaml"
    if delta == 0:
        return src, Spec.load(src)
    data = yaml.safe_load(open(src))
    base = Spec.load(src)
    new = copy.deepcopy(data)
    for name, c in new["constraints"].items():
        if c.get("status") == "unsupported":
            continue
        sc = base._scale(data["constraints"][name])
        if "min" in c:
            c["min"] = c["min"] + delta * sc
        if "max" in c:
            c["max"] = c["max"] - delta * sc
    tdir = os.path.join(os.environ.get("TMPDIR", "/tmp"), "specs")
    os.makedirs(tdir, exist_ok=True)
    path = f"{tdir}/{cell}__d{delta:.2f}.yaml"
    with open(path, "w") as fh:
        yaml.safe_dump(new, fh, sort_keys=False)
    return path, base


def run(exp, cell, cand, delta, seed, rawdir):
    import proposal as P, bench_anchor_prep as PREP, mysolve as MS
    from spec import Spec
    delta, seed = float(delta), int(seed)
    if cand == "template":
        net = TPL + ("wideband_shunt_feedback.net" if "-wb-" in cell
                     else "narrowband_cascode_tank.net")
        tok = P.round_trip(open(net).read())["tokens"]
        src = os.path.relpath(net, REPO)
    else:
        tf = REPO + "/" + anchors()[cand]["tokens_file"]
        tok = json.load(open(tf))
        src = os.path.relpath(tf, REPO)
    sp, base = tightened_spec(cell, delta)
    t0 = time.time()
    rec = {"exp": exp, "cell": cell, "cand": cand, "cand_src": src,
           "delta": delta, "seed": seed, "budget": BUDGET, "pdk": PDK,
           "era": os.environ.get("AUDIT_ERA", "unknown")}
    try:
        r = PREP.smoke_run(list(tok), sp, seed, BUDGET, PDK)
        err = None
    except Exception as e:                                   # noqa: BLE001
        r, err = None, repr(e)
    rec["secs"] = round(time.time() - t0, 1)
    if r is None:
        rec.update(not_sizable=(err is None), error=err, feasible=False,
                   worst=None, binding=None, margins=None, metrics=None)
    else:
        rows, worst = MS._margins(base, r.get("metrics") or {})   # vs ORIGINAL spec
        trows, tworst = MS._margins(Spec.load(sp), r.get("metrics") or {})
        rec.update(not_sizable=False, error=None, feasible=bool(r["feasible"]),
                   worst=(worst[1] if worst else None),
                   binding=(worst[0] if worst else None),
                   worst_vs_tightened=(tworst[1] if tworst else None),
                   margins={n: mg for n, _a, _c, mg, _s in rows},
                   metrics=r.get("metrics"), n_evals=r.get("n_evals"),
                   n_sim_fail=r.get("n_sim_fail"), sim_error=r.get("sim_error"),
                   winner_reeval_ungated=r.get("winner_reeval_ungated"))
    fn = f"{rawdir}/{exp}__{cell}__{cand}__d{delta:.2f}__s{seed}.json"
    json.dump(rec, open(fn, "w"), indent=1, default=repr)
    print(exp, cell, cand, delta, seed, "feas=", rec["feasible"], "worst=",
          rec["worst"], rec["binding"], "secs=", rec["secs"], flush=True)


def collect(exp, rawdir, out):
    rows = []
    for j in jobs(exp):
        c, cand, d, s = j.split()
        fn = f"{rawdir}/{exp}__{c}__{cand}__d{float(d):.2f}__s{int(s)}.json"
        rows.append(json.load(open(fn)) if os.path.exists(fn)
                    else {"exp": exp, "cell": c, "cand": cand, "delta": float(d),
                          "seed": int(s), "missing": True})
    json.dump({"exp": exp, "n_rows": len(rows), "rows": rows}, open(out, "w"),
              indent=1, default=repr)
    print("collected", len(rows), "missing", sum(1 for r in rows if r.get("missing")))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "jobs":
        print("\n".join(jobs(a[1])))
    elif a[0] == "run":
        run(*a[1:7])
    elif a[0] == "collect":
        collect(a[1], a[2], a[3])

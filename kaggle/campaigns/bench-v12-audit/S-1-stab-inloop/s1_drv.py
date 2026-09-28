"""S-1 stability-aware sizing driver (bench_anchor_prep.smoke_run, opt-in
STAB_WIDE_INLOOP wide-stability term).

usage:
  s1_drv.py jobs    <regress|tpl|ec|anchors>        one job per line
  s1_drv.py run     <exp> <cell> <cand> <specmode> <mode> <seed> <rawdir>
  s1_drv.py collect <rawdir> <out.json>
  s1_drv.py picks                                   print the E-c wb edit picks

cand     : template | lna-a2-current-reuse | lna-a4-twostage | ec:<E-c cid>
specmode : lib  = untouched library spec (no mu_min -> gate OFF)
           stab = bench_anchor_prep.stability_spec(lib) (mu_min >= 1 -> gate ON)
mode     : gate   = STAB_WIDE_INLOOP unset (post-hoc gate only, existing behavior)
           inloop = STAB_WIDE_INLOOP=1 (gate + in-loop wide-stability term)
Engine: bench_anchor_prep.smoke_run(tokens, spec, seed, 2500, "bptm45") -- the
same call E-a/E-b/E-c/stability-gate made (anchors: bptm45 pdk override as E-b).

Every run also records the FINAL winner's wide mu(f) curve on the gate's exact
grid (1e8..2e10, 401 lin) for the 100 MHz edge analysis.
"""
import sys, os, json, time, re
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("CR_REPO",
                      "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180")
for p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop"):
    sys.path.insert(0, p)

LIB = REPO + "/kaggle/editcap-lib-v12-45nm"
TPL = REPO + "/kaggle/claude-solutions/templates/"
ECD = REPO + "/kaggle/campaigns/bench-v12-audit/E-c/"
BUDGET, SEEDS, PDK = 2500, (1, 2, 3), "bptm45"
ANCH = ("lna-a2-current-reuse", "lna-a4-twostage")
NB_CELLS = ("v12-nb-f15-g12", "v12-nb-f15-g16", "v12-nb-f24-g12", "v12-nb-f24-g18")
REGRESS = [  # (cell, cand, specmode, mode, seed) -- compared to stability-gate rows
    ("v12-wb-s11n10-g10-b0530", "template", "lib", "gate", 1),    # flags off, gate off
    ("v12-wb-s11n10-g10-b0530", "template", "stab", "gate", 1),   # flags off, gate on
    ("v12-wb-s11n10-g10-b0530", "template", "lib", "inloop", 1),  # flag set, gate off -> inert
]
# nb-template runs recorded FINAL-feasible by the stability-gate campaign (mix of
# f15/f24, replaced/not) -- re-run gate-only to sweep their winners' mu(f)
EDGE = [("v12-nb-f15-g14", 1), ("v12-nb-f15-g16", 2), ("v12-nb-f15-g18", 1),
        ("v12-nb-f24-g12", 1), ("v12-nb-f24-g18", 2)]
# recorded spec-feasible but wide-FAILING nb runs with mu_wide >= 0.99 (where is
# their minimum: the 100 MHz edge or an interior dip?)
EDGE_FAIL = [("v12-nb-f15-g12", "template", 1), ("v12-nb-f24-g12", "template", 2),
             ("v12-nb-f24-g14", "template", 1),
             ("v12-nb-f15-g12", "lna-a1-inddegen-cascode", 3)]


def cells():
    return sorted(d for d in os.listdir(LIB) if d.startswith("v12-"))


def ec_picks():
    """Per wb cell, up to 3 distinct confirmed-feasible E-c edits: the template
    move `add R n1-n2` (if confirmed) + the best others ranked by (in-band
    stable_mu, seeds_pass/3, in-band mu_min), all descending."""
    out = {}
    for c in json.load(open(ECD + "summary.json")):
        if "-wb-" not in c["cell"]:
            continue
        fe = [e for e in c["feasible_edits"] if e["confirm_seed1"]]
        tm = [e for e in fe if e["desc"] == "add R n1-n2"]
        rest = sorted([e for e in fe if e["desc"] != "add R n1-n2"],
                      key=lambda e: (-int(e["stable_mu"]), -e["seeds_pass"],
                                     -(e["mu_min"] if e["mu_min"] is not None else -9)))
        out[c["cell"]] = [{"cid": e["cid"], "desc": e["desc"],
                           "seeds_pass": e["seeds_pass"], "mu_min_inband_ec": e["mu_min"]}
                          for e in (tm + rest[:3 - len(tm)])]
    return out


def tokens_for(cell, cand):
    import proposal as P
    if cand == "template":
        net = TPL + ("wideband_shunt_feedback.net" if "-wb-" in cell
                     else "narrowband_cascode_tank.net")
        return P.round_trip(open(net).read())["tokens"]
    if cand.startswith("ec:"):
        cid = cand[3:]
        for ln in open(ECD + "candidates.jsonl"):
            c = json.loads(ln)
            if c["cid"] == cid:
                return c["tokens"]
        raise KeyError(cid)
    m = json.load(open(REPO + "/kaggle/bench-anchors/MANIFEST.json"))
    tf = m["classes"]["lna"]["families"][cand]["tokens_file"]
    return json.load(open(REPO + "/" + tf))


def spec_for(cell, specmode):
    import bench_anchor_prep as PREP
    src = f"{LIB}/{cell}/spec.yaml"
    # per-process out_dir: parallel workers on the same cell would otherwise
    # rewrite the same $TMPDIR/stab-specs/<cell>__mu1.yaml concurrently (a
    # reader can see it truncated). Content/basename identical to the default.
    od = os.path.join(os.environ.get("TMPDIR", "/tmp"), "stab-specs", str(os.getpid()))
    return src if specmode == "lib" else PREP.stability_spec(src, out_dir=od)


def jobs(kind):
    if kind == "regress":
        return [f"regress {c} {cand} {sm} {md} {s}" for c, cand, sm, md, s in REGRESS]
    if kind == "tpl":
        return [f"tpl {c} template stab {md} {s}" for c in cells() if "-wb-" in c
                for md in ("inloop", "gate") for s in SEEDS]
    if kind == "ec":
        return [f"ec {c} ec:{p['cid']} stab {md} {s}"
                for c, ps in ec_picks().items() for p in ps
                for md in ("inloop", "gate") for s in SEEDS]
    if kind == "edge":   # 5 recorded nb-template stable winners (the edge concern)
        return ([f"edge {c} template stab gate {s}" for c, s in EDGE]
                + [f"edgefail {c} {a} stab gate {s}" for c, a, s in EDGE_FAIL])
    if kind == "anchors":
        return [f"anchors {c} {a} stab {md} {s}" for c in NB_CELLS for a in ANCH
                for md in ("inloop", "gate") for s in SEEDS]
    raise SystemExit(kind)


def mu_curve(body, params):
    """mu(f) on the gate's exact grid for (body, params); [(f, mu), ...]."""
    import extract as E
    lines = [body.rstrip(),
             ".param " + " ".join(f"{k}={v}" for k, v in params.items()),
             "\n".join([".control", "op", "sp lin 401 1e8 2e10 1"]
                       + E._stability_lets() + ["print mul", ".endc", ".end"])]
    txt = E.run_deck("\n".join(lines) + "\n", "stabc_", "s.cir", timeout=120) or ""
    pts = []
    for ln in txt.splitlines():
        t = ln.split()
        if len(t) == 3 and re.match(r"^\d+$", t[0]):
            try:
                pts.append((float(t[1]), float(t[2])))
            except ValueError:
                pass
    return pts


def curve_summary(pts, band):
    if not pts:
        return None
    fmin, mmin = min(pts, key=lambda p: p[1])
    inner = pts[1:]
    fi, mi = min(inner, key=lambda p: p[1])
    return {"n_pts": len(pts), "argmin_hz": fmin, "mu_min": mmin,
            "argmin_is_edge": fmin == pts[0][0], "mu_at_100MHz": pts[0][1],
            "mu_at_20GHz": pts[-1][1],
            "interior_argmin_hz": fi, "interior_mu_min": mi,
            "n_mu_lt_1": sum(1 for _f, m in pts if m < 1.0),
            "n_mu_lt_1p001": sum(1 for _f, m in pts if m < 1.001),
            "unstable_span_hz": ([min(f for f, m in pts if m < 1.0),
                                  max(f for f, m in pts if m < 1.0)]
                                 if any(m < 1.0 for _f, m in pts) else None),
            "band": band}


def run(exp, cell, cand, specmode, mode, seed, rawdir):
    fn = f"{rawdir}/{exp}__{cell}__{cand.replace(':', '_')}__{specmode}__{mode}__s{seed}.json"
    if os.path.exists(fn):
        print("skip (exists)", fn)
        return
    if mode == "inloop":
        os.environ["STAB_WIDE_INLOOP"] = "1"
    else:
        os.environ.pop("STAB_WIDE_INLOOP", None)
    import bench_anchor_prep as PREP, mysolve as MS
    from spec import Spec
    seed = int(seed)
    # instrumentation only (no behavior change): time/split every wide sim into
    # loop (in-loop term) vs gate (post-hoc audit) and keep the gate's calls so
    # the final winner's (body, params) can be re-swept for the mu(f) curve.
    phase = {"p": "loop"}
    tstat = {"loop": [0, 0.0], "gate": [0, 0.0]}
    gate_calls = []
    _ws, _gate = PREP.wide_stability, PREP._wide_stability_gate

    def _timed(spec, body, params):
        t = time.time()
        r = _ws(spec, body, params)
        s = tstat[phase["p"]]
        s[0] += 1
        s[1] += time.time() - t
        if phase["p"] == "gate":
            gate_calls.append((body, dict(params), r[1]))
        return r

    def _gated(*a, **k):
        phase["p"] = "gate"
        return _gate(*a, **k)
    PREP.wide_stability, PREP._wide_stability_gate = _timed, _gated
    tok = tokens_for(cell, cand)
    sp = spec_for(cell, specmode)
    t0 = time.time()
    r = PREP.smoke_run(list(tok), sp, seed, BUDGET, PDK)
    secs = time.time() - t0
    rec = {"exp": exp, "cell": cell, "cand": cand, "specmode": specmode, "mode": mode,
           "seed": seed, "budget": BUDGET, "pdk": PDK, "spec": os.path.basename(sp),
           "era": os.environ.get("AUDIT_ERA", "unknown"), "secs": round(secs, 1),
           "wide_sims_loop": tstat["loop"][0], "wide_secs_loop": round(tstat["loop"][1], 2),
           "wide_sims_gate": tstat["gate"][0], "wide_secs_gate": round(tstat["gate"][1], 2)}
    if r is None:
        rec.update(not_sizable=True, feasible=False)
    else:
        spec = Spec.load(sp)
        rows, worst = MS._margins(spec, r.get("metrics") or {})
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
        if gate_calls:
            body, params, _ok = (gate_calls[-1] if r.get("stab_winner_replaced")
                                 else gate_calls[0])
            rec["curve"] = curve_summary(mu_curve(body, params),
                                         [spec.band.get("f_lo"), spec.band.get("f_hi")])
    json.dump(rec, open(fn, "w"), indent=1, default=repr)
    c = rec.get("curve") or {}
    print(exp, cell, cand, specmode, mode, seed, "feas=", rec["feasible"],
          "spec_feas=", rec.get("spec_feasible"), "mu=", rec.get("mu_min"),
          "mu_wide=", rec.get("mu_min_wide"), "argmin=", c.get("argmin_hz"),
          "repl=", rec.get("stab_winner_replaced"), "secs=", rec["secs"],
          "loopwide=", rec["wide_sims_loop"], rec["wide_secs_loop"], flush=True)


def collect(rawdir, out):
    rows = [json.load(open(os.path.join(rawdir, f)))
            for f in sorted(os.listdir(rawdir)) if f.endswith(".json")]
    json.dump({"n_rows": len(rows), "ec_picks": ec_picks(), "rows": rows},
              open(out, "w"), indent=1, default=repr)
    print("collected", len(rows))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "jobs":
        print("\n".join(jobs(a[1])))
    elif a[0] == "run":
        run(*a[1:8])
    elif a[0] == "collect":
        collect(a[1], a[2])
    elif a[0] == "picks":
        print(json.dumps(ec_picks(), indent=1))

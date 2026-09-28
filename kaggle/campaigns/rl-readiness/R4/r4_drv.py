"""R4 verifier loophole audit -- sizing driver with winner CAPTURE.

The verifier under audit (the config RL will use):
    bench_anchor_prep.smoke_run(tokens, stability_spec(<cell spec>), seed, 2500,
                                "bptm45")  with env STAB_WIDE_INLOOP=1
smoke_run's result dict carries no sized values, so this driver wraps
SZ.make_objective (instrumentation only: the objective/evaluate are returned
unchanged, byte-identical results) to capture the prepared body, the
sizable/fixed maps, `decode`, and every EXTERNAL `evaluate(x)` call. The first
external call is smoke_run's endpoint re-eval at bx (the spec winner); if the
wide gate replaced the winner, `stab_replacement.x` is the final winner.

usage:
  r4_drv.py jobs <set>                              one job per line
  r4_drv.py run <tag> <cell> <cand> <mode> <seed> <rawdir>
  r4_drv.py collect <rawdir> <out.json>

cand : template | anchor:<family> | ec:<E-c cid> | ed:<E-d key> | net:<name>
       (net:<name> = netlist text in R4/mutations.json)
mode : inloop = stab spec + STAB_WIDE_INLOOP=1  (THE verifier under audit)
       gate   = stab spec, gate only (recorded stability-gate behavior)
       lib    = untouched library spec (no mu_min; historical smoke_run)
       topo   = inloop + VERIFY_TOPO_LIMITS=1 (guard (a))
"""
import sys, os, json, time
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop"):
    sys.path.insert(0, p)

LIB = REPO + "/kaggle/editcap-lib-v12-45nm"
TPL = REPO + "/kaggle/claude-solutions/templates/"
AUD = REPO + "/kaggle/campaigns/bench-v12-audit/"
BUDGET, PDK = 2500, "bptm45"


def cells():
    return sorted(d for d in os.listdir(LIB) if d.startswith("v12-"))


def template_net(cell):
    return open(TPL + ("wideband_shunt_feedback.net" if "-wb-" in cell
                       else "narrowband_cascode_tank.net")).read()


def tokens_for(cell, cand):
    import proposal as P
    if cand == "template":
        return P.round_trip(template_net(cell))["tokens"]
    if cand.startswith("ec:"):
        cid = cand[3:]
        for ln in open(AUD + "E-c/candidates.jsonl"):
            c = json.loads(ln)
            if c["cid"] == cid:
                return c["tokens"]
        raise KeyError(cid)
    if cand.startswith("ed:"):
        return json.load(open(AUD + "E-d/cand.json"))[f"{cell}|{cand[3:]}"]
    if cand.startswith("anchor:"):
        m = json.load(open(REPO + "/kaggle/bench-anchors/MANIFEST.json"))
        tf = m["classes"]["lna"]["families"][cand[7:]]["tokens_file"]
        return json.load(open(REPO + "/" + tf))
    if cand.startswith("net:"):
        txt = json.load(open(HERE + "/mutations.json"))[cand[4:]]
        rt = P.round_trip(txt)
        if not rt["ok"]:
            raise RuntimeError(f"round_trip failed: {rt['error']}")
        return rt["tokens"]
    raise KeyError(cand)


def spec_for(cell, mode):
    import bench_anchor_prep as PREP
    src = f"{LIB}/{cell}/spec.yaml"
    if mode == "lib":
        return src
    od = os.path.join(os.environ.get("TMPDIR", "/tmp"), "stab-specs", str(os.getpid()))
    return PREP.stability_spec(src, out_dir=od)


def run(tag, cell, cand, mode, seed, rawdir):
    fn = f"{rawdir}/{tag}__{cell}__{cand.replace(':', '_')}__{mode}__s{seed}.json"
    if os.path.exists(fn):
        print("skip (exists)", fn)
        return
    for k in ("STAB_WIDE_INLOOP", "VERIFY_TOPO_LIMITS", "VERIFY_STRUCT", "VERIFY_FINITE",
              "VERIFY_NF_BAND", "VERIFY_NO_INERT", "VERIFY_ROBUST", "VERIFY_BAND_METRICS",
              "STAB_WIDE_WINDOW"):
        os.environ.pop(k, None)
    if mode in ("inloop", "topo", "struct", "all", "win50"):
        os.environ["STAB_WIDE_INLOOP"] = "1"
    if mode == "topo":
        os.environ["VERIFY_TOPO_LIMITS"] = "1"
    if mode == "struct":
        os.environ["VERIFY_STRUCT"] = "1"
    if mode == "win50":         # guard (d): 10 MHz - 50 GHz window, same ~50 MHz spacing
        os.environ["STAB_WIDE_WINDOW"] = "1e7,5e10,1001"
    if mode == "all":           # every R4 guard on
        os.environ.update(VERIFY_TOPO_LIMITS="1", VERIFY_STRUCT="1", VERIFY_FINITE="1",
                          VERIFY_NF_BAND="1", VERIFY_NO_INERT="1", VERIFY_ROBUST="10",
                          VERIFY_BAND_METRICS="1")
    import bench_anchor_prep as PREP
    import mysolve as MS
    from spec import Spec
    cap = {"evals": []}
    _mk = PREP.SZ.make_objective

    def _cap_mk(body, spec, sizable, fixed, **kw):
        obj, names, decode, evaluate = _mk(body, spec, sizable, fixed, **kw)
        cap.update(body=body, sizable=dict(sizable), fixed=dict(fixed),
                   names=list(names), decode=decode)

        def ev(x, *a, **k):
            cap["evals"].append([float(v) for v in x])
            return evaluate(x, *a, **k)
        return obj, names, decode, ev
    PREP.SZ.make_objective = _cap_mk
    seed = int(seed)
    tok = tokens_for(cell, cand)
    sp = spec_for(cell, mode)
    t0 = time.time()
    r = PREP.smoke_run(list(tok), sp, seed, BUDGET, PDK)
    secs = time.time() - t0
    rec = {"tag": tag, "cell": cell, "cand": cand, "mode": mode, "seed": seed,
           "budget": BUDGET, "pdk": PDK, "spec": sp, "secs": round(secs, 1),
           "tokens": list(tok), "result": r}
    if r is not None and "decode" in cap:
        spec = Spec.load(sp)
        rows, worst = MS._margins(spec, r.get("metrics") or {})
        rec["worst"] = worst
        dec = cap["decode"]
        x_bx = cap["evals"][0] if cap["evals"] else None
        rep = r.get("stab_replacement")
        x_win = rep["x"] if (r.get("stab_winner_replaced") and rep) else x_bx
        rec.update(body=cap["body"], sizable=cap["sizable"], fixed=cap["fixed"],
                   names=cap["names"], x_bx=x_bx,
                   params_bx=dec(x_bx) if x_bx else None,
                   x_win=x_win, params_win=dec(x_win) if x_win else None,
                   n_external_evals=len(cap["evals"]))
    json.dump(rec, open(fn, "w"), indent=1, default=repr)
    print(tag, cell, cand, mode, seed, "feas=", (r or {}).get("feasible"),
          "spec_feas=", (r or {}).get("spec_feasible"),
          "mu_wide=", (r or {}).get("mu_min_wide"), "secs=", rec["secs"], flush=True)


# ------------------------------------------------------------------ job sets
def _s1_rows():
    return json.load(open(AUD + "S-1-stab-inloop/results.json"))["rows"]


def jobs(kind):
    out = []
    if kind == "s1":        # S-1 inloop final-feasible winners (unique; addR n1-n2 == tpl)
        s1 = json.load(open(AUD + "S-1-stab-inloop/results.json"))
        dup = {"ec:" + p["cid"] for ps in s1["ec_picks"].values() for p in ps
               if p["desc"] == "add R n1-n2"}
        for r in s1["rows"]:
            if r["cand"] in dup:
                continue
            if r["mode"] == "inloop" and r["feasible"] and r["exp"] in ("tpl", "ec"):
                out.append(f"s1 {r['cell']} {r['cand']} inloop {r['seed']}")
    elif kind == "nb":      # new: nb template + a1 + E-c 'add L VIN1-n1' under the RL verifier
        ec = json.load(open(AUD + "E-c/summary.json"))
        for c in cells():
            if "-nb-" not in c:
                continue
            addl = [e["cid"] for e in next(x for x in ec if x["cell"] == c)["feasible_edits"]
                    if e["desc"] == "add L VIN1-n1"][0]
            for s in (1, 2, 3):
                out += [f"nb {c} template inloop {s}",
                        f"nb {c} anchor:lna-a1-inddegen-cascode inloop {s}",
                        f"nb {c} ec:{addl} inloop {s}"]
    elif kind == "ed":      # E-d feasible Qwen edits re-scored under the RL verifier
        seen = set()
        for ln in open(AUD + "E-d/score.jsonl"):
            r = json.loads(ln)
            if r["feasible"] and (r["cell"], r["key"]) not in seen:
                seen.add((r["cell"], r["key"]))
                out += [f"ed {r['cell']} ed:{r['key']} inloop {s}" for s in (1, 2, 3)]
    elif kind == "gatefail":  # gate-only designs that are spec-feasible but wide-unstable
        for c in cells():
            if "-wb-" in c:
                out.append(f"gf {c} template gate 1")
        for c in ("v12-nb-f15-g12", "v12-nb-f15-g16", "v12-nb-f24-g12", "v12-nb-f24-g18"):
            out.append(f"gf {c} anchor:lna-a4-twostage gate 1")
    elif kind == "mut":     # adversarial mutations (item f), parents are in s1/nb sets
        for name in json.load(open(HERE + "/mutations.json")):
            cell = "v12-wb-s11n10-g10-b0824" if name.startswith("wb_") else "v12-nb-f15-g16"
            out += [f"mut {cell} net:{name} inloop {s}" for s in (1, 2)]
    elif kind == "dir":     # E-c 'add R VIN1-VOUT1' solutions: recorded (lib) + RL verifier
        for c in ("v12-wb-s11n10-g10-b0824", "v12-wb-s11n10-g12-b0824", "v12-wb-s11n11-g10-b0824",
                  "v12-wb-s11n8-g10-b0530", "v12-wb-s11n9-g10-b0530"):
            out += [f"dir {c} ec:72945e70a2a1:030 lib 1", f"dir {c} ec:72945e70a2a1:030 inloop 1"]
    elif kind == "reg":     # flags-off regression vs RECORDED rows + guard (a) on/off
        out += ["reg v12-wb-s11n10-g10-b0530 ec:72945e70a2a1:131 lib 1",   # E-c results.jsonl
                "reg v12-nb-f15-g14 template gate 1",                     # stability-gate row
                "reg v12-wb-s11n10-g10-b0824 template inloop 1",          # S-1 row
                "reg v12-nb-f15-g16 template topo 1",                     # guard on, passing
                "reg v12-wb-s11n10-g10-b0824 template topo 1"]            # guard on, violating
    elif kind == "reg2":    # same after the FINAL bench_anchor_prep edit + end-to-end guards
        out += ["reg2 v12-wb-s11n10-g10-b0530 ec:72945e70a2a1:131 lib 1",
                "reg2 v12-nb-f15-g14 template gate 1",
                "reg2 v12-wb-s11n10-g10-b0824 template inloop 1",
                "reg2 v12-nb-f15-g16 net:nb_dead_mos struct 1",           # must reject
                "reg2 v12-nb-f15-g16 template struct 1",                  # clean -> as inloop
                "reg2 v12-nb-f15-g16 template all 1",                     # every guard on
                "reg2 v12-nb-f15-g16 net:nb_bleeder all 1",
                "reg2 v12-wb-s11n10-g10-b0824 template win50 1"]
    elif kind == "win50":   # the 8 winners that fail 0.01-50 GHz, re-sized under the wide window
        out += [f"win50 {c} {cand} win50 {s}" for c, cand, s in (
            ("v12-wb-s11n10-g10-b0824", "ed:9af88577a27709b7", 1),
            ("v12-wb-s11n10-g10-b0824", "ed:c7deae173fa1561a", 1),
            ("v12-wb-s11n11-g10-b0824", "ed:47a457c041f79c4d", 1),
            ("v12-wb-s11n8-g10-b0530", "ed:47a457c041f79c4d", 2),
            ("v12-nb-f24-g16", "anchor:lna-a1-inddegen-cascode", 1),
            ("v12-wb-s11n8-g10-b0530", "ec:72945e70a2a1:147", 2),
            ("v12-wb-s11n9-g10-b0530", "ec:72945e70a2a1:126", 2),
            ("v12-wb-s11n9-g10-b0530", "ec:72945e70a2a1:156", 1))]
    else:
        raise SystemExit(kind)
    return out


def collect(rawdir, out):
    rows = [json.load(open(os.path.join(rawdir, f)))
            for f in sorted(os.listdir(rawdir)) if f.endswith(".json")]
    json.dump({"n_rows": len(rows), "rows": rows}, open(out, "w"), indent=1, default=repr)
    print("collected", len(rows))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "jobs":
        print("\n".join(jobs(a[1])))
    elif a[0] == "run":
        run(*a[1:7])
    elif a[0] == "collect":
        collect(a[1], a[2])

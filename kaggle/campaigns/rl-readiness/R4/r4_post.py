"""R4 per-design audit on captured designs (items b-dynamic, c, d, e, f).

usage: r4_post.py one <raw.json> <outdir>      (one raw run -> <outdir>/<name>.json)
       r4_post.py collect <outdir> <out.json>

Designs taken from one raw run (r4_drv capture):
  win  : the FINAL winner when the run is final-feasible (spec AND wide gate)
  fail : a design the wide gate REJECTED although spec-feasible:
         the spec winner (bx) of a run whose winner was replaced, or of a run
         that ended spec-feasible but wide-unstable.
Per design:
  repro      re-eval via SZ.eval_metrics == recorded metrics (determinism)
  op         per-MOS |Id| / region, Vsup and VBGEN branch currents  (b)
  inert      each proposal R/C/L opened (R 1e12, C 1e-20 F, L 1 H) one at a
             time -> does the design stay final-feasible?            (b, f)
  bounds     sized values pinned at the range limits                 (f)
  frag       10 draws, every sized value x (1+U[-5%,+5%]), seed = md5(id) (c)
  windows    mu_min over 0.1-10 GHz lin 199, 0.1-20 lin 401 (gate),
             0.01-50 lin 1001 (+ dec 50/decade 1e7-5e10 for the edges)  (d)
  s21        peak |S21| over 0.01-50 GHz vs in-band                  (f)
  nfband     NF at all 51 band points vs the NF at f0 the spec checks (f)
  tran       transient, 5x5 port terminations (r50/open/short/l3n/c1p),
             ~10 ps 1 mA kick at VIN1+VOUT1, 80 ns, trap; any 'oscillates'
             re-checked with method=gear                             (e)
"""
import sys, os, json, hashlib, random, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r4_sim as S                                           # noqa: E402

N_FRAG, FRAG = 10, 0.05
WINDOWS = {"w0p1_10": "lin 199 1e8 1e10", "w0p1_20": "lin 401 1e8 2e10",
           "w0p01_50": "lin 1001 1e7 5e10", "w0p01_50_dec": "dec 50 1e7 5e10",
           "w0p1_20_fine": "lin 3981 1e8 2e10"}   # 5 MHz grid: dips between gate points?


def designs(rec):
    r = rec.get("result") or {}
    if not rec.get("params_win"):
        return []
    out = []
    if r.get("feasible"):
        out.append(("win", rec["params_win"], rec["x_win"]))
    if r.get("spec_feasible") and (r.get("stab_winner_replaced") or not r.get("stab_wide_ok")):
        out.append(("fail", rec["params_bx"], rec["x_bx"]))
    return out


def _open_value(kind):
    return {"R": "1e12", "C": "1e-20", "L": "1"}[kind]


def analyse(rec, role, params, x):
    spec = S.spec_of(rec)
    did = f"{rec['cell']}|{rec['cand']}|{rec['mode']}|s{rec['seed']}|{role}"
    d = {"id": did, "cell": rec["cell"], "cand": rec["cand"], "mode": rec["mode"],
         "seed": rec["seed"], "role": role, "tag": rec["tag"]}
    m, sf, st, ok, ff, op = S.full_eval(rec, params, op=True)
    rm = (rec["result"] or {}).get("metrics") or {}
    d["metrics"] = m
    d["spec_feasible"], d["wide_ok"], d["final_feasible"] = sf, ok, ff
    d["mu_wide_gate"] = (st or {}).get("mu_min")
    d["worst_margin"] = S.worst_margin(spec, m)
    if role == "win":
        d["repro_identical"] = all(m.get(k) == rm.get(k) for k in rm)
    # ---- op (b) ----
    devs = (op or {}).get("devices", {})
    br = (op or {}).get("branches", {})
    d["op"] = {"mos": {k: {"id": v.get("id"), "region": v.get("region"),
                           "vgs": v.get("vgs"), "vds": v.get("vds")}
                       for k, v in devs.items() if k.startswith("m")},
               "branches": br}
    d["n_mos"] = len(d["op"]["mos"])
    d["n_mos_lt_1uA"] = sum(1 for v in d["op"]["mos"].values()
                            if v["id"] is not None and abs(v["id"]) < 1e-6)
    d["n_mos_off_50uA"] = sum(1 for v in d["op"]["mos"].values() if v["region"] == "off")
    d["vbgen_current_a"] = sum(abs(v) for k, v in br.items() if k.startswith("vbgen"))
    # ---- inert passives (b/f) ----
    inert = []
    for name, kind in rec["sizable"].items():
        if kind not in ("R", "C", "L"):
            continue
        p2 = dict(params)
        p2[name] = _open_value(kind)
        r2 = S.full_eval(rec, p2)
        if r2[4]:
            inert.append(name)
    d["inert_passives"] = inert
    d["n_passives"] = sum(1 for k in rec["sizable"].values() if k in ("R", "C", "L"))
    # ---- bounds (f) ----
    names = rec["names"]
    d["at_bounds"] = [(n, rec["sizable"][n], "lo" if xi <= 1e-3 else "hi")
                      for n, xi in zip(names, x) if xi <= 1e-3 or xi >= 1 - 1e-3]
    # ---- fragility (c) ----
    if role == "win":
        rng = random.Random(int(hashlib.md5(did.encode()).hexdigest()[:8], 16))
        draws = []
        for _ in range(N_FRAG):
            p2 = dict(params)
            for n in names:
                p2[n] = f"{float(params[n]) * (1 + rng.uniform(-FRAG, FRAG)):.6g}"
            m2, sf2, st2, ok2, ff2 = S.full_eval(rec, p2)
            draws.append({"spec_feasible": sf2, "wide_ok": ok2, "final_feasible": ff2,
                          "worst_margin": S.worst_margin(spec, m2) if m2 else None,
                          "mu_wide": (st2 or {}).get("mu_min"),
                          "viol": sorted(spec.feasible(m2)[1]) if m2 else ["sim_fail"]})
        d["frag"] = draws
        d["frag_final_feasible"] = sum(x_["final_feasible"] for x_ in draws)
        d["frag_spec_feasible"] = sum(x_["spec_feasible"] for x_ in draws)
        d["frag_wide_ok"] = sum(x_["wide_ok"] for x_ in draws)
    # ---- windows (d) ----
    sp_ = S.stab_params(rec, params)
    win = {}
    for k, sw in WINDOWS.items():
        pts = S.mu_curve(rec["body"], sp_, sw)
        if not pts:
            win[k] = None
            continue
        fmin, mmin = min(pts, key=lambda t: t[1])
        below = [f for f, mu in pts if mu < 1.0]
        win[k] = {"mu_min": mmin, "argmin_hz": fmin, "n": len(pts),
                  "unstable_span_hz": [min(below), max(below)] if below else None}
    d["windows"] = win
    # ---- s21 peak (f) ----
    s = S.s21_curve(rec["body"], sp_, "dec 50 1e7 5e10") + \
        S.s21_curve(rec["body"], sp_, "lin 1001 1e7 5e10")
    if s:
        fpk, spk = max(s, key=lambda t: t[1])
        d["s21_peak_db"], d["s21_peak_hz"] = spk, fpk
    # ---- NF over band (f) ----
    nb = S.nf_band(rec, params)
    if nb:
        fmax, nmax = max(nb, key=lambda t: t[1])
        d["nf_band_max_db"], d["nf_band_argmax_hz"] = nmax, fmax
        d["nf_f0_db"] = (m or {}).get("nf_db")
        c = spec.constraints.get("nf_db", {})
        d["nf_band_ok"] = ("max" not in c) or nmax <= c["max"]
    # ---- transient (e) ----
    tr = {}
    for ts in S.TERMS:
        for tl in S.TERMS:
            r = S.tran_run(rec["body"], sp_, term_src=ts, term_load=tl)
            v = S.tran_verdict(r)
            if v == "oscillates":
                rg = S.tran_run(rec["body"], sp_, term_src=ts, term_load=tl, method="gear")
                r = dict(r, gear=rg, gear_verdict=S.tran_verdict(rg))
                v = "oscillates" if S.tran_verdict(rg) == "oscillates" else "osc_trap_only"
            tr[f"{ts}/{tl}"] = {"verdict": v, "amp": r}
    d["tran"] = tr
    d["tran_r50"] = tr["r50/r50"]["verdict"]
    d["tran_n_osc"] = sum(1 for v in tr.values() if v["verdict"] == "oscillates")
    return d


def one(raw, outdir):
    rec = json.load(open(raw))
    name = os.path.basename(raw)[:-5]
    fn = os.path.join(outdir, name + ".json")
    if os.path.exists(fn):
        print("skip", fn)
        return
    out = {"raw": name, "designs": [analyse(rec, role, p, x) for role, p, x in designs(rec)]}
    json.dump(out, open(fn, "w"), indent=1, default=repr)
    print(name, [(d["role"], d.get("frag_final_feasible"), d["tran_r50"], d["tran_n_osc"])
                 for d in out["designs"]], flush=True)


def collect(outdir, out):
    rows = []
    for f in sorted(os.listdir(outdir)):
        if f.endswith(".json"):
            rows += json.load(open(os.path.join(outdir, f)))["designs"]
    json.dump({"n": len(rows), "designs": rows}, open(out, "w"), indent=1, default=repr)
    print("collected", len(rows))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "one":
        os.makedirs(a[2], exist_ok=True)
        one(a[1], a[2])
    elif a[0] == "collect":
        collect(a[1], a[2])

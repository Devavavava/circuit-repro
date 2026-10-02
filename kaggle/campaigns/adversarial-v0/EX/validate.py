"""EX: validation of the reality checks on known cases (no re-sizing; read-only inputs).

  R-a  9 bench-v2 L-IN-G port-DC cells (motif-audit sized_P0, the rl-v1 winners that
       rl-v1.1 rejects) must FAIL the DC-grounded source (P2); the 2 controls
       (nb090-gain-007, wb1020-noise-003) must pass P1 and P2. P1 is compared with the
       motif audit's own P1 verdicts.
  R-b  R4 confirmed oscillators: 5 gate-rejected + 3 lib R(VIN1-VOUT1) winners are
       LINEAR (osc_smallkick) -> must FAIL; the 7 rl-era nb-f24 winners that limit-
       cycle only after the 1 mA kick -> must NOT fail (large_signal_only);
       R4 osc_control VCO core -> FAIL, damped copy -> pass.
  R-c  synthetic positive control: a high-Q series R-L-C trap from VIN1 to ground
       tuned to f_lo + 0.025 (f_hi - f_lo) -- between two of the verifier's 101 sp /
       51 noise points, on a point of the 4x grids -- added to a clean winner: the
       verifier grid must not see it, R-c must. Negative control: the same winner.
  R-d/R-e  identity: temp=27 C and VDD x 1.0 reproduce the nominal metrics exactly.
usage: validate.py <seeds raw dir> <out.json>
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ex_lib as X  # noqa: E402

REPO = X.REPO
MA = f"{REPO}/kaggle/campaigns/bench-v2/motif-audit/results"
CELLS = f"{REPO}/kaggle/campaigns/bench-v2/run/cells"
R4 = f"{REPO}/kaggle/campaigns/rl-readiness/R4"
CONTROLS = ("v2a-nb090-gain-007", "v2a-wb1020-noise-003")


def v_Ra():
    out = {}
    for cell in sorted(os.listdir(MA)):
        p = f"{MA}/{cell}/sized_P0.json"
        if not os.path.exists(p):
            continue
        d = json.load(open(p))
        spec = X.load_spec(f"{CELLS}/{cell}/spec.yaml")
        base = X.full_eval(d["body"], d["params"], spec)
        ra = X.check_Ra(d["body"], d["params"], spec)
        aud = {}
        try:
            a = json.load(open(f"{MA}/{cell}/audit.json"))
            aud = {k: (a.get("probe") or a.get("probes") or {}).get(k, {}).get("final_ok")
                   for k in ("P1", "P2")}
        except Exception:                                        # noqa: BLE001
            pass
        role = "control" if cell in CONTROLS else "L-IN-G"
        out[cell] = {"role": role, "base_ok": base["ok"],
                     "P1_ok": ra["P1"]["ok"], "P1_mag": ra["P1"]["mag"],
                     "P1_worst": ra["P1"].get("worst"),
                     "P2_ok": ra["P2"]["ok"], "P2_mag": ra["P2"]["mag"],
                     "P2_worst": ra["P2"].get("worst"), "P2_dIdd_pct": ra["P2"].get("dIdd_pct"),
                     "motif_audit_final_ok": aud,
                     "expected": "P2 fail" if role == "L-IN-G" else "P1+P2 pass",
                     "as_expected": (not ra["P2"]["ok"]) if role == "L-IN-G"
                     else (ra["P1"]["ok"] and ra["P2"]["ok"])}
        print("Ra", cell, out[cell]["P1_ok"], out[cell]["P2_ok"], out[cell]["as_expected"], flush=True)
    return out


def _r4_rows():
    d = json.load(open(f"{R4}/results.json"))["rows"]
    idx = {}
    for r in d:
        k = f"{r['cell']}|{r['cand']}|{r['mode']}|s{r['seed']}"
        idx.setdefault(k, r)
    return idx


def v_Rb():
    import r4_sim as S                                           # noqa: F401
    sys.path.insert(0, R4)
    import osc_control as OC
    idx = _r4_rows()
    out = {}
    for o in json.load(open(f"{R4}/osc_smallkick.json")):
        key = o["id"].rsplit("|", 1)[0]
        r = idx[key]
        params = r["params_win"] if o["role"] == "win" else r["params_bx"]
        rb = X.check_Rb(r["body"], params)
        linear = o["smallkick_verdict"] == "oscillates"
        out[o["id"]] = {"r4_role": o["role"], "r4_term": o["term"], "r4_linear": linear,
                        "linear_osc": rb["linear_osc"], "large_signal_only": rb["large_signal_only"],
                        "fail": rb["fail"], "as_expected": rb["fail"] == linear,
                        "large_signal_seen": bool(rb["large_signal_only"])}
        print("Rb", o["id"], linear, rb["fail"], rb["linear_osc"][:3], rb["large_signal_only"][:3], flush=True)
    for name, damp in (("vco_pos", False), ("vco_damped", True)):
        b = OC.body(damp)
        rb = X.check_Rb(b, {"pVDD": "1.1"})
        out[name] = {"fail": rb["fail"], "linear_osc": rb["linear_osc"],
                     "large_signal_only": rb["large_signal_only"],
                     "as_expected": rb["fail"] == (not damp)}
        print("Rb", name, rb["fail"], flush=True)
    return out


def trap_body(body, spec):
    import math
    b = spec.band
    f0 = float(b["f0"])
    flo, fhi = float(b.get("f_lo", f0 * .98)), float(b.get("f_hi", f0 * 1.02))
    # mid-band, away from the band-edge maxima: 0.475 = 190/400 (a 4x sp point,
    # 95/200 a 4x noise point) lies between verifier sp points 47/100 and 48/100
    ft = flo + 0.475 * (fhi - flo)
    # trap reactance 2*L*dw = 2 kohm at the nearest verifier grid points
    # (offset (f_hi - f_lo)/200); R = 25 ohm at resonance (a dense-grid point;
    # 3-dB width R/(2 pi L) = 1/80 of that offset, robust to sweep rounding)
    L = 2e3 / (2 * 2 * math.pi * (fhi - flo) / 200)
    C = 1.0 / ((2 * math.pi * ft) ** 2 * L)
    return body.rstrip() + (f"\nRtrapx VIN1 ntrapa 25\nLtrapx ntrapa ntrapb {L:.15g}\n"
                            f"Ctrapx ntrapb 0 {C:.15g}\n"), ft


def v_Rc(seeds_dir):
    out = {}
    picks = []
    for f in sorted(os.listdir(seeds_dir)):
        if not f.endswith(".json"):
            continue
        r = json.load(open(f"{seeds_dir}/{f}"))
        if r.get("verifier_pass") and r.get("summary") and not r["summary"]["material"]:
            picks.append(r)
    nb = [r for r in picks if "nb" in os.path.basename(r["spec"])][:2]
    wb = [r for r in picks if "wb" in os.path.basename(r["spec"])][:2]
    for r in nb + wb:
        spec = X.load_spec(f"{REPO}/{r['spec']}")
        tb, ft = trap_body(r["body"], spec)
        grid = X.full_eval(tb, r["params"], spec)
        rc = X.check_Rc(tb, r["params"], spec, grid.get("metrics"))
        neg = X.check_Rc(r["body"], r["params"], spec, X.full_eval(r["body"], r["params"], spec)["metrics"])
        base = X.full_eval(r["body"], r["params"], spec)
        # identity checks for R-d / R-e
        t27 = X.corner_eval(r["body"], r["params"], spec, temp=27)
        v1 = X.corner_eval(r["body"], r["params"], spec, vdd_scale=1.0)
        same = lambda a, b: all(a.get(k) == b.get(k) for k in ("s11_max_db", "s21_db", "idd_ma", "nf_db", "nf_max_db", "mu_min"))  # noqa: E731
        out[r["sid"]] = {"spec": r["spec"], "f_trap": ft,
                         "verifier_grid_with_trap_ok": grid["ok"],
                         "verifier_grid_with_trap_mag": grid["mag"],
                         "grid_s11_max_trap": (grid.get("metrics") or {}).get("s11_max_db"),
                         "grid_s11_max_clean": base["metrics"].get("s11_max_db"),
                         "Rc_trap_fail": rc["fail"], "Rc_trap_mag": rc["mag"], "Rc_trap_worst": rc["worst"],
                         "Rc_trap_dense": rc["dense"],
                         "Rc_clean_fail": neg["fail"], "Rc_clean_mag": neg["mag"],
                         "Rd_T27_identical": same(t27["metrics"], base["metrics"]),
                         "Re_V1.0_identical": same(v1["metrics"], base["metrics"]),
                         # detector test: the dense grid sees a violation clearly larger
                         # than whatever leaks onto the verifier grid, and the clean
                         # design stays clean (nb winners sit exactly on their limit, so
                         # the trap's off-resonance leak is visible on the grid too)
                         "as_expected": bool(grid["mag"] < 0.02 and rc["fail"]
                                             and rc["mag"] > max(0.02, 2 * grid["mag"])
                                             and not neg["fail"])}
        print("Rc", r["sid"], out[r["sid"]]["verifier_grid_with_trap_ok"], rc["fail"], rc["mag"], neg["fail"], flush=True)
    return out


def main(seeds_dir, out):
    res = {}
    if os.path.exists(out):
        res = json.load(open(out))
    for name, fn in (("Ra", v_Ra), ("Rb", v_Rb), ("Rc", lambda: v_Rc(seeds_dir))):
        if name not in res:
            res[name] = fn()
            json.dump(res, open(out, "w"), indent=1, default=repr)
    summ = {}
    for name in ("Ra", "Rb", "Rc"):
        v = res[name]
        summ[name] = {"n": len(v), "as_expected": sum(bool(x.get("as_expected")) for x in v.values())}
    res["summary"] = summ
    json.dump(res, open(out, "w"), indent=1, default=repr)
    print(json.dumps(summ))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

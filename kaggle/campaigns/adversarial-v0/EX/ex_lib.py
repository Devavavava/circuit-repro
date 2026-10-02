"""EX (PREREG-ADVERSARIAL-V0, commit 307673caf): verifier-exploiter library.

  sized_run_v11(tokens, spec_path, seed)  rl-v1.1 smoke_run VERBATIM (seed x 2500,
        bptm45) with read-only capture patches (prepared body, decode, budget) so the
        FINAL winner's sized params are known (stab replacement if any, else bx) --
        the same capture as bench-v2/motif-audit/motif_audit.py:sized_run.
  reality_checks(body, params, spec, which)  R-a..R-e on a sized winner (NO re-sizing):
     R-a  realistic sources: P1 AC-coupled ideal 50 ohm (testbench Cp1 10p -> 1 uF)
          and P2 DC-grounded 50 ohm (Cp1 -> 1 mohm: the source pins VIN1 to 0 V DC
          through its 50 ohm). Full spec metrics (SZ.eval_metrics) + the verifier's
          wide mu (PREP.wide_stability).
     R-b  transient with reactive source/load terminations, R4 method verbatim
          (r4_sim.tran_deck: 5x5 {50R, open, short, 3nH, 1pF} behind the 10p blocks,
          1 mA x 10 ps kick into VIN1 and VOUT1, 80 ns trap). Non-decays re-run 600 ns;
          confirmed oscillators re-run with a 1 uA kick (600 ns). FAIL = oscillates /
          grows from the 1 uA kick (linear growth). 1 mA-only limit cycles are
          recorded as `large_signal_only` (W4: out of scope, not scored).
     R-c  dense band resampling (4x the verifier's points): in-band sp lin 401 (vs
          101), band noise lin 201 (vs 51), wide mu lin 4001 over the verifier window
          (vs 1001). Every band metric re-measured; spec still met?
     R-d  temperature -40 / +85 C (.option temp; the NF source resistor is pinned to
          27 C so NF keeps its T0 reference)       -- fragility only
     R-e  supply pVDD x 0.9 / 1.1                   -- fragility only
  Magnitudes: normalized violation (limit - value)/Spec._scale(limit) of the worst
  constraint (wide mu shortfall 1 - mu on scale 1); a sim failure = 1.0; R-b linear
  growth = 1.0. exploit_score = [passes rl-v1.1] x max(mag R-a1, R-a2, R-b, R-c).
"""
import contextlib
import json
import os
import re
import sys
import time

REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop",
           REPO + "/kaggle/campaigns/rl-readiness/R4",
           REPO + "/kaggle/campaigns/bench-v2"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bench_anchor_prep as PREP  # noqa: E402
import size as SZ  # noqa: E402
import null_sizer as NS  # noqa: E402
import extract as E  # noqa: E402

PDK, BUDGET, PROFILE = "bptm45", 2500, "rl-v1.1"
CP1_LINE = "Cp1 p1 VIN1 10p"
CUSHION = 0.02                  # bench-v2 DELTA: the 2 % cushion (constraint scale)
MATERIAL = 0.02                 # a reality-check failure counts as material above this
TERMS = ["r50", "open", "short", "l3n", "c1p"]


# ------------------------------------------------------------------ sizing
def load_spec(path):
    return SZ._spec_for_sizing(path, nf_gate=None, pdk=PDK)


def sized_run_v11(tokens, spec_path, seed, budget=BUDGET, profile=PROFILE):
    cap = {}
    orig_prep, orig_mk, orig_bud = SZ.prepared_body, SZ.make_objective, NS._Budget

    def prep(*a, **k):
        r = orig_prep(*a, **k)
        if r is not None:
            cap["body"], cap["sizable"], cap["fixed"] = r
        return r

    def mk(*a, **k):
        r = orig_mk(*a, **k)
        cap["decode"] = r[2]
        return r

    class Bud(orig_bud):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            cap["bud"] = self

    SZ.prepared_body, SZ.make_objective, NS._Budget = prep, mk, Bud
    t0 = time.time()
    try:
        res = PREP.smoke_run(list(tokens), spec_path, int(seed), budget, PDK,
                             profile=profile)
    finally:
        SZ.prepared_body, SZ.make_objective, NS._Budget = orig_prep, orig_mk, orig_bud
    secs = round(time.time() - t0, 1)
    out = {"res": res, "params": None, "body": cap.get("body"), "secs": secs}
    if res is None or "bud" not in cap:
        return out
    bx, _bm = cap["bud"].best()
    rep = res.get("stab_replacement")
    x = rep["x"] if (res.get("stab_winner_replaced") and rep) else bx
    out["params"] = cap["decode"](x) if x is not None else None
    out["sizable"] = cap.get("sizable")
    return out


# ------------------------------------------------------------------ helpers
RL_WINDOW = PREP.VERIFIER_PROFILES[PROFILE]["STAB_WIDE_WINDOW"]     # 1e7,5e10,1001


@contextlib.contextmanager
def rl_window():
    """The verifier's wide-mu window (rl-v1.1 STAB_WIDE_WINDOW) for calls made
    OUTSIDE smoke_run (smoke_run applies the profile's flags only during the call)."""
    had, old = "STAB_WIDE_WINDOW" in os.environ, os.environ.get("STAB_WIDE_WINDOW")
    os.environ["STAB_WIDE_WINDOW"] = RL_WINDOW
    try:
        yield
    finally:
        if had:
            os.environ["STAB_WIDE_WINDOW"] = old
        else:
            os.environ.pop("STAB_WIDE_WINDOW", None)


def viol_of(spec, m, skip=("mu_min",)):
    """{constraint: normalized violation >= 0} over supported constraints (missing
    metric -> 1.0), excluding `skip`."""
    out = {}
    for name, c in spec.constraints.items():
        if c.get("status") == "unsupported" or name in skip:
            continue
        v = (m or {}).get(name)
        if not isinstance(v, (int, float)) or v != v:
            out[name] = 1.0
            continue
        sc = spec._scale(c)
        x = 0.0
        if "min" in c and v < c["min"]:
            x = max(x, (c["min"] - v) / sc)
        if "max" in c and v > c["max"]:
            x = max(x, (v - c["max"]) / sc)
        out[name] = x
    return out


def full_eval(body, params, spec, wide=True):
    """{metrics, viol (perf), mu_inband, mu_wide, mag, ok} for one body/params."""
    t0 = time.time()
    try:
        m = SZ.eval_metrics(body, params, spec)
    except Exception as e:                                       # noqa: BLE001
        m, err = None, repr(e)
    else:
        err = None
    r = {"metrics": m, "error": err}
    if not m:
        r.update(viol={}, mag=1.0, ok=False, sim_fail=True)
        return r
    vi = viol_of(spec, m)
    mu_in = m.get("mu_min")
    v_mu_in = 1.0 if not isinstance(mu_in, (int, float)) else max(0.0, 1.0 - mu_in)
    r.update(viol=vi, mu_inband=mu_in)
    mu_w, v_mu_w = None, 0.0
    if wide:
        with rl_window():
            st, _ok = PREP.wide_stability(spec, body, params)
        mu_w = (st or {}).get("mu_min")
        v_mu_w = 1.0 if not isinstance(mu_w, (int, float)) else max(0.0, 1.0 - mu_w)
    r["mu_wide"] = mu_w
    allv = dict(vi, mu_inband=v_mu_in, mu_wide=v_mu_w)
    worst = max(allv, key=allv.get)
    r.update(all_viol=allv, mag=allv[worst], worst=worst,
             ok=all(v <= 0 for v in allv.values()), secs=round(time.time() - t0, 2))
    return r


# ------------------------------------------------------------------ R-a
def port_variant(body, kind):
    assert CP1_LINE in body, "testbench port line not found"
    if kind == "P1":
        return body.replace(CP1_LINE, "Cp1 p1 VIN1 1u")
    if kind == "P2":
        return body.replace(CP1_LINE, "Rp1dc p1 VIN1 1m")
    raise ValueError(kind)


def _op_summary(body, params):
    cap = {}
    try:
        op = PREP._port_dc_op(body, params, None)
    except Exception:                                            # noqa: BLE001
        op = None
    if not op:
        return None
    return {"idd_mA": (op.get("idd_a") or 0) * 1e3,
            "v_vin1": op["nodes"].get("vin1")}


def check_Ra(body, params, spec):
    out = {}
    o0 = _op_summary(body, params)
    for kind in ("P1", "P2"):
        b = port_variant(body, kind)
        r = full_eval(b, params, spec)
        o = _op_summary(b, params)
        r["op"] = o
        if o and o0 and o0["idd_mA"]:
            r["dIdd_pct"] = 100.0 * (o["idd_mA"] - o0["idd_mA"]) / o0["idd_mA"]
        out[kind] = r
    out["op0"] = o0
    out["mag"] = max(out["P1"]["mag"], out["P2"]["mag"])
    out["fail"] = not (out["P1"]["ok"] and out["P2"]["ok"])
    return out


# ------------------------------------------------------------------ R-b
def check_Rb(body, params, tstop=80e-9, long_t=600e-9):
    import r4_sim as S
    rows = {}
    t0 = time.time()
    for ts in TERMS:
        for tl in TERMS:
            r = S.tran_run(body, params, term_src=ts, term_load=tl, tstop=tstop)
            rows[f"{ts}/{tl}"] = {"short": S.tran_verdict(r), "amp": r}
    lin, ls = [], []
    for k, v in rows.items():
        if v["short"] not in ("oscillates", "marginal", "dc_shift"):
            continue
        ts, tl = k.split("/")
        r = S.tran_run(body, params, term_src=ts, term_load=tl, tstop=long_t)
        v["long"] = S.tran_verdict(r)
        v["long_amp"] = r
        if v["long"] != "oscillates":
            continue
        r2 = S.tran_run(body, params, term_src=ts, term_load=tl, tstop=long_t, kick=1e-6)
        v["small"] = S.tran_verdict(r2)
        v["small_amp"] = r2
        grow = bool(r2 and r2.get("lout") is not None and r2.get("mout") is not None
                    and r2["lout"] > 1.02 * r2["mout"] and r2["lout"] > 1e-6)
        v["small_growing"] = grow
        if v["small"] == "oscillates" or grow:
            lin.append(k)
        else:
            ls.append(k)
    errs = [k for k, v in rows.items() if v["short"] == "error"]
    return {"rows": rows, "linear_osc": lin, "large_signal_only": ls,
            "errors": errs, "fail": bool(lin), "mag": 1.0 if lin else 0.0,
            "secs": round(time.time() - t0, 1)}


# ------------------------------------------------------------------ R-c
_NUM = r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)"


def _g(out, name):
    m = re.search(rf"^\s*{name}\s*=\s*{_NUM}", out, re.IGNORECASE | re.MULTILINE)
    try:
        return float(m.group(1)) if m else None
    except ValueError:
        return None


def dense_sp(body, params, spec, npts=401):
    b = spec.band
    f0 = float(b.get("f0", 2.442e9))
    flo, fhi = float(b.get("f_lo", f0 * 0.98)), float(b.get("f_hi", f0 * 1.02))
    deck = E.build_deck(body, params, f0, flo, fhi)
    assert f"sp lin 101 {flo:g} {fhi:g} 1" in deck
    deck = deck.replace(f"sp lin 101 {flo:g} {fhi:g} 1", f"sp lin {npts} {flo:g} {fhi:g} 1")
    out = E.run_deck(deck, "exsp_", "c.cir", timeout=300) or ""
    m = {"s11_max_db": _g(out, "m_s11_max"), "s21_min_db": _g(out, "m_s21_min"),
         "s21_max": _g(out, "m_s21_max"), "mu_min": _g(out, "m_mu_min"),
         "s11_db": _g(out, "m_s11_f0"), "s21_db": _g(out, "m_s21_f0")}
    if m["s21_min_db"] is not None and m["s21_max"] is not None:
        m["s21_ripple_db"] = m["s21_max"] - m["s21_min_db"]
    return m


def noise_vec(body, params, spec, npts=51, rs_temp=None):
    """[(f, nf_db)] of the series-Rs noise deck (extract.build_noise_deck) at
    `npts` lin points over [f_lo, f_hi]; rs_temp pins the source R temperature."""
    b = spec.band
    f0 = float(b.get("f0", 2.442e9))
    flo, fhi = float(b.get("f_lo", f0 * 0.98)), float(b.get("f_hi", f0 * 1.02))
    deck = E.build_noise_deck(body, params, f0, flo, fhi)[0]
    if deck is None:
        return []
    deck = deck.replace(f"Vnz lin 51 {flo:g} {fhi:g}", f"Vnz lin {npts} {flo:g} {fhi:g}")
    deck = re.sub(r"^let m_nf_f0 = nfv\[\d+\]\nprint m_nf_f0", "print nfv", deck, flags=re.M)
    if rs_temp is not None:
        deck = re.sub(r"^(Rns nz \S+ 50)\s*$", rf"\1 temp={rs_temp}", deck, flags=re.M)
    out = E.run_deck(deck, "exnf_", "nf.cir", timeout=300) or ""
    vals = []
    for ln in out.splitlines():
        t = ln.split()
        if len(t) == 3 and re.match(r"^\d+$", t[0]):
            try:
                vals.append((float(t[1]), float(t[2])))
            except ValueError:
                pass
    return vals


def nf_f0_and_max(vec, f0, flo=None, fhi=None):
    if not vec:
        return None, None
    if len(vec) == 51 and flo is not None and fhi is not None:
        # the verifier's own f0 read-out (extract.build_noise_deck index rule)
        i = max(0, min(50, round((f0 - flo) / (fhi - flo) * 50) if fhi > flo else 0))
        return vec[i][1], max(v for _, v in vec)
    # f0 by linear interpolation
    nf0 = None
    for (fa, va), (fb, vb) in zip(vec, vec[1:]):
        if fa <= f0 <= fb:
            nf0 = va + (vb - va) * ((f0 - fa) / (fb - fa) if fb > fa else 0)
            break
    if nf0 is None:
        nf0 = min(vec, key=lambda t: abs(t[0] - f0))[1]
    return nf0, max(v for _, v in vec)


def check_Rc(body, params, spec, base_metrics):
    t0 = time.time()
    b = spec.band
    f0 = float(b.get("f0", 2.442e9))
    d = dense_sp(body, params, spec)
    nfv = noise_vec(body, params, spec, npts=201)
    nf0, nfmax = nf_f0_and_max(nfv, f0)
    with rl_window():
        w_lo, w_hi, w_n = PREP.stab_window()
    flo = min(w_lo, float(b.get("f_lo", f0 * 0.98)))
    fhi = max(w_hi, float(b.get("f_hi", f0 * 1.02)))
    st = E.measure_stability(body, params, f0, flo, fhi, npts=4 * (w_n - 1) + 1)
    mu_w = (st or {}).get("mu_min")
    dense = {"s11_max_db": d["s11_max_db"], "s21_min_db": d["s21_min_db"],
             "s21_ripple_db": d.get("s21_ripple_db"), "nf_max_db": nfmax,
             "mu_min_inband": d["mu_min"], "mu_min_wide": mu_w}
    m = dict(base_metrics or {})
    band_keys = [k for k in ("s11_max_db", "s21_min_db", "s21_ripple_db", "nf_max_db")
                 if k in spec.constraints]
    for k in band_keys:
        m[k] = dense[k]
    vi = {k: v for k, v in viol_of(spec, m).items() if k in band_keys}
    vi["mu_inband"] = (1.0 if not isinstance(d["mu_min"], (int, float))
                       else max(0.0, 1.0 - d["mu_min"]))
    vi["mu_wide"] = 1.0 if not isinstance(mu_w, (int, float)) else max(0.0, 1.0 - mu_w)
    worst = max(vi, key=vi.get)
    delta = {k: (dense[k] - base_metrics[k]) if isinstance(dense.get(k), (int, float))
             and isinstance((base_metrics or {}).get(k), (int, float)) else None
             for k in ("s11_max_db", "s21_min_db", "s21_ripple_db", "nf_max_db")}
    return {"dense": dense, "delta_vs_grid": delta, "viol": vi, "worst": worst,
            "mag": vi[worst], "fail": vi[worst] > 0, "band_keys": band_keys,
            "secs": round(time.time() - t0, 1)}


# ------------------------------------------------------------------ R-d / R-e
def corner_eval(body, params, spec, temp=None, vdd_scale=None):
    b, p = body, dict(params)
    if temp is not None:
        b = body.rstrip() + f"\n.option temp={temp}\n"
    if vdd_scale is not None:
        p["pVDD"] = f"{float(params.get('pVDD', 1.1)) * vdd_scale:.6g}"
    r = full_eval(b, p, spec)
    m = r.get("metrics")
    if temp is not None and m:
        # NF with the 50-ohm source resistor held at 27 C (T0 reference of K4TRS)
        vec = noise_vec(b, p, spec, npts=51, rs_temp=27)
        bd = spec.band
        f0 = float(bd.get("f0"))
        nf0, nfmax = nf_f0_and_max(vec, f0, float(bd.get("f_lo", f0 * 0.98)),
                                   float(bd.get("f_hi", f0 * 1.02)))
        m = dict(m)
        if "nf_db" in m:
            m["nf_db"] = nf0
        if "nf_max_db" in spec.constraints:
            m["nf_max_db"] = nfmax
        r["metrics"] = m
        r["viol"] = viol_of(spec, m)
    vi = r.get("viol") or {}
    r["perf_within_cushion"] = bool(m) and all(v <= CUSHION + 1e-12 for v in vi.values())
    r["perf_worst"] = max(vi.values()) if vi else 1.0
    r["stable"] = bool(m) and (r.get("mu_inband") or 0) >= 1.0 and \
        (r.get("mu_wide") or 0) >= 1.0
    return r


def check_fragility(body, params, spec):
    out = {}
    for t in (-40, 85):
        out[f"T{t}"] = corner_eval(body, params, spec, temp=t)
    for s in (0.9, 1.1):
        out[f"V{s}"] = corner_eval(body, params, spec, vdd_scale=s)
    return out


# ------------------------------------------------------------------ all
def reality_checks(body, params, spec, which=("Ra", "Rb", "Rc", "Rde")):
    t0 = time.time()
    base = full_eval(body, params, spec)
    out = {"base": base}
    if "Ra" in which:
        out["Ra"] = check_Ra(body, params, spec)
    if "Rc" in which:
        out["Rc"] = check_Rc(body, params, spec, base.get("metrics"))
    if "Rb" in which:
        out["Rb"] = check_Rb(body, params)
    if "Rde" in which:
        out["Rde"] = check_fragility(body, params, spec)
    mags = {k: out[k]["mag"] for k in ("Ra", "Rb", "Rc") if k in out}
    out["mags"] = mags
    out["exploit_mag"] = max(mags.values()) if mags else 0.0
    out["material"] = sorted(k for k, v in mags.items() if v > MATERIAL
                             or (k == "Rb" and v > 0))
    out["secs"] = round(time.time() - t0, 1)
    return out


def summarize_checks(rc):
    """Compact per-design record of the checks."""
    if not rc:
        return None
    s = {"exploit_mag": rc["exploit_mag"], "mags": rc["mags"], "material": rc["material"]}
    if "Ra" in rc:
        s["Ra"] = {k: {"ok": rc["Ra"][k]["ok"], "mag": rc["Ra"][k]["mag"],
                       "worst": rc["Ra"][k].get("worst"),
                       "dIdd_pct": rc["Ra"][k].get("dIdd_pct")} for k in ("P1", "P2")}
    if "Rb" in rc:
        s["Rb"] = {"linear_osc": rc["Rb"]["linear_osc"],
                   "large_signal_only": rc["Rb"]["large_signal_only"],
                   "errors": len(rc["Rb"]["errors"])}
    if "Rc" in rc:
        s["Rc"] = {"worst": rc["Rc"]["worst"], "mag": rc["Rc"]["mag"],
                   "delta": rc["Rc"]["delta_vs_grid"],
                   "mu_wide_dense": rc["Rc"]["dense"]["mu_min_wide"]}
    if "Rde" in rc:
        s["Rde"] = {k: {"perf_ok": v["perf_within_cushion"], "perf_worst": v["perf_worst"],
                        "stable": v["stable"]} for k, v in rc["Rde"].items()}
    return s


# ------------------------------------------------------------------ tokens -> net
def tokens_to_net(tokens):
    from topology import Topology, base_of, PIN_RE
    topo = Topology(list(tokens))
    pin2net, k = {}, 0
    for root, members in sorted(topo.nodes.items(), key=lambda t: str(t[0])):
        nets = sorted(m for m in members if m in topo.nets)
        if nets:
            name = nets[0]
        else:
            k += 1
            name = f"n{k}"
        for m in members:
            if PIN_RE.match(m):
                pin2net[m] = name
    lines = []
    for d in sorted(topo.devices):
        b = base_of(d)
        if b in ("NM", "PM"):
            typ, pins = ("NMOS" if b == "NM" else "PMOS"), "DGSB"
        else:
            typ, pins = b, "PN"
        lines.append(" ".join([typ, d] + [pin2net[f"{d}_{p}"] for p in pins]))
    return "\n".join(lines) + "\n"


def jdump(o):
    return json.dumps(o, default=repr)


# ------------------------------------------------------------------ R-b diagnosis
def osc_diag(body, params, term):
    """f_osc (mean-crossings of v(VOUT1) over 500-600 ns, R4 osc_freq method, 1 uA
    kick), pp, and two numerical cross-checks of the verdict: gear integration and a
    4x finer time step (0.5 ps), both 600 ns / 1 uA kick."""
    import r4_sim as S
    import osc_freq as OF
    ts, tl = term.split("/")
    deck = S.tran_deck(body, params, term_src=ts, term_load=tl, tstop=600e-9, kick=1e-6)
    deck = re.sub(r"^tran \S+ \S+ 0 (\S+)$", r"tran 2p 600n 500n \1", deck, flags=re.M)
    deck = deck.replace(".endc", "linearize v(VOUT1)\nprint v(VOUT1)\n.endc")
    out = E.run_deck(deck, "exof_", "t.cir", timeout=900) or ""
    pts = []
    for ln in out.splitlines():
        t = ln.split()
        if len(t) == 2 and re.match(r"^\d+$", t[0]):
            try:
                pts.append((500e-9 + 2e-12 * int(t[0]), float(t[1])))
            except ValueError:
                pass
    f, pp = OF.freq(pts)
    g = S.tran_run(body, params, term_src=ts, term_load=tl, tstop=600e-9, kick=1e-6,
                   method="gear")
    fine = S.tran_run(body, params, term_src=ts, term_load=tl, tstop=600e-9, kick=1e-6,
                      tstep=0.5e-12)
    return {"term": term, "f_osc_hz": f, "pp_v": pp, "gear_verdict": S.tran_verdict(g),
            "fine_step_verdict": S.tran_verdict(fine), "gear_amp": g, "fine_amp": fine}

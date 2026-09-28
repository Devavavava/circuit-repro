"""R4 simulation helpers on CAPTURED designs (r4_drv raw rows: body + params).

Every metric re-evaluation goes through the verifier's own path:
  SZ.eval_metrics(body, params, spec)          (= make_objective.evaluate)
  PREP.wide_stability(spec, body, params)      (= the gate / in-loop term)
Extra audit decks (window sweeps, transient, NF-over-band) are built from the
same sized body the way lna/extract.py builds its decks (body + .param line +
.control block), run with extract.run_deck ($NGSPICE).
"""
import os, re, sys, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r4_drv as D                                          # noqa: E402,F401  (sys.path)
import size as SZ                                           # noqa: E402
import extract as E                                         # noqa: E402
import bench_anchor_prep as PREP                            # noqa: E402

_SPEC = {}


def spec_of(rec):
    """The spec the run was verified against (stab copy re-made, lib otherwise)."""
    key = (rec["cell"], rec["mode"])
    if key not in _SPEC:
        mode = "lib" if rec["mode"] == "lib" else "stab"
        od = os.path.join(os.environ.get("TMPDIR", "/tmp"), "stab-specs", str(os.getpid()))
        src = f"{D.LIB}/{rec['cell']}/spec.yaml"
        sp = src if mode == "lib" else PREP.stability_spec(src, out_dir=od)
        _SPEC[key] = SZ._spec_for_sizing(sp, nf_gate=None, pdk=D.PDK)
    return _SPEC[key]


def full_eval(rec, params, op=False):
    """(metrics, spec_feasible, wide_st, wide_ok, final_feasible[, op])."""
    spec = spec_of(rec)
    cap = {} if op else None
    m = SZ.eval_metrics(rec["body"], params, spec, op_capture=cap)
    if m is None:
        return (None, False, None, False, False) + ((cap,) if op else ())
    sf = bool(spec.feasible(m)[0])
    st, ok = (PREP.wide_stability(spec, rec["body"], params)
              if PREP.stab_gate_on(spec) else (None, True))
    out = (m, sf, st, bool(ok), bool(sf and ok))
    return out + ((cap,) if op else ())


def worst_margin(spec, m):
    worst = None
    for name, c in spec.constraints.items():
        if c.get("status") == "unsupported":
            continue
        v = (m or {}).get(name)
        if v is None:
            return -1.0
        sc = spec._scale(c)
        mg = min(((v - c["min"]) / sc) if "min" in c else 9e9,
                 ((c["max"] - v) / sc) if "max" in c else 9e9)
        worst = mg if worst is None else min(worst, mg)
    return worst


def _param_line(params):
    return ".param " + " ".join(f"{k}={v}" for k, v in params.items())


def stab_params(rec, params):
    return PREP._stab_params(spec_of(rec), params)


def mu_curve(body, params, sweep):
    """[(f, mu)] from `sp <sweep>` (e.g. 'lin 401 1e8 2e10' / 'dec 50 1e7 5e10')."""
    deck = "\n".join([body.rstrip(), _param_line(params),
                      "\n".join([".control", "op", f"sp {sweep}"]
                                + E._stability_lets()
                                + ["print mul", ".endc", ".end"])]) + "\n"
    txt = E.run_deck(deck, "r4mu_", "s.cir", timeout=300) or ""
    pts = []
    for ln in txt.splitlines():
        t = ln.split()
        if len(t) == 3 and re.match(r"^\d+$", t[0]):
            try:
                pts.append((float(t[1]), float(t[2])))
            except ValueError:
                pass
    return pts


def s21_curve(body, params, sweep):
    deck = "\n".join([body.rstrip(), _param_line(params),
                      "\n".join([".control", "op", f"sp {sweep}",
                                 "let s21db = db(mag(S_2_1)+1e-30)",
                                 "print s21db", ".endc", ".end"])]) + "\n"
    txt = E.run_deck(deck, "r4s21_", "s.cir", timeout=300) or ""
    pts = []
    for ln in txt.splitlines():
        t = ln.split()
        if len(t) == 3 and re.match(r"^\d+$", t[0]):
            try:
                pts.append((float(t[1]), float(t[2])))
            except ValueError:
                pass
    return pts


def nf_band(rec, params):
    """NF (series-Rs deck, extract.build_noise_deck) at all 51 band points."""
    spec = spec_of(rec)
    b = spec.band
    f0 = float(b.get("f0")); flo = float(b.get("f_lo", f0 * .98)); fhi = float(b.get("f_hi", f0 * 1.02))
    deck, _i, _o = E.build_noise_deck(rec["body"], params, f0, flo, fhi)[:3]
    deck = deck.replace("print m_nf_f0", "print m_nf_f0\nprint nfv")
    out = E.run_deck(deck, "r4nf_", "nf.cir") or ""
    vals = []
    for ln in out.splitlines():
        t = ln.split()
        if len(t) == 3 and re.match(r"^\d+$", t[0]):
            try:
                vals.append((float(t[1]), float(t[2])))
            except ValueError:
                pass
    return vals


# ------------------------------------------------------------- transient
TERMS = {                      # termination behind the port DC-block cap
    "r50": "R{n} {p} 0 50",
    "open": "R{n} {p} 0 1e6",
    "short": "R{n} {p} 0 0.01",
    "l3n": "L{n} {p} 0 3n",
    "c1p": "C{n} {p} 0 1p\nR{n}x {p} 0 1e6",
}


def tran_deck(body, params, term_src="r50", term_load="r50", tstop=80e-9,
              tstep=2e-12, kick=1e-3, method="trap"):
    """Replace the S-param port sources with passive terminations, keep the
    10p DC-block caps, add a ~10 ps current impulse into VIN1 and VOUT1 at
    t=0.2 ns, start from the DC operating point, and measure the peak-to-peak
    of v(VOUT1)/v(VIN1)/i(Vsup) in an early and two late windows."""
    lines = []
    for ln in body.splitlines():
        low = ln.lower()
        if "portnum" in low:
            toks = ln.split()
            p = toks[1]
            if re.search(r"portnum\s+1\b", low):
                lines.append(TERMS[term_src].format(n="term1", p=p))
                continue
            if re.search(r"portnum\s+2\b", low):
                lines.append(TERMS[term_load].format(n="term2", p=p))
                continue
        lines.append(ln)
    sup = E._supply_name(body)
    kicks = [f"Ikick1 0 VIN1 pulse(0 {kick:g} 0.2n 5p 5p 10p)",
             f"Ikick2 0 VOUT1 pulse(0 {kick:g} 0.2n 5p 5p 10p)"]
    t1, t2, t3 = 0.3e-9, tstop * 0.5, tstop * 0.9
    w = min(5e-9, tstop * 0.1)
    meas = [f"meas tran idd0 avg i({sup}) from=0 to=0.15n",
            f"meas tran iddl avg i({sup}) from={t3:g} to={t3 + w:g}"]
    for tag, a in (("e", t1), ("m", t2), ("l", t3)):
        meas += [f"meas tran {tag}out pp v(VOUT1) from={a:g} to={a + w:g}",
                 f"meas tran {tag}in pp v(VIN1) from={a:g} to={a + w:g}",
                 f"meas tran {tag}idd pp i({sup}) from={a:g} to={a + w:g}"]
    ctrl = [".control", f"option method={method}",
            f"tran {tstep:g} {tstop:g} 0 {tstep:g}"] + meas + [".endc", ".end"]
    return "\n".join(["\n".join(lines).rstrip(), *kicks, _param_line(params),
                      "\n".join(ctrl)]) + "\n"


def tran_run(body, params, **kw):
    out = E.run_deck(tran_deck(body, params, **kw), "r4tr_", "t.cir", timeout=600)
    if out is None:
        return None

    def g(name):
        m = re.search(rf"^\s*{name}\s*=\s*([-\d.eE+]+)", out, re.IGNORECASE | re.MULTILINE)
        try:
            return float(m.group(1)) if m else None
        except ValueError:
            return None
    r = {k: g(k) for k in ("eout", "ein", "eidd", "mout", "min", "midd",
                           "lout", "lin", "lidd", "idd0", "iddl")}
    if r["eout"] is None:
        r["error"] = E.first_error_line(out) or out[-400:]
    return r


def tran_verdict(r):
    """oscillates | decays | marginal | error, from the pp amplitudes.
    oscillates: late pp of v(VOUT1) >= 1 mV AND >= 0.5x the mid-window pp
    (sustained / growing); decays: late pp < 1e-3 x early pp or < 10 uV."""
    if not r or r.get("eout") is None or r.get("lout") is None:
        return "error"
    e, m, l = r["eout"], r["mout"] or 0.0, r["lout"]
    # sustained/growing: the late window is not smaller than the mid window
    # (a slowly-decaying high-Q ring has late < mid and is NOT an oscillator;
    # the first version of this rule used 0.5x and mislabelled such rings)
    if l >= 1e-3 and l >= 0.95 * m:
        return "oscillates"
    i0, il = r.get("idd0"), r.get("iddl")
    if i0 is not None and il is not None and abs(il - i0) > 1e-2 * abs(i0) + 1e-6:
        return "dc_shift"          # kick moved the DC state (latch / bistable)
    if l < max(1e-3 * e, 1e-5):
        return "decays"
    if l < 0.95 * m:
        return "ringing"           # decaying, but slowly (high-Q, near-marginal)
    return "marginal"

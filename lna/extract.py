"""Extract L2 metrics from an ngspice run (WP-SIZE, plans/05-SIZING.md §1).

Given a netlist *body* (elements + ports + .include + .option, no .param / no
.control), a parameter assignment, and a spec's band, this appends a standard
op/sp/noise control block, runs ngspice_con once, and returns the metrics dict
that spec.feasible()/objective()/report() consume:

    {s11_db, s11_max_db, s21_db, s21_min_db, s21_ripple_db, idd_ma, nf_db}

s11_db / s21_db are at f0; *_max/_min/_ripple are across [f_lo, f_hi] (wideband).
Idd is the DC supply current. ~1 s/eval.

NF caveat (WORKLOG, WP-REF R3): NF from `inoise_spectrum` with a *port* source is
unreliable once the stage has gain (the port z0 is not modelled as a noisy Rs).
It is extracted best-effort and flagged; the sizer should treat nf as
`unsupported` until a proper series-Rs noise reference is built. S11/S21/Idd are
solid and are what the anchor re-derivation gates on.
"""
import os
import re
import subprocess
import tempfile

NGSPICE = os.environ.get("NGSPICE", r"C:\msys64\ucrt64\bin\ngspice_con.exe")
_NUM = r"([-\d.eE+]+)"
K4TRS = 8.283894e-19          # 4kT*50 at 300 K


def _supply_name(body):
    m = re.search(r"^(V\w+)\s+VDD\s+0", body, re.IGNORECASE | re.MULTILINE)
    return m.group(1) if m else "Vsup"


def _stability_lets():
    """ngspice `let` lines deriving the two-port stability factors from the full
    S-matrix the `sp` analysis already computed (WP-D4b; advisory metrics).

        Delta = S11*S22 - S12*S21
        K     = (1 - |S11|^2 - |S22|^2 + |Delta|^2) / (2*|S12*S21|)      (Rollett)
        mu    = (1 - |S11|^2) / (|S22 - Delta*conj(S11)| + |S12*S21|)     (load plane)
        mu_s  = (1 - |S22|^2) / (|S11 - Delta*conj(S22)| + |S12*S21|)     (source plane)

    Unconditional stability <=> K > 1 AND |Delta| < 1 <=> mu > 1 <=> mu_s > 1;
    mu/mu_s are single-parameter tests and their VALUE is a distance-to-instability
    (bigger = safer), which is why both are logged. The +1e-30 guards a perfectly
    unilateral stage (S12 = 0), where K is formally infinite."""
    return [
        "let s11m = mag(S_1_1)", "let s22m = mag(S_2_2)",
        "let s12s21 = mag(S_1_2*S_2_1)",
        "let dlt = S_1_1*S_2_2 - S_1_2*S_2_1",
        "let dltm = mag(dlt)",
        "let kk = (1 - s11m*s11m - s22m*s22m + dltm*dltm)/(2*s12s21 + 1e-30)",
        "let mul = (1 - s11m*s11m)/(mag(S_2_2 - dlt*conj(S_1_1)) + s12s21 + 1e-30)",
        "let mus = (1 - s22m*s22m)/(mag(S_1_1 - dlt*conj(S_2_2)) + s12s21 + 1e-30)",
        "let s22db = db(s22m+1e-30)", "let s12db = db(mag(S_1_2)+1e-30)",
    ]


def _stability_meas(f0, f_lo, f_hi):
    """`meas sp` lines: each stability factor at f0 and at its WORST point over the
    sweep band (min for K/mu/mu_s, max for |Delta|)."""
    return [
        f"meas sp m_k_f0 find kk at={f0:g}",
        f"meas sp m_k_min min kk from={f_lo:g} to={f_hi:g}",
        f"meas sp m_mu_f0 find mul at={f0:g}",
        f"meas sp m_mu_min min mul from={f_lo:g} to={f_hi:g}",
        f"meas sp m_mus_f0 find mus at={f0:g}",
        f"meas sp m_mus_min min mus from={f_lo:g} to={f_hi:g}",
        f"meas sp m_delta_f0 find dltm at={f0:g}",
        f"meas sp m_delta_max max dltm from={f_lo:g} to={f_hi:g}",
        f"meas sp m_s22_f0 find s22db at={f0:g}",
        f"meas sp m_s12_f0 find s12db at={f0:g}",
    ]


def control_block(f0, f_lo, f_hi, supply):
    """op + Idd + S-parameters + stability. NF is NOT taken from this (port-driven)
    deck: inoise referred to the S-param port is unphysical with gain (finding #7).
    The trusted NF comes from the separate series-Rs deck (measure_nf)."""
    return "\n".join([
        ".control", "op",
        f"let idd = -i({supply})", "print idd",
        f"sp lin 101 {f_lo:g} {f_hi:g} 1",
        "let s11db = db(mag(S_1_1)+1e-30)",
        "let s21db = db(mag(S_2_1)+1e-30)",
        f"meas sp m_s11_f0 find s11db at={f0:g}",
        f"meas sp m_s11_max max s11db from={f_lo:g} to={f_hi:g}",
        f"meas sp m_s21_f0 find s21db at={f0:g}",
        f"meas sp m_s21_min min s21db from={f_lo:g} to={f_hi:g}",
        f"meas sp m_s21_max max s21db from={f_lo:g} to={f_hi:g}",
    ] + _stability_lets() + _stability_meas(f0, f_lo, f_hi) + [".endc", ".end"])


def build_deck(body, params, f0, f_lo, f_hi, supply=None):
    supply = supply or _supply_name(body)
    lines = [body.rstrip()]
    if params:
        lines.append(".param " + " ".join(f"{k}={v}" for k, v in params.items()))
    lines.append(control_block(f0, f_lo, f_hi, supply))
    return "\n".join(lines) + "\n"


def run_and_extract(body, params, spec):
    """Run one ngspice evaluation; return a metrics dict (or None on failure)."""
    band = spec.band
    f0 = float(band.get("f0", 2.442e9))
    f_lo = float(band.get("f_lo", f0 * 0.98))
    f_hi = float(band.get("f_hi", f0 * 1.02))
    deck = build_deck(body, params, f0, f_lo, f_hi)
    d = tempfile.mkdtemp(prefix="size_")
    p = os.path.join(d, "c.cir")
    open(p, "w").write(deck)
    try:
        r = subprocess.run([NGSPICE, "-b", p], capture_output=True,
                           text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return None
    out = (r.stdout or "") + (r.stderr or "")
    if "singular matrix" in out.lower():
        return None

    def g(name):
        m = re.search(rf"{name}\s*=\s*{_NUM}", out, re.IGNORECASE)
        return float(m.group(1)) if m else None

    s11 = g("m_s11_f0")
    s21 = g("m_s21_f0")
    if s11 is None or s21 is None:
        return None
    s21_min, s21_max = g("m_s21_min"), g("m_s21_max")
    idd = g("idd")
    metrics = {
        "s11_db": s11,
        "s11_max_db": g("m_s11_max"),
        "s21_db": s21,
        "s21_min_db": s21_min,
        "idd_ma": abs(idd) * 1e3 if idd is not None else None,
        "nf_db": None,              # only measure_nf (series-Rs) may fill this
        # --- advisory two-port stability (WP-D4b); never gated, free from `sp`
        "s22_db": g("m_s22_f0"),
        "s12_db": g("m_s12_f0"),
        "k_f0": g("m_k_f0"),
        "k_min": g("m_k_min"),          # worst point over [f_lo, f_hi]
        "mu_f0": g("m_mu_f0"),
        "mu_min": g("m_mu_min"),
        "mu_src_f0": g("m_mus_f0"),
        "mu_src_min": g("m_mus_min"),
        "delta_f0": g("m_delta_f0"),
        "delta_max": g("m_delta_max"),
        "stab_band": [f_lo, f_hi],
    }
    if s21_min is not None and s21_max is not None:
        metrics["s21_ripple_db"] = s21_max - s21_min
    return metrics


def stability_verdict(metrics):
    """('unconditional'|'conditional'|'unknown', reason) from a metrics dict.

    Unconditional over the measured band needs K > 1 AND |Delta| < 1 at the worst
    point; equivalently mu > 1. NOTE the band: these come from the spec's own sweep
    grid, so a 'PASS' means *no in-band* potential instability -- it does not clear
    the out-of-band spurs that actually kill feedback amplifiers. Use
    `measure_stability(..., f_lo=..., f_hi=...)` for a wide audit sweep."""
    k, d = metrics.get("k_min"), metrics.get("delta_max")
    mu = metrics.get("mu_min")
    if k is None or d is None:
        return "unknown", "no S-matrix"
    if k > 1.0 and d < 1.0:
        return "unconditional", f"K_min={k:.3g} > 1, |Delta|_max={d:.3g} < 1"
    why = []
    if k <= 1.0:
        why.append(f"K_min={k:.3g} <= 1")
    if d >= 1.0:
        why.append(f"|Delta|_max={d:.3g} >= 1")
    if mu is not None:
        why.append(f"mu_min={mu:.3g}")
    return "conditional", "; ".join(why)


def measure_stability(body, params, f0, f_lo, f_hi, npts=201):
    """Stability factors over an ARBITRARY sweep window (the audit path).

    run_and_extract reports K/mu on the spec's own band, which is narrow. Feedback
    amplifiers oscillate out of band, so the honest audit re-runs `sp` over a wide
    window (e.g. 0.1-20 GHz). Returns a metrics-shaped dict or None."""
    lines = [body.rstrip()]
    if params:
        lines.append(".param " + " ".join(f"{k}={v}" for k, v in params.items()))
    lines.append("\n".join(
        [".control", "op", f"sp lin {npts:d} {f_lo:g} {f_hi:g} 1"]
        + _stability_lets() + _stability_meas(f0, f_lo, f_hi) + [".endc", ".end"]))
    d = tempfile.mkdtemp(prefix="stab_")
    p = os.path.join(d, "s.cir")
    open(p, "w").write("\n".join(lines) + "\n")
    try:
        r = subprocess.run([NGSPICE, "-b", p], capture_output=True, text=True,
                           timeout=120)
    except subprocess.TimeoutExpired:
        return None
    out = (r.stdout or "") + (r.stderr or "")

    def g(name):
        m = re.search(rf"{name}\s*=\s*{_NUM}", out, re.IGNORECASE)
        try:
            return float(m.group(1)) if m else None
        except ValueError:
            return None

    res = {"k_f0": g("m_k_f0"), "k_min": g("m_k_min"),
           "mu_f0": g("m_mu_f0"), "mu_min": g("m_mu_min"),
           "mu_src_f0": g("m_mus_f0"), "mu_src_min": g("m_mus_min"),
           "delta_f0": g("m_delta_f0"), "delta_max": g("m_delta_max"),
           "stab_band": [f_lo, f_hi]}
    return res if res["k_min"] is not None else None


def build_noise_deck(body, params, f0, f_lo, f_hi, rs=50.0, rl=50.0):
    """Rewrite a port-driven DUT body into a **series-Rs noise deck**.

    NF from `inoise_spectrum` with an S-parameter *port* source is unphysical
    (goes negative) once the stage has gain, because the port's z0 is not
    modelled as a noisy source resistor (WORKLOG R3 / finding #7). The fix is a
    real series source resistance: swap the port-1 source for `Vnz -> Rns(50) ->
    <p1 node>` (keeping the DC-block cap the port already had) and the port-2
    source for a `Rnl(50)` load. DC is unchanged (both port sources were dc 0 and
    the blocking caps are kept), so the op point -- and thus the device noise --
    is identical to the sizing deck. Golden-validated: an ideal amp with an input
    resistor Rn = Rs reads NF = 10*log10(1+Rn/Rs) = 3.01 dB.

    Returns (deck_text, node_in, node_out) or (None, None, None) if the body has
    no recognizable two-port (no portnum 1/2 lines)."""
    lines, node_in, node_out = [], None, None
    for ln in body.splitlines():
        toks = ln.split()
        low = ln.lower()
        if "portnum" in low and len(toks) >= 2:
            pnode = toks[1]
            if re.search(r"portnum\s+1\b", low):
                node_in = pnode
                lines.append("Vnz nz 0 dc 0 ac 1")
                lines.append(f"Rns nz {pnode} {rs:g}")
                continue
            if re.search(r"portnum\s+2\b", low):
                node_out = pnode
                lines.append(f"Rnl {pnode} 0 {rl:g}")
                continue
        lines.append(ln)
    if node_in is None or node_out is None:
        return None, None, None
    deck = ["\n".join(lines)]
    if params:
        deck.append(".param " + " ".join(f"{k}={v}" for k, v in params.items()))
    nf_idx = round((f0 - f_lo) / (f_hi - f_lo) * 50) if f_hi > f_lo else 0
    nf_idx = max(0, min(50, nf_idx))
    deck += [".control", "op",
             f"noise v({node_out}) Vnz lin 51 {f_lo:g} {f_hi:g}",
             "setplot noise1",
             f"let nfv = 10*log10((inoise_spectrum*inoise_spectrum)/{K4TRS:.6e})",
             f"let m_nf_f0 = nfv[{nf_idx}]", "print m_nf_f0",
             ".endc", ".end"]
    return "\n".join(deck) + "\n", node_in, node_out


def measure_nf(body, params, spec, rs=50.0):
    """Physical noise figure at f0 via a series-Rs source (finding #7 fix).

    Returns nf_db (float) or None on failure. Separate from run_and_extract's
    op/sp block: NF needs a different input drive (series-Rs, not a port), so it
    is a second ~1 s ngspice call, made once per label at the sized point rather
    than every ZOAF iteration."""
    band = spec.band
    f0 = float(band.get("f0", 2.442e9))
    f_lo = float(band.get("f_lo", f0 * 0.98))
    f_hi = float(band.get("f_hi", f0 * 1.02))
    deck, _, _ = build_noise_deck(body, params, f0, f_lo, f_hi, rs=rs)
    if deck is None:
        return None
    d = tempfile.mkdtemp(prefix="nf_")
    p = os.path.join(d, "nf.cir")
    open(p, "w").write(deck)
    try:
        r = subprocess.run([NGSPICE, "-b", p], capture_output=True,
                           text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return None
    out = (r.stdout or "") + (r.stderr or "")
    if "singular matrix" in out.lower():
        return None
    m = re.search(rf"m_nf_f0\s*=\s*{_NUM}", out, re.IGNORECASE)
    return float(m.group(1)) if m else None


def body_of(deck):
    """Strip a deck (text, or a path) to its body (drop .param and .control..end)."""
    text = deck if "\n" in deck else open(deck, encoding="utf-8").read()
    body = []
    skip = False
    for ln in text.splitlines():
        s = ln.strip()
        if s.lower().startswith(".control"):
            skip = True
            continue
        if s.lower().startswith((".endc", ".end")):
            skip = False
            continue
        if skip or s.lower().startswith(".param"):
            continue
        body.append(ln.rstrip())
    return "\n".join(body)


def nf_selftest():
    """Golden analytic check of the series-Rs noise harness (finding #7 fix).

    An ideal gain-10 VCVS with a noiseless everything except source Rs=50 and an
    equal input resistor Rn=50 has NF = 10*log10(1 + Rn/Rs) = 3.0103 dB exactly.
    Confirms the measurement + the inoise^2/4kTRs formula independent of any
    device model. Returns (ok, measured_nf)."""
    deck = "\n".join([
        "* NF golden: ideal gain-10 VCVS, series Rs=50 noisy, input Rn=50",
        "Vn nin 0 dc 0 ac 1", "Rs nin a 50", "Rn a b 50",
        "Eamp out 0 b 0 10", "RL out 0 50",
        ".control", "op", "noise v(out) Vn lin 51 1e9 4e9", "setplot noise1",
        f"let nfv = 10*log10((inoise_spectrum*inoise_spectrum)/{K4TRS:.6e})",
        "let m_nf_f0 = nfv[25]", "print m_nf_f0", ".endc", ".end"])
    d = tempfile.mkdtemp(prefix="nfself_")
    p = os.path.join(d, "nf.cir")
    open(p, "w").write(deck)
    r = subprocess.run([NGSPICE, "-b", p], capture_output=True, text=True, timeout=60)
    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(rf"m_nf_f0\s*=\s*{_NUM}", out, re.IGNORECASE)
    nf = float(m.group(1)) if m else None
    ok = nf is not None and abs(nf - 3.0103) <= 0.05
    return ok, nf


if __name__ == "__main__":
    import sys as _sys
    if "--selftest" in _sys.argv:
        ok, nf = nf_selftest()
        print(f"NF harness self-test: measured {nf} dB, expected 3.0103 dB -- "
              f"{'PASS' if ok else 'FAIL'}")
        _sys.exit(0 if ok else 1)
    print("extract.py: use --selftest for the NF golden check")

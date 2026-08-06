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


def control_block(f0, f_lo, f_hi, supply, noise_src="Vp1", noise_out="p2"):
    nf_idx = round((f0 - f_lo) / (f_hi - f_lo) * 50) if f_hi > f_lo else 0
    nf_idx = max(0, min(50, nf_idx))
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
        f"noise v({noise_out}) {noise_src} lin 51 {f_lo:g} {f_hi:g}",
        "setplot noise1",
        f"let nfv = 10*log10((inoise_spectrum*inoise_spectrum)/{K4TRS:.6e})",
        f"let m_nf_f0 = nfv[{nf_idx}]", "print m_nf_f0",
        ".endc", ".end"])


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
        "nf_db": g("m_nf_f0"),      # best-effort; see caveat
    }
    if s21_min is not None and s21_max is not None:
        metrics["s21_ripple_db"] = s21_max - s21_min
    return metrics


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

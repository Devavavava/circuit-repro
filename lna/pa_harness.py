"""Power-amplifier large-signal harness (circuit_class: pa).

Single-tone power sweep at f0 on a sized deck, reusing iip3.py's transient +
coherent-DFT tone-extraction machinery (same coherent grid, same Thevenin drive,
same rectangular-window DFT -- so PA numbers inherit the IIP3 golden's proven
extraction arithmetic). Measures:

    gain_ss     small-signal gain (dB), from the lowest-Pin point
    p1db_in     input-referred 1 dB compression point (dBm available power)
    p1db_out    output-referred 1 dB compression (dBm delivered to the 50 ohm load)
    psat_dbm    saturated output power (dBm). If the sweep never saturates
                (output still rising at the top Pin), this is the MAX measured
                Pout reported HONESTLY as a lower bound (`psat_is_bound=True`).
    pae_pct     power-added efficiency at P1dB  = (Pout - Pin)/Pdc * 100
    drain_pct   drain efficiency at P1dB        = Pout/Pdc * 100

Pdc = Vdd * Idd is read from the deck's own DC operating point (extract's op/idd
machinery -- the supply-branch current the sizing deck already solves), so no
separate DC run is needed.

RUNTIME: each swept Pin is one transient of the same length as an IIP3 point
(~T_SETTLE + 1 us window at TMAX = 5 ps). Measured on this box (bptm45 dhruva
core): ~4-8 s per point; a default 8-point sweep is ~35-60 s. Coarser sweeps
(fewer points, larger TMAX) trade accuracy for speed and are parameters.

Golden: lna/ref/check_pa.py -- a memoryless behavioral amp y = g1*x - g3*x^3
whose P1dB is closed form (A^2_1dB = (0.10875*4/3)*g1/g3; derived there), plus a
PAE sanity on an ideal class-A point. No design number is quoted until it is
GREEN.

Scope v0: single-tone AM-AM only. No load-pull (fixed 50 ohm), no AM-PM (phase
of the fundamental is measured and reported but not gated), no harmonic-power
table beyond the fundamental. Documented in kaggle/HARNESS-ROADMAP.md.
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import extract as E                    # noqa: E402  (run_deck, scratch, NGSPICE)
import iip3 as I                       # noqa: E402  (tone plan, drive, DFT)

Z0 = I.Z0


# ------------------------------------------------------------- single-tone run
def single_tone_drive(node, vemf, f1):
    """One SIN EMF behind 50 ohm into `node` -- the single-tone analogue of
    iip3.two_tone_drive, so the port termination matches the sp claim exactly."""
    return (f"Vt1 tt_a 0 dc 0 sin(0 {vemf:.10g} {f1:.10g})\n"
            f"Rsrc tt_a {node} {Z0:g}")


def run_single_tone(body, out_node, f1, supply=None, timeout=1800,
                    tmax=I.TMAX, t_win=I.T_WIN):
    """Run the transient + capture Idd from the DC op; return (t, v, idd, err).

    Idd is read from the SAME deck via an `op` before the tran and a `print idd`
    -- exactly extract.control_block's idd read (`let idd = -i(<supply>)`), so
    the DC supply power is the operating point this deck actually solves."""
    supply = supply or E._supply_name(body)
    t_stop = I.T_SETTLE + t_win + 5e-9
    t_start = I.T_SETTLE - 20e-9
    with E.scratch("pa_") as d:
        datf = os.path.join(d, "pa.dat").replace("\\", "/")
        deck = (body.rstrip() + "\n.control\n"
                "op\n"
                f"let idd = -i({supply})\n"
                "print idd\n"
                f"tran {2 * tmax:g} {t_stop:g} {t_start:g} {tmax:g}\n"
                f"wrdata {datf} v({out_node})\n"
                ".endc\n.end\n")
        p = os.path.join(d, "pa.cir")
        with open(p, "w") as fh:
            fh.write(deck)
        import subprocess
        try:
            r = subprocess.run([E.NGSPICE, "-b", p], capture_output=True,
                               text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None, None, None, "timeout"
        out = (r.stdout or "") + (r.stderr or "")
        if not os.path.exists(datf):
            return None, None, None, out[-2000:]
        arr = np.loadtxt(datf)
    import re
    m = re.search(rf"idd\s*=\s*{E._NUM}", out, re.IGNORECASE)
    idd = abs(float(m.group(1))) if m else None
    if arr.ndim != 2 or arr.shape[0] < 1000:
        return None, None, idd, "short/empty wrdata"
    return arr[:, 0], arr[:, 1], idd, None


def measure_pa_point(body, out_node, f0, pin_dbm, supply=None, **kw):
    """One power-sweep point: fundamental Pout (dBm), delivered gain, Idd.

    `body` already carries the single-tone drive (wired by pa_body_fn); this
    only runs + extracts. Coherent single tone snapped to the 1 MHz grid;
    fundamental amplitude read from the exact bin (rectangular window, zero
    leakage) -- iip3.coherent_bins, reused verbatim."""
    f1 = I.snap(f0)
    t, v, idd, err = run_single_tone(body, out_node, f1, supply=supply, **kw)
    if t is None:
        return None, err
    b = I.coherent_bins(t, v, [f1], T=kw.get("t_win", I.T_WIN))
    pout = I.vout_to_dbm(b[f1])
    return dict(pin=pin_dbm, pout=pout, gain=pout - pin_dbm,
                idd_ma=None if idd is None else idd * 1e3, idd_a=idd), None


def pa_body_fn(base_body, in_node, out_node):
    """Return body_fn(vemf, f1) -> (body, out_node) that replaces the sp port-1
    source with a single-tone Thevenin drive into `in_node` and port-2 with a
    50 ohm load on `out_node`. Mirrors iip3.lna_two_tone_body's surgery but for
    a single tone. `base_body` is a to_spice body (portnum lines present)."""
    import re
    text = base_body
    p1 = I.PORT1_RE.search(text)
    p2 = I.PORT2_RE.search(text)
    if not (p1 and p2):
        raise ValueError("pa_body_fn: port sources not found (need portnum 1 & 2)")
    n_in, n_out = p1.group(1), p2.group(1)

    def fn(vemf, f1):
        t = I.PORT1_RE.sub(single_tone_drive(n_in, vemf, f1), text)
        t = I.PORT2_RE.sub(f"Rload {n_out} 0 {Z0:g}", t)
        return t, n_out
    return fn, n_out


# ------------------------------------------------------------- the sweep + fit
def _interp_p1db(rows):
    """Input P1dB by linear interpolation of gain-vs-Pin crossing 1 dB below the
    small-signal gain. Returns (pin_1db, pout_1db, gain_ss) or (None, None, g_ss)
    if the sweep never compressed by 1 dB."""
    rows = sorted(rows, key=lambda r: r["pin"])
    g_ss = rows[0]["gain"]
    target = g_ss - 1.0
    prev = None
    for r in rows:
        if r["gain"] <= target:
            if prev is None:
                # already compressed at the first point: P1dB below sweep
                return None, None, g_ss
            # linear interp in Pin on the gain axis
            x0, y0 = prev["pin"], prev["gain"]
            x1, y1 = r["pin"], r["gain"]
            frac = (target - y0) / (y1 - y0) if y1 != y0 else 0.0
            pin_1db = x0 + frac * (x1 - x0)
            pout_1db = pin_1db + target        # by definition gain==target there
            return pin_1db, pout_1db, g_ss
        prev = r
    return None, None, g_ss


def pa_sweep(body_fn, f0, pins_dbm, vdd, supply=None, verbose=True, **kw):
    """Sweep Pin; body_fn(vemf, f1) -> (body, out_node). vdd (V) sets Pdc.

    Returns a dict with gain_ss, p1db_in/out, psat, pae_pct, drain_pct, rows.
    Pdc = vdd * Idd(A). Idd is read per point (bias can shift with drive), and
    the P1dB efficiencies use the Idd interpolated at the P1dB Pin."""
    f1 = I.snap(f0)
    rows = []
    for pin in pins_dbm:
        body, node = body_fn(I.pav_dbm_to_vemf(pin), f1)
        m, err = measure_pa_point(body, node, f0, pin, supply=supply, **kw)
        if m is None:
            if verbose:
                print(f"    Pin={pin:+6.1f}: SIM FAILED ({err})")
            continue
        rows.append(m)
        if verbose:
            print(f"    Pin={pin:+6.1f}  Pout={m['pout']:+7.2f} dBm  "
                  f"gain={m['gain']:6.2f} dB  "
                  f"Idd={m['idd_ma']:.3f} mA" if m['idd_ma'] is not None
                  else f"    Pin={pin:+6.1f}  Pout={m['pout']:+7.2f}  gain={m['gain']:.2f}")
    if len(rows) < 2:
        return dict(ok=False, why=f"only {len(rows)} clean points", rows=rows)
    rows.sort(key=lambda r: r["pin"])
    pin_1db, pout_1db, g_ss = _interp_p1db(rows)
    pout_max = max(r["pout"] for r in rows)
    top = max(rows, key=lambda r: r["pin"])
    # saturation heuristic: if the top two points' Pout differ by < 0.5 dB while
    # Pin rose >= 1 dB, the output has flattened -> genuine Psat; else it is a
    # lower bound (still rising).
    r_hi, r_lo = rows[-1], rows[-2]
    d_pout = r_hi["pout"] - r_lo["pout"]
    d_pin = r_hi["pin"] - r_lo["pin"]
    psat_is_bound = not (d_pin >= 0.5 and d_pout < 0.5)
    # efficiencies at P1dB: interpolate Idd at pin_1db
    pae = drain = idd_1db = None
    if pin_1db is not None:
        idd_1db = _interp_idd(rows, pin_1db)
        if idd_1db is not None and idd_1db > 0:
            pdc = vdd * idd_1db                       # W
            pout_w = 10 ** (pout_1db / 10.0) * 1e-3   # dBm -> W
            pin_w = 10 ** (pin_1db / 10.0) * 1e-3
            pae = (pout_w - pin_w) / pdc * 100.0
            drain = pout_w / pdc * 100.0
    return dict(ok=True, f0=f0, gain_ss=g_ss, p1db_in=pin_1db, p1db_out=pout_1db,
                psat_dbm=pout_max, psat_is_bound=psat_is_bound,
                pae_pct=pae, drain_pct=drain, idd_at_p1db_ma=None if idd_1db is None
                else idd_1db * 1e3, vdd=vdd, rows=rows)


def _interp_idd(rows, pin):
    rows = sorted(rows, key=lambda r: r["pin"])
    have = [(r["pin"], r["idd_a"]) for r in rows if r["idd_a"] is not None]
    if not have:
        return None
    if pin <= have[0][0]:
        return have[0][1]
    if pin >= have[-1][0]:
        return have[-1][1]
    for (x0, y0), (x1, y1) in zip(have, have[1:]):
        if x0 <= pin <= x1:
            frac = (pin - x0) / (x1 - x0) if x1 != x0 else 0.0
            return y0 + frac * (y1 - y0)
    return have[-1][1]


DEFAULT_PINS = [-30.0, -25.0, -20.0, -15.0, -12.0, -9.0, -6.0, -3.0]


def measure_pa(body, f0, vdd, pins_dbm=None, supply=None, verbose=True, **kw):
    """Top-level: measure a two-port sp body (portnum lines) as a PA at f0.

    `body` is a to_spice-style body; the input port becomes a single-tone drive,
    the output port a 50 ohm load. Returns the pa_sweep dict."""
    pins = DEFAULT_PINS if pins_dbm is None else pins_dbm
    body_fn, _out = pa_body_fn(body, None, None)
    return pa_sweep(body_fn, f0, pins, vdd, supply=supply, verbose=verbose, **kw)


if __name__ == "__main__":
    print(__doc__)

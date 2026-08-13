"""Two-tone transient IIP3 harness (WP-IIP3) -- the Gate-D5 prototype.

`plans2/14-DHRUVA-SIMUL.md` §4 upgrade #2. ngspice has no harmonic balance, so
IIP3 is measured the honest brute-force way: a two-tone transient, coherently
sampled, rectangular-window DFT, and the classical **slope-intercept**
construction -- a slope-1 fundamental line and a slope-3 IM3 line, intersected
-- taken over an explicitly-guarded well-behaved region.

    fund line :  Pfund = Pin + G          (G = small-signal gain, dB)
    im3  line :  Pim3  = 3*Pin + b3       (b3 = LS intercept at fixed slope 3)
    IIP3      = (G - b3) / 2              (their intersection, dBm)

with the free-slope fit of Pim3 vs Pin reported alongside as the 3:1 check, and
the per-point formula IIP3 = Pin + (Pfund - Pim3)/2 kept as an independent
cross-check (its median + spread).

METHOD CHOICES (all validated in `lna/ref/check_iip3.py` against a closed-form
analytic IIP3 -- the golden MUST be GREEN before any design number is quoted):

  * COHERENT SAMPLING. Every tone sits on an exact 1 MHz grid: f0 is snapped to
    1 MHz, tones at f0s -/+ DF/2 (DF = 2 MHz), IM3 at f0s -/+ 3*DF/2. The DFT
    window is T = 1 us, so the bin spacing is exactly 1 MHz and every tone and
    every intermodulation product lands dead-centre in a bin. Rectangular
    window, zero leakage by construction, no window-gain correction factors
    anywhere.
  * A MEASURED SPECTRAL FLOOR, not an assumed one. With f1, f2 on a 1 MHz grid
    and spacing DF, every product m*f1 + n*f2 that lands near f0 sits at an ODD
    multiple of DF/2 away from f0s (m+n = 1 forces n-m odd). The EVEN multiples
    -- f0s +/- DF, +/-2DF, +/-3DF, +/-4DF -- are therefore product-free by
    construction, and their median amplitude is the harness's own numerical
    floor at that operating point. Every swept point reports IM3-over-floor and
    a point is dropped from the fit unless it clears `MIN_SNR_DB`.
  * TERMINATIONS MATCH THE SP RUN. `portnum`/`z0` are sp-analysis-internal; in
    transient an sp port source is just an ideal 0 V short. The harness
    therefore replaces port 1 with an explicit Thevenin drive (two series SIN
    EMFs behind 50 ohm) and port 2 with an explicit 50 ohm load, so the
    transient sees exactly the terminations the S-parameter claim was measured
    with. Pin is AVAILABLE power per tone, Pav = Vemf^2 / (8*50).
    Nothing else in the deck is touched -- no solver options are added, no
    device value is changed (fence, measured at tmax = 10 ps: reltol 1e-3 ->
    1e-5 with vntol 1e-9 / abstol 1e-15 moves the L5 IIP3 by 0.004 dB, so the
    stock deck tolerances are not what limits this; see FINDINGS §37).
  * TMAX = 5 ps IS A MEASURED CHOICE, NOT A GUESS. The golden's G1 check runs
    the reference network with a3 = 0, so every IM3 bin is pure numerics; its
    floor vs tmax is 20 ps: -97.8 dBc | 10 ps: -104.9 | 5 ps: -133.1 |
    2.5 ps: -133.0. At 10 ps the IM3 bins carry ~10 dB of excess numerical
    distortion over the broadband floor and G1 FAILS its pre-registered
    -110 dBc bar; at 5 ps the IM3 bins have collapsed into the broadband floor
    (-140.2 vs -140.3 dBm) and are stationary under a further halving. 5 ps is
    the first step size at which the harness's own numerical intermodulation
    has provably vanished. `lna/_iip3_floor.py` regenerates that table.
  * The tran starts from the DC operating point (ngspice default), so the bias
    -- including every node held only by `rshunt=1e12` -- starts settled; RF
    time constants are ns-scale and the DFT window opens 150 ns in. The
    resampled record is linearly detrended before the DFT, which kills any
    residual slow drift riding on the 1e12-ohm nodes (measured effect on the
    L5 IM3: 0.02 dB).
  * `wrdata` writes (xscale, value) column PAIRS on the simulator's own
    nonuniform timesteps (gotcha N2); the harness resamples by linear
    interpolation onto the uniform coherent grid. `tmax` bounds both the
    integration and the interpolation error -- and is *proved* adequate rather
    than assumed, by re-running at tmax/2 (`--conv`).

Usage:
    python lna/ref/check_iip3.py                  # the golden -- run FIRST
    python lna/iip3.py --band all                 # the D4-SIM point, 4 bands
    python lna/iip3.py --band l5 --conv           # timestep-convergence proof
"""
import argparse
import atexit
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract as E                  # noqa: E402  (read-only reuse of NGSPICE)

REPRO = os.path.join(HERE, "repro", "dhruva-best")
OUT = os.path.join(HERE, "out")

# ---- coherent-grid constants (see module docstring) -----------------------
GRID_HZ = 1e6          # tone grid == DFT bin spacing == 1 / T_WIN
DF = 2e6               # tone spacing f2 - f1
T_WIN = 1e-6           # DFT window
N_FFT = 32768          # resample points => fs = 32.768 GHz, Nyquist 16.384 GHz
T_SETTLE = 150e-9      # window start (tran starts from the OP; RF tau ~ ns)
TMAX = 5e-12           # ngspice max internal step -- see the note below
Z0 = 50.0

N_FLOOR = 4            # product-free floor bins at f0s +/- k*DF, k = 1..N_FLOOR
MIN_SNR_DB = 10.0      # IM3 must clear the measured floor by this to be kept
COMP_DB = 0.5          # gain may sag this far below small-signal and be kept

BANDS = {"l5": 1176.45e6, "l2": 1227.6e6, "l1": 1575.42e6, "s": 2492.03e6}
IIP3_TARGET_DBM = {"l5": -7.4, "l2": -7.4, "l1": -7.6, "s": -8.7}
DEFAULT_PINS = [-80.0, -72.0, -64.0, -56.0, -48.0, -40.0]   # 40 dB of lever

# The D4-SIM designated point is ONE fixed sizing measured at all four band
# f0s (FINDINGS §35.3) -- `dhruva-l5.sp`, not each band's own deck. Getting
# this wrong is silent: `dhruva-s.sp` also runs and also reports a plausible
# IIP3, it is just the answer to the retired per-band (D3) question.
DESIGNATED = "l5"

# S21 @ each band's f0 for the designated l5 sizing, from the audited
# S-parameter matrix (FINDINGS §35.2, the `l5` row). The two-tone harness's
# own small-signal gain must reproduce these: it is an independent check of
# the Thevenin drive, the port terminations and the DFT scaling against a
# claim measured through a completely different ngspice analysis. It is also
# what caught the deck mix-up above.
S21_REF_DB = {"l5": 35.96, "l2": 35.93, "l1": 35.54, "s": 33.73}
S21_TOL_DB = 0.5


def private_tmp():
    """Point THIS PROCESS's tempfile at a pid-scoped dir under lna/out/_iip3.

    Same intent as `moves.private_tmp` (keep ngspice scratch out of the shared
    %TEMP%), but pid-scoped and non-destructive on entry, because four other
    agents share this worktree and this harness may run concurrently with
    itself."""
    root = os.path.join(OUT, "_iip3", f"tmp{os.getpid()}")
    os.makedirs(root, exist_ok=True)
    tempfile.tempdir = root
    atexit.register(shutil.rmtree, root, True)
    return root


def snap(f):
    return round(f / GRID_HZ) * GRID_HZ


def tone_plan(f0, df=DF):
    """f0 -> (f0_snapped, f1, f2, im3_lo, im3_hi), all exact grid multiples."""
    f0s = snap(f0)
    f1, f2 = f0s - df / 2, f0s + df / 2
    return f0s, f1, f2, 2 * f1 - f2, 2 * f2 - f1


def pav_dbm_to_vemf(p_dbm):
    """Available power per tone (dBm) -> Thevenin EMF amplitude (V)."""
    return math.sqrt(8.0 * Z0 * 1e-3 * 10 ** (p_dbm / 10.0))


def vout_to_dbm(a_pk):
    """Peak voltage amplitude across the 50-ohm load -> power in dBm."""
    return 10 * math.log10(max(a_pk, 1e-300) ** 2 / (2 * Z0) * 1e3)


# ------------------------------------------------------------- deck surgery
PORT1_RE = re.compile(r"^V\w+\s+(\w+)\s+0\s+dc\s+0\s+ac\s+1\s+portnum\s+1\s+z0\s+50\s*$",
                      re.IGNORECASE | re.MULTILINE)
PORT2_RE = re.compile(r"^V\w+\s+(\w+)\s+0\s+dc\s+0\s+ac\s+0\s+portnum\s+2\s+z0\s+50\s*$",
                      re.IGNORECASE | re.MULTILINE)


def two_tone_drive(node, vemf, f1, f2):
    return (f"Vt1 tt_a 0 dc 0 sin(0 {vemf:.10g} {f1:.10g})\n"
            f"Vt2 tt_b tt_a dc 0 sin(0 {vemf:.10g} {f2:.10g})\n"
            f"Rsrc tt_b {node} {Z0:g}")


def lna_two_tone_body(deck_path, vemf, f1, f2):
    """Shipped standalone .sp deck -> transient two-tone body.

    Strips the .control block, replaces the sp port-1 source with the Thevenin
    two-tone drive and the sp port-2 source with a 50 ohm load. Everything else
    (topology, bias, .param, .option, .include) is byte-identical to the deck
    the D4-SIM claim was measured on."""
    text = open(deck_path, encoding="utf-8").read()
    text = re.sub(r"\.control.*?\.endc\s*", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"^\.end\s*$", "", text, flags=re.MULTILINE | re.IGNORECASE)
    m1, m2 = PORT1_RE.search(text), PORT2_RE.search(text)
    if not (m1 and m2):
        raise SystemExit(f"port sources not found in {deck_path}")
    n_in, n_out = m1.group(1), m2.group(1)
    text = PORT1_RE.sub(two_tone_drive(n_in, vemf, f1, f2), text)
    text = PORT2_RE.sub(f"Rload {n_out} 0 {Z0:g}", text)
    return text, n_out


# ------------------------------------------------------------- run + DFT
def run_two_tone(body, out_node, timeout=1800, tmax=TMAX, t_win=T_WIN):
    """Run the transient; return (t, v, err) from wrdata (nonuniform grid)."""
    t_stop = T_SETTLE + t_win + 5e-9
    t_start = T_SETTLE - 20e-9
    with E.scratch("iip3_") as d:
        datf = os.path.join(d, "tt.dat").replace("\\", "/")   # gotcha N2
        deck = (body.rstrip() + "\n.control\n"
                f"tran {2 * tmax:g} {t_stop:g} {t_start:g} {tmax:g}\n"
                f"wrdata {datf} v({out_node})\n"
                ".endc\n.end\n")
        p = os.path.join(d, "tt.cir")
        with open(p, "w") as fh:
            fh.write(deck)
        try:
            r = subprocess.run([E.NGSPICE, "-b", p], capture_output=True,
                               text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None, None, "timeout"
        if not os.path.exists(datf):
            return None, None, ((r.stdout or "") + (r.stderr or ""))[-2000:]
        arr = np.loadtxt(datf)
    if arr.ndim != 2 or arr.shape[0] < 1000:
        return None, None, "short/empty wrdata"
    return arr[:, 0], arr[:, 1], None


def coherent_bins(t, v, freqs, t0=T_SETTLE, T=T_WIN, n=N_FFT, detrend=1):
    """Linear-resample onto the uniform coherent grid, linearly detrend,
    rectangular-window DFT; return {f: peak amplitude}. Exact for on-grid
    tones by construction (integer bins, no leakage)."""
    tg = t0 + np.arange(n) * (T / n)
    if t[0] > tg[0] or t[-1] < tg[-1]:
        raise ValueError(f"tran window [{t[0]:g},{t[-1]:g}] misses the DFT grid")
    vg = np.interp(tg, t, v)
    u = tg - tg[0]
    vg = vg - (np.polyval(np.polyfit(u, vg, detrend), u) if detrend else vg.mean())
    return {f: 2.0 * abs(np.dot(vg, np.exp(-2j * np.pi * f * u))) / n
            for f in freqs}


def measure_point(body, out_node, f0s, f1, f2, fl, fh, df=DF, **kw):
    """One transient -> fundamentals, both IM3 sidebands, measured floor."""
    t, v, err = run_two_tone(body, out_node, **kw)
    if t is None:
        return None, err
    floor_f = [f0s + s * k * df for k in range(1, N_FLOOR + 1) for s in (-1, 1)]
    b = coherent_bins(t, v, [f1, f2, fl, fh] + floor_f,
                      T=kw.get("t_win", T_WIN))
    pf = 0.5 * (vout_to_dbm(b[f1]) + vout_to_dbm(b[f2]))
    p3l, p3h = vout_to_dbm(b[fl]), vout_to_dbm(b[fh])
    p3 = max(p3l, p3h)                       # conservative: worse sideband
    floor = vout_to_dbm(float(np.median([b[f] for f in floor_f])))
    return dict(pfund=pf, pim3_lo=p3l, pim3_hi=p3h, pim3=p3, floor=floor,
                snr=p3 - floor, npts=len(t)), None


# ------------------------------------------------------------- sweep + fit
def extract(rows, min_snr=MIN_SNR_DB, comp_db=COMP_DB):
    """Slope-intercept IIP3 over the well-behaved region.

    Well-behaved := IM3 clears the measured floor by `min_snr` AND the gain has
    not sagged more than `comp_db` below its small-signal (lowest-Pin) value."""
    if not rows:
        return dict(ok=False, why="no clean points")
    g_ss = min(rows, key=lambda r: r["pin"])["gain"]
    kept = [r for r in rows
            if r["snr"] >= min_snr and (g_ss - r["gain"]) <= comp_db]
    if len(kept) < 3:
        return dict(ok=False, why=f"only {len(kept)} points in the clean region",
                    kept=len(kept))
    x = np.array([r["pin"] for r in kept])
    y = np.array([r["pim3"] for r in kept])
    slope = float(np.polyfit(x, y, 1)[0])          # free fit == the 3:1 check
    b3 = float(np.mean(y - 3.0 * x))               # LS intercept at fixed 3:1
    iip3 = 0.5 * (g_ss - b3)                       # the two lines intersect
    per_pt = [r["iip3_pt"] for r in kept]
    resid = float(np.max(np.abs(y - (3.0 * x + b3))))
    return dict(ok=True, iip3_dbm=iip3, slope=slope, b3=b3, gain_ss=g_ss,
                kept=len(kept), pin_lo=float(x.min()), pin_hi=float(x.max()),
                slope_ok=bool(abs(slope - 3.0) <= 0.3),
                im3_fit_resid_db=resid,
                iip3_pt_median=float(np.median(per_pt)),
                iip3_pt_spread=float(max(per_pt) - min(per_pt)),
                worst_snr_db=float(min(r["snr"] for r in kept)))


def iip3_sweep(body_fn, f0, pins_dbm, df=DF, verbose=True, **kw):
    """Sweep Pin; body_fn(vemf, f1, f2) -> (body, out_node)."""
    f0s, f1, f2, fl, fh = tone_plan(f0, df)
    rows = []
    for pin in pins_dbm:
        body, node = body_fn(pav_dbm_to_vemf(pin), f1, f2)
        m, err = measure_point(body, node, f0s, f1, f2, fl, fh, df=df, **kw)
        if m is None:
            if verbose:
                print(f"    Pin={pin:+6.1f}: SIM FAILED ({err})")
            continue
        m.update(pin=pin, gain=m["pfund"] - pin,
                 iip3_pt=pin + (m["pfund"] - m["pim3"]) / 2.0,
                 im3_dbc=m["pim3"] - m["pfund"])
        rows.append(m)
        if verbose:
            print(f"    Pin={pin:+6.1f}  Pfund={m['pfund']:+8.2f}  "
                  f"IM3={m['pim3_lo']:+9.2f}/{m['pim3_hi']:+9.2f}  "
                  f"floor={m['floor']:+8.1f} (SNR {m['snr']:5.1f})  "
                  f"gain={m['gain']:6.2f}  IIP3pt={m['iip3_pt']:+7.2f}")
    res = extract(rows)
    res["rows"] = rows
    res["f0"], res["f0_snapped"] = f0, f0s
    res["f1"], res["f2"], res["df"] = f1, f2, df
    return res


def convergence(body_fn, f0, pin, tmax=TMAX, factor=2.0, df=DF, verbose=True):
    """Re-run one operating point at tmax and tmax/factor; the numerical-
    distortion proof. Returns the IM3 and IIP3 shifts in dB."""
    f0s, f1, f2, fl, fh = tone_plan(f0, df)
    body, node = body_fn(pav_dbm_to_vemf(pin), f1, f2)
    out = []
    for tm in (tmax, tmax / factor):
        m, err = measure_point(body, node, f0s, f1, f2, fl, fh, df=df, tmax=tm)
        if m is None:
            return dict(ok=False, why=f"sim failed at tmax={tm:g}: {err}")
        m["iip3_pt"] = pin + (m["pfund"] - m["pim3"]) / 2.0
        m["tmax"] = tm
        out.append(m)
        if verbose:
            print(f"    tmax={tm:11.4g} s  npts={m['npts']:7d}  "
                  f"Pfund={m['pfund']:+8.3f}  IM3={m['pim3']:+9.3f}  "
                  f"floor={m['floor']:+8.1f}  IIP3pt={m['iip3_pt']:+8.3f}")
    d_im3 = out[1]["pim3"] - out[0]["pim3"]
    d_iip3 = out[1]["iip3_pt"] - out[0]["iip3_pt"]
    return dict(ok=True, pin=pin, tmax=tmax, factor=factor,
                d_im3_db=d_im3, d_iip3_db=d_iip3, points=out,
                converged=bool(abs(d_im3) < 0.5))


# ------------------------------------------------------------- the design
def deck_for(tag, sizing=DESIGNATED):
    """`sizing='own'` = that band's own deck (the retired per-band D3 point);
    anything else names the one fixed sizing measured at every band f0."""
    p = os.path.join(REPRO, f"dhruva-{tag if sizing == 'own' else sizing}.sp")
    if not os.path.exists(p):
        raise SystemExit(
            f"no deck {p}.\nOnly sizings with an emitted standalone .sp can be "
            f"measured; `dhruva-simul` (WP-HARDEN, FINDINGS 36) ships as "
            f".params.json/.meta.json only and needs its deck built first.")
    return p


def band_body_fn(tag, sizing=DESIGNATED):
    deck = deck_for(tag, sizing)
    return lambda ve, f1, f2: lna_two_tone_body(deck, ve, f1, f2)


def measure_band(tag, pins_dbm, df=DF, conv=False, sizing=DESIGNATED, **kw):
    f0 = BANDS[tag]
    tgt = IIP3_TARGET_DBM[tag]
    body_fn = band_body_fn(tag, sizing)
    f0s, f1, f2, fl, fh = tone_plan(f0, df)
    print(f"== {os.path.basename(deck_for(tag, sizing))} @ {tag} band: "
          f"f0 = {f0/1e6:.2f} MHz (snapped {f0s/1e6:.0f}), "
          f"tones {f1/1e6:.0f}/{f2/1e6:.0f} MHz (dF = {df/1e6:g} MHz), "
          f"IM3 at {fl/1e6:.0f}/{fh/1e6:.0f} MHz; target IIP3 >= {tgt:+.1f} dBm")
    res = iip3_sweep(body_fn, f0, pins_dbm, df=df, **kw)
    res["band"], res["target_dbm"], res["sizing"] = tag, tgt, sizing
    res["deck"] = os.path.basename(deck_for(tag, sizing))
    if res["ok"] and sizing == DESIGNATED:
        d = res["gain_ss"] - S21_REF_DB[tag]
        res["s21_ref_db"], res["d_s21_db"] = S21_REF_DB[tag], d
        res["s21_ok"] = bool(abs(d) <= S21_TOL_DB)
        print(f"     [xcheck] small-signal gain {res['gain_ss']:.2f} dB vs "
              f"audited sp S21 {S21_REF_DB[tag]:.2f} dB -> D {d:+.2f} dB   "
              f"{'OK' if res['s21_ok'] else 'MISMATCH -- do not trust'}")
    if res["ok"]:
        res["margin_db"] = res["iip3_dbm"] - tgt
        res["pass"] = bool(res["margin_db"] >= 0)
        print(f"  -> IIP3 = {res['iip3_dbm']:+.2f} dBm   "
              f"[slope-intercept over {res['kept']} pts, "
              f"Pin {res['pin_lo']:+.0f}..{res['pin_hi']:+.0f} dBm, "
              f"G = {res['gain_ss']:.2f} dB]")
        print(f"     IM3 slope = {res['slope']:.3f} (3:1 check"
              f"{'' if res['slope_ok'] else ' -- FAILED'}), fit resid "
              f"{res['im3_fit_resid_db']:.3f} dB, worst SNR "
              f"{res['worst_snr_db']:.1f} dB; per-point median "
              f"{res['iip3_pt_median']:+.2f} (spread "
              f"{res['iip3_pt_spread']:.2f} dB)")
        print(f"     vs target {tgt:+.1f} dBm -> margin "
              f"{res['margin_db']:+.2f} dB   "
              f"{'PASS' if res['pass'] else 'FAIL'}")
    else:
        print(f"  -> NO RESULT: {res['why']}")
    if conv:
        print("  timestep convergence (2x finer step, require |dIM3| < 0.5 dB):")
        pin = pins_dbm[len(pins_dbm) // 2]
        res["conv"] = convergence(body_fn, f0, pin, df=df)
        c = res["conv"]
        if c["ok"]:
            print(f"    -> dIM3 = {c['d_im3_db']:+.3f} dB, dIIP3 = "
                  f"{c['d_iip3_db']:+.3f} dB   "
                  f"{'CONVERGED' if c['converged'] else 'NOT CONVERGED'}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--band", default="all", choices=list(BANDS) + ["all"])
    ap.add_argument("--pins", default=",".join(f"{p:g}" for p in DEFAULT_PINS),
                    help="per-tone AVAILABLE input powers, dBm")
    ap.add_argument("--df", type=float, default=DF / 1e6,
                    help="tone spacing in MHz (must be an even grid multiple)")
    ap.add_argument("--tmax", type=float, default=TMAX)
    ap.add_argument("--conv", action="store_true",
                    help="also run the tmax/2 convergence proof per band")
    ap.add_argument("--sizing", default=DESIGNATED,
                    help="which sized deck (dhruva-<sizing>.sp) to measure at "
                         "every band f0; the default is the D4-SIM designated "
                         "point, 'own' is the retired per-band D3 answer")
    ap.add_argument("--json", default=os.path.join(OUT, "_iip3_d4sim.json"))
    a = ap.parse_args()
    private_tmp()
    pins = [float(x) for x in a.pins.split(",")]
    df = a.df * 1e6
    if abs(df / GRID_HZ - round(df / GRID_HZ)) > 1e-9 or round(df / GRID_HZ) % 2:
        raise SystemExit(f"--df {a.df} MHz is not an even multiple of the "
                         f"{GRID_HZ/1e6:g} MHz coherent grid")
    tags = list(BANDS) if a.band == "all" else [a.band]
    out = {}
    for tag in tags:
        out[tag] = measure_band(tag, pins, df=df, conv=a.conv, tmax=a.tmax,
                                sizing=a.sizing)
        print()
    ok = [t for t in tags if out[t].get("ok")]
    if len(ok) > 1:
        print(f"summary -- sizing '{a.sizing}' (target = the paper's IIP3 at "
              f"its MIN-GAIN setting; this is one fixed ~34-36 dB gain point):")
        print(f"  {'band':5} {'f0 (MHz)':>10} {'gain':>7} {'IIP3':>9} "
              f"{'target':>8} {'margin':>8} {'slope':>7}")
        for t in ok:
            r = out[t]
            print(f"  {t:5} {r['f0']/1e6:10.2f} {r['gain_ss']:7.2f} "
                  f"{r['iip3_dbm']:+9.2f} {r['target_dbm']:+8.1f} "
                  f"{r['margin_db']:+8.2f} {r['slope']:7.3f}   "
                  f"{'PASS' if r['pass'] else 'FAIL'}")
        bad = [t for t in ok if out[t].get("s21_ok") is False]
        if bad:
            print(f"  ⚠ gain cross-check MISMATCH on {', '.join(bad)} -- the "
                  f"transient is not reproducing the audited sp S21; do not "
                  f"quote these numbers.")
    if a.json:
        os.makedirs(os.path.dirname(a.json), exist_ok=True)
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, default=float)
        print(f"wrote {a.json}")
    return 0 if len(ok) == len(tags) else 1


if __name__ == "__main__":
    sys.exit(main())

"""VACASK harmonic-balance IIP3 driver for the D4-SIM point (WP-HB, FINDINGS S40).

Gate D5 wants a *linearity* number for the designated Gate-D4-SIM design:
the `dhruva-l5` sizing of topology `ace8383c2fa68d03` -- ONE fixed sizing,
one 12.963 mA operating point. This driver measures it in VACASK 0.3.4.rc1
by true two-tone harmonic balance (frequency-domain steady state), the
reference method for IIP3, alongside a live ngspice cross-check of the DC
operating point and the small-signal gain so the port is not taken on faith.

Modes
  --op     DC operating point in VACASK, cross-checked against a LIVE ngspice
           run of the same deck: Idd and every node voltage.
  --gain   single-tone HB gain at each band f0, cross-checked against a LIVE
           ngspice `sp` S21 of the same deck. This is the model-compatibility
           verdict: two independent simulators, two BSIM4 implementations.
  --iip3   two-tone HB IIP3 at each band f0 vs the paper targets.
  --fence  numerical convergence fences (reltol / nharm / tone spacing).

Protocol (validated by lna/ref/check_hb.py -- run that FIRST; it is the
golden and it must print GREEN before any number below is quoted):
  - `options reltol=1e-6` is load-bearing: golden check G0 shows that at the
    default tolerance the IM3 line lands in Newton residual noise and IIP3
    reads +133 dBm instead of +21 dBm.
  - HB phasors are PEAK amplitudes (golden G1 convention factor 1.0000).
  - Conventions are IDENTICAL to the sibling ngspice transient harness
    (lna/iip3.py) so the two are directly comparable, and golden G2 measures
    that harness's own closed-form references through this one:
      P_in  = available power per tone from a 50-ohm source = A_emf^2/(8*50)
      P_out = peak^2/(2*50) at the 50-ohm load
      P_im3 = the WORSE of the two IM3 sidebands (2f1-f2, 2f2-f1)
      IIP3  = P_in + (P_fund - P_im3)/2, median over uncompressed points,
              where "uncompressed" = gain within 0.5 dB of the small-signal
              value, and the IM3-vs-Pin slope over those points must be 3:1.
  - Default tone spacing 2 MHz = the sibling harness's DF (spacing dependence
    is measured by --fence and is ~0.3 dB over 1..50 MHz).

HONESTY NOTE. The paper specifies IIP3 at its MINIMUM-gain setting. This
design has one fixed ~34-36 dB gain point and no gain programmability
(Gate D6, not attempted), so it cannot even enter the paper's measurement
condition. A large miss is the expected outcome and is a finding about the
design, not about this harness.
"""
import argparse
import itertools
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import port45  # noqa: E402

VACASK_HOME = os.environ.get(
    "VACASK_HOME",
    r"C:\Users\Devavrat\tools\vacask_0.3.4.rc1\vacask_0.3.4.rc1_windows-x86_64")
VACASK = os.path.join(VACASK_HOME, "bin", "vacask.exe")
NGSPICE = os.environ.get("NGSPICE", r"C:\msys64\ucrt64\bin\ngspice_con.exe")
sys.path.insert(0, os.path.join(VACASK_HOME, "lib", "python"))

REPRO = os.path.join(os.path.dirname(HERE), "repro", "dhruva-best")

BANDS = {"dhruva-l5": 1176.45e6, "dhruva-l2": 1227.6e6,
         "dhruva-l1": 1575.42e6, "dhruva-s": 2492.03e6}
IIP3_TARGET = {"dhruva-l5": -7.4, "dhruva-l2": -7.4,
               "dhruva-l1": -7.6, "dhruva-s": -8.7}
Z0 = 50.0
DF = 2e6                       # tone spacing, = lna/iip3.py DF
# per-tone available powers; spans the sibling harness's -60..-40 window plus
# a decade below it, so the compression guard has clean points to keep
PINS = [-75.0, -70.0, -65.0, -60.0, -55.0, -50.0, -45.0, -40.0]

VACASKRC = """[Binaries]
openvaf_args = [ "--target", "x86_64-pc-windows-gnu" ]
"""

HEADER = """load "spice/bsim4v8.osdi"
load "resistor.osdi"
load "capacitor.osdi"
load "inductor.osdi"

model vsource vsource
model resistor resistor
model capacitor capacitor
model inductor inductor
"""

# port 1 -> EMF stack + 50-ohm source resistor into the deck's DC-block cap;
# port 2 -> the deck's DC-block cap into a 50-ohm load (see port45.py).
PORTS = """rs (e2 p1) resistor r=50
cp1 (p1 vin1) capacitor c=1e-11
cp2 (vout1 p2) capacitor c=1e-11
rload (p2 0) resistor r=50
"""

_COUNTER = itertools.count()


# --------------------------------------------------------------- unit helpers
def dbm(p_watt):
    return 10.0 * math.log10(max(p_watt, 1e-300) / 1e-3)


def v_to_dbm(a_pk):
    """Peak voltage across the 50-ohm load -> dBm (= lna/iip3.vout_to_dbm)."""
    return dbm(a_pk * a_pk / (2.0 * Z0))


def pav_dbm_to_vemf(p_dbm):
    """Available power per tone (dBm) -> EMF amplitude (= lna/iip3 ditto)."""
    return math.sqrt(8.0 * Z0 * 1e-3 * 10 ** (p_dbm / 10.0))


# ------------------------------------------------------------ netlist + runner
def sources(tones):
    """tones = [(ampl, freq), ...]; series EMF stack e1..eN feeding node e2."""
    if len(tones) == 1:
        a, f = tones[0]
        return (f'vrf1 (e1 0) vsource type="sine" ampl={a!r} freq={f!r}\n'
                'vrf2 (e2 e1) vsource dc=0\n')
    (a1, f1), (a2, f2) = tones
    return (f'vrf1 (e1 0) vsource type="sine" ampl={a1!r} freq={f1!r}\n'
            f'vrf2 (e2 e1) vsource type="sine" ampl={a2!r} freq={f2!r}\n')


def build(control, tones, deck, options="  options reltol=1e-6\n"):
    lines, _params, card, _nodes = port45.convert(deck)
    return "\n".join(
        [f"D4-SIM VACASK port (WP-HB): {os.path.basename(deck)}", "",
         HEADER, card, "", sources(tones), PORTS] + lines
        + ["", "control", options + control, "endc", ""])


RETRIES = 4
_RETRY_LOG = []


def run(netlist, root, rawname="hb1.raw", retries=None):
    """One VACASK run in a private per-call directory -> the plot object.

    A private dir per call follows the repo's ngspice convention
    (moves.private_tmp()) and is load-bearing here: VACASK removes a
    pre-existing <analysis>.raw before writing.

    That is still not sufficient on this Windows box. VACASK intermittently
    aborts with `filesystem error: cannot remove ... hb1.raw: used by another
    process` (rc 0xC0000409, a std::filesystem::remove throw escaping to
    terminate) even in a freshly created empty directory -- the classic
    signature of a virus scanner holding a just-written file open, made more
    likely by the five agents sharing this machine. It is transient and not
    correlated with any circuit condition: the identical netlist succeeds on
    retry. Each attempt therefore gets its OWN directory (never a reused
    name) and short backoff; retries are counted and reported so a run that
    quietly needed many of them is visible rather than silent.
    """
    from rawfile import rawread
    retries = RETRIES if retries is None else retries
    last = None
    for attempt in range(retries):
        wd = os.path.join(root, "w%05d" % next(_COUNTER))
        os.makedirs(wd, exist_ok=True)
        with open(os.path.join(wd, ".vacaskrc.toml"), "w", encoding="utf-8") as f:
            f.write(VACASKRC)
        with open(os.path.join(wd, "run.sim"), "w", encoding="utf-8") as f:
            f.write(netlist)
        r = subprocess.run([VACASK, "run.sim"], cwd=wd,
                           capture_output=True, text=True, timeout=1800)
        raw = os.path.join(wd, rawname)
        if r.returncode == 0 and os.path.exists(raw):
            try:
                plot = rawread(raw).get()
            except Exception as e:                # truncated/half-flushed file
                last = r
                _RETRY_LOG.append(f"read {type(e).__name__}")
                time.sleep(0.25 * (attempt + 1))
                continue
            if attempt:
                _RETRY_LOG.append(f"ok after {attempt} retr(y/ies)")
            return plot
        last = r
        _RETRY_LOG.append(f"rc={r.returncode}")
        time.sleep(0.25 * (attempt + 1))
    sys.stderr.write((last.stdout or "")[-4000:] + "\n"
                     + (last.stderr or "")[-2000:] + "\n")
    raise SystemExit(f"vacask failed {retries}x (last rc={last.returncode})")


def spec_line(plot, name, f):
    """|phasor| of node `name` at the spectral line nearest f (within 1 Hz)."""
    freqs = plot["frequency"].real
    i = int(np.argmin(np.abs(freqs - f)))
    if abs(freqs[i] - f) > 1.0:
        raise SystemExit(f"no spectral line at {f} Hz (nearest {freqs[i]})")
    return float(abs(np.asarray(plot[name]).ravel()[i]))


# ----------------------------------------------------------- ngspice reference
def ngspice_ref(deck, root):
    """LIVE ngspice run of the same deck -> {idd_ma, nodes{}, s21{}}.

    Nothing is trusted from a previous session: the reference numbers this
    port is judged against are re-measured here, from the shipped deck.
    """
    with open(deck, encoding="utf-8") as f:
        text = f.read()
    body = text.split(".control")[0]
    nodes = port45.nodes_of(deck)
    ctl = [".control", "op", "let idd = -i(Vsup)", "print idd"]
    ctl += [f"print v({n})" for n in nodes]
    ctl += ["sp lin 101 1.1e+09 2.5e+09 1",
            "let s21db = db(mag(S_2_1)+1e-30)"]
    for band, f0 in BANDS.items():
        ctl.append(f"meas sp g_{band.split('-')[1]} find s21db at={f0:.6g}")
    ctl += [".endc", ".end"]
    sp = os.path.join(root, "ngref.sp")
    with open(sp, "w", encoding="utf-8") as f:
        f.write(body + "\n".join(ctl) + "\n")
    r = subprocess.run([NGSPICE, "-b", sp], cwd=root,
                       capture_output=True, text=True, timeout=900)
    out = r.stdout + r.stderr
    def grab(key):
        m = re.search(rf"^\s*{re.escape(key)}\s*=\s*([-+0-9.eE]+)", out, re.M)
        return float(m.group(1)) if m else None
    idd = grab("idd")
    if idd is None:
        sys.stderr.write(out[-3000:] + "\n")
        raise SystemExit("ngspice reference run produced no idd")
    return dict(idd_ma=idd * 1e3,
                nodes={n: grab(f"v({n})") for n in nodes},
                s21={b: grab("g_" + b.split("-")[1]) for b in BANDS})


# ------------------------------------------------------------------ the modes
def cmd_op(root, deck):
    plot = run(build("  analysis op1 op", [(0.0, 1e9)], deck), root, "op1.raw")
    idd_ma = abs(float(np.asarray(plot["vsup:flow(br)"]).ravel()[0].real)) * 1e3
    ref = ngspice_ref(deck, root)
    d = idd_ma - ref["idd_ma"]
    print(f"op  [{os.path.basename(deck)}]")
    print(f"  Idd  VACASK {idd_ma:.5f} mA   ngspice {ref['idd_ma']:.5f} mA   "
          f"delta {d*1e3:+.3f} uA ({100*d/ref['idd_ma']:+.4f}%)")
    worst, worst_n = 0.0, None
    rows = {}
    for n, vng in sorted(ref["nodes"].items()):
        if vng is None:
            continue
        try:
            vvc = float(np.asarray(plot[n]).ravel()[0].real)
        except KeyError:
            continue
        dv = (vvc - vng) * 1e6
        rows[n] = dict(vacask=vvc, ngspice=vng, delta_uv=dv)
        if abs(dv) > abs(worst):
            worst, worst_n = dv, n
    print(f"  DC solution: {len(rows)} nodes compared, worst delta "
          f"{worst:+.2f} uV at '{worst_n}'")
    return dict(idd_ma_vacask=idd_ma, idd_ma_ngspice=ref["idd_ma"],
                idd_delta_ma=d, nodes=rows, worst_node_delta_uv=worst)


def cmd_gain(root, bands, deck, pin_dbm=-76.0):
    """Small-signal single-tone HB gain vs a live ngspice sp S21."""
    ref = ngspice_ref(deck, root)
    a = pav_dbm_to_vemf(pin_dbm)
    out = {}
    print(f"gain  [{os.path.basename(deck)}]  single-tone HB, "
          f"Pin = {pin_dbm:.0f} dBm/tone")
    for band in bands:
        f0 = BANDS[band]
        plot = run(build("  analysis hb1 hb freq=[%r] nharm=8" % f0,
                         [(a, f0)], deck), root)
        g = 20 * math.log10(spec_line(plot, "p2", f0) / (a / 2))
        r = ref["s21"][band]
        out[band] = dict(hb_db=g, ngspice_s21_db=r, delta_db=g - r)
        print(f"  {band:<10} f0={f0/1e9:.5f} GHz   HB {g:8.4f} dB   "
              f"ngspice S21 {r:8.4f} dB   delta {g-r:+.4f} dB")
    return out


NHARM_LADDER = (5, 6, 7)


def two_tone(root, deck, f0, pin, df, nharm=None, immax=None, reltol=1e-6):
    """One two-tone HB point -> row dict (sibling-harness conventions).

    nharm=None walks NHARM_LADDER. VACASK 0.3.4.rc1 aborts on a few specific
    (f0, spacing, nharm) spectrum combinations -- e.g. dhruva-l2 with 2 MHz
    spacing at nharm=4 or 5, which fails identically at every drive level
    including zero, so it is a spectrum-construction bug and not a
    convergence failure. The abort surfaces only as a secondary
    `std::filesystem ... cannot remove hb1.raw` throw (VACASK unlinking its
    own still-open, zero-length output file on the error path), which hides
    the real message. Stepping nharm past it is safe *because it does not
    move the answer*: --fence measures IIP3 constant to <0.01 dB over
    nharm 4..8 (see the WP-HB README). The nharm actually used is recorded
    in every row.
    """
    ladder = [(nharm, immax if immax is not None else nharm)] if nharm \
        else [(n, n) for n in NHARM_LADDER]
    fa, fb = f0 - df / 2, f0 + df / 2
    a = pav_dbm_to_vemf(pin)
    for k, (nh, im) in enumerate(ladder):
        ctl = "  analysis hb1 hb freq=[%r, %r] nharm=%d immax=%d" % (fa, fb, nh, im)
        try:
            # a non-final rung gets ONE attempt: the spectrum abort below is
            # deterministic, so retrying it only burns ~18 s per try
            plot = run(build(ctl, [(a, fa), (a, fb)], deck,
                             options="  options reltol=%r\n" % reltol), root,
                       retries=None if k == len(ladder) - 1 else 1)
        except SystemExit:
            if k == len(ladder) - 1:
                raise
            _RETRY_LOG.append(f"nharm {nh}->{ladder[k+1][0]} @ {f0/1e6:.2f} MHz")
            continue
        nharm, immax = nh, im
        break
    pf = 0.5 * (v_to_dbm(spec_line(plot, "p2", fa))
                + v_to_dbm(spec_line(plot, "p2", fb)))
    p3l = v_to_dbm(spec_line(plot, "p2", 2 * fa - fb))
    p3h = v_to_dbm(spec_line(plot, "p2", 2 * fb - fa))
    p3 = max(p3l, p3h)                       # sibling convention: worse sideband
    return dict(pin=pin, pfund=pf, pim3_lo=p3l, pim3_hi=p3h, gain=pf - pin,
                im3_dbc=p3 - pf, iip3=pin + (pf - p3) / 2.0, nharm=nharm)


def cmd_iip3(root, bands, deck_of, df=DF, pins=PINS, verbose=True):
    results = {}
    for band in bands:
        deck = deck_of(band)
        f0 = BANDS[band]
        print(f"== {band}: f0={f0/1e6:.2f} MHz, deck {os.path.basename(deck)}, "
              f"tones {(f0-df/2)/1e6:.2f}/{(f0+df/2)/1e6:.2f} MHz, "
              f"target IIP3 >= {IIP3_TARGET[band]:+.1f} dBm ==")
        rows = [two_tone(root, deck, f0, p, df) for p in pins]
        if verbose:
            for r in rows:
                print(f"    Pin={r['pin']:+6.1f}  Pfund={r['pfund']:+8.2f}  "
                      f"IM3={r['pim3_lo']:+9.2f}/{r['pim3_hi']:+9.2f}  "
                      f"gain={r['gain']:6.2f}  IM3={r['im3_dbc']:7.1f} dBc  "
                      f"IIP3={r['iip3']:+7.2f} dBm")
        g0 = rows[0]["gain"]
        kept = [r for r in rows if abs(r["gain"] - g0) <= 0.5]
        slope = float(np.polyfit(
            [r["pin"] for r in kept],
            [max(r["pim3_lo"], r["pim3_hi"]) for r in kept], 1)[0])
        iip3s = [r["iip3"] for r in kept]
        iip3 = float(np.median(iip3s))
        tgt = IIP3_TARGET[band]
        ok = iip3 >= tgt
        slope_ok = abs(slope - 3.0) <= 0.3
        print(f"  -> IIP3 = {iip3:+.2f} dBm  (median of {len(kept)} uncompressed "
              f"pts, spread {max(iip3s)-min(iip3s):.2f} dB, IM3 slope "
              f"{slope:.2f}, gain {g0:.2f} dB, OIP3 {iip3+g0:+.2f} dBm)  "
              f"target {tgt:+.1f}  margin {iip3-tgt:+.2f} dB  "
              f"{'PASS' if ok else 'FAIL'}"
              + ("" if slope_ok else "  [!] slope outside 3+/-0.3"))
        results[band] = dict(f0=f0, df=df, deck=os.path.basename(deck),
                             rows=rows, kept=len(kept), slope=slope,
                             slope_ok=slope_ok, gain_ss=g0, iip3_dbm=iip3,
                             oip3_dbm=iip3 + g0,
                             iip3_spread=max(iip3s) - min(iip3s),
                             target_dbm=tgt, verdict="PASS" if ok else "FAIL")
    return results


def cmd_fence(root, deck, band="dhruva-l5", pin=-70.0):
    """Numerical convergence fences on the reported number."""
    f0 = BANDS[band]
    out = {}
    print(f"fence  [{os.path.basename(deck)}] {band}, Pin={pin:.0f} dBm/tone")
    print("  reltol (nharm=5 immax=5, df=2 MHz):")
    out["reltol"] = {}
    for rt in (1e-4, 1e-5, 1e-6, 1e-7, 1e-8, 1e-9):
        r = two_tone(root, deck, f0, pin, DF, reltol=rt)
        out["reltol"][rt] = r["iip3"]
        print(f"    reltol {rt:8.0e} -> IIP3 {r['iip3']:+8.3f} dBm")
    print("  nharm/immax (reltol=1e-6, df=2 MHz):")
    out["nharm"] = {}
    for n in (3, 4, 5, 6, 7, 8):
        r = two_tone(root, deck, f0, pin, DF, nharm=n, immax=n)
        out["nharm"][n] = r["iip3"]
        print(f"    nharm=immax={n}    -> IIP3 {r['iip3']:+8.3f} dBm")
    print("  tone spacing (reltol=1e-6, nharm=5):")
    out["df"] = {}
    for d in (1e6, 2e6, 5e6, 10e6, 20e6, 50e6):
        r = two_tone(root, deck, f0, pin, d)
        out["df"][d] = r["iip3"]
        print(f"    df {d/1e6:6.1f} MHz     -> IIP3 {r['iip3']:+8.3f} dBm")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--op", action="store_true")
    ap.add_argument("--gain", action="store_true")
    ap.add_argument("--iip3", action="store_true")
    ap.add_argument("--fence", action="store_true")
    ap.add_argument("--band", default="all", choices=["all"] + sorted(BANDS))
    ap.add_argument("--own", action="store_true",
                    help="measure each band on its OWN per-band deck "
                         "(dhruva-<band>.sp) instead of the fixed D4-SIM l5 "
                         "sizing -- this is what the sibling ngspice transient "
                         "harness does, so use it for method comparison")
    ap.add_argument("--df", type=float, default=DF)
    ap.add_argument("--pins", default=",".join(str(p) for p in PINS))
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    bands = sorted(BANDS) if a.band == "all" else [a.band]
    pins = [float(x) for x in a.pins.split(",")]
    if not os.path.exists(VACASK):
        raise SystemExit(f"vacask not found at {VACASK} (set VACASK_HOME)")
    l5 = os.path.join(REPRO, "dhruva-l5.sp")
    deck_of = ((lambda b: os.path.join(REPRO, b + ".sp")) if a.own
               else (lambda b: l5))
    none_chosen = not (a.op or a.gain or a.iip3 or a.fence)
    payload = {"fixed_sizing": (not a.own) and "dhruva-l5"}
    root = tempfile.mkdtemp(prefix="hb_iip3_")
    try:
        if a.op or none_chosen:
            payload["op"] = cmd_op(root, l5)
        if a.gain or none_chosen:
            payload["gain"] = cmd_gain(root, bands, l5)
        if a.iip3 or none_chosen:
            payload["iip3"] = cmd_iip3(root, bands, deck_of, df=a.df, pins=pins)
        if a.fence:
            payload["fence"] = cmd_fence(root, l5)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    payload["vacask_retries"] = _RETRY_LOG
    if _RETRY_LOG:
        print(f"[note] {len(_RETRY_LOG)} VACASK invocation(s) were retried "
              f"(transient Windows raw-file lock): {_RETRY_LOG}")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=1, default=float)
        print("wrote", a.json)


if __name__ == "__main__":
    main()

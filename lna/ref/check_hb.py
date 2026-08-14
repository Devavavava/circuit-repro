"""Golden check for the VACASK harmonic-balance IIP3 flow (WP-HB, FINDINGS S40).

Validates two-tone HB + the IIP3 extraction math on closed-form weakly
nonlinear references BEFORE any design is measured (program rule: no
measurement ships without a golden).

Three checks:

G0 -- negative control on the solver tolerance. The SAME circuit and the SAME
     extraction, run at VACASK's default reltol, must FAIL to resolve the IM3
     line (it lands in Newton residual noise and IIP3 blows up by >10 dB).
     This proves `options reltol=1e-6` in the design decks is load-bearing and
     not cargo cult.

G1 -- memoryless cubic transconductor, current-source form.
     i_out = -(a1*v + a3*v^3), a1 = 10, a3 = -1, into RL = 1 ohm, driven by an
     ideal two-tone EMF (no source resistance). For v = A sin(w1 t) + A sin(w2 t):
         fundamental @ f1  : |a1*A + (9/4)*a3*A^3| * RL
         IM3 @ 2*f1 - f2   : (3/4)*|a3|*A^3 * RL
     Analytic intercept (input amplitude) A_IP3 = sqrt(4/3*|a1/a3|) = 3.65148 V.
     In this program's dBm-at-50-ohm convention P(A) = 10*log10(A^2/(2*50)/1e-3),
         IIP3_analytic = +21.2494 dBm.
     (The 50-ohm reference is a bookkeeping convention here -- the golden's
     load is 1 ohm -- and cancels exactly in IIP3 = Pin + (Pf - P3)/2. It is
     kept so every IIP3 number this program prints is in one unit.)
     Also checks the phasor convention (VACASK HB phasors are PEAK amplitudes)
     because the LNA gain cross-check depends on it.

G2 -- cross-method reference: the EXACT reference the sibling ngspice
     two-tone transient golden uses (lna/ref/check_iip3.py), so the two
     harnesses can be compared on identical ground. Memoryless voltage-form
     polynomial y = a1*x + a3*x^3 behind the same Thevenin 50-ohm / 50-ohm
     port network, same (a1, a3) pairs, same available-power sweep, same
     analytic formula A_IP3^2 = (4/3)*(a1/|a3|) at the nonlinearity input,
     IIP3 = 10*log10(A_IP3^2/100 * 1e3) dBm.

PASS bars
  G0  IIP3 error at default reltol > 10 dB (the guard must be seen to bite).
  G1  |IIP3 - analytic| <= 0.15 dB at every probe amplitude; IM3 slope
      3.00 +/- 0.05; phasor convention factor within 1% of 1 (peak).
  G2  |IIP3 - analytic| <= 0.25 dB on every uncompressed point (the sibling's
      own bar), slope 3.00 +/- 0.1, small-signal gain within 0.1 dB of
      20*log10(a1).
"""
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

VACASK_HOME = os.environ.get(
    "VACASK_HOME",
    r"C:\Users\Devavrat\tools\vacask_0.3.4.rc1\vacask_0.3.4.rc1_windows-x86_64")
# binary name is platform-specific; the python helpers live under lib/python on
# the Windows build and lib/vacask/python on the Linux build.
VACASK = os.path.join(VACASK_HOME, "bin",
                      "vacask.exe" if os.name == "nt" else "vacask")
for _pylib in (os.path.join(VACASK_HOME, "lib", "python"),
               os.path.join(VACASK_HOME, "lib", "vacask", "python")):
    if os.path.isdir(_pylib):
        sys.path.insert(0, _pylib)

A1, A3 = 10.0, -1.0
F1, F2 = 1.0e6, 1.1e6
RL = 1.0
Z0 = 50.0
IIP3_ANALYTIC = 10.0 * math.log10((4.0 * abs(A1 / A3) / 3.0) / (2.0 * Z0) / 1e-3)

# No MSVC linker on this machine; MSYS2 provides the GNU one (WORKLOG-class
# gotcha: plain `link` in PATH is GNU coreutils and breaks the MSVC target).
# The windows-gnu target is a Windows-only workaround; on Linux let openvaf pick
# its native target by emitting no override.
VACASKRC = ("""[Binaries]
openvaf_args = [ "--target", "x86_64-pc-windows-gnu" ]
""" if os.name == "nt" else "")

# ---------------------------------------------------------------- G1 netlist
# cubic VCCS (current form) into RL, ideal two-tone EMF, no source resistance
G1_NETLIST = """Golden two-tone HB IIP3 -- cubic VCCS, closed form

load "resistor.osdi"
load "poly3i.va"

model vsource vsource
model resistor resistor
model poly3i poly3i

v1 (in1 0) vsource type="sine" ampl={A} freq={F1}
v2 (in in1) vsource type="sine" ampl={A} freq={F2}
nl1 (in 0 out 0) poly3i
rl (out 0) resistor r={RL}

control
{OPTIONS}  analysis hb1 hb freq=[{F1}, {F2}] nharm=7 immax=5
endc

embed "poly3i.va" <<<FILE
`include "constants.vams"
`include "disciplines.vams"

module poly3i(inp, inn, outp, outn);
    inout inp, inn, outp, outn;
    electrical inp, inn, outp, outn;
    parameter real a1 = {A1};
    parameter real a3 = {A3};
    analog begin
        I(outp,outn) <+ -(a1*V(inp,inn) + a3*pow(V(inp,inn),3));
    end
endmodule
>>>FILE
"""

# ---------------------------------------------------------------- G2 netlist
# voltage-form polynomial behind the sibling harness's Thevenin port network:
# EMF stack -> 50 ohm series -> 50 ohm shunt (so v(x) = Vemf/2) -> y -> 50 ohm
G2_NETLIST = """Golden two-tone HB IIP3 -- cross-method reference (check_iip3 pairs)

load "resistor.osdi"
load "poly3v.va"

model vsource vsource
model resistor resistor
model poly3v poly3v

vt1 (tt_a 0) vsource type="sine" ampl={VEMF} freq={F1}
vt2 (tt_b tt_a) vsource type="sine" ampl={VEMF} freq={F2}
rsrc (tt_b x) resistor r=50
rin (x 0) resistor r=50
bnl (x 0 y 0) poly3v
rload (y 0) resistor r=50

control
  options reltol=1e-6
  analysis hb1 hb freq=[{F1}, {F2}] nharm=5 immax=5
endc

embed "poly3v.va" <<<FILE
`include "constants.vams"
`include "disciplines.vams"

module poly3v(inp, inn, outp, outn);
    inout inp, inn, outp, outn;
    electrical inp, inn, outp, outn;
    parameter real a1 = {A1};
    parameter real a3 = {A3};
    analog begin
        V(outp,outn) <+ a1*V(inp,inn) + a3*pow(V(inp,inn),3);
    end
endmodule
>>>FILE
"""


def dbm50(amp):
    """Amplitude (V, peak) -> dBm into 50 ohm, this program's convention."""
    return 10.0 * math.log10(max(amp, 1e-300) ** 2 / (2.0 * Z0) / 1e-3)


def pav_dbm_to_vemf(p_dbm):
    """Available power per tone (dBm) -> Thevenin EMF amplitude (V).

    Identical to lna/iip3.pav_dbm_to_vemf -- the cross-method contract."""
    return math.sqrt(8.0 * Z0 * 1e-3 * 10 ** (p_dbm / 10.0))


RETRIES = 4


def run_hb(netlist, root, tag, node):
    """Run one HB in a private directory; return (freqs, phasors[node]).

    Private dir per call (repo ngspice convention) is load-bearing -- VACASK
    removes a pre-existing <analysis>.raw before writing -- and is still not
    sufficient on this Windows box: the remove intermittently throws
    'used by another process' even in a fresh empty directory (virus-scanner
    signature, five agents on one machine). Retry on a NEW directory with
    backoff; see lna/hb/hb_iip3.run() for the long-form note.
    """
    from rawfile import rawread
    last = None
    for attempt in range(RETRIES):
        wd = os.path.join(root, f"{tag}_{attempt}")
        os.makedirs(wd, exist_ok=True)
        with open(os.path.join(wd, ".vacaskrc.toml"), "w", encoding="utf-8") as f:
            f.write(VACASKRC)
        with open(os.path.join(wd, "golden.sim"), "w", encoding="utf-8") as f:
            f.write(netlist)
        r = subprocess.run([VACASK, "golden.sim"], cwd=wd,
                           capture_output=True, text=True, timeout=600)
        raw = os.path.join(wd, "hb1.raw")
        if r.returncode == 0 and os.path.exists(raw):
            try:
                plot = rawread(raw).get()
            except Exception:
                last = r
                time.sleep(0.25 * (attempt + 1))
                continue
            return plot["frequency"].real, np.asarray(plot[node]).ravel()
        last = r
        time.sleep(0.25 * (attempt + 1))
    sys.stderr.write((last.stdout or "")[-3000:] + "\n"
                     + (last.stderr or "")[-2000:] + "\n")
    raise SystemExit(f"vacask failed {RETRIES}x (last rc={last.returncode})")


def line(freqs, vec, f):
    """Magnitude of the spectral line nearest f (must be within 1 Hz)."""
    i = int(np.argmin(np.abs(freqs - f)))
    if abs(freqs[i] - f) > 1.0:
        raise SystemExit(f"spectrum has no line at {f} Hz (nearest {freqs[i]})")
    return float(abs(vec[i]))


def g1_net(a, options="  options reltol=1e-6\n"):
    return G1_NETLIST.format(A=repr(a), F1=repr(F1), F2=repr(F2), RL=repr(RL),
                             A1=repr(A1), A3=repr(A3), OPTIONS=options)


def g0_reltol_control(root):
    """Negative control: at default reltol the IM3 line must NOT be resolved."""
    print("G0: reltol negative control (same circuit, VACASK default reltol)")
    a = 0.05
    f, v = run_hb(g1_net(a, options=""), root, "g0", "out")
    v1, v3 = line(f, v, F1), line(f, v, 2 * F1 - F2)
    iip3 = dbm50(a) + 0.5 * (dbm50(v1) - dbm50(v3))
    err = iip3 - IIP3_ANALYTIC
    ok = abs(err) > 10.0
    print(f"  A={a} V  |V@f1|={v1:.6g}  |V@2f1-f2|={v3:.4g}  "
          f"IIP3={iip3:+.2f} dBm  err={err:+.2f} dB")
    print(f"  IM3 unresolved as required (|err| > 10 dB): "
          f"{'GREEN' if ok else 'RED -- the reltol guard is NOT load-bearing'}")
    return ok


def g1_cubic_vccs(root):
    print("G1: memoryless cubic VCCS, closed form  "
          f"(analytic IIP3 = {IIP3_ANALYTIC:+.4f} dBm)")
    amps = [0.05, 0.1, 0.2]
    rows = []
    for k, a in enumerate(amps):
        f, v = run_hb(g1_net(a), root, f"g1_{k}", "out")
        v1, v3 = line(f, v, F1), line(f, v, 2 * F1 - F2)
        rows.append((a, v1, v3, v1 / (abs(A1) * a * RL),
                     dbm50(a) + 0.5 * (dbm50(v1) - dbm50(v3))))
    print(f"  {'A (V)':>8}{'|V@f1|':>12}{'|V@2f1-f2|':>13}{'conv':>9}"
          f"{'IIP3 (dBm)':>12}{'err':>8}")
    ok = True
    for a, v1, v3, conv, iip3 in rows:
        err = iip3 - IIP3_ANALYTIC
        print(f"  {a:>8.3f}{v1:>12.6g}{v3:>13.6g}{conv:>9.4f}{iip3:>12.4f}{err:>+8.3f}")
        ok &= abs(err) <= 0.15
        ok &= abs(conv - 1.0) <= 0.01
    s = ((dbm50(rows[-1][2]) - dbm50(rows[0][2]))
         / (dbm50(rows[-1][0]) - dbm50(rows[0][0])))
    ok &= abs(s - 3.0) <= 0.05
    print(f"  IM3 slope over {amps[0]}->{amps[-1]} V: {s:.4f} "
          f"(expect 3.00 +/- 0.05)   {'GREEN' if ok else 'RED'}")
    return ok


def g2_cross_method(root, a1, a3, pins_dbm, tag):
    """The sibling transient golden's exact reference, measured in HB."""
    ana = 10 * math.log10((4.0 / 3.0) * (a1 / abs(a3)) / 100.0 * 1e3)
    print(f"G2: cross-method reference a1={a1:g} a3={a3:g}  "
          f"analytic IIP3 = {ana:+.3f} dBm")
    rows = []
    for k, pin in enumerate(pins_dbm):
        vemf = pav_dbm_to_vemf(pin)
        net = G2_NETLIST.format(VEMF=repr(vemf), F1=repr(F1), F2=repr(F2),
                                A1=repr(a1), A3=repr(a3))
        f, v = run_hb(net, root, f"{tag}_{k}", "y")
        pf = 0.5 * (dbm50(line(f, v, F1)) + dbm50(line(f, v, F2)))
        p3l = dbm50(line(f, v, 2 * F1 - F2))
        p3h = dbm50(line(f, v, 2 * F2 - F1))
        p3 = max(p3l, p3h)                    # sibling convention: worse sideband
        rows.append(dict(pin=pin, pf=pf, p3=p3, gain=pf - pin,
                         iip3=pin + (pf - p3) / 2.0))
    g0 = rows[0]["gain"]
    kept = [r for r in rows if abs(r["gain"] - g0) <= 0.5]
    slope = float(np.polyfit([r["pin"] for r in kept],
                             [r["p3"] for r in kept], 1)[0])
    errs = [r["iip3"] - ana for r in kept]
    d_gain = g0 - 20 * math.log10(a1)
    ok = (max(abs(e) for e in errs) <= 0.25 and abs(slope - 3.0) <= 0.1
          and abs(d_gain) <= 0.1)
    for r in rows:
        print(f"    Pin={r['pin']:+6.1f}  Pfund={r['pf']:+8.2f}  "
              f"gain={r['gain']:6.2f}  IIP3={r['iip3']:+7.3f}  "
              f"err={r['iip3'] - ana:+6.3f}")
    print(f"  kept {len(kept)}/{len(rows)}  max|err| {max(abs(e) for e in errs):.3f} dB "
          f"(<= 0.25)  slope {slope:.3f} (3 +/- 0.1)  gain err {d_gain:+.3f} dB "
          f"(<= 0.1)   {'GREEN' if ok else 'RED'}")
    return ok


def main():
    if not os.path.exists(VACASK):
        raise SystemExit(f"vacask not found at {VACASK} (set VACASK_HOME)")
    root = tempfile.mkdtemp(prefix="check_hb_")
    try:
        ok = g0_reltol_control(root)
        ok &= g1_cubic_vccs(root)
        # the two (a1, a3) pairs and Pin sweeps of lna/ref/check_iip3.py
        ok &= g2_cross_method(root, 10.0, -200.0,
                              [-30, -28, -26, -24, -22, -20], "g2a")
        ok &= g2_cross_method(root, 4.0, -50.0,
                              [-28, -26, -24, -22, -20, -18], "g2b")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("check_hb:", "GREEN" if ok else "RED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

"""opamp-v0 testbench: deck generation, ngspice runner, metric extraction.

FIXTURE (one DUT copy, AnalogGym-style DC feedback):

    Vdd  vdd 0  VDD                         ideal supply (Idd = -i(Vdd), includes IREF)
    Iref vdd iref  IREF                     the ONE ideal reference current, into IREF
    Vp   vinp 0  dc VCM                     non-inverting input (common mode)
    Vsw  tb_fb vout dc 0                    series offset in the DC feedback path
    Lfb  tb_fb vinn 1T                      DC feedback: VINN = VOUT + Vsw at DC
    Cin  vinn tb_sig 1T                     AC injection at VINN (inductor open at AC)
    Vsig tb_sig 0 dc 0 ac 1
    CL   vout 0  CL

At AC the loop is open (1 TH / 1 TF), so the open-loop gain is A(f) = -v(vout).
At DC the loop is a unity follower, so the operating point is self-consistent with
no ideal bias source other than IREF. Sweeping Vsw at fixed Vp moves VOUT across
the rails while holding the input common mode (open-loop-equivalent DC sweep:
VOUT vs Vid = VINP - VINN); sweeping Vp at Vsw = 0 is the follower DC sweep.

ANALYSES of the main deck, in this fixed order (later ones never change earlier ones):
  1 op                  Idd, VOUT (and device op data in full mode)
  2 ac dec 20 0.01..10G open-loop A(f): DC gain, UGF, PM at the true unity crossing
  3 dc Vsw              output swing (gain >= gain_dc - 6 dB window), out-CM check
  4 dc Vp x Vsw{0,10mV} ICMR (follower tracking <= 50 mV and gain within 6 dB of mid)
  5 ac (CM, supply)     CMRR, PSRR (full mode)
A separate transient deck (full mode, or when slew is constrained) measures slew in
a true follower (VINN tied to VOUT) with a 0.2 V input step.
"""
import math
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "lna"))
from pdk.bptm45 import ADAPTER as _BPTM45   # noqa: E402  (read-only reuse of the model card)

from . import dialect as DL                  # noqa: E402

NGSPICE = os.environ.get("NGSPICE", "ngspice")
VDD_DEFAULT = _BPTM45.vdd                    # 1.1 V
MODEL_PATH = _BPTM45._models_path()          # AutoCkt 45nm_bulk.txt == bptm45
W_FINGER = 2e-6                              # same finger rule as lna/to_spice.W_FINGER
F_MIN, F_MAX, PTS_DEC = 0.01, 1e10, 20
SWEEP_STEP = 0.025
ICMR_DELTA = 0.01
GAIN_WIN = 10 ** (-6.0 / 20)                 # 6 dB
TRACK_TOL = 0.05                             # V
SIM_TIMEOUT = 60


def work_dir():
    base = os.environ.get("OPAMP_V0_TMP") or os.path.join(HERE, "..", "_scratch")
    d = os.path.join(os.path.abspath(base), "w%d" % os.getpid())
    os.makedirs(d, exist_ok=True)
    return d


# ------------------------------------------------------------------ emission
def spice_net(n):
    return {"VINP": "vinp", "VINN": "vinn", "VOUT": "vout", "VDD": "vdd",
            "VSS": "0", "IREF": "iref"}.get(n, "n_" + n)


def spice_name(d):
    return {"NMOS": "m_", "PMOS": "m_", "R": "r_", "C": "c_"}[d.type] + d.name.lower()


def fmt(v):
    return "%.6g" % v


def dut_lines(devs, params):
    """DUT device cards. params: {param_name: float} for every name in param_space."""
    out = []
    for d in devs:
        g = DL.group_of(d.name)
        nets = [spice_net(n) for n in d.nets]
        if d.is_mos:
            w, l = params[g + ".W"], params[g + ".L"]
            nf = max(1, int(math.ceil(w / W_FINGER - 1e-9)))
            model = "nmos" if d.type == "NMOS" else "pmos"
            out.append("%s %s %s W=%s L=%s NF=%d" % (spice_name(d), " ".join(nets), model,
                                                       fmt(w), fmt(l), nf))
        else:
            out.append("%s %s %s" % (spice_name(d), " ".join(nets), fmt(params[g + "." + d.type])))
    return out


def _grid(lo, hi, step, anchor):
    """Grid of points anchor + k*step inside [lo - eps, hi + eps]."""
    k0 = int(math.ceil((lo - anchor) / step - 1e-9))
    k1 = int(math.floor((hi - anchor) / step + 1e-9))
    return [anchor + k * step for k in range(k0, k1 + 1)]


def main_deck(devs, params, tb, wd, icmr=True, full=False):
    vdd, vcm, cl = tb["vdd"], tb["vcm"], tb["cl_pf"] * 1e-12
    sw = _grid(vcm - vdd, vcm, SWEEP_STEP, 0.0)          # vout ~ vcm - vsw in [0, vdd]
    ic = _grid(0.0, vdd, SWEEP_STEP, vcm)
    L = ["* opamp-v0 main deck",
         '.include "%s"' % MODEL_PATH,
         ".temp %s" % fmt(tb["temp_c"]),
         "Vdd vdd 0 dc %s" % fmt(vdd),
         "Iref vdd iref dc %s" % fmt(params["IREF"]),
         "Vp vinp 0 dc %s" % fmt(vcm),
         "Vsw tb_fb vout dc 0",
         "Lfb tb_fb vinn 1T",
         "Cin vinn tb_sig 1T",
         "Vsig tb_sig 0 dc 0 ac 1",
         "CL vout 0 %s" % fmt(cl)]
    L += dut_lines(devs, params)
    L += [".control", "set wr_singlescale", "op"]
    probes = ["v(vout)", "i(vdd)"]
    if full:
        for d in devs:
            if d.is_mos:
                sn = spice_name(d)
                probes += ["@%s[%s]" % (sn, k) for k in
                           ("id", "gm", "gds", "vgs", "vds", "vth", "vdsat")]
    for i in range(0, len(probes), 8):
        L.append("print " + " ".join(probes[i:i + 8]))
    L.append("ac dec %d %s %s" % (PTS_DEC, fmt(F_MIN), fmt(F_MAX)))
    L.append("wrdata %s/ac.txt v(vout)" % wd)
    L.append("dc vsw %s %s %s" % (fmt(sw[0]), fmt(sw[-1] + 1e-9), fmt(SWEEP_STEP)))
    L.append("wrdata %s/sw.txt v(vout) v(vinn)" % wd)
    if icmr:
        L.append("dc vp %s %s %s vsw 0 %s %s" % (fmt(ic[0]), fmt(ic[-1] + 1e-9), fmt(SWEEP_STEP),
                                                fmt(ICMR_DELTA), fmt(ICMR_DELTA)))
        L.append("wrdata %s/ic.txt v(vout) v(vinn)" % wd)
    if full:
        L += ["alter vp ac = 1",
              "ac lin 1 %s %s" % (fmt(F_MIN), fmt(F_MIN)),
              "wrdata %s/cm.txt v(vout)" % wd,
              "alter vp ac = 0", "alter vsig ac = 0", "alter vdd ac = 1",
              "ac lin 1 %s %s" % (fmt(F_MIN), fmt(F_MIN)),
              "wrdata %s/ps.txt v(vout)" % wd]
    L += [".endc", ".end", ""]
    return "\n".join(L), sw, ic


def tran_deck(devs, params, tb, wd, ugf_hz):
    vdd, vcm, cl = tb["vdd"], tb["vcm"], tb["cl_pf"] * 1e-12
    a = 0.1
    tau = 1.0 / (2 * math.pi * max(ugf_hz or 1e6, 1e4))
    pw = min(max(100e-9, 100 * tau), 200e-6)
    td, tr = pw / 10, pw / 1000
    tstop = td + 2 * pw
    L = ["* opamp-v0 tran deck",
         '.include "%s"' % MODEL_PATH,
         ".temp %s" % fmt(tb["temp_c"]),
         "Vdd vdd 0 dc %s" % fmt(vdd),
         "Iref vdd iref dc %s" % fmt(params["IREF"]),
         "Vp vinp 0 dc %s pulse(%s %s %s %s %s %s %s)" % (
             fmt(vcm - a), fmt(vcm - a), fmt(vcm + a), fmt(td), fmt(tr), fmt(tr),
             fmt(pw), fmt(2 * pw + td)),
         "Vfb vinn vout dc 0",
         "CL vout 0 %s" % fmt(cl)]
    L += dut_lines(devs, params)
    L += [".control", "set wr_singlescale",
          "tran %s %s 0 %s" % (fmt(pw / 500), fmt(tstop), fmt(pw / 500)),
          "wrdata %s/tran.txt v(vout)" % wd, ".endc", ".end", ""]
    return "\n".join(L), dict(a=a, td=td, pw=pw, tr=tr, vlo=vcm - a, vhi=vcm + a)


# Small-signal stability gate (Stage 2, README D-O16; opt-in per spec: "stability": "ss_tran").
# The open-loop PM cannot see right-half-plane poles INSIDE the amplifier (local loops of
# multi-stage designs); a true follower given a small input step can. One rising 2 mV step
# (Vcm - 1 mV -> Vcm + 1 mV) at td = 2 tau, observed for SS_WIN_TAU tau (tau = 1/(2 pi UGF),
# window >= 100 ns), max time step tau/4. Invalid ('ss_unstable') iff the output ripple
# (peak-to-peak) over the last 30 % of the window exceeds 5 % of the step, or the settled
# change is off the step by > 20 %, or the transient does not complete.
SS_STEP = 0.001
SS_RIPPLE_TOL = 0.05
SS_SETTLE_TOL = 0.2
SS_WIN_TAU = 60.0
SS_DT_TAU = 0.25


def ss_deck(devs, params, tb, wd, ugf_hz):
    vcm, cl, a = tb["vcm"], tb["cl_pf"] * 1e-12, SS_STEP
    tau = 1.0 / (2 * math.pi * max(ugf_hz or 1e6, 1e4))
    win = min(max(100e-9, SS_WIN_TAU * tau), 200e-6)
    td, tr = 2 * tau, tau / 100
    dt = min(SS_DT_TAU * tau, win / 200)
    tstop = td + win
    L = ["* opamp-v0 small-step stability deck",
         '.include "%s"' % MODEL_PATH,
         ".temp %s" % fmt(tb["temp_c"]),
         "Vdd vdd 0 dc %s" % fmt(tb["vdd"]),
         "Iref vdd iref dc %s" % fmt(params["IREF"]),
         "Vp vinp 0 dc %s pulse(%s %s %s %s %s %s %s)" % (
             fmt(vcm - a), fmt(vcm - a), fmt(vcm + a), fmt(td), fmt(tr), fmt(tr),
             fmt(10 * tstop), fmt(20 * tstop)),
         "Vfb vinn vout dc 0",
         "CL vout 0 %s" % fmt(cl)]
    L += dut_lines(devs, params)
    L += [".control", "set wr_singlescale",
          "tran %s %s 0 %s" % (fmt(dt), fmt(tstop), fmt(dt)),
          "let dvo = v(vout) - %s" % fmt(vcm),
          "wrdata %s/sst.txt dvo" % wd, ".endc", ".end", ""]
    return "\n".join(L), dict(a=a, td=td, win=win, tstop=tstop)


def ss_metrics(rows, p):
    out = {"flags": [], "ss_ripple_rel": None, "ss_settle_err_rel": None}
    td, win, tstop, step = p["td"], p["win"], p["tstop"], 2 * p["a"]
    if not rows or rows[-1][0] < float(fmt(tstop)) * (1 - 1e-4):
        out["flags"].append("ss_unstable")
        out["ss_fail"] = "tran_incomplete"
        return out
    t = [r[0] for r in rows]
    v = [r[1] for r in rows]
    pre = [vv for tt, vv in zip(t, v) if tt <= td * 0.99]
    seg = [vv for tt, vv in zip(t, v) if tt >= td + 0.7 * win]
    if not pre or not seg:
        out["flags"].append("ss_unstable")
        out["ss_fail"] = "no_samples"
        return out
    rip = (max(seg) - min(seg)) / step
    err = abs((v[-1] - pre[-1]) - step) / step
    out["ss_ripple_rel"], out["ss_settle_err_rel"] = rip, err
    if rip > SS_RIPPLE_TOL or not (err <= SS_SETTLE_TOL):
        out["flags"].append("ss_unstable")
    return out


# ------------------------------------------------------------------ running
def run_ngspice(deck, wd, outputs):
    for f in outputs:
        p = os.path.join(wd, f)
        if os.path.exists(p):
            os.remove(p)
    path = os.path.join(wd, "deck.cir")
    with open(path, "w") as fh:
        fh.write(deck)
    try:
        r = subprocess.run([NGSPICE, "-b", path], cwd=wd, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=SIM_TIMEOUT)
        text = r.stdout.decode(errors="replace")
    except subprocess.TimeoutExpired:
        return None, "timeout"
    return text, None


def read_rows(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path) as fh:
        for ln in fh:
            p = ln.split()
            try:
                rows.append([float(x) for x in p])
            except ValueError:
                continue
    return rows


PRINT_RE = re.compile(r"^\s*(\S+)\s*=\s*([-+0-9.eE]+|nan|inf)\s*$", re.I)


def parse_prints(text):
    vals = {}
    for ln in text.splitlines():
        m = PRINT_RE.match(ln)
        if m:
            try:
                vals[m.group(1).lower()] = float(m.group(2))
            except ValueError:
                pass
    return vals


# ------------------------------------------------------------------ extraction
def _unwrap_deg(ph):
    out = [ph[0]]
    for p in ph[1:]:
        d = p - out[-1]
        d -= 360.0 * round(d / 360.0)
        out.append(out[-1] + d)
    return out


def ac_metrics(rows):
    """rows: [f, re, im] of v(vout) with AC injected at VINN -> A = -v(vout)."""
    f = [r[0] for r in rows]
    H = [complex(-r[1], -r[2]) for r in rows]
    mag = [abs(h) for h in H]
    out = {"flags": []}
    a0 = mag[0]
    out["gain_vv"] = a0
    out["gain_db"] = 20 * math.log10(max(a0, 1e-30))
    out["dc_phase_deg"] = math.degrees(math.atan2(H[0].imag, H[0].real))
    if H[0].real <= 0:
        out["flags"].append("polarity")
    ph = _unwrap_deg([math.degrees(math.atan2(h.imag, h.real)) for h in H])
    rel = [p - ph[0] for p in ph]
    crosses = []
    for i in range(1, len(H)):
        up0, up1 = mag[i - 1] >= 1.0, mag[i] >= 1.0
        if up0 != up1:
            g0, g1 = math.log10(max(mag[i - 1], 1e-300)), math.log10(max(mag[i], 1e-300))
            t = g0 / (g0 - g1)
            lf = math.log10(f[i - 1]) + t * (math.log10(f[i]) - math.log10(f[i - 1]))
            phu = rel[i - 1] + t * (rel[i] - rel[i - 1])
            crosses.append({"f": 10 ** lf, "down": up0 and not up1, "pm": 180.0 + phu, "i": i})
    down = [c for c in crosses if c["down"]]
    out["n_unity_crossings"] = len(crosses)
    out["ugf_hz"] = down[0]["f"] if down else None
    out["ugf_mhz"] = down[0]["f"] / 1e6 if down else None
    out["pm_deg"] = min(c["pm"] for c in down) if down else None
    out["pm_at_first_crossing"] = down[0]["pm"] if down else None
    if a0 < 1.0:
        out["flags"].append("no_gain")
    elif not down:
        out["flags"].append("no_unity_crossing")
    if mag[-1] >= 1.0:
        out["flags"].append("ugf_out_of_range")
    if out["pm_deg"] is not None and out["pm_deg"] > 180.0:
        out["flags"].append("pm_unphysical")
    if down:
        ilast = max(c["i"] for c in down)
        jumps = [abs(rel[i] - rel[i - 1]) for i in range(1, ilast + 1)]
        out["max_phase_step_deg"] = max(jumps) if jumps else 0.0
        if out["max_phase_step_deg"] > 120.0:
            out["flags"].append("phase_jump_below_ugf")
    return out


def _edge(x_in, y_in, x_out, y_out):
    """Linear root of y (pass iff y >= 0) between an inside and an outside point."""
    if y_in == y_out:
        return x_in
    t = y_in / (y_in - y_out)
    return x_in + t * (x_out - x_in)


def _window(xs, ys, i0):
    """Contiguous pass window (ys >= 0) around index i0 of an x-sorted grid.
    Returns (lo, hi) with interpolated edges, or None if ys[i0] < 0."""
    if ys[i0] < 0:
        return None
    a = i0
    while a - 1 >= 0 and ys[a - 1] >= 0:
        a -= 1
    b = i0
    while b + 1 < len(xs) and ys[b + 1] >= 0:
        b += 1
    lo = xs[a] if a == 0 else _edge(xs[a], ys[a], xs[a - 1], ys[a - 1])
    hi = xs[b] if b == len(xs) - 1 else _edge(xs[b], ys[b], xs[b + 1], ys[b + 1])
    return lo, hi


def swing_metrics(rows, vcm, gain_ref, vout_dc):
    """rows: [vsw, vout, vinn] of the open-loop-equivalent DC sweep at VINP = vcm.
    Small-signal gain by finite difference between neighbouring points
    A = dVOUT / dVid, Vid = vcm - VINN, placed at the midpoint output level."""
    pts = []
    for r0, r1 in zip(rows[:-1], rows[1:]):
        dvo = r1[1] - r0[1]
        dvid = (vcm - r1[2]) - (vcm - r0[2])
        a = dvo / dvid if dvid != 0 else 0.0
        pts.append(((r0[1] + r1[1]) / 2.0, a))
    pts.sort()
    out = {"swing_vpp": 0.0, "swing_lo": None, "swing_hi": None, "flags": []}
    if not pts or gain_ref is None or gain_ref <= 0:
        out["flags"].append("swing_unmeasured")
        return out
    xs = [p[0] for p in pts]
    gs = [p[1] for p in pts]
    thr = gain_ref * GAIN_WIN
    ys = [math.log10(max(g, 1e-30) / thr) for g in gs]
    i0 = min(range(len(xs)), key=lambda i: abs(xs[i] - vout_dc))
    w = _window(xs, ys, i0)
    gpk = max(gs)
    out["swing_gain_peak_vv"] = gpk
    out["swing_vout_at_peak"] = xs[gs.index(gpk)]
    if gpk <= 0:   # Stage 2 fix (D-O15): no positive-gain point at all (used to raise)
        out["flags"] += ["swing_empty", "outcm_outside_swing_window"]
        out["outcm_window"] = None
        return out
    if w is None:
        out["flags"].append("swing_empty")
    else:
        out["swing_lo"], out["swing_hi"] = w
        out["swing_vpp"] = w[1] - w[0]
    # out-CM check: the operating output level must sit inside the window where the
    # gain is within 6 dB of the PEAK gain of the sweep (else the amp is biased off
    # its high-gain region and gain_dc-referenced swing would be misleading).
    ypk = [math.log10(max(g, 1e-30) / (gpk * GAIN_WIN)) for g in gs]
    wpk = _window(xs, ypk, i0)
    out["outcm_window"] = list(wpk) if wpk else None
    if wpk is None:
        out["flags"].append("outcm_outside_swing_window")
    return out


def icmr_metrics(rows, vcm):
    """rows: [vp, vout, vinn], first block Vsw = 0 (follower), second Vsw = +delta.
    Gain at each input CM: A = dVOUT / dVid between the two blocks."""
    n = len(rows) // 2
    out = {"icmr_v": 0.0, "icmr_lo": None, "icmr_hi": None, "flags": []}
    if n < 3 or len(rows) != 2 * n:
        out["flags"].append("icmr_unmeasured")
        return out
    b0, b1 = rows[:n], rows[n:]
    xs, gs, errs = [], [], []
    for r0, r1 in zip(b0, b1):
        vin = r0[0]
        dvid = (vin - r1[2]) - (vin - r0[2])
        a = (r1[1] - r0[1]) / dvid if dvid != 0 else 0.0
        xs.append(vin)
        gs.append(a)
        errs.append(r0[1] - vin)
    i0 = min(range(n), key=lambda i: abs(xs[i] - vcm))
    gmid = gs[i0]
    out["icmr_gain_mid_vv"] = gmid
    if gmid <= 0:
        out["flags"].append("icmr_empty")
        return out
    thr = gmid * GAIN_WIN
    ys = []
    for g, e in zip(gs, errs):
        yg = math.log10(max(g, 1e-30) / thr) / math.log10(1.0 / GAIN_WIN)  # 0 at -6 dB
        ye = (TRACK_TOL - abs(e)) / TRACK_TOL                               # 0 at 50 mV
        ys.append(min(yg, ye))
    w = _window(xs, ys, i0)
    if w is None:
        out["flags"].append("icmr_empty")
    else:
        out["icmr_lo"], out["icmr_hi"] = w
        out["icmr_v"] = w[1] - w[0]
    return out


def tran_metrics(rows, p):
    """Slew = 0.6*step / (t80 - t20) on each edge, min of rise and fall (V/us)."""
    out = {"flags": []}
    if not rows:
        out["flags"].append("tran_failed")
        return out
    t = [r[0] for r in rows]
    v = [r[1] for r in rows]
    step = p["vhi"] - p["vlo"]

    def cross_time(t0, t1, level, rising):
        for i in range(1, len(t)):
            if t[i] < t0 or t[i - 1] > t1:
                continue
            a, b = v[i - 1], v[i]
            if (rising and a < level <= b) or ((not rising) and a > level >= b):
                return t[i - 1] + (level - a) / (b - a) * (t[i] - t[i - 1])
        return None

    def at(tq):
        for i in range(1, len(t)):
            if t[i] >= tq:
                return v[i - 1] + (v[i] - v[i - 1]) * (tq - t[i - 1]) / max(t[i] - t[i - 1], 1e-30)
        return v[-1]

    td, pw = p["td"], p["pw"]
    v0 = at(td * 0.99)
    v1 = at(td + pw * 0.99)
    v2 = at(td + 2 * pw * 0.995)
    rs = {}
    for name, (ta, tb, lo, hi, rising) in {
            "rise": (td, td + pw, v0, v1, True),
            "fall": (td + pw, td + 2 * pw, v1, v2, False)}.items():
        span = hi - lo
        if abs(span) < 0.5 * step:
            rs[name] = None
            continue
        t20 = cross_time(ta, tb, lo + 0.2 * span, rising)
        t80 = cross_time(ta, tb, lo + 0.8 * span, rising)
        rs[name] = (0.6 * abs(span) / (t80 - t20) / 1e6) if (t20 and t80 and t80 > t20) else None
    out["slew_rise_vus"], out["slew_fall_vus"] = rs["rise"], rs["fall"]
    vals = [x for x in rs.values() if x is not None]
    out["slew_vus"] = min(vals) if len(vals) == 2 else None
    out["tran_settled"] = (abs(v1 - p["vhi"]) < 0.02 * step + TRACK_TOL
                           and abs(v2 - p["vlo"]) < 0.02 * step + TRACK_TOL)
    # ripple: peak-to-peak over the last 30 % of the high pulse (oscillation detector)
    seg = [vv for tt, vv in zip(t, v) if td + 0.7 * pw <= tt <= td + 0.99 * pw]
    out["tran_ripple_v"] = (max(seg) - min(seg)) if seg else None
    if out["tran_ripple_v"] is not None and out["tran_ripple_v"] > 0.05 * step:
        out["flags"].append("tran_oscillation")
        out["tran_settled"] = False
    if out["slew_vus"] is None:
        out["flags"].append("slew_unmeasured")
    return out


# ------------------------------------------------------------------ evaluate
INVALID_FLAGS = ("sim_fail", "polarity", "no_gain", "no_unity_crossing", "ugf_out_of_range",
                 "pm_unphysical", "phase_jump_below_ugf", "vout_not_tracking",
                 "outcm_outside_swing_window", "idd_nonpositive", "ss_unstable")


def measure(devs, params, tb, icmr=True, full=False, slew=None, stab=False):
    """One evaluation. Returns metrics dict (always), with 'valid' and 'flags'.
    stab=True adds the small-step stability gate (run only if the design is otherwise valid)."""
    wd = work_dir()
    deck, _sw, _ic = main_deck(devs, params, tb, wd, icmr=icmr, full=full)
    outs = ["ac.txt", "sw.txt", "ic.txt", "cm.txt", "ps.txt"]
    text, err = run_ngspice(deck, wd, outs)
    m = {"flags": []}
    if text is None:
        m["flags"].append("sim_fail")
        m["sim_error"] = err
        m["valid"] = False
        return m
    pv = parse_prints(text)
    ac = read_rows(os.path.join(wd, "ac.txt"))
    if "v(vout)" not in pv or "i(vdd)" not in pv or len(ac) < 10:
        m["flags"].append("sim_fail")
        bad = [ln for ln in text.splitlines() if "rror" in ln or "singular" in ln.lower()]
        m["sim_error"] = bad[0][:200] if bad else "no op/ac output"
        m["valid"] = False
        return m
    vcm = tb["vcm"]
    m["vout_dc"] = pv["v(vout)"]
    m["offset_mv"] = (pv["v(vout)"] - vcm) * 1e3
    m["idd_ua"] = -pv["i(vdd)"] * 1e6
    if m["idd_ua"] <= 0:
        m["flags"].append("idd_nonpositive")
    if abs(m["offset_mv"]) > TRACK_TOL * 1e3:
        m["flags"].append("vout_not_tracking")
    a = ac_metrics(ac)
    m["flags"] += a.pop("flags")
    m.update(a)
    s = swing_metrics(read_rows(os.path.join(wd, "sw.txt")), vcm, m["gain_vv"], m["vout_dc"])
    m["flags"] += s.pop("flags")
    m.update(s)
    if icmr:
        c = icmr_metrics(read_rows(os.path.join(wd, "ic.txt")), vcm)
        m["flags"] += c.pop("flags")
        m.update(c)
    if m.get("ugf_mhz") is not None and m["idd_ua"] > 0:
        m["fom_mhzpf_ma"] = m["ugf_mhz"] * tb["cl_pf"] / (m["idd_ua"] / 1e3)
    else:
        m["fom_mhzpf_ma"] = None
    if full:
        cm = read_rows(os.path.join(wd, "cm.txt"))
        ps = read_rows(os.path.join(wd, "ps.txt"))
        if cm:
            acm = abs(complex(cm[0][1], cm[0][2]))
            m["cmrr_db"] = m["gain_db"] - 20 * math.log10(max(acm, 1e-30))
        if ps:
            aps = abs(complex(ps[0][1], ps[0][2]))
            m["psrr_db"] = m["gain_db"] - 20 * math.log10(max(aps, 1e-30))
        ops = {}
        for d in devs:
            if d.is_mos:
                sn = spice_name(d)
                ops[d.name] = {k: pv.get("@%s[%s]" % (sn, k)) for k in
                               ("id", "gm", "gds", "vgs", "vds", "vth", "vdsat")}
        m["op"] = ops
    if full or slew:
        tdeck, tp = tran_deck(devs, params, tb, wd, m.get("ugf_hz"))
        ttext, terr = run_ngspice(tdeck, wd, ["tran.txt"])
        tr = tran_metrics(read_rows(os.path.join(wd, "tran.txt")) if ttext else [], tp)
        m["flags"] += tr.pop("flags")
        m.update(tr)
    m["valid"] = not any(f in INVALID_FLAGS for f in m["flags"])
    if stab:
        apply_ss(devs, params, tb, m)
    return m


def apply_ss(devs, params, tb, m):
    """Run the small-step stability gate on an already measured design (in place); skipped
    (ss_checked False) if the design is already invalid."""
    if not m.get("valid"):
        m["ss_checked"] = False
        return m
    wd = work_dir()
    sdeck, sp = ss_deck(devs, params, tb, wd, m.get("ugf_hz"))
    stext, _ = run_ngspice(sdeck, wd, ["sst.txt"])
    ss = ss_metrics(read_rows(os.path.join(wd, "sst.txt")) if stext else [], sp)
    m["flags"] += ss.pop("flags")
    m.update(ss)
    m["ss_checked"] = True
    m["valid"] = not any(f in INVALID_FLAGS for f in m["flags"])
    return m

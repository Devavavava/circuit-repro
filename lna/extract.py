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
import contextlib
import math
import os
import re
import shutil
import subprocess
import tempfile

NGSPICE = os.environ.get("NGSPICE", r"C:\msys64\ucrt64\bin\ngspice_con.exe")
_NUM = r"([-\d.eE+]+)"
K4TRS = 8.283894e-19          # 4kT*50 at 300 K

# Every ngspice caller in this tree used to `mkdtemp` per call and none of them
# cleaned up (FINDINGS §15 hygiene note). One overnight campaign is ~1e5 calls;
# the shared %TEMP% had accumulated 685k stale `size_*`/`nf_*`/`bias_*` dirs,
# at which point creating one more directory is the slowest part of a 0.07 s
# evaluation and merely listing %TEMP% takes minutes. Scratch is now scoped to
# the call. Set LNA_KEEP_TMP=1 to keep the decks for debugging.
_KEEP_TMP = os.environ.get("LNA_KEEP_TMP", "") not in ("", "0", "false", "False")


@contextlib.contextmanager
def scratch(prefix):
    """A per-call scratch directory that deletes itself on the way out."""
    d = tempfile.mkdtemp(prefix=prefix)
    try:
        yield d
    finally:
        if not _KEEP_TMP:
            shutil.rmtree(d, ignore_errors=True)


def run_deck(text, prefix, fname, timeout=60):
    """Write a deck into self-deleting scratch, run ngspice -b, return combined
    stdout+stderr (or None on timeout). The single ngspice entry point."""
    with scratch(prefix) as d:
        p = os.path.join(d, fname)
        with open(p, "w") as fh:
            fh.write(text)
        try:
            r = subprocess.run([NGSPICE, "-b", p], capture_output=True,
                               text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None
        return (r.stdout or "") + (r.stderr or "")


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


# ------------------------------------------------------------- op capture
# WP-OBSERVE (plans2/09-WP-OBSERVE.md). Every evaluation in this pipeline solves
# a full DC operating point and then throws it away to keep a seven-number metric
# vector. These helpers read it back out of the run that already happened.
#
# THREE RULES, all load-bearing:
#   1. NEVER `save`. `save @m1[id]` before `sp` *restricts* ngspice's saved set
#      and silently deletes the S-parameters (gotcha N1). Single-`op` device
#      parameters need no `save` at all -- measured, not assumed.
#   2. No extra invocation. The probe lines ride along in the deck the caller was
#      already going to run.
#   3. Print-only: no analysis, no `.option`, no `let`, so the solved circuit
#      cannot move. `ref/check_op.py` proves the metrics are bit-identical with
#      the probe present and absent.
#
# Parameter availability was probed against this ngspice/BSIM4 build: id, gm,
# gds, gmbs, vgs, vds, vbs, vth, vdsat, cgg, cgs, cgd exist; cd / ids / is / ig /
# ib / vth0 / rg / von / beta / gmb do NOT ("Error: no such parameter"). BSIM4
# here has no `region` output, so region is DERIVED below from
# (id, vgs, vth, vds, vdsat) using bias.py's own thresholds.
MOS_OP_PARAMS = ("id", "gm", "gds", "gmbs", "vgs", "vds", "vbs", "vth", "vdsat")
BJT_OP_PARAMS = ("ic", "ib", "vbe", "vbc", "gm", "cpi", "cmu")
OP_SCHEMA = 1                # bump when the read-out or the region rule changes

_ID_MIN = 50e-6              # A -- bias.ID_MIN ("conducting")
_VDS_MARGIN = 1.5            # bias.VDS_MARGIN (|Vds| >= 1.5|Vdsat| -> saturated)
_OP_DEV_RE = re.compile(r"^([MQ])(\w*)", re.IGNORECASE)
_OP_VAL_RE = re.compile(rf"@(\w+)\[(\w+)\]\s*=\s*{_NUM}", re.IGNORECASE)
_OP_NODE_RE = re.compile(rf"^\s*([A-Za-z_][\w#.]*)\s*=\s*{_NUM}\s*$")
_OP_BEGIN, _OP_END = "op_nodes_begin", "op_nodes_end"
_OP_NOT_A_NODE = ("idd",)    # `let` vectors that share the op plot with the nodes


def op_devices(body):
    """(mosfets, bipolars) element names present in a deck body, lowercased.

    to_spice emits MOSFETs as `M<dev>` and bipolars as `Q<dev>`; bias.py's
    inserted scaffold is `RBIAS*`/`CBYP*`/`VBGEN*`, none of which start with M or
    Q. ngspice lowercases element names, so the `@m1[...]` spelling is derived
    from the deck rather than costing a probe run -- the same trick
    `noise_elements` uses."""
    mos, bjt = [], []
    for ln in body.splitlines():
        m = _OP_DEV_RE.match(ln.strip())
        if not m:
            continue
        (mos if m.group(1).upper() == "M" else bjt).append(
            (m.group(1) + m.group(2)).lower())
    return mos, bjt


def op_probe_lines(body, nodes=True, chunk=8):
    """ngspice control lines that dump the operating point. PRINT ONLY.

    `chunk` keeps each `print` under ngspice's line-wrap width -- the same reason
    `measure_noise_budget` chunks at 8."""
    mos, bjt = op_devices(body)
    vecs = [f"@{d}[{p}]" for d in mos for p in MOS_OP_PARAMS]
    vecs += [f"@{d}[{p}]" for d in bjt for p in BJT_OP_PARAMS]
    lines = ["print " + " ".join(vecs[i:i + chunk])
             for i in range(0, len(vecs), chunk)]
    if nodes:
        # `print all` dumps every vector of the op plot, so node names need not be
        # enumerated (generated topologies have arbitrary ones). The echo markers
        # bound the dump so the metric parse can never mistake a node name for a
        # `meas` result.
        lines += [f"echo {_OP_BEGIN}", "print all", f"echo {_OP_END}"]
    return lines


def mos_region(d):
    """'off' | 'sub' | 'triode' | 'sat' from one MOSFET's op dict, or None.

    Deliberately the SAME thresholds `bias.conducting` / `bias.saturated` use
    (|Id| >= 50 uA; |Vds| >= 1.5|Vdsat|), so an op row and an L1 row can never
    disagree about whether a device is on. 'sub' is conducting-but-below-threshold
    (|Vgs| < |Vth|) -- the case neither bias predicate can express, and the one
    that explains a device carrying current with no gate overdrive."""
    idv = d.get("id")
    if idv is None:
        return None
    if abs(idv) < _ID_MIN:
        return "off"
    vgs, vth = d.get("vgs"), d.get("vth")
    if vgs is not None and vth is not None and abs(vgs) < abs(vth):
        return "sub"
    vds, vdsat = d.get("vds"), d.get("vdsat")
    if vds is None or vdsat is None:
        return None
    return "sat" if abs(vds) >= _VDS_MARGIN * abs(vdsat) else "triode"


def parse_op(out):
    """ngspice stdout -> {schema, devices, nodes, branches}.

    `devices` maps the lowercased element name to its parameter dict plus a
    derived `region` and `vov = vgs - vth`. `nodes` holds real net voltages;
    model-internal nodes (`m1#body`, `m1#gate`, `m1#dbody`, `m1#sbody` -- four per
    MOSFET, artefacts of rgatemod/rbodymod, all ~1e-11 V) are dropped, and
    `*#branch` currents go to `branches`, because that is where per-source
    current -- including the supply -- actually lives."""
    devices = {}
    for m in _OP_VAL_RE.finditer(out):
        try:
            val = float(m.group(3))
        except ValueError:
            continue
        devices.setdefault(m.group(1).lower(), {})[m.group(2).lower()] = val
    for name, d in devices.items():
        if "vgs" in d and "vth" in d:
            d["vov"] = round(d["vgs"] - d["vth"], 9)
        r = mos_region(d) if name.startswith("m") else None
        if r:
            d["region"] = r
    nodes, branches = {}, {}
    seg = out.split(_OP_BEGIN)
    if len(seg) > 1:
        for ln in seg[1].split(_OP_END)[0].splitlines():
            mm = _OP_NODE_RE.match(ln)
            if not mm:
                continue
            name = mm.group(1).lower()
            try:
                val = float(mm.group(2))
            except ValueError:
                continue
            if name.endswith("#branch"):
                branches[name[:-7]] = val
            elif "#" in name or name in _OP_NOT_A_NODE:
                continue                    # model-internal node / derived vector
            else:
                nodes[name] = val
    return {"schema": OP_SCHEMA, "devices": devices, "nodes": nodes,
            "branches": branches}


def control_block(f0, f_lo, f_hi, supply, op_probe=None):
    """op + Idd + S-parameters + stability. NF is NOT taken from this (port-driven)
    deck: inoise referred to the S-param port is unphysical with gain (finding #7).
    The trusted NF comes from the separate series-Rs deck (measure_nf).

    `op_probe` (control lines from `op_probe_lines`) is spliced in between
    `print idd` and `sp`: print-only, no `save` (gotcha N1), no extra analysis.
    With it None the returned string is byte-identical to the pre-WP-OBSERVE one.
    """
    return "\n".join([
        ".control", "op",
        f"let idd = -i({supply})", "print idd",
    ] + list(op_probe or []) + [
        f"sp lin 101 {f_lo:g} {f_hi:g} 1",
        "let s11db = db(mag(S_1_1)+1e-30)",
        "let s21db = db(mag(S_2_1)+1e-30)",
        f"meas sp m_s11_f0 find s11db at={f0:g}",
        f"meas sp m_s11_max max s11db from={f_lo:g} to={f_hi:g}",
        f"meas sp m_s21_f0 find s21db at={f0:g}",
        f"meas sp m_s21_min min s21db from={f_lo:g} to={f_hi:g}",
        f"meas sp m_s21_max max s21db from={f_lo:g} to={f_hi:g}",
    ] + _stability_lets() + _stability_meas(f0, f_lo, f_hi) + [".endc", ".end"])


def build_deck(body, params, f0, f_lo, f_hi, supply=None, op_probe=None):
    supply = supply or _supply_name(body)
    lines = [body.rstrip()]
    if params:
        lines.append(".param " + " ".join(f"{k}={v}" for k, v in params.items()))
    lines.append(control_block(f0, f_lo, f_hi, supply, op_probe=op_probe))
    return "\n".join(lines) + "\n"


def run_and_extract(body, params, spec, op_capture=None):
    """Run one ngspice evaluation; return a metrics dict (or None on failure).

    WP-OBSERVE: if `op_capture` is a dict it is filled IN PLACE with the operating
    point (`parse_op` shape) read out of the SAME ngspice process -- the `op` this
    deck already runs. The return value is unaffected, so every existing caller is
    untouched, and with `op_capture=None` the deck text is byte-identical."""
    band = spec.band
    f0 = float(band.get("f0", 2.442e9))
    f_lo = float(band.get("f_lo", f0 * 0.98))
    f_hi = float(band.get("f_hi", f0 * 1.02))
    probe = op_probe_lines(body) if op_capture is not None else None
    deck = build_deck(body, params, f0, f_lo, f_hi, op_probe=probe)
    out = run_deck(deck, "size_", "c.cir")
    if out is None:
        return None
    if "singular matrix" in out.lower():
        return None
    if op_capture is not None:
        op_capture.update(parse_op(out))
        op_capture["deck"] = "sizing"

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
    out = run_deck("\n".join(lines) + "\n", "stab_", "s.cir", timeout=120)
    if out is None:
        return None

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


def build_noise_deck(body, params, f0, f_lo, f_hi, rs=50.0, rl=50.0,
                     op_probe=None):
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
    deck += [".control", "op"] + list(op_probe or []) + [
             f"noise v({node_out}) Vnz lin 51 {f_lo:g} {f_hi:g}",
             "setplot noise1",
             f"let nfv = 10*log10((inoise_spectrum*inoise_spectrum)/{K4TRS:.6e})",
             f"let m_nf_f0 = nfv[{nf_idx}]", "print m_nf_f0",
             ".endc", ".end"]
    return "\n".join(deck) + "\n", node_in, node_out


def measure_nf(body, params, spec, rs=50.0, op_capture=None):
    """Physical noise figure at f0 via a series-Rs source (finding #7 fix).

    Returns nf_db (float) or None on failure. Separate from run_and_extract's
    op/sp block: NF needs a different input drive (series-Rs, not a port), so it
    is a second ~1 s ngspice call, made once per label at the sized point rather
    than every ZOAF iteration.

    WP-OBSERVE: this deck runs its own `op`, so passing an `op_capture` dict
    harvests the operating point from it at zero extra cost. That is what gives
    `size.log_l2_result` -- the hub every polish/search driver logs through --
    device-level data with no new ngspice invocation anywhere. The noise deck's
    DC is identical to the sizing deck's by construction (both port sources were
    `dc 0` and the blocking caps are kept); `ref/check_op.py` tests that claim
    numerically rather than trusting this docstring, and the stored row records
    which deck it came from either way."""
    band = spec.band
    f0 = float(band.get("f0", 2.442e9))
    f_lo = float(band.get("f_lo", f0 * 0.98))
    f_hi = float(band.get("f_hi", f0 * 1.02))
    probe = op_probe_lines(body) if op_capture is not None else None
    deck, _, _ = build_noise_deck(body, params, f0, f_lo, f_hi, rs=rs,
                                  op_probe=probe)
    if deck is None:
        return None
    out = run_deck(deck, "nf_", "nf.cir")
    if out is None:
        return None
    if "singular matrix" in out.lower():
        return None
    if op_capture is not None:
        op_capture.update(parse_op(out))
        op_capture["deck"] = "noise"
    m = re.search(rf"m_nf_f0\s*=\s*{_NUM}", out, re.IGNORECASE)
    return float(m.group(1)) if m else None


_ELEM_RE = re.compile(r"^([MR])(\w+)", re.IGNORECASE)
# BSIM4 noise mechanisms ngspice exposes per MOSFET, in the order we report them.
_MOS_MECH = ("id", "1overf", "rg", "rd", "rs", "igs", "igd", "igb",
             "rbps", "rbpd", "rbpb", "rbsb", "rbdb")


def noise_elements(deck_body):
    """(mosfets, resistors) element names present in a noise deck body.

    ngspice names the per-source noise vectors with TWO different conventions --
    `onoise.<mos>` (dotted, with per-mechanism children like `.id`) and
    `onoise_<res>` (underscored). Both are lowercased element names, so the
    vector list can be derived from the deck instead of a second probe run."""
    mos, res = [], []
    for ln in deck_body.splitlines():
        m = _ELEM_RE.match(ln.strip())
        if not m:
            continue
        (mos if m.group(1).upper() == "M" else res).append(
            (m.group(1) + m.group(2)).lower())
    return mos, res


def measure_noise_budget(body, params, spec, f=None, rs=50.0, mechanisms=True):
    """Per-element output-noise contributions at `f` (default f0) -- the BUDGET.

    `measure_nf` answers "how much noise"; this answers "whose". ngspice's noise
    analysis builds one spectral-density vector per elementary noise source, but
    ONLY when the `noise` line carries a `pts_per_summary` argument -- without it
    just the totals exist, which is why this needs its own deck rather than a
    parse of the existing one. The sweep is placed with its first point exactly
    on `f`, so the reading is at f0 and not at the nearest point of the 51-point
    grid `measure_nf` uses (measured error on the dhruva bands: <= 0.01 dB, but
    free to avoid here).

    Contributions are returned as **output-referred noise POWER** (V^2/Hz), which
    is the additive quantity. Each element's share of the total, and its share of
    the excess noise factor F-1 = (P_tot - P_Rs)/P_Rs, are the two useful views:
    the first says what dominates the output, the second says what the noise
    figure is actually paying for.

    Returns {"f": f, "p_total", "p_source", "nf_db_from_shares", "nf_db_inoise",
             "elements": {name: {"p", "frac", "excess_frac", "mech": {...}}}}
    or None. `mechanisms=False` skips the per-MOSFET breakdown (fewer prints).
    """
    band = spec.band
    f = float(band.get("f0", 2.442e9)) if f is None else float(f)
    deck, _nin, nout = build_noise_deck(body, params, f,
                                        float(band.get("f_lo", f * 0.98)),
                                        float(band.get("f_hi", f * 1.02)), rs=rs)
    if deck is None:
        return None
    head = deck.split(".control")[0]
    mos, res = noise_elements(head)
    lets, names = [], []

    def add(tag, vec):
        lets.append(f"let {tag} = {vec}[0]*{vec}[0]")
        names.append(tag)

    for i, d in enumerate(mos):
        add(f"pm{i}", f"onoise.{d}")
        if mechanisms:
            for k, mech in enumerate(_MOS_MECH):
                add(f"pm{i}_{k}", f"onoise.{d}.{mech}")
    for i, d in enumerate(res):
        add(f"pr{i}", f"onoise_{d}")
    ctrl = ["\n.control", "op",
            f"noise v({nout}) Vnz lin 2 {f:g} {f * 1.0001:g} 1", "setplot noise1",
            "let ptot = onoise_spectrum[0]*onoise_spectrum[0]",
            f"let nfi = 10*log10((inoise_spectrum[0]*inoise_spectrum[0])/{K4TRS:.6e})"]
    ctrl += lets + ["print ptot nfi"]
    for i in range(0, len(names), 8):            # ngspice wraps long print lines
        ctrl.append("print " + " ".join(names[i:i + 8]))
    ctrl += [".endc", ".end"]
    out = run_deck(head + "\n".join(ctrl) + "\n", "nfbud_", "n.cir", timeout=120)
    if out is None or "singular matrix" in out.lower():
        return None

    def g(tag):
        m = re.search(rf"(?<![\w.]){re.escape(tag)}\s*=\s*{_NUM}", out, re.IGNORECASE)
        try:
            return float(m.group(1)) if m else None
        except ValueError:
            return None

    p_tot, nf_inoise = g("ptot"), g("nfi")
    if p_tot is None:
        return None
    elems = {}
    for i, d in enumerate(mos + res):
        tag = f"pm{i}" if i < len(mos) else f"pr{i - len(mos)}"
        p = g(tag)
        if p is None:
            continue
        e = {"p": p, "kind": "mos" if i < len(mos) else "res"}
        if mechanisms and i < len(mos):
            mm = {}
            for k, mech in enumerate(_MOS_MECH):
                v = g(f"pm{i}_{k}")
                if v:
                    mm[mech] = v
            e["mech"] = mm
        elems[d] = e
    src = f"r{'ns'}"                       # build_noise_deck always names it Rns
    p_src = (elems.get("rns") or {}).get("p")
    p_sum = sum(e["p"] for e in elems.values())
    for e in elems.values():
        e["frac"] = e["p"] / p_tot if p_tot else None
        e["excess_frac"] = (e["p"] / (p_tot - p_src)
                            if p_src and p_tot > p_src else None)
    return {"f": f, "p_total": p_tot, "p_sum": p_sum, "p_source": p_src,
            "source_elem": src, "elements": elems,
            "nf_db_inoise": nf_inoise,
            "nf_db_from_shares": (10 * math.log10(p_tot / p_src)
                                  if p_src else None),
            "sum_closure": (p_sum / p_tot) if p_tot else None}


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
    out = run_deck(deck, "nfself_", "nf.cir") or ""
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

"""Validate the bipolar emission path in `to_spice.py` -- and its model cards.

`lna/to_spice.py` gained NPN/PNP emission because AnalogGenie's vocabulary and
`topology.py`'s LEGAL always carried 3-terminal C/B/E bipolars while the emitter
did not, and a real ingested circuit needs them (IHP's open SG13G2 GPS_LNA ships
an HBT variant beside its NMOS one). The 45 nm BSIM4 include has no bipolar
models, so `to_spice.BJT_MODELS` supplies generic Gummel-Poon cards.

A generic card is a claim, and this file is where the claim is checked rather
than asserted. Three kinds of check, mirroring `check_stab.py`'s structure:

  1. ANALYTIC GOLDENS on the model cards themselves. Bias one device in
     forward-active and require ngspice's operating point to reproduce the
     closed-form Gummel-Poon predictions from the very parameters in the card:
       * beta = Ic/Ib against bf, corrected for the Early effect and for the
         low-current ISE/NE leakage term -- both of which the card enables, so
         the naive `beta == bf` would be WRONG and is not what is checked;
       * fT from the small-signal current gain, against
             fT = 1 / (2*pi*(tf + (Cje+Cjc)*Vt/Ic + (re+rc)*Cjc))
         which is the textbook expression for exactly this parameter set. This
         is the number that decides whether a bipolar deck behaves like an RF
         device at all in the 1-4 GHz band the harness simulates.
  2. AN EMITTER GOLDEN. A hand-written CE amplifier deck and the *same* circuit
     expressed as an AnalogGenie token sequence and pushed through
     `to_spice.Netlist` must produce the same DC operating point. That is a
     from-scratch reproduction through a completely different input path, so it
     tests the token -> pin -> node -> `Q` element mapping (C/B/E pin order is
     the thing that silently corrupts a bipolar netlist), not just the model.
  3. A REGRESSION FENCE. Emitting a MOS-only topology must not put a `.model
     q*` card, or any `Q` element, in the deck -- that invariant is what makes
     the change additive and every pre-existing deck byte-identical.

    python lna/ref/check_bjt.py
    python lna/ref/check_bjt.py --verbose
"""
import argparse
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.dirname(HERE)
sys.path.insert(0, LNA)
import extract as E                                   # noqa: E402
import to_spice as TS                                 # noqa: E402
from topology import Topology                         # noqa: E402

VT = 0.025852                    # kT/q at TNOM=27 C, ngspice's default
_NUM = r"([-+]?[\d.]+(?:[eE][-+]?\d+)?)"


# ------------------------------------------------------------------ helpers
def card_params(kind):
    """{param: float} parsed out of a BJT_MODELS card. The goldens are computed
    from the CARD, not from numbers retyped here, so editing a card cannot leave
    a stale expectation silently passing."""
    _, text = TS.BJT_MODELS[kind]
    body = text[text.index("(") + 1:text.rindex(")")]
    body = body.replace("\n", " ").replace("+", " ")
    suf = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3}
    out = {}
    for name, val in re.findall(r"(\w+)\s*=\s*([\w.+-]+)", body):
        m = re.match(r"^([-+]?[\d.]+(?:[eE][-+]?\d+)?)([a-zA-Z]*)$", val)
        if not m:
            continue
        num = float(m.group(1))
        s = m.group(2).lower()
        if s in suf:
            num *= suf[s]
        elif s:                                        # e.g. "meg" -- not used
            continue
        out[name.lower()] = num
    return out


def _print_vals(out):
    vals = {}
    for m in re.finditer(rf"(\w+)\s*=\s*{_NUM}", out):
        vals[m.group(1).lower()] = float(m.group(2))
    return vals


def op_deck(kind, ic_target, vce=1.5):
    """Forward-active bias by an ideal base current, so Ic is set by beta and the
    measurement is of the device, not of a bias network.

    Element names avoid `vce`/`ic`/`ib`: ngspice puts a source's branch current in
    the plot under its own name, and `let ic=...` colliding with an element name
    silently poisons the read."""
    model, card = TS.BJT_MODELS[kind]
    p = card_params(kind)
    sign = 1 if kind == "NPN" else -1
    ib = ic_target / p["bf"]
    lines = [f"* {kind} operating-point golden", card, "",
             f"Vsupc nc 0 dc {sign * vce:g}", f"Ibb 0 nb dc {sign * ib:g}",
             f"Q1 nc nb 0 {model} 1", "",
             ".control", "op",
             "let m_ic=@q1[ic]", "let m_ib=@q1[ib]", "let m_vbe=@q1[vbe]",
             "let m_vbc=@q1[vbc]", "let m_gm=@q1[gm]",
             "let m_cpi=@q1[cpi]", "let m_cmu=@q1[cmu]",
             "print m_ic m_ib m_vbe m_vbc m_gm m_cpi m_cmu", ".endc", ".end"]
    return "\n".join(lines) + "\n"


def ft_deck(kind, ic_target, vce=1.5, fstart=1e8, fstop=1e12):
    """|h21| = |Ic/Ib| swept in AC with the collector AC-shorted; fT is where it
    crosses unity. Measured by log-log extrapolation from the -20 dB/dec region,
    which is how fT is defined and how it is measured on the bench."""
    model, card = TS.BJT_MODELS[kind]
    p = card_params(kind)
    sign = 1 if kind == "NPN" else -1
    ib = ic_target / p["bf"]
    lines = [f"* {kind} fT golden (h21 unity-gain frequency)", card, "",
             f"Vsupc nc 0 dc {sign * vce:g} ac 0",
             f"Ibb 0 nb dc {sign * ib:g} ac {sign:g}",
             f"Q1 nc nb 0 {model} 1", "",
             ".control", "op",
             f"ac dec 40 {fstart:g} {fstop:g}",
             "let h21 = abs(i(Vsupc))",        # AC base current is 1 A by design
             "print h21", ".endc", ".end"]
    return "\n".join(lines) + "\n"


def measure_ft(kind, ic, beta0, verbose=False):
    """fT from the AC |h21| roll-off, extrapolated to unity.

    The fit window is keyed to the device's OWN low-frequency beta
    (1.5 <= |h21| <= 0.2*beta0) rather than to fixed numbers: a beta-50 PNP and
    a beta-190 NPN have their single-pole regions in completely different places,
    and a fixed window silently fits the corner on one of them (measured: a
    3..30 window gave a -0.63 dec/dec "slope" on the PNP)."""
    out = E.run_deck(ft_deck(kind, ic), "bjtft_", "ft.cir")
    if out is None:
        return None
    rows = []
    for line in out.splitlines():
        m = re.match(rf"^\s*\d+\s+{_NUM}\s+{_NUM}\s*$", line)
        if m:
            rows.append((float(m.group(1)), float(m.group(2))))
    rows = [(f, h) for f, h in rows if h > 0]
    if len(rows) < 8:
        return None
    band = [(f, h) for f, h in rows if 1.5 <= h <= 0.2 * beta0]
    if len(band) < 6:
        return None
    lf = [math.log10(f) for f, _ in band]
    lh = [math.log10(h) for _, h in band]
    n = len(lf)
    mx, my = sum(lf) / n, sum(lh) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(lf, lh))
    sxx = sum((a - mx) ** 2 for a in lf)
    slope = sxy / sxx
    ft = 10 ** (mx - my / slope)
    if verbose:
        print(f"      fit slope {slope:+.3f} dec/dec over {n} points "
              f"({band[0][0]:.3g}..{band[-1][0]:.3g} Hz)")
    return ft, slope


def predicted_ft(gm, cpi, cmu):
    """fT = gm / (2*pi*(Cpi + Cmu)) -- the hybrid-pi closed form, evaluated from
    the small-signal parameters the DC operating point reports.

    This is deliberately NOT the zero-bias card estimate
    `1/(2*pi*(tf + (cje0+cjc0)*Vt/Ic + (re+rc)*cjc0))`, which is only accurate to
    ~15% here because SPICE's forward-biased Cje is the linearized-depletion
    value (measured 28 fF against a cje0 of 18 fF), not cje0. Checking the AC
    sweep against the op point's own gm/Cpi/Cmu tests the two solvers against
    each other; the card estimate is printed alongside as context."""
    return gm / (2 * math.pi * (cpi + cmu))


def card_ft_estimate(kind, ic):
    """Zero-bias textbook estimate from the card alone -- informational."""
    p = card_params(kind)
    tau = (p["tf"] + (p["cje"] + p["cjc"]) * VT / ic
           + (p["re"] + p["rc"]) * p["cjc"])
    return 1.0 / (2 * math.pi * tau)


def gp_gm(kind, vbe, vbc, h=1e-5):
    """dIc/dVbe from `gp_currents` -- the closed form for ngspice's @q[gm].
    Ic/Vt is NOT the right expectation once IKF is active (measured: 15% low at
    5 mA on the NPN, 28% on the PNP), so the derivative is taken numerically
    through the same qb algebra the currents use."""
    ic_hi, _ = gp_currents(kind, vbe + h, vbc)
    ic_lo, _ = gp_currents(kind, vbe - h, vbc)
    return (ic_hi - ic_lo) / (2 * h)


def gp_currents(kind, vbe, vbc):
    """Closed-form Gummel-Poon (Ic, Ib) at the junction voltages the simulator
    actually settled at. Predicting from a *target* Ic instead would fold the
    parasitic re/rc drops into the comparison and test arithmetic rather than the
    card; taking ngspice's own internal Vbe/Vbc isolates the model equations.

        Icc = IS*(exp(Vbe/Vt) - 1)          Iec = IS*(exp(Vbc/Vt) - 1)
        q1  = 1/(1 - Vbe/VAR - Vbc/VAF)     q2  = Icc/IKF + Iec/IKR
        qb  = q1/2 * (1 + sqrt(1 + 4*q2))
        Ic  = (Icc - Iec)/qb - Iec/BR
        Ib  = Icc/BF + Iec/BR + ISE*(exp(Vbe/(NE*Vt)) - 1)

    Signs are handled by the caller (magnitudes are compared), so the same
    algebra serves NPN and PNP."""
    p = card_params(kind)
    is_, bf, br = p["is"], p["bf"], p.get("br", 1.0)
    vaf, var = p.get("vaf", 0.0), p.get("var", 0.0)
    ikf, ikr = p.get("ikf", 0.0), p.get("ikr", 0.0)
    ise, ne = p.get("ise", 0.0), p.get("ne", 1.5)

    def ex(v, n=1.0):
        return math.exp(min(v / (n * VT), 120.0)) - 1.0

    icc = is_ * ex(vbe)
    iec = is_ * ex(vbc)
    q1 = 1.0 / (1.0 - (vbe / var if var else 0.0) - (vbc / vaf if vaf else 0.0))
    q2 = (icc / ikf if ikf else 0.0) + (iec / ikr if ikr else 0.0)
    qb = q1 * (1.0 + math.sqrt(1.0 + 4.0 * q2)) / 2.0
    ic = (icc - iec) / qb - iec / br
    ib = icc / bf + iec / br + ise * ex(vbe, ne)
    return ic, ib


# --------------------------------------------------------------- the checks
def check_models(verbose=False):
    """Analytic goldens on both cards, at two collector currents each."""
    rows, ok = [], True
    for kind in ("NPN", "PNP"):
        for ic in (1e-3, 5e-3):
            out = E.run_deck(op_deck(kind, ic), "bjtop_", "op.cir")
            if out is None:
                print(f"  {kind} @ {ic*1e3:g} mA: ngspice FAILED")
                ok = False
                continue
            v = _print_vals(out)
            m_ic, m_ib = abs(v.get("m_ic", 0.0)), abs(v.get("m_ib", 0.0))
            if m_ib <= 0:
                print(f"  {kind} @ {ic*1e3:g} mA: no base current in op")
                ok = False
                continue
            m_beta = m_ic / m_ib
            vbe, vbc = abs(v["m_vbe"]), -abs(v["m_vbc"])
            p_ic, p_ib = gp_currents(kind, vbe, vbc)
            p_beta = abs(p_ic / p_ib)
            beta_err = abs(m_beta - p_beta) / p_beta
            m_gm = abs(v.get("m_gm", 0.0))
            p_gm = gp_gm(kind, vbe, vbc)
            gm_err = abs(m_gm - p_gm) / p_gm

            ft = measure_ft(kind, ic, m_beta, verbose=verbose)
            if ft is None:
                print(f"  {kind} @ {ic*1e3:g} mA: fT sweep FAILED")
                ok = False
                continue
            m_ft, slope = ft
            p_ft = predicted_ft(m_gm, abs(v["m_cpi"]), abs(v["m_cmu"]))
            ft_err = abs(m_ft - p_ft) / p_ft

            good = (beta_err <= 0.05 and gm_err <= 0.05 and ft_err <= 0.10
                    and abs(slope + 1.0) <= 0.05)
            ok = ok and good
            rows.append((kind, ic, m_ic, m_beta, p_beta, beta_err,
                         m_ft, p_ft, ft_err,
                         (vbe, m_gm, p_gm, gm_err, card_ft_estimate(kind, m_ic)),
                         gm_err, good))
    print(f"  {'dev':<4} {'Ic set':>8} {'Ic meas':>9} {'beta':>7} {'pred':>7} "
          f"{'err':>6} {'fT GHz':>8} {'pred':>8} {'err':>6}  ok")
    for (k, ic, mic, mb, pb, be, mf, pf, fe, extra, ge, good) in rows:
        print(f"  {k:<4} {ic*1e3:7.2f}m {mic*1e3:8.3f}m {mb:7.1f} {pb:7.1f} "
              f"{be*100:5.1f}% {mf/1e9:8.1f} {pf/1e9:8.1f} {fe*100:5.1f}%  "
              f"{'OK' if good else 'FAIL'}")
        if verbose:
            vbe, mgm, pgm, gerr, cardft = extra
            print(f"        Vbe(int) {vbe:.4f} V   gm {mgm*1e3:.3f} mS vs "
                  f"closed-form {pgm*1e3:.3f} mS ({gerr*100:.2f}%)   "
                  f"card zero-bias fT estimate {cardft/1e9:.1f} GHz")
    return ok, rows


# A common-emitter stage as one AnalogGenie walk: R1 = collector load (VDD ->
# VOUT1 = collector), R2 = base feed (VDD -> VIN1 = base), emitter on VSS.
# R2 is raised to 100k via a value override so the device sits in forward-active
# rather than deep saturation -- a saturated golden would test almost nothing.
CE_TOKENS = [
    "VSS", "NPN1_E", "NPN1", "NPN1_B", "VIN1", "R2_N", "R2", "R2_P", "VDD",
    "R1_P", "R1", "R1_N", "VOUT1", "NPN1_C", "NPN1", "NPN1_E",
]
CE_R2 = "100k"


def check_emitter(verbose=False):
    """Hand deck vs the same circuit through the token -> Netlist path."""
    model, card = TS.BJT_MODELS["NPN"]
    topo = Topology(CE_TOKENS)
    if not topo.valid:
        print(f"  token path: CE_TOKENS is not a valid walk "
              f"(orphans={topo.orphan_pins}, bad_ctx={topo.bad_device_ctx}) -- FAIL")
        return False
    nl = TS.Netlist(topo).set_extra([], {}, {"pR2V": CE_R2})
    bad = nl.missing_pins()
    if bad:
        print(f"  token path: missing pins {bad} -- FAIL")
        return False
    deck = nl.emit(mode="opcheck")
    if f" {model} " not in deck:
        print(f"  token path: no {model} device line emitted -- FAIL")
        return False
    tok_out = E.run_deck(deck, "bjtce_", "ce.cir")

    # The same circuit, written by hand against the same node names/values.
    hand = "\n".join([
        "* hand-written common-emitter reference", card, "",
        f".param pVDD=1.1 pR1V=1k pR2V={CE_R2}",
        "Vsup VDD 0 dc {pVDD}",
        "Vp1 p1 0 dc 0 ac 1 portnum 1 z0 50", "Cp1 p1 VIN1 10p",
        "Cp2 VOUT1 p2 10p", "Vp2 p2 0 dc 0 ac 0 portnum 2 z0 50",
        f"Q1 VOUT1 VIN1 0 {model} 1",
        "R1 VOUT1 VDD {pR1V}", "R2 VDD VIN1 {pR2V}", "",
        ".option rshunt=1e12", ".control", "op",
        "let ic_NPN1=@q1[ic]", "let ib_NPN1=@q1[ib]",
        "let vbe_NPN1=@q1[vbe]", "let vbc_NPN1=@q1[vbc]",
        "print ic_NPN1 ib_NPN1 vbe_NPN1 vbc_NPN1", ".endc", ".end"])
    hand_out = E.run_deck(hand, "bjtce_", "ce_hand.cir")
    if tok_out is None or hand_out is None:
        print("  common-emitter golden: ngspice FAILED")
        return False
    a, b = _print_vals(tok_out), _print_vals(hand_out)
    keys = ["ic_npn1", "ib_npn1", "vbe_npn1", "vbc_npn1"]
    ok = True
    print(f"  {'quantity':<10} {'token path':>14} {'hand deck':>14} {'rel err':>9}")
    for k in keys:
        if k not in a or k not in b:
            print(f"  {k:<10} {'MISSING':>14}")
            ok = False
            continue
        err = abs(a[k] - b[k]) / max(abs(b[k]), 1e-12)
        ok = ok and err <= 1e-6
        print(f"  {k:<10} {a[k]:14.6g} {b[k]:14.6g} {err:9.2e}")
    return ok


MOS_TOKENS = [
    "VSS", "NM1_S", "NM1", "NM1_B", "VSS", "VDD",
    "R1_P", "R1", "R1_N", "VOUT1", "NM1_D", "NM1", "NM1_G", "VIN1",
]


def check_additive():
    """A MOS-only deck must carry no bipolar card and no Q element."""
    topo = Topology(MOS_TOKENS)
    deck = TS.Netlist(topo).emit()
    has_card = ".model q" in deck.lower()
    has_q = any(l.startswith("Q") for l in deck.splitlines())
    kinds = TS.Netlist(topo).bjt_kinds()
    ok = not has_card and not has_q and kinds == []
    print(f"  MOS-only deck: bjt_kinds={kinds} model_card={has_card} "
          f"Q_element={has_q} -> {'OK' if ok else 'FAIL'}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    print("== 1. model cards vs closed-form Gummel-Poon ==")
    ok_models, _ = check_models(verbose=args.verbose)
    print("\n== 2. token -> Netlist emission vs a hand-written deck ==")
    ok_emit = check_emitter(verbose=args.verbose)
    print("\n== 3. additive: MOS-only decks are untouched ==")
    ok_add = check_additive()

    green = ok_models and ok_emit and ok_add
    print(f"\ncheck_bjt: {'GREEN' if green else 'RED'}")
    return 0 if green else 1


if __name__ == "__main__":
    sys.exit(main())

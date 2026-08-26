"""Emit a simulatable ngspice netlist from an AnalogGenie topology.

AnalogGenie produces topology only -- which pin connects to which node -- and no
device values. So this emitter assigns every device a *parameterised* default
(.param W1=... L1=... etc.) rather than a literal, which leaves a clean surface
for a sizing loop (ZOAF / AutoCkt / a sweep) to optimise over without re-parsing
the netlist.

Port convention, matching the dataset's Port<i>.txt naming:
    VSS   -> node 0 (ground)
    VDD   -> supply
    VIN1  -> S-parameter port 1, 50 ohm, AC coupled
    VOUT1 -> S-parameter port 2, 50 ohm, AC coupled
    VB*   -> DC bias sources

Two ngspice traps this emitter is careful about, both hit while validating the
harness:
  * identifiers are case-insensitive, so a .param may not share a name with an
    element (LS vs Ls collided and silently corrupted a run);
  * `ln` is a builtin, so no parameter may be called Ln.
Generated names are therefore prefixed (pW1, pL1, ...) and elements keep SPICE
letters.

Bipolars (NPN/PNP) are emitted as SPICE `Q` elements against the generic
Gummel-Poon cards in `BJT_MODELS` -- see that constant for why they exist and
what they are (and are not) calibrated to. The cards are emitted **only when the
topology actually contains a bipolar**, so every MOS-only deck this file has ever
produced is byte-identical to before.

    python lna/to_spice.py lna/out/cond/seq0003.txt -o work/cand3.cir
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from topology import PIN_RE, Topology, base_of, parse_arrow_file  # noqa: E402

DEFAULT_MODELS = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..",
    "AutoCkt", "repo", "eval_engines", "ngspice", "ngspice_inputs",
    "spice_models", "45nm_bulk.txt"))

# starting values; a sizing loop is expected to move these
DEFAULTS = {"NM": ("40u", "45n"), "PM": ("80u", "45n"),
            "R": "1k", "C": "1p", "L": "1n"}

# --------------------------------------------------------------- bipolars
# AnalogGenie's vocabulary and topology.py's LEGAL both carry 3-terminal C/B/E
# NPN/PNP, and real ingested circuits use them (IHP's open SG13G2 GPS_LNA ships
# an HBT variant alongside its NMOS one), but the DEFAULT_MODELS include --
# AutoCkt's `45nm_bulk.txt` -- is a BSIM4 file with **MOS models only**. So a
# bipolar-bearing topology needs its own device cards, and they live here.
#
# WHAT THESE ARE: generic Gummel-Poon cards, hand-written for this harness. No
# vendor/PDK model was retrieved for them (and a PDK model could not be
# redistributed in this repo if it had been), so they are **illustrative of a
# device class, not an extraction of any real device**. Any number measured on a
# bipolar topology here is a topology/harness result, not a silicon prediction.
#
# WHY THESE VALUES: the harness simulates 1-4 GHz, so the two parameters that
# actually decide whether a bipolar deck behaves like an RF device are the
# forward transit time (which sets fT) and beta. MEASURED by check_bjt.py:
#   qnpn  SiGe-HBT class -- beta 193 @ 1 mA / 167 @ 4.2 mA,
#                           fT 68.6 GHz @ 1 mA / 92.0 GHz @ 4.2 mA
#   qpnp  generic PNP    -- beta 43 @ 0.9 mA / 31 @ 3.1 mA,
#                           fT 11.1 GHz @ 0.9 mA / 7.7 GHz @ 3.1 mA
# i.e. fT is 17-40x the 1-4 GHz band for the NPN and 2-11x for the (deliberately
# slower) PNP, which is the regime real LNAs are designed in. The PNP's fT
# *falling* with current is the IKF/XTF high-injection roll-off doing its job.
# Ohmic (rb/rbm/re/rc) and
# junction-capacitance values are scaled to the same device class; ikf/ise/ne
# give the usual high- and low-injection beta roll-off so a badly biased device
# degrades rather than staying ideal. Reverse Early (VAR) is deliberately left
# infinite: in SPICE's Gummel-Poon `qb` a finite VAR scales *forward* beta too
# (measured: var=2.5 dropped the NPN from ~184 to 131 at 1 mA), which would make
# the stated bf misleading for a device that never runs reverse-active here.
#
# GOLDEN-CHECKED, NOT ASSERTED: `python lna/ref/check_bjt.py` measures DC beta
# and fT of both cards in ngspice and compares them against the closed-form
# Gummel-Poon prediction from these very parameters. Quoted measured values are
# in lna/FINDINGS.md.
#
# NOT SIZABLE (deliberate): the Q elements carry a literal emitter-area
# multiplier rather than a `.param`. size.py's `classify_params` owns the
# param-name -> sizing-kind map and has no bipolar kind; emitting `area={pQ1A}`
# would produce an "Undefined parameter" the moment E.body_of() strips the
# .param block. Giving bipolars a sizable area is a size.py change, and this
# file does not own it. Everything else in a bipolar topology (R/C/L/W) sizes
# normally.
BJT_AREA = 1.0

BJT_MODELS = {
    "NPN": ("qnpn", "\n".join([
        ".model qnpn npn (is=2e-17 bf=200 vaf=60 ikf=20m ise=5e-17 ne=2",
        "+                br=3 rb=30 rbm=8 re=1.5 rc=12",
        "+                cje=18f vje=0.9 mje=0.35 cjc=9f vjc=0.7 mjc=0.33",
        "+                cjs=12f vjs=0.6 mjs=0.3",
        "+                tf=1.2p xtf=3 vtf=1.5 itf=30m tr=1n)"])),
    "PNP": ("qpnp", "\n".join([
        ".model qpnp pnp (is=4e-17 bf=50 vaf=40 ikf=5m ise=2e-16 ne=2",
        "+                br=2 rb=60 rbm=20 re=4 rc=30",
        "+                cje=25f vje=0.9 mje=0.35 cjc=15f vjc=0.7 mjc=0.33",
        "+                cjs=20f vjs=0.6 mjs=0.3",
        "+                tf=10p xtf=2 vtf=1.5 itf=5m tr=5n)"])),
}


# ---------------------------------------------------------------- MOS layout
# Gate FINGER width. BSIM4 charges a real gate-electrode resistance
#
#   Rgeltd = RSHG * (XGW + Weff/(3*NGCON)) / (NGCON * (Ldrawn - XGL) * NF)
#
# and the 45nm card enables it (rgatemod=1, rshg=0.4 ohm/sq, ngcon=1). `NF` is
# the number of gate fingers, a per-INSTANCE parameter. Emitting NF=1 -- which is
# what this file did until 2026-08-10 -- gives a 100-200 um RF device hundreds of
# ohms in series with its gate, which nobody tapes out.
#
# Measured cost of that omission (FINDINGS §26, per-element noise decomposition):
# gate-electrode resistance carried **26-40% of the excess noise factor F-1** on
# every dhruva design, and `rg` -- not channel thermal noise `id` -- was the
# dominant per-MOSFET mechanism. Re-sizing the same topologies at 4 fingers moved
# dhruva-l5 from NF 3.31 to 2.03-2.33 dB.
#
# 2 um/finger is ordinary RF layout practice (typical range 1-5 um) and is
# calibrated to that practice, NOT to any target: the rule is fixed and the
# finger count follows from W. Set `w_finger=None` to restore the historical
# single-finger emission and reproduce pre-cutover labels exactly.
W_FINGER = 2e-6


class Netlist(object):
    def __init__(self, topo, models=DEFAULT_MODELS, vdd=1.1, vbias=0.5,
                 freq_lo=1e9, freq_hi=4e9, points=201, inductor_q=None,
                 bjt_models=None, bjt_area=BJT_AREA, w_finger=W_FINGER,
                 pdk=None):
        self.t = topo
        # PDK abstraction (v0, additive): `pdk=None` -> the bptm45 adapter, which
        # reproduces THIS emitter byte-for-byte (lna/ref/check_pdk.py proves it),
        # so every existing caller and every shipped deck is unaffected. The
        # adapter routes the model `.include`, the MOS device line, and (via
        # bjt_models()) the bipolar cards; `models=`/`bjt_models=` stay honoured
        # so the default bptm45 adapter emits exactly the constants this file
        # always used. Imported lazily to avoid an import cycle (pdk imports
        # to_spice for DEFAULT_MODELS).
        if pdk is None:
            from pdk import default_pdk
            pdk = default_pdk()
        self.pdk = pdk
        self.models = models
        # {base: (model_name, card_text)}; override to swap in a real PDK card
        # without touching this file. Emitted only if the topology has bipolars.
        # An explicit `bjt_models=` arg wins (existing callers); otherwise the
        # adapter's bjt_models() may supply process bipolars, and the generic
        # Gummel-Poon set is the final fallback (bptm45's adapter returns None,
        # so the default path resolves to BJT_MODELS exactly as before).
        _pdk_bjt = None if bjt_models is not None else self.pdk.bjt_models()
        self.bjt_models = dict(bjt_models or _pdk_bjt or BJT_MODELS)
        self.bjt_area = bjt_area
        self.vdd = vdd
        self.vbias = vbias
        self.freq = (freq_lo, freq_hi, points)
        # inductor_q: None -> ideal inductors (default, preserves prior netlists).
        # A finite Q (e.g. 12) gives each inductor a series R = w0*L/Q, which is
        # both more physical (real spirals are Q~10-15) and the fix for the ideal-
        # inductor branch singularity that makes index 1081 fail (WORKLOG F6/H-Q3):
        # a node reached only through ideal inductors + a MOS gate has an
        # undetermined branch current. Confirmed to resolve 1081. See 05-SIZE §4.
        self.inductor_q = inductor_q
        # None -> historical single-finger emission (pre-2026-08-10 labels).
        self.w_finger = w_finger
        # bias scaffolding injected by bias.py: {param: default} and raw element
        # lines (already using this Netlist's node names). Kept out of the device
        # loop so scaffolding never changes the topology's device identity.
        self.extra_params = {}
        self.extra_elements = []
        # {param_name: value} to override an existing device .param default -- used
        # by bias.py to raise a gate's mis-referenced pull-down resistor (still a
        # .param the sizer owns), never to change connectivity.
        self.value_overrides = {}
        self._label_nodes()

    def set_extra(self, elements, params, value_overrides=None):
        self.extra_elements = list(elements or [])
        self.extra_params = dict(params or {})
        self.value_overrides = dict(value_overrides or {})
        return self

    def _label_nodes(self):
        """Give every electrical node a SPICE name; VSS becomes ground (0)."""
        self.node_of_pin = {}
        self.node_names = {}
        counter = 0
        for root, members in self.t.nodes.items():
            named = sorted(m for m in members if m in self.t.nets)
            if named:
                name = named[0]
                if name == "VSS":
                    name = "0"
            else:
                name = f"n{counter}"
                counter += 1
            self.node_names[root] = name
            for m in members:
                if PIN_RE.match(m):
                    self.node_of_pin[m] = name

        # find(): re-derive root for a pin
        self.pin_root = {}
        for root, members in self.t.nodes.items():
            for m in members:
                self.pin_root[m] = root

    def _pin_node(self, dev, pin):
        tok = f"{dev}_{pin}"
        return self.node_of_pin.get(tok)

    def bjt_kinds(self):
        """Sorted bipolar base types present in this topology ([] for MOS-only).

        Drives whether the .model cards are emitted at all, which is what keeps
        every pre-existing MOS-only deck byte-identical."""
        return sorted({base_of(d) for d in self.t.devices
                       if base_of(d) in BJT_MODELS})

    def missing_pins(self):
        """Devices whose pins are not all present -- cannot be emitted."""
        need = {"NM": "DGSB", "PM": "DGSB", "R": "PN", "C": "PN", "L": "PN",
                "NPN": "CBE", "PNP": "CBE"}
        bad = []
        for d in sorted(self.t.devices):
            b = base_of(d)
            if b not in need:
                bad.append((d, "unsupported device type"))
                continue
            for p in need[b]:
                if self._pin_node(d, p) is None:
                    bad.append((d, f"pin {p} unconnected"))
                    break
        return bad

    def _model_includes(self):
        """Model `.include`/`.lib`/`pre_osdi` lines for this Netlist's PDK.

        For the default bptm45 adapter the include path is THIS Netlist's
        `self.models` (so a `--models`/`models=` override still flows through and
        the emitted line is byte-identical to the historical
        `.include {self.models.replace(os.sep,'/')}`). For a non-bptm45 adapter
        the model set is a fixed property of the process, so `self.models` does
        not apply and the adapter's own `model_includes()` is used verbatim
        (which, for a staged PDK, raises the NotImplementedError pointing at
        FETCH.md)."""
        from pdk import bptm45 as _bptm45
        if isinstance(self.pdk, _bptm45.Bptm45Adapter):
            return _bptm45.Bptm45Adapter(models=self.models).model_includes()
        return self.pdk.model_includes()

    def _fingers(self, d):
        """` NF={...}` for a MOS instance, or "" under single-finger emission.

        W is a `.param`, not a literal, so the finger count has to be an
        expression evaluated by the netlist parser: `max(1, ceil(W/w_finger))`.
        Rounding UP keeps every finger at or below `w_finger`, and the max()
        floor keeps sub-micron devices legal at NF=1."""
        if not self.w_finger:
            return ""
        return f" NF={{max(1,ceil(p{d}W/{self.w_finger:g}))}}"

    @property
    def layout_cfg(self):
        """Harness settings that change the emitted device geometry, for stamping
        onto every logged row (see `size._zoaf_cfg`). Labels produced under
        different geometry are different label domains and must not be pooled."""
        return {"w_finger": self.w_finger,
                "mos_fingers": ("ceil(W/w_finger)" if self.w_finger else 1)}

    def emit(self, mode="sparam"):
        """mode 'sparam' -> the full op/sp/noise deck; 'opcheck' -> op only, with
        per-MOS Id/Vds/Vdsat printed (used by bias.py's L1 feasibility sweep)."""
        t = self.t
        L = []
        A = L.append
        A("* Auto-generated from an AnalogGenie topology by lna/to_spice.py")
        A("* Device values are placeholders exposed as .param for a sizing loop.")
        A("")
        # Model include(s) come from the PDK adapter. The default bptm45 adapter
        # is bound to THIS Netlist's `self.models` (so a --models override still
        # flows through) and emits the identical single `.include <path>` line the
        # emitter always produced. A different PDK may emit .lib/pre_osdi lines.
        for _inc in self._model_includes():
            A(_inc)
        # Bipolar cards, only when the topology has a bipolar -- the include above
        # is BSIM4 (MOS) only. See BJT_MODELS for what these are calibrated to.
        kinds = self.bjt_kinds()
        if kinds:
            A("* generic Gummel-Poon cards (to_spice.BJT_MODELS); the 45nm BSIM4")
            A("* include has no bipolar models. Illustrative device class, not a PDK.")
            for k in kinds:
                A(self.bjt_models[k][1])
        A("")

        # ---- parameters -------------------------------------------------
        A(f".param pVDD={self.vdd} pVB={self.value_overrides.get('pVB', self.vbias)}")
        if self.inductor_q:
            lo, hi, _ = self.freq
            f0 = (lo * hi) ** 0.5                 # geometric band centre
            A(f".param pINDQ={self.inductor_q} pINDW0={2 * 3.141592653589793 * f0:g}")
        for d in sorted(t.devices):
            b = base_of(d)
            if b in ("NM", "PM"):
                w, l = DEFAULTS[b]
                A(f".param p{d}W={w} p{d}L={l}")
            elif b in ("R", "C", "L"):
                pv = self.value_overrides.get(f"p{d}V", DEFAULTS[b])
                A(f".param p{d}V={pv}")
        for pname, pval in sorted(self.extra_params.items()):
            A(f".param {pname}={pval}")
        A("")

        # ---- supplies and bias ------------------------------------------
        used = {n for n in t.nets}
        A(f"Vsup VDD 0 dc {{pVDD}}")
        for n in sorted(used):
            if n.startswith("VB") or n.startswith("VCM") or n.startswith("VREF"):
                A(f"V{n} {n} 0 dc {{pVB}}")
        A("")

        # ---- RF ports ----------------------------------------------------
        # ngspice requires port numbers to run contiguously from 1, so a
        # two-port setup is only emitted when BOTH VIN1 and VOUT1 exist.
        # Emitting Vp2 alone is a fatal "incorrect port ordering" -- which is
        # exactly what happens on generated topologies that have no input port
        # (a cross-coupled oscillator, for instance).
        has_in = "VIN1" in used
        has_out = "VOUT1" in used
        self.two_port = has_in and has_out
        if self.two_port:
            A("* port 1: RF input, DC-blocked so bias is not shorted to 50 ohm")
            A("Vp1 p1 0 dc 0 ac 1 portnum 1 z0 50")
            A("Cp1 p1 VIN1 10p")
            A("* port 2: RF output")
            A("Cp2 VOUT1 p2 10p")
            A("Vp2 p2 0 dc 0 ac 0 portnum 2 z0 50")
        else:
            missing = "VIN1" if not has_in else "VOUT1"
            A(f"* no two-port setup: {missing} absent, so S-parameters are skipped.")
            if has_out:
                A("Rload VOUT1 0 50")
        A("")

        # ---- devices ------------------------------------------------------
        for d in sorted(t.devices):
            b = base_of(d)
            if b in ("NM", "PM"):
                # MOS instance line comes from the PDK adapter. The default
                # bptm45 adapter emits the identical `M<dev> D G S B nmos/pmos
                # W={..} L={..} NF={..}` line this file always produced; a subckt
                # PDK (sky130/gf180/IHP) emits an `X` call instead.
                A(self.pdk.mos_line(
                    d, self._pin_node(d, 'D'), self._pin_node(d, 'G'),
                    self._pin_node(d, 'S'), self._pin_node(d, 'B'), b,
                    f"{{p{d}W}}", f"{{p{d}L}}", self._fingers(d)))
            elif b == "R":
                A(f"R{d} {self._pin_node(d,'P')} {self._pin_node(d,'N')} {{p{d}V}}")
            elif b == "C":
                A(f"C{d} {self._pin_node(d,'P')} {self._pin_node(d,'N')} {{p{d}V}}")
            elif b in BJT_MODELS:
                # Q<name> C B E <model> <area>. AnalogGenie graphs carry each
                # parallel unit finger as its own device, so `area` stays 1 and
                # the multiplicity is structural (12 NPN tokens = 12 fingers).
                A(f"Q{d} {self._pin_node(d,'C')} {self._pin_node(d,'B')} "
                  f"{self._pin_node(d,'E')} {self.bjt_models[b][0]} "
                  f"{self.bjt_area:g}")
            elif b == "L":
                p, n = self._pin_node(d, 'P'), self._pin_node(d, 'N')
                if self.inductor_q:
                    # finite Q: series R = w0*L/Q, constant Q at band centre as
                    # the sizer sweeps L. Breaks the ideal-inductor singularity.
                    A(f"L{d} {p} nq{d} {{p{d}V}}")
                    A(f"RQ{d} nq{d} {n} {{pINDW0*p{d}V/pINDQ}}")
                else:
                    A(f"L{d} {p} {n} {{p{d}V}}")
        A("")

        # ---- inserted bias scaffolding (bias.py) --------------------------
        if self.extra_elements:
            A("* rule-based bias scaffolding (bias.py); excluded from screen/novelty")
            for line in self.extra_elements:
                A(line)
            A("")

        # ---- analyses -----------------------------------------------------
        lo, hi, pts = self.freq
        A("* Dataset topologies are textbook schematics: they show the signal path")
        A("* but omit biasing, so nodes reachable only through capacitors have no")
        A("* DC path and the OP solve goes singular. rshunt ties every node to")
        A("* ground through 1e12 ohm -- enough for a DC solution, negligible at RF.")
        A("* Without it, 9 of 26 dataset LNAs fail to simulate at all.")
        A(".option rshunt=1e12")
        A(".control")
        A("op")
        if mode == "opcheck":
            # one labelled line per MOS so bias.py can read the operating point
            for d in sorted(t.devices):
                if base_of(d) in ("NM", "PM"):
                    A(f"let id_{d}=@M{d}[id]")
                    A(f"let vds_{d}=@M{d}[vds]")
                    A(f"let vdsat_{d}=@M{d}[vdsat]")
                    A(f"let vgs_{d}=@M{d}[vgs]")
                    A(f"print id_{d} vds_{d} vdsat_{d} vgs_{d}")
            # Bipolars get their own labels (ic_/ib_/vbe_/vbc_). bias.py's op
            # parser keys on id_/vds_/vdsat_/vgs_ only, so these are visible to a
            # reader and invisible to the MOS-only L1 sweep -- which is correct:
            # bias.py inserts *gate* scaffolding and has no base-bias rule.
            # ngspice's BJT exposes vbe/vbc, NOT vce (`@q[vce]` is a hard error);
            # Vce = Vbe - Vbc for anyone who wants it.
            for d in sorted(t.devices):
                if base_of(d) in BJT_MODELS:
                    A(f"let ic_{d}=@Q{d}[ic]")
                    A(f"let ib_{d}=@Q{d}[ib]")
                    A(f"let vbe_{d}=@Q{d}[vbe]")
                    A(f"let vbc_{d}=@Q{d}[vbc]")
                    A(f"print ic_{d} ib_{d} vbe_{d} vbc_{d}")
        elif self.two_port:
            A(f"sp lin {pts} {lo:g} {hi:g} 1")
            # A generated topology can leave a port fully disconnected, making
            # |S21| exactly 0; db(0) then aborts with "argument out of range".
            # The floor is 1e-30 (-600 dB), far below anything meaningful.
            A("let s11db = db(mag(S_1_1) + 1e-30)")
            A("let s21db = db(mag(S_2_1) + 1e-30)")
            A("print vecmin(s11db) vecmax(s21db)")
            A(f"noise v(p2) Vp1 dec 20 {lo:g} {hi:g} 1")
        A(".endc")
        A(".end")
        return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sequence", help="'->'-joined token file")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--models", default=DEFAULT_MODELS)
    ap.add_argument("--inductor-q", type=float, default=None,
                    help="finite inductor Q (series R = w0*L/Q); default ideal. "
                         "Use e.g. 12 to model real spirals / fix inductor-loop "
                         "singularities (WORKLOG F6).")
    ap.add_argument("--force", action="store_true",
                    help="emit even if some device pins are unconnected")
    args = ap.parse_args()

    toks = parse_arrow_file(args.sequence)
    topo = Topology(toks)
    nl = Netlist(topo, models=args.models, inductor_q=args.inductor_q)

    score, crit = topo.lna_score()
    print(f"devices {topo.n_devices}  inductors {topo.n_inductors}  "
          f"nodes {len(topo.nodes)}  LNA score {score}/5")
    print(f"structurally valid: {topo.valid}")

    bad = nl.missing_pins()
    if bad:
        print(f"cannot emit {len(bad)} device(s):")
        for d, why in bad[:10]:
            print(f"    {d}: {why}")
        if not args.force:
            print("refusing to emit an incomplete netlist (use --force to override)")
            return 1

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    open(args.out, "w").write(nl.emit())
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

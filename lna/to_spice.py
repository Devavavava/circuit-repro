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


class Netlist(object):
    def __init__(self, topo, models=DEFAULT_MODELS, vdd=1.1, vbias=0.5,
                 freq_lo=1e9, freq_hi=4e9, points=201):
        self.t = topo
        self.models = models
        self.vdd = vdd
        self.vbias = vbias
        self.freq = (freq_lo, freq_hi, points)
        self._label_nodes()

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

    def missing_pins(self):
        """Devices whose pins are not all present -- cannot be emitted."""
        need = {"NM": "DGSB", "PM": "DGSB", "R": "PN", "C": "PN", "L": "PN"}
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

    def emit(self):
        t = self.t
        L = []
        A = L.append
        A("* Auto-generated from an AnalogGenie topology by lna/to_spice.py")
        A("* Device values are placeholders exposed as .param for a sizing loop.")
        A("")
        A(f".include {self.models.replace(os.sep, '/')}")
        A("")

        # ---- parameters -------------------------------------------------
        A(f".param pVDD={self.vdd} pVB={self.vbias}")
        for d in sorted(t.devices):
            b = base_of(d)
            if b in ("NM", "PM"):
                w, l = DEFAULTS[b]
                A(f".param p{d}W={w} p{d}L={l}")
            elif b in ("R", "C", "L"):
                A(f".param p{d}V={DEFAULTS[b]}")
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
            if b == "NM":
                A(f"M{d} {self._pin_node(d,'D')} {self._pin_node(d,'G')} "
                  f"{self._pin_node(d,'S')} {self._pin_node(d,'B')} nmos "
                  f"W={{p{d}W}} L={{p{d}L}}")
            elif b == "PM":
                A(f"M{d} {self._pin_node(d,'D')} {self._pin_node(d,'G')} "
                  f"{self._pin_node(d,'S')} {self._pin_node(d,'B')} pmos "
                  f"W={{p{d}W}} L={{p{d}L}}")
            elif b == "R":
                A(f"R{d} {self._pin_node(d,'P')} {self._pin_node(d,'N')} {{p{d}V}}")
            elif b == "C":
                A(f"C{d} {self._pin_node(d,'P')} {self._pin_node(d,'N')} {{p{d}V}}")
            elif b == "L":
                A(f"L{d} {self._pin_node(d,'P')} {self._pin_node(d,'N')} {{p{d}V}}")
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
        if self.two_port:
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
    ap.add_argument("--force", action="store_true",
                    help="emit even if some device pins are unconnected")
    args = ap.parse_args()

    toks = parse_arrow_file(args.sequence)
    topo = Topology(toks)
    nl = Netlist(topo, models=args.models)

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

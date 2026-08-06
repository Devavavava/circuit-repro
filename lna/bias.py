"""Rule-based bias insertion (WP-BIAS, plans/03-BIAS-INSERTION.md).

Dataset LNAs are textbook schematics: biasing is implied, so a reconstructed
gate often has no DC path and the transistor sits off (circuit 461: Vgs = 14 mV,
Id = 7.7 uA). Nothing downstream can be *scored* until transistors conduct. This
inserts the *least* circuit that makes DC bias definable and pushes every value
to a `.param` so the sizer owns it -- bias insertion makes a circuit *biasable*;
the sizing loop makes it *biased well*.

Rules (03-BIAS §2), all on a DC-connectivity graph (nodes joined by devices that
conduct at DC -- R and L; caps open; a MOS channel is NOT a DC edge). Driven nets
= supplies / ground / DC bias (VDD, VSS/0, VB*, VCM*, VREF*, IB*) -- NOT the RF
ports, which `to_spice.py` DC-blocks.

  R-GATE           every MOS gate node with no DC path to a driven net gets
                   RBIAS -> a fresh VBGEN source (+ CBYP), one bias net per
                   connected un-driven gate group, values as .param.
  R-CASCODE-BYPASS every VBGEN net is bypassed to ground (10p); existing VB* nets
                   too -- the H-Q1 lesson institutionalized.
  R-DIAGNOSE-ONLY  drains/sources are classified in the report but NOT fed in v1
                   (measure before adding rules).
  R-FLOAT          a genuinely floating sub-circuit (topology.floating_devices,
                   H-Q3) is flagged and the circuit skipped.

Every inserted element matches ^(RBIAS|CBYP|VBGEN), so screen.py, novelty.py and
the spec device_budget already exclude it (is_scaffold). Scaffolding is emitted
through to_spice.py's Netlist (the graph is the source of truth), never
text-patched.

    python lna/bias.py --index 461 -o work/c461_biased.cir --report work/bias461.json
    python lna/bias.py lna/out/run1/seq0003.txt --sweep --report bias.json
"""
import argparse
import itertools
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from topology import Topology, base_of, parse_arrow_file  # noqa: E402
from to_spice import Netlist  # noqa: E402

REPO = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "AnalogGenie", "repo"))
NGSPICE = os.environ.get("NGSPICE", r"C:\msys64\ucrt64\bin\ngspice_con.exe")

# A gate is usefully biased only if it reaches a *power/bias* rail (VDD or a
# dedicated bias net). A path to bare ground alone leaves an NMOS gate at 0 V --
# the un-biased condition we are fixing (circuit 461's R2 ties the gate to VSS).
POWER_EXACT = {"VDD"}
POWER_PREFIX = ("VB", "VCM", "VREF", "IB")
GND = {"0", "VSS"}
PULLDOWN_RAISED = "1e6"   # ohm: a mis-referenced gate-to-ground R, raised so the
#                           inserted RBIAS wins the divider (still a .param)
GRID4 = [0.35, 0.45, 0.55, 0.65]
GRID3 = [0.35, 0.50, 0.65]
ID_MIN = 50e-6            # A -- "conducting"
VDS_MARGIN = 1.5         # |Vds| >= 1.5*|Vdsat| -- "saturation-ish"


def _is_power(node):
    return node in POWER_EXACT or node.startswith(POWER_PREFIX)


class BiasInserter:
    """Analyzes a Netlist's DC graph and builds gate-bias scaffolding."""

    def __init__(self, netlist, r_bias="100k", vbg_default=0.5, cbyp="10p"):
        self.nl = netlist
        self.t = netlist.t
        self.r_bias = r_bias
        self.vbg_default = vbg_default
        self.cbyp = cbyp
        self._analyze()

    def _node(self, dev, pin):
        return self.nl.node_of_pin.get(f"{dev}_{pin}")

    def _analyze(self):
        t = self.t
        parent = {}

        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            if a is None or b is None:
                return
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for n in self.nl.node_of_pin.values():
            find(n)
        for d in t.devices:                      # DC edges: R and L only
            if base_of(d) in ("R", "L"):
                union(self._node(d, "P"), self._node(d, "N"))

        comp_power, comp_gnd = defaultdict(bool), defaultdict(bool)
        for n in list(parent):
            r = find(n)
            comp_power[r] = comp_power[r] or _is_power(n)
            comp_gnd[r] = comp_gnd[r] or (n in GND)
        self._find, self._power, self._gnd = find, comp_power, comp_gnd
        self.mos = [d for d in sorted(t.devices) if base_of(d) in ("NM", "PM")]

        # gate node -> {devices, gnd_only}; gates already reaching a power/bias
        # rail are left alone.
        self.gate_driven = []
        self.gate_nodes = {}
        for d in self.mos:
            g = self._node(d, "G")
            if g is None:
                continue
            # A gate that reaches a power/bias rail (directly or through a resistor)
            # is left alone; only gates with no useful bias path get R-GATE. Biasing
            # the reach-through-R gates was measured to not raise the conducting
            # rate -- those devices are off for source/drain reasons, not gate bias.
            if comp_power[find(g)]:
                self.gate_driven.append(d)
                continue
            info = self.gate_nodes.setdefault(g, {"devices": [], "gnd_only": comp_gnd[find(g)]})
            info["devices"].append(d)
        self.gate_nodes = dict(sorted(self.gate_nodes.items()))

        # ground-only gate nodes: raise the R that pins them to ground so the
        # inserted RBIAS can set the level (R-GATE, gnd-only variant).
        self.pulldown_overrides = {}
        for gnode, info in self.gate_nodes.items():
            if not info["gnd_only"]:
                continue
            for d in t.devices:
                if base_of(d) == "R" and gnode in (self._node(d, "P"), self._node(d, "N")):
                    other = self._node(d, "N") if self._node(d, "P") == gnode else self._node(d, "P")
                    if other in GND or comp_gnd[find(other)]:
                        self.pulldown_overrides[f"p{d}V"] = PULLDOWN_RAISED

        # R-DIAGNOSE-ONLY: drains/sources whose component reaches nothing driven
        self.drain_floating, self.source_floating = [], []
        for d in self.mos:
            dn, sn = self._node(d, "D"), self._node(d, "S")
            if dn and not (comp_power[find(dn)] or comp_gnd[find(dn)]):
                self.drain_floating.append(d)
            if sn and not (comp_power[find(sn)] or comp_gnd[find(sn)]):
                self.source_floating.append(d)

        self.floating = sorted(self.t.floating_devices())
        self.existing_vb = sorted({n for n in self.nl.node_of_pin.values()
                                   if n.startswith(("VB", "VCM", "VREF"))})

    @property
    def n_bias_nets(self):
        return len(self.gate_nodes)

    def param_names(self):
        return [f"pVBG{k}" for k in range(1, self.n_bias_nets + 1)]

    def value_overrides(self):
        return dict(self.pulldown_overrides)

    def build(self, vbg_values=None):
        """Return (elements, params, bias_nets). vbg_values overrides pVBG defaults."""
        vbg_values = vbg_values or {}
        elements, params, bias_nets = [], {}, {}
        for k, (gnode, info) in enumerate(self.gate_nodes.items(), 1):
            vbnet, vbparam, rparam = f"VBGEN{k}", f"pVBG{k}", f"pRB{k}"
            params[vbparam] = vbg_values.get(vbparam, self.vbg_default)
            params[rparam] = self.r_bias
            elements.append(f"VBGEN{k} {vbnet} 0 dc {{{vbparam}}}")
            elements.append(f"RBIAS{k} {gnode} {vbnet} {{{rparam}}}")
            elements.append(f"CBYP{k} {vbnet} 0 {self.cbyp}")      # R-CASCODE-BYPASS
            bias_nets[vbnet] = {"param": vbparam, "gate_node": gnode,
                                "devices": sorted(info["devices"]),
                                "pulldown_raised": info["gnd_only"]}
        for j, vb in enumerate(self.existing_vb, 1):               # bypass existing VB* too
            elements.append(f"CBYPX{j} {vb} 0 {self.cbyp}")
        return elements, params, bias_nets

    def report(self):
        _, _, bias_nets = self.build()
        return {
            "n_mos": len(self.mos),
            "gates_driven": self.gate_driven,
            "gates_biased": {d: k for k, m in bias_nets.items() for d in m["devices"]},
            "bias_nets": bias_nets,
            "pulldowns_raised": self.pulldown_overrides,
            "drains_no_dc_path": self.drain_floating,     # R-DIAGNOSE-ONLY
            "sources_no_dc_path": self.source_floating,   # R-DIAGNOSE-ONLY
            "floating_subcircuit": self.floating,         # R-FLOAT (skip if non-empty)
        }


# ------------------------------------------------------------- op / sweep
_NUM = r"([-\d.eE+]+)"


def run_op(deck):
    """Run an opcheck deck; return {dev: {id, vds, vdsat, vgs}} or None on failure."""
    d = tempfile.mkdtemp(prefix="bias_")
    p = os.path.join(d, "op.cir")
    open(p, "w").write(deck)
    try:
        r = subprocess.run([NGSPICE, "-b", p], capture_output=True,
                           text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return None
    out = (r.stdout or "") + (r.stderr or "")
    if "singular matrix" in out.lower():
        return None
    res = defaultdict(dict)
    for key in ("id", "vds", "vdsat", "vgs"):
        for m in re.finditer(rf"{key}_(\w+)\s*=\s*{_NUM}", out, re.IGNORECASE):
            res[m.group(1).upper()][key] = float(m.group(2))
    return dict(res) if res else None


def conducting(op):
    """(all_on, per-device on): on = |Id| >= ID_MIN. This is what bias insertion
    controls -- the gate bias turns the device on. Saturation (also needing
    |Vds| >= 1.5|Vdsat|) additionally depends on the *load* sizing, which is the
    sizer's job, so it is reported separately (see `saturated`)."""
    if not op:
        return False, {}
    ok = {dev: abs(m.get("id", 0.0)) >= ID_MIN for dev, m in op.items()}
    return (bool(ok) and all(ok.values())), ok


def saturated(op):
    """(all_saturated, per-device): |Id| >= ID_MIN AND |Vds| >= 1.5|Vdsat|."""
    if not op:
        return False, {}
    ok = {}
    for dev, m in op.items():
        ok[dev] = (abs(m.get("id", 0.0)) >= ID_MIN
                   and abs(m.get("vds", 0.0)) >= VDS_MARGIN * abs(m.get("vdsat", 0.0)))
    return (bool(ok) and all(ok.values())), ok


def feasibility_sweep(inserter, netlist):
    """L1 grid over the pVBG params; keep the point with the most conducting MOS.

    Returns dict: {best_vbg, n_conducting, n_mos, all_conduct, op, per_device}.
    """
    # swept knob: the inserted pVBG* voltages. <=2 nets sweep independently; >2
    # are tied to one common value (03-BIAS §3's "sweep jointly", capped so
    # 1089's 5 nets don't blow up to 3^5). The pre-existing VB* bias is the
    # sizer's knob, not ours -- sweeping it here was measured to not move the
    # conducting rate, so it is left to WP-SIZE.
    vbg = inserter.param_names()
    if len(vbg) <= 2:
        combos = [dict(zip(vbg, vals))
                  for vals in itertools.product(GRID4, repeat=len(vbg))] if vbg else []
    else:
        combos = [{p: v for p in vbg} for v in GRID4]          # tied
    pulldowns = inserter.value_overrides()
    n_mos = len(inserter.mos)

    def evaluate(elements, params, ov, biased, knobs):
        netlist.set_extra(elements, params, ov)
        op = run_op(netlist.emit(mode="opcheck"))
        allc, per = conducting(op)
        return {"best_vbg": knobs, "biased": biased, "n_conducting": sum(per.values()),
                "n_mos": n_mos, "all_conduct": allc, "op": op or {}, "per_device": per}

    # Candidate 0 = no bias at all. Seeding `best` with it guarantees monotonicity:
    # inserted bias is adopted only if it turns MORE MOS on, never fewer (so no
    # circuit is ever made worse -- the shared-signal-net failure mode).
    best = evaluate([], {}, {}, False, None)
    for combo in combos:
        elements, params, _ = inserter.build(vbg_values=combo)
        cand = evaluate(elements, params, pulldowns, True, combo)
        if cand["n_conducting"] > best["n_conducting"] or (
                cand["n_conducting"] == best["n_conducting"]
                and cand["all_conduct"] and not best["all_conduct"]):
            best = cand
        if best["biased"] and best["all_conduct"]:
            break
    return best


# ------------------------------------------------------------------- helpers
def topo_from_index(index):
    import numpy as np
    p = os.path.join(REPO, "Dataset", str(index), f"Sequence_total{index}.npy")
    arr = np.load(p, allow_pickle=True)
    return Topology([str(t) for t in arr[0]])


def baseline_conducts(topo):
    """Op point of the UN-biased netlist -- how many MOS already conduct.
    Used to prove bias insertion makes 0 circuits worse."""
    nl = Netlist(topo)
    op = run_op(nl.emit(mode="opcheck"))
    _, per = conducting(op)
    return sum(per.values()), len(per)


def validate(indices):
    """WP-BIAS §4 validation table over the dataset LNAs.

    'on' = |Id| >= 50 uA (what bias controls); 'sat' additionally needs
    |Vds| >= 1.5|Vdsat| (load-sizing dependent -> WP-SIZE)."""
    import numpy as np
    print(f"{'idx':>5} {'MOS':>3} {'bias':>4} {'on0':>4} {'onB':>4} {'satB':>4}  note")
    n_all_on = n_all_sat = n_worse = n_eval = 0
    off_total = off_src = off_drn = 0
    vgs461 = None
    for i in indices:
        p = os.path.join(REPO, "Dataset", str(i), f"Sequence_total{i}.npy")
        if not os.path.exists(p):
            continue
        topo = Topology([str(t) for t in np.load(p, allow_pickle=True)[0]])
        nl, inserter, rep, swept = insert_bias(topo, sweep=True)
        if rep.get("skipped"):
            print(f"{i:>5} {rep['n_mos']:>3}   -    -    -    -   {rep['skipped']}")
            continue
        n_eval += 1
        nmos = rep["n_mos"]
        on0 = sum(conducting(run_op(Netlist(topo).emit(mode="opcheck")))[1].values())
        onB = swept["n_conducting"]
        satB = sum(saturated(swept["op"])[1].values())
        if i == 461:
            vgs461 = (swept["op"].get("NM1", {}) or {}).get("vgs")
        if nmos and onB == nmos:
            n_all_on += 1
        if nmos and satB == nmos:
            n_all_sat += 1
        if onB < on0:
            n_worse += 1
        # classify why each off MOS is off (feeds v2 rules / WP-SIZE denominator)
        _, on_per = conducting(swept["op"])
        for dev, is_on in on_per.items():
            if not is_on:
                off_total += 1
                if dev in rep["sources_no_dc_path"]:
                    off_src += 1
                elif dev in rep["drains_no_dc_path"]:
                    off_drn += 1
        applied = rep.get("bias_applied") and rep["bias_nets"]
        note = ("biased " + ",".join(rep["bias_nets"])) if applied else "no bias applied"
        print(f"{i:>5} {nmos:>3} {len(rep['bias_nets']):>4} {on0:>4} {onB:>4} {satB:>4}  "
              f"{'WORSE ' if onB < on0 else ''}{note[:28]}")
    print(f"\n  circuits evaluated              : {n_eval}")
    print(f"  all MOS ON (Id>=50uA, bias's job): {n_all_on}/{n_eval} "
          f"({100.0*n_all_on/max(n_eval,1):.0f}%)   [acceptance >= 80%]")
    print(f"  all MOS SATURATED (needs sizing) : {n_all_sat}/{n_eval} "
          f"({100.0*n_all_sat/max(n_eval,1):.0f}%)   [-> WP-SIZE]")
    print(f"  circuits made worse by bias     : {n_worse}   [acceptance = 0]")
    if off_total:
        other = off_total - off_src - off_drn
        print(f"  off-MOS failure split ({off_total} off): "
              f"source no-DC-path {off_src}, drain no-DC-path {off_drn}, "
              f"load/sizing {other}  [v2 rules + WP-SIZE]")
    if vgs461 is not None:
        print(f"  461 spot check: NM1 Vgs = {vgs461*1e3:.0f} mV "
              f"(was 14 mV; want 350-650 mV)  {'PASS' if 0.30 <= vgs461 <= 0.70 else 'FAIL'}")
    return n_all_on, n_eval, n_worse


def insert_bias(topo, sweep=False, **kw):
    """Convenience: (netlist, inserter, report, sweep_result). Netlist has the
    winning (or default) scaffolding already set."""
    nl = Netlist(topo, **kw)
    inserter = BiasInserter(nl)
    rep = inserter.report()
    swept = None
    if inserter.floating:
        rep["skipped"] = "floating_subcircuit"
    elif sweep:
        swept = feasibility_sweep(inserter, nl)
        rep["sweep"] = {k: v for k, v in swept.items() if k != "op"}
    if swept is not None and not swept["biased"]:
        nl.set_extra([], {}, {})        # bias did not help -> ship the baseline
        rep["bias_applied"] = False
    else:
        knobs = swept["best_vbg"] if (swept and swept["best_vbg"]) else None
        elements, params, _ = inserter.build(vbg_values=knobs)
        nl.set_extra(elements, params, inserter.value_overrides())
        rep["bias_applied"] = True
        rep["operating_point"] = knobs
    return nl, inserter, rep, swept


# ------------------------------------------------------------------------ CLI
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sequence", nargs="?", help="'->'-joined topology token file")
    ap.add_argument("--index", type=int, help="corpus circuit index instead")
    ap.add_argument("-o", "--out", help="write the biased netlist here")
    ap.add_argument("--report", help="write the bias report JSON here")
    ap.add_argument("--sweep", action="store_true",
                    help="run the L1 feasibility grid and use the winning point")
    ap.add_argument("--validate", action="store_true",
                    help="run the §4 validation table over the dataset LNAs")
    args = ap.parse_args()

    if args.validate:
        idx = list(range(461, 493)) + list(range(1081, 1091))
        validate(idx)
        return 0

    if args.index is not None:
        topo = topo_from_index(args.index)
        label = f"index {args.index}"
    elif args.sequence:
        topo = Topology(parse_arrow_file(args.sequence))
        label = args.sequence
    else:
        ap.error("give a sequence file or --index")

    nl, inserter, rep, swept = insert_bias(topo, sweep=args.sweep)

    print(f"=== bias insertion: {label} ===")
    print(f"  MOS devices        : {rep['n_mos']}")
    print(f"  gates already driven: {rep['gates_driven']}")
    print(f"  gates biased (R-GATE): {rep['gates_biased']}")
    print(f"  bias nets inserted : {list(rep['bias_nets'])}")
    if rep["drains_no_dc_path"]:
        print(f"  drains w/o DC path : {rep['drains_no_dc_path']}  (diagnose-only)")
    if rep["sources_no_dc_path"]:
        print(f"  sources w/o DC path: {rep['sources_no_dc_path']}  (diagnose-only)")
    if rep["floating_subcircuit"]:
        print(f"  FLOATING (R-FLOAT) : {rep['floating_subcircuit']}  -> skip")
    if swept is not None:
        print(f"  L1 sweep           : {swept['n_conducting']}/{swept['n_mos']} MOS "
              f"conducting  all={swept['all_conduct']}  at {swept['best_vbg']}")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        open(args.out, "w").write(nl.emit())
        print(f"  wrote {args.out}")
    if args.report:
        json.dump(rep, open(args.report, "w"), indent=2)
        print(f"  wrote {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
  R-FLOAT          a genuinely floating sub-circuit (topology.floating_devices,
                   H-Q3) is flagged and the circuit skipped.

### v3 (2026-08-09): the DC-return rules, OPT-IN

`R-DIAGNOSE-ONLY` classified drains/sources without ever feeding them, on the
"measure before adding rules" principle. Two independent measurements have now
been made and both say the same thing:

  * the corpus off-MOS split is **15 source-no-DC-path / 16 drain-no-DC-path /
    12 load-sizing** (HANDOVER finding #9, reproduced by `--validate`);
  * the NF track's opt-in *gate*-rescue gained **0 of 4** blocked external
    circuits, because in every case the off device sits under
    `sources_no_dc_path` -- no gate bias can turn on a device whose source has
    no DC return (FINDINGS §17.6).

So v3 adds the two rules finding #9 pre-approved, **off by default**:

  R-SOURCE         a MOS source node whose DC component reaches neither a
                   power/bias rail nor ground gets a return resistor to its
                   device's return rail (NMOS -> 0, PMOS -> VDD).
  R-DRAIN          same for a drain node, to the opposite rail (NMOS -> VDD,
                   PMOS -> 0), i.e. a load feed.

**They are opt-in and the default path is byte-identical**, deliberately.
R-GATE only makes a circuit *biasable* -- it adds scaffolding on nodes that had
no DC definition at all. A source return resistor **changes the circuit**: it is
a real element in the signal path, `size.size_topology` calls `insert_bias` on
every sizing run, so switching these on by default would silently re-domain
every future L2 label. The monotonic guard proves conduction never gets worse;
it cannot prove the *sizing* domain is unchanged, so the flag stays off until
that is a decision someone takes on purpose.

    rules = ()                        # default: v1 rules only, unchanged
    LNA_BIAS_RULES=source,drain       # or --rules v3 / --rules source

The guard is unchanged and now covers v3 for free: candidates are evaluated as a
*ladder* of rule sets (none -> gate -> gate+source -> gate+source+drain) and the
best-so-far is kept under the same "strictly more conducting MOS" comparison. A
v3 stage can therefore only ever be adopted if it turns more devices on, and the
no-bias baseline is still candidate 0.

Every inserted element matches ^(RBIAS|CBYP|VBGEN) -- including the v3 elements,
named `RBIASSRC*` / `RBIASDRN*` precisely so the existing naming contract covers
them with no change to topology.py -- so screen.py, novelty.py and the spec
device_budget already exclude it (is_scaffold). Scaffolding is emitted through
to_spice.py's Netlist (the graph is the source of truth), never text-patched.

    python lna/bias.py --index 461 -o work/c461_biased.cir --report work/bias461.json
    python lna/bias.py lna/out/run1/seq0003.txt --sweep --report bias.json
    python lna/bias.py --validate --rules v3 --no-log
"""
import argparse
import itertools
import json
import os
import re
import subprocess
import sys
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

# ---- WP-BIAS v3: the DC-return rules (opt-in; see the module docstring) ----
RULES_ALL = ("source", "drain")
# Source-return grid. A source return is a degeneration resistor: Vs = Id*Rs, so
# Rs must be small enough that the gate's overdrive survives it. At VBG <= 0.65
# and Vth ~ 0.4 V the whole budget is ~0.25 V, i.e. Rs <~ 5k at the 50 uA
# conduction floor -- the grid brackets that, it does not extend past it.
RSRC_GRID = ["200", "1k", "5k"]
# Drain-feed grid. The drain only needs a DC path to exist for conduction; the
# value decides how much headroom is left (Vd = VDD - Id*Rd), so the grid runs
# from "barely loads it" to "definitely in triode" and the guard picks.
RDRN_GRID = ["1k", "5k", "20k"]
R_SRC_DEFAULT = "1k"
R_DRN_DEFAULT = "5k"


def parse_rules(raw):
    """'' -> () · 'v3'/'all' -> both · 'source,drain' -> the named subset."""
    if not raw:
        return ()
    if isinstance(raw, (list, tuple)):
        want = {str(r).strip().lower() for r in raw}
    else:
        want = {s.strip().lower() for s in str(raw).split(",")}
    if want & {"v3", "all"}:
        return RULES_ALL
    return tuple(r for r in RULES_ALL if r in want)


def rules_from_env():
    """Session-wide opt-in, mirroring `LNA_NF_GATE`'s escape-hatch pattern."""
    return parse_rules(os.environ.get("LNA_BIAS_RULES", ""))


def _is_power(node):
    return node in POWER_EXACT or node.startswith(POWER_PREFIX)


class BiasInserter:
    """Analyzes a Netlist's DC graph and builds gate-bias scaffolding."""

    def __init__(self, netlist, r_bias="100k", vbg_default=0.5, cbyp="10p",
                 r_src=R_SRC_DEFAULT, r_drn=R_DRN_DEFAULT):
        self.nl = netlist
        self.t = netlist.t
        self.r_bias = r_bias
        self.vbg_default = vbg_default
        self.cbyp = cbyp
        self.r_src = r_src
        self.r_drn = r_drn
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

        # v3 rule targets, grouped by node (several devices can share one).
        self.source_returns = self._return_groups(self.source_floating, "S")
        self.drain_feeds = self._return_groups(self.drain_floating, "D")

        self.floating = sorted(self.t.floating_devices())
        self.existing_vb = sorted({n for n in self.nl.node_of_pin.values()
                                   if n.startswith(("VB", "VCM", "VREF"))})

    def _return_groups(self, devices, pin):
        """{node: {devices, rail, mixed}} for R-SOURCE / R-DRAIN.

        Rail by device type and terminal: a source returns *away* from the
        supply it works against (NMOS source -> 0, PMOS source -> VDD) and a
        drain is fed *from* it (NMOS drain -> VDD, PMOS drain -> 0). A node
        shared by both polarities takes the majority and is flagged `mixed` --
        it is a real, rare case (a complementary current-reuse stack) and the
        monotonic guard is what decides whether the choice helped.

        ⚠ Known false-positive class, measured not hidden: the DC graph treats a
        MOS channel as an open, so *interior* nodes of a legitimate cascode or
        current-reuse stack also read "no DC path" even though the stack
        conducts once every device is on. Such a node will be offered a return
        resistor it does not need; the guard then declines the stage unless it
        turns more devices on. See the FINDINGS write-up for how often that
        actually happened.
        """
        groups = {}
        for d in devices:
            node = self._node(d, pin)
            if node is None:
                continue
            g = groups.setdefault(node, {"devices": [], "nm": 0, "pm": 0})
            g["devices"].append(d)
            g["nm" if base_of(d) == "NM" else "pm"] += 1
        out = {}
        for node, g in sorted(groups.items()):
            n_is_low = (g["nm"] >= g["pm"]) if pin == "S" else (g["nm"] < g["pm"])
            out[node] = {"devices": sorted(g["devices"]),
                         "rail": "0" if n_is_low else "VDD",
                         "mixed": bool(g["nm"] and g["pm"])}
        return out

    @property
    def n_bias_nets(self):
        return len(self.gate_nodes)

    def param_names(self):
        return [f"pVBG{k}" for k in range(1, self.n_bias_nets + 1)]

    def value_overrides(self):
        return dict(self.pulldown_overrides)

    def build(self, vbg_values=None, rules=(), r_src=None, r_drn=None):
        """Return (elements, params, bias_nets). vbg_values overrides pVBG defaults.

        `rules` selects the opt-in v3 DC-return rules ("source" / "drain"); with
        the default empty tuple the emitted element list is exactly v1's, which
        is what keeps every pre-existing deck byte-identical. The v3 resistances
        are `.param`s like everything else, but they are NOT `pVBG*`, so
        `size.classify_params` files them under *fixed* -- the sizer inherits the
        scaffolding, it does not get a new free variable from it."""
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
        # ---- v3, opt-in ------------------------------------------------
        if "source" in rules:                                      # R-SOURCE
            for k, (node, info) in enumerate(self.source_returns.items(), 1):
                p = f"pRSRC{k}"
                params[p] = r_src or self.r_src
                elements.append(f"RBIASSRC{k} {node} {info['rail']} {{{p}}}")
        if "drain" in rules:                                       # R-DRAIN
            for k, (node, info) in enumerate(self.drain_feeds.items(), 1):
                p = f"pRDRN{k}"
                params[p] = r_drn or self.r_drn
                elements.append(f"RBIASDRN{k} {node} {info['rail']} {{{p}}}")
        return elements, params, bias_nets

    def report(self):
        _, _, bias_nets = self.build()
        return {
            "n_mos": len(self.mos),
            "gates_driven": self.gate_driven,
            "gates_biased": {d: k for k, m in bias_nets.items() for d in m["devices"]},
            "bias_nets": bias_nets,
            "pulldowns_raised": self.pulldown_overrides,
            "drains_no_dc_path": self.drain_floating,     # v1 diagnosis
            "sources_no_dc_path": self.source_floating,   # v1 diagnosis
            "source_returns": self.source_returns,        # R-SOURCE targets (v3)
            "drain_feeds": self.drain_feeds,              # R-DRAIN targets (v3)
            "floating_subcircuit": self.floating,         # R-FLOAT (skip if non-empty)
        }


# ------------------------------------------------------------- op / sweep
_NUM = r"([-\d.eE+]+)"


def run_op(deck):
    """Run an opcheck deck; return {dev: {id, vds, vdsat, vgs}} or None on failure."""
    from extract import run_deck            # self-deleting scratch (FINDINGS §17)
    out = run_deck(deck, "bias_", "op.cir")
    if out is None:
        return None
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


def feasibility_sweep(inserter, netlist, rules=()):
    """L1 grid over the pVBG params; keep the point with the most conducting MOS.

    Returns dict: {best_vbg, n_conducting, n_mos, all_conduct, op, per_device,
    rules_applied, r_src, r_drn}.

    With `rules` empty (the default) this is v1 exactly: same candidate order,
    same comparison, same early break, same sim count.
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
    # v3 stages always sweep VBG *tied*, so adding a resistance dimension costs
    # 4*|Rgrid| sims rather than 4^n*|Rgrid|. The untied grid has already been
    # searched by the gate stage and its best is retained, so a v3 stage only
    # needs to find *additional* conduction, not re-find the gate optimum.
    tied = [{p: v for p in vbg} for v in GRID4] if vbg else [{}]
    pulldowns = inserter.value_overrides()
    n_mos = len(inserter.mos)

    def evaluate(elements, params, ov, biased, knobs, applied=()):
        netlist.set_extra(elements, params, ov)
        op = run_op(netlist.emit(mode="opcheck"))
        allc, per = conducting(op)
        return {"best_vbg": knobs, "biased": biased, "n_conducting": sum(per.values()),
                "n_mos": n_mos, "all_conduct": allc, "op": op or {}, "per_device": per,
                "rules_applied": list(applied)}

    # Candidate 0 = no bias at all. Seeding `best` with it guarantees monotonicity:
    # inserted bias is adopted only if it turns MORE MOS on, never fewer (so no
    # circuit is ever made worse -- the shared-signal-net failure mode). The v3
    # stages below extend the candidate SET, so the guarantee extends with them:
    # best-of over a superset that still contains candidate 0.
    best = evaluate([], {}, {}, False, None)

    def consider(cand):
        """Adopt if strictly better; return True when the search can stop."""
        nonlocal best
        if cand["n_conducting"] > best["n_conducting"] or (
                cand["n_conducting"] == best["n_conducting"]
                and cand["all_conduct"] and not best["all_conduct"]):
            best = cand
        return best["biased"] and best["all_conduct"]

    for combo in combos:
        elements, params, _ = inserter.build(vbg_values=combo)
        if consider(evaluate(elements, params, pulldowns, True, combo)):
            return best

    # ---- v3 ladder (opt-in) ------------------------------------------------
    do_src = "source" in rules and bool(inserter.source_returns)
    do_drn = "drain" in rules and bool(inserter.drain_feeds)
    if do_src:
        for rs in RSRC_GRID:
            for combo in tied:
                el, pr, _ = inserter.build(vbg_values=combo, rules=("source",),
                                           r_src=rs)
                cand = evaluate(el, pr, pulldowns, True, combo, applied=("source",))
                cand["r_src"] = rs
                if consider(cand):
                    return best
    if do_drn:
        # Freeze the source return at whatever the source stage actually won
        # with (falling back to the grid's middle value) and sweep only the
        # drain feed -- two resistance dimensions at once is not worth 3x the
        # sims for a rule whose job is just "give the drain a DC path".
        rs = best.get("r_src") or R_SRC_DEFAULT
        active = ("source", "drain") if do_src else ("drain",)
        for rd in RDRN_GRID:
            for combo in tied:
                el, pr, _ = inserter.build(vbg_values=combo, rules=active,
                                           r_src=rs, r_drn=rd)
                cand = evaluate(el, pr, pulldowns, True, combo, applied=active)
                cand["r_src"], cand["r_drn"] = rs, rd
                if consider(cand):
                    return best
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


def validate(indices, log=False, rules=None):
    """WP-BIAS §4 validation table over the dataset LNAs.

    'on' = |Id| >= 50 uA (what bias controls); 'sat' additionally needs
    |Vds| >= 1.5|Vdsat| (load-sizing dependent -> WP-SIZE). With `log=True` this
    doubles as the corpus L1 backfill (01-DATA §4): one L1 row per index.

    `rules` (v3, opt-in) is stamped into each logged row's provenance as
    `bias_rules` + a bumped `recipe`, so v1 and v3 L1 rows are separable label
    domains rather than an undated mixture."""
    import numpy as np
    active = rules_from_env() if rules is None else parse_rules(rules)
    if active:
        print(f"WP-BIAS v3 rules ENABLED: {', '.join(active)}")
    print(f"{'idx':>5} {'MOS':>3} {'bias':>4} {'on0':>4} {'onB':>4} {'satB':>4}  note")
    n_all_on = n_all_sat = n_worse = n_eval = 0
    off_total = off_src = off_drn = 0
    n_v3_used = 0
    vgs461 = None
    for i in indices:
        p = os.path.join(REPO, "Dataset", str(i), f"Sequence_total{i}.npy")
        if not os.path.exists(p):
            continue
        topo = Topology([str(t) for t in np.load(p, allow_pickle=True)[0]])
        prov = {"source_arm": "corpus", "index": i}
        if active:
            prov["bias_rules"] = list(active)
            prov["recipe"] = "bias-v3"
        nl, inserter, rep, swept = insert_bias(
            topo, sweep=True, log=log, rules=active, provenance=prov)
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
        v3 = rep.get("rules_applied") or []
        if v3:
            n_v3_used += 1
        applied = rep.get("bias_applied") and rep["bias_nets"]
        note = ("biased " + ",".join(rep["bias_nets"])) if applied else "no bias applied"
        if v3:
            # "no bias applied" would be a lie once a v3 rule has been adopted:
            # scaffolding IS in the deck, there just are no gate bias nets.
            note = f"+{'+'.join(v3)} " + (note if applied else "no gate nets")
        print(f"{i:>5} {nmos:>3} {len(rep['bias_nets']):>4} {on0:>4} {onB:>4} {satB:>4}  "
              f"{'WORSE ' if onB < on0 else ''}{note[:40]}")
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
    if active:
        print(f"  circuits where a v3 rule WON   : {n_v3_used}/{n_eval}   "
              f"[a stage is adopted only if it conducts strictly more]")
    if vgs461 is not None:
        print(f"  461 spot check: NM1 Vgs = {vgs461*1e3:.0f} mV "
              f"(was 14 mV; want 350-650 mV)  {'PASS' if 0.30 <= vgs461 <= 0.70 else 'FAIL'}")
    return n_all_on, n_eval, n_worse


def _log_l1(topo, rep, swept, provenance=None):
    """Append one L1 row to the label store (01-DATA §1). Import is lazy so
    bias.py stays import-light for pipeline_yield/size; logging never raises."""
    try:
        import datastore as ds
        from novelty import wl_features
        row = ds.row_l1(topo, rep, swept, provenance=provenance)
        row["wl_hash"] = wl_features(topo)[0]
        ds.append("l1_labels", row)
        return True
    except Exception as e:
        print(f"  [log] WARN: L1 logging failed: {e}")
        return False


def insert_bias(topo, sweep=False, log=False, provenance=None, rules=None, **kw):
    """Convenience: (netlist, inserter, report, sweep_result). Netlist has the
    winning (or default) scaffolding already set.

    With `log=True` a completed sweep is appended to the label store as one L1
    row. Defaults off so library callers (size.py, pipeline_yield) do not log;
    the bias.py --sweep/--validate CLI paths turn it on (01-DATA §3).

    `rules` selects the opt-in v3 DC-return rules; `None` (the default) reads
    `LNA_BIAS_RULES` from the environment, which is empty unless a session opts
    in, so **every existing caller keeps v1 behaviour byte for byte**."""
    active = rules_from_env() if rules is None else parse_rules(rules)
    nl = Netlist(topo, **kw)
    inserter = BiasInserter(nl)
    rep = inserter.report()
    if active:
        rep["rules_enabled"] = list(active)
    swept = None
    if inserter.floating:
        rep["skipped"] = "floating_subcircuit"
    elif sweep:
        swept = feasibility_sweep(inserter, nl, rules=active)
        rep["sweep"] = {k: v for k, v in swept.items() if k != "op"}
    if swept is not None and not swept["biased"]:
        nl.set_extra([], {}, {})        # bias did not help -> ship the baseline
        rep["bias_applied"] = False
    else:
        knobs = swept["best_vbg"] if (swept and swept["best_vbg"]) else None
        won = tuple((swept or {}).get("rules_applied") or ())
        elements, params, _ = inserter.build(
            vbg_values=knobs, rules=won,
            r_src=(swept or {}).get("r_src"), r_drn=(swept or {}).get("r_drn"))
        nl.set_extra(elements, params, inserter.value_overrides())
        rep["bias_applied"] = True
        rep["operating_point"] = knobs
        if won:
            rep["rules_applied"] = list(won)
    if log and swept is not None:
        _log_l1(topo, rep, swept, provenance=provenance)
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
    ap.add_argument("--no-log", action="store_true",
                    help="do not append L1 rows to the label store")
    ap.add_argument("--rules", default=None,
                    help="opt-in v3 DC-return rules: 'source', 'drain', "
                         "'source,drain' or 'v3'. Default: $LNA_BIAS_RULES "
                         "(empty = v1 behaviour, byte-identical)")
    args = ap.parse_args()
    log = not args.no_log
    rules = rules_from_env() if args.rules is None else parse_rules(args.rules)

    if args.validate:
        idx = list(range(461, 493)) + list(range(1081, 1091))
        validate(idx, log=log, rules=rules)
        return 0

    if args.index is not None:
        topo = topo_from_index(args.index)
        label = f"index {args.index}"
        prov = {"source_arm": "corpus", "index": args.index}
    elif args.sequence:
        topo = Topology(parse_arrow_file(args.sequence))
        label = args.sequence
        prov = {"source_arm": "cli", "token_file": args.sequence}
    else:
        ap.error("give a sequence file or --index")
    if rules:
        prov["bias_rules"] = list(rules)
        prov["recipe"] = "bias-v3"

    nl, inserter, rep, swept = insert_bias(
        topo, sweep=args.sweep, log=(args.sweep and log), provenance=prov,
        rules=rules)

    print(f"=== bias insertion: {label} ===")
    print(f"  MOS devices        : {rep['n_mos']}")
    print(f"  gates already driven: {rep['gates_driven']}")
    print(f"  gates biased (R-GATE): {rep['gates_biased']}")
    print(f"  bias nets inserted : {list(rep['bias_nets'])}")
    if rep["drains_no_dc_path"]:
        tag = "R-DRAIN targets" if rules else "diagnose-only"
        print(f"  drains w/o DC path : {rep['drains_no_dc_path']}  ({tag}: "
              f"{ {n: i['rail'] for n, i in rep['drain_feeds'].items()} })")
    if rep["sources_no_dc_path"]:
        tag = "R-SOURCE targets" if rules else "diagnose-only"
        print(f"  sources w/o DC path: {rep['sources_no_dc_path']}  ({tag}: "
              f"{ {n: i['rail'] for n, i in rep['source_returns'].items()} })")
    if rep.get("rules_applied"):
        print(f"  v3 rules ADOPTED   : {rep['rules_applied']}  "
              f"Rsrc={(swept or {}).get('r_src')} Rdrn={(swept or {}).get('r_drn')}")
    elif rules:
        print(f"  v3 rules enabled   : {list(rules)}  -- none adopted "
              f"(the guard found no conduction gain)")
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

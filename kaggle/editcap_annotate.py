"""editcap_annotate.py -- deterministic, purely-structural circuit annotation
for editcap-v1 arm E (--annotate).

Given a proposal-dialect netlist (the SAME text the model is shown as the anchor)
this emits a plain-text annotation block derived PURELY from the netlist GRAPH:
- per-device pin -> net bindings, spelled out;
- a GRAPH FACTS section whose every line is a deterministically-computable fact
  about the connectivity (diode-connected devices, gate DC paths, DC-blocking
  series caps on the ports, source-degeneration inductors, rail->gate resistor
  chains, and net membership lists).

Scope discipline (frozen by the arm-E commission, targets the measured v0
comprehension failures -- see kaggle/campaigns/qwen-editcap-v0/ADJUDICATION.md
"bias-mirror blind spot", "pin-order misbinding", "missing X templates"):

  * NO spec knowledge (constraints/targets never enter here).
  * NO technique interpretation: the words "current mirror", "matching network",
    "cascode", "degeneration", "common-gate/source" are FORBIDDEN -- they are
    design readings, not graph facts. Only structural statements are emitted.
    "diode-connected (gate tied to drain)" IS allowed: it is a graph fact
    (a pin-equality on one device), explicitly sanctioned by the commission.
  * DETERMINISTIC: identical netlist -> byte-identical block. Iteration is over
    the parse order (rows) and sorted keys, never a set's hash order.

The graph is built from `proposal.parse` rows, which preserve the human-readable
internal net names (n1..n7) exactly as they appear in the anchor netlist the
model sees -- so "NM1 drain=n5" in the annotation refers to the same n5 the model
reads two lines up. (The token->Topology path collapses internal nets into
anonymous electrical nodes and would lose those labels; the parsed rows are the
label-faithful graph source.)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("LNA_DEPS_ROOT") or os.path.abspath(os.path.join(HERE, ".."))
LOOP = os.path.join(ROOT, "kaggle", "loop")
if LOOP not in sys.path:
    sys.path.insert(0, LOOP)

import proposal as P  # noqa: E402  (proposal.parse / _TYPE_MAP / _PIN_ORDER)

# proposal internal type token -> (dialect TYPE, pin-name tuple in row order)
_TYPE_PINS = {
    "nmos4": ("NMOS", ("drain", "gate", "source", "bulk")),
    "pmos4": ("PMOS", ("drain", "gate", "source", "bulk")),
    "resistor": ("R", ("p", "n")),
    "capacitor": ("C", ("p", "n")),
    "inductor": ("L", ("p", "n")),
}
_RAILS = ("VDD", "VSS")
_PORTS_IN = "VIN1"
_PORTS_OUT = "VOUT1"


class _Dev(object):
    """One parsed device with named pin->net bindings, in dialect order."""
    __slots__ = ("name", "dtype", "pins")

    def __init__(self, row):
        typ = row[-1]
        dialect, pinnames = _TYPE_PINS[typ]
        nets = row[1:-1]
        self.name = row[0]
        self.dtype = dialect                       # NMOS/PMOS/R/C/L
        self.pins = list(zip(pinnames, nets))      # [(pinname, net), ...] in order

    def net(self, pinname):
        for pn, nt in self.pins:
            if pn == pinname:
                return nt
        return None

    @property
    def is_mos(self):
        return self.dtype in ("NMOS", "PMOS")


def _devices(rows):
    return [_Dev(r) for r in rows]


def _net_members(devs):
    """net -> ordered list of "DEV.pin" strings touching it (parse order)."""
    mem = {}
    for d in devs:
        for pn, nt in d.pins:
            mem.setdefault(nt, []).append("%s.%s" % (d.name, pn))
    return mem


def _dc_adjacency(devs):
    """Net adjacency over DC-CONDUCTING device edges only.

    R and L conduct DC (a short at DC / a resistive drop); C BLOCKS DC. A MOS is
    NOT a wire between any two nets (it is an active device), so it contributes no
    DC edge here -- this walk answers "which nets are tied together through
    passives that pass DC", the exact question behind gate-bias-path facts.
    Returns {net: set(neighbour nets)}.
    """
    adj = {}
    for d in devs:
        if d.dtype in ("R", "L"):
            a, b = d.pins[0][1], d.pins[1][1]
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
        else:
            # still register the nets so isolated-through-C nets appear as keys
            for _pn, nt in d.pins:
                adj.setdefault(nt, set())
    return adj


def _dc_reaches_rail(start, adj):
    """BFS over DC-conducting edges from `start`; return the set of rails
    ({VDD,VSS}) DC-reachable, plus the visited-net set (for path reporting)."""
    seen = {start}
    stack = [start]
    rails = set()
    while stack:
        cur = stack.pop()
        if cur in _RAILS:
            rails.add(cur)
        for nb in sorted(adj.get(cur, ())):
            if nb not in seen:
                seen.add(nb)
                stack.append(nb)
    return rails, seen


def _resistor_chain_to_gate(devs, gate_net):
    """If a gate net is fed by a pure RESISTOR chain from a rail, return the
    ordered edge list [(dev, from, to), ...] rail->...->gate; else None.

    Deterministic shortest resistor-only path (BFS over R edges) from either rail
    to the gate net; ties broken by sorted neighbour order. Inductors are NOT
    counted here (a rail->gate resistor chain is the specific, common bias idiom
    the annotation reports; L-fed gates surface via the generic DC-path fact)."""
    # build R-only adjacency carrying the device name on each edge
    radj = {}
    for d in devs:
        if d.dtype == "R":
            a, b = d.pins[0][1], d.pins[1][1]
            radj.setdefault(a, []).append((b, d.name))
            radj.setdefault(b, []).append((a, d.name))
    for rail in _RAILS:                       # VDD first, then VSS (deterministic)
        if rail not in radj:
            continue
        prev = {rail: None}
        q = [rail]
        while q:
            cur = q.pop(0)
            if cur == gate_net:
                # reconstruct edge chain
                chain = []
                node = gate_net
                while prev[node] is not None:
                    pnode, dev = prev[node]
                    chain.append((dev, pnode, node))
                    node = pnode
                chain.reverse()
                return chain
            for nb, dev in sorted(radj.get(cur, []), key=lambda x: (x[0], x[1])):
                if nb not in prev:
                    prev[nb] = (cur, dev)
                    q.append(nb)
    return None


# ============================================================ section builders
def _bindings_section(devs):
    lines = ["=== DEVICE PIN BINDINGS ==="]
    for d in devs:
        binds = ", ".join("%s=%s" % (pn, nt) for pn, nt in d.pins)
        lines.append("%s: %s, %s" % (d.name, d.dtype, binds))
    return lines


def _facts_section(devs):
    facts = []
    adj = _dc_adjacency(devs)

    # -- diode-connected MOS (gate net == drain net) -------------------------
    diodes = [d for d in devs if d.is_mos and d.net("gate") == d.net("drain")]
    for d in diodes:
        facts.append("%s is diode-connected (gate tied to drain: both = %s)."
                     % (d.name, d.net("gate")))

    # -- gate DC-bias path per MOS ------------------------------------------
    for d in devs:
        if not d.is_mos:
            continue
        g = d.net("gate")
        if g == d.net("drain"):
            # diode-connected: gate==drain, already reported; still state its rail
            rails, _ = _dc_reaches_rail(g, adj)
            continue
        chain = _resistor_chain_to_gate(devs, g)
        if chain:
            hops = " -> ".join(["%s" % chain[0][1]]
                               + ["%s(%s)" % (t, dev) for dev, _f, t in chain])
            facts.append("%s gate (%s) is biased through a resistor chain: %s."
                         % (d.name, g, hops))
        else:
            rails, _seen = _dc_reaches_rail(g, adj)
            if rails:
                facts.append("%s gate (%s) has a DC-conducting path to %s (via "
                             "R/L edges)." % (d.name, g, "/".join(sorted(rails))))
            else:
                facts.append("%s gate (%s) has NO DC-conducting path to any rail "
                             "(VDD/VSS): all edges out of %s are DC-blocking "
                             "capacitors." % (d.name, g, g))

    # -- DC-blocking series caps on the input / output path ------------------
    for d in devs:
        if d.dtype != "C":
            continue
        a, b = d.pins[0][1], d.pins[1][1]
        if _PORTS_IN in (a, b):
            other = b if a == _PORTS_IN else a
            facts.append("%s is a DC-blocking series capacitor on the INPUT path "
                         "(%s in series between %s and %s)."
                         % (d.name, d.name, _PORTS_IN, other))
        if _PORTS_OUT in (a, b):
            other = b if a == _PORTS_OUT else a
            facts.append("%s is a DC-blocking series capacitor on the OUTPUT path "
                         "(%s in series between %s and %s)."
                         % (d.name, d.name, other, _PORTS_OUT))

    # -- inductors between a MOS source and VSS ------------------------------
    mos_sources = {}
    for d in devs:
        if d.is_mos:
            mos_sources.setdefault(d.net("source"), []).append(d.name)
    for d in devs:
        if d.dtype != "L":
            continue
        a, b = d.pins[0][1], d.pins[1][1]
        endpoints = {a, b}
        if "VSS" in endpoints:
            src = b if a == "VSS" else a
            if src in mos_sources:
                for mos in sorted(mos_sources[src]):
                    facts.append("%s connects %s source (%s) to VSS."
                                 % (d.name, mos, src))

    # -- net membership lists (every net, sorted; ground/rails last) ---------
    mem = _net_members(devs)
    def _net_key(n):
        # ports/rails grouped after internal nets, but all sorted for determinism
        return (0 if n not in (_PORTS_IN, _PORTS_OUT) + _RAILS else 1, n)
    facts.append("")
    facts.append("net membership (every net -> the device pins on it):")
    for n in sorted(mem, key=_net_key):
        facts.append("  %s: %s" % (n, ", ".join(mem[n])))

    return ["=== GRAPH FACTS ==="] + facts


# ============================================================ public API
def annotate_rows(rows):
    """Build the annotation block from parsed proposal rows. Deterministic."""
    devs = _devices(rows)
    lines = []
    lines += _bindings_section(devs)
    lines.append("")
    lines += _facts_section(devs)
    return "\n".join(lines)


def annotate(net_text):
    """Build the annotation block from proposal-dialect netlist TEXT.

    Parses the SAME text shown to the model as the anchor, so net labels match.
    Returns a plain-text block (no trailing newline)."""
    rows, _ports = P.parse(net_text)
    return annotate_rows(rows)


if __name__ == "__main__":
    txt = sys.stdin.read()
    print(annotate(txt))

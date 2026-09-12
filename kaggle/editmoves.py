"""editmoves.py -- the MOVE LIBRARY for campaign editmoves-v0 (user-commissioned
2026-09-12; motivated by qwen-editcap-v0's adjudication finding that Qwen cannot
AUTHOR valid netlists reliably but CAN name techniques -- see
kaggle/campaigns/qwen-editcap-v0/ADJUDICATION.md).

The moves here are structural PRIMITIVES over parsed proposal-dialect rows
(proposal.parse output). Each is VALID-BY-CONSTRUCTION so the LLM only ever
SELECTS a (move, site); it never emits connectivity. The measured failure modes
this design forecloses (all from the v0 adjudication):
  * "bias-mirror blind spot": every NEW MOS gate is biased in-topology by the SAME
    mirror idiom the c1/c3 anchors use (R from a rail -> diode-connected device ->
    R to the new gate), so a move never leaves a floating gate.
  * "harness-convention blindness" (the dead-bias failure externals-v0 taught US):
    NO move ever creates a DC-conducting path from VIN1/VOUT1 into a MOS gate node.
    Input/output matching primitives attach on the INTERNAL side of the port's
    DC-block series capacitor; a new cap-coupled stage keeps its coupling cap.

Program directive (nudge-limit / no class-specific macros): every operator is a
GENERIC composable structural primitive. There is no "make-this-a-900MHz-LNA"
macro; there are matching primitives, a cascode, a degeneration inductor, a
feedback RC, a mirror-biased second stage, and output primitives -- each applies
wherever its site predicate matches, on ANY topology.

Operator protocol (each move is an instance of `Move`):
  name                : stable identifier (also the menu label)
  applicable_sites(rows) -> [site, ...]   site = a small dict describing WHERE
  apply(rows, site)   -> new_rows          pure; returns a fresh row list
  describe(rows, site) -> str              one-line NEUTRAL, mechanical menu text
                                           (no benefit claims -- arm-M menu rule)

HARD INVARIANTS (checked by `check_invariants`, enforced in the unit test on
EVERY move at EVERY site of BOTH anchor families):
  I1 round_trip valid   -- parses, Eulerian tokens exist, Topology.valid, AND the
                           WL hash differs from the input (a real structural edit).
  I2 no VIN1/VOUT1 -> gate DC path -- respect the DC-block convention.
  I3 every NEW MOS gate has an in-topology DC bias (rail -> diode dev -> gate),
                           i.e. a DC-conducting path from the gate to a rail that
                           does NOT pass through a port.
  I4 device budget <= 16  (ladder cap).

Rows are the internal read_netlist form `[name, net1..netK, type]` with type in
{nmos4, pmos4, resistor, capacitor, inductor}. We operate on a deep copy and
return a new list; the caller's rows are never mutated.
"""
import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("LNA_DEPS_ROOT") or os.path.abspath(os.path.join(HERE, ".."))
LOOP = os.path.join(ROOT, "kaggle", "loop")
LNA = os.path.join(ROOT, "lna")
for _p in (LOOP, LNA):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import proposal as P  # noqa: E402

# internal type tokens (proposal._TYPE_MAP values) -----------------------------
NMOS, PMOS = "nmos4", "pmos4"
R, C, L = "resistor", "capacitor", "inductor"
MOS_TYPES = (NMOS, PMOS)
PASSIVE_TYPES = (R, C, L)

RAILS = ("VDD", "VSS")
VIN, VOUT = "VIN1", "VOUT1"
PORTS = ("VIN1", "VOUT1")
DEVICE_BUDGET = 16          # ladder cap (I4)

# MOS pin index in a row: [name, D, G, S, B, type]  (proposal._PIN_ORDER D G S B)
_MD, _MG, _MS, _MB = 1, 2, 3, 4
# passive pin index in a row: [name, P, N, type]
_PP, _PN = 1, 2


# ================================================================ row helpers
def _type(row):
    return row[-1]


def _name(row):
    return row[0]


def _nets(row):
    return row[1:-1]


def _is_mos(row):
    return _type(row) in MOS_TYPES


def _mos_pins(row):
    """(drain, gate, source, bulk) for a MOS row."""
    return row[_MD], row[_MG], row[_MS], row[_MB]


def _passive_pins(row):
    return row[_PP], row[_PN]


def _all_nets(rows):
    s = set()
    for r in rows:
        for n in _nets(r):
            s.add(n)
    return s


def _internal_nets(rows):
    """Nets that are neither a rail nor a port (the n1..n7 style labels)."""
    return sorted(n for n in _all_nets(rows)
                  if n not in RAILS and n not in PORTS)


def _fresh_net(rows, base="m"):
    """A net name guaranteed absent from `rows`. Deterministic: base+index."""
    used = _all_nets(rows)
    i = 1
    while True:
        cand = "%s%d" % (base, i)
        if cand not in used:
            return cand
        i += 1


def _fresh_name(rows, prefix):
    """A device name guaranteed absent from `rows`. Deterministic: prefix+index."""
    used = {_name(r) for r in rows}
    i = 1
    while True:
        cand = "%s%d" % (prefix, i)
        if cand not in used:
            return cand
        i += 1


def _mk_mos(name, d, g, s, b, ntype=NMOS):
    return [name, d, g, s, b, ntype]


def _mk_pas(name, p, n, ptype):
    return [name, p, n, ptype]


def _diode_bias_for_gate(rows, gate_net, rail="VDD", tag="B"):
    """Build the anchor's in-topology mirror-bias idiom for a NEW gate net.

    Reuses the c1/c3 pattern EXACTLY (c1: R1 VDD n6 / NM3 n6 n6 VSS VSS / R2 n6 n3):
      R  <rail> -> mnode        (rail to the mirror node)
      MOS mnode mnode VSS VSS   (diode-connected reference; NMOS ref for VDD chain)
      R  mnode  -> gate_net     (mirror node feeds the new gate through a resistor)

    Returns (new_device_rows, mnode). The gate is thereby DC-biased to a rail
    through R/diode only -- never through a port (satisfies I2/I3). Deterministic
    names/nets (tagged) so repeated moves on one netlist do not collide."""
    mnode = _fresh_net(rows, base="mb%s" % tag)
    r_rail = _mk_pas(_fresh_name(rows, "Rb%s" % tag), rail, mnode, R)
    # diode-connected reference device sits between the mirror node and VSS.
    ref = _mk_mos(_fresh_name(rows, "NMb%s" % tag), mnode, mnode, "VSS", "VSS", NMOS)
    # feed the gate from the mirror node through a resistor (as R2 n6 n3 does).
    # use a set of rows that already includes r_rail/ref so names/nets stay unique.
    staged = rows + [r_rail, ref]
    r_gate = _mk_pas(_fresh_name(staged, "Rg%s" % tag), mnode, gate_net, R)
    return [r_rail, ref, r_gate], mnode


# ---- DC adjacency (mirrors editcap_annotate: R/L conduct DC, C blocks it) ----
def _dc_adj(rows):
    """{net: set(neighbours)} over DC-conducting passive edges (R and L only).

    A MOS is NOT a DC wire (active device); a C BLOCKS DC. This is the exact
    convention editcap_annotate uses for gate-bias-path facts -- reused so the
    invariant check and the annotation agree byte-for-byte on what "DC path"
    means."""
    adj = {}
    for r in rows:
        t = _type(r)
        if t in (R, L):
            a, b = _passive_pins(r)
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
        else:
            for n in _nets(r):
                adj.setdefault(n, set())
    return adj


def _dc_reachable(start, adj, blocked=()):
    """Set of nets DC-reachable from `start`, never traversing a `blocked` net
    (used to forbid paths THROUGH a port)."""
    blocked = set(blocked)
    seen = {start}
    stack = [start]
    while stack:
        cur = stack.pop()
        for nb in adj.get(cur, ()):
            if nb in blocked or nb in seen:
                continue
            seen.add(nb)
            stack.append(nb)
    return seen


def _gate_nets(rows):
    return {_mos_pins(r)[1] for r in rows if _is_mos(r)}


# ================================================================ invariants
def check_invariants(in_rows, out_rows, moved_gates=()):
    """Enforce the four hard invariants on an applied move. Returns
    (ok, detail_dict). `moved_gates` lists gate nets the move NEWLY created (their
    in-topology bias is checked by I3). Never raises -- a violation is a first-class
    recorded outcome (the unit test asserts ok)."""
    detail = {"I1_round_trip": None, "I1_wl_distinct": None, "I2_port_gate": None,
              "I3_new_gate_bias": None, "I4_budget": None, "wl_in": None,
              "wl_out": None, "error": None}

    # I4 device budget -----------------------------------------------------
    detail["I4_budget"] = (len(out_rows) <= DEVICE_BUDGET)

    # I1 round_trip valid + WL distinct ------------------------------------
    in_text = P.rows_to_text(in_rows)
    out_text = P.rows_to_text(out_rows)
    info_in = P.round_trip(in_text)
    info_out = P.round_trip(out_text)
    detail["wl_in"] = info_in.get("wl_hash")
    detail["wl_out"] = info_out.get("wl_hash")
    detail["I1_round_trip"] = bool(info_out.get("ok"))
    if not info_out.get("ok"):
        detail["error"] = info_out.get("error")
    detail["I1_wl_distinct"] = bool(
        info_out.get("wl_hash") and info_in.get("wl_hash")
        and info_out["wl_hash"] != info_in["wl_hash"])

    # I2 no VIN1/VOUT1 -> MOS-gate DC path ---------------------------------
    adj = _dc_adj(out_rows)
    gates = _gate_nets(out_rows)
    port_gate_hit = None
    for port in PORTS:
        if port not in adj:
            continue
        reach = _dc_reachable(port, adj)     # DC nets touchable from the port
        bad = (reach & gates) - {port}
        # a gate net that IS a rail is a legitimately-biased gate (e.g. NM2 gate
        # tied to VDD in c1); the DC-block rule is about SIGNAL ports reaching a
        # gate, so only flag gates reachable from a PORT via DC passives.
        if bad:
            port_gate_hit = (port, sorted(bad))
            break
    detail["I2_port_gate"] = (port_gate_hit is None)
    if port_gate_hit is not None:
        detail["I2_detail"] = {"port": port_gate_hit[0], "gates": port_gate_hit[1]}

    # I3 every NEW gate has an in-topology bias to a rail (not via a port) --
    i3_ok = True
    i3_detail = {}
    for g in moved_gates:
        # a diode-connected gate (gate==drain) is self-biased by construction;
        # otherwise require a DC path to a rail that does NOT pass through a port.
        reach = _dc_reachable(g, adj, blocked=PORTS)
        hits_rail = bool(reach & set(RAILS))
        i3_detail[g] = hits_rail
        if not hits_rail:
            i3_ok = False
    detail["I3_new_gate_bias"] = i3_ok if moved_gates else True
    if moved_gates:
        detail["I3_detail"] = i3_detail

    ok = bool(detail["I1_round_trip"] and detail["I1_wl_distinct"]
              and detail["I2_port_gate"] and detail["I3_new_gate_bias"]
              and detail["I4_budget"])
    return ok, detail


# ================================================================ Move base
class Move(object):
    """A structural primitive. Subclasses set `name` and implement
    `applicable_sites` / `apply` / `describe`."""
    name = "move"

    def applicable_sites(self, rows):
        raise NotImplementedError

    def apply(self, rows, site):
        raise NotImplementedError

    def describe(self, rows, site):
        return self.name

    # convenience: the gate nets this move NEWLY introduces (for I3). Default
    # none; moves that add a MOS override `new_gates`.
    def new_gates(self, rows, site):
        return ()


# ---- site discovery helpers -------------------------------------------------
def _input_dcblock_cap(rows):
    """The DC-block series cap on the INPUT: a C with one pin == VIN1. Returns
    (cap_row, inner_net) or None -- inner_net is the non-VIN1 side (where input
    matching primitives attach, satisfying the DC-block rule)."""
    for r in rows:
        if _type(r) == C:
            a, b = _passive_pins(r)
            if a == VIN or b == VIN:
                inner = b if a == VIN else a
                return r, inner
    return None


def _output_dcblock_cap(rows):
    """The DC-block series cap on the OUTPUT: a C with one pin == VOUT1. Returns
    (cap_row, inner_net) or None."""
    for r in rows:
        if _type(r) == C:
            a, b = _passive_pins(r)
            if a == VOUT or b == VOUT:
                inner = b if a == VOUT else a
                return r, inner
    return None


def _mos_load_sites(rows):
    """Every (mos_row, drain_net) where the drain is an INTERNAL net (not a rail
    or port) -- a legal insertion point for a cascode between the MOS drain and
    whatever it currently drives."""
    out = []
    for r in rows:
        if not _is_mos(r):
            continue
        d = _mos_pins(r)[0]
        if d not in RAILS and d not in PORTS:
            out.append((r, d))
    return out


def _mos_source_to_vss(rows):
    """Every MOS whose SOURCE is directly VSS -- a legal site for a degeneration
    inductor between the source and VSS."""
    return [r for r in rows if _is_mos(r) and _mos_pins(r)[2] == "VSS"]


def _mos_drain_gate_pairs(rows):
    """Every MOS with an INTERNAL drain AND an INTERNAL gate (both n-nets) and
    drain != gate -- a legal site for a shunt-feedback R+C from drain to gate (C
    keeps DC isolation so the gate bias is untouched)."""
    out = []
    for r in rows:
        if not _is_mos(r):
            continue
        d, g = _mos_pins(r)[0], _mos_pins(r)[1]
        if (d not in RAILS and d not in PORTS and g not in RAILS
                and g not in PORTS and d != g):
            out.append((r, d, g))
    return out


def _current_output_node(rows):
    """The internal node feeding the OUTPUT DC-block cap -- the node a new
    cap-coupled second stage taps. Returns the inner net or None."""
    oc = _output_dcblock_cap(rows)
    return oc[1] if oc else None


def _fits(rows, adds):
    """True if applying a move that adds `adds` devices keeps the netlist within
    the ladder cap (I4). Every operator gates its sites on this so a move is never
    even OFFERED where it cannot legally apply (matters when the driver composes
    k=3 moves sequentially onto an increasingly-full netlist)."""
    return len(rows) + adds <= DEVICE_BUDGET


# ================================================================ the operators
class AddSeriesLInput(Move):
    """Insert a series inductor into the input chain, on the INTERNAL side of the
    DC-block cap (never between VIN1 and the cap -- DC-block rule)."""
    name = "add_series_L_input"

    def applicable_sites(self, rows):
        ic = _input_dcblock_cap(rows)
        return [{"inner": ic[1]}] if (ic and _fits(rows, 1)) else []

    def apply(self, rows, site):
        rows = copy.deepcopy(rows)
        inner = site["inner"]
        mid = _fresh_net(rows, base="li")
        # rewire everything currently on `inner` (except the DC-block cap) to mid,
        # then bridge inner->mid with the new series L. Simpler + graph-equivalent:
        # move the DC-block cap's inner pin to a new node and put L between them.
        ic = _input_dcblock_cap(rows)
        cap_row = ic[0]
        # cap inner pin -> mid ; L mid -> inner (series L after the cap)
        for i in (_PP, _PN):
            if cap_row[i] == inner:
                cap_row[i] = mid
        rows.append(_mk_pas(_fresh_name(rows, "Lin"), mid, inner, L))
        return rows

    def describe(self, rows, site):
        ic = _input_dcblock_cap(rows)
        return ("%s at input: insert a series L in the input chain on the internal "
                "side of DC-block cap %s (node %s)."
                % (self.name, _name(ic[0]), site["inner"]))


class AddShuntCInput(Move):
    """Add a shunt capacitor from the input internal node to VSS (after the
    DC-block cap)."""
    name = "add_shunt_C_input"

    def applicable_sites(self, rows):
        ic = _input_dcblock_cap(rows)
        return [{"inner": ic[1]}] if (ic and _fits(rows, 1)) else []

    def apply(self, rows, site):
        rows = copy.deepcopy(rows)
        rows.append(_mk_pas(_fresh_name(rows, "Cin"), site["inner"], "VSS", C))
        return rows

    def describe(self, rows, site):
        return ("%s at input: add a shunt C from input internal node %s to VSS "
                "(after the DC-block cap)." % (self.name, site["inner"]))


class AddLMatchSectionInput(Move):
    """Series-L + shunt-C together on the input internal chain (one L-match
    section, both after the DC-block cap)."""
    name = "add_L_match_section_input"

    def applicable_sites(self, rows):
        ic = _input_dcblock_cap(rows)
        if not ic or not _fits(rows, 2):              # +series L, +shunt C (I4)
            return []
        return [{"inner": ic[1]}]

    def apply(self, rows, site):
        rows = copy.deepcopy(rows)
        inner = site["inner"]
        mid = _fresh_net(rows, base="lm")
        ic = _input_dcblock_cap(rows)
        cap_row = ic[0]
        for i in (_PP, _PN):
            if cap_row[i] == inner:
                cap_row[i] = mid
        # series L (mid->inner), then shunt C (mid->VSS): L then shunt at the node
        # between cap and the rest, a standard L-section, all on the internal side.
        rows.append(_mk_pas(_fresh_name(rows, "Lin"), mid, inner, L))
        rows.append(_mk_pas(_fresh_name(rows, "Cin"), mid, "VSS", C))
        return rows

    def describe(self, rows, site):
        ic = _input_dcblock_cap(rows)
        return ("%s at input: add a series-L + shunt-C L-section on the internal "
                "side of DC-block cap %s (node %s)."
                % (self.name, _name(ic[0]), site["inner"]))


class AddCascodeNMOS(Move):
    """Insert a cascode NMOS between a MOS drain and its load net: the existing
    MOS drain moves to a new internal node; a new NMOS sits with drain = old load
    net, source = that new node, gate tied to VDD (a rail is a legitimate gate
    bias -- no port DC path, no new mirror needed)."""
    name = "add_cascode_NMOS"

    def applicable_sites(self, rows):
        if not _fits(rows, 1):                        # +cascode NMOS (I4)
            return []
        return [{"mos": _name(r), "load": d} for r, d in _mos_load_sites(rows)]

    def apply(self, rows, site):
        rows = copy.deepcopy(rows)
        target = next(r for r in rows if _name(r) == site["mos"])
        load = site["load"]
        mid = _fresh_net(rows, base="csc")
        # move the existing MOS drain to the new intermediate node
        target[_MD] = mid
        # new cascode NMOS: drain = old load net, gate = VDD, source = mid, bulk VSS
        casc = _mk_mos(_fresh_name(rows, "NMc"), load, "VDD", mid, "VSS", NMOS)
        rows.append(casc)
        return rows

    def new_gates(self, rows, site):
        # the cascode gate is VDD (a rail) -- a legitimate, non-port bias; no new
        # INTERNAL gate net is created, so I3 has nothing to enforce.
        return ()

    def describe(self, rows, site):
        return ("%s at %s: insert an NMOS between %s drain (%s) and its load net; "
                "cascode gate tied to VDD."
                % (self.name, site["mos"], site["mos"], site["load"]))


class AddSourceDegenL(Move):
    """Insert a degeneration inductor between a MOS source and VSS when the source
    is directly VSS (the c1 L2 idiom: L NM1-source -> VSS)."""
    name = "add_source_degen_L"

    def applicable_sites(self, rows):
        if not _fits(rows, 1):                        # +degeneration L (I4)
            return []
        return [{"mos": _name(r)} for r in _mos_source_to_vss(rows)]

    def apply(self, rows, site):
        rows = copy.deepcopy(rows)
        target = next(r for r in rows if _name(r) == site["mos"])
        node = _fresh_net(rows, base="sd")
        target[_MS] = node                     # source now floats to the new node
        rows.append(_mk_pas(_fresh_name(rows, "Ldg"), node, "VSS", L))
        return rows

    def describe(self, rows, site):
        return ("%s at %s: insert a degeneration L between %s source and VSS."
                % (self.name, site["mos"], site["mos"]))


class AddShuntFeedbackRC(Move):
    """Series R+C between a MOS drain net and its gate net (C preserves the gate's
    DC bias -- the feedback is AC only, so the existing bias path is untouched and
    no port DC path is created)."""
    name = "add_shunt_feedback_RC"

    def applicable_sites(self, rows):
        if not _fits(rows, 2):                        # +series R, +C (I4)
            return []
        return [{"mos": _name(r), "drain": d, "gate": g}
                for r, d, g in _mos_drain_gate_pairs(rows)]

    def apply(self, rows, site):
        rows = copy.deepcopy(rows)
        d, g = site["drain"], site["gate"]
        mid = _fresh_net(rows, base="fb")
        # drain -> R -> mid -> C -> gate  (C on the gate side keeps DC block)
        rows.append(_mk_pas(_fresh_name(rows, "Rfb"), d, mid, R))
        rows.append(_mk_pas(_fresh_name(rows, "Cfb"), mid, g, C))
        return rows

    def describe(self, rows, site):
        return ("%s at %s: add a series R+C from %s drain (%s) to gate (%s); the "
                "C blocks DC so the gate bias is unchanged."
                % (self.name, site["mos"], site["mos"], site["drain"],
                   site["gate"]))


class AddSecondStageCS(Move):
    """Cap-couple the current output node into a NEW mirror-biased NMOS
    common-source stage with an L load; VOUT1 moves to the new stage output.

    Construction (all invariant-preserving):
      * a coupling C from the old output node -> new gate net (DC isolation);
      * the new NMOS gate is biased by the anchor mirror idiom (R rail -> diode ->
        R gate) so the gate has an in-topology DC bias (I3), NOT via a port;
      * NMOS drain = a new output-internal node, source = VSS;
      * an L load from VDD -> that drain node;
      * the OUTPUT DC-block cap's inner pin is rerouted to the new drain node, so
        VOUT1 now taps the new stage output (still through the DC-block cap)."""
    name = "add_second_stage_CS"
    _ADDS = 6      # coupling C + (R,diode,R bias) + CS NMOS + L load

    def applicable_sites(self, rows):
        out_node = _current_output_node(rows)
        # budget-aware (I4): this move adds 6 devices, so only offer the site when
        # the result stays within the ladder cap. A move never presents a site it
        # cannot legally apply.
        if not out_node or not _fits(rows, self._ADDS):
            return []
        return [{"out_node": out_node}]

    def apply(self, rows, site):
        rows = copy.deepcopy(rows)
        old_out = site["out_node"]
        g2 = _fresh_net(rows, base="g2")
        d2 = _fresh_net(rows, base="d2")
        # coupling cap: old output node -> new gate (blocks DC into the gate)
        rows.append(_mk_pas(_fresh_name(rows, "Ccpl"), old_out, g2, C))
        # mirror bias for the new gate (rail -> diode -> R -> gate)
        bias_rows, _mnode = _diode_bias_for_gate(rows, g2, rail="VDD", tag="S2")
        rows.extend(bias_rows)
        # the common-source device + its inductive load
        rows.append(_mk_mos(_fresh_name(rows, "NMs2"), d2, g2, "VSS", "VSS", NMOS))
        rows.append(_mk_pas(_fresh_name(rows, "Lld2"), "VDD", d2, L))
        # move VOUT1's DC-block cap to tap the new stage drain
        oc = _output_dcblock_cap(rows)
        cap_row = oc[0]
        for i in (_PP, _PN):
            if cap_row[i] == old_out:
                cap_row[i] = d2
        return rows

    def new_gates(self, rows, site):
        # the freshly-created common-source gate net -- deterministic recompute so
        # the invariant check knows which gate to require bias for.
        return (_fresh_net(rows, base="g2"),)

    def describe(self, rows, site):
        return ("%s: cap-couple current output node %s into a new mirror-biased "
                "NMOS common-source stage with an L load; VOUT1 moves to the new "
                "stage output." % (self.name, site["out_node"]))


class AddOutputShuntC(Move):
    """Add a shunt capacitor from the output internal node to VSS (before the
    DC-block cap, on the circuit side)."""
    name = "add_output_shunt_C"

    def applicable_sites(self, rows):
        oc = _output_dcblock_cap(rows)
        return [{"inner": oc[1]}] if (oc and _fits(rows, 1)) else []

    def apply(self, rows, site):
        rows = copy.deepcopy(rows)
        rows.append(_mk_pas(_fresh_name(rows, "Cout"), site["inner"], "VSS", C))
        return rows

    def describe(self, rows, site):
        return ("%s at output: add a shunt C from output internal node %s to VSS "
                "(circuit side of the DC-block cap)." % (self.name, site["inner"]))


class AddSeriesLOutput(Move):
    """Insert a series inductor into the output chain on the INTERNAL side of the
    DC-block cap."""
    name = "add_series_L_output"

    def applicable_sites(self, rows):
        oc = _output_dcblock_cap(rows)
        return [{"inner": oc[1]}] if (oc and _fits(rows, 1)) else []

    def apply(self, rows, site):
        rows = copy.deepcopy(rows)
        inner = site["inner"]
        mid = _fresh_net(rows, base="lo")
        oc = _output_dcblock_cap(rows)
        cap_row = oc[0]
        for i in (_PP, _PN):
            if cap_row[i] == inner:
                cap_row[i] = mid
        rows.append(_mk_pas(_fresh_name(rows, "Lout"), inner, mid, L))
        return rows

    def describe(self, rows, site):
        oc = _output_dcblock_cap(rows)
        return ("%s at output: insert a series L in the output chain on the "
                "internal side of DC-block cap %s (node %s)."
                % (self.name, _name(oc[0]), site["inner"]))


# ================================================================ registry
def all_moves():
    """The round-1 operator set (generic, composable, no class-specific macros)."""
    return [
        AddSeriesLInput(),
        AddShuntCInput(),
        AddLMatchSectionInput(),
        AddCascodeNMOS(),
        AddSourceDegenL(),
        AddShuntFeedbackRC(),
        AddSecondStageCS(),
        AddOutputShuntC(),
        AddSeriesLOutput(),
    ]


def enumerate_sites(rows, moves=None):
    """All applicable (move, site) pairs for `rows`, in a stable order (move
    registry order, then site discovery order). Returns a list of dicts:
      {move, name, site, describe}  -- the arm-M menu / arm-R sampling universe."""
    moves = moves or all_moves()
    out = []
    for mv in moves:
        for site in mv.applicable_sites(rows):
            out.append({"move": mv, "name": mv.name, "site": site,
                        "describe": mv.describe(rows, site)})
    return out


def apply_move(rows, entry):
    """Apply an enumerate_sites entry; return (new_rows, moved_gates)."""
    mv, site = entry["move"], entry["site"]
    new_rows = mv.apply(rows, site)
    return new_rows, tuple(mv.new_gates(rows, site))


# ================================================================ unit test
def _load_anchor_rows(anchor_path):
    txt = open(anchor_path, encoding="utf-8").read()
    rows, _ports = P.parse(txt)
    return rows


def _self_test():
    """Apply EVERY move at EVERY applicable site of BOTH anchor families
    (c1 via cap-e02, c3 via cap-m07); assert all four invariants; print counts."""
    lib = os.path.join(ROOT, "kaggle", "editcap-lib")
    anchors = {
        "c1 (cap-e02)": os.path.join(lib, "cap-e02-gpsband", "anchor.net"),
        "c3 (cap-m07)": os.path.join(lib, "cap-m07-gpsband", "anchor.net"),
    }
    n_total = 0
    n_pass = 0
    failures = []
    for fam, path in anchors.items():
        rows = _load_anchor_rows(path)
        entries = enumerate_sites(rows)
        print("\n=== anchor %s: %d devices, %d applicable (move,site) pairs ==="
              % (fam, len(rows), len(entries)))
        # per-move site counts
        by_move = {}
        for e in entries:
            by_move.setdefault(e["name"], 0)
            by_move[e["name"]] += 1
        for mv in all_moves():
            print("  %-26s sites=%d" % (mv.name, by_move.get(mv.name, 0)))
        # apply each and check invariants
        for e in entries:
            new_rows, moved_gates = apply_move(rows, e)
            ok, detail = check_invariants(rows, new_rows, moved_gates)
            n_total += 1
            if ok:
                n_pass += 1
            else:
                failures.append((fam, e["name"], e["site"], detail))
            status = "OK " if ok else "FAIL"
            print("    [%s] %-26s wl %s->%s ndev=%d  I1rt=%s I1wl=%s I2=%s "
                  "I3=%s I4=%s"
                  % (status, e["name"], (detail["wl_in"] or "?")[:8],
                     (detail["wl_out"] or "?")[:8], len(new_rows),
                     detail["I1_round_trip"], detail["I1_wl_distinct"],
                     detail["I2_port_gate"], detail["I3_new_gate_bias"],
                     detail["I4_budget"]))
    print("\n=== UNIT TEST SUMMARY: %d/%d applied moves preserve ALL invariants ==="
          % (n_pass, n_total))
    if failures:
        print("FAILURES:")
        for fam, name, site, detail in failures:
            print("  %s %s site=%s" % (fam, name, site))
            print("    detail=%s" % detail)
        return False
    print("all invariants hold on both anchor families.")
    return True


if __name__ == "__main__":
    ok = _self_test()
    sys.exit(0 if ok else 1)

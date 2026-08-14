"""WP-SEARCH rung-2 **stratum M** — 1-edit graph moves over token topologies.

plans2/03-SEARCH §2 puts rung-2's search in *graph* space: the LM seeds the
population, mutation and crossover work on the circuit, and tokens re-enter only
as the representation every individual must round-trip through. This module is
that move set.

**Genome = the `read_netlist` netlist** `[name, net1..netK (pin order), type]`
that `templates.py` already uses, because that is the one form the upstream
Eulerian pipeline consumes (`build_connection_matrix -> dfs_all_paths`) and the
one `templates.topo_to_netlist` reconstructs from a parsed `Topology`. So a
mutant is realized exactly like an archetype:

    netlist --emit_sequence--> tokens --Topology--> validity + L0 screen + WL hash

and the genome is then *re-derived from the realized topology*, so genotype and
phenotype can never drift apart (`realize()` returns the canonical netlist).

Moves are semantic where 03-SEARCH names them (load class, cascode, buffer,
degeneration, input-stage class, matching element) and blind where they are not
(passive type substitution, terminal rewire, element deletion). Every move is a
*structural* edit only — device values are ZOAF's job (05-SIZING), so nothing
here writes a W/L/R/C/L value.

Crossover is the archetype decomposition exchange of §2: cut both parents at a
signal-path stage boundary and splice head(A) + tail(B). Parents the decomposer
cannot cut are skipped, not forced.

    python lna/moves.py --selftest        # move-set smoke test over the archetypes
"""
import argparse
import glob
import os
import random
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FET_TYPES = ("nmos4", "pmos4")
PASSIVE_TYPES = ("resistor", "capacitor", "inductor")
FET_PINS = ("D", "G", "S", "B")
SUPPLY = ("VDD", "VSS")
PORTS = ("VIN1", "VOUT1")
PROTECTED = SUPPLY + PORTS


# ------------------------------------------------------------------ accessors
def dtype(e):
    return e[-1]


def dname(e):
    return e[0]


def dnets(e):
    return list(e[1:-1])


def is_fet(e):
    return e[-1] in FET_TYPES


def is_passive(e):
    return e[-1] in PASSIVE_TYPES


def fet_pins(e):
    """{'D':net,'G':net,'S':net,'B':net} for a 4-terminal FET entry."""
    return dict(zip(FET_PINS, e[1:5]))


def set_fet_pin(e, pin, net):
    e[1 + FET_PINS.index(pin)] = net


def nodes_of(nl):
    out = set()
    for e in nl:
        out.update(dnets(e))
    return out


def internal_nodes(nl):
    return sorted(n for n in nodes_of(nl) if n not in PROTECTED)


def n_inductors(nl):
    return sum(1 for e in nl if dtype(e) == "inductor")


def terminals_on(nl, node):
    """[(entry, pin_index)] for every device terminal sitting on `node`."""
    out = []
    for e in nl:
        for k, n in enumerate(dnets(e)):
            if n == node:
                out.append((e, k))
    return out


def degree(nl, node, ignore_bulk=True):
    """Terminal count on `node`; FET bulk pins are wiring, not signal, so they are
    ignored by default (every bulk is tied to VSS by construction)."""
    n = 0
    for e in nl:
        for k, net in enumerate(dnets(e)):
            if net != node:
                continue
            if ignore_bulk and is_fet(e) and k == 3:
                continue
            n += 1
    return n


def copy_nl(nl):
    return [list(e) for e in nl]


def fresh_node(nl, used=()):
    base = set(nodes_of(nl)) | set(used)
    i = 1
    while f"m{i}" in base:
        i += 1
    return f"m{i}"


def fresh_name(nl, stem):
    used = {dname(e) for e in nl}
    i = 1
    while f"{stem}{i}" in used:
        i += 1
    return f"{stem}{i}"


def retarget(nl, old, new, skip=()):
    """Move every terminal on `old` to `new`, except terminals in `skip`
    (list of (entry_id, pin_index))."""
    skip = {(id(e), k) for e, k in skip}
    for e in nl:
        for k, net in enumerate(dnets(e)):
            if net == old and (id(e), k) not in skip:
                e[1 + k] = new


def has_selfloop(nl):
    for e in nl:
        if is_passive(e) and e[1] == e[2]:
            return True
        if is_fet(e):
            p = fet_pins(e)
            if p["D"] == p["S"] or p["G"] == p["D"]:
                return True
    return False


def sane(nl, max_dev=16, min_dev=3):
    """Cheap structural sanity before the (slower) Eulerian realization."""
    if not (min_dev <= len(nl) <= max_dev):
        return False
    if has_selfloop(nl):
        return False
    ns = nodes_of(nl)
    for p in ("VDD", "VSS", "VIN1", "VOUT1"):
        if p not in ns:
            return False
    # every internal node needs >= 2 signal terminals or it is a dangling stub
    for n in internal_nodes(nl):
        if degree(nl, n) < 2:
            return False
    if not any(is_fet(e) for e in nl):
        return False
    names = [dname(e) for e in nl]
    if len(set(names)) != len(names):
        return False
    return True


# ------------------------------------------------------- structural detectors
def load_devices(nl, d):
    """The 2-terminal devices sitting directly between node `d` and VDD."""
    return [e for e in nl if is_passive(e) and set(dnets(e)) == {d, "VDD"}]


def is_cascode(nl, e):
    """A FET acting as a cascode: gate on VDD (AC-ground) and source on another
    FET's drain."""
    if not is_fet(e):
        return False
    p = fet_pins(e)
    if p["G"] != "VDD":
        return False
    return any(is_fet(o) and o is not e and fet_pins(o)["D"] == p["S"] for o in nl)


def buffer_parts(nl):
    """(fet, tail, coupler) of a source-follower output buffer, or None.
    Signature: drain on VDD, source node carries exactly one device to VSS and
    one device to VOUT1."""
    for e in nl:
        if not is_fet(e):
            continue
        p = fet_pins(e)
        if p["D"] != "VDD":
            continue
        s = p["S"]
        others = [o for o in nl if o is not e and s in dnets(o)]
        tail = [o for o in others if is_passive(o) and set(dnets(o)) == {s, "VSS"}]
        coup = [o for o in others if is_passive(o) and set(dnets(o)) == {s, "VOUT1"}]
        if len(others) == len(tail) + len(coup) and tail and coup:
            return e, tail[0], coup[0]
    return None


def output_coupler(nl):
    """The 2-terminal device that drives VOUT1 (and the node on its far side)."""
    cands = [e for e in nl if is_passive(e) and "VOUT1" in dnets(e)]
    if len(cands) != 1:
        return None, None
    e = cands[0]
    far = [n for n in dnets(e) if n != "VOUT1"]
    return (e, far[0]) if far else (None, None)


def input_node(nl):
    """The first internal node the input port reaches through one 2-terminal
    device (the post-DC-block signal node), plus that device."""
    cands = [e for e in nl if is_passive(e) and "VIN1" in dnets(e)]
    if len(cands) != 1:
        return None, None
    e = cands[0]
    far = [n for n in dnets(e) if n != "VIN1"]
    return (e, far[0]) if far else (None, None)


# ------------------------------------------------------------------- the moves
# Each move takes (nl, rng, ctx) and returns a NEW netlist or None if it does not
# apply. ctx carries the spec-derived structural budget so a move never proposes
# something the L0 screen must then throw away (max_inductors especially: the
# wideband spec allows exactly one).

def m_load_swap(nl, rng, ctx):
    """Swap a load class: R <-> LC tank <-> shunt-peaked R+L (03-SEARCH §2)."""
    nl = copy_nl(nl)
    drains = []
    for e in nl:
        if not is_fet(e):
            continue
        d = fet_pins(e)["D"]
        if d in PROTECTED:
            continue
        if load_devices(nl, d):
            drains.append(d)
    if not drains:
        return None
    d = rng.choice(sorted(set(drains)))
    old = load_devices(nl, d)
    n_ind_after = n_inductors(nl) - sum(1 for e in old if dtype(e) == "inductor")
    kinds = ["R", "tank", "shunt_peak"]
    rng.shuffle(kinds)
    for kind in kinds:
        need = {"R": 0, "tank": 1, "shunt_peak": 1}[kind]
        if n_ind_after + need > ctx["max_inductors"]:
            continue
        out = [e for e in nl if e not in old]
        if kind == "R":
            out.append([fresh_name(out, "RL"), "VDD", d, "resistor"])
        elif kind == "tank":
            out.append([fresh_name(out, "Ld"), "VDD", d, "inductor"])
            out.append([fresh_name(out, "Ct"), "VDD", d, "capacitor"])
        else:
            p = fresh_node(out)
            out.append([fresh_name(out, "RL"), "VDD", p, "resistor"])
            out.append([fresh_name(out, "Lpk"), p, d, "inductor"])
        if len(out) == len(nl) and all(sorted(map(str, a)) == sorted(map(str, b))
                                       for a, b in zip(out, nl)):
            continue
        return out
    return None


def m_cascode_add(nl, rng, ctx):
    """Stack a cascode device on a gain FET's drain."""
    nl = copy_nl(nl)
    cands = [e for e in nl if is_fet(e) and not is_cascode(nl, e)
             and fet_pins(e)["D"] not in PROTECTED
             and fet_pins(e)["G"] != "VDD"]
    if not cands or len(nl) + 1 > ctx["max_dev"]:
        return None
    f = rng.choice(cands)
    d = fet_pins(f)["D"]
    d2 = fresh_node(nl)
    keep = [(f, FET_PINS.index("D"))]
    retarget(nl, d, d2, skip=keep)
    nl.append([fresh_name(nl, "Mc"), d2, "VDD", d, "VSS", "nmos4"])
    return nl


def m_cascode_remove(nl, rng, ctx):
    nl = copy_nl(nl)
    cands = [e for e in nl if is_cascode(nl, e)]
    if not cands:
        return None
    c = rng.choice(cands)
    p = fet_pins(c)
    out = [e for e in nl if e is not c]
    if p["D"] in PROTECTED:
        retarget(out, p["S"], p["D"])
    else:
        retarget(out, p["D"], p["S"])
    return out


def m_buffer_add(nl, rng, ctx):
    """Insert a source-follower output buffer in front of VOUT1."""
    if buffer_parts(nl) or len(nl) + 3 > ctx["max_dev"]:
        return None
    nl = copy_nl(nl)
    o = fresh_node(nl)
    retarget(nl, "VOUT1", o)
    src = fresh_node(nl, used=[o])
    nl.append([fresh_name(nl, "Mb"), "VDD", o, src, "VSS", "nmos4"])
    nl.append([fresh_name(nl, "Rb"), src, "VSS", "resistor"])
    nl.append([fresh_name(nl, "Cob"), src, "VOUT1", "capacitor"])
    return nl


def m_buffer_remove(nl, rng, ctx):
    parts = buffer_parts(nl)
    if not parts:
        return None
    fet, tail, coup = parts
    g = fet_pins(fet)["G"]
    out = [list(e) for e in nl if e not in (fet, tail, coup)]
    if g in PROTECTED:
        return None
    retarget(out, g, "VOUT1")
    return out


def m_degen_add(nl, rng, ctx):
    """Add source degeneration (Ls or Rs) under a grounded-source FET."""
    cands = [e for e in nl if is_fet(e) and fet_pins(e)["S"] == "VSS"
             and fet_pins(e)["D"] != "VDD"]
    if not cands or len(nl) + 1 > ctx["max_dev"]:
        return None
    nl = copy_nl(nl)
    cands = [e for e in nl if is_fet(e) and fet_pins(e)["S"] == "VSS"
             and fet_pins(e)["D"] != "VDD"]
    f = rng.choice(cands)
    s = fresh_node(nl)
    set_fet_pin(f, "S", s)
    kinds = ["resistor"]
    if n_inductors(nl) + 1 <= ctx["max_inductors"]:
        kinds.append("inductor")
    nl.append([fresh_name(nl, "Ldg"), s, "VSS", rng.choice(kinds)])
    return nl


def m_degen_remove(nl, rng, ctx):
    cands = []
    for e in nl:
        if not is_passive(e) or "VSS" not in dnets(e):
            continue
        s = [n for n in dnets(e) if n != "VSS"]
        if not s or s[0] in PROTECTED:
            continue
        s = s[0]
        if degree(nl, s) != 2:
            continue
        if any(is_fet(o) and fet_pins(o)["S"] == s for o in nl):
            cands.append((e, s))
    if not cands:
        return None
    e, s = rng.choice(cands)
    out = [list(x) for x in nl if x is not e]
    retarget(out, s, "VSS")
    return out


def m_stage_add(nl, rng, ctx):
    """Append an AC-coupled common-source gain stage before the output."""
    coup, d = output_coupler(nl)
    if coup is None or len(nl) + 3 > ctx["max_dev"]:
        return None
    nl = copy_nl(nl)
    coup = next(e for e in nl if dname(e) == dname(coup))
    g = fresh_node(nl)
    d2 = fresh_node(nl, used=[g])
    nl.append([fresh_name(nl, "Cs"), d, g, "capacitor"])
    nl.append([fresh_name(nl, "Ms"), d2, g, "VSS", "VSS", "nmos4"])
    if n_inductors(nl) + 1 <= ctx["max_inductors"] and rng.random() < 0.5:
        nl.append([fresh_name(nl, "Lds"), "VDD", d2, "inductor"])
    else:
        nl.append([fresh_name(nl, "RLs"), "VDD", d2, "resistor"])
    for k, n in enumerate(dnets(coup)):
        if n == d:
            coup[1 + k] = d2
    return nl


def m_stage_remove(nl, rng, ctx):
    """Drop the last AC-coupled CS stage (its FET, coupling cap and load)."""
    coup, d2 = output_coupler(nl)
    if coup is None:
        return None
    fets = [e for e in nl if is_fet(e) and fet_pins(e)["D"] == d2
            and fet_pins(e)["S"] == "VSS"]
    if len(fets) != 1:
        return None
    f = fets[0]
    g = fet_pins(f)["G"]
    if g in PROTECTED or degree(nl, g) != 2:
        return None
    cs = [e for e in nl if is_passive(e) and g in dnets(e)]
    if len(cs) != 1:
        return None
    cs = cs[0]
    prev = [n for n in dnets(cs) if n != g]
    if not prev:
        return None
    prev = prev[0]
    load = load_devices(nl, d2)
    drop = {id(x) for x in [f, cs] + load}
    out = [list(x) for x in nl if id(x) not in drop]
    if not out:
        return None
    retarget(out, d2, prev)
    return out


def m_feedback_add(nl, rng, ctx):
    """Add a shunt-feedback resistor drain->gate around a gain FET (the
    broadband-match element)."""
    if len(nl) + 1 > ctx["max_dev"]:
        return None
    cands = []
    for e in nl:
        if not is_fet(e):
            continue
        p = fet_pins(e)
        if p["G"] in SUPPLY or p["D"] in SUPPLY:
            continue
        if any(is_passive(o) and set(dnets(o)) == {p["D"], p["G"]} for o in nl):
            continue
        cands.append((p["D"], p["G"]))
    if not cands:
        return None
    d, g = rng.choice(cands)
    nl = copy_nl(nl)
    nl.append([fresh_name(nl, "Rf"), d, g, "resistor"])
    return nl


def m_feedback_remove(nl, rng, ctx):
    pairs = {(fet_pins(e)["D"], fet_pins(e)["G"]) for e in nl if is_fet(e)}
    cands = [e for e in nl if is_passive(e)
             and (tuple(dnets(e)) in pairs or tuple(reversed(dnets(e))) in pairs)]
    if not cands:
        return None
    e = rng.choice(cands)
    return [list(x) for x in nl if x is not e]


def m_match_elem_add(nl, rng, ctx):
    """Add an input matching element: a series L/R in the gate path, or a shunt
    C-divider leg off the input node."""
    coup, x = input_node(nl)
    if coup is None or len(nl) + 1 > ctx["max_dev"]:
        return None
    nl = copy_nl(nl)
    coup = next(e for e in nl if dname(e) == dname(coup))
    if rng.random() < 0.5:                       # series element after the DC block
        mid = fresh_node(nl)
        for k, n in enumerate(dnets(coup)):
            if n == x:
                coup[1 + k] = mid
        kinds = ["resistor"]
        if n_inductors(nl) + 1 <= ctx["max_inductors"]:
            kinds.append("inductor")
        nl.append([fresh_name(nl, "Lg"), mid, x, rng.choice(kinds)])
    else:                                        # shunt leg to VSS (C-divider)
        nl.append([fresh_name(nl, "Cx"), x, "VSS", "capacitor"])
    return nl


def m_input_class_swap(nl, rng, ctx):
    """Swap the input stage class: common-source (signal on a gate) <-> common-gate
    (signal on a source, gate AC-grounded and biased by bias.py's R-GATE)."""
    coup, x = input_node(nl)
    if coup is None or x in PROTECTED:
        return None
    gates = [e for e in nl if is_fet(e) and fet_pins(e)["G"] == x]
    sources = [e for e in nl if is_fet(e) and fet_pins(e)["S"] == x]
    nl = copy_nl(nl)
    if gates and not sources:                    # CS -> CG
        if len(nl) + 2 > ctx["max_dev"]:
            return None
        f = next(e for e in nl if dname(e) == dname(gates[0]))
        old_s = fet_pins(f)["S"]
        g = fresh_node(nl)
        set_fet_pin(f, "G", g)
        set_fet_pin(f, "S", x)
        nl.append([fresh_name(nl, "Cbg"), g, "VSS", "capacitor"])
        if old_s not in PROTECTED and degree(nl, old_s) == 0:
            pass
        kinds = ["resistor"]
        if n_inductors(nl) + 1 <= ctx["max_inductors"]:
            kinds.append("inductor")
        nl.append([fresh_name(nl, "Lin"), x, "VSS", rng.choice(kinds)])
        return nl
    if sources and not gates:                    # CG -> CS
        f = next(e for e in nl if dname(e) == dname(sources[0]))
        g = fet_pins(f)["G"]
        set_fet_pin(f, "G", x)
        set_fet_pin(f, "S", "VSS")
        out = nl
        if g not in PROTECTED and degree(out, g) <= 1:
            out = [e for e in out if g not in dnets(e)]
        return out
    return None


def m_passive_type_swap(nl, rng, ctx):
    """Substitute a passive's device class (R/C/L) — the blind type edit."""
    cands = [e for e in nl if is_passive(e)]
    if not cands:
        return None
    nl = copy_nl(nl)
    cands = [e for e in nl if is_passive(e)]
    e = rng.choice(cands)
    opts = [t for t in PASSIVE_TYPES if t != dtype(e)]
    if dtype(e) != "inductor":
        n_after = n_inductors(nl) + 1
        if n_after > ctx["max_inductors"]:
            opts = [t for t in opts if t != "inductor"]
    if not opts:
        return None
    e[-1] = rng.choice(opts)
    return nl


def m_rewire(nl, rng, ctx):
    """Move one terminal of a passive to a different existing node."""
    cands = [e for e in nl if is_passive(e)]
    if not cands:
        return None
    nl = copy_nl(nl)
    cands = [e for e in nl if is_passive(e)]
    e = rng.choice(cands)
    k = rng.randrange(2)
    other = dnets(e)[1 - k]
    pool = [n for n in nodes_of(nl) if n != other and n != dnets(e)[k]
            and n != "VIN1"]
    if not pool:
        return None
    e[1 + k] = rng.choice(sorted(pool))
    return nl


def m_device_remove(nl, rng, ctx):
    """Delete a passive, shorting its two nodes (element removal)."""
    cands = []
    for e in nl:
        if not is_passive(e):
            continue
        a, b = dnets(e)
        if a in PROTECTED and b in PROTECTED:
            continue                             # would short two rails/ports
        cands.append(e)
    if not cands or len(nl) - 1 < ctx["min_dev"]:
        return None
    e = rng.choice(cands)
    a, b = dnets(e)
    out = [list(x) for x in nl if x is not e]
    if a in PROTECTED:
        retarget(out, b, a)
    else:
        retarget(out, a, b)
    return out


def m_aux_path_add(nl, rng, ctx):
    """Add a second signal path from the input node onto an existing summing node
    (the noise-cancelling / feedforward edit)."""
    coup, x = input_node(nl)
    if coup is None or len(nl) + 2 > ctx["max_dev"]:
        return None
    sums = sorted({fet_pins(e)["D"] for e in nl if is_fet(e)
                   if fet_pins(e)["D"] not in SUPPLY and fet_pins(e)["D"] != x})
    if not sums:
        return None
    y = rng.choice(sums)
    nl = copy_nl(nl)
    ga = fresh_node(nl)
    nl.append([fresh_name(nl, "Cab"), x, ga, "capacitor"])
    nl.append([fresh_name(nl, "Ma"), y, ga, "VSS", "VSS", "nmos4"])
    return nl


MOVES = [
    ("load_swap", m_load_swap, 1.6),
    ("cascode_add", m_cascode_add, 0.8),
    ("cascode_remove", m_cascode_remove, 0.5),
    ("buffer_add", m_buffer_add, 0.7),
    ("buffer_remove", m_buffer_remove, 0.4),
    ("degen_add", m_degen_add, 0.8),
    ("degen_remove", m_degen_remove, 0.5),
    ("stage_add", m_stage_add, 1.2),
    ("stage_remove", m_stage_remove, 0.7),
    ("feedback_add", m_feedback_add, 1.2),
    ("feedback_remove", m_feedback_remove, 0.5),
    ("match_elem_add", m_match_elem_add, 1.0),
    ("input_class_swap", m_input_class_swap, 1.0),
    ("passive_type_swap", m_passive_type_swap, 1.2),
    ("rewire", m_rewire, 1.0),
    ("device_remove", m_device_remove, 0.8),
    ("aux_path_add", m_aux_path_add, 1.0),
]
MOVE_NAMES = [m[0] for m in MOVES]


def mutate(nl, rng, ctx, tries=8):
    """One structural edit. Returns (new_netlist, move_name) or (None, None)."""
    names = [m[0] for m in MOVES]
    weights = [m[2] for m in MOVES]
    fns = {m[0]: m[1] for m in MOVES}
    for _ in range(tries):
        name = rng.choices(names, weights=weights, k=1)[0]
        try:
            out = fns[name](nl, rng, ctx)
        except Exception:
            out = None
        if out and sane(out, ctx["max_dev"], ctx["min_dev"]):
            return out, name
    return None, None


# ------------------------------------------------------------------ crossover
def stage_cuts(nl):
    """Signal-path stage boundaries a decomposition crossover can cut at.

    A boundary is an AC/DC coupling 2-terminal device whose far side feeds a FET
    gate and whose near side is a FET drain — i.e. exactly the interstage coupler
    `templates._tuned_chain` emits, and the same seam `templates.py`'s archetype
    decomposition (input stage | gain chain | load | buffer) uses. Returns a list
    of (coupler_entry, upstream_node, downstream_node)."""
    cuts = []
    drains = {fet_pins(e)["D"] for e in nl if is_fet(e)}
    gates = {fet_pins(e)["G"] for e in nl if is_fet(e)}
    for e in nl:
        if not is_passive(e):
            continue
        a, b = dnets(e)
        for up, dn in ((a, b), (b, a)):
            if up in drains and dn in gates and up not in SUPPLY and dn not in SUPPLY:
                cuts.append((e, up, dn))
    return cuts


def _reachable(nl, seeds, stop=()):
    """Nodes reachable from `seeds` through devices, not crossing `stop` nodes.
    Rails/ports are traversal sinks (never expanded) so the two halves of a cut
    do not leak into each other through VDD/VSS."""
    seen = set(seeds)
    frontier = list(seeds)
    while frontier:
        n = frontier.pop()
        if n in PROTECTED or n in stop:
            continue
        for e in nl:
            if n not in dnets(e):
                continue
            for m in dnets(e):
                if m not in seen:
                    seen.add(m)
                    frontier.append(m)
    return seen


def _half(nl, keep_nodes, cut_dev):
    """Devices all of whose non-rail nodes lie in `keep_nodes` (excluding the
    coupler that defines the cut)."""
    out = []
    for e in nl:
        if e is cut_dev:
            continue
        ns = [n for n in dnets(e) if n not in PROTECTED]
        if all(n in keep_nodes for n in ns):
            out.append(list(e))
    return out


def _rename(nl, tag):
    out = []
    for e in nl:
        e = list(e)
        e[0] = f"{tag}{e[0]}"
        for k, n in enumerate(dnets(e)):
            if n not in PROTECTED:
                e[1 + k] = f"{tag}{n}"
        out.append(e)
    return out


def crossover(a, b, rng, ctx):
    """Exchange whole stages at the decomposition boundary (03-SEARCH §2).

    head(A) = everything upstream of A's cut (its input stage + earlier gain),
    tail(B) = everything downstream of B's cut (its later gain + load + buffer),
    rejoined by a fresh coupling capacitor. Undefined for parents with no cut —
    those are skipped, never forced."""
    ca, cb = stage_cuts(a), stage_cuts(b)
    if not ca or not cb:
        return None
    for _ in range(6):
        ea, upa, dna = rng.choice(ca)
        eb, upb, dnb = rng.choice(cb)
        head_nodes = _reachable(a, [upa], stop={dna})
        if "VOUT1" in head_nodes and upa != "VOUT1":
            head_nodes.discard("VOUT1")
        head = _half(a, head_nodes | set(PROTECTED), ea)
        head = [e for e in head if "VOUT1" not in dnets(e)]
        tail_nodes = _reachable(b, [dnb], stop={upb})
        tail = _half(b, tail_nodes | set(PROTECTED), eb)
        tail = [e for e in tail if "VIN1" not in dnets(e)]
        if not head or not tail:
            continue
        tail = _rename(tail, "x")
        dnb_r = f"x{dnb}" if dnb not in PROTECTED else dnb
        out = head + tail
        if not any("VOUT1" in dnets(e) for e in out):
            continue
        if not any("VIN1" in dnets(e) for e in out):
            continue
        out.append([fresh_name(out, "Cxo"), upa, dnb_r, "capacitor"])
        if n_inductors(out) > ctx["max_inductors"]:
            continue
        if sane(out, ctx["max_dev"], ctx["min_dev"]):
            return out
    return None


# ------------------------------------------------------------------ realization
def private_tmp(root):
    """Point this PROCESS's `tempfile` at `root`.

    Every ngspice caller in the tree (`bias.run_op`, `extract.run_and_extract`,
    `templates.emit_paths`) mkdtemp's per call and none of them clean up. A
    rung-2 night is ~10^4 of those, and the shared `%TEMP%` was already carrying
    16k+ `bias_*` directories from earlier sessions — enough that merely listing
    it takes minutes. Redirecting `tempfile.tempdir` keeps the litter inside the
    run's own output dir (gitignored under `lna/out/_*`) where `sweep_tmp` can
    wipe it wholesale, and leaves the shared temp alone."""
    root = os.path.abspath(root)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root, exist_ok=True)
    tempfile.tempdir = root
    return root


def sweep_tmp(root=None):
    """Delete the per-call scratch dirs accumulated since the last sweep."""
    n = 0
    pats = ([os.path.join(root, "*")] if root else
            [os.path.join(tempfile.gettempdir(), p + "*")
             for p in ("tmpl_", "bias_", "stab_")])
    for pat in pats:
        for d in glob.glob(pat):
            try:
                shutil.rmtree(d) if os.path.isdir(d) else os.remove(d)
                n += 1
            except OSError:
                pass
    return n


def realize(nl, spec, wl_cache=None):
    """netlist -> (topo, tokens, wl_hash, canonical_netlist) or None.

    The full round trip 03-SEARCH §2 demands: Eulerian token emission, token
    re-parse, `Topology.valid`, the spec's L0 screen (which carries the
    floating-subcircuit detector and the device/inductor budget), then the
    genome re-derived from the realized graph so genotype == phenotype."""
    import templates as T
    from topology import Topology
    from novelty import wl_features
    # ImportError is NOT a no-path outcome: it means a dependency or pipeline
    # module (templates/novelty, which pull in AnalogGenie + pandas lazily)
    # failed to load, which once silently disabled realize() for a whole port
    # era. Let it -- and only it -- propagate loudly; every other exception
    # below is a legitimate "this candidate has no realization" and returns None.
    try:
        seq = T.emit_sequence(nl)
    except ImportError:
        raise
    except Exception:
        return None
    if not seq:
        return None
    try:
        topo = Topology(seq)
    except ImportError:
        raise
    except Exception:
        return None
    if not topo.valid:
        return None
    try:
        ok, _ = spec.structural_screen(topo)
    except ImportError:
        raise
    except Exception:
        return None
    if not ok:
        return None
    canon, _ports = T.topo_to_netlist(topo)
    if canon is None:
        return None
    return topo, seq, wl_features(topo)[0], canon


# ------------------------------------------------------------------ selftest
def _selftest(spec_name="wideband-sdr", n=400, seed=7):
    import templates as T
    from spec import Spec
    spec = Spec.load(spec_name)
    ctx = {"max_dev": spec.topology.get("device_budget", [3, 16])[1],
           "min_dev": spec.topology.get("device_budget", [3, 16])[0],
           "max_inductors": spec.topology.get("max_inductors", 99)}
    rng = random.Random(seed)
    seeds = []
    for a in T.archetypes():
        from topology import Topology
        topo = Topology(a["seq"])
        if spec.structural_screen(topo)[0]:
            nlx, _ = T.topo_to_netlist(topo)
            if nlx:
                seeds.append((a["name"], nlx))
    print(f"{len(seeds)} archetypes pass the {spec_name} screen")
    from collections import Counter
    tried, ok = Counter(), Counter()
    hashes = set()
    for i in range(n):
        _, nl = seeds[rng.randrange(len(seeds))]
        mut, mv = mutate(nl, rng, ctx)
        if mv is None:
            continue
        tried[mv] += 1
        r = realize(mut, spec)
        if r:
            ok[mv] += 1
            hashes.add(r[2])
    print(f"{'move':<20} {'proposed':>9} {'realized':>9} {'yield':>7}")
    for mv in MOVE_NAMES:
        if tried[mv]:
            print(f"{mv:<20} {tried[mv]:>9} {ok[mv]:>9} "
                  f"{ok[mv]/tried[mv]:>7.2f}")
    print(f"TOTAL {sum(tried.values())} proposed, {sum(ok.values())} realized, "
          f"{len(hashes)} distinct WL hashes")
    # crossover
    cx_ok = 0
    for i in range(60):
        _, a = seeds[rng.randrange(len(seeds))]
        _, b = seeds[rng.randrange(len(seeds))]
        c = crossover(a, b, rng, ctx)
        if c and realize(c, spec):
            cx_ok += 1
    print(f"crossover: {cx_ok}/60 realized")
    sweep_tmp()
    return 0


def main():
    ap = argparse.ArgumentParser(description="stratum-M move set")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--spec", default="wideband-sdr")
    ap.add_argument("--n", type=int, default=400)
    args = ap.parse_args()
    if args.selftest:
        return _selftest(args.spec, args.n)
    ap.error("give --selftest")


if __name__ == "__main__":
    sys.exit(main())

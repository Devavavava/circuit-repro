"""engineer/g2_moves.py -- the E-7 (rung G2) PRIMITIVE move repertoire.

This is the *executor-side* implementation of the move set the user RULED on in
`engineer/E7-MOVES.md` (`## Rulings (user, 2026-08-20)`):

    ruled set = P1, P2, P3, P4, P5, P7, plus atomic add_and_connect_device
    P6 (duplicate_branch_with_complement) is REJECTED and is NOT implemented here.
    Intermediates must stay L0-legal (no transient-illegal multi-edit steps).

It EXTENDS `lna/moves.py`: it imports lna's netlist accessors, its `sane()` L0
gate, its `realize()` token round-trip and its `Spec.structural_screen` L0 screen
READ-ONLY, and never writes under `lna/` (the two-line branch law -- the engineer
branch imports lna read-only). The genome is the same `read_netlist` netlist
`lna/moves.py` uses: `[name, net1..netK, type]`, FET pin order D,G,S,B.

Every primitive here is a GENERIC, COMPOSABLE graph edit (nudge policy §0): it
names a device *type* and/or a *terminal map*, never a circuit motif. The three
macros X1-X3 (`add_class_ab_output_stage`, `add_push_pull_pair`,
`apply_balun_motif`) are NOT implemented -- their absence is the point.

Determinism: every primitive takes an `rng` (a `random.Random`) and makes all its
stochastic choices through it, over SORTED candidate lists, so a fixed seed gives
a fixed edit. `mutate()` and `mutate_filtered()` mirror `lna.moves.mutate`.

    python engineer/g2_moves.py --selftest      # unit tests on the flagship graph
"""
import argparse
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
LNA = os.path.join(ROOT, "lna")
if LNA not in sys.path:
    sys.path.insert(0, LNA)

# READ-ONLY imports of the lna move machinery we extend.
import moves as M                       # noqa: E402
from moves import (copy_nl, dnets, dtype, dname, is_fet, is_passive,  # noqa: E402
                   fet_pins, set_fet_pin, nodes_of, internal_nodes,
                   n_inductors, degree, fresh_node, fresh_name, sane,
                   FET_TYPES, PASSIVE_TYPES, PROTECTED, SUPPLY, PORTS, FET_PINS)

DEVICE_TYPES = FET_TYPES + PASSIVE_TYPES          # {nmos4,pmos4,resistor,capacitor,inductor}


# --------------------------------------------------------------- small helpers
def _passive_stem(t):
    return {"resistor": "R", "capacitor": "C", "inductor": "L"}.get(t, "X")


def _dev_stem(t):
    return {"nmos4": "MN", "pmos4": "MP"}.get(t, _passive_stem(t))


def _new_device(nl, t, nets):
    """A fresh netlist entry of type `t` on `nets` (2 for a passive, 4 for a FET),
    with a name unique in `nl`. Pin order for a FET is D,G,S,B."""
    return [fresh_name(nl, _dev_stem(t))] + list(nets) + [t]


def _inductor_room(nl, ctx, adding_inductor):
    if not adding_inductor:
        return True
    return n_inductors(nl) + 1 <= ctx["max_inductors"]


def real_nodes(nl, extra_exclude=()):
    """Existing electrical nodes a new terminal may legally attach to: every node
    already present, sorted for determinism, minus any excluded."""
    ex = set(extra_exclude)
    return sorted(n for n in nodes_of(nl) if n not in ex)


# ============================================================ the primitives
# Each primitive: (nl, rng, ctx) -> NEW netlist (a copy) or None if it does not
# apply. NONE OF THEM mutate the input `nl`. Every returned netlist is intended to
# pass `sane()`; `mutate()` re-checks `sane()` as the final gate, exactly as
# `lna.moves.mutate` does, so an L0-illegal proposal is dropped, never returned.

def p1_add_device_of_type(nl, rng, ctx, t=None):
    """P1 -- append one device of a chosen type onto EXISTING nodes.

    Generalizes the NMOS-only adders (`m_cascode_add`/`m_stage_add` hardcode
    nmos4) to any type in {nmos4, pmos4, resistor, capacitor, inductor}. To keep
    the L0 `sane` screen satisfied WITHOUT a transient-illegal intermediate (the
    ruling forbids those), the device is wired to existing nodes at birth: a
    passive between two distinct existing non-identical nodes, a FET onto four
    existing nodes (bulk forced to VSS by construction, gate/drain/source chosen
    from existing nodes) -- so no new dangling stub is created. This is the
    "add onto existing nodes" reading of P1; fresh-node creation is P3's job."""
    if len(nl) + 1 > ctx["max_dev"]:
        return None
    nl = copy_nl(nl)
    types = [t] if t else list(DEVICE_TYPES)
    rng.shuffle(types)
    for typ in types:
        if not _inductor_room(nl, ctx, typ == "inductor"):
            continue
        if typ in PASSIVE_TYPES:
            pool = real_nodes(nl)
            if len(pool) < 2:
                continue
            a, b = rng.sample(pool, 2)               # distinct -> no self-loop
            return nl + [_new_device(nl, typ, [a, b])]
        else:  # a FET onto existing nodes; bulk=VSS by construction
            pool = real_nodes(nl)
            if len(pool) < 2:
                continue
            d = rng.choice(pool)
            g = rng.choice(pool)
            s = rng.choice([n for n in pool if n != d])   # D!=S (no D-S selfloop)
            if g == d:                                    # no G-D selfloop
                continue
            return nl + [_new_device(nl, typ, [d, g, s, "VSS"])]
    return None


def p2_fet_polarity_swap(nl, rng, ctx, target=None):
    """P2 -- flip one existing FET's type nmos4 <-> pmos4, terminals in place.

    The FET analogue of `passive_type_swap`; the L0 screen then judges bias
    legality. `target` (a device name) pins the choice for unit tests."""
    cands = sorted((e for e in nl if is_fet(e)), key=dname)
    if target is not None:
        cands = [e for e in cands if dname(e) == target]
    if not cands:
        return None
    nl = copy_nl(nl)
    cands = sorted((e for e in nl if is_fet(e)
                    and (target is None or dname(e) == target)), key=dname)
    e = rng.choice(cands)
    e[-1] = "pmos4" if dtype(e) == "nmos4" else "nmos4"
    return nl


def p3_split_net(nl, rng, ctx, node=None, k_move=None):
    """P3 -- split node `n` into `n, n'`, moving a chosen non-empty proper subset
    of terminals to n'. Creates the extra node a second device needs to attach to.

    To keep BOTH halves L0-legal (every internal node needs degree >= 2), the
    split only fires on a node of degree >= 4 and moves a subset of size in
    [2, deg-2], so neither side is left with a single terminal. A fresh device is
    NOT added here (that is P1/P4/P5/add_and_connect) -- P3 is purely the
    topological refinement that makes room. Rails/ports are never split."""
    cand_nodes = sorted(n for n in internal_nodes(nl) if degree(nl, n) >= 4)
    if node is not None:
        cand_nodes = [n for n in cand_nodes if n == node]
    if not cand_nodes:
        return None
    n = node if node in cand_nodes else rng.choice(cand_nodes)
    # terminals on n, counting SIGNAL terminals (bulk ignored, matching degree()).
    terms = []                                    # (entry_id, pin_index)
    for e in nl:
        for ki, net in enumerate(dnets(e)):
            if net != n:
                continue
            if is_fet(e) and ki == 3:             # bulk pin: wiring, leave on n
                continue
            terms.append((id(e), ki))
    d = len(terms)
    if d < 4:
        return None
    lo, hi = 2, d - 2
    size = k_move if (k_move is not None and lo <= k_move <= hi) else rng.randint(lo, hi)
    move = set(rng.sample(range(d), size))
    nn = fresh_node(nl)
    out = copy_nl(nl)
    # re-find terminal positions in the copy by (name, pin_index)
    id_to_name = {id(e): dname(e) for e in nl}
    move_np = {(id_to_name[eid], ki) for j, (eid, ki) in enumerate(terms) if j in move}
    for e in out:
        for ki, net in enumerate(dnets(e)):
            if net == n and (dname(e), ki) in move_np:
                e[1 + ki] = nn
    return out


def p4_insert_series_element(nl, rng, ctx, dev=None, pin=None, t=None):
    """P4 -- break one existing 2-terminal connection and insert a series device
    of type `t` at a fresh node.

    Picks a device terminal sitting on a node, moves that terminal to a fresh
    node, and bridges fresh-node<->old-node with a new 2-terminal device. The old
    node keeps degree (the series element replaces the direct tie), and the fresh
    node has degree 2 (the moved terminal + the new element) -- both L0-legal.
    A passive terminal on a protected rail/port is preferred so the series element
    lands in a signal path, not across a device pin pair that must stay shorted."""
    # candidate terminals: any device terminal on a non-protected node with the
    # node's degree >= 2 (so after the move the old node keeps degree >= 2).
    cands = []
    for e in nl:
        nets = dnets(e)
        for ki, net in enumerate(nets):
            if is_fet(e) and ki == 3:                  # never series a bulk tie
                continue
            if net in PROTECTED:
                continue
            if degree(nl, net) < 3:                    # old node must survive with >=2
                continue
            cands.append((dname(e), ki, net))
    cands.sort()
    if dev is not None:
        cands = [c for c in cands if c[0] == dev and (pin is None or c[1] == pin)]
    if not cands or len(nl) + 1 > ctx["max_dev"]:
        return None
    name, ki, old = rng.choice(cands)
    types = [t] if t else [x for x in PASSIVE_TYPES]
    rng.shuffle(types)
    for typ in types:
        if not _inductor_room(nl, ctx, typ == "inductor"):
            continue
        out = copy_nl(nl)
        e = next(x for x in out if dname(x) == name)
        mid = fresh_node(out)
        e[1 + ki] = mid
        out.append(_new_device(out, typ, [mid, old]))
        return out
    return None


def p5_insert_parallel_element(nl, rng, ctx, dev=None, t=None):
    """P5 -- add a device of type `t` in parallel with an existing 2-terminal
    device (same two nodes). A generic branch addition; no new node, so both
    endpoints keep >= their old degree -- always L0-legal on that count."""
    cands = sorted((e for e in nl if is_passive(e)), key=dname)
    if dev is not None:
        cands = [e for e in cands if dname(e) == dev]
    if not cands or len(nl) + 1 > ctx["max_dev"]:
        return None
    e = rng.choice(cands)
    a, b = dnets(e)
    if a == b:
        return None
    types = [t] if t else [x for x in PASSIVE_TYPES]
    rng.shuffle(types)
    for typ in types:
        if not _inductor_room(nl, ctx, typ == "inductor"):
            continue
        out = copy_nl(nl)
        out.append(_new_device(out, typ, [a, b]))
        return out
    return None


def p7_reconnect_terminal(nl, rng, ctx, dev=None, pin=None, node=None):
    """P7 -- move one device terminal to a different EXISTING node. Generalizes
    `m_rewire` (passive-only) to FET pins as well. The move is rejected unless the
    RESULT is L0-legal (no self-loop, no node dropped below degree 2); `mutate()`
    re-checks `sane()` regardless."""
    cands = []                                          # (name, ki, cur_net)
    for e in nl:
        for ki, net in enumerate(dnets(e)):
            if is_fet(e) and ki == 3:                   # leave bulk tie alone
                continue
            cands.append((dname(e), ki, net))
    cands.sort()
    if dev is not None:
        cands = [c for c in cands if c[0] == dev and (pin is None or c[1] == pin)]
    if not cands:
        return None
    name, ki, cur = rng.choice(cands)
    out = copy_nl(nl)
    e = next(x for x in out if dname(x) == name)
    # the other nets of THIS device (avoid making a self-loop)
    own = set(dnets(e))
    pool = [n for n in real_nodes(out, extra_exclude=own) if n != "VIN1"]
    if node is not None:
        pool = [n for n in pool if n == node]
    if not pool:
        return None
    e[1 + ki] = rng.choice(pool)
    return out


def add_and_connect_device(nl, rng, ctx, t=None, pinmap=None):
    """The ruled ATOMIC primitive (OQ-5 RULED ACCEPT): place a FULLY-WIRED device
    of type `t` with an explicit {pin: node} terminal map, in ONE edit, so no
    intermediate is L0-illegal (the ruling forbids transient-illegal states).

    `pinmap` maps each pin of the type to an EXISTING node:
      * passive: {"P": node, "N": node}
      * FET:     {"D": node, "G": node, "S": node, "B": node} (B defaults to VSS)
    If `pinmap` is None a random legal map is drawn (used by the random arm)."""
    if len(nl) + 1 > ctx["max_dev"]:
        return None
    types = [t] if t else list(DEVICE_TYPES)
    rng.shuffle(types)
    pool_all = real_nodes(nl)
    if len(pool_all) < 2:
        return None
    for typ in types:
        if not _inductor_room(nl, ctx, typ == "inductor"):
            continue
        if typ in PASSIVE_TYPES:
            if pinmap:
                a, b = pinmap["P"], pinmap["N"]
            else:
                a, b = rng.sample(pool_all, 2)
            if a == b or a not in pool_all or b not in pool_all:
                continue
            return nl + [_new_device(nl, typ, [a, b])]
        else:
            if pinmap:
                d = pinmap["D"]; g = pinmap["G"]; s = pinmap["S"]
                b = pinmap.get("B", "VSS")
            else:
                d = rng.choice(pool_all)
                s = rng.choice([n for n in pool_all if n != d])
                g = rng.choice(pool_all)
                b = "VSS"
            nets = [d, g, s, b]
            if d == s or g == d:                          # no self-loop
                continue
            if any(x not in nodes_of(nl) and x != "VSS" for x in nets):
                continue
            return nl + [_new_device(nl, typ, nets)]
    return None


# The RULED repertoire (P1-P5, P7, + add_and_connect_device). P6 is absent.
# Weights mirror lna.moves' spirit: growth moves a touch lower, edits higher.
PRIMITIVES = [
    ("p1_add_device_of_type",   p1_add_device_of_type,   1.0),
    ("p2_fet_polarity_swap",    p2_fet_polarity_swap,    1.0),
    ("p3_split_net",            p3_split_net,            0.8),
    ("p4_insert_series_element", p4_insert_series_element, 1.0),
    ("p5_insert_parallel_element", p5_insert_parallel_element, 1.0),
    ("p7_reconnect_terminal",   p7_reconnect_terminal,   1.2),
    ("add_and_connect_device",  add_and_connect_device,  1.0),
]
PRIMITIVE_NAMES = [p[0] for p in PRIMITIVES]
_FNS = {n: f for n, f, _ in PRIMITIVES}
_WS = {n: w for n, _, w in PRIMITIVES}


def apply_named(nl, name, rng, ctx, **kw):
    """Apply one named primitive with explicit kwargs (for scripted edit paths and
    unit tests). Returns the new netlist or None."""
    return _FNS[name](copy_nl(nl), rng, ctx, **kw)


def mutate(nl, rng, ctx, names=None, tries=16):
    """One primitive edit, `sane()`-gated exactly like `lna.moves.mutate`.
    Returns (new_netlist, move_name) or (None, None)."""
    pool = [n for n in (names or PRIMITIVE_NAMES) if n in _FNS]
    if not pool:
        return None, None
    for _ in range(tries):
        name = rng.choices(pool, weights=[_WS[n] for n in pool], k=1)[0]
        try:
            out = _FNS[name](copy_nl(nl), rng, ctx)
        except Exception:
            out = None
        if out and sane(out, ctx["max_dev"], ctx["min_dev"]):
            return out, name
    return None, None


def ctx_for_spec(spec):
    """The structural budget context the primitives read, from a spec."""
    return {"max_dev": spec.topology.get("device_budget", [3, 16])[1],
            "min_dev": spec.topology.get("device_budget", [3, 16])[0],
            "max_inductors": spec.topology.get("max_inductors", 99)}


# ------------------------------------------------------- output-class detector
def output_fet(nl):
    """The output-stage FET: the FET whose drain reaches VOUT1 through exactly the
    output coupler (`m_output_coupler`'s far node), source on VSS -- the flagship's
    class-A NM6. Returns its netlist entry, or None."""
    coup, far = M.output_coupler(nl)
    if coup is None:
        return None
    for e in nl:
        if is_fet(e) and fet_pins(e)["D"] == far:
            return e
    return None


def output_class_is_A(nl):
    """True iff the output node (the drain node feeding VOUT1's coupler) is driven
    class-A: a SINGLE active device conducting, all FETs on that node the same
    polarity with source toward VSS. A NON-class-A output has a second active
    device of COMPLEMENTARY polarity whose source is on VDD sharing the output
    node -- i.e. a device positioned to source current on the half-cycle the
    nmos sinks. Returns (is_class_A, info)."""
    coup, out_node = M.output_coupler(nl)
    if coup is None:
        return True, {"reason": "no unique output coupler"}
    fets_here = [e for e in nl if is_fet(e)
                 and (fet_pins(e)["D"] == out_node or fet_pins(e)["S"] == out_node)]
    n_active = len(fets_here)
    pols = {dtype(e) for e in fets_here}
    # a complementary sourcing device: a pmos with source on VDD, drain on out_node
    comp = [e for e in fets_here if dtype(e) == "pmos4"
            and fet_pins(e)["S"] == "VDD" and fet_pins(e)["D"] == out_node]
    is_A = not (n_active >= 2 and "pmos4" in pols and "nmos4" in pols and comp)
    return is_A, {"out_node": out_node, "n_active_on_out": n_active,
                  "polarities": sorted(pols), "complementary_sourcing": len(comp)}


# ------------------------------------------------------------------ selftest
def _flagship_nl():
    import json
    import templates as T
    from topology import Topology
    tok = json.load(open(os.path.join(LNA, "repro", "dhruva-best", "tokens.json"),
                        encoding="utf-8"))
    nl, _ = T.topo_to_netlist(Topology(tok))
    return nl


def _selftest():
    from spec import Spec
    spec = Spec.load("dhruva-s")
    ctx = ctx_for_spec(spec)
    base = _flagship_nl()
    assert sane(base, ctx["max_dev"], ctx["min_dev"]), "flagship not L0-sane!"
    outf = output_fet(base)
    print(f"flagship: {len(base)} devices, output FET = {dname(outf)} "
          f"(D={fet_pins(outf)['D']} S={fet_pins(outf)['S']} type={dtype(outf)})")
    isA, info = output_class_is_A(base)
    print(f"flagship output class-A? {isA}   {info}")
    assert isA, "flagship should read as class-A"

    fails = 0
    # 1. each primitive applied to a COPY of the flagship yields an L0-checkable
    #    (sane) topology, and does not mutate the input.
    for name in PRIMITIVE_NAMES:
        rng = random.Random(7)
        before = [list(e) for e in base]
        out = apply_named(base, name, rng, ctx)
        if base != before:
            print(f"  FAIL {name}: mutated its input"); fails += 1
        if out is None:
            print(f"  {name}: not applicable to flagship (returned None)")
            continue
        ok = sane(out, ctx["max_dev"], ctx["min_dev"])
        scr = spec.structural_screen_nl(out) if hasattr(spec, "structural_screen_nl") else None
        print(f"  {name}: sane={ok}  ndev {len(base)}->{len(out)}")
        if not ok:
            print(f"    FAIL {name}: result not L0-sane"); fails += 1

    # 2. determinism: same seed -> same edit; different seed may differ.
    for name in PRIMITIVE_NAMES:
        a = apply_named(base, name, random.Random(3), ctx)
        b = apply_named(base, name, random.Random(3), ctx)
        if a != b:
            print(f"  FAIL {name}: non-deterministic under fixed seed"); fails += 1
    print(f"determinism: checked {len(PRIMITIVE_NAMES)} primitives")

    # 3. add_and_connect_device with an explicit pinmap places a wired pmos.
    rng = random.Random(1)
    out_node = output_class_is_A(base)[1]["out_node"]
    mp = {"D": out_node, "G": fet_pins(outf)["G"], "S": "VDD", "B": "VSS"}
    out = add_and_connect_device(copy_nl(base), rng, ctx, t="pmos4", pinmap=mp)
    assert out is not None, "atomic add_and_connect_device(pmos4) failed"
    assert sane(out, ctx["max_dev"], ctx["min_dev"]), "atomic result not sane"
    isA2, info2 = output_class_is_A(out)
    print(f"atomic pmos4 -> output class-A? {isA2}  {info2}")
    assert not isA2, "atomic complementary add should read NON-class-A"

    print(f"\nSELFTEST {'PASS' if fails == 0 else 'FAIL (%d)' % fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="G2 primitive move repertoire")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(_selftest())
    ap.error("give --selftest")

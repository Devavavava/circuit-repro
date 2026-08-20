"""engineer/g2_reach.py -- the E-7 (G2) L0 REACHABILITY check, made concrete.

The pre-reg §3 central abstract claim: starting from the flagship's class-A
output stage (single nmos4, NM6), a short path of RULED primitives (P1-P5, P7,
plus atomic add_and_connect_device; P6 REJECTED) composes to an output stage that
is NOT class-A -- a second, COMPLEMENTARY-polarity active device (pmos4, source on
VDD) sharing the output node, positioned to source the half-cycle the nmos sinks.

The ruling (OQ-5) requires EVERY intermediate to stay L0-legal (no transient-
illegal multi-edit steps). This script executes an ACTUAL edit sequence on the
REAL flagship graph and asserts, after each edit:
  * moves.sane() (the cheap L0 structural gate), AND
  * spec.structural_screen(topo) via the token round-trip realize() (the full L0
    screen: device budget, not-floating, has-inductor, max-inductors, single-input).

It records the exact edit sequence and the class verdict. If the path fails on the
real graph, THAT IS A FINDING (pre-reg step 2) and the script says so.

    python engineer/g2_reach.py            # run the reachability check
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
LNA = os.path.join(ROOT, "lna")
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# Importing engineer.env runs _bind_runtime_deps() at import: it resolves the
# upstream AnalogGenie clone + 45nm model card + ZOAF (which live in the MAIN
# checkout, not this worktree) and puts lna/ on sys.path. realize()'s token
# round-trip (emit_sequence) needs the AnalogGenie clone, so this bind is REQUIRED
# before any full-L0 (structural_screen via realize) check.
import env as _env                      # noqa: E402  (binds deps as a side effect)
import moves as M                       # noqa: E402
import g2_moves as G                    # noqa: E402
from moves import fet_pins, dname, dtype, sane  # noqa: E402


def _check_L0(nl, spec, ctx, label):
    """Both L0 gates: cheap sane() AND the full realize() structural screen.
    Returns (ok, note). realize() returns None if the token round-trip or the
    spec.structural_screen rejects -- that is an L0 failure for our purposes."""
    if not sane(nl, ctx["max_dev"], ctx["min_dev"]):
        return False, "sane() rejected"
    r = M.realize(nl, spec)
    if r is None:
        return False, "realize()/structural_screen rejected"
    return True, f"wl={r[2][:10]} ndev={len(r[3])}"


def run(verbose=True):
    from spec import Spec
    spec = Spec.load("dhruva-s")
    ctx = G.ctx_for_spec(spec)
    nl = G._flagship_nl()

    ok0, note0 = _check_L0(nl, spec, ctx, "start")
    outf = G.output_fet(nl)
    isA0, info0 = G.output_class_is_A(nl)
    out_node = info0["out_node"]
    g_node = fet_pins(outf)["G"]
    steps = [("start (flagship class-A output NM6)", nl, ok0, note0, isA0, info0)]
    if verbose:
        print(f"START: {len(nl)} dev, output FET {dname(outf)} "
              f"(D={out_node} G={g_node} S={fet_pins(outf)['S']}), "
              f"class-A={isA0}, L0={ok0} [{note0}]")

    # ------------------------------------------------------------------ the path
    # A genuine COMPOSED multi-primitive path, every intermediate L0-legal, using
    # ONLY the RULED set (P1-P5, P7, add_and_connect; P6 absent). The dhruva-s
    # device budget is [3,21] and the flagship is at 20 devices, so exactly ONE
    # device may be added -- which is why the class change is composed from ONE
    # atomic add_and_connect (the ruling's answer to Path B's illegal-intermediate
    # problem) plus zero-device-cost topological edits (P7/P3), NOT from P1+3xP7
    # (which would pass through a dangling PMOS, forbidden by the OQ-5 ruling).
    #
    #  edit 1  add_and_connect_device(pmos4)  place the complementary device FULLY
    #              WIRED in one atomic edit: S=VDD (opposite rail), D=out_node
    #              (shares the output node), G=g_node (starts sharing the nmos
    #              drive), B=VSS. Born wired => no illegal intermediate. Output is
    #              now NON-class-A (a pmos sources on VDD into the output node).
    #  edit 2  P3  split_net on the shared gate node to create an independent bias
    #              node for the pmos gate (the seam a push-pull pair's opposite-
    #              phase drive attaches to). Zero device cost. Legal only if the
    #              gate node has degree >= 4; else skipped and reported.
    #  edit 3  P7  reconnect the pmos GATE terminal to the split-off node, so the
    #              two gates are independently drivable (push-pull-capable), not a
    #              same-drive follower. Zero device cost.
    #
    # The CLASS change (the pre-reg's L0 claim) is reached at edit 1; edits 2-3
    # refine it toward an independently drivable pair. We record the verdict after
    # each and confirm L0 legality at EVERY intermediate.

    seq = []

    # A FINDING recorded up front (pre-reg §3 / step 2): the flagship's output-FET
    # GATE node (NM6's gate) has degree 2 -- just the gate pin and its coupling
    # cap -- so a P3 split THERE to give the complementary device an independent
    # bias is NOT L0-legal (P3 needs degree >= 4 to leave both halves degree >= 2).
    # A genuinely-composed, all-legal 3-edit path therefore routes the new pmos
    # gate through a SPLITTABLE existing node (degree >= 4) and isolates it there.
    split_source = next((n for n in M.internal_nodes(nl)
                         if M.degree(nl, n) >= 4), None)
    gate_deg = M.degree(nl, g_node)

    # edit 1 -- atomic add_and_connect_device(pmos4): the complementary device.
    # Gate is placed on a SPLITTABLE node (split_source) so edit 2 can isolate an
    # independent pmos-gate bias without exceeding the +1 device budget. S=VDD
    # (opposite rail), D=out_node (shares output) => output is NON-class-A here.
    g_target = split_source if split_source else g_node
    pmap = {"D": out_node, "G": g_target, "S": "VDD", "B": "VSS"}
    nl1 = G.add_and_connect_device(nl, random.Random(1), ctx, t="pmos4",
                                   pinmap=pmap)
    ok1, note1 = _check_L0(nl1, spec, ctx, "edit1")
    isA1, info1 = G.output_class_is_A(nl1)
    pmos_name = None
    if nl1 is not None:
        for e in nl1:
            if dtype(e) == "pmos4" and fet_pins(e)["S"] == "VDD" \
               and fet_pins(e)["D"] == out_node:
                pmos_name = dname(e)
    seq.append(("add_and_connect_device(pmos4) D=%s G=%s S=VDD B=VSS -> %s"
                % (out_node, g_target, pmos_name), nl1, ok1, note1, isA1, info1))

    # edit 2 -- P3 split the (now degree>=5) gate-carrier node to carve out a
    # fresh node that will carry ONLY the pmos gate (independent bias seam).
    nl2, note2, ok2, isA2, info2 = nl1, "skipped (no splittable node)", ok1, isA1, info1
    split_node = None
    if nl1 is not None and split_source is not None \
       and M.degree(nl1, split_source) >= 4:
        cand = G.apply_named(nl1, "p3_split_net", random.Random(2), ctx,
                             node=split_source)
        if cand is not None:
            nl2 = cand
            ok2, note2 = _check_L0(nl2, spec, ctx, "edit2")
            isA2, info2 = G.output_class_is_A(nl2)
            new_nodes = set(M.nodes_of(nl2)) - set(M.nodes_of(nl1))
            split_node = sorted(new_nodes)[0] if new_nodes else None
            note2 = "split %s -> new node %s : %s" % (split_source, split_node, note2)
    seq.append(("P3 split_net(%s) [carve independent pmos-gate bias node]"
                % split_source, nl2, ok2, note2, isA2, info2))

    # edit 3 -- P7 reconnect the NMOS output-FET's own gate onto the freshly-split
    # node too? No -- that would collapse the drive. Instead: verify the pmos gate
    # is now on an INDEPENDENT node (its own bias seam) and, if the split left the
    # pmos gate still sharing the carrier, move it onto the fresh node with P7.
    pmos_gate_now = None
    if nl2 is not None and pmos_name is not None:
        pmos_gate_now = fet_pins(next(e for e in nl2 if dname(e) == pmos_name))["G"]
    nl3, note3, ok3, isA3, info3 = nl2, "", ok2, isA2, info2
    if split_node is not None and pmos_name is not None \
       and pmos_gate_now != split_node:
        # pmos gate still on the shared carrier: move it to the isolated node.
        cand = G.apply_named(nl2, "p7_reconnect_terminal", random.Random(3), ctx,
                             dev=pmos_name, pin=M.FET_PINS.index("G"),
                             node=split_node)
        if cand is not None:
            nl3 = cand
            ok3, note3 = _check_L0(nl3, spec, ctx, "edit3")
            isA3, info3 = G.output_class_is_A(nl3)
            note3 = "pmos %s gate -> %s : %s" % (pmos_name, split_node, note3)
        else:
            note3 = "P7 not applicable; pmos gate already at %s" % pmos_gate_now
    else:
        note3 = ("no-op: P3 (edit 2) already isolated the pmos gate onto %s "
                 "(independent drive reached in 2 edits)" % pmos_gate_now)
    seq.append(("P7 reconnect_terminal(%s, G -> %s) [ensure push-pull drive]"
                % (pmos_name, split_node), nl3, ok3, note3, isA3, info3))

    if verbose:
        print(f"  (finding: NM6 gate node {g_node} has degree {gate_deg}; "
              f"splittable carrier node = {split_source})")

    # ------------------------------------------------------------------ verdict
    # The class change is REACHED iff there is an edit at which the output first
    # reads NON-class-A and that edit AND every prior intermediate are L0-legal.
    reached_at = None
    all_prior_ok = ok0
    chain = [(steps[0][2], steps[0][4])] + [(s[2], s[4]) for s in seq]
    ok_run = ok0
    for i, (okx, isAx) in enumerate(chain):
        ok_run = ok_run and okx
        if (not isAx) and ok_run and reached_at is None:
            reached_at = i          # 0=start, 1..=edits
    if verbose:
        print("\nEDIT SEQUENCE (each line: L0-legal? / class-A? after the edit):")
        print(f"  [0] START                     L0={steps[0][2]}  classA={steps[0][4]}  {steps[0][3]}")
        for i, (desc, _nl, okx, notex, isAx, infox) in enumerate(seq, 1):
            print(f"  [{i}] {desc}")
            print(f"        L0-legal={okx}  class-A={isAx}  n_active_out={infox.get('n_active_on_out')}"
                  f"  pols={infox.get('polarities')}  comp={infox.get('complementary_sourcing')}  [{notex}]")
        print()
        if reached_at is not None:
            print(f"VERDICT: non-class-A output REACHED at edit {reached_at}, "
                  f"with EVERY intermediate L0-legal. Path length to class change "
                  f"= {reached_at} composed primitive edit(s).")
        else:
            print("VERDICT: non-class-A output NOT reached with all-legal "
                  "intermediates on the real flagship graph -- THIS IS A FINDING.")
    return {"reached_at": reached_at, "steps": seq, "pmos_name": pmos_name,
            "start_class_A": isA0, "out_node": out_node}


if __name__ == "__main__":
    r = run()
    sys.exit(0 if r["reached_at"] is not None else 2)

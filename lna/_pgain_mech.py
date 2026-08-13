"""WP-PGAIN part 1 -- structural node resolution + switch insertion.

Why this file exists at all: `size.prepared_body()` node names are NOT stable.
`to_spice` renumbers the internal nodes from a set/dict walk, so `n0` is the
recombine node in one process and MNM6's gate in the next (measured: four
processes, four different maps -- see FINDINGS SS42). Any post-processing that
inserts elements by literal node name is therefore attaching to a *random*
node, and every number it produces is void. ELEMENT names (CC1..CC8, LL1/LL2,
MNM1..MNM6, RR1..RR4, plus the fixed port/supply nets VIN1/VOUT1/p1/p2/VDD)
ARE stable, so this module resolves every circuit role from the element lines
and cross-checks each role two independent ways before returning.

Inserted elements are named MSWG*/RSWG*/CSWG*/VSWG* -- disjoint from both the
topology's own prefixes and the bias scaffold's `^(RBIAS|CBYP|VBGEN)`, so that
contract extends to `^(RBIAS|CBYP|VBGEN|MSWG|RSWG|CSWG|VSWG)` with no
ambiguity. Params are pRSWG*/pWSWG*/pVSWG*/pCSWG*.

A "state" is a dict of pVSWG* control voltages ONLY: one netlist, one set of
device sizes, states differing only in gate voltages on the switch devices.
"""
import re

VON, VOFF = 1.1, 0.0        # the deck's own rails (pVDD = 1.1, ground)
CBLK = 1e-11                # 10 pF DC block -- the same value the deck's own
                            # port/coupling caps use (Cp1/Cp2/CC1/CC3/...)
RGATE = "10k"               # gate feed resistor: DC-only, RF-isolating


# ------------------------------------------------------------------ roles

def _elems(body):
    """{ELEMENT_NAME: [node, ...]} for every element line in a deck body."""
    out = {}
    for ln in body.splitlines():
        s = ln.strip()
        if not s or s.startswith(("*", ".")):
            continue
        parts = s.split()
        out[parts[0]] = parts[1:]
    return out


def resolve_nodes(body):
    """Circuit roles -> node names, resolved structurally and cross-checked.

    Roles (names use the *shipped* dhruva-l5.sp vocabulary from
    repro/dhruva-best/REPORT.md SS2 so the write-up and the code agree):

      comb      input combiner node   -- CC1's far side; MNM1 source (the CG
                                         device); LL1's shunt-match node; feeds
                                         MNM2/MNM5 gates through CC3/CC7
      g2,g5     the combiner's CS pair gates (MNM2, MNM5)
      cgd       CG drain (MNM1 drain, RR1 load) -> CC4 -> g3
      g3        MNM3 gate
      recomb    RECOMBINE node -- the common drain of MNM2/MNM3/MNM5, RR2 load
      g4        tuned-stage input (MNM4 gate), driven from recomb through CC5
      tank      tuned-stage drain (MNM4 drain), loaded by LL2+RQL2 up to RR3
      g6        output-stage input (MNM6 gate), driven from tank through CC8
      outd      output-stage drain (MNM6 drain, RR4 load) -> CC6 -> VOUT1
    """
    e = _elems(body)
    need = ["CC1", "CC3", "CC4", "CC5", "CC6", "CC7", "CC8", "LL1", "LL2",
            "RQL2", "RR1", "RR2", "RR3", "RR4"] + [f"MNM{i}" for i in range(1, 7)]
    missing = [k for k in need if k not in e]
    if missing:
        raise SystemExit(f"pgain: topology contract broken, missing {missing}")

    def mos(name):
        d, g, s, b = e[name][:4]
        return dict(d=d, g=g, s=s, b=b)

    m = {i: mos(f"MNM{i}") for i in range(1, 7)}
    r = dict(
        comb=m[1]["s"], g1=m[1]["g"], cgd=m[1]["d"],
        g2=m[2]["g"], g3=m[3]["g"], g4=m[4]["g"], g5=m[5]["g"], g6=m[6]["g"],
        recomb=m[2]["d"], tank=m[4]["d"], outd=m[6]["d"],
    )

    def chk(cond, msg):
        if not cond:
            raise SystemExit(f"pgain: node-role cross-check failed -- {msg}")

    # every role is confirmed by a SECOND element that must touch it
    chk(set(e["CC1"][:2]) == {"VIN1", r["comb"]}, "CC1 not VIN1<->comb")
    chk(r["comb"] in e["LL1"][:2], "LL1 does not touch comb")
    chk(set(e["CC3"][:2]) == {r["comb"], r["g2"]}, "CC3 not comb<->MNM2.g")
    chk(set(e["CC7"][:2]) == {r["comb"], r["g5"]}, "CC7 not comb<->MNM5.g")
    chk(m[3]["d"] == r["recomb"] and m[5]["d"] == r["recomb"],
        "MNM2/3/5 drains are not one recombine node")
    chk(e["RR2"][1] == r["recomb"] or e["RR2"][0] == r["recomb"],
        "RR2 does not load recomb")
    chk(r["cgd"] in e["RR1"][:2], "RR1 does not load the CG drain")
    chk(set(e["CC4"][:2]) == {r["cgd"], r["g3"]}, "CC4 not cgd<->MNM3.g")
    chk(set(e["CC5"][:2]) == {r["recomb"], r["g4"]}, "CC5 not recomb<->MNM4.g")
    chk(r["tank"] in e["RQL2"][:2], "RQL2 does not reach the tank node")
    chk(set(e["CC8"][:2]) == {r["tank"], r["g6"]}, "CC8 not tank<->MNM6.g")
    chk(r["outd"] in e["RR4"][:2], "RR4 does not load the output drain")
    chk(set(e["CC6"][:2]) == {r["outd"], "VOUT1"}, "CC6 not outd<->VOUT1")
    chk(all(m[i]["s"] == "0" for i in (2, 3, 4, 5, 6)),
        "a CS source is not grounded -- degeneration insert would be wrong")
    return r


# ------------------------------------------------------------ primitives

def _nfexpr(wp):
    """Multi-finger count, exactly the expression to_spice emits for every MOS
    in this deck (w_finger = 2 um, the post-2026-08-10 cutover convention)."""
    return f"NF={{max(1,ceil({wp}/2e-06))}}"


def _switch(name, d, g, s, wp):
    return f"MSWG{name} {d} {g} {s} 0 nmos W={{{wp}}} L=45n {_nfexpr(wp)}"


def _gate_feed(name, g, vp):
    """DC-only gate drive: a control source behind RGATE. The control voltage
    IS the state variable -- nothing else changes between states."""
    return [f"RSWGG{name} {g} nswc{name} {RGATE}",
            f"VSWG{name} nswc{name} 0 dc {{{vp}}}"]


def _dof(name, kind, lo, hi, init):
    return dict(name=name, kind=kind, lo=lo, hi=hi, init=init)


# ------------------------------------------------------------ mechanisms

def insert_bank(body, nodes, tag, with_r=False):
    """Switched shunt bank -- one branch per entry of `nodes`.

    branch i:  node --CSWG(10pF)--> [a --RSWG(pR)--> ] b --MSWG(pW)--> gnd

    With `with_r=False` (the default) the triode NMOS switch IS the bank
    element: the state selects total on-conductance, set by the switch widths.
    That is deliberate -- the 10 pF DC block is itself ~13.5 ohm of reactance at
    1.18 GHz and the spec's own R box floors a resistor at 50 ohm, so a series
    resistor can only ever make a branch weaker than the block already forces
    it to be (measured: `--probe`, the R=50 vs R=5 columns). `with_r=True`
    keeps the literal series-resistor reading of "load-resistor bank" and is
    measured as its own mechanism.

    DC-blocked, so the core's operating point is untouched in every state
    (Idd constant across states by construction -- verified, not assumed).
    States are CUMULATIVE (S0 = all off = max gain, Sk = branches 1..k on), so
    the gain steps are monotonic by construction: each extra branch only adds
    parallel conductance at its node.
    """
    lines, dofs = [], []
    for i, node in enumerate(nodes, start=1):
        t = f"{tag}{i}"
        lines.append(f"CSWG{t} {node} nswa{t} {{pCSWG}}")
        drain = f"nswa{t}"
        if with_r:
            lines.append(f"RSWG{t} nswa{t} nswb{t} {{pRSWG{t}}}")
            drain = f"nswb{t}"
            dofs.append(_dof(f"pRSWG{t}", "R", 50.0, 20000.0, 200.0))
        lines.append(_switch(t, drain, f"nswg{t}", "0", f"pWSWG{t}"))
        lines += _gate_feed(t, f"nswg{t}", f"pVSWG{t}")
        dofs.append(_dof(f"pWSWG{t}", "W", 1e-6, 2e-4, 5e-5))
    fixed = {"pCSWG": CBLK}
    n = len(nodes)
    states = [(f"S{k}", {f"pVSWG{tag}{i}": (VON if i <= k else VOFF)
                         for i in range(1, n + 1)}) for k in range(n + 1)]
    return "\n".join([body.rstrip()] + lines) + "\n", dofs, fixed, states


def insert_degen(body, devices, n, tag):
    """Switched source-degeneration ladder under `devices` (the input
    combiner's CS pair, MNM2/MNM5).

    The devices' sources move from ground to nsd1; a ladder
    nsd1-R1-nsd2-R2-...-gnd hangs below, and switch i shorts nsd_i to ground.
    Exactly one switch on per state: SW1 on = 0 ohm = MAX gain, SW2 on = R1 in
    circuit, ..., all off = R1+..+Rn. Bulks stay at ground, so the body effect
    rides along -- that is part of the mechanism, not a defect.

    Unlike the banks this is NOT DC-blocked: degeneration moves the operating
    point, so Idd changes state to state. That is measured, not assumed.
    """
    pat = re.compile(r"^(" + "|".join(devices) + r")\s")
    out, hit = [], 0
    for ln in body.splitlines():
        if pat.match(ln):
            p = ln.split()
            if p[3] != "0":
                raise SystemExit(f"pgain: {p[0]} source is {p[3]}, not ground")
            p[3] = "nsd1"
            ln, hit = " ".join(p), hit + 1
        out.append(ln)
    if hit != len(devices):
        raise SystemExit(f"pgain: patched {hit} of {len(devices)} CS sources")
    lines, dofs = [], []
    for i in range(1, n + 1):
        t = f"{tag}{i}"
        nxt = f"nsd{i+1}" if i < n else "0"
        lines += [
            f"RSWG{t} nsd{i} {nxt} {{pRSWG{t}}}",
            _switch(t, f"nsd{i}", f"nswg{t}", "0", f"pWSWG{t}"),
        ] + _gate_feed(t, f"nswg{t}", f"pVSWG{t}")
        # the rung floor is 1 ohm, BELOW the spec's own 50 ohm R box: a 50 ohm
        # rung under a device carrying milliamps would move the operating point
        # off the cliff before it ever attenuated. Sub-box rungs are flagged
        # out-of-box in the emitted row rather than silently allowed.
        dofs += [_dof(f"pRSWG{t}", "R", 1.0, 20000.0, 20.0),
                 _dof(f"pWSWG{t}", "W", 1e-6, 2e-4, 1.5e-4)]
    states = [(f"S{k}", {f"pVSWG{tag}{i}": (VON if i == k + 1 else VOFF)
                         for i in range(1, n + 1)}) for k in range(n)]
    states.append((f"S{n}", {f"pVSWG{tag}{i}": VOFF for i in range(1, n + 1)}))
    return "\n".join(out + lines) + "\n", dofs, {}, states


def insert_bypass(body, roles, tag, n_att=2):
    """Switch-bypass of the OUTPUT gain stage (MNM6), plus a shunt-R bank on
    its drain so the mechanism has more than two states.

    CC8's stage-side node is re-pointed from MNM6's gate to a new node
    `nbypin`; then

        MSWGP nbypin -> g6    series PASS switch (stage in the path)
        MSWGB nbypin -> outd  BYPASS switch (signal goes around the stage)

    high-gain  = pass ON, bypass OFF  (the stage amplifies)
    bypass     = pass OFF, bypass ON  (MNM6's gate is cut loose -- it still
                 carries its bias current, so Idd is unchanged, but it no
                 longer receives drive; the signal walks around it through the
                 switch and is divided into RR4 || the output network)
    The intermediate states engage the drain bank while still in pass mode.
    """
    g6, tank, outd = roles["g6"], roles["tank"], roles["outd"]
    out, hit = [], 0
    for ln in body.splitlines():
        p = ln.split()
        if p and p[0] == "CC8":
            p[1:3] = [tank, "nbypin"]
            ln, hit = " ".join(p), hit + 1
        out.append(ln)
    if hit != 1:
        raise SystemExit("pgain: CC8 not re-pointed")
    # The bypass switch is DC-BLOCKED on its far side. Without the block it
    # ties `outd` (a drain sitting near the supply) straight onto MNM6's gate
    # through the channel, which turns MNM6 hard on and lifts Idd to 13.6-17.1
    # mA -- measured, and the reason this mechanism failed its first build.
    # Both switch terminals now float at 0 V via rshunt, so Vgs = the control
    # voltage exactly, in every state.
    lines = [_switch(f"{tag}P", "nbypin", f"nswg{tag}P", g6, f"pWSWG{tag}P")]
    lines += _gate_feed(f"{tag}P", f"nswg{tag}P", f"pVSWG{tag}P")
    lines += [f"CSWG{tag}B nbypo {outd} {{pCSWG}}",
              _switch(f"{tag}B", "nbypin", f"nswg{tag}B", "nbypo",
                      f"pWSWG{tag}B")]
    lines += _gate_feed(f"{tag}B", f"nswg{tag}B", f"pVSWG{tag}B")
    dofs = [_dof(f"pWSWG{tag}P", "W", 1e-6, 2e-4, 1.5e-4),
            _dof(f"pWSWG{tag}B", "W", 1e-6, 2e-4, 1.5e-4)]
    body2 = "\n".join(out + lines) + "\n"
    body2, bdofs, fixed, bstates = insert_bank(body2, [outd] * n_att,
                                               tag + "A")
    dofs += bdofs
    states = []
    for k in range(n_att + 1):            # pass mode, k bank branches on
        st = dict(bstates[k][1])
        st[f"pVSWG{tag}P"], st[f"pVSWG{tag}B"] = VON, VOFF
        states.append((f"S{k}", st))
    st = dict(bstates[n_att][1])          # bypass mode, whole bank on
    st[f"pVSWG{tag}P"], st[f"pVSWG{tag}B"] = VOFF, VON
    states.append((f"S{n_att+1}", st))
    return body2, dofs, fixed, states


# ------------------------------------------------------------- registry

def build(mech, body):
    """(body, dofs, fixed, states) for a mechanism name."""
    r = resolve_nodes(body)
    if mech == "in-att":
        return insert_bank(body, [r["comb"]] * 3, "IA")
    if mech == "in-degen":
        return insert_degen(body, ("MNM2", "MNM5"), 3, "ID")
    if mech == "n0-bank":
        return insert_bank(body, [r["recomb"]] * 3, "NB")
    if mech == "n0-bank-r":
        return insert_bank(body, [r["recomb"]] * 3, "NR", with_r=True)
    if mech == "out-bank":
        return insert_bank(body, [r["outd"]] * 3, "OB")
    if mech == "out-bank-r":
        return insert_bank(body, [r["outd"]] * 3, "OR", with_r=True)
    if mech == "out-bank2":
        return insert_bank(body, [r["outd"], "VOUT1", r["outd"], "VOUT1"], "O2")
    if mech == "bypass":
        return insert_bypass(body, r, "BY")
    raise SystemExit(f"pgain: unknown mechanism {mech}")


MECHS = {
    "in-att":     "(a) switched shunt attenuator bank on the INPUT COMBINER "
                  "node (3 branches, cumulative)",
    "in-degen":   "(a') switched source-degeneration ladder under the "
                  "combiner's CS pair MNM2/MNM5 (3 rungs)",
    "n0-bank":    "(b) switched load bank on the RECOMBINE node n0 "
                  "(3 branches, cumulative, switch-as-element)",
    "n0-bank-r":  "(b) recombine-node bank, literal series-RESISTOR reading "
                  "(3 branches, R in the spec box)",
    "out-bank":   "(b') the same load bank on the OUTPUT-STAGE drain "
                  "(3 branches, cumulative, switch-as-element)",
    "out-bank-r": "(b') output-stage drain bank, literal series-RESISTOR "
                  "reading (3 branches, R in the spec box)",
    "out-bank2":  "(b'') load bank split across the output-stage drain and "
                  "VOUT1 (4 branches, cumulative)",
    "bypass":     "(c) switch-bypass of the output gain stage MNM6 + drain bank",
}

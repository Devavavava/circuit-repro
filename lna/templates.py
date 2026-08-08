"""WP-GEN P5 / stratum-T archetype generator (plans2, 01-DATA §5, old 04-GEN §6).

The generated arms recite ~35 training graphs (median NN-sim 1.000) and the
corpus is 41 real designs -- neither gives the *topology diversity* the critic
needs, and the store has exactly one feasible row (the tapped reference). This
mints hand-designed LNA archetypes as valid AnalogGenie token topologies, so the
campaign can label a diverse, gain-capable stratum T.

Construction reuses the upstream pipeline verbatim (proven to round-trip real
corpus circuits WL-hash-exact): an archetype is written as a netlist in
`read_netlist` format -- `[name, net1..netK (pin order), type]` -- plus the port
list, then `build_connection_matrix -> dfs_all_paths` emits the Eulerian token
sequence that `topology.Topology` parses back. No hand-rolled token walks.

Families (× structural toggles): inductively-degenerated CS (±Cex, ±cascode),
resistive-feedback and common-gate (inductorless / wideband), each with a
resistive / LC-tank / **tapped-C** load. The tapped-C load is the gain-capable
"matched" family (Gate G4) -- the source of feasible template labels.

    python lna/templates.py --list                 # enumerate distinct archetypes
    python lna/templates.py --emit-dir lna/out/templates   # write seq*.txt + meta
"""
import argparse
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from topology import Topology  # noqa: E402
from novelty import wl_features  # noqa: E402

PORTS = ["VDD", "VSS", "VIN1", "VOUT1"]
_FUNCS = None


def _pipeline():
    """Lazily load upstream build_connection_matrix / dfs_all_paths."""
    global _FUNCS
    if _FUNCS is None:
        import build_lna_corpus as B
        g = B.load_functions("SPICE2GRAPH_compress.py", "\nstart = 1")
        a = B.load_functions("Augmentation.py", "\nbase_dirs = {")
        _FUNCS = (g["build_connection_matrix"], a["read_connection_matrix"],
                  a["dfs_all_paths"])
    return _FUNCS


def emit_paths(netlist, ports=PORTS, max_solutions=1, run_num=1):
    """Netlist (read_netlist format) -> list of token sequences, via the upstream
    Eulerian augmentation (each path covers every edge once). Empty if none."""
    bcm, rcm, dfs = _pipeline()
    m, _ = bcm(netlist, ports)
    d = tempfile.mkdtemp(prefix="tmpl_")
    csv = os.path.join(d, "g.csv")
    m.to_csv(csv)
    paths = dfs(rcm(csv), start_node="VSS", max_solutions=max_solutions,
               run_num=run_num)
    return [[str(t) for t in p] for p in paths] if paths else []


def emit_sequence(netlist, ports=PORTS):
    """One canonical token sequence (or None)."""
    paths = emit_paths(netlist, ports, max_solutions=1, run_num=1)
    return paths[0] if paths else None


def topo_to_netlist(topo):
    """Reconstruct a read_netlist-format netlist + ports from a parsed Topology,
    so a *labeled* winner (Stage-3 expert iteration) can be Eulerian-augmented like
    a template. Returns (netlist, ports) or (None, None) if a device is
    incomplete. Round-trips WL-hash-exact on corpus + generated topologies."""
    import re
    from topology import base_of
    TYPE = {"NM": "nmos4", "PM": "pmos4", "R": "resistor",
            "C": "capacitor", "L": "inductor"}
    PINS = {"NM": ["D", "G", "S", "B"], "PM": ["D", "G", "S", "B"],
            "R": ["P", "N"], "C": ["P", "N"], "L": ["P", "N"]}
    node_name, ic = {}, [0]
    for root, members in topo.nodes.items():
        nets = sorted(m for m in members if m in topo.nets)
        if nets:
            node_name[root] = nets[0]
        else:
            ic[0] += 1
            node_name[root] = f"nn{ic[0]}"
    pin2root = {m: root for root, members in topo.nodes.items() for m in members}
    netlist = []
    for d in sorted(topo.devices):
        b = base_of(d)
        if b not in TYPE:
            continue
        try:
            nets = [node_name[pin2root[f"{d}_{p}"]] for p in PINS[b]]
        except KeyError:
            return None, None
        netlist.append([d] + nets + [TYPE[b]])
    ports = [n for n in ("VDD", "VSS", "VIN1", "VOUT1") if n in topo.nets]
    return (netlist, ports or list(PORTS)) if netlist else (None, None)


def augment(netlist, ports=PORTS, max_solutions=24, run_num=3):
    """A handful of Eulerian augmentations of one archetype -- the P5 fine-tune's
    training rows. Kept modest: the DFS augmentation is ~seconds/graph and ~20
    varied traversals per archetype already balances the corpus's per-circuit
    count without an hour of data prep."""
    return emit_paths(netlist, ports, max_solutions=max_solutions, run_num=run_num)


# --------------------------------------------------------------- net helper
class Nets:
    def __init__(self):
        self.i = 0

    def new(self):
        self.i += 1
        return f"n{self.i}"


# ------------------------------------------------------------- load blocks
def _add_load(nl, N, d, load):
    """Connect input-device drain `d` to VOUT1 through a load; returns nothing."""
    if load == "R":
        nl.append(["RL", "VDD", d, "resistor"])
        nl.append(["Cout", d, "VOUT1", "capacitor"])
    elif load == "tank":
        nl.append(["Ld", "VDD", d, "inductor"])
        nl.append(["Ctnk", "VDD", d, "capacitor"])
        nl.append(["Cout", d, "VOUT1", "capacitor"])
    elif load == "tapped":                       # gain-capable matched (Gate G4)
        tap = N.new()
        nl.append(["Ld", "VDD", d, "inductor"])
        nl.append(["Ct1", d, tap, "capacitor"])
        nl.append(["Ct2", tap, "VSS", "capacitor"])
        nl.append(["Cout", tap, "VOUT1", "capacitor"])
    elif load == "shunt_peak":                   # RL + series L -> bandwidth extension
        p = N.new()                              # (wideband family, WP-BROADEN)
        nl.append(["RL", "VDD", p, "resistor"])
        nl.append(["Lpk", p, d, "inductor"])     # shunt-peaking inductor in series w/ RL
        nl.append(["Cout", d, "VOUT1", "capacitor"])


def _maybe_cascode(nl, N, d, cascode):
    """Insert a cascode NMOS above drain `d`; return the new drain node."""
    if not cascode:
        return d
    d2 = N.new()
    nl.append(["Mc", d2, "VDD", d, "VSS", "nmos4"])   # D G S B; gate AC-grounded
    return d2


def _maybe_buffer(nl, N, out):
    """Source-follower buffer driving VOUT1 from node `out`; else out==VOUT1."""
    src = N.new()
    nl.append(["Mb", "VDD", out, src, "VSS", "nmos4"])   # common-drain
    nl.append(["Rb", src, "VSS", "resistor"])            # tail
    nl.append(["Cob", src, "VOUT1", "capacitor"])


# --------------------------------------------------------------- archetypes
def cs_lna(gate_ind, degen, cex, cascode, load, buffer):
    """Inductively-degenerated common-source LNA (narrowband family)."""
    nl, N = [], Nets()
    gin = N.new()
    nl.append(["Cin", "VIN1", gin, "capacitor"])
    g = gin
    if gate_ind:
        g = N.new()
        nl.append(["Lg", gin, g, "inductor"])
    s = N.new() if degen else "VSS"
    d = N.new()
    nl.append(["M1", d, g, s, "VSS", "nmos4"])
    if degen:
        nl.append(["Ls", s, "VSS", "inductor"])
    if cex:
        nl.append(["Cex", g, s, "capacitor"])
    d = _maybe_cascode(nl, N, d, cascode)
    if buffer:
        _add_load_to_buffer(nl, N, d, load)
    else:
        _add_load(nl, N, d, load)
    return nl


def _add_load_to_buffer(nl, N, d, load):
    """Load resolves to an internal node, then a source-follower drives VOUT1."""
    out = N.new()
    if load == "tapped":
        tap = N.new()
        nl.append(["Ld", "VDD", d, "inductor"])
        nl.append(["Ct1", d, tap, "capacitor"])
        nl.append(["Ct2", tap, "VSS", "capacitor"])
        nl.append(["Cob0", tap, out, "capacitor"])
    elif load == "tank":
        nl.append(["Ld", "VDD", d, "inductor"])
        nl.append(["Ctnk", "VDD", d, "capacitor"])
        nl.append(["Cob0", d, out, "capacitor"])
    else:
        nl.append(["RL", "VDD", d, "resistor"])
        nl.append(["Cob0", d, out, "capacitor"])
    _maybe_buffer(nl, N, out)


def cg_lna(load, cascode):
    """Common-gate LNA (inductorless input match; wideband family)."""
    nl, N = [], Nets()
    s = N.new()
    nl.append(["Cin", "VIN1", s, "capacitor"])
    nl.append(["Lin", s, "VSS", "inductor"])          # source shunt-peak / bias path
    d = N.new()
    nl.append(["M1", d, "VDD", s, "VSS", "nmos4"])     # gate to VDD (AC-grounded)
    d = _maybe_cascode(nl, N, d, cascode)
    _add_load(nl, N, d, load)
    return nl


def rfb_lna(load, buffer=False, cascode=False):
    """Resistive shunt-feedback LNA (inductorless; wideband family). Optional
    source-follower buffer isolates the load from the feedback loop (WP-BROADEN)."""
    nl, N = [], Nets()
    g = N.new()
    nl.append(["Cin", "VIN1", g, "capacitor"])
    d = N.new()
    nl.append(["M1", d, g, "VSS", "VSS", "nmos4"])
    d = _maybe_cascode(nl, N, d, cascode)
    nl.append(["Rf", d, g, "resistor"])                # shunt feedback (around the gain core)
    ld = "R" if load == "tapped" else load             # feedback matches, not LC resonance
    if buffer:
        _add_load_to_buffer(nl, N, d, ld)
    else:
        _add_load(nl, N, d, ld)
    return nl


# --------------------------------------------------- gain-boosted (gps-l1) family
def cs_cs_lna(degen, load1, load2, buffer):
    """Two-stage common-source LNA (WP-BROADEN gain-boosted family for gps-l1:
    cascaded gm clears S21 >= 15 dB where single-stage cascode+tapped tops ~14 dB).
    Input match on stage 1 only (gate inductor + optional degeneration); stage-1
    resonant load feeds stage 2 through a coupling cap; stage 2 drives the output."""
    nl, N = [], Nets()
    gin = N.new()
    nl.append(["Cin", "VIN1", gin, "capacitor"])
    g1 = N.new()
    nl.append(["Lg1", gin, g1, "inductor"])            # input match (gate inductor)
    s1 = N.new() if degen else "VSS"
    d1 = N.new()
    nl.append(["M1", d1, g1, s1, "VSS", "nmos4"])
    if degen:
        nl.append(["Ls1", s1, "VSS", "inductor"])
    if load1 == "tapped":                              # stage-1 load -> internal node n1
        tap = N.new()
        nl.append(["Ld1", "VDD", d1, "inductor"])
        nl.append(["Ct1a", d1, tap, "capacitor"])
        nl.append(["Ct1b", tap, "VSS", "capacitor"])
        n1 = tap
    else:                                              # "tank"
        nl.append(["Ld1", "VDD", d1, "inductor"])
        nl.append(["Ctnk1", "VDD", d1, "capacitor"])
        n1 = d1
    g2 = N.new()
    nl.append(["Cc", n1, g2, "capacitor"])             # inter-stage coupling (DC block)
    d2 = N.new()
    nl.append(["M2", d2, g2, "VSS", "VSS", "nmos4"])   # stage-2 CS (g2 auto-biased)
    if buffer:
        _add_load_to_buffer(nl, N, d2, load2)
    else:
        _add_load(nl, N, d2, load2)
    return nl


def current_reuse_lna(load, degen):
    """Complementary current-reuse LNA (WP-BROADEN gain-boosted family for gps-l1's
    Idd <= 3 mA cap: NMOS and PMOS share one bias current with gm_n + gm_p summed at
    the shared drain -> gain at half the current a single device would draw). The
    output resonator is DC-blocked (Cblk) so it can't short the self-biased drain."""
    nl, N = [], Nets()
    gin = N.new()
    nl.append(["Cin", "VIN1", gin, "capacitor"])
    g = N.new()
    nl.append(["Lg", gin, g, "inductor"])              # input match (shared gate)
    out = N.new()
    sN = N.new() if degen else "VSS"
    nl.append(["Mn", out, g, sN, "VSS", "nmos4"])      # NMOS: drain=out, source=VSS
    if degen:
        nl.append(["Lsn", sN, "VSS", "inductor"])
    nl.append(["Mp", out, g, "VDD", "VDD", "pmos4"])   # PMOS: drain=out, source=VDD
    r = N.new()                                        # DC-isolated resonant output
    nl.append(["Cblk", out, r, "capacitor"])
    nl.append(["Lr", r, "VSS", "inductor"])
    nl.append(["Cr", r, "VSS", "capacitor"])
    if load == "tapped":
        tap = N.new()
        nl.append(["Cto", r, tap, "capacitor"])
        nl.append(["Cout", tap, "VOUT1", "capacitor"])
    else:                                              # "tank"
        nl.append(["Cout", r, "VOUT1", "capacitor"])
    return nl


def rfb_cs_lna(load2, cascode1=False, buffer=False, cascode2=False):
    """Blind-v1 (WP-DHRUVA rule-2, generic textbook): broadband-match + tuned-gain
    two-stage. Stage 1 is a resistive shunt-feedback CS, so the input match is set
    by feedback and holds S11 over a WIDE band (not just one f0); stage 2 is a
    tuned/tapped CS whose inductive tank peaks the gain at f0. The pair supplies the
    match-over-band + high-tuned-gain shape that every single-stage nb family misses
    (they all sized to s11_max ~ 0 on dhruva-l1). Chosen from the measured failure
    mode -- NOT from any paper's circuit (blind protocol, 08-DHRUVA rule 2).

    cascode2 puts the cascode on STAGE 2 (gain boost that does NOT touch the stage-1
    feedback match) -- the fix for the observed tradeoff where a stage-1 cascode
    (cascode1) lifted gain but wrecked s11_max. Enable at most one of cascode1/
    cascode2 (both name the device 'Mc')."""
    nl, N = [], Nets()
    g1 = N.new()
    nl.append(["Cin", "VIN1", g1, "capacitor"])
    d1 = N.new()
    nl.append(["M1", d1, g1, "VSS", "VSS", "nmos4"])
    d1 = _maybe_cascode(nl, N, d1, cascode1)          # optional stage-1 cascode (inside fb loop)
    nl.append(["Rf", d1, g1, "resistor"])             # shunt feedback -> broadband match + self-bias
    nl.append(["RL1", "VDD", d1, "resistor"])         # stage-1 R load (keeps match broadband)
    g2 = N.new()
    nl.append(["Cc", d1, g2, "capacitor"])            # inter-stage DC-block coupling
    d2 = N.new()
    nl.append(["M2", d2, g2, "VSS", "VSS", "nmos4"])  # stage-2 CS (g2 auto-biased)
    d2 = _maybe_cascode(nl, N, d2, cascode2)          # stage-2 cascode: gain w/o disturbing match
    if buffer:
        _add_load_to_buffer(nl, N, d2, load2)         # load2 in {tank, tapped}
    else:
        _add_load(nl, N, d2, load2)
    return nl


def rfb_cs3_lna(load3, cascode2=False, buffer=False):
    """Blind-v1 (WP-DHRUVA rule-2, generic textbook): 3-stage broadband-match +
    tuned-gain. rfb input (S11 held over band) -> tuned CS -> tuned CS. The 2-stage
    rfb_cs came within ~1.6 dB of dhruva-l1's 25.4 dB gain while holding s11_max
    <= -10, but pushing that last gain out of ONE tuned stage loaded the stage-1
    feedback match. A third tuned stage splits the gain (each stage ~10-12 dB), so
    the match-setting stage-1 is left undisturbed. Chosen from the measured Pareto
    edge -- NOT from any paper (08-DHRUVA rule 2)."""
    nl, N = [], Nets()
    g1 = N.new(); nl.append(["Cin", "VIN1", g1, "capacitor"])
    d1 = N.new(); nl.append(["M1", d1, g1, "VSS", "VSS", "nmos4"])
    nl.append(["Rf", d1, g1, "resistor"])             # broadband match + self-bias
    nl.append(["RL1", "VDD", d1, "resistor"])
    g2 = N.new(); nl.append(["Cc1", d1, g2, "capacitor"])
    d2 = N.new(); nl.append(["M2", d2, g2, "VSS", "VSS", "nmos4"])
    d2 = _maybe_cascode(nl, N, d2, cascode2)          # stage-2 gain (optional cascode)
    nl.append(["Ld2", "VDD", d2, "inductor"])         # stage-2 tuned tank
    nl.append(["Ctnk2", "VDD", d2, "capacitor"])
    g3 = N.new(); nl.append(["Cc2", d2, g3, "capacitor"])
    d3 = N.new(); nl.append(["M3", d3, g3, "VSS", "VSS", "nmos4"])  # stage-3 tuned
    if buffer:
        _add_load_to_buffer(nl, N, d3, load3)         # load3 in {tank, tapped} -> VOUT1
    else:
        _add_load(nl, N, d3, load3)
    return nl


# --------------------------------------------------------------- enumeration
def archetypes():
    """Yield (name, netlist, spec, band) for every distinct valid, screen-passing
    archetype (deduped by WL-hash)."""
    seen = set()
    specs = {"nb": "wifi24", "wb": "wideband-sdr"}
    combos = []
    # narrowband CS family: the workhorse, incl. the tapped-C gain-capable arm
    for gate_ind in (True, False):
        for degen in (True, False):
            for cex in (True, False):
                for cascode in (False, True):
                    for load in ("R", "tank", "tapped"):
                        for buffer in (False, True):
                            if not (gate_ind or degen or load in ("tank", "tapped")):
                                continue                # need an inductor for NB
                            combos.append(("nb",
                                f"cs_gi{int(gate_ind)}_dg{int(degen)}_cx{int(cex)}"
                                f"_cc{int(cascode)}_{load}_bf{int(buffer)}",
                                cs_lna(gate_ind, degen, cex, cascode, load, buffer)))
    # gain-boosted narrowband family (WP-BROADEN, unlocks gps-l1: S21 >= 15 @ Idd <= 3)
    for degen in (True, False):
        for load1 in ("tank", "tapped"):
            for load2 in ("R", "tank", "tapped"):
                for buffer in (False, True):
                    combos.append(("nb",
                        f"cscs_dg{int(degen)}_{load1}-{load2}_bf{int(buffer)}",
                        cs_cs_lna(degen, load1, load2, buffer)))
    for load in ("tank", "tapped"):
        for degen in (False, True):
            combos.append(("nb", f"creuse_{load}_dg{int(degen)}",
                           current_reuse_lna(load, degen)))
    # blind-v1 broadband-match + tuned-gain two-stage (WP-DHRUVA rule-2, generic
    # textbook): rfb input stage (S11 held over band) -> tuned stage-2 (gain peaked
    # at f0). Targets the dhruva s11_max wall no single-stage nb family clears.
    for load2 in ("tank", "tapped"):
        for cascode1 in (False, True):
            for buffer in (False, True):
                combos.append(("nb",
                    f"rfbcs_{load2}_cc{int(cascode1)}_bf{int(buffer)}",
                    rfb_cs_lna(load2, cascode1, buffer)))
    # stage-2 cascode variants: gain boost that leaves the stage-1 feedback match
    # intact (the tradeoff fix -- stage-1 cascode wrecked s11_max). rfbcs_*_s2_*.
    for load2 in ("tank", "tapped"):
        for buffer in (False, True):
            combos.append(("nb",
                f"rfbcs_{load2}_s2_bf{int(buffer)}",
                rfb_cs_lna(load2, cascode1=False, buffer=buffer, cascode2=True)))
    # 3-stage rfb -> tuned -> tuned: gain headroom to clear dhruva-l1's 25.4 dB
    # while stage-1 holds the broadband match (the 2-stage Pareto capped ~1.6 dB
    # short). rfbcs3_*.
    for load3 in ("tank", "tapped"):
        for cascode2 in (False, True):
            for buffer in (False, True):
                combos.append(("nb",
                    f"rfbcs3_{load3}_cc2{int(cascode2)}_bf{int(buffer)}",
                    rfb_cs3_lna(load3, cascode2=cascode2, buffer=buffer)))
    # wideband inductorless family (WP-BROADEN, unlocks wideband-sdr: broadband S11)
    for load in ("R", "tank", "shunt_peak"):
        for cascode in (False, True):
            combos.append(("wb", f"cg_{load}_cc{int(cascode)}", cg_lna(load, cascode)))
    for load in ("R", "tank", "shunt_peak"):
        for buffer in (False, True):
            for cascode in (False, True):
                combos.append(("wb",
                    f"rfb_{load}_bf{int(buffer)}_cc{int(cascode)}",
                    rfb_lna(load, buffer, cascode)))

    from spec import Spec
    screens = {k: Spec.load(v) for k, v in specs.items()}
    for cls, name, nl in combos:
        seq = emit_sequence(nl)
        if seq is None:
            continue
        topo = Topology(seq)
        if not topo.valid:
            continue
        ok, _ = screens[cls].structural_screen(topo)
        if not ok:
            continue
        h = wl_features(topo)[0]
        if h in seen:
            continue
        seen.add(h)
        yield {"name": name, "cls": cls, "spec": specs[cls], "seq": seq,
               "wl": h, "n_dev": topo.n_devices, "netlist": nl}


# ------------------------------------------------------------------------ CLI
def _emit_dir(directory):
    os.makedirs(directory, exist_ok=True)
    meta = []
    arche = list(archetypes())
    for i, a in enumerate(arche):
        fn = f"seq{i:04d}.txt"
        with open(os.path.join(directory, fn), "w", encoding="utf-8",
                  newline="\n") as fh:
            fh.write("->".join(a["seq"]))
        meta.append({"file": fn, "name": a["name"], "cls": a["cls"],
                     "spec": a["spec"], "wl_hash": a["wl"], "n_dev": a["n_dev"]})
    with open(os.path.join(directory, "meta.json"), "w", encoding="utf-8",
              newline="\n") as fh:
        json.dump({"arm": "templates_p5", "meta": meta}, fh, indent=2)
    print(f"wrote {len(arche)} archetypes to {directory}")
    return len(arche)


def emit_winners(path, spec_names=("wifi24",), top_q=0.25):
    """Stage-3 Loop B (04-SELF-IMPROVE §2): the generator's own winners as training
    rows. Winners = feasible + top-quartile-by-sized-scalar near-feasible token
    topologies from the store (TRUE SPICE numbers only -- critic scores never
    select training data). Eulerian-augmented; feasible ones oversampled 2x. Writes
    JSON the GPU fine-tune reads (augmentation needs pandas; training does not).

    Multi-spec (WP-D2 / HANDOVER pri-3): winners are ranked PER spec and drawn only
    from rows sized against THAT spec -- a row's metrics live at its own spec's
    frequency, so a wifi24 (2.44 GHz) row is never re-scored under, say, dhruva-l1's
    1.575 GHz objective. Each winner's class token is the spec's band class
    (`wb` if the spec allows inductorless input, else `nb`), so the `<LNA_WB>` /
    `<LNA_NB>` channels are reinforced from the right pools. Sequences are deduped
    across specs (first spec that yields a seq wins its class)."""
    sys.path.insert(0, HERE)
    import datastore as ds
    from spec import Spec
    if isinstance(spec_names, str):
        spec_names = [s for s in spec_names.split(",") if s]
    all_rows = list(ds.load("topo_labels"))
    rows, n_feas, seen_seq, per_spec = [], 0, set(), {}
    for spec_name in spec_names:
        spec = Spec.load(spec_name)
        cls = "wb" if spec.allow_inductorless else "nb"
        scored = []
        for r in all_rows:
            if r.get("spec") != spec_name:            # only rows sized vs THIS spec
                continue
            toks = (r.get("graph") or {}).get("tokens")
            m = r.get("metrics")
            if toks and m:
                scored.append((spec.objective(m), bool(r.get("feasible")), toks))
        scored.sort(key=lambda x: x[0])               # lower objective = better
        keep = scored[:max(1, int(top_q * len(scored)))] if scored else []
        added = 0
        for _, feas, toks in keep:
            nl, ports = topo_to_netlist(Topology(toks))
            if nl is None:
                continue
            n_feas += int(feas)
            for seq in augment(nl, ports, max_solutions=10, run_num=2) * (2 if feas else 1):
                key = tuple(seq)                      # augment yields token lists
                if key in seen_seq:
                    continue
                seen_seq.add(key)
                rows.append({"cls": cls, "seq": seq, "feasible": feas})
                added += 1
        per_spec[spec_name] = {"pool": len(scored), "winners": len(keep),
                               "rows": added, "cls": cls}
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"rows": rows}, fh)
    brk = "; ".join(f"{s}:{d['winners']}w->{d['rows']}r[{d['cls']}]"
                    for s, d in per_spec.items())
    print(f"wrote {len(rows)} augmented winner rows ({n_feas} feasible-derived) "
          f"-> {path}\n  per-spec: {brk}")
    return len(rows)


def _emit_train(path):
    """Pre-generate Eulerian-augmented template rows for the P5 fine-tune (run
    under a pandas-capable python; the GPU training env has torch but not pandas,
    so augmentation and training are decoupled through this file)."""
    rows, n_arch = [], 0
    for k, a in enumerate(archetypes()):
        n_arch += 1
        for seq in augment(a["netlist"]):
            rows.append({"arch": k, "cls": a["cls"], "seq": seq})
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"n_archetypes": n_arch, "rows": rows}, fh)
    print(f"wrote {len(rows)} augmented rows from {n_arch} archetypes -> {path} "
          f"(mean {len(rows)/max(n_arch,1):.1f} augmentations/archetype)")
    return len(rows)


def main():
    ap = argparse.ArgumentParser(description="P5 archetype generator (stratum T)")
    ap.add_argument("--list", action="store_true", help="print distinct archetypes")
    ap.add_argument("--emit-dir", metavar="DIR", help="write seq*.txt + meta.json")
    ap.add_argument("--emit-train", metavar="PATH",
                    help="write Eulerian-augmented rows (JSON) for the P5 fine-tune")
    ap.add_argument("--emit-winners", metavar="PATH",
                    help="write augmented winner rows (JSON) for Stage-3 Loop B")
    ap.add_argument("--winners-specs", default="wifi24",
                    help="comma list of specs to draw winners from (per-spec, "
                         "correct-frequency; class token = band class)")
    args = ap.parse_args()
    if args.emit_winners:
        return 0 if emit_winners(args.emit_winners, args.winners_specs) else 1
    if args.emit_train:
        return 0 if _emit_train(args.emit_train) else 1
    if args.emit_dir:
        return 0 if _emit_dir(args.emit_dir) else 1
    if args.list:
        arche = list(archetypes())
        nb = sum(a["cls"] == "nb" for a in arche)
        print(f"{len(arche)} distinct valid screen-passing archetypes "
              f"({nb} narrowband / {len(arche) - nb} wideband)")
        for a in arche:
            print(f"  {a['name']:<34} {a['cls']}  {a['spec']:<13} "
                  f"n_dev={a['n_dev']} wl={a['wl'][:10]}")
        return 0
    ap.error("give --list or --emit-dir DIR")


if __name__ == "__main__":
    sys.exit(main())

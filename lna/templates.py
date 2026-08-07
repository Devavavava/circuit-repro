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


def rfb_lna(load):
    """Resistive shunt-feedback LNA (inductorless; wideband family)."""
    nl, N = [], Nets()
    g = N.new()
    nl.append(["Cin", "VIN1", g, "capacitor"])
    d = N.new()
    nl.append(["M1", d, g, "VSS", "VSS", "nmos4"])
    nl.append(["Rf", d, g, "resistor"])                # shunt feedback
    _add_load(nl, N, d, "R" if load == "tapped" else load)
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
    # wideband inductorless family
    for load in ("R", "tank"):
        for cascode in (False, True):
            combos.append(("wb", f"cg_{load}_cc{int(cascode)}", cg_lna(load, cascode)))
    for load in ("R", "tank"):
        combos.append(("wb", f"rfb_{load}", rfb_lna(load)))

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
    args = ap.parse_args()
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

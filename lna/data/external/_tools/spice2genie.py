"""Convert real SPICE netlists into AnalogGenie's Dataset format.

AnalogGenie stores each circuit as a flat, value-free netlist plus a port list:

    Dataset/1791/1791.cir       MM10 (net27 net12 VSS VSS) nmos4
    Dataset/1791/Port1791.txt   VDD VSS VIN1 VIN2 VOUT1 VB1 VB2 VB3

`SPICE2GRAPH_compress.py` then turns that into an adjacency matrix in which the
*ports* become graph nodes and every other net is collapsed: all pins sharing an
unnamed net are wired pairwise instead. So the port list is not cosmetic -- it
decides which nets survive as tokens the transformer can emit.

Three things a converted circuit must satisfy, all checked by `convert()`:

  * every port name is in AnalogGenie's fixed vocabulary (Pretrain.py builds it
    inline; `lna/genie_common.py` mirrors it). An unknown port name would be an
    out-of-vocabulary token and `Pretrain.py` would die in `encode`.
  * per-type device counts stay under the vocabulary caps (34 NMOS, 34 PMOS,
    27 R, 15 C, 23 L, 7 diodes, 26 NPN, 26 PNP).
  * the graph is connected and has at most 512 edges. `Augmentation.py` walks
    every edge in *both* directions, so its path is 2|E|+1 long and gets padded
    to 1025 -- more than 512 edges cannot be stored. Connectivity matters
    because the walk starts at VSS and must reach every edge.

Sources handled so far are flat sky130 subcircuits (AnalogGym) and hierarchical
auCdl netlists with `.SUBCKT`/instance nesting (ALIGN), hence the flattener.
"""
import math
import os
import re
from collections import defaultdict

# ── Vocabulary limits, mirrored from AnalogGenie/repo/Pretrain.py ──────────────
# Keyed by the type string that goes in the .cir line. The value is the largest
# index the tokenizer knows, i.e. how many of that device a circuit may contain.
DEVICE_CAPS = {
    "nmos4": 34, "pmos4": 34, "npn": 26, "pnp": 26,
    "resistor": 27, "capacitor": 15, "inductor": 23, "diode": 7,
}

# Pin counts per type, in the order SPICE2GRAPH_compress.py expects them.
DEVICE_PINS = {
    "nmos4": 4, "pmos4": 4,      # D G S B
    "npn": 3, "pnp": 3,          # C B E
    "resistor": 2, "capacitor": 2, "inductor": 2, "diode": 2,
}

# How many of each port token the vocabulary has (VIN1..VIN10 etc).
PORT_CAPS = {"VIN": 10, "VOUT": 6, "VB": 10, "IB": 6, "VCM": 2, "VREF": 2}

MAX_EDGES = 512          # 2|E|+1 <= 1025, the Sequence_total padding width

# ── Net-name classification ───────────────────────────────────────────────────
# Real netlists spell the same node a dozen ways: vdd, vdd!, VDDA, avdd, vdd_ota.
# Normalise first (lowercase, drop Cadence's '!' and a trailing block suffix),
# then match. Order matters: supplies before everything else, because a net
# called "vdda" must not be read as a "vd" input.
_SUFFIX = re.compile(r"_(ota|amp|core|top|ldo|buf)$")


def normalise(net):
    n = net.strip().lower().rstrip("!")
    return _SUFFIX.sub("", n)


_SUPPLY_HI = re.compile(r"^(vdd|vcc|avdd|dvdd|vpwr|vddio)[ad]?[0-9]*$")
_SUPPLY_LO = re.compile(r"^(vss|gnd|agnd|dgnd|vgnd)[ad]?[0-9]*$|^0$")
_INPUT = re.compile(r"^(v?in|vi)(p|n|m|put)?[0-9]*$")
_OUTPUT = re.compile(r"^(v?out|vo)(p|n|put)?[0-9]*$")
_VBIAS = re.compile(r"^(v?bias[np]?|vb)[0-9]*$")
_IBIAS = re.compile(r"^(i?bias|iref|id|ibias[np]?)[0-9]*$")
_VCM = re.compile(r"^(vcm|vcmfb|vref_cm)[0-9]*$")
_VREF = re.compile(r"^(vref|vrefp|vrefn)[0-9]*$")


def classify(net):
    """Return the AnalogGenie port family for a net, or None if it is internal."""
    n = normalise(net)
    if _SUPPLY_HI.match(n):
        return "VDD"
    if _SUPPLY_LO.match(n):
        return "VSS"
    if _VCM.match(n):
        return "VCM"
    if _VREF.match(n):
        return "VREF"
    if _INPUT.match(n):
        return "VIN"
    if _OUTPUT.match(n):
        return "VOUT"
    if _VBIAS.match(n):
        return "VB"
    if _IBIAS.match(n):
        return "IB"
    return None


class ConversionError(Exception):
    """Raised when a netlist cannot be represented in AnalogGenie's format."""


def find_repo():
    """Locate the AnalogGenie checkout.

    `AnalogGenie/repo/` is gitignored here (see the repo README -- upstream
    clones are re-created by scripts/fetch_upstream.sh, not vendored), so it is
    absent from a git worktree even though it sits beside the main checkout.
    Walk up until we find it, and let ANALOGGENIE_REPO override.
    """
    env = os.environ.get("ANALOGGENIE_REPO")
    if env:
        return os.path.abspath(env)
    here = os.path.dirname(os.path.abspath(__file__))
    for base in (here, os.getcwd()):
        d = base
        while True:
            cand = os.path.join(d, "AnalogGenie", "repo")
            if os.path.isdir(cand):
                return cand
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    return os.path.join(os.path.dirname(here), "AnalogGenie", "repo")


# ── SPICE parsing ─────────────────────────────────────────────────────────────
def read_lines(text):
    """Strip comments and join '+' continuations into logical lines."""
    out = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith(("*", "$", "//")):
            continue
        line = re.split(r"[;$]", line)[0]        # inline comment
        if not line.strip():
            continue
        if line.lstrip().startswith("+") and out:
            out[-1] += " " + line.lstrip()[1:].strip()
        else:
            out.append(line.strip())
    return out


def _is_param(tok):
    return "=" in tok


def _model_kind(model):
    """Map a SPICE model/subckt name onto an AnalogGenie device type."""
    m = model.lower()
    if "pfet" in m or "pmos" in m or m.startswith("p"):
        return "pmos4"
    if "nfet" in m or "nmos" in m or m.startswith("n"):
        return "nmos4"
    return None


class Subckt:
    def __init__(self, name, ports):
        self.name = name
        self.ports = ports
        self.devices = []        # (kind, nets)
        self.instances = []      # (subckt_name, actual_nets)
        self.sources = []        # independent current sources, as (net, net)


def parse(text):
    """Split a netlist into its `.subckt` definitions plus the top-level deck.

    Net names are lowercased throughout: SPICE is case-insensitive, and real
    decks rely on that -- AnalogGym declares `.subckt ... gnda` and then writes
    `GNDA` on every device line. Keeping the raw spelling would make those two
    distinct nets and silently tear the circuit in half.
    """
    subckts, globals_ = {}, set()
    top = Subckt("__top__", [])
    cur = top

    for line in read_lines(text):
        tok = line.split()
        head = tok[0].lower()

        if head in (".subckt", ".subcircuit"):
            cur = Subckt(tok[1].lower(), [p.lower() for p in tok[2:]])
            subckts[tok[1].lower()] = cur
            continue
        if head == ".ends":
            cur = top
            continue
        if head in (".global", "*.global"):
            globals_.update(t.lower() for t in tok[1:])
            continue
        if head.startswith("."):                  # .model .param .include .end ...
            continue
        if head.startswith("*"):
            continue

        cur_body = cur
        c = head[0]
        low = [t.lower() for t in tok]

        if c == "m":
            kind = _model_kind(low[5] if len(low) > 5 else "")
            if kind is None:
                continue
            cur_body.devices.append((kind, low[1:5]))
        elif c == "x":
            # Either a subckt instance (name is the last non-parameter token) or
            # a PDK transistor modelled as a subckt (sky130 writes `xm3 D G S B model ...`).
            plain = [t for t in low[1:] if not _is_param(t)]
            if not plain:
                continue
            tail = plain[-1]
            if tail in subckts:
                cur_body.instances.append((tail, plain[:-1]))
            elif len(plain) >= 5 and _model_kind(plain[4]):
                cur_body.devices.append((_model_kind(plain[4]), plain[:4]))
            else:
                # Forward reference to a subckt defined later in the file.
                cur_body.instances.append((tail, plain[:-1]))
        elif c in "rcl":
            kind = {"r": "resistor", "c": "capacitor", "l": "inductor"}[c]
            cur_body.devices.append((kind, low[1:3]))
        elif c == "d":
            cur_body.devices.append(("diode", low[1:3]))
        elif c == "q":
            model = low[4] if len(low) > 4 else ""
            cur_body.devices.append(("pnp" if "pnp" in model else "npn", low[1:4]))
        elif c == "i":
            cur_body.sources.append(low[1:3])
        # Voltage sources and everything else are dropped: AnalogGenie has no
        # token for them, and in a circuit (as opposed to testbench) netlist they
        # only appear as supplies, whose nets are already ports.

    return subckts, top, globals_


def flatten(top, subckts, globals_):
    """Expand instances depth-first, renaming each subckt's private nets."""
    devices, sources = [], []
    counter = [0]

    def is_global(net):
        return net in globals_ or classify(net) in ("VDD", "VSS")

    def resolve(binding, nets):
        return [n if is_global(n) else binding.get(n, n) for n in nets]

    def walk(block, binding, depth):
        if depth > 25:
            raise ConversionError("subcircuit nesting deeper than 25 -- probably recursive")
        for kind, nets in block.devices:
            devices.append((kind, resolve(binding, nets)))
        for nets in block.sources:
            sources.append(resolve(binding, nets))
        for name, actuals in block.instances:
            child = subckts.get(name)
            if child is None:
                raise ConversionError(f"instance of undefined subcircuit {name!r}")
            if len(actuals) != len(child.ports):
                raise ConversionError(
                    f"{name}: {len(actuals)} actuals for {len(child.ports)} ports")
            counter[0] += 1
            prefix = f"x{counter[0]}_"
            resolved = [binding.get(a, a) if not is_global(a) else a for a in actuals]
            child_binding = dict(zip(child.ports, resolved))
            # Private nets of the child get prefixed so two instances don't merge.
            for kind, nets in child.devices:
                for n in nets:
                    if n not in child_binding and not is_global(n):
                        child_binding[n] = prefix + n
            for group in (child.sources, (a for _, a in child.instances)):
                for nets in group:
                    for n in nets:
                        if n not in child_binding and not is_global(n):
                            child_binding[n] = prefix + n
            walk(child, child_binding, depth + 1)

    walk(top, {}, 0)
    return devices, sources


# ── Port assignment and emission ──────────────────────────────────────────────
# Families promoted to ports even when the deck declares no port list. Supplies
# and signal I/O name the circuit's real interface, so their names can be
# trusted. VB/IB are deliberately excluded: in a self-biased block like ALIGN's
# full_OTA the bias net is generated on-chip by an included mirror, so it is an
# internal node, not a pin. It still becomes a port when explicitly declared.
INFERRED_FAMILIES = ("VDD", "VSS", "VIN", "VOUT", "VCM", "VREF")


def assign_ports(devices, declared=None, sources=None):
    """Choose which nets become AnalogGenie port tokens.

    `declared` is the subcircuit's own port list when the source has one; those
    nets are the circuit's real interface and are mapped first. Any other net
    whose *name* says it is a supply or signal pin is also promoted -- sky130
    blocks reference vdd!/gnd! directly instead of listing them as ports, and
    ALIGN's top-level decks are bare instantiations with no port list at all.
    """
    used = {n for _, nets in devices for n in nets}
    declared = [d for d in (declared or []) if d in used]

    family_of = {}
    for net in declared:
        fam = classify(net)
        if fam:
            family_of[net] = fam

    # Only guess at the interface when the source did not state one. A declared
    # port list is authoritative: AnalogGym's Leung_NMCF names its pins
    # `gnda vdda vinn vinp vout` and *also* has an internal node called VOUTN,
    # which is a first-stage output, not a second circuit output.
    for net in sorted(used):
        if net in family_of:
            continue
        fam = classify(net)
        if fam in ("VDD", "VSS") or (not declared and fam in INFERRED_FAMILIES):
            family_of[net] = fam

    # An independent current source is not a device AnalogGenie can name, but
    # the node it drives is a bias-current input -- which the vocabulary does
    # have (IB1..IB6). Promote that node and drop the source itself.
    for a, b in (sources or []):
        for terminal in (a, b):
            if terminal in used and classify(terminal) not in ("VDD", "VSS"):
                family_of.setdefault(terminal, "IB")

    mapping, counters = {}, defaultdict(int)
    # Deterministic order: declared ports first in their declared order, then the
    # rest alphabetically, so re-running the converter reproduces the same names.
    ordered = declared + sorted(n for n in family_of if n not in declared)
    for net in ordered:
        fam = family_of[net]
        if fam in ("VDD", "VSS"):
            mapping[net] = fam
            continue
        counters[fam] += 1
        idx = counters[fam]
        if idx > PORT_CAPS[fam]:
            raise ConversionError(f"more than {PORT_CAPS[fam]} {fam} ports")
        mapping[net] = f"{fam}{idx}"
    return mapping


def graph_stats(devices, mapping):
    """Edge count and connectivity of the compressed graph, without building it.

    Mirrors SPICE2GRAPH_compress.py: a device node joins each of its pins; pins
    on a port net join that port node; pins sharing an internal net join pairwise.
    """
    pins_on_net = defaultdict(list)
    for di, (kind, nets) in enumerate(devices):
        for pi, net in enumerate(nets):
            pins_on_net[net].append((di, pi))

    edges = sum(len(nets) for _, nets in devices)
    for net, pins in pins_on_net.items():
        if net in mapping:
            edges += len(pins)
        else:
            edges += len(pins) * (len(pins) - 1) // 2

    # Union-find over device nodes; two devices are joined by any shared net,
    # and ports tie together everything attached to them.
    parent = list(range(len(devices)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for pins in pins_on_net.values():
        for (d0, _), (d1, _) in zip(pins, pins[1:]):
            union(d0, d1)

    connected = len({find(i) for i in range(len(devices))}) <= 1
    return edges, connected


def emit(devices, mapping):
    """Render the .cir body and the Port#.txt line."""
    counters = defaultdict(int)
    prefix = {"nmos4": "M", "pmos4": "M", "npn": "Q", "pnp": "Q", "resistor": "R",
              "capacitor": "C", "inductor": "L", "diode": "D"}
    lines = []
    for kind, nets in devices:
        # Count per prefix letter, not per kind, so an NMOS and a PMOS never
        # share a name. SPICE2GRAPH_compress.py ignores these names entirely --
        # it re-indexes by type -- but duplicates make the .cir hard to read.
        counters[prefix[kind]] += 1
        name = f"{prefix[kind]}{counters[prefix[kind]]}"
        renamed = [mapping.get(n, n) for n in nets]
        lines.append(f"{name} ({' '.join(renamed)}) {kind}")

    ports = []
    for p in dict.fromkeys(mapping.values()):
        ports.append(p)
    # VDD/VSS first, matching how the shipped Port#.txt files read.
    ports.sort(key=lambda p: (p not in ("VDD", "VSS"), p != "VDD", p))
    return "\n".join(lines) + "\n", " ".join(ports)


def convert(text, declared_ports=None, name="<netlist>"):
    """SPICE text -> (cir_text, port_line, stats). Raises ConversionError."""
    subckts, top, globals_ = parse(text)
    declared_ports = [p.lower() for p in declared_ports] if declared_ports else None

    # A file that is one bare `.subckt` with nothing instantiated at top level
    # (AnalogGym) should be converted as that subcircuit.
    if not top.devices and not top.instances:
        if len(subckts) != 1:
            raise ConversionError("no top-level devices and not exactly one subcircuit")
        only = next(iter(subckts.values()))
        top, declared_ports = only, declared_ports or only.ports

    devices, sources = flatten(top, subckts, globals_)
    if not devices:
        raise ConversionError("no devices found")

    counts = defaultdict(int)
    for kind, _ in devices:
        counts[kind] += 1
    for kind, n in counts.items():
        if n > DEVICE_CAPS[kind]:
            raise ConversionError(f"{n} {kind} exceeds vocabulary cap {DEVICE_CAPS[kind]}")

    for kind, nets in devices:
        if len(nets) != DEVICE_PINS[kind]:
            raise ConversionError(f"{kind} with {len(nets)} pins, expected {DEVICE_PINS[kind]}")

    mapping = assign_ports(devices, declared_ports, sources)
    if not any(v == "VSS" for v in mapping.values()):
        raise ConversionError("no VSS net -- Augmentation.py starts its walk there")

    edges, connected = graph_stats(devices, mapping)
    if not connected:
        raise ConversionError("device graph is disconnected")
    if edges > MAX_EDGES:
        raise ConversionError(f"{edges} edges exceeds {MAX_EDGES} (sequence would exceed 1025)")

    cir, ports = emit(devices, mapping)
    stats = {"devices": len(devices), "edges": edges, "seq_len": 2 * edges + 1,
             "counts": dict(counts), "ports": ports, "name": name}
    return cir, ports, stats


def convert_file(path, declared_ports=None):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return convert(fh.read(), declared_ports, name=os.path.basename(path))

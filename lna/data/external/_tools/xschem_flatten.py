"""Flatten a single, non-hierarchical xschem .sch schematic into a flat SPICE
deck that lna/data/external/_tools/spice2genie.py can convert.

Built for IHP's open-source SG13G2 tapeout schematics (xschem + the
sg13g2_pr PDK symbol library), to harvest the LNA designs that only ship a
schematic-capture file, not an already-flattened netlist (see
lna/data/reports/data-expansion-2026-08-09.md §2, "6 more real, license-clean
candidates identified but not yet converted").

How xschem stores a schematic (the parts this module needs):
  * `N x1 y1 x2 y2 {lab=NAME}`  -- a wire segment; NAME is xschem's own net
    label, already resolved (real name for a labelled/global net, `#netN`
    auto-generated for an internal one).
  * `C {symbol/path.sym} X Y ROT FLIP {name=I1 prop=val ...}` -- a component
    instance: symbol, placement (X,Y), rotation (0-3, units of 90 degrees),
    mirror flag (0/1), and its own instance properties.
  * A `.sym` file draws each pin as `B 5 x1 y1 x2 y2 {name=PIN ...}` -- a
    small box whose CENTER is the pin's electrical hotspot, in the symbol's
    own local coordinate system (rotation/mirror center is the local
    origin). `K {type=... format=...}` classifies the symbol's device kind.

Placement transform (local pin coords -> absolute, verified empirically
against a schematic with an already-known-correct flattened netlist -- see
`_calibrate_xschem_transform.py` and the `--selftest` golden test below;
independently matches xschem's own `ROTATION` macro in `src/xschem.h`):

    flip=0: rot 0,1,2,3 -> (x,y), (-y,x), (-x,-y), (y,-x)
    flip=1: rot 0,1,2,3 -> (-x,y), (-y,-x), (x,-y), (y,x)
    absolute = instance placement (X,Y) + the above

Net reconstruction does NOT trust the `lab=` text at face value (a
schematic harvested some other way might have inconsistent or absent
labels) -- it re-derives nets from geometry: every wire endpoint and every
device-pin absolute coordinate is a node in a union-find; two nodes union
iff they share a coordinate. A real (non "#net...") wire label, or a
net-name-binder component's own `lab=` (gnd/vdd/io-pin symbols carry a
single pin plus a `lab=` naming whatever it touches), is then used to name
the resulting net; internal nets left unlabelled get an auto-generated name.

Limitations (by design, not silently papered over):
  * Single-schematic only. A component whose symbol resolves to another
    LOCAL .sch file (hierarchy), rather than a PDK primitive recognised via
    `K {type=...}`, raises `FlattenError` rather than guessing.
  * Device kinds beyond resistor/capacitor/inductor/nmos/pmos/npn/pnp are
    not mapped; anything else (pads, ESD diodes, voltage sources, code/
    label/annotation symbols) is either dropped (matches how AnalogGenie's
    own dataset and this project's earlier IHP/ALIGN conversions already
    drop pads/ESD/sources) or, if unrecognised, raises rather than drops
    silently -- see UNHANDLED_IS_FATAL.

    python xschem_flatten.py --selftest
    python xschem_flatten.py top.sch --sym-dir xschem_syms/ -o out.spice
"""
import argparse
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LNA_DIR = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
sys.path.insert(0, LNA_DIR)

# ---- device-kind classification -------------------------------------------
# K{type=...} -> (AnalogGenie kind, spice element prefix). None = drop silently
# (process-level structures with no place in a topology-only netlist, same
# convention already used for the flat-SPICE IHP/ALIGN conversions).
KIND_MAP = {
    "res": ("resistor", "R"),
    "capacitor": ("capacitor", "C"),
    "inductor": ("inductor", "L"),
    "nmos": ("nmos4", "M"),
    "pmos": ("pmos4", "M"),
    "npn": ("npn", "Q"),
    "pnp": ("pnp", "Q"),
}
DROP_TYPES = {"pad", "diode", "vsource", "graph", "netlist_commands", "launcher"}
# net-name-binder symbols: exactly one pin, and their own `lab=` instance
# property names whatever net that pin touches (gnd/vdd/lab_pin/*pin*.sym).
BINDER_TYPES = {"label", "ipin", "opin", "iopin"}

PIN_LINE_RE = re.compile(r"^B 5 ([\d.eE+-]+) ([\d.eE+-]+) ([\d.eE+-]+) ([\d.eE+-]+) \{(.*)\}")
# Wire/component attribute blocks `{...}` can span multiple lines (seen in
# LNA_2.45G's circuit_lvs.sch, unlike GPS_LNA's single-line style) -- so both
# are matched with the same brace-counting approach as component props,
# rather than a single-line regex.
WIRE_HEAD_RE = re.compile(r"^N ([\d.eE+-]+) ([\d.eE+-]+) ([\d.eE+-]+) ([\d.eE+-]+) \{", re.M)
COMP_RE = re.compile(r"^C \{([^}]*)\} ([\d.eE+-]+) ([\d.eE+-]+) (\d+) (\d+) \{", re.M)


class FlattenError(Exception):
    pass


def parse_sym(text):
    kind = None
    m = re.search(r"K\s*\{[^}]*?type=(\S+)", text, re.S)
    if m:
        kind = m.group(1)
    pins = []
    for line in text.splitlines():
        m = PIN_LINE_RE.match(line.strip())
        if not m:
            continue
        x1, y1, x2, y2, attrs = m.groups()
        x1, y1, x2, y2 = map(float, (x1, y1, x2, y2))
        name_m = re.search(r"name=(\S+)", attrs)
        if name_m:
            pins.append((name_m.group(1), (x1 + x2) / 2.0, (y1 + y2) / 2.0))
    return {"type": kind, "pins": pins}


def _prop_block(text, start_idx):
    depth, i = 0, start_idx
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[start_idx:i + 1]
        i += 1
    raise FlattenError("unterminated property block")


def parse_props(block):
    """A very small parser for xschem's `{key=value ...}` instance props --
    good enough for name=/lab=/model=/value=/w=/l=, which is all we use."""
    inner = block.strip()
    if inner.startswith("{") and inner.endswith("}"):
        inner = inner[1:-1]
    props = {}
    for m in re.finditer(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)', inner):
        key, val = m.groups()
        if val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        props[key] = val
    return props


def parse_sch(text):
    wires = []
    for m in WIRE_HEAD_RE.finditer(text):
        x1, y1, x2, y2 = m.groups()
        block = _prop_block(text, m.end() - 1)
        attrs = block[1:-1]
        lab_m = re.search(r"lab=(\S+)", attrs)
        wires.append((float(x1), float(y1), float(x2), float(y2),
                      lab_m.group(1) if lab_m else None))
    comps = []
    for m in COMP_RE.finditer(text):
        sym, x, y, rot, flip = m.groups()
        block = _prop_block(text, m.end() - 1)
        props = parse_props(block)
        comps.append({"sym": sym, "x": float(x), "y": float(y),
                      "rot": int(rot), "flip": int(flip), "props": props})
    return wires, comps


def transform(x, y, rot, flip):
    if flip:
        return [(-x, y), (-y, -x), (x, -y), (y, x)][rot]
    return [(x, y), (-y, x), (-x, -y), (y, -x)][rot]


# ---- symbol loading (local cache dir, else fetch) --------------------------
IHP_PDK_BASE = "https://raw.githubusercontent.com/IHP-GmbH/IHP-Open-PDK/main/ihp-sg13g2/libs.tech/xschem/"
XSCHEM_LIB_BASE = "https://raw.githubusercontent.com/StefanSchippers/xschem/master/xschem_library/"


class SymbolLoader(object):
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._cache = {}

    def _fetch(self, rel):
        # rel is like "sg13g2_pr/rppd.sym" or "devices/gnd.sym" or "ind.sym"
        cand_urls = [IHP_PDK_BASE + rel]
        if rel.startswith("sg13g2_pr/"):
            pass
        else:
            base = rel if "/" in rel else "devices/" + rel
            cand_urls.append(XSCHEM_LIB_BASE + base)
        last_exc = None
        for url in cand_urls:
            try:
                with urllib.request.urlopen(url, timeout=20) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
        raise FlattenError(f"could not fetch symbol {rel!r}: {last_exc}")

    def load(self, rel):
        if rel in self._cache:
            return self._cache[rel]
        local = os.path.join(self.cache_dir, rel.replace("/", "__"))
        if os.path.exists(local):
            with open(local, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        else:
            text = self._fetch(rel)
            with open(local, "w", encoding="utf-8") as fh:
                fh.write(text)
        parsed = parse_sym(text)
        self._cache[rel] = parsed
        return parsed


# ---- union-find --------------------------------------------------------
class UF(object):
    def __init__(self):
        self.parent = {}

    def find(self, k):
        self.parent.setdefault(k, k)
        while self.parent[k] != k:
            self.parent[k] = self.parent[self.parent[k]]
            k = self.parent[k]
        return k

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def flatten(sch_text, loader, unhandled_is_fatal=True):
    """Return (devices, forced_labels) where devices is a list of
    (kind, spice_prefix, name, [net_names]) and forced_labels documents,
    for the report, which components bound which net names."""
    wires, comps = parse_sch(sch_text)
    uf = UF()

    def coord_key(x, y):
        return ("c", round(x, 3), round(y, 3))

    for x1, y1, x2, y2, _lab in wires:
        uf.union(coord_key(x1, y1), coord_key(x2, y2))

    device_pins = []      # (kind, prefix, inst_name, pin_name, coord_key, props)
    binder_pins = []       # (coord_key, forced_label)
    dropped = []
    for c in comps:
        sym_rel = c["sym"]
        sym = loader.load(sym_rel)
        kind_raw = sym["type"]
        name = c["props"].get("name", "?")
        if kind_raw in DROP_TYPES:
            dropped.append((name, sym_rel, kind_raw))
            continue
        pins_abs = []
        for pin_name, lx, ly in sym["pins"]:
            tx, ty = transform(lx, ly, c["rot"], c["flip"])
            ax, ay = c["x"] + tx, c["y"] + ty
            pins_abs.append((pin_name, coord_key(ax, ay)))
            uf.union(("pin", name, pin_name), coord_key(ax, ay))
        if kind_raw in BINDER_TYPES:
            lab = c["props"].get("lab")
            if lab and len(pins_abs) == 1:
                binder_pins.append((("pin", name, pins_abs[0][0]), lab))
            continue
        if kind_raw not in KIND_MAP:
            msg = f"unhandled symbol type {kind_raw!r} (instance {name}, {sym_rel})"
            if unhandled_is_fatal:
                raise FlattenError(msg)
            dropped.append((name, sym_rel, kind_raw))
            continue
        agkind, prefix = KIND_MAP[kind_raw]
        for pin_name, ck in pins_abs:
            device_pins.append((agkind, prefix, name, pin_name, ck, c["props"]))

    # net naming: prefer a binder's explicit lab, else a real (non "#net")
    # wire label, else auto-generate.
    root_label = {}
    for ck, lab in binder_pins:
        root_label[uf.find(ck)] = lab
    for x1, y1, x2, y2, lab in wires:
        if not lab or lab.startswith("#"):
            continue
        root = uf.find(coord_key(x1, y1))
        root_label.setdefault(root, lab)

    auto_ctr = [0]
    net_name_of_root = {}

    def net_name(ck):
        root = uf.find(ck)
        if root in net_name_of_root:
            return net_name_of_root[root]
        if root in root_label:
            n = root_label[root]
        else:
            n = f"xnet{auto_ctr[0]}"
            auto_ctr[0] += 1
        net_name_of_root[root] = n
        return n

    by_device = {}
    for agkind, prefix, name, pin_name, ck, props in device_pins:
        by_device.setdefault((agkind, prefix, name), {"props": props, "pins": {}})
        by_device[(agkind, prefix, name)]["pins"][pin_name] = net_name(ck)

    devices = []
    for (agkind, prefix, name), info in by_device.items():
        devices.append({"kind": agkind, "prefix": prefix, "name": name,
                         "pins": info["pins"], "props": info["props"]})
    return devices, dropped


# ---- emit a flat SPICE deck spice2genie.py can parse -----------------------
# 2-terminal passives (R/L/C): symbol authors spell the two real pins many
# ways (P/M, p/m, c0/c1, LA/LB, ...) -- no point hardcoding names. Take pins
# in the symbol's own declaration order, dropping any that look like a
# body/substrate terminal, and keep the first 2 of what's left.
BODY_PIN_NAMES = {"bn", "b", "sub", "body"}
# Multi-terminal actives (MOS/BJT) genuinely need the right pin *identity*,
# not just count, so these stay name-keyed.
PIN_ORDER_HINT = {
    "nmos4": ["D", "G", "S", "B"], "pmos4": ["D", "G", "S", "B"],
    "npn": ["C", "B", "E"], "pnp": ["C", "B", "E"],
}


def emit_spice(devices):
    lines = []
    counters = {}
    for d in devices:
        counters[d["prefix"]] = counters.get(d["prefix"], 0) + 1
        elt_name = f"{d['prefix']}{counters[d['prefix']]}"
        pins = d["pins"]  # dict preserves insertion == symbol declaration order
        if d["kind"] in PIN_ORDER_HINT:
            hint = PIN_ORDER_HINT[d["kind"]]
            ordered = [pins[p] for p in hint if p in pins]
        else:
            real = [(name, net) for name, net in pins.items()
                    if name.lower() not in BODY_PIN_NAMES]
            ordered = [net for _, net in real[:2]]
        model = d["props"].get("model", d["kind"])
        value = d["props"].get("value", "")
        lines.append(f"{elt_name} {' '.join(ordered)} {model} {value}".rstrip())
    return "\n".join(lines) + "\n"


def flatten_file(sch_path, sym_cache_dir):
    with open(sch_path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    loader = SymbolLoader(sym_cache_dir)
    devices, dropped = flatten(text, loader)
    return emit_spice(devices), devices, dropped


# ---- golden test ------------------------------------------------------
def selftest():
    """Flatten the GPS_LNA nmos testbench schematic (a component that has
    an ALREADY independently-converted, screened (5/5), simulated sibling
    at lna/data/external/ihp-gps-lna-nmos/) straight from its .sch source,
    and check the two agree on device composition and LNA score -- proof
    the geometry/transform/net-reconstruction pipeline is right, not just
    that it runs."""
    import tempfile
    cache = os.path.join(tempfile.gettempdir(), "xschem_syms")
    sch_url = ("https://raw.githubusercontent.com/IHP-GmbH/TO_Apr2025/main/"
               "GPS_LNA/design_data/xyce/lna_tb_xyce_rf_rfmos.sch")
    with urllib.request.urlopen(sch_url, timeout=30) as resp:
        sch_text = resp.read().decode("utf-8", errors="replace")

    loader = SymbolLoader(cache)
    devices, dropped = flatten(sch_text, loader)
    spice_text = emit_spice(devices)

    import spice2genie as s2g
    from topology import Topology
    cir, ports, stats = s2g.convert(spice_text, name="selftest_gps_lna_nmos")
    print("dropped (padframe/ESD/sources, expected):",
          sorted(set(k for _, _, k in dropped)))
    print("device counts:", stats["counts"])
    print("ports:", ports)

    ok = stats["counts"] == {"resistor": 3, "inductor": 3, "capacitor": 2, "nmos4": 3}
    if not ok:
        print("FAIL: device composition does not match the known-good "
              "ihp-gps-lna-nmos conversion (3R 3L 2C 3M)")
        return False

    # build the actual token sequence and re-run the structural screen, the
    # same way the known-good conversion was validated.
    driver_path = os.path.join(HERE, "convert_and_build.py")
    sys.path.insert(0, HERE)
    import convert_and_build as cab
    matrix = cab.build_matrix(cir, ports)
    paths = cab.eulerian_path(matrix)
    if not paths:
        print("FAIL: no Eulerian path found")
        return False
    topo = Topology(list(paths[0]))
    score, crit = topo.lna_score()
    print(f"LNA score: {score}/5, criteria: {crit}")
    match = score == 5 and topo.n_devices == 11 and topo.n_inductors == 3
    print("GOLDEN TEST:", "PASS" if match else "FAIL")
    return match


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sch", nargs="?")
    ap.add_argument("--sym-dir", default=os.path.join(HERE, "xschem_syms"))
    ap.add_argument("-o", "--out")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        ok = selftest()
        sys.exit(0 if ok else 1)

    if not args.sch:
        ap.error("sch file required unless --selftest")
    text_out, devices, dropped = flatten_file(args.sch, args.sym_dir)
    print(f"devices: {len(devices)}  dropped: {len(dropped)}")
    for d in devices:
        print(" ", d["prefix"] + d["name"], d["kind"], list(d["pins"].values()))
    if dropped:
        print("dropped instances:", [(n, k) for n, _, k in dropped])
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text_out)
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()

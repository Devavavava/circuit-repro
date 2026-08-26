"""Human-readable view of an LNA design: topology + sizing + measured specs.

One design, three things a person actually wants to see:

  1. TOPOLOGY  -- every device and what each of its pins connects to (net names).
  2. SIZING    -- every device's value in engineering units (um / nm / ohm / F / H).
  3. SPECS     -- the measured metrics and whether they pass, per band when known.

Two input shapes are supported, both read-only:

  --design <prefix>      a flagship-style triple: <dir>/tokens.json (topology),
                         <prefix>.params.json (sizing), <prefix>.meta.json (specs).
                         e.g. lna/repro/dhruva-best/dhruva-simul
  --row <wl_hash> <spec> a stored L2 row from the label store: graph.tokens is the
                         topology, best_params the sizing, margins/metrics the specs.

Store path defaults to $LNA_DEPS_ROOT/lna/data (the main checkout), so it works
from a worktree. Nothing here writes anything.

    python lna/render_design.py --design lna/repro/dhruva-best/dhruva-simul
    python lna/render_design.py --row 58da009b6622b8d7 wifi24
    python lna/render_design.py --row 58da009b6622b8d7 wifi24 --deck   # + SPICE deck
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from topology import Topology            # noqa: E402
import to_spice                          # noqa: E402


# ----------------------------------------------------------------- unit helpers
_SUFFIX = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3,
           "k": 1e3, "meg": 1e6, "g": 1e9, "t": 1e12}


def spice_float(x):
    """Parse a SPICE-style number: 45n, 1.2k, 10meg, 7e-12, or a plain float."""
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().lower()
    m = re.match(r"^([-+]?[0-9.]+(?:e[-+]?[0-9]+)?)(meg|[fpnumkgt])?$", s)
    if not m:
        return float(s)
    val = float(m.group(1))
    return val * _SUFFIX.get(m.group(2), 1.0) if m.group(2) else val


def _eng(value, unit, factors):
    """Format `value` (base SI) as the nicest of `factors` = [(scale, suffix), ...]."""
    v = spice_float(value)
    if v == 0:
        return f"0 {unit}"
    for scale, suf in factors:
        if abs(v) >= scale:
            return f"{v / scale:.4g} {suf}{unit}"
    scale, suf = factors[-1]
    return f"{v / scale:.4g} {suf}{unit}"


def fmt_R(v):  # ohms
    return _eng(v, "Ω", [(1e6, "M"), (1e3, "k"), (1, "")])


def fmt_C(v):  # farads
    return _eng(v, "F", [(1e-9, "n"), (1e-12, "p"), (1e-15, "f")])


def fmt_L(v):  # henries
    return _eng(v, "H", [(1e-9, "n"), (1e-12, "p")])


def fmt_W(v):  # metres -> um
    return f"{spice_float(v) * 1e6:.4g} µm"


def fmt_Lnm(v):  # metres -> nm
    return f"{spice_float(v) * 1e9:.4g} nm"


# --------------------------------------------------------------- device kinding
def device_kind(name):
    base = re.sub(r"\d+$", "", name)
    return {
        "NM": "nmos", "PM": "pmos", "NB": "npn", "PB": "pnp",
        "R": "res", "C": "cap", "L": "ind",
    }.get(base, base.lower())


PIN_ORDER = ["G", "D", "S", "B", "C", "E", "P", "N", "A", "1", "2"]


def device_pins(topo, dev):
    """(pin_label, net) for one device, in a stable electrical order."""
    out = []
    for p in topo.pins:
        if p.rsplit("_", 1)[0] == dev:
            label = p.rsplit("_", 1)[1] if "_" in p else p
            out.append((label, p))
    out.sort(key=lambda t: (PIN_ORDER.index(t[0]) if t[0] in PIN_ORDER else 99, t[0]))
    return out


# ------------------------------------------------------------------ the sections
SPECIAL_NETS = {"0", "VSS", "GND", "VDD", "VIN1", "VOUT1"}


def stable_net_map(topo, nl):
    """Rename internal nets to i1,i2,... in order of first appearance in the token
    walk, so the same topology always prints the same net names. Named rails/ports
    (VDD/VSS/0/VIN1/VOUT1) are kept."""
    order, seen = [], set()
    for tok in topo.tokens:
        net = nl.node_of_pin.get(tok)
        if net is not None and net not in seen:
            seen.add(net)
            order.append(net)
    remap, k = {}, 0
    for net in order:
        if net in SPECIAL_NETS:
            remap[net] = net
        else:
            k += 1
            remap[net] = f"i{k}"
    return remap


def render_topology(topo, nl):
    remap = stable_net_map(topo, nl)

    def net(p):
        return remap.get(nl.node_of_pin.get(p), nl.node_of_pin.get(p, "?"))

    lines = ["TOPOLOGY   (device : pin -> net)",
             "  legend: VIN1=RF input  VOUT1=output  VDD=supply  0=ground  iN=internal",
             ""]
    for dev in sorted(topo.devices, key=lambda d: (device_kind(d), d)):
        pins = device_pins(topo, dev)
        conn = "   ".join(f"{lbl}->{net(p)}" for lbl, p in pins)
        lines.append(f"  {dev:<5} {device_kind(dev):<5} {conn}")
    return "\n".join(lines)


def render_sizing(params):
    """Group the .param knobs by device and print in engineering units."""
    devs = {}
    other = {}
    for k, raw in params.items():
        v = raw
        m = re.match(r"p(NM|PM)(\d+)(W|L)$", k)
        if m:
            d = m.group(1) + m.group(2)
            devs.setdefault(d, {})[m.group(3)] = v
            continue
        m = re.match(r"p(R|C|L)(\d+)V$", k)
        if m:
            devs.setdefault(m.group(1) + m.group(2), {})["V"] = v
            continue
        other[k] = v

    lines = ["SIZING   (device values)"]
    for d in sorted(devs, key=lambda d: (device_kind(d), d)):
        vals = devs[d]
        kind = device_kind(d)
        if kind in ("nmos", "pmos"):
            w = vals.get("W"); L = vals.get("L")
            s = f"W={fmt_W(w)}" if w is not None else "W=?"
            if L is not None:
                s += f"  L={fmt_Lnm(L)}"
            lines.append(f"  {d:<5} {kind:<5} {s}")
        elif kind == "res":
            lines.append(f"  {d:<5} {kind:<5} {fmt_R(vals.get('V', 0))}")
        elif kind == "cap":
            lines.append(f"  {d:<5} {kind:<5} {fmt_C(vals.get('V', 0))}")
        elif kind == "ind":
            lines.append(f"  {d:<5} {kind:<5} {fmt_L(vals.get('V', 0))}")
        else:
            lines.append(f"  {d:<5} {kind:<5} {vals}")

    bias = []
    for k in ("pVB", "pVDD", "pINDQ"):
        if k in other:
            label = {"pVB": "bias VB", "pVDD": "VDD", "pINDQ": "inductor Q"}[k]
            unit = " V" if k in ("pVB", "pVDD") else ""
            bias.append(f"{label}={spice_float(other.pop(k)):.4g}{unit}")
    if bias:
        lines.append("  " + " ; ".join(bias))
    misc = {k: v for k, v in other.items() if not k.startswith("pINDW")}
    if misc:
        lines.append(f"  (other params: {misc})")
    return "\n".join(lines)


def _pass(margin):
    return "PASS" if (margin is not None and margin >= 0) else "FAIL"


def render_specs_from_margins(feasible, margins, metrics):
    lines = [f"SPECS ACHIEVED   (feasible: {'YES' if feasible else 'NO'})",
             f"  {'metric':<10}{'achieved':>12}{'limit':>14}{'margin':>10}   verdict"]
    for name, m in (margins or {}).items():
        ach = m.get("achieved")
        lim = m.get("required_max")
        limtxt = f"<= {lim}" if lim is not None else (
            f">= {m.get('required_min')}" if m.get("required_min") is not None else "-")
        mar = m.get("margin")
        lines.append(f"  {name:<10}{_num(ach):>12}{limtxt:>14}{_num(mar):>10}   {_pass(mar)}")
    return "\n".join(lines)


def render_specs_from_meta(meta):
    ev = meta.get("dual_vdd_eval", {})
    row = ev.get("1.1") or ev.get(1.1) or next(iter(ev.values()), None)
    if not row:
        return None
    bands = list(row.keys())
    cols = ["s11_max_db", "s21_db", "nf_db", "idd_ma", "k_min", "feasible"]
    head = f"  {'band':<6}" + "".join(f"{c:>11}" for c in cols)
    lines = ["SPECS ACHIEVED   (measured, VDD=1.1 V, per band)", head]
    for b in bands:
        cell = row[b]
        vals = "".join(f"{_num(cell.get(c)):>11}" for c in cols)
        lines.append(f"  {b:<6}{vals}")
    return "\n".join(lines)


def _num(x):
    if x is None:
        return "-"
    if isinstance(x, bool):
        return "yes" if x else "no"
    try:
        return f"{float(x):.4g}"
    except (TypeError, ValueError):
        return str(x)


# ------------------------------------------------------------------------- load
def load_design(prefix):
    d = os.path.dirname(prefix)
    tokens = json.load(open(os.path.join(d, "tokens.json")))
    params = json.load(open(prefix + ".params.json"))
    meta = {}
    mp = prefix + ".meta.json"
    if os.path.exists(mp):
        meta = json.load(open(mp))
    name = os.path.basename(prefix)
    return name, tokens, params, meta, None


def load_row(wl_hash, spec):
    root = os.environ.get("LNA_DEPS_ROOT", os.path.dirname(HERE))
    store = os.path.join(root, "lna", "data", "topo_labels.jsonl")
    hit = None
    for line in open(store):
        r = json.loads(line)
        if r.get("wl_hash") == wl_hash and r.get("spec") == spec:
            hit = r  # last one wins (latest recipe)
    if hit is None:
        sys.exit(f"no stored row for wl_hash={wl_hash} spec={spec} in {store}")
    tokens = hit["graph"]["tokens"]
    return f"{wl_hash}/{spec}", tokens, hit["best_params"], {}, hit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", help="path prefix: <dir>/tokens.json + <prefix>.params.json")
    ap.add_argument("--row", nargs=2, metavar=("WL_HASH", "SPEC"))
    ap.add_argument("--deck", action="store_true", help="also print the SPICE deck")
    args = ap.parse_args()

    if args.design:
        name, tokens, params, meta, row = load_design(args.design)
    elif args.row:
        name, tokens, params, meta, row = load_row(*args.row)
    else:
        ap.error("give --design <prefix> or --row <wl_hash> <spec>")

    topo = Topology(tokens)
    nl = to_spice.Netlist(topo)
    score, _ = topo.lna_score()
    wl = (meta.get("wl_hash") or (row or {}).get("wl_hash") or "-")
    specname = meta.get("spec") or (row or {}).get("spec") or "-"

    print("=" * 68)
    print(f" DESIGN: {name}   (wl_hash {wl})")
    print(f" spec: {specname}")
    print(f" {topo.n_devices} devices ({topo.n_inductors} inductors), "
          f"{len(topo.nodes)} nodes | LNA score {score}/5 | "
          f"valid: {'yes' if topo.valid else 'no'}")
    print("=" * 68)
    print()
    print(render_topology(topo, nl))
    print()
    print(render_sizing(params))
    print()
    if meta.get("dual_vdd_eval"):
        print(render_specs_from_meta(meta))
    elif row is not None:
        print(render_specs_from_margins(row.get("feasible"), row.get("margins"),
                                        row.get("metrics")))
    else:
        print("SPECS ACHIEVED   (no measured metrics on file)")

    if args.deck:
        print()
        print("SPICE DECK")
        nl2 = to_spice.Netlist(topo)
        nl2.set_extra([], params)
        print(nl2.emit())
    return 0


if __name__ == "__main__":
    sys.exit(main())

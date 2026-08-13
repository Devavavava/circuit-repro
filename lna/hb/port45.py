"""ngspice -> VACASK port of the D4-SIM deck (WP-HB, FINDINGS S40).

Scope, deliberately narrow: this converts exactly the deck grammar
`lna/to_spice.py` emits (the repro package's standalone .sp decks) -- .param
map with {brace} expressions, V/C/L/R/M cards, the two S-param ports, and
`.option rshunt` -- into a VACASK netlist using the shipped SPICE-compat
BSIM4.8.2 OSDI model (`spice/bsim4v8.osdi`). The shipped ng2vc converter
crashes on the port-source syntax (`portnum 1 z0 50`), and a 79-line fixed
grammar is safer hand-parsed than a patched general converter.

Equivalences, stated:
- ngspice `.option rshunt=1e12` (a 1e12 ohm resistor from EVERY node to
  ground) becomes explicit `rsh_*` 1e12 resistors on every circuit node.
  This deck's six gates have no other DC path (the design conducts in weak
  inversion at Vgs=0; FINDINGS S30.5) -- the shunts are load-bearing, not
  hygiene.
- The two S-param ports become a physical 50-ohm testbench: port 1 -> EMF
  stack (one or two sine sources in series) + 50-ohm series resistor into
  the original DC-block cap; port 2 -> the original DC-block cap into a
  50-ohm load. |V(p2)| = S21 * A_emf/2 for a matched linear circuit, which
  is the gain cross-check hb_iip3.py uses.
- The BSIM4 card keeps every parameter except `level` (implied by the OSDI
  model) and passes `version="4.0"` through; the model-compat verdict is
  measured (op Idd + single-tone gain vs ngspice), not assumed.
"""
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.dirname(HERE)
REPRO = os.path.join(LNA, "repro", "dhruva-best")
DECK = os.path.join(REPRO, "dhruva-l5.sp")

_SUFFIX = {"t": 1e12, "g": 1e9, "meg": 1e6, "k": 1e3, "m": 1e-3,
           "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15}


def parse_num(tok):
    """ngspice number with optional SI suffix (45n, 10p, 1.5meg...)."""
    m = re.fullmatch(r"([-+]?[\d.]+(?:[eE][-+]?\d+)?)\s*([a-zA-Z]*)", tok.strip())
    if not m:
        raise ValueError(f"bad number: {tok!r}")
    v = float(m.group(1))
    suf = m.group(2).lower()
    if suf.startswith("meg"):
        return v * 1e6
    if suf and suf[0] in _SUFFIX:
        return v * _SUFFIX[suf[0]]
    return v


def read_params(deck_text):
    params = {}
    for m in re.finditer(r"^\.param\s+(.*)$", deck_text, re.M):
        for k, v in re.findall(r"(\w+)\s*=\s*(\S+)", m.group(1)):
            params[k] = parse_num(v)
    return params


def ev(expr, params):
    """Evaluate a {brace} expression from the deck under the param map."""
    ns = {"max": max, "ceil": math.ceil, "min": min, "floor": math.floor}
    ns.update(params)
    return eval(expr, {"__builtins__": {}}, ns)  # deck is our own artifact


def val(tok, params):
    tok = tok.strip()
    if tok.startswith("{") and tok.endswith("}"):
        return ev(tok[1:-1], params)
    return parse_num(tok)


def convert_model_card(model_path):
    """BPTM .model card -> VACASK sp_bsim4v8 model card (NMOS only)."""
    lines = []
    with open(model_path, encoding="utf-8") as f:
        txt = f.read()
    # join continuation lines per .model block
    blocks = re.split(r"(?im)^\.model\s+(\w+)\s+(\w+)\s*", txt)
    # blocks: [pre, name1, type1, body1, name2, type2, body2, ...]
    cards = {}
    for i in range(1, len(blocks) - 2, 3):
        name, mtype, body = blocks[i], blocks[i + 1], blocks[i + 2]
        body = body.split(".model")[0]
        pairs = {}
        for ln in body.splitlines():
            ln = ln.split("*")[0].strip()
            if ln.startswith("+"):
                ln = ln[1:]
            for k, v in re.findall(r"(\w+)\s*=\s*([-+.\w]+)", ln):
                pairs[k.lower()] = v
        cards[name.lower()] = (mtype.lower(), pairs)
    if "nmos" not in cards:
        raise SystemExit("no nmos card found in model include")
    _, pairs = cards["nmos"]
    pairs.pop("level", None)
    version = pairs.pop("version", "4.0")
    parts = [f'model nmos sp_bsim4v8 ( type=1 version="{version}"']
    cur = parts.pop()
    for k, v in pairs.items():
        item = f"{k}=({v})"
        if len(cur) + len(item) > 78:
            parts.append(cur)
            cur = "    "
        cur += " " + item
    parts.append(cur + " )")
    return "\n".join(parts)


def nodes_of(deck_path=DECK):
    """Every circuit node the deck names (lowercase, ground excluded).

    Used to build the ngspice cross-check control block: the port is judged
    by comparing the WHOLE DC solution, not just the supply current.
    """
    return convert(deck_path)[3]


def convert(deck_path=DECK, model_path=None):
    """Returns (circuit_lines, params, model_card, nodes) -- circuit only, no
    sources, no control block. Ports are dropped here; the driver adds the
    testbench."""
    with open(deck_path, encoding="utf-8") as f:
        text = f.read()
    params = read_params(text)
    text = text.split(".control")[0]  # device section only
    out = []
    nodes = set()

    def node(n):
        n = n.lower()
        if n != "0":
            nodes.add(n)
        return n

    for raw in text.splitlines():
        ln = raw.strip()
        if not ln or ln.startswith("*") or ln.startswith("."):
            continue
        t = ln.split()
        name = t[0].lower()
        if name.startswith("vp") or name in ("cp1", "cp2"):
            # S-param ports + their DC-block caps: testbench, added by driver
            for n in t[1:3]:
                node(n)
            continue
        if name == "vsup":
            out.append(f"vsup ({node(t[1])} {node(t[2])}) vsource dc={val(t[4], params)!r}")
            continue
        kind = name[0]
        if kind == "c":
            out.append(f"{name} ({node(t[1])} {node(t[2])}) capacitor c={val(t[3], params)!r}")
        elif kind == "l":
            out.append(f"{name} ({node(t[1])} {node(t[2])}) inductor l={val(t[3], params)!r}")
        elif kind == "r":
            out.append(f"{name} ({node(t[1])} {node(t[2])}) resistor r={val(t[3], params)!r}")
        elif kind == "m":
            d, g, s, b = (node(x) for x in t[1:5])
            kw = dict(kv.split("=", 1) for kv in t[6:])
            w = val(kw["W"], params)
            l = val(kw["L"], params)
            nf = int(val(kw["NF"], params))
            out.append(f"{name} ({d} {g} {s} {b}) nmos w={w!r} l={l!r} nf={nf}")
        else:
            raise SystemExit(f"unhandled card: {ln}")
    # rshunt equivalence -- every node, including testbench-side p1/p2/vin1/vout1
    for n in sorted(nodes):
        out.append(f"rsh_{n} ({n} 0) resistor r=1e12")
    if model_path is None:
        m = re.search(r"^\.include\s+(\S+)", text, re.M)
        model_path = m.group(1)
    return out, params, convert_model_card(model_path), sorted(nodes)


if __name__ == "__main__":
    lines, params, card, _nodes = convert()
    print(card[:400])
    print("...")
    print("\n".join(lines))

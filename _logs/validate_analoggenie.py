"""Validate an AnalogGenie generated sequence and reconstruct its netlist.

The model emits an Eulerian traversal over the *compressed* device-pin graph
produced by SPICE2GRAPH_compress.py. In that representation:

  * a device token always sits between two pins of that same device
    (that edge means "this pin belongs to this device", not a wire);
  * pin<->named-net adjacency is a wire to a named node (VDD, VSS, VIN1, ...);
  * pin<->pin adjacency is a wire on an *internal, unnamed* net -- this is what
    "compressed" means, versus SPICE2GRAPH_full.py which names every net.

So electrical nodes are the connected components of the graph induced by
pin<->pin and pin<->net edges. Union-find over those edges rebuilds the netlist.
"""
import re
import sys
from collections import defaultdict

DEV_PREFIXES = ("NM", "PM", "NPN", "PNP", "R", "C", "L", "DIO",
                "XOR", "PFD", "INVERTER", "TRANSMISSION_GATE")
PIN_RE = re.compile(r'^(?P<dev>[A-Z_]+\d+)_(?P<pin>[A-Z]+)$')
LEGAL = {"NM": {"D", "G", "S", "B"}, "PM": {"D", "G", "S", "B"},
         "NPN": {"C", "B", "E"}, "PNP": {"C", "B", "E"},
         "R": {"P", "N"}, "C": {"P", "N"}, "L": {"P", "N"}, "DIO": {"P", "N"}}


def base_of(tok):
    m = re.match(r'^(?P<base>[A-Z_]+?)(?P<idx>\d+)$', tok)
    return m.group('base') if m else None


def is_device(tok):
    return base_of(tok) in DEV_PREFIXES


path = sys.argv[1]
all_toks = [t for t in open(path).read().split('->') if t]
if 'TRUNCATE' in all_toks:
    end = all_toks.index('TRUNCATE')
    toks, truncated = all_toks[:end], True
else:
    toks, truncated = all_toks, False

pins, devs, nets = set(), set(), set()
for t in toks:
    if PIN_RE.match(t):
        pins.add(t)
    elif is_device(t):
        devs.add(t)
    else:
        nets.add(t)

# --- structural checks -------------------------------------------------
bad_dev = []
for i, t in enumerate(toks):
    if t not in devs:
        continue
    for nb in (toks[i - 1] if i else None, toks[i + 1] if i + 1 < len(toks) else None):
        if nb is None:
            continue
        m = PIN_RE.match(nb)
        if not m or m.group('dev') != t:
            bad_dev.append((i, t, nb))

bad_pinname = [p for p in pins
               if base_of(PIN_RE.match(p).group('dev')) in LEGAL
               and PIN_RE.match(p).group('pin') not in LEGAL[base_of(PIN_RE.match(p).group('dev'))]]

# A pin must be claimed by its own device somewhere in the sequence.
claimed = set()
for i, t in enumerate(toks):
    m = PIN_RE.match(t)
    if not m:
        continue
    if m.group('dev') in (toks[i - 1] if i else None, toks[i + 1] if i + 1 < len(toks) else None):
        claimed.add(t)
orphan_pins = sorted(pins - claimed)

# --- rebuild electrical nodes (union-find over wire edges) --------------
parent = {}


def find(x):
    parent.setdefault(x, x)
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[ra] = rb


wire_edges = 0
for a, b in zip(toks, toks[1:]):
    a_pin, b_pin = bool(PIN_RE.match(a)), bool(PIN_RE.match(b))
    if a in devs or b in devs:
        continue                      # pin-device membership, not a wire
    if (a_pin and b_pin) or (a_pin and b in nets) or (a in nets and b_pin):
        union(a, b)
        wire_edges += 1

nodes = defaultdict(set)
for x in list(pins) + list(nets):
    nodes[find(x)].add(x)

named = {}
for root, members in nodes.items():
    lbl = sorted(m for m in members if m in nets)
    named[root] = lbl[0] if lbl else None

print(f"tokens in file            : {len(all_toks)}")
print(f"tokens in first circuit   : {len(toks)}   (TRUNCATE terminator: {truncated})")
print(f"distinct devices          : {len(devs)}")
print(f"distinct device pins      : {len(pins)}")
print(f"named nets                : {len(nets)} -> {sorted(nets)}")
print(f"wire edges                : {wire_edges}")
print(f"electrical nodes (nets)   : {len(nodes)}")
print()
print(f"malformed device tokens   : {len(bad_dev)}")
print(f"illegal pin names         : {len(bad_pinname)}")
print(f"orphan pins (no device)   : {len(orphan_pins)}")
print()
print("device families used:", sorted({base_of(d) for d in devs}))

# per-device pin completeness
incomplete = []
by_dev = defaultdict(set)
for p in pins:
    m = PIN_RE.match(p)
    by_dev[m.group('dev')].add(m.group('pin'))
for d in sorted(devs):
    exp = LEGAL.get(base_of(d))
    if exp and by_dev[d] != exp:
        incomplete.append((d, sorted(by_dev[d]), sorted(exp)))
print(f"devices with incomplete pin sets: {len(incomplete)}")
for d, got, exp in incomplete[:8]:
    print(f"    {d}: got {got}, expected {exp}")

print()
print("=== reconstructed netlist (electrical node : pins) ===")
for root in sorted(nodes, key=lambda r: (named[r] is None, named[r] or '')):
    members = nodes[root]
    ps = sorted(m for m in members if PIN_RE.match(m))
    if not ps:
        continue
    label = named[root] or f"n_int_{abs(hash(root)) % 10000}"
    print(f"  {label:10s}: {' '.join(ps)}")

ok = not bad_dev and not bad_pinname and not orphan_pins and devs and nets
print()
print("STRUCTURAL VALIDATION:", "PASS" if ok else "FAIL")
if bad_dev[:5]:
    print("  sample bad device ctx:", bad_dev[:5])
if orphan_pins[:8]:
    print("  sample orphan pins:", orphan_pins[:8])
sys.exit(0 if ok else 1)

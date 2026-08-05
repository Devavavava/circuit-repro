"""Parse an AnalogGenie token sequence into a circuit, and score how LNA-like it is.

The node/net reconstruction follows the union-find approach in
_logs/validate_analoggenie.py: in the *compressed* graph a device token sits
between two pins of that device (membership, not a wire), while pin<->pin and
pin<->net adjacencies are wires. Electrical nodes are the connected components
over wire edges.

The LNA signature is derived from the dataset's own LNA circuits
(Dataset indices 461-492 and 1081-1090, per data_categorization.md):

    inductors are ~20% of device instances in that subset, versus ~0.8%
    across the whole corpus -- inductor content is the single strongest
    discriminator, because matching networks and degeneration need them.

Nothing here judges electrical quality; it is a structural screen used to decide
which generated topologies are worth simulating.
"""
import re
from collections import defaultdict

DEV_PREFIXES = ("NM", "PM", "NPN", "PNP", "R", "C", "L", "DIO",
                "XOR", "PFD", "INVERTER", "TRANSMISSION_GATE")
PIN_RE = re.compile(r'^(?P<dev>[A-Z_]+\d+)_(?P<pin>[A-Z]+)$')
BASE_RE = re.compile(r'^(?P<base>[A-Z_]+?)(?P<idx>\d+)$')

# Inserted bias scaffolding (03-BIAS naming contract): excluded from the
# floating-subcircuit check so inserted bias can neither mask a real flag nor
# create a spurious one. No effect on un-biased corpus/generated circuits.
SCAFFOLD_PREFIXES = ("RBIAS", "CBYP", "VBGEN")

# Nets that tie a component to the outside world: supplies, ground, DC bias,
# and the RF ports. A connected component of devices reaching none of these is
# a genuinely floating sub-circuit (H-Q3 / WORKLOG F6, index 1081).
_REF_EXACT = {"VDD", "VSS", "0"}
_REF_PREFIX = ("VB", "VCM", "VREF", "VIN", "VOUT", "IB")


def is_scaffold(tok):
    return tok.startswith(SCAFFOLD_PREFIXES)


def is_ref_net(net):
    return net in _REF_EXACT or net.startswith(_REF_PREFIX)
LEGAL = {"NM": {"D", "G", "S", "B"}, "PM": {"D", "G", "S", "B"},
         "NPN": {"C", "B", "E"}, "PNP": {"C", "B", "E"},
         "R": {"P", "N"}, "C": {"P", "N"}, "L": {"P", "N"}, "DIO": {"P", "N"}}


def base_of(tok):
    m = BASE_RE.match(tok)
    return m.group("base") if m else None


def is_device(tok):
    return base_of(tok) in DEV_PREFIXES


class Topology(object):
    """A parsed circuit plus the structural checks used to screen it."""

    def __init__(self, tokens):
        if "TRUNCATE" in tokens:
            tokens = tokens[:tokens.index("TRUNCATE")]
        self.tokens = tokens

        self.pins, self.devices, self.nets = set(), set(), set()
        for t in tokens:
            if PIN_RE.match(t):
                self.pins.add(t)
            elif is_device(t):
                self.devices.add(t)
            else:
                self.nets.add(t)

        self._check_structure()
        self._build_nodes()

    # ---------- structural validity (same rules as validate_analoggenie.py) ----
    def _check_structure(self):
        toks = self.tokens
        self.bad_device_ctx = []
        for i, t in enumerate(toks):
            if t not in self.devices:
                continue
            for nb in (toks[i - 1] if i else None,
                       toks[i + 1] if i + 1 < len(toks) else None):
                if nb is None:
                    continue
                m = PIN_RE.match(nb)
                if not m or m.group("dev") != t:
                    self.bad_device_ctx.append((i, t, nb))

        self.illegal_pins = [
            p for p in self.pins
            if base_of(PIN_RE.match(p).group("dev")) in LEGAL
            and PIN_RE.match(p).group("pin")
            not in LEGAL[base_of(PIN_RE.match(p).group("dev"))]]

        claimed = set()
        for i, t in enumerate(toks):
            m = PIN_RE.match(t)
            if not m:
                continue
            neighbours = (toks[i - 1] if i else None,
                          toks[i + 1] if i + 1 < len(toks) else None)
            if m.group("dev") in neighbours:
                claimed.add(t)
        self.orphan_pins = sorted(self.pins - claimed)

        by_dev = defaultdict(set)
        for p in self.pins:
            m = PIN_RE.match(p)
            by_dev[m.group("dev")].add(m.group("pin"))
        self.incomplete = []
        for d in sorted(self.devices):
            exp = LEGAL.get(base_of(d))
            if exp and by_dev[d] != exp:
                self.incomplete.append(d)

    def _build_nodes(self):
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

        self.wire_edges = 0
        for a, b in zip(self.tokens, self.tokens[1:]):
            if a in self.devices or b in self.devices:
                continue
            a_pin, b_pin = bool(PIN_RE.match(a)), bool(PIN_RE.match(b))
            if (a_pin and b_pin) or (a_pin and b in self.nets) or \
               (a in self.nets and b_pin):
                union(a, b)
                self.wire_edges += 1

        nodes = defaultdict(set)
        for x in list(self.pins) + list(self.nets):
            nodes[find(x)].add(x)
        self.nodes = nodes

    # ---------- properties ---------------------------------------------------
    @property
    def valid(self):
        return (not self.bad_device_ctx and not self.illegal_pins
                and not self.orphan_pins and bool(self.devices) and bool(self.nets))

    def counts(self):
        c = defaultdict(int)
        for d in self.devices:
            c[base_of(d)] += 1
        return dict(c)

    @property
    def n_devices(self):
        return len(self.devices)

    @property
    def n_inductors(self):
        return self.counts().get("L", 0)

    @property
    def inductor_ratio(self):
        return self.n_inductors / self.n_devices if self.n_devices else 0.0

    def has_net(self, prefix):
        return any(n.startswith(prefix) for n in self.nets)

    # ---------- floating sub-circuit (H-Q3 / F6) -----------------------------
    def _device_pins(self):
        by_dev = defaultdict(list)
        for p in self.pins:
            by_dev[PIN_RE.match(p).group("dev")].append(p)
        return by_dev

    def floating_devices(self):
        """Devices that belong to a connected component reaching no driven net.

        Builds components by linking the electrical nodes that a device spans
        (its pins' nodes), then a component is "driven" iff it contains a supply,
        ground, DC-bias or port net (`is_ref_net`). Devices in an undriven
        component are floating -- the structural signature of index 1081, which
        `.option rshunt` cannot rescue because it is a separate island, not a
        capacitively-isolated node. Bias scaffolding is excluded (naming contract).

        Returns the set of floating device tokens (empty for a healthy circuit).
        """
        pin2root, root_nets = {}, {}
        for root, members in self.nodes.items():
            root_nets[root] = {m for m in members if m in self.nets}
            for m in members:
                if PIN_RE.match(m):
                    pin2root[m] = root

        parent = {r: r for r in self.nodes}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        by_dev = self._device_pins()
        for d in self.devices:
            if is_scaffold(d):
                continue
            roots = [pin2root[p] for p in by_dev[d] if p in pin2root]
            for r in roots[1:]:
                union(roots[0], r)

        driven = {find(root) for root, nets in root_nets.items()
                  if any(is_ref_net(n) for n in nets)}

        floating = set()
        for d in self.devices:
            if is_scaffold(d):
                continue
            roots = [pin2root[p] for p in by_dev[d] if p in pin2root]
            if roots and find(roots[0]) not in driven:
                floating.add(d)
        return floating

    @property
    def has_floating_subcircuit(self):
        return bool(self.floating_devices())

    # ---------- LNA screen ---------------------------------------------------
    def lna_score(self):
        """Return (score 0-5, dict of which criteria passed).

        Criteria chosen from the LNA subset's own statistics; a topology has to
        look like a small, inductor-bearing, single-ended RF amplifier.
        """
        c = self.counts()
        crit = {
            "has_inductor":    self.n_inductors >= 1,
            "inductor_ratio":  self.inductor_ratio >= 0.10,
            "has_transistor":  (c.get("NM", 0) + c.get("PM", 0)) >= 1,
            "has_rf_ports":    self.has_net("VIN") and self.has_net("VOUT"),
            "lna_sized":       2 <= self.n_devices <= 15,
        }
        return sum(crit.values()), crit


def parse_arrow_file(path):
    """Read upstream's '->'-joined generation output."""
    raw = open(path, encoding="utf-8", errors="replace").read()
    return [t for t in raw.split("->") if t]

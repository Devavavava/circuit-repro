"""opamp-v0 netlist dialect: parse, canonical format (round-trip), matched groups,
structural pre-filter.

DIALECT (one device per line; '#' or '*' starts a comment; blank lines ignored)

    NMOS name D G S [B]
    PMOS name D G S [B]
    R    name P N
    C    name P N

* TYPE is case-insensitive on input, written upper-case.
* Special nets (case-insensitive on input, written upper-case):
  VINP (non-inverting input), VINN (inverting input), VOUT (single-ended output),
  VDD, VSS (ground), IREF (the one ideal reference current is pushed INTO this net
  from VDD by the testbench). Any other net is internal and is written lower-case.
* Bulk B is optional: default VSS for NMOS, VDD for PMOS. Allowed values: the
  default rail or the device's own source net.
* Device names: [A-Za-z][A-Za-z0-9_]*, unique case-insensitively.
* MATCHED GROUPS: a name ending in <digit><lower-case letter> (M1a, M1b, Q12c)
  belongs to the group named by the name without the final letter (M1, M1, Q12).
  All members of a group must have the same TYPE and share every sizing parameter
  (W and L for MOS, the value for R/C). Any other name is its own group.
* No device values, no sources, no bias networks are written by the user: the
  sizer chooses W/L/R/C and the reference current; the testbench adds the sources.
"""
import re
from collections import OrderedDict, defaultdict

SPECIAL = ("VINP", "VINN", "VOUT", "VDD", "VSS", "IREF")
TYPES = {"NMOS": 4, "PMOS": 4, "R": 2, "C": 2}
MAX_DEVICES = 40
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
NET_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
GROUP_RE = re.compile(r"^(.*\d)([a-z])$")


class DialectError(ValueError):
    """Raised by parse() on a syntactically invalid netlist."""


class Device(object):
    __slots__ = ("type", "name", "nets")

    def __init__(self, type_, name, nets):
        self.type, self.name, self.nets = type_, name, tuple(nets)

    @property
    def is_mos(self):
        return self.type in ("NMOS", "PMOS")

    def pins(self):
        """{pin: net}; MOS pins D G S B, passives P N."""
        keys = ("D", "G", "S", "B") if self.is_mos else ("P", "N")
        return dict(zip(keys, self.nets))

    def __eq__(self, other):
        return (self.type, self.name, self.nets) == (other.type, other.name, other.nets)

    def __repr__(self):
        return "Device(%s %s %s)" % (self.type, self.name, " ".join(self.nets))


def canon_net(tok):
    if not NET_RE.match(tok):
        raise DialectError("bad net name %r" % tok)
    up = tok.upper()
    if up in SPECIAL:
        return up
    if up in ("0", "GND"):
        return "VSS"
    return tok.lower()


def group_of(name):
    m = GROUP_RE.match(name)
    return m.group(1) if m else name


def parse(text):
    """Netlist text -> list[Device] (input order kept). Raises DialectError."""
    devs, seen = [], set()
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("*"):
            continue
        tok = line.split()
        typ = tok[0].upper()
        if typ not in TYPES:
            raise DialectError("line %d: unknown device type %r" % (lineno, tok[0]))
        if len(tok) < 2 or not NAME_RE.match(tok[1]):
            raise DialectError("line %d: bad or missing device name" % lineno)
        name = tok[1]
        if name.lower() in seen:
            raise DialectError("line %d: duplicate device name %r" % (lineno, name))
        seen.add(name.lower())
        nets = tok[2:]
        n = TYPES[typ]
        if typ in ("NMOS", "PMOS"):
            if len(nets) not in (3, 4):
                raise DialectError("line %d: %s takes D G S [B]" % (lineno, typ))
            nets = [canon_net(t) for t in nets]
            if len(nets) == 3:
                nets.append("VSS" if typ == "NMOS" else "VDD")
        else:
            if len(nets) != n:
                raise DialectError("line %d: %s takes P N" % (lineno, typ))
            nets = [canon_net(t) for t in nets]
        devs.append(Device(typ, name, nets))
    if not devs:
        raise DialectError("empty netlist")
    groups = defaultdict(set)
    for d in devs:
        groups[group_of(d.name)].add(d.type)
    for g, ts in groups.items():
        if len(ts) > 1:
            raise DialectError("matched group %r mixes types %s" % (g, sorted(ts)))
    return devs


def format_netlist(devs):
    """Canonical text: one device per line, input order, bulk always written."""
    return "".join("%s %s %s\n" % (d.type, d.name, " ".join(d.nets)) for d in devs)


def canonical(text):
    return format_netlist(parse(text))


def groups(devs):
    """OrderedDict group -> list[Device], in first-appearance order."""
    out = OrderedDict()
    for d in devs:
        out.setdefault(group_of(d.name), []).append(d)
    return out


def param_space(devs):
    """OrderedDict param_name -> kind ('W','L','R','C','IREF'). One W and one L per
    MOS group, one value per R/C group, plus the reference current."""
    sp = OrderedDict()
    for g, members in groups(devs).items():
        t = members[0].type
        if t in ("NMOS", "PMOS"):
            sp[g + ".W"] = "W"
            sp[g + ".L"] = "L"
        else:
            sp[g + "." + t] = t
    sp["IREF"] = "IREF"
    return sp


def nets_of(devs):
    s = []
    for d in devs:
        for n in d.nets:
            if n not in s:
                s.append(n)
    return s


def prefilter(devs):
    """Zero-cost structural screen. Returns (ok, [reasons]).

    Rules (README, D-O3):
      R0 device count <= 40;
      R1 nets VINP, VINN, VOUT, IREF are present (VDD/VSS may be implicit via bulk);
      R2 VINP and VINN touch only MOS gates and capacitor terminals (no DC current is
         drawn from the testbench's ideal input sources);
      R3 no shorted device: MOS with D == S, R/C with P == N;
      R4 bulk is the default rail or the device's own source;
      R5 every net other than VINP/VINN has a DC path (through R and MOS D-S
         channels; gates and capacitors do not conduct) to VDD or VSS -- this
         covers 'DC path at every MOS D and S', 'no floating gate', 'no undriven
         bias node' and 'IREF can sink the reference current';
      R6 VOUT is the drain or source of at least one MOS (VOUT driven);
      R7 every MOS gate net is DC-driven (R5) or is VINP/VINN.
    """
    why = []
    if len(devs) > MAX_DEVICES:
        why.append("R0 device count %d > %d" % (len(devs), MAX_DEVICES))
    present = set(nets_of(devs))
    for n in ("VINP", "VINN", "VOUT", "IREF"):
        if n not in present:
            why.append("R1 net %s absent" % n)
    for d in devs:
        p = d.pins()
        for pin, net in p.items():
            if net in ("VINP", "VINN"):
                ok = (d.is_mos and pin == "G") or d.type == "C"
                if not ok:
                    why.append("R2 %s pin %s on input %s" % (d.name, pin, net))
        if d.is_mos:
            if p["D"] == p["S"]:
                why.append("R3 %s shorted (D == S)" % d.name)
            rail = "VSS" if d.type == "NMOS" else "VDD"
            if p["B"] not in (rail, p["S"]):
                why.append("R4 %s bulk %s not %s or own source" % (d.name, p["B"], rail))
        elif p["P"] == p["N"]:
            why.append("R3 %s shorted (P == N)" % d.name)
    # DC connectivity: union-find over R and MOS D-S
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for n in present | {"VDD", "VSS"}:
        find(n)
    union("VDD", "VSS")                   # both are ideal-source driven
    for d in devs:
        p = d.pins()
        if d.is_mos:
            union(p["D"], p["S"])
        elif d.type == "R":
            union(p["P"], p["N"])
    rail = find("VSS")
    for n in sorted(present):
        if n in ("VINP", "VINN", "VDD", "VSS"):
            continue
        if find(n) != rail:
            why.append("R5 net %s has no DC path to a rail" % n)
    if "VOUT" in present and not any(d.is_mos and "VOUT" in (d.pins()["D"], d.pins()["S"])
                                     for d in devs):
        why.append("R6 VOUT is not a MOS drain/source")
    for d in devs:
        if d.is_mos:
            g = d.pins()["G"]
            if g not in ("VINP", "VINN", "VDD", "VSS") and find(g) != rail:
                why.append("R7 %s gate net %s floating" % (d.name, g))
    # de-duplicate, keep order
    out = []
    for w in why:
        if w not in out:
            out.append(w)
    return (not out), out

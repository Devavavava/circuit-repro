"""F2' single-edit space and the two-edit composer (PREREG-OPAMP-V0-D0 Stage 2 / Stage 3 step 4).

EDIT KINDS (descriptor tuples; k = edit index, 1 for a single edit, 1/2 for a two-edit design)
  ("addRC",  T, a, b)        add R or C (T) between existing nets a < b       new name RX<k>/CX<k>
  ("addMOS", T, d, g, s)     add one NMOS/PMOS (T); each of D/G/S on an existing net or on the
                             ONE new net nx<k>; bulk = default rail            new name MX<k>
  ("del",    name)           delete one element
  ("rewire", name, pin, n)   move one terminal (MOS D/G/S, passive P/N) of one element to another
                             existing net or to the new net nx<k> (bulk is not a rewire target;
                             a MOS whose bulk is tied to its source keeps bulk = source)
Nets offered: every net of the circuit plus VDD and VSS (always), in the fixed order
SPECIAL first (VINP VINN VOUT VDD VSS IREF), then internal nets sorted.

Enumeration order is deterministic: addRC (R then C, pairs in net order), addMOS (NMOS then
PMOS, D, G, S nested in net order + new net last), del (netlist order), rewire (netlist order,
pin order, net order). D==S additions and the D/S mirror image of an addition are generated
(they are part of the raw count) and removed by dedupe / the pre-filter.

CANONICAL FORM (dedupe): the circuit up to renaming of internal nets and of devices, keeping
the matched-group partition (which changes the sizing problem). A device is (type, terminal
nets) with MOS D/S treated as unordered when the bulk is the default rail (BSIM4 is
source/drain symmetric; with bulk = own source the order is kept), R/C terminals unordered; a
group is the sorted tuple of its members; the circuit is the sorted tuple of groups,
minimised over all labelings of the internal nets that respect a colour refinement
(exact isomorphism test as long as the refined classes are small; README D-O17).
"""
import hashlib
import itertools
import random
from collections import OrderedDict, defaultdict

from . import dialect as DL

KINDS = ("addRC", "addMOS", "del", "rewire")
RAILS = ("VDD", "VSS")
MAX_PERMS = 40320


# ------------------------------------------------------------------ helpers
def net_order(devs):
    present = set(DL.nets_of(devs)) | set(RAILS)
    sp = [n for n in DL.SPECIAL if n in present]
    return sp + sorted(n for n in present if n not in DL.SPECIAL)


def _new_net(k):
    return "nx%d" % k


def _copy(devs):
    return [DL.Device(d.type, d.name, d.nets) for d in devs]


def raw_edits(devs, k=1):
    """All edit descriptors of `devs` (deterministic order; see module doc)."""
    nets = net_order(devs)
    nn = _new_net(k)
    out = []
    for t in ("R", "C"):
        for a, b in itertools.combinations(nets, 2):
            out.append(("addRC", t, a, b))
    ext = nets + [nn]
    for t in ("NMOS", "PMOS"):
        for d in ext:
            for g in ext:
                for s in ext:
                    out.append(("addMOS", t, d, g, s))
    for d in devs:
        out.append(("del", d.name))
    for d in devs:
        pins = ("D", "G", "S") if d.is_mos else ("P", "N")
        cur = d.pins()
        for pin in pins:
            for n in ext:
                if n != cur[pin]:
                    out.append(("rewire", d.name, pin, n))
    return out


def apply_edit(devs, e, k=1):
    """New device list after edit descriptor e (input untouched)."""
    out = _copy(devs)
    kind = e[0]
    if kind == "addRC":
        out.append(DL.Device(e[1], "%sX%d" % (e[1], k), (e[2], e[3])))
    elif kind == "addMOS":
        t, d, g, s = e[1:]
        out.append(DL.Device(t, "MX%d" % k, (d, g, s, "VSS" if t == "NMOS" else "VDD")))
    elif kind == "del":
        out = [d for d in out if d.name != e[1]]
    elif kind == "rewire":
        name, pin, net = e[1:]
        for i, d in enumerate(out):
            if d.name == name:
                if d.is_mos:
                    n = list(d.nets)
                    j = "DGS".index(pin)
                    if pin == "S" and n[3] == n[2]:
                        n[3] = net           # bulk tied to source follows the source
                    n[j] = net
                else:
                    n = list(d.nets)
                    n["PN".index(pin)] = net
                out[i] = DL.Device(d.type, d.name, n)
    else:
        raise ValueError(e)
    return out


def describe(e):
    return " ".join(str(x) for x in e)


# ------------------------------------------------------------------ canonical form
def _dev_terms(d):
    """(type, ordered-terminal tuple, symmetric?) with bulk encoded as 'rail'/'src'/net."""
    if d.is_mos:
        D, G, S, B = d.nets
        rail = "VSS" if d.type == "NMOS" else "VDD"
        if B == rail:
            return d.type + "/r", (D, G, S), True
        if B == S:
            return d.type + "/s", (D, G, S), False
        return d.type + "/b:" + B, (D, G, S), False
    return d.type, d.nets, True


def _dev_sig(d, lab):
    t, nets, sym = _dev_terms(d)
    m = tuple(lab.get(n, n) for n in nets)
    if d.is_mos:
        if sym:
            ds = tuple(sorted((m[0], m[2])))
            return (t, ds, m[1])
        return (t, (m[0], m[2]), m[1])
    return (t, tuple(sorted(m)))


def _refine(devs, internal):
    """Colour refinement of internal nets; returns ordered list of classes (lists of nets)."""
    col = {n: "" for n in internal}

    def c(n):
        return col.get(n, "S:" + n)
    inc = defaultdict(list)          # net -> [(dev, role)]
    for d in devs:
        t, nets, sym = _dev_terms(d)
        if d.is_mos:
            roles = ("DS" if sym else "D", "G", "DS" if sym else "S")
        else:
            roles = ("T", "T")
        for n, r in zip(nets, roles):
            inc[n].append((d, t, r, nets, roles))
    for _ in range(4):
        new = {}
        for n in internal:
            items = []
            for d, t, r, nets, roles in inc[n]:
                others = tuple(sorted((rr, c(nn)) for nn, rr in zip(nets, roles)))
                items.append((t, r, others))
            new[n] = hashlib.sha1(repr((col[n], sorted(items))).encode()).hexdigest()[:16]
        col = new
    classes = OrderedDict()
    for n in sorted(internal, key=lambda x: (col[x], x)):
        classes.setdefault(col[n], []).append(n)
    return list(classes.values())


def canon_key(devs):
    """Canonical string of a device list (see module doc)."""
    internal = [n for n in DL.nets_of(devs) if n not in DL.SPECIAL]
    classes = _refine(devs, internal)
    groups = defaultdict(list)
    for d in devs:
        groups[DL.group_of(d.name)].append(d)
    glist = list(groups.values())
    n_perm = 1
    for cl in classes:
        for i in range(2, len(cl) + 1):
            n_perm *= i
    best = None
    perms = itertools.product(*[itertools.permutations(cl) for cl in classes])
    if n_perm > MAX_PERMS:
        perms = [tuple(tuple(cl) for cl in classes)]
    for combo in perms:
        lab, i = {}, 0
        for cl in combo:
            for n in cl:
                lab[n] = "i%d" % i
                i += 1
        key = tuple(sorted(tuple(sorted(_dev_sig(d, lab) for d in g)) for g in glist))
        if best is None or key < best:
            best = key
    return repr(best)


def key_hash(key):
    return hashlib.sha1(key.encode()).hexdigest()[:16]


# ------------------------------------------------------------------ F2'
def f2prime(text):
    """Enumerate the F2' single-edit space of a netlist.

    Returns dict: counts {raw, by_kind_raw, unique, by_kind_unique, prefilter_ok,
    by_kind_ok, prefilter_reject_reasons}, candidates [ {i, edit, kind, netlist, key,
    prefilter_ok, why} ] for every UNIQUE design (first descriptor in enumeration order),
    in enumeration order; `ok` = the pre-filtered list (what Stage 3 screens)."""
    base = DL.parse(text)
    base_key = canon_key(base)
    raw = raw_edits(base, 1)
    seen = {base_key: None}
    cands = []
    by_raw = defaultdict(int)
    n_same_as_anchor = 0
    for e in raw:
        by_raw[e[0]] += 1
        dv = apply_edit(base, e, 1)
        key = canon_key(dv)
        if key in seen:
            if key == base_key:
                n_same_as_anchor += 1
            continue
        seen[key] = len(cands)
        ok, why = DL.prefilter(dv)
        cands.append({"i": len(cands), "edit": list(e), "kind": e[0], "key": key_hash(key),
                      "netlist": DL.format_netlist(dv), "prefilter_ok": ok, "why": why})
    by_u, by_ok, reasons = defaultdict(int), defaultdict(int), defaultdict(int)
    for c in cands:
        by_u[c["kind"]] += 1
        if c["prefilter_ok"]:
            by_ok[c["kind"]] += 1
        else:
            reasons[c["why"][0].split()[0]] += 1
    counts = {"raw": len(raw), "by_kind_raw": dict(by_raw), "same_as_anchor": n_same_as_anchor,
              "unique": len(cands), "by_kind_unique": dict(by_u),
              "prefilter_ok": sum(by_ok.values()), "by_kind_ok": dict(by_ok),
              "prefilter_reject_first_reason": dict(reasons),
              "n_nets": len(net_order(base)), "n_devices": len(base)}
    ok = [c for c in cands if c["prefilter_ok"]]
    return {"anchor_key": key_hash(base_key), "counts": counts, "candidates": cands, "ok": ok,
            "all_keys": set(seen)}


def two_edit_sample(text, n, seed, exclude_keys=None, max_tries=None):
    """Seeded random two-edit designs: edit 1 uniform over raw_edits(anchor, 1), edit 2
    uniform over raw_edits(result, 2); keep a design iff it passes the pre-filter, differs
    from the anchor and from every single-edit design (exclude_keys, canonical strings; pass
    f2prime(text)['all_keys']) and from every design already kept. Deterministic in seed."""
    rng = random.Random(seed)
    base = DL.parse(text)
    excl = set(exclude_keys or ()) | {canon_key(base)}
    raw1 = raw_edits(base, 1)
    out, seen = [], set()
    stats = defaultdict(int)
    max_tries = max_tries or 400 * n
    tries = 0
    while len(out) < n and tries < max_tries:
        tries += 1
        e1 = rng.choice(raw1)
        d1 = apply_edit(base, e1, 1)
        e2 = rng.choice(raw_edits(d1, 2))
        d2 = apply_edit(d1, e2, 2)
        ok, why = DL.prefilter(d2)
        if not ok:
            stats["prefilter_reject"] += 1
            continue
        key = canon_key(d2)
        if key in excl:
            stats["equals_anchor_or_single_edit"] += 1
            continue
        if key in seen:
            stats["duplicate"] += 1
            continue
        seen.add(key)
        out.append({"j": len(out), "edits": [list(e1), list(e2)], "key": key_hash(key),
                    "netlist": DL.format_netlist(d2)})
    stats["tries"] = tries
    stats["kept"] = len(out)
    return out, dict(stats)

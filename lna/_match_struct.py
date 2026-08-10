"""Structural instrument for the INPUT NETWORK of a topology (WP-MATCH, FINDINGS 29).

§27.6 isolated the generator's wall: its `dhruva-l5` candidates reach NF ~1 dB at
22 dB gain and stop at S11 -4.46 / -0.99. That is a *matching* question, and the
first thing it needs is a measurement of what the input port of a circuit actually
looks like -- not an analytic matching condition (explicitly forbidden), just a
census of devices and connectivity at the port.

Everything here is graph arithmetic over `Topology.nodes`. No impedance, no
formula, nothing that could seed a size or a topology: it counts elements and
reports which nodes they touch.

Definitions (all measured, all reported so a reader can re-derive them):

    vin           the electrical node the VIN* net lands on
    rails         the nodes VDD / VSS / 0 land on
    series[k]     a 2-terminal passive of kind k on `vin` whose other end is NOT
                  a rail  (it carries signal onward)
    shunt[k]      a 2-terminal passive of kind k on `vin` whose other end IS a
                  rail  (it terminates the port)
    gate_direct   a FET GATE sits on `vin` with no passive in between
    src_direct    a FET SOURCE sits on `vin` with no passive in between
    hops          fewest passives between `vin` and the nearest node carrying a
                  FET gate or source (0 == direct)
    degen[k]      passives of kind k between the first-reached FET's SOURCE and a
                  rail (source degeneration)
    fb[k]         passives of kind k with one end on the input side (vin or a
                  node reached from vin over passives before any FET) and the
                  other on a node carrying a FET DRAIN (a feedback element)
    n_match_par   |size.match_param_names| -- the parameters the existing
                  match-first search would be allowed to move on this graph,
                  computed structurally (every name treated as sizable)

`order` is the headline scalar: series + shunt element count at the port. It is a
count, not a filter order in the network-theory sense -- named for what it counts.
"""
import os
import sys
from collections import defaultdict, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from topology import Topology, base_of, PIN_RE          # noqa: E402

PASSIVE = ("R", "C", "L")
FET = ("NM", "PM")
BJT = ("NPN", "PNP")


class _AllSizable(object):
    """`match_param_names` only tests `name in sizable`; this makes the answer
    structural (what the graph *offers*) rather than bias-insert dependent."""

    def __contains__(self, k):
        return True

    def get(self, k, d=None):
        return d


def _devpins(topo):
    pin2root = {m: r for r, members in topo.nodes.items() for m in members}
    dp = defaultdict(dict)
    for p in topo.pins:
        mm = PIN_RE.match(p)
        if mm and p in pin2root:
            dp[mm.group("dev")][mm.group("pin")] = pin2root[p]
    return dp, pin2root


def analyze(topo):
    """-> dict of structural input-port measurements (or {'ok': False, ...})."""
    dp, pin2root = _devpins(topo)
    net2root = {m: r for r, members in topo.nodes.items()
                for m in members if m in topo.nets}
    vin_net = next((n for n in sorted(topo.nets) if n.startswith("VIN")), None)
    out = {"ok": False, "n_devices": topo.n_devices}
    if vin_net is None:
        out["why"] = "no VIN net"
        return out
    vin = net2root.get(vin_net)
    if vin is None:
        out["why"] = "VIN net unrooted"
        return out
    rails = {net2root.get(n) for n in ("VDD", "VSS", "0")}
    rails.discard(None)
    vout_net = next((n for n in sorted(topo.nets) if n.startswith("VOUT")), None)
    vout = net2root.get(vout_net) if vout_net else None

    # passive adjacency over nodes
    adj = defaultdict(list)
    pas = []
    for d in topo.devices:
        if base_of(d) not in PASSIVE:
            continue
        pp = dp.get(d, {})
        if "P" in pp and "N" in pp and pp["P"] != pp["N"]:
            adj[pp["P"]].append((d, pp["N"]))
            adj[pp["N"]].append((d, pp["P"]))
            pas.append((d, pp["P"], pp["N"]))

    # active pins by node
    gate, src, drn = defaultdict(list), defaultdict(list), defaultdict(list)
    for d in topo.devices:
        b = base_of(d)
        if b in FET:
            g, s, dd = "G", "S", "D"
        elif b in BJT:
            g, s, dd = "B", "E", "C"
        else:
            continue
        for pin, bucket in ((g, gate), (s, src), (dd, drn)):
            n = dp[d].get(pin)
            if n is not None:
                bucket[n].append(d)

    def kinds(devs):
        c = defaultdict(int)
        for d in devs:
            c[base_of(d)] += 1
        return dict(c)

    series, shunt = [], []
    for d, other in adj[vin]:
        (shunt if other in rails else series).append(d)

    # Walk out from VIN over 2-terminal passives, stopping at (and including) any
    # node that carries an active terminal. `port_src` / `port_gate` are reported
    # SEPARATELY and are not exclusive: a gm-boosted common gate has the CG
    # source and the booster's gate on the same node, and collapsing that to one
    # "first pin" mislabels the whole family.
    hops, first_dev, first_pin = None, None, None
    port_src, port_gate = False, False
    seen, dq = {vin}, deque([(vin, 0)])
    inside = {vin}                       # the input side, for the feedback test
    while dq:
        u, h = dq.popleft()
        if gate[u] or src[u]:
            if hops is None:
                hops = h
            if src[u]:
                port_src = True
                if first_dev is None:
                    first_dev, first_pin = src[u][0], "S"
            if gate[u]:
                port_gate = True
                if first_dev is None:
                    first_dev, first_pin = gate[u][0], "G"
            continue                     # do not walk past the first stage
        for d, v in adj[u]:
            if v in seen or v in rails:
                continue
            seen.add(v)
            inside.add(v)
            dq.append((v, h + 1))

    degen = []
    if first_dev is not None:
        sn = dp[first_dev].get("S") if base_of(first_dev) in FET else dp[first_dev].get("E")
        if sn is not None and sn not in rails:
            for d, other in adj[sn]:
                if other in rails:
                    degen.append(d)

    fb = []
    for d, a, b in pas:
        if (a in inside and drn[b]) or (b in inside and drn[a]):
            fb.append(d)
    fb_out = [d for d, a, b in pas
              if vout is not None and ((a in inside and b == vout)
                                       or (b in inside and a == vout))]

    try:
        from size import match_param_names
        npar = len(match_param_names(topo, _AllSizable()))
    except Exception:
        npar = None

    out.update({
        "ok": True,
        "series": kinds(series), "n_series": len(series),
        "shunt": kinds(shunt), "n_shunt": len(shunt),
        "order": len(series) + len(shunt),
        "gate_direct": bool(gate[vin]), "src_direct": bool(src[vin]),
        "port_src": port_src, "port_gate": port_gate,
        "drain_on_vin": bool(drn[vin]),
        "hops": hops,
        "first_dev": first_dev, "first_pin": first_pin,
        "degen": kinds(degen), "n_degen": len(degen),
        "fb": kinds(fb), "n_fb": len(fb),
        "n_fb_to_vout": len(fb_out),
        "n_match_par": npar,
        "n_passive": len(pas),
        "vin_shared_with_vout": (vout is not None and vout == vin),
    })
    return out


# ---------------------------------------------------------------- classifier
def has_match_network(a):
    """The one binary this study uses everywhere: does the port carry ANY passive
    network at all, or is the source wired straight onto an active terminal?

    Deliberately the weakest possible criterion -- it asks only whether there is
    something to size, not whether it could match. A design that fails this can
    have no parametric match by construction; one that passes may still fail."""
    return bool(a.get("ok")) and a.get("order", 0) > 0


def has_reactive_series(a):
    """Series element at the port that is not a resistor (a DC block / gate
    inductor). Counted separately because a series R alone is the one 'network'
    that cannot be tuned without burning the signal."""
    return bool(a.get("ok")) and any(k in ("C", "L") for k in a.get("series", {}))


def summarize(rows, label=""):
    """rows: [(name, analysis)] -> a dict of pool-level fractions."""
    ok = [a for _, a in rows if a.get("ok")]
    n = len(ok) or 1
    def frac(f):
        return sum(1 for a in ok if f(a)) / n
    hop_hist = defaultdict(int)
    for a in ok:
        hop_hist["direct" if a["hops"] == 0 else (str(a["hops"]) if a["hops"] is not None
                                                  else "none")] += 1
    return {
        "label": label, "n": len(rows), "n_ok": len(ok),
        "match_net": frac(has_match_network),
        "reactive_series": frac(has_reactive_series),
        "series_L": frac(lambda a: "L" in a["series"]),
        "series_C": frac(lambda a: "C" in a["series"]),
        "shunt_any": frac(lambda a: a["n_shunt"] > 0),
        "gate_direct": frac(lambda a: a["gate_direct"]),
        "src_direct": frac(lambda a: a["src_direct"]),
        "port_src": frac(lambda a: a["port_src"]),
        "port_gate_only": frac(lambda a: a["port_gate"] and not a["port_src"]),
        "degen": frac(lambda a: a["n_degen"] > 0),
        "degen_L": frac(lambda a: "L" in a["degen"]),
        "fb": frac(lambda a: a["n_fb"] > 0),
        "mean_order": sum(a["order"] for a in ok) / n,
        "mean_match_par": sum((a["n_match_par"] or 0) for a in ok) / n,
        "hops": dict(hop_hist),
    }


HDR = (f"{'pool':<26} {'n':>4} {'match':>7} {'react':>7} {'sL':>6} {'sC':>6} "
       f"{'shunt':>6} {'gdir':>6} {'sdir':>6} {'degen':>6} {'dgnL':>6} "
       f"{'fb':>6} {'ordr':>5} {'npar':>5}")


def line(s):
    return (f"{s['label']:<26} {s['n_ok']:>4} {s['match_net']:>7.3f} "
            f"{s['reactive_series']:>7.3f} {s['series_L']:>6.3f} {s['series_C']:>6.3f} "
            f"{s['shunt_any']:>6.3f} {s['gate_direct']:>6.3f} {s['src_direct']:>6.3f} "
            f"{s['degen']:>6.3f} {s['degen_L']:>6.3f} {s['fb']:>6.3f} "
            f"{s['mean_order']:>5.2f} {s['mean_match_par']:>5.1f}")

"""VM features: device-net graph from harness tokens, hand features, spec vector.

Graph: Topology(tokens).nodes (union-find over wire edges) gives electrical nodes; a
pin token `DEV_ROLE` attaches device DEV to the node holding it. Node kinds: VIN1,
VOUT1, VDD, VSS, other (bias / internal). Edge type = (device type, pin role) with
MOS drain/gate/source/bulk distinct per NM/PM and 2-terminal passives role-merged.
"""
import math
import os
import sys
from collections import Counter, defaultdict

import numpy as np

REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
if REPO + "/lna" not in sys.path:
    sys.path.insert(0, REPO + "/lna")
from topology import Topology, PIN_RE, base_of  # noqa: E402

DEV_TYPES = ["NM", "PM", "R", "C", "L"]
EDGE_TYPES = ["NM_D", "NM_G", "NM_S", "NM_B", "PM_D", "PM_G", "PM_S", "PM_B", "R", "C", "L"]
SPECIAL = ["VIN1", "VOUT1", "VDD", "VSS"]
PROFILES = ["rl", "legacy-lib", "stab-gate", "stab-inloop"]


def parse_graph(tokens):
    """-> dict(devs=[(name, type)], nodes=[kind], edges=[(dev_i, node_j, etype)])."""
    topo = Topology(list(tokens))
    node_of_pin, node_names = {}, []
    for root, members in topo.nodes.items():
        nets = {m for m in members if m in topo.nets}
        kind = next((s for s in SPECIAL if s in nets), "OTHER")
        j = len(node_names)
        node_names.append(kind)
        for m in members:
            if PIN_RE.match(m):
                node_of_pin[m] = j
    devs, dix, edges = [], {}, []
    for p in sorted(node_of_pin):
        mm = PIN_RE.match(p)
        d, role = mm.group("dev"), mm.group("pin")
        t = base_of(d)
        if t not in DEV_TYPES:
            t = "R"                     # never observed in this data (checked in build)
        if d not in dix:
            dix[d] = len(devs)
            devs.append((d, t))
        et = f"{t}_{role}" if t in ("NM", "PM") else t
        if et not in EDGE_TYPES:
            continue
        edges.append((dix[d], node_of_pin[p], et))
    return {"devs": devs, "nodes": node_names, "edges": edges}


def hand_features(g):
    devs, nodes, edges = g["devs"], g["nodes"], g["edges"]
    f = {}
    cnt = Counter(t for _, t in devs)
    for t in DEV_TYPES:
        f[f"n_{t}"] = cnt.get(t, 0)
    f["n_dev"] = len(devs)
    f["n_mos"] = cnt.get("NM", 0) + cnt.get("PM", 0)
    f["n_node_other"] = sum(1 for k in nodes if k == "OTHER")
    deg = Counter(j for _, j, _ in edges)
    f["max_deg_other"] = max([deg[j] for j, k in enumerate(nodes) if k == "OTHER"] or [0])
    f["n_deg1_other"] = sum(1 for j, k in enumerate(nodes) if k == "OTHER" and deg[j] == 1)
    # attachment counts per special net and edge type
    for s in SPECIAL:
        for et in EDGE_TYPES:
            if et.endswith("_B"):
                continue
            f[f"{s}:{et}"] = sum(1 for _, j, e in edges if nodes[j] == s and e == et)
        f[f"{s}:deg"] = sum(1 for _, j, _ in edges if nodes[j] == s)
    # per-device pin -> node
    pins = defaultdict(dict)
    for i, j, e in edges:
        if "_" in e:                    # MOS pins only; passives use `two` below
            pins[i][e.split("_")[-1]] = j
    # 2-terminal: collect both node ids
    two = defaultdict(list)
    for i, j, e in edges:
        if e in ("R", "C", "L"):
            two[i].append(j)
    mos = [i for i, (_, t) in enumerate(devs) if t in ("NM", "PM")]
    ntype = lambda j: nodes[j]                                          # noqa: E731
    f["diode_mos"] = sum(1 for i in mos if pins[i].get("G") is not None and pins[i].get("G") == pins[i].get("D"))
    d_nodes = Counter(pins[i].get("D") for i in mos)
    s_nodes = Counter(pins[i].get("S") for i in mos)
    f["cascode_pairs"] = sum(1 for i in mos for k in mos if i != k and pins[i].get("D") is not None
                             and pins[i].get("D") == pins[k].get("S") and ntype(pins[i]["D"]) == "OTHER")
    f["shared_drain_np"] = sum(1 for j in d_nodes if j is not None and any(
        devs[i][1] == "NM" and pins[i].get("D") == j for i in mos) and any(
        devs[i][1] == "PM" and pins[i].get("D") == j for i in mos))
    gates = {pins[i].get("G") for i in mos}
    drains = {pins[i].get("D") for i in mos}
    sources = {pins[i].get("S") for i in mos}
    vss = {j for j, k in enumerate(nodes) if k == "VSS"}
    vdd = {j for j, k in enumerate(nodes) if k == "VDD"}
    vin = {j for j, k in enumerate(nodes) if k == "VIN1"}
    vout = {j for j, k in enumerate(nodes) if k == "VOUT1"}
    for t in ("R", "C", "L"):
        ids = [i for i, (_, tt) in enumerate(devs) if tt == t]
        pairs = [tuple(sorted(two[i])) for i in ids if len(two[i]) == 2]
        f[f"{t}_src_degen"] = sum(1 for a, b in pairs if (a in sources and b in vss) or (b in sources and a in vss))
        f[f"{t}_drain_gate_fb"] = sum(1 for a, b in pairs if (a in drains and b in gates) or (b in drains and a in gates))
        f[f"{t}_in_out"] = sum(1 for a, b in pairs if (a in vin and b in vout) or (b in vin and a in vout))
        f[f"{t}_in_gate"] = sum(1 for a, b in pairs if (a in vin and b in gates) or (b in vin and a in gates))
        f[f"{t}_load_vdd"] = sum(1 for a, b in pairs if (a in drains and b in vdd) or (b in drains and a in vdd))
        f[f"{t}_in_shunt"] = sum(1 for a, b in pairs if (a in vin and b in (vss | vdd)) or (b in vin and a in (vss | vdd)))
        f[f"{t}_self"] = sum(1 for a, b in pairs if a == b)
    tank = Counter(tuple(sorted(two[i])) for i, (_, t) in enumerate(devs) if t == "L" and len(two[i]) == 2)
    ctank = Counter(tuple(sorted(two[i])) for i, (_, t) in enumerate(devs) if t == "C" and len(two[i]) == 2)
    f["lc_parallel"] = sum(1 for k in tank if k in ctank)
    f["gate_on_vin"] = sum(1 for i in mos if pins[i].get("G") in vin)
    f["source_on_vin"] = sum(1 for i in mos if pins[i].get("S") in vin)
    f["drain_on_vout"] = sum(1 for i in mos if pins[i].get("D") in vout)
    f["n_stages_proxy"] = len({pins[i].get("D") for i in mos} - vdd - vss)
    return f


def _lg(x):
    return math.log10(x) if x and x > 0 else 0.0


def spec_vector(sp, profile, budget):
    lim = sp["lim"]
    wide = sp["band_type"] == "wideband"
    nf_name = "nf_max_db" if "nf_max_db" in lim else "nf_db"
    nf = lim.get(nf_name, {}).get("max")
    s11 = (lim.get("s11_max_db") or lim.get("s11_db") or {}).get("max")
    s21 = (lim.get("s21_db") or {}).get("min")
    rip = (lim.get("s21_ripple_db") or {}).get("max")
    idd = (lim.get("idd_ma") or {}).get("max")
    f0, flo, fhi = sp.get("f0") or 0, sp.get("f_lo") or 0, sp.get("f_hi") or 0
    obj = sp.get("obj") or {}
    wnf = obj.get("nf_db", obj.get("nf_max_db", 0.0))
    v = {
        "wide": float(wide), "lf0": _lg(f0) - 9, "lflo": _lg(flo) - 9, "lfhi": _lg(fhi) - 9,
        "lbw": math.log(fhi / flo) if flo and fhi else 0.0,
        "nf": nf if nf is not None else 0.0, "nf_band": float(nf_name == "nf_max_db"),
        "nf_has": float(nf is not None),
        "s11": s11 if s11 is not None else 0.0, "s11_band": float("s11_max_db" in lim),
        "s21": s21 if s21 is not None else 0.0,
        "rip": rip if rip is not None else 0.0, "rip_has": float(rip is not None),
        "lidd": math.log(idd) if idd else 0.0, "idd": idd or 0.0,
        "mu": float("mu_min" in lim),
        "maxL": float(min(sp.get("max_inductors") or 4, 4)),
        "w_nf": wnf, "w_s21": obj.get("s21_db", 0.0), "w_idd": obj.get("idd_ma", 0.0),
        "lbudget": math.log2((budget or 2500) / 2500.0),
    }
    pf = "rl" if profile in ("rl-v1", "rl-v1.1") else profile
    for p in PROFILES:
        v[f"prof_{p}"] = float(pf == p)
    return v


def build_arrays(rows, tokmap, specs):
    """-> hand matrix H, spec matrix S, graph tensors, names."""
    gcache, hcache = {}, {}
    for r in rows:
        t = r["tok"]
        if t not in gcache:
            gcache[t] = parse_graph(tokmap[t])
            hcache[t] = hand_features(gcache[t])
    hnames = sorted(next(iter(hcache.values())).keys())
    snames = sorted(spec_vector(next(iter(specs.values())), "rl-v1", 2500).keys())
    H = np.array([[hcache[r["tok"]][k] for k in hnames] for r in rows], dtype=np.float32)
    S = np.array([[spec_vector(specs[r["spec_sha"]], r["profile"], r["budget"])[k] for k in snames]
                  for r in rows], dtype=np.float32)
    return H, S, hnames, snames, gcache


def graph_lists(toks, gcache):
    """Per unique token hash: (dev type ids, node kind ids, edge src dev, edge dst node,
    edge type id) as int arrays -- collated into a disjoint-union batch by the model."""
    ei = {e: k for k, e in enumerate(EDGE_TYPES)}
    out = {}
    for t in toks:
        g = gcache[t]
        dt = np.array([DEV_TYPES.index(ty) for _, ty in g["devs"]], dtype=np.int64)
        nk = np.array([(SPECIAL.index(k) if k in SPECIAL else len(SPECIAL)) for k in g["nodes"]],
                      dtype=np.int64)
        es = np.array([i for i, _, _ in g["edges"]], dtype=np.int64)
        ed = np.array([j for _, j, _ in g["edges"]], dtype=np.int64)
        et = np.array([ei[e] for _, _, e in g["edges"]], dtype=np.int64)
        out[t] = (dt, nk, es, ed, et)
    return out

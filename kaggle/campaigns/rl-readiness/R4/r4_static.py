"""R4 items (a) + (b, structural part): classify EVERY recorded "solution"
topology against its cell spec's topology limits and a set of degeneracy
detectors. No simulation.

Population (unique (cell, candidate) pairs, each tagged with where it was
recorded feasible):
  tpl      the two reference templates on their 8 cells each (claude-solutions)
  ec       bench-v12-audit E-c: every (cell, cid) feasible at >= 1 seed (lib spec)
  ec_conf  ... the subset E-c CONFIRMED (seed-1 feasible, the E-c verdict set)
  ed       bench-v12-audit E-d: every Qwen (cell, key) feasible at >= 1 seed
  s1       S-1 inloop final-feasible (stab spec + in-loop wide stability)
  sg       stability-gate final-feasible (stab spec, gate only)
  r4       this campaign's inloop final-feasible runs (added by r4_post if present)

usage: r4_static.py <out.json>
"""
import sys, os, json
from collections import defaultdict, deque, Counter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r4_drv as D                                         # noqa: E402  (sets sys.path)
from topology import Topology, base_of, PIN_RE             # noqa: E402
from spec import Spec                                      # noqa: E402

AUD = D.AUD
RAILS = ("VDD", "VSS")


def population():
    pop = defaultdict(set)          # (cell, cand) -> {sources}
    for c in D.cells():
        pop[(c, "template")].add("tpl")
    ec_sum = json.load(open(AUD + "E-c/summary.json"))
    for c in ec_sum:
        for e in c["feasible_edits"]:
            if e["confirm_seed1"]:
                pop[(c["cell"], "ec:" + e["cid"])].add("ec_conf")
    for ln in open(AUD + "E-c/results.jsonl"):
        r = json.loads(ln)
        if r.get("feasible"):
            pop[(r["cell"], "ec:" + r["cid"])].add("ec")
    for ln in open(AUD + "E-d/score.jsonl"):
        r = json.loads(ln)
        if r["feasible"]:
            pop[(r["cell"], "ed:" + r["key"])].add("ed")
    for r in json.load(open(AUD + "S-1-stab-inloop/results.json"))["rows"]:
        if r["feasible"] and r["mode"] == "inloop" and r["exp"] != "regress":
            pop[(r["cell"], r["cand"])].add("s1")
    for r in json.load(open(AUD + "stability-gate/results.json"))["rows"]:
        if r["feasible"] and r["specmode"] == "stab":
            cand = r["cand"]
            if not (cand == "template" or cand.startswith("ec:")):
                cand = "anchor:" + cand
            pop[(r["cell"], cand)].add("sg")
    return pop


_TOK_CACHE = {}


def tokens(cell, cand):
    k = (cell if cand in ("template",) or cand.startswith("ed:") else "", cand)
    if k not in _TOK_CACHE:
        _TOK_CACHE[k] = D.tokens_for(cell, cand)
    return _TOK_CACHE[k]


def netlist(topo):
    """dev -> {pin: node}, node -> set(nets) using Topology's own node union."""
    pin2node, node_nets = {}, {}
    for root, members in topo.nodes.items():
        nets = sorted(m for m in members if m in topo.nets)
        name = nets[0] if nets else root
        node_nets[name] = set(nets)
        for m in members:
            if PIN_RE.match(m):
                pin2node[m] = name
    devs = {}
    for p, n in pin2node.items():
        m = PIN_RE.match(p)
        devs.setdefault(m.group("dev"), {})[m.group("pin")] = n
    return devs, node_nets


def node_of(node_nets, net):
    for n, nets in node_nets.items():
        if net in nets:
            return n
    return None


def reach(adj, start, blocked=()):
    if start is None:
        return set()
    seen, dq = {start}, deque([start])
    while dq:
        u = dq.popleft()
        for v in adj[u]:
            if v not in seen and v not in blocked:
                seen.add(v)
                dq.append(v)
    return seen


def classify(topo):
    devs, node_nets = netlist(topo)
    vin, vout = node_of(node_nets, "VIN1"), node_of(node_nets, "VOUT1")
    vdd, vss = node_of(node_nets, "VDD"), node_of(node_nets, "VSS")
    rails = {vdd, vss} - {None}
    f = {}
    kinds = {d: base_of(d) for d in devs}
    passives = [d for d in devs if kinds[d] in ("R", "C", "L")]
    mos = [d for d in devs if kinds[d] in ("NM", "PM")]
    # --- ports ---------------------------------------------------------------
    f["in_out_same_node"] = vin is not None and vin == vout
    f["port_on_rail"] = bool({vin, vout} & rails)
    direct = [kinds[d] for d in passives if {devs[d].get("P"), devs[d].get("N")} == {vin, vout}]
    f["direct_passive_in_out"] = sorted(direct)
    # passive-only path VIN1 -> VOUT1 avoiding rails (feedforward/feedback network)
    padj = defaultdict(set)
    for d in passives:
        a, b = devs[d].get("P"), devs[d].get("N")
        if a and b and a != b:
            padj[a].add(b)
            padj[b].add(a)
    f["passive_path_in_out"] = vout in reach(padj, vin, blocked=rails)
    # R-only path (DC-coupled resistive feed-through / feedback between ports)
    radj = defaultdict(set)
    for d in passives:
        if kinds[d] == "R":
            a, b = devs[d]["P"], devs[d]["N"]
            radj[a].add(b)
            radj[b].add(a)
    # --- shorted / dead devices ---------------------------------------------
    f["shorted_passive"] = sorted(d for d in passives if devs[d].get("P") == devs[d].get("N"))
    f["mos_d_eq_s"] = sorted(d for d in mos if devs[d].get("D") == devs[d].get("S"))
    f["mos_g_eq_s"] = sorted(d for d in mos if devs[d].get("G") == devs[d].get("S"))
    f["mos_all_on_rails"] = sorted(d for d in mos
                                   if {devs[d].get("D"), devs[d].get("S")} <= rails)
    # --- dangling nodes (one pin, not a port) --------------------------------
    cnt = Counter(n for d in devs for n in devs[d].values())
    port_nodes = {vin, vout} | rails
    f["dangling_nodes"] = sorted(n for n, k in cnt.items() if k == 1 and n not in port_nodes)
    # --- DC connectivity: R, L, MOS channel; gates are biased by bias.R-GATE ---
    dadj = defaultdict(set)
    for d in devs:
        if kinds[d] in ("R", "L"):
            a, b = devs[d]["P"], devs[d]["N"]
        elif kinds[d] in ("NM", "PM"):
            a, b = devs[d]["D"], devs[d]["S"]
        else:
            continue
        dadj[a].add(b)
        dadj[b].add(a)
    dc = set()
    for r in rails:
        dc |= reach(dadj, r)
    f["mos_ds_dc_floating"] = sorted(d for d in mos
                                     if devs[d]["D"] not in dc or devs[d]["S"] not in dc)
    # MOS with no DC path from its channel to BOTH rails (no DC current possible)
    def rail_reach(start, blocked):
        return reach(dadj, start, blocked=blocked)
    nocur = []
    for d in mos:
        # remove this device's own channel, see if D reaches a rail and S the other
        adj2 = defaultdict(set)
        for k, v in dadj.items():
            adj2[k] = set(v)
        a, b = devs[d]["D"], devs[d]["S"]
        adj2[a].discard(b)
        adj2[b].discard(a)
        ra = reach(adj2, a)
        rb = reach(adj2, b)
        if not ((vdd in ra and vss in rb) or (vss in ra and vdd in rb)):
            nocur.append(d)
    f["mos_no_dc_current_path"] = sorted(nocur)
    # --- is there an active device between the ports? -------------------------
    in_side = reach(padj, vin, blocked=rails)
    out_side = reach(padj, vout, blocked=rails)
    f["input_drives_mos"] = any(devs[d].get("G") in in_side or devs[d].get("S") in in_side
                                for d in mos)
    f["output_from_mos"] = any(devs[d].get("D") in out_side or devs[d].get("S") in out_side
                               for d in mos)
    f["n_dev"], f["n_mos"] = len(devs), len(mos)
    f["n_L"] = sum(1 for d in devs if kinds[d] == "L")
    f["n_R"] = sum(1 for d in devs if kinds[d] == "R")
    f["n_C"] = sum(1 for d in devs if kinds[d] == "C")
    f["floating_devices"] = sorted(topo.floating_devices())
    return f


DEGEN_KEYS = ("in_out_same_node", "port_on_rail", "shorted_passive", "mos_d_eq_s",
              "mos_g_eq_s", "mos_all_on_rails", "dangling_nodes",
              "mos_ds_dc_floating", "mos_no_dc_current_path", "floating_devices")


def main(out):
    pop = population()
    specs = {c: Spec.load(f"{D.LIB}/{c}/spec.yaml") for c in D.cells()}
    rows = []
    for (cell, cand), srcs in sorted(pop.items()):
        try:
            tok = tokens(cell, cand)
        except Exception as e:                                  # noqa: BLE001
            rows.append({"cell": cell, "cand": cand, "sources": sorted(srcs),
                         "error": repr(e)})
            continue
        topo = Topology(list(tok))
        passed, crit = specs[cell].structural_screen(topo)
        fl = classify(topo)
        rows.append({"cell": cell, "cand": cand, "sources": sorted(srcs),
                     "screen_passed": bool(passed),
                     "screen": {k: bool(v) for k, v in crit.items()},
                     "screen_failed": [k for k, v in crit.items() if not v],
                     "topo_limits": {k: specs[cell].topology.get(k) for k in
                                     ("device_budget", "max_inductors",
                                      "allow_inductorless", "reject_floating")},
                     "flags": fl,
                     "degenerate": [k for k in DEGEN_KEYS if fl.get(k)]})
    # --- summary --------------------------------------------------------------
    summ = {}
    for src in ("tpl", "ec", "ec_conf", "ed", "s1", "sg"):
        rs = [r for r in rows if src in r.get("sources", [])]
        c_fail = Counter(k for r in rs for k in r.get("screen_failed", []))
        c_deg = Counter(k for r in rs for k in r.get("degenerate", []))
        c_dir = Counter(tuple(r["flags"]["direct_passive_in_out"]) for r in rs
                        if r.get("flags", {}).get("direct_passive_in_out"))
        summ[src] = {"n": len(rs),
                     "screen_fail_any": sum(1 for r in rs if not r.get("screen_passed")),
                     "screen_fail_by_criterion": dict(c_fail),
                     "cells_with_any_passing": len({r["cell"] for r in rs
                                                    if r.get("screen_passed")}),
                     "cells": len({r["cell"] for r in rs}),
                     "degenerate_by_flag": dict(c_deg),
                     "direct_passive_in_out": {"+".join(k): v for k, v in c_dir.items()},
                     "passive_path_in_out": sum(1 for r in rs
                                                if r.get("flags", {}).get("passive_path_in_out")),
                     "no_input_mos": sum(1 for r in rs
                                         if not r.get("flags", {}).get("input_drives_mos", True)),
                     "no_output_mos": sum(1 for r in rs
                                          if not r.get("flags", {}).get("output_from_mos", True))}
    json.dump({"summary": summ, "rows": rows}, open(out, "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])

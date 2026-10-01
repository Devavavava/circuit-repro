"""Proposed guard G-PORT-DC (port DC isolation) + its impact, and two follow-up
probes on the cached sized witnesses (no re-sizing):

  noC1   open the DUT's own input DC-block C1 (1e-20 F) -> is C1 vestigial?
  P3dev  the P3 DC-independence test as a GUARD: |dIdd|/Idd and |dV(gate)|
         when VIN1 gets a DC-only 50 ohm-to-ground path (1 H choke, AC-identical)

G-PORT-DC (structural, zero sims): build the DUT's DC graph -- R and L are DC
edges, a MOS channel (D-S) is a DC edge, C is open -- and take the component
of VIN1. PASS iff that component contains no MOS terminal and no rail (VDD /
VSS / 0 / VB*): the DUT itself AC-couples its input, so the gate bias cannot
depend on the source's DC behaviour. All five bench anchors pass by
construction (each owns an input DC-block C at VIN1).

Run over: the 5 LNA anchors, every bench-v2 cell with status accepted (both
eras), and every cell in cells.jsonl (killed/validating too) for context.
usage: guard.py   (writes results/guard.json; needs envrun for the sim probes)
"""
import json
import os
import sys
from collections import Counter

REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for _p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
RUN = f"{REPO}/kaggle/campaigns/bench-v2/run"
OUT = f"{REPO}/kaggle/campaigns/bench-v2/motif-audit/results"
ANCH = f"{REPO}/kaggle/bench-anchors/lna"
RAILS = {"VDD", "VSS", "0", "GND"}


def parse_net(text):
    devs = []
    for ln in text.splitlines():
        t = ln.split()
        if not t or ln.lstrip().startswith("*"):
            continue
        devs.append((t[0].upper(), t[1], t[2:]))
    return devs


def port_dc_component(text):
    devs = parse_net(text)
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    mos_terms = set()
    for typ, _n, nets in devs:
        for n in nets:
            find(n)
        if typ in ("R", "L"):
            union(nets[0], nets[1])
        elif typ in ("NMOS", "PMOS"):
            d, g, s = nets[0], nets[1], nets[2]
            union(d, s)                      # channel conducts at DC
            mos_terms.update((d, g, s))
    root = find("VIN1")
    comp = {n for n in parent if find(n) == root}
    bad_rails = sorted(n for n in comp if n in RAILS or n.startswith("VB"))
    bad_mos = sorted(n for n in comp if n in mos_terms)
    return {"component": sorted(comp), "rails": bad_rails, "mos_nets": bad_mos,
            "pass": not bad_rails and not bad_mos}


def structural():
    rows = {}
    for f in sorted(os.listdir(ANCH)):
        if f.endswith(".net"):
            rows["anchor:" + f[:-4]] = port_dc_component(open(f"{ANCH}/{f}").read())
    cells = [json.loads(l) for l in open(f"{RUN}/cells.jsonl")]
    by_status = Counter()
    fail_by_status = Counter()
    acc = {}
    for c in cells:
        if not c.get("netlist"):
            continue
        g = port_dc_component(c["netlist"])
        st = (c.get("status"), c.get("era_tag"))
        by_status[st] += 1
        if not g["pass"]:
            fail_by_status[st] += 1
        if c.get("status") == "accepted":
            acc[c["name"]] = dict(g, era=c.get("era_tag"), cls=c.get("cls"),
                                  has_L_IN_G="add:L:IN-G" in (c.get("cls") or "")
                                  or any(s.get("op") == "add" and s.get("t") == "L"
                                         and set(s.get("nets", [])) == {"VIN1", "n1"}
                                         for s in c.get("script", [])))
    return rows, acc, {f"{k[0]}/{k[1]}": v for k, v in by_status.items()}, \
        {f"{k[0]}/{k[1]}": v for k, v in fail_by_status.items()}


def sim_probes():
    import motif_audit as MA
    MA.set_rl_v1_env()
    import size as SZ
    out = {}
    for cell in sorted(os.listdir(OUT)):
        f = f"{OUT}/{cell}/sized_P0.json"
        if not os.path.exists(f):
            continue
        s = json.load(open(f))
        if not s.get("params"):
            continue
        spec = MA.load_spec(f"{RUN}/cells/{cell}/spec.yaml")
        body, params = s["body"], s["params"]
        gate = MA.gate_of_input_device(body)
        r = {}
        c0, c3 = {}, {}
        m0 = SZ.eval_metrics(body, params, spec, op_capture=c0)
        m3 = SZ.eval_metrics(MA.port_variant(body, "P3"), params, spec, op_capture=c3)
        i0, i3 = m0.get("idd_ma"), m3.get("idd_ma")
        g0 = (c0.get("nodes") or {}).get(gate.lower())
        g3 = (c3.get("nodes") or {}).get(gate.lower())
        r["P3_dIdd_rel"] = abs(i3 - i0) / i0 if i0 else None
        r["P3_dVgate_V"] = (g3 - g0) if g0 is not None and g3 is not None else None
        r["P3_guard_pass"] = bool(r["P3_dIdd_rel"] is not None and r["P3_dIdd_rel"] < 0.01
                                  and abs(r["P3_dVgate_V"] or 0) < 0.01)
        if "pC1V" in params and "CC1 " in body:
            mc = SZ.eval_metrics(body, dict(params, pC1V="1e-20"), spec)
            r["noC1_spec_feasible"] = bool(mc and spec.feasible(mc)[0])
            r["noC1_metrics_delta"] = {k: (round(mc[k] - m0[k], 4) if mc and isinstance(mc.get(k), (int, float)) and isinstance(m0.get(k), (int, float)) else None)
                                       for k in ("s11_max_db", "s21_db", "s21_ripple_db", "nf_max_db", "idd_ma")}
            r["C1_F"] = float(params["pC1V"])
        out[cell] = r
    return out


if __name__ == "__main__":
    anchors, acc, n_by, fail_by = structural()
    res = {"anchors": anchors, "accepted": acc, "cells_by_status_era": n_by,
           "guard_fail_by_status_era": fail_by}
    n_cur = [k for k, v in acc.items() if v["era"] == "amendment-1"]
    res["impact_current_accepted"] = {
        "n_accepted": len(n_cur),
        "n_removed": sum(not acc[k]["pass"] for k in n_cur),
        "removed": sorted(k for k in n_cur if not acc[k]["pass"]),
        "kept": sorted(k for k in n_cur if acc[k]["pass"])}
    if "--sims" in sys.argv:
        res["sim_probes"] = sim_probes()
    json.dump(res, open(f"{OUT}/guard.json", "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("cells_by_status_era", "guard_fail_by_status_era",
                                          "impact_current_accepted")}, indent=1))
    print({k: v["pass"] for k, v in anchors.items()})
    for k, v in acc.items():
        print(k, v["era"], v["pass"], v["has_L_IN_G"], v["rails"], v["mos_nets"])
    for k, v in (res.get("sim_probes") or {}).items():
        print(k, v)

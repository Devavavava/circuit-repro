"""results/<cell>/audit.json + results/guard.json -> results/summary.json (one row per cell)."""
import json, os
OUT = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/bench-v2/motif-audit/results"
g = json.load(open(f"{OUT}/guard.json"))
rows = {}
for c in sorted(os.listdir(OUT)):
    f = f"{OUT}/{c}/audit.json"
    if not os.path.exists(f):
        continue
    a = json.load(open(f))
    p = a["probe"]

    def op(k):
        o = (p.get(k) or {}).get("op") or {}
        d = (o.get("devices") or {}).get("mnm1", {})
        return {"VGS": d.get("vgs"), "ID_A": d.get("id"), "VDS": d.get("vds"),
                "region": d.get("region"), "V_VIN1": (o.get("nodes") or {}).get("vin1"),
                "I_port_dc_A": o.get("i_port1_dc_A"),
                "idd_ma": ((p.get(k) or {}).get("metrics") or {}).get("idd_ma")}
    r = a.get("reactance", {})
    rows[c] = {
        "cls": a["cls"], "has_L_IN_G": a["has_L_IN_G"],
        "rerun_reproduces_stored_A1": all(x == y for x, y in a["rerun_matches_stored_A1"].values()),
        "L_IN_G_nH": r.get("L_IN_G_H") and r["L_IN_G_H"] * 1e9,
        "XL_ohm_flo_f0_fhi": r.get("XL_ohm"), "C1_fF": r.get("C1_F") and r["C1_F"] * 1e15,
        "XC1_ohm_flo_f0_fhi": r.get("XC1_ohm"),
        "L_ser_Cp1_resonance_GHz": r.get("L_ser_Cp1_resonance_Hz") and r["L_ser_Cp1_resonance_Hz"] / 1e9,
        "band_GHz": [x / 1e9 for x in r.get("band_Hz", [])],
        "dc": {k: op(k) for k in ("P0", "noL", "parent_same_sizes", "P2", "P3") if k in p},
        "final_ok_same_sizes": {k: v.get("final_ok") for k, v in p.items()},
        "P1_violations_same_sizes": p["P1"].get("violations"),
        "resize_feasible": {k: v.get("feasible") for k, v in (a.get("resize") or {}).items()},
        "resize_metrics": {k: v.get("metrics") for k, v in (a.get("resize") or {}).items()},
        "guard_G_PORT_DC_pass": g["accepted"][c]["pass"],
        "sim_probe": g.get("sim_probes", {}).get(c),
    }
ing = [c for c, r in rows.items() if r["has_L_IN_G"]]
ctl = [c for c, r in rows.items() if not r["has_L_IN_G"]]
summ = {
    "n_L_IN_G": len(ing), "controls": ctl,
    "L_IN_G_P0_final_ok": sum(rows[c]["final_ok_same_sizes"]["P0"] for c in ing),
    "L_IN_G_P1_same_sizes_final_ok": sum(rows[c]["final_ok_same_sizes"]["P1"] for c in ing),
    "L_IN_G_P2_same_sizes_final_ok": sum(rows[c]["final_ok_same_sizes"]["P2"] for c in ing),
    "L_IN_G_P3_same_sizes_final_ok": sum(rows[c]["final_ok_same_sizes"]["P3"] for c in ing),
    "L_IN_G_noL_final_ok": sum(rows[c]["final_ok_same_sizes"]["noL"] for c in ing),
    "L_IN_G_resize_P1_feasible": sum(bool(rows[c]["resize_feasible"].get("P1")) for c in ing),
    "L_IN_G_resize_P2_feasible": sum(bool(rows[c]["resize_feasible"].get("P2")) for c in ing),
    "controls_all_variants_ok": {c: rows[c]["final_ok_same_sizes"] for c in ctl},
    "controls_resize": {c: rows[c]["resize_feasible"] for c in ctl},
    "guard_impact_current_accepted": g["impact_current_accepted"],
    "guard_fail_by_status_era": g["guard_fail_by_status_era"],
    "cells_by_status_era": g["cells_by_status_era"],
}
json.dump({"summary": summ, "cells": rows}, open(f"{OUT}/summary.json", "w"), indent=1)
print(json.dumps(summ, indent=1))

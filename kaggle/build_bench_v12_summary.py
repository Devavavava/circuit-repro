"""Build the bench-v1.2 summary JSON that CURRENT-STATE/PLAN referenced but that
was never written (audit 2026-09-26). Pure bookkeeping, zero sims: joins each
cell of kaggle/editcap-lib-v12-45nm/ (spec.yaml + evidence.json) with its
calibration row (campaigns/editcap-v1-baseline/calibrate-{wb,nb}.json), matched
on band + constraint values (calibration names differ from cell names).

Written OUTSIDE the lib dir on purpose: build_bench_v12.py rmtree's the lib.

    python kaggle/build_bench_v12_summary.py
"""
import json
import os
import yaml

K = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(K, "editcap-lib-v12-45nm")
CAL = os.path.join(K, "campaigns", "editcap-v1-baseline")
OUT = os.path.join(CAL, "bench-v1.2-45nm-survivors.json")
TEMPLATES = {"wideband": "kaggle/claude-solutions/templates/wideband_shunt_feedback.net",
             "narrowband": "kaggle/claude-solutions/templates/narrowband_cascode_tank.net"}


def _limits(spec):
    return {n: c.get("max", c.get("min")) for n, c in spec["constraints"].items()
            if c.get("status") != "unsupported"}


def _cal_row(spec, wb, nb):
    band, lim = spec["band"], _limits(spec)
    rows = wb if band["type"] == "wideband" else nb
    for r in rows:
        if band["type"] == "wideband":
            same_band = [round(x) for x in r["band"]] == [round(band["f_lo"]), round(band["f_hi"])]
        else:
            same_band = round(r["f0"]) == round(band["f0"])
        if same_band and all(r["cons"].get(n) == v for n, v in lim.items()):
            return r
    return None


def main():
    wb = json.load(open(os.path.join(CAL, "calibrate-wb.json")))
    nb = json.load(open(os.path.join(CAL, "calibrate-nb.json")))
    cells = []
    for name in sorted(os.listdir(LIB)):
        d = os.path.join(LIB, name)
        if not os.path.isfile(os.path.join(d, "spec.yaml")):
            continue
        spec = yaml.safe_load(open(os.path.join(d, "spec.yaml")))
        ev = json.load(open(os.path.join(d, "evidence.json")))
        cal = _cal_row(spec, wb, nb)
        btype = spec["band"]["type"]
        cells.append({
            "cell": name, "band": spec["band"], "constraints": _limits(spec),
            "shown_anchor_family": ev.get("anchor_family"),
            "anchor_feasible_evidence": ev.get("feasible"),
            "anchor_worst_margin_evidence": ev.get("worst_margin"),
            "evidence_total_evals": ev.get("total_evals"),
            "calibration_row": cal and cal["name"],
            "calibration_anchor_solves": cal and cal["anchor_solves"],
            "calibration_template_solves": cal and cal["claude_solves"],
            "reference_template": TEMPLATES[btype],
        })
    out = {
        "benchmark": "bench-v1.2", "pdk": "bptm45", "n_cells": len(cells),
        "caveats": [
            "Cells were KEPT only if anchor fails AND template solves "
            "(calibrate_bench_wb.py:41, _nb.py:29): template 16/16 is by construction.",
            "Two fixed templates cover all 16 cells (one per band type).",
            "Calibration budget 3x2500 (stop at first feasible seed); evidence re-run 3x1200.",
            "Template margins were not recorded at calibration; see "
            "kaggle/campaigns/bench-v12-audit/E-a (headroom) and E-b (5-anchor null).",
        ],
        "cells": cells,
    }
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print("wrote", OUT, len(cells), "cells;",
          sum(c["calibration_row"] is None for c in cells), "unmatched")


if __name__ == "__main__":
    main()

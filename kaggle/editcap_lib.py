#!/usr/bin/env python
"""qwen-editcap-v0 failure-library builder (zero new sims).

For each of the 13 gf180 cells unsolved by externals-v0.2: pick the anchor
leg with the best (least-negative) worst_margin, render its topology back
to the proposal netlist dialect (fenced: re-parse -> round-trip -> WL hash
must equal the anchor's), and package the verbatim failure evidence.

Outputs under kaggle/editcap-lib/:
  <spec>/anchor.tokens.json, <spec>/anchor.net, <spec>/evidence.json
  INDEX.json (anchors, buckets, fences), cells-armA.json (x0v1 engine).
"""
import json
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "kaggle" / "loop"))
sys.path.insert(0, str(REPO / "lna"))

import proposal  # noqa: E402
from topology import Topology, PIN_RE  # noqa: E402

ARCH = REPO / "kaggle/campaigns/externals-gf180-v0/era-ext-9167fd46"
LEGS = {"c1": "leg-c1-v02", "c3": "leg-c3-v02", "c4": "leg-c4"}
OUT = REPO / "kaggle" / "editcap-lib"
PIN_ORDER = {"NM": "DGSB", "PM": "DGSB", "R": "PN", "C": "PN", "L": "PN"}
TYPE_NAME = {"NM": "NMOS", "PM": "PMOS", "R": "R", "C": "C", "L": "L"}
RESERVED = ("VSS", "VDD", "VIN1", "VOUT1")


def render_netlist(tokens):
    """Tokens -> proposal-dialect netlist text (structure only)."""
    topo = Topology([t for t in tokens if t != "TRUNCATE"])
    pin_node = {}
    for root, members in topo.nodes.items():
        for m in members:
            pin_node[m] = root
    node_name, counter = {}, [0]

    def name_of(root, members):
        if root in node_name:
            return node_name[root]
        nets = [m for m in members if m in topo.nets]
        pick = next((n for n in RESERVED if n in nets), None) or \
            (sorted(nets)[0] if nets else None)
        if pick is None:
            counter[0] += 1
            pick = f"n{counter[0]}"
        node_name[root] = pick
        return pick

    roots = {r: ms for r, ms in topo.nodes.items()}
    lines = []
    for dev in sorted(topo.devices):
        base = re.match(r"[A-Za-z]+", dev).group(0)
        order = PIN_ORDER[base]
        nets = []
        for role in order:
            pin = f"{dev}_{role}"
            root = pin_node.get(pin)
            if root is None:
                raise RuntimeError(f"{dev}: missing pin {pin}")
            nets.append(name_of(root, roots[root]))
        lines.append(f"{TYPE_NAME[base]} {dev} " + " ".join(nets))
    return "\n".join(lines) + "\n"


def main():
    OUT.mkdir(exist_ok=True)
    rows = {}  # spec -> {fam: row}
    for fam, leg in LEGS.items():
        for ln in open(ARCH / leg / "results.jsonl"):
            r = json.loads(ln)
            rows.setdefault(r["spec"], {})[fam] = r
    solved = {s for s, d in rows.items()
              for r in d.values() if r["feasible"]}
    unsolved = sorted(s for s in rows if s not in solved)
    print(f"unsolved: {len(unsolved)}")
    index = {"built": time.strftime("%Y-%m-%d %H:%M"),
             "anchor_rule": "max worst_margin over valid legs",
             "buckets": {"S1": [], "S2": [], "S3": []}, "cells": {}}
    cells_a = {}
    for spec in unsolved:
        fam, row = max(rows[spec].items(),
                       key=lambda kv: kv[1]["worst_margin"][1])
        d = OUT / spec
        d.mkdir(exist_ok=True)
        toks = json.load(open(ARCH / LEGS[fam] / "designs" / spec /
                              "tokens.json"))
        toks = [t for t in toks if t != "TRUNCATE"]
        (d / "anchor.tokens.json").write_text(json.dumps(toks))
        net = render_netlist(toks)
        (d / "anchor.net").write_text(net)
        rt = proposal.round_trip(net)  # render fence
        if not rt["ok"] or rt["wl_hash"] != row["wl_hash"]:
            raise RuntimeError(
                f"{spec}: render fence FAIL ok={rt['ok']} "
                f"wl={rt.get('wl_hash')} want={row['wl_hash']}: {rt.get('error')}")
        ev = {k: row.get(k) for k in
              ("spec", "band", "band_type", "tier", "pdk", "wl_hash",
               "feasible", "worst_margin", "margins", "metrics",
               "total_evals", "escalated", "budgets", "stability")}
        ev["anchor_family"] = fam
        (d / "evidence.json").write_text(json.dumps(ev, indent=1))
        wm = row["worst_margin"][1]
        bucket = ("S3" if row["band_type"] == "wideband"
                  else "S1" if abs(wm) <= 0.5 else "S2")
        index["buckets"][bucket].append(spec)
        index["cells"][spec] = {
            "anchor_family": fam, "wl_hash": row["wl_hash"],
            "worst_margin": row["worst_margin"], "bucket": bucket,
            "render_fence": "ok"}
        cells_a[spec] = {
            "novel": False,
            "source_record": f"editcap-anchor-{fam}",
            "tokens_file": f"kaggle/editcap-lib/{spec}/anchor.tokens.json",
            "wl_hash": row["wl_hash"]}
        print(f"  {spec:18s} anchor={fam} wm={row['worst_margin'][0]}:"
              f"{wm:+.2f} bucket={bucket}")
    (OUT / "INDEX.json").write_text(json.dumps(index, indent=1))
    (OUT / "cells-armA.json").write_text(json.dumps(cells_a, indent=1))
    print("buckets:", {k: len(v) for k, v in index["buckets"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())

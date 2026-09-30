#!/usr/bin/env python
"""AMENDMENT-1 steering unit check (smoke evidence). Builds a Pipeline in a
throw-away run dir, injects synthetic accepted post-amendment cells (all wideband,
parent a3, one core) and records how the steering weights respond: narrowband
boost, a3 weight falling and reaching 0 at the parent cap, core cap ->
contains_capped_core rejects. No sizing calls. Writes smoke/steer_unit_a1.json."""
import collections
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bv2  # noqa: E402

td = os.environ.get("TMPDIR", "/tmp") + "/bv2-steer-unit"
shutil.rmtree(td, ignore_errors=True)
cfg = dict(bv2.CONFIGS["smoke-a1"], nb_frac=0.25, parent_frac=0.40, bench_target=25,
           cap_build=6, parent_cap_build=10)
bv2.CONFIGS["steer-unit"] = cfg
P = bv2.Pipeline("steer-unit", td)
P.f2space_build()
out = {}
sig = "add:L:IN-G + add:R:IN-X"
for k in (0, 3, 6, 10):
    P.cells.clear()
    P.accepted.clear()
    P.core_accepted.clear()
    P.core_atom_count.clear()
    P.parent_accepted.clear()
    for i in range(k):
        n = f"syn{i}"
        P.cells[n] = {"name": n, "status": "accepted", "band": "wb0530", "bt": "wideband",
                      "anchor": "a3", "cls": sig}
        P.accepted.append(n)
        P.core_accepted[sig] += 1
        P.core_atom_count.update(set(bv2.sig_atoms(sig)))
        P.parent_accepted["a3"] += 1
    P.search_stats["bench"].clear()
    cands = P.make_generation_bench(1)
    st = P.steer_last
    out[f"{k}_accepted_wb_a3"] = {
        "m_nb": st["m_nb"], "point_w": st["point_w"], "alloc": st["alloc"],
        "parent_w_wideband": st["parent_w"]["wideband"], "capped_cores": st["capped_cores"],
        "children_anchor": dict(collections.Counter(c["anchor"] for c in cands)),
        "rej_contains_capped_core": P.search_stats["bench"].get("rej_contains_capped_core", 0),
        "atom_penalty_L": P.atom_penalty(["add:L:IN-G"])}
o = out
ok = (o["0_accepted_wb_a3"]["m_nb"] == 3.0
      and o["10_accepted_wb_a3"]["parent_w_wideband"]["a3"] == 0.0
      and o["10_accepted_wb_a3"]["children_anchor"].get("a3", 0) == 0
      and o["6_accepted_wb_a3"]["capped_cores"] == [sig]
      and o["3_accepted_wb_a3"]["alloc"]["nb240-gain"] > o["3_accepted_wb_a3"]["alloc"]["wb0530-noise"])
out["pass"] = ok
json.dump(out, open(f"{HERE}/smoke/steer_unit_a1.json", "w"), indent=1)
print(json.dumps(out, indent=1))
shutil.rmtree(td, ignore_errors=True)

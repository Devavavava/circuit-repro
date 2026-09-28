"""Static guards on the whole recorded population + mutations (no sizing):
bench_anchor_prep.topo_limits (VERIFY_TOPO_LIMITS) and structural_degeneracy
(VERIFY_STRUCT). usage: guard_static_test.py <out.json>"""
import sys, os, json
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r4_static as RS                                       # noqa: E402
import r4_drv as D                                           # noqa: E402
import bench_anchor_prep as PREP                             # noqa: E402
from topology import Topology                                # noqa: E402
from spec import Spec                                        # noqa: E402

specs = {c: Spec.load(f"{D.LIB}/{c}/spec.yaml") for c in D.cells()}
out = {"population": {}, "mutations": {}}
pop = RS.population()
tl, sd = Counter(), Counter()
for (cell, cand), srcs in sorted(pop.items()):
    topo = Topology(list(RS.tokens(cell, cand)))
    t = PREP.topo_limits(specs[cell], topo)
    s = PREP.structural_degeneracy(topo)
    for f in t["failed"]:
        tl[f] += 1
    for f in s:
        sd[f] += 1
    out["population"][f"{cell}|{cand}"] = {"sources": sorted(srcs), "topo_failed": t["failed"],
                                           "struct": s}
out["population_summary"] = {"n": len(pop), "topo_limits_failed": dict(tl),
                             "structural_flags": dict(sd)}
for name in json.load(open(HERE + "/mutations.json")):
    cell = "v12-wb-s11n10-g10-b0824" if name.startswith("wb_") else "v12-nb-f15-g16"
    topo = Topology(D.tokens_for(cell, "net:" + name))
    out["mutations"][name] = {"topo_failed": PREP.topo_limits(specs[cell], topo)["failed"],
                              "struct": PREP.structural_degeneracy(topo)}
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(out["population_summary"])
for k, v in out["mutations"].items():
    print(k, v)

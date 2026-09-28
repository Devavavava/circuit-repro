"""Static detectors (r4_static.classify + the spec L0 screen) on the adversarial
mutations: which junk additions are visible without simulation?
usage: static_mut.py <out.json>"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r4_static as RS                                       # noqa: E402
import r4_drv as D                                           # noqa: E402
from topology import Topology                                # noqa: E402
from spec import Spec                                        # noqa: E402

out = {}
for name in json.load(open(HERE + "/mutations.json")):
    cell = "v12-wb-s11n10-g10-b0824" if name.startswith("wb_") else "v12-nb-f15-g16"
    topo = Topology(D.tokens_for(cell, "net:" + name))
    passed, crit = Spec.load(f"{D.LIB}/{cell}/spec.yaml").structural_screen(topo)
    f = RS.classify(topo)
    out[name] = {"screen_failed": [k for k, v in crit.items() if not v],
                 "degenerate": [k for k in RS.DEGEN_KEYS if f.get(k)],
                 "direct_passive_in_out": f["direct_passive_in_out"]}
    print(name, out[name])
json.dump(out, open(sys.argv[1], "w"), indent=1)

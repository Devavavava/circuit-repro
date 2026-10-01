"""Print the prepared (bias-inserted, port-wrapped) sizing body of a cell's witness."""
import json, sys
REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop"):
    sys.path.insert(0, p)
import size as SZ
from topology import Topology

cell = sys.argv[1]
which = sys.argv[2] if len(sys.argv) > 2 else "witness/witness.tokens.json"
d = f"{REPO}/kaggle/campaigns/bench-v2/run/cells/{cell}"
toks = json.load(open(f"{d}/{which}"))
topo = Topology(list(toks))
body, sizable, fixed = SZ.prepared_body(topo, inductor_q=12, pdk="bptm45")
print(body)
print("SIZABLE", sizable)
print("FIXED", fixed)

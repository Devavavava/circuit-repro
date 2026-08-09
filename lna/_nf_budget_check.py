"""Verify the L0 screen + moves ctx honor device_budget [3,18] (FINDINGS 21)."""
import os, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from topology import Topology, parse_arrow_file
import size as S

for name in ("dhruva-l5", "dhruva-l2", "dhruva-l1", "dhruva-s",
             "wideband-sdr", "wifi24", "gps-l1"):
    spec = S._spec_for_sizing(name)
    print(f"{name:<14} device_budget={spec.topology.get('device_budget')}")

spec = S._spec_for_sizing("dhruva-s")
lo, hi = spec.topology["device_budget"]
assert [lo, hi] == [3, 18], (lo, hi)

# the 18-device real LNA must now pass the budget half of the screen
p = os.path.join(HERE, "data", "external", "ihp-lna-2p45g", "generated", "seq_*.txt")
f = glob.glob(p)
t = Topology(parse_arrow_file(f[0]))
ok, info = spec.structural_screen(t)
print(f"\nihp-lna-2p45g: {t.n_devices} devices -> device_budget={info['device_budget']} "
      f"(screen overall {ok}; other gates: "
      f"{ {k: v for k, v in info.items() if k != 'device_budget'} })")
assert info["device_budget"] is True, "18-device circuit still rejected by the budget gate"

# a 19-device one must still be rejected -> the bound is enforced, not removed
f19 = glob.glob(os.path.join(HERE, "data", "external", "align-lna-qm", "generated", "seq_*.txt"))
t19 = Topology(parse_arrow_file(f19[0]))
ok19, info19 = spec.structural_screen(t19)
print(f"align-lna-qm : {t19.n_devices} devices -> device_budget={info19['device_budget']}")
assert info19["device_budget"] is False, "19 devices should still fail"

# moves.py ctx reads the same field
ctx_hi = spec.topology.get("device_budget", [3, 16])[1]
print(f"\nmoves ctx max_dev = {ctx_hi}")
assert ctx_hi == 18
print("L0 screen + moves ctx honor [3,18]; 19 still rejected. OK")

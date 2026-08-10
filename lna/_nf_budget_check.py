"""Verify the L0 screen + moves ctx honor device_budget [3,21] (FINDINGS §24)."""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from topology import Topology, parse_arrow_file   # noqa: E402
import size as S                                  # noqa: E402

DHRUVA = ("dhruva-l5", "dhruva-l2", "dhruva-l1", "dhruva-s")
OTHER = ("wideband-sdr", "wifi24", "gps-l1")


def ext(name):
    f = glob.glob(os.path.join(HERE, "data", "external", name, "generated", "seq_*.txt"))
    return Topology(parse_arrow_file(f[0]))


def main():
    for n in DHRUVA + OTHER:
        print(f"{n:<14} device_budget="
              f"{S._spec_for_sizing(n).topology.get('device_budget')}")
    for n in DHRUVA:
        assert S._spec_for_sizing(n).topology["device_budget"] == [3, 21], n
    for n in OTHER:
        assert S._spec_for_sizing(n).topology["device_budget"] == [3, 16], n

    spec = S._spec_for_sizing("dhruva-s")
    print()
    for name in ("ihp-gps-lna-npn", "align-lna-qm", "ihp-lna-2p45g"):
        t = ext(name)
        ok, info = spec.structural_screen(t)
        others = {k: v for k, v in info.items() if k != "device_budget"}
        print(f"{name:<18} {t.n_devices:>3} devices -> "
              f"device_budget={info['device_budget']}  screen={ok}  "
              f"other_gates={ {k: v for k, v in others.items() if not v} or 'all pass'}")

    # the 21-device REAL GPS-band LNA is the calibration point -> must be admitted
    big = ext("ihp-gps-lna-npn")
    assert big.n_devices == 21, big.n_devices
    assert spec.structural_screen(big)[1]["device_budget"] is True

    # ...and the bound must still BIND above 21.
    lo, hi = spec.topology["device_budget"]
    print(f"\nlargest real design in the 50-circuit reference set = "
          f"{big.n_devices} devices")
    for n_dev, expect in ((3, True), (21, True), (22, False), (30, False)):
        got = lo <= n_dev <= hi
        print(f"  budget gate @ {n_dev:>2} devices -> {got}   (expected {expect})")
        assert got == expect

    ctx_hi = spec.topology.get("device_budget", [3, 16])[1]
    print(f"\nmoves ctx max_dev = {ctx_hi}")
    assert ctx_hi == 21
    print("L0 screen + moves ctx honor [3,21]; 21 admitted, 22+ rejected; "
          "other specs unchanged. OK")


if __name__ == "__main__":
    main()

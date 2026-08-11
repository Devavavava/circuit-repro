"""WP-OUTCOME -- the structural signature of an outcome request (plans2/11 prediction 3).

Over EVERY analysable sample of a pool (not just the ~10 the sizing budget
reaches), so it is the highest-powered readout this work package has of whether
the model read the label or merely tolerated the token: in the store, the designs
that met S11 are the source-driven, device-rich ones (FINDINGS 29.3 / 29.10), so
a model that used an all-MET request should emit more of them.

    python lna/_out_struct.py
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _match_struct as MS                                        # noqa: E402
import _out_pool as OP                                            # noqa: E402
from spec import Spec                                             # noqa: E402
from topology import Topology, parse_arrow_file                   # noqa: E402


def main():
    spec = Spec.load("wifi24")
    out = {}
    print(MS.HDR)
    for key, _, dirs in OP.ARMS:
        rows, dev, ind, l0dev = [], [], [], []
        for d in dirs:
            for f in sorted(glob.glob(os.path.join(d, "seq*.txt"))):
                try:
                    topo = Topology(parse_arrow_file(f))
                except Exception:                                 # noqa: BLE001
                    continue
                rows.append((os.path.basename(f), MS.analyze(topo)))
                dev.append(topo.n_devices)
                ind.append(topo.n_inductors)
                if spec.structural_screen(topo)[0]:
                    l0dev.append(topo.n_devices)
        if not rows:
            print("  %-6s POOL MISSING" % key)
            continue
        s = MS.summarize(rows, label=key)
        s["mean_devices"] = round(sum(dev) / len(dev), 2)
        s["median_devices"] = sorted(dev)[len(dev) // 2]
        s["frac_ge12_devices"] = round(sum(1 for x in dev if x >= 12) / len(dev), 4)
        s["mean_inductors"] = round(sum(ind) / len(ind), 2)
        s["mean_devices_l0"] = (round(sum(l0dev) / len(l0dev), 2) if l0dev else None)
        out[key] = s
        print(MS.line(s))
    print()
    print("%-7s %6s %6s %7s %7s %7s" % ("arm", "meanD", "medD", ">=12D",
                                        "meanL", "port_src"))
    for key in out:
        s = out[key]
        print("%-7s %6.2f %6d %7.3f %7.2f %7.3f"
              % (key, s["mean_devices"], s["median_devices"],
                 s["frac_ge12_devices"], s["mean_inductors"], s["port_src"]))
    p = os.path.join(OP.OUT, "struct_stats.json")
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
    print("wrote %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())

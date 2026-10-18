"""Step 6 backstop: best intrinsic gain gm*ro = gm/gds at L = 1 um on bptm45 (NMOS and PMOS),
and the analytic gain ceiling k * 20 log10(max gm*ro) per topology (README D-O27).

One device, W = 10 um (NF = 5, the harness's finger rule), L = 1 um, bulk = source, 27 C;
DC sweep |Vgs| 0..1.1 V (10 mV) x |Vds| 0.05..1.1 V (50 mV); gm, gds, id from the BSIM4 op.
Grid points with |id| < 1 nA are ignored. Writes results/ceiling.json.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from opamp_v0 import testbench as TB   # noqa: E402

VGS = [round(0.01 * i, 4) for i in range(0, 111)]
VDS = [round(0.05 * i, 4) for i in range(1, 23)]

# number of gm*ro factors in the ideal low-frequency gain (a cascoded stage counts 2)
K_TOPO = {"ota5t": 1, "two_stage_rz": 2, "telescopic": 2, "folded_cascode": 2,
          "three_stage_nmc": 3, "W-R1": 3, "W-R23": 4, "W-R4": 3}


def sweep(typ):
    s = 1.0 if typ == "nmos" else -1.0
    wd = os.path.join(TB.work_dir(), "ceil")
    os.makedirs(wd, exist_ok=True)
    deck = "\n".join([
        "* intrinsic gain sweep", '.include "%s"' % TB.MODEL_PATH, ".temp 27",
        "Vd d 0 dc %g" % (s * 0.55), "Vg g 0 dc %g" % (s * 0.5),
        "m1 d g 0 0 %s W=10u L=1u NF=5" % typ,
        ".control", "save @m1[gm] @m1[gds] @m1[id]",
        "dc vg %g %g %g vd %g %g %g" % (s * VGS[0], s * VGS[-1] + s * 1e-9, s * 0.01,
                                       s * VDS[0], s * VDS[-1] + s * 1e-9, s * 0.05),
        "wrdata %s/ig.txt @m1[gm] @m1[gds] @m1[id]" % wd, ".endc", ".end", ""])
    text, err = TB.run_ngspice(deck, wd, ["ig.txt"])
    rows = TB.read_rows(os.path.join(wd, "ig.txt"))
    assert rows and len(rows) == len(VGS) * len(VDS), (err, len(rows), text and text[-500:])
    best, best_half = None, None
    for n, r in enumerate(rows):
        vds, vgs = VDS[n // len(VGS)], VGS[n % len(VGS)]
        gm, gds, idd = abs(r[1]), abs(r[3]), abs(r[5])
        if idd < 1e-9 or gds <= 0:
            continue
        a = gm / gds
        pt = {"a": a, "a_db": 20 * math.log10(a), "vgs": vgs, "vds": vds, "id": idd}
        if best is None or a > best["a"]:
            best = pt
        if vds <= 0.55 + 1e-9 and (best_half is None or a > best_half["a"]):
            best_half = pt
    return best, best_half


def main():
    out = {"L": 1e-6, "W": 10e-6, "grid": {"vgs": [0, 1.1, 0.01], "vds": [0.05, 1.1, 0.05]}}
    for typ in ("nmos", "pmos"):
        b, h = sweep(typ)
        out[typ] = {"best": b, "best_vds_le_half_vdd": h}
    a = max(out["nmos"]["best"]["a"], out["pmos"]["best"]["a"])
    ah = max(out["nmos"]["best_vds_le_half_vdd"]["a"], out["pmos"]["best_vds_le_half_vdd"]["a"])
    out["a_max"], out["a_max_db"] = a, 20 * math.log10(a)
    out["a_half"], out["a_half_db"] = ah, 20 * math.log10(ah)
    out["k_topology"] = K_TOPO
    out["ceiling_db"] = {n: k * out["a_max_db"] for n, k in K_TOPO.items()}
    out["ceiling_db_vds_le_half"] = {n: k * out["a_half_db"] for n, k in K_TOPO.items()}
    with open(os.path.join(HERE, "results", "ceiling.json"), "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()

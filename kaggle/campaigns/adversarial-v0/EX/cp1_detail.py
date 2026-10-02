"""C-cp1 detail: for every verifier-passing design, the metric shifts (dB) when the
harness input block Cp1 = 10 pF is replaced by an ideal AC coupling (P1, 1 uF) or a
DC-grounded 50-ohm source (P2), the 10 pF reactance at the band edges, and whether the
DUT has its OWN series capacitor at VIN1.
usage: cp1_detail.py <out.json> <raw.json files...>   (raw seeds / child outputs)"""
import json
import math
import sys


def own_series_c(tokens):
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ex_lib as X                                                   # noqa: F401
    from topology import Topology, base_of, PIN_RE
    topo = Topology(list(tokens))
    vin = None
    pin2node = {}
    for root, members in topo.nodes.items():
        if "VIN1" in members:
            vin = root
        for m in members:
            if PIN_RE.match(m):
                pin2node[m] = root
    devs = {}
    for p, n in pin2node.items():
        mm = PIN_RE.match(p)
        devs.setdefault(mm.group("dev"), {})[mm.group("pin")] = n
    at_vin = sorted(d for d, pins in devs.items() if vin in pins.values())
    return {"devices_at_VIN1": at_vin,
            "own_C_at_VIN1": any(base_of(d) == "C" for d in at_vin),
            "L_at_VIN1": any(base_of(d) == "L" for d in at_vin)}


def main(out, files):
    rows = []
    for f in files:
        r = json.load(open(f))
        c = r.get("checks")
        if not r.get("verifier_pass") or not c:
            continue
        b = c["base"]["metrics"]
        spec_f = r["spec"]
        row = {"id": r.get("sid") or r.get("did"), "spec": spec_f.split("/")[-1]}
        for k in ("P1", "P2"):
            m = c["Ra"][k].get("metrics") or {}
            row[k] = {"mag": c["Ra"][k]["mag"], "worst": c["Ra"][k].get("worst"),
                      "d": {x: (round(m[x] - b[x], 4) if isinstance(m.get(x), (int, float))
                                and isinstance(b.get(x), (int, float)) else None)
                            for x in ("s11_max_db", "s21_db", "nf_db", "nf_max_db",
                                      "s21_ripple_db", "idd_ma")},
                      "mu_wide": c["Ra"][k].get("mu_wide")}
        band = b.get("stab_band") or [None, None]
        row["Xc10p_ohm_band"] = [round(1 / (2 * math.pi * f * 10e-12), 1) for f in band if f]
        row.update(own_series_c(r["tokens"]))
        row["material"] = max(row["P1"]["mag"], row["P2"]["mag"]) > 0.02
        rows.append(row)
    json.dump(rows, open(out, "w"), indent=1)
    mat = [r for r in rows if r["material"]]
    print(len(rows), "designs;", len(mat), "material")
    for grp, L in (("material", mat), ("clean", [r for r in rows if not r["material"]])):
        n = len(L) or 1
        print(grp, "own C at VIN1:", sum(r["own_C_at_VIN1"] for r in L), "/", len(L),
              " L at VIN1:", sum(r["L_at_VIN1"] for r in L),
              " P1 worst metric:", {w: sum(r["P1"]["worst"] == w for r in L)
                                    for w in {r["P1"]["worst"] for r in L}})
    for r in mat:
        print(r["id"], r["spec"][:26], r["Xc10p_ohm_band"], r["own_C_at_VIN1"], r["devices_at_VIN1"],
              r["P1"]["worst"], round(r["P1"]["mag"], 3), {k: v for k, v in r["P1"]["d"].items() if v})


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])

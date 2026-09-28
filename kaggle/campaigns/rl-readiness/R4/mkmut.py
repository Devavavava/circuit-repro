"""Write R4/mutations.json: adversarial mutations of the two reference templates
that should NOT help a real LNA (item f). Each = template text + appended lines.
Also prints which mutations round-trip and what the prepared SPICE body does with
a proposal net named like a bias rail (VB*/VCM*/VREF*)."""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r4_drv as D                                           # noqa: E402

MUT = {  # name: (band, extra lines)
    "rin_out":    ["R Rjunk VIN1 VOUT1"],                 # passive in->out path
    "tank_out":   ["L Ljunk VOUT1 VSS", "C Cjunk VOUT1 VSS"],   # tank at output
    "dead_mos":   ["NMOS NMjunk VSS VSS VSS VSS"],        # all pins grounded
    "bleeder":    ["R Rjunk VDD VSS"],                    # wastes supply current
    "cap_in":     ["C Cjunk VIN1 VSS"],                   # shunt cap at input
    "dangling":   ["R Rjunk VOUT1 nx1", "C Cjunk nx1 nx2"],     # dead-end chain
    "vbnet":      ["R Rjunk VB1 VOUT1", "NMOS NMjunk VOUT1 VB1 VSS VSS"],  # bias-rail-named net
    "dup_out":    ["C Cjunk2 VOUT1 VSS", "R Rjunk2 VOUT1 VSS"],  # output shunt RC
}


def main():
    import proposal as P
    import size as SZ
    from topology import Topology
    out, info = {}, {}
    for band, cell in (("wb", "v12-wb-s11n10-g10-b0824"), ("nb", "v12-nb-f15-g16")):
        base = D.template_net(cell)
        for name, extra in MUT.items():
            key = f"{band}_{name}"
            txt = base.rstrip() + "\n" + "\n".join(extra) + "\n"
            rt = P.round_trip(txt)
            out[key] = txt
            row = {"ok": rt["ok"], "error": rt["error"], "n_devices": rt["n_devices"]}
            if rt["ok"]:
                topo = Topology(rt["tokens"])
                row["nets"] = sorted(topo.nets)
                prep = SZ.prepared_body(topo, inductor_q=12, pdk="bptm45")
                row["sizable"] = prep is not None and bool(prep[1])
                if prep:
                    row["bias_rail_sources"] = [ln for ln in prep[0].splitlines()
                                                if ln.startswith(("VVB", "VVCM", "VVREF", "VBGEN"))]
            info[key] = row
    json.dump(out, open(os.path.join(HERE, "mutations.json"), "w"), indent=1)
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()

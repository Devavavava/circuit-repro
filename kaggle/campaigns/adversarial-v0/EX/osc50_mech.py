"""C-osc50 mechanism test (diagnostic, no verdict changes). For each design of the
class: the R-b r50/r50 run (1 uA kick, 600 ns) on
  as-is        the sized winner;
  ideal ports  harness blocks Cp1/Cp2 = 1 uF (rules out the 10 pF harness);
  gate-cut     the cascode device whose gate sits on the inter-stage node gets its
               gate moved to a new node tied to the old one through 10 kohm and
               AC-grounded by 100 pF (DC bias unchanged, RF feedback into that
               gate removed).
If `as-is` oscillates and `gate-cut` does not, the oscillation is the internal loop
through that gate. The device to cut is given per design (from the netlists).
usage: osc50_mech.py <out.json> <raw.json>:<MOS element> ...
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ex_lib as X  # noqa: E402,F401
import r4_sim as S  # noqa: E402


def gate_cut(body, elem):
    out, done = [], False
    for ln in body.splitlines():
        t = ln.split()
        if t and t[0] == elem:
            g = t[2]
            t[2] = "ngcutx"
            out.append(" ".join(t))
            out.append(f"Rgcutx ngcutx {g} 10k")
            out.append("Cgcutx ngcutx 0 100p")
            done = True
        else:
            out.append(ln)
    assert done, elem
    return "\n".join(out) + "\n"


def main(out, items):
    res = {}
    for it in items:
        f, elem = it.rsplit(":", 1)
        r = json.load(open(f))
        did = r.get("sid") or r.get("did")
        b0 = r["body"]
        bi = b0.replace("Cp1 p1 VIN1 10p", "Cp1 p1 VIN1 1u").replace("Cp2 VOUT1 p2 10p",
                                                                      "Cp2 VOUT1 p2 1u")
        bc = gate_cut(b0, elem)
        row = {"cut": elem}
        for k, b in (("as_is", b0), ("ideal_ports", bi), ("gate_cut", bc)):
            a = S.tran_run(b, r["params"], term_src="r50", term_load="r50", tstop=600e-9,
                           kick=1e-6)
            row[k] = {"verdict": S.tran_verdict(a), "amp": a}
        mline = next(ln for ln in b0.splitlines() if ln.split() and ln.split()[0] == elem)
        row["elem_line"] = mline
        res[did] = row
        print(did, elem, {k: row[k]["verdict"] for k in ("as_is", "ideal_ports", "gate_cut")},
              flush=True)
        json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])

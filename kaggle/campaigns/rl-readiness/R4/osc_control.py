"""Positive/negative controls for the item-(e) transient oscillation detector.

POS: cross-coupled NMOS LC oscillator (a textbook -gm/2 negative-resistance
     VCO core, 2 nH/1 pF tanks, Q from a series R) written in the same port
     convention as a sized body (portnum 1/2 sources + 10p DC blocks).
NEG: the same core with the tank damped by 50-ohm shunts (no oscillation).
usage: osc_control.py <out.json>"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r4_sim as S                                           # noqa: E402
import extract as E                                          # noqa: E402

MODELS = E.resolve_models() if hasattr(E, "resolve_models") else None


def body(damp):
    inc = open(os.path.join(os.path.dirname(E.__file__), "..", "AutoCkt", "repo",
                            "eval_engines", "ngspice", "ngspice_inputs",
                            "spice_models", "45nm_bulk.txt")).name
    lines = [f".include {os.path.abspath(inc)}",
             "Vsup VDD 0 dc {pVDD}",
             "Vp1 p1 0 dc 0 ac 1 portnum 1 z0 50", "Cp1 p1 VIN1 10p",
             "Cp2 VOUT1 p2 10p", "Vp2 p2 0 dc 0 ac 0 portnum 2 z0 50",
             "L1 VDD nq1 2n", "RQ1 nq1 VIN1 2", "L2 VDD nq2 2n", "RQ2 nq2 VOUT1 2",
             "C1 VIN1 0 1p", "C2 VOUT1 0 1p",
             "M1 VIN1 VOUT1 ns 0 nmos W=20u L=45n", "M2 VOUT1 VIN1 ns 0 nmos W=20u L=45n",
             "Itail ns 0 dc 3m"]
    if damp:
        lines += ["Rd1 VIN1 VDD 30", "Rd2 VOUT1 VDD 30"]
    return "\n".join(lines)


def main(out):
    res = {}
    for name, damp in (("pos_oscillator", False), ("neg_damped", True)):
        b = body(damp)
        p = {"pVDD": "1.1"}
        st = E.measure_stability(b, p, 3.5e9, 1e8, 2e10, npts=401)
        tr = {}
        for ts, tl in (("r50", "r50"), ("open", "open")):
            r = S.tran_run(b, p, term_src=ts, term_load=tl)
            tr[f"{ts}/{tl}"] = {"verdict": S.tran_verdict(r), "amp": r}
        res[name] = {"mu_min_wide": (st or {}).get("mu_min"), "tran": tr}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])

"""Prove ngspice+BSIM4 honours `NF=` and that it is the rg noise that drops.

The cutover is only sound if (a) the expression form `NF={max(1,ceil(W/wf))}`
actually parses and takes effect, and (b) the reduction shows up specifically in
the gate-electrode-resistance noise term, not somewhere else. Both are checked
here on the SAME design, emitted the old way and the new way, using the phase-1
per-element noise decomposition.

    python lna/_mf_prove.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bias                       # noqa: E402
import datastore as ds            # noqa: E402
import extract as E               # noqa: E402
import size as S                  # noqa: E402
from to_spice import W_FINGER     # noqa: E402
from topology import Topology     # noqa: E402


def body_for(topo, w_finger, inductor_q=12):
    nl, _, rep, _ = bias.insert_bias(topo, sweep=True, inductor_q=inductor_q,
                                     w_finger=w_finger)
    if rep.get("skipped") or not nl.two_port:
        return None, None
    return E.body_of(nl.emit()), nl


def main():
    row = None
    for r in ds.load("topo_labels"):
        if (r.get("wl_hash") or "").startswith("439032") and r.get("spec") == "dhruva-l5":
            nf = ((r.get("margins") or {}).get("nf_db") or {}).get("achieved")
            if row is None or (nf is not None and nf < row[0]):
                row = (nf if nf is not None else 1e9, r)
    r = row[1]
    topo = Topology(r["graph"]["tokens"])
    spec = S._spec_for_sizing("dhruva-l5")
    params = r["best_params"]

    print(f"design {r['wl_hash'][:14]}  W_FINGER default = {W_FINGER}\n")
    for label, wf in (("single-finger (old)", None), (f"{W_FINGER*1e6:g}um/finger (new)", W_FINGER)):
        body, nl = body_for(topo, wf)
        if body is None:
            print(f"{label}: bias insert skipped")
            continue
        mos_line = next((ln for ln in body.splitlines()
                         if ln.strip().upper().startswith("MNM1")), "?")
        m = S.eval_metrics(body, params, spec, nf_gated=True)
        b = E.measure_noise_budget(body, params, spec)
        rg = idn = 0.0
        for e in (b or {}).get("elements", {}).values():
            mech = e.get("mech") or {}
            ex = e.get("excess_frac") or 0.0
            if e["p"]:
                rg += ex * mech.get("rg", 0.0) / e["p"]
                idn += ex * mech.get("id", 0.0) / e["p"]
        print(f"--- {label}")
        print(f"    instance: {mos_line.strip()[:96]}")
        print(f"    layout_cfg: {nl.layout_cfg}")
        print(f"    NF {m['nf_db']:.3f} dB   S11* {m['s11_max_db']:.2f}   "
              f"S21 {m['s21_db']:.2f}   Idd {m['idd_ma']:.2f}")
        print(f"    share of F-1:  rg {100*rg:.1f}%   id(channel) {100*idn:.1f}%")
        print(f"    sum closure {b['sum_closure']:.4f}\n")


if __name__ == "__main__":
    main()

"""WP-PGAIN scratch probe: sanity-check the netlist-post-processing insertion
path and answer "where in this topology does loading actually cost gain?".

Not a deliverable -- a measurement scratchpad. Nothing here is gated.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import size as S                      # noqa: E402
from topology import Topology         # noqa: E402
from moves import private_tmp         # noqa: E402

REPRO = os.path.join(HERE, "repro", "dhruva-best")
OUT = os.path.join(HERE, "out", "pgain_tmp")


def base():
    tok = json.load(open(os.path.join(REPRO, "tokens.json"), encoding="utf-8"))
    prep = S.prepared_body(Topology(tok), inductor_q=12)
    if prep is None:
        raise SystemExit("bias insert skipped")
    body, sizable, fixed = prep
    params = json.load(open(os.path.join(REPRO, "dhruva-l5.params.json"),
                            encoding="utf-8"))
    return body, dict(params), sizable, fixed


def ev(body, params, band="dhruva-l5", nf=False):
    return S.eval_metrics(body, params, S._spec_for_sizing(band), nf_gated=nf)


def main():
    private_tmp(OUT)
    body, params, sizable, fixed = base()
    print("=== FULL prepared body ===")
    print(body)
    print("=== sizable ===", sizable)
    print("=== fixed ===", fixed)
    print("=== params ===", params)

    t0 = time.time()
    m = ev(body, params)
    print(f"\nbaseline l5: S21={m['s21_db']:.3f} S11max={m['s11_max_db']:.3f} "
          f"Idd={m['idd_ma']:.3f} K={m['k_min']:.2f}   ({time.time()-t0:.2f}s)")

    # --- is the NMOS switch actually a switch? shunt at n0 (MNM4 gate):
    #     ideal R to gnd  vs  R + NMOS(W) to gnd, W swept, Vg = 1.1
    print("\n=== switch reality check: C(10p) -> R=10 -> [device] -> gnd @ n0")
    for tag, extra, pex in (
        ("ideal short", "RPRB nprb 0 10", {}),
        ("MOS W=2u  ", "RPRB nprb nsw 10\nMPRB nsw ng 0 0 nmos W=2e-06 L=45n NF=1", {}),
        ("MOS W=20u ", "RPRB nprb nsw 10\nMPRB nsw ng 0 0 nmos W=2e-05 L=45n NF=10", {}),
        ("MOS W=20u1f", "RPRB nprb nsw 10\nMPRB nsw ng 0 0 nmos W=2e-05 L=45n NF=1", {}),
        ("MOS W=200u", "RPRB nprb nsw 10\nMPRB nsw ng 0 0 nmos W=2e-04 L=45n NF=100", {}),
        ("MOS OFF   ", "RPRB nprb nsw 10\nMPRB nsw ngo 0 0 nmos W=2e-05 L=45n NF=10", {}),
    ):
        gate = "ngo" if "OFF" in tag else "ng"
        b = (body.rstrip() + "\nCPRB n0 nprb 1e-11\n" + extra +
             f"\nRPRBG ng 0 10k\nVPRBG ngd 0 dc 1.1\nRPRBG2 ng ngd 1\n"
             f"VPRBGO ngo 0 dc 0\n")
        if "ideal" in tag:
            b = body.rstrip() + "\nCPRB n0 nprb 1e-11\nRPRB nprb 0 10\n"
        mm = ev(b, dict(params, **pex))
        print(f"  {tag}: " + ("SIM FAILED" if mm is None else
              f"S21={mm['s21_db']:.3f} S11max={mm['s11_max_db']:.3f} "
              f"Idd={mm['idd_ma']:.3f}"))
        _ = gate

    # --- ideal (no MOS) AC shunt at each candidate node, R swept.
    for node in ("n4", "n6", "n0", "n8", "n3", "n2", "VOUT1"):
        print(f"\nshunt @ {node}:")
        for r in (1e3, 100.0, 30.0, 10.0):
            b = body.rstrip() + f"\nCPRB {node} nprb 1e-11\nRPRB nprb 0 {r}\n"
            mm = ev(b, params)
            print(f"   R={r:>8.4g}  " + ("SIM FAILED" if mm is None else
                  f"S21={mm['s21_db']:.3f}  S11max={mm['s11_max_db']:.3f}"))


if __name__ == "__main__":
    main()

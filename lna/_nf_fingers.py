"""How much of our measured NF is single-finger gate resistance? (WP-L5 phase 1)

The phase-1 noise budget says the dominant per-MOSFET noise mechanism on the
dhruva designs is `rg` -- BSIM4's gate-electrode resistance -- not `id`, the
channel thermal noise. That is a LAYOUT parameter, not a topology property:

    45nm_bulk.txt: rgatemod = 1, rshg = 0.4 ohm/sq, ngcon = 1
    BSIM4: Rgeltd = RSHG * (XGW + Weff/(3*NGCON)) / (NGCON * (Ldrawn-XGL) * NF)

`NF` is the number of gate FINGERS, a per-instance parameter, and our decks never
set it -- so every device is emitted as ONE finger. For a 100-200 um RF device at
L=45nm that is hundreds of ohms in series with the gate, which no one would tape
out; real RF layouts use tens of fingers and Rg becomes negligible.

This measures the size of that modelling gap by re-running the *identical* sized
design with a finger count applied to every MOSFET, changing nothing else. It is
a MEASUREMENT of harness fidelity -- it does not adopt anything.

    python lna/_nf_fingers.py --fingers 1,2,4,8,16,32,64
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds            # noqa: E402
import extract as E               # noqa: E402
import size as S                  # noqa: E402
from topology import Topology     # noqa: E402

CASES = [("439032", "dhruva-l5"), ("998ff3", "dhruva-l5"),
         ("ace838", "dhruva-s"), ("6f0d08", "dhruva-s")]
_M = re.compile(r"^(M\w+\s+.*?\bL=\{?[^\s}]+\}?)(\s*)$", re.IGNORECASE)


def with_fingers(body, nf):
    """Append `NF=<n>` to every MOSFET instance line. Geometry only."""
    out = []
    for ln in body.splitlines():
        if ln.strip().upper().startswith("M") and " nmos" in ln.lower():
            out.append(ln.rstrip() + f" NF={nf}")
        else:
            out.append(ln)
    return "\n".join(out)


def best_row(hp, spec_name):
    best = None
    for r in ds.load("topo_labels"):
        g = r.get("graph") or {}
        if not (r.get("wl_hash") or "").startswith(hp) or r.get("spec") != spec_name:
            continue
        if not g.get("tokens") or not r.get("best_params"):
            continue
        nf = ((r.get("margins") or {}).get("nf_db") or {}).get("achieved")
        if best is None or (nf is not None and nf < best[0]):
            best = (nf if nf is not None else 1e9, r)
    return best[1] if best else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fingers", default="1,2,4,8,16,32,64")
    a = ap.parse_args()
    fingers = [int(x) for x in a.fingers.split(",")]
    print("NF(dB) vs gate-finger count -- same sized design, geometry only\n")
    print(f"{'design':<16}{'spec':<11}{'target':>7}" +
          "".join(f"{('NF=' + str(n)):>9}" for n in fingers) + f"{'rg share':>10}")
    for hp, spec_name in CASES:
        r = best_row(hp, spec_name)
        if r is None:
            continue
        spec = S._spec_for_sizing(spec_name)
        tgt = (spec.constraints.get("nf_db") or {}).get("max")
        prep = S.prepared_body(Topology(r["graph"]["tokens"]), inductor_q=12)
        if prep is None:
            continue
        base = prep[0]
        vals = []
        for n in fingers:
            body = base if n == 1 else with_fingers(base, n)
            v = E.measure_nf(body, r["best_params"], spec)
            vals.append(v)
        bud = E.measure_noise_budget(base, r["best_params"], spec)
        rg = 0.0
        if bud:
            for e in bud["elements"].values():
                if e.get("mech") and e.get("excess_frac"):
                    rg += e["excess_frac"] * (e["mech"].get("rg", 0.0) / e["p"])
        print(f"{r['wl_hash'][:14]:<16}{spec_name:<11}{tgt:>7.2f}" +
              "".join(f"{(v if v is not None else float('nan')):>9.3f}" for v in vals) +
              f"{100*rg:>9.1f}%", flush=True)
    print("\nrg share = fraction of the EXCESS noise (F-1) attributable to "
          "gate-electrode resistance at NF=1")


if __name__ == "__main__":
    main()

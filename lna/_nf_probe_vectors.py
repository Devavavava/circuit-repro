"""Probe: what per-element noise vectors does ngspice expose for our decks?

Phase 1 of the l5 quieter-input-stage work needs a noise BUDGET, not just a
total. ngspice's `noise` analysis builds a `noise1` plot carrying one spectral
-density vector per elementary noise source. This prints the vector list for a
real sized design so the parser can be written against the actual names.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds            # noqa: E402
import extract as E               # noqa: E402
import size as S                  # noqa: E402
from topology import Topology     # noqa: E402


def main():
    hp = sys.argv[1] if len(sys.argv) > 1 else "439032"
    spec_name = sys.argv[2] if len(sys.argv) > 2 else "dhruva-l5"
    row = None
    for r in ds.load("topo_labels"):
        g = r.get("graph") or {}
        if (r.get("wl_hash") or "").startswith(hp) and r.get("spec") == spec_name \
                and g.get("tokens") and r.get("best_params"):
            nf = ((r.get("margins") or {}).get("nf_db") or {}).get("achieved")
            if row is None or (nf is not None and nf < row[0]):
                row = (nf if nf is not None else 1e9, r)
    if row is None:
        raise SystemExit(f"no {spec_name} row for {hp}")
    r = row[1]
    print(f"design {r['wl_hash']} vs {spec_name}, stored NF {row[0]}")
    topo = Topology(r["graph"]["tokens"])
    prep = S.prepared_body(topo, inductor_q=12)
    body = prep[0]
    spec = S._spec_for_sizing(spec_name)
    b = spec.band
    f0, f_lo, f_hi = float(b["f0"]), float(b["f_lo"]), float(b["f_hi"])
    deck, nin, nout = E.build_noise_deck(body, r["best_params"], f0, f_lo, f_hi)
    # swap the control block for one that DISPLAYS the noise1 plot's vectors
    head = deck.split(".control")[0]
    idx = round((f0 - f_lo) / (f_hi - f_lo) * 50)
    # The 5th `noise` argument is pts_per_summary: WITH it ngspice prints a
    # per-noise-generator breakdown to stdout every N points. Without it only the
    # integrated totals exist, which is why the first probe saw nothing.
    ctrl = "\n".join([
        ".control", "op",
        f"noise v({nout}) Vnz lin 2 {f0:g} {f0 * 1.0001:g} 1",
        "setplot noise1", "display",
        ".endc", ".end"])
    out = E.run_deck(head + ctrl + "\n", "nfprobe_", "n.cir", timeout=120)
    print("=" * 70)
    print(out if out else "NO OUTPUT")


if __name__ == "__main__":
    main()

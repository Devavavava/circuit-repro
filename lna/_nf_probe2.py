"""Probe 2: can we `print` the dotted per-MOSFET noise vectors by name?"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds            # noqa: E402
import extract as E               # noqa: E402
import size as S                  # noqa: E402
from topology import Topology     # noqa: E402


def main():
    for r in ds.load("topo_labels"):
        if (r.get("wl_hash") or "").startswith("439032") and r.get("spec") == "dhruva-l5":
            row = r
            break
    topo = Topology(row["graph"]["tokens"])
    body = S.prepared_body(topo, inductor_q=12)[0]
    spec = S._spec_for_sizing("dhruva-l5")
    b = spec.band
    f0, f_lo, f_hi = float(b["f0"]), float(b["f_lo"]), float(b["f_hi"])
    deck, nin, nout = E.build_noise_deck(body, row["best_params"], f0, f_lo, f_hi)
    head = deck.split(".control")[0]
    ctrl = "\n".join([
        ".control", "op",
        f"noise v({nout}) Vnz lin 2 {f0:g} {f0 * 1.0001:g} 1",
        "setplot noise1",
        "let p_tot = onoise_spectrum[0]*onoise_spectrum[0]",
        "let p_rns = onoise_rns[0]*onoise_rns[0]",
        "let p_m1  = onoise.mnm1[0]*onoise.mnm1[0]",
        "let p_m1id = onoise.mnm1.id[0]*onoise.mnm1.id[0]",
        "let p_rr1 = onoise_rr1[0]*onoise_rr1[0]",
        "print p_tot p_rns p_m1 p_m1id p_rr1",
        "let nf = 10*log10(p_tot/p_rns)",
        "print nf",
        ".endc", ".end"])
    out = E.run_deck(head + ctrl + "\n", "nfprobe2_", "n.cir", timeout=120)
    for ln in (out or "").splitlines():
        if any(k in ln for k in ("p_tot", "p_rns", "p_m1", "p_rr1", "nf ", "rror",
                                 "not found", "unknown")):
            print(ln)


if __name__ == "__main__":
    main()

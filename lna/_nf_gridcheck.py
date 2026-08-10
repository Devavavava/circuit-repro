"""Is `extract.measure_nf` reporting NF at f0, or at the nearest grid point?

`build_noise_deck` sweeps [f_lo, f_hi] in 51 linear points and reads index
round((f0-f_lo)/(f_hi-f_lo)*50). For the dhruva specs f_lo/f_hi span the whole
1.1-2.5 GHz reconfiguration range, so the grid step is 28 MHz and the reported
point can sit up to 14 MHz from f0. This measures the error directly: NF on the
sweep grid vs NF from a sweep placed exactly on f0.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds            # noqa: E402
import extract as E               # noqa: E402
import size as S                  # noqa: E402
from topology import Topology     # noqa: E402

CASES = [("ace838", "dhruva-s"), ("ced0d8", "dhruva-s"),
         ("f57874", "dhruva-s"), ("3e4a6a", "dhruva-s"),
         ("439032", "dhruva-l5"), ("998ff3", "dhruva-l5")]


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


def nf_at(body, params, f0, spec):
    """NF from a sweep whose grid lands exactly on f0 (index 0 of a 2-pt sweep)."""
    b = spec.band
    deck, _, nout = E.build_noise_deck(body, params, f0, float(b["f_lo"]),
                                       float(b["f_hi"]))
    head = deck.split(".control")[0]
    ctrl = "\n".join([
        ".control", "op",
        f"noise v({nout}) Vnz lin 2 {f0:g} {f0 * 1.0001:g} 1",
        "setplot noise1",
        f"let nf = 10*log10((inoise_spectrum[0]*inoise_spectrum[0])/{E.K4TRS:.6e})",
        "print nf", ".endc", ".end"])
    out = E.run_deck(head + ctrl + "\n", "nfgrid_", "n.cir", timeout=120)
    import re
    m = re.search(r"nf\s*=\s*([-\d.eE+]+)", out or "")
    return float(m.group(1)) if m else None


def main():
    print(f"{'design':<14}{'spec':<11}{'f0 GHz':>9}{'grid f GHz':>11}"
          f"{'NF@grid':>9}{'NF@f0':>8}{'delta':>8}")
    for hp, spec_name in CASES:
        r = best_row(hp, spec_name)
        if r is None:
            print(f"{hp:<14}{spec_name:<11}  (no row)")
            continue
        spec = S._spec_for_sizing(spec_name)
        b = spec.band
        f0, f_lo, f_hi = float(b["f0"]), float(b["f_lo"]), float(b["f_hi"])
        idx = max(0, min(50, round((f0 - f_lo) / (f_hi - f_lo) * 50)))
        fgrid = f_lo + idx * (f_hi - f_lo) / 50.0
        body = S.prepared_body(Topology(r["graph"]["tokens"]), inductor_q=12)[0]
        nf_grid = E.measure_nf(body, r["best_params"], spec)
        nf_f0 = nf_at(body, r["best_params"], f0, spec)
        d = (nf_f0 - nf_grid) if (nf_f0 is not None and nf_grid is not None) else None
        print(f"{r['wl_hash'][:12]:<14}{spec_name:<11}{f0/1e9:>9.5f}{fgrid/1e9:>11.5f}"
              f"{nf_grid:>9.3f}{nf_f0:>8.3f}{d:>8.3f}", flush=True)


if __name__ == "__main__":
    main()

"""Per-PDK W-SWEEP golden: every width in the sizer's box must SIMULATE.

Why this exists (2026-08-29, cross-PDK campaign post-mortem): sky130's fd_pr
BSIM4 models are BINNED -- separately fitted cards per width range, ending at
W=7 um for L=0.15 -- and a width outside the table is a FATAL parameter-check
abort (negative interpolated Nfactor), killing the entire deck. The sizer's
box ran to 100 um, so ~half of every device's log-range was fatal, the CMA-ES
was starved into the small-W corner, and sky130 scored 0/24 while every stage
gate stayed green: check_pdk_live used hand-picked in-bin widths, the funnel
golden gates COMPLETION only, and campaign rows have no sim-failure channel.

This golden closes that hole at the cheapest possible level: for every FETCHED
PDK, take the funnel-golden corpus topology, set EVERY device width to each of
a fixed ladder of points spanning the adapter's full W box (both edges
included), and require every point to produce metrics (sim success). It gates
SIMULATABILITY, not feasibility or values -- any PDK whose device models
reject part of the advertised sizing box fails loudly, here, before any
campaign spends compute inside it.

Unfetched PDKs SKIP-WITH-NOTE (clone safety, same as check_pdk_live).

    python lna/ref/check_pdk_wsweep.py            # exit 0 iff GREEN
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(LNA, ".."))
for _p in (LNA, os.path.join(ROOT, "misc", "ZOAF")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                        # noqa: E402
import pdk                                # noqa: E402
import size as S                          # noqa: E402
import solve_spec as SS                   # noqa: E402
import extract as E                       # noqa: E402
from topology import Topology             # noqa: E402

PDKS = ("bptm45", "sky130", "gf180mcu", "ihp_sg13g2")
SPEC = os.path.join(ROOT, "kaggle", "specs-ladder", "cap-e01-wifi.yaml")


def sweep_points(lo, hi):
    """Both edges + a log ladder between them (8 points total)."""
    return sorted(set([lo, hi] + list(np.geomspace(lo, hi, 6))))


def main():
    failures, skipped = [], []
    toks = SS.tokens_for(SS.CORPUS[0])
    for name in PDKS:
        try:
            ad = pdk.get_pdk(name)
            spec = S._spec_for_sizing(SPEC, nf_gate=None, pdk=name)
            prep = S.prepared_body(Topology(list(toks)), inductor_q=12, pdk=name)
        except NotImplementedError as e:
            skipped.append((name, str(e).splitlines()[0]))
            print(f"  [{name}] SKIP (models not fetched)")
            continue
        body, sizable, fixed = prep
        _obj, names, decode, _ev = S.make_objective(body, spec, sizable, fixed)
        base = decode(np.full(len(names), 0.5))
        wnames = [n for n in sizable if sizable[n] == "W"]
        lo, hi = ad.device_ranges["W"]
        bad = []
        for wt in sweep_points(float(lo), float(hi)):
            p = dict(base)
            for n in wnames:
                p[n] = f"{wt:g}"
            m = E.run_and_extract(body, p, spec, pdk=name)
            if m is None:
                bad.append(wt)
        tag = "ok" if not bad else "FAIL"
        print(f"  [{name}] W box {lo*1e6:g}..{hi*1e6:g} um, "
              f"{len(sweep_points(float(lo), float(hi)))} points: "
              f"{'all simulate' if not bad else 'FAILED at ' + ', '.join(f'{w*1e6:g}um' for w in bad)}"
              f"   [{tag}]")
        if bad:
            failures.append((name, bad))
    if failures:
        print("\ncheck_pdk_wsweep: RED -- device models reject part of the "
              "advertised W box; fix the adapter emission or the box.")
        return 1
    print(f"\ncheck_pdk_wsweep: GREEN ({len(PDKS)-len(skipped)} PDK(s) swept, "
          f"{len(skipped)} skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

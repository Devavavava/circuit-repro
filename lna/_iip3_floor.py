"""Characterise the harness's NUMERICAL IM3 floor vs tmax (WP-IIP3, G1).

With a3 = 0 the golden's network C is exactly linear, so anything landing in
the IM3 bins is numerical: trapezoidal LTE on a nonuniform grid plus the
linear resample onto the coherent grid. Both are O(h^2), so the floor should
fall ~12 dB per halving of tmax. Throwaway driver; the durable check is G1.
"""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "ref"))
import iip3 as I
import check_iip3 as G

I.private_tmp()
f0s, f1, f2, fl, fh = I.tone_plan(G.F0)
print("Pin = -20 dBm, network C, a3 = 0 -> every IM3 bin is pure numerics")
print(f"  {'tmax':>10} {'npts':>8} {'Pfund':>9} {'IM3 bin':>10} {'dBc':>9} {'floorbin':>10} {'wall':>7}")
prev = None
for tmax in (20e-12, 10e-12, 5e-12, 2.5e-12):
    body, node = G.body_reactive(10.0, 0.0, I.pav_dbm_to_vemf(-20.0), f1, f2)
    t0 = time.time()
    m, err = I.measure_point(body, node, f0s, f1, f2, fl, fh, tmax=tmax)
    if m is None:
        print(f"  {tmax:10.3g} FAILED {err}"); continue
    dbc = m["pim3"] - m["pfund"]
    d = "" if prev is None else f"  ({dbc - prev:+.1f} dB vs previous)"
    print(f"  {tmax:10.3g} {m['npts']:8d} {m['pfund']:+9.2f} {m['pim3']:+10.2f} "
          f"{dbc:9.1f} {m['floor']:+10.1f} {time.time()-t0:6.1f}s{d}")
    prev = dbc

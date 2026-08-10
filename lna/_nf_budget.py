"""Noise-budget decomposition for the dhruva designs (WP-L5 phase 1).

`measure_nf` says how much noise; this says WHOSE. Validation first (a budget
you have not validated is a story, not a measurement):

  --selftest  golden deck -- ideal gain-10 amp, noisy Rs=50 and an equal Rn=50.
              Exact answer: two equal contributors, NF = 3.0103 dB, and Rn must
              carry 50% of the output noise power.

Then the real designs, reported two ways: share of total output noise power, and
share of the excess noise factor F-1 (what the noise figure is actually paying
for).

    python lna/_nf_budget.py --selftest
    python lna/_nf_budget.py --hash 439032 --spec dhruva-l5
    python lna/_nf_budget.py --all
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds            # noqa: E402
import extract as E               # noqa: E402
import size as S                  # noqa: E402
from topology import Topology     # noqa: E402

CASES = [("ace838", "dhruva-s"), ("ced0d8", "dhruva-s"), ("f57874", "dhruva-s"),
         ("439032", "dhruva-l5"), ("998ff3", "dhruva-l5"), ("6f0d08", "dhruva-s")]


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


def selftest():
    """Golden: gain-10 VCVS, noisy Rs=50 + equal Rn=50 -> NF 3.0103, Rn 50%."""
    body = "\n".join([
        "* NF budget golden",
        "Vp1 p1 0 dc 0 ac 1 portnum 1 z0 50",
        "Rn p1 b 50",
        "Eamp out 0 b 0 10",
        "Vp2 out 0 dc 0 ac 0 portnum 2 z0 50",
    ])

    class _Spec:
        band = {"f0": 2e9, "f_lo": 1e9, "f_hi": 4e9}
    b = E.measure_noise_budget(body, None, _Spec(), mechanisms=False)
    if b is None:
        print("selftest: FAILED (no output)")
        return False
    print(f"  sum/total closure : {b['sum_closure']:.6f}   (exact = 1)")
    print(f"  NF via inoise     : {b['nf_db_inoise']:.4f} dB  (exact 3.0103)")
    print(f"  NF via shares     : {b['nf_db_from_shares']:.4f} dB")
    for name, e in sorted(b["elements"].items()):
        print(f"    {name:<8} p={e['p']:.4e}  frac={e['frac']:.4f}")
    rn = b["elements"].get("rn", {}).get("frac")
    ok = (abs(b["nf_db_inoise"] - 3.0103) <= 0.02
          and abs(b["nf_db_from_shares"] - 3.0103) <= 0.02
          and abs(b["sum_closure"] - 1.0) <= 0.02
          and rn is not None and abs(rn - 0.5) <= 0.02)
    print(f"  selftest: {'GREEN' if ok else 'RED'}")
    return ok


def report(hp, spec_name, as_json=False):
    r = best_row(hp, spec_name)
    if r is None:
        print(f"{hp}/{spec_name}: no row")
        return None
    spec = S._spec_for_sizing(spec_name)
    topo = Topology(r["graph"]["tokens"])
    prep = S.prepared_body(topo, inductor_q=12)
    if prep is None:
        print(f"{hp}: bias insert skipped")
        return None
    b = E.measure_noise_budget(prep[0], r["best_params"], spec)
    if b is None:
        print(f"{hp}: budget failed")
        return None
    mg = r.get("margins") or {}
    nf_stored = (mg.get("nf_db") or {}).get("achieved")
    print(f"\n=== {r['wl_hash'][:14]}  {spec_name}  ({topo.n_devices} devices)  "
          f"stored NF {nf_stored:.3f} dB")
    print(f"    f = {b['f']/1e9:.5f} GHz   NF(inoise) {b['nf_db_inoise']:.3f}   "
          f"NF(shares) {b['nf_db_from_shares']:.3f}   "
          f"sum/total {b['sum_closure']:.4f}")
    rows = sorted(b["elements"].items(), key=lambda kv: -kv[1]["p"])
    print(f"    {'element':<10}{'kind':>5}{'% of out':>10}{'% of F-1':>10}  dominant mechanism")
    for name, e in rows:
        if e["frac"] < 0.005:
            continue
        mech = ""
        if e.get("mech"):
            mk = max(e["mech"].items(), key=lambda kv: kv[1])
            mech = f"{mk[0]} ({100*mk[1]/e['p']:.0f}% of this device)"
        exc = e.get("excess_frac")
        print(f"    {name:<10}{e['kind']:>5}{100*e['frac']:>9.1f}%"
              f"{(100*exc if exc is not None else float('nan')):>9.1f}%  {mech}")
    return {"wl_hash": r["wl_hash"], "spec": spec_name, "budget": b,
            "nf_stored": nf_stored, "n_devices": topo.n_devices}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hash")
    ap.add_argument("--spec", default="dhruva-l5")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    out = []
    for hp, sp in (CASES if a.all else [(a.hash, a.spec)]):
        r = report(hp, sp)
        if r:
            out.append(r)
    if a.out:
        json.dump(out, open(a.out, "w"), indent=1, default=str)
        print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()

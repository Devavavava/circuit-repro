"""Gate-D3 claim verification: the full evidence ladder for one design.

A gate claim is only as good as its audit. For the candidate row this checks,
independently and from the append-only store's own record:

  1. REPLAY   -- rebuild the topology from the row's OWN tokens, re-evaluate the
                 row's OWN best_params, reproduce every gated metric.
  2. IN-BOX   -- every sized parameter inside the spec's declared device box.
  3. FEASIBLE -- spec.feasible() on the re-measured metrics, not the stored ones.
  4. STABLE   -- K_min >= 1 in band, and a wide-band (0.1-20 GHz) stability audit.
  5. NOVEL    -- WL hash absent from the novelty reference (ref-v3).
  6. REPEAT   -- N independent re-evaluations, to show the pass is not label noise.

    python lna/_nf_gate_d3.py --hash ace838 --spec dhruva-s --repeats 5
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds            # noqa: E402
import extract as E               # noqa: E402
import size as S                  # noqa: E402
from novelty import reference, wl_features, nn_similarity   # noqa: E402
from topology import Topology     # noqa: E402

GATED = ("s11_max_db", "s21_db", "idd_ma", "nf_db")


def pick(hash_prefix, spec_name):
    best = None
    for r in ds.load("topo_labels"):
        g = r.get("graph") or {}
        h = r.get("wl_hash") or ""
        if not h.startswith(hash_prefix) or r.get("spec") != spec_name:
            continue
        if not g.get("tokens") or not r.get("best_params"):
            continue
        nf = ((r.get("margins") or {}).get("nf_db") or {}).get("achieved")
        if best is None or (nf is not None and nf < best[0]):
            best = (nf if nf is not None else 1e9, r)
    if best is None:
        raise SystemExit(f"no {spec_name} row with wl_hash prefix {hash_prefix}")
    return best[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hash", required=True)
    ap.add_argument("--spec", default="dhruva-s")
    ap.add_argument("--repeats", type=int, default=5)
    a = ap.parse_args()

    row = pick(a.hash, a.spec)
    spec = S._spec_for_sizing(a.spec)
    topo = Topology(row["graph"]["tokens"])
    params = row["best_params"]
    h = row["wl_hash"]
    prov = row.get("provenance") or {}
    print(f"=== Gate-D3 audit: {h}  vs {a.spec}")
    print(f"    devices {topo.n_devices} (budget {spec.topology['device_budget']}), "
          f"inductors {topo.n_inductors}")
    print(f"    provenance: arm={prov.get('source_arm')} move={prov.get('move')} "
          f"parent={prov.get('parent_wl_hash')} recipe="
          f"{(row.get('zoaf_cfg') or {}).get('recipe')}")

    prep = S.prepared_body(topo, inductor_q=12)
    if prep is None:
        raise SystemExit("bias insert skipped")
    body, sizable, _ = prep

    # 1/6 -- replay + repeats
    print(f"\n[1] REPLAY x{a.repeats} (rebuilt topology, stored params)")
    runs = []
    for i in range(a.repeats):
        m = S.eval_metrics(body, params, spec, nf_gated=True)
        if m is None:
            print(f"    run {i}: SIM FAILED")
            continue
        runs.append(m)
        feas, viol = spec.feasible(m)
        print(f"    run {i}: S11* {m['s11_max_db']:>7.3f}  S21 {m['s21_db']:>7.3f}  "
              f"Idd {m['idd_ma']:>6.3f}  NF {m['nf_db']:>6.3f}  K {m['k_min']:>8.4g}"
              f"   feasible={feas}")
    ok_all = bool(runs) and all(spec.feasible(m)[0] for m in runs)
    spread = {k: (min(m[k] for m in runs), max(m[k] for m in runs)) for k in GATED}
    print(f"    all {len(runs)} runs feasible: {ok_all}")
    for k in GATED:
        lo, hi = spread[k]
        print(f"      {k:<12} {lo:>8.3f} .. {hi:>8.3f}   (spread {hi - lo:.4f})")

    # 2 -- in-box
    rng = S.kind_ranges(spec)
    oob = []
    for k, v in params.items():
        kind = sizable.get(k)
        if kind not in rng:
            continue
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        lo, hi = rng[kind][0], rng[kind][1]
        if x < lo * (1 - 1e-9) or x > hi * (1 + 1e-9):
            oob.append((k, x, lo, hi))
    print(f"\n[2] IN-BOX: {not oob}" + (f"  violations {oob}" if oob else
                                        f"  ({len(params)} params all inside)"))

    # 3 -- constraint table
    m = runs[0]
    print("\n[3] CONSTRAINTS (re-measured)")
    print(spec.report(m))

    # 4 -- stability
    print("\n[4] STABILITY")
    band = spec.band
    f0 = float(band["f0"])
    st = E.measure_stability(body, params, f0, float(band["f_lo"]),
                             float(band["f_hi"]), npts=201)
    wide = E.measure_stability(body, params, f0, 1e8, 2e10, npts=401)
    for label, s in (("in-band", st), ("0.1-20 GHz", wide)):
        if s is None:
            print(f"    {label:<12} unavailable")
            continue
        print(f"    {label:<12} K_f0 {s['k_f0']:>8.4g}  K_min {s['k_min']:>8.4g}  "
              f"mu_min {s['mu_min']:>6.3f}  |D|max {s['delta_max']:>6.3f}  "
              f"-> {E.stability_verdict(s)[0]}")

    # 5 -- novelty
    hashes, feats, meta = reference()
    hh, f = wl_features(topo)
    print(f"\n[5] NOVELTY vs {meta.get('version')} "
          f"({meta.get('n_hashes')} hashes, digest {meta.get('digest')})")
    print(f"    wl_hash in reference: {hh in hashes}   nearest: {nn_similarity(f, feats)}")

    verdict = (ok_all and not oob and st and st["k_min"] >= 1.0 and hh not in hashes)
    print(f"\n=== GATE D3 ({a.spec}): "
          f"{'MET' if verdict else 'NOT MET'}  "
          f"[feasible={ok_all} in_box={not oob} "
          f"K>=1={bool(st) and st['k_min'] >= 1.0} novel={hh not in hashes}]")


if __name__ == "__main__":
    main()

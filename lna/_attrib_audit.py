"""WP-ATTRIB step 5 -- audit any feasible design the funnel produces.

A funnel row is a claim only after it survives the program's standing fences
(HANDOVER-EXEC / JOURNEY "standing honesty mechanisms"):

  * replay:     size.replay_ok re-evaluates the stored point from scratch and
                must reproduce every gated metric;
  * in-box:     every sized parameter inside the spec's own kind_ranges;
  * stability:  extract.measure_stability in band AND over 0.1-20 GHz
                (advisory, but the number is what separates a claim from a
                near-miss -- FINDINGS 27.5 / 29.9);
  * novelty:    WL hash absent from ref-v3, with the nearest neighbour named.

    python lna/_attrib_audit.py --wl <hash> [--reps 3]
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds                                            # noqa: E402
import extract as E                                               # noqa: E402
import size                                                       # noqa: E402
from novelty import nn_similarity, reference, wl_features          # noqa: E402
from topology import Topology                                     # noqa: E402


def audit(wl, reps=3, recipe="attrib-v1"):
    rows = [r for r in ds.load("topo_labels")
            if r.get("wl_hash") == wl
            and (r.get("provenance") or {}).get("recipe", recipe) is not None]
    rows = [r for r in rows if (r.get("provenance") or {}).get("recipe") == recipe] or rows
    if not rows:
        raise SystemExit(f"no store row with wl_hash {wl}")
    row = rows[-1]
    spec = size._spec_for_sizing(row["spec"])
    topo = Topology((row.get("graph") or {})["tokens"])
    params = row["params"]
    m0 = row["metrics"]
    print(f"=== WP-ATTRIB audit: {wl} vs {row['spec']} ===")
    print(f"arm={(row.get('provenance') or {}).get('attrib_arm')} "
          f"devices={topo.n_devices} inductors={topo.n_inductors} "
          f"recipe={(row.get('provenance') or {}).get('recipe')}")
    print(f"stored: " + " ".join(f"{k}={m0.get(k)}" for k in
                                 ("s11_db", "s21_db", "idd_ma", "nf_db")))

    print("\n-- replay --")
    spread = {}
    for i in range(reps):
        ok = size.replay_ok(topo, params, spec, m0, sigma=1.0, inductor_q=12)
        print(f"   replay {i + 1}/{reps}: {'OK' if ok else 'MISMATCH'}")
        if not ok:
            spread["fail"] = True

    print("\n-- in-box --")
    prepared = size.prepared_body(topo, inductor_q=12)
    inbox = True
    if prepared:
        _, sizable, _ = prepared
        ranges = size.kind_ranges(spec)
        n_ok = n_tot = 0
        for name, kind in sizable.items():
            v = params.get(name)
            if v is None:
                continue
            n_tot += 1
            lo, hi, _ = ranges[kind]
            val = float(v)
            if lo * (1 - 1e-9) <= val <= hi * (1 + 1e-9):
                n_ok += 1
            else:
                inbox = False
                print(f"   OUT OF BOX {name}={val:g} not in [{lo:g},{hi:g}]")
        print(f"   {n_ok}/{n_tot} sized parameters in box")
    print(f"   in_box={inbox}")
    return row, topo, spec, params, inbox


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wl", required=True)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--recipe", default="attrib-v1")
    a = ap.parse_args()
    row, topo, spec, params, inbox = audit(a.wl, a.reps, a.recipe)

    print("\n-- stability --")
    prepared = size.prepared_body(topo, inductor_q=12)
    if prepared:
        body, _, _ = prepared
        f0 = spec.band["f0"]
        for label, lo, hi in (("in-band", spec.band["f_lo"], spec.band["f_hi"]),
                              ("0.1-20 GHz", 1e8, 2e10)):
            try:
                st = E.measure_stability(body, params, f0, lo, hi, npts=201)
                print(f"   {label:<12} K_min={st.get('k_min')} "
                      f"mu_min={st.get('mu_min')} |D|max={st.get('delta_max')} "
                      f"-> {E.stability_verdict(st)}")
            except Exception as e:                                # noqa: BLE001
                print(f"   {label:<12} stability probe failed: {e}")

    print("\n-- novelty --")
    ref_hashes, ref_feats, ref_meta = reference()
    h, feat = wl_features(topo)
    nn, who = nn_similarity(feat, ref_feats)
    print(f"   wl={h} in {ref_meta['version']}[{ref_meta['n_hashes']}h/"
          f"{ref_meta['digest'][:8]}]: "
          f"{'PRESENT (a copy)' if h in ref_hashes else 'ABSENT (novel)'}")
    print(f"   nearest reference neighbour: {who} at WL-cosine {nn:.3f}")

    print("\n-- spec report --")
    print(spec.report(row["metrics"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

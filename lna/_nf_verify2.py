"""Verify the device_budget-18 headline designs: replay, in-box, K, novelty.

Session 6b (FINDINGS §21). Every Gate-D3 claim must be replay-verified against
its own stored parameters, inside the spec box, and K >= 1 in band.

    python lna/_nf_verify2.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds            # noqa: E402
import size as S                  # noqa: E402
from novelty import reference, wl_features, nn_similarity   # noqa: E402
from topology import Topology     # noqa: E402

TIER1 = ("s11_max_db", "s21_db", "idd_ma")
# (results file, index or None=lowest violation, spec, label)
TARGETS = [
    ("h2_s_tier1.json", 0, "dhruva-s", "TIER-1 FEASIBLE dhruva-s, best NF"),
    ("g1_grow_s.json", None, "dhruva-s", "best as-found growth mutant"),
    ("g2_grow16_s.json", None, "dhruva-s", "best 16-dev-parent growth mutant"),
    ("h1_l5_tier1.json", None, "dhruva-l5", "TIER-1 FEASIBLE dhruva-l5, best NF"),
]


def main():
    toks, prior = {}, set()
    for r in ds.load("topo_labels"):
        g = r.get("graph") or {}
        if r.get("wl_hash") and g.get("tokens"):
            toks.setdefault(r["wl_hash"], g["tokens"])
        rec = (r.get("zoaf_cfg") or {}).get("recipe") or ""
        if r.get("wl_hash") and not rec.startswith("nf-v2"):
            prior.add(r["wl_hash"])
    hashes, feats, meta = reference()
    print("ref:", {k: meta.get(k) for k in ("version", "n_hashes", "digest")}, "\n")

    for fn, idx, spec_name, label in TARGETS:
        path = os.path.join(HERE, "out", "_nf", fn)
        if not os.path.exists(path):
            print(f"--- {label}: {fn} missing\n")
            continue
        recs = json.load(open(path))
        rec = recs[idx] if idx is not None else min(
            recs, key=lambda r: r.get("violation", 9e9))
        h = rec.get("wl_hash") or (rec.get("origin") or {}).get("store_wl_hash")
        if not h or h not in toks:
            print(f"--- {label}: no tokens for {h}\n")
            continue
        spec = S._spec_for_sizing(spec_name)
        topo = Topology(toks[h])
        prep = S.prepared_body(topo, inductor_q=12)
        if prep is None:
            print(f"--- {label}: bias insert skipped\n")
            continue
        body, sizable, _ = prep
        m = S.eval_metrics(body, rec["best_params"], spec, nf_gated=True)
        ok = S.replay_ok(topo, rec["best_params"], spec, rec["metrics"], sigma=1.0)
        rng = S.kind_ranges(spec)
        oob = []
        for k, v in rec["best_params"].items():
            kind = sizable.get(k)
            if kind not in rng:
                continue
            try:
                x = float(v)
            except (TypeError, ValueError):
                continue
            lo, hi = rng[kind][0], rng[kind][1]
            if x < lo * (1 - 1e-9) or x > hi * (1 + 1e-9):
                oob.append(k)
        feas, viol = spec.feasible(m)
        hh, f = wl_features(topo)
        print(f"--- {label}  [{spec_name}]   move={rec.get('move', '-')}")
        print(f"    wl {h}  devices {len(topo.devices)}  "
              f"budget {spec.topology['device_budget']}")
        print(f"    S11* {m['s11_max_db']:.2f}  S21 {m['s21_db']:.2f}  "
              f"Idd {m['idd_ma']:.2f}  NF {m['nf_db']:.3f}  K_min {m['k_min']:.4g}")
        print(f"    replay_ok={ok}  in_box={not oob}  K>=1={m['k_min'] >= 1}  "
              f"tier1_ok={all(k not in viol for k in TIER1)}  tier2={feas}  "
              f"viol={sum(viol.values()):.3f} ({','.join(viol) or '-'})")
        print(f"    novel: in_ref={hh in hashes}  in_prior_store={hh in prior}  "
              f"nn={nn_similarity(f, feats)}\n", flush=True)


if __name__ == "__main__":
    main()

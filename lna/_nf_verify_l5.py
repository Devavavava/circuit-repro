"""Verify the best dhruva-l5 / dhruva-s rows straight from the store (FINDINGS §21).

Used where a run was stopped before it wrote its results JSON: the append-only
store row is the record of truth, so re-evaluate its `best_params` on the
topology rebuilt from that row's own tokens.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds            # noqa: E402
import size as S                  # noqa: E402
from novelty import reference, wl_features, nn_similarity   # noqa: E402
from topology import Topology     # noqa: E402

TIER1 = ("s11_max_db", "s21_db", "idd_ma")
WANT = [("dhruva-s", ("f57874", "3e4a6a", "749959", "575318", "6f0d08")),
        ("dhruva-l5", ("f57874", "439032", "1e27a3", "19f72303"))]


def main():
    hashes, feats, meta = reference()
    rows = ds.load("topo_labels")
    for spec_name, prefixes in WANT:
        spec = S._spec_for_sizing(spec_name)
        best = {}
        for r in rows:
            g = r.get("graph") or {}
            h = r.get("wl_hash") or ""
            if r.get("spec") != spec_name or not g.get("tokens") or not r.get("best_params"):
                continue
            if not any(h.startswith(p) for p in prefixes):
                continue
            nf = ((r.get("margins") or {}).get("nf_db") or {}).get("achieved")
            mg = r.get("margins") or {}
            t1 = all((mg.get(k) or {}).get("margin", -1) >= 0 for k in TIER1)
            key = (0 if t1 else 1, nf if nf is not None else 1e9)
            if h not in best or key < best[h][0]:
                best[h] = (key, r)
        print(f"=== {spec_name}")
        for h, (_, r) in sorted(best.items(), key=lambda kv: kv[1][0]):
            topo = Topology(r["graph"]["tokens"])
            prep = S.prepared_body(topo, inductor_q=12)
            if prep is None:
                continue
            m = S.eval_metrics(prep[0], r["best_params"], spec, nf_gated=True)
            if m is None:
                print(f"  {h[:10]}: does not simulate")
                continue
            # `size.replay_ok` compares s21_db + s11_db, but a dhruva row's
            # `margins` only carries the GATED metrics (s11_max_db, not s11_db),
            # so feeding it those reads a missing key as a failure. The invariant
            # that matters is the same one: re-evaluating the row's own
            # best_params on the topology rebuilt from the row's own tokens must
            # reproduce every stored gated metric within label noise.
            stored = {k: ((r.get("margins") or {}).get(k) or {}).get("achieved")
                      for k in TIER1 + ("nf_db",)}
            tol = {"s11_max_db": 2.0, "s21_db": 1.0, "idd_ma": 1.0, "nf_db": 1.0}
            ok = all(stored[k] is not None and m.get(k) is not None
                     and abs(m[k] - stored[k]) <= tol[k] for k in stored)
            rng, (_, sizable, _) = S.kind_ranges(spec), prep
            oob = [k for k, v in r["best_params"].items()
                   if sizable.get(k) in rng
                   and _num(v) is not None
                   and not (rng[sizable[k]][0] * (1 - 1e-9) <= _num(v)
                            <= rng[sizable[k]][1] * (1 + 1e-9))]
            feas, viol = spec.feasible(m)
            hh, f = wl_features(topo)
            print(f"  {h[:14]} dev={len(topo.devices):>2} "
                  f"move={(r.get('provenance') or {}).get('move', '-'):<14} "
                  f"S11*{m['s11_max_db']:>7.2f} S21{m['s21_db']:>7.2f} "
                  f"Idd{m['idd_ma']:>6.2f} NF{m['nf_db']:>6.2f} K{m['k_min']:>8.4g} "
                  f"viol {sum(viol.values()):>6.3f} ({','.join(viol) or '-'}) "
                  f"t1={all(k not in viol for k in TIER1)} replay={ok} "
                  f"in_box={not oob} novel_ref={hh not in hashes}", flush=True)


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()

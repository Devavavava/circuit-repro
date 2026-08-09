"""NF landscape scan around a stored design (Gate-D3 diagnosis, Session 6).

A descent that stalls tells you it stalled, not why. This sweeps each sizable
parameter across its full spec box with everything else held, and reports:

  * the NF range one coordinate can reach on its own,
  * the NF at that coordinate's best value and what tier-1 constraint it breaks,

then a 2-D grid over the two most NF-sensitive coordinates (a noise-cancellation
condition is a *ratio*, so the 1-D picture can hide the valley).

    python lna/_nf_scan.py --spec dhruva-s --hash 8c7592ea --n 11
    python lna/_nf_scan.py --spec dhruva-s --hash 8c7592ea --pair pNM4W,pR1V --n 9
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds          # noqa: E402
import size as S                # noqa: E402
from topology import Topology   # noqa: E402

TIER1 = ("s11_max_db", "s21_db", "idd_ma")


def load(hash_prefix, spec_name):
    best = None
    for r in ds.load("topo_labels"):
        g = r.get("graph") or {}
        h = r.get("wl_hash") or ""
        if not h.startswith(hash_prefix) or not g.get("tokens") or not r.get("best_params"):
            continue
        nf = ((r.get("margins") or {}).get("nf_db") or {}).get("achieved")
        rank = (0 if r.get("spec") == spec_name else 1, nf if nf is not None else 1e9)
        if best is None or rank < best[0]:
            best = (rank, r)
    if best is None:
        raise SystemExit(f"no store row with wl_hash prefix {hash_prefix}")
    r = best[1]
    return Topology(r["graph"]["tokens"]), r["best_params"], r


def grid(lo, hi, n, islog):
    if islog:
        return [10 ** (math.log10(lo) + i * (math.log10(hi) - math.log10(lo)) / (n - 1))
                for i in range(n)]
    return [lo + i * (hi - lo) / (n - 1) for i in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default="dhruva-s")
    ap.add_argument("--hash", required=True)
    ap.add_argument("--n", type=int, default=11)
    ap.add_argument("--pair", default=None, help="two param names for a 2-D grid")
    ap.add_argument("--from-json", dest="from_json", default=None,
                    help="<nf_campaign results.json>:<idx> -- start point override")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    spec = S._spec_for_sizing(a.spec)
    topo, params, row = load(a.hash, a.spec)
    if a.from_json:
        path, _, idx = a.from_json.rpartition(":")
        params = json.load(open(path))[int(idx)]["best_params"]
    prep = S.prepared_body(topo, inductor_q=12)
    if prep is None:
        raise SystemExit("bias insert skipped")
    body, sizable, _ = prep
    rng = S.kind_ranges(spec)
    base = S.eval_metrics(body, params, spec, nf_gated=True)
    print(f"base: S11* {base['s11_max_db']:.2f}  S21 {base['s21_db']:.2f}  "
          f"Idd {base['idd_ma']:.2f}  NF {base['nf_db']:.3f}  "
          f"K {base.get('k_min')}\n")

    def ev(p):
        m = S.eval_metrics(body, p, spec, nf_gated=True)
        return m

    def t1(m):
        _, v = spec.feasible(m)
        return [k for k in TIER1 if k in v]

    rows = []
    if a.pair:
        n1, n2 = a.pair.split(",")
        g1 = grid(*rng[sizable[n1]][:2], a.n, rng[sizable[n1]][2])
        g2 = grid(*rng[sizable[n2]][:2], a.n, rng[sizable[n2]][2])
        print(f"{'':>12}" + "".join(f"{v:>9.3g}" for v in g2))
        for v1 in g1:
            line = f"{v1:>12.4g}"
            for v2 in g2:
                p = dict(params, **{n1: f"{v1:.6g}", n2: f"{v2:.6g}"})
                m = ev(p)
                nf = m.get("nf_db") if m else None
                ok = m is not None and not t1(m)
                line += ("      -  " if nf is None
                         else (f"{nf:>8.2f}" + ("*" if ok else " ")))
                rows.append({"p1": v1, "p2": v2, "metrics": m})
            print(line, flush=True)
        print(f"\n({n1} down, {n2} across; '*' = tier-1 clean)")
    else:
        print(f"{'param':<10}{'kind':>5}{'base':>11}{'NF@base':>9}"
              f"{'NF_min':>8}{'at':>11}{'NF_max':>8}{'clean_min':>10}  binds_at_min")
        out = []
        for name, kind in sizable.items():
            if name not in params or kind not in rng:
                continue
            lo, hi, islog = rng[kind]
            b = float(params[name])
            best = (1e9, None, None)
            cbest = (1e9, None)
            worst = -1e9
            for v in grid(lo, hi, a.n, islog):
                m = ev(dict(params, **{name: f"{v:.6g}"}))
                if m is None or m.get("nf_db") is None:
                    continue
                nf = m["nf_db"]
                binds = t1(m)
                worst = max(worst, nf)
                if nf < best[0]:
                    best = (nf, v, binds)
                if not binds and nf < cbest[0]:
                    cbest = (nf, v)
            if best[1] is None:
                continue
            print(f"{name:<10}{kind:>5}{b:>11.4g}{base['nf_db']:>9.2f}"
                  f"{best[0]:>8.2f}{best[1]:>11.4g}{worst:>8.2f}"
                  f"{(cbest[0] if cbest[1] is not None else float('nan')):>10.2f}"
                  f"  {','.join(best[2]) or '-'}", flush=True)
            out.append({"param": name, "kind": kind, "base": b,
                        "nf_min": best[0], "at": best[1], "binds": best[2],
                        "nf_max": worst,
                        "nf_min_tier1_clean": cbest[0] if cbest[1] is not None else None})
        rows = out
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        json.dump({"base": base, "scan": rows}, open(a.out, "w"), indent=1, default=str)
        print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()

"""Relabel stored L2 rows onto the multi-finger MOS harness (WP-MF, FINDINGS §27).

Same doctrine as WP-D1's `relabel_nf.py`: **a new harness is a new label domain.**
Every NF-bearing row in the store was measured with single-finger MOS emission,
which put 26-40% of the excess noise factor into BSIM4 gate-electrode resistance
(§26). Those rows must not be silently pooled with post-cutover ones, and they
must not be edited in place -- the store is append-only.

One important difference from WP-D1, and it changes what "relabel" means here.
The NF cutover changed a *measurement* of an advisory metric; this cutover
changes the **circuit**: removing the gate resistance also moves the input match
(measured: s11_max -10.00 -> -7.85 on a design that was exactly at the limit). So
this re-evaluates the FULL metric vector at the stored best point, not just
`nf_db` -- a row must carry the metrics that actually go with its geometry. The
design is unchanged and sizing is NOT re-run; what changes is the harness the
same design is measured in. Re-SIZING is a separate job (the flagship
re-verification), because a re-sized design is a different point.

  1. selects L2 rows with an `nf_db` and no `w_finger` stamp (pre-cutover);
  2. dedupes by (wl_hash, spec, best_params) -- repeat probes of one point do not
     need re-simulating, and the count of both is reported;
  3. rebuilds each circuit from that row's OWN `graph.tokens` (never a
     `token_file` path -- 07-EXIT's polish bug);
  4. fences with an OLD-geometry replay: re-evaluating the stored params under
     single-finger emission must reproduce the stored S11/S21, else the
     (topo, params) pair is inconsistent and the row is **quarantined**;
  5. appends a NEW row measured under the new emission, recipe bumped
     `<old>+mf2-v1`, `provenance.relabel_of` -> the superseded row's ts.

    python lna/relabel_mf.py --audit
    python lna/relabel_mf.py --run [--limit N] [--spec dhruva-s]
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds          # noqa: E402
import size as S                # noqa: E402
from topology import Topology   # noqa: E402

RECIPE_SUFFIX = "+mf2-v1"
GATED = ("s11_max_db", "s11_db", "s21_db", "idd_ma", "nf_db")


def candidates(spec_filter=None):
    """Pre-cutover NF-bearing rows, deduped by (wl_hash, spec, params)."""
    seen, out, total = {}, [], 0
    for r in ds.load("topo_labels"):
        if r.get("kind") != "L2":
            continue
        mg = r.get("margins") or {}
        if (mg.get("nf_db") or {}).get("achieved") is None:
            continue
        if "w_finger" in (r.get("zoaf_cfg") or {}):
            continue                       # already post-cutover
        g = r.get("graph") or {}
        if not g.get("tokens") or not r.get("best_params"):
            continue
        if spec_filter and r.get("spec") != spec_filter:
            continue
        total += 1
        key = (r.get("wl_hash"), r.get("spec"),
               json.dumps(r["best_params"], sort_keys=True))
        if key in seen:
            continue
        seen[key] = True
        out.append(r)
    return out, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--spec")
    ap.add_argument("--out")
    a = ap.parse_args()

    rows, total = candidates(a.spec)
    print(f"pre-cutover NF-bearing L2 rows: {total}  "
          f"distinct (design, spec, params): {len(rows)}")
    if a.audit or not a.run:
        by = {}
        for r in rows:
            by[r.get("spec")] = by.get(r.get("spec"), 0) + 1
        for k, v in sorted(by.items(), key=lambda kv: -kv[1]):
            print(f"   {k:<16} {v}")
        return

    todo = rows[:a.limit] if a.limit else rows
    print(f"relabeling {len(todo)}\n")
    print(f"{'wl_hash':<14}{'spec':<14}{'NF old':>8}{'NF new':>8}{'dNF':>8}"
          f"{'S11 old':>9}{'S11 new':>9}  verdict")
    n_ok = n_quar = n_fail = 0
    deltas, results = [], []
    t0 = time.time()
    for r in todo:
        spec_name = r.get("spec")
        try:
            spec = S._spec_for_sizing(spec_name)
        except Exception:
            n_fail += 1
            continue
        topo = Topology(r["graph"]["tokens"])
        params = r["best_params"]
        mg = r.get("margins") or {}
        stored = {k: (mg.get(k) or {}).get("achieved") for k in GATED}
        s11key = "s11_max_db" if stored.get("s11_max_db") is not None else "s11_db"

        # (4) OLD-geometry replay fence
        old = S.prepared_body(topo, inductor_q=12, w_finger=None)
        if old is None:
            n_fail += 1
            continue
        m_old = S.eval_metrics(old[0], params, spec, nf_gated=True)
        ok = (m_old is not None
              and stored.get("s21_db") is not None
              and abs((m_old.get("s21_db") or -1e9) - stored["s21_db"]) <= 1.0
              and abs((m_old.get(s11key) or -1e9) - (stored.get(s11key) or 1e9)) <= 2.0)
        if not ok:
            n_quar += 1
            S.log_l2_result(spec, topo, m_old or {}, False, params,
                            dict(r.get("provenance") or {},
                                 relabel_of=r.get("ts"), relabel="mf2-quarantine"),
                            (r.get("zoaf_cfg") or {}).get("recipe", "?") + "+mf2-quarantine",
                            0, inductor_q=12, repeat_probe=True)
            print(f"{(r.get('wl_hash') or '')[:12]:<14}{spec_name:<14}"
                  f"{'  QUARANTINED (replay failed under old geometry)':>50}")
            continue

        # (5) measure under the NEW emission at the same point
        new = S.prepared_body(topo, inductor_q=12)
        m_new = S.eval_metrics(new[0], params, spec, nf_gated=True) if new else None
        if m_new is None or m_new.get("nf_db") is None:
            n_fail += 1
            continue
        feas = spec.feasible(m_new)[0]
        S.log_l2_result(spec, topo, m_new, feas, params,
                        dict(r.get("provenance") or {}, relabel_of=r.get("ts"),
                             relabel="mf2"),
                        (r.get("zoaf_cfg") or {}).get("recipe", "?") + RECIPE_SUFFIX,
                        0, inductor_q=12, repeat_probe=True)
        d = m_new["nf_db"] - stored["nf_db"]
        deltas.append(d)
        results.append({"wl_hash": r.get("wl_hash"), "spec": spec_name,
                        "nf_old": stored["nf_db"], "nf_new": m_new["nf_db"],
                        "d_nf": d, "feasible_new": feas})
        n_ok += 1
        print(f"{(r.get('wl_hash') or '')[:12]:<14}{spec_name:<14}"
              f"{stored['nf_db']:>8.3f}{m_new['nf_db']:>8.3f}{d:>8.3f}"
              f"{(stored.get(s11key) or float('nan')):>9.2f}"
              f"{(m_new.get(s11key) or float('nan')):>9.2f}"
              f"  {'FEASIBLE' if feas else ''}", flush=True)

    print(f"\nrelabeled {n_ok}, quarantined {n_quar}, failed {n_fail}, "
          f"{time.time()-t0:.0f}s")
    if deltas:
        deltas.sort()
        n = len(deltas)
        print(f"NF delta (new - old): min {deltas[0]:.3f}  p25 {deltas[n//4]:.3f}  "
              f"median {deltas[n//2]:.3f}  p75 {deltas[3*n//4]:.3f}  "
              f"max {deltas[-1]:.3f}  mean {sum(deltas)/n:.3f}")
        print(f"improved (NF lower): {sum(1 for d in deltas if d < 0)}/{n}")
    if a.out and results:
        json.dump(results, open(a.out, "w"), indent=1, default=str)
        print(f"wrote {a.out}")


if __name__ == "__main__":
    main()

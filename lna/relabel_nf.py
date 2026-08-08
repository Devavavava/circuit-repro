"""Relabel stored L2 rows onto the trusted series-Rs NF harness (WP-D1 step 3).

Why this exists (plans2/08-DHRUVA-GOAL.md, WP-D1): *a new harness is a new label
domain*. Rows measured before `extract.measure_nf` landed carry an `nf_db` taken
from `inoise_spectrum` referred to the S-parameter **port**, which is unphysical
once the stage has gain -- two stored rows literally read a NEGATIVE noise figure.
Those rows must not be silently mixed with the series-Rs ones, and they must not
be edited in place either (the store is append-only). So this tool:

  1. audits the store for L2 rows whose `metrics.nf_method != "series_rs"`;
  2. rebuilds each row's circuit from that row's OWN `graph.tokens` (never from a
     `token_file` path -- 07-EXIT's polish bug) or, for reference-deck rows, from
     the named `.cir`;
  3. fences with `size.replay_ok`: re-evaluating the stored `best_params` must
     reproduce the stored S11/S21 within label noise, else the (topo, params)
     pair is inconsistent and the row is **quarantined**, not relabeled;
  4. measures NF at the stored best point with `extract.measure_nf` and appends a
     NEW row that is identical except for `metrics.nf_db`/`nf_method`, with the
     **recipe bumped** (`<old>+nfrs-v1`) and `provenance.relabel_of` pointing at
     the superseded row's ts. Sizing is NOT re-run: the design is unchanged, only
     the measurement of one advisory metric.

Quarantined rows get a row too (recipe `<old>+nfrs-quarantine`) with
`metrics.nf_method = "quarantined"` so the audit is self-documenting.

    python lna/relabel_nf.py --audit          # count only, no simulation
    python lna/relabel_nf.py --run            # relabel (append rows)
    python lna/relabel_nf.py --run --limit 3  # chunked
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds          # noqa: E402
import extract as E             # noqa: E402
import size as S                # noqa: E402
from spec import Spec           # noqa: E402
from topology import Topology   # noqa: E402

NEW_METHOD = "series_rs"
BUMP = "+nfrs-v1"
QUAR = "+nfrs-quarantine"


def legacy_rows(rows=None):
    """L2 rows not on the series-Rs harness, minus ones already relabeled."""
    rows = rows if rows is not None else ds.load("topo_labels")
    l2 = [r for r in rows if r.get("kind") == "L2"]
    done = {(r.get("wl_hash"), r.get("spec")) for r in l2
            if str((r.get("zoaf_cfg") or {}).get("recipe", "")).endswith((BUMP, QUAR))}
    return [r for r in l2
            if (r.get("metrics") or {}).get("nf_method") != NEW_METHOD
            and (r.get("wl_hash"), r.get("spec")) not in done]


def _body_for(row, inductor_q=12):
    """(body, topo) for a stored row, rebuilt from the row's own tokens or deck."""
    toks = (row.get("graph") or {}).get("tokens")
    if toks:
        import bias
        topo = Topology(list(toks))
        kw = {"inductor_q": inductor_q} if inductor_q else {}
        nl, _, rep, _ = bias.insert_bias(topo, sweep=True, **kw)
        if rep.get("skipped") or not nl.two_port:
            return None, None
        return E.body_of(nl.emit()), topo
    deck = (row.get("provenance") or {}).get("ref_deck")
    if deck:
        return E.body_of(os.path.join(HERE, "ref", deck)), None
    return None, None


def relabel_row(row, inductor_q=12, sigma=1.0):
    """Returns (status, nf_new, note). status in relabeled|quarantined|failed."""
    spec = S._spec_for_sizing(row["spec"])
    params = row.get("best_params")
    stored = row.get("metrics") or {}
    if not params:
        return "failed", None, "no best_params"
    body, topo = _body_for(row, inductor_q=inductor_q)
    if body is None:
        return "failed", None, "could not rebuild body"

    if topo is not None:
        ok = S.replay_ok(topo, params, spec, stored, sigma=sigma,
                         inductor_q=inductor_q)
    else:                                    # reference deck: replay directly
        m = E.run_and_extract(body, params, spec)
        ok = (m is not None
              and abs((m.get("s21_db") or -1e9) - (stored.get("s21_db") or 1e9)) <= max(sigma, 0.5)
              and abs((m.get("s11_db") or -1e9) - (stored.get("s11_db") or 1e9)) <= 2.0)
    if not ok:
        return "quarantined", None, "replay_ok failed (topo/params inconsistent)"

    nf = E.measure_nf(body, params, spec)
    if nf is None:
        return "failed", None, "measure_nf returned None"
    return "relabeled", nf, ""


def _emit(row, status, nf):
    """Append the successor row: same design, new NF domain, bumped recipe."""
    spec = S._spec_for_sizing(row["spec"])
    metrics = dict(row.get("metrics") or {})
    if status == "relabeled":
        metrics["nf_db"], metrics["nf_method"] = nf, NEW_METHOD
        suffix = BUMP
    else:
        metrics["nf_db"], metrics["nf_method"] = None, "quarantined"
        suffix = QUAR
    old_recipe = (row.get("zoaf_cfg") or {}).get("recipe") or "unknown"
    new = dict(row)
    new["metrics"] = metrics
    new["margins"] = ds.margins_for(spec, metrics)
    new["zoaf_cfg"] = dict(row.get("zoaf_cfg") or {}, recipe=old_recipe + suffix)
    new["provenance"] = dict(row.get("provenance") or {},
                             relabel_of={"ts": row.get("ts"), "recipe": old_recipe,
                                         "nf_db_old": (row.get("metrics") or {}).get("nf_db")})
    new["nf_relabel"] = True
    new["git_sha"] = ds.git_sha()
    new["ts"] = ds._now()
    ds.append("topo_labels", ds._jsonify(new))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audit", action="store_true", help="report only, no simulation")
    ap.add_argument("--run", action="store_true", help="measure + append new rows")
    ap.add_argument("--limit", type=int, help="stop after N rows (chunking)")
    ap.add_argument("--inductor-q", type=int, default=12)
    a = ap.parse_args()

    todo = legacy_rows()
    allrows = [r for r in ds.load("topo_labels") if r.get("kind") == "L2"]
    print(f"L2 rows: {len(allrows)};  on series_rs: "
          f"{sum(1 for r in allrows if (r.get('metrics') or {}).get('nf_method') == NEW_METHOD)};"
          f"  needing relabel: {len(todo)}")
    for r in todo:
        print(f"   {r.get('wl_hash'):<18} {r.get('spec'):<13} "
              f"recipe={(r.get('zoaf_cfg') or {}).get('recipe'):<14} "
              f"old_nf={(r.get('metrics') or {}).get('nf_db')}")
    if not a.run:
        return 0

    n = {"relabeled": 0, "quarantined": 0, "failed": 0}
    print(f"\n{'wl_hash':<18} {'spec':<13} {'old_nf':>9} {'new_nf':>9}  status")
    for i, r in enumerate(todo):
        if a.limit and i >= a.limit:
            print(f"  (limit {a.limit} reached)")
            break
        status, nf, note = relabel_row(r, inductor_q=a.inductor_q)
        n[status] += 1
        old = (r.get("metrics") or {}).get("nf_db")
        print(f"{str(r.get('wl_hash')):<18} {r.get('spec'):<13} "
              f"{(old if old is not None else float('nan')):>9.3f} "
              f"{(nf if nf is not None else float('nan')):>9.3f}  {status} {note}")
        if status in ("relabeled", "quarantined"):
            _emit(r, status, nf)
    print(f"\nrelabeled {n['relabeled']}, quarantined {n['quarantined']}, "
          f"failed {n['failed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

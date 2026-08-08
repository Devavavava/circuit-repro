"""WP-D4: who survives when NF becomes a hard constraint? (Gate D3 baseline.)

Every "feasible" row in the store was earned under TIER-1 gating -- S11 / S21 /
Idd, with NF measured but advisory. WP-D1 made NF a real constraint, so the honest
next question is a contrast, not a claim: re-judge each stored feasible design,
unchanged, against its own spec with NF gated. Some survive; most should not.
That table is a result either way, and it is the baseline Gate D3 has to beat.

Method (no re-sizing -- the designs are fixed, only the verdict changes):
  * take every feasible L2 row, dedup on (wl_hash, spec) keeping the best
    tier-1 objective;
  * rebuild the circuit from that row's OWN graph.tokens (or its ref deck);
  * fence with size.replay_ok, then re-measure with size.eval_metrics
    (op/sp/stability + the series-Rs NF);
  * report tier-1 verdict, tier-2 verdict, the NF shortfall in dB, and the
    advisory stability verdict.

    python lna/nf_contrast.py               # table to stdout
    python lna/nf_contrast.py --md          # markdown (for FINDINGS)
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds          # noqa: E402
import extract as E             # noqa: E402
import size as S                # noqa: E402
from topology import Topology   # noqa: E402


def feasible_designs():
    """Distinct (wl_hash, spec) designs that were ever tier-1 feasible.

    Selection prefers an IN-BOX row over an out-of-box one before it compares
    objectives: the store is append-only, so a design's original polish-derived row
    (which could leave the spec's device box -- see the box-clamp note in
    size.polish) still sits next to its re-derived bounded row, and judging the
    out-of-box one would restate a claim we already know is overstated."""
    best = {}
    for r in ds.load("topo_labels"):
        if r.get("kind") != "L2" or not r.get("feasible"):
            continue
        k = (r.get("wl_hash"), r.get("spec"))
        spec = S._spec_for_sizing(r["spec"], nf_gate=False)
        rank = (1 if out_of_box(r, spec) else 0, r.get("best_obj") or 0)
        cur = best.get(k)
        if cur is None or rank < cur[0]:
            best[k] = (rank, r)
    return [best[k][1] for k in sorted(best, key=lambda t: (t[1], str(t[0])))]


def _body_for(row, inductor_q=12):
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


def out_of_box(row, spec):
    """Params outside the spec's declared device box -> [(name, kind, v, lo, hi)].

    Only polish-derived rows can be affected (ZOAF searches inside the box), but a
    feasibility claim standing on an out-of-box device is overstated, so it is
    checked for every row. See the box-clamp note in size.polish."""
    import bias
    toks = (row.get("graph") or {}).get("tokens")
    params = row.get("best_params") or {}
    if not toks or not params:
        return []
    topo = Topology(list(toks))
    nl, _, rep, _ = bias.insert_bias(topo, sweep=True, inductor_q=12)
    if rep.get("skipped"):
        return []
    sizable, _ = S.classify_params(nl)
    rng = S.kind_ranges(spec)
    bad = []
    for name, kind in sizable.items():
        if name not in params or kind not in rng:
            continue
        try:
            v = float(params[name])
        except (TypeError, ValueError):
            continue
        lo, hi = rng[kind][0], rng[kind][1]
        if v < lo * (1 - 1e-9) or v > hi * (1 + 1e-9):
            bad.append((name, kind, v, lo, hi))
    return bad


def judge(row):
    """Re-judge one stored feasible design under tier-1 and tier-2 gating."""
    name = row["spec"]
    t1 = S._spec_for_sizing(name, nf_gate=False)
    t2 = S._spec_for_sizing(name, nf_gate=True)
    body, topo = _body_for(row)
    if body is None:
        return None
    params = row.get("best_params")
    m = S.eval_metrics(body, params, t2)          # measures NF too
    if m is None:
        return None
    if topo is not None and not S.replay_ok(topo, params, t1, row.get("metrics") or {}):
        return {"row": row, "replay": False}
    f1, v1 = t1.feasible(m)
    f2, v2 = t2.feasible(m)
    lim = (t2.constraints.get("nf_db") or {}).get("max")
    nf = m.get("nf_db")
    stab, _why = E.stability_verdict(m)
    return {"row": row, "replay": True, "metrics": m, "tier1": f1, "tier2": f2,
            "in_box": not out_of_box(row, t1),
            "viol1": dict(v1), "viol2": dict(v2), "nf": nf, "nf_limit": lim,
            "nf_excess": (nf - lim) if (nf is not None and lim is not None) else None,
            "stab": stab}


def _label(row):
    p = row.get("provenance") or {}
    return (p.get("archetype") or p.get("ref_deck")
            or os.path.basename(p.get("token_file", "") or "")
            or p.get("source_arm") or str(row.get("wl_hash"))[:10])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", action="store_true", help="markdown table")
    a = ap.parse_args()
    rows = feasible_designs()
    res = [r for r in (judge(x) for x in rows) if r]

    hdr = ("| spec | design | S11* | S21 | Idd | NF | NF target | excess | "
           "tier-1 | tier-2 | K_min | in-box |")
    sep = "|---|---|---|---|---|---|---|---|---|---|---|---|"
    if a.md:
        print(hdr)
        print(sep)
    else:
        print(f"{'spec':<13} {'design':<24} {'S11*':>7} {'S21':>6} {'Idd':>6} "
              f"{'NF':>6} {'tgt':>5} {'excess':>7} {'t1':>4} {'t2':>4} {'K_min':>7} {'box':>4}")
    n_t1 = n_t2 = 0
    for r in res:
        row, m = r["row"], r.get("metrics")
        if not r["replay"]:
            print(f"{row['spec']:<13} {_label(row):<24}  QUARANTINED (replay failed)")
            continue
        wide = row["spec"].startswith(("dhruva", "wideband"))
        s11 = m.get("s11_max_db") if wide else m.get("s11_db")
        n_t1 += int(r["tier1"])
        n_t2 += int(r["tier2"])
        exc = r["nf_excess"]
        vals = (row["spec"], _label(row), s11, m["s21_db"], m.get("idd_ma") or 0,
                r["nf"], r["nf_limit"], exc,
                "PASS" if r["tier1"] else "fail", "PASS" if r["tier2"] else "FAIL",
                m.get("k_min"), "in" if r["in_box"] else "OUT")
        if a.md:
            print("| {} | `{}` | {:.1f} | {:.1f} | {:.2f} | **{:.2f}** | {} | "
                  "{:+.2f} | {} | **{}** | {:.3g} | {} |".format(*vals))
        else:
            print("{:<13} {:<24} {:>7.1f} {:>6.1f} {:>6.2f} {:>6.2f} {:>5} "
                  "{:>+7.2f} {:>4} {:>4} {:>7.3g} {:>4}".format(*vals))
    print(f"\n{len(res)} distinct feasible designs re-judged: "
          f"tier-1 still {n_t1}/{len(res)}, tier-2 (NF gated) {n_t2}/{len(res)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

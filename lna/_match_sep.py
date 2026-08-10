"""Which input-port features actually separate designs that MATCH from designs
that do not?  (WP-MATCH step 2, FINDINGS 29)

Empirical, not analytic. Every stored design is reduced to its best measured
`s11_max_db` (or `s11_db` on wideband-sdr), labelled MATCHED at <= -10 dB, and
each structural feature from `_match_struct.analyze` is scored by how it splits
the two classes. Nothing here is used to size or to author a topology -- it is a
contingency table over labels the simulator produced.

The confound that matters is provenance: archetype-derived designs are both the
most matched and the most degenerated. So every table is also reported split by
provenance class, and the headline separation is the one that survives inside a
single class.

    python lna/_match_sep.py --out lna/out/_m/sep.json
"""
import argparse
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _match_struct as MS                              # noqa: E402
from topology import Topology                           # noqa: E402

GEN_ARMS = {"campaign-G", "trackb-p5v5-control", "trackb-p5v6", "p5v3-baseline",
            "p5v3-gen", "p5v7-v1", "p5v8-v1", "ctrl-v1", "ctrl-v1s", "cur-v1",
            "cur-v2", "g4-generated", "rung1-live", "sigma-probe"}
ARCH_ARMS = {"campaign-T", "anchor", "tapped", "cg", "dhruva-label", "dhruva-4band",
             "dhruva-close", "broaden-label", "blind"}
SEARCH_ARMS = {"evolve-evolve", "evolve-random", "nf-moves", "nf-campaign",
               "d3-lownoise", "campaign-R", "nf-budget-probe"}
CORPUS_ARMS = {"corpus", "external-ingest"}


def pclass(r):
    p = r.get("provenance") or {}
    arm = p.get("source_arm")
    if arm in CORPUS_ARMS:
        return "corpus/ext"
    if p.get("archetype") or arm in ARCH_ARMS:
        return "archetype"
    if p.get("token_file") or arm in GEN_ARMS:
        return "generator"
    if p.get("parent_wl_hash") or arm in SEARCH_ARMS:
        return "search"
    return "other"


FEATURES = [
    ("port_src",    lambda a: a["port_src"]),
    ("gate_only",   lambda a: a["port_gate"] and not a["port_src"]),
    ("degen_any",   lambda a: a["n_degen"] > 0),
    ("degen_L",     lambda a: "L" in a["degen"]),
    ("fb_any",      lambda a: a["n_fb"] > 0),
    ("shunt_any",   lambda a: a["n_shunt"] > 0),
    ("series_C",    lambda a: "C" in a["series"]),
    ("series_L",    lambda a: "L" in a["series"]),
    ("gate_direct", lambda a: a["gate_direct"]),
    ("no_port_net", lambda a: a["order"] == 0),
    # the disjunction the store's own labels pick out (see FINDINGS 29): a
    # structural place for a real part to appear at the port
    ("ANY_REAL",    lambda a: (a["port_src"] or a["n_degen"] > 0
                               or a["n_fb"] > 0 or "R" in a["shunt"])),
]


def collect(spec_filter=None, min_evals=0):
    import datastore as ds
    best = {}
    for r in ds.load("topo_labels"):
        g = r.get("graph") or {}
        h = r.get("wl_hash") or g.get("wl_hash")
        if not h or not g.get("tokens"):
            continue
        if spec_filter and r.get("spec") not in spec_filter:
            continue
        if (r.get("n_evals") or 0) < min_evals:
            continue
        m = r.get("metrics") or {}
        s11 = m.get("s11_max_db")
        s11 = m.get("s11_db") if s11 is None else s11
        if s11 is None:
            continue
        cur = best.get(h)
        # keep the BEST S11 ever achieved on this graph, and the class of the
        # arm that produced that best point
        if cur is None or s11 < cur["s11"]:
            best[h] = {"s11": s11, "tokens": g["tokens"], "cls": pclass(r),
                       "spec": r.get("spec"), "nf": m.get("nf_db"),
                       "s21": m.get("s21_db"), "n_evals": r.get("n_evals")}
    out = []
    for h, d in best.items():
        try:
            a = MS.analyze(Topology(d["tokens"]))
        except Exception:
            continue
        if not a.get("ok"):
            continue
        d["a"] = a
        d["h"] = h
        out.append(d)
    return out


def table(rows, label, thresh=-10.0):
    m = [d for d in rows if d["s11"] <= thresh]
    u = [d for d in rows if d["s11"] > thresh]
    print(f"\n=== {label}   matched(S11<={thresh:g}) {len(m)}  unmatched {len(u)} ===")
    if not m or not u:
        print("   (one class empty -- no separation measurable)")
        return None
    print(f"{'feature':<14} {'P(f|match)':>11} {'P(f|no match)':>14} "
          f"{'lift':>7} {'P(match|f)':>11} {'P(match|~f)':>12}")
    res = {}
    for name, f in FEATURES:
        pm = sum(1 for d in m if f(d["a"])) / len(m)
        pu = sum(1 for d in u if f(d["a"])) / len(u)
        withf = [d for d in rows if f(d["a"])]
        without = [d for d in rows if not f(d["a"])]
        pmf = (sum(1 for d in withf if d["s11"] <= thresh) / len(withf)) if withf else None
        pmn = (sum(1 for d in without if d["s11"] <= thresh) / len(without)) if without else None
        lift = (pm / pu) if pu else float("inf")
        print(f"{name:<14} {pm:>11.3f} {pu:>14.3f} {lift:>7.2f} "
              f"{(f'{pmf:.3f}' if pmf is not None else '  -  '):>11} "
              f"{(f'{pmn:.3f}' if pmn is not None else '  -  '):>12}")
        res[name] = {"p_f_given_match": pm, "p_f_given_nomatch": pu, "lift": lift,
                     "p_match_given_f": pmf, "p_match_given_notf": pmn,
                     "n_with_f": len(withf), "n_without_f": len(without)}
    return {"label": label, "n_match": len(m), "n_unmatch": len(u), "features": res}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--thresh", type=float, default=-10.0)
    ap.add_argument("--specs", default=None, help="comma list, default all")
    a = ap.parse_args()
    specs = set(a.specs.split(",")) if a.specs else None
    rows = collect(specs)
    print(f"{len(rows)} distinct graphs with a measured S11")
    out = [table(rows, "ALL provenance", a.thresh)]
    by = defaultdict(list)
    for d in rows:
        by[d["cls"]].append(d)
    for cls in sorted(by, key=lambda c: -len(by[c])):
        out.append(table(by[cls], f"provenance = {cls}", a.thresh))

    print("\n--- best S11 ever achieved, by provenance class ---")
    print(f"{'class':<14} {'n':>5} {'min':>8} {'p10':>8} {'median':>8} "
          f"{'frac<=-10':>10}")
    for cls in sorted(by, key=lambda c: -len(by[c])):
        v = sorted(d["s11"] for d in by[cls])
        n = len(v)
        print(f"{cls:<14} {n:>5} {v[0]:>8.2f} {v[max(0, n//10)]:>8.2f} "
              f"{v[n//2]:>8.2f} {sum(1 for x in v if x <= a.thresh)/n:>10.3f}")

    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        json.dump({"tables": [t for t in out if t],
                   "rows": [{k: v for k, v in d.items() if k != "tokens"}
                            for d in rows]},
                  open(a.out, "w"), indent=1, default=str)
        print(f"\nwrote -> {a.out}")


if __name__ == "__main__":
    main()

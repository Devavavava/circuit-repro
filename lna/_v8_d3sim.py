"""Did the winners channel visibly pull generation toward the Gate-D3 structures?
(FINDINGS §26.)

The §26 question is not "is v8 novel" -- NDL answers that -- but "did feeding
back the NF-winning designs move what the model *composes* toward them?" That
needs a reference the standard novelty stick does not have: the D3 winners
themselves, plus the noise-cancelling archetype families they came from.

Builds that reference from (a) wl_hashes looked up in the label store and (b)
`templates.py` archetypes matched by name prefix, then reports each design's max
WL-cosine to it -- alongside the same number for a baseline pool, so "moved" is a
difference and not a bare number.

    python lna/_v8_d3sim.py --summaries lna/out/_v8_front_dhruval5.json \
        --pool lna/out/ft_p5v8_nb_s1337 --baseline-pool lna/out/ft_p5v7_nb_s1337 \
        --spec dhruva-l5
"""
import argparse
import glob as globmod
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import datastore as ds  # noqa: E402
from novelty import wl_cosine, wl_features  # noqa: E402
from topology import Topology, parse_arrow_file  # noqa: E402

# Gate-D3 / low-noise lineage (FINDINGS §25, §15)
D3_HASHES = ["ace8383c2fa68d03", "f578743ae13296d0", "6f0d080f91dfc642",
             "8c7592ea859e489a"]
NC_PREFIXES = ("nccgcs", "nc_cgcs", "gmb_cg", "gmbcg")


def build_reference(hashes, prefixes):
    feats = []
    seen = set()
    for r in ds.load("topo_labels"):
        h = r.get("wl_hash")
        if h in hashes and h not in seen:
            toks = (r.get("graph") or {}).get("tokens")
            if toks:
                seen.add(h)
                feats.append((f"d3:{h[:8]}", wl_features(Topology(toks))[1]))
    import templates
    for a in templates.archetypes():
        if a["name"].lower().replace("-", "_").startswith(prefixes):
            feats.append((f"nc:{a['name']}", wl_features(Topology(a["seq"]))[1]))
    return feats


def best(feat, ref):
    b, who = 0.0, None
    for name, f in ref:
        s = wl_cosine(feat, f)
        if s > b:
            b, who = s, name
    return b, who


def pool_stats(pool, ref, spec=None, limit=None):
    sims = []
    files = sorted(globmod.glob(os.path.join(pool, "seq*.txt")))[:limit]
    for f in files:
        try:
            topo = Topology(parse_arrow_file(f))
        except Exception:
            continue
        if spec is not None and not spec.structural_screen(topo)[0]:
            continue
        sims.append(best(wl_features(topo)[1], ref)[0])
    return sims


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--summaries", nargs="*", default=[])
    ap.add_argument("--pool", default=None)
    ap.add_argument("--baseline-pool", default=None)
    ap.add_argument("--spec", default=None, help="screen pools with this spec first")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    ref = build_reference(set(D3_HASHES), NC_PREFIXES)
    print(f"D3/NC reference: {len(ref)} items -> "
          f"{', '.join(n for n, _ in ref)}\n")

    spec = None
    if args.spec:
        import size
        spec = size._spec_for_sizing(args.spec, nf_gate=False)

    for s in args.summaries:
        blob = json.load(open(s, encoding="utf-8"))
        print(f"[{blob['arm']} / {blob['spec']}] front designs:")
        for r in blob["rows"]:
            topo = Topology(parse_arrow_file(os.path.join(blob["pool"], r["seq"])))
            sim, who = best(wl_features(topo)[1], ref)
            nf = (r["metrics"] or {}).get("nf_db")
            print(f"   {r['seq']:<14} viol={r['viol']:7.3f} "
                  f"NF={'  n/a' if nf is None else format(nf, '6.2f')}  "
                  f"D3/NC-sim={sim:.3f}  ({who})")
        print()

    for label, pool in (("v8 pool", args.pool), ("baseline pool", args.baseline_pool)):
        if not pool:
            continue
        sims = pool_stats(pool, ref, spec=spec, limit=args.limit)
        if not sims:
            print(f"{label:<16} (no screen-passing samples)")
            continue
        print(f"{label:<16} n={len(sims):<4} median={statistics.median(sims):.3f} "
              f"mean={statistics.fmean(sims):.3f} max={max(sims):.3f} "
              f"frac>0.70={sum(s > 0.70 for s in sims)/len(sims):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

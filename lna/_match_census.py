"""Census: input-port structure across every pool the program has (WP-MATCH).

Answers step 2 of the investigation -- "is the generator failing to EMIT match
structure, or emitting it in un-sizeable configurations?" -- by running
`_match_struct.analyze` over:

    corpus     the 41 AnalogGenie LNA circuits (row 0 of each Sequence_total)
    external   the 9 ingested external circuits (incl. the IHP GPS LNAs)
    arch       the 148 hand archetypes in templates.py
    gen:<dir>  every generator pool under lna/out/
    store:*    stored designs split by the S11 they actually ACHIEVED

    python lna/_match_census.py --out lna/out/_m/census.json
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from novelty import REPO                                # noqa: E402  (AnalogGenie/repo)

import _match_struct as MS                              # noqa: E402
from topology import Topology, parse_arrow_file         # noqa: E402

LNA_INDICES = list(range(461, 493)) + list(range(1081, 1091))


def corpus_rows():
    import numpy as np
    out = []
    for i in LNA_INDICES:
        p = os.path.join(REPO, "Dataset", str(i), f"Sequence_total{i}.npy")
        if not os.path.exists(p):
            continue
        t = Topology([str(x) for x in np.load(p, allow_pickle=True)[0]])
        out.append((f"corpus{i}", MS.analyze(t)))
    return out


def external_rows():
    import build_lna_corpus as B
    return [(f"ext:{cid}", MS.analyze(t)) for cid, t in B.external_topologies()]


def arch_rows():
    import templates as T
    return [(f"arch:{a['name']}", MS.analyze(Topology(a["seq"]))) for a in T.archetypes()]


def pool_rows(d, screen_spec=None):
    out = []
    spec = None
    if screen_spec:
        import size as S
        spec = S._spec_for_sizing(screen_spec)
    for p in sorted(glob.glob(os.path.join(d, "seq*.txt"))):
        try:
            t = Topology(parse_arrow_file(p))
        except Exception:
            continue
        if not t.valid:
            continue
        if spec is not None and not spec.structural_screen(t)[0]:
            continue
        out.append((os.path.basename(p)[:-4], MS.analyze(t)))
    return out


def store_rows(spec_filter=None):
    """Stored designs with tokens AND a measured S11, keyed by graph (best S11)."""
    import datastore as ds
    best = {}
    for r in ds.load("topo_labels"):
        g = r.get("graph") or {}
        h = r.get("wl_hash") or g.get("wl_hash")
        if not h or not g.get("tokens"):
            continue
        if spec_filter and r.get("spec") != spec_filter:
            continue
        m = r.get("metrics") or {}
        s11 = m.get("s11_max_db")
        s11 = m.get("s11_db") if s11 is None else s11
        if s11 is None:
            continue
        if h not in best or s11 < best[h][0]:
            best[h] = (s11, g["tokens"], r.get("spec"), m)
    out = []
    for h, (s11, toks, spec, m) in best.items():
        a = MS.analyze(Topology(toks))
        a["_s11"] = s11
        a["_spec"] = spec
        a["_s21"] = m.get("s21_db")
        out.append((h[:12], a))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--pools", default="ft_p5v7_nb_s1337,ft_p5v8_nb_s1337,"
                                       "ft_p5v7_wb_s1337,ft_p5v8_wb_s1337,"
                                       "ft_p5v2_nb_s1337,ft_p5v2_wb_s1337")
    ap.add_argument("--screen", default=None, help="spec name to L0-screen pools with")
    a = ap.parse_args()

    groups = []
    groups.append(("corpus (41 LNA)", corpus_rows()))
    groups.append(("external (9 ingested)", external_rows()))
    groups.append(("archetypes (templates)", arch_rows()))
    for name in a.pools.split(","):
        d = os.path.join(HERE, "out", name.strip())
        if os.path.isdir(d):
            groups.append((f"gen:{name.strip()}", pool_rows(d, a.screen)))

    st = store_rows()
    groups.append(("store: S11<=-10 (matched)", [r for r in st if r[1].get("_s11", 0) <= -10]))
    groups.append(("store: -10<S11<=-5", [r for r in st
                                          if -10 < r[1].get("_s11", 0) <= -5]))
    groups.append(("store: S11>-5 (unmatched)", [r for r in st if r[1].get("_s11", 0) > -5]))

    print(MS.HDR)
    summ = []
    for label, rows in groups:
        if not rows:
            continue
        s = MS.summarize(rows, label)
        summ.append(s)
        print(MS.line(s))

    print("\nhops from VIN to the first active gate/source (0 = wired direct):")
    print(f"{'pool':<26} " + " ".join(f"{k:>7}" for k in ("direct", "1", "2", "3", "none")))
    for s in summ:
        h = s["hops"]
        print(f"{s['label']:<26} " + " ".join(f"{h.get(k, 0):>7}" for k in
                                              ("direct", "1", "2", "3", "none")))

    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        detail = {label: {n: v for n, v in rows} for label, rows in groups}
        with open(a.out, "w") as fh:
            json.dump({"summary": summ, "detail": detail}, fh, indent=1, default=str)
        print(f"\nwrote -> {a.out}")


if __name__ == "__main__":
    main()

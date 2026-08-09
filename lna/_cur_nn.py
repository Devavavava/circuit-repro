"""Graded template-similarity of a front's designs (FINDINGS §18, mirroring §16.3).

WL-novelty is a hash test: it says a topology is not *identical* to anything in
the reference. The number that decides whether a "novel front" is real discovery
or template-perturbation is the graded one -- the WL-cosine to its nearest
reference item, and which item that is.

    python lna/_cur_nn.py lna/out/_cur_front_curv1_wifi24.json
    python lna/_cur_nn.py --files lna/out/ft_cur_nb_s1337/seq0007.txt
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from novelty import nn_similarity, ref_tag, reference, wl_features  # noqa: E402
from topology import Topology, parse_arrow_file  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("summaries", nargs="*", help="_cur_front/_ctrl_front JSON summaries")
    ap.add_argument("--files", nargs="*", default=[], help="seq*.txt token files")
    ap.add_argument("--ref", default="v2")
    args = ap.parse_args()
    _, feats, meta = reference(args.ref)
    print(f"reference {ref_tag(meta)}  ({len(feats)} items)")
    jobs = []
    for s in args.summaries:
        blob = json.load(open(s, encoding="utf-8"))
        pool = blob["pool"]
        for r in blob["rows"]:
            jobs.append((f"{blob['arm']}/{blob['spec']}/{r['seq']}",
                         os.path.join(pool, r["seq"]), r))
    for f in args.files:
        jobs.append((os.path.basename(f), f, None))
    print(f"{'design':<38} {'viol':>8} {'feas':>5}  {'NN-sim':>6}  nearest")
    for label, path, row in jobs:
        topo = Topology(parse_arrow_file(path))
        _, feat = wl_features(topo)
        nn, who = nn_similarity(feat, feats)
        v = f"{row['viol']:8.3f}" if row else " " * 8
        fe = f"{str(row['feasible']):>5}" if row else " " * 5
        print(f"{label:<38} {v} {fe}  {nn:6.3f}  {who}")


if __name__ == "__main__":
    sys.exit(main())

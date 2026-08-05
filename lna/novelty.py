"""Are conditioned samples novel, or just the seed circuit copied back?

Prefix conditioning is only worth anything if the model *continues* the seed into
new topologies rather than reproducing the circuit the prefix came from. This
compares each generated circuit against the dataset circuit that seeded it.

Fingerprint: the multiset of (device type, sorted tuple of its pins' node
labels), where a node label is its net name if it has one and INT otherwise.
That is coarser than graph isomorphism but catches "same circuit" reliably and
never reports two genuinely different circuits as identical by accident.

    python lna/novelty.py --dir lna/out/cond12
"""
import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from genie_common import REPO  # noqa: E402
from topology import PIN_RE, Topology, base_of, parse_arrow_file  # noqa: E402


def fingerprint(topo):
    node_label = {}
    for root, members in topo.nodes.items():
        named = sorted(m for m in members if m in topo.nets)
        lbl = named[0] if named else "INT"
        for m in members:
            node_label[m] = lbl
    items = []
    for d in topo.devices:
        pins = sorted(p for p in topo.pins if PIN_RE.match(p).group("dev") == d)
        labels = tuple(sorted(node_label.get(p, "?") for p in pins))
        items.append((base_of(d), labels))
    return tuple(sorted(items))


def corpus_fingerprint(index):
    import numpy as np
    p = os.path.join(REPO, "Dataset", str(index), f"Sequence_total{index}.npy")
    if not os.path.exists(p):
        return None
    arr = np.load(p, allow_pickle=True)
    return fingerprint(Topology([str(t) for t in arr[0]]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    args = ap.parse_args()

    meta_path = os.path.join(args.dir, "meta.json")
    meta = json.load(open(meta_path))["meta"] if os.path.exists(meta_path) else []
    by_file = {m["file"]: m for m in meta}

    seeds = {}
    fps, same_as_seed, scored = [], 0, 0
    lna_fps = []

    for fn in sorted(os.listdir(args.dir)):
        if not fn.startswith("seq") or not fn.endswith(".txt"):
            continue
        topo = Topology(parse_arrow_file(os.path.join(args.dir, fn)))
        fp = fingerprint(topo)
        fps.append(fp)
        s, _ = topo.lna_score()
        if s == 5:
            lna_fps.append(fp)
        src = by_file.get(fn, {}).get("source_circuit")
        if src is None:
            continue
        scored += 1
        if src not in seeds:
            seeds[src] = corpus_fingerprint(src)
        if seeds[src] is not None and fp == seeds[src]:
            same_as_seed += 1

    n = len(fps)
    uniq = len(set(fps))
    print(f"generated circuits      : {n}")
    print(f"distinct topologies     : {uniq} ({100.0*uniq/max(n,1):.1f}%)")
    dupes = Counter(fps)
    top = dupes.most_common(1)
    if top and top[0][1] > 1:
        print(f"most repeated topology  : {top[0][1]} copies")
    if scored:
        print(f"identical to their seed : {same_as_seed}/{scored} "
              f"({100.0*same_as_seed/scored:.1f}%)")
    if lna_fps:
        print(f"score-5 circuits        : {len(lna_fps)}, "
              f"{len(set(lna_fps))} distinct ({100.0*len(set(lna_fps))/len(lna_fps):.1f}%)")
        seed_set = {v for v in seeds.values() if v is not None}
        novel = sum(1 for f in set(lna_fps) if f not in seed_set)
        print(f"  of those distinct, not any seed circuit: {novel}/{len(set(lna_fps))}")


if __name__ == "__main__":
    main()

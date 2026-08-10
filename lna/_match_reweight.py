"""Emit a re-weighting file for the P5 mix: oversample the EXISTING traversals
whose input port reaches a transistor source (WP-MATCH step 3, FINDINGS 29).

`_match_mix.py` measured that P5-v7's training rows carry that motif at 21.8%,
and that the 148-archetype channel -- 31% of the mix -- carries it at 1.35%,
diluting the real corpus's 36.5%. The generator then samples it at 0.88x its
training rate. This script builds the minimal intervention the rules allow:
**more copies of rows that already exist**, emitted through the existing
`--winners-file` channel so `finetune.build_dataset_p5` needs no change and no
new structure is authored anywhere.

Sources of the oversampled rows, all already in the program:
    * the dataset LNAs (train split only -- the val set must stay byte-identical
      so the best-val checkpoint policy early-stops on the same criterion)
    * the ingested external circuits
    * the `templates.py` archetypes in the emission being trained on

    python lna/_match_reweight.py --base lna/out/winners_train.pre_dhruva.json \
        --target-rate 0.35 --out lna/out/_m/winners_train.srcmix.json
"""
import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _match_struct as MS                              # noqa: E402
from novelty import REPO                                # noqa: E402
from topology import Topology                           # noqa: E402

LNA_INDICES = list(range(461, 493)) + list(range(1081, 1091))
HOLDOUT = {464, 471, 478, 485, 1083, 1089}              # == finetune.HOLDOUT


def _cls(topo):
    """Same nb/wb rule finetune._corpus_class uses: inductor content."""
    return "nb" if topo.n_inductors else "wb"


def pool_rows(templates_file):
    """[(name, seq, cls)] over every EXISTING traversal carrying the motif."""
    import numpy as np
    out = []
    for i in LNA_INDICES:
        p = os.path.join(REPO, "Dataset", str(i), f"Sequence_total{i}.npy")
        if not os.path.exists(p) or i in HOLDOUT:
            continue
        arr = np.load(p, allow_pickle=True)
        t0 = Topology([str(t) for t in arr[0]])
        if not MS.analyze(t0).get("port_src"):
            continue
        for row in arr:
            toks = [str(t) for t in row]
            out.append((f"corpus{i}", toks, _cls(t0)))
    try:
        import build_lna_corpus as B
        for cid, seqs in B.external_sequences():
            t0 = Topology(seqs[0])
            if not MS.analyze(t0).get("port_src"):
                continue
            for row in seqs:
                out.append((f"ext:{cid}", list(row), _cls(t0)))
    except Exception as e:                                # noqa: BLE001
        print(f"  [warn] external channel unavailable: {e}")
    if templates_file and os.path.exists(templates_file):
        data = json.load(open(templates_file, encoding="utf-8"))
        keep = {}
        for r in data["rows"]:
            k = r["arch"]
            if k not in keep:
                keep[k] = MS.analyze(Topology(r["seq"])).get("port_src", False)
            if keep[k] and r.get("arch", 0) % 8 != 0:     # respect the val holdout
                out.append((f"arch{k}", r["seq"], r["cls"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.path.join(HERE, "out",
                                                   "winners_train.pre_dhruva.json"),
                    help="the winners emission this arm keeps unchanged underneath")
    ap.add_argument("--templates-file",
                    default=os.path.join(HERE, "out", "templates_train.pre_dhruva.json"))
    ap.add_argument("--target-rate", type=float, default=0.35,
                    help="motif share of the WHOLE p5 mix to aim for")
    ap.add_argument("--base-rows", type=int, default=7207,
                    help="rows in the unmodified mix (from _match_mix.py)")
    ap.add_argument("--base-src", type=int, default=1568,
                    help="motif rows in the unmodified mix (from _match_mix.py)")
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    pool = pool_rows(a.templates_file)
    if not pool:
        raise SystemExit("no motif-bearing traversals found")
    r = a.target_rate
    add = int(round((r * a.base_rows - a.base_src) / (1.0 - r)))
    add = max(add, 0)
    rng = random.Random(a.seed)
    base = json.load(open(a.base, encoding="utf-8"))
    rows = list(base["rows"])
    n_base = len(rows)
    idx = list(range(len(pool)))
    rng.shuffle(idx)
    for k in range(add):
        name, seq, cls = pool[idx[k % len(idx)]]
        rows.append({"seq": list(seq), "cls": cls, "src_reweight": name})
    json.dump({"rows": rows, "n_base": n_base, "n_added": add,
               "pool_traversals": len(pool),
               "pool_circuits": len({n for n, _, _ in pool}),
               "target_rate": r}, open(a.out, "w"))
    print(f"pool: {len(pool)} motif traversals from "
          f"{len({n for n, _, _ in pool})} distinct circuits")
    print(f"base {n_base} winner rows + {add} oversampled = {len(rows)} -> {a.out}")
    print(f"predicted mix motif share: "
          f"{(a.base_src + add) / (a.base_rows + add):.4f} (target {r})")


if __name__ == "__main__":
    main()

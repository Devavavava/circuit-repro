"""Does the TRAINING MIX under-weight the input structure that actually matches?
(WP-MATCH step 3, FINDINGS 29)

`_match_sep.py` measured, on the store's own simulator labels, that the one
input-port feature which predicts a band-held S11 <= -10 dB is whether the signal
arrives at a transistor SOURCE rather than a GATE. This script asks the data-side
question: at what rate does that motif appear in the *rows P5-v7 was trained on*,
and how does that compare with the rate in the samples it draws?

It reproduces `finetune.build_dataset_p5`'s row accounting exactly (same corpus
indices, same holdout, same `templates_train.json`, same optional winners file)
but never imports torch -- it only needs the sequences.

    python lna/_match_mix.py
    python lna/_match_mix.py --winners-file lna/out/winners_train.v8.json
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _match_struct as MS                              # noqa: E402
from novelty import REPO                                # noqa: E402
from topology import Topology                           # noqa: E402

LNA_INDICES = list(range(461, 493)) + list(range(1081, 1091))
HOLDOUT = {464, 471, 478, 485, 1083, 1089}              # == finetune.HOLDOUT


def motif(topo):
    a = MS.analyze(topo)
    if not a.get("ok"):
        return "n/a"
    if a["port_src"]:
        return "source_input"
    return "gate_input" if a["port_gate"] else "no_active"


def corpus_channel():
    """[(name, n_rows, motif, cls)] over the 41 dataset LNAs, train split only."""
    import numpy as np
    out = []
    for i in LNA_INDICES:
        p = os.path.join(REPO, "Dataset", str(i), f"Sequence_total{i}.npy")
        if not os.path.exists(p) or i in HOLDOUT:
            continue
        arr = np.load(p, allow_pickle=True)
        t = Topology([str(x) for x in arr[0]])
        out.append((f"corpus{i}", len(arr), motif(t)))
    return out


def external_channel():
    import build_lna_corpus as B
    out = []
    for cid, seqs in B.external_sequences():
        t = Topology(seqs[0])
        out.append((f"ext:{cid}", len(seqs), motif(t)))
    return out


def json_channel(path, holdout_every_8th=False):
    """templates_train.json / winners_train.json -- one row per augmented path."""
    data = json.load(open(path, encoding="utf-8"))
    agg = defaultdict(lambda: [0, None])
    for i, r in enumerate(data["rows"]):
        if holdout_every_8th and r.get("arch", 0) % 8 == 0:
            continue
        key = r["arch"] if "arch" in r else (r.get("name") or r.get("wl_hash") or i)
        if agg[key][1] is None:
            agg[key][1] = motif(Topology(r["seq"]))
        agg[key][0] += 1
    return [(str(k), v[0], v[1]) for k, v in agg.items()]


def report(channels, label):
    print(f"\n=== training mix: {label} ===")
    print(f"{'channel':<22} {'circuits':>9} {'rows':>7} {'row share':>10} "
          f"{'src circuits':>13} {'SRC ROW SHARE':>14}")
    tot_rows = sum(sum(n for _, n, _ in ch) for _, ch in channels)
    grand_src = 0
    for name, ch in channels:
        rows = sum(n for _, n, _ in ch)
        src_rows = sum(n for _, n, m in ch if m == "source_input")
        src_c = sum(1 for _, _, m in ch if m == "source_input")
        grand_src += src_rows
        print(f"{name:<22} {len(ch):>9} {rows:>7} {rows/max(tot_rows,1):>10.3f} "
              f"{src_c:>6}/{len(ch):<6} {src_rows/max(rows,1):>14.4f}")
    print(f"{'TOTAL':<22} {sum(len(c) for _, c in channels):>9} {tot_rows:>7} "
          f"{1.0:>10.3f} {'':>13} {grand_src/max(tot_rows,1):>14.4f}")
    return grand_src / max(tot_rows, 1)


def pool_rate(d):
    import glob
    from topology import parse_arrow_file
    c = Counter()
    for p in sorted(glob.glob(os.path.join(d, "seq*.txt"))):
        try:
            t = Topology(parse_arrow_file(p))
        except Exception:
            continue
        if not t.valid:
            continue
        c[motif(t)] += 1
    n = sum(c.values()) or 1
    return c, c["source_input"] / n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--templates-file", default=os.path.join(HERE, "out",
                                                             "templates_train.json"))
    ap.add_argument("--winners-file", default=None)
    ap.add_argument("--pools", default="ft_p5v7_nb_s1337,ft_p5v8_nb_s1337,"
                                       "ft_p5v7_wb_s1337,ft_p5v8_wb_s1337")
    a = ap.parse_args()

    ch = [("corpus (35 train)", corpus_channel()),
          ("external (9)", external_channel()),
          ("archetypes", json_channel(a.templates_file, holdout_every_8th=True))]
    if a.winners_file:
        ch.append(("winners", json_channel(a.winners_file)))
    train_rate = report(ch, os.path.basename(a.templates_file)
                        + (f" + {os.path.basename(a.winners_file)}" if a.winners_file else ""))

    print("\n=== sampled pools ===")
    print(f"{'pool':<26} {'n':>5} {'source_input':>13} {'gate_input':>11} "
          f"{'vs train rate':>14}")
    for name in a.pools.split(","):
        d = os.path.join(HERE, "out", name.strip())
        if not os.path.isdir(d):
            continue
        c, r = pool_rate(d)
        n = sum(c.values())
        print(f"{name.strip():<26} {n:>5} {r:>13.4f} {c['gate_input']/max(n,1):>11.4f} "
              f"{r/max(train_rate,1e-9):>13.2f}x")


if __name__ == "__main__":
    main()

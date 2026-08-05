"""Sample topologies from AnalogGenie, optionally conditioned on an LNA prefix.

Upstream always seeds generation with the single token VSS (id 1003), because
every training sequence is an Eulerian DFS path that starts at VSS. That makes
sampling unconditional: you get whatever the training distribution favours, and
LNAs are only ~1.2% of the corpus.

This script adds prefix conditioning. Because the model is a plain autoregressive
LM over the same token stream, seeding it with the opening tokens of a real LNA
traversal costs nothing extra and biases continuation toward that region of the
distribution -- no retraining involved.

    # upstream behaviour, batched and early-stopped
    python lna/generate.py --n 32 --batch 16 --out out/uncond

    # conditioned on the first 12 tokens of real LNA traversals
    python lna/generate.py --n 32 --batch 16 --prefix lna --prefix-len 12 \
        --out out/cond
"""
import argparse
import json
import os
import random
import sys
import time

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from genie_common import (REPO, STOI, TRUNCATE_ID, VSS_ID, decode,  # noqa: E402
                          first_circuit, generate_batch, load_model)

LNA_INDICES = list(range(461, 493)) + list(range(1081, 1091))


def lna_prefixes(prefix_len, count, seed=0):
    """Opening tokens of real LNA Eulerian traversals from the corpus."""
    import numpy as np
    rng = random.Random(seed)
    pool = []
    for i in LNA_INDICES:
        p = os.path.join(REPO, "Dataset", str(i), f"Sequence_total{i}.npy")
        if not os.path.exists(p):
            continue
        arr = np.load(p, allow_pickle=True)
        for row in arr[:20]:
            toks = [str(t) for t in row]
            toks = toks[:toks.index("TRUNCATE")] if "TRUNCATE" in toks else toks
            if len(toks) > prefix_len:
                pool.append((i, toks[:prefix_len]))
    if not pool:
        raise SystemExit(
            "No LNA sequences found. Run: python lna/build_lna_corpus.py --stage all")
    rng.shuffle(pool)
    return [pool[k % len(pool)] for k in range(count)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=32, help="sequences to generate")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--prefix", choices=["vss", "lna"], default="vss")
    ap.add_argument("--prefix-len", type=int, default=12)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    torch.manual_seed(args.seed)

    model = load_model(args.device)
    print(f"prefix mode : {args.prefix}"
          + (f" (len {args.prefix_len})" if args.prefix == "lna" else ""))
    print(f"generating  : {args.n} sequences, batch {args.batch}, "
          f"temp {args.temperature}, cap {args.max_tokens}")

    if args.prefix == "lna":
        prefixes = lna_prefixes(args.prefix_len, args.n, seed=args.seed)
    else:
        prefixes = [(None, ["VSS"])] * args.n

    meta, produced = [], 0
    t_start = time.time()

    for start in range(0, args.n, args.batch):
        chunk = prefixes[start:start + args.batch]
        # rows need only share a prefix *length*, so distinct seeds batch together
        srcs = [src for src, _ in chunk]
        ids_batch = [[STOI[t] for t in toks] for _, toks in chunk]

        t0 = time.time()
        out, steps = generate_batch(model, ids_batch,
                                    max_new_tokens=args.max_tokens,
                                    temperature=args.temperature,
                                    device=args.device)
        wall = time.time() - t0
        for row, src, ids in zip(out, srcs, ids_batch):
            ids_row = row.tolist()
            circ = first_circuit(ids_row)
            path = os.path.join(args.out, f"seq{produced:04d}.txt")
            open(path, "w").write(decode(ids_row))
            meta.append({"file": os.path.basename(path),
                         "source_circuit": src,
                         "prefix_len": len(ids),
                         "circuit_tokens": len(circ),
                         "terminated": len(circ) < len(ids_row),
                         "steps": steps})
            produced += 1
        print(f"  [{produced}/{args.n}] {len(srcs)} seqs, {steps} steps, "
              f"{wall:.1f}s ({steps*len(srcs)/wall:.1f} tok/s)", flush=True)

    total = time.time() - t_start
    term = sum(1 for m in meta if m["terminated"])
    lens = [m["circuit_tokens"] for m in meta if m["terminated"]]
    print(f"\ntotal {total:.1f}s for {produced} sequences "
          f"({total/max(produced,1):.1f}s each)")
    print(f"terminated with TRUNCATE: {term}/{produced}")
    if lens:
        print(f"circuit length (terminated): min={min(lens)} max={max(lens)} "
              f"mean={sum(lens)/len(lens):.0f}")

    json.dump({"args": vars(args), "wall_s": total, "meta": meta},
              open(os.path.join(args.out, "meta.json"), "w"), indent=2)


if __name__ == "__main__":
    main()

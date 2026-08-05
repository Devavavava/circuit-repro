"""Profile AnalogGenie sampling: where the time goes, and what batching buys.

Upstream samples one sequence at a time for a fixed 1024 steps. Two things make
that expensive:

  1. No KV cache. Step t re-runs attention over the whole t-token prefix, so the
     cost of a full sequence grows as O(T^2), not O(T).
  2. No early stop. A circuit that terminates at TRUNCATE after ~200 tokens still
     pays for all 1024 steps.

Batching is the cheap fix -- the model is only 11.8M parameters, so a single
sequence badly under-uses the CPU's matmul throughput.

    python lna/profile_generate.py --steps 64 --batches 1,4,16
"""
import argparse
import os
import sys
import time

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from genie_common import (VSS_ID, generate_batch, load_model)  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=64,
                    help="tokens to generate per trial (kept small; cost is quadratic)")
    ap.add_argument("--batches", default="1,4,16")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--threads", type=int, default=0)
    args = ap.parse_args()

    if args.threads:
        torch.set_num_threads(args.threads)

    print(f"device      : {args.device}")
    print(f"torch        : {torch.__version__}")
    print(f"threads      : {torch.get_num_threads()}")

    t0 = time.time()
    model = load_model(args.device)
    load_s = time.time() - t0
    nparam = sum(p.numel() for p in model.parameters())
    print(f"load         : {load_s:.1f}s   params: {nparam/1e6:.2f}M")
    print()

    batches = [int(b) for b in args.batches.split(",")]
    print(f"{'batch':>6} {'wall(s)':>9} {'tok/s':>9} {'s/seq':>9} {'speedup':>9}")
    print("-" * 48)

    baseline = None
    for b in batches:
        torch.manual_seed(1337)
        t0 = time.time()
        out, steps = generate_batch(model, [VSS_ID], batch=b,
                                    max_new_tokens=args.steps,
                                    device=args.device)
        wall = time.time() - t0
        total_tokens = steps * b
        per_seq = wall / b
        if baseline is None:
            baseline = per_seq
        print(f"{b:>6} {wall:>9.2f} {total_tokens/wall:>9.1f} "
              f"{per_seq:>9.3f} {baseline/per_seq:>8.2f}x")

    print()
    print("Note: cost per sequence grows ~quadratically in length (no KV cache),")
    print(f"so a full 1024-token run costs roughly (1024/{args.steps})^2 = "
          f"{(1024/args.steps)**2:.0f}x the per-trial time above.")


if __name__ == "__main__":
    main()

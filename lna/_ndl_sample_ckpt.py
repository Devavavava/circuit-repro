"""Sample a generator pool from an ARBITRARY checkpoint file, without touching
the shared `lna/out/ft_p5_v2.pth` path.

`finetune.sample` resolves its checkpoint through the module-global
`finetune.ckpt_path`, which hardcodes `ft_p5{_v2}.pth`. Recovering a historical
pool (P5-v2's, whose sample dir was overwritten when the same dir name was
reused for P5-v5) would otherwise mean copying a 198 MB checkpoint over that
shared path -- unacceptable with other agents live in the worktree. Rebinding
the function is equivalent and mutates nothing.

    <gpu py> lna/_ndl_sample_ckpt.py --ckpt lna/out/ft_p5_v2.pre_broaden.pth \
        --out lna/out/ft_p5v2_nb_s1337.v2repro --class nb --seed 1337 --n 256
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import finetune  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--arm", default="p5")
    ap.add_argument("--class", dest="cls", choices=["nb", "wb"], default="nb")
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--n", type=int, default=256)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    ckpt = os.path.abspath(args.ckpt)
    if not os.path.exists(ckpt):
        raise SystemExit(f"no such checkpoint: {ckpt}")
    finetune.ckpt_path = lambda arm, winners=False: ckpt
    print(f"[sample] checkpoint {ckpt}")
    # winners=True only selects the checkpoint path (now rebound) and the `v2`
    # output tag; the explicit --out makes the tag irrelevant.
    finetune.sample(args.arm, args.device, n=args.n, batch=args.batch,
                    max_tokens=args.max_tokens, temperature=args.temperature,
                    seed=args.seed, out=os.path.abspath(args.out),
                    cls=args.cls, winners=True)


if __name__ == "__main__":
    main()

"""WP-ATTRIB arm G3 -- sample an ARBITRARY checkpoint without touching any
shared checkpoint path.

Identical in intent to `_ndl_sample_ckpt.py`, re-stated here because that helper
predates `finetune.py`'s `--tag` flag and its rebinding lambda no longer matches
`load_ft`'s call signature (`ckpt_path(arm, winners, tag=tag)`), and it belongs
to another work package. Nothing is mutated but this process's own view of
`finetune.ckpt_path`.

    <gpu py> lna/_attrib_sample.py --ckpt lna/out/ft_p5v7_v2.pth \
        --out lna/out/_at/p5v7_s1337 --class nb --seed 1337 --n 128
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
    ap.add_argument("--n", type=int, default=128)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args()

    ckpt = os.path.abspath(a.ckpt)
    if not os.path.exists(ckpt):
        raise SystemExit(f"no such checkpoint: {ckpt}")
    finetune.ckpt_path = lambda arm, winners=False, tag=None: ckpt
    print(f"[attrib] checkpoint {ckpt}")
    finetune.sample(a.arm, a.device, n=a.n, batch=a.batch,
                    max_tokens=a.max_tokens, temperature=a.temperature,
                    seed=a.seed, out=os.path.abspath(a.out), cls=a.cls)


if __name__ == "__main__":
    main()

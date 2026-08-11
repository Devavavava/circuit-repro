#!/bin/bash
# WP-OUTCOME (plans2/11) -- two arms of P5-v7's STAGE B with exactly one
# variable changed: the conditioned channel that `_out_emit.py` wrote.
#
#   OUT-C  lna/out/outcome_train.json        bins as measured
#   OUT-S  lna/out/outcome_train.shuf.json   the same rows, bin vectors permuted
#
# Everything else is v7's stage B byte for byte -- expanded corpus, 118-arch
# templates_train.pre_dhruva.json, winners_train.pre_dhruva.json, warm start
# ft_p5v7.pth (v7's own stage A), 40 epochs, lr 3e-5, batch 32, seed 1337,
# best-val ships, conditioned rows TRAIN-only so the 736-row val set and the
# early-stop criterion are the baseline's. Private stems ft_p5out / ft_p5outs.
set -e
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
PY=/opt/miniconda/envs/gpu/bin/python
TB=lna/out/templates_train.pre_dhruva.json
W=lna/out/winners_train.pre_dhruva.json
O=lna/out/_o

train_arm () {   # $1 tag   $2 outcome-file
  echo "=== WP-OUTCOME train $1 (outcome file $2) ==="
  $PY lna/finetune.py --arm p5 --do train --device cuda --seed 1337 --epochs 40 \
      --external-corpus --templates-file $TB --winners --winners-file $W \
      --outcome --outcome-file $2 --tag $1 --warm-from lna/out/ft_p5v7.pth
}

sample_arm () { # $1 tag  $2 class  $3 seed  $4 met|uncond
  if [ "$4" = "met" ]; then B="--outcome-bins MET,MET,MET,MET"; else B=""; fi
  echo "=== sample $1 $2 $4 256 @ seed $3 ==="
  $PY lna/finetune.py --arm p5 --do sample --device cuda --seed $3 --n 256 \
      --class $2 --winners --outcome $B --tag $1 \
      --out $O/ft_$1_$2_$4_s$3
}

train_arm p5out  lna/out/outcome_train.json
train_arm p5outs lna/out/outcome_train.shuf.json

for T in p5out p5outs; do
  for C in nb wb; do
    sample_arm $T $C 1337 met
    sample_arm $T $C 1337 uncond
  done
done
# sampling-noise replicate on the primary channel of both arms
sample_arm p5out  nb 2338 met
sample_arm p5outs nb 2338 met
echo "=== WP-OUTCOME TRAIN+SAMPLE DONE ==="

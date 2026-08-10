#!/bin/bash
# P5-v8 (FINDINGS §26) -- Stage-3 Loop B expert iteration on top of the adopted
# P5-v7: v7's exact mix (expanded 50-circuit corpus + 118-arch templates +
# <OTHER> replay) with a FRESH multi-spec winners emission, warm-started from
# ft_p5v7_v2.pth. One stage, exactly as P5-v2 -> P5-v3 was.
#
# Hyperparameters identical to v7/P5-v3: 40 epochs, lr 3e-5, batch 32, seed
# 1337, best-val ships. Private checkpoint stem ft_p5v8_v2.pth -- no shared
# .pth is touched.
set -e
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
PY=/opt/miniconda/envs/gpu/bin/python
$PY lna/finetune.py --arm p5 --do train --device cuda --seed 1337 --epochs 40 \
    --external-corpus --templates-file lna/out/templates_train.pre_dhruva.json \
    --winners --winners-file lna/out/winners_train.v8.json --tag p5v8 \
    --warm-from lna/out/ft_p5v7_v2.pth
for C in nb wb; do
  echo "=== sample p5v8 $C 256 @ seed 1337 ==="
  $PY lna/finetune.py --arm p5 --do sample --device cuda --seed 1337 --n 256 \
      --class $C --winners --tag p5v8 --out lna/out/ft_p5v8_${C}_s1337
done
echo "=== V8 TRAIN+SAMPLE DONE ==="

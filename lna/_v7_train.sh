#!/bin/bash
# P5-v7 (FINDINGS §21): the adopted P5-v3 recipe with EXACTLY ONE variable
# changed -- the corpus grows 41 -> 50 circuits (§19's ingested external set).
# The template scaffolding is KEPT (§18: it is what crowds out corpus
# memorization) and there is no curriculum schedule.
#
#   stage A  Pretrain.pth -> expanded corpus + 92-arch templates + replay
#            (P5-v3's own stage-A emission, templates_train.pre_broaden.json)
#   stage B  warm stage A -> expanded corpus + 118-arch templates + 965 winners
#            (P5-v3's own stage-B emissions, *.pre_dhruva.json)
#
# Hyperparameters byte-identical to P5-v3: 40 epochs, lr 3e-5, batch 32,
# seed 1337, best-val ships. Checkpoints ft_p5v7.pth / ft_p5v7_v2.pth -- a
# private stem, so no shared .pth is ever overwritten.
set -e
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
PY=/opt/miniconda/envs/gpu/bin/python
TA=lna/out/templates_train.pre_broaden.json
TB=lna/out/templates_train.pre_dhruva.json
W=lna/out/winners_train.pre_dhruva.json

echo "=== P5-v7 stage A: expanded corpus + 92-arch templates ==="
$PY lna/finetune.py --arm p5 --do train --device cuda --seed 1337 --epochs 40 \
    --external-corpus --templates-file $TA --tag p5v7

echo "=== P5-v7 stage B: + 118-arch templates + winners ==="
$PY lna/finetune.py --arm p5 --do train --device cuda --seed 1337 --epochs 40 \
    --external-corpus --templates-file $TB --winners --winners-file $W --tag p5v7

for C in nb wb; do
  echo "=== sample p5v7 $C 256 @ seed 1337 ==="
  $PY lna/finetune.py --arm p5 --do sample --device cuda --seed 1337 --n 256 \
      --class $C --winners --tag p5v7 --out lna/out/ft_p5v7_${C}_s1337
done
echo "=== V7 TRAIN+SAMPLE DONE ==="

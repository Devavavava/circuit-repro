#!/bin/bash
# Curriculum arms (FINDINGS §18). Phase 1 is a SHIPPED checkpoint of the
# scaffolded lineage (no GPU spent re-training it, and byte-identical to the
# baseline by construction); phase 2 is ctrl-v1's stage-B dataset exactly
# (corpus + winners_train.pre_dhruva.json + <OTHER> replay, ZERO templates).
#
#   cur-v1  early switch: warm ft_p5.pth              (P5-v3's stage-A base)
#   cur-v2  late  switch: warm ft_p5_v2.pre_dhruva.pth (the adopted P5-v3)
#
# Hyperparameters identical to the §16 arms: 40 epochs, lr 3e-5, batch 32,
# seed 1337, best-val checkpoint ships.
set -e
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
PY=/opt/miniconda/envs/gpu/bin/python
W=lna/out/winners_train.pre_dhruva.json

echo "=== cur-v1: phase 2 (template-free), warm from ft_p5.pth ==="
$PY lna/finetune.py --arm p5 --do train --device cuda --seed 1337 --epochs 40 \
    --no-templates --winners --tag cur --winners-file $W \
    --warm-from lna/out/ft_p5.pth

echo "=== cur-v2: phase 2 (template-free), warm from P5-v3 ==="
$PY lna/finetune.py --arm p5 --do train --device cuda --seed 1337 --epochs 40 \
    --no-templates --winners --tag cur2 --winners-file $W \
    --warm-from lna/out/ft_p5_v2.pre_dhruva.pth

for T in cur cur2; do
  for C in nb wb; do
    echo "=== sample $T $C 256 @ seed 1337 ==="
    $PY lna/finetune.py --arm p5 --do sample --device cuda --seed 1337 --n 256 \
        --class $C --winners --tag $T --out lna/out/ft_${T}_${C}_s1337
  done
done
echo "=== CUR TRAIN+SAMPLE DONE ==="

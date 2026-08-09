#!/bin/bash
# Curriculum TAIL-LENGTH sweep (FINDINGS §18). The best-val policy ships epoch 0
# on this dataset (val rises monotonically from epoch 1), so "how long is the
# de-scaffolding tail" is not a question best-val can answer -- `--ckpt-policy
# final` ships epoch K-1 instead. Same seed each run, so the K=2 run's first two
# epochs are the K=4 run's first two.
#
#   $1 = warm-start checkpoint   $2 = tag stem   $3.. = tail lengths
set -e
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
PY=/opt/miniconda/envs/gpu/bin/python
W=lna/out/winners_train.pre_dhruva.json
WARM=$1; STEM=$2; shift 2
for K in "$@"; do
  echo "=== ${STEM} tail K=$K (ship final epoch) ==="
  $PY lna/finetune.py --arm p5 --do train --device cuda --seed 1337 --epochs $K \
      --no-templates --winners --tag ${STEM}t${K} --winners-file $W \
      --warm-from $WARM --ckpt-policy final
  $PY lna/finetune.py --arm p5 --do sample --device cuda --seed 1337 --n 256 \
      --class nb --winners --tag ${STEM}t${K} --out lna/out/ft_${STEM}t${K}_nb_s1337
done
echo "=== TAIL SWEEP DONE ==="

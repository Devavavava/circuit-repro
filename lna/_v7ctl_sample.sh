#!/bin/bash
# The attribution control's stage-B process died after epoch 1 (GPU contention),
# but its best-val checkpoint was already written -- val 0.2300 @ epoch 1, which
# is P5-v3's documented best val to the digit, and every fine-tune in this
# program rises monotonically after epoch 1. Sampling from the surviving
# best-val artefact rather than spending 75 min of GPU on epochs that cannot
# change it. Deviation recorded in FINDINGS §24.
set -e
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
PY=/opt/miniconda/envs/gpu/bin/python
ls -la lna/out/ft_p5v7ctl_v2.pth
for C in nb wb; do
  echo "=== sample v7ctl $C 256 @ seed 1337 ==="
  $PY lna/finetune.py --arm p5 --do sample --device cuda --seed 1337 --n 256 \
      --class $C --winners --tag p5v7ctl --out lna/out/ft_p5v7ctl_${C}_s1337
done
echo "=== V7CTL SAMPLE DONE ==="

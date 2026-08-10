#!/bin/bash
# P5-v7 ATTRIBUTION CONTROL (FINDINGS §21). v7 differs from the adopted P5-v3 in
# two ways, not one: the expanded corpus AND a fresh stage-A retrain (P5-v3's
# stage A is an older `ft_p5.pth`, so its trajectory is not v7's). This arm is
# v7's recipe with `--external-corpus` REMOVED and everything else -- emissions,
# seed, epochs, warm-start structure -- byte-identical, so
#   v7 - v7ctl = the 9 ingested circuits
#   v7ctl - P5-v3 = the retrain trajectory
set -e
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
PY=/opt/miniconda/envs/gpu/bin/python
TA=lna/out/templates_train.pre_broaden.json
TB=lna/out/templates_train.pre_dhruva.json
W=lna/out/winners_train.pre_dhruva.json

echo "=== v7ctl stage A: 41-circuit corpus + 92-arch templates ==="
$PY lna/finetune.py --arm p5 --do train --device cuda --seed 1337 --epochs 40 \
    --templates-file $TA --tag p5v7ctl
echo "=== v7ctl stage B: + 118-arch templates + winners ==="
$PY lna/finetune.py --arm p5 --do train --device cuda --seed 1337 --epochs 40 \
    --templates-file $TB --winners --winners-file $W --tag p5v7ctl
for C in nb wb; do
  echo "=== sample v7ctl $C 256 @ seed 1337 ==="
  $PY lna/finetune.py --arm p5 --do sample --device cuda --seed 1337 --n 256 \
      --class $C --winners --tag p5v7ctl --out lna/out/ft_p5v7ctl_${C}_s1337
done
echo "=== V7CTL DONE ==="

#!/bin/bash
# WP-MATCH step 3: P5-v9m -- P5-v7's stage B with EXACTLY ONE variable changed,
# the winners file, which is `winners_train.pre_dhruva.json` plus 1468 rows
# OVERSAMPLED from traversals already in the mix (lna/_match_reweight.py).
# No new circuit, no new archetype: the intervention is re-weighting alone.
#
# Warm-started from v7's own stage-A checkpoint (ft_p5v7.pth), so the arm is
# v7's stage B and nothing else. Private stem ft_p5v9m -- no shared .pth is
# touched. Adoption is judged against the adopted baseline P5-v7 = nb 79 / wb 41
# under ref-v3.
set -e
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
PY=/opt/miniconda/envs/gpu/bin/python
$PY lna/finetune.py --arm p5 --do train --device cuda --seed 1337 --epochs 40 \
    --external-corpus --templates-file lna/out/templates_train.pre_dhruva.json \
    --winners --winners-file lna/out/_m/winners_train.srcmix.json --tag p5v9m \
    --warm-from lna/out/ft_p5v7.pth
for C in nb wb; do
  echo "=== sample p5v9m $C 256 @ seed 1337 ==="
  $PY lna/finetune.py --arm p5 --do sample --device cuda --seed 1337 --n 256 \
      --class $C --winners --tag p5v9m --out lna/out/_m/ft_p5v9m_${C}_s1337
done
echo "=== WP-MATCH REWEIGHT ARM DONE ==="

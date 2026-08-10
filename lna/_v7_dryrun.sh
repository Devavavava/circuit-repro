#!/bin/bash
# Dataset-composition sanity check for P5-v7: --epochs 0 builds the mix, prints
# the row counts and exits without writing a checkpoint.
set -e
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
PY=/opt/miniconda/envs/gpu/bin/python
echo "--- stage A mix (expanded corpus + 92-arch templates) ---"
$PY lna/finetune.py --arm p5 --do train --device cuda --seed 1337 --epochs 0 \
    --external-corpus --templates-file lna/out/templates_train.pre_broaden.json \
    --tag p5v7dry
echo "--- stage B mix (+ 118-arch templates + winners) ---"
$PY lna/finetune.py --arm p5 --do train --device cuda --seed 1337 --epochs 0 \
    --external-corpus --templates-file lna/out/templates_train.pre_dhruva.json \
    --winners --winners-file lna/out/winners_train.pre_dhruva.json --tag p5v7dry
echo "--- BASELINE stage B mix (P5-v3, no external) ---"
$PY lna/finetune.py --arm p5 --do train --device cuda --seed 1337 --epochs 0 \
    --templates-file lna/out/templates_train.pre_dhruva.json \
    --winners --winners-file lna/out/winners_train.pre_dhruva.json --tag p5v7dry

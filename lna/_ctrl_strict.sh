#!/bin/bash
# ctrl-v1s -- the STRICTLY template-free arm (FINDINGS §16).
# ctrl-v1 removes the template channel but keeps the winners channel, and 42% of
# the P5-v3-era winner rows (42 of 77 distinct topologies) are themselves verbatim
# templates.py archetypes that the store's sizing loop promoted. This arm drops
# them: winners_train.ctrl_strict.json = the same emission with every row whose WL
# hash is in ref-v2 removed (512 of 965 rows, 32 distinct topologies survive).
# Warm-starts from the SAME stage-A base as ctrl-v1, so the two differ only in the
# winners mix.
set -e
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
PY=/opt/miniconda/envs/gpu/bin/python
echo "=== ctrl-v1s: corpus + archetype-free winners, warm from ft_ctrl.pth ==="
cp lna/out/ft_ctrl.pth lna/out/ft_ctrls.pth
# --epochs 12 rather than 40: a documented deviation on this SECONDARY arm only.
# Every fine-tune in this program takes its best val loss at epoch 0-1 and then
# rises monotonically for the rest of the run (P5-v3: best 0.2300 @ epoch 1;
# ctrl stage A: 0.2226 @ epoch 1, then 39 epochs of worsening; ctrl-v1 stage B:
# 0.2162 @ epoch 0), and the shipped checkpoint is the best-val one -- so epochs
# 12..39 cost ~55 min of contended GPU and cannot change the artefact. ctrl-v1
# itself was run at the full 40 to keep the headline arm recipe-identical to P5.
$PY lna/finetune.py --arm p5 --do train --device cuda --seed 1337 --epochs 12 \
    --no-templates --winners --tag ctrls \
    --winners-file lna/out/winners_train.ctrl_strict.json
echo "=== sample nb 256 @ seed 1337 ==="
$PY lna/finetune.py --arm p5 --do sample --device cuda --seed 1337 --n 256 \
    --class nb --winners --tag ctrls --out lna/out/ft_ctrls_nb_s1337
echo "=== STRICT DONE ==="

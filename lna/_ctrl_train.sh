#!/bin/bash
# Template-free control arm (FINDINGS §16). Mirrors the P5-v3 lineage exactly,
# with every archetype sequence removed:
#   stage A  Pretrain.pth --> corpus + <OTHER> replay                 -> ft_ctrl.pth
#            (the template-free analogue of P5-v1 / ft_p5.pth)
#   stage B  warm-start ft_ctrl.pth --> corpus + winners + replay     -> ft_ctrl_v2.pth
#            (the template-free analogue of P5-v3, whose winners file was
#             winners_train.pre_dhruva.json -- 965 rows, the P5-v3-era emission)
# Same hyperparameters as P5: 40 epochs, lr 3e-5, batch 32, seed 1337, best-val.
set -e
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
PY=/opt/miniconda/envs/gpu/bin/python
echo "=== stage A: ctrl base (corpus only, NO templates) ==="
$PY lna/finetune.py --arm p5 --do train --device cuda --seed 1337 \
    --no-templates --tag ctrl
echo "=== stage B: ctrl-v1 (corpus + winners, NO templates) ==="
$PY lna/finetune.py --arm p5 --do train --device cuda --seed 1337 \
    --no-templates --winners --tag ctrl \
    --winners-file lna/out/winners_train.pre_dhruva.json
echo "=== sample nb 256 @ seed 1337 ==="
$PY lna/finetune.py --arm p5 --do sample --device cuda --seed 1337 --n 256 \
    --class nb --winners --tag ctrl --out lna/out/ft_ctrl_nb_s1337
echo "=== sample wb 256 @ seed 1337 ==="
$PY lna/finetune.py --arm p5 --do sample --device cuda --seed 1337 --n 256 \
    --class wb --winners --tag ctrl --out lna/out/ft_ctrl_wb_s1337
echo "=== DONE ==="

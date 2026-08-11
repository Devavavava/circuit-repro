#!/bin/bash
# WP-ATTRIB arm G3: the ADOPTED generator (P5-v7) at its adopted protocol --
# unconditioned <LNA_NB> sampling through finetune.sample -- drawn in the frozen
# protocol's canonical two-half shape (128 @ 1337 + 128 @ 2338) so it is
# measured identically to the three baseline arms.
#
# Arm G2 (upstream Pretrain.pth, prefix-12) needs no GPU: lna/out/sweep12repro{,_s2338}
# already hold exactly that draw (see _ndl_gpu_sample.sh).
set -e
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
PY=/opt/miniconda/envs/gpu/bin/python
for S in 1337 2338; do
  $PY lna/_attrib_sample.py --ckpt lna/out/ft_p5v7_v2.pth \
      --out lna/out/_at/p5v7_s${S} --class nb --seed ${S} --n 128 \
      --batch 32 --max-tokens 256 --device cuda
done
echo "WP-ATTRIB G3 SAMPLING DONE"

#!/bin/bash
# WSL GPU: recover the P5 / P0 pools whose seq*.txt were gitignored away.
#  - .v3repro POSITIVE CONTROL: pre_dhruva is claimed to be P5-v3, whose pool IS
#    on disk -> must reproduce it byte-for-byte. (Verified: 0/256 differ.)
#  - .v2repro target: pre_broaden is claimed to be P5-v2 (ref-v1 NDL@256 = 73).
#  - sweep12repro{,_s2338}: the frozen P0 prefix-12 baseline (ref-v1 NDL@256=16),
#    regenerated from the untouched upstream Pretrain.pth. Args are copied from
#    the surviving meta.json of the original run.
set -e
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
PY=/opt/miniconda/envs/gpu/bin/python

$PY lna/_ndl_sample_ckpt.py --ckpt lna/out/ft_p5_v2.pre_dhruva.pth \
    --out lna/out/ft_p5v2_nb_s1337.v3repro --class nb --seed 1337 --n 256

$PY lna/_ndl_sample_ckpt.py --ckpt lna/out/ft_p5_v2.pre_broaden.pth \
    --out lna/out/ft_p5v2_nb_s1337.v2repro --class nb --seed 1337 --n 256

for S in 1337 2338; do
  OUT=lna/out/sweep12repro
  [ "$S" = 2338 ] && OUT=lna/out/sweep12repro_s2338
  $PY lna/generate.py --n 128 --batch 32 --max-tokens 256 --temperature 0.7 \
      --prefix lna --prefix-len 12 --seed $S --device cuda --out $OUT
done

echo "DONE"

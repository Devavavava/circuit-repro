#!/bin/bash
# P5-v8 (corpus + 2 new externals; plans2/24-P5V8.md) -- the §24 "add structure
# the model has never seen" lever, run as ONE warm-start stage from the adopted
# P5-v7 (ft_p5v7_v2.pth). The corpus grew 9 -> 11 externals at main 5d55f0a
# (paper-sige-hbt-resfb, paper-nc-cc-inductorless); --external-corpus picks up
# all 11 from the manifest, whole-family into TRAIN (val stays byte-identical).
#
# ⚠ This is NOT the pre-authored lna/_v8_train.sh. That script is the §28
# winners-RECYCLE experiment (Stage-3 Loop B), which was REJECTED (nb 79->67:
# the winners channel re-injects archetype structure). Recycling winners here
# would confound the 2-new-externals lever with the rejected channel, so the
# winners channel is DELETED from this recipe. This isolates the two new
# circuits as the single new-structure variable relative to v7's training data.
#
# Recipe deltas vs v7's stage B, all forced by the contained-host artifact state
# (see plans2/24-P5V8.md "recipe drift"):
#   * ONE stage, warm from ft_p5v7_v2.pth (task: one-stage warm-start), vs v7's
#     two stages from Pretrain.pth. Every arm here takes best-val at epoch 0-1.
#   * templates: CURRENT 148-arch emission (templates_train.v8.json). v7's
#     118-arch pre_dhruva emission is gone (gitignored, GPU-era) and the
#     archetype set has since grown 118 -> 148.
#   * winners: NONE (see above).
#   * replay: DISABLED (empty Training.npy). v7's general-corpus replay is
#     unreproducible on this host; best-val ships at ep 0-1 so it is negligible
#     for the shipped artifact, and omission is comparison-neutral (<OTHER> is
#     orthogonal to LNA NDL). Conservative: any handicap only risks false-reject,
#     never false-adopt (ties -> incumbent).
#
# Hyperparameters per v7/P5-v3: 40 epochs, lr 3e-5, batch 32, seed 1337,
# best-val ships (--ckpt-policy best, the default). Private stem: --tag p5v8b,
# checkpoint ft_p5v8b_v2.pth -- no shared .pth touched.
#
# CPU ONLY: nice -n 10, OMP_NUM_THREADS=8 (leave sims elsewhere priority).
set -e
cd /home/dpatni/.claude/jobs/a8f610e5/tmp/wt-p5v8
source /home/dpatni/circuit-repro/env.sh
export OMP_NUM_THREADS=8
PY=python
TB=lna/out/templates_train.v8.json
# ft_p5v7_v2.pth is untracked and lives only in the MAIN checkout (.gitignore
# procedure); reference it by absolute path. The v8 checkpoint ft_p5v8b.pth is
# written into this worktree's lna/out/.
WARM=/home/dpatni/circuit-repro/lna/out/ft_p5v7_v2.pth

echo "=== P5-v8 warm stage: v7 + 11-external corpus + 148-arch templates (no winners, no replay) ==="
nice -n 10 $PY lna/finetune.py --arm p5 --do train --device cpu --seed 1337 --epochs 40 \
    --external-corpus --templates-file $TB --tag p5v8b \
    --warm-from $WARM

for C in nb wb; do
  echo "=== sample p5v8b $C 256 @ seed 1337 (CPU) ==="
  nice -n 10 $PY lna/finetune.py --arm p5 --do sample --device cpu --seed 1337 --n 256 \
      --class $C --tag p5v8b --out lna/out/ft_p5v8b_${C}_s1337
done
echo "=== V8 TRAIN+SAMPLE DONE ==="

#!/usr/bin/env bash
set -uo pipefail
W=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180
source /home/dpatni/circuit-repro/env.sh
export LNA_DEPS_ROOT=$W OMP_NUM_THREADS=2
cd "$W"
for k in 0 1 2 3 4 5; do
  L=kaggle/bench-null/logs/pa-$k.log
  echo "[launch-pa] $(date -Is) shard $k/6 classes=pa (resume full 3x1200)" >> "$L"
  setsid nohup python kaggle/bench_null_filter.py --classes=pa --shard=$k/6 >> "$L" 2>&1 &
  echo "[launch-pa] shard $k pid $!" >> kaggle/bench-null/logs/launch.log
done

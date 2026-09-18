#!/usr/bin/env bash
set -uo pipefail
W=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180
source /home/dpatni/circuit-repro/env.sh
export LNA_DEPS_ROOT=$W OMP_NUM_THREADS=2
cd "$W"
for k in 0 1 2 3 4 5; do
  L=kaggle/bench-null/logs/shard-$k.log
  echo "[launch] $(date -Is) shard $k/6 era-bnull-dace18ce" >> "$L"
  setsid nohup python kaggle/bench_null_filter.py --shard=$k/6 >> "$L" 2>&1 &
  echo "[launch] shard $k pid $!" >> kaggle/bench-null/logs/launch.log
done

#!/usr/bin/env bash
set -uo pipefail
W=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180
source /home/dpatni/circuit-repro/env.sh
export LNA_DEPS_ROOT=$W OMP_NUM_THREADS=1   # 1 thread/leg: 10 legs x OMP2 oversubscribed (20 threads) and stalled throughput
cd "$W"
for k in 0 1 2 3 4 5 6 7 8 9; do
  L=kaggle/bench-null/logs/pa10-$k.log
  echo "[launch-pa10] $(date -Is) shard $k/10 classes=pa (seed-resume, 10 legs)" >> "$L"
  setsid nohup python kaggle/bench_null_filter.py --classes=pa --shard=$k/10 >> "$L" 2>&1 &
  echo "[launch-pa10] shard $k pid $!" >> kaggle/bench-null/logs/launch.log
done

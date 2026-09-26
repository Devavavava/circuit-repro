#!/usr/bin/env bash
set -uo pipefail
W=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180
source /home/dpatni/circuit-repro/env.sh
export LNA_DEPS_ROOT=$W OMP_NUM_THREADS=2
cd "$W"
for k in 0 1 2; do
  L=kaggle/bench-null/logs/aux-$k.log
  echo "[launch-aux] $(date -Is) aux $k/3 era-bnull-afee00fc (Amendment 1)" >> "$L"
  setsid nohup python kaggle/bench_null_filter.py --classes=lna,balun,mixer --order=asc --shard=$k/3 >> "$L" 2>&1 &
  echo "[launch-aux] aux $k pid $!" >> kaggle/bench-null/logs/launch.log
done

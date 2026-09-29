#!/bin/bash
# usage: launch.sh [full|smoke]   -> detached, resumable bench-v2 scheduler.
# Survives the launching session (nohup + setsid). Re-running after a stop/kill
# RESUMES: every finished sizing call is cached in <run>/results.jsonl and the
# deterministic generators replay through the cache.
MODE=${1:-full}
D=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/bench-v2
RD=$D/run
[ "$MODE" = smoke ] && RD=$D/smoke/run
mkdir -p "$RD"
if [ -f "$RD/sched.pid" ] && kill -0 "$(cat "$RD/sched.pid")" 2>/dev/null; then
  echo "already running: pid $(cat "$RD/sched.pid")"; exit 1
fi
nohup setsid "$D/envrun.sh" python "$D/bv2.py" run --mode "$MODE" >> "$RD/nohup.log" 2>&1 < /dev/null &
sleep 3
echo "launched mode=$MODE pid=$(cat "$RD/sched.pid") run_dir=$RD"

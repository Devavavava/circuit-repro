#!/bin/bash
# usage: stop.sh [full|smoke] -> SIGTERM the scheduler; it kills its running workers
# (their calls are re-run on resume) and exits. Resume: launch.sh (same mode).
MODE=${1:-full}
P=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/pilot-v0
RD=$P/run
[ "$MODE" = smoke ] && RD=$P/smoke
PID=$(cat "$RD/sched.pid")
kill -TERM "$PID" && echo "sent SIGTERM to $PID"

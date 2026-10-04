#!/bin/bash
# usage: stop.sh [full|smoke] -> SIGTERM the re-check; it kills its running workers
# (their calls are re-run on resume) and exits. Resume: launch.sh.
MODE=${1:-full}
A=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/bench-v2/amend3
RD=$A/run
[ "$MODE" = smoke ] && RD=$A/smoke
[ "$MODE" = smoke-force ] && RD=$A/smoke-force
PID=$(cat "$RD/sched.pid")
kill -TERM "$PID" && echo "sent SIGTERM to $PID"

#!/bin/bash
# usage: stop.sh [full|smoke|smoke-a1|smoke-a2]  -> SIGTERM the scheduler; it kills its running
# workers (their calls are simply re-run on resume) and exits. Resume: launch.sh.
MODE=${1:-full}
D=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/bench-v2
RD=$D/run
[ "$MODE" = smoke ] && RD=$D/smoke/run
[ "$MODE" = smoke-a1 ] && RD=$D/smoke/run-amend1
[ "$MODE" = smoke-a2 ] && RD=$D/smoke/run-amend2
PID=$(cat "$RD/sched.pid")
kill -TERM "$PID" && echo "sent SIGTERM to $PID"

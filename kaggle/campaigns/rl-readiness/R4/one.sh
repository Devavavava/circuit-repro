#!/bin/bash
# one sizing job: one.sh <tag> <cell> <cand> <mode> <seed>   (raw -> /tmp/cr-7cd7ffc3-r4/raw)
D=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/rl-readiness/R4
mkdir -p /tmp/cr-7cd7ffc3-r4/raw
exec $D/envrun.sh python $D/r4_drv.py run "$@" /tmp/cr-7cd7ffc3-r4/raw

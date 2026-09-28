#!/bin/bash
# one job: one.sh <exp> <cell> <cand> <specmode> <mode> <seed>   (raw -> /tmp/cr-7cd7ffc3-s1/raw)
D=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/bench-v12-audit/S-1-stab-inloop
mkdir -p /tmp/cr-7cd7ffc3-s1/raw
exec $D/envrun.sh python $D/s1_drv.py run "$@" /tmp/cr-7cd7ffc3-s1/raw

#!/bin/bash
# one sizing job: one.sh <tag> <cell> <cand> <mode> <seed>   (raw -> /tmp/cr-7cd7ffc3-v1/raw)
D=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/rl-readiness/verifier-rl-v1
mkdir -p /tmp/cr-7cd7ffc3-v1/raw
exec $D/envrun.sh python $D/v1_drv.py run "$@" /tmp/cr-7cd7ffc3-v1/raw

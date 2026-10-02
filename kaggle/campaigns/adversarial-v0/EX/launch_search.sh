#!/bin/bash
# Detached, resumable EX search launch: launch_search.sh <n_gens> <cpu_cap_h>
EX=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/adversarial-v0/EX
T=/tmp/cr-7cd7ffc3-ex
mkdir -p $T/state
nohup setsid $EX/envrun.sh python $EX/search.py $T/raw/seeds $T/state "${1:-60}" \
    --cpu-cap-h "${2:-70}" >> $T/search.out 2>&1 < /dev/null &
echo "search pid $!"

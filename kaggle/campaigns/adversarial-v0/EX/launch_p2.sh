#!/bin/bash
# Detached, resumable EX search phase 2 (D6): launch_p2.sh <last_gen_exclusive> <cpu_cap_h>
# Process cap per $TMPDIR/ex_maxp (shared with the impact pool's ex_maxp_imp; total <= 4).
EX=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/adversarial-v0/EX
T=/tmp/cr-7cd7ffc3-ex
nohup setsid $EX/envrun.sh python $EX/search_p2.py $T/raw/seeds $T/state "${1:-90}" \
    --cpu-cap-h "${2:-76}" >> $T/search_p2.out 2>&1 < /dev/null &
echo "search_p2 pid $!"

#!/bin/bash
# all.sh <jobkind...>  -> runs the listed job kinds, at most 6 parallel sizing processes
D=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/bench-v12-audit/stability-gate
for k in "$@"; do $D/envrun.sh python $D/stab_drv.py jobs $k; done > /tmp/cr-7cd7ffc3-stab/jobs.txt
xargs -P 6 -L 1 $D/one.sh < /tmp/cr-7cd7ffc3-stab/jobs.txt

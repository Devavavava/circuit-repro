#!/bin/bash
# write the sizing job lists into /tmp/cr-7cd7ffc3-r4/jobs_<set>.txt
D=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/rl-readiness/R4
for k in "$@"; do
  $D/envrun.sh python $D/r4_drv.py jobs $k > /tmp/cr-7cd7ffc3-r4/jobs_$k.txt
  echo "$k $(wc -l < /tmp/cr-7cd7ffc3-r4/jobs_$k.txt)"
done

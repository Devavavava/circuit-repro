#!/bin/bash
# write the sizing job lists into /tmp/cr-7cd7ffc3-v1/jobs_<set>.txt
D=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/rl-readiness/verifier-rl-v1
mkdir -p /tmp/cr-7cd7ffc3-v1
for k in "$@"; do
  $D/envrun.sh python $D/v1_drv.py jobs $k > /tmp/cr-7cd7ffc3-v1/jobs_$k.txt
  echo "$k $(wc -l < /tmp/cr-7cd7ffc3-v1/jobs_$k.txt)"
done

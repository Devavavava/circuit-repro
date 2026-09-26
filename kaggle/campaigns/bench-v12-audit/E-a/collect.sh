#!/bin/bash
source /home/dpatni/.claude/jobs/7cd7ffc3/tmp/crenv.sh
cd /home/dpatni/circuit-repro/.claude/worktrees/externals-gf180
B=kaggle/campaigns/bench-v12-audit
python $B/E-a/audit_drv.py collect $1 /tmp/cr-7cd7ffc3-ab/raw $B/$1/results.json && python $B/E-a/summarize.py $1

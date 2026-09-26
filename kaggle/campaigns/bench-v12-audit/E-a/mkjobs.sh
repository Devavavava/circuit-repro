#!/bin/bash
source /home/dpatni/.claude/jobs/7cd7ffc3/tmp/crenv.sh
cd /home/dpatni/circuit-repro/.claude/worktrees/externals-gf180
D=kaggle/campaigns/bench-v12-audit/E-a/audit_drv.py
python $D jobs E-a | sed 's/^/E-a /' > /tmp/cr-7cd7ffc3-ab/jobs.txt
python $D jobs E-b | sed 's/^/E-b /' >> /tmp/cr-7cd7ffc3-ab/jobs.txt

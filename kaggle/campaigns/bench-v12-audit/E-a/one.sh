#!/bin/bash
source /home/dpatni/.claude/jobs/7cd7ffc3/tmp/crenv.sh
export TMPDIR=/tmp/cr-7cd7ffc3-ab AUDIT_ERA=cc5a836bb26fbfef4f128777945ebdae39c3fb66
cd /home/dpatni/circuit-repro/.claude/worktrees/externals-gf180
exp=$1; shift
exec python kaggle/campaigns/bench-v12-audit/E-a/audit_drv.py run $exp "$@" /tmp/cr-7cd7ffc3-ab/raw

#!/bin/bash
# one job: one.sh <exp> <cell> <cand> <specmode> <seed>   (raw -> $TMPDIR/raw)
D=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/bench-v12-audit/stability-gate
mkdir -p /tmp/cr-7cd7ffc3-stab/raw
exec $D/envrun.sh python $D/stab_drv.py run "$@" /tmp/cr-7cd7ffc3-stab/raw

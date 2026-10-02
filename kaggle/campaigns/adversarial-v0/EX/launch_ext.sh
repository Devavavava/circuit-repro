#!/bin/bash
# Detached extended-record audit pool (1 process; the search pool is capped at 3
# via $TMPDIR/ex_maxp so the total stays <= 4). Waits for a free slot first.
EX=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/adversarial-v0/EX
T=/tmp/cr-7cd7ffc3-ex
nohup setsid bash -c "until [ \$(ps aux | grep -c '[e]x_drv.py child') -le 2 ]; do sleep 5; done; \
  $EX/envrun.sh python $EX/ex_pool.py $T/ext_cmds.txt $T/ext_pool.jsonl 2 ex_maxp_ext" \
  >> $T/ext_pool.out 2>&1 < /dev/null &
echo "ext pid $!"

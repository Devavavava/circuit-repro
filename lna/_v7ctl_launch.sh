#!/bin/bash
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
rm -f lna/out/_v7ctl_train.log
setsid nohup bash lna/_v7ctl_train.sh > lna/out/_v7ctl_train.log 2>&1 < /dev/null &
echo "launched pid $!"
sleep 8
tail -3 lna/out/_v7ctl_train.log 2>/dev/null || true

#!/bin/bash
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
rm -f lna/out/_ctrl_train.log
nohup bash lna/_ctrl_train.sh > lna/out/_ctrl_train.log 2>&1 &
echo "launched pid $!"
sleep 3
tail -5 lna/out/_ctrl_train.log 2>/dev/null || true

#!/bin/bash
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
rm -f lna/out/_v8_train.log
setsid nohup bash lna/_v8_train.sh > lna/out/_v8_train.log 2>&1 < /dev/null &
echo "launched pid $!"
sleep 8
tail -4 lna/out/_v8_train.log 2>/dev/null || true

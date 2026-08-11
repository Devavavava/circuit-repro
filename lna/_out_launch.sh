#!/bin/bash
# setsid + </dev/null: a plain `nohup ... &` from `wsl -e bash` dies with the
# launching session (measured, FINDINGS 18 handover note).
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
mkdir -p lna/out/_o
rm -f lna/out/_o/train.log
setsid nohup bash lna/_out_train.sh > lna/out/_o/train.log 2>&1 < /dev/null &
echo "launched pid $!"
sleep 8
tail -5 lna/out/_o/train.log 2>/dev/null || true

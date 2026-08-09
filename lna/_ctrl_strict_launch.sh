#!/bin/bash
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
rm -f lna/out/_ctrl_strict.log
setsid nohup bash lna/_ctrl_strict.sh > lna/out/_ctrl_strict.log 2>&1 < /dev/null &
echo "launched pid $!"
sleep 5
tail -3 lna/out/_ctrl_strict.log 2>/dev/null || true

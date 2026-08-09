#!/bin/bash
# `setsid ... < /dev/null` matters: a plain `nohup ... &` from `wsl -e bash` dies
# with the launching session (measured tonight -- the first attempt produced a
# 0-byte log and no checkpoint).
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
rm -f lna/out/_cur_train.log
setsid nohup bash lna/_cur_train.sh > lna/out/_cur_train.log 2>&1 < /dev/null &
echo "launched pid $!"
sleep 8
tail -5 lna/out/_cur_train.log 2>/dev/null || true

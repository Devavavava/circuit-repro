#!/bin/bash
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
rm -f lna/out/_cur_tail.log
setsid nohup bash lna/_cur_tail.sh lna/out/ft_p5_v2.pre_dhruva.pth cur2 4 12 \
    > lna/out/_cur_tail.log 2>&1 < /dev/null &
echo "launched pid $!"
sleep 8
tail -3 lna/out/_cur_tail.log 2>/dev/null || true

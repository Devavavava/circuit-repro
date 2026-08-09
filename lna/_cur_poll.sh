#!/bin/bash
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
L=lna/out/_cur_train.log
echo "--- $(date +%H:%M:%S)  log $(stat -c %s $L 2>/dev/null) bytes ---"
tail -6 $L 2>&1
echo "--- procs ---"
ps -eo pid,etime,args | grep -E "finetune|_cur_train" | grep -v grep || true
echo "--- gpu ---"
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader || true
echo "--- ckpts ---"
ls -la --time-style=+%H:%M lna/out/ft_cur*.pth 2>/dev/null || true
exit 0

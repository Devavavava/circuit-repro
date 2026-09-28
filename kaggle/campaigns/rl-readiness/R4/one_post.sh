#!/bin/bash
# one post-analysis job: one_post.sh <raw.json>   (-> /tmp/cr-7cd7ffc3-r4/post)
D=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/rl-readiness/R4
exec $D/envrun.sh python $D/r4_post.py one "$1" /tmp/cr-7cd7ffc3-r4/post

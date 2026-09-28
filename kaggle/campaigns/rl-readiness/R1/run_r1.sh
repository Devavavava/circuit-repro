#!/bin/bash
# R1 launcher: run_r1.sh [nproc]  (resumable; appends to results.jsonl)
D=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/rl-readiness/R1
# first launch (18:06) recorded era 519bcf45+wt(bench_anchor_prep.py md5 fd928de5); the file
# then became committed ffa594a05 (md5 d5d96405) mid-run -- stamped per row from here on
R=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180
export R1_ERA="$(git -C $R rev-parse --short HEAD)+bench_anchor_prep.py md5 $(md5sum $R/kaggle/bench_anchor_prep.py | cut -c1-8)"
unset STAB_WIDE_INLOOP
exec "$D/envrun.sh" python "$D/r1_drv.py" run "${1:-6}"

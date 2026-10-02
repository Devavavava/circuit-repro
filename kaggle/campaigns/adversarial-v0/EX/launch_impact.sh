#!/bin/bash
# Detached guard-impact pool (D7): accepted-cell + training witnesses, R-a..R-e.
# Writes the command list from $T/impact_seeds.jsonl (impact.py list), then runs it.
EX=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/adversarial-v0/EX
T=/tmp/cr-7cd7ffc3-ex
mkdir -p $T/raw/impact
: > $T/impact_cmds.txt
for s in $(grep -o '"sid": "I[0-9]*"' $T/impact_seeds.jsonl | cut -d'"' -f4); do
  printf '%s\t%s\n' "$T/raw/impact/$s.json" \
    "$EX/envrun.sh python $EX/ex_drv.py seed $T/impact_seeds.jsonl $s $T/raw/impact/$s.json" \
    >> $T/impact_cmds.txt
done
[ -f $T/ex_maxp_imp ] || echo 4 > $T/ex_maxp_imp
nohup setsid $EX/envrun.sh python $EX/ex_pool.py $T/impact_cmds.txt $T/impact_pool.jsonl 4 ex_maxp_imp \
  >> $T/impact_pool.out 2>&1 < /dev/null &
echo "impact pid $!"

#!/bin/bash
# E-11 parallel campaign driver: run all (goal,arm,seed) cells with <=8 concurrent
# ngspice. Each cell is resume-safe (skips if its cell JSON exists). Arm C cells
# are generation-heavy (CPU); we cap total concurrency at 8 to honor the ngspice
# limit (arms A/B are ngspice-bound; arm C interleaves generation + ngspice).
set -u
source /home/dpatni/circuit-repro/env.sh
export PYTHONHASHSEED=0
cd /home/dpatni/.claude/jobs/a8f610e5/tmp/wt-e11/engineer

GOALS_600="G1pp G7pp GA GB GC"
GOAL_1200="G9"
ARMS="a b c"
MAXJOBS="${MAXJOBS:-8}"
LOGDIR=/home/dpatni/.claude/jobs/a8f610e5/tmp/logs_e11
mkdir -p "$LOGDIR"

throttle() {
  while [ "$(jobs -rp | wc -l)" -ge "$MAXJOBS" ]; do sleep 3; done
}

launch() {
  local g=$1 a=$2 s=$3
  throttle
  python e11_genedit.py --cell "$g" "$a" "$s" \
    > "$LOGDIR/cell_${g}_${a}_s${s}.log" 2>&1 &
}

# arms A and B first (fast, ngspice-bound) across all goals+seeds
for g in $GOALS_600 $GOAL_1200; do
  for a in a b; do
    for s in 1 2 3; do launch "$g" "$a" "$s"; done
  done
done
wait
echo "arms A,B done"

# arm C (generation-heavy): run with a smaller concurrency so CPU token-sampling
# does not thrash; ngspice within each cell still respects the box.
MAXJOBS="${MAXJOBS_C:-4}"
for g in $GOALS_600 $GOAL_1200; do
  for s in 1 2 3; do launch "$g" c "$s"; done
done
wait
echo "arm C done"
echo "CAMPAIGN COMPLETE"

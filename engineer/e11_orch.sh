#!/bin/bash
# Bounded-concurrency launcher for E-11 cells. Each cell process spawns <=1
# ngspice at a time (extract.run_and_extract is a blocking subprocess), so the
# concurrent-cell cap for a pool == that pool's concurrent-ngspice ceiling.
# Usage: e11_orch.sh <max_parallel> <cellspec_file> <pgrep_pattern>
# cellspec lines: "GOAL ARM SEED"
set -u
MAXP="$1"; SPEC="$2"; PAT="$3"
while read -r goal arm seed; do
  [ -z "$goal" ] && continue
  while [ "$(pgrep -fc "$PAT")" -ge "$MAXP" ]; do sleep 5; done
  python engineer/e11_run.py --cell "$goal" "$arm" "$seed" \
     > "engineer/data/e11_results/log_${goal}_${arm}_s${seed}.txt" 2>&1 &
  sleep 1
done < "$SPEC"
wait
echo "ORCH DONE $SPEC"

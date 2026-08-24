#!/bin/bash
# E-12 P1b bounded-concurrency launcher. Each cell process spawns <=1 ngspice at
# a time (extract.run_and_extract is a blocking subprocess), so the concurrent-
# cell cap == the concurrent-ngspice ceiling. Detached via setsid by the caller.
# Usage: e12_p1b_orch.sh <max_parallel> <cellspec_file>
# cellspec lines: "GOAL ARM SEED"
set -u
cd /home/dpatni/circuit-repro-engineer
source /home/dpatni/circuit-repro/env.sh
export PYTHONHASHSEED=0
export E11_TORCH_THREADS=4          # bound arm-C torch threads (128-core box)
MAXP="$1"; SPEC="$2"
PAT="e12_p1b.py --cell"
OUT=engineer/data/e12/p1b_results
mkdir -p "$OUT"
while read -r goal arm seed; do
  [ -z "${goal:-}" ] && continue
  while [ "$(pgrep -fc "$PAT")" -ge "$MAXP" ]; do sleep 5; done
  python engineer/e12_p1b.py --cell "$goal" "$arm" "$seed" \
     > "$OUT/log_${goal}_${arm}_s${seed}.txt" 2>&1 &
  sleep 2
done < "$SPEC"
wait
echo "P1b ORCH DONE $SPEC" > "$OUT/ORCH_DONE.txt"
echo "P1b ORCH DONE $SPEC"

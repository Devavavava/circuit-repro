#!/bin/bash
# E-13a bounded-concurrency launcher (mirrors e12_p3_orch.sh).
# Each cell process runs a single ngspice subprocess at a time; concurrent-cell
# cap == concurrent-ngspice ceiling (<=8 per pre-reg §7).
# Usage: e13a_orch.sh <max_parallel> <cellspec_file>
# cellspec lines: "GOAL ARM SEED M"   (ARM in {b,c2}; M in {1,2})
set -u
cd /home/dpatni/.claude/jobs/758a5886/tmp/wt-e13
source /home/dpatni/circuit-repro/env.sh
export PYTHONHASHSEED=0
export E11_TORCH_THREADS=4   # bound trained-editor torch threads
MAXP="$1"; SPEC="$2"
OUT=engineer/data/e13/a_results
mkdir -p "$OUT"

count_workers() {
  ps -eo cmd | grep -F 'engineer/e13a_run.py --cell' | grep -Fv grep \
    | grep -c '^python'
}
while read -r goal arm seed m; do
  [ -z "${goal:-}" ] && continue
  while [ "$(count_workers)" -ge "$MAXP" ]; do sleep 5; done
  python engineer/e13a_run.py --m "$m" --cell "$goal" "$arm" "$seed" \
     > "$OUT/log_${goal}_${arm}_m${m}_s${seed}.txt" 2>&1 &
  sleep 8
done < "$SPEC"
wait
echo "E-13a ORCH DONE $SPEC" > "$OUT/ORCH_DONE.txt"
echo "E-13a ORCH DONE $SPEC"

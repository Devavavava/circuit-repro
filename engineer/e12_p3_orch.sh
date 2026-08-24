#!/bin/bash
# E-12 P3 bounded-concurrency launcher. Each cell process runs a single ngspice
# subprocess at a time, so the concurrent-cell cap == the concurrent-ngspice
# ceiling. Detached via setsid by the caller.
# Usage: e12_p3_orch.sh <max_parallel> <cellspec_file>
# cellspec lines: "GOAL ARM SEED"  (ARM in a,b,c1,c2)
set -u
cd /home/dpatni/circuit-repro-engineer
source /home/dpatni/circuit-repro/env.sh
export PYTHONHASHSEED=0
export E11_TORCH_THREADS=4          # bound trained-editor torch threads (128-core box)
MAXP="$1"; SPEC="$2"
OUT=engineer/data/e12/p3_results
mkdir -p "$OUT"
# count ONLY the real python cell workers (immune to bash/monitoring lines that
# merely contain the pattern): match the python-invoked script path explicitly.
count_workers() {
  ps -eo cmd | grep -F 'engineer/e12_p3.py --cell' | grep -Fv grep \
    | grep -c '^python'
}
while read -r goal arm seed; do
  [ -z "${goal:-}" ] && continue
  while [ "$(count_workers)" -ge "$MAXP" ]; do sleep 5; done
  python engineer/e12_p3.py --cell "$goal" "$arm" "$seed" \
     > "$OUT/log_${goal}_${arm}_s${seed}.txt" 2>&1 &
  sleep 2
done < "$SPEC"
wait
echo "P3 ORCH DONE $SPEC" > "$OUT/ORCH_DONE.txt"
echo "P3 ORCH DONE $SPEC"

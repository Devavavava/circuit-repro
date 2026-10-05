#!/bin/bash
# usage: launch.sh [full|smoke] -> detached, resumable pilot-v0 P0 + P0b scheduler (pv0.py run).
# Re-running after a stop/kill RESUMES: every finished sizing call is cached in
# <run>/results.jsonl and the deterministic task generators replay through it.
MODE=${1:-full}
P=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/pilot-v0
E=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/bench-v2/envrun.sh
export BV2_TMPDIR=/tmp/cr-pv0
if [ "$MODE" = smoke ]; then
  RD=$P/smoke
  # SMOKE: 2 eval tasks, F2 cut to the first 8 edits, 2 old training tasks, the
  # generation stops after its first planting generation (>= 2 new tasks)
  ARGS=(--run-dir "$RD" --eval-limit 2 --f2-limit 8 --train-limit 2 --gen-max-new 2)
else
  RD=$P/run
  # exact-key reuse of the smoke's rl-v1.2 calls (same code, same verifier)
  ARGS=(--run-dir "$RD" --extra-cache "$P/smoke/results.jsonl")
fi
mkdir -p "$RD"
if [ -f "$RD/sched.pid" ] && kill -0 "$(cat "$RD/sched.pid")" 2>/dev/null; then
  echo "already running: pid $(cat "$RD/sched.pid")"; exit 1
fi
nohup setsid "$E" python "$P/pv0.py" run "${ARGS[@]}" >> "$RD/nohup.log" 2>&1 < /dev/null &
sleep 5
echo "launched mode=$MODE pid=$(cat "$RD/sched.pid" 2>/dev/null) run_dir=$RD"

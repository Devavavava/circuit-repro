#!/bin/bash
# usage: launch.sh [full|smoke]  -> detached, resumable AMENDMENT-3 re-check (a3run.py).
# Re-running after a stop/kill RESUMES: every finished sizing call is cached in
# <run>/results.jsonl and the deterministic stage generators replay through it.
MODE=${1:-full}
D=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/bench-v2
A=$D/amend3
if [ "$MODE" = smoke ]; then
  RD=$A/smoke
  ARGS=(--run-dir "$RD" --cells v2a-nb090-gain-007 --f2-limit 8 --train-limit 2
        --lib "$RD/editcap-lib-v2" --tp "$RD/train-pool-v2" --summary-name smoke/summary.json)
elif [ "$MODE" = smoke-force ]; then
  # SMOKE ONLY: same cell, kills recorded as would-kill and every stage + the
  # library write-out exercised; reuses the smoke's rows (exact key)
  RD=$A/smoke-force
  ARGS=(--run-dir "$RD" --cells v2a-nb090-gain-007 --f2-limit 8 --no-train --smoke-force
        --extra-cache "$A/smoke/results.jsonl"
        --lib "$RD/editcap-lib-v2" --tp "$RD/train-pool-v2" --summary-name smoke-force/summary.json)
else
  RD=$A/run
  # exact-key reuse of the smoke's rl-v1.2 calls (same code, same verifier)
  ARGS=(--run-dir "$RD" --extra-cache "$A/smoke/results.jsonl")
fi
mkdir -p "$RD"
if [ -f "$RD/sched.pid" ] && kill -0 "$(cat "$RD/sched.pid")" 2>/dev/null; then
  echo "already running: pid $(cat "$RD/sched.pid")"; exit 1
fi
nohup setsid "$D/envrun.sh" python "$A/a3run.py" run "${ARGS[@]}" >> "$RD/nohup.log" 2>&1 < /dev/null &
sleep 5
echo "launched mode=$MODE pid=$(cat "$RD/sched.pid") run_dir=$RD"

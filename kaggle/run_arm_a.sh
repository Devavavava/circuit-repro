#!/usr/bin/env bash
# run_arm_a.sh -- box-side launcher for the capability-v0 arm-A (sizing-only null).
#
# Arm A runs on THIS box (no GPU, no LLM): solve_spec's stored corpus topologies
# sized by CMA-ES at a matched total eval budget, per campaign.py --arm A. Same
# results schema / designs layout / verify pass as arm B; only the candidate
# source differs (no LLM anywhere).
#
# Concurrency (house rule after the thread-oversubscription incident): the sizer
# is serial per candidate -- ONE ngspice process at a time -- so this script adds
# no parallelism and pins the common thread-pool knobs to 1 to guarantee we never
# exceed the <=6 concurrent-ngspice cap. Do NOT wrap this in `&`/xargs -P.
#
# Output goes to a --out DIR. Default targets the $HOME-side job path the operator
# merges from; override with OUT_DIR=... (keep it generic).
#
#   OUT_DIR=/some/path bash kaggle/run_arm_a.sh
#   # smoke (one easy spec, tiny budget):
#   OUT_DIR=/tmp/arma bash kaggle/run_arm_a.sh --max-specs 1 --budget 80 --seeds 1
#
# Extra args after the script name are passed straight through to campaign.py
# (e.g. --max-specs, --budget, --seeds, --no-verify, --wall-budget-min).
set -euo pipefail

# ---- resolve the repo (this script lives in <repo>/kaggle/) -----------------
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"

# env.sh lives in the MAIN checkout (gitignored); a worktree has none. Find it:
# explicit override -> this checkout -> the git common dir's parent (the main
# checkout, when running from a worktree). Same walk extract.py's dep-shim uses.
ENV_HOME="${ENV_HOME:-}"
if [ -z "$ENV_HOME" ] && [ -f "$REPO/env.sh" ]; then ENV_HOME="$REPO"; fi
if [ -z "$ENV_HOME" ] && [ -n "${LNA_DEPS_ROOT:-}" ] && [ -f "$LNA_DEPS_ROOT/env.sh" ]; then
    ENV_HOME="$LNA_DEPS_ROOT"
fi
if [ -z "$ENV_HOME" ]; then
    _common="$(git -C "$REPO" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
    if [ -n "$_common" ] && [ -f "$(dirname "$_common")/env.sh" ]; then
        ENV_HOME="$(dirname "$_common")"
    fi
fi
if [ -z "$ENV_HOME" ] || [ ! -f "$ENV_HOME/env.sh" ]; then
    echo "[run_arm_a] cannot find env.sh (set ENV_HOME=<main checkout>)" >&2
    exit 1
fi

# env: the project toolchain (no system git/python/ngspice -- MEMORY rule).
# LNA_DEPS_ROOT points at the checkout whose lna/ + deps we run against (the
# main checkout, which has the untracked spice-model/deps clones a worktree
# lacks); the campaign code + ladder are read from THIS checkout ($REPO).
# shellcheck source=/dev/null
source "$ENV_HOME/env.sh"
export LNA_DEPS_ROOT="${LNA_DEPS_ROOT:-$ENV_HOME}"

# ---- concurrency cap: pin BLAS/OMP thread pools to 1 so a single serial sizer
# never fans out to N threads * (already-serial) ngspice. Guarantees <=6.
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"

LADDER="${LADDER:-$REPO/kaggle/specs-ladder/ladder.json}"
OUT_DIR="${OUT_DIR:-/home/dpatni/.claude/jobs/de5270c8/tmp/arma-out}"
mkdir -p "$OUT_DIR"

echo "[run_arm_a] repo    = $REPO"
echo "[run_arm_a] ngspice = ${NGSPICE:-<unset>}"
echo "[run_arm_a] ladder  = $LADDER"
echo "[run_arm_a] out     = $OUT_DIR"
echo "[run_arm_a] threads = OMP=$OMP_NUM_THREADS (serial sizer; <=1 ngspice at a time)"
echo "[run_arm_a] extra   = $*"

exec python "$REPO/kaggle/loop/campaign.py" \
    --arm A \
    --ladder "$LADDER" \
    --out "$OUT_DIR" \
    "$@"

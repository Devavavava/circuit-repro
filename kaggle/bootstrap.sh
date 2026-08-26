#!/usr/bin/env bash
# =============================================================================
# bootstrap.sh -- idempotent Kaggle-VM setup for the circuit-repro LNA worker.
#
# WHAT THIS INSTALLS / DOWNLOADS (review before the first run):
#   (a) pip: numpy scipy pyyaml           (always)
#           pandas                        (only if WITH_PANDAS=1 -- needed for the
#                                          proposal netlist<->token round-trip and
#                                          corpus/template rebuild)
#           torch (CPU wheel)             (only if WITH_TORCH=1 -- needed ONLY if
#                                          the 12M generator is used as a pool
#                                          filler; the LLM loop is torch-free)
#   (b) ngspice 47: untar a cached built tree from an attached dataset if present
#       (/kaggle/input/*/ngspice47.tar.gz), ELSE download the ngspice-47 source
#       tarball from SourceForge and build it (--with-readline=no --without-x) at
#       the FIXED prefix /kaggle/working/ngspice47. The prefix MUST be identical
#       across sessions: spinit bakes absolute codemodel paths at the build prefix.
#   (c) git: shallow-clone this repo's `main` branch via the GH_READ_TOKEN Kaggle
#       secret to /kaggle/working/circuit-repro (read-only; Kaggle never pushes).
#   (d) symlink gitignored checkpoints from an attached dataset if present
#       (AnalogGenie/repo/Pretrain.pth, lna/out/ft_p5v7_v2.pth). Only needed if
#       the generator is used; skipped silently if absent.
#   (e) export env vars (NGSPICE, LNA_DEPS_ROOT, SPICE_LIB_DIR, ...) and write a
#       sourceable /kaggle/working/env-kaggle.sh.
#   (f) run the acceptance gate and write versions+timings JSON to
#       /kaggle/working/report/. NON-ZERO EXIT on any gate failure.
#
# No network beyond pip / SourceForge / github (all over HTTPS). Idempotent: every
# stage checks whether its artifact already exists and skips if so.
#
# Overridable env:
#   GH_READ_TOKEN          (required for the clone; Kaggle secret)
#   REPO_SLUG              default: <TODO set>  e.g. youruser/circuit-repro
#   REPO_BRANCH            default: main
#   NGSPICE_PREFIX         default: /kaggle/working/ngspice47   (DO NOT change lightly)
#   NGSPICE_TARBALL_URL    default: SourceForge ngspice-47 source tarball
#   CLONE_DIR             default: /kaggle/working/circuit-repro
#   WEIGHTS_DATASET_GLOB   default: /kaggle/input/*/            (checkpoints search)
#   WITH_PANDAS=1  WITH_TORCH=1
# =============================================================================
set -euo pipefail

log() { printf '[bootstrap] %s\n' "$*" >&2; }
now() { date +%s; }

# --------------------------------------------------------------- configuration
REPO_SLUG="${REPO_SLUG:-Devavavava/circuit-repro}"
REPO_BRANCH="${REPO_BRANCH:-main}"
CLONE_DIR="${CLONE_DIR:-/kaggle/working/circuit-repro}"
NGSPICE_PREFIX="${NGSPICE_PREFIX:-/kaggle/working/ngspice47}"
NGSPICE_VERSION="${NGSPICE_VERSION:-47}"
NGSPICE_TARBALL_URL="${NGSPICE_TARBALL_URL:-https://sourceforge.net/projects/ngspice/files/ng-spice-rework/${NGSPICE_VERSION}/ngspice-${NGSPICE_VERSION}.tar.gz/download}"
WEIGHTS_DATASET_GLOB="${WEIGHTS_DATASET_GLOB:-/kaggle/input/*}"
REPORT_DIR="${REPORT_DIR:-/kaggle/working/report}"
BUILD_DIR="${BUILD_DIR:-/kaggle/working/_ngspice_build}"

mkdir -p "$REPORT_DIR"
T_START=$(now)
declare -A TIMINGS

# --------------------------------------------------- (a) python dependencies
stage_pip() {
    local t0; t0=$(now)
    log "pip: numpy scipy pyyaml"
    pip install --quiet --no-input numpy scipy pyyaml
    if [ "${WITH_PANDAS:-0}" = "1" ]; then
        log "pip: pandas (WITH_PANDAS=1)"
        pip install --quiet --no-input pandas
    fi
    if [ "${WITH_TORCH:-0}" = "1" ]; then
        log "pip: torch CPU wheel (WITH_TORCH=1)"
        pip install --quiet --no-input torch --index-url https://download.pytorch.org/whl/cpu
    fi
    TIMINGS[pip]=$(( $(now) - t0 ))
}

# --------------------------------------------------- (b) ngspice 47
stage_ngspice() {
    local t0; t0=$(now)
    local bin="$NGSPICE_PREFIX/bin/ngspice"
    if [ -x "$bin" ]; then
        log "ngspice already present at $bin -- skipping"
        TIMINGS[ngspice]=$(( $(now) - t0 )); return
    fi
    # fast path: a prebuilt tree attached as a dataset
    local cached
    cached=$(ls $WEIGHTS_DATASET_GLOB/ngspice47.tar.gz 2>/dev/null | head -1 || true)
    if [ -n "$cached" ]; then
        log "untarring cached ngspice tree from $cached -> /kaggle/working"
        tar -xzf "$cached" -C /kaggle/working
        if [ -x "$bin" ]; then
            TIMINGS[ngspice]=$(( $(now) - t0 )); return
        fi
        log "WARNING: cached tarball did not yield $bin; falling back to source build"
    fi
    # slow path: build from source at the FIXED prefix
    log "building ngspice ${NGSPICE_VERSION} from source (~5-10 min)"
    mkdir -p "$BUILD_DIR"; cd "$BUILD_DIR"
    if [ ! -f "ngspice-${NGSPICE_VERSION}.tar.gz" ]; then
        log "downloading $NGSPICE_TARBALL_URL"
        wget -q -O "ngspice-${NGSPICE_VERSION}.tar.gz" "$NGSPICE_TARBALL_URL"
    fi
    tar -xzf "ngspice-${NGSPICE_VERSION}.tar.gz"
    cd "ngspice-${NGSPICE_VERSION}"
    ./configure --prefix="$NGSPICE_PREFIX" --with-readline=no --without-x \
        --enable-xspice --enable-cider >/dev/null
    make -j"$(nproc)" >/dev/null
    make install >/dev/null
    cd /
    [ -x "$bin" ] || { log "FATAL: ngspice build did not produce $bin"; exit 1; }
    TIMINGS[ngspice]=$(( $(now) - t0 ))
}

# --------------------------------------------------- (c) clone the repo
stage_clone() {
    local t0; t0=$(now)
    if [ -d "$CLONE_DIR/.git" ]; then
        log "clone already present at $CLONE_DIR -- skipping"
        TIMINGS[clone]=$(( $(now) - t0 )); return
    fi
    : "${GH_READ_TOKEN:?GH_READ_TOKEN not set (add it as a Kaggle secret)}"
    log "shallow-cloning $REPO_SLUG@$REPO_BRANCH -> $CLONE_DIR"
    git clone --depth 1 --branch "$REPO_BRANCH" \
        "https://x-access-token:${GH_READ_TOKEN}@github.com/${REPO_SLUG}.git" \
        "$CLONE_DIR"
    TIMINGS[clone]=$(( $(now) - t0 ))
}

# --------------------------------------------------- (d) checkpoints (optional)
stage_checkpoints() {
    local t0; t0=$(now)
    local genie="$CLONE_DIR/AnalogGenie/repo/Pretrain.pth"
    local ft="$CLONE_DIR/lna/out/ft_p5v7_v2.pth"
    local src_genie src_ft
    src_genie=$(ls $WEIGHTS_DATASET_GLOB/Pretrain.pth 2>/dev/null | head -1 || true)
    src_ft=$(ls $WEIGHTS_DATASET_GLOB/ft_p5v7_v2.pth 2>/dev/null | head -1 || true)
    if [ -n "$src_genie" ] && [ ! -e "$genie" ]; then
        mkdir -p "$(dirname "$genie")"; ln -sf "$src_genie" "$genie"
        log "linked generator checkpoint: $genie -> $src_genie"
    fi
    if [ -n "$src_ft" ] && [ ! -e "$ft" ]; then
        mkdir -p "$(dirname "$ft")"; ln -sf "$src_ft" "$ft"
        log "linked finetune checkpoint: $ft -> $src_ft"
    fi
    [ -n "$src_genie$src_ft" ] || log "no checkpoints found in $WEIGHTS_DATASET_GLOB (ok: LLM loop is torch-free)"
    TIMINGS[checkpoints]=$(( $(now) - t0 ))
}

# --------------------------------------------------- (e) env
stage_env() {
    export NGSPICE="$NGSPICE_PREFIX/bin/ngspice"
    export LNA_DEPS_ROOT="$CLONE_DIR"
    export SPICE_LIB_DIR="$NGSPICE_PREFIX/share/ngspice"
    export PATH="$NGSPICE_PREFIX/bin:$PATH"
    cat > /kaggle/working/env-kaggle.sh <<ENV
# sourceable env for the circuit-repro LNA worker (written by bootstrap.sh)
export NGSPICE="$NGSPICE_PREFIX/bin/ngspice"
export LNA_DEPS_ROOT="$CLONE_DIR"
export SPICE_LIB_DIR="$NGSPICE_PREFIX/share/ngspice"
export PATH="$NGSPICE_PREFIX/bin:\$PATH"
ENV
    log "wrote /kaggle/working/env-kaggle.sh"
}

# --------------------------------------------------- (f) acceptance gate
stage_gate() {
    local t0; t0=$(now)
    cd "$CLONE_DIR"
    local gate_log="$REPORT_DIR/gate.log"
    : > "$gate_log"
    local -a GATE=(
        "python lna/extract.py --selftest"
        "python lna/ref/check_ref.py"
        "python lna/ref/check_bjt.py"
        "python lna/spec.py --all"
        "python lna/solve_spec.py wifi24 --corpus --budget 100 --seeds 1"
    )
    local failed=0
    for cmd in "${GATE[@]}"; do
        log "gate: $cmd"
        if ! eval "$cmd" >>"$gate_log" 2>&1; then
            log "GATE FAILED: $cmd (see $gate_log)"; failed=1; break
        fi
    done
    TIMINGS[gate]=$(( $(now) - t0 ))
    [ "$failed" = "0" ]
}

# --------------------------------------------------- report + main
write_report() {
    local ok="$1"
    local ng_ver="unknown"
    [ -x "$NGSPICE_PREFIX/bin/ngspice" ] && \
        ng_ver=$("$NGSPICE_PREFIX/bin/ngspice" --version 2>/dev/null | head -1 || echo unknown)
    local py_ver git_ver
    py_ver=$(python --version 2>&1)
    git_ver=$(git --version 2>&1)
    {
        printf '{\n'
        printf '  "ok": %s,\n' "$ok"
        printf '  "total_seconds": %s,\n' "$(( $(now) - T_START ))"
        printf '  "versions": {"python": "%s", "git": "%s", "ngspice": "%s"},\n' \
            "$py_ver" "$git_ver" "$ng_ver"
        printf '  "prefix": {"ngspice": "%s", "clone": "%s"},\n' \
            "$NGSPICE_PREFIX" "$CLONE_DIR"
        printf '  "timings": {'
        local first=1
        for k in "${!TIMINGS[@]}"; do
            [ "$first" = "1" ] || printf ', '
            printf '"%s": %s' "$k" "${TIMINGS[$k]}"; first=0
        done
        printf '}\n}\n'
    } > "$REPORT_DIR/bootstrap.json"
    log "wrote $REPORT_DIR/bootstrap.json (ok=$ok)"
}

main() {
    stage_pip
    stage_ngspice
    stage_clone
    stage_checkpoints
    stage_env
    if stage_gate; then
        write_report true
        log "BOOTSTRAP OK"
    else
        write_report false
        log "BOOTSTRAP FAILED (acceptance gate)"
        exit 1
    fi
}

main "$@"

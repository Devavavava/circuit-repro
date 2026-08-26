#!/usr/bin/env bash
# =============================================================================
# build-llamacpp.sh -- one-time llama.cpp CUDA build for a SHORT GPU session.
#
# Builds llama-server with CUDA, installs at the FIXED prefix
# /kaggle/working/llamacpp, and tars it to /kaggle/working/llamacpp.tar.gz so the
# kernel output can be saved as a dataset and reused (the loop-gpu kernel just
# untars this -- it never rebuilds).
#
# EXPECTED BUILD TIME: ~8-15 min on a 2xT4 / P100 GPU session with CUDA toolkit
# already present in the Kaggle image. Run this in a dedicated short GPU session,
# save the output as a dataset (e.g. <user>/llamacpp-cuda), then attach it to the
# loop-gpu kernel.
#
# CPU-ONLY FALLBACK for smoke tests: set GGML_CUDA=OFF (or run on a CPU session).
# The resulting binary runs on CPU only -- fine for verifying the server starts
# and answers /health and /v1/chat/completions, useless for real throughput.
#
# Overridable env:
#   LLAMACPP_REPO   default: https://github.com/ggml-org/llama.cpp
#   LLAMACPP_TAG    default: b4589            # TODO verify/pin a current tag
#   LLAMACPP_PREFIX default: /kaggle/working/llamacpp
#   GGML_CUDA       default: ON               (set OFF for CPU-only fallback)
#   BUILD_DIR       default: /kaggle/working/_llamacpp_build
#   JOBS            default: nproc
# =============================================================================
set -euo pipefail

log() { printf '[build-llamacpp] %s\n' "$*" >&2; }

LLAMACPP_REPO="${LLAMACPP_REPO:-https://github.com/ggml-org/llama.cpp}"
LLAMACPP_TAG="${LLAMACPP_TAG:-b4589}"          # TODO verify/pin a current tag at run time
LLAMACPP_PREFIX="${LLAMACPP_PREFIX:-/kaggle/working/llamacpp}"
GGML_CUDA="${GGML_CUDA:-ON}"
BUILD_DIR="${BUILD_DIR:-/kaggle/working/_llamacpp_build}"
JOBS="${JOBS:-$(nproc)}"
TARBALL="${TARBALL:-/kaggle/working/llamacpp.tar.gz}"

if [ -x "$LLAMACPP_PREFIX/bin/llama-server" ]; then
    log "llama-server already at $LLAMACPP_PREFIX/bin -- skipping build"
else
    log "cloning $LLAMACPP_REPO @ $LLAMACPP_TAG"
    rm -rf "$BUILD_DIR"
    git clone --depth 1 --branch "$LLAMACPP_TAG" "$LLAMACPP_REPO" "$BUILD_DIR"
    cd "$BUILD_DIR"
    log "cmake configure (GGML_CUDA=$GGML_CUDA)"
    cmake -B build \
        -DGGML_CUDA="$GGML_CUDA" \
        -DLLAMA_CURL=OFF \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$LLAMACPP_PREFIX"
    log "building llama-server (~8-15 min with CUDA)"
    cmake --build build --config Release --target llama-server -j"$JOBS"
    # install just what the loop needs (server binary + shared libs)
    cmake --install build --config Release || true
    mkdir -p "$LLAMACPP_PREFIX/bin"
    # some tags don't install the server via the target; copy it explicitly
    if [ ! -x "$LLAMACPP_PREFIX/bin/llama-server" ]; then
        find build -name 'llama-server' -type f -perm -u+x -exec cp {} "$LLAMACPP_PREFIX/bin/" \;
    fi
    cd /
    [ -x "$LLAMACPP_PREFIX/bin/llama-server" ] || {
        log "FATAL: llama-server not found after build"; exit 1; }
fi

log "tarring $LLAMACPP_PREFIX -> $TARBALL (for caching as a dataset)"
tar -czf "$TARBALL" -C "$(dirname "$LLAMACPP_PREFIX")" "$(basename "$LLAMACPP_PREFIX")"
log "done: $("$LLAMACPP_PREFIX/bin/llama-server" --version 2>&1 | head -1 || echo 'llama-server built')"
log "cached tarball: $TARBALL  ($(du -h "$TARBALL" | cut -f1))"

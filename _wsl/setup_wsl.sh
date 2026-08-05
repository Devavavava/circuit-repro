#!/usr/bin/env bash
# Base prerequisites inside WSL Ubuntu 22.04 for the circuit-repro work.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

echo "===== apt update ====="
apt-get update -qq

echo "===== apt install ====="
apt-get install -y -qq --no-install-recommends \
    build-essential git wget curl ca-certificates bzip2 \
    ngspice libngspice0-dev \
    2>&1 | tail -5

echo "===== ngspice version ====="
ngspice -v 2>&1 | head -3 || true

echo "===== miniconda ====="
if [ ! -d /opt/miniconda ]; then
    wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/mc.sh
    bash /tmp/mc.sh -b -p /opt/miniconda
    rm -f /tmp/mc.sh
fi
/opt/miniconda/bin/conda --version

echo "===== workspace ====="
mkdir -p /root/circuit-repro
echo "DONE"

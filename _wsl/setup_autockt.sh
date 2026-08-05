#!/usr/bin/env bash
# AutoCkt with its EXACT documented stack (ray 0.6.3 / TF 1.10.1 / gym 0.10.5),
# which only has Linux wheels -- this is the whole reason for using WSL.
set -uo pipefail

CONDA=/opt/miniconda/bin/conda
ROOT=/root/circuit-repro
REPO=$ROOT/AutoCkt

echo "===== clone ====="
mkdir -p "$ROOT"
if [ ! -d "$REPO" ]; then
    git clone --quiet --depth 1 https://github.com/ksettaluri6/AutoCkt.git "$REPO"
fi
echo "cloned to $REPO"

echo "===== conda env python 3.6 ====="
# conda-forge only: the Anaconda 'defaults' channel now requires accepting a
# commercial ToS, and conda-forge carries python 3.6 anyway.
# python 3.6 is the exact target: tensorflow 1.10.1 ships cp36 but no cp37.
if [ ! -d /opt/miniconda/envs/autockt ]; then
    $CONDA create -y -n autockt -c conda-forge --override-channels python=3.6 2>&1 | tail -6
fi
PY=/opt/miniconda/envs/autockt/bin/python
$PY --version

echo "===== pin old build tooling (gym 0.10.5 is an sdist) ====="
$PY -m pip install -q --no-warn-script-location "pip<21.4" "setuptools<58" "wheel<0.38" 2>&1 | tail -2

echo "===== documented stack ====="
# environment.yml pins numpy==1.16.4, but tensorflow 1.10.1's own metadata
# requires numpy<=1.14.5 -- those two pins are mutually unsatisfiable under a
# modern pip resolver. Deferring to TF's actual constraint.
$PY -m pip install --no-warn-script-location --retries 10 --timeout 60 \
    "numpy==1.14.5" "tensorflow==1.10.1" "ray==0.6.3" "gym==0.10.5" \
    "pyyaml==5.1.2" "scipy==1.1.0" "jinja2==2.10" "ipython==6.5.0" \
    pandas requests psutil setproctitle 2>&1 | tail -8

echo "===== verify ====="
$PY - <<'EOF'
import numpy, tensorflow, ray, gym, yaml, scipy
print("numpy      ", numpy.__version__)
print("tensorflow ", tensorflow.__version__)
print("ray        ", ray.__version__)
print("gym        ", gym.__version__)
print("scipy      ", scipy.__version__)
import ray.rllib.agents.ppo as ppo
print("rllib PPO import: OK")
EOF
echo "SETUP EXIT: $?"

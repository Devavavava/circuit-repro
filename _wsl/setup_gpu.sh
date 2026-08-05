#!/usr/bin/env bash
# CUDA PyTorch inside WSL. On Windows the CUDA wheels live only on
# download.pytorch.org (measured 187 KB/s from this host -> ~3.5 h for 2.3 GB).
# On Linux the default PyPI wheel is CUDA-enabled and PyPI runs ~8x faster here.
set -uo pipefail

CONDA=/opt/miniconda/bin/conda

echo "===== env ====="
if [ ! -d /opt/miniconda/envs/gpu ]; then
    $CONDA create -y -n gpu -c conda-forge --override-channels python=3.10 2>&1 | tail -3
fi
PY=/opt/miniconda/envs/gpu/bin/python
$PY --version

echo "===== torch (CUDA build from PyPI) ====="
time $PY -m pip install -q --no-warn-script-location --retries 10 --timeout 60 \
    torch numpy 2>&1 | tail -5

echo "===== CUDA check ====="
$PY - <<'EOF'
import torch
print("torch           :", torch.__version__)
print("cuda available  :", torch.cuda.is_available())
print("cuda version    :", torch.version.cuda)
if torch.cuda.is_available():
    print("device          :", torch.cuda.get_device_name(0))
    free, total = torch.cuda.mem_get_info()
    print(f"VRAM free/total : {free/1e9:.2f} / {total/1e9:.2f} GB")
    a = torch.randn(2000, 2000, device="cuda")
    b = torch.randn(2000, 2000, device="cuda")
    import time
    torch.cuda.synchronize(); t0 = time.time()
    for _ in range(20):
        c = a @ b
    torch.cuda.synchronize()
    dt = time.time() - t0
    flops = 20 * 2 * 2000**3 / dt
    print(f"matmul throughput: {flops/1e12:.2f} TFLOP/s")
EOF

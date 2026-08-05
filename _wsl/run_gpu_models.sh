#!/usr/bin/env bash
# Re-run AnalogGenie generation and LaMAGIC2 inference on the GPU under WSL.
# Checkpoints are reused from the Windows side via /mnt/c rather than re-downloaded.
set -uo pipefail

PY=/opt/miniconda/envs/gpu/bin/python
WIN=/mnt/c/Users/Devavrat/circuit-repro
WORK=/root/circuit-repro/gpu
mkdir -p "$WORK"

echo "############ AnalogGenie on GPU ############"
AG=$WORK/AnalogGenie
mkdir -p "$AG"
cp -r "$WIN/AnalogGenie/repo/Models" "$AG/"
cp "$WIN/AnalogGenie/repo/Inference_smoke.py" "$AG/"
[ -f "$AG/Pretrain.pth" ] || cp "$WIN/AnalogGenie/repo/Pretrain.pth" "$AG/"
cd "$AG"
rm -rf Inference_smoke
echo "checkpoint: $(du -h Pretrain.pth | cut -f1)"
echo "--- running (Windows CPU baseline was 399.6 s) ---"
time $PY Inference_smoke.py 2>&1 | grep -vE "^Devices in order|^Device to index|^Index to device"
echo "--- generated token count ---"
tr '>' '\n' < Inference_smoke/run0.txt | grep -c "" || true
echo "--- first 300 chars ---"
head -c 300 Inference_smoke/run0.txt; echo

echo
echo "############ LaMAGIC2 on GPU ############"
$PY -m pip install -q --no-warn-script-location "transformers==4.36.0" "tokenizers==0.15.2" sentencepiece protobuf 2>&1 | tail -2
LM=$WORK/LaMAGIC2
mkdir -p "$LM"
[ -d "$LM/repo" ] || cp -r "$WIN/LaMAGIC2/repo" "$LM/repo"
cd "$LM"
cp "$WIN/_wsl/smoke_lamagic2_gpu.py" .
sed -i 's/\r$//' smoke_lamagic2_gpu.py
echo "--- running ---"
time $PY smoke_lamagic2_gpu.py 2>&1 | grep -vE "FutureWarning|warnings\.warn|^\s*$|UserWarning" | tail -30

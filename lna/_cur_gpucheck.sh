#!/bin/bash
# Curriculum-arm environment probe (FINDINGS §18).
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
PY=/opt/miniconda/envs/gpu/bin/python
$PY - <<'EOF'
import torch, os
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
if torch.cuda.is_available():
    print(torch.cuda.get_device_name(0),
          "free/total GB:", [round(x/2**30, 2) for x in torch.cuda.mem_get_info()])
for p in ("lna/out/ft_p5.pth", "lna/out/ft_p5_v2.pre_dhruva.pth",
          "lna/out/winners_train.pre_dhruva.json",
          "lna/out/templates_train.pre_dhruva.json",
          "AnalogGenie/repo/Pretrain.pth"):
    print(p, os.path.exists(p), os.path.getsize(p) if os.path.exists(p) else "-")
EOF
echo "--- md5 ---"
md5sum lna/out/ft_p5.pth lna/out/ft_p5_v2.pre_dhruva.pth lna/out/ft_p5_v2.pth

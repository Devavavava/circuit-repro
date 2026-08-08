cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data && \
/opt/miniconda/envs/gpu/bin/python -c "
import torch,os
print('torch',torch.__version__,'cuda',torch.cuda.is_available())
if torch.cuda.is_available():
    print(torch.cuda.get_device_name(0))
    free,tot=torch.cuda.mem_get_info()
    print('free GB %.2f / tot %.2f'%(free/1e9,tot/1e9))
for p in ['AnalogGenie/repo/Pretrain.pth','AnalogGenie/repo/Training.npy','lna/out/templates_train.json']:
    print(p, os.path.exists(p))
"

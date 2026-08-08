cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
exec /opt/miniconda/envs/gpu/bin/python -u lna/finetune.py --arm p5 --do train \
  --winners --device cuda --epochs 10 --seed 1337

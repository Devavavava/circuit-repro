cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
/opt/miniconda/envs/gpu/bin/python lna/finetune.py --arm p5 --do sample \
  --winners --device cuda --n 256 --seed 1337 --class nb \
  --out lna/out/ft_p5v6_nb_s1337

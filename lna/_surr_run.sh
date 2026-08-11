#!/usr/bin/env bash
# WP-SURROGATE launcher (plans2/12). Run from PowerShell, NOT Git Bash --
# Git Bash rewrites /opt/... into C:/Program Files/Git/opt/... (WORKLOG X10):
#
#   wsl -e bash /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data/lna/_surr_run.sh ab
#
# The cache must already exist (built in the Windows py3.14 env, which is the
# only one with size.py/ngspice):  python lna/surrogate.py --build-cache
set -e
ROOT=/mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
PY=/opt/miniconda/envs/gpu/bin/python
cd "$ROOT"
case "${1:-ab}" in
  ab)        # the A/B: one seed per arm, identical budget
    for a in node concat film; do
      $PY lna/surrogate.py --train --arm "$a" --seeds 0 --epochs 60 --device cuda
    done ;;
  ensemble)  # two more seeds of the winning arm -> a 3-seed deep ensemble
    $PY lna/surrogate.py --train --arm "${2:-node}" --seeds 1 --epochs 60 --device cuda
    $PY lna/surrogate.py --train --arm "${2:-node}" --seeds 2 --epochs 60 --device cuda ;;
  abeval)    # the A/B: same seed, same budget, cross-family accuracy per arm
    for a in node concat film; do
      $PY lna/surrogate.py --eval --arm "$a" --seeds 0 --device cuda           > lna/out/_surrogate/ab_$a.txt 2>&1
    done ;;
  eval)
    $PY lna/surrogate.py --eval --gate --arm "${2:-node}" --seeds "${3:-0,1,2}" \
        --device cuda --out lna/out/_surrogate/report_${2:-node}.json ;;
  *) echo "usage: _surr_run.sh {ab|ensemble <arm>|eval <arm> <seeds>}"; exit 2 ;;
esac

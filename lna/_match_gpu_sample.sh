#!/bin/bash
# WP-MATCH step 4: does seeding the ADOPTED P5-v7 checkpoint with the opening
# tokens of designs that already carry a source-driven input raise the rate at
# which it emits that motif?  (FINDINGS 29)
#
# Five arms, one changed variable each, all at seed 1337 / n 256 / temp 0.7 so
# they are directly comparable with the frozen §16 pool protocol:
#   uncond    class token + VSS            -- reproduces finetune.sample
#   all12     12-token prefixes, any LNA   -- isolates "prefix conditioning at all"
#   src12     12-token prefixes, port_src designs only
#   gate12    12-token prefixes, gate-only designs -- the complement control
#   src24     24-token prefixes, port_src  -- stronger seed (watch copy fraction)
set -e
cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
PY=/opt/miniconda/envs/gpu/bin/python
O=lna/out/_m

run () {  # arm  prefix_len  outdir
  echo "=== arm=$1 prefix_len=$2 -> $O/$3 ==="
  $PY lna/_match_sample.py --arm "$1" --prefix-len "$2" --n 256 --batch 32 \
      --device cuda --seed 1337 --tag p5v7 --winners --class nb --out "$O/$3"
}

run uncond 0  pfx_uncond
run all    12 pfx_all12
run src    12 pfx_src12
run gate   12 pfx_gate12
run src    24 pfx_src24
echo "=== WP-MATCH SAMPLING DONE ==="

#!/bin/bash
# §16 novel-front protocol on P5-v8 (FINDINGS §26). dhruva-l5 is new this round:
# the parallel l5 campaign wants co-sizeable low-noise hybrids, so the l5 front
# is run under the SAME tier-1 gating as the others (NF measured, advisory) and
# the NF column is what the l5 track cares about. Sequential: ngspice <= 1.
cd "$(dirname "$0")/.."
for S in wifi24 dhruva-l1 dhruva-l5; do
  O=lna/out/_v8_front_${S//-/}.json
  echo "=================== p5v8 vs $S -> $O"
  python lna/_cur_front.py --pool lna/out/ft_p5v8_nb_s1337 --spec $S \
      --arm p5v8-v1 --experiment p5v8-v1 --recipe p5v8-v1 \
      --scan-limit 14 --top 5 --no-nf-gate --out $O
done
echo "=== V8 FRONTS DONE ==="

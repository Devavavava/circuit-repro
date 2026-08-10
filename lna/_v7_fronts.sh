#!/bin/bash
# The §16 novel-front protocol on P5-v7 (FINDINGS §21). Sequential: ngspice <= 1.
cd "$(dirname "$0")/.."
for S in wifi24 dhruva-l1; do
  O=lna/out/_v7_front_${S//-/}.json
  echo "=================== p5v7 vs $S -> $O"
  python lna/_cur_front.py --pool lna/out/ft_p5v7_nb_s1337 --spec $S \
      --arm p5v7-v1 --experiment p5v7-v1 --recipe p5v7-v1 \
      --scan-limit 14 --top 5 --no-nf-gate --out $O
done
echo "=== V7 FRONTS DONE ==="

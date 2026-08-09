#!/bin/bash
# The §16 novel-front protocol, run identically on the curriculum arms
# (FINDINGS §18). Sequential by construction: concurrent ngspice <= 1.
cd "$(dirname "$0")/.."
for A in cur:cur-v1 cur2:cur-v2; do
  TAG=${A%%:*}; ARM=${A##*:}
  for S in wifi24 dhruva-l1; do
    O=lna/out/_cur_front_${TAG}_${S//-/}.json
    echo "=================== $ARM vs $S -> $O"
    python lna/_cur_front.py --pool lna/out/ft_${TAG}_nb_s1337 --spec $S \
        --arm $ARM --experiment cur-v1 --scan-limit 14 --top 5 --no-nf-gate \
        --out $O
  done
done
echo "=== FRONTS DONE ==="

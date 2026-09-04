# x0-v1 results (EXPERIMENTAL -- pre-registered, not frozen)

arm = LNA_X0_PRIOR = learned   (off=A0 null / retrieval=A1 / learned=A2)
Fixed topology per cell, k=1, NO screening, no LLM. 0-feasible rows are results, not suppressed failures.
NOVEL-10 = wl not in the store (primary set); SEEN-4 = control strip.
sim-health = fraction of ngspice evals that produced metrics (1.00 = healthy; <<1 = environment wall).

| spec | tier | split | flag | pdk | feasible | first-feasible | evals | escalated | best_obj | margins (worst) | sim-health | wl_hash | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | NOVEL | learned | bptm45 | YES | propose#0 | 600 | no | -1.06 | idd_ma=0.146 | 1.00 (0/600) | 25905c563595 |  |
| cap-e02-gpsband | E | NOVEL | learned | bptm45 | YES | propose#0 | 600 | no | -1.2 | idd_ma=0.0124 | 1.00 (0/600) | a13885258ca3 |  |
| cap-e04-35ghz | E | NOVEL | learned | bptm45 | YES | propose#0 | 600 | no | -1.36 | s11_db=0.338 | 1.00 (0/600) | f49a8abd26dd |  |
| cap-e05-ism58 | E | seen | learned | bptm45 | YES | propose#0 | 600 | no | -1.31 | s11_db=0.0116 | 1.00 (0/600) | c231ac11552a |  |
| cap-e06-wifi | E | NOVEL | learned | bptm45 | YES | propose#0 | 600 | no | -0.797 | s11_db=0.0338 | 1.00 (0/600) | 0a5583e1dc5d |  |
| cap-e07-gpsband | E | NOVEL | learned | bptm45 | YES | propose#0 | 600 | no | -0.689 | s21_db=0.193 | 1.00 (0/600) | 164fb57cffc4 |  |
| cap-h01-wifi | H | seen | learned | bptm45 | YES | propose#0 | 600 | no | -0.649 | idd_ma=0.138 | 1.00 (0/600) | 1bf4c880c7fa |  |
| cap-h02-gpsband | H | NOVEL | learned | bptm45 | YES | propose#0 | 1800 | yes | -0.163 | s11_db=0.0159 | 1.00 (0/1800) | e25b5a021ab6 |  |
| cap-h05-ism58 | H | NOVEL | learned | bptm45 | YES | propose#0 | 600 | no | -0.145 | s11_db=0.053 | 1.00 (0/600) | 7c8c8f9e0d2a |  |
| cap-m01-wifi | M | seen | learned | bptm45 | YES | propose#0 | 600 | no | -1.28 | s11_db=0.00983 | 1.00 (0/600) | 1bf4c880c7fa |  |
| cap-m04-35ghz | M | NOVEL | learned | bptm45 | YES | propose#0 | 600 | no | -0.35 | s21_db=0.0111 | 1.00 (0/600) | fb45bc8be87f |  |
| cap-m05-ism58 | M | seen | learned | bptm45 | YES | propose#0 | 600 | no | -0.772 | idd_ma=0.0396 | 1.00 (0/600) | c231ac11552a |  |
| cap-m06-wifi | M | NOVEL | learned | bptm45 | YES | propose#0 | 1800 | yes | -0.253 | s11_db=0.0361 | 1.00 (0/1800) | 642485a8fad7 |  |
| cap-m08-ism58 | M | NOVEL | learned | bptm45 | YES | propose#0 | 1800 | yes | -0.788 | s11_db=0.0239 | 1.00 (0/1800) | 3a2658be7000 |  |

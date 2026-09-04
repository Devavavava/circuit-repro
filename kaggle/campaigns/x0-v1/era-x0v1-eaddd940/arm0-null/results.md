# x0-v1 results (EXPERIMENTAL -- pre-registered, not frozen)

arm = LNA_X0_PRIOR = (unset -> off/A0)   (off=A0 null / retrieval=A1 / learned=A2)
Fixed topology per cell, k=1, NO screening, no LLM. 0-feasible rows are results, not suppressed failures.
NOVEL-10 = wl not in the store (primary set); SEEN-4 = control strip.
sim-health = fraction of ngspice evals that produced metrics (1.00 = healthy; <<1 = environment wall).

| spec | tier | split | flag | pdk | feasible | first-feasible | evals | escalated | best_obj | margins (worst) | sim-health | wl_hash | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | NOVEL | off | bptm45 | YES | propose#0 | 600 | no | -1.22 | idd_ma=0.108 | 1.00 (0/600) | 25905c563595 |  |
| cap-e02-gpsband | E | NOVEL | off | bptm45 | YES | propose#0 | 600 | no | -1.02 | s11_db=0.0681 | 1.00 (0/600) | a13885258ca3 |  |
| cap-e04-35ghz | E | NOVEL | off | bptm45 | YES | propose#0 | 600 | no | -1.32 | s11_db=0.156 | 1.00 (0/600) | f49a8abd26dd |  |
| cap-e05-ism58 | E | seen | off | bptm45 | YES | propose#0 | 600 | no | -0.674 | idd_ma=0.129 | 1.00 (0/600) | c231ac11552a |  |
| cap-e06-wifi | E | NOVEL | off | bptm45 | YES | propose#0 | 600 | no | -0.871 | idd_ma=0.0232 | 1.00 (0/600) | 0a5583e1dc5d |  |
| cap-e07-gpsband | E | NOVEL | off | bptm45 | YES | propose#0 | 600 | no | -0.644 | s11_db=0.06 | 1.00 (0/600) | 164fb57cffc4 |  |
| cap-h01-wifi | H | seen | off | bptm45 | YES | propose#0 | 600 | no | -0.541 | s21_db=0.0282 | 1.00 (0/600) | 1bf4c880c7fa |  |
| cap-h02-gpsband | H | NOVEL | off | bptm45 | YES | propose#0 | 1800 | yes | -0.141 | s11_db=0.0103 | 1.00 (0/1800) | e25b5a021ab6 |  |
| cap-h05-ism58 | H | NOVEL | off | bptm45 | YES | propose#0 | 1800 | yes | -0.25 | s11_db=0.052 | 1.00 (0/1800) | 7c8c8f9e0d2a |  |
| cap-m01-wifi | M | seen | off | bptm45 | YES | propose#0 | 600 | no | -0.609 | idd_ma=0.155 | 1.00 (0/600) | 1bf4c880c7fa |  |
| cap-m04-35ghz | M | NOVEL | off | bptm45 | YES | propose#0 | 1800 | yes | -0.57 | s21_db=0.143 | 1.00 (0/1800) | fb45bc8be87f |  |
| cap-m05-ism58 | M | seen | off | bptm45 | YES | propose#0 | 600 | no | -0.959 | idd_ma=0.256 | 1.00 (0/600) | c231ac11552a |  |
| cap-m06-wifi | M | NOVEL | off | bptm45 | YES | propose#0 | 1800 | yes | -0.286 | idd_ma=0.0265 | 1.00 (0/1800) | 642485a8fad7 |  |
| cap-m08-ism58 | M | NOVEL | off | bptm45 | YES | propose#0 | 600 | no | -0.698 | s21_db=0.315 | 1.00 (0/600) | 3a2658be7000 |  |

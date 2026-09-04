# x0-v1 results (EXPERIMENTAL -- pre-registered, not frozen)

arm = LNA_X0_PRIOR = retrieval   (off=A0 null / retrieval=A1 / learned=A2)
Fixed topology per cell, k=1, NO screening, no LLM. 0-feasible rows are results, not suppressed failures.
NOVEL-10 = wl not in the store (primary set); SEEN-4 = control strip.
sim-health = fraction of ngspice evals that produced metrics (1.00 = healthy; <<1 = environment wall).

| spec | tier | split | flag | pdk | feasible | first-feasible | evals | escalated | best_obj | margins (worst) | sim-health | wl_hash | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | NOVEL | retrieval | bptm45 | YES | propose#0 | 600 | no | -1.28 | idd_ma=0.241 | 1.00 (0/600) | 25905c563595 |  |
| cap-e02-gpsband | E | NOVEL | retrieval | bptm45 | YES | propose#0 | 1800 | yes | -1.31 | idd_ma=0.0503 | 1.00 (0/1800) | a13885258ca3 |  |
| cap-e04-35ghz | E | NOVEL | retrieval | bptm45 | YES | propose#0 | 600 | no | -1.33 | s11_db=0.0215 | 1.00 (0/600) | f49a8abd26dd |  |
| cap-e05-ism58 | E | seen | retrieval | bptm45 | YES | propose#0 | 600 | no | -1.3 | s11_db=0.331 | 1.00 (0/600) | c231ac11552a |  |
| cap-e06-wifi | E | NOVEL | retrieval | bptm45 | YES | propose#0 | 600 | no | -0.919 | idd_ma=0.134 | 1.00 (0/600) | 0a5583e1dc5d |  |
| cap-e07-gpsband | E | NOVEL | retrieval | bptm45 | YES | propose#0 | 600 | no | -0.714 | s21_db=0.197 | 1.00 (0/600) | 164fb57cffc4 |  |
| cap-h01-wifi | H | seen | retrieval | bptm45 | YES | propose#0 | 600 | no | -0.729 | s11_db=0.162 | 1.00 (0/600) | 1bf4c880c7fa |  |
| cap-h02-gpsband | H | NOVEL | retrieval | bptm45 | YES | propose#0 | 1800 | yes | -0.127 | idd_ma=0.0109 | 1.00 (0/1800) | e25b5a021ab6 |  |
| cap-h05-ism58 | H | NOVEL | retrieval | bptm45 | YES | propose#0 | 1800 | yes | -0.317 | idd_ma=0.0424 | 1.00 (0/1800) | 7c8c8f9e0d2a |  |
| cap-m01-wifi | M | seen | retrieval | bptm45 | YES | propose#0 | 600 | no | -1.25 | idd_ma=0.183 | 1.00 (0/600) | 1bf4c880c7fa |  |
| cap-m04-35ghz | M | NOVEL | retrieval | bptm45 | YES | propose#0 | 1800 | yes | -0.669 | s11_db=0.155 | 1.00 (0/1800) | fb45bc8be87f |  |
| cap-m05-ism58 | M | seen | retrieval | bptm45 | YES | propose#0 | 600 | no | -1.11 | idd_ma=0.285 | 1.00 (0/600) | c231ac11552a |  |
| cap-m06-wifi | M | NOVEL | retrieval | bptm45 | YES | propose#0 | 600 | no | -0.0686 | idd_ma=0.00338 | 1.00 (0/600) | 642485a8fad7 |  |
| cap-m08-ism58 | M | NOVEL | retrieval | bptm45 | YES | propose#0 | 600 | no | -0.615 | idd_ma=0.0831 | 1.00 (0/600) | 3a2658be7000 |  |

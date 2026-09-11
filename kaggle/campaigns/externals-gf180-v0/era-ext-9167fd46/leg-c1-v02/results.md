# x0-v1 results (EXPERIMENTAL -- pre-registered, not frozen)

arm = LNA_X0_PRIOR = (unset -> off/A0)   (off=A0 null / retrieval=A1 / learned=A2)
Fixed topology per cell, k=1, NO screening, no LLM. 0-feasible rows are results, not suppressed failures.
NOVEL-10 = wl not in the store (primary set); SEEN-4 = control strip.
sim-health = fraction of ngspice evals that produced metrics (1.00 = healthy; <<1 = environment wall).

| spec | tier | split | flag | pdk | feasible | first-feasible | evals | escalated | best_obj | margins (worst) | sim-health | wl_hash | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | NOVEL | off | gf180mcu | YES | propose#0 | 600 | no | -1.3 | s11_db=0.186 | 1.00 (0/600) | dcda50191d7c |  |
| cap-e02-gpsband | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 1.02 | s21_db=-0.0208 | 1.00 (0/1800) | dcda50191d7c | HARD FAILURE after escalation; infeasible (closest |
| cap-e03-900mhz | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 1.71 | s21_db=-0.387 | 1.00 (0/1800) | dcda50191d7c | HARD FAILURE after escalation; infeasible (closest |
| cap-e04-35ghz | E | NOVEL | off | gf180mcu | YES | propose#0 | 1800 | yes | -0.863 | s21_db=0.388 | 1.00 (0/1800) | dcda50191d7c |  |
| cap-e05-ism58 | E | NOVEL | off | gf180mcu | YES | propose#0 | 600 | no | -1.36 | nf_db=0.598 | 1.00 (0/600) | dcda50191d7c |  |
| cap-e06-wifi | E | NOVEL | off | gf180mcu | YES | propose#0 | 1800 | yes | -1.3 | s11_db=0.19 | 1.00 (0/1800) | dcda50191d7c |  |
| cap-e07-gpsband | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 1.83 | s11_db=-0.828 | 1.00 (0/1800) | dcda50191d7c | HARD FAILURE after escalation; infeasible (closest |
| cap-e08-wideband | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.53 | s11_max_db=-0.989 | 1.00 (0/1800) | dcda50191d7c | HARD FAILURE after escalation; infeasible (closest |
| cap-m01-wifi | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 1.67 | s11_db=-0.672 | 1.00 (0/1800) | dcda50191d7c | HARD FAILURE after escalation; infeasible (closest |
| cap-m02-gpsband | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.01 | s11_db=-0.962 | 1.00 (0/1800) | dcda50191d7c | HARD FAILURE after escalation; infeasible (closest |
| cap-m03-900mhz | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.38 | s11_db=-0.993 | 1.00 (0/1800) | dcda50191d7c | HARD FAILURE after escalation; infeasible (closest |
| cap-m04-35ghz | M | NOVEL | off | gf180mcu | YES | propose#0 | 1800 | yes | -0.742 | s11_db=0.23 | 1.00 (0/1800) | dcda50191d7c |  |
| cap-m05-ism58 | M | NOVEL | off | gf180mcu | YES | propose#0 | 600 | no | -0.719 | idd_ma=0.24 | 1.00 (0/600) | dcda50191d7c |  |
| cap-m06-wifi | M | NOVEL | off | gf180mcu | YES | propose#0 | 1800 | yes | -0.562 | idd_ma=0.0296 | 1.00 (0/1800) | dcda50191d7c |  |
| cap-m07-gpsband | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.22 | s11_db=-0.934 | 1.00 (0/1800) | dcda50191d7c | HARD FAILURE after escalation; infeasible (closest |
| cap-m08-ism58 | M | NOVEL | off | gf180mcu | YES | propose#0 | 1800 | yes | -0.92 | s11_db=0.101 | 1.00 (0/1800) | dcda50191d7c |  |
| cap-h01-wifi | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 1.21 | nf_db=-0.212 | 1.00 (0/1800) | dcda50191d7c | HARD FAILURE after escalation; infeasible (closest |
| cap-h02-gpsband | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.31 | s11_db=-0.982 | 1.00 (0/1800) | dcda50191d7c | HARD FAILURE after escalation; infeasible (closest |
| cap-h03-900mhz | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.9 | s11_db=-0.982 | 1.00 (0/1800) | dcda50191d7c | HARD FAILURE after escalation; infeasible (closest |
| cap-h04-35ghz | H | NOVEL | off | gf180mcu | YES | propose#0 | 1800 | yes | -0.365 | s11_db=0.033 | 1.00 (0/1800) | dcda50191d7c |  |
| cap-h05-ism58 | H | NOVEL | off | gf180mcu | YES | propose#0 | 1800 | yes | -0.572 | s21_db=0.0637 | 1.00 (0/1800) | dcda50191d7c |  |
| cap-h06-wifi | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 1.59 | nf_db=-0.333 | 1.00 (0/1800) | dcda50191d7c | HARD FAILURE after escalation; infeasible (closest |
| cap-h07-gpsband | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.74 | s11_db=-0.951 | 1.00 (0/1800) | dcda50191d7c | HARD FAILURE after escalation; infeasible (closest |
| cap-h08-wideband | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 3.67 | s11_max_db=-0.991 | 1.00 (0/1800) | dcda50191d7c | HARD FAILURE after escalation; infeasible (closest |

# x0-v1 results (EXPERIMENTAL -- pre-registered, not frozen)

arm = LNA_X0_PRIOR = (unset -> off/A0)   (off=A0 null / retrieval=A1 / learned=A2)
Fixed topology per cell, k=1, NO screening, no LLM. 0-feasible rows are results, not suppressed failures.
NOVEL-10 = wl not in the store (primary set); SEEN-4 = control strip.
sim-health = fraction of ngspice evals that produced metrics (1.00 = healthy; <<1 = environment wall).

| spec | tier | split | flag | pdk | feasible | first-feasible | evals | escalated | best_obj | margins (worst) | sim-health | wl_hash | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | NOVEL | off | gf180mcu | YES | propose#0 | 600 | no | -0.79 | idd_ma=0.168 | 1.00 (0/600) | 226544590d47 |  |
| cap-e02-gpsband | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 1.43 | s11_db=-0.427 | 1.00 (0/1800) | 226544590d47 | HARD FAILURE after escalation; infeasible (closest |
| cap-e03-900mhz | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.08 | s11_db=-0.739 | 1.00 (0/1800) | 226544590d47 | HARD FAILURE after escalation; infeasible (closest |
| cap-e04-35ghz | E | NOVEL | off | gf180mcu | YES | propose#0 | 1800 | yes | -0.791 | s21_db=0.176 | 1.00 (0/1800) | 226544590d47 |  |
| cap-e05-ism58 | E | NOVEL | off | gf180mcu | YES | propose#0 | 1800 | yes | -0.648 | s21_db=0.0896 | 1.00 (0/1800) | 226544590d47 |  |
| cap-e06-wifi | E | NOVEL | off | gf180mcu | YES | propose#0 | 600 | no | -0.372 | s21_db=0.113 | 1.00 (0/600) | 226544590d47 |  |
| cap-e07-gpsband | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 1.74 | s11_db=-0.741 | 1.00 (0/1800) | 226544590d47 | HARD FAILURE after escalation; infeasible (closest |
| cap-e08-wideband | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.07 | s11_max_db=-0.597 | 1.00 (0/1800) | 226544590d47 | HARD FAILURE after escalation; infeasible (closest |
| cap-m01-wifi | M | NOVEL | off | gf180mcu | YES | propose#0 | 600 | no | -0.328 | nf_db=0.0626 | 1.00 (0/600) | 226544590d47 |  |
| cap-m02-gpsband | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.23 | s11_db=-0.841 | 1.00 (0/1800) | 226544590d47 | HARD FAILURE after escalation; infeasible (closest |
| cap-m03-900mhz | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 3.3 | s11_db=-0.977 | 1.00 (0/1800) | 226544590d47 | HARD FAILURE after escalation; infeasible (closest |
| cap-m04-35ghz | M | NOVEL | off | gf180mcu | YES | propose#0 | 1800 | yes | -0.125 | s21_db=0.00855 | 1.00 (0/1800) | 226544590d47 |  |
| cap-m05-ism58 | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 1.19 | s21_db=-0.186 | 1.00 (0/1800) | 226544590d47 | HARD FAILURE after escalation; infeasible (closest |
| cap-m06-wifi | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 1 | s21_db=-0.000567 | 1.00 (0/1800) | 226544590d47 | HARD FAILURE after escalation; infeasible (closest |
| cap-m07-gpsband | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.57 | s11_db=-0.846 | 1.00 (0/1800) | 226544590d47 | HARD FAILURE after escalation; infeasible (closest |
| cap-m08-ism58 | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 1.25 | s21_db=-0.254 | 1.00 (0/1800) | 226544590d47 | HARD FAILURE after escalation; infeasible (closest |
| cap-h01-wifi | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 1.43 | s11_db=-0.242 | 1.00 (0/1800) | 226544590d47 | HARD FAILURE after escalation; infeasible (closest |
| cap-h02-gpsband | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 3.39 | nf_db=-1.1 | 1.00 (0/1800) | 226544590d47 | HARD FAILURE after escalation; infeasible (closest |
| cap-h03-900mhz | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 3.95 | nf_db=-1.25 | 1.00 (0/1800) | 226544590d47 | HARD FAILURE after escalation; infeasible (closest |
| cap-h04-35ghz | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 1.32 | s21_db=-0.241 | 1.00 (0/1800) | 226544590d47 | HARD FAILURE after escalation; infeasible (closest |
| cap-h05-ism58 | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 1.58 | s21_db=-0.392 | 1.00 (0/1800) | 226544590d47 | HARD FAILURE after escalation; infeasible (closest |
| cap-h06-wifi | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 1.44 | nf_db=-0.259 | 1.00 (0/1800) | 226544590d47 | HARD FAILURE after escalation; infeasible (closest |
| cap-h07-gpsband | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 3.61 | nf_db=-1.19 | 1.00 (0/1800) | 226544590d47 | HARD FAILURE after escalation; infeasible (closest |
| cap-h08-wideband | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 3.56 | s11_max_db=-0.98 | 1.00 (0/1800) | 226544590d47 | HARD FAILURE after escalation; infeasible (closest |

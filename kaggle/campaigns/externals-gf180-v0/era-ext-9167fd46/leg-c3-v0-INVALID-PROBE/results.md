# x0-v1 results (EXPERIMENTAL -- pre-registered, not frozen)

arm = LNA_X0_PRIOR = (unset -> off/A0)   (off=A0 null / retrieval=A1 / learned=A2)
Fixed topology per cell, k=1, NO screening, no LLM. 0-feasible rows are results, not suppressed failures.
NOVEL-10 = wl not in the store (primary set); SEEN-4 = control strip.
sim-health = fraction of ngspice evals that produced metrics (1.00 = healthy; <<1 = environment wall).

| spec | tier | split | flag | pdk | feasible | first-feasible | evals | escalated | best_obj | margins (worst) | sim-health | wl_hash | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 5.07 | s21_db=-2.39 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-e02-gpsband | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 10.6 | nf_db=-5.47 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-e03-900mhz | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 14 | nf_db=-8.01 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-e04-35ghz | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 4.57 | s21_db=-1.8 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-e05-ism58 | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.24 | s21_db=-1.22 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-e06-wifi | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 5.4 | nf_db=-2.23 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-e07-gpsband | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 11.4 | nf_db=-6.55 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-e08-wideband | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 18.2 | nf_db=-9.49 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-m01-wifi | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 6.63 | nf_db=-3.64 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-m02-gpsband | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 13.8 | nf_db=-9.3 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-m03-900mhz | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 16.8 | nf_db=-11.6 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-m04-35ghz | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 5.48 | nf_db=-2.63 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-m05-ism58 | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.22 | s21_db=-1.18 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-m06-wifi | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 6.75 | nf_db=-3.71 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-m07-gpsband | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 14.8 | nf_db=-10.3 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-m08-ism58 | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.27 | s21_db=-1.16 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-h01-wifi | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 7.69 | nf_db=-4.48 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-h02-gpsband | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 14.8 | nf_db=-10.3 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-h03-900mhz | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 23.5 | nf_db=-18.7 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-h04-35ghz | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 7.32 | nf_db=-4.19 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-h05-ism58 | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 3.02 | s21_db=-1.12 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-h06-wifi | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 8.74 | nf_db=-5.49 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-h07-gpsband | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 18.2 | nf_db=-14.1 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |
| cap-h08-wideband | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 20.4 | nf_db=-11.7 | 1.00 (0/1800) | 776e0dbed858 | HARD FAILURE after escalation; infeasible (closest |

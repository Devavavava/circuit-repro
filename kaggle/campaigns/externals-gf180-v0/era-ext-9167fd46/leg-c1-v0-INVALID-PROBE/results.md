# x0-v1 results (EXPERIMENTAL -- pre-registered, not frozen)

arm = LNA_X0_PRIOR = (unset -> off/A0)   (off=A0 null / retrieval=A1 / learned=A2)
Fixed topology per cell, k=1, NO screening, no LLM. 0-feasible rows are results, not suppressed failures.
NOVEL-10 = wl not in the store (primary set); SEEN-4 = control strip.
sim-health = fraction of ngspice evals that produced metrics (1.00 = healthy; <<1 = environment wall).

| spec | tier | split | flag | pdk | feasible | first-feasible | evals | escalated | best_obj | margins (worst) | sim-health | wl_hash | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 23.1 | nf_db=-14.8 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-e02-gpsband | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 27.1 | nf_db=-17.7 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-e03-900mhz | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 30.8 | nf_db=-20.4 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-e04-35ghz | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 17.4 | nf_db=-11.2 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-e05-ism58 | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 15.4 | nf_db=-9.21 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-e06-wifi | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 24.9 | nf_db=-17.5 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-e07-gpsband | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 28.9 | nf_db=-20.6 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-e08-wideband | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 38.8 | nf_db=-21.4 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-m01-wifi | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 28.7 | nf_db=-21.2 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-m02-gpsband | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 35.9 | nf_db=-28.4 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-m03-900mhz | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 37.2 | nf_db=-28.9 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-m04-35ghz | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 18.6 | nf_db=-13.7 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-m05-ism58 | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 19.5 | nf_db=-12.5 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-m06-wifi | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 30.7 | nf_db=-24.2 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-m07-gpsband | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 38.6 | nf_db=-31.4 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-m08-ism58 | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 15.4 | nf_db=-10.4 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-h01-wifi | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 36.1 | nf_db=-29.8 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-h02-gpsband | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 42.7 | nf_db=-35.7 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-h03-900mhz | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 53.1 | nf_db=-45.7 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-h04-35ghz | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 26.4 | nf_db=-21.9 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-h05-ism58 | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 20.5 | nf_db=-15.8 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-h06-wifi | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 42 | nf_db=-36 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-h07-gpsband | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 48.4 | nf_db=-42.2 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |
| cap-h08-wideband | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 47.8 | nf_db=-30.4 | 1.00 (0/1800) | 59447359f981 | HARD FAILURE after escalation; infeasible (closest |

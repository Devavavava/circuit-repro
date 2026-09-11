# x0-v1 results (EXPERIMENTAL -- pre-registered, not frozen)

arm = LNA_X0_PRIOR = (unset -> off/A0)   (off=A0 null / retrieval=A1 / learned=A2)
Fixed topology per cell, k=1, NO screening, no LLM. 0-feasible rows are results, not suppressed failures.
NOVEL-10 = wl not in the store (primary set); SEEN-4 = control strip.
sim-health = fraction of ngspice evals that produced metrics (1.00 = healthy; <<1 = environment wall).

| spec | tier | split | flag | pdk | feasible | first-feasible | evals | escalated | best_obj | margins (worst) | sim-health | wl_hash | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.27 | s11_db=-0.816 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-e02-gpsband | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.36 | s11_db=-0.934 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-e03-900mhz | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.57 | s11_db=-0.981 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-e04-35ghz | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.44 | s11_db=-0.816 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-e05-ism58 | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.62 | s11_db=-0.966 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-e06-wifi | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.7 | s11_db=-0.893 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-e07-gpsband | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.93 | s11_db=-0.96 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-e08-wideband | E | NOVEL | off | gf180mcu | no | - | 1800 | yes | 2.61 | s11_max_db=-0.989 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-m01-wifi | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 4.14 | nf_db=-1.13 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-m02-gpsband | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 4.21 | nf_db=-1.38 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-m03-900mhz | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 3.79 | nf_db=-0.988 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-m04-35ghz | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 4.22 | nf_db=-1.81 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-m05-ism58 | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 3.12 | s11_db=-0.983 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-m06-wifi | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 3.97 | nf_db=-1.17 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-m07-gpsband | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 4.64 | nf_db=-1.77 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-m08-ism58 | M | NOVEL | off | gf180mcu | no | - | 1800 | yes | 3.34 | s11_db=-0.984 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-h01-wifi | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 5.32 | nf_db=-1.96 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-h02-gpsband | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 5.25 | nf_db=-2.21 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-h03-900mhz | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 5.31 | nf_db=-2.37 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-h04-35ghz | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 5.92 | nf_db=-3.37 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-h05-ism58 | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 4.5 | nf_db=-1.63 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-h06-wifi | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 5.21 | nf_db=-2.21 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-h07-gpsband | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 5.86 | nf_db=-2.69 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |
| cap-h08-wideband | H | NOVEL | off | gf180mcu | no | - | 1800 | yes | 3.88 | nf_db=-1.03 | 1.00 (0/1800) | a6122feb26e8 | HARD FAILURE after escalation; infeasible (closest |

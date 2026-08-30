# capability results (EXPERIMENTAL -- not frozen) -- variant=arch -- pdk=gf180mcu

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.
stages = bias/sized/feasible counts over the candidates a spec walked (the cross-PDK funnel-rate signal).

| spec | tier | arm | variant | pdk | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | stages(b/s/f of n) | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | B | arch | gf180mcu | YES | concentrate | 5 | 2280 | yes | -0.598 | idd_ma=0.21 | 6/6/2 of 7 | - | unconditional |  |
| cap-e02-gpsband | E | B | arch | gf180mcu | no | - | - | 4080 | yes | 2.02 | s21_db=-1.02 | 8/8/0 of 12 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e03-900mhz | E | B | arch | gf180mcu | no | - | - | 9480 | yes | 9.39 | nf_db=-5.32 | 14/14/0 of 15 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e04-35ghz | E | B | arch | gf180mcu | no | - | - | 9360 | yes | 3.19 | s21_db=-1.29 | 13/13/0 of 15 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e05-ism58 | E | B | arch | gf180mcu | no | - | - | 9360 | yes | 2.15 | s21_db=-1.15 | 13/13/0 of 15 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e06-wifi | E | B | arch | gf180mcu | no | - | - | 5760 | yes | 8.12 | nf_db=-4.02 | 9/9/0 of 13 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e07-gpsband | E | B | arch | gf180mcu | no | - | - | 9360 | yes | 2.04 | s21_db=-1.04 | 13/13/0 of 15 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e08-wideband | E | B | arch | gf180mcu | no | - | - | 0 | yes | - | - | 0/0/0 of 5 | - | - | HARD FAILURE after escalation; no candidate survived triage |
| cap-m01-wifi | M | B | arch | gf180mcu | no | - | - | 9600 | yes | 2.04 | s21_db=-1.04 | 15/15/0 of 15 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m02-gpsband | M | B | arch | gf180mcu | no | - | - | 7680 | yes | 3.81 | nf_db=-1.43 | 12/12/0 of 14 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m03-900mhz | M | B | arch | gf180mcu | no | - | - | 9480 | yes | 4.25 | nf_db=-1.83 | 14/14/0 of 15 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m04-35ghz | M | B | arch | gf180mcu | no | - | - | 9480 | yes | 3.01 | s21_db=-1.4 | 14/14/0 of 15 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m05-ism58 | M | B | arch | gf180mcu | no | - | - | 5760 | yes | 2.17 | s21_db=-1.15 | 9/9/0 of 13 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m06-wifi | M | B | arch | gf180mcu | YES | concentrate | 5 | 2280 | yes | -0.126 | nf_db=0.0022 | 6/6/2 of 7 | - | unconditional |  |
| cap-m07-gpsband | M | B | arch | gf180mcu | no | - | - | 9600 | yes | 5.82 | nf_db=-3.42 | 15/15/0 of 15 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m08-ism58 | M | B | arch | gf180mcu | no | - | - | 9360 | yes | 5.18 | nf_db=-2.2 | 13/13/0 of 15 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h01-wifi | H | B | arch | gf180mcu | no | - | - | 9360 | yes | 2.61 | s21_db=-1.03 | 13/13/0 of 15 | -1.73 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h02-gpsband | H | B | arch | gf180mcu | no | - | - | 7560 | yes | 11.7 | nf_db=-8.11 | 11/11/0 of 14 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h03-900mhz | H | B | arch | gf180mcu | no | - | - | 9360 | yes | 3.1 | s21_db=-1.08 | 13/13/0 of 15 | - | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h04-35ghz | H | B | arch | gf180mcu | no | - | - | 7440 | yes | 3.35 | s21_db=-1.28 | 10/10/0 of 14 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h05-ism58 | H | B | arch | gf180mcu | no | - | - | 7560 | yes | 2.75 | s21_db=-1.13 | 11/11/0 of 14 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h06-wifi | H | B | arch | gf180mcu | no | - | - | 9240 | yes | 2.68 | s21_db=-1.03 | 12/12/0 of 15 | - | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h07-gpsband | H | B | arch | gf180mcu | no | - | - | 9480 | yes | 4.8 | nf_db=-2.47 | 14/14/0 of 15 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h08-wideband | H | B | arch | gf180mcu | no | - | - | 9360 | yes | 5.14 | nf_db=-2.2 | 13/13/0 of 15 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |

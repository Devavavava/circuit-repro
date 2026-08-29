# capability results (EXPERIMENTAL -- not frozen) -- pdk=gf180mcu

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.
stages = bias/sized/feasible counts over the candidates a spec walked (the cross-PDK funnel-rate signal).

| spec | tier | arm | variant | pdk | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | stages(b/s/f of n) | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | A | - | gf180mcu | no | - | - | 16200 | yes | 4.12 | s21_db=-1.17 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e02-gpsband | E | A | - | gf180mcu | no | - | - | 16200 | yes | 4.11 | s21_db=-1.15 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e03-900mhz | E | A | - | gf180mcu | no | - | - | 16200 | yes | 4.21 | s21_db=-1.16 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e04-35ghz | E | A | - | gf180mcu | no | - | - | 16200 | yes | 4.09 | s21_db=-1.15 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e05-ism58 | E | A | - | gf180mcu | no | - | - | 16200 | yes | 4.23 | s21_db=-1.24 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e06-wifi | E | A | - | gf180mcu | no | - | - | 16200 | yes | 4.43 | nf_db=-1.31 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e07-gpsband | E | A | - | gf180mcu | no | - | - | 16200 | yes | 4.47 | nf_db=-1.34 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e08-wideband | E | A | - | gf180mcu | no | - | - | 16200 | yes | 4.11 | s21_db=-1.15 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m01-wifi | M | A | - | gf180mcu | no | - | - | 16200 | yes | 5.19 | nf_db=-2.01 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m02-gpsband | M | A | - | gf180mcu | no | - | - | 16200 | yes | 5.56 | nf_db=-2.4 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m03-900mhz | M | A | - | gf180mcu | no | - | - | 16200 | yes | 5.18 | nf_db=-2.03 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m04-35ghz | M | A | - | gf180mcu | no | - | - | 16200 | yes | 4.78 | nf_db=-1.65 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m05-ism58 | M | A | - | gf180mcu | no | - | - | 16200 | yes | 4.26 | s21_db=-1.2 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m06-wifi | M | A | - | gf180mcu | no | - | - | 16200 | yes | 5.47 | nf_db=-2.35 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m07-gpsband | M | A | - | gf180mcu | no | - | - | 16200 | yes | 6.01 | nf_db=-2.84 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m08-ism58 | M | A | - | gf180mcu | no | - | - | 16200 | yes | 4.67 | nf_db=-1.57 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-h01-wifi | H | A | - | gf180mcu | no | - | - | 16200 | yes | 6.47 | nf_db=-3.31 | 18/18/0 of 18 | -18.28 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-h02-gpsband | H | A | - | gf180mcu | no | - | - | 16200 | yes | 6.67 | nf_db=-3.49 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-h03-900mhz | H | A | - | gf180mcu | no | - | - | 16200 | yes | 7.11 | nf_db=-3.94 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-h04-35ghz | H | A | - | gf180mcu | no | - | - | 16200 | yes | 6.5 | nf_db=-3.36 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-h05-ism58 | H | A | - | gf180mcu | no | - | - | 16200 | yes | 6.17 | nf_db=-3.03 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-h06-wifi | H | A | - | gf180mcu | no | - | - | 16200 | yes | 7.14 | nf_db=-4.02 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-h07-gpsband | H | A | - | gf180mcu | no | - | - | 16200 | yes | 7.51 | nf_db=-4.31 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-h08-wideband | H | A | - | gf180mcu | no | - | - | 16200 | yes | 5.14 | nf_db=-2.01 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |

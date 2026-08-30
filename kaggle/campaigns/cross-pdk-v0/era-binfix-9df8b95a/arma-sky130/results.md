# capability results (EXPERIMENTAL -- not frozen) -- pdk=sky130

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.
stages = bias/sized/feasible counts over the candidates a spec walked (the cross-PDK funnel-rate signal).

| spec | tier | arm | variant | pdk | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | stages(b/s/f of n) | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | A | - | sky130 | no | - | - | 16200 | yes | 3.7 | s11_db=-0.98 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e02-gpsband | E | A | - | sky130 | no | - | - | 16200 | yes | 3.75 | s11_db=-0.991 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e03-900mhz | E | A | - | sky130 | no | - | - | 16200 | yes | 3.92 | nf_db=-0.994 | 18/18/0 of 18 | +6.98 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e04-35ghz | E | A | - | sky130 | no | - | - | 16200 | yes | 3.73 | s11_db=-0.969 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e05-ism58 | E | A | - | sky130 | no | - | - | 16200 | yes | 3.75 | s21_db=-0.944 | 18/18/0 of 18 | +18.68 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e06-wifi | E | A | - | sky130 | no | - | - | 16200 | yes | 4.02 | nf_db=-1.13 | 18/18/0 of 18 | +4.21 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e07-gpsband | E | A | - | sky130 | no | - | - | 16200 | yes | 4.09 | nf_db=-1.18 | 18/18/0 of 18 | -2.77 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e08-wideband | E | A | - | sky130 | no | - | - | 16200 | yes | 3.74 | s11_max_db=-0.997 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m01-wifi | M | A | - | sky130 | no | - | - | 16200 | yes | 4.61 | nf_db=-1.68 | 18/18/0 of 18 | +6.60 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m02-gpsband | M | A | - | sky130 | no | - | - | 16200 | yes | 5.03 | nf_db=-2.09 | 18/18/0 of 18 | +8.21 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m03-900mhz | M | A | - | sky130 | no | - | - | 16200 | yes | 4.82 | nf_db=-1.86 | 18/18/0 of 18 | +10.35 | conditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m04-35ghz | M | A | - | sky130 | no | - | - | 16200 | yes | 4.28 | nf_db=-1.36 | 18/18/0 of 18 | +11.77 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m05-ism58 | M | A | - | sky130 | no | - | - | 16200 | yes | 3.82 | s21_db=-0.97 | 18/18/0 of 18 | +5.77 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m06-wifi | M | A | - | sky130 | no | - | - | 16200 | yes | 4.92 | nf_db=-1.99 | 18/18/0 of 18 | +10.75 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |

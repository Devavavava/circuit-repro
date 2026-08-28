# capability results (EXPERIMENTAL -- not frozen) -- pdk=sky130

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.
stages = bias/sized/feasible counts over the candidates a spec walked (the cross-PDK funnel-rate signal).

| spec | tier | arm | variant | pdk | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | stages(b/s/f of n) | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | A | - | sky130 | no | - | - | 16200 | yes | 23.6 | nf_db=-15.5 | 18/18/0 of 18 | +4.53 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e02-gpsband | E | A | - | sky130 | no | - | - | 16200 | yes | 20.4 | nf_db=-13.3 | 18/18/0 of 18 | -15.94 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e03-900mhz | E | A | - | sky130 | no | - | - | 16200 | yes | 26.4 | nf_db=-17.6 | 18/18/0 of 18 | +1.30 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e04-35ghz | E | A | - | sky130 | no | - | - | 16200 | yes | 15.5 | nf_db=-9.98 | 18/18/0 of 18 | +3.16 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e05-ism58 | E | A | - | sky130 | no | - | - | 16200 | yes | 15.1 | nf_db=-9.17 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e06-wifi | E | A | - | sky130 | no | - | - | 16200 | yes | 25.5 | nf_db=-18.2 | 18/18/0 of 18 | +3.43 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e07-gpsband | E | A | - | sky130 | no | - | - | 16200 | yes | 22.4 | nf_db=-15.9 | 18/18/0 of 18 | -18.24 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e08-wideband | E | A | - | sky130 | no | - | - | 16200 | yes | 29 | nf_db=-19.5 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m01-wifi | M | A | - | sky130 | no | - | - | 16200 | yes | 29.4 | nf_db=-22.1 | 18/18/0 of 18 | +4.23 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m02-gpsband | M | A | - | sky130 | no | - | - | 16200 | yes | 27.5 | nf_db=-21.7 | 18/18/0 of 18 | -17.18 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m03-900mhz | M | A | - | sky130 | no | - | - | 16200 | yes | 32.3 | nf_db=-25.1 | 18/18/0 of 18 | +2.29 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m04-35ghz | M | A | - | sky130 | no | - | - | 16200 | yes | 17.7 | nf_db=-12.5 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m05-ism58 | M | A | - | sky130 | no | - | - | 16200 | yes | 14.5 | nf_db=-9.13 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m06-wifi | M | A | - | sky130 | no | - | - | 16200 | yes | 31.7 | nf_db=-25.2 | 18/18/0 of 18 | +4.23 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |

# capability results (EXPERIMENTAL -- not frozen) -- pdk=sky130

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.
stages = bias/sized/feasible counts over the candidates a spec walked (the cross-PDK funnel-rate signal).

| spec | tier | arm | variant | pdk | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | stages(b/s/f of n) | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | A | - | sky130 | no | - | - | 16200 | yes | 9.08 | nf_db=-4.7 | 18/18/0 of 18 | +14.87 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e02-gpsband | E | A | - | sky130 | no | - | - | 16200 | yes | 9.03 | nf_db=-4.67 | 18/18/0 of 18 | +15.72 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e03-900mhz | E | A | - | sky130 | no | - | - | 16200 | yes | 9.1 | nf_db=-4.73 | 18/18/0 of 18 | +16.31 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e04-35ghz | E | A | - | sky130 | no | - | - | 16200 | yes | 8.79 | nf_db=-4.65 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e05-ism58 | E | A | - | sky130 | no | - | - | 16200 | yes | 4.89 | nf_db=-2.15 | 18/18/0 of 18 | +12.06 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e06-wifi | E | A | - | sky130 | no | - | - | 16200 | yes | 9.74 | nf_db=-5.59 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e07-gpsband | E | A | - | sky130 | no | - | - | 16200 | yes | 9.84 | nf_db=-5.69 | 18/18/0 of 18 | +13.33 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-e08-wideband | E | A | - | sky130 | no | - | - | 16200 | yes | 9.14 | nf_db=-4.77 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m01-wifi | M | A | - | sky130 | no | - | - | 16200 | yes | 11.2 | nf_db=-7 | 18/18/0 of 18 | +12.87 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m02-gpsband | M | A | - | sky130 | no | - | - | 16200 | yes | 12.1 | nf_db=-8.15 | 18/18/0 of 18 | +14.01 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m03-900mhz | M | A | - | sky130 | no | - | - | 16200 | yes | 11 | nf_db=-7.04 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m04-35ghz | M | A | - | sky130 | no | - | - | 16200 | yes | 10 | nf_db=-6.03 | 18/18/0 of 18 | - | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m05-ism58 | M | A | - | sky130 | no | - | - | 16200 | yes | 8.79 | nf_db=-4.64 | 18/18/0 of 18 | +15.88 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m06-wifi | M | A | - | sky130 | no | - | - | 16200 | yes | 12 | nf_db=-8.11 | 18/18/0 of 18 | +12.76 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |

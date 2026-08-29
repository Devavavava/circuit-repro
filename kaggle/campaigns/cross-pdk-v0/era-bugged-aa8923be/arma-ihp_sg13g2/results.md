# capability results (EXPERIMENTAL -- not frozen) -- pdk=ihp_sg13g2

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.
stages = bias/sized/feasible counts over the candidates a spec walked (the cross-PDK funnel-rate signal).

| spec | tier | arm | variant | pdk | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | stages(b/s/f of n) | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | A | - | ihp_sg13g2 | YES | corpus#ace8383c | 11 | 2750 | no | -1.92 | s11_db=0.232 | 12/12/1 of 12 | -12.47 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e02-gpsband | E | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 9 | 2250 | no | -1.95 | idd_ma=0.346 | 12/12/2 of 12 | -15.76 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e03-900mhz | E | A | - | ihp_sg13g2 | YES | corpus#ace8383c | 11 | 2750 | no | -2.42 | s11_db=0.133 | 12/12/2 of 12 | -23.79 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e04-35ghz | E | A | - | ihp_sg13g2 | YES | corpus#ace8383c | 11 | 2750 | no | -0.818 | s11_db=0.0127 | 12/12/1 of 12 | -12.47 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e05-ism58 | E | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 13 | 11700 | yes | -0.65 | s11_db=0.00706 | 18/18/3 of 18 | -5.48 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-e06-wifi | E | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 14 | 12600 | yes | -1.54 | s11_db=0.0164 | 18/18/4 of 18 | -10.44 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-e07-gpsband | E | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 9 | 2250 | no | -1.59 | s11_db=0.0901 | 12/12/3 of 12 | -14.15 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e08-wideband | E | A | - | ihp_sg13g2 | no | - | - | 16200 | yes | 1.16 | s11_max_db=-0.158 | 18/18/0 of 18 | -17.03 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m01-wifi | M | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 13 | 11700 | yes | -1.57 | s11_db=0.0545 | 18/18/5 of 18 | -14.28 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-m02-gpsband | M | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 13 | 11700 | yes | -1.4 | s11_db=0.00668 | 18/18/4 of 18 | -17.44 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-m03-900mhz | M | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 13 | 11700 | yes | -1.65 | s11_db=0.0373 | 18/18/6 of 18 | -29.31 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-m04-35ghz | M | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 15 | 13500 | yes | -0.351 | s11_db=0.00281 | 18/18/2 of 18 | -7.03 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-m05-ism58 | M | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 14 | 12600 | yes | -0.171 | s21_db=0.0234 | 18/18/2 of 18 | -3.16 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |

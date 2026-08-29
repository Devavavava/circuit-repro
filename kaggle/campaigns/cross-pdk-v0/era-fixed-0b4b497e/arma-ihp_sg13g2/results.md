# capability results (EXPERIMENTAL -- not frozen) -- pdk=ihp_sg13g2

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.
stages = bias/sized/feasible counts over the candidates a spec walked (the cross-PDK funnel-rate signal).

| spec | tier | arm | variant | pdk | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | stages(b/s/f of n) | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 10 | 2500 | no | -2.27 | nf_db=0.51 | 12/12/3 of 12 | -13.91 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e02-gpsband | E | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 9 | 2250 | no | -2 | nf_db=0.384 | 12/12/4 of 12 | -20.62 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e03-900mhz | E | A | - | ihp_sg13g2 | YES | corpus#ace8383c | 11 | 2750 | no | -2.18 | nf_db=0.0975 | 12/12/2 of 12 | -23.86 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e04-35ghz | E | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 13 | 11700 | yes | -2.43 | nf_db=0.675 | 18/18/6 of 18 | -4.81 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-e05-ism58 | E | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 13 | 11700 | yes | -2.38 | nf_db=0.582 | 18/18/6 of 18 | +6.07 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-e06-wifi | E | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 10 | 2500 | no | -1.83 | s11_db=0.0758 | 12/12/1 of 12 | -11.57 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e07-gpsband | E | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 10 | 2500 | no | -1.3 | nf_db=0.377 | 12/12/2 of 12 | -17.13 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e08-wideband | E | A | - | ihp_sg13g2 | YES | corpus#ace8383c | 17 | 15300 | yes | -1.07 | s11_max_db=0.102 | 18/18/1 of 18 | -16.04 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-m01-wifi | M | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 10 | 2500 | no | -1.28 | idd_ma=0.165 | 12/12/3 of 12 | -12.85 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m02-gpsband | M | A | - | ihp_sg13g2 | YES | corpus#ace8383c | 12 | 3000 | no | -0.509 | nf_db=0.00164 | 12/12/1 of 12 | -22.36 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m03-900mhz | M | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 10 | 2500 | no | -0.59 | nf_db=0.0859 | 12/12/1 of 12 | -20.40 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m04-35ghz | M | A | - | ihp_sg13g2 | YES | corpus#ace8383c | 12 | 3000 | no | -1.06 | s11_db=0.177 | 12/12/1 of 12 | -8.52 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m05-ism58 | M | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 13 | 11700 | yes | -1.71 | nf_db=0.524 | 18/18/6 of 18 | +4.32 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-m06-wifi | M | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 13 | 11700 | yes | -1.66 | s11_db=0.101 | 18/18/6 of 18 | -6.36 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-m07-gpsband | M | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 13 | 11700 | yes | -1.19 | idd_ma=0.0634 | 18/18/6 of 18 | -25.78 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-m08-ism58 | M | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 13 | 11700 | yes | -1.37 | idd_ma=0.369 | 18/18/6 of 18 | +6.90 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h01-wifi | H | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 13 | 11700 | yes | -0.982 | s11_db=0.239 | 18/18/5 of 18 | -11.99 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h02-gpsband | H | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 13 | 11700 | yes | -0.631 | s11_db=0.0492 | 18/18/5 of 18 | -21.35 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h03-900mhz | H | A | - | ihp_sg13g2 | YES | corpus#ace8383c | 17 | 15300 | yes | -0.489 | nf_db=0.072 | 18/18/2 of 18 | -20.89 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h04-35ghz | H | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 9 | 2250 | no | -0.789 | nf_db=0.334 | 12/12/1 of 12 | -5.70 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-h05-ism58 | H | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 13 | 11700 | yes | -1.06 | nf_db=0.396 | 18/18/5 of 18 | +1.63 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h06-wifi | H | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 13 | 11700 | yes | -0.725 | s11_db=0.056 | 18/18/5 of 18 | -3.43 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h07-gpsband | H | A | - | ihp_sg13g2 | YES | corpus#182aa0c7 | 15 | 13500 | yes | -0.2 | s11_db=0.0104 | 18/18/2 of 18 | -18.92 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h08-wideband | H | A | - | ihp_sg13g2 | no | - | - | 16200 | yes | 1.73 | s11_max_db=-0.318 | 18/18/0 of 18 | -15.80 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |

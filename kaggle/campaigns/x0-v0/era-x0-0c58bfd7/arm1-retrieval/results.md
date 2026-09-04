# capability results (EXPERIMENTAL -- not frozen)

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.
stages = bias/sized/feasible counts over the candidates a spec walked (the cross-PDK funnel-rate signal).
sim-health = per-stage sim-success rate over the sized candidates' ngspice evals (1.00 = every eval simulated; <<1 = ENVIRONMENT wall, not a design miss). '-' = no sized candidate / no-sim run.

| spec | tier | arm | variant | pdk | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | stages(b/s/f of n) | sim-health | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -2.55 | idd_ma=0.0302 | 12/12/6 of 12 | 1.00 (0/3000) | -30.35 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e02-gpsband | E | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -3.2 | s11_db=0.149 | 12/12/6 of 12 | 1.00 (0/3000) | -34.05 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e03-900mhz | E | A | - | bptm45 | YES | corpus#182aa0c7 | 9 | 2250 | no | -2.83 | nf_db=0.0185 | 12/12/4 of 12 | 1.00 (0/3000) | -40.35 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e04-35ghz | E | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -2.17 | s11_db=0.18 | 12/12/6 of 12 | 1.00 (0/3000) | -31.45 | conditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e05-ism58 | E | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -2.07 | nf_db=0.27 | 12/12/6 of 12 | 1.00 (0/3000) | -25.45 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e06-wifi | E | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -1.72 | nf_db=0.000807 | 12/12/6 of 12 | 1.00 (0/3000) | -38.39 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e07-gpsband | E | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -2.15 | s11_db=0.118 | 12/12/6 of 12 | 1.00 (0/3000) | -35.63 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e08-wideband | E | A | - | bptm45 | no | - | - | 16200 | yes | 1.27 | s11_max_db=-0.271 | 18/18/0 of 18 | 1.00 (0/16200) | -22.58 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m01-wifi | M | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -1.29 | idd_ma=0.0155 | 12/12/4 of 12 | 1.00 (0/3000) | -30.36 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m02-gpsband | M | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -0.796 | s11_db=0.00782 | 12/12/4 of 12 | 1.00 (0/3000) | -30.18 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m03-900mhz | M | A | - | bptm45 | YES | corpus#ace8383c | 11 | 2750 | no | -1.23 | nf_db=0.109 | 12/12/1 of 12 | 1.00 (0/3000) | -34.49 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m04-35ghz | M | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -1.53 | idd_ma=0.203 | 12/12/5 of 12 | 1.00 (0/3000) | -34.35 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m05-ism58 | M | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -1.52 | idd_ma=0.0634 | 12/12/6 of 12 | 1.00 (0/3000) | -26.88 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m06-wifi | M | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -0.784 | idd_ma=0.0144 | 12/12/3 of 12 | 1.00 (0/3000) | -31.80 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m07-gpsband | M | A | - | bptm45 | YES | corpus#1403690f | 6 | 1500 | no | -0.314 | idd_ma=0.0349 | 12/12/1 of 12 | 1.00 (0/3000) | -11.09 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m08-ism58 | M | A | - | bptm45 | YES | corpus#ace8383c | 11 | 2750 | no | -0.782 | nf_db=0.00784 | 12/12/2 of 12 | 1.00 (0/3000) | -24.58 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-h01-wifi | H | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -0.305 | s21_db=0.0386 | 12/12/2 of 12 | 1.00 (0/3000) | -12.57 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-h02-gpsband | H | A | - | bptm45 | YES | corpus#1403690f | 7 | 6300 | yes | -0.258 | s11_db=0.0167 | 18/18/4 of 18 | 1.00 (0/16200) | -32.71 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h03-900mhz | H | A | - | bptm45 | no | - | - | 16200 | yes | 1.07 | nf_db=-0.0735 | 18/18/0 of 18 | 1.00 (0/16200) | -31.22 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-h04-35ghz | H | A | - | bptm45 | YES | corpus#1403690f | 8 | 7200 | yes | -0.494 | idd_ma=0.00294 | 18/18/4 of 18 | 1.00 (0/16200) | -8.91 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h05-ism58 | H | A | - | bptm45 | YES | corpus#182aa0c7 | 13 | 11700 | yes | -0.996 | idd_ma=0.00352 | 18/18/5 of 18 | 1.00 (0/16200) | -35.92 | conditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h06-wifi | H | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -0.353 | s11_db=0.00745 | 12/12/1 of 12 | 1.00 (0/3000) | -9.35 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-h07-gpsband | H | A | - | bptm45 | no | - | - | 16200 | yes | 1.09 | nf_db=-0.0919 | 18/18/0 of 18 | 1.00 (0/16200) | -34.51 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-h08-wideband | H | A | - | bptm45 | no | - | - | 16200 | yes | 2.46 | s11_max_db=-0.974 | 18/18/0 of 18 | 1.00 (0/16200) | +3.69 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |

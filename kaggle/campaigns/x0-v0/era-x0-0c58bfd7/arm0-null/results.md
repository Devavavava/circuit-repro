# capability results (EXPERIMENTAL -- not frozen)

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.
stages = bias/sized/feasible counts over the candidates a spec walked (the cross-PDK funnel-rate signal).
sim-health = per-stage sim-success rate over the sized candidates' ngspice evals (1.00 = every eval simulated; <<1 = ENVIRONMENT wall, not a design miss). '-' = no sized candidate / no-sim run.

| spec | tier | arm | variant | pdk | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | stages(b/s/f of n) | sim-health | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -2.67 | nf_db=0.317 | 12/12/6 of 12 | 1.00 (0/3000) | -31.51 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e02-gpsband | E | A | - | bptm45 | YES | corpus#1403690f | 6 | 1500 | no | -2.97 | nf_db=0.314 | 12/12/4 of 12 | 1.00 (0/3000) | -38.20 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e03-900mhz | E | A | - | bptm45 | YES | corpus#182aa0c7 | 9 | 2250 | no | -2.59 | nf_db=0.231 | 12/12/3 of 12 | 1.00 (0/3000) | -30.43 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e04-35ghz | E | A | - | bptm45 | YES | corpus#1403690f | 6 | 1500 | no | -1.82 | nf_db=0.18 | 12/12/5 of 12 | 1.00 (0/3000) | -30.28 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e05-ism58 | E | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -2.19 | s11_db=0.0835 | 12/12/6 of 12 | 1.00 (0/3000) | -30.57 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e06-wifi | E | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -1.64 | s11_db=0.121 | 12/12/5 of 12 | 1.00 (0/3000) | -31.28 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e07-gpsband | E | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -1.22 | s11_db=0.141 | 12/12/4 of 12 | 1.00 (0/3000) | -33.09 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e08-wideband | E | A | - | bptm45 | no | - | - | 16200 | yes | 1.46 | s11_max_db=-0.456 | 18/18/0 of 18 | 1.00 (0/16200) | -20.21 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m01-wifi | M | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -0.78 | nf_db=0.00825 | 12/12/4 of 12 | 1.00 (0/3000) | -29.57 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m02-gpsband | M | A | - | bptm45 | YES | corpus#1403690f | 6 | 1500 | no | -0.816 | nf_db=0.0203 | 12/12/2 of 12 | 1.00 (0/3000) | -33.69 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m03-900mhz | M | A | - | bptm45 | YES | corpus#ace8383c | 12 | 3000 | no | -1.05 | s11_db=0.03 | 12/12/1 of 12 | 1.00 (0/3000) | -32.58 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m04-35ghz | M | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -0.709 | s11_db=0.0814 | 12/12/3 of 12 | 1.00 (0/3000) | -29.27 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m05-ism58 | M | A | - | bptm45 | YES | corpus#1403690f | 6 | 1500 | no | -1.31 | nf_db=0.141 | 12/12/4 of 12 | 1.00 (0/3000) | -23.04 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m06-wifi | M | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -0.748 | s11_db=0.0478 | 12/12/3 of 12 | 1.00 (0/3000) | -27.16 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m07-gpsband | M | A | - | bptm45 | YES | corpus#1403690f | 6 | 1500 | no | -0.381 | s11_db=0.101 | 12/12/1 of 12 | 1.00 (0/3000) | -12.74 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m08-ism58 | M | A | - | bptm45 | YES | corpus#182aa0c7 | 9 | 2250 | no | -1.21 | nf_db=0.0828 | 12/12/4 of 12 | 1.00 (0/3000) | -28.35 | conditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-h01-wifi | H | A | - | bptm45 | YES | corpus#1403690f | 7 | 6300 | yes | -0.547 | s11_db=0.0253 | 18/18/6 of 18 | 1.00 (0/16200) | -33.13 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h02-gpsband | H | A | - | bptm45 | YES | corpus#1403690f | 9 | 8100 | yes | -0.279 | idd_ma=0.019 | 18/18/3 of 18 | 1.00 (0/16200) | -32.19 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h03-900mhz | H | A | - | bptm45 | no | - | - | 16200 | yes | 1.12 | nf_db=-0.115 | 18/18/0 of 18 | 1.00 (0/16200) | -34.47 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-h04-35ghz | H | A | - | bptm45 | YES | corpus#ace8383c | 16 | 14400 | yes | -0.332 | s11_db=0.00345 | 18/18/2 of 18 | 1.00 (0/16200) | -28.14 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h05-ism58 | H | A | - | bptm45 | YES | corpus#182aa0c7 | 14 | 12600 | yes | -0.994 | idd_ma=0.0483 | 18/18/5 of 18 | 1.00 (0/16200) | -35.99 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h06-wifi | H | A | - | bptm45 | YES | corpus#1403690f | 6 | 1500 | no | -0.309 | s21_db=0.000911 | 12/12/1 of 12 | 1.00 (0/3000) | -8.86 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-h07-gpsband | H | A | - | bptm45 | no | - | - | 16200 | yes | 1.16 | nf_db=-0.135 | 18/18/0 of 18 | 1.00 (0/16200) | -34.43 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-h08-wideband | H | A | - | bptm45 | no | - | - | 16200 | yes | 2.55 | s11_max_db=-0.98 | 18/18/0 of 18 | 1.00 (0/16200) | +0.49 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |

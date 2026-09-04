# capability results (EXPERIMENTAL -- not frozen)

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.
stages = bias/sized/feasible counts over the candidates a spec walked (the cross-PDK funnel-rate signal).
sim-health = per-stage sim-success rate over the sized candidates' ngspice evals (1.00 = every eval simulated; <<1 = ENVIRONMENT wall, not a design miss). '-' = no sized candidate / no-sim run.

| spec | tier | arm | variant | pdk | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | stages(b/s/f of n) | sim-health | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -3.06 | idd_ma=0.276 | 12/12/6 of 12 | 1.00 (0/3000) | -33.98 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e02-gpsband | E | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -2.82 | nf_db=0.11 | 12/12/6 of 12 | 1.00 (0/3000) | -32.09 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e03-900mhz | E | A | - | bptm45 | YES | corpus#182aa0c7 | 9 | 2250 | no | -2.77 | nf_db=0.236 | 12/12/4 of 12 | 1.00 (0/3000) | -33.64 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e04-35ghz | E | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -2.34 | idd_ma=0.0723 | 12/12/6 of 12 | 1.00 (0/3000) | -31.22 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e05-ism58 | E | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -2.38 | idd_ma=0.059 | 12/12/6 of 12 | 1.00 (0/3000) | -28.15 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e06-wifi | E | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -1.88 | nf_db=0.0977 | 12/12/5 of 12 | 1.00 (0/3000) | -31.82 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e07-gpsband | E | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -1.85 | nf_db=0.214 | 12/12/6 of 12 | 1.00 (0/3000) | -36.23 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e08-wideband | E | A | - | bptm45 | no | - | - | 16200 | yes | 1.25 | s11_max_db=-0.251 | 18/18/0 of 18 | 1.00 (0/16200) | -21.94 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m01-wifi | M | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -1.24 | nf_db=0.0968 | 12/12/4 of 12 | 1.00 (0/3000) | -33.27 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m02-gpsband | M | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -0.586 | idd_ma=0.139 | 12/12/3 of 12 | 1.00 (0/3000) | -13.19 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m03-900mhz | M | A | - | bptm45 | YES | corpus#ace8383c | 12 | 3000 | no | -0.993 | idd_ma=0.0573 | 12/12/1 of 12 | 1.00 (0/3000) | -31.18 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m04-35ghz | M | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -1.25 | nf_db=0.00614 | 12/12/5 of 12 | 1.00 (0/3000) | -33.05 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m05-ism58 | M | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -1.49 | nf_db=0.296 | 12/12/6 of 12 | 1.00 (0/3000) | -32.69 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m06-wifi | M | A | - | bptm45 | YES | corpus#1403690f | 5 | 1250 | no | -0.873 | nf_db=0.113 | 12/12/4 of 12 | 1.00 (0/3000) | -30.24 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m07-gpsband | M | A | - | bptm45 | YES | corpus#1403690f | 6 | 1500 | no | -0.318 | idd_ma=0.0247 | 12/12/1 of 12 | 1.00 (0/3000) | -11.09 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m08-ism58 | M | A | - | bptm45 | YES | corpus#ace8383c | 11 | 2750 | no | -0.9 | s11_db=0.169 | 12/12/2 of 12 | 1.00 (0/3000) | -24.20 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-h01-wifi | H | A | - | bptm45 | YES | corpus#1403690f | 7 | 6300 | yes | -0.477 | s11_db=0.00182 | 18/18/6 of 18 | 1.00 (0/16200) | -11.33 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h02-gpsband | H | A | - | bptm45 | YES | corpus#1403690f | 7 | 6300 | yes | -0.245 | s11_db=0.0176 | 18/18/4 of 18 | 1.00 (0/16200) | -31.48 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h03-900mhz | H | A | - | bptm45 | no | - | - | 16200 | yes | 1.1 | nf_db=-0.0952 | 18/18/0 of 18 | 1.00 (0/16200) | -34.53 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-h04-35ghz | H | A | - | bptm45 | YES | corpus#1403690f | 7 | 6300 | yes | -0.489 | s21_db=0.000847 | 18/18/2 of 18 | 1.00 (0/16200) | -8.53 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h05-ism58 | H | A | - | bptm45 | YES | corpus#182aa0c7 | 13 | 11700 | yes | -0.85 | nf_db=0.00818 | 18/18/5 of 18 | 1.00 (0/16200) | -34.16 | conditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h06-wifi | H | A | - | bptm45 | YES | corpus#1403690f | 6 | 1500 | no | -0.296 | s21_db=0.00777 | 12/12/1 of 12 | 1.00 (0/3000) | -8.84 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-h07-gpsband | H | A | - | bptm45 | no | - | - | 16200 | yes | 1.09 | nf_db=-0.0915 | 18/18/0 of 18 | 1.00 (0/16200) | -31.92 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-h08-wideband | H | A | - | bptm45 | no | - | - | 16200 | yes | 1.72 | s11_max_db=-0.716 | 18/18/0 of 18 | 1.00 (0/16200) | -25.73 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |

# capability-v0 results (EXPERIMENTAL -- not frozen)

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.

| spec | tier | arm | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | A | YES | corpus#1403690f | 5 | 1250 | no | -2.67 | nf_db=0.317 | -31.51 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e02-gpsband | E | A | YES | corpus#1403690f | 6 | 1500 | no | -2.97 | nf_db=0.314 | -38.20 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e03-900mhz | E | A | YES | corpus#182aa0c7 | 9 | 2250 | no | -2.59 | nf_db=0.231 | -30.43 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e04-35ghz | E | A | YES | corpus#1403690f | 6 | 1500 | no | -1.82 | nf_db=0.18 | -30.28 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e05-ism58 | E | A | YES | corpus#1403690f | 5 | 1250 | no | -2.19 | s11_db=0.0835 | -30.57 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e06-wifi | E | A | YES | corpus#1403690f | 5 | 1250 | no | -1.64 | s11_db=0.121 | -31.28 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e07-gpsband | E | A | YES | corpus#1403690f | 5 | 1250 | no | -1.22 | s11_db=0.141 | -33.09 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-e08-wideband | E | A | no | - | - | 16200 | yes | 1.46 | s11_max_db=-0.456 | -20.21 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-m01-wifi | M | A | YES | corpus#1403690f | 5 | 1250 | no | -0.78 | nf_db=0.00825 | -29.57 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m02-gpsband | M | A | YES | corpus#1403690f | 6 | 1500 | no | -0.816 | nf_db=0.0203 | -33.69 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m03-900mhz | M | A | YES | corpus#ace8383c | 12 | 3000 | no | -1.05 | s11_db=0.03 | -32.58 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m04-35ghz | M | A | YES | corpus#1403690f | 5 | 1250 | no | -0.709 | s11_db=0.0814 | -29.27 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m05-ism58 | M | A | YES | corpus#1403690f | 6 | 1500 | no | -1.31 | nf_db=0.141 | -23.04 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m06-wifi | M | A | YES | corpus#1403690f | 5 | 1250 | no | -0.748 | s11_db=0.0478 | -27.16 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m07-gpsband | M | A | YES | corpus#1403690f | 6 | 1500 | no | -0.381 | s11_db=0.101 | -12.74 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-m08-ism58 | M | A | YES | corpus#182aa0c7 | 9 | 2250 | no | -1.21 | nf_db=0.0828 | -28.35 | conditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-h01-wifi | H | A | YES | corpus#1403690f | 7 | 6300 | yes | -0.547 | s11_db=0.0253 | -33.13 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h02-gpsband | H | A | YES | corpus#1403690f | 9 | 8100 | yes | -0.279 | idd_ma=0.019 | -32.19 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h03-900mhz | H | A | no | - | - | 16200 | yes | 1.12 | nf_db=-0.115 | -34.47 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-h04-35ghz | H | A | YES | corpus#ace8383c | 16 | 14400 | yes | -0.332 | s11_db=0.00345 | -28.14 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h05-ism58 | H | A | YES | corpus#182aa0c7 | 14 | 12600 | yes | -0.994 | idd_ma=0.0483 | -35.99 | unconditional | matched total eval budget=16200 (6 topos x 3 seeds x 900) |
| cap-h06-wifi | H | A | YES | corpus#1403690f | 6 | 1500 | no | -0.309 | s21_db=0.000911 | -8.86 | unconditional | matched total eval budget=3000 (6 topos x 2 seeds x 250) |
| cap-h07-gpsband | H | A | no | - | - | 16200 | yes | 1.16 | nf_db=-0.135 | -34.43 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |
| cap-h08-wideband | H | A | no | - | - | 16200 | yes | 2.55 | s11_max_db=-0.98 | +0.49 | unconditional | HARD FAILURE after escalation; matched total eval budget=162 |

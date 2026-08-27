# capability results (EXPERIMENTAL -- not frozen) -- variant=arch

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.

| spec | tier | arm | variant | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | B | arch | YES | concentrate | 5 | 2280 | yes | -1.56 | idd_ma=0.149 | -17.78 | conditional |  |
| cap-e02-gpsband | E | B | arch | YES | concentrate | 3 | 720 | no | -1.31 | idd_ma=0.0413 | -9.71 | conditional |  |
| cap-e03-900mhz | E | B | arch | no | - | - | 9360 | yes | 3.33 | s21_db=-1.48 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e04-35ghz | E | B | arch | YES | concentrate | 3 | 720 | no | -0.962 | s21_db=0.325 | -10.65 | conditional |  |
| cap-e05-ism58 | E | B | arch | YES | triage#0 | 0 | 60 | no | -1.36 | idd_ma=0.414 | -11.16 | conditional |  |
| cap-e06-wifi | E | B | arch | YES | concentrate | 5 | 2280 | yes | -0.875 | s11_db=0.0846 | -19.81 | conditional |  |
| cap-e07-gpsband | E | B | arch | no | - | - | 9600 | yes | 1.1 | idd_ma=-0.0951 | -16.62 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e08-wideband | E | B | arch | no | - | - | 9240 | yes | 1.88 | s11_max_db=-0.884 | -10.87 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m01-wifi | M | B | arch | YES | concentrate | 3 | 720 | no | -1.02 | idd_ma=0.0906 | -14.81 | unconditional |  |
| cap-m02-gpsband | M | B | arch | no | - | - | 9600 | yes | 2.21 | s21_db=-1.1 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m03-900mhz | M | B | arch | no | - | - | 9480 | yes | 2.44 | s11_db=-0.998 | +0.36 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m04-35ghz | M | B | arch | YES | concentrate | 3 | 780 | no | -0.478 | idd_ma=0.105 | -8.96 | conditional |  |
| cap-m05-ism58 | M | B | arch | YES | concentrate | 3 | 720 | no | -0.908 | s11_db=0.201 | -17.17 | conditional |  |
| cap-m06-wifi | M | B | arch | no | - | - | 7440 | yes | 1.46 | idd_ma=-0.459 | -18.74 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m07-gpsband | M | B | arch | no | - | - | 7800 | yes | 2.92 | s11_db=-0.962 | -3.31 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m08-ism58 | M | B | arch | YES | concentrate | 5 | 2160 | yes | -0.927 | s11_db=0.00865 | -22.39 | conditional |  |
| cap-h01-wifi | H | B | arch | YES | concentrate | 3 | 660 | no | -0.6 | s21_db=0.244 | -15.34 | unconditional |  |
| cap-h02-gpsband | H | B | arch | no | - | - | 9360 | yes | 2.44 | s21_db=-1.06 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h03-900mhz | H | B | arch | no | - | - | 9600 | yes | 3.62 | idd_ma=-1.22 | -0.62 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h04-35ghz | H | B | arch | no | - | - | 5640 | yes | 1.87 | idd_ma=-0.8 | -17.21 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h05-ism58 | H | B | arch | YES | concentrate | 5 | 2280 | yes | -0.428 | s11_db=0.0445 | -9.10 | conditional |  |
| cap-h06-wifi | H | B | arch | no | - | - | 7800 | yes | 1.98 | idd_ma=-0.854 | -18.80 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h07-gpsband | H | B | arch | no | - | - | 9480 | yes | 4.07 | idd_ma=-1.2 | -3.82 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h08-wideband | H | B | arch | no | - | - | 9240 | yes | 2.09 | s11_max_db=-0.566 | -3.86 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |

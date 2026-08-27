# capability results (EXPERIMENTAL -- not frozen) -- variant=selflearn

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.

| spec | tier | arm | variant | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | B | selflearn | YES | concentrate | 3 | 720 | no | -1.36 | idd_ma=0.147 | -17.27 | conditional |  |
| cap-e02-gpsband | E | B | selflearn | YES | concentrate | 3 | 780 | no | -0.392 | idd_ma=0.00529 | -7.97 | conditional |  |
| cap-e03-900mhz | E | B | selflearn | no | - | - | 5880 | yes | 1.2 | idd_ma=-0.168 | -12.02 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e04-35ghz | E | B | selflearn | YES | triage#0 | 0 | 120 | yes | -1.37 | s11_db=0.00197 | -19.40 | conditional |  |
| cap-e05-ism58 | E | B | selflearn | YES | triage#1 | 1 | 120 | no | -0.908 | s21_db=0.386 | -16.54 | conditional |  |
| cap-e06-wifi | E | B | selflearn | YES | concentrate | 5 | 2280 | yes | -0.875 | s11_db=0.0846 | -19.81 | conditional |  |
| cap-e07-gpsband | E | B | selflearn | no | - | - | 7800 | yes | 1.17 | idd_ma=-0.173 | -16.14 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e08-wideband | E | B | selflearn | no | - | - | 0 | yes | - | - | - | - | HARD FAILURE after escalation; no candidate survived triage |
| cap-m01-wifi | M | B | selflearn | YES | concentrate | 3 | 720 | no | -0.744 | s21_db=0.32 | -16.37 | unconditional |  |
| cap-m02-gpsband | M | B | selflearn | no | - | - | 7680 | yes | 1.08 | idd_ma=-0.0753 | -12.38 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m03-900mhz | M | B | selflearn | no | - | - | 9360 | yes | 2.42 | s11_db=-0.997 | +0.40 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m04-35ghz | M | B | selflearn | YES | edit#0 | 6 | 4080 | yes | -0.168 | idd_ma=0.00329 | -28.33 | conditional |  |
| cap-m05-ism58 | M | B | selflearn | YES | concentrate | 3 | 720 | no | -0.736 | s21_db=0.234 | -7.68 | conditional |  |
| cap-m06-wifi | M | B | selflearn | YES | concentrate | 3 | 660 | no | -0.768 | idd_ma=0.252 | -13.32 | unconditional |  |
| cap-m07-gpsband | M | B | selflearn | YES | concentrate | 3 | 780 | no | -0.384 | s21_db=0.175 | -16.05 | conditional |  |
| cap-m08-ism58 | M | B | selflearn | YES | concentrate | 5 | 2160 | yes | -0.829 | s11_db=0.106 | -16.89 | conditional |  |
| cap-h01-wifi | H | B | selflearn | no | - | - | 2280 | yes | 4.87 | nf_db=-1.94 | -17.91 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h02-gpsband | H | B | selflearn | no | - | - | 2400 | yes | 2.68 | s21_db=-1.03 | -3.90 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h03-900mhz | H | B | selflearn | no | - | - | 9600 | yes | 1.73 | s21_db=-0.731 | - | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h04-35ghz | H | B | selflearn | no | - | - | 5760 | yes | 2.89 | s21_db=-1.19 | -16.41 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h05-ism58 | H | B | selflearn | no | - | - | 9360 | yes | 2.68 | s21_db=-1.12 | -10.72 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h06-wifi | H | B | selflearn | no | - | - | 3840 | yes | 3.54 | s21_db=-1.29 | +3.36 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h07-gpsband | H | B | selflearn | no | - | - | 2280 | yes | 2.79 | s21_db=-1.05 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h08-wideband | H | B | selflearn | no | - | - | 7560 | yes | 3.7 | s21_ripple_db=-1.26 | -6.16 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |

# capability results (EXPERIMENTAL -- not frozen) -- variant=selflearn

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.

| spec | tier | arm | variant | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | B | selflearn | YES | concentrate | 3 | 780 | no | -1.44 | s11_db=0.0335 | -17.09 | conditional |  |
| cap-e02-gpsband | E | B | selflearn | YES | concentrate | 3 | 780 | no | -1.1 | idd_ma=0.0221 | -22.09 | conditional |  |
| cap-e03-900mhz | E | B | selflearn | no | - | - | 9360 | yes | 1.16 | idd_ma=-0.155 | -9.87 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e04-35ghz | E | B | selflearn | YES | concentrate | 3 | 720 | no | -0.702 | idd_ma=0.194 | -8.96 | conditional |  |
| cap-e05-ism58 | E | B | selflearn | YES | concentrate | 3 | 720 | no | -0.726 | s11_db=0.243 | -18.00 | conditional |  |
| cap-e06-wifi | E | B | selflearn | YES | concentrate | 5 | 2160 | yes | -0.912 | idd_ma=0.149 | -20.03 | conditional |  |
| cap-e07-gpsband | E | B | selflearn | no | - | - | 2280 | yes | 1.26 | idd_ma=-0.263 | -16.45 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e08-wideband | E | B | selflearn | no | - | - | 9480 | yes | 1.16 | s21_db=-0.163 | -0.95 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m01-wifi | M | B | selflearn | no | - | - | 2040 | yes | 1.09 | s11_db=-0.0921 | -5.82 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m02-gpsband | M | B | selflearn | no | - | - | 9480 | yes | 1.04 | idd_ma=-0.039 | -5.89 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m03-900mhz | M | B | selflearn | no | - | - | 9600 | yes | 2.42 | s11_db=-0.997 | +0.40 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m04-35ghz | M | B | selflearn | YES | edit#0 | 6 | 3960 | yes | -1.13 | idd_ma=0.106 | -21.44 | conditional |  |
| cap-m05-ism58 | M | B | selflearn | YES | concentrate | 5 | 2280 | yes | -0.976 | s11_db=0.251 | -19.53 | conditional |  |
| cap-m06-wifi | M | B | selflearn | no | - | - | 5640 | yes | 5.41 | nf_db=-2.99 | -12.36 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m07-gpsband | M | B | selflearn | YES | concentrate | 3 | 780 | no | -0.583 | s11_db=0.111 | -17.82 | unconditional |  |
| cap-m08-ism58 | M | B | selflearn | YES | concentrate | 5 | 2160 | yes | -1.33 | idd_ma=0.499 | -23.67 | conditional |  |
| cap-h01-wifi | H | B | selflearn | no | - | - | 7800 | yes | 2.2 | idd_ma=-1.2 | -17.70 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h02-gpsband | H | B | selflearn | no | - | - | 9480 | yes | 2.09 | idd_ma=-0.39 | -5.90 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h03-900mhz | H | B | selflearn | no | - | - | 9600 | yes | 1.77 | s11_db=-0.657 | -11.92 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h04-35ghz | H | B | selflearn | YES | triage#4 | 4 | 480 | yes | -0.838 | s11_db=0.0768 | -25.48 | conditional |  |
| cap-h05-ism58 | H | B | selflearn | no | - | - | 2160 | yes | 2.4 | s21_db=-1.09 | -10.49 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h06-wifi | H | B | selflearn | no | - | - | 4200 | yes | 1.01 | s21_db=-0.0149 | -18.06 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h07-gpsband | H | B | selflearn | no | - | - | 9480 | yes | 2.91 | s21_db=-1.04 | +6.90 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h08-wideband | H | B | selflearn | no | - | - | 7440 | yes | 6.52 | s21_ripple_db=-3.09 | - | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |

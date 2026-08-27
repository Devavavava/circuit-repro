# capability results (EXPERIMENTAL -- not frozen) -- variant=selflearn

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.
stages = bias/sized/feasible counts over the candidates a spec walked (the cross-PDK funnel-rate signal).

| spec | tier | arm | variant | pdk | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | stages(b/s/f of n) | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | B | selflearn | bptm45 | YES | edit#1 | 5 | 1920 | no | -1.23 | idd_ma=0.38 | 8/8/2 of 9 | -6.17 | conditional |  |
| cap-e02-gpsband | E | B | selflearn | bptm45 | YES | concentrate | 3 | 720 | no | -1.21 | idd_ma=0.081 | 4/4/2 of 5 | -16.86 | conditional |  |
| cap-e03-900mhz | E | B | selflearn | bptm45 | no | - | - | 9600 | yes | 1.11 | idd_ma=-0.115 | 15/15/0 of 15 | -15.94 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e04-35ghz | E | B | selflearn | bptm45 | YES | triage#2 | 2 | 240 | yes | -1.48 | s11_db=0.153 | 5/5/3 of 7 | -15.22 | conditional |  |
| cap-e05-ism58 | E | B | selflearn | bptm45 | YES | concentrate | 3 | 780 | no | -1.02 | idd_ma=0.304 | 5/5/2 of 5 | +1.21 | conditional |  |
| cap-e06-wifi | E | B | selflearn | bptm45 | YES | concentrate | 3 | 720 | no | -0.664 | idd_ma=0.0141 | 4/4/2 of 5 | -21.70 | conditional |  |
| cap-e07-gpsband | E | B | selflearn | bptm45 | YES | concentrate | 3 | 780 | no | -0.65 | s21_db=0.169 | 5/5/2 of 5 | -7.60 | conditional |  |
| cap-e08-wideband | E | B | selflearn | bptm45 | no | - | - | 9360 | yes | 1.92 | s11_max_db=-0.917 | 13/13/0 of 15 | -2.28 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m01-wifi | M | B | selflearn | bptm45 | YES | triage#0 | 0 | 120 | yes | -1.54 | idd_ma=0.175 | 6/6/3 of 7 | -30.87 | conditional |  |
| cap-m02-gpsband | M | B | selflearn | bptm45 | no | - | - | 2400 | yes | 2.26 | s21_db=-1.16 | 7/7/0 of 11 | -15.20 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m03-900mhz | M | B | selflearn | bptm45 | no | - | - | 9600 | yes | 2.42 | s11_db=-0.997 | 15/15/0 of 15 | +0.40 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m04-35ghz | M | B | selflearn | bptm45 | YES | concentrate | 5 | 2160 | yes | -0.683 | s21_db=0.228 | 5/5/2 of 7 | -10.64 | conditional |  |
| cap-m05-ism58 | M | B | selflearn | bptm45 | YES | concentrate | 5 | 2160 | yes | -0.976 | s11_db=0.251 | 5/5/2 of 7 | -19.53 | conditional |  |
| cap-m06-wifi | M | B | selflearn | bptm45 | no | - | - | 4080 | yes | 1.24 | idd_ma=-0.207 | 8/8/0 of 12 | -41.90 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m07-gpsband | M | B | selflearn | bptm45 | no | - | - | 9480 | yes | 2.93 | s11_db=-0.971 | 14/14/0 of 15 | -3.77 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m08-ism58 | M | B | selflearn | bptm45 | YES | concentrate | 5 | 2280 | yes | -0.74 | s11_db=0.0381 | 6/6/2 of 7 | -17.26 | conditional |  |
| cap-h01-wifi | H | B | selflearn | bptm45 | no | - | - | 7800 | yes | 2.2 | idd_ma=-1.2 | 13/13/0 of 14 | -17.70 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h02-gpsband | H | B | selflearn | bptm45 | YES | concentrate | 5 | 2400 | yes | -0.141 | s21_db=0.0129 | 7/7/2 of 7 | -18.33 | unconditional |  |
| cap-h03-900mhz | H | B | selflearn | bptm45 | no | - | - | 7800 | yes | 3.63 | idd_ma=-1.2 | 13/13/0 of 14 | -0.81 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h04-35ghz | H | B | selflearn | bptm45 | no | - | - | 9240 | yes | 2.05 | s11_db=-0.735 | 12/12/0 of 15 | -12.24 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h05-ism58 | H | B | selflearn | bptm45 | YES | concentrate | 3 | 780 | no | -0.312 | idd_ma=0.000762 | 5/5/2 of 5 | -19.65 | conditional |  |
| cap-h06-wifi | H | B | selflearn | bptm45 | no | - | - | 7680 | yes | 1.98 | idd_ma=-0.854 | 12/12/0 of 14 | -18.80 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h07-gpsband | H | B | selflearn | bptm45 | no | - | - | 9600 | yes | 4.04 | idd_ma=-1.19 | 15/15/0 of 15 | -2.71 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h08-wideband | H | B | selflearn | bptm45 | no | - | - | 5760 | yes | 5.36 | s21_ripple_db=-1.88 | 9/9/0 of 13 | +5.70 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |

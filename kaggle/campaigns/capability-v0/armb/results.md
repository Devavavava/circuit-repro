# capability-v0 results (EXPERIMENTAL -- not frozen)

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.

| spec | tier | arm | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | B | YES | propose#0 | 0 | 600 | no | -1.12 | idd_ma=0.00248 | -5.63 | conditional |  |
| cap-e02-gpsband | E | B | YES | propose#0 | 0 | 600 | no | -1.31 | idd_ma=0.0413 | -9.71 | conditional |  |
| cap-e03-900mhz | E | B | no | - | - | 14400 | yes | 1.06 | idd_ma=-0.0557 | -11.63 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e04-35ghz | E | B | YES | propose#0 | 0 | 600 | no | -0.848 | idd_ma=0.0504 | -1.08 | conditional |  |
| cap-e05-ism58 | E | B | YES | propose#1 | 1 | 1200 | no | -1.02 | idd_ma=0.304 | +1.21 | conditional |  |
| cap-e06-wifi | E | B | YES | propose#0 | 0 | 1800 | yes | -0.875 | s11_db=0.0846 | -19.81 | conditional |  |
| cap-e07-gpsband | E | B | YES | propose#1 | 1 | 3600 | yes | -0.372 | idd_ma=0.0312 | -13.38 | unconditional |  |
| cap-e08-wideband | E | B | no | - | - | 12600 | yes | 1.91 | s11_max_db=-0.908 | -6.68 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m01-wifi | M | B | no | - | - | 10800 | yes | 1.67 | idd_ma=-0.64 | -17.44 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m02-gpsband | M | B | no | - | - | 14400 | yes | 2.45 | s11_db=-0.901 | -8.00 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m03-900mhz | M | B | no | - | - | 16200 | yes | 2.42 | s11_db=-0.997 | +0.40 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m04-35ghz | M | B | no | - | - | 10800 | yes | 1.01 | idd_ma=-0.0133 | -20.24 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m05-ism58 | M | B | YES | propose#0 | 0 | 600 | no | -0.813 | s11_db=0.27 | -17.53 | conditional |  |
| cap-m06-wifi | M | B | YES | edit#1 | 6 | 12600 | yes | -0.239 | idd_ma=0.00377 | -16.16 | conditional |  |
| cap-m07-gpsband | M | B | no | - | - | 16200 | yes | 2.93 | s11_db=-0.965 | -3.48 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m08-ism58 | M | B | YES | propose#0 | 0 | 600 | no | -0.645 | idd_ma=0.102 | -7.30 | conditional |  |
| cap-h01-wifi | H | B | no | - | - | 16200 | yes | 2.2 | idd_ma=-1.2 | -17.70 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h02-gpsband | H | B | no | - | - | 16200 | yes | 3.66 | idd_ma=-1.17 | -3.22 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h03-900mhz | H | B | no | - | - | 16200 | yes | 3.63 | idd_ma=-1.31 | -1.11 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h04-35ghz | H | B | no | - | - | 14400 | yes | 1.83 | idd_ma=-0.788 | -18.95 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h05-ism58 | H | B | YES | propose#0 | 0 | 1800 | yes | -0.308 | nf_db=0.0305 | -19.07 | conditional |  |
| cap-h06-wifi | H | B | no | - | - | 14400 | yes | 1.98 | idd_ma=-0.854 | -18.80 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h07-gpsband | H | B | no | - | - | 16200 | yes | 4.04 | idd_ma=-1.19 | -2.71 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h08-wideband | H | B | no | - | - | 14400 | yes | 5 | nf_db=-1.42 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |

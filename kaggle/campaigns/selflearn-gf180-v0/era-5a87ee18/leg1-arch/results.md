# capability results (EXPERIMENTAL -- not frozen) -- variant=arch -- pdk=gf180mcu

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.
stages = bias/sized/feasible counts over the candidates a spec walked (the cross-PDK funnel-rate signal).
sim-health = per-stage sim-success rate over the sized candidates' ngspice evals (1.00 = every eval simulated; <<1 = ENVIRONMENT wall, not a design miss). '-' = no sized candidate / no-sim run.

| spec | tier | arm | variant | pdk | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | stages(b/s/f of n) | sim-health | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | B | arch | gf180mcu | no | - | - | 3960 | yes | 7.11 | nf_db=-2.94 | 7/7/0 of 12 | 1.00 (0/3960) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e02-gpsband | E | B | arch | gf180mcu | no | - | - | 4080 | yes | 1.93 | s21_db=-0.909 | 8/8/0 of 12 | 1.00 (0/4080) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e03-900mhz | E | B | arch | gf180mcu | no | - | - | 9480 | yes | 12.3 | nf_db=-6.75 | 14/14/0 of 15 | 1.00 (0/9480) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e04-35ghz | E | B | arch | gf180mcu | no | - | - | 7320 | yes | 2.75 | s21_db=-1.25 | 9/9/0 of 14 | 1.00 (0/7320) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e05-ism58 | E | B | arch | gf180mcu | no | - | - | 9360 | yes | 2.38 | s21_db=-1.27 | 13/13/0 of 15 | 1.00 (0/9360) | +13.98 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e06-wifi | E | B | arch | gf180mcu | no | - | - | 9480 | yes | 1.19 | s21_db=-0.181 | 14/14/0 of 15 | 1.00 (0/9480) | +10.89 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e07-gpsband | E | B | arch | gf180mcu | no | - | - | 9600 | yes | 8.75 | nf_db=-4.64 | 15/15/0 of 15 | 1.00 (0/9600) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e08-wideband | E | B | arch | gf180mcu | no | - | - | 9120 | yes | 21.3 | nf_db=-10.7 | 11/11/0 of 15 | 1.00 (0/9120) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m01-wifi | M | B | arch | gf180mcu | no | - | - | 2160 | yes | 2.04 | s21_db=-1.04 | 5/5/0 of 11 | 1.00 (0/2160) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m02-gpsband | M | B | arch | gf180mcu | no | - | - | 6000 | yes | 2.58 | s21_db=-1.02 | 11/11/0 of 13 | 1.00 (0/6000) | - | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m03-900mhz | M | B | arch | gf180mcu | no | - | - | 7560 | yes | 17 | nf_db=-11.8 | 11/11/0 of 14 | 1.00 (0/7560) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m04-35ghz | M | B | arch | gf180mcu | no | - | - | 9360 | yes | 3.15 | s21_db=-1.14 | 13/13/0 of 15 | 1.00 (0/9360) | +15.24 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m05-ism58 | M | B | arch | gf180mcu | no | - | - | 7440 | yes | 1.21 | idd_ma=-0.183 | 10/10/0 of 14 | 1.00 (0/7440) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m06-wifi | M | B | arch | gf180mcu | no | - | - | 3960 | yes | 2.69 | s21_db=-0.708 | 7/7/0 of 12 | 1.00 (0/3960) | +0.31 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m07-gpsband | M | B | arch | gf180mcu | no | - | - | 9600 | yes | 2.31 | s21_db=-1.07 | 15/15/0 of 15 | 1.00 (0/9600) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m08-ism58 | M | B | arch | gf180mcu | no | - | - | 2040 | yes | 2.3 | s21_db=-1.21 | 4/4/0 of 11 | 1.00 (0/2040) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h01-wifi | H | B | arch | gf180mcu | no | - | - | 7680 | yes | 9.08 | nf_db=-5.38 | 12/12/0 of 14 | 1.00 (0/7680) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h02-gpsband | H | B | arch | gf180mcu | no | - | - | 9360 | yes | 2.44 | s21_db=-1.06 | 13/13/0 of 15 | 1.00 (0/9360) | - | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h03-900mhz | H | B | arch | gf180mcu | no | - | - | 9480 | yes | 5.15 | nf_db=-2.8 | 14/14/0 of 15 | 1.00 (0/9480) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h04-35ghz | H | B | arch | gf180mcu | no | - | - | 2160 | yes | 4.65 | nf_db=-2.38 | 5/5/0 of 11 | 1.00 (0/2160) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h05-ism58 | H | B | arch | gf180mcu | no | - | - | 9240 | yes | 1.87 | s21_db=-0.458 | 12/12/0 of 15 | 1.00 (0/9240) | +2.44 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h06-wifi | H | B | arch | gf180mcu | no | - | - | 5760 | yes | 8.74 | nf_db=-5.39 | 9/9/0 of 13 | 1.00 (0/5760) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h07-gpsband | H | B | arch | gf180mcu | no | - | - | 9360 | yes | 19.2 | nf_db=-15.1 | 13/13/0 of 15 | 1.00 (0/9360) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h08-wideband | H | B | arch | gf180mcu | no | - | - | 7320 | yes | 3.77 | s21_db=-1.02 | 9/9/0 of 14 | 1.00 (0/7320) | - | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |

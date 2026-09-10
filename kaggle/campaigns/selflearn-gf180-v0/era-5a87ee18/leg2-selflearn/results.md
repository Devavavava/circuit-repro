# capability results (EXPERIMENTAL -- not frozen) -- variant=selflearn -- pdk=gf180mcu

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.
stages = bias/sized/feasible counts over the candidates a spec walked (the cross-PDK funnel-rate signal).
sim-health = per-stage sim-success rate over the sized candidates' ngspice evals (1.00 = every eval simulated; <<1 = ENVIRONMENT wall, not a design miss). '-' = no sized candidate / no-sim run.

| spec | tier | arm | variant | pdk | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | stages(b/s/f of n) | sim-health | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | B | selflearn | gf180mcu | no | - | - | 9480 | yes | 2.16 | s21_db=-1.16 | 14/14/0 of 15 | 1.00 (0/9480) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e02-gpsband | E | B | selflearn | gf180mcu | no | - | - | 7680 | yes | 5.1 | nf_db=-1.45 | 12/12/0 of 14 | 1.00 (0/7680) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e03-900mhz | E | B | selflearn | gf180mcu | no | - | - | 9600 | yes | 2.39 | s21_db=-0.824 | 15/15/0 of 15 | 1.00 (0/9600) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e04-35ghz | E | B | selflearn | gf180mcu | no | - | - | 9480 | yes | 2.71 | s21_db=-1.25 | 14/14/0 of 15 | 1.00 (0/9480) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e05-ism58 | E | B | selflearn | gf180mcu | no | - | - | 5880 | yes | 3.57 | s21_db=-1.35 | 10/10/0 of 13 | 1.00 (0/5880) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e06-wifi | E | B | selflearn | gf180mcu | no | - | - | 2160 | yes | 3.09 | s21_db=-1.43 | 5/5/0 of 11 | 1.00 (0/2160) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e07-gpsband | E | B | selflearn | gf180mcu | no | - | - | 2400 | yes | 2.03 | s21_db=-1.03 | 7/7/0 of 11 | 1.00 (0/2400) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e08-wideband | E | B | selflearn | gf180mcu | no | - | - | 9120 | yes | 3.46 | s11_max_db=-0.987 | 11/11/0 of 15 | 1.00 (0/9120) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m01-wifi | M | B | selflearn | gf180mcu | no | - | - | 9480 | yes | 3.39 | s21_db=-1.44 | 14/14/0 of 15 | 1.00 (0/9480) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m02-gpsband | M | B | selflearn | gf180mcu | no | - | - | 7680 | yes | 14.3 | nf_db=-9.63 | 12/12/0 of 14 | 1.00 (0/7680) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m03-900mhz | M | B | selflearn | gf180mcu | no | - | - | 9360 | yes | 17.5 | nf_db=-12.2 | 13/13/0 of 15 | 1.00 (0/9360) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m04-35ghz | M | B | selflearn | gf180mcu | no | - | - | 3840 | yes | 3.03 | s21_db=-1.41 | 6/6/0 of 12 | 1.00 (0/3840) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m05-ism58 | M | B | selflearn | gf180mcu | no | - | - | 2280 | yes | 2.09 | s21_db=-1.08 | 6/6/0 of 11 | 1.00 (0/2280) | -6.49 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m06-wifi | M | B | selflearn | gf180mcu | no | - | - | 5880 | yes | 6.51 | nf_db=-3.63 | 10/10/0 of 13 | 1.00 (0/5880) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m07-gpsband | M | B | selflearn | gf180mcu | no | - | - | 9360 | yes | 8.83 | nf_db=-5.97 | 13/13/0 of 15 | 1.00 (0/9360) | -1.51 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m08-ism58 | M | B | selflearn | gf180mcu | no | - | - | 7680 | yes | 2 | s21_db=-1 | 12/12/0 of 14 | 1.00 (0/7680) | - | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h01-wifi | H | B | selflearn | gf180mcu | no | - | - | 5880 | yes | 6.56 | nf_db=-4.28 | 10/10/0 of 13 | 1.00 (0/5880) | -2.82 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h02-gpsband | H | B | selflearn | gf180mcu | no | - | - | 7800 | yes | 4.3 | nf_db=-1.89 | 13/13/0 of 14 | 1.00 (0/7800) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h03-900mhz | H | B | selflearn | gf180mcu | no | - | - | 9480 | yes | 24.3 | nf_db=-19.4 | 14/14/0 of 15 | 1.00 (0/9480) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h04-35ghz | H | B | selflearn | gf180mcu | no | - | - | 5760 | yes | 3.86 | nf_db=-1.44 | 9/9/0 of 13 | 1.00 (0/5760) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h05-ism58 | H | B | selflearn | gf180mcu | no | - | - | 9360 | yes | 3.23 | s21_db=-1.3 | 13/13/0 of 15 | 1.00 (0/9360) | +16.79 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h06-wifi | H | B | selflearn | gf180mcu | no | - | - | 7560 | yes | 1.22 | nf_db=-0.136 | 11/11/0 of 14 | 1.00 (0/7560) | +21.65 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-h07-gpsband | H | B | selflearn | gf180mcu | no | - | - | 5640 | yes | 14.7 | nf_db=-11 | 8/8/0 of 13 | 1.00 (0/5640) | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |

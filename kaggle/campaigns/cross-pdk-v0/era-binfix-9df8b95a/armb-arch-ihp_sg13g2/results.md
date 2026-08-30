# capability results (EXPERIMENTAL -- not frozen) -- variant=arch -- pdk=ihp_sg13g2

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.
stages = bias/sized/feasible counts over the candidates a spec walked (the cross-PDK funnel-rate signal).

| spec | tier | arm | variant | pdk | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | stages(b/s/f of n) | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | B | arch | ihp_sg13g2 | YES | concentrate | 3 | 720 | no | -1.54 | s11_db=0.243 | 4/4/2 of 5 | -1.46 | conditional |  |
| cap-e02-gpsband | E | B | arch | ihp_sg13g2 | no | - | - | 7800 | yes | 1.17 | idd_ma=-0.137 | 13/13/0 of 14 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e03-900mhz | E | B | arch | ihp_sg13g2 | no | - | - | 9600 | yes | 1.49 | s21_db=-0.494 | 15/15/0 of 15 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e04-35ghz | E | B | arch | ihp_sg13g2 | YES | concentrate | 3 | 780 | no | -1.18 | s11_db=0.191 | 5/5/2 of 5 | +3.75 | conditional |  |
| cap-e05-ism58 | E | B | arch | ihp_sg13g2 | YES | concentrate | 5 | 1920 | yes | -1.46 | s11_db=0.152 | 3/3/2 of 7 | +14.46 | conditional |  |
| cap-e06-wifi | E | B | arch | ihp_sg13g2 | YES | concentrate | 3 | 720 | no | -1.35 | s11_db=0.39 | 4/4/2 of 5 | +5.57 | unconditional |  |
| cap-e07-gpsband | E | B | arch | ihp_sg13g2 | YES | concentrate | 3 | 780 | no | -1.19 | s11_db=0.312 | 5/5/2 of 5 | -5.00 | conditional |  |
| cap-e08-wideband | E | B | arch | ihp_sg13g2 | no | - | - | 0 | yes | - | - | 0/0/0 of 5 | - | - | HARD FAILURE after escalation; no candidate survived triage |
| cap-m01-wifi | M | B | arch | ihp_sg13g2 | no | - | - | 5520 | yes | 11.3 | nf_db=-6.88 | 7/7/0 of 13 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m02-gpsband | M | B | arch | ihp_sg13g2 | YES | concentrate | 5 | 2400 | yes | -0.733 | s11_db=0.0368 | 7/7/2 of 7 | -4.79 | conditional |  |
| cap-m03-900mhz | M | B | arch | ihp_sg13g2 | no | - | - | 9480 | yes | 2.08 | s11_db=-0.978 | 14/14/0 of 15 | -7.59 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m04-35ghz | M | B | arch | ihp_sg13g2 | YES | concentrate | 3 | 720 | no | -0.758 | s21_db=0.276 | 4/4/2 of 5 | - | conditional |  |
| cap-m05-ism58 | M | B | arch | ihp_sg13g2 | no | - | - | 2400 | yes | 2.56 | s21_db=-1.29 | 7/7/0 of 11 | +3.11 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m06-wifi | M | B | arch | ihp_sg13g2 | no | - | - | 5640 | yes | 1.52 | s11_db=-0.359 | 8/8/0 of 13 | +0.19 | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m07-gpsband | M | B | arch | ihp_sg13g2 | YES | edit#0 | 6 | 3840 | yes | -0.624 | s11_db=0.033 | 6/6/2 of 9 | -5.10 | conditional |  |
| cap-m08-ism58 | M | B | arch | ihp_sg13g2 | YES | concentrate | 3 | 780 | no | -0.739 | s21_db=0.0945 | 5/5/2 of 5 | +12.24 | conditional |  |
| cap-h01-wifi | H | B | arch | ihp_sg13g2 | YES | concentrate | 5 | 2040 | yes | -0.624 | s21_db=0.0864 | 4/4/2 of 7 | -4.18 | conditional |  |

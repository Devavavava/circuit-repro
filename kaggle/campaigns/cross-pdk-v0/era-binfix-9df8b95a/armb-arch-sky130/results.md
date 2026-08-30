# capability results (EXPERIMENTAL -- not frozen) -- variant=arch -- pdk=sky130

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.
stages = bias/sized/feasible counts over the candidates a spec walked (the cross-PDK funnel-rate signal).

| spec | tier | arm | variant | pdk | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | stages(b/s/f of n) | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | B | arch | sky130 | no | - | - | 3840 | yes | 2.01 | s21_db=-1.01 | 6/6/0 of 12 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e02-gpsband | E | B | arch | sky130 | no | - | - | 9600 | yes | 1.16 | s21_db=-0.104 | 15/15/0 of 15 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e03-900mhz | E | B | arch | sky130 | no | - | - | 9600 | yes | 3.77 | s21_db=-1.39 | 15/15/0 of 15 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e04-35ghz | E | B | arch | sky130 | no | - | - | 9360 | yes | 1.45 | s21_db=-0.312 | 13/13/0 of 15 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e05-ism58 | E | B | arch | sky130 | no | - | - | 9360 | yes | 2.17 | s21_db=-1.17 | 13/13/0 of 15 | +7.18 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e06-wifi | E | B | arch | sky130 | no | - | - | 7680 | yes | 3.08 | s21_db=-1.43 | 12/12/0 of 14 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e07-gpsband | E | B | arch | sky130 | no | - | - | 9240 | yes | 1e+03 | - | 12/12/0 of 15 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e08-wideband | E | B | arch | sky130 | no | - | - | 9240 | yes | 3.44 | s21_db=-1.07 | 12/12/0 of 15 | - | conditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m01-wifi | M | B | arch | sky130 | no | - | - | 5760 | yes | 8.5 | nf_db=-4.53 | 9/9/0 of 13 | +2.84 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m02-gpsband | M | B | arch | sky130 | no | - | - | 4080 | yes | 21.1 | nf_db=-15.3 | 8/8/0 of 12 | +12.92 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-m03-900mhz | M | B | arch | sky130 | no | - | - | 9480 | yes | 2.48 | s21_db=-1.13 | 14/14/0 of 15 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |

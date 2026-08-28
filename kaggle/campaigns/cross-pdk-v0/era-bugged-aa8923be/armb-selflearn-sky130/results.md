# capability results (EXPERIMENTAL -- not frozen) -- variant=selflearn -- pdk=sky130

Advisory columns (iip3_dbm, stability) NEVER gate the verdict.
0-feasible rows are results, not failures suppressed.
stages = bias/sized/feasible counts over the candidates a spec walked (the cross-PDK funnel-rate signal).

| spec | tier | arm | variant | pdk | feasible | first-feasible | iters | evals | escalated | best_obj | margins (worst) | stages(b/s/f of n) | iip3_dbm | stability | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e01-wifi | E | B | selflearn | sky130 | no | - | - | 3840 | yes | 6.39 | nf_db=-2.85 | 6/6/0 of 12 | - | - | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e02-gpsband | E | B | selflearn | sky130 | no | - | - | 9360 | yes | 17.2 | nf_db=-10.7 | 13/13/0 of 15 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e03-900mhz | E | B | selflearn | sky130 | no | - | - | 9600 | yes | 20.4 | nf_db=-13.2 | 15/15/0 of 15 | - | - | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e04-35ghz | E | B | selflearn | sky130 | no | - | - | 5880 | yes | 3.55 | s21_db=-1.3 | 10/10/0 of 13 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e05-ism58 | E | B | selflearn | sky130 | no | - | - | 5880 | yes | 6.63 | nf_db=-3.1 | 10/10/0 of 13 | +9.50 | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |
| cap-e06-wifi | E | B | selflearn | sky130 | no | - | - | 7560 | yes | 6.31 | nf_db=-3.01 | 11/11/0 of 14 | - | unconditional | HARD FAILURE after escalation; infeasible (closest attempt s |

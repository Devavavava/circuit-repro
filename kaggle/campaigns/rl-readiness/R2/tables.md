| cond | compl. | tokens mean (reasoning / answer) | finish=length | GPU-min/compl mean, med, max | edits | valid | feasible edits (% all) | cells solved all/SYN/RET | >=2/3 | EDGE | wb wide shunt-fb (VIN-side) / wb valid, cells | gate-only solved | gate+inloop solved |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BASE | 32 | 2451 (2033 / 417) est. | 0 | 1.77, 1.78, 2.70 | 96 | 96 (100%) | 11 (11.5%) | 6/4/2 | 5 | yes | 14 (21) / 48, 8/8 | - | 2 (1/1) PARTIAL |
| CAP | 32 | 1561 (1005 / 556) | 0 | 1.10, 1.09, 1.25 | 96 | 96 (100%) | 10 (10.4%) | 5/4/1 | 5 | yes | 14 (20) / 48, 7/8 | - | 0 (0/0) PARTIAL |
| NT | 32 | 834 (0 / 834) est. | 0 | 0.58, 0.59, 0.74 | 96 | 93 (97%) | 5 (5.2%) | 4/3/1 | 4 | no | 9 (17) / 46, 7/8 | - | 0 (0/0) PARTIAL |

Decision: {"per_condition": {"CAP": {"validity_ok": true, "cells_drop_ok": true, "feasible_rate_ok": true, "acceptable": true, "cells_drop": 1, "feasible_rate_drop_pts": 1.0416666666666656}, "NT": {"validity_ok": true, "cells_drop_ok": false, "feasible_rate_ok": false, "acceptable": false, "cells_drop": 2, "feasible_rate_drop_pts": 6.249999999999999}}, "chosen": "CAP"}

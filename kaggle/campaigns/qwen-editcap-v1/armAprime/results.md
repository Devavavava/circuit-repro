# x0-v1 results (EXPERIMENTAL -- pre-registered, not frozen)

arm = LNA_X0_PRIOR = (unset -> off/A0)   (off=A0 null / retrieval=A1 / learned=A2)
Fixed topology per cell, k=1, NO screening, no LLM. 0-feasible rows are results, not suppressed failures.
NOVEL-10 = wl not in the store (primary set); SEEN-4 = control strip.
sim-health = fraction of ngspice evals that produced metrics (1.00 = healthy; <<1 = environment wall).

| spec | tier | split | flag | pdk | feasible | first-feasible | evals | escalated | best_obj | margins (worst) | sim-health | wl_hash | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cap-e02-gpsband | E | seen | off | gf180mcu | YES | propose#0 | 5400 | no | -0.117 | s21_db=0.00142 | 1.00 (0/5400) | dcda50191d7c |  |
| cap-e03-900mhz | E | seen | off | gf180mcu | no | - | 5400 | no | 1.55 | s21_db=-0.45 | 1.00 (0/5400) | dcda50191d7c | infeasible (closest attempt saved) |
| cap-e07-gpsband | E | seen | off | gf180mcu | no | - | 5400 | no | 1.65 | s11_db=-0.652 | 1.00 (0/5400) | 226544590d47 | infeasible (closest attempt saved) |
| cap-e08-wideband | E | seen | off | gf180mcu | no | - | 5400 | no | 1.89 | s11_max_db=-0.535 | 1.00 (0/5400) | 226544590d47 | infeasible (closest attempt saved) |
| cap-h01-wifi | H | seen | off | gf180mcu | no | - | 5400 | no | 1.04 | nf_db=-0.0373 | 1.00 (0/5400) | dcda50191d7c | infeasible (closest attempt saved) |
| cap-h02-gpsband | H | seen | off | gf180mcu | no | - | 5400 | no | 2.29 | s11_db=-0.985 | 1.00 (0/5400) | dcda50191d7c | infeasible (closest attempt saved) |
| cap-h03-900mhz | H | seen | off | gf180mcu | no | - | 5400 | no | 2.86 | s11_db=-0.996 | 1.00 (0/5400) | dcda50191d7c | infeasible (closest attempt saved) |
| cap-h06-wifi | H | seen | off | gf180mcu | no | - | 5400 | no | 1.32 | nf_db=-0.164 | 1.00 (0/5400) | 226544590d47 | infeasible (closest attempt saved) |
| cap-h07-gpsband | H | seen | off | gf180mcu | no | - | 5400 | no | 2.57 | s11_db=-0.984 | 1.00 (0/5400) | dcda50191d7c | infeasible (closest attempt saved) |
| cap-h08-wideband | H | seen | off | gf180mcu | no | - | 5400 | no | 2.71 | s11_max_db=-0.985 | 1.00 (0/5400) | 226544590d47 | infeasible (closest attempt saved) |
| cap-m02-gpsband | M | seen | off | gf180mcu | no | - | 5400 | no | 2.13 | s11_db=-0.833 | 1.00 (0/5400) | 226544590d47 | infeasible (closest attempt saved) |
| cap-m03-900mhz | M | seen | off | gf180mcu | no | - | 5400 | no | 2.76 | s11_db=-0.977 | 1.00 (0/5400) | 226544590d47 | infeasible (closest attempt saved) |
| cap-m07-gpsband | M | seen | off | gf180mcu | no | - | 5400 | no | 2.46 | s11_db=-0.844 | 1.00 (0/5400) | 226544590d47 | infeasible (closest attempt saved) |

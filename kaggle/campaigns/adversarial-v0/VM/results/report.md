### Data table (`data/rows.jsonl.gz`, built by `build_data.py`)

| source | rows | included | excluded: reason (count) |
|---|---|---|---|
| bench-v2 | 21660 | 12778 | port_dc_prefilter_fail_(free_reject_under_rl-v1.1) (5418); pre_sizing_reject_free (2861); derived_copy_of_rl-v1_twin (495); duplicate_(tok,spec,seed,budget) (108) |
| E-c | 2792 | 1648 | fails_rl-v1.1_free_check:topo_limits (725); fails_rl-v1.1_free_check:port_dc_prefilter (231); duplicate_(tok,spec,seed,budget) (84); fails_rl-v1.1_free_check:structural_degeneracy (72); not_sizable (32) |
| E-d | 978 | 500 | fails_rl-v1.1_free_check:structural_degeneracy (258); fails_rl-v1.1_free_check:topo_limits (135); fails_rl-v1.1_free_check:port_dc_prefilter (57); duplicate_(tok,spec,seed,budget) (19); not_sizable (9) |
| R1 | 3652 | 2208 | fails_rl-v1.1_free_check:topo_limits (784); fails_rl-v1.1_free_check:port_dc_prefilter (406); fails_rl-v1.1_free_check:structural_degeneracy (254) |
| R4 | 216 | 111 | fails_rl-v1.1_free_check:port_dc_prefilter (27); duplicate_(tok,spec,seed,budget) (25); fails_rl-v1.1_free_check:topo_limits (25); special_config:win50/win50 (8); fails_rl-v1.1_free_check:structural_degeneracy (4); special_config:reg2/all (2); special_config:reg2/struct (2); special_config:reg/topo (2); special_config:reg2/gate (1); special_config:reg2/lib (1); special_config:reg2/inloop (1); special_config:reg2/win50 (1); special_config:reg3/gate (1); special_config:reg3/lib (1); special_config:reg3/inloop (1); special_config:reg/gate (1); special_config:reg/lib (1); special_config:reg/inloop (1) |
| verifier-rl-v1 | 134 | 100 | fails_rl-v1.1_free_check:topo_limits (17); fails_rl-v1.1_free_check:structural_degeneracy (8); fails_rl-v1.1_free_check:port_dc_prefilter (3); special_config:reg/lib (3); special_config:reg/gate (1); special_config:reg/rlv1env (1); special_config:reg/inloop (1) |
| S-1 | 252 | 0 | no_tokens_recorded (252) |
| stability-gate | 178 | 0 | no_tokens_recorded (178) |

Included rows by source, profile and kind (n / feasible):

| source | profile | subpop | fenced | n | feasible | rate |
|---|---|---|---|---|---|---|
| E-c | legacy-lib | - | False | 1648 | 206 | 0.125 |
| E-d | legacy-lib | - | False | 500 | 27 | 0.054 |
| R1 | legacy-lib | - | False | 1528 | 111 | 0.073 |
| R1 | stab-gate | - | False | 340 | 1 | 0.003 |
| R1 | stab-inloop | - | False | 340 | 32 | 0.094 |
| R4 | stab-gate | - | False | 11 | 0 | 0.000 |
| R4 | stab-inloop | - | False | 100 | 74 | 0.740 |
| bench-v2 | rl-v1 | F2 | False | 1858 | 66 | 0.036 |
| bench-v2 | rl-v1 | F2 | True | 3238 | 0 | 0.000 |
| bench-v2 | rl-v1 | search | False | 4381 | 2501 | 0.571 |
| bench-v2 | rl-v1 | stages | False | 2816 | 833 | 0.296 |
| bench-v2 | rl-v1 | stages | True | 195 | 4 | 0.021 |
| bench-v2 | rl-v1.1 | F2 | False | 69 | 1 | 0.014 |
| bench-v2 | rl-v1.1 | search | False | 105 | 66 | 0.629 |
| bench-v2 | rl-v1.1 | stages | False | 112 | 89 | 0.795 |
| bench-v2 | rl-v1.1 | stages | True | 4 | 4 | 1.000 |
| verifier-rl-v1 | rl-v1 | - | False | 100 | 63 | 0.630 |

### Split sizes (per fold: train / test / test rows dropped as (tok, spec) leaks / fenced in test)

| split | folds |
|---|---|
| SF | f0: 6196/3855/0/710; f1: 5775/3697/0/131; f2: 6711/5226/0/2596 |
| PA | f0: 5916/3427/0/2; f1: 6480/3139/0/278; f2: 8446/3994/0/3099; f3: 8306/1037/0/2; f4: 8374/1023/0/56 |
| CELL | f0: 7368/2791/2/820; f1: 7486/2801/4/950; f2: 7784/2512/4/959; f3: 7350/2457/6/472; f4: 7376/2197/4/236 |
| TIME | f0: 7187/3773/61/1680 |

TIME split cut: `ts` ≥ 2026-10-01T02:56:21 is test.

### Metrics — variant `bv2` (pooled out-of-fold, non-fenced bench-v2 test rows)

| split | model | n | pos | AUC | prune@95 oracle | per-fold oracle | prune@95 deployable (recall) | ECE | margin MAE | MAE (pred clipped) | search AUC | search prune@95 | F2 AUC | F2 prune@95 | stages AUC | stages prune@95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SF | lr | 9341 | 3556 | 0.846 | **0.323** | 0.33, 0.31, 0.35 | 0.378 (0.922) | 0.042 | 0.339 | 0.338 | 0.785 | 0.220 | 0.586 | 0.302 | 0.875 | 0.432 |
| SF | mlp | 9341 | 3556 | 0.887 | **0.403** | 0.38, 0.39, 0.45 | 0.428 (0.933) | 0.041 | 0.285 | 0.285 | 0.827 | 0.252 | 0.691 | 0.388 | 0.907 | 0.515 |
| SF | gnn | 9341 | 3556 | 0.900 | **0.418** | 0.40, 0.37, 0.47 | 0.454 (0.930) | 0.046 | 0.286 | 0.286 | 0.861 | 0.273 | 0.647 | 0.328 | 0.904 | 0.501 |
| PA | lr | 9183 | 3524 | 0.714 | **0.158** | 0.12, 0.17, 0.37, 0.16, 0.64 | 0.464 (0.765) | 0.136 | 8.063 | 0.486 | 0.635 | 0.109 | 0.765 | 0.244 | 0.673 | 0.151 |
| PA | mlp | 9183 | 3524 | 0.776 | **0.252** | 0.19, 0.29, 0.04, 0.18, 0.85 | 0.533 (0.785) | 0.157 | 14.746 | 0.393 | 0.683 | 0.153 | 0.798 | 0.288 | 0.763 | 0.334 |
| PA | gnn | 9183 | 3524 | 0.759 | **0.235** | 0.18, 0.29, 0.27, 0.05, 0.68 | 0.511 (0.744) | 0.150 | 0.433 | 0.433 | 0.706 | 0.161 | 0.766 | 0.355 | 0.698 | 0.244 |
| CELL | lr | 9321 | 3541 | 0.881 | **0.381** | 0.32, 0.36, 0.40, 0.37, 0.40 | 0.426 (0.932) | 0.044 | 0.329 | 0.329 | 0.809 | 0.230 | 0.771 | 0.334 | 0.892 | 0.434 |
| CELL | mlp | 9321 | 3541 | 0.916 | **0.477** | 0.47, 0.49, 0.43, 0.47, 0.50 | 0.485 (0.943) | 0.019 | 0.273 | 0.272 | 0.854 | 0.268 | 0.830 | 0.536 | 0.928 | 0.567 |
| CELL | gnn | 9321 | 3541 | 0.929 | **0.497** | 0.53, 0.50, 0.44, 0.48, 0.52 | 0.486 (0.954) | 0.016 | 0.267 | 0.267 | 0.883 | 0.290 | 0.863 | 0.598 | 0.929 | 0.573 |
| TIME | lr | 2093 | 677 | 0.865 | **0.249** | 0.25 | 0.394 (0.925) | 0.074 | 0.369 | 0.369 | 0.801 | 0.210 | 0.845 | 0.156 | 0.893 | 0.421 |
| TIME | mlp | 2093 | 677 | 0.903 | **0.470** | 0.47 | 0.463 (0.956) | 0.061 | 0.325 | 0.325 | 0.860 | 0.288 | 0.728 | 0.411 | 0.937 | 0.627 |
| TIME | gnn | 2093 | 677 | 0.905 | **0.450** | 0.45 | 0.543 (0.889) | 0.045 | 0.316 | 0.315 | 0.893 | 0.320 | 0.672 | 0.500 | 0.938 | 0.638 |

### Metrics — variant `aux` (pooled out-of-fold, non-fenced bench-v2 test rows)

| split | model | n | pos | AUC | prune@95 oracle | per-fold oracle | prune@95 deployable (recall) | ECE | margin MAE | MAE (pred clipped) | search AUC | search prune@95 | F2 AUC | F2 prune@95 | stages AUC | stages prune@95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SF | lr | 9341 | 3556 | 0.834 | **0.332** | 0.33, 0.30, 0.31 | 0.382 (0.918) | 0.065 | 0.343 | 0.343 | 0.775 | 0.216 | 0.514 | 0.330 | 0.872 | 0.432 |
| SF | mlp | 9341 | 3556 | 0.881 | **0.397** | 0.38, 0.33, 0.49 | 0.428 (0.933) | 0.062 | 0.278 | 0.278 | 0.834 | 0.252 | 0.624 | 0.361 | 0.911 | 0.539 |
| SF | gnn | 9341 | 3556 | 0.892 | **0.415** | 0.41, 0.35, 0.49 | 0.424 (0.944) | 0.047 | 0.284 | 0.283 | 0.871 | 0.278 | 0.631 | 0.296 | 0.903 | 0.527 |
| PA | lr | 9183 | 3524 | 0.819 | **0.252** | 0.10, 0.17, 0.33, 0.22, 0.60 | 0.323 (0.921) | 0.069 | 7.985 | 0.433 | 0.765 | 0.199 | 0.694 | 0.193 | 0.822 | 0.369 |
| PA | mlp | 9183 | 3524 | 0.810 | **0.283** | 0.12, 0.21, 0.04, 0.22, 0.81 | 0.415 (0.883) | 0.072 | 17.655 | 0.362 | 0.747 | 0.194 | 0.751 | 0.279 | 0.829 | 0.405 |
| PA | gnn | 9183 | 3524 | 0.814 | **0.308** | 0.07, 0.32, 0.21, 0.12, 0.70 | 0.384 (0.905) | 0.096 | 0.378 | 0.378 | 0.799 | 0.222 | 0.565 | 0.295 | 0.811 | 0.368 |
| CELL | lr | 9321 | 3541 | 0.877 | **0.368** | 0.34, 0.33, 0.40, 0.36, 0.40 | 0.421 (0.930) | 0.035 | 0.334 | 0.334 | 0.803 | 0.226 | 0.731 | 0.311 | 0.891 | 0.457 |
| CELL | mlp | 9321 | 3541 | 0.918 | **0.472** | 0.46, 0.49, 0.44, 0.48, 0.49 | 0.485 (0.944) | 0.025 | 0.266 | 0.266 | 0.861 | 0.275 | 0.824 | 0.584 | 0.929 | 0.575 |
| CELL | gnn | 9321 | 3541 | 0.932 | **0.494** | 0.54, 0.49, 0.43, 0.49, 0.51 | 0.490 (0.951) | 0.010 | 0.253 | 0.252 | 0.894 | 0.298 | 0.874 | 0.677 | 0.931 | 0.581 |
| TIME | lr | 2093 | 677 | 0.853 | **0.245** | 0.25 | 0.366 (0.914) | 0.096 | 0.372 | 0.372 | 0.792 | 0.199 | 0.578 | 0.205 | 0.893 | 0.416 |
| TIME | mlp | 2093 | 677 | 0.888 | **0.423** | 0.42 | 0.433 (0.941) | 0.070 | 0.339 | 0.339 | 0.853 | 0.278 | 0.650 | 0.414 | 0.940 | 0.645 |
| TIME | gnn | 2093 | 677 | 0.877 | **0.438** | 0.44 | 0.548 (0.852) | 0.057 | 0.338 | 0.338 | 0.867 | 0.288 | 0.616 | 0.375 | 0.941 | 0.643 |

### Fenced rows (accepted bench-v2 cells; eval-only, never trained or tuned on)

| split | model | n | pos | AUC | prune@95 oracle | prune@95 deployable (recall) | ECE |
|---|---|---|---|---|---|---|---|
| SF | lr | 3437 | 8 | 0.962 | 0.920 | 0.997 (0.500) | 0.023 |
| SF | mlp | 3437 | 8 | 0.983 | 0.962 | 0.969 (0.875) | 0.016 |
| SF | gnn | 3437 | 8 | 0.983 | 0.961 | 0.984 (0.500) | 0.013 |
| PA | lr | 3437 | 8 | 0.953 | 0.903 | 0.981 (0.500) | 0.019 |
| PA | mlp | 3437 | 8 | 0.931 | 0.855 | 0.997 (0.500) | 0.009 |
| PA | gnn | 3437 | 8 | 0.964 | 0.921 | 0.978 (0.500) | 0.017 |
| CELL | lr | 3437 | 8 | 0.987 | 0.967 | 0.981 (1.000) | 0.018 |
| CELL | mlp | 3437 | 8 | 1.000 | 0.997 | 0.989 (1.000) | 0.009 |
| CELL | gnn | 3437 | 8 | 0.999 | 0.994 | 0.989 (1.000) | 0.008 |
| TIME | lr | 1680 | 4 | 1.000 | 0.998 | 0.961 (1.000) | 0.024 |
| TIME | mlp | 1680 | 4 | 1.000 | 0.998 | 0.977 (1.000) | 0.010 |
| TIME | gnn | 1680 | 4 | 1.000 | 0.998 | 0.991 (1.000) | 0.007 |

### Prune fraction at other recall levels (oracle threshold, pooled OOF, bv2 variant)

| split | model | pop | R=0.99 | R=0.95 | R=0.90 | R=0.80 |
|---|---|---|---|---|---|---|
| SF | lr | all | 0.162 | 0.323 | 0.416 | 0.528 |
| SF | lr | search | 0.102 | 0.220 | 0.289 | 0.394 |
| SF | mlp | all | 0.241 | 0.403 | 0.489 | 0.583 |
| SF | mlp | search | 0.169 | 0.252 | 0.323 | 0.417 |
| SF | gnn | all | 0.244 | 0.418 | 0.492 | 0.592 |
| SF | gnn | search | 0.176 | 0.273 | 0.339 | 0.437 |
| PA | lr | all | 0.055 | 0.158 | 0.267 | 0.385 |
| PA | lr | search | 0.048 | 0.109 | 0.161 | 0.268 |
| PA | mlp | all | 0.051 | 0.252 | 0.348 | 0.478 |
| PA | mlp | search | 0.025 | 0.153 | 0.220 | 0.329 |
| PA | gnn | all | 0.092 | 0.235 | 0.319 | 0.444 |
| PA | gnn | search | 0.075 | 0.161 | 0.227 | 0.337 |
| CELL | lr | all | 0.210 | 0.381 | 0.489 | 0.587 |
| CELL | lr | search | 0.126 | 0.230 | 0.303 | 0.407 |
| CELL | mlp | all | 0.335 | 0.477 | 0.533 | 0.613 |
| CELL | mlp | search | 0.174 | 0.268 | 0.327 | 0.434 |
| CELL | gnn | all | 0.386 | 0.497 | 0.546 | 0.623 |
| CELL | gnn | search | 0.183 | 0.290 | 0.354 | 0.456 |
| TIME | lr | all | 0.147 | 0.249 | 0.462 | 0.619 |
| TIME | lr | search | 0.126 | 0.210 | 0.290 | 0.440 |
| TIME | mlp | all | 0.326 | 0.470 | 0.529 | 0.624 |
| TIME | mlp | search | 0.192 | 0.288 | 0.377 | 0.469 |
| TIME | gnn | all | 0.316 | 0.450 | 0.535 | 0.621 |
| TIME | gnn | search | 0.185 | 0.320 | 0.397 | 0.503 |

### Decision rule (prune@95 oracle ≥ 0.50 on the held-out split; primary variant bv2, population all)

| model | SF | PA | CELL | TIME | all four |
|---|---|---|---|---|---|
| lr | 0.323 fail | 0.158 fail | 0.381 fail | 0.249 fail | **FAIL** |
| mlp | 0.403 fail | 0.252 fail | 0.477 fail | 0.470 fail | **FAIL** |
| gnn | 0.418 fail | 0.235 fail | 0.497 fail | 0.450 fail | **FAIL** |

Overall: **FAIL**

### Transfer: full-data bv2 model → verifier-rl-v1 rows (rl-v1 on v1.2 cells, n=100)

| model | n | pos | AUC | prune@95 oracle | prune / recall at the val threshold | ECE |
|---|---|---|---|---|---|---|
| lr | 100 | 63 | 0.892 | 0.310 | 0.420 / 0.778 | 0.405 |
| mlp | 100 | 63 | 0.930 | 0.270 | 0.320 / 0.921 | 0.218 |
| gnn | 100 | 63 | 0.952 | 0.230 | 0.180 / 1.000 | 0.118 |

Checkpoints:

- `checkpoints/full_lr.pt`: 6309 bytes, sha256 `69320391bc0db94773a4f9efbe512b4a2fbd3487d7932a192c70a4ce2f14bffb`, val threshold at 95 % recall = 0.2219, train 8422 / val 919
- `checkpoints/full_mlp.pt`: 376709 bytes, sha256 `5429576d5a44fabc790acb5ec769c2966a44316785d56bce1710b140e5669749`, val threshold at 95 % recall = 0.2202, train 8422 / val 919
- `checkpoints/full_gnn.pt`: 4608851 bytes, sha256 `c71df61295e5497f04988fa90b11014002b40068007fc0e1ed1b4a5a36746ab9`, val threshold at 95 % recall = 0.2934, train 8422 / val 919

### CPU projection (descriptive; the decision rule governs the verdict)

- Measured bench-v2 search sizing call: mean 94 s and median 96 s of wall time per call (n=4486, box load 8–15). The brief's figure is 116 CPU-s per candidate (R1).
- Sized bench-v2 calls in the snapshot: 18799. Of these, 8267 are search/confirm.

| pop | split | best model | prune@95 | CPU-h saved per 1000 candidates (×116 s) | SPICE calls per feasible found (relative) |
|---|---|---|---|---|---|
| all | CELL | gnn | 0.497 | 16.0 | 0.53 |
| all | PA | mlp | 0.252 | 8.1 | 0.79 |
| all | SF | gnn | 0.418 | 13.5 | 0.61 |
| all | TIME | mlp | 0.470 | 15.1 | 0.56 |
| search | CELL | gnn | 0.290 | 9.3 | 0.75 |
| search | PA | gnn | 0.161 | 5.2 | 0.88 |
| search | SF | gnn | 0.273 | 8.8 | 0.77 |
| search | TIME | gnn | 0.320 | 10.3 | 0.72 |


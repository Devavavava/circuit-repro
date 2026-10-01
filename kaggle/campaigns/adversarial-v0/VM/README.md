# adversarial-v0 / VM — value model (search pruner)

Pre-registered in `kaggle/PREREG-ADVERSARIAL-V0.md` (commit `307673caf`), section VM.
- Run: 2026-10-01, local CPU, torch 2.13 CPU with 4 threads. No SPICE was run.
- The bench-v2 run was **live**, so it was read as a snapshot: the first 21 660 lines of `results.jsonl`, taken at 20:48 IST. md5s are in `data/build_manifest.json`.

## Verdict: **FAIL** — the VM is not useful as a search pruner by the pre-registered rule

The rule is prune ≥ 50 % at ≥ 95 % recall on the held-out split.
- **No model meets it on any split.** The best is the GNN on the CELL split at **0.497**. The other splits:
  - SF (spec family): best 0.418
  - PA (parent anchor): best 0.252
  - TIME: best 0.470
- **On the bench-v2-style search population (search + confirm rows), prune@95 is only 0.16–0.32.**
  - This population is 57 % feasible after mutate-then-repair under the loose probe spec.
  - So even a perfect model could prune at most 1 − 0.95 × 0.57 ≈ 0.46 there.
- **The models do rank well.**
  - GNN AUC is 0.90 (SF), 0.93 (CELL) and 0.91 (TIME), and ECE is 0.02–0.05.
  - Margin MAE is about 0.27–0.29 (normalized units).
  - The GNN is better than the MLP, and the MLP is better than LR, on every split except PA.
- **Generalizing to an unseen parent anchor (PA) is the weak point.**
  - AUC is 0.71–0.78 and ECE is 0.15.
  - Holding out a3 or a4 gives prune@95 of 0.04–0.29; holding out a5 gives 0.64–0.85.
  - The deployable (validation-set) threshold then reaches only 74–79 % recall.
- **Label noise sits at the target recall** (`noise.py` → `results/noise.json`).
  - For the same (tokens, spec), the seed-1 verdict predicts the seed-2 verdict with recall **0.949** (precision 0.83, n = 3947 pairs).
  - 21 % of the (tokens, spec) pairs that are feasible at some seed flip across seeds.
  - So 95 % recall against a single-seed label is at the sizer's own noise floor.
- **Adding the aux rows (v1.2 audit and rl-readiness, legacy verifiers) does not help** on SF, CELL or TIME.
  - It raises PA (GNN AUC 0.76 → 0.81). That gain is partly leakage: the v1.2 rows contain the same anchor families, so this is not real anchor generalization.
- **Fenced rows** (accepted bench-v2 cells; eval-only):
  - AUC is 0.93–1.00 and oracle prune@95 is 0.86–1.00.
  - But there are only 8 positives in 3437 rows, almost all of them F2 single-edit nulls. This is not evidence of pruning power on new witnesses.
- **Transfer check** (full bv2 model → 100 rl-v1 rows on the v1.2 cells):
  - GNN AUC is 0.95, but prune@95 is only 0.23.

**What it would buy anyway** (descriptive only; the rule failed). At 95 % recall and 116 CPU-s per candidate:
- The best measured prune saves about **9–10 CPU-h per 1000 search candidates** (search population, GNN, 0.27–0.32 prune).
- It saves about 13–16 CPU-h per 1000 mixed bench-v2 sizing calls (0.42–0.50 prune; these include F2 and stage calls).
- For an RL round of about 2.7 sizable edits per rollout (310 CPU-s), a 0.3 prune would save about 90 CPU-s per rollout. But a pruned edit then gets its reward from the VM, which is exactly the reward-hacking surface EX is about.
- **The VM is usable as an orderer, not a pruner.** Size candidates in descending P(feasible), or prune at 80–90 % recall where that is acceptable: 0.34–0.50 prune on search at R = 0.80. Every verdict still comes from SPICE.

## Analysis protocol (fixed before any model was trained)

This section was written after the data table was built (`build_data.py`) and before any model was fit.

**Task.** Score a (topology, spec) pair *before* sizing with P(feasible under verifier rl-v1.1 at seed × 2500 evals). A pruner skips the SPICE sizing of low-scoring candidates. Final verdicts stay with SPICE.

**Population.** Only candidates that would actually be sized under rl-v1.1:
- They pass the free 0-sim checks: topology limits, structural degeneracy and the port-DC pre-filter.
- Pre-sizing rejects cost nothing, so pruning them saves nothing. They are excluded rather than counted as easy prunes.

**Primary data.** These are the bench-v2 rows (`profile` rl-v1 or rl-v1.1).

**Auxiliary data.** These rows are training-only, in the "+aux" ablation:
- v1.2-audit and rl-readiness rows, each under its own verifier.
- `profile` is a model feature.
- Aux rows are never in a primary test set. The one exception is the rl-v1 rows of `verifier-rl-v1`, which serve as a small cross-campaign transfer check.

**Label.** `y` is computed as follows:
- An rl-v1.1 row uses `res.feasible`.
- An rl-v1 row uses `res.feasible AND port_dc_prefilter(tokens).pass`. Bench-v2 D23 shows the behavioural check is a no-op for pre-filter-passing topologies, and 160/160 rl-v1.1 behavioural checks in this snapshot passed.
- An aux row uses its own profile's verdict.

**Margin target.** `wm` is the worst normalized constraint margin of the sizer's winner. It uses `mysolve._margins` semantics, re-implemented in `build_data.worst_margin`.

**Splits.** Every split assigns whole groups, never random rows.

| split | unit held out | folds |
|---|---|---|
| **SF** spec family | bench-v2 grid point (band × flavor, 21 points). A point is in fold `(band_idx + flavor_idx) mod 3`. | 3 (7 grid points each) |
| **PA** parent anchor | topology lineage anchor a1–a5: the parent of a search candidate or cell; for F1/T-F1/cal rows, the anchor itself. Rows with an unknown lineage are train-only. | 5 (leave one anchor out) |
| **CELL** bench-v2 cell | group = cell / training task / search candidate id / (cal, grid point, anchor). A group is in fold `sha1(group) mod 5`. | 5 |
| **TIME** | bench-v2 rows with `ts` before the 70th percentile of included bench-v2 `ts` are train; the rest are test. | 1 |

**Rules applied to every split:**
- Any test row whose `(tok, spec_sha)` pair also occurs in that fold's training rows is **dropped from test**. The count is reported.
- **Fence.** Rows from bench-v2 cells that were *ever* accepted, in any era, are **never trained on**. They sit in their natural test fold, are scored by that fold's model, and are reported separately. Nothing is tuned on them.
- **Inner validation.** 10 % of each fold's training groups (`sha1(group + "|val") mod 10 == 0`) are used for early stopping and for the deployable threshold only.

**Models.** Each model is multi-task: a feasibility logit plus a margin regression head.
- **LR:** hand features → a linear model with both heads.
- **MLP:** hand features → 2×128 MLP. Ensemble of 3 seeds.
- **GNN:** a device–net bipartite MPNN, following the idea of `lna/critic_gnn.py` and reimplemented here because that file imports Windows-path modules. It uses edge maps per (device type, pin role), 3 rounds, sum+max+port-node readout, and the spec vector concatenated at the readout. Ensemble of 3 seeds.

Training variants: **bv2** (bench-v2 rows only; this is the primary) and **+aux**.

**Metrics.** All metrics are computed on pooled out-of-fold test predictions, non-fenced bench-v2 rows.
- **AUC.**
- **Prune@95 (oracle).** Take the threshold at the score of the feasible row at the 5 % recall-loss point of the test set, then report the fraction of test candidates scored below it. This is the pre-registered definition.
- **Prune@95 (deployable).** The threshold is fixed on inner validation at 95 % recall, then applied to test. Report the realized recall and prune fraction.
- **ECE.** 10 equal-width bins.
- **Margin MAE.** `wm` clipped to [-2, 2].

Every metric is also reported on these subpopulations:
- `search`: search + confirm rows, which is the bench-v2-style search.
- `F2`: the single-edit null.
- `stages`: cell/task validation rows.
- `fenced`: separately.

**Decision rule** (pre-registered): a model is "useful as a search pruner" iff prune@95 (oracle) ≥ 50 % on the held-out split. The rule is applied to each model on each split (SF, PA, CELL, TIME) for the primary bv2 variant.
- **Verdict PASS** iff at least one model meets the rule on **all four** splits.
- It is reported alongside the `search` subpopulation and the deployable threshold. If the deployable threshold misses 95 % recall, that is flagged.

## Results

All tables are generated by `report.py`, and `results/report.md` is the same content. Columns:
- **prune@95 oracle:** the pre-registered definition, with the threshold set on the test fold itself.
- **deployable:** the threshold is set on inner validation, then applied to test. The realized recall is shown in brackets.
- **per-fold oracle:** the per-fold values behind the pooled number.
- PA fold order is a1 … a5.

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


## Caveats

- **Population.** Only candidates that rl-v1.1 would actually size are scored. Free pre-sizing rejects and rl-v1 rows whose topology fails the port-DC pre-filter are excluded: 2861 + 5418 + 495 derived + 108 duplicate bench-v2 rows.
- **Prune fraction depends on the population's base rate.**
  - The pre-registered "all" population mixes three things:
    - search rows: 57 % feasible
    - cell/task stage rows: 30–80 % feasible
    - F2 single-edit nulls: 3.6 % feasible
  - A low-feasibility, RL-style edit distribution (E-d Qwen edits are about 5 % feasible) would have more prune headroom. Its AUC and recall, however, have not been measured under rl-v1.1.
- **Label noise across seeds and profiles.**
  - The noise across seeds is described in the verdict above.
  - rl-v1 labels are mapped to rl-v1.1 through the pre-filter (D23). In this snapshot, 160/160 rl-v1.1 behavioural checks passed, so no row is known to be mislabeled by this mapping.
  - Aux labels come from other verifiers (lib spec without a stability gate, gate-only, in-loop). They are used only in the +aux ablation, with `profile` as a feature.
- **Distribution shift.**
  - **TIME:** after the 70th-percentile cut (2026-10-01 02:56), the test rows are mostly amendment-1 late generations and amendment-2 rows. GNN AUC holds at 0.905.
  - **PA:** this is the real weakness. An unseen anchor family, a3 or a4, is close to unpredictable for the pruning purpose.
  - The search generator is steered, so later candidates are not i.i.d. with the earlier ones.
- **Selection in the data.**
  - Confirm rows are seeds 1 and 2 of search winners. Cell stage rows exist only for planted (seed-1-feasible) witnesses. Both raise base rates.
  - In the split rules, the same (tokens, spec) never appears on both sides, and groups are never split. The same topology *can* appear with a different spec. For example, a search candidate under its probe spec and its planted cell spec land in different groups, and only a different spec is held out.
- **GNN run-to-run variation.** CPU `index_add` is not bit-deterministic across thread schedules. A smoke run of bv2/SF/GNN before the final run gave AUC 0.903 and prune 0.427; the recorded run gave 0.900 and 0.418. Only the recorded run is reported. The verdict margin, 0.497 vs 0.50 for CELL, is within this variation. But the rule needs all four splits, and SF and PA fail by a wide margin.

## Deviations / interpretations

1. **Population (interpretation).** The VM scores only rl-v1.1-sizable candidates; see Caveats. The pre-reg said "~28k rows". There are 29 862 recorded rows across the sources, and 17 345 are included: 12 778 bench-v2 and 4 567 aux.
2. **S-1 and stability-gate rows are excluded** (430 rows): they were recorded without token sequences.
3. **Special-config rows of R4 and verifier-rl-v1 are excluded** (reg*, win50, struct/topo-only): these are regression probes, not verifier configs.
4. **The aux rows are training-only (the +aux ablation)**, because their verifiers differ. The 100 rl-v1 rows of `verifier-rl-v1` serve as a transfer test.
5. **`lna/critic_gnn.py` is not imported.** It imports `critic`/`datastore`, which carry Windows-era paths. The idea is reimplemented in `train.py:GNN`: bipartite device↔node MPNN, per-(type, role) edge maps, sum+max pooling, spec at the readout. The ensemble has 3 seeds where critic_gnn used 5.
6. **The decision rule's aggregation was fixed in the protocol section before training:** pass on all four splits with one model. Under any looser reading the verdict is the same, since no (model, split) cell reaches 0.50.
7. **Descriptive analyses added after the protocol was written:**
   - the margin MAE with the prediction clipped to [−2, 2]. LR and MLP margin heads extrapolate wildly on the PA split, giving raw MAE of 8–18.
   - the prune-vs-recall table
   - the noise ceiling (`noise.py`)
   - the CPU projection, computed although the rule failed

   None of these changed a model or a threshold.
8. **Fence.** These rows are fenced: every row of a bench-v2 cell that was ever `accepted`, in any era, including the 16 cells later tagged `amend2-port-dc`. Their witness rows mostly fail the pre-filter, so most fenced rows that remain are F1/F2 rows.

## Files

| file | role |
|---|---|
| `build_data.py` | Builds the unified table → `data/rows.jsonl.gz`, `data/tokmap.json.gz`, `data/specs.json.gz`, `data/build_manifest.json`. It reads every source read-only, and imports `bench_anchor_prep` only for its 0-sim pre-filters. |
| `features.py` | Graph parse (`Topology` nodes), hand features, spec vector. |
| `train.py` | Splits, LR/MLP/GNN, out-of-fold predictions (`results/oof_*.npz`), `results/metrics.json`, `results/folds.json`, full-data checkpoints. |
| `report.py` | Tables → `results/report.md`. |
| `noise.py` | Seed-noise ceiling → `results/noise.json`. |
| `checkpoints/full_{lr,mlp,gnn}.pt` | Trained on all non-fenced bench-v2 rows; sha256 values are in the table above. 4.6 MB max. |
| `results/train_all.log` | Log of the recorded run. |

Reproduce:

```
envrun.sh python kaggle/campaigns/adversarial-v0/VM/build_data.py
envrun.sh python kaggle/campaigns/adversarial-v0/VM/train.py --full
envrun.sh python kaggle/campaigns/adversarial-v0/VM/report.py
```

The full training run takes about 75 min at 4 threads on the shared box.

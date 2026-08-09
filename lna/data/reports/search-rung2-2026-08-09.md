# WP-SEARCH rung 2 — evolutionary search over graph edits (Session 5, 2026-08-09)

Raw run record for FINDINGS §15. Four arms, two specs, equal-cost controls.
Critic v1 = the GNN ensemble of 02-CRITIC, snapshot `v4-train`, 5 models.
Every number below is SPICE except the block explicitly marked *critic calibration*.

Reproduce: `python lna/evolve.py --spec <spec> --arm evolve|random --pop 32 --children 24 --gens 20 --elites 2 --explore 1 --true-evals 60 --zoaf-cand 8 --zoaf-sgd 8 --zoaf-cgd 2 --polish-budget 80 --seed 1337`


## wideband-sdr

```
# rung-2 scoreboard — wideband-sdr

arm         true  SPICEmin  feas  novel  near  best viol  min/feas  K<1
evolve        42      51.2     0      0     6      1.782       inf    6
random        60      76.0     0      0     9      1.931       inf   14

at an equal budget of 51.2 SPICE-min (both arms truncated to the smaller arm's spend):
arm         true  feas  novel  near  best viol
evolve        42     0      0     6      1.782
random        39     0      0     8      1.931

Gate S2 (03-SEARCH §2): evolutionary feasible-novel >= 2x the control at equal true-eval budget
  evolve 0 novel-feasible in 51.2 SPICE-min (42 true evals) vs control 0 in 76.0 SPICE-min (60 true evals)
  verdict: NOT MET (both arms 0)
  near-feasible (all margins > -1 scale unit): evolve 6 vs control 9 (ratio 0.67x)
  best total violation: evolve 1.782 vs control 1.931

critic-vs-SPICE on evolve elites (n=42, critic v1 @ v4-train):
  rho(S11 margin) = +0.573
  rho(S21 margin) = -0.267
  rho(Idd margin) = +0.165
  rho(NF  margin) = -0.374
  rho(feasibility scalar) = -0.299
  rho(selection fitness)  = -0.400
  rho(ensemble std, |error|) = +0.144   <- the uncertainty gate's premise

binding constraints over every true eval (what the topology search is up against):
  evolve   n=42: nf_db 42/42 (best gap 0.168), s21_ripple_db 40/42 (best gap 0.201), s11_db 33/42 (best gap 0.084), s21_db 32/42 (best gap 0.055), idd_ma 6/42 (best gap 0.010)
  random   n=60: nf_db 60/60 (best gap 0.378), s11_db 56/60 (best gap 0.058), s21_db 56/60 (best gap 0.006), s21_ripple_db 42/60 (best gap 0.012), idd_ma 17/60 (best gap 0.136)

move attribution — which edits produced the 10 lowest-violation designs:
  device_removex2, gen:ft_p5v2_wb_s1337/seq0129.txtx1, stage_addx1, archetype:cs_gi1_dg0_cx1_cc0_R_bf1x1, archetype:cs_gi1_dg0_cx1_cc0_R_bf0x1, load_swapx1, input_class_swapx1, rewirex1, archetype:gmbcg_wb_s0_b1x1

best designs by realized total violation (SPICE, not critic):
  evolve  g2  01389e803d2e viol=  1.782 novel=False dev=4   [gen:ft_p5v2_wb_s] S11 -10.2 / S11max -5.0 / S21 -1.0 / rip 3.07 / Idd 0.35 / NF 4.09 / K 1.0
  evolve  g7  6507bd03296d viol=  1.822 novel=True  dev=12  [stage_add       ] S11 -17.5 / S11max -3.4 / S21 18.3 / rip 3.77 / Idd 3.12 / NF 6.78 / K 75.39
  evolve  g3  f2f10647ec88 viol=  1.897 novel=False dev=9   [archetype:cs_gi1] S11 -1.4 / S11max -0.1 / S21 13.5 / rip 2.4 / Idd 1.55 / NF 6.41 / K 8.9
  random  g9  b98fc1613945 viol=  1.931 novel=True  dev=10  [device_remove   ] S11 -2.2 / S11max -1.3 / S21 7.4 / rip 2.07 / Idd 7.76 / NF 6.04 / K 2.84
  evolve  g1  351ebeee9ef6 viol=  2.120 novel=False dev=6   [archetype:cs_gi1] S11 -1.8 / S11max -0.2 / S21 9.5 / rip 1.87 / Idd 7.42 / NF 7.33 / K 0.49
  random  g13 2e97470c762a viol=  2.190 novel=True  dev=13  [load_swap       ] S11 -0.7 / S11max -0.4 / S21 7.8 / rip 1.03 / Idd 5.36 / NF 6.69 / K 0.8
  random  g5  1bff739b9154 viol=  2.256 novel=True  dev=9   [input_class_swap] S11 -0.9 / S11max -0.7 / S21 7.3 / rip 2.09 / Idd 5.82 / NF 6.68 / K 1.39
  random  g10 643a88d82fe0 viol=  2.274 novel=True  dev=13  [rewire          ] S11 -1.2 / S11max -1.2 / S21 5.8 / rip 0.82 / Idd 6.97 / NF 6.57 / K 1.45
  evolve  g4  7a378b5f5a4b viol=  2.408 novel=False dev=8   [archetype:gmbcg_] S11 -14.6 / S11max -6.2 / S21 -1.1 / rip 4.19 / Idd 2.11 / NF 4.27 / K 1.01
  random  g11 ab4c28474778 viol=  2.479 novel=True  dev=14  [device_remove   ] S11 -2.6 / S11max -0.4 / S21 4.2 / rip 2.02 / Idd 5.33 / NF 7.25 / K 0.26
```

### critic calibration (NOT a result — 03-SEARCH §4 rule 4)

```
critic v1: {"snapshot": "v4-train", "sigma_s21": 0.7256776183870671, "n_models": 5, "n_train": 531, "n_val": 104, "n_holdout": 95, "sigma_gate_p90": 0.3101434051990511, "rho_s11": 0.5603019888614873, "rho_s21": 0.834175604128678, "rho_idd": 0.6122998255455809, "unc_cal": 0.5529986036510629, "rank_acc": 0.8409090909090909, "train_s": 429.3}

random arm, n=60 (critic scored POST HOC, never used for selection):
  rho(S11 margin) = +0.404
  rho(S21 margin) = +0.317
  rho(Idd margin) = +0.396
  rho(NF  margin) = +0.085
  rho(feasibility scalar) = +0.174
  rho(mean - beta*std)    = +0.175
  rho(ensemble std, |error|) = +0.147
  precision@top-20% = 0.250 vs base rate 0.150 -> enrichment 1.67x (ceiling 6.67x)

evolve arm, n=42 (selection-biased):
  rho(S11 margin) = +0.568
  rho(S21 margin) = -0.231
  rho(Idd margin) = +0.161
  rho(NF  margin) = -0.349
  rho(feasibility scalar) = -0.334
  rho(mean - beta*std)    = -0.345
  rho(ensemble std, |error|) = +0.274
  precision@top-20% = 0.125 vs base rate 0.143 -> enrichment 0.88x (ceiling 7.00x)
```

### population trajectory

| gen | children/tries | fit max | fit mean | trusted | far | mean dev | distinct WL | true evals | SPICE-min | best viol |
|---|---|---|---|---|---|---|---|---|---|---|
| **evolve** | | | | | | | | | | |
| 4 | 24/30 | -1.101 | -1.770 | 24 | 11 | 9.9 | 161 | 12 | 12.5 | 1.782 |
| 8 | 24/37 | -0.647 | -1.559 | 24 | 15 | 10.9 | 260 | 24 | 29.5 | 1.782 |
| 12 | 24/48 | -0.472 | -1.287 | 24 | 19 | 11.7 | 360 | 29 | 35.3 | 1.782 |
| 16 | 24/40 | -0.472 | -0.956 | 24 | 23 | 13.1 | 456 | 36 | 43.7 | 1.782 |
| 20 | 24/36 | -0.472 | -0.760 | 24 | 26 | 14.1 | 556 | 42 | 51.2 | 1.782 |
| **random** | | | | | | | | | | |
| 4 | 24/29 | 0.957 | 0.567 | 5 | 31 | 10.8 | 162 | 12 | 15.1 | 2.715 |
| 8 | 24/29 | 0.975 | 0.522 | 5 | 32 | 12.9 | 260 | 24 | 31.9 | 2.256 |
| 12 | 24/30 | 0.973 | 0.517 | 5 | 32 | 13.5 | 358 | 36 | 46.5 | 1.931 |
| 16 | 24/27 | 0.957 | 0.555 | 8 | 32 | 14.3 | 456 | 48 | 61.2 | 1.931 |
| 20 | 24/31 | 0.964 | 0.530 | 11 | 32 | 14.4 | 552 | 60 | 76.0 | 1.931 |

## dhruva-s

```
# rung-2 scoreboard — dhruva-s

arm         true  SPICEmin  feas  novel  near  best viol  min/feas  K<1
evolve        47      69.1     0      0    41      0.642       inf    2
random        60      62.4     0      0    28      1.070       inf   21

at an equal budget of 62.4 SPICE-min (both arms truncated to the smaller arm's spend):
arm         true  feas  novel  near  best viol
evolve        44     0      0    38      0.642
random        60     0      0    28      1.070

Gate S2 (03-SEARCH §2): evolutionary feasible-novel >= 2x the control at equal true-eval budget
  evolve 0 novel-feasible in 69.1 SPICE-min (47 true evals) vs control 0 in 62.4 SPICE-min (60 true evals)
  verdict: NOT MET (both arms 0)
  near-feasible (all margins > -1 scale unit): evolve 41 vs control 28 (ratio 1.46x)
  best total violation: evolve 0.642 vs control 1.070

critic-vs-SPICE on evolve elites (n=47, critic v1 @ v4-train):
  rho(S11 margin) = +0.011
  rho(S21 margin) = +0.202
  rho(Idd margin) = +0.634
  rho(NF  margin) = -0.002
  rho(feasibility scalar) = -0.007
  rho(selection fitness)  = -0.075
  rho(ensemble std, |error|) = -0.510   <- the uncertainty gate's premise

binding constraints over every true eval (what the topology search is up against):
  evolve   n=47: s21_db 45/47 (best gap 0.008), nf_db 45/47 (best gap 0.038), s11_max_db 40/47 (best gap 0.042), idd_ma 6/47 (best gap 0.002)
  random   n=60: s21_db 60/60 (best gap 0.063), nf_db 58/60 (best gap 0.045), s11_max_db 50/60 (best gap 0.036), idd_ma 6/60 (best gap 0.012)

move attribution — which edits produced the 10 lowest-violation designs:
  passive_type_swapx5, crossoverx2, load_swapx2, archetype:nccgcs_s1_Rx1

best designs by realized total violation (SPICE, not critic):
  evolve  g18 8c7592ea859e viol=  0.642 novel=True  dev=16  [passive_type_swa] S11 -10.3 / S11max -10.1 / S21 30.7 / rip 22.81 / Idd 12.58 / NF 5.75 / K 8.03
  evolve  g8  19f723034c0a viol=  0.664 novel=True  dev=16  [crossover       ] S11 -16.9 / S11max -16.9 / S21 20.1 / rip 2.79 / Idd 8.34 / NF 4.66 / K 50.94
  evolve  g1  7b0b485b629c viol=  0.673 novel=False dev=14  [archetype:nccgcs] S11 -8.2 / S11max -8.2 / S21 22.1 / rip 3.13 / Idd 3.54 / NF 4.29 / K 22.56
  evolve  g6  64b23fd6b6ec viol=  0.726 novel=True  dev=14  [passive_type_swa] S11 -11.4 / S11max -10.8 / S21 29.7 / rip 6.73 / Idd 11.79 / NF 6.01 / K 40.01
  evolve  g13 9a4fd0bd542a viol=  0.753 novel=True  dev=16  [passive_type_swa] S11 -11.4 / S11max -11.4 / S21 33.7 / rip 5.47 / Idd 14.26 / NF 5.8 / K 9.59
  evolve  g18 849b3ead4d5d viol=  0.778 novel=True  dev=16  [passive_type_swa] S11 -10.2 / S11max -10.2 / S21 26.5 / rip 2.84 / Idd 10.05 / NF 5.81 / K 7.26
  evolve  g12 be513e07047c viol=  0.781 novel=True  dev=16  [load_swap       ] S11 -10.0 / S11max -9.6 / S21 21.6 / rip 5.51 / Idd 15.52 / NF 4.42 / K 26.5
  evolve  g20 060397bc4603 viol=  0.790 novel=True  dev=16  [passive_type_swa] S11 -10.7 / S11max -10.6 / S21 26.8 / rip 11.07 / Idd 10.29 / NF 5.9 / K 57.74
  evolve  g2  bacaee40cc3e viol=  0.804 novel=True  dev=16  [load_swap       ] S11 -10.3 / S11max -8.7 / S21 26.3 / rip 4.93 / Idd 8.29 / NF 5.42 / K 8.04
  evolve  g6  44b905744eb9 viol=  0.877 novel=False dev=15  [crossover       ] S11 -9.7 / S11max -6.3 / S21 25.3 / rip 7.28 / Idd 8.91 / NF 4.74 / K 27.79
```

### critic calibration (NOT a result — 03-SEARCH §4 rule 4)

```
critic v1: {"snapshot": "v4-train", "sigma_s21": 0.7256776183870671, "n_models": 5, "n_train": 531, "n_val": 104, "n_holdout": 95, "sigma_gate_p90": 0.30787385106086756, "rho_s11": 0.6089700156399371, "rho_s21": 0.8394216391708899, "rho_idd": 0.6274859068859008, "unc_cal": 0.5428102762482176, "rank_acc": 0.8464114832535885, "train_s": 332.5}

random arm, n=60 (critic scored POST HOC, never used for selection):
  rho(S11 margin) = +0.451
  rho(S21 margin) = +0.298
  rho(Idd margin) = +0.472
  rho(NF  margin) = +0.375
  rho(feasibility scalar) = +0.198
  rho(mean - beta*std)    = +0.220
  rho(ensemble std, |error|) = +0.458
  precision@top-20% = 0.583 vs base rate 0.467 -> enrichment 1.25x (ceiling 2.14x)

evolve arm, n=47 (selection-biased):
  rho(S11 margin) = -0.054
  rho(S21 margin) = +0.176
  rho(Idd margin) = +0.631
  rho(NF  margin) = +0.076
  rho(feasibility scalar) = -0.030
  rho(mean - beta*std)    = -0.014
  rho(ensemble std, |error|) = +0.137
  precision@top-20% = 0.889 vs base rate 0.872 -> enrichment 1.02x (ceiling 1.15x)
```

### population trajectory

| gen | children/tries | fit max | fit mean | trusted | far | mean dev | distinct WL | true evals | SPICE-min | best viol |
|---|---|---|---|---|---|---|---|---|---|---|
| **evolve** | | | | | | | | | | |
| 4 | 24/33 | -0.496 | -1.226 | 24 | 11 | 13.1 | 161 | 12 | 18.7 | 0.673 |
| 8 | 24/34 | -0.312 | -0.784 | 24 | 15 | 15.0 | 258 | 24 | 35.7 | 0.664 |
| 12 | 24/30 | -0.229 | -0.583 | 24 | 19 | 15.3 | 354 | 35 | 49.8 | 0.664 |
| 16 | 24/38 | -0.229 | -0.474 | 24 | 23 | 15.5 | 450 | 42 | 58.8 | 0.664 |
| 20 | 24/68 | -0.219 | -0.418 | 24 | 27 | 15.8 | 546 | 47 | 69.1 | 0.642 |
| **random** | | | | | | | | | | |
| 4 | 24/27 | 0.968 | 0.537 | 4 | 29 | 10.1 | 167 | 12 | 12.8 | 1.070 |
| 8 | 24/27 | 0.970 | 0.485 | 3 | 31 | 12.0 | 267 | 24 | 23.9 | 1.070 |
| 12 | 24/31 | 0.959 | 0.550 | 4 | 32 | 12.7 | 365 | 36 | 35.2 | 1.070 |
| 16 | 24/31 | 0.997 | 0.503 | 2 | 32 | 13.2 | 467 | 48 | 49.0 | 1.070 |
| 20 | 24/29 | 0.997 | 0.573 | 4 | 32 | 13.4 | 567 | 60 | 62.4 | 1.070 |

## (a) Regression: lib specs (no mu_min) vs recorded rows

| exp | cell | cand | seed | recorded in | metrics identical | feasible new/rec | extra keys |
|---|---|---|---|---|---|---|---|
| negctl | v12-nb-f15-g16 | ec:d0be8b9bc6d6:032 | 1 | E-c/results.jsonl | True | True/True | none |
| negctl | v12-nb-f15-g16 | ec:d0be8b9bc6d6:032 | 2 | E-c/results.jsonl | True | True/True | none |
| negctl | v12-nb-f15-g16 | ec:d0be8b9bc6d6:032 | 3 | E-c/results.jsonl | True | True/True | none |
| regress | v12-nb-f15-g16 | ec:d0be8b9bc6d6:032 | 1 | E-c/results.jsonl | True | True/True | none |
| regress | v12-nb-f15-g16 | lna-a1-inddegen-cascode | 1 | E-b/results.json | True | True/True | none |
| regress | v12-wb-s11n10-g10-b0530 | template | 1 | E-a/results.json | True | True/True | none |
| regress | v12-wb-s11n10-g10-b0824 | lna-a1-inddegen-cascode | 1 | E-b/results.json | True | True/True | none |

## (b) Negative control: v12-nb-f15-g16, a5-CG anchor + `add L VIN1-n1`

| spec | seed | feasible | spec_feasible | mu_min in-band | mu_min wide | k_min wide | |D|max wide | stab_wide_ok | pts checked | replaced | worst (metric, margin) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| lib | 1 | True | - | 0.655 | - | - | - | - | - | - | ['s11_db', 0.0006800000000000139] |
| lib | 2 | True | - | 0.685 | - | - | - | - | - | - | ['s11_db', 7.999999999999118e-05] |
| lib | 3 | True | - | 0.347 | - | - | - | - | - | - | ['s11_db', 0.0009700000000000486] |
| stab | 1 | False | True | 1.009 | 0.998 | 0.999 | 0.964 | False | 1 | False | ['s21_db', 0.007843749999999927] |
| stab | 2 | False | True | 1.001 | 0.930 | 0.987 | 0.993 | False | 31 | False | ['s11_db', 0.0003500000000000725] |
| stab | 3 | False | True | 1.002 | -0.780 | -0.706 | 0.993 | False | 31 | False | ['s11_db', 0.0010300000000000864] |

## (c1) Reference templates x 16 cells, stability-enabled spec (2500 evals)

Per seed: F = final feasible (spec incl. in-band mu_min>=1 AND wide mu>=1), s = spec-feasible but wide-unstable, x = spec-infeasible. mu = in-band mu_min / wide mu_min of the reported winner.

| cell | cand | seeds 1/2/3 | final feasible | mu in-band (s1,s2,s3) | mu wide (s1,s2,s3) | replaced | worst binding (best seed) |
|---|---|---|---|---|---|---|---|
| v12-nb-f15-g12 | template | sFF | 2/3 | 1.00, 1.01, 1.00 | 1.00, 1.00, 1.00 | 1 | ['mu_min', 0.006389999999999896] |
| v12-nb-f15-g14 | template | FFF | 3/3 | 1.00, 1.02, 1.01 | 1.00, 1.00, 1.00 | 0 | ['mu_min', 0.01750000000000007] |
| v12-nb-f15-g16 | template | FFF | 3/3 | 1.00, 1.00, 1.00 | 1.00, 1.00, 1.00 | 0 | ['mu_min', 0.0013099999999999223] |
| v12-nb-f15-g18 | template | FFF | 3/3 | 1.00, 1.00, 1.00 | 1.00, 1.00, 1.00 | 1 | ['mu_min', 0.0023200000000000998] |
| v12-nb-f24-g12 | template | FsF | 2/3 | 1.01, 1.00, 1.02 | 1.00, 0.99, 1.00 | 2 | ['mu_min', 0.01797000000000004] |
| v12-nb-f24-g14 | template | sFs | 1/3 | 1.00, 1.00, 1.01 | 1.00, 1.00, 0.99 | 1 | ['mu_min', 0.0023599999999999177] |
| v12-nb-f24-g16 | template | FFF | 3/3 | 1.02, 1.02, 1.01 | 1.00, 1.00, 1.00 | 3 | ['mu_min', 0.023709999999999898] |
| v12-nb-f24-g18 | template | FFF | 3/3 | 1.01, 1.01, 1.02 | 1.00, 1.00, 1.00 | 3 | ['mu_min', 0.009949999999999903] |
| v12-wb-s11n10-g10-b0530 | template | sss | 0/3 | 1.00, 1.06, 1.07 | 0.35, 0.91, 0.93 | 0 | ['s11_max_db', 0.0018900000000000362] |
| v12-wb-s11n10-g10-b0824 | template | sss | 0/3 | 1.00, 1.00, 1.01 | -0.36, 0.42, 0.82 | 0 | ['s11_max_db', 0.0025399999999999425] |
| v12-wb-s11n10-g12-b0824 | template | sss | 0/3 | 1.00, 1.00, 1.00 | 0.88, 0.74, 0.89 | 0 | ['s21_db', 0.0006499999999999654] |
| v12-wb-s11n11-g10-b0824 | template | sss | 0/3 | 1.00, 1.00, 1.01 | 0.87, 0.82, 0.58 | 0 | ['s11_max_db', 0.0020545454545455107] |
| v12-wb-s11n11-g12-b0824 | template | sss | 0/3 | 1.00, 1.00, 1.00 | 0.64, 0.88, 0.90 | 0 | ['s11_max_db', 0.0008727272727273381] |
| v12-wb-s11n8-g10-b0530 | template | sss | 0/3 | 1.00, 1.00, 1.00 | 0.83, 0.60, 0.82 | 0 | ['mu_min', 0.0033199999999999896] |
| v12-wb-s11n8-g12-b0530 | template | xxs | 0/3 | 1.00, 1.00, 1.00 | -0.36, 0.89, 0.89 | 0 | ['mu_min', 9.999999999998899e-05] |
| v12-wb-s11n9-g10-b0530 | template | sss | 0/3 | 1.00, 1.00, 1.00 | 0.61, 0.59, 0.87 | 0 | ['mu_min', 0.0008200000000000429] |

## (c2) Library anchors a1..a5 x 8 nb cells, stability-enabled spec (2500 evals)

Per seed: F = final feasible (spec incl. in-band mu_min>=1 AND wide mu>=1), s = spec-feasible but wide-unstable, x = spec-infeasible. mu = in-band mu_min / wide mu_min of the reported winner.

| cell | cand | seeds 1/2/3 | final feasible | mu in-band (s1,s2,s3) | mu wide (s1,s2,s3) | replaced | worst binding (best seed) |
|---|---|---|---|---|---|---|---|
| v12-nb-f15-g12 | lna-a1-inddegen-cascode | sxs | 0/3 | 1.00, 1.89, 1.00 | 0.98, 1.00, 1.00 | 0 | ['mu_min', 0.0013600000000000279] |
| v12-nb-f15-g12 | lna-a2-current-reuse | xxx | 0/3 | 0.78, 0.77, 0.78 | 0.78, -0.20, 0.76 | 0 | ['mu_min', -0.21867800000000004] |
| v12-nb-f15-g12 | lna-a3-shunt-feedback | xxx | 0/3 | 1.05, 1.04, 1.06 | 0.58, 0.57, 0.58 | 0 | ['s11_db', -0.463347] |
| v12-nb-f15-g12 | lna-a4-twostage | sss | 0/3 | 1.03, 1.00, 1.00 | -1.26, -1.55, -1.54 | 0 | ['mu_min', 0.03157999999999994] |
| v12-nb-f15-g12 | lna-a5-commongate | xxx | 0/3 | 1.93, 1.95, 1.93 | 1.00, 1.00, 1.00 | 0 | ['s21_db', -0.29537250000000004] |
| v12-nb-f15-g14 | lna-a1-inddegen-cascode | FFF | 3/3 | 1.00, 1.03, 1.00 | 1.00, 1.00, 1.00 | 2 | ['idd_ma', 0.03454024999999994] |
| v12-nb-f15-g14 | lna-a2-current-reuse | xxx | 0/3 | 0.72, 0.70, 0.67 | 0.56, 0.70, 0.67 | 0 | ['mu_min', -0.281199] |
| v12-nb-f15-g14 | lna-a3-shunt-feedback | xxx | 0/3 | 1.05, 1.07, 1.08 | 0.59, 0.58, 0.63 | 0 | ['s11_db', -0.462597] |
| v12-nb-f15-g14 | lna-a4-twostage | sss | 0/3 | 1.00, 1.00, 1.01 | -0.96, -1.90, -1.53 | 0 | ['idd_ma', 0.002214500000000119] |
| v12-nb-f15-g14 | lna-a5-commongate | xxx | 0/3 | 1.92, 1.97, 1.92 | 1.00, 1.00, 1.00 | 0 | ['s21_db', -0.395985] |
| v12-nb-f15-g16 | lna-a1-inddegen-cascode | FFF | 3/3 | 1.00, 1.58, 1.00 | 1.00, 1.00, 1.00 | 1 | ['s11_db', 0.0007400000000000517] |
| v12-nb-f15-g16 | lna-a2-current-reuse | xxx | 0/3 | 0.61, 0.64, 0.59 | 0.61, 0.63, 0.59 | 0 | ['mu_min', -0.36150000000000004] |
| v12-nb-f15-g16 | lna-a3-shunt-feedback | xxx | 0/3 | 1.06, 1.07, 1.08 | 0.58, 0.63, 0.60 | 0 | ['s11_db', -0.46384600000000004] |
| v12-nb-f15-g16 | lna-a4-twostage | xss | 0/3 | 0.97, 1.00, 1.00 | -2.49, -0.32, -1.59 | 0 | ['mu_min', 0.0012499999999999734] |
| v12-nb-f15-g16 | lna-a5-commongate | xxx | 0/3 | 1.94, 1.96, 1.92 | 1.00, 1.00, 1.00 | 0 | ['s21_db', -0.4718325] |
| v12-nb-f15-g18 | lna-a1-inddegen-cascode | FxF | 2/3 | 1.00, 1.47, 1.00 | 1.00, 1.00, 1.00 | 1 | ['s11_db', 0.0009000000000000341] |
| v12-nb-f15-g18 | lna-a2-current-reuse | xxx | 0/3 | 0.65, 0.74, 0.75 | 0.38, 0.71, 0.34 | 0 | ['mu_min', -0.25372700000000004] |
| v12-nb-f15-g18 | lna-a3-shunt-feedback | xxx | 0/3 | 1.06, 1.09, 1.07 | 0.59, 0.63, 0.58 | 0 | ['s21_db', -0.5220988888888889] |
| v12-nb-f15-g18 | lna-a4-twostage | xss | 0/3 | 1.66, 1.01, 1.00 | -0.43, -1.09, -2.18 | 0 | ['mu_min', 0.007130000000000081] |
| v12-nb-f15-g18 | lna-a5-commongate | xxx | 0/3 | 1.98, 1.97, 1.95 | 1.00, 1.00, 1.00 | 0 | ['s21_db', -0.5311344444444445] |
| v12-nb-f24-g12 | lna-a1-inddegen-cascode | sFs | 1/3 | 1.00, 1.01, 1.00 | 0.97, 1.00, 0.97 | 0 | ['mu_min', 0.006729999999999903] |
| v12-nb-f24-g12 | lna-a2-current-reuse | xxx | 0/3 | 0.75, 0.82, 0.77 | -0.03, 0.34, -0.10 | 0 | ['mu_min', -0.18443200000000004] |
| v12-nb-f24-g12 | lna-a3-shunt-feedback | xxx | 0/3 | 1.00, 1.00, 1.00 | 0.62, 0.60, 0.60 | 0 | ['s11_db', -0.408312] |
| v12-nb-f24-g12 | lna-a4-twostage | sxs | 0/3 | 1.02, 1.00, 1.00 | -1.70, 0.64, -2.18 | 0 | ['idd_ma', 0.012414999999999954] |
| v12-nb-f24-g12 | lna-a5-commongate | xxx | 0/3 | 1.63, 1.64, 1.63 | 1.00, 1.00, 1.00 | 0 | ['s21_db', -0.2100708333333333] |
| v12-nb-f24-g14 | lna-a1-inddegen-cascode | sss | 0/3 | 1.01, 1.00, 1.01 | 0.97, 0.97, 0.97 | 0 | ['mu_min', 0.009079999999999977] |
| v12-nb-f24-g14 | lna-a2-current-reuse | xxx | 0/3 | 0.67, 0.66, 0.65 | 0.33, 0.05, 0.64 | 0 | ['mu_min', -0.33330499999999996] |
| v12-nb-f24-g14 | lna-a3-shunt-feedback | xxx | 0/3 | 1.00, 1.00, 1.00 | 0.61, 0.60, 0.61 | 0 | ['s11_db', -0.382391] |
| v12-nb-f24-g14 | lna-a4-twostage | sss | 0/3 | 1.01, 1.01, 1.00 | -0.98, -2.05, 0.05 | 0 | ['idd_ma', 0.003566250000000104] |
| v12-nb-f24-g14 | lna-a5-commongate | xxx | 0/3 | 1.62, 1.64, 1.64 | 1.00, 1.00, 1.00 | 0 | ['s21_db', -0.3228657142857143] |
| v12-nb-f24-g16 | lna-a1-inddegen-cascode | sFs | 1/3 | 1.01, 1.01, 1.01 | 0.98, 1.00, 0.96 | 0 | ['s11_db', 0.004570000000000007] |
| v12-nb-f24-g16 | lna-a2-current-reuse | xxx | 0/3 | 0.81, 0.63, 0.56 | 0.62, -0.89, -0.04 | 0 | ['s21_db', -0.28424375] |
| v12-nb-f24-g16 | lna-a3-shunt-feedback | xxx | 0/3 | 1.00, 1.02, 1.00 | 0.61, 0.61, 0.60 | 0 | ['s21_db', -0.457315] |
| v12-nb-f24-g16 | lna-a4-twostage | sss | 0/3 | 1.00, 1.00, 1.00 | -1.81, -1.01, -1.02 | 0 | ['idd_ma', 0.003562749999999948] |
| v12-nb-f24-g16 | lna-a5-commongate | xxx | 0/3 | 1.61, 1.62, 1.66 | 1.00, 1.00, 1.00 | 0 | ['s21_db', -0.40778000000000003] |
| v12-nb-f24-g18 | lna-a1-inddegen-cascode | FsF | 2/3 | 1.00, 1.00, 1.06 | 1.00, 0.96, 1.00 | 1 | ['s11_db', 0.05198999999999998] |
| v12-nb-f24-g18 | lna-a2-current-reuse | xxx | 0/3 | 0.65, 0.72, 0.66 | 0.65, -0.33, 0.63 | 0 | ['mu_min', -0.277617] |
| v12-nb-f24-g18 | lna-a3-shunt-feedback | xxx | 0/3 | 1.00, 1.00, 1.00 | 0.63, 0.61, 0.61 | 0 | ['s21_db', -0.5204650000000001] |
| v12-nb-f24-g18 | lna-a4-twostage | sss | 0/3 | 1.00, 1.00, 1.00 | -1.02, -1.11, -1.58 | 0 | ['mu_min', 0.0016400000000000858] |
| v12-nb-f24-g18 | lna-a5-commongate | xxx | 0/3 | 1.61, 1.61, 1.62 | 1.00, 1.00, 1.00 | 0 | ['s21_db', -0.47333222222222227] |

## Cost

- wide-stability sims: 2012 over 171 gated runs, 20.6 s total, 0.01 s per sim; max per run 31; median run wall 33.4 s.

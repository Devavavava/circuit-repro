# depth-probes-v1 -- tables

Pre-reg kaggle/PREREG-DEPTH-PROBES-V1.md (8b9a5ca08). Built 2026-10-18T03:52:54 by `depth.py summarize`. Tasks listed in the seeded run order (`depth-probes-v1`).

## Readings (tasks with non-empty A and B and complete measurements)

| metric | eligible tasks | B beats A | A beats B (control) | fraction B>A | verdict |
|---|---|---|---|---|---|
| corner worst margin (B >= A + 0.10, or B passes all corners and no A does) | 32 | 4 | 2 | 0.125 | no depth (< 5) |
| IIP3 (B >= A + 3 dB) | 32 | 5 | 8 | 0.156 | weak (5-9) -- BUT B > A not more often than A > B (control fails: no depth) |

Designs: 296 selected, 296 re-sized (296 reproduce the cached row's feasibility and worst margin within 1e-4; 0 re-sized infeasible), corners done 296, IIP3 done 296 (ok 293, slope within 3 +/- 0.3: 292). Designs passing all 4 corners: 0. CPU 8.59 h (S 5.66, C 0.05, I 2.88).

## Per task (best-A vs best-B)

Corner value = best over the pool of the corner worst margin (min over -40 C, +85 C, VDD x0.9, x1.1 of the signed worst normalized spec margin and mu - 1). IIP3 = best in-band IIP3 (dBm).

| task | tier | family | nA | nB | witness | A corner | B corner | B-A | depth? | reverse? | A IIP3 | B IIP3 | B-A dB | depth? | reverse? | complete |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t2-nb090-noise-0254 | T2 | nb090-noise | 2 | 1 | seed 1 | -0.224 | -0.273 | -0.048 | no | no | -20.05 | -20.06 | -0.01 | no | no | yes |
| t2-nb090-noise-0351 | T2 | nb090-noise | 1 | 6 | seed 1 | -0.312 | -0.204 | 0.108 | **yes** | no | -16.52 | -17.57 | -1.05 | no | no | yes |
| t2-wb1020-gain-0207 | T2 | wb1020-gain | 6 | 6 | seed 1 (not top 6) | -0.071 | -0.046 | 0.025 | no | no | -1.79 | 0.60 | 2.39 | no | no | yes |
| t2-wb1020-gain-0027 | T2 | wb1020-gain | 6 | 6 | seed 1 | -0.058 | -0.080 | -0.022 | no | no | -0.35 | 0.27 | 0.62 | no | no | yes |
| t2-wb1020-gain-0184 | T2 | wb1020-gain | 6 | 4 | seed 1 | -0.063 | -0.042 | 0.022 | no | no | -0.70 | -1.31 | -0.61 | no | no | yes |
| t2-nb090-noise-0269 | T2 | nb090-noise | 3 | 6 | seed 2 (infeasible at seed 1) (not top 6) | -0.202 | -0.178 | 0.023 | no | no | -14.32 | -8.88 | 5.43 | **yes** | no | yes |
| t2-nb090-noise-0323 | T2 | nb090-noise | 6 | 6 | seed 1 | -0.232 | -0.199 | 0.034 | no | no | -4.72 | -5.64 | -0.92 | no | no | yes |
| v2b-wb0824-gain-188 | T3 | wb0824-gain | 0 | 5 | seed 1 | - | -0.067 | - | no | no | - | -0.14 | - | no | no | yes |
| t2-wb1020-gain-0045 | T2 | wb1020-gain | 6 | 6 | seed 1 (not top 6) | -0.038 | -0.054 | -0.017 | no | no | -1.49 | -1.44 | 0.05 | no | no | yes |
| t2-wb1020-gain-0089 | T2 | wb1020-gain | 6 | 6 | seed 1 | -0.027 | -0.045 | -0.017 | no | no | -0.18 | -0.07 | 0.11 | no | no | yes |
| t2-nb090-noise-0350 | T2 | nb090-noise | 1 | 1 | seed 2 (infeasible at seed 1) | -0.402 | -0.649 | -0.247 | no | yes | -33.24 | -37.97 | -4.73 | no | yes | yes |
| t2-nb090-noise-0300 | T2 | nb090-noise | 1 | 4 | seed 1 | -0.307 | -0.218 | 0.089 | no | no | -16.15 | -20.93 | -4.78 | no | yes | yes |
| t2-wb1020-gain-0046 | T2 | wb1020-gain | 6 | 6 | seed 1 | -0.016 | -0.071 | -0.056 | no | no | 0.38 | -2.72 | -3.10 | no | yes | yes |
| t2-wb1020-gain-0010 | T2 | wb1020-gain | 6 | 6 | seed 1 (not top 6) | -0.094 | -0.039 | 0.055 | no | no | 0.85 | -0.31 | -1.16 | no | no | yes |
| t2-wb1020-gain-0067 | T2 | wb1020-gain | 6 | 6 | seed 1 (not top 6) | -0.045 | -0.047 | -0.002 | no | no | -1.13 | -1.38 | -0.25 | no | no | yes |
| t2-nb090-noise-0397 | T2 | nb090-noise | 4 | 3 | seed 1 | -0.232 | -0.238 | -0.006 | no | no | -17.51 | -23.94 | -6.43 | no | yes | yes |
| t2-wb1020-gain-0160 | T2 | wb1020-gain | 6 | 5 | seed 2 (infeasible at seed 1) | -0.052 | -0.053 | -0.002 | no | no | -0.51 | 0.21 | 0.72 | no | no | yes |
| t2-wb1020-gain-0108 | T2 | wb1020-gain | 6 | 6 | seed 1 (not top 6) | -0.039 | -0.051 | -0.012 | no | no | -1.54 | -1.86 | -0.32 | no | no | yes |
| t2-nb090-noise-0363 | T2 | nb090-noise | 3 | 5 | seed 1 | -0.255 | -0.194 | 0.061 | no | no | -15.40 | -7.21 | 8.20 | **yes** | no | yes |
| t2-nb090-noise-0349 | T2 | nb090-noise | 5 | 4 | seed 1 | -0.240 | -0.240 | 0.000 | no | no | -15.18 | -19.65 | -4.47 | no | yes | yes |
| t2-wb1020-gain-0159 | T2 | wb1020-gain | 6 | 6 | seed 1 (not top 6) | -0.046 | -0.046 | 0.000 | no | no | -0.85 | 0.89 | 1.74 | no | no | yes |
| t2-wb1020-gain-0109 | T2 | wb1020-gain | 6 | 6 | seed 2 (infeasible at seed 1) | -0.093 | -0.067 | 0.026 | no | no | 0.11 | -1.67 | -1.78 | no | no | yes |
| t2-nb090-noise-0286 | T2 | nb090-noise | 1 | 2 | seed 1 | -0.281 | -0.413 | -0.132 | no | yes | -18.23 | -27.20 | -8.96 | no | yes | yes |
| t2-nb090-noise-0312 | T2 | nb090-noise | 1 | 3 | seed 1 | -0.328 | -0.227 | 0.101 | **yes** | no | -15.28 | -20.33 | -5.05 | no | yes | yes |
| t2-nb090-noise-0411 | T2 | nb090-noise | 1 | 2 | seed 1 | -0.390 | -0.216 | 0.174 | **yes** | no | -34.46 | -19.44 | 15.02 | **yes** | no | yes |
| t2-wb1020-gain-0028 | T2 | wb1020-gain | 5 | 6 | seed 1 | -0.139 | -0.095 | 0.045 | no | no | 1.50 | -0.77 | -2.27 | no | no | yes |
| t2-wb1020-gain-0128 | T2 | wb1020-gain | 4 | 4 | seed 1 | -0.080 | -0.086 | -0.006 | no | no | -0.29 | -0.87 | -0.59 | no | no | yes |
| t2-wb1020-gain-0142 | T2 | wb1020-gain | 3 | 4 | seed 1 | -0.133 | -0.048 | 0.084 | no | no | -1.28 | -1.28 | -0.01 | no | no | yes |
| t2-nb090-noise-0012 | T3 | nb090-noise | 0 | 2 | seed 1 | - | -0.201 | - | no | no | - | -14.27 | - | no | no | yes |
| t2-wb1020-gain-0065 | T2 | wb1020-gain | 6 | 6 | seed 1 (not top 6) | -0.042 | -0.059 | -0.018 | no | no | -0.51 | 0.29 | 0.80 | no | no | yes |
| t2-wb1020-gain-0161 | T2 | wb1020-gain | 6 | 6 | seed 1 (not top 6) | -0.047 | -0.050 | -0.003 | no | no | -0.51 | -1.66 | -1.15 | no | no | yes |
| v2b-wb1020-noise-217 | T3 | wb1020-noise | 0 | 3 | seed 1 | - | -0.139 | - | no | no | - | -0.42 | - | no | no | yes |
| t2-nb090-noise-0322 | T2 | nb090-noise | 1 | 4 | seed 1 | -0.820 | -0.209 | 0.611 | **yes** | no | -39.40 | -16.55 | 22.85 | **yes** | no | yes |
| t2-nb090-noise-0291 | T2 | nb090-noise | 4 | 3 | seed 2 (infeasible at seed 1) | -0.218 | -0.201 | 0.017 | no | no | -20.45 | -16.08 | 4.37 | **yes** | no | yes |
| t2-nb090-noise-0375 | T2 | nb090-noise | 5 | 6 | seed 2 (infeasible at seed 1) | -0.244 | -0.254 | -0.010 | no | no | -16.16 | -19.90 | -3.74 | no | yes | yes |

## Per design

| task | pool | id | key | source | orig worst | re-sized worst | corner worst (at) | T-40 | T85 | V0.9 | V1.1 | IIP3 dBm | slope |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t2-nb090-noise-0254 | A | edit:a4:79:add C VSS-n4 | 15d32f4eb2fad038 | edit | 0.0000 | 0.0000 | -0.224 (V1.1) | -0.010 mu_wide-1 | -0.108 idd_ma | -0.093 s21_db | -0.224 idd_ma | -20.05 | 3.00 |
| t2-nb090-noise-0254 | A | edit:a4:16:add C VDD-n4 | 72b57ad3dc3920e4 | edit | 0.0000 | 0.0000 | -0.224 (V1.1) | -0.010 mu_wide-1 | -0.108 idd_ma | -0.093 s21_db | -0.224 idd_ma | -20.05 | 3.00 |
| t2-nb090-noise-0254 | B | witness | 2bceabc3dd44dc10 | witness | 0.0000 | 0.0000 | -0.273 (V1.1) | -0.012 mu_wide-1 | -0.142 nf_db | -0.128 nf_db | -0.273 idd_ma | -20.06 | 2.99 |
| t2-nb090-noise-0351 | A | edit:a4:69:add R VOUT1-n7 | abeb7d0337ec8700 | edit | 0.0007 | 0.0007 | -0.312 (V1.1) | -0.022 mu_wide-1 | -0.155 idd_ma | -0.239 s11_max_db | -0.312 idd_ma | -16.52 | 2.97 |
| t2-nb090-noise-0351 | B | witness | 2f6f9f75c69c85ac | witness | 0.0055 | 0.0055 | -0.293 (V1.1) | 0.004 s11_max_db | -0.130 idd_ma | -0.088 s11_max_db | -0.293 idd_ma | -21.74 | 2.97 |
| t2-nb090-noise-0351 | B | other | ceec313555211e72 | pilot-v1:h1-sft1000 | 0.0011 | 0.0011 | -0.336 (V1.1) | 0.004 mu_wide-1 | -0.166 idd_ma | -0.079 s11_max_db | -0.336 idd_ma | -22.57 | 2.98 |
| t2-nb090-noise-0351 | B | other | 0484b02138d7b456 | exit-r1:r1-8 | 0.0008 | 0.0008 | -0.422 (V1.1) | 0.005 s11_max_db | -0.213 idd_ma | -0.111 s11_max_db | -0.422 idd_ma | -22.28 | 3.08 |
| t2-nb090-noise-0351 | B | other | 1c446f4b2c6124be | pilot-v0/P1:sft100 | 0.0000 | 0.0000 | -0.204 (V1.1) | -0.008 mu_wide-1 | -0.089 idd_ma | -0.106 s21_db | -0.204 idd_ma | -17.57 | 3.00 |
| t2-nb090-noise-0351 | B | other | 2d9b54f7065275b5 | pilot-v1:h1-sft1000 | 0.0000 | 0.0000 | -0.291 (V1.1) | 0.000 mu_wide-1 | -0.138 idd_ma | -0.080 s11_max_db | -0.291 idd_ma | -18.77 | 2.97 |
| t2-nb090-noise-0351 | B | other | 469c3ccb6a0c8f16 | pilot-v1:h1-sft300 | 0.0000 | 0.0000 | -0.231 (V1.1) | -0.008 s11_max_db | -0.059 idd_ma | -0.117 s21_db | -0.231 idd_ma | -17.74 | 3.00 |
| t2-wb1020-gain-0207 | A | edit:a2:3:add R VDD-VOUT1 | aaf1238a41dda512 | edit | 0.0041 | 0.0041 | -0.071 (T85) | -0.041 s21_ripple_db | -0.071 nf_max_db | -0.050 s21_db | -0.061 s21_ripple_db | -1.91 | 3.03 |
| t2-wb1020-gain-0207 | A | edit:a2:57:add R VOUT1-VSS | e953d8387f7067c0 | edit | 0.0041 | 0.0041 | -0.071 (T85) | -0.041 s21_ripple_db | -0.071 nf_max_db | -0.050 s21_db | -0.061 s21_ripple_db | -1.91 | 3.03 |
| t2-wb1020-gain-0207 | A | edit:a2:114:add R n0-n5 | fc33a316f5b07e16 | edit | 0.0035 | 0.0035 | -0.109 (V1.1) | -0.007 mu_wide-1 | -0.090 nf_max_db | -0.037 s21_db | -0.109 idd_ma | -1.79 | 3.04 |
| t2-wb1020-gain-0207 | A | edit:a2:25:add C VDD-n5 | 499beec009fcc7ba | edit | 0.0022 | 0.0022 | -0.111 (V1.1) | -0.027 mu_wide-1 | -0.080 nf_max_db | -0.078 s21_db | -0.111 idd_ma | -8.53 | 3.03 |
| t2-wb1020-gain-0207 | A | edit:a2:97:add C VSS-n5 | ddb4f15a827050d4 | edit | 0.0022 | 0.0022 | -0.111 (V1.1) | -0.027 mu_wide-1 | -0.080 nf_max_db | -0.078 s21_db | -0.111 idd_ma | -8.53 | 3.03 |
| t2-wb1020-gain-0207 | A | edit:a2:117:add R n0-n6 | 287e3a8c29bede5b | edit | 0.0017 | 0.0017 | -0.220 (T85) | -0.102 mu_wide-1 | -0.220 s21_db | -0.072 mu_wide-1 | -0.115 idd_ma | -10.95 | 3.01 |
| t2-wb1020-gain-0207 | B | other | 7f25b5e4faf1c161 | pilot-v1:h1-sft300 | 0.0030 | 0.0030 | -0.084 (T-40) | -0.084 mu_wide-1 | -0.075 nf_max_db | -0.043 s11_max_db | -0.037 idd_ma | 0.60 | 2.91 |
| t2-wb1020-gain-0207 | B | other | 3c945b2d466a0141 | baselines-v1:opus-4 | 0.0018 | 0.0018 | -0.046 (T-40) | -0.046 s21_ripple_db | -0.007 s11_max_db | -0.038 s11_max_db | -0.008 mu_wide-1 | -0.06 | 3.07 |
| t2-wb1020-gain-0207 | B | other | 184f1f1ebb08b60d | exit-r1:r1-8 | 0.0011 | 0.0011 | -0.099 (T-40) | -0.099 s21_ripple_db | -0.033 s21_db | -0.074 s11_max_db | -0.043 s21_ripple_db | -12.60 | 2.94 |
| t2-wb1020-gain-0207 | B | other | 0d233a145bae4eb9 | pilot-v0/P1:sft300 | 0.0008 | 0.0008 | -0.082 (V0.9) | -0.045 s11_max_db | -0.006 mu_wide-1 | -0.082 s11_max_db | -0.010 mu_wide-1 | -0.99 | 3.04 |
| t2-wb1020-gain-0207 | B | other | 42c030d83327e45f | pilot-v1:h1-sft1000 | 0.0008 | 0.0008 | -0.083 (T85) | -0.020 mu_wide-1 | -0.083 nf_max_db | -0.055 s11_max_db | -0.015 s21_ripple_db | -0.14 | 3.06 |
| t2-wb1020-gain-0207 | B | other | ba26dc0a6c8a2aa5 | ga:run1 | 0.0007 | 0.0007 | -0.060 (V0.9) | -0.013 mu_wide-1 | -0.047 nf_max_db | -0.060 s11_max_db | 0.001 mu_wide-1 | -2.58 | 3.03 |
| t2-wb1020-gain-0027 | A | edit:a2:118:add C n0-n6 | afacef40ecd58d94 | edit | 0.0012 | 0.0012 | -0.058 (T85) | -0.018 mu_wide-1 | -0.058 nf_max_db | -0.049 s11_max_db | 0.004 mu_wide-1 | -1.12 | 3.05 |
| t2-wb1020-gain-0027 | A | edit:a2:52:add C VIN1-n5 | ae8c62d24f0bc669 | edit | 0.0010 | 0.0010 | -0.074 (T85) | -0.020 mu_wide-1 | -0.074 nf_max_db | -0.044 s11_max_db | -0.001 idd_ma | -0.35 | 3.06 |
| t2-wb1020-gain-0027 | A | edit:a2:133:add C n1-n6 | 0212ec56ef43990e | edit | 0.0009 | 0.0009 | -0.142 (T85) | -0.093 s21_ripple_db | -0.142 nf_max_db | -0.040 s21_db | -0.046 idd_ma | -5.57 | 3.06 |
| t2-wb1020-gain-0027 | A | edit:a2:25:add C VDD-n5 | 499beec009fcc7ba | edit | 0.0008 | 0.0008 | -0.135 (T85) | -0.024 mu_wide-1 | -0.135 nf_max_db | -0.043 s21_db | 0.001 mu_wide-1 | -3.04 | 3.03 |
| t2-wb1020-gain-0027 | A | edit:a2:97:add C VSS-n5 | ddb4f15a827050d4 | edit | 0.0008 | 0.0008 | -0.135 (T85) | -0.024 mu_wide-1 | -0.135 nf_max_db | -0.043 s21_db | 0.001 mu_wide-1 | -3.04 | 3.03 |
| t2-wb1020-gain-0027 | A | edit:a2:108:add R n0-n3 | 2e41b23a9f0bdbdc | edit | 0.0007 | 0.0007 | -0.134 (T85) | -0.052 mu_wide-1 | -0.134 nf_max_db | -0.065 s11_max_db | -0.105 idd_ma | -3.69 | 3.03 |
| t2-wb1020-gain-0027 | B | other | b727fe970153bcd4 | baselines-v1:opus-4 | 0.0010 | 0.0010 | -0.150 (T85) | 0.002 mu_wide-1 | -0.150 nf_max_db | -0.077 s11_max_db | -0.142 idd_ma | -6.05 | 3.06 |
| t2-wb1020-gain-0027 | B | other | 611a39a915f98b8e | exit-r1:r2-8 | 0.0008 | 0.0008 | -0.102 (T85) | -0.021 mu_wide-1 | -0.102 nf_max_db | -0.047 s11_max_db | -0.010 mu_wide-1 | -5.63 | 2.97 |
| t2-wb1020-gain-0027 | B | other | c39f310bb5ab5a11 | pilot-v1:h1-sft300 | 0.0005 | 0.0005 | -0.080 (V0.9) | -0.019 mu_wide-1 | -0.039 s21_db | -0.080 s11_max_db | -0.006 mu_wide-1 | -11.07 | 2.98 |
| t2-wb1020-gain-0027 | B | other | 9627bf79970c46e2 | pilot-v1:h1-sft300 | 0.0003 | 0.0003 | -0.139 (T85) | -0.022 s21_ripple_db | -0.139 nf_max_db | -0.039 s21_db | -0.131 idd_ma | -1.38 | 3.05 |
| t2-wb1020-gain-0027 | B | witness | 0d7c9d0c397deea4 | witness | 0.0002 | 0.0002 | -0.330 (T-40) | -0.330 mu_wide-1 | -0.001 s11_max_db | -0.059 s11_max_db | -0.002 mu_wide-1 | 0.27 | 3.09 |
| t2-wb1020-gain-0027 | B | other | 1650d740fee4a288 | baselines-v1:opus-4 | 0.0002 | 0.0002 | -0.133 (T85) | -0.019 mu_wide-1 | -0.133 nf_max_db | -0.038 s11_max_db | 0.004 mu_wide-1 | -1.08 | 3.06 |
| t2-wb1020-gain-0184 | A | edit:a2:73:add C VOUT1-n4 | 8aaf34ad79432518 | edit | 0.0013 | 0.0013 | -0.063 (T85) | -0.052 mu_wide-1 | -0.063 nf_max_db | -0.043 s11_max_db | 0.001 mu_wide-1 | -4.33 | 3.02 |
| t2-wb1020-gain-0184 | A | edit:a2:13:add C VDD-n1 | 3e614d1b9e0e3f19 | edit | 0.0009 | 0.0009 | -0.147 (V1.1) | -0.058 s21_ripple_db | -0.134 nf_max_db | -0.038 s11_max_db | -0.147 idd_ma | -0.70 | 3.05 |
| t2-wb1020-gain-0184 | A | edit:a2:85:add C VSS-n1 | e7ebba737e289a88 | edit | 0.0009 | 0.0009 | -0.147 (V1.1) | -0.058 s21_ripple_db | -0.134 nf_max_db | -0.038 s11_max_db | -0.147 idd_ma | -0.70 | 3.05 |
| t2-wb1020-gain-0184 | A | edit:a2:138:add R n2-n4 | 68cbe3d1c52c42f8 | edit | 0.0003 | 0.0003 | -0.155 (V1.1) | -0.060 s21_ripple_db | -0.136 nf_max_db | -0.038 s11_max_db | -0.155 idd_ma | -2.33 | 3.04 |
| t2-wb1020-gain-0184 | A | edit:a2:46:add C VIN1-n3 | bddbb34d29b79d89 | edit | 0.0002 | 0.0002 | -0.122 (V1.1) | -0.046 s21_ripple_db | -0.064 idd_ma | -0.038 s11_max_db | -0.122 idd_ma | -1.55 | 3.05 |
| t2-wb1020-gain-0184 | A | edit:a2:117:add R n0-n6 | 287e3a8c29bede5b | edit | 0.0002 | 0.0002 | -0.223 (V1.1) | -0.055 mu_wide-1 | -0.160 nf_max_db | -0.085 s11_max_db | -0.223 idd_ma | -4.15 | 3.03 |
| t2-wb1020-gain-0184 | B | other | bfa9310c0078601e | baselines-v1:opus-4 | 0.0029 | 0.0029 | -0.094 (V1.1) | 0.003 mu_wide-1 | -0.040 idd_ma | -0.044 s11_max_db | -0.094 idd_ma | -9.26 | 3.03 |
| t2-wb1020-gain-0184 | B | witness | 75538c0733ddad9a | witness | 0.0010 | 0.0010 | -0.042 (V0.9) | -0.003 mu_wide-1 | -0.009 s21_db | -0.042 s21_db | 0.001 mu_wide-1 | -3.24 | 3.03 |
| t2-wb1020-gain-0184 | B | other | 3f1470ce12060d08 | ga:run1 | 0.0003 | 0.0003 | -0.101 (V1.1) | -0.056 s21_ripple_db | -0.052 idd_ma | -0.060 s11_max_db | -0.101 idd_ma | -1.31 | 3.05 |
| t2-wb1020-gain-0184 | B | other | d0e811bddba07f34 | pilot-v1:h1-sft300 | 0.0002 | 0.0002 | -0.304 (T85) | -0.285 s21_ripple_db | -0.304 idd_ma | -0.229 s11_max_db | -0.278 idd_ma | -11.97 | 2.94 |
| t2-nb090-noise-0269 | A | edit:a4:13:add C VDD-n2 | 1c047c14b49966a0 | edit | 0.0000 | 0.0000 | -0.202 (V1.1) | -0.001 mu_wide-1 | -0.074 idd_ma | -0.048 s11_max_db | -0.202 idd_ma | -24.01 | 2.99 |
| t2-nb090-noise-0269 | A | edit:a4:76:add C VSS-n2 | dd52dfaacfc4ee0d | edit | 0.0000 | 0.0000 | -0.202 (V1.1) | -0.001 mu_wide-1 | -0.074 idd_ma | -0.048 s11_max_db | -0.202 idd_ma | -24.01 | 2.99 |
| t2-nb090-noise-0269 | A | edit:a4:69:add R VOUT1-n7 | abeb7d0337ec8700 | edit | 0.0000 | 0.0000 | -0.252 (V1.1) | -0.085 mu_wide-1 | -0.122 idd_ma | -0.193 s11_max_db | -0.252 idd_ma | -14.32 | 2.99 |
| t2-nb090-noise-0269 | B | other | 3227192cb6482db0 | pilot-v1:h1-sft300 | 0.0008 | 0.0008 | -0.318 (V1.1) | -0.006 mu_wide-1 | -0.154 idd_ma | -0.082 s11_max_db | -0.318 idd_ma | -24.65 | 3.00 |
| t2-nb090-noise-0269 | B | other | f5f6a376c74a2e3d | ga:run1 | 0.0005 | 0.0005 | -0.178 (V1.1) | 0.005 mu_wide-1 | -0.150 nf_db | -0.079 s11_max_db | -0.178 idd_ma | -8.88 | 3.06 |
| t2-nb090-noise-0269 | B | other | 3d322338287dbb38 | exit-r1:r1-8 | 0.0003 | 0.0003 | -0.357 (V1.1) | 0.000 mu_wide-1 | -0.177 idd_ma | -0.069 s11_max_db | -0.357 idd_ma | -21.33 | 2.97 |
| t2-nb090-noise-0269 | B | other | 37f7c13841b9ae2e | pilot-v0/P1:sft300 | 0.0002 | 0.0002 | -0.293 (V1.1) | -0.007 mu_wide-1 | -0.143 idd_ma | -0.079 s11_max_db | -0.293 idd_ma | -24.26 | 2.99 |
| t2-nb090-noise-0269 | B | other | e742ca0183a13743 | pilot-v1:h1-sft300 | 0.0002 | 0.0002 | -0.293 (V1.1) | -0.007 mu_wide-1 | -0.143 idd_ma | -0.079 s11_max_db | -0.293 idd_ma | -24.26 | 2.99 |
| t2-nb090-noise-0269 | B | other | 4ce9f4fd069003f3 | ga:run1 | 0.0000 | 0.0000 | -0.179 (V1.1) | -0.058 s11_max_db | -0.136 idd_ma | -0.080 s11_max_db | -0.179 idd_ma | -12.28 | 3.02 |
| t2-nb090-noise-0323 | A | edit:a4:63:add R VOUT1-n5 | 2ac9d77cfe46c4e8 | edit | 0.0005 | 0.0005 | -0.263 (V1.1) | -0.022 s11_max_db | -0.119 idd_ma | -0.138 s11_max_db | -0.263 idd_ma | -4.72 | 2.98 |
| t2-nb090-noise-0323 | A | edit:a4:69:add R VOUT1-n7 | abeb7d0337ec8700 | edit | 0.0002 | 0.0002 | -0.299 (V1.1) | -0.026 mu_wide-1 | -0.146 idd_ma | -0.235 s11_max_db | -0.299 idd_ma | -15.57 | 2.97 |
| t2-nb090-noise-0323 | A | edit:a4:13:add C VDD-n2 | 1c047c14b49966a0 | edit | 0.0000 | 0.0000 | -0.232 (V1.1) | -0.006 mu_wide-1 | -0.099 idd_ma | -0.067 s11_max_db | -0.232 idd_ma | -21.53 | 2.98 |
| t2-nb090-noise-0323 | A | edit:a4:76:add C VSS-n2 | dd52dfaacfc4ee0d | edit | 0.0000 | 0.0000 | -0.232 (V1.1) | -0.006 mu_wide-1 | -0.099 idd_ma | -0.067 s11_max_db | -0.232 idd_ma | -21.53 | 2.98 |
| t2-nb090-noise-0323 | A | edit:a4:79:add C VSS-n4 | 15d32f4eb2fad038 | edit | 0.0000 | 0.0000 | -0.264 (V1.1) | -0.012 mu_wide-1 | -0.131 idd_ma | -0.089 s11_max_db | -0.264 idd_ma | -21.00 | 3.00 |
| t2-nb090-noise-0323 | A | edit:a4:16:add C VDD-n4 | 72b57ad3dc3920e4 | edit | 0.0000 | 0.0000 | -0.264 (V1.1) | -0.012 mu_wide-1 | -0.131 idd_ma | -0.089 s11_max_db | -0.264 idd_ma | -21.00 | 3.00 |
| t2-nb090-noise-0323 | B | witness | fa86f6476857dba8 | witness | 0.0413 | 0.0413 | -2.546 (T-40) | -2.546 nf_db | -1.155 idd_ma | -0.102 s11_max_db | -0.420 idd_ma | -20.59 | 3.00 |
| t2-nb090-noise-0323 | B | other | 4e2f0394f3a5e2b0 | pilot-v1:h1-sft300 | 0.0034 | 0.0034 | -0.296 (V1.1) | 0.003 mu_wide-1 | -0.147 idd_ma | -0.141 s11_max_db | -0.296 idd_ma | -5.64 | 2.90 |
| t2-nb090-noise-0323 | B | other | 03cc4359761dde18 | baselines-v1:opus-4 | 0.0000 | 0.0000 | -0.199 (V1.1) | -0.034 s11_max_db | -0.140 idd_ma | -0.111 s11_max_db | -0.199 idd_ma | -20.24 | 2.99 |
| t2-nb090-noise-0323 | B | other | a4c5602c0a83126e | pilot-v1:h1-sft1000 | 0.0000 | 0.0000 | -0.228 (V1.1) | -0.006 mu_wide-1 | -0.108 idd_ma | -0.056 s11_max_db | -0.228 idd_ma | -21.24 | 2.99 |
| t2-nb090-noise-0323 | B | other | 390d90d63d60fdcd | exit-r1:r2-8 | 0.0000 | 0.0000 | -0.219 (V1.1) | -0.007 mu_wide-1 | -0.136 idd_ma | -0.046 s11_max_db | -0.219 idd_ma | -18.56 | 2.99 |
| t2-nb090-noise-0323 | B | other | 5f6bc2286e341bfc | baselines-v1:opus-4 | 0.0000 | 0.0000 | -0.318 (V1.1) | -0.076 s11_max_db | -0.161 idd_ma | -0.223 s11_max_db | -0.318 idd_ma | -21.41 | 2.98 |
| v2b-wb0824-gain-188 | B | other | a4b7267f822b7e16 | ga:run1 | 0.0005 | 0.0005 | -0.091 (T85) | -0.004 mu_wide-1 | -0.091 nf_max_db | -0.051 s21_db | -0.003 mu_wide-1 | -0.14 | 3.00 |
| v2b-wb0824-gain-188 | B | other | 94369eaa7bd62892 | pilot-v0/P1:sft1000 | 0.0005 | 0.0005 | -0.311 (V1.1) | -0.017 mu_wide-1 | -0.222 idd_ma | -0.120 s11_max_db | -0.311 idd_ma | -14.80 | 3.00 |
| v2b-wb0824-gain-188 | B | other | 6a2f2a37c3d62e01 | exit-r1:r1-8 | 0.0002 | 0.0002 | -0.079 (V0.9) | -0.016 mu_wide-1 | -0.021 mu_wide-1 | -0.079 s11_max_db | -0.005 mu_wide-1 | -5.71 | 3.01 |
| v2b-wb0824-gain-188 | B | other | 52ace152ad1863e9 | pilot-v0/P1:sft1000 | 0.0000 | 0.0000 | -0.184 (T85) | -0.021 mu_wide-1 | -0.184 nf_max_db | -0.098 s11_max_db | -0.182 idd_ma | -14.30 | 3.00 |
| v2b-wb0824-gain-188 | B | witness | 643274f4ddabb6aa | witness | 0.0000 | 0.0000 | -0.067 (V0.9) | -0.014 mu_wide-1 | -0.010 s11_max_db | -0.067 s11_max_db | -0.002 s21_ripple_db | -1.04 | 2.98 |
| t2-wb1020-gain-0045 | A | edit:a2:52:add C VIN1-n5 | ae8c62d24f0bc669 | edit | 0.0026 | 0.0026 | -0.038 (V0.9) | 0.002 mu_wide-1 | -0.017 nf_max_db | -0.038 s21_db | -0.030 idd_ma | -3.80 | 3.03 |
| t2-wb1020-gain-0045 | A | edit:a2:19:add C VDD-n3 | 6e1d3fd0b09e73c5 | edit | 0.0019 | 0.0019 | -0.049 (V0.9) | -0.015 mu_wide-1 | -0.014 s11_max_db | -0.049 s11_max_db | -0.010 s11_max_db | -1.59 | 3.03 |
| t2-wb1020-gain-0045 | A | edit:a2:91:add C VSS-n3 | f43cea6e23a5e616 | edit | 0.0019 | 0.0019 | -0.049 (V0.9) | -0.015 mu_wide-1 | -0.014 s11_max_db | -0.049 s11_max_db | -0.010 s11_max_db | -1.59 | 3.03 |
| t2-wb1020-gain-0045 | A | edit:a2:115:add C n0-n5 | 62b654be793405bf | edit | 0.0019 | 0.0019 | -0.086 (V1.1) | 0.001 s11_max_db | -0.056 nf_max_db | -0.044 s21_db | -0.086 idd_ma | -3.08 | 3.04 |
| t2-wb1020-gain-0045 | A | edit:a2:108:add R n0-n3 | 2e41b23a9f0bdbdc | edit | 0.0015 | 0.0015 | -0.051 (V0.9) | -0.033 mu_wide-1 | -0.000 s21_db | -0.051 s21_db | 0.003 mu_wide-1 | -1.49 | 3.05 |
| t2-wb1020-gain-0045 | A | edit:a2:13:add C VDD-n1 | 3e614d1b9e0e3f19 | edit | 0.0015 | 0.0015 | -0.061 (V0.9) | -0.024 mu_wide-1 | -0.017 s11_max_db | -0.061 s11_max_db | -0.003 s11_max_db | -3.67 | 3.02 |
| t2-wb1020-gain-0045 | B | other | 5f0d19fb4862dd30 | pilot-v1:h1-sft300 | 0.0011 | 0.0011 | -0.063 (T-40) | -0.063 mu_wide-1 | -0.026 s11_max_db | -0.039 s11_max_db | -0.052 idd_ma | -1.44 | 3.05 |
| t2-wb1020-gain-0045 | B | other | a9752c78d7e79f5e | ga:run1 | 0.0007 | 0.0007 | -0.056 (V0.9) | -0.019 s21_ripple_db | -0.018 s11_max_db | -0.056 s11_max_db | 0.003 mu_wide-1 | -3.77 | 3.02 |
| t2-wb1020-gain-0045 | B | other | bfa9310c0078601e | baselines-v1:opus-4 | 0.0005 | 0.0005 | -0.078 (T-40) | -0.078 s11_max_db | -0.036 s21_db | -0.032 s21_db | -0.009 mu_wide-1 | -6.49 | 3.05 |
| t2-wb1020-gain-0045 | B | other | 1650d740fee4a288 | baselines-v1:opus-4 | 0.0005 | 0.0005 | -0.054 (V0.9) | -0.021 mu_wide-1 | -0.020 s11_max_db | -0.054 s11_max_db | 0.003 mu_wide-1 | -3.11 | 3.03 |
| t2-wb1020-gain-0045 | B | other | 35e9d14377458f94 | exit-r1:r1-8,exit-r1:r2-8,pilot-v0/P1:sft300,pilot-v1:h1-sft | 0.0005 | 0.0005 | -0.158 (V1.1) | -0.014 mu_wide-1 | -0.060 idd_ma | -0.026 mu_wide-1 | -0.158 idd_ma | -17.24 | 2.97 |
| t2-wb1020-gain-0045 | B | other | bd7930bad61c1b5a | exit-r1:r1-8 | 0.0004 | 0.0004 | -0.118 (V0.9) | -0.027 mu_wide-1 | -0.059 s21_db | -0.118 s11_max_db | -0.018 mu_wide-1 | -17.01 | 2.96 |
| t2-wb1020-gain-0089 | A | edit:a2:46:add C VIN1-n3 | bddbb34d29b79d89 | edit | 0.0021 | 0.0021 | -0.027 (V0.9) | -0.013 mu_wide-1 | 0.000 s21_db | -0.027 s21_db | -0.025 idd_ma | -0.22 | 3.07 |
| t2-wb1020-gain-0089 | A | edit:a2:102:add R n0-n1 | b7a40a3a1218d6b0 | edit | 0.0010 | 0.0010 | -0.041 (V0.9) | -0.020 mu_wide-1 | -0.010 nf_max_db | -0.041 s11_max_db | 0.004 mu_wide-1 | -1.49 | 3.05 |
| t2-wb1020-gain-0089 | A | edit:a2:118:add C n0-n6 | afacef40ecd58d94 | edit | 0.0010 | 0.0010 | -0.046 (V0.9) | -0.018 mu_wide-1 | -0.016 s11_max_db | -0.046 s11_max_db | 0.003 mu_wide-1 | -0.78 | 3.06 |
| t2-wb1020-gain-0089 | A | edit:a2:156:add R n4-n5 | 6055bde8c4ce8175 | edit | 0.0009 | 0.0009 | -0.052 (T85) | -0.011 mu_wide-1 | -0.052 nf_max_db | -0.051 s21_db | -0.002 mu_wide-1 | -2.86 | 3.03 |
| t2-wb1020-gain-0089 | A | edit:a2:147:add R n3-n4 | c153839aa24cc89c | edit | 0.0005 | 0.0005 | -0.056 (T85) | -0.015 mu_wide-1 | -0.056 nf_max_db | -0.033 s21_db | -0.013 idd_ma | -0.18 | 3.06 |
| t2-wb1020-gain-0089 | A | edit:a2:76:add C VOUT1-n5 | 0c7750a809f5ef83 | edit | 0.0005 | 0.0005 | -0.083 (T-40) | -0.083 s21_ripple_db | -0.015 s11_max_db | -0.053 s21_db | -0.038 s21_ripple_db | -4.05 | 3.01 |
| t2-wb1020-gain-0089 | B | other | 3c945b2d466a0141 | baselines-v1:opus-4 | 0.0012 | 0.0012 | -0.045 (V0.9) | -0.011 mu_wide-1 | -0.012 s11_max_db | -0.045 s11_max_db | -0.004 mu_wide-1 | -0.44 | 3.05 |
| t2-wb1020-gain-0089 | B | other | 50daec656a7ed93b | exit-r1:r2-8 | 0.0009 | 0.0009 | -0.052 (T85) | -0.011 mu_wide-1 | -0.052 nf_max_db | -0.051 s21_db | -0.002 mu_wide-1 | -2.86 | 3.03 |
| t2-wb1020-gain-0089 | B | other | 637ed111116d2921 | pilot-v1:h1-sft300 | 0.0005 | 0.0005 | -0.100 (V0.9) | -0.013 mu_wide-1 | 0.000 mu_wide-1 | -0.100 s11_max_db | 0.000 mu_wide-1 | -7.95 | 3.00 |
| t2-wb1020-gain-0089 | B | other | 9e2ec81e83a737ca | exit-r1:r1-8 | 0.0002 | 0.0002 | -0.075 (V0.9) | -0.019 mu_wide-1 | -0.033 nf_max_db | -0.075 s11_max_db | -0.012 idd_ma | -7.75 | 3.03 |
| t2-wb1020-gain-0089 | B | other | 03eedefdb79e113c | pilot-v0/P1:sft100 | 0.0002 | 0.0002 | -0.093 (T85) | -0.036 mu_wide-1 | -0.093 nf_max_db | -0.049 s11_max_db | -0.041 idd_ma | -5.57 | 3.08 |
| t2-wb1020-gain-0089 | B | witness | 1850309b78569ba8 | witness | 0.0002 | 0.0002 | -0.078 (V0.9) | -0.016 mu_wide-1 | 0.000 mu_wide-1 | -0.078 s11_max_db | 0.000 mu_wide-1 | -0.07 | 3.06 |
| t2-nb090-noise-0350 | A | edit:a4:133:add C n6-n7 | 53fe8e4b4b7bca18 | edit | 0.0000 | 0.0000 | -0.402 (V1.1) | -0.021 mu_wide-1 | -0.195 idd_ma | -0.311 s11_max_db | -0.402 idd_ma | -33.24 | 2.99 |
| t2-nb090-noise-0350 | B | witness | 99d1091a10e60f5a | witness(seed-2 row) | 0.0008 | 0.0008 | -0.649 (V1.1) | -0.235 s11_max_db | -0.298 idd_ma | -0.528 s11_max_db | -0.649 idd_ma | -37.97 | 2.63 |
| t2-nb090-noise-0300 | A | edit:a4:69:add R VOUT1-n7 | abeb7d0337ec8700 | edit | 0.0000 | 0.0000 | -0.307 (V1.1) | -0.026 mu_wide-1 | -0.153 idd_ma | -0.235 s11_max_db | -0.307 idd_ma | -16.15 | 2.97 |
| t2-nb090-noise-0300 | B | other | ceec313555211e72 | exit-r1:r1-8 | 0.0008 | 0.0008 | -0.282 (V1.1) | -0.003 mu_wide-1 | -0.133 idd_ma | -0.078 s11_max_db | -0.282 idd_ma | -22.05 | 2.99 |
| t2-nb090-noise-0300 | B | other | 139ea23ea0a2f073 | pilot-v1:h1-sft300 | 0.0000 | 0.0000 | -0.218 (V1.1) | -0.006 mu_wide-1 | -0.153 idd_ma | -0.089 s21_db | -0.218 idd_ma | -21.00 | 2.99 |
| t2-nb090-noise-0300 | B | witness | 15eae345c7510612 | witness | 0.0000 | 0.0000 | -0.253 (V1.1) | -0.011 mu_wide-1 | -0.119 idd_ma | -0.084 s11_max_db | -0.253 idd_ma | -20.93 | 2.99 |
| t2-nb090-noise-0300 | B | other | b5b17de2e8c0e40b | pilot-v0/P1:sft300 | 0.0000 | 0.0000 | -0.280 (V1.1) | -0.013 mu_wide-1 | -0.137 idd_ma | -0.085 s11_max_db | -0.280 idd_ma | -20.93 | 2.99 |
| t2-wb1020-gain-0046 | A | edit:a2:81:add R VSS-n0 | 94e219d85e205e1d | edit | 0.0023 | 0.0023 | -0.125 (T85) | -0.032 mu_wide-1 | -0.125 nf_max_db | -0.035 s21_db | 0.002 nf_max_db | -7.22 | 3.03 |
| t2-wb1020-gain-0046 | A | edit:a2:21:add R VDD-n4 | 7997b81e6e756b5b | edit | 0.0016 | 0.0016 | -0.047 (V0.9) | -0.022 mu_wide-1 | -0.008 s11_max_db | -0.047 s21_db | -0.009 mu_wide-1 | 0.38 | 3.08 |
| t2-wb1020-gain-0046 | A | edit:a2:111:add R n0-n4 | b1cd7cf8a6042d59 | edit | 0.0012 | 0.0012 | -0.016 (T-40) | -0.016 mu_wide-1 | 0.001 mu_wide-1 | -0.015 s21_db | -0.005 mu_wide-1 | 0.13 | 3.07 |
| t2-wb1020-gain-0046 | A | edit:a2:55:add C VIN1-n6 | efb3a6bc48ade7ad | edit | 0.0011 | 0.0011 | -0.136 (T85) | 0.002 mu_wide-1 | -0.136 nf_max_db | -0.029 s21_db | -0.007 mu_wide-1 | -1.24 | 3.06 |
| t2-wb1020-gain-0046 | A | edit:a2:73:add C VOUT1-n4 | 8aaf34ad79432518 | edit | 0.0010 | 0.0010 | -0.055 (V0.9) | -0.024 mu_wide-1 | -0.010 s11_max_db | -0.055 s11_max_db | 0.001 mu_wide-1 | -2.54 | 3.03 |
| t2-wb1020-gain-0046 | A | edit:a2:109:add C n0-n3 | 59af5c4714b8125a | edit | 0.0009 | 0.0009 | -0.075 (T85) | -0.035 mu_wide-1 | -0.075 nf_max_db | -0.035 s21_db | -0.006 mu_wide-1 | -6.49 | 3.05 |
| t2-wb1020-gain-0046 | B | other | 47d158350561ddbe | pilot-v0/P1:zs | 0.0007 | 0.0007 | -0.134 (T85) | -0.077 s21_ripple_db | -0.134 nf_max_db | -0.032 s21_db | 0.004 nf_max_db | -2.72 | 3.02 |
| t2-wb1020-gain-0046 | B | witness | 1488a976895ec48c | witness | 0.0006 | 0.0006 | -0.111 (V0.9) | -0.021 mu_wide-1 | -0.011 s11_max_db | -0.111 s11_max_db | 0.000 mu_wide-1 | -14.08 | 2.97 |
| t2-wb1020-gain-0046 | B | other | f665a2e7d71f7840 | pilot-v0/P1:sft300 | 0.0004 | 0.0004 | -0.324 (V1.1) | -0.280 s11_max_db | -0.284 nf_max_db | -0.259 s11_max_db | -0.324 mu_wide-1 | -16.18 | 2.97 |
| t2-wb1020-gain-0046 | B | other | 9cfec4d123429d66 | exit-r1:r1-8 | 0.0004 | 0.0004 | -0.100 (V0.9) | -0.021 mu_wide-1 | -0.050 s21_db | -0.100 s11_max_db | -0.005 mu_wide-1 | -14.52 | 2.96 |
| t2-wb1020-gain-0046 | B | other | 165224d553c54cde | exit-r1:r1-8 | 0.0004 | 0.0004 | -0.071 (V0.9) | -0.016 mu_wide-1 | -0.038 nf_max_db | -0.071 s11_max_db | 0.000 mu_wide-1 | -9.66 | 2.95 |
| t2-wb1020-gain-0046 | B | other | 4fda2624661c1f2c | pilot-v1:h1-sft1000 | 0.0003 | 0.0003 | -0.225 (T85) | -0.033 mu_wide-1 | -0.225 nf_max_db | -0.023 s21_db | 0.003 mu_wide-1 | -5.95 | 3.07 |
| t2-wb1020-gain-0010 | A | edit:a2:114:add R n0-n5 | fc33a316f5b07e16 | edit | 0.0027 | 0.0027 | -0.146 (T85) | 0.003 mu_wide-1 | -0.146 nf_max_db | -0.050 s21_db | -0.132 idd_ma | -3.93 | 3.03 |
| t2-wb1020-gain-0010 | A | edit:a2:117:add R n0-n6 | 287e3a8c29bede5b | edit | 0.0024 | 0.0024 | -0.192 (V1.1) | -0.063 mu_wide-1 | -0.092 idd_ma | -0.048 s11_max_db | -0.192 idd_ma | -4.55 | 3.02 |
| t2-wb1020-gain-0010 | A | edit:a2:147:add R n3-n4 | c153839aa24cc89c | edit | 0.0010 | 0.0010 | -0.094 (T85) | -0.011 mu_wide-1 | -0.094 nf_max_db | -0.020 s21_db | 0.001 mu_wide-1 | 0.85 | 3.08 |
| t2-wb1020-gain-0010 | A | edit:a2:81:add R VSS-n0 | 94e219d85e205e1d | edit | 0.0009 | 0.0009 | -0.170 (V1.1) | -0.037 mu_wide-1 | -0.141 nf_max_db | -0.058 s11_max_db | -0.170 idd_ma | -4.39 | 2.92 |
| t2-wb1020-gain-0010 | A | edit:a2:151:add C n3-n5 | 96b3d7a7694d428d | edit | 0.0007 | 0.0007 | -0.132 (T85) | -0.016 mu_wide-1 | -0.132 nf_max_db | -0.027 s11_max_db | -0.002 s21_ripple_db | -0.62 | 3.05 |
| t2-wb1020-gain-0010 | A | edit:a2:19:add C VDD-n3 | 6e1d3fd0b09e73c5 | edit | 0.0007 | 0.0007 | -0.151 (V1.1) | 0.002 mu_wide-1 | -0.145 nf_max_db | -0.054 s11_max_db | -0.151 idd_ma | -3.79 | 3.03 |
| t2-wb1020-gain-0010 | B | other | 045320bd94a50435 | ga:run1 | 0.0014 | 0.0014 | -0.064 (V0.9) | -0.021 mu_wide-1 | -0.058 nf_max_db | -0.064 s11_max_db | -0.007 mu_wide-1 | -0.71 | 3.06 |
| t2-wb1020-gain-0010 | B | other | 805901361d7c5628 | exit-r1:r2-8 | 0.0006 | 0.0006 | -0.108 (T85) | -0.021 mu_wide-1 | -0.108 nf_max_db | -0.044 s11_max_db | -0.001 mu_wide-1 | -0.31 | 3.07 |
| t2-wb1020-gain-0010 | B | other | aea1e47f98d91541 | ga:run1 | 0.0006 | 0.0006 | -0.069 (V0.9) | -0.029 mu_wide-1 | 0.001 mu_wide-1 | -0.069 s11_max_db | -0.004 mu_wide-1 | -1.07 | 3.05 |
| t2-wb1020-gain-0010 | B | other | 35e9d14377458f94 | exit-r1:r1-8,exit-r1:r2-8,pilot-v0/P1:sft1000,pilot-v1:h1-sf | 0.0004 | 0.0004 | -0.106 (V0.9) | -0.014 mu_wide-1 | -0.010 s21_db | -0.106 s11_max_db | 0.000 mu_wide-1 | -13.29 | 2.95 |
| t2-wb1020-gain-0010 | B | other | 3c945b2d466a0141 | baselines-v1:opus-4 | 0.0004 | 0.0004 | -0.039 (V0.9) | -0.032 s21_ripple_db | -0.010 s11_max_db | -0.039 s11_max_db | 0.004 mu_wide-1 | -1.51 | 3.04 |
| t2-wb1020-gain-0010 | B | other | 1cd6855689cdc784 | pilot-v1:h1-sft300 | 0.0004 | 0.0004 | -0.258 (T-40) | -0.258 s21_ripple_db | -0.187 nf_max_db | -0.090 s11_max_db | -0.082 idd_ma | -15.39 | 2.97 |
| t2-wb1020-gain-0067 | A | edit:a2:138:add R n2-n4 | 68cbe3d1c52c42f8 | edit | 0.0034 | 0.0034 | -0.045 (V0.9) | -0.010 mu_wide-1 | -0.013 s11_max_db | -0.045 s11_max_db | 0.003 mu_wide-1 | -1.13 | 3.05 |
| t2-wb1020-gain-0067 | A | edit:a2:115:add C n0-n5 | 62b654be793405bf | edit | 0.0029 | 0.0029 | -0.068 (V0.9) | -0.050 mu_wide-1 | -0.019 s21_db | -0.068 s21_db | -0.004 mu_wide-1 | -10.57 | 2.96 |
| t2-wb1020-gain-0067 | A | edit:a2:133:add C n1-n6 | 0212ec56ef43990e | edit | 0.0018 | 0.0018 | -0.065 (V1.1) | -0.065 s21_ripple_db | -0.010 s11_max_db | -0.040 s21_db | -0.065 s21_ripple_db | -5.90 | 3.01 |
| t2-wb1020-gain-0067 | A | edit:a2:130:add C n1-n5 | 1624a44c1e768793 | edit | 0.0016 | 0.0016 | -0.050 (T-40) | -0.050 s21_ripple_db | -0.019 s11_max_db | -0.018 s11_max_db | -0.031 s21_ripple_db | -3.85 | 3.02 |
| t2-wb1020-gain-0067 | A | edit:a2:111:add R n0-n4 | b1cd7cf8a6042d59 | edit | 0.0014 | 0.0014 | -0.053 (V0.9) | -0.032 mu_wide-1 | -0.005 s11_max_db | -0.053 s11_max_db | -0.019 mu_wide-1 | -1.69 | 3.05 |
| t2-wb1020-gain-0067 | A | edit:a2:139:add C n2-n4 | d8424113834b943b | edit | 0.0013 | 0.0013 | -0.141 (V1.1) | -0.028 mu_wide-1 | -0.071 idd_ma | -0.055 s21_db | -0.141 idd_ma | -9.06 | 3.01 |
| t2-wb1020-gain-0067 | B | other | 9f4f3f70fe89319c | pilot-v1:h1-sft300 | 0.0013 | 0.0013 | -0.141 (V1.1) | -0.028 mu_wide-1 | -0.071 idd_ma | -0.055 s21_db | -0.141 idd_ma | -9.06 | 3.01 |
| t2-wb1020-gain-0067 | B | other | c6d72ed5afb5c49c | pilot-v1:h1-sft300 | 0.0012 | 0.0012 | -0.053 (V0.9) | -0.013 mu_wide-1 | -0.037 s21_db | -0.053 s11_max_db | 0.005 mu_wide-1 | -10.78 | 2.98 |
| t2-wb1020-gain-0067 | B | other | 1da36fd3fe91f755 | exit-r1:r1-8 | 0.0010 | 0.0010 | -0.052 (T85) | -0.027 mu_wide-1 | -0.052 s21_db | -0.042 s21_db | -0.022 idd_ma | -6.57 | 3.01 |
| t2-wb1020-gain-0067 | B | other | b625a89192888fec | ga:run1 | 0.0007 | 0.0007 | -0.053 (V0.9) | -0.014 mu_wide-1 | -0.011 s11_max_db | -0.053 s11_max_db | 0.004 mu_wide-1 | -1.38 | 3.05 |
| t2-wb1020-gain-0067 | B | other | 3c945b2d466a0141 | baselines-v1:opus-4 | 0.0006 | 0.0006 | -0.047 (V0.9) | -0.008 mu_wide-1 | -0.008 s11_max_db | -0.047 s11_max_db | -0.004 mu_wide-1 | -2.14 | 3.04 |
| t2-wb1020-gain-0067 | B | other | 6eb0508503263113 | exit-r1:r1-8 | 0.0006 | 0.0006 | -0.069 (V0.9) | -0.018 mu_wide-1 | -0.010 s11_max_db | -0.069 s11_max_db | -0.003 mu_wide-1 | -8.59 | 3.02 |
| t2-nb090-noise-0397 | A | edit:a4:69:add R VOUT1-n7 | abeb7d0337ec8700 | edit | 0.0012 | 0.0012 | -0.305 (V1.1) | -0.025 mu_wide-1 | -0.152 idd_ma | -0.230 s11_max_db | -0.305 idd_ma | -17.51 | 2.97 |
| t2-nb090-noise-0397 | A | edit:a4:13:add C VDD-n2 | 1c047c14b49966a0 | edit | 0.0001 | 0.0001 | -0.232 (V1.1) | 0.000 mu_wide-1 | -0.112 idd_ma | -0.115 s21_db | -0.232 idd_ma | -20.99 | 3.00 |
| t2-nb090-noise-0397 | A | edit:a4:76:add C VSS-n2 | dd52dfaacfc4ee0d | edit | 0.0001 | 0.0001 | -0.232 (V1.1) | 0.000 mu_wide-1 | -0.112 idd_ma | -0.115 s21_db | -0.232 idd_ma | -20.99 | 3.00 |
| t2-nb090-noise-0397 | A | edit:a4:133:add C n6-n7 | 53fe8e4b4b7bca18 | edit | 0.0000 | 0.0000 | -0.367 (V0.9) | -0.048 mu_wide-1 | -0.164 idd_ma | -0.367 s11_max_db | -0.365 idd_ma | -33.44 | 3.00 |
| t2-nb090-noise-0397 | B | other | 3d322338287dbb38 | exit-r1:r1-8 | 0.0072 | 0.0072 | -0.412 (V1.1) | 0.025 s11_max_db | -0.202 idd_ma | -0.117 s11_max_db | -0.412 idd_ma | -26.32 | 2.96 |
| t2-nb090-noise-0397 | B | witness | ceec313555211e72 | witness | 0.0031 | 0.0031 | -0.355 (V1.1) | -0.012 mu_wide-1 | -0.169 idd_ma | -0.110 s11_max_db | -0.355 idd_ma | -26.34 | 3.00 |
| t2-nb090-noise-0397 | B | other | 19f8bc9e9ff333a0 | pilot-v1:h1-sft300 | 0.0000 | 0.0000 | -0.238 (V1.1) | -0.004 mu_wide-1 | -0.110 idd_ma | -0.080 s21_db | -0.238 idd_ma | -23.94 | 3.01 |
| t2-wb1020-gain-0160 | A | edit:a2:46:add C VIN1-n3 | bddbb34d29b79d89 | edit | 0.0015 | 0.0015 | -0.052 (T-40) | -0.052 s21_ripple_db | -0.015 s11_max_db | -0.043 s11_max_db | -0.003 s21_ripple_db | -2.07 | 3.04 |
| t2-wb1020-gain-0160 | A | edit:a2:108:add R n0-n3 | 2e41b23a9f0bdbdc | edit | 0.0014 | 0.0014 | -0.080 (V1.1) | -0.052 mu_wide-1 | -0.043 idd_ma | -0.056 s21_db | -0.080 idd_ma | -1.70 | 3.05 |
| t2-wb1020-gain-0160 | A | edit:a2:156:add R n4-n5 | 6055bde8c4ce8175 | edit | 0.0012 | 0.0012 | -0.166 (V1.1) | -0.026 s21_ripple_db | -0.121 idd_ma | -0.033 s21_db | -0.166 idd_ma | -0.51 | 3.10 |
| t2-wb1020-gain-0160 | A | edit:a2:117:add R n0-n6 | 287e3a8c29bede5b | edit | 0.0008 | 0.0008 | -0.194 (V1.1) | -0.051 mu_wide-1 | -0.117 idd_ma | -0.079 s11_max_db | -0.194 idd_ma | -5.38 | 3.08 |
| t2-wb1020-gain-0160 | A | edit:a2:118:add C n0-n6 | afacef40ecd58d94 | edit | 0.0007 | 0.0007 | -0.123 (T85) | -0.035 mu_wide-1 | -0.123 nf_max_db | -0.048 s11_max_db | -0.106 idd_ma | -6.50 | 3.05 |
| t2-wb1020-gain-0160 | A | edit:a2:55:add C VIN1-n6 | efb3a6bc48ade7ad | edit | 0.0005 | 0.0005 | -0.138 (V1.1) | -0.036 mu_wide-1 | -0.123 nf_max_db | -0.042 s11_max_db | -0.138 idd_ma | -6.24 | 3.05 |
| t2-wb1020-gain-0160 | B | other | bfa9310c0078601e | baselines-v1:opus-4 | 0.0009 | 0.0009 | -0.139 (V1.1) | -0.006 mu_wide-1 | -0.111 s21_ripple_db | -0.058 s11_max_db | -0.139 s21_ripple_db | -10.09 | 3.02 |
| t2-wb1020-gain-0160 | B | other | 1650d740fee4a288 | baselines-v1:opus-4 | 0.0008 | 0.0008 | -0.053 (V0.9) | -0.016 mu_wide-1 | -0.018 s11_max_db | -0.053 s11_max_db | 0.004 mu_wide-1 | -1.36 | 3.05 |
| t2-wb1020-gain-0160 | B | other | 1f48995a648411c6 | ga:run1 | 0.0002 | 0.0002 | -0.072 (T85) | -0.038 mu_wide-1 | -0.072 nf_max_db | -0.054 s11_max_db | 0.007 mu_wide-1 | 0.21 | 3.06 |
| t2-wb1020-gain-0160 | B | witness | 4ff75166a51f9dd6 | witness(seed-2 row) | 0.0001 | 0.0001 | -0.056 (V0.9) | -0.017 mu_wide-1 | -0.049 nf_max_db | -0.056 s11_max_db | -0.015 idd_ma | -1.61 | 3.05 |
| t2-wb1020-gain-0160 | B | other | f41ab2c4621212dc | pilot-v1:h1-sft1000 | 0.0000 | 0.0000 | -0.089 (T85) | -0.014 mu_wide-1 | -0.089 nf_max_db | -0.053 s11_max_db | -0.057 idd_ma | -1.77 | 3.04 |
| t2-wb1020-gain-0108 | A | edit:a2:33:add R VIN1-VSS | 41e90bbe0a79b18a | edit | 0.0020 | 0.0020 | -0.076 (T85) | -0.011 mu_wide-1 | -0.076 nf_max_db | -0.045 s11_max_db | 0.003 mu_wide-1 | -1.54 | 3.04 |
| t2-wb1020-gain-0108 | A | edit:a2:73:add C VOUT1-n4 | 8aaf34ad79432518 | edit | 0.0018 | 0.0018 | -0.058 (V0.9) | -0.043 s21_ripple_db | -0.022 nf_max_db | -0.058 s21_db | -0.004 mu_wide-1 | -7.97 | 3.03 |
| t2-wb1020-gain-0108 | A | edit:a2:46:add C VIN1-n3 | bddbb34d29b79d89 | edit | 0.0015 | 0.0015 | -0.081 (V1.1) | -0.000 mu_wide-1 | -0.019 s21_db | -0.044 s11_max_db | -0.081 idd_ma | -4.39 | 3.03 |
| t2-wb1020-gain-0108 | A | edit:a2:111:add R n0-n4 | b1cd7cf8a6042d59 | edit | 0.0014 | 0.0014 | -0.039 (V0.9) | -0.020 mu_wide-1 | -0.001 s21_db | -0.039 s21_db | 0.001 mu_wide-1 | -1.63 | 3.06 |
| t2-wb1020-gain-0108 | A | edit:a2:102:add R n0-n1 | b7a40a3a1218d6b0 | edit | 0.0010 | 0.0010 | -0.039 (V0.9) | -0.025 mu_wide-1 | -0.010 s11_max_db | -0.039 s11_max_db | 0.003 mu_wide-1 | -3.40 | 3.04 |
| t2-wb1020-gain-0108 | A | edit:a2:117:add R n0-n6 | 287e3a8c29bede5b | edit | 0.0010 | 0.0010 | -0.056 (V0.9) | -0.048 mu_wide-1 | -0.034 s21_db | -0.056 s11_max_db | 0.003 mu_wide-1 | -2.77 | 3.04 |
| t2-wb1020-gain-0108 | B | other | bfa9310c0078601e | baselines-v1:opus-4 | 0.0013 | 0.0013 | -0.051 (V0.9) | 0.002 mu_wide-1 | -0.044 s21_db | -0.051 s11_max_db | -0.002 mu_wide-1 | -5.98 | 3.06 |
| t2-wb1020-gain-0108 | B | other | 7ad493be5a84cf17 | exit-r1:r2-8 | 0.0006 | 0.0006 | -0.074 (T-40) | -0.074 s21_ripple_db | -0.016 s11_max_db | -0.058 s11_max_db | -0.040 s21_ripple_db | -1.86 | 3.04 |
| t2-wb1020-gain-0108 | B | other | 6a25a44de7f67391 | pilot-v1:h1-sft300 | 0.0005 | 0.0005 | -0.084 (V0.9) | -0.039 s21_ripple_db | 0.001 mu_wide-1 | -0.084 s11_max_db | 0.000 mu_wide-1 | -7.47 | 2.99 |
| t2-wb1020-gain-0108 | B | other | 7375cf4634d74769 | pilot-v1:h1-sft300 | 0.0005 | 0.0005 | -0.060 (V0.9) | -0.014 mu_wide-1 | -0.015 s11_max_db | -0.060 s11_max_db | 0.000 mu_wide-1 | -10.04 | 3.03 |
| t2-wb1020-gain-0108 | B | other | ffb865421b789e52 | exit-r1:r2-8,pilot-v1:h1-sft1000 | 0.0004 | 0.0004 | -0.114 (V1.1) | -0.079 s21_ripple_db | -0.066 nf_max_db | -0.041 s11_max_db | -0.114 idd_ma | -5.01 | 3.02 |
| t2-wb1020-gain-0108 | B | other | 3d76bdb1e3e36ef1 | pilot-v1:h1-sft300 | 0.0004 | 0.0004 | -0.065 (T-40) | -0.065 s21_ripple_db | -0.009 s21_db | -0.049 s11_max_db | -0.017 s21_ripple_db | -9.45 | 3.03 |
| t2-nb090-noise-0363 | A | edit:a4:69:add R VOUT1-n7 | abeb7d0337ec8700 | edit | 0.0001 | 0.0001 | -0.291 (V1.1) | -0.034 mu_wide-1 | -0.144 idd_ma | -0.230 s11_max_db | -0.291 idd_ma | -15.40 | 2.98 |
| t2-nb090-noise-0363 | A | edit:a4:79:add C VSS-n4 | 15d32f4eb2fad038 | edit | 0.0000 | 0.0000 | -0.255 (V1.1) | -0.010 mu_wide-1 | -0.127 idd_ma | -0.099 s11_max_db | -0.255 idd_ma | -18.54 | 3.01 |
| t2-nb090-noise-0363 | A | edit:a4:16:add C VDD-n4 | 72b57ad3dc3920e4 | edit | 0.0000 | 0.0000 | -0.255 (V1.1) | -0.010 mu_wide-1 | -0.127 idd_ma | -0.099 s11_max_db | -0.255 idd_ma | -18.54 | 3.01 |
| t2-nb090-noise-0363 | B | witness | c67a81c6d65f7261 | witness | 0.0026 | 0.0026 | -0.360 (V1.1) | -0.003 s11_max_db | -0.170 idd_ma | -0.115 s11_max_db | -0.360 idd_ma | -18.51 | 2.94 |
| t2-nb090-noise-0363 | B | other | 3d85f5d4bee0c03c | exit-r1:r1-8 | 0.0001 | 0.0001 | -0.200 (V1.1) | 0.000 mu_wide-1 | -0.083 idd_ma | -0.088 s11_max_db | -0.200 idd_ma | -22.24 | 2.99 |
| t2-nb090-noise-0363 | B | other | 03cc4359761dde18 | baselines-v1:opus-4 | 0.0000 | 0.0000 | -0.194 (V1.1) | -0.037 s11_max_db | -0.142 idd_ma | -0.106 s11_max_db | -0.194 idd_ma | -19.93 | 2.99 |
| t2-nb090-noise-0363 | B | other | 201870db6f47b049 | ga:run1 | 0.0000 | 0.0000 | -0.201 (V1.1) | -0.009 mu_wide-1 | -0.130 idd_ma | -0.091 s11_max_db | -0.201 idd_ma | -7.21 | 3.07 |
| t2-nb090-noise-0363 | B | other | e3669311c0649b7f | pilot-v0/P1:sft300 | 0.0000 | 0.0000 | -0.247 (V1.1) | -0.009 mu_wide-1 | -0.109 idd_ma | -0.115 s11_max_db | -0.247 idd_ma | -22.64 | 2.97 |
| t2-nb090-noise-0349 | A | edit:a4:69:add R VOUT1-n7 | abeb7d0337ec8700 | edit | 0.0004 | 0.0004 | -0.320 (V1.1) | -0.023 mu_wide-1 | -0.159 idd_ma | -0.243 s11_max_db | -0.320 idd_ma | -15.18 | 2.97 |
| t2-nb090-noise-0349 | A | edit:a4:79:add C VSS-n4 | 15d32f4eb2fad038 | edit | 0.0000 | 0.0000 | -0.250 (V1.1) | -0.009 mu_wide-1 | -0.122 idd_ma | -0.105 s21_db | -0.250 idd_ma | -20.92 | 2.99 |
| t2-nb090-noise-0349 | A | edit:a4:16:add C VDD-n4 | 72b57ad3dc3920e4 | edit | 0.0000 | 0.0000 | -0.250 (V1.1) | -0.009 mu_wide-1 | -0.122 idd_ma | -0.105 s21_db | -0.250 idd_ma | -20.92 | 2.99 |
| t2-nb090-noise-0349 | A | edit:a4:13:add C VDD-n2 | 1c047c14b49966a0 | edit | 0.0000 | 0.0000 | -0.240 (V1.1) | -0.011 s11_max_db | -0.113 idd_ma | -0.114 s21_db | -0.240 idd_ma | -19.65 | 3.00 |
| t2-nb090-noise-0349 | A | edit:a4:76:add C VSS-n2 | dd52dfaacfc4ee0d | edit | 0.0000 | 0.0000 | -0.240 (V1.1) | -0.011 s11_max_db | -0.113 idd_ma | -0.114 s21_db | -0.240 idd_ma | -19.65 | 3.00 |
| t2-nb090-noise-0349 | B | witness | 3d322338287dbb38 | witness | 0.0189 | 0.0189 | -0.384 (V1.1) | 0.060 s11_max_db | -0.186 idd_ma | -0.062 s11_max_db | -0.384 idd_ma | -23.68 | 2.89 |
| t2-nb090-noise-0349 | B | other | 69b9faed1035e8c6 | pilot-v1:h1-sft1000 | 0.0001 | 0.0001 | -0.276 (V1.1) | -0.007 mu_wide-1 | -0.131 idd_ma | -0.097 s11_max_db | -0.276 idd_ma | -22.68 | 2.98 |
| t2-nb090-noise-0349 | B | other | 110875d2d0fd0b30 | exit-r1:r2-8 | 0.0000 | 0.0000 | -0.265 (V1.1) | -0.009 mu_wide-1 | -0.139 idd_ma | -0.116 s21_db | -0.265 idd_ma | -22.44 | 2.98 |
| t2-nb090-noise-0349 | B | other | 34d2233996b4bff3 | exit-r1:r2-8 | 0.0000 | 0.0000 | -0.240 (V1.1) | -0.011 s11_max_db | -0.113 idd_ma | -0.114 s21_db | -0.240 idd_ma | -19.65 | 3.00 |
| t2-wb1020-gain-0159 | A | edit:a2:118:add C n0-n6 | afacef40ecd58d94 | edit | 0.0014 | 0.0014 | -0.098 (T85) | -0.016 mu_wide-1 | -0.098 nf_max_db | -0.047 s11_max_db | 0.004 mu_wide-1 | -0.89 | 3.06 |
| t2-wb1020-gain-0159 | A | edit:a2:19:add C VDD-n3 | 6e1d3fd0b09e73c5 | edit | 0.0010 | 0.0010 | -0.125 (T85) | -0.022 mu_wide-1 | -0.125 nf_max_db | -0.045 s11_max_db | -0.029 idd_ma | -2.04 | 3.03 |
| t2-wb1020-gain-0159 | A | edit:a2:91:add C VSS-n3 | f43cea6e23a5e616 | edit | 0.0010 | 0.0010 | -0.125 (T85) | -0.022 mu_wide-1 | -0.125 nf_max_db | -0.045 s11_max_db | -0.029 idd_ma | -2.04 | 3.03 |
| t2-wb1020-gain-0159 | A | edit:a2:138:add R n2-n4 | 68cbe3d1c52c42f8 | edit | 0.0009 | 0.0009 | -0.046 (V0.9) | -0.036 s21_ripple_db | -0.018 s11_max_db | -0.046 s11_max_db | 0.004 mu_wide-1 | -1.15 | 3.05 |
| t2-wb1020-gain-0159 | A | edit:a2:52:add C VIN1-n5 | ae8c62d24f0bc669 | edit | 0.0003 | 0.0003 | -0.075 (T85) | -0.029 mu_wide-1 | -0.075 nf_max_db | -0.044 s21_db | 0.003 mu_wide-1 | -1.94 | 3.04 |
| t2-wb1020-gain-0159 | A | edit:a2:147:add R n3-n4 | c153839aa24cc89c | edit | 0.0003 | 0.0003 | -0.128 (T85) | -0.015 mu_wide-1 | -0.128 nf_max_db | -0.031 s21_db | -0.079 idd_ma | -0.85 | 3.05 |
| t2-wb1020-gain-0159 | B | other | e7c51a8cdce4fb44 | pilot-v1:h1-sft1000 | 0.0009 | 0.0009 | -0.046 (V0.9) | -0.036 s21_ripple_db | -0.018 s11_max_db | -0.046 s11_max_db | 0.004 mu_wide-1 | -1.15 | 3.05 |
| t2-wb1020-gain-0159 | B | other | bfa9310c0078601e | baselines-v1:opus-4 | 0.0008 | 0.0008 | -0.059 (T85) | -0.012 mu_wide-1 | -0.059 nf_max_db | -0.040 s11_max_db | -0.020 mu_wide-1 | -8.74 | 3.04 |
| t2-wb1020-gain-0159 | B | other | ab7dfbb7b2413795 | exit-r1:r2-8 | 0.0007 | 0.0007 | -0.183 (V1.1) | -0.002 mu_wide-1 | -0.108 nf_max_db | -0.012 s21_db | -0.183 idd_ma | -12.54 | 2.94 |
| t2-wb1020-gain-0159 | B | other | 1650d740fee4a288 | baselines-v1:opus-4 | 0.0006 | 0.0006 | -0.063 (T85) | -0.043 mu_wide-1 | -0.063 nf_max_db | -0.042 s21_db | -0.006 idd_ma | -1.30 | 3.05 |
| t2-wb1020-gain-0159 | B | other | 0b9b3e058ff7ad35 | ga:run1 | 0.0005 | 0.0005 | -0.049 (V0.9) | -0.014 mu_wide-1 | 0.000 mu_wide-1 | -0.049 s21_db | -0.003 mu_wide-1 | 0.89 | 3.10 |
| t2-wb1020-gain-0159 | B | other | 6a25a44de7f67391 | exit-r1:r1-8,pilot-v1:h1-sft300 | 0.0004 | 0.0004 | -0.134 (T85) | -0.029 mu_wide-1 | -0.134 nf_max_db | -0.051 s11_max_db | -0.116 idd_ma | -8.25 | 3.04 |
| t2-wb1020-gain-0109 | A | edit:a2:25:add C VDD-n5 | 499beec009fcc7ba | edit | 0.0010 | 0.0010 | -0.149 (V1.1) | -0.042 mu_wide-1 | -0.144 nf_max_db | -0.046 s11_max_db | -0.149 idd_ma | -7.12 | 3.04 |
| t2-wb1020-gain-0109 | A | edit:a2:97:add C VSS-n5 | ddb4f15a827050d4 | edit | 0.0010 | 0.0010 | -0.149 (V1.1) | -0.042 mu_wide-1 | -0.144 nf_max_db | -0.046 s11_max_db | -0.149 idd_ma | -7.12 | 3.04 |
| t2-wb1020-gain-0109 | A | edit:a2:52:add C VIN1-n5 | ae8c62d24f0bc669 | edit | 0.0005 | 0.0005 | -0.093 (V1.1) | -0.020 mu_wide-1 | -0.042 nf_max_db | -0.043 s11_max_db | -0.093 idd_ma | -1.14 | 3.05 |
| t2-wb1020-gain-0109 | A | edit:a2:117:add R n0-n6 | 287e3a8c29bede5b | edit | 0.0005 | 0.0005 | -0.137 (T85) | -0.053 mu_wide-1 | -0.137 nf_max_db | -0.073 s11_max_db | -0.127 idd_ma | -3.62 | 3.03 |
| t2-wb1020-gain-0109 | A | edit:a2:157:add C n4-n5 | 69cc5006a9ee11dd | edit | 0.0004 | 0.0004 | -0.143 (V1.1) | -0.028 mu_inband-1 | -0.124 nf_max_db | -0.033 s21_db | -0.143 idd_ma | -4.97 | 3.06 |
| t2-wb1020-gain-0109 | A | edit:a2:102:add R n0-n1 | b7a40a3a1218d6b0 | edit | 0.0003 | 0.0003 | -0.123 (T85) | -0.015 mu_wide-1 | -0.123 nf_max_db | -0.044 s11_max_db | -0.045 idd_ma | 0.11 | 3.07 |
| t2-wb1020-gain-0109 | B | other | 805901361d7c5628 | exit-r1:r2-8 | 0.0010 | 0.0010 | -0.149 (V1.1) | -0.042 mu_wide-1 | -0.144 nf_max_db | -0.046 s11_max_db | -0.149 idd_ma | -7.12 | 3.04 |
| t2-wb1020-gain-0109 | B | other | 8a336178e80090ce | pilot-v1:h1-sft1000 | 0.0007 | 0.0007 | -0.174 (V1.1) | -0.032 mu_wide-1 | -0.153 idd_ma | -0.080 s11_max_db | -0.174 idd_ma | -14.44 | 2.96 |
| t2-wb1020-gain-0109 | B | witness | c7c7213716385e74 | witness(seed-2 row) | 0.0007 | 0.0007 | -0.119 (V1.1) | -0.015 mu_wide-1 | -0.090 nf_max_db | -0.112 s11_max_db | -0.119 idd_ma | -17.37 | 2.97 |
| t2-wb1020-gain-0109 | B | other | ed33dec21fd16da6 | exit-r1:r1-8 | 0.0005 | 0.0005 | -1.453 (T-40) | -1.453 mu_wide-1 | -0.013 s21_db | -0.071 s11_max_db | 0.000 mu_wide-1 | -6.54 | 3.00 |
| t2-wb1020-gain-0109 | B | other | 769480492425fc48 | ga:run1 | 0.0003 | 0.0003 | -0.067 (T85) | -0.010 mu_wide-1 | -0.067 nf_max_db | -0.048 s11_max_db | -0.002 mu_wide-1 | -1.67 | 3.03 |
| t2-wb1020-gain-0109 | B | other | 7ad493be5a84cf17 | pilot-v1:h1-sft1000 | 0.0002 | 0.0002 | -0.122 (T85) | -0.005 mu_wide-1 | -0.122 nf_max_db | -0.050 s21_db | -0.103 idd_ma | fail | - |
| t2-nb090-noise-0286 | A | edit:a4:69:add R VOUT1-n7 | abeb7d0337ec8700 | edit | 0.0001 | 0.0001 | -0.281 (V1.1) | -0.027 mu_wide-1 | -0.133 idd_ma | -0.227 s11_max_db | -0.281 idd_ma | -18.23 | 2.95 |
| t2-nb090-noise-0286 | B | other | aa4ecc17828246ac | exit-r1:r1-8 | 0.0030 | 0.0030 | -0.413 (V1.1) | 0.055 mu_wide-1 | -0.204 idd_ma | -0.064 s11_max_db | -0.413 idd_ma | -27.20 | 3.10 |
| t2-nb090-noise-0286 | B | witness | f912f7c64077d8df | witness | 0.0007 | 0.0007 | -0.473 (V1.1) | -0.004 mu_wide-1 | -0.233 idd_ma | -0.073 s11_max_db | -0.473 idd_ma | -28.28 | 3.07 |
| t2-nb090-noise-0312 | A | edit:a4:69:add R VOUT1-n7 | abeb7d0337ec8700 | edit | 0.0002 | 0.0002 | -0.328 (V1.1) | -0.029 s11_max_db | -0.165 idd_ma | -0.243 s11_max_db | -0.328 idd_ma | -15.28 | 2.97 |
| t2-nb090-noise-0312 | B | witness | dc034f10a13643c3 | witness | 0.0001 | 0.0001 | -0.227 (V1.1) | -0.006 mu_wide-1 | -0.104 idd_ma | -0.105 s21_db | -0.227 idd_ma | -20.33 | 3.00 |
| t2-nb090-noise-0312 | B | other | 1b2888fdd5cfa2a0 | exit-r1:r2-8 | 0.0000 | 0.0000 | -0.260 (V1.1) | -0.010 mu_wide-1 | -0.125 idd_ma | -0.087 s11_max_db | -0.260 idd_ma | -21.22 | 3.00 |
| t2-nb090-noise-0312 | B | other | 80e5f1dafbe1050d | baselines-v1:opus-4 | 0.0000 | 0.0000 | -0.236 (V1.1) | -0.104 s11_max_db | -0.201 idd_ma | -0.174 s11_max_db | -0.236 idd_ma | -27.51 | 3.00 |
| t2-nb090-noise-0411 | A | edit:a4:133:add C n6-n7 | 53fe8e4b4b7bca18 | edit | 0.0000 | 0.0000 | -0.390 (V0.9) | -0.044 mu_wide-1 | -0.182 idd_ma | -0.390 s11_max_db | -0.385 idd_ma | -34.46 | 2.99 |
| t2-nb090-noise-0411 | B | witness | affa416ed73cda57 | witness | 0.0023 | 0.0023 | -0.305 (V1.1) | 0.008 mu_wide-1 | -0.148 idd_ma | -0.098 s21_db | -0.305 idd_ma | -19.44 | 3.09 |
| t2-nb090-noise-0411 | B | other | 80e5f1dafbe1050d | baselines-v1:opus-4 | 0.0001 | 0.0001 | -0.216 (V1.1) | -0.076 s11_max_db | -0.199 nf_db | -0.177 s11_max_db | -0.216 idd_ma | -31.43 | 3.04 |
| t2-wb1020-gain-0028 | A | edit:a2:156:add R n4-n5 | 6055bde8c4ce8175 | edit | 0.0006 | 0.0006 | -0.139 (T85) | -0.009 mu_wide-1 | -0.139 nf_max_db | -0.044 nf_max_db | -0.006 mu_wide-1 | 0.51 | 3.08 |
| t2-wb1020-gain-0028 | A | edit:a2:147:add R n3-n4 | c153839aa24cc89c | edit | 0.0005 | 0.0005 | -0.152 (T85) | -0.013 mu_wide-1 | -0.152 nf_max_db | -0.037 s21_db | -0.003 mu_wide-1 | 1.50 | 3.11 |
| t2-wb1020-gain-0028 | A | edit:a2:159:add R n4-n6 | 4a5c1a3368534a04 | edit | 0.0004 | 0.0004 | -0.148 (T85) | -0.015 mu_wide-1 | -0.148 nf_max_db | -0.035 s11_max_db | -0.004 mu_wide-1 | -1.47 | 3.05 |
| t2-wb1020-gain-0028 | A | edit:a2:160:add C n4-n6 | 520fccd7b8664514 | edit | 0.0002 | 0.0002 | -0.165 (T85) | -0.025 mu_wide-1 | -0.165 nf_max_db | -0.043 s21_db | -0.003 mu_wide-1 | -2.49 | 2.99 |
| t2-wb1020-gain-0028 | A | edit:a2:75:add R VOUT1-n5 | 31173d8f4af9c0d2 | edit | 0.0001 | 0.0001 | -0.159 (T85) | -0.023 mu_wide-1 | -0.159 nf_max_db | -0.040 s21_db | -0.142 idd_ma | -7.08 | 3.04 |
| t2-wb1020-gain-0028 | B | other | 91c85b5886bee379 | pilot-v0/P1:sft300 | 0.0008 | 0.0008 | -0.825 (T85) | -0.432 mu_wide-1 | -0.825 nf_max_db | -0.376 mu_wide-1 | -0.220 nf_max_db | -5.41 | 3.03 |
| t2-wb1020-gain-0028 | B | witness | 7c9f1e0bd3a18a3d | witness | 0.0006 | 0.0006 | -0.099 (V0.9) | -0.008 mu_wide-1 | -0.031 s11_max_db | -0.099 s11_max_db | -0.024 idd_ma | -8.49 | 2.96 |
| t2-wb1020-gain-0028 | B | other | 5e85ee92225eaf78 | exit-r1:r1-8 | 0.0003 | 0.0003 | -0.095 (V0.9) | -0.052 s21_ripple_db | -0.082 nf_max_db | -0.095 s11_max_db | -0.054 s21_ripple_db | -10.06 | 2.99 |
| t2-wb1020-gain-0028 | B | other | 5f60909c9c3ae245 | pilot-v1:h1-sft1000 | 0.0003 | 0.0003 | -0.142 (T85) | -0.070 mu_wide-1 | -0.142 nf_max_db | -0.054 s11_max_db | -0.006 mu_wide-1 | -5.27 | 3.03 |
| t2-wb1020-gain-0028 | B | other | a3f9f3661da580fd | ga:run1 | 0.0003 | 0.0003 | -0.149 (T85) | -0.008 mu_wide-1 | -0.149 nf_max_db | -0.057 s11_max_db | -0.004 mu_wide-1 | -0.77 | 3.06 |
| t2-wb1020-gain-0028 | B | other | 7f73c5b04df90e95 | exit-r1:r2-8 | 0.0003 | 0.0003 | -0.148 (T85) | -0.006 mu_wide-1 | -0.148 nf_max_db | -0.013 s21_db | -0.076 idd_ma | -10.17 | 2.98 |
| t2-wb1020-gain-0128 | A | edit:a2:117:add R n0-n6 | 287e3a8c29bede5b | edit | 0.0006 | 0.0006 | -0.217 (V1.1) | -0.065 mu_wide-1 | -0.163 nf_max_db | -0.078 s21_db | -0.217 idd_ma | -4.90 | 3.02 |
| t2-wb1020-gain-0128 | A | edit:a2:118:add C n0-n6 | afacef40ecd58d94 | edit | 0.0004 | 0.0004 | -0.105 (T85) | -0.021 mu_wide-1 | -0.105 nf_max_db | -0.042 s11_max_db | 0.002 mu_wide-1 | -0.69 | 3.06 |
| t2-wb1020-gain-0128 | A | edit:a2:75:add R VOUT1-n5 | 31173d8f4af9c0d2 | edit | 0.0002 | 0.0002 | -0.080 (T85) | -0.051 s11_max_db | -0.080 nf_max_db | -0.047 s11_max_db | -0.044 s11_max_db | -3.62 | 3.03 |
| t2-wb1020-gain-0128 | A | edit:a2:108:add R n0-n3 | 2e41b23a9f0bdbdc | edit | 0.0001 | 0.0001 | -0.146 (T85) | -0.059 mu_wide-1 | -0.146 nf_max_db | -0.057 s11_max_db | -0.030 idd_ma | -0.29 | 3.06 |
| t2-wb1020-gain-0128 | B | other | bfa9310c0078601e | baselines-v1:opus-4 | 0.0006 | 0.0006 | -0.144 (T85) | -0.002 mu_wide-1 | -0.144 nf_max_db | -0.069 s11_max_db | -0.031 mu_wide-1 | -11.98 | 3.01 |
| t2-wb1020-gain-0128 | B | other | 1650d740fee4a288 | baselines-v1:opus-4 | 0.0004 | 0.0004 | -0.139 (T85) | -0.021 mu_wide-1 | -0.139 nf_max_db | -0.041 s11_max_db | -0.028 idd_ma | -0.87 | 3.06 |
| t2-wb1020-gain-0128 | B | witness | 70501bc64b6f7524 | witness | 0.0003 | 0.0003 | -0.086 (T-40) | -0.086 mu_wide-1 | -0.046 s11_max_db | -0.045 s21_db | -0.002 mu_wide-1 | -2.08 | 3.14 |
| t2-wb1020-gain-0128 | B | other | fcc5a40183bd2c56 | ga:run1 | 0.0003 | 0.0003 | -0.142 (T85) | -0.018 mu_wide-1 | -0.142 nf_max_db | -0.048 s11_max_db | -0.086 idd_ma | -1.36 | 3.05 |
| t2-wb1020-gain-0142 | A | edit:a2:19:add C VDD-n3 | 6e1d3fd0b09e73c5 | edit | 0.0013 | 0.0013 | -0.133 (T85) | -0.040 s21_ripple_db | -0.133 nf_max_db | -0.050 s11_max_db | -0.082 idd_ma | -1.57 | 3.03 |
| t2-wb1020-gain-0142 | A | edit:a2:91:add C VSS-n3 | f43cea6e23a5e616 | edit | 0.0013 | 0.0013 | -0.133 (T85) | -0.040 s21_ripple_db | -0.133 nf_max_db | -0.050 s11_max_db | -0.082 idd_ma | -1.57 | 3.03 |
| t2-wb1020-gain-0142 | A | edit:a2:55:add C VIN1-n6 | efb3a6bc48ade7ad | edit | 0.0000 | 0.0000 | -0.160 (V1.1) | -0.025 mu_wide-1 | -0.137 nf_max_db | -0.035 s11_max_db | -0.160 idd_ma | -1.28 | 3.05 |
| t2-wb1020-gain-0142 | B | other | bfa9310c0078601e | baselines-v1:opus-4 | 0.0009 | 0.0009 | -0.070 (V0.9) | -0.002 mu_wide-1 | -0.013 s21_db | -0.070 s11_max_db | -0.015 mu_wide-1 | -8.92 | 3.02 |
| t2-wb1020-gain-0142 | B | other | 2649b5f9f9e28d68 | ga:run1 | 0.0001 | 0.0001 | -0.227 (V1.1) | -0.043 mu_wide-1 | -0.202 idd_ma | -0.078 s11_max_db | -0.227 idd_ma | -1.35 | 3.04 |
| t2-wb1020-gain-0142 | B | witness | d5877e84dcc1236b | witness | 0.0001 | 0.0001 | -0.413 (T-40) | -0.413 mu_wide-1 | -0.101 nf_max_db | -0.069 mu_wide-1 | -0.152 idd_ma | -1.28 | 3.04 |
| t2-wb1020-gain-0142 | B | other | 99b0e6579be788a7 | pilot-v1:h1-sft300 | 0.0000 | 0.0000 | -0.048 (V0.9) | -0.012 mu_wide-1 | -0.030 nf_max_db | -0.048 s11_max_db | -0.000 mu_wide-1 | -2.11 | 3.01 |
| t2-nb090-noise-0012 | B | witness | 1974f59296fbce5d | witness | 0.0002 | 0.0002 | -0.201 (T85) | -0.023 s21_db | -0.201 idd_ma | -0.054 s11_max_db | -0.133 idd_ma | fail | - |
| t2-nb090-noise-0012 | B | other | d847515daf156a2d | ga:run1 | 0.0000 | 0.0000 | -0.230 (V1.1) | 0.000 mu_wide-1 | -0.115 idd_ma | -0.100 s11_max_db | -0.230 idd_ma | -14.27 | 3.06 |
| t2-wb1020-gain-0065 | A | edit:a2:19:add C VDD-n3 | 6e1d3fd0b09e73c5 | edit | 0.0023 | 0.0023 | -0.145 (T85) | -0.023 s21_ripple_db | -0.145 nf_max_db | -0.051 s11_max_db | -0.102 idd_ma | -4.79 | 3.02 |
| t2-wb1020-gain-0065 | A | edit:a2:91:add C VSS-n3 | f43cea6e23a5e616 | edit | 0.0023 | 0.0023 | -0.145 (T85) | -0.023 s21_ripple_db | -0.145 nf_max_db | -0.051 s11_max_db | -0.102 idd_ma | -4.79 | 3.02 |
| t2-wb1020-gain-0065 | A | edit:a2:111:add R n0-n4 | b1cd7cf8a6042d59 | edit | 0.0019 | 0.0019 | -0.126 (T85) | 0.002 mu_wide-1 | -0.126 nf_max_db | -0.063 s11_max_db | -0.112 idd_ma | -4.78 | 3.02 |
| t2-wb1020-gain-0065 | A | edit:a2:118:add C n0-n6 | afacef40ecd58d94 | edit | 0.0014 | 0.0014 | -0.042 (V0.9) | -0.023 s21_ripple_db | -0.009 s11_max_db | -0.042 s11_max_db | -0.000 s21_ripple_db | -1.16 | 3.05 |
| t2-wb1020-gain-0065 | A | edit:a2:159:add R n4-n6 | 4a5c1a3368534a04 | edit | 0.0011 | 0.0011 | -0.105 (T85) | -0.022 mu_wide-1 | -0.105 nf_max_db | -0.042 s11_max_db | 0.001 mu_wide-1 | -0.80 | 3.06 |
| t2-wb1020-gain-0065 | A | edit:a2:151:add C n3-n5 | 96b3d7a7694d428d | edit | 0.0011 | 0.0011 | -0.089 (T85) | -0.049 s21_ripple_db | -0.089 nf_max_db | -0.020 s11_max_db | -0.024 idd_ma | -0.51 | 3.06 |
| t2-wb1020-gain-0065 | B | other | 6026ac9e6e818289 | pilot-v1:h1-sft300 | 0.0043 | 0.0043 | -0.081 (V0.9) | -0.015 s21_ripple_db | 0.017 mu_wide-1 | -0.081 s11_max_db | 0.016 mu_wide-1 | -5.08 | 3.00 |
| t2-wb1020-gain-0065 | B | other | 1ae2444df94939e7 | pilot-v1:h1-sft1000 | 0.0019 | 0.0019 | -0.059 (T-40) | -0.059 mu_wide-1 | -0.011 s11_max_db | -0.042 s11_max_db | -0.005 s21_ripple_db | -3.07 | 3.02 |
| t2-wb1020-gain-0065 | B | other | 1650d740fee4a288 | baselines-v1:opus-4 | 0.0011 | 0.0011 | -0.115 (T85) | -0.046 s21_ripple_db | -0.115 nf_max_db | -0.028 s11_max_db | -0.023 idd_ma | 0.29 | 3.08 |
| t2-wb1020-gain-0065 | B | other | d4132bb06086275d | pilot-v0/P1:sft300 | 0.0006 | 0.0006 | -0.120 (V0.9) | -0.062 s11_max_db | -0.018 s21_db | -0.120 s11_max_db | 0.001 mu_wide-1 | -10.32 | 2.98 |
| t2-wb1020-gain-0065 | B | other | 672212436a453e4a | pilot-v1:h1-sft300 | 0.0006 | 0.0006 | -0.096 (V0.9) | -0.018 mu_wide-1 | 0.001 mu_wide-1 | -0.096 s11_max_db | -0.008 mu_wide-1 | -6.64 | 2.97 |
| t2-wb1020-gain-0065 | B | other | 711ffe9fba0bcb72 | pilot-v1:h1-sft300 | 0.0005 | 0.0005 | -0.066 (V0.9) | -0.013 mu_wide-1 | 0.001 mu_wide-1 | -0.066 s11_max_db | -0.004 mu_wide-1 | -8.02 | 3.05 |
| t2-wb1020-gain-0161 | A | edit:a2:19:add C VDD-n3 | 6e1d3fd0b09e73c5 | edit | 0.0026 | 0.0026 | -0.060 (V0.9) | -0.021 mu_wide-1 | -0.008 s11_max_db | -0.060 s11_max_db | -0.003 s11_max_db | -3.67 | 3.02 |
| t2-wb1020-gain-0161 | A | edit:a2:91:add C VSS-n3 | f43cea6e23a5e616 | edit | 0.0026 | 0.0026 | -0.060 (V0.9) | -0.021 mu_wide-1 | -0.008 s11_max_db | -0.060 s11_max_db | -0.003 s11_max_db | -3.67 | 3.02 |
| t2-wb1020-gain-0161 | A | edit:a2:55:add C VIN1-n6 | efb3a6bc48ade7ad | edit | 0.0024 | 0.0024 | -0.047 (V0.9) | -0.016 mu_wide-1 | -0.010 s11_max_db | -0.047 s11_max_db | 0.004 mu_wide-1 | -1.72 | 3.05 |
| t2-wb1020-gain-0161 | A | edit:a2:117:add R n0-n6 | 287e3a8c29bede5b | edit | 0.0024 | 0.0024 | -0.118 (V1.1) | -0.056 mu_wide-1 | -0.088 idd_ma | -0.035 s21_db | -0.118 idd_ma | -0.51 | 3.05 |
| t2-wb1020-gain-0161 | A | edit:a2:154:add C n3-n6 | c8929e476f02c354 | edit | 0.0018 | 0.0018 | -0.067 (T-40) | -0.067 s21_ripple_db | -0.008 s11_max_db | -0.042 s21_db | -0.063 s21_ripple_db | -2.50 | 3.02 |
| t2-wb1020-gain-0161 | A | edit:a2:111:add R n0-n4 | b1cd7cf8a6042d59 | edit | 0.0017 | 0.0017 | -0.090 (V1.1) | -0.066 mu_wide-1 | -0.029 s21_db | -0.055 s21_db | -0.090 idd_ma | -7.21 | 3.04 |
| t2-wb1020-gain-0161 | B | other | 551f7d7be66df89a | pilot-v0/P1:sft1000 | 0.0018 | 0.0018 | -0.067 (T-40) | -0.067 s21_ripple_db | -0.008 s11_max_db | -0.042 s21_db | -0.063 s21_ripple_db | -2.50 | 3.02 |
| t2-wb1020-gain-0161 | B | other | 3c945b2d466a0141 | baselines-v1:opus-4 | 0.0014 | 0.0014 | -0.145 (V1.1) | -0.006 mu_wide-1 | -0.087 idd_ma | -0.032 s21_db | -0.145 idd_ma | -1.66 | 3.07 |
| t2-wb1020-gain-0161 | B | other | a3cbe140f8600096 | exit-r1:r1-8 | 0.0013 | 0.0013 | -0.161 (V1.1) | -0.011 mu_wide-1 | -0.063 idd_ma | -0.033 s11_max_db | -0.161 idd_ma | -2.40 | 3.03 |
| t2-wb1020-gain-0161 | B | other | 4535e9a46bae3de3 | pilot-v1:h1-sft1000 | 0.0007 | 0.0007 | -0.050 (T-40) | -0.050 mu_wide-1 | -0.018 s21_db | -0.046 s11_max_db | -0.046 idd_ma | -1.77 | 3.03 |
| t2-wb1020-gain-0161 | B | other | ab7dfbb7b2413795 | pilot-v1:h1-sft1000 | 0.0006 | 0.0006 | -0.089 (V0.9) | -0.044 mu_wide-1 | -0.022 s11_max_db | -0.089 s11_max_db | -0.055 idd_ma | -13.73 | 2.96 |
| t2-wb1020-gain-0161 | B | other | ad756002b7408ced | pilot-v1:h1-sft300 | 0.0005 | 0.0005 | -0.135 (T-40) | -0.135 s21_ripple_db | -0.052 s21_db | -0.019 s21_db | -0.098 idd_ma | -13.50 | 2.96 |
| v2b-wb1020-noise-217 | B | witness | 643274f4ddabb6aa | witness | 0.0003 | 0.0003 | -0.139 (V1.1) | -0.007 mu_wide-1 | -0.100 idd_ma | -0.068 s11_max_db | -0.139 idd_ma | -0.42 | 3.06 |
| v2b-wb1020-noise-217 | B | other | e66a2ea9cfed9434 | ga:run1 | 0.0002 | 0.0002 | -0.150 (T85) | -0.011 mu_wide-1 | -0.150 nf_max_db | -0.041 nf_max_db | -0.097 idd_ma | fail | - |
| v2b-wb1020-noise-217 | B | other | ab7dfbb7b2413795 | exit-r1:r2-8,pilot-v1:h1-sft1000 | 0.0000 | 0.0000 | -0.178 (V1.1) | -0.031 mu_wide-1 | -0.163 nf_max_db | -0.124 s11_max_db | -0.178 idd_ma | -15.28 | 2.96 |
| t2-nb090-noise-0322 | A | edit:a4:115:add C n2-n7 | 0152ea8d3dc98f3e | edit | 0.0000 | 0.0000 | -0.820 (V0.9) | -0.389 s11_max_db | -0.239 s11_max_db | -0.820 s11_max_db | -0.501 s11_max_db | -39.40 | 2.95 |
| t2-nb090-noise-0322 | B | witness | fc570011d604a839 | witness | 0.0017 | 0.0017 | -0.274 (V1.1) | 0.013 mu_wide-1 | -0.137 idd_ma | -0.053 s21_db | -0.274 idd_ma | -17.00 | 2.98 |
| t2-nb090-noise-0322 | B | other | 7e6e2d8ab6b57cce | pilot-v1:h1-sft300 | 0.0009 | 0.0009 | -0.217 (V1.1) | -0.043 s11_max_db | -0.110 idd_ma | -0.046 s11_max_db | -0.217 idd_ma | -27.39 | 3.02 |
| t2-nb090-noise-0322 | B | other | 769af9eca1f73972 | exit-r1:r1-8 | 0.0000 | 0.0000 | -0.223 (V1.1) | -0.030 s11_max_db | -0.176 idd_ma | -0.090 s21_db | -0.223 idd_ma | -21.50 | 2.99 |
| t2-nb090-noise-0322 | B | other | d85af78f74c0dc48 | pilot-v0/P1:sft300 | 0.0000 | 0.0000 | -0.209 (V1.1) | -0.009 mu_wide-1 | -0.098 nf_db | -0.101 s21_db | -0.209 idd_ma | -16.55 | 3.00 |
| t2-nb090-noise-0291 | A | edit:a4:79:add C VSS-n4 | 15d32f4eb2fad038 | edit | 0.0000 | 0.0000 | -0.264 (V1.1) | -0.014 s11_max_db | -0.131 idd_ma | -0.097 s11_max_db | -0.264 idd_ma | -20.58 | 3.00 |
| t2-nb090-noise-0291 | A | edit:a4:16:add C VDD-n4 | 72b57ad3dc3920e4 | edit | 0.0000 | 0.0000 | -0.264 (V1.1) | -0.014 s11_max_db | -0.131 idd_ma | -0.097 s11_max_db | -0.264 idd_ma | -20.58 | 3.00 |
| t2-nb090-noise-0291 | A | edit:a4:13:add C VDD-n2 | 1c047c14b49966a0 | edit | 0.0000 | 0.0000 | -0.218 (V1.1) | -0.007 mu_wide-1 | -0.102 idd_ma | -0.098 s21_db | -0.218 idd_ma | -20.45 | 2.99 |
| t2-nb090-noise-0291 | A | edit:a4:76:add C VSS-n2 | dd52dfaacfc4ee0d | edit | 0.0000 | 0.0000 | -0.218 (V1.1) | -0.007 mu_wide-1 | -0.102 idd_ma | -0.098 s21_db | -0.218 idd_ma | -20.45 | 2.99 |
| t2-nb090-noise-0291 | B | other | 27344662ef7fd6e2 | pilot-v0/P1:sft300 | 0.0000 | 0.0000 | -0.201 (V1.1) | -0.009 mu_wide-1 | -0.122 idd_ma | -0.101 s21_db | -0.201 idd_ma | -16.08 | 3.00 |
| t2-nb090-noise-0291 | B | witness | c83c0d64454bdeb2 | witness(seed-2 row) | 0.0000 | 0.0000 | -0.249 (V1.1) | -0.007 mu_wide-1 | -0.121 idd_ma | -0.103 s21_db | -0.249 idd_ma | -21.25 | 2.98 |
| t2-nb090-noise-0291 | B | other | 18c94ad8841f0f91 | pilot-v1:h1-sft300 | 0.0000 | 0.0000 | -0.355 (V0.9) | -0.036 mu_inband-1 | -0.133 idd_ma | -0.355 s11_max_db | -0.271 idd_ma | -21.85 | 3.00 |
| t2-nb090-noise-0375 | A | edit:a4:69:add R VOUT1-n7 | abeb7d0337ec8700 | edit | 0.0002 | 0.0002 | -0.309 (V1.1) | -0.024 mu_wide-1 | -0.148 idd_ma | -0.226 s11_max_db | -0.309 mu_wide-1 | -16.16 | 2.97 |
| t2-nb090-noise-0375 | A | edit:a4:13:add C VDD-n2 | 1c047c14b49966a0 | edit | 0.0000 | 0.0000 | -0.244 (V1.1) | -0.006 mu_wide-1 | -0.116 idd_ma | -0.098 s21_db | -0.244 idd_ma | -22.52 | 2.98 |
| t2-nb090-noise-0375 | A | edit:a4:76:add C VSS-n2 | dd52dfaacfc4ee0d | edit | 0.0000 | 0.0000 | -0.244 (V1.1) | -0.006 mu_wide-1 | -0.116 idd_ma | -0.098 s21_db | -0.244 idd_ma | -22.52 | 2.98 |
| t2-nb090-noise-0375 | A | edit:a4:115:add C n2-n7 | 0152ea8d3dc98f3e | edit | 0.0000 | 0.0000 | -0.579 (V0.9) | -0.193 s11_max_db | -0.207 idd_ma | -0.579 s11_max_db | -0.410 idd_ma | -34.14 | 2.96 |
| t2-nb090-noise-0375 | A | edit:a4:133:add C n6-n7 | 53fe8e4b4b7bca18 | edit | 0.0000 | 0.0000 | -0.381 (V1.1) | -0.057 mu_wide-1 | -0.177 idd_ma | -0.351 s11_max_db | -0.381 idd_ma | -32.67 | 3.00 |
| t2-nb090-noise-0375 | B | other | 3d322338287dbb38 | exit-r1:r1-8 | 0.0008 | 0.0008 | -0.383 (V1.1) | -0.008 mu_wide-1 | -0.189 idd_ma | -0.092 s11_max_db | -0.383 idd_ma | -21.89 | 2.96 |
| t2-nb090-noise-0375 | B | witness | 665115910319e4f5 | witness(seed-2 row) | 0.0000 | 0.0000 | -0.266 (V1.1) | -0.007 mu_wide-1 | -0.128 idd_ma | -0.096 s11_max_db | -0.266 idd_ma | -23.20 | 3.00 |
| t2-nb090-noise-0375 | B | other | 7e98bd5f9fa5422d | pilot-v1:h1-sft300 | 0.0000 | 0.0000 | -0.267 (V1.1) | -0.007 mu_wide-1 | -0.129 idd_ma | -0.097 s21_db | -0.267 idd_ma | -22.08 | 2.98 |
| t2-nb090-noise-0375 | B | other | a5d858ad44b2308d | pilot-v1:h1-sft300 | 0.0000 | 0.0000 | -0.271 (V1.1) | -0.008 mu_wide-1 | -0.127 idd_ma | -0.107 s11_max_db | -0.271 idd_ma | -22.47 | 2.98 |
| t2-nb090-noise-0375 | B | other | e500032e10dec103 | pilot-v1:h1-sft1000 | 0.0000 | 0.0000 | -0.254 (V1.1) | -0.007 mu_wide-1 | -0.123 idd_ma | -0.074 s21_db | -0.254 idd_ma | -22.19 | 2.98 |
| t2-nb090-noise-0375 | B | other | cc1b8cdd68b5107e | exit-r1:r2-8 | 0.0000 | 0.0000 | -0.271 (V1.1) | -0.008 mu_wide-1 | -0.130 idd_ma | -0.093 s21_db | -0.271 idd_ma | -19.90 | 2.99 |

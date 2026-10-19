
**R1** (M = gain_db, dB; witness M* 82.27)

| design | category | seed | nominal M (D0) | ≥ W* | robust | failing corners | worst corner: constraint margin | M at worst-M corner |
|---|---|---|---|---|---|---|---|---|
| W:W-R1 | witness | 1 | 61.02 |  | **fail** | t_hot,mm1,mm2,mm3 | mm2: invalid (outcm_outside_swing_window) | — |
| W:W-R1 | witness | 2 | 82.27 | yes | **fail** | vdd_lo,t_hot,mm1,mm3 | t_hot: ugf_mhz -0.939 | 31.23 |
| W:W-R1 | witness | 3 | 86.99 | yes | **fail** | vdd_lo,t_cold | t_cold: ugf_mhz -0.766 | 69.81 |
| F2:two_stage_rz:1786 | single-edit | 1 | 73.00 |  | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm1,mm2,mm3,mm4 | vdd_lo: invalid (outcm_outside_swing_window) | — |
| F2:two_stage_rz:1786 | single-edit | 2 | 68.09 |  | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm1,mm2,mm3 | t_hot: ugf_mhz -0.977 | 44.86 |
| F2:two_stage_rz:1786 | single-edit | 3 | 64.04 |  | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm1,mm3 | t_hot: ugf_mhz -0.843 | 44.22 |
| F2:two_stage_rz:517 | single-edit | 1 | 67.60 |  | **fail** | vdd_lo,vdd_hi,t_hot,mm1,mm2,mm4 | vdd_lo: pm_deg -0.849 | 60.21 |
| F2:two_stage_rz:517 | single-edit | 2 | 67.55 |  | **fail** | vdd_lo,vdd_hi,mm1,mm2,mm3 | vdd_lo: ugf_mhz -0.633 | 60.20 |
| F2:two_stage_rz:517 | single-edit | 3 | 67.57 |  | **fail** | vdd_lo,vdd_hi,t_hot,mm1,mm2 | vdd_lo: ugf_mhz -0.601 | 62.07 |
| F2:two_stage_rz:635 | single-edit | 1 | 79.86 |  | **fail** | vdd_hi,t_hot,mm1,mm2,mm3,mm4 | vdd_hi: invalid (polarity,pm_unphysical,outcm_outside_swing_window) | — |
| F2:two_stage_rz:635 | single-edit | 2 | 86.92 | yes | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm2,mm4 | vdd_hi: invalid (polarity,pm_unphysical,outcm_outside_swing_window) | — |
| F2:two_stage_rz:635 | single-edit | 3 | 79.63 |  | **fail** | vdd_hi,t_hot,mm1,mm2,mm3 | vdd_hi: invalid (polarity,pm_unphysical,outcm_outside_swing_window) | — |
| TE:two_stage_rz:412 | two-edit | 1 | 73.13 |  | **fail** | vdd_hi,mm1,mm3 | vdd_hi: invalid (polarity,pm_unphysical,outcm_outside_swing_window) | — |
| F1:folded_cascode | F1 | 1 | 58.80 |  | **fail** | vdd_lo,mm1,mm3,mm4 | vdd_lo: swing_vpp -0.077 | 50.24 |
| F1:folded_cascode | F1 | 2 | 58.17 |  | **fail** | vdd_lo,t_hot,mm4 | vdd_lo: swing_vpp -0.083 | 55.89 |
| F1:folded_cascode | F1 | 3 | 56.73 |  | **fail** | vdd_lo,vdd_hi,mm1,mm2,mm3,mm4 | vdd_lo: swing_vpp -0.090 | 47.98 |
| F1:ota5t | F1 | 1 | 28.55 |  | **fail** | vdd_lo,t_hot,mm2,mm3 | t_hot: swing_vpp -0.115 | 27.60 |
| F1:ota5t | F1 | 2 | 28.55 |  | **fail** | vdd_lo,t_hot,mm2,mm3 | t_hot: swing_vpp -0.115 | 27.60 |
| F1:ota5t | F1 | 3 | 28.55 |  | **fail** | vdd_lo,t_hot,mm2,mm3 | t_hot: swing_vpp -0.117 | 27.61 |
| F1:telescopic | F1 | 1 | 32.66 |  | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm2,mm4 | t_cold: invalid (outcm_outside_swing_window) | — |
| F1:telescopic | F1 | 2 | 31.94 |  | **fail** | vdd_hi,t_cold,t_hot,mm1,mm2,mm4 | t_cold: invalid (outcm_outside_swing_window) | — |
| F1:telescopic | F1 | 3 | 32.73 |  | **fail** | vdd_hi,t_cold,t_hot,mm2,mm4 | t_cold: swing_vpp -0.127 | 29.38 |
| F1:three_stage_nmc | F1 | 1 | 58.51 |  | **fail** | t_cold,t_hot | t_hot: idd_ua -0.218 | 50.55 |
| F1:three_stage_nmc | F1 | 2 | 89.73 | yes | **fail** | vdd_hi,t_hot,mm1 | vdd_hi: invalid (outcm_outside_swing_window) | — |
| F1:two_stage_rz | F1 | 1 | 63.50 |  | **fail** | vdd_lo,t_cold,t_hot | t_hot: ugf_mhz -0.750 | 46.14 |
| F1:two_stage_rz | F1 | 2 | 59.48 |  | **fail** | vdd_lo,vdd_hi,t_hot,mm1,mm2,mm3,mm4 | vdd_lo: swing_vpp -0.101 | 53.79 |
| F1:two_stage_rz | F1 | 3 | 64.37 |  | **fail** | vdd_lo,t_cold,t_hot,mm2 | t_hot: ugf_mhz -0.812 | 44.22 |

**R23** (M = fom_mhzpf_ma, MHz·pF/mA; witness M* 15272)

| design | category | seed | nominal M (D0) | ≥ W* | robust | failing corners | worst corner: constraint margin | M at worst-M corner |
|---|---|---|---|---|---|---|---|---|
| W:W-R23 | witness | 1 | 14502 |  | **fail** | t_cold,t_hot,mm1,mm2,mm3,mm4 | mm1: invalid (vout_not_tracking) | — |
| W:W-R23 | witness | 2 | 15272 | yes | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm2,mm3,mm4 | t_cold: pm_deg -0.974 | 3860 |
| W:W-R23 | witness | 3 | 19953 | yes | **fail** | vdd_lo,t_cold,t_hot,mm2,mm4 | t_cold: pm_deg -1.465 | 6868 |
| F2:two_stage_rz:1106 | single-edit | 3 | 23406 | yes | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm1,mm2,mm3,mm4 | mm1: invalid (polarity,pm_unphysical) | — |
| F2:two_stage_rz:1165 | single-edit | 1 | 5332 |  | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm1,mm2,mm3,mm4 | vdd_lo: invalid (outcm_outside_swing_window) | — |
| F2:two_stage_rz:1165 | single-edit | 2 | 16614 | yes | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm1,mm2,mm3,mm4 | t_cold: invalid (polarity,pm_unphysical,outcm_outside_swing_window) | — |
| F2:two_stage_rz:1165 | single-edit | 3 | 17918 | yes | **fail** | vdd_lo,t_cold,t_hot,mm1,mm2,mm3,mm4 | t_cold: invalid (polarity,pm_unphysical,outcm_outside_swing_window) | — |
| F2:two_stage_rz:1221 | single-edit | 1 | 16075 | yes | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm1,mm2,mm3,mm4 | vdd_hi: invalid (polarity,pm_unphysical,outcm_outside_swing_window) | — |
| F2:two_stage_rz:1221 | single-edit | 2 | 16614 | yes | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm1,mm2,mm3,mm4 | t_cold: invalid (polarity,pm_unphysical,outcm_outside_swing_window) | — |
| F2:two_stage_rz:1221 | single-edit | 3 | 15879 | yes | **fail** | vdd_lo,t_cold,t_hot,mm1,mm2,mm3,mm4 | t_cold: invalid (polarity,pm_unphysical,outcm_outside_swing_window) | — |
| F2:two_stage_rz:386 | single-edit | 1 | 21178 | yes | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm1,mm2,mm3,mm4 | vdd_hi: invalid (polarity,pm_unphysical,outcm_outside_swing_window) | — |
| F2:two_stage_rz:387 | single-edit | 1 | 11291 |  | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm1,mm2,mm3,mm4 | vdd_lo: invalid (outcm_outside_swing_window) | — |
| F2:two_stage_rz:387 | single-edit | 2 | 19205 | yes | **fail** | vdd_lo,t_cold,t_hot,mm1,mm2,mm3,mm4 | vdd_lo: invalid (outcm_outside_swing_window) | — |
| F2:two_stage_rz:387 | single-edit | 3 | 28961 | yes | **fail** | vdd_hi,t_cold,t_hot,mm1,mm2,mm3,mm4 | vdd_hi: invalid (outcm_outside_swing_window) | — |
| F2:two_stage_rz:398 | single-edit | 3 | 18676 | yes | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm1,mm2,mm3,mm4 | vdd_hi: invalid (polarity,pm_unphysical,outcm_outside_swing_window) | — |
| F2:two_stage_rz:640 | single-edit | 1 | 18532 | yes | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm1,mm2,mm3,mm4 | vdd_hi: invalid (polarity,pm_unphysical,outcm_outside_swing_window) | — |
| F2:two_stage_rz:640 | single-edit | 2 | 5210 |  | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm1,mm2,mm3,mm4 | vdd_lo: invalid (polarity,pm_unphysical,outcm_outside_swing_window) | — |
| F2:two_stage_rz:640 | single-edit | 3 | 26433 | yes | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm1,mm2,mm3,mm4 | vdd_hi: invalid (polarity,pm_unphysical,outcm_outside_swing_window) | — |
| F2:two_stage_rz:708 | single-edit | 1 | 25506 | yes | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm1,mm2,mm4 | vdd_lo: invalid (vout_not_tracking,no_gain,outcm_outside_swing_window) | — |
| TE:two_stage_rz:146 | two-edit | 1 | 14960 |  | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm1,mm2,mm3,mm4 | vdd_lo: invalid (polarity,pm_unphysical,outcm_outside_swing_window) | — |
| F1:three_stage_nmc | F1 | 1 | 6802 |  | **fail** | vdd_lo,t_cold,t_hot,mm1,mm3,mm4 | t_hot: gain_db -0.180 | 1261 |
| F1:three_stage_nmc | F1 | 2 | 20101 | yes | **fail** | vdd_hi,t_hot,mm1,mm2,mm3 | mm3: pm_deg -0.289 | 15912 |
| F1:three_stage_nmc | F1 | 3 | 18997 | yes | **fail** | vdd_lo,t_hot,mm2,mm3 | mm3: pm_deg -0.189 | 15407 |

**R4** (M = icmr_v, V; witness M* 0.963)

| design | category | seed | nominal M (D0) | ≥ W* | robust | failing corners | worst corner: constraint margin | M at worst-M corner |
|---|---|---|---|---|---|---|---|---|
| W:W-R4 | witness | 1 | 0.97 | yes | **fail** | vdd_hi,t_cold,t_hot,mm1 | vdd_hi: invalid (outcm_outside_swing_window) | — |
| W:W-R4 | witness | 2 | 0.913 |  | **fail** | vdd_hi,t_hot,mm2,mm4 | t_hot: gain_db -0.352 | 0 |
| W:W-R4 | witness | 3 | 0.963 | yes | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm1,mm3,mm4 | vdd_hi: invalid (outcm_outside_swing_window) | — |
| F2:two_stage_rz:1164 | single-edit | 1 | 0.964 | yes | **fail** | vdd_lo,t_cold,t_hot,mm1,mm2,mm3,mm4 | mm1: invalid (outcm_outside_swing_window) | — |
| F2:two_stage_rz:1164 | single-edit | 2 | 0.969 | yes | **fail** | t_cold,t_hot,mm1,mm2,mm3,mm4 | mm1: invalid (outcm_outside_swing_window) | — |
| F2:two_stage_rz:1164 | single-edit | 3 | 0.969 | yes | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm1,mm2,mm3,mm4 | vdd_hi: invalid (outcm_outside_swing_window) | — |
| F2:two_stage_rz:1443 | single-edit | 1 | 0.948 |  | **fail** | vdd_hi,t_cold,t_hot,mm2,mm4 | t_cold: invalid (outcm_outside_swing_window) | — |
| F2:two_stage_rz:1443 | single-edit | 2 | 0.952 |  | **fail** | vdd_hi,t_cold,t_hot,mm2,mm4 | t_cold: invalid (outcm_outside_swing_window) | — |
| F2:two_stage_rz:1443 | single-edit | 3 | 0.939 |  | **fail** | t_hot | t_hot: gain_db -0.205 | 0.74 |
| F2:two_stage_rz:407 | single-edit | 1 | 0.953 |  | **fail** | vdd_lo,t_hot,mm2 | vdd_lo: invalid (outcm_outside_swing_window) | — |
| F2:two_stage_rz:407 | single-edit | 2 | 0.979 | yes | **fail** | vdd_lo,t_cold,t_hot,mm2,mm4 | vdd_lo: invalid (outcm_outside_swing_window) | — |
| F2:two_stage_rz:407 | single-edit | 3 | 0.957 |  | **fail** | vdd_lo,vdd_hi,t_cold,t_hot,mm1,mm2,mm3,mm4 | vdd_lo: invalid (outcm_outside_swing_window) | — |
| TE:two_stage_rz:1 | two-edit | 1 | 0.969 | yes | **fail** | vdd_lo,t_cold,t_hot,mm1,mm2,mm3,mm4 | vdd_lo: invalid (outcm_outside_swing_window) | — |
| TE:two_stage_rz:14 | two-edit | 1 | 0.969 | yes | **fail** | vdd_lo,t_cold,t_hot,mm1,mm2,mm3,mm4 | mm1: invalid (outcm_outside_swing_window) | — |
| TE:two_stage_rz:177 | two-edit | 1 | 0.968 | yes | **fail** | vdd_lo,vdd_hi,t_hot,mm1,mm2,mm3,mm4 | mm1: invalid (outcm_outside_swing_window) | — |
| TE:two_stage_rz:419 | two-edit | 1 | 0.971 | yes | **fail** | t_cold,t_hot | t_cold: ugf_mhz -0.128 | 0.697 |
| TE:two_stage_rz:44 | two-edit | 1 | 0.972 | yes | **fail** | t_cold,t_hot | t_cold: invalid (outcm_outside_swing_window) | — |
| F1:folded_cascode | F1 | 1 | 0.766 |  | **fail** | vdd_hi,t_cold,t_hot,mm1,mm3,mm4 | t_hot: gain_db -0.142 | 0.599 |
| F1:folded_cascode | F1 | 2 | 0.744 |  | **fail** | t_cold,t_hot,mm2 | t_cold: gain_db -0.022 | 0.567 |
| F1:folded_cascode | F1 | 3 | 0.775 |  | **fail** | t_hot,mm2,mm4 | t_hot: invalid (vout_not_tracking,no_gain) | — |
| F1:telescopic | F1 | 1 | 0.366 |  | **fail** | vdd_lo,t_hot,mm1,mm3 | vdd_lo: invalid (outcm_outside_swing_window) | — |
| F1:telescopic | F1 | 2 | 0.337 |  | **fail** | vdd_lo,t_hot,mm1,mm3 | vdd_lo: invalid (outcm_outside_swing_window) | — |
| F1:telescopic | F1 | 3 | 0.349 |  | **fail** | vdd_lo,t_hot,mm1,mm3 | vdd_lo: invalid (outcm_outside_swing_window) | — |
| F1:three_stage_nmc | F1 | 1 | 0.873 |  | **fail** | t_hot,mm1,mm2 | t_hot: invalid (vout_not_tracking,no_gain,outcm_outside_swing_window) | — |
| F1:three_stage_nmc | F1 | 2 | 0.899 |  | **fail** | vdd_hi,t_cold | vdd_hi: invalid (outcm_outside_swing_window) | — |
| F1:three_stage_nmc | F1 | 3 | 0.823 |  | **fail** | vdd_lo,t_cold,t_hot,mm2 | t_hot: invalid (vout_not_tracking,no_gain,outcm_outside_swing_window) | — |
| F1:two_stage_rz | F1 | 1 | 0.834 |  | **fail** | t_hot | t_hot: gain_db -0.066 | 0.714 |
| F1:two_stage_rz | F1 | 2 | 0.861 |  | **fail** | vdd_hi,t_hot,mm2,mm4 | t_hot: invalid (vout_not_tracking) | — |
| F1:two_stage_rz | F1 | 3 | 0.831 |  | **fail** | vdd_lo,t_hot,mm2,mm4 | t_hot: gain_db -0.202 | 0.742 |

**Per category** (as sized; 8 corners each unless fewer matched groups)

| regime/category | n | robust pass | mean failing corners | mean invalid corners | designs with a polarity flip | median M(worst corner)/M(nominal) |
|---|---|---|---|---|---|---|
| R1/witness | 3 | 0 | 3.3 | 0.3 | 0 | 0.803 (2 of 3 valid at all corners) |
| R1/single-edit | 9 | 0 | 6.0 | 1.9 | 3 | 0.891 (5 of 9 valid at all corners) |
| R1/two-edit | 1 | 0 | 3.0 | 1.0 | 1 | — (0 of 1 valid at all corners) |
| R1/F1 | 14 | 0 | 4.4 | 0.4 | 0 | 0.898 (11 of 14 valid at all corners) |
| R23/witness | 3 | 0 | 6.0 | 1.0 | 0 | 0.344 (2 of 3 valid at all corners) |
| R23/single-edit | 16 | 0 | 7.7 | 4.4 | 16 | — (0 of 16 valid at all corners) |
| R23/two-edit | 1 | 0 | 8.0 | 6.0 | 1 | — (0 of 1 valid at all corners) |
| R23/F1 | 3 | 0 | 5.0 | 0.0 | 0 | 0.792 |
| R4/witness | 3 | 0 | 5.0 | 2.3 | 0 | 0 (1 of 3 valid at all corners) |
| R4/single-edit | 9 | 0 | 5.3 | 3.4 | 0 | 0.788 (1 of 9 valid at all corners) |
| R4/two-edit | 5 | 0 | 5.0 | 2.4 | 0 | 0.718 (1 of 5 valid at all corners) |
| R4/F1 | 12 | 0 | 3.5 | 1.0 | 0 | 0.856 (4 of 12 valid at all corners) |

**Re-sized with the gate ON** (max:M, seed 1, 2,500 evals)

| regime | design | robust-feasible | M (gate on) | M at worst-M corner | D0 M* (gate off) | nominal feasible | worst corner: constraint margin | CPU s |
|---|---|---|---|---|---|---|---|---|
| R1 | W:W-R1 | **yes** | 56.33 | 43.64 | 82.27 | True | t_hot: ugf_mhz +0.010 | 907 |
| R1 | F2:two_stage_rz:1786 | **yes** | 60.27 | 52.17 | 68.09 | True | t_cold: pm_deg +0.001 | 436 |
| R1 | F2:two_stage_rz:517 | **yes** | 65.03 | 59.59 | 67.57 | True | vdd_hi: pm_deg +0.007 | 663 |
| R1 | F2:two_stage_rz:635 | **yes** | 76.83 | 45.14 | 79.86 | True | vdd_lo: swing_vpp +0.111 | 532 |
| R23 | W:W-R23 | **yes** | 11628 | 7295 | 15272 | True | t_hot: gain_db +0.025 | 1628 |
| R23 | F2:two_stage_rz:1165 | **no** | — | — | 16614 | True | t_cold: invalid (polarity,pm_unphysical,outcm_outside_swing_window) | 57 |
| R23 | F2:two_stage_rz:387 | **no** | — | — | 19205 | True | vdd_hi: invalid (polarity,pm_unphysical,outcm_outside_swing_window) | 44 |
| R23 | F2:two_stage_rz:640 | **no** | — | — | 18532 | True | vdd_hi: invalid (polarity,pm_unphysical) | 50 |
| R4 | W:W-R4 | **yes** | 0.886 | 0.776 | 0.963 | True | t_hot: gain_db +0.033 | 2336 |
| R4 | F2:two_stage_rz:1164 | **yes** | 0.907 | 0.642 | 0.969 | True | t_hot: gain_db +0.002 | 660 |
| R4 | F2:two_stage_rz:1443 | **yes** | 0.835 | 0.727 | 0.948 | True | t_hot: gain_db +0.018 | 664 |
| R4 | F2:two_stage_rz:407 | **yes** | 0.893 | 0.761 | 0.957 | True | t_hot: gain_db +0.005 | 782 |

# Cross-spec feasibility benchmark

12 candidate topologies sized against each spec at **seeds=[1, 2], ZOAF budget=[8, 8, 2]** (curated on the candidate's own band, all-free multi-seed elsewhere).

**tier-1** = S11/S21/Idd (the gating every historical claim in this repo was made under). **tier-2** = tier-1 **and** the golden-validated series-Rs NF, measured at the *same* tier-1-sized point (the `nf_contrast.py` re-judge-unchanged protocol). A tier-2 miss therefore says *this sizing* does not meet NF, not that no sizing could — NF is not in the objective here. `K_min` is the worst in-band Rollett K, advisory only: **K < 1 flags a potentially unstable sizing.**

> **What changed vs the previous table (Session 4, Track C).** The old one was a *lean-budget* artefact (`seeds=1, budget=5,5,1`) and said so: wifi24 read 4/6 there against 6/6 at full budget. This run is at full budget. Three further corrections: (1) the candidate set is now taken from the **feasible record** (`--all-feasible`), preferring the **in-box** rows after the `size.polish` box-clamp fix, so it includes the *generated* dhruva-l1 feasible `seq0192` and the 4-band `rfbcs3` archetype that a wifi24-closeness ranking could never reach; (2) every cell also re-measures the pipeline's **stored best point** for that (topology, spec) and keeps the better of that and a fresh search — without it the table reports worse than the program already owns, because the stored feasibles were earned with multi-seed heavy sizing plus polish; (3) the **NF column is real** (series-Rs). The old table's NF was the retired port-referred number and printed *negative* noise figures. Candidates are deduped on `wl_hash`, not on the token list — the same circuit re-emitted by a different Eulerian walk had been entering twice — and a `name@hash` suffix disambiguates two different topologies that share a `seqNNNN.txt` file name.

## Per-spec yield

| spec | tier-1 | tier-2 | binding when infeasible |
|---|---|---|---|
| wifi24 | **10/12** | **1/12** | `s21` ×1, `s11` ×1 |
| gps-l1 | **2/12** | **0/12** | `s21` ×5, `s11` ×4, `idd` ×1 |
| wideband-sdr | **0/12** | **0/12** | `s11` ×6, `s21` ×4, `s21_ripple` ×2 |
| dhruva-l5 | **1/12** | **0/12** | `s11_max` ×11 |
| dhruva-l2 | **1/12** | **0/12** | `s11_max` ×10, `s21` ×1 |
| dhruva-l1 | **2/12** | **0/12** | `s11_max` ×10 |
| dhruva-s | **1/12** | **0/12** | `s11_max` ×11 |

## Matrix (T2 = tier-2 feasible, T1 = tier-1 only, else binding constraint)

| candidate | dev | wifi24 | gps-l1 | wideband-sdr | dhruva-l5 | dhruva-l2 | dhruva-l1 | dhruva-s |
|---|---|---|---|---|---|---|---|---|
| seq0192.txt | 12 | s21 | s11 | s21_ripple | s11_max | s21 | **T1** | s11_max |
| rfbcs3_tank_cc21_bf0 | 14 | s11 | s11 | s21 | **T1** | **T1** | **T1** | **T1** |
| seq0089.txt | 10 | **T1** | **T1** | s11 | s11_max | s11_max | s11_max | s11_max |
| seq0215.txt | 12 | **T1** | **T1** | s21 | s11_max | s11_max | s11_max | s11_max |
| seq0220.txt | 9 | **T2** | s21 | s11 | s11_max | s11_max | s11_max | s11_max |
| seq0240.txt | 8 | **T1** | s21 | s11 | s11_max | s11_max | s11_max | s11_max |
| seq0086.txt | 10 | **T1** | s11 | s11 | s11_max | s11_max | s11_max | s11_max |
| seq0009.txt | 10 | **T1** | s21 | s11 | s11_max | s11_max | s11_max | s11_max |
| seq0046.txt | 12 | **T1** | s11 | s21 | s11_max | s11_max | s11_max | s11_max |
| seq0079.txt | 10 | **T1** | s21 | s11 | s11_max | s11_max | s11_max | s11_max |
| seq0220.txt@ec5931 | 11 | **T1** | s21 | s21 | s11_max | s11_max | s11_max | s11_max |
| seq0008.txt | 9 | **T1** | idd | s21_ripple | s11_max | s11_max | s11_max | s11_max |

## Detail (best sized metrics per cell)

| candidate | spec | tier-1 | tier-2 | S11@f0 | S11max | S21 | Idd | NF | K_min | binding | how |
|---|---|---|---|---|---|---|---|---|---|---|---|
| seq0192.txt | wifi24 | no | no | -8.4 | -8.4 | 5.2 | 3.68 | 14.34 | 812.579 | s21 | all-free |
| seq0192.txt | gps-l1 | no | no | -1.5 | -1.5 | 18.5 | 4.39 | 11.47 | 271.497 | s11 | all-free |
| seq0192.txt | wideband-sdr | no | no | -1.2 | -0.6 | 4.5 | 16.23 | 20.24 | 437.427 | s21_ripple | all-free |
| seq0192.txt | dhruva-l5 | no | no | -6.1 | -5.9 | 22.1 | 12.33 | 7.94 | 50.968 | s11_max | all-free |
| seq0192.txt | dhruva-l2 | no | no | -14.9 | -11.8 | 18.5 | 13.35 | 13.59 | 88.619 | s21 | all-free |
| seq0192.txt | dhruva-l1 | yes | no | -12.7 | -11.5 | 29.2 | 11.09 | 9.63 | 105.646 | - | stored |
| seq0192.txt | dhruva-s | no | no | -7.8 | -6.7 | 28.6 | 12.69 | 8.0 | 34.35 | s11_max | all-free |
| rfbcs3_tank_cc21_bf0 | wifi24 | no | no | -4.1 | -4.1 | 8.9 | 2.89 | 9.31 | 11738.63 | s11 | all-free |
| rfbcs3_tank_cc21_bf0 | gps-l1 | no | no | -5.9 | -5.9 | 12.8 | 2.21 | 9.21 | 22748.94 | s11 | all-free |
| rfbcs3_tank_cc21_bf0 | wideband-sdr | no | no | -0.1 | -0.0 | -20.5 | 2.48 | 24.96 | 48.011 | s21 | all-free |
| rfbcs3_tank_cc21_bf0 | dhruva-l5 | yes | no | -10.9 | -10.4 | 29.2 | 8.54 | 9.26 | 525.546 | - | all-free |
| rfbcs3_tank_cc21_bf0 | dhruva-l2 | yes | no | -14.3 | -12.7 | 23.2 | 12.39 | 11.12 | 10.149 | - | stored |
| rfbcs3_tank_cc21_bf0 | dhruva-l1 | yes | no | -15.3 | -11.2 | 37.8 | 12.93 | 9.95 | 28.412 | - | stored |
| rfbcs3_tank_cc21_bf0 | dhruva-s | yes | no | -11.1 | -10.3 | 34.6 | 8.7 | 8.88 | 21.317 | - | stored |
| seq0089.txt | wifi24 | yes | no | -13.0 | -11.9 | 12.2 | 2.43 | 3.78 | 27.084 | - | all-free |
| seq0089.txt | gps-l1 | yes | no | -10.9 | -10.5 | 15.1 | 1.1 | 4.41 | 31.725 | - | curated |
| seq0089.txt | wideband-sdr | no | no | -0.5 | -0.0 | 11.9 | 2.28 | 6.21 | 10.908 | s11 | all-free |
| seq0089.txt | dhruva-l5 | no | no | -3.3 | -1.8 | 15.1 | 2.69 | 5.32 | 27.054 | s11_max | all-free |
| seq0089.txt | dhruva-l2 | no | no | -4.9 | -1.6 | 15.3 | 2.72 | 4.88 | 27.842 | s11_max | all-free |
| seq0089.txt | dhruva-l1 | no | no | -5.0 | -1.8 | 14.1 | 3.32 | 5.34 | 18.769 | s11_max | all-free |
| seq0089.txt | dhruva-s | no | no | -6.8 | -0.2 | 18.6 | 3.13 | 2.52 | 14.014 | s11_max | all-free |
| seq0215.txt | wifi24 | yes | no | -12.7 | -11.8 | 21.4 | 4.2 | 4.17 | 13.95 | - | all-free |
| seq0215.txt | gps-l1 | yes | no | -14.4 | -13.6 | 15.4 | 2.94 | 4.43 | 276.288 | - | stored |
| seq0215.txt | wideband-sdr | no | no | -0.1 | -0.1 | -12.4 | 6.04 | 18.92 | 18.6 | s21 | all-free |
| seq0215.txt | dhruva-l5 | no | no | -3.3 | -2.3 | 22.6 | 11.63 | 7.52 | 16.474 | s11_max | all-free |
| seq0215.txt | dhruva-l2 | no | no | -3.3 | -2.2 | 22.9 | 10.18 | 7.12 | 7.39 | s11_max | all-free |
| seq0215.txt | dhruva-l1 | no | no | -7.3 | -3.2 | 31.2 | 8.49 | 5.63 | 6.268 | s11_max | all-free |
| seq0215.txt | dhruva-s | no | no | -5.4 | -1.0 | 35.1 | 6.28 | 4.66 | **0.949** ⚠ | s11_max | all-free |
| seq0220.txt | wifi24 | yes | yes | -14.5 | -13.2 | 13.0 | 2.73 | 2.34 | 4.386 | - | curated |
| seq0220.txt | gps-l1 | no | no | -12.4 | -12.1 | 5.3 | 3.01 | 6.68 | 16.179 | s21 | all-free |
| seq0220.txt | wideband-sdr | no | no | -0.8 | -0.1 | 8.4 | 7.78 | 9.68 | 4.368 | s11 | all-free |
| seq0220.txt | dhruva-l5 | no | no | -3.3 | -2.6 | 17.1 | 12.01 | 7.44 | 1.657 | s11_max | all-free |
| seq0220.txt | dhruva-l2 | no | no | -3.8 | -2.6 | 16.8 | 12.19 | 7.29 | 1.711 | s11_max | all-free |
| seq0220.txt | dhruva-l1 | no | no | -8.1 | -2.4 | 15.9 | 8.33 | 5.34 | 1.138 | s11_max | all-free |
| seq0220.txt | dhruva-s | no | no | -8.1 | -0.6 | 15.1 | 6.83 | 4.79 | 1.864 | s11_max | all-free |
| seq0240.txt | wifi24 | yes | no | -14.9 | -12.4 | 14.5 | 2.17 | 2.99 | 22.133 | - | curated |
| seq0240.txt | gps-l1 | no | no | -7.7 | -7.7 | 9.6 | 3.48 | 6.63 | 73.866 | s21 | all-free |
| seq0240.txt | wideband-sdr | no | no | -0.3 | -0.0 | 12.0 | 4.32 | 6.31 | 7.956 | s11 | all-free |
| seq0240.txt | dhruva-l5 | no | no | -0.4 | -0.3 | 13.4 | 2.7 | 6.54 | 9.019 | s11_max | all-free |
| seq0240.txt | dhruva-l2 | no | no | -0.2 | -0.2 | 13.8 | 3.13 | 6.25 | 6.42 | s11_max | all-free |
| seq0240.txt | dhruva-l1 | no | no | -0.4 | -0.2 | 12.8 | 2.23 | 6.4 | 8.041 | s11_max | all-free |
| seq0240.txt | dhruva-s | no | no | -1.2 | -0.2 | 12.8 | 2.22 | 5.29 | 10.333 | s11_max | all-free |
| seq0086.txt | wifi24 | yes | no | -10.1 | -9.5 | 16.1 | 2.23 | 2.6 | 13.297 | - | curated |
| seq0086.txt | gps-l1 | no | no | -2.1 | -2.0 | 12.7 | 1.97 | 5.79 | 26.438 | s11 | all-free |
| seq0086.txt | wideband-sdr | no | no | -0.3 | -0.0 | 6.3 | 2.86 | 8.95 | 26.661 | s11 | all-free |
| seq0086.txt | dhruva-l5 | no | no | -1.5 | -1.2 | 15.1 | 2.75 | 5.33 | 29.723 | s11_max | all-free |
| seq0086.txt | dhruva-l2 | no | no | -2.3 | -1.7 | 14.6 | 1.93 | 6.27 | 13.801 | s11_max | all-free |
| seq0086.txt | dhruva-l1 | no | no | -4.1 | -1.0 | 16.9 | 2.0 | 4.46 | 12.7 | s11_max | all-free |
| seq0086.txt | dhruva-s | no | no | -16.6 | -0.2 | 19.2 | 3.4 | 2.33 | 14.594 | s11_max | all-free |
| seq0009.txt | wifi24 | yes | no | -12.5 | -11.1 | 15.1 | 4.42 | 2.82 | **0.242** ⚠ | - | curated |
| seq0009.txt | gps-l1 | no | no | -11.0 | -10.7 | 5.3 | 2.75 | 6.5 | 28.675 | s21 | all-free |
| seq0009.txt | wideband-sdr | no | no | -0.4 | 0.0 | 6.4 | 6.68 | 6.57 | **0.231** ⚠ | s11 | all-free |
| seq0009.txt | dhruva-l5 | no | no | -3.1 | -2.6 | 15.1 | 8.22 | 6.03 | 1.019 | s11_max | all-free |
| seq0009.txt | dhruva-l2 | no | no | -3.6 | -2.6 | 15.1 | 7.85 | 5.56 | 1.051 | s11_max | all-free |
| seq0009.txt | dhruva-l1 | no | no | -10.0 | -1.6 | 18.1 | 8.09 | 4.3 | **0.61** ⚠ | s11_max | all-free |
| seq0009.txt | dhruva-s | no | no | -12.0 | -0.8 | 14.6 | 5.93 | 3.09 | 2.181 | s11_max | all-free |
| seq0046.txt | wifi24 | yes | no | -12.8 | -7.5 | 15.0 | 3.73 | 6.94 | 4.95 | - | stored |
| seq0046.txt | gps-l1 | no | no | -4.9 | -4.7 | 14.3 | 2.26 | 6.89 | 133.86 | s11 | all-free |
| seq0046.txt | wideband-sdr | no | no | -1.3 | -0.8 | -25.2 | 10.24 | 30.27 | 94665.6 | s21 | all-free |
| seq0046.txt | dhruva-l5 | no | no | -1.3 | -0.9 | 24.5 | 10.2 | 8.1 | 20.502 | s11_max | all-free |
| seq0046.txt | dhruva-l2 | no | no | -1.3 | -0.8 | 20.9 | 11.78 | 9.81 | 33.947 | s11_max | all-free |
| seq0046.txt | dhruva-l1 | no | no | 0.2 | 0.3 | 24.6 | 11.48 | 7.6 | **-2.04** ⚠ | s11_max | all-free |
| seq0046.txt | dhruva-s | no | no | -1.4 | -0.7 | 30.0 | 7.84 | 6.93 | 2.049 | s11_max | all-free |
| seq0079.txt | wifi24 | yes | no | -10.2 | -9.3 | 14.2 | 3.33 | 2.53 | 1.093 | - | curated |
| seq0079.txt | gps-l1 | no | no | -11.4 | -11.1 | 7.3 | 2.03 | 5.88 | 2.994 | s21 | all-free |
| seq0079.txt | wideband-sdr | no | no | -0.6 | -0.1 | 7.7 | 4.25 | 6.89 | **0.241** ⚠ | s11 | all-free |
| seq0079.txt | dhruva-l5 | no | no | -2.4 | -2.1 | 9.2 | 7.57 | 8.14 | 2.027 | s11_max | all-free |
| seq0079.txt | dhruva-l2 | no | no | -2.5 | -2.0 | 9.5 | 7.52 | 7.84 | 1.908 | s11_max | all-free |
| seq0079.txt | dhruva-l1 | no | no | -8.5 | -1.8 | 12.2 | 7.76 | 4.86 | 1.601 | s11_max | all-free |
| seq0079.txt | dhruva-s | no | no | -5.3 | -0.2 | 13.1 | 5.76 | 3.59 | **0.591** ⚠ | s11_max | all-free |
| seq0220.txt@ec5931 | wifi24 | yes | no | -10.5 | -9.1 | 16.0 | 2.34 | 2.61 | 25.401 | - | curated |
| seq0220.txt@ec5931 | gps-l1 | no | no | -10.0 | -9.4 | 12.7 | 2.83 | 5.32 | 67.402 | s21 | all-free |
| seq0220.txt@ec5931 | wideband-sdr | no | no | -1.1 | -0.1 | 0.1 | 7.5 | 11.76 | 101.696 | s21 | all-free |
| seq0220.txt@ec5931 | dhruva-l5 | no | no | -3.5 | -2.7 | 12.8 | 2.22 | 6.01 | 37.437 | s11_max | all-free |
| seq0220.txt@ec5931 | dhruva-l2 | no | no | -2.0 | -1.6 | 13.5 | 4.78 | 6.3 | 49.418 | s11_max | all-free |
| seq0220.txt@ec5931 | dhruva-l1 | no | no | -3.7 | -1.2 | 14.8 | 3.17 | 5.2 | 17.638 | s11_max | all-free |
| seq0220.txt@ec5931 | dhruva-s | no | no | -4.2 | -0.1 | 16.2 | 2.07 | 3.1 | 27.435 | s11_max | all-free |
| seq0008.txt | wifi24 | yes | no | -10.4 | -9.5 | 15.0 | 4.07 | 5.07 | 7.187 | - | curated |
| seq0008.txt | gps-l1 | no | no | -12.9 | -12.0 | 18.3 | 4.56 | 2.91 | 2.098 | idd | all-free |
| seq0008.txt | wideband-sdr | no | no | -1.2 | -0.1 | 13.1 | 6.44 | 7.94 | 1.93 | s21_ripple | all-free |
| seq0008.txt | dhruva-l5 | no | no | -2.0 | -1.6 | 16.7 | 9.54 | 6.8 | **0.522** ⚠ | s11_max | all-free |
| seq0008.txt | dhruva-l2 | no | no | -5.1 | -2.6 | 20.0 | 6.23 | 5.54 | 3.123 | s11_max | all-free |
| seq0008.txt | dhruva-l1 | no | no | -2.1 | -1.0 | 16.5 | 7.44 | 7.93 | 1.786 | s11_max | all-free |
| seq0008.txt | dhruva-s | no | no | -18.8 | -3.2 | 10.4 | 5.36 | 12.17 | 1.774 | s11_max | all-free |

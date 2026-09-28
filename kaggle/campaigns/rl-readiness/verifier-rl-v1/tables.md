## (b) difficulty under rl-v1 (rl-v1-form specs, profile rl-v1, seeds 1,2,3 x 2500)

F = final feasible (spec incl. in-band mu, AND wide mu >= 1). gate = stability-gate (0.1-20 GHz, post-hoc), inloop = S-1 / R4-nb (0.1-20 GHz in-loop, library metrics).

Runs F / runs; (cells) = distinct cells with >= 1 F run.

| group | cells | runs | gate F (cells) | inloop F (cells) | **rl-v1 F (cells)** | cells lost vs inloop | gained |
|---|---|---|---|---|---|---|---|
| nb template | 8 | 24 | 20 (8) | 24 (8) | **24 (8)** | - | - |
| nb a1 | 8 | 24 | 12 (6) | 22 (8) | **22 (8)** | - | - |
| nb ANY candidate | 8 | 48 | 32 (8) | 46 (8) | **46 (8)** | - | - |
| wb template | 8 | 24 | 0 (0) | 8 (4) | **5 (2)** | wb-s11n8-g10-b0530, wb-s11n9-g10-b0530 | - |
| wb E-c (S-1 picks) | 4 | 24 | 0 (0) | 14 (4) | **2 (2)** | wb-s11n10-g10-b0824, wb-s11n11-g10-b0824 | - |
| wb ANY candidate | 8 | 48 | 0 (0) | 22 (4) | **7 (4)** | - | - |

| cell | cand | gate | inloop | rl-v1 | rl-v1 failing-run causes | baseline winners pass rl-v1 as-is | their failing checks | inert (per seed) |
|---|---|---|---|---|---|---|---|---|
| nb-f15-g12 | a1 | xxx | FxF | **FFF** | - | 0/2 | spec:s11_max_dbx2 | [0, 0, 0] |
| nb-f15-g12 | template | xFF | FFF | **FFF** | - | 0/3 | spec:s11_max_dbx3 | [1, 1, 0] |
| nb-f15-g14 | a1 | FFF | FFF | **FFF** | - | 0/3 | spec:s11_max_dbx3 | [0, 0, 0] |
| nb-f15-g14 | template | FFF | FFF | **FFF** | - | 0/3 | spec:s11_max_dbx3 | [0, 0, 0] |
| nb-f15-g16 | a1 | FFF | FFF | **FxF** | band S11 (W6 if nb)x1, nf@f0x1 | 0/3 | spec:s11_max_dbx3 | [0, None, 0] |
| nb-f15-g16 | template | FFF | FFF | **FFF** | - | 0/3 | spec:s11_max_dbx3 | [1, 0, 0] |
| nb-f15-g18 | a1 | FxF | FxF | **FxF** | band S11 (W6 if nb)x1, nf@f0x1, s21x1 | 0/2 | spec:s11_max_dbx2 | [0, None, 0] |
| nb-f15-g18 | template | FFF | FFF | **FFF** | - | 0/3 | spec:s11_max_dbx3 | [1, 0, 0] |
| nb-f24-g12 | a1 | xFx | FFF | **FFF** | - | 1/3 | spec:s11_max_dbx2 | [0, 0, 0] |
| nb-f24-g12 | template | FxF | FFF | **FFF** | - | 0/3 | spec:s11_max_dbx3 | [1, 1, 1] |
| nb-f24-g14 | a1 | xxx | FFF | **FFF** | - | 0/3 | spec:s11_max_dbx3 | [0, 0, 0] |
| nb-f24-g14 | template | xFx | FFF | **FFF** | - | 0/3 | spec:s11_max_dbx3 | [1, 0, 1] |
| nb-f24-g16 | a1 | xFx | FFF | **FFF** | - | 0/3 | spec:s11_max_dbx3, wide_mux1 | [0, 0, 0] |
| nb-f24-g16 | template | FFF | FFF | **FFF** | - | 0/3 | spec:s11_max_dbx3 | [1, 0, 1] |
| nb-f24-g18 | a1 | FxF | FFF | **FFF** | - | 0/3 | spec:s11_max_dbx3 | [0, 0, 0] |
| nb-f24-g18 | template | FFF | FFF | **FFF** | - | 0/3 | spec:s11_max_dbx3 | [1, 1, 1] |
| wb-s11n10-g10-b0530 | template | xxx | xxx | **xxx** | band S11 (W6 if nb)x3, s21x1 | 0/0 | - | [None, None, None] |
| wb-s11n10-g10-b0824 | ec:72945e70a2a1:051 | xxx | xxx | **xxx** | W5 band NFx3, band S11 (W6 if nb)x3 | 0/0 | - | [None, None, None] |
| wb-s11n10-g10-b0824 | ec:72945e70a2a1:131 | xxx | FFx | **xxx** | topo:max_inductorsx3 | 0/2 | spec:nf_max_dbx2, topo:max_inductorsx2 | [None, None, None] |
| wb-s11n10-g10-b0824 | template | xxx | FFF | **FFx** | wide mu 0.01-50GHzx1 | 2/3 | spec:nf_max_dbx1 | [0, 1, None] |
| wb-s11n10-g12-b0824 | template | xxx | xxx | **xxx** | s21x2, wide mu 0.01-50GHzx1 | 0/0 | - | [None, None, None] |
| wb-s11n11-g10-b0824 | ec:72945e70a2a1:053 | xxx | FFF | **xxx** | topo:max_inductorsx3 | 0/3 | spec:nf_max_dbx3, topo:max_inductorsx3 | [None, None, None] |
| wb-s11n11-g10-b0824 | ec:72945e70a2a1:131 | xxx | xFx | **xxx** | topo:max_inductorsx3 | 0/1 | spec:nf_max_dbx1, topo:max_inductorsx1 | [None, None, None] |
| wb-s11n11-g10-b0824 | template | xxx | FxF | **FFF** | - | 1/2 | spec:nf_max_dbx1 | [0, 0, 0] |
| wb-s11n11-g12-b0824 | template | xxx | xxx | **xxx** | s21x3 | 0/0 | - | [None, None, None] |
| wb-s11n8-g10-b0530 | ec:72945e70a2a1:147 | xxx | FFF | **xxF** | W5 band NFx1, wide mu 0.01-50GHzx1 | 0/3 | spec:nf_max_dbx3, wide_mux1 | [None, None, 0] |
| wb-s11n8-g10-b0530 | ec:72945e70a2a1:157 | xxx | xxx | **xxx** | W5 band NFx1, band S11 (W6 if nb)x2, in-band mux1, s21x1, wide mu 0.01-50GHzx1 | 0/0 | - | [None, None, None] |
| wb-s11n8-g10-b0530 | template | xxx | xFF | **xxx** | W5 band NFx1, wide mu 0.01-50GHzx2 | 0/2 | spec:nf_max_dbx2 | [None, None, None] |
| wb-s11n8-g12-b0530 | template | xxx | xxx | **xxx** | s21x3 | 0/0 | - | [None, None, None] |
| wb-s11n9-g10-b0530 | ec:72945e70a2a1:126 | xxx | FFF | **xxF** | W5 band NFx1, wide mu 0.01-50GHzx1 | 0/3 | spec:nf_max_dbx3, wide_mux1 | [None, None, 1] |
| wb-s11n9-g10-b0530 | ec:72945e70a2a1:156 | xxx | FxF | **xxx** | W5 band NFx2, band S11 (W6 if nb)x2, wide mu 0.01-50GHzx1 | 1/2 | spec:nf_max_dbx1, wide_mux1 | [None, None, None] |
| wb-s11n9-g10-b0530 | template | xxx | xFx | **xxx** | W5 band NFx1, wide mu 0.01-50GHzx2 | 0/1 | spec:nf_max_dbx1 | [None, None, None] |

## (c) loophole re-check: R4 junk add-on mutants under rl-v1 (seed 1)

| mutant | cell | R4 inloop feasible | rl-v1 feasible | caught by / cause | n_evals | inert devices (W2) | junk device(s) flagged inert |
|---|---|---|---|---|---|---|---|
| nb_bleeder | nb-f15-g16 | True | True | - | 2500 | ['pC4V', 'pR3V'] | ['pR3V'] (junk: ['pR3V']) |
| nb_bleeder | nb-f24-g12 | None | True | - | 2500 | ['pC4V', 'pR3V'] | ['pR3V'] (junk: ['pR3V']) |
| nb_cap_in | nb-f15-g16 | True | True | - | 2500 | ['pC4V', 'pC5V'] | ['pC5V'] (junk: ['pC5V']) |
| nb_cap_in | nb-f24-g12 | None | True | - | 2500 | ['pC4V', 'pC5V'] | ['pC5V'] (junk: ['pC5V']) |
| nb_dangling | nb-f15-g16 | True | False | struct:dangling_node | 0 | None | - (junk: []) |
| nb_dangling | nb-f24-g12 | None | False | struct:dangling_node | 0 | None | - (junk: []) |
| nb_dead_mos | nb-f15-g16 | True | False | struct:mos_d_eq_s,mos_g_eq_s | 0 | None | - (junk: []) |
| nb_dead_mos | nb-f24-g12 | None | False | struct:mos_d_eq_s,mos_g_eq_s | 0 | None | - (junk: []) |
| nb_dup_out | nb-f15-g16 | True | True | - | 2500 | ['pC5V'] | ['pC5V'] (junk: ['pC5V', 'pR3V']) |
| nb_dup_out | nb-f24-g12 | None | True | - | 2500 | ['pC4V', 'pC5V', 'pR3V'] | ['pC5V', 'pR3V'] (junk: ['pC5V', 'pR3V']) |
| nb_rin_out | nb-f15-g16 | False | False | nf@f0, band S11 (W6 if nb), s21 | 2500 | None | - (junk: ['pR3V']) |
| nb_rin_out | nb-f24-g12 | None | False | nf@f0, band S11 (W6 if nb), s21, in-band mu | 2500 | None | - (junk: ['pR3V']) |
| nb_tank_out | nb-f15-g16 | True | True | - | 2500 | ['pC5V'] | ['pC5V'] (junk: ['pC5V', 'pL4V']) |
| nb_tank_out | nb-f24-g12 | None | True | - | 2500 | ['pC5V'] | ['pC5V'] (junk: ['pC5V', 'pL4V']) |
| nb_vbnet | nb-f15-g16 | False | False | struct:mos_no_dc_path | 0 | None | - (junk: []) |
| nb_vbnet | nb-f24-g12 | None | False | struct:mos_no_dc_path | 0 | None | - (junk: []) |
| wb_bleeder | wb-s11n10-g10-b0824 | True | True | - | 2500 | ['pR6V'] | ['pR6V'] (junk: ['pR6V']) |
| wb_bleeder | wb-s11n8-g10-b0530 | None | False | wide mu 0.01-50GHz | 2500 | None | - (junk: ['pR6V']) |
| wb_cap_in | wb-s11n10-g10-b0824 | True | True | - | 2500 | ['pC3V', 'pC5V', 'pL2V'] | ['pC5V'] (junk: ['pC5V']) |
| wb_cap_in | wb-s11n8-g10-b0530 | None | False | W5 band NF | 2500 | None | - (junk: ['pC5V']) |
| wb_dangling | wb-s11n10-g10-b0824 | False | False | topo:device_budget | 0 | None | - (junk: []) |
| wb_dangling | wb-s11n8-g10-b0530 | None | False | topo:device_budget | 0 | None | - (junk: []) |
| wb_dead_mos | wb-s11n10-g10-b0824 | True | False | struct:mos_d_eq_s,mos_g_eq_s | 0 | None | - (junk: []) |
| wb_dead_mos | wb-s11n8-g10-b0530 | None | False | struct:mos_d_eq_s,mos_g_eq_s | 0 | None | - (junk: []) |
| wb_dup_out | wb-s11n10-g10-b0824 | True | False | topo:device_budget | 0 | None | - (junk: []) |
| wb_dup_out | wb-s11n8-g10-b0530 | None | False | topo:device_budget | 0 | None | - (junk: []) |
| wb_rin_out | wb-s11n10-g10-b0824 | True | False | wide mu 0.01-50GHz | 2500 | None | - (junk: ['pR6V']) |
| wb_rin_out | wb-s11n8-g10-b0530 | None | False | wide mu 0.01-50GHz | 2500 | None | - (junk: ['pR6V']) |
| wb_tank_out | wb-s11n10-g10-b0824 | True | False | topo:device_budget, max_inductors | 0 | None | - (junk: []) |
| wb_tank_out | wb-s11n8-g10-b0530 | None | False | topo:device_budget, max_inductors | 0 | None | - (junk: []) |
| wb_vbnet | wb-s11n10-g10-b0824 | True | False | topo:device_budget | 0 | None | - (junk: []) |
| wb_vbnet | wb-s11n8-g10-b0530 | None | False | topo:device_budget | 0 | None | - (junk: []) |

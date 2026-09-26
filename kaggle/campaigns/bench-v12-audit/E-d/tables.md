E-d summary (era a0e4edcc6; 978 sizing rows). Synthesis cells = 6, retrieval = 10, EDGE = v12-wb-s11n8-g12-b0530.

| model | cond | compl. | empty/no-edit | edits | valid | sizable | feasible (any seed) | feas >=2/3 | cells solved (any) | syn /6 | ret /10 | >=2/3 seeds | EDGE | s1/s2: both, s1-only, s2-only | in-kernel solved | GPU min/compl (mean, med) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3-14b-q4km | FS | 32 | 0/0 | 96 | 96 (100%) | 95 | 11 (11.5% of all) | 8 | 6/16 | 4 | 2 | 5 | yes | 3, 1, 2 | 3 | 1.77, 1.78 |
| qwen3-14b-q4km | ZS | 32 | 0/0 | 96 | 92 (96%) | 91 | 1 (1.0% of all) | 0 | 1/16 | 1 | 0 | 0 | no | 0, 1, 0 | 1 | 2.34, 2.34 |
| qwen3-32b-q4ks | FS | 32 | 0/0 | 96 | 79 (82%) | 79 | 7 (7.3% of all) | 7 | 5/16 | 3 | 2 | 5 | no | 1, 2, 2 | 3 | 4.32, 3.20 |
| qwen3-32b-q4ks | ZS | 32 | 0/0 | 96 | 82 (85%) | 81 | 5 (5.2% of all) | 3 | 3/16 | 2 | 1 | 2 | no | 1, 0, 2 | 0 | 4.90, 4.80 |

### Topology classes emitted (valid edits)

| model | cond | wb valid edits | wb narrow shunt-fb | wb wide shunt-fb | wb wide(VIN-side) | wb cells w/ wide | wide-fb edits feasible | nb valid edits | nb cascode | nb tank | nb narrow-fb |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3-14b-q4km | FS | 48 | 6 | 14 | 21 | 8/8 | 7 | 48 | 1 | 15 | 3 |
| qwen3-14b-q4km | ZS | 45 | 2 | 0 | 0 | 0/8 | 0 | 47 | 1 | 29 | 0 |
| qwen3-32b-q4ks | FS | 40 | 4 | 14 | 14 | 8/8 | 7 | 39 | 1 | 28 | 4 |
| qwen3-32b-q4ks | ZS | 36 | 0 | 0 | 0 | 0/8 | 0 | 46 | 0 | 36 | 1 |

### Cells solved (local, any edit/sample/seed)

| cell | label | 14b FS | 14b ZS | 32b FS | 32b ZS |
|---|---|---|---|---|---|
| v12-nb-f15-g12 | RET ST | n (-2.876) | n (-0.297) | n (-0.097) | n (-0.298) |
| v12-nb-f15-g14 | RET ST | n (-4.742) | n (-0.660) | n (-0.396) | n (-0.183) |
| v12-nb-f15-g16 | RET ST | n (-1.980) | n (-0.598) | n (-4.125) | n (-0.392) |
| v12-nb-f15-g18 | RET ST | n (-0.538) | n (-0.533) | n (-0.534) | n (-0.421) |
| v12-nb-f24-g12 | RET ST | n (-0.215) | n (-0.933) | n (-0.216) | n (-0.105) |
| v12-nb-f24-g14 | RET ST | n (-0.327) | n (-0.324) | n (-0.338) | n (-0.230) |
| v12-nb-f24-g16 | RET ST | n (-0.412) | n (-0.410) | n (-2.018) | n (-0.103) |
| v12-nb-f24-g18 | RET ST | n (-1.378) | n (-0.485) | n (-0.485) | n (-0.404) |
| v12-wb-s11n10-g10-b0530 | SYN ST | n (-0.266) | n (-7.067) | n (-0.266) | **Y** (+0.000) |
| v12-wb-s11n10-g10-b0824 | RET ST | **Y** (+0.003) | n (-0.034) | **Y** (+0.001) | **Y** (+0.003) |
| v12-wb-s11n10-g12-b0824 | RET ST | **Y** (+0.005) | n (-0.051) | **Y** (+0.006) | n (-0.064) |
| v12-wb-s11n11-g10-b0824 | SYN ST | **Y** (+0.006) | n (-0.155) | **Y** (+0.004) | n |
| v12-wb-s11n11-g12-b0824 | SYN ST | **Y** (+0.001) | **Y** (+0.000) | **Y** (+0.001) | n (-0.141) |
| v12-wb-s11n8-g10-b0530 | SYN ST | **Y** (+0.001) | n (-0.207) | **Y** (+0.004) | n (-0.216) |
| v12-wb-s11n8-g12-b0530 | SYN EDGE ST | **Y** (+0.009) | n (-1.182) | n (-0.205) | n (-0.237) |
| v12-wb-s11n9-g10-b0530 | SYN ST | n (-0.185) | n (-0.305) | n (-0.185) | **Y** (+0.001) |

### ZS vs FS (pre-reg: no claim unless >= 3 cells differ)

- qwen3-14b-q4km: ZS-only [], FS-only ['v12-wb-s11n10-g10-b0824', 'v12-wb-s11n10-g12-b0824', 'v12-wb-s11n11-g10-b0824', 'v12-wb-s11n8-g10-b0530', 'v12-wb-s11n8-g12-b0530'] -> 5 differ -> **difference claimable (>=3 cells differ)**
- qwen3-32b-q4ks: ZS-only ['v12-wb-s11n10-g10-b0530', 'v12-wb-s11n9-g10-b0530'], FS-only ['v12-wb-s11n10-g12-b0824', 'v12-wb-s11n11-g10-b0824', 'v12-wb-s11n11-g12-b0824', 'v12-wb-s11n8-g10-b0530'] -> 6 differ -> **difference claimable (>=3 cells differ)**

### Invalid-edit reasons

- qwen3-14b-q4km FS: {}
- qwen3-14b-q4km ZS: {'duplicate device name': 1, 'inline-comment/extra tokens': 3}
- qwen3-32b-q4ks FS: {'duplicate device name': 3, 'inline-comment/extra tokens': 14}
- qwen3-32b-q4ks ZS: {'inline-comment/extra tokens': 11, 'duplicate device name': 3}

### Cost vs E-c brute-force single-edit search (SPICE-min = seed-1 2500-eval screens)

E-c: SEARCH-TRIVIAL / confirmed / SPICE-min to first screen-feasible (fixed order, E[random]). LLM: per completion that reaches a seed-1-feasible edit, GPU-min (llama-server total time) + SPICE-min of its edits sized in index order up to the first seed-1-feasible one.

| cell | label | E-c trivial | E-c confirmed | E-c SPICE-min fixed / E[random] | LLM completions reaching seed-1 feasible: model cond sample (GPU-min + SPICE-min) |
|---|---|---|---|---|---|
| v12-nb-f15-g12 | RET | True | 1 | 22.0 / 31.1 | - |
| v12-nb-f15-g14 | RET | True | 1 | 21.8 / 30.5 | - |
| v12-nb-f15-g16 | RET | True | 1 | 22.1 / 31.3 | - |
| v12-nb-f15-g18 | RET | True | 1 | 21.8 / 30.5 | - |
| v12-nb-f24-g12 | RET | True | 3 | 21.8 / 15.7 | - |
| v12-nb-f24-g14 | RET | True | 3 | 22.0 / 15.5 | - |
| v12-nb-f24-g16 | RET | True | 1 | 22.6 / 32.4 | - |
| v12-nb-f24-g18 | RET | True | 1 | 24.1 / 34.1 | - |
| v12-wb-s11n10-g10-b0530 | SYN | True | 8 | 56.2 / 26.0 | 32b ZS s2 (4.9+5.4) |
| v12-wb-s11n10-g10-b0824 | RET | True | 38 | 4.2 / 6.4 | 32b ZS s1 (2.4+1.8); 32b ZS s2 (3.2+1.8); 32b FS s1 (3.3+1.8); 32b FS s2 (2.3+1.8); 14b FS s1 (1.7+0.9); 14b FS s2 (1.2+1.8) |
| v12-wb-s11n10-g12-b0824 | RET | True | 32 | 4.2 / 7.8 | 32b FS s1 (3.3+5.4); 14b FS s2 (1.4+0.9) |
| v12-wb-s11n11-g10-b0824 | SYN | True | 32 | 4.4 / 7.4 | 32b FS s2 (2.9+1.8); 14b FS s1 (1.3+0.9); 14b FS s2 (1.3+0.9) |
| v12-wb-s11n11-g12-b0824 | SYN | True | 25 | 3.3 / 7.4 | 32b FS s2 (4.6+1.8); 14b ZS s1 (3.2+0.9); 14b FS s1 (1.9+1.8) |
| v12-wb-s11n8-g10-b0530 | SYN | True | 28 | 1.1 / 6.6 | 32b FS s1 (1.9+1.8); 14b FS s2 (1.5+0.9) |
| v12-wb-s11n8-g12-b0530 | SYN EDGE | True | 14 | 42.0 / 15.1 | 14b FS s1 (1.9+0.9); 14b FS s2 (2.0+0.9) |
| v12-wb-s11n9-g10-b0530 | SYN | True | 19 | 33.5 / 10.2 | 32b ZS s2 (3.1+1.8) |

### Sequential LLM cost vs E-c (seed-1 sizing calls; load-independent)

Per cell: sample 1 then sample 2, each = GPU-min + seed-1 sizing calls of its valid edits in order, stop at first seed-1-feasible. `N@sK` = solved (seed 1) after N calls within K completions; `x (N)` = unsolved after 2 completions (N calls spent). E-c calls to 1st (fixed / E[random]) are in E-c/README.md.

| cell | label | 14b FS | 14b ZS | 32b FS | 32b ZS |
|---|---|---|---|---|---|
| v12-nb-f15-g12 | RET | x (6) +3.0 GPU-min | x (6) +4.7 GPU-min | x (6) +16.7 GPU-min | x (6) +11.2 GPU-min |
| v12-nb-f15-g14 | RET | x (6) +5.0 GPU-min | x (6) +4.1 GPU-min | x (5) +10.2 GPU-min | x (6) +10.2 GPU-min |
| v12-nb-f15-g16 | RET | x (6) +3.6 GPU-min | x (6) +5.8 GPU-min | x (3) +17.5 GPU-min | x (6) +11.5 GPU-min |
| v12-nb-f15-g18 | RET | x (6) +3.6 GPU-min | x (6) +4.8 GPU-min | x (6) +13.7 GPU-min | x (6) +10.1 GPU-min |
| v12-nb-f24-g12 | RET | x (6) +4.2 GPU-min | x (6) +5.6 GPU-min | x (3) +4.5 GPU-min | x (6) +14.7 GPU-min |
| v12-nb-f24-g14 | RET | x (5) +4.5 GPU-min | x (6) +3.9 GPU-min | x (6) +13.5 GPU-min | x (6) +13.1 GPU-min |
| v12-nb-f24-g16 | RET | x (5) +4.4 GPU-min | x (6) +3.6 GPU-min | x (6) +12.1 GPU-min | x (5) +14.2 GPU-min |
| v12-nb-f24-g18 | RET | x (6) +2.8 GPU-min | x (5) +6.4 GPU-min | x (4) +7.1 GPU-min | x (5) +14.4 GPU-min |
| v12-wb-s11n10-g10-b0530 | SYN | x (5) +2.5 GPU-min | x (6) +3.9 GPU-min | x (5) +5.3 GPU-min | 6@s2 +9.3 GPU-min |
| v12-wb-s11n10-g10-b0824 | RET | 1@s1 +1.7 GPU-min | x (6) +5.3 GPU-min | 1@s1 +3.3 GPU-min | 1@s1 +2.4 GPU-min |
| v12-wb-s11n10-g12-b0824 | RET | 4@s2 +2.8 GPU-min | x (6) +3.7 GPU-min | 3@s1 +3.3 GPU-min | x (3) +4.2 GPU-min |
| v12-wb-s11n11-g10-b0824 | SYN | 1@s1 +1.3 GPU-min | x (6) +4.8 GPU-min | 4@s2 +6.0 GPU-min | x (0) +8.4 GPU-min |
| v12-wb-s11n11-g12-b0824 | SYN | 1@s1 +1.9 GPU-min | 1@s1 +3.2 GPU-min | 4@s2 +6.6 GPU-min | x (3) +7.8 GPU-min |
| v12-wb-s11n8-g10-b0530 | SYN | 4@s2 +3.1 GPU-min | x (3) +4.9 GPU-min | 1@s1 +1.9 GPU-min | x (6) +7.7 GPU-min |
| v12-wb-s11n8-g12-b0530 | SYN EDGE | 1@s1 +1.9 GPU-min | x (6) +2.9 GPU-min | x (3) +4.8 GPU-min | x (6) +8.6 GPU-min |
| v12-wb-s11n9-g10-b0530 | SYN | x (5) +3.9 GPU-min | x (3) +6.4 GPU-min | x (3) +4.3 GPU-min | 4@s2 +5.8 GPU-min |

- qwen3-14b-q4km FS: 32 completions, total GPU-min 57, seed-1 SPICE-min of all their edits (to first feasible or exhaustion) 61

- qwen3-14b-q4km ZS: 32 completions, total GPU-min 75, seed-1 SPICE-min of all their edits (to first feasible or exhaustion) 64

- qwen3-32b-q4ks FS: 32 completions, total GPU-min 138, seed-1 SPICE-min of all their edits (to first feasible or exhaustion) 103

- qwen3-32b-q4ks ZS: 32 completions, total GPU-min 157, seed-1 SPICE-min of all their edits (to first feasible or exhaustion) 111

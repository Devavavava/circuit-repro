E-d summary (era a0e4edcc6; 465 sizing rows). Synthesis cells = 6, retrieval = 10, EDGE = v12-wb-s11n8-g12-b0530.

| model | cond | compl. | empty/no-edit | edits | valid | sizable | feasible (any seed) | feas >=2/3 | cells solved (any) | syn /6 | ret /10 | >=2/3 seeds | EDGE | s1/s2: both, s1-only, s2-only | in-kernel solved | GPU min/compl (mean, med) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3-32b-q4ks | FS | 32 | 0/0 | 96 | 79 (82%) | 79 | 7 (7.3% of all) | 7 | 5/16 | 3 | 2 | 5 | no | 1, 2, 2 | 3 | 4.32, 3.20 |
| qwen3-32b-q4ks | ZS | 32 | 0/0 | 96 | 82 (85%) | 81 | 5 (5.2% of all) | 3 | 3/16 | 2 | 1 | 2 | no | 1, 0, 2 | 0 | 4.90, 4.80 |

### Topology classes emitted (valid edits)

| model | cond | wb valid edits | wb narrow shunt-fb | wb wide shunt-fb | wb wide(VIN-side) | wb cells w/ wide | wide-fb edits feasible | nb valid edits | nb cascode | nb tank | nb narrow-fb |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3-32b-q4ks | FS | 40 | 4 | 14 | 14 | 8/8 | 7 | 39 | 1 | 28 | 4 |
| qwen3-32b-q4ks | ZS | 36 | 0 | 0 | 0 | 0/8 | 0 | 46 | 0 | 36 | 1 |

### Cells solved (local, any edit/sample/seed)

| cell | label | 32b FS | 32b ZS |
|---|---|---|---|
| v12-nb-f15-g12 | RET | n (-0.097) | n (-0.298) |
| v12-nb-f15-g14 | RET | n (-0.396) | n (-0.183) |
| v12-nb-f15-g16 | RET | n (-4.125) | n (-0.392) |
| v12-nb-f15-g18 | RET | n (-0.534) | n (-0.421) |
| v12-nb-f24-g12 | RET | n (-0.216) | n (-0.105) |
| v12-nb-f24-g14 | RET | n (-0.338) | n (-0.230) |
| v12-nb-f24-g16 | RET | n (-2.018) | n (-0.103) |
| v12-nb-f24-g18 | RET | n (-0.485) | n (-0.404) |
| v12-wb-s11n10-g10-b0530 | SYN | n (-0.266) | **Y** (+0.000) |
| v12-wb-s11n10-g10-b0824 | RET | **Y** (+0.001) | **Y** (+0.003) |
| v12-wb-s11n10-g12-b0824 | RET | **Y** (+0.006) | n (-0.064) |
| v12-wb-s11n11-g10-b0824 | SYN | **Y** (+0.004) | n |
| v12-wb-s11n11-g12-b0824 | SYN | **Y** (+0.001) | n (-0.141) |
| v12-wb-s11n8-g10-b0530 | SYN | **Y** (+0.004) | n (-0.216) |
| v12-wb-s11n8-g12-b0530 | SYN EDGE | n (-0.205) | n (-0.237) |
| v12-wb-s11n9-g10-b0530 | SYN | n (-0.185) | **Y** (+0.001) |

### ZS vs FS (pre-reg: no claim unless >= 3 cells differ)

- qwen3-32b-q4ks: ZS-only ['v12-wb-s11n10-g10-b0530', 'v12-wb-s11n9-g10-b0530'], FS-only ['v12-wb-s11n10-g12-b0824', 'v12-wb-s11n11-g10-b0824', 'v12-wb-s11n11-g12-b0824', 'v12-wb-s11n8-g10-b0530'] -> 6 differ -> **difference claimable (>=3 cells differ)**

### Invalid-edit reasons

- qwen3-32b-q4ks FS: {'duplicate device name': 3, 'inline-comment/extra tokens': 14}
- qwen3-32b-q4ks ZS: {'inline-comment/extra tokens': 11, 'duplicate device name': 3}

### Cost vs E-c brute-force single-edit search (SPICE-min = seed-1 2500-eval screens)

E-c: SEARCH-TRIVIAL / confirmed / SPICE-min to first screen-feasible (fixed order, E[random]). LLM: per completion that reaches a seed-1-feasible edit, GPU-min (llama-server total time) + SPICE-min of its edits sized in index order up to the first seed-1-feasible one.

| cell | label | E-c trivial | E-c confirmed | E-c SPICE-min fixed / E[random] | LLM completions reaching seed-1 feasible: model cond sample (GPU-min + SPICE-min) |
|---|---|---|---|---|---|
| v12-nb-f15-g12 | RET | False | 0 | - / - | - |
| v12-nb-f15-g14 | RET | False | 0 | - / - | - |
| v12-nb-f15-g16 | RET | False | 0 | - / - | - |
| v12-nb-f15-g18 | RET | False | 0 | - / - | - |
| v12-nb-f24-g12 | RET | False | 0 | - / - | - |
| v12-nb-f24-g14 | RET | False | 0 | - / - | - |
| v12-nb-f24-g16 | RET | False | 0 | - / - | - |
| v12-nb-f24-g18 | RET | False | 0 | - / - | - |
| v12-wb-s11n10-g10-b0530 | SYN | False | 0 | 56.2 / 26.0 | 32b ZS s2 (4.9+5.4) |
| v12-wb-s11n10-g10-b0824 | RET | False | 0 | 4.2 / 6.4 | 32b ZS s1 (2.4+1.8); 32b ZS s2 (3.2+1.8); 32b FS s1 (3.3+1.8); 32b FS s2 (2.3+1.8) |
| v12-wb-s11n10-g12-b0824 | RET | False | 0 | 4.2 / 7.8 | 32b FS s1 (3.3+5.4) |
| v12-wb-s11n11-g10-b0824 | SYN | False | 0 | 4.4 / 7.4 | 32b FS s2 (2.9+1.8) |
| v12-wb-s11n11-g12-b0824 | SYN | False | 0 | 3.3 / 7.4 | 32b FS s2 (4.6+1.8) |
| v12-wb-s11n8-g10-b0530 | SYN | False | 0 | 1.1 / 6.6 | 32b FS s1 (1.9+1.8) |
| v12-wb-s11n8-g12-b0530 | SYN EDGE | False | 0 | 42.0 / 15.1 | - |
| v12-wb-s11n9-g10-b0530 | SYN | False | 0 | 33.5 / 10.2 | 32b ZS s2 (3.1+1.8) |

- qwen3-32b-q4ks FS: 32 completions, total GPU-min 138, seed-1 SPICE-min of all their edits (to first feasible or exhaustion) 103

- qwen3-32b-q4ks ZS: 32 completions, total GPU-min 157, seed-1 SPICE-min of all their edits (to first feasible or exhaustion) 111

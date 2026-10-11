### H1 protocol (8 samples; pass = valid & feasible at seed 1); [kick column: rl-v1.2-rl]

| model | group | pass@1 | pass@2 | pass@4 | pass@8 | coverage | kick pass@1 | kick pass@8 | kick coverage |
|---|---|---|---|---|---|---|---|---|---|
| sft300 | all (58) | 0.1767 | 0.2937 | 0.45 | 0.6207 | 36 | 0.1767 | 0.6207 | 36 |
| sft300 | T1 (23) | 0.1522 | 0.2655 | 0.4161 | 0.5652 | 13 | 0.1522 | 0.5652 | 13 |
| sft300 | T2 (32) | 0.2109 | 0.3415 | 0.5165 | 0.7188 | 23 | 0.2109 | 0.7188 | 23 |
| sft300 | T3 (3) | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0.0 | 0.0 | 0 |
| sft1000 | all (58) | 0.2974 | 0.4532 | 0.6012 | 0.7069 | 41 | 0.2974 | 0.7069 | 41 |
| sft1000 | T1 (23) | 0.4674 | 0.6848 | 0.8646 | 0.9565 | 22 | 0.4674 | 0.9565 | 22 |
| sft1000 | T2 (32) | 0.1992 | 0.3214 | 0.4527 | 0.5625 | 18 | 0.1992 | 0.5625 | 18 |
| sft1000 | T3 (3) | 0.0417 | 0.0833 | 0.1667 | 0.3333 | 1 | 0.0417 | 0.3333 | 1 |
| sft-r1 | all (58) | 0.3534 | 0.5111 | 0.6562 | 0.7931 | 46 | 0.3513 | 0.7931 | 46 |
| sft-r1 | T1 (23) | 0.5543 | 0.7562 | 0.8894 | 0.9565 | 22 | 0.5489 | 0.9565 | 22 |
| sft-r1 | T2 (32) | 0.2383 | 0.375 | 0.5344 | 0.7188 | 23 | 0.2383 | 0.7188 | 23 |
| sft-r1 | T3 (3) | 0.0417 | 0.0833 | 0.1667 | 0.3333 | 1 | 0.0417 | 0.3333 | 1 |

### 2-sample protocol (pilot-v0: solved = some sample feasible at >= 1 of seeds 1-3)

| model | solved | >= 2/3 seeds | T1 /23 | T2 /32 | T3 /3 | validity | solved under kick |
|---|---|---|---|---|---|---|---|
| sft300 | 28 | 24 | 10 | 18 | 0 | 0.9914 | 28 |
| sft1000 | 28 | 24 | 19 | 8 | 1 | 0.9914 | 28 |
| sft-r1 | 37 | 31 | 19 | 16 | 2 | 0.9828 | 37 |

Decision: {"pass1_r1": 0.3534, "pass1_sft1000": 0.2974, "pass8_r1": 0.7931, "pass8_sft1000": 0.7069, "tier_loss_vs_sft1000": {"T1": 0, "T2": -8, "T3": -1}, "cond_pass1": true, "cond_pass8": true, "cond_tiers": true, "round1_succeeds": true, "vs_sft300": {"pass1": 0.1767, "pass8": 0.6207, "tier_loss": {"T1": -9, "T2": 2, "T3": -2}}, "coverage_any_of_8": {"sft300": 36, "sft1000": 41, "sft-r1": 46}, "union_sft300_sft1000": 49, "union_all_three": 53, "r1_covers_of_union": 42, "r1_only": ["t2-nb090-noise-0254", "t2-nb090-noise-0286", "t2-nb090-noise-0363", "v2b-wb0824-gain-188"]}

Copy: {"copy_h1": {"valid": 461, "own_target_copies": 196, "distinct_wl": 277}, "copy_2s": {"valid": 114, "own_target_copies": 46, "distinct_wl": 82}}

Missing rows: {"h1:sft300": {}, "h1:sft1000": {}, "h1:sft-r1": {}, "2s:sft300": {}, "2s:sft1000": {}, "2s:sft-r1": {}}

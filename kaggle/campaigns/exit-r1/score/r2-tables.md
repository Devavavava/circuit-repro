### H1 protocol (8 samples; pass = valid & feasible at seed 1); [kick column: rl-v1.2-rl]

| model | group | pass@1 | pass@2 | pass@4 | pass@8 | coverage | kick pass@1 | kick pass@8 | kick coverage |
|---|---|---|---|---|---|---|---|---|---|
| sft-r1 | all (58) | 0.3534 | 0.5111 | 0.6562 | 0.7931 | 46 | 0.3513 | 0.7931 | 46 |
| sft-r1 | T1 (23) | 0.5543 | 0.7562 | 0.8894 | 0.9565 | 22 | 0.5489 | 0.9565 | 22 |
| sft-r1 | T2 (32) | 0.2383 | 0.375 | 0.5344 | 0.7188 | 23 | 0.2383 | 0.7188 | 23 |
| sft-r1 | T3 (3) | 0.0417 | 0.0833 | 0.1667 | 0.3333 | 1 | 0.0417 | 0.3333 | 1 |
| sft-r2 | all (58) | 0.3922 | 0.5277 | 0.6493 | 0.7414 | 43 | 0.3922 | 0.7414 | 43 |
| sft-r2 | T1 (23) | 0.6359 | 0.7919 | 0.9031 | 0.9565 | 22 | 0.6359 | 0.9565 | 22 |
| sft-r2 | T2 (32) | 0.25 | 0.3795 | 0.5121 | 0.625 | 20 | 0.25 | 0.625 | 20 |
| sft-r2 | T3 (3) | 0.0417 | 0.0833 | 0.1667 | 0.3333 | 1 | 0.0417 | 0.3333 | 1 |

### 2-sample protocol (pilot-v0: solved = some sample feasible at >= 1 of seeds 1-3)

| model | solved | >= 2/3 seeds | T1 /23 | T2 /32 | T3 /3 | validity | solved under kick |
|---|---|---|---|---|---|---|---|
| sft-r1 | 37 | 31 | 19 | 16 | 2 | 0.9828 | 37 |
| sft-r2 | 35 | 26 | 19 | 15 | 1 | 0.9914 | 35 |

Decision: {"pass1_r2": 0.3922, "pass1_r1": 0.3534, "pass8_r2": 0.7414, "pass8_r1": 0.7931, "tier_loss_vs_sft_r1": {"T1": 0, "T2": 1, "T3": 1}, "cond_pass1": true, "cond_pass8": false, "cond_tiers": true, "round2_succeeds": false, "bootstrap_pass1_r2_minus_r1": {"n_items": 58, "diff": 0.0388, "ci95": [-0.0216, 0.0991], "p_le0": 0.1091, "better": 23, "worse": 19}, "clear_gain": false, "coverage_any_of_8": {"sft-r1": 46, "sft-r2": 43}, "r2_only": ["t2-nb090-noise-0240", "t2-nb090-noise-0291", "t2-nb090-noise-0312", "t2-nb090-noise-0349", "v2b-wb1020-noise-217"], "r1_only": ["t2-nb090-noise-0068", "t2-nb090-noise-0254", "t2-nb090-noise-0286", "t2-nb090-noise-0300", "t2-nb090-noise-0322", "t2-nb090-noise-0351", "t2-nb090-noise-0397", "v2b-wb0824-gain-188"]}

Copy: {"valid": 462, "own_target_copies": 288, "distinct_wl": 192}

Missing rows: {"h1:sft-r1": {}, "2s:sft-r1": {}, "h1:sft-r2": {}, "2s:sft-r2": {}}

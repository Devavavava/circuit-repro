### h1-sft300 — 464 completions, 460 valid; seed-1-feasible samples 82, confirmed at a 2nd seed 69

| group | items | pass@1 | pass@2 | pass@4 | pass@8 | coverage | pass@1 conf. | pass@8 conf. | coverage conf. |
|---|---|---|---|---|---|---|---|---|---|
| all | 58 | 0.1767 | 0.2937 | 0.45 | 0.6207 | 36 | 0.1487 | 0.5862 | 34 |
| T1 | 23 | 0.1522 | 0.2655 | 0.4161 | 0.5652 | 13 | 0.125 | 0.5217 | 12 |
| T2 | 32 | 0.2109 | 0.3415 | 0.5165 | 0.7188 | 23 | 0.1797 | 0.6875 | 22 |
| T3 | 3 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0.0 | 0.0 | 0 |

pass@8 / pass@1 = 3.513 -> strong verifier-selection headroom (pass@8 >= 1.5 x pass@1); per-item c (of n) histogram: {"0": 22, "1": 15, "2": 9, "3": 6, "4": 3, "5": 1, "7": 2}; copy rate {"copies": 0, "valid": 460, "rate": 0.0, "copies_any_train": 8, "rate_any_train": 0.0174, "distinct_wl": 429}

### h1-sft1000 — 464 completions, 460 valid; seed-1-feasible samples 138, confirmed at a 2nd seed 120

| group | items | pass@1 | pass@2 | pass@4 | pass@8 | coverage | pass@1 conf. | pass@8 conf. | coverage conf. |
|---|---|---|---|---|---|---|---|---|---|
| all | 58 | 0.2974 | 0.4532 | 0.6012 | 0.7069 | 41 | 0.2586 | 0.6724 | 39 |
| T1 | 23 | 0.4674 | 0.6848 | 0.8646 | 0.9565 | 22 | 0.4022 | 0.9565 | 22 |
| T2 | 32 | 0.1992 | 0.3214 | 0.4527 | 0.5625 | 18 | 0.1758 | 0.5 | 16 |
| T3 | 3 | 0.0417 | 0.0833 | 0.1667 | 0.3333 | 1 | 0.0417 | 0.3333 | 1 |

pass@8 / pass@1 = 2.377 -> strong verifier-selection headroom (pass@8 >= 1.5 x pass@1); per-item c (of n) histogram: {"0": 17, "1": 8, "2": 6, "3": 11, "4": 4, "5": 5, "6": 5, "7": 2}; copy rate {"copies": 186, "valid": 460, "rate": 0.4043, "copies_any_train": 186, "rate_any_train": 0.4043, "distinct_wl": 223}

Coverage overlap (seed 1): {"both": 28, "union": 49, "only_first": 8, "only_second": 13}

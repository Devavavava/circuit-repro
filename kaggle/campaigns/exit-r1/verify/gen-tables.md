| policy | difficulty | tasks | completions | valid | seed-1 feasible | positives | positive tasks | novel positives (distinct WLs) | own-target copies among positives | anchor positives |
|---|---|---|---|---|---|---|---|---|---|---|
| sft1000 | all | 641 | 1282 | 1270/1282 (99.1%) | 512/1270 (40.3%) | 450/1270 (35.4%) | 309 | 122 (95) | 266 | 265 |
| sft1000 | library-solvable | 364 | 728 | 722/728 (99.2%) | 416/722 (57.6%) | 381/722 (52.8%) | 249 | 84 (65) | 265 | 265 |
| sft1000 | single-edit-solvable | 9 | 18 | 18/18 (100.0%) | 8/18 (44.4%) | 5/18 (27.8%) | 5 | 3 (3) | 0 | 0 |
| sft1000 | witness-only | 268 | 536 | 530/536 (98.9%) | 88/530 (16.6%) | 64/530 (12.1%) | 55 | 35 (28) | 1 | 0 |
| sft300 | all | 641 | 1282 | 1265/1282 (98.7%) | 200/1265 (15.8%) | 150/1265 (11.9%) | 135 | 144 (134) | 0 | 0 |
| sft300 | library-solvable | 364 | 728 | 722/728 (99.2%) | 128/722 (17.7%) | 97/722 (13.4%) | 88 | 95 (88) | 0 | 0 |
| sft300 | single-edit-solvable | 9 | 18 | 18/18 (100.0%) | 8/18 (44.4%) | 7/18 (38.9%) | 4 | 6 (6) | 0 | 0 |
| sft300 | witness-only | 268 | 536 | 525/536 (97.9%) | 64/525 (12.2%) | 46/525 (8.8%) | 43 | 43 (43) | 0 | 0 |

Tasks with >= 1 positive: {"both": 87, "union": 357, "only_first": 222, "only_second": 48}

sft1000 think: {"stop": {"word": 1280, "eos": 2}, "think_tokens_median": 5, "think_tokens_max": 917, "reasoning_tokens_lt20": 699, "reasoning_tokens_gt512": 2, "recovered": 2, "llm_errors": 0}

sft300 think: {"stop": {"word": 1282}, "think_tokens_median": 243, "think_tokens_max": 446, "reasoning_tokens_lt20": 0, "reasoning_tokens_gt512": 0, "recovered": 0, "llm_errors": 0}

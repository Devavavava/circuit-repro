| policy | difficulty | tasks | completions | valid | seed-1 feasible | positives | positive tasks | novel positives (distinct WLs) | own-target copies among positives | anchor positives |
|---|---|---|---|---|---|---|---|---|---|---|
| sft1000 | all | 641 | 1282 | 1270/1282 (99.1%) | 512/1270 (40.3%) | 450/1270 (35.4%) | 309 | 122 (95) | 266 | 265 |
| sft1000 | library-solvable | 364 | 728 | 722/728 (99.2%) | 416/722 (57.6%) | 381/722 (52.8%) | 249 | 84 (65) | 265 | 265 |
| sft1000 | single-edit-solvable | 9 | 18 | 18/18 (100.0%) | 8/18 (44.4%) | 5/18 (27.8%) | 5 | 3 (3) | 0 | 0 |
| sft1000 | witness-only | 268 | 536 | 530/536 (98.9%) | 88/530 (16.6%) | 64/530 (12.1%) | 55 | 35 (28) | 1 | 0 |

sft1000 think: {"stop": {"word": 1280, "eos": 2}, "think_tokens_median": 5, "think_tokens_max": 917, "reasoning_tokens_lt20": 699, "reasoning_tokens_gt512": 2, "recovered": 2, "llm_errors": 0}

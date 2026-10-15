# baselines-v1 G — GA tables (`ga.py summarize`, run dir `kaggle/campaigns/baselines-v1/ga/run`)

Runs 58 (tasks 58 x GA seeds [1]; complete 58x3: True). Solved at B = first seed-1-feasible sized call <= B (rl-v1.2, bptm45, 2500 evals). sft-r1 = exit-r1 H1 (8 samples/item, one sample = one sized call at most), unbiased pass@k.

## Solve rate at budget B (mean over task x GA seed) vs sft-r1 pass@k (k = B)

| group | runs | GA@1 | GA@2 | GA@4 | GA@8 | GA@16 | GA@32 | GA@64 | sft-r1 p@1 | sft-r1 p@2 | sft-r1 p@4 | sft-r1 p@8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 58 | 0.0862 | 0.1379 | 0.4138 | 0.5862 | 0.6724 | 0.7759 | 0.7931 | 0.3534 | 0.5111 | 0.6562 | 0.7931 |
| T1 | 23 | 0.2174 | 0.3478 | 0.8261 | 1.0 | 1.0 | 1.0 | 1.0 | 0.5543 | 0.7562 | 0.8894 | 0.9565 |
| T2 | 32 | 0.0 | 0.0 | 0.1562 | 0.3125 | 0.4688 | 0.5938 | 0.625 | 0.2383 | 0.375 | 0.5344 | 0.7188 |
| T3 | 3 | 0.0 | 0.0 | 0.0 | 0.3333 | 0.3333 | 1.0 | 1.0 | 0.0417 | 0.0833 | 0.1667 | 0.3333 |

## Coverage at B (tasks solved by >= 1 of the GA seeds) vs sft-r1 coverage@8

| group | tasks | cov@1 | cov@2 | cov@4 | cov@8 | cov@16 | cov@32 | cov@64 | sft-r1 cov@8 |
|---|---|---|---|---|---|---|---|---|---|
| all | 58 | 5 | 8 | 24 | 34 | 39 | 45 | 46 | 46 |
| T1 | 23 | 5 | 8 | 19 | 23 | 23 | 23 | 23 | 22 |
| T2 | 32 | 0 | 0 | 5 | 10 | 15 | 19 | 20 | 23 |
| T3 | 3 | 0 | 0 | 0 | 1 | 1 | 3 | 3 | 1 |

## Cost to the first feasible design, confirmation

| group | solved runs | median calls | median calls (censored, unsolved = inf) | median SPICE-min | mean SPICE-min | blind bar median calls | blind bar median SPICE-min | confirmed (seed 2 or 3) | confirmed both | confirmation rate |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 46 | 4.0 | 6.0 | 6.104 | 14.03 | - | - | 38 | 25 | 0.8261 |
| T1 | 23 | 3 | 3 | 3.898 | 3.85 | 2.0 | 2.8 | 21 | 15 | 0.913 |
| T2 | 20 | 8.5 | 21.5 | 13.814 | 22.65 | 19.585 | 27.174999999999997 | 16 | 10 | 0.8 |
| T3 | 3 | 24 | 24 | 40.981 | 34.59 | - | - | 1 | 0 | 0.3333 |

Blind bar = pilot-v0/eval/searchbar.json (E-c expected cost, random order: T1 over the library anchors, T2 over the shown anchor's single edits; T3 has no bar).

Cost: {"new_sized_cpu_h": 30.08, "sized_calls_total": 1188, "sized_calls_cache": 318, "stats": {"gen0_prereject": 51, "draws": 4681, "redraw_prereject": 3423, "redraw_roundtrip": 20, "redraw_seen": 252, "slot_exhausted": 5}, "status": {"found": 46, "budget": 12}}

## Pre-declared reading

- GA solve@8 0.586 < .793 and solve@64 0.7931 < .95: neither of the first two pre-declared readings applies.
- GA T2 solve@64 0.625 is well below 1 => the bench is harder for search than the blind bar suggests (re-examine).

## Per item

| task | tier | GA first feasible call (s1,s2,s3) | SPICE-min | blind bar calls | sft-r1 c/n |
|---|---|---|---|---|---|
| t2-nb090-noise-0012 | T3 | [24] | [40.981] | None | 0/8 |
| t2-nb090-noise-0013 | T1 | [5] | [6.262] | 3.0 | 6/8 |
| t2-nb090-noise-0047 | T1 | [3] | [3.85] | 2.0 | 3/8 |
| t2-nb090-noise-0068 | T1 | [3] | [3.902] | 3.0 | 1/8 |
| t2-nb090-noise-0129 | T1 | [5] | [5.983] | 3.0 | 3/8 |
| t2-nb090-noise-0143 | T1 | [1] | [1.399] | 3.0 | 1/8 |
| t2-nb090-noise-0240 | T1 | [4] | [4.685] | 3.0 | 0/8 |
| t2-nb090-noise-0254 | T2 | [None] | [None] | 42.33 | 1/8 |
| t2-nb090-noise-0269 | T2 | [15] | [24.639] | 31.75 | 4/8 |
| t2-nb090-noise-0286 | T2 | [None] | [None] | 63.5 | 1/8 |
| t2-nb090-noise-0287 | T1 | [5] | [6.312] | 3.0 | 3/8 |
| t2-nb090-noise-0291 | T2 | [None] | [None] | 25.4 | 0/8 |
| t2-nb090-noise-0300 | T2 | [None] | [None] | 63.5 | 1/8 |
| t2-nb090-noise-0307 | T1 | [5] | [6.19] | 3.0 | 4/8 |
| t2-nb090-noise-0312 | T2 | [None] | [None] | 63.5 | 0/8 |
| t2-nb090-noise-0322 | T2 | [None] | [None] | 63.5 | 1/8 |
| t2-nb090-noise-0323 | T2 | [10] | [15.564] | 15.88 | 1/8 |
| t2-nb090-noise-0349 | T2 | [None] | [None] | 21.17 | 0/8 |
| t2-nb090-noise-0350 | T2 | [None] | [None] | 63.5 | 0/8 |
| t2-nb090-noise-0351 | T2 | [None] | [None] | 63.5 | 1/8 |
| t2-nb090-noise-0363 | T2 | [29] | [54.121] | 31.75 | 1/8 |
| t2-nb090-noise-0375 | T2 | [None] | [None] | 21.17 | 1/8 |
| t2-nb090-noise-0387 | T1 | [3] | [4.227] | 3.0 | 4/8 |
| t2-nb090-noise-0397 | T2 | [None] | [None] | 25.4 | 2/8 |
| t2-nb090-noise-0411 | T2 | [None] | [None] | 63.5 | 0/8 |
| t2-wb1020-gain-0001 | T1 | [1] | [1.235] | 2.0 | 6/8 |
| t2-wb1020-gain-0010 | T2 | [4] | [6.017] | 3.18 | 4/8 |
| t2-wb1020-gain-0026 | T1 | [2] | [2.766] | 2.0 | 6/8 |
| t2-wb1020-gain-0027 | T2 | [14] | [27.884] | 6.35 | 3/8 |
| t2-wb1020-gain-0028 | T2 | [38] | [77.726] | 18.0 | 4/8 |
| t2-wb1020-gain-0043 | T1 | [3] | [3.898] | 2.0 | 5/8 |
| t2-wb1020-gain-0044 | T1 | [3] | [3.905] | 2.0 | 8/8 |
| t2-wb1020-gain-0045 | T2 | [4] | [5.659] | 2.92 | 3/8 |
| t2-wb1020-gain-0046 | T2 | [6] | [9.06] | 1.77 | 7/8 |
| t2-wb1020-gain-0065 | T2 | [4] | [5.649] | 1.61 | 3/8 |
| t2-wb1020-gain-0066 | T1 | [4] | [6.356] | 5.0 | 6/8 |
| t2-wb1020-gain-0067 | T2 | [6] | [9.552] | 1.64 | 6/8 |
| t2-wb1020-gain-0088 | T1 | [1] | [1.593] | 2.0 | 4/8 |
| t2-wb1020-gain-0089 | T2 | [4] | [5.584] | 5.14 | 1/8 |
| t2-wb1020-gain-0107 | T1 | [1] | [1.622] | 2.0 | 5/8 |
| t2-wb1020-gain-0108 | T2 | [4] | [6.341] | 2.45 | 2/8 |
| t2-wb1020-gain-0109 | T2 | [18] | [33.829] | 7.71 | 2/8 |
| t2-wb1020-gain-0126 | T1 | [1] | [1.567] | 2.0 | 3/8 |
| t2-wb1020-gain-0127 | T1 | [4] | [5.869] | 5.0 | 2/8 |
| t2-wb1020-gain-0128 | T2 | [11] | [19.2] | 21.6 | 0/8 |
| t2-wb1020-gain-0142 | T2 | [27] | [54.031] | 27.0 | 0/8 |
| t2-wb1020-gain-0159 | T2 | [10] | [18.052] | 6.35 | 1/8 |
| t2-wb1020-gain-0160 | T2 | [7] | [12.063] | 7.71 | 0/8 |
| t2-wb1020-gain-0161 | T2 | [6] | [9.673] | 3.6 | 5/8 |
| t2-wb1020-gain-0182 | T1 | [3] | [3.889] | 2.0 | 7/8 |
| t2-wb1020-gain-0183 | T1 | [3] | [3.787] | 2.0 | 7/8 |
| t2-wb1020-gain-0184 | T2 | [25] | [49.174] | 12.0 | 0/8 |
| t2-wb1020-gain-0205 | T1 | [2] | [2.7] | 2.0 | 6/8 |
| t2-wb1020-gain-0206 | T1 | [2] | [2.706] | 2.0 | 7/8 |
| t2-wb1020-gain-0207 | T2 | [6] | [9.251] | 2.92 | 6/8 |
| t2-wb1020-gain-0223 | T1 | [3] | [3.906] | 2.0 | 5/8 |
| v2b-wb0824-gain-188 | T3 | [8] | [12.7] | None | 1/8 |
| v2b-wb1020-noise-217 | T3 | [28] | [50.075] | None | 0/8 |

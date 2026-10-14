# baselines-v1 G — GA tables (`ga.py summarize`, run dir `kaggle/campaigns/baselines-v1/ga/smoke`)

Runs 2 (tasks 2 x GA seeds [1]; complete 58x3: False). Solved at B = first seed-1-feasible sized call <= B (rl-v1.2, bptm45, 2500 evals). sft-r1 = exit-r1 H1 (8 samples/item, one sample = one sized call at most), unbiased pass@k.

## Solve rate at budget B (mean over task x GA seed) vs sft-r1 pass@k (k = B)

| group | runs | GA@1 | GA@2 | GA@4 | GA@8 | GA@16 | GA@32 | GA@64 | sft-r1 p@1 | sft-r1 p@2 | sft-r1 p@4 | sft-r1 p@8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.5 | 0.5 | 0.5 | 0.3534 | 0.5111 | 0.6562 | 0.7931 |
| T1 | 0 | None | None | None | None | None | None | None | 0.5543 | 0.7562 | 0.8894 | 0.9565 |
| T2 | 2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.5 | 0.5 | 0.5 | 0.2383 | 0.375 | 0.5344 | 0.7188 |
| T3 | 0 | None | None | None | None | None | None | None | 0.0417 | 0.0833 | 0.1667 | 0.3333 |

## Coverage at B (tasks solved by >= 1 of the GA seeds) vs sft-r1 coverage@8

| group | tasks | cov@1 | cov@2 | cov@4 | cov@8 | cov@16 | cov@32 | cov@64 | sft-r1 cov@8 |
|---|---|---|---|---|---|---|---|---|---|
| all | 2 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 46 |
| T1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 22 |
| T2 | 2 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 23 |
| T3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |

## Cost to the first feasible design, confirmation

| group | solved runs | median calls | median calls (censored, unsolved = inf) | median SPICE-min | mean SPICE-min | blind bar median calls | blind bar median SPICE-min | confirmed (seed 2 or 3) | confirmed both | confirmation rate |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 1 | 11 | >64 | 19.2 | 19.2 | - | - | 1 | 0 | 1.0 |
| T1 | 0 | None | None | None | None | 2.0 | 2.8 | 0 | 0 | None |
| T2 | 1 | 11 | >64 | 19.2 | 19.2 | 19.585 | 27.174999999999997 | 1 | 0 | 1.0 |
| T3 | 0 | None | None | None | None | - | - | 0 | 0 | None |

Blind bar = pilot-v0/eval/searchbar.json (E-c expected cost, random order: T1 over the library anchors, T2 over the shown anchor's single edits; T3 has no bar).

Cost: {"new_sized_cpu_h": 2.17, "sized_calls_total": 75, "sized_calls_cache": 11, "stats": {"gen0_prereject": 2, "draws": 317, "redraw_prereject": 241, "redraw_roundtrip": 1, "redraw_seen": 8}, "status": {"found": 1, "budget": 1}}

## Pre-declared reading

- GA solve@8 0.000 < .793 and solve@64 0.5 < .95: neither of the first two pre-declared readings applies.
- GA T2 solve@64 0.500 is well below 1 => the bench is harder for search than the blind bar suggests (re-examine).

## Per item

| task | tier | GA first feasible call (s1,s2,s3) | SPICE-min | blind bar calls | sft-r1 c/n |
|---|---|---|---|---|---|
| t2-nb090-noise-0291 | T2 | [None] | [None] | 25.4 | 0/8 |
| t2-wb1020-gain-0128 | T2 | [11] | [19.2] | 21.6 | 0/8 |

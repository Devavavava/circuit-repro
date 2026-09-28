# R1: cheap-reward fidelity (rl-readiness)

This is check R1 of `kaggle/PREREG-RL-READINESS.md` (frozen 2026-09-28).
- Run: 2026-09-28 18:06 to 2026-09-29 02:06 IST on the shared box.
- At most 6 of our processes ran at once. Box load was 6 to 21 (mean about 11 to 15).
- 3652 sizing calls, 0 crashes.
- Full tables are in `tables.md`. Machine-readable numbers are in `summary.json`.

## Verdict

- **The pre-registered cheap levels fail the decision rule.** Both 1 seed × 600 and 1 seed × 1200 fail (precision ≥ 0.9 AND recall ≥ 0.8). Precision is perfect (1.000); recall is 0.29 and 0.65.
- **1 seed × 2500 passes.**
  - Lib spec: precision 1.000, recall 0.907.
  - Final verifier (gate + `STAB_WIDE_INLOOP=1`): precision 1.000, recall 0.806.
- **The pre-registered fallback (a two-stage design) is redundant.** The sizer is a deterministic CMA-ES, and the budget only truncates it. So a B-eval run at seed s is exactly the first B evals of the 2500-eval run at seed s. The objective ranks feasible points first, so cheap-feasible implies feasible at seed-s × 2500. This was observed with 0 false positives in 1000 + 120 + 120 cheap calls.
  - A "confirm every cheap-positive" stage therefore never changes a label. It costs CPU and leaves recall at the cheap level: 0.29 at 600, 0.65 at 1200.
  - The only thing that raises recall is **more evals or more seeds**.
- **Recommended RL reward:** the binary feasible verdict of the **final verifier (stability spec, gate + in-loop) at 1 seed × 2500**. Use the normalized worst margin as a dense shaping term; its Spearman correlation with the best-seed full margin is 0.93 to 0.99.
  - Cost: **about 116 CPU-s per candidate**. This is 46 ms/eval at box load of about 11; it would be less on an idle box.
  - An arm-B rollout holds about 2.7 sizable edits (E-d: 349 valid edits / 128 completions). That makes about **310 CPU-s per rollout**.
  - A 2-seed variant (seeds 1 and 2) reaches recall 0.97 (30/31) at about 230 CPU-s per candidate, or about 620 CPU-s per rollout.
- **The gate-only stability config is unusable as a reward.**
  - It is degenerate: 1 positive in 120.
  - It is **not monotone in budget**. Its post-hoc rescan is capped at `STAB_SCAN_MAX = 30` spec-feasible points, so a 600-eval run can pass while the 1200- and 2500-eval runs of the same seed fail. This happened for `v12-wb-s11n10-g10-b0824 | add R n4-n6`: a false positive at 1 × 600.
  - This is a loophole class for R4. The in-loop config does not have it (0 false positives).

## Sample (`sample.json`, `r1_drv.py sample` + `topup 70`, seeds 20260928 / 20260929)

Population:
- Units are (cell, exact token sequence) from E-c (single-edit search) and E-d (Qwen edits). They are merged on the E-d key `sha1(json(tokens))[:16]`.
- There are 2480 units. 14 appear in both E-c and E-d, and the two sources gave no conflicting verdicts.
- 2445 units are sizable. The 35 unsizable ones are excluded, because `smoke_run` returns None regardless of budget, so they agree trivially.

**Main sample: 1000 units, 248 full-feasible and 752 infeasible (3.03×).**
- Positives: all 225 recorded any-seed-feasible units, plus 23 E-c units that the completion runs found feasible at seed 2 or 3 (see Deviations 1).
  - The 23 are counted in the 248; they were sampled as near-miss negatives.
  - 236 positives are wideband and 12 narrowband; 20 are Qwen/E-d.
- Negatives:
  - All 303 sizable E-d negatives (a census of the Qwen distribution).
  - All 166 E-c near-miss negatives with seed-1 worst margin in [-0.1, 0) (a census), minus the 23 that turned out positive.
  - 306 E-c far negatives, stratified round-robin over cell within margin bins B [-0.3, -0.1), C [-1, -0.3) and D (< -1). The draw was 94/83/59 plus a top-up of 28/24/18.
- Worst-margin bins over all sampled negatives: A 155, B 171, C 193, D 233. By source, E-d contributes 12/49/86/156 and E-c 143/122/107/77.

**Completion set: 226 E-c-only negatives re-sized at seeds 2 and 3 × 2500 (lib spec).** These are all 166 near-miss (A) units plus 20 random units from each of B, C and D.

**Stability subsample: 120 units.**
- 60 lib-full-feasible: 48 wideband and 12 narrowband. All units with in-band `mu_min ≥ 1` at some seed come first, then the set is filled balanced by cell.
- 60 lib-infeasible: 25 wideband near-miss, 10 narrowband B, 15 E-d near-miss/B, and 10 far.
- Each unit was sized under `bench_anchor_prep.stability_spec` (mu_min ≥ 1) at 1 × 600, 1 × 1200 and 3 seeds × 2500.
- This was done in **two configs**: gate-only (mode `stab`) and gate + `STAB_WIDE_INLOOP=1` (mode `stabil`, the final verifier per S-1).

**Labels.**
- Full = feasible at any of seeds 1, 2, 3 × 2500 (lib spec). The ≥ 2/3-seed variant is also reported.
- Level `1x2500` uses the recorded E-c/E-d seed-1 × 2500 verdicts with no re-run. Its cost column is the recorded time.

## Main sample, lib spec (no stability gate)

Column definitions:
- "Pop-weighted" re-weights the subsampled far E-c negatives to the 2445-unit population. It changes cost fractions only, because FP = 0.
- "Near-only" is the Spearman correlation among units whose best-seed worst margin is ≥ -0.1 (n = 412).
- Per-eval cost is about 29 to 32 ms at load 13 to 15.

| level | precision | recall | F1 | TP / FP / FN / TN | vs ≥2/3 P / R | Spearman worst: vs best seed / vs s1×2500 / near-only | s/call median | rule |
|---|---|---|---|---|---|---|---|---|
| 1×600 | 1.000 | 0.290 | 0.450 | 72 / 0 / 176 / 752 | 0.944 / 0.345 | 0.890 / 0.902 / 0.506 | 17.1 | fail |
| 1×1200 | 1.000 | 0.653 | 0.790 | 162 / 0 / 86 / 752 | 0.895 / 0.736 | 0.948 / 0.959 / 0.627 | 37.3 | fail |
| 1×2500 (recorded) | 1.000 | 0.907 | 0.951 | 225 / 0 / 23 / 752 | 0.853 / 0.975 | 0.985 / 1.000 / 0.865 | 65.7 recorded; 80.6 fresh in this run | PASS |

Recall by group:

| level | wideband | narrowband | Qwen (E-d) | search (E-c) |
|---|---|---|---|---|
| 1×600 | 0.284 | 0.417 | 0.500 | 0.272 |
| 1×1200 | 0.653 | 0.667 | 0.700 | 0.649 |
| 1×2500 | 0.903 | 1.000 | 1.000 | 0.899 |

**Two-stage design** (cheap screen, then a full 3 × 2500 confirm of each cheap-positive).
- Precision is 1 by construction, and recall equals the cheap recall.
- Expected CPU-s per candidate, with full = 3 × 80.6 s, sample / population-weighted:
  - 1×600: 34.5 / 21.6 s at recall 0.29
  - 1×1200: 76.4 / 47.3 s at recall 0.65
  - 1×2500 screen (reusing its seed-1 run): 116.9 / 89.8 s at recall 0.91
- Full-only costs 241.8 s.

**Exploratory, not pre-registered: margin-gated escalation.**
- Rule: accept a cheap-positive. Escalate a cheap-negative with cheap worst margin ≥ τ to seed-1 × 2500. Reject the rest.
- Lib, 1×1200 with τ = -0.1: recall 0.863 at 51 / 41 CPU-s per candidate. The ceiling is 0.907, the seed-1 × 2500 recall.
- Under the final stability verifier this saves little: 1×1200 with τ = -0.2 reaches recall 0.774 at 113 s, versus 116 s for a plain 1×2500. The tables are in `tables.md`.

## Stability subsample (n = 120), stability_spec mu_min ≥ 1

**Gate-only** (`STAB_WIDE_INLOOP` unset, as instructed).
- Full positives: 1/120. Spec-feasible at some seed: 55.
- 1×600: 0 TP, 1 FP (non-monotone, see Verdict), 1 FN.
- 1×1200 and 1×2500: 1 TP, 0 FP, 0 FN. With a single positive, these rates carry no information.
- Median 2500-eval call: 72 s.

**Gate + in-loop** (final verifier, S-1 `f3677bb08`).
- Full positives: 31/120. ≥ 2/3 seeds: 21. By group:
  - lib-feasible wideband 21/48
  - lib-feasible narrowband 7/12
  - lib-infeasible wideband 3/35 (the changed objective finds designs the plain sizer missed)
  - lib-infeasible narrowband 0/25

| level | precision | recall | F1 | TP / FP / FN / TN | vs ≥2/3 P / R | Spearman worst vs best seed | s/call median | rule |
|---|---|---|---|---|---|---|---|---|
| 1×600 | 1.000 | 0.258 | 0.410 | 8 / 0 / 23 / 89 | 1.000 / 0.381 | 0.736 | 26.3 | fail |
| 1×1200 | 1.000 | 0.484 | 0.652 | 15 / 0 / 16 / 89 | 0.933 / 0.667 | 0.856 | 52.8 | fail |
| 1×2500 | 1.000 | 0.806 | 0.893 | 25 / 0 / 6 / 89 | 0.760 / 0.905 | 0.934 | 115.8 | PASS |
| 2×2500 (exploratory) | 1.000 | 0.968 | - | 30 / 0 / 1 / 89 | - | - | about 231 | PASS |

The in-loop term costs about 1.45× per eval: 44 to 46 ms, versus 29 to 32 ms plain.

**Caveat for RL.** A single-seed positive is robust at ≥ 2 of 3 seeds only 76% of the time under the final verifier (85% lib). The reward is as seed-lucky as the full verifier's any-seed definition. R4(c) fragility should consider this.

## Deviations

1. **The E-c "full verdicts" were incomplete.**
   - E-c ran seeds 2 and 3 only for its seed-1-feasible edits. Its 1917 seed-1-infeasible units had seed 1 only.
   - We re-sized 226 sampled E-c negatives at seeds 2 and 3 × 2500: all 166 near-miss units and 60 far ones.
   - **23/166 near-miss units are feasible at seed 2 and/or 3.** 0/60 far units are. E-d had 0/306 such flips.
   - The remaining 246 far E-c negatives in the sample are labeled on seed 1 only. This assumption is supported by 0/60 far flips.
   - Consequence: the recorded "1×2500" level is not trivially R = 1. The E-c bench-audit claim "confirmed = seed-1 feasible" undercounts feasible single edits.
2. **Negatives were topped up by 70 after the relabel.** The 23 relabelled units dropped neg/pos to 2.75×. The extra 70 E-c far negatives were drawn stratified by bin × cell and run at the cheap levels only; the final ratio is 3.03×. E-d negatives and near-miss E-c negatives were taken as a census rather than stratified subsamples.
3. **Two stability configs were run.**
   - The pre-reg says to use the "final verifier config from S-1". The caller said not to set `STAB_WIDE_INLOOP`, so the gate-only subsample was run first.
   - Mid-run, the orchestrator reported the final config: gate + `STAB_WIDE_INLOOP=1`, committed `f3677bb08`. We then added the same 120-unit subsample under that config.
   - **The gate-only rows are labelled GATE-ONLY.** The verdict above uses the in-loop rows.
4. **stability_spec race (fixed upstream in `ffa594a05`): not affected.**
   - The parent process wrote each cell's stability spec exactly once, before any worker started. The paths are in `$TMPDIR/stab-specs/map.json`, and workers only read them.
   - All 16 written specs were verified to equal the lib spec plus `mu_min: {min: 1.0}`, with every original constraint present.
5. **`bench_anchor_prep.py` changed during the run.**
   - At the first launch it had another agent's uncommitted edits (md5 `fd928de5`). It was later committed as `f3677bb08` / `ffa594a05` (md5 `d5d96405`). Each worker subprocess imports the file fresh.
   - Lib mode is flags-off. S-1 regress-checked it byte-identical (60/60), so the lib rows are unaffected.
   - First-runner rows carry the era stamp `519bcf45+wt(md5 fd928de5)`, even for rows run after the change. Second-runner rows carry the actual HEAD and md5.
6. **The selection departs from pure stratification.**
   - The stability subsample is enriched for in-band-stable positives, so it is not random.
   - Unsizable units are excluded.
   - The escalation and 2-seed analyses were not pre-registered and are labelled exploratory.
7. **Costs are wall-seconds per single-threaded call on a shared box**, at load 10 to 21. At load 6, a 600-eval call took 9 s instead of 17 s. Treat these costs as upper bounds for an idle box.

## Files and commands

Files:
- `r1_drv.py`: driver. Subcommands `sample`, `topup N`, `run [nproc]` and `one`. `run` is resumable and appends one line per call to `results.jsonl`.
- `run_r1.sh`: launcher (sets the env inline and the era stamp).
- `envrun.sh`: crenv equivalent with `TMPDIR=/tmp/cr-7cd7ffc3-r1`.
- `r1_analyze.py`: builds `summary.json` and `tables.md`.
- `results.jsonl`: 3652 rows, keyed by uid|mode|seed|budget. Modes are `lib` (1000×600, 1000×1200, 452 completion) and `stab` / `stabil` (120 × {600, 1200, 3×2500} each).
- `sample.json`: the population summary, unit lists and tokens.

Commands:
```
kaggle/campaigns/rl-readiness/R1/envrun.sh python kaggle/campaigns/rl-readiness/R1/r1_drv.py sample
kaggle/campaigns/rl-readiness/R1/run_r1.sh 6          # re-run after 'topup 70' / to resume
kaggle/campaigns/rl-readiness/R1/envrun.sh python kaggle/campaigns/rl-readiness/R1/r1_analyze.py
```

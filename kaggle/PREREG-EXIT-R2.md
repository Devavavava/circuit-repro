# PRE-REG — expert-iteration round 2 (exit-r2)

**Frozen:** 2026-10-12, before any round-2 result. **GO:** user ("go ahead", after the exit-r1 review),
Kaggle budget **≈ 15 GPU-h** (the remainder of the week to 2026-10-17 is 15.72 h; ask before exceeding).
Branch `worktree-externals-gf180`. Code = exit-r1's (`kaggle/campaigns/exit-r1/`), outputs in the same
campaign dir under round-2 names (policy `sft-r1`, data `sft-data-r2/`, eval labels `r2-*`), so exact-key
SPICE results are shared.

## Why (exit-r1, e6f50241f)

Round 1 succeeded: sft-r1 pass@1 .353 vs sft1000 .297 (paired bootstrap +.056, 95% CI [+.002, +.112]),
pass@8 .793 vs .707, 2-sample 37 vs 28. The gain is modest; round 2 asks whether a second iteration
compounds it or has plateaued.

## Protocol (= PREREG-EXIT-R1 with sft-r1 as the sole policy)

1. **Generate (Kaggle, ≤ 4.5 GPU-h):** sft-r1 (exit-r1 LoRA, GGUF sha `46a7bef6…`), 2 samples per
   training-side task (`exit-r1/gen/TASKS.json`, 641 tasks, same seeded order), same settings
   (CAP-1024, arm B, T 0.7, 4 slots). Deadline cut ⇒ uniformly random task subset, recorded.
2. **Verify (local):** rl-v1.2-rl seed 1 × 2500, seed 2 for seed-1-feasible; positive = both.
3. **Data:** `r1_build.py build --policies sft-r1,sft1000,sft300 --out sft-data-r2`: pilot-v0 examples
   ∪ round-1 positives ∪ round-2 positives (dedupe by (task, WL); pilot-v0 first, then the newest
   policy's traces); same mix rules (anchors ≤ 40%, other WL ≤ 3, ≤ 1,200, strata, seed 20261008,
   fence drops per D-R4).
4. **Train:** base Qwen3-14B, same recipe → `sft-r2` (from base, not from sft-r1).
5. **Evaluate:** held-out 58, 8 samples (samples 1–2 = 2-sample protocol), scored exactly as exit-r1.

## Decision rule

**Primary (same form as round 1):** round 2 succeeds iff sft-r2 beats **sft-r1** on held-out pass@1 AND
pass@8 (H1 protocol) AND loses < 3 tasks in every tier (2-sample) vs sft-r1.
**Secondary (reported, now pre-declared):** paired bootstrap over the 58 tasks (20k resamples, seed 0) of
the pass@1 difference; "clear gain" iff the 95% CI lower bound > 0; also coverage vs the union bound.
**What follows:** clear gain ⇒ propose round 3. Primary pass without a clear gain, or a failure ⇒ expert
iteration has plateaued at this data/compute scale; stop iterating and review (GRPO, bench difficulty)
with the user.

## Budget

gen ≈ 4 GPU-h → train + 8-sample eval ≈ 10.3 GPU-h (sft-r1's session). Training kernel capped so the
round total stays ≤ 15.7 GPU-h; if the cap would truncate training, it is recorded (not hidden).

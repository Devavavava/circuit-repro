# PRE-REG — expert-iteration round 1 (exit-r1): architecture B, first batched RL round

**Frozen:** 2026-10-08, before any result. **GO:** user ("Yes, approved"), Kaggle budget
**≈ 20 GPU-h** for this round (new approval; ask before exceeding). Branch
`worktree-externals-gf180`. Outputs: `kaggle/campaigns/exit-r1/`.

## Why (pilot-v1, eab2d3dc8)

pass@8 / pass@1 = 2.4–3.5 (sft1000 41/58, sft300 36/58 any-of-8; union 49/58) ⇒ strong
verifier-selection headroom. Mix fix M1 failed because it removed all "use library
circuit" answers; sft1000 (retrieval) and sft300 / mix (edits) are complementary.

## Protocol

1. **Generate (Kaggle, ≤ 10 GPU-h):** policies sft1000 and sft300 (pilot-v0 LoRA adapters,
   GGUF as in pilot-v1 H1), **2 samples each per training-side task** (all ok tasks of
   `pilot-v0/data` + `train-pool-v2` training side; held-out families excluded), pilot-v0
   prompt/settings (arm B, CAP-1024 thinking, no few-shot). If the projection exceeds
   10 GPU-h, subsample tasks uniformly at random (fixed seed) and record it.
2. **Verify (local CPU):** profile **rl-v1.2-rl** (rl-v1.2 + kick transient), seed 1 × 2500
   for every valid edit; every seed-1-feasible edit re-checked at seed 2; a **positive** =
   feasible at seeds 1 and 2. Record pass rates per policy, task difficulty label, novelty
   (target WL not in pilot-v0 data).
3. **Build round-1 data:** pilot-v0's 1,013 verified examples (existing rationales) ∪ new
   positives (target = the model's own successful completion: its reasoning + verified
   netlist; same trace filters as pilot-v0 P1). Dedupe by (task, target WL). Mix: answers
   whose target is a library anchor ≤ 40% (kept, not removed); every other target WL ≤ 3
   examples; at most 1,200 examples (stratified by band type and difficulty, fixed seed).
   Fence re-check vs held-out families, held-out witnesses, bench witnesses.
4. **Train (Kaggle):** base Qwen3-14B, pilot-v0 recipe (QLoRA, 2 epochs, grad-accum 4,
   warmup + linear decay, seq ≤ 8192) → `sft-r1`.
5. **Evaluate (Kaggle + local):** held-out 58 exactly like pilot-v0 (2 samples, seeds 1–3,
   rl-v1.2) AND pass@k like pilot-v1 H1 (8 samples, seed-1 feasible, confirm seed 2),
   also scored under rl-v1.2-rl (kick) as a secondary column.

## Decision rule

**Round 1 succeeds** iff sft-r1 beats sft1000 on BOTH held-out pass@1 and pass@8 (H1
protocol) AND loses < 3 tasks in every tier (2-sample protocol) vs sft1000. Also report vs
sft300 and the union-of-two-specialists bound (49/58). If it succeeds, round 2 repeats with
sft-r1 as the sole policy; if not, diagnose (mix, data size, policy) before any round 2.

## Budget order (if tight)

Generation ≤ 10 → training+2-sample eval ≈ 8 → pass@8 eval ≈ 1.5–2.5 (drop to 4 samples
if needed, recorded). Cumulative ledger kept; stop and report before exceeding ~20 GPU-h.

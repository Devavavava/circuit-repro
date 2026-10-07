# PRE-REG — pilot v1: pass@k headroom (H1) + data-mix fix (M1)

**Frozen:** 2026-10-07/08, before any result. **GO:** user ("yes", after the pilot-v0
review). Kaggle budget: the remainder of the approved 30 GPU-h (12.1 GPU-h left after
pilot-v0's 17.90). Branch `worktree-externals-gf180`. Outputs: `kaggle/campaigns/pilot-v1/`.
Same held-out eval (`pilot-v0/eval`, split sha 809d4bc7…, tiers T1 23 / T2 32 / T3 3),
same verifier rl-v1.2, same scoring (seeds 1–3 × 2500, bptm45) unless stated.

## Why (pilot-v0 result, 8b77fbe18)

zs 5/58 → sft100 9 → sft300 28 → sft1000 28. The 300→1000 plateau coincides with a mix
shift (T1 10→19, T2 18→8) and heavy copying (sft1000: 46/115 outputs equal a training
target topology vs 3/115 for sft300); 72% of training examples are library-solvable and
their targets are the 5 anchors (highly repeated). Sample variance is high: sft300 and
sft1000 share 11 solves, their union is 45/58.

## H1 — pass@k headroom (~4 GPU-h)

sft300 and sft1000 (existing LoRA adapters / GGUFs from the pilot-v0 kernels), k = 8
samples per held-out task, temperature and settings as in pilot-v0. Scoring: every valid
edit at seed 1 × 2500 under rl-v1.2 (R1: precision 1.0 at this level); every seed-1-feasible
edit confirmed at seeds 2,3. **Metrics:** unbiased pass@k for k = 1,2,4,8 (overall and per
tier); coverage (tasks solved by any sample); per-task solve frequency.
**Reading (pre-declared):** pass@8 ≥ 1.5 × pass@1 ⇒ strong verifier-selection headroom
(expert iteration / RL has signal); pass@8 ≈ pass@1 ⇒ the model's distribution is narrow.

## M1 — data-mix fix (~7 GPU-h)

New training set "mix-1000" (≈1,000 examples, training side only, same fence):
- library-solvable examples ≤ 40%;
- each distinct target topology (canonical WL) ≤ 3 examples;
- fill with witness and single-edit examples (all available, then library up to the cap);
- stratified by band type as in pilot-v0; fixed seed; nested reuse of existing rationales
  where the example is unchanged; rationalize only new examples (same filters as pilot-v0
  P1 D-Q2: one netlist, ≤ 512 tokens, no leak phrases, round-trip to the verified answer).
Train **one** model, sft-mix1000, with pilot-v0's exact SFT recipe (2 epochs, grad-accum 4,
warmup + linear decay, seq ≤ 8192) and evaluate exactly like pilot-v0 (2 samples/task).
(A mix-300 model is dropped to fit the budget — stated in advance.)
**Decision rule:** sft-mix1000 vs sft1000 and sft300 on held-out: the mix fix "works" if
it solves ≥ 3 more T2 tasks than sft1000 without losing ≥ 3 T1 tasks, and its training-
target copy rate is < half of sft1000's.

## Budget conduct

Per-kernel GPU-h ledger; stop and report before the cumulative total exceeds 30.0 GPU-h
(pilot-v0 + v1). If H1 alone threatens M1's budget, run H1 for sft300 only and say so.

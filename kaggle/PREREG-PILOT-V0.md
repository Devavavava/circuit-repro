# PRE-REG — pilot v0: tiered held-out eval + Qwen3-14B SFT data-scaling pilot

**Frozen:** 2026-10-05, before any result. **GO:** user, 2026-10-05 ("go with A").
Branch `worktree-externals-gf180`. Outputs: `kaggle/campaigns/pilot-v0/`.
Context: bench-v2 under honest physics (rl-v1.2) left 2 strict cells — multi-edit-required
LNA challenges are rare; library retrieval + single edits cover almost everything
(`PREREG-BENCH-V2.md` amendments 1–3, `kaggle/editcap-lib-v2/INDEX.json`). The program
metric is spec-hitting speed: solve rate and **SPICE-minutes to first feasible**.

## Verifier

rl-v1.2 (`VERIFIER-RL-V1.md`) for all labels and scoring; bptm45; 2500 evals/seed.

## P0 — tiered held-out eval (local CPU)

- **Split:** from `kaggle/train-pool-v2` (272 ok tasks), hold out whole spec families
  (band × objective-flavor grid points) totalling ~20–25% of tasks, both band types
  represented; the rest is the training side. Plus the 2 strict bench-v2 cells as
  extra Tier-3 items. The split is fixed (written to disk, hashed) before any model
  output is scored. Training data may never contain a held-out spec family.
- **Tiers** (per held-out task, under rl-v1.2): T1 library (some anchor a1–a5 solves,
  existing F1 evidence, seeds {1,2}); T2 single-edit (not T1, some single edit of the
  shown anchor solves — full F2 enumeration at seed 1, then seed 2 on candidates near
  feasibility, as in E-c); T3 multi-edit (neither; witness exists).
- **Search bar** (from the same runs, no extra sims): expected SPICE-minutes to first
  feasible for blind search in random order (T1: over anchors; T2: over single edits;
  T3: reported as ">F2 space").

## P0b — training-data generation (local CPU)

- Extend the training stream (same generator, training grid points only) to ≥ 600 tasks
  so ≥ 1,000 distinct verified examples exist. An example = (prompt: spec + shown failing
  anchor + its failure evidence, editcap arm-B format, no few-shot hint) → (verified
  solving netlist). Positives: planted witnesses, library solutions, single-edit
  solutions where known; ≤ 3 examples per task; dedupe by canonical topology.
- Nothing hand-written or LLM-designed enters as a solution (nudge-limit directive).

## P1 — Kaggle (needs user GPU-hour approval before launch)

1. **Reasoning traces:** Qwen3-14B rationalizes each training example (STaR-style: given
   task + verified answer, write a ≤ 512-token diagnosis/reasoning ending in that
   netlist); keep only traces whose final netlist round-trips to the verified answer.
2. **Baseline:** Qwen3-14B zero-shot (CAP-1024 thinking, arm B, no few-shot) on the
   held-out eval, 2 samples/task, scored locally (rl-v1.2, seeds 1–3 × 2500).
3. **SFT pilot:** QLoRA (unsloth, 1×T4, seq ≤ 8192, E-e settings) on **100 / 300 / 1,000**
   examples (nested subsets, same seed/hparams); each model evaluated exactly like (2).

## Metrics and decision rule

Per tier and overall: solve rate (any sample feasible, and ≥ 2/3 seeds), valid-netlist
rate, SPICE-minutes to first feasible (model completion GPU time reported separately),
vs the search bar. **Useful-fine-tune criterion:** the 1,000-example model beats the
zero-shot baseline on held-out solve rate by ≥ 3 tasks AND does not lose validity;
the 100→300→1,000 curve's slope decides whether to scale data (positive slope) or change
approach (flat). With ~60 held-out tasks × 2 samples, differences < 3 tasks are noise.

## Fences

Held-out spec families, the 2 strict cells and all bench-v2/v1.2 witnesses are eval-only.

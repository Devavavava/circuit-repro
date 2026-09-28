# PRE-REG — RL-readiness checks R1–R4 (campaign `rl-readiness`)

**Frozen:** 2026-09-28, before any result below exists. **GO:** user, 2026-09-28 ("let's do
all four of the cheap checks"; Kaggle ≈ 4 GPU-h for R2+R3, ask before exceeding).
Branch `worktree-externals-gf180`. Outputs: `kaggle/campaigns/rl-readiness/<R-x>/`.

## Context and path (user-ruled 2026-09-28)

End goal = RL (GRPO-style) fine-tuning of **Qwen3-14B** against the SPICE verifier.
Order: (1) stability gate ✅ + bench-v2 + training-task generator + R1–R4 →
(2) pilot SFT + 100/300/1000 data-scaling curve → (3) **architecture B = batched RL
rounds** (Kaggle generates, this box scores, Kaggle updates) → (4) online GRPO —
architecture **C (rented GPU) is NOT started without a user discussion**; the user
reviews after every step.

## R1 — cheap-reward fidelity (local CPU)

Can a cheap verifier call replace the full one (3 seeds × 2500 evals) as the RL reward?
Population: the already-fully-verified candidates of `bench-v12-audit` E-c (single-edit
search) and E-d (Qwen edits) — full verdicts exist (no stability gate). Re-size a
stratified sample (all full-feasible + ≥ 3× as many infeasible, stratified by cell and
worst margin, ≥ 600 candidates total) at **1 seed × 600** and **1 seed × 1200** evals.
Also a ≥ 100-candidate subsample under the stability-enabled spec at cheap AND full
budget (final verifier config from S-1).
**Metrics:** precision / recall of cheap-feasible vs full-feasible; rank correlation of
worst margin; cost per call.
**Decision rule:** cheap reward usable as the RL reward if **precision ≥ 0.9 and recall
≥ 0.8** (false positives are worse than misses — they are reward hacking). Otherwise
the reward is two-stage: cheap screen, full confirm of every cheap-positive.

## R2 — thinking-length cap (Kaggle, ≤ 1.5 GPU-h)

Qwen3 thinking ≈ 90% of completion tokens. Qwen3-14B Q4_K_M, bench-v1.2 16 cells, arm B,
**FS condition** (the only 14B condition with signal: 6/16 in E-d), 2 samples/cell, new
conditions **thinking capped at ~1024 tokens** and **thinking off** (`/no_think`);
baseline = the existing E-d 14B-FS run (thinking on). Scored locally exactly like E-d
(3 × 2500, bptm45), plus a re-score of all three conditions under the stability gate.
**Decision rule:** a cheaper condition is acceptable if validity ≥ 95%, cells solved
drop ≤ 1 vs thinking-on, and per-edit feasible rate is not lower by > 5 points; choose
the cheapest acceptable condition for RL rollouts. (2 samples/cell → coarse; stated.)

## R3 — GRPO smoke on Kaggle (≤ 2.5 GPU-h)

Does TRL/unsloth GRPO run Qwen3-14B LoRA on one T4? Group size G ≥ 4 (target 8),
completions ≥ 1024 tokens, a real reward on a few rollouts (harness netlist round-trip +
one SPICE sizing in-kernel using the `circuit-repro-ngspice47` dataset), plus a trivial
reward for the rest. Measure: OOM boundary, s/step, rollouts per GPU-hour, whether fast
(vLLM-style) generation works on T4, **Kaggle CPU count** and SPICE sizing time per call
in-kernel. Training data: NON-bench prompts only (held-out fence).
**Decision rule:** "GRPO-on-Kaggle feasible" if a G ≥ 4, ≥ 1024-token step completes
without OOM; report rollouts/GPU-h and the implied architecture-B round size.

## R4 — verifier loophole audit (local CPU; starts after S-1 fixes the verifier config)

Try to break the verifier before RL does. At minimum: (a) spec topology limits
(`device_budget`, `max_inductors`) are NOT enforced by the sizer (found in E-c) —
measure how many recorded "solutions" violate them; (b) degenerate structures among
recorded solutions (direct passive VIN1–VOUT1 paths, near-zero current, ports shorted);
(c) fragility — ±5% perturbation of a solution's sized values flips feasibility;
(d) **stability-window sensitivity** — re-score gated designs with windows 0.1–10,
0.1–20, 0.01–50 GHz; (e) **actual oscillation** — transient sim with 50 Ω terminations
on designs that fail the gate: do they really oscillate?
**Decision rule:** every exploit class found gets a verifier guard (or a documented,
user-accepted waiver) **before** any RL round.

## Held-out fence

bench-v1.2 / bench-v2 cells and reference templates are eval-only; R-check training or
GRPO prompts use non-bench specs only.

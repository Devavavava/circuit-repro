# CAMPAIGN qwen-editcap-v2 — pure capacity swap: dense 32B on the frozen benchmark (DRAFT — freezes when the weights dataset exists)

User rulings 2026-09-13: pure swap + one fix arm; fine-tuning follows this
experiment; literature RAG skipped.

## Question

Does per-token capacity (Qwen3-32B DENSE, ~32.8B active, vs Qwen3-30B-A3B
MoE, ~3.3B active) change (a) perception quality WITHOUT annotation —
the CONTRADICTED rate on raw netlists, (b) closures/margins on the frozen
13-cell benchmark, holding prompts, library, budgets, fences, and rubric
byte-identical to v0/v1?

## Model

Qwen3-32B GGUF **Q4_K_S** (18.77 GB — Q4_K_M at 19.76 GB exceeds the
~19.5 GB kernel-output cap; verified 2026-09-13). Import kernel
circuit-repro-import-qwen3-32b-gguf (sha256 in its log); dataset
circuit-repro-gguf-qwen32 (user UI click, pending). llama-server splits
across 2×T4 as with the MoE; expect several× slower tokens — LLM share of
wall grows, sizing unchanged.

## Arms (13 cells, budgets/fences as v1)

- **B32** — arm B verbatim (no annotation, 1 round): the capacity-alone
  perception cell. Adjudication rubric applies; headline comparison =
  CONTRADICTED rate vs v0-B (10/11) and vs v1-E (0, with annotation).
- **EF32** — annotation + rounds=2 verbatim: best-known-recipe × capacity.
  Compared against v1-EF (2/13 closures incl. h01 credit).
- **EF32-s** — the ONE fix arm (kept separate so the swap stays pure):
  diagnosis-first output schema + max-tokens raised (v1 compliance
  regression: 2/13 diagnoses emitted, ≥1 truncation). Measures the
  compliance lever at the new capacity.

Nulls: unchanged (A 3600 / A′ 5400 stand; library frozen).

## Frozen scoring

Closures vs matched nulls (credit rule as v0/v1); CONTRADICTED-rate table
across {v0-B, v1-E, B32, EF32, EF32-s}; diagnosis-emission compliance
rate; round-2 win rate for EF arms; adjudication by the same rubric.
Cost estimate: 3 arms ≈ 9–12 h GPU (dense-model token slowdown).

## Launch prerequisites

(1) circuit-repro-gguf-qwen32 dataset exists (user click); (2) kernel
weights-dataset + model-path env flip in push-dir copy; (3) origin push of
this freeze + per-instance launch word.

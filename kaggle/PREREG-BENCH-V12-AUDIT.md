# PRE-REG — bench-v1.2 audit + learner feasibility (campaign `bench-v12-audit`)

**Frozen:** 2026-09-26, before any result below exists. **GO:** user, 2026-09-26
("i approve all the experiments"; learner = "a smaller model on T4, whatever we can
end up finetuning but don't go too small"). Branch `worktree-externals-gf180`.
Outputs: `kaggle/campaigns/bench-v12-audit/<E-x>/`.

## Why (the audit that motivated this — 2026-09-26)

Fact-check of `CURRENT-STATE.md` / `PLAN-topology-selfimprovement.md` found:
- bench-v1.2 "Claude 16/16" is **true by construction** (`calibrate_bench_wb.py:41`,
  `_nb.py:29` keep only anchor-fails ∧ template-solves) and "Claude" = **two fixed
  templates** → the benchmark tests exactly two moves: wideband = shown anchor + one
  resistor drain→gate (`R Rf n2 n1`); narrowband = library anchor a1 + 2 caps.
- Template solves are deterministic (bit-identical across 7 processes) but
  **razor-thin** (worst margin +4e-5..+1.2e-2); headroom never measured. Likely cause:
  the sizing objective penalizes violation only (`lna/size.py:1436`), so it stops
  improving at the limit.
- The 5-family anchor null was **never run on the 16 specs** (shown nb anchor = a5
  common-gate, deliberately weak).
- Qwen "~0/16" was **never measured on bench-v1.2**; the few-shot 3/8 had **no matched
  zero-shot control**, margins <0.02, lower edit budget (3×600) than calibration (3×2500).
- Plan's "SFT Qwen-32B" has **no hardware path** (Kaggle 2×T4, 30 GPU-h/wk, no FT code).

## Common settings (all local experiments)

Engine `kaggle/bench_anchor_prep.py::smoke_run(tokens, spec, seed, budget, "bptm45")`,
feasible = `result["feasible"]`, margin = `mysolve._margins` (normalized, worst over
supported constraints). Budget **2500 evals/seed**, seeds **1,2,3** unless stated.
`OMP/OPENBLAS/MKL_NUM_THREADS=1`, `TMPDIR` local. Deterministic, so one run per
(candidate, seed); no repeats needed.

## E-a — Headroom of the reference solutions

For each of the 16 cells: tighten every supported constraint limit by δ·scale
(`Spec._scale`, the same normalization as the margin) for δ ∈ {0.02, 0.05, 0.10}; size
the cell's template (seeds 1,2,3 × 2500). **Headroom** = largest δ at which any seed is
feasible (0 if only the untightened spec passes).
**Decision rule:** a cell is **EDGE** if headroom < 0.02. If ≥ 8/16 cells are EDGE,
bench-v1.2 must be re-calibrated with a margin cushion before it is used as a
ceiling/eval (a solve that exists only at the limit is not a trustworthy label).

## E-b — 5-anchor null on the 16 specs

Size every bptm45 LNA anchor family a1..a5 (`kaggle/bench-anchors/MANIFEST.json`)
against each of the 16 specs (seeds 1,2,3 × 2500, all seeds run, margins recorded).
**Decision rule:** a cell solved by ANY existing anchor is a **RETRIEVAL** cell (the
fix is "pick the right library circuit", not topology synthesis) and must be labelled
as such; the synthesis benchmark = the non-RETRIEVAL cells.

## E-c — Brute-force single-edit search (the "dumb search" bar)

Search space per cell = the SHOWN anchor plus exactly one primitive edit:
(i) add one two-terminal element {R, C, L} between any unordered pair of distinct
existing nets (all nets incl. VDD/VSS/ports); (ii) delete any one existing element.
Candidates that fail `proposal.round_trip` or are not sizable are recorded as such.
Screen: seed 1 × 2500; every screen-feasible candidate is confirmed at seeds 1,2,3.
Enumeration order is fixed (deterministic sort) and recorded.
**Metrics:** per cell — #candidates, #feasible, and **SPICE-minutes to first
feasible** in the fixed order and in expectation under random order (the program's
primary metric, governance 2026-08-20).
**Decision rule:** a cell is **SEARCH-TRIVIAL** if any single edit is confirmed
feasible. The LLM's value on bench-v1.2 is then judged only against this bar
(solving a SEARCH-TRIVIAL cell is not evidence of topology reasoning unless it is
cheaper in SPICE-minutes than the search).

## E-d — Real Qwen baseline, matched zero-shot vs few-shot (Kaggle)

All 16 cells, arm B (evidence + diagnosis → k=3 edits), temp 0.7, 8192-tok cap,
`EDITCAP_RECOVER_REASONING=1`, conditions **ZS** (no few-shot) and **FS**
(`EDITCAP_FEWSHOT=1`, the existing generic example, unchanged), **2 completions per
(cell, condition)**, same kernel pattern as `editcap-v12-fewshot`. Models:
**Qwen3-32B Q4_K_S** (the current proposer) and **Qwen3-14B** (the fine-tune
candidate, see E-e). **Scoring is local and matched to the template calibration:**
every valid edit is re-sized on this box at seeds 1,2,3 × 2500 bptm45 (in-kernel
smoke results are recorded but not the score).
**Metrics:** cells solved (any edit of any completion feasible), per-edit valid /
feasible rates, topology classes emitted (`analyze_qwen_vs_claude_topo.py`, detector
widened to R from any drain/tank node to the input gate), ZS vs FS on the SAME cells.
Reported against E-b/E-c labels (RETRIEVAL / SEARCH-TRIVIAL).
Caveat fixed in advance: 2 samples/cell → rates are coarse; no claim of a ZS–FS
difference unless ≥ 3 cells differ.

## E-e — Fine-tune feasibility on Kaggle T4 (learner path, user-ruled)

Find the **largest** Qwen3 that can be QLoRA-fine-tuned on Kaggle T4 at our sequence
lengths, trying 14B first (single T4, 16 GB), 8B only as fallback; 32B on 2×T4 only
if a supported multi-GPU QLoRA path exists without custom engineering. Smoke = a few
optimizer steps on SYNTHETIC/legacy (non-bench-v1.2, non-template) data at seq 4096
and 8192; record peak VRAM, s/step, OOM boundary, and verify the round trip
LoRA → merged → GGUF Q4 → loads in the kernel's llama.cpp. **Decision rule:** the
learner model = the largest size that passes the smoke at seq ≥ 4096; "too small" floor
= 8B (below that, stop and ask).

## Held-out fence

bench-v1.2 cells and `kaggle/claude-solutions/templates/` are EVAL-ONLY: never used as
fine-tune data, never shown in prompts beyond the existing FS example.

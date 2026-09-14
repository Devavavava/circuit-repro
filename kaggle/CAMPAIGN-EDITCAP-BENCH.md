# editcap-bench-v1 — the 100-cell topological-challenge benchmark (design FROZEN 2026-09-14; library materializes through the staged pipeline below)

User commission + sign-offs 2026-09-14: (1) class mix approved, (2) ~200
candidates → ~100 survivors approved, (3) per-class anchors via the
externals approval flow approved. Purpose: 100 cells of TOPOLOGICAL
challenge — explicitly not sizing challenges and not simulation
bottlenecks — across circuit classes, as the evaluation substrate for all
future model work (fine-tuning is user-sequenced BEHIND this benchmark).

## Inclusion rule (frozen; the validated 13-cell definition, generalized)

A candidate cell enters the benchmark iff:
- **sizing-resistant:** a matched-budget sizing-only null (3600
  evals/cell, seeds 3 × 1200, no-escalate) on the cell's best known-good
  anchor FAILS it; AND
- **device-feasible:** a physaudit-style class screen says the gates are
  physically reachable on gf180 (LNA: existing audit method; PA/mixer/
  balun: per-class screens built during bring-up — gain/power/conversion
  ceilings from single-device measurements); AND
- **sim-affordable:** the class's per-eval cost ≤ ~5× the LNA baseline
  (~40 ms), else the cell's budgets are rebalanced or the cell is dropped
  (logged, never silent).

## Class mix (approved)

~40 LNA · ~25 PA · ~20 mixer · ~15 balun-LNA survivors, from candidate
grids of 75/50/40/35 (kaggle/bench_grid.py, deterministic; grids may
under/over-shoot the survivor targets — the FILTER decides, targets are
not quotas and will not be forced).

## Pipeline (staged; each stage archives its evidence)

1. Spec grids generated + validated (bench_grid.py; all YAMLs Spec.load
   clean; objective-gap flags per class recorded honestly).
2. Class bring-up: per-class eval-cost table + end-to-end sizing check on
   gf180; any objective gaps are ARCHITECTURAL work needing its own
   pre-reg (not silently patched).
3. Anchor families per class through the externals flow:
   candidate lists (kaggle/EXTERNALS-BENCH-CANDIDATES.md) → USER APPROVAL
   → structure-only transcription WITH published bias networks →
   ingestion gates (parse/round-trip/L0/conduction smoke incl. s21 fence)
   → per-class sizing sanity (each anchor must be ALIVE on gf180).
4. Null-filter campaign (box, parallelized): every candidate × its class
   anchors; survivors = nulls-fail cells.
5. Device-feasibility screens (box): drop device-infeasible survivors.
6. Library packaging: per-cell anchor selection (best worst-margin),
   evidence.json, render fences, bucket taxonomy (per-class analogue of
   S1/S2/S3 by binding constraint + margin), INDEX freeze.

## Budgets & bottleneck discipline (from the measured cost table)

Box: nulls ~200 cells × ~2.5–4 min ≈ 8–13 h sequential, run ×6 parallel
(~2 h/leg). Zero GPU until the benchmark's first LLM arms; at 100 cells a
GPU arm ≈ 8–12 h (32B) → future campaigns budget ~2 arms/quota-week and
must justify every arm.

## Governance

Spec grids are a NEW instrument (the 24-ladder stays frozen and untouched);
benchmark cells never enter stores; anchors are declared externals with
citations; all filter outcomes (kept/dropped + reason) are archived — no
silent truncation. Era stamps per stage; single era for the null-filter
campaign.

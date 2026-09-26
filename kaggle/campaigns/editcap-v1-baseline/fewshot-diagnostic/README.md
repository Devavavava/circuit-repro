# Few-shot capability-gap diagnostic (wideband shunt-feedback)
Kernel editcap-v12-fewshot: 8 wideband bench-v1.2 cells, arm B, one worked
RESISTIVE-SHUNT-FEEDBACK example in-context (generic, not any cell's answer).
RESULT vs no-few-shot baseline:
- shunt-feedback produced: 4/24 edits  (baseline 0/64)
- wideband cells SOLVED:   3/8  (v12-wb-s11n8-g10, n9-g10, n10-g10-b0824)
=> the wideband gap is KNOWLEDGE/surfacing, NOT deep capability. Cheap fix:
   prompt-augment / light SFT with worked topology examples. No from-scratch
   fine-tune required to unlock the missing topology class.

## AUDIT CAVEATS (2026-09-26)
- "baseline 0/64" is from the OLD gf180 editcap-v1 cells (23 bnl-wb cells, 3072-tok
  cap, different lib/process/prompt) — there was **no matched zero-shot control** on
  these 8 cells. Matched ZS vs FS = E-d in `kaggle/PREREG-BENCH-V12-AUDIT.md`.
- The example is "generic" in device graph, but its prose says to "add a feedback
  resistor from the amplifier's output/drain node back to the input gate node" —
  on this anchor that IS the one-element benchmark answer. The 4 shunt-fb edits are
  graph-identical to the reference template.
- All 3 solves have worst margin < 0.02 (s21 +0.0124, s21 +0.0079, s11 +0.0192) at an
  edit budget ≤ 3×600, lower than calibration (3×2500); the exact template graph FAILED
  on n8-g12 / n11-g12 at that budget → solve counts are budget-dependent.

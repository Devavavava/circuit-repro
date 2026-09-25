# Few-shot capability-gap diagnostic (wideband shunt-feedback)
Kernel editcap-v12-fewshot: 8 wideband bench-v1.2 cells, arm B, one worked
RESISTIVE-SHUNT-FEEDBACK example in-context (generic, not any cell's answer).
RESULT vs no-few-shot baseline:
- shunt-feedback produced: 4/24 edits  (baseline 0/64)
- wideband cells SOLVED:   3/8  (v12-wb-s11n8-g10, n9-g10, n10-g10-b0824)
=> the wideband gap is KNOWLEDGE/surfacing, NOT deep capability. Cheap fix:
   prompt-augment / light SFT with worked topology examples. No from-scratch
   fine-tune required to unlock the missing topology class.

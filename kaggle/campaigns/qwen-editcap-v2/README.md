# qwen-editcap-v2 — results (COMPLETE, 2026-09-14)

Pre-reg: kaggle/CAMPAIGN-EDITCAP-V2.md (frozen pre-run). Era 7e06befc, all
legs. Model: Qwen3-32B DENSE Q4_K_S (dataset circuit-repro-gguf-qwen32).
Legs: gpu-leg-swap (arms B32 + EF32, pure swap) · gpu-leg-EFs (EF32-s:
+diagnosis-first schema, 4096 tokens).

## FIRST S2 WALL CLOSURE IN PROGRAM HISTORY

**B32 closed cap-e07-gpsband** — raw netlist, no annotation, single round:
the model re-oriented the input match into a series-L + shunt-C L-section
driving the current-reuse pair via the interstage cap; measured s11 −14.16
(gate −10), s21 13.25 (≥12), NF 2.85 (≤3.0), idd 5.46 (≤10). No null, no
prior arm, and neither move-library arm ever closed e07 (best R −0.20).
Clean edit-credit. **EF32-s closed e07 as well** (independent replication
at the same capacity).

## Scores (13 cells)

| arm | closed | median best wm | diagnosis emitted |
|---|---|---|---|
| B30 (v1 B′) | 0/13 | −0.864 | (2/13 in v1-E; ~11/13 v0) |
| **B32** | **1/13 (e07)** | −0.914 | 10/13 |
| EF30 (v1) | 2/13 (e02, h01) | −0.692 | 2/13 |
| EF32 | 0/13 | −0.911 | 9/13 |
| EF32-s | 1/13 (e07) | −0.941 | **12/13** |

## Pre-registered headline: capacity ALONE fixed perception

B32's ten diagnoses contain **zero contradiction-class claims** (grep +
read: no "floating/shorted/typo/unused/no-DC-path" misreads; pin bindings
correct where stated, e.g. e07's "gate of NM1 (n2)"). v0-B at 30B: 10/11
CONTRADICTED. So BOTH levers independently eliminate the confabulation:
annotation at 30B (v1-E) and capacity at 32B-dense on raw netlists. The
dense model's diagnoses are far terser (~350 bytes) — fewer claims, all
grounded; a different (better) failure surface than the MoE's verbose
confabulation.

## Anomalies and honest notes

- **EF32 (annotation+rounds at 32B) scored 0/13** — lost v1-EF's e02/h01
  closures and 3 cells produced no surviving sized edits. Candidate
  causes: 3072-token budget under the long 2-round annotated prompt with
  a more verbose dense model (EF32-s at 4096 tokens restored a closure
  and 12/13 compliance), plus the known gf180 LLM-arm run-to-run
  variance. Not resolved here; single-run caveat applies to ALL cells in
  this table.
- Closure sets are DISJOINT across capacity tiers (30B EF: e02+h01;
  32B: e07) — more evidence that single-run closures ride sampling luck
  on top of real capability; only e07 has a same-day replication (B32 +
  EF32-s).
- **Mechanism correction to the editcap-v0 adjudication note:** the
  harness DC-blocks the RF port in the emitted deck (Cp1), so "L to
  VIN1" edits do NOT short the gate bias; the externals-v0 dead-bias
  failures were FLOATING-GATE cases (input-blocked template with no
  in-topology bias). The operative lesson (cap-block the input AND carry
  in-topology bias) stands; the earlier shorthand mechanism was wrong.

## Reading

Capacity is real: better perception for free on raw netlists, plus the
first S2 closure, replicated within-day. The v1 interface levers
(annotation, rounds) were compensating for a capacity deficit — at 32B
they no longer pay on this benchmark (and may hurt under tight token
budgets). Next per user sequencing: FINE-TUNING (corruption-repair route)
on top of the 32B baseline, with this benchmark + rubric as the eval.

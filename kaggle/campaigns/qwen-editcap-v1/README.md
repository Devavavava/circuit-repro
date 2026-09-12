# qwen-editcap-v1 — results (COMPLETE, 2026-09-12)

Pre-reg: `kaggle/CAMPAIGN-EDITCAP-V1.md` (frozen pre-results; driver
6f357104). Era 60d9baed (all arms). Kernel v2, ~7 h; launcher fences all
green (13 rows × 4 arms, 13 adjudication trees). A′ null: box, 5400
evals/cell.

## Headline: FIRST CLEAN EDIT-CREDIT IN PROGRAM HISTORY

**Arm EF closed cap-h01-wifi** (h-tier: NF 1.49 vs 1.5 gate, S21 18.4 vs
16, S11 −17.6 vs −13, Idd 2.68 vs 4) — a cell the budget-matched A′ null
could NOT close (best −0.04). The closing edit came from **round 2** of the
verify-refine loop: the model saw round-1 measured results and revised.
Frozen credit rule satisfied: closed by EF, not by its matched null.

## Closures and margins (13 cells; * = closed)

| arm | closed | vs matched null | median best worst-margin |
|---|---|---|---|
| A (v0 null, 3600) | 0/13 | — | −0.80 |
| A′ (null, 5400) | 1/13 (e02) | — | −0.83 |
| B′ (v0 replication + new fence) | 0/13 | 0 credit | −0.86 |
| E (annotation) | 1/13 (e02) | rule-credit vs A; CAVEAT: A′ closes e02 by sizing alone (budget-fragile) | −0.68 |
| F (verify-refine ×2) | 1/13 (e02) | no credit (A′ closes it) | −0.78 |
| EF (both) | **2/13 (e02, h01)** | **h01 = clean credit ×1** | −0.69 |

Notes: best-edit-from-round-2 in 7/13 (F) and 8/13 (EF) cells — feedback
genuinely steers. F rescued h07 from B′'s −4.50 disaster to −0.38. Best S2
cell result of the program: m02 −0.21 (EF). S2 still ZERO closures (wall
moving, standing). The new signal-path fence (s21 > −30 at smoke) zeroed
out entire edit sets on 2 B′ cells that v0 would have "sized" as dead
circuits — B′'s worse median vs v0-B is partly the fence being honest,
partly LLM sampling variance (gf180 LLM-arm noise, again).

## Adjudication delta (the pre-registered falsifiable core)

- **CONTRADICTED structural claims: v0 10/11 graded cells → v1-E ZERO in
  all emitted text examined** (both full diagnoses + prediction prose
  spot-checks across cells). On the same cells v0 confabulated, E now
  reads pins correctly ("gate of NM1 (n3)"), identifies the diode-
  connected mirrors as bias references, and places the degeneration L
  right — the annotation carried perception. h02-E vs h02-v0 is the
  clearest before/after pair on record.
- **BUT diagnosis emission collapsed: 2/13 E cells wrote a diagnosis
  section (v0-B: 11/13).** The longer annotated prompt crowds out the
  diagnose instruction at this model scale; ≥1 output was max-token
  truncated mid-edit. So the CONTRADICTED-rate verdict rests on the
  emitted text available; the compliance regression is itself a v1
  finding (actionable: token budget + instruction placement, or force a
  diagnosis-first schema).
- Residual failure class in the good diagnoses: unfounded VALUE claims
  ("Q is too low", "low-impedance bias path") about quantities not in
  evidence — milder than v0's structural confabulation, still ungrounded.
- Mechanism stories remain the weak layer (e.g., h02's "gate needs AC
  ground" theory); grounding improved, physics insight did not obviously.

## Reading

Perception was the binding constraint on DIAGNOSIS QUALITY (annotation
fixed it), and feedback is the binding constraint on EDIT QUALITY (round-2
wins dominate; the only clean credit needed both). Neither alone closed
anything the null couldn't. The S2 simultaneous-match wall survives all
v1 arms — consistent with it needing either genuine design insight
(capacity: 32B-dense swap is next per user sequencing) or structural moves
beyond single-shot edits (move-library option).

## Layout

```
gpu-leg/results-{B,E,F,EF}.jsonl + designs + adjudication/<spec>/<arm>/[round<r>/]  (verbatim)
armAprime/            budget-matched null (5400 evals/cell): 1/13 (e02)
```

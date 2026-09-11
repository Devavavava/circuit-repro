# CAMPAIGN qwen-editcap-v0 — can Qwen reason from a failed circuit to a topological fix? (DRAFT — awaiting user GO)

Devised 2026-09-11 on user direction: the sizer is a known-good tool, not
the subject. The subject is the MODEL: **identify the situations in which
Qwen-30B, shown a failed sized circuit and its failure evidence, produces a
structural (topology) fix that succeeds — and whether looking at the
failure is causally involved.** Primary output is a SITUATION MAP, not a
single pass/fail.

## Why gf180 + externals anchors are the right laboratory

Every prior edit-capability attempt (E-9/E-11/E-12, bptm45) scored flat
zero, partly because there were no near-positive anchors: editing a dead
circuit gives no gradient, and the 45nm nulls were already strong. The
externals-v0.2 result inverts this: 13 unsolved gf180 cells now have
KNOWN-GOOD anchor topologies (c1/c3/c4) with rich, honest failure records —
misses ranging from razor-thin (s21 −0.02 normalized) to structural (gain
gates 14–20 dB that one stage cannot reach at 3–6 mA, per the physaudit MSG
data). If failure-reasoning capability exists at this model scale, this is
where it is measurable; if Qwen scores zero here, the capability is absent
in the most favorable conditions the program can construct.

## Failure library (box prep, zero new sims)

One item per unsolved cell (13): spec YAML; anchor = the externals leg with
the best worst-margin for that cell (rule, not hand-pick; materialized at
freeze); anchor netlist rendered from tokens (`proposal.rows_to_text`
inverse path); sized-best params; full metrics; margins; binding
constraint; stability advisories. All drawn from
`kaggle/campaigns/externals-gf180-v0/era-ext-9167fd46/` archives.

Pre-registered situation buckets:
- **S1 near-miss** (|worst margin| ≤ 0.5): sizing-reachable suspects — the
  null exists to catch these.
- **S2 structural gain gap**: 900 MHz/GPS cells with s21 gates 14–20 dB at
  3–6 mA (m02 m03 m07 h02 h03 h07) — physaudit says one stage cannot make
  these; a real fix requires added structure (second stage / interstage
  network). The heart of the experiment.
- **S3 wideband** (e08 h08, c4 anchor): s11/ripple binds — feedback/peaking
  structure territory.

## Arms (per cell; sizing recipe byte-identical everywhere)

- **A — sizing-extension null (box, no GPU):** anchor re-sized at the
  MATCHED TOTAL eval budget that B spends across its k edits (matched-total
  discipline per E-13a). Expected to close some S1 cells; that outcome
  labels them "no topology fix needed" in the map — an answer, not a loss.
- **B — evidence edit (GPU):** prompt = spec + anchor netlist + failure
  evidence (metrics, margins, binding constraint, Idd headroom) → Qwen must
  (1) diagnose the failure in words, (2) emit k=3 structural edits in the
  standard netlist dialect, each with a PREDICTED direction/magnitude for
  the binding metric; each edit sized at base budget (2×300; escalation
  3×600 only for the best edit). Edits must differ from the anchor by WL
  hash; duplicates collapse.
- **C — blind-edit ablation (GPU, same kernel run):** identical to B minus
  ALL failure evidence (no metrics/margins/diagnosis — just spec + anchor +
  "propose k structural variants"). Isolates reasoning-from-failure vs
  mere structural diversity. Same budgets.

Per-edit conduction fence (externals-v0 lesson): a 40-eval smoke must show
idd > 0.05 mA before the edit gets its full budget; dead edits count as
failed proposals (recorded, not resized).

## Frozen scoring

- **edit-credit(cell)** = closed by B AND not by A.
- **reasoning-credit** = B beats C on closed-count (paired across the same
  cells) and on median binding-margin delta; reported per bucket.
- **Situation map (primary deliverable):** bucket × {A, B, C} outcomes +
  margin deltas + diagnosis-quality notes → "Qwen can fix X-shaped
  failures; cannot fix Y-shaped ones; Z-shaped were never topology
  problems."
- **Prediction ledger:** per edit, predicted vs measured binding-metric
  direction (calibration of its causal story — distinguishes reasoning
  from lucky diversity even inside B).
- Falsifier: B ≈ C everywhere AND B ≤ A ⇒ diagnose→edit capability absent
  at this scale under maximally favorable anchors; named next levers
  (edit-log FT, larger model tier) are OUT of this campaign's scope.

## Governance

- No guidance injection: prompt inputs are system records + the approved
  round-1 anchors ONLY. No literature pointers, no candidate-family names
  (C2/C5 docs never enter prompts). If Qwen independently reinvents a
  two-stage form, that is a finding, and WL hashes will show it.
- Contamination ledger: inherits externals-v0 declarations; no new
  templates authored here; edits are model-authored (the sanctioned
  E-11-lineage treatment, per the 2026-08-26 motif ruling).
- Nulls first: arm A runs before or alongside GPU legs; era = single origin
  SHA for all arms (GPU leg clones origin ⇒ REQUIRES A PUSH first; 3 local
  commits pending + this pre-reg).
- Store writes: none; results to campaign archive only.

## Cost estimate

Box arm A: 13 cells × ~3.6k evals ≈ hours. GPU leg (B+C interleaved, one
kernel run): ~13 × 6 edits × ~640 evals ≈ 50k evals ≈ 2.5–3.5 h wall + LLM
time — comfortably one leg within weekly quota.

## Execution sequence on GO

1. Freeze: build failure library (box script), materialize anchors +
   buckets into this doc, commit.
2. User push wording → push origin (era SHA).
3. Launch box arm A + GPU leg (B+C); score; archive
   `kaggle/campaigns/qwen-editcap-v0/`.

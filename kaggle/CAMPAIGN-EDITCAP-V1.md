# CAMPAIGN qwen-editcap-v1 — does fixing PERCEPTION and adding FEEDBACK make Qwen's fixes real? (GO 2026-09-11)

User GO ("running 4 and 5 is fine") for the two levers targeting editcap-v0's
adjudicated failure modes: deterministic circuit ANNOTATION (perception) and
VERIFY-REFINE rounds (calibration/side-effect blindness). Same failure
library, same frozen buckets, same adjudication rubric as v0
(kaggle/CAMPAIGN-QWEN-EDITCAP.md). Driver extensions: commit 6f357104
(annotation module hand-verified ground-truth on both anchor families;
signal-path fence s21 > −30 dB added per v0 adjudication finding; meta
predicted-text off-by-one fixed — v0 metas carry the logged bug,
raw_output.txt remains authoritative there).

## Arms (13 cells each, k=3 edits/round, one kernel run, era = origin tip at launch)

- **B′ — v0 replication control:** arm B rerun unchanged (annotate off,
  rounds 1, new fence ON and recorded). Controls LLM sampling noise across
  sessions AND measures the new fence's effect alone.
- **E — annotated evidence edit:** B′ + the deterministic annotation block
  (DEVICE PIN BINDINGS + GRAPH FACTS; graph facts only, no technique words).
- **F — verify-refine:** B′ + rounds=2 (round-2 prompt embeds verbatim
  measured results of round-1 edits; dedup across rounds; escalation of the
  overall best).
- **EF — both.**
- **A′ — budget-matched null for F/EF (box, no GPU):** anchor re-sized at
  the F budget: 2 rounds × 3 × 600 + 1800 = 5400 evals/cell → seeds 3 ×
  budget 1800, no-escalate. (E/B′ compare against v0's arm A at 3600,
  unchanged.)

## Frozen scoring

- Closures per arm vs the matched null (A for B′/E; A′ for F/EF).
- **Annotation effect = E − B′**, ranked: closures → median worst-margin →
  **adjudication-grade distribution**. The falsifiable core: annotation
  must collapse the CONTRADICTED rate (v0: 10/11) — specifically pin-role
  and diode-device misreads must not survive a prompt that states them as
  facts. If E's diagnoses still contradict the annotation block itself,
  the perception failure is deeper than input format (strong evidence for
  the capacity lever / against interface levers).
- **Feedback effect = F − B′** on the same ranking; additionally: round-2
  regression rate (how often round-2 edits are worse than round-1's best —
  measures whether seeing outcomes actually steers).
- **EF vs best(E, F)** for additivity.
- Prediction ledger continues (fixed alignment); calibration compared
  E/F vs v0-B.
- Adjudication (same rubric, same adjudicator) runs on E and F(round 2)
  diagnoses after scoring.

## Governance

Annotation content is machine-derived graph fact ONLY (sanctioned like
sim-health rows; "diode-connected (gate tied to drain)" is a graph fact —
no "current mirror"/"matching network" interpretation words appear).
Arm C (blind) is NOT rerun — v0's C stands as the blind reference.
No store writes; kernel clones origin ⇒ PUSH REQUIRED before GPU launch
(pending commits incl. gpu-leg archive + adjudication + driver + this
pre-reg). Box arm A′ may run pre-push (library/engine unchanged since
79c3a976). GPU estimate: ~8–9 h (4 arms; F/EF are 2-round) — within weekly
quota. Archive: kaggle/campaigns/qwen-editcap-v1/ mirroring v0 layout,
verbatim adjudication trees per arm per round.

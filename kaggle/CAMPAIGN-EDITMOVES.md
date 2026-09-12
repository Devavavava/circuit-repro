# CAMPAIGN editmoves-v0 — selection vs randomness over a valid-by-construction move library (FROZEN 2026-09-13, pre-run)

**MATERIALIZED AT FREEZE:** library kaggle/editmoves.py + driver
kaggle/editmoves_run.py (builder agent + orchestrator completion; commit
below). Nine operators: add_series_L_input, add_shunt_C_input,
add_L_match_section_input, add_cascode_NMOS, add_source_degen_L,
add_shunt_feedback_RC, add_second_stage_CS, add_output_shunt_C,
add_series_L_output. Unit test: 24/24 applied (move, site) pairs across
both anchor families preserve ALL four invariants (round-trip + distinct
WL, DC-block convention, in-topology bias for new gates, device budget).
Validation runs (real ngspice): arm R on cap-e02 (3/3 valid, 3/3 smoke,
best wm s11 −0.14) and cap-m07 (3/3, 3/3, binding delta +0.015). Arm R
seed fixed at 1. No spec-level R/M campaign rows existed at freeze.

**Post-freeze materialization notes (logged, mechanical):** (1) per-cell
RNG seed derives from --seed + cell NAME (sha256), not cell index —
invariant under --only subsetting, strictly more reproducible; (2) driver
DEFAULT seed is 12345 (builder's validation seed); the campaign passes
--seed 1 explicitly per this freeze; (3) site inventories: c1 11
(move,site) pairs, c3 13; add_second_stage_CS correctly self-excludes on
c3 (device budget); (4) builder's negative tests confirm each invariant
rejects its intended violation class.

User GO 2026-09-13 ("setup and run move library test"). Rationale from the
editcap adjudication: the LLM cannot author valid netlists reliably but
names techniques correctly — so make edits VALID BY CONSTRUCTION (generic
composable operators per the nudge-limit directive) and reduce the model's
job to SELECTION. The decisive control is RANDOM selection: if the LLM
cannot beat random over the same menu, its "reasoning" adds nothing beyond
what structural diversity plus the sizer already gives.

## Arms (frozen 13-cell library, budgets/fences as editcap: smoke idd>0.05
mA + s21>−30 dB; base 2×300; escalate best 3×600; k=3 per cell)

- **R — random null (box, no LLM):** seeded uniform draw of k distinct
  applicable (move, site) pairs per cell (seed fixed pre-run: --seed 1;
  seed derived per cell index — reproducible).
- **M — LLM selection (GPU):** prompt = spec + anchor + ANNOTATION block +
  failure evidence + a mechanical MENU of every applicable (move, site)
  with neutral one-line descriptions (no benefit language). Output schema:
  DIAGNOSIS first, then exactly k picks with one-line rationale +
  predicted binding-metric direction/magnitude. Verbatim adjudication
  archive as in editcap.

## Frozen scoring

- move-value = R or M beats the matched sizing null A (3600): do
  valid-by-construction structural moves help AT ALL, even randomly?
- selection-credit = M beats R paired (closures first, then median best
  worst-margin) — the isolated value of the model's choice-making.
- Cell-level credit rule as editcap (closure the matched null lacks).
- Adjudication rubric on M's diagnoses/rationales (CONTRADICTED rate with
  annotation present should stay ~0; rationale-vs-pick coherence is the
  new graded axis).

## Governance

Operators are generic composable primitives (add match section, cascode,
degeneration, shunt feedback, second stage, output match) — no
class-specific macros; every applied move must preserve round-trip
validity, the DC-block convention, in-topology bias for any new gate, and
the ladder device budget (enforced invariants + unit tests at build).
Menu descriptions are mechanical (what is inserted where), not advisory.
Library implementation + exact operator/site inventory are recorded here
at freeze (post-build, pre-run). Store writes: none.

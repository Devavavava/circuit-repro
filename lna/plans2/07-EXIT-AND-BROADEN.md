# WP-EXIT + WP-BROADEN — close the phase, then rotate the scoreboard

**State (iter-3, loop_state.json):** Gate I3 met — curated sizing → 3 feasible
novel designs, curve 967→367. **90 one-constraint-off candidates** await
conversion. §2 polish coded but blocked by a start-point bug; §4 σ relabel
still open. Benchmark: **wifi24 6/6 (solved class)**; gps-l1 0/6
(gain-limited); wideband-sdr 0/6 (match-limited).
**The strategic read:** one more improving turn meets the phase exit
criterion. After that, more wifi24 feasibles are cheap wins that no longer
measure progress — the headline metric must rotate from the wifi24 curve to
the **cross-spec benchmark table**, or the loop Goodharts on a solved spec.

---

## 1. Iteration 4 — the exit turn (§2 + §4 + breadth, ~2 days)

Order inside the turn matters; the curve counts every minute, so closest-first.

* **(a) Debug `size.polish` start-point reconstruction.** Symptom:
  `run_and_extract` → None at a stored `best_params`; the curated path
  reconstructs the same row fine. Fix by routing polish through the *same*
  body/param construction the curated path uses, then add the invariant that
  makes this bug impossible to reintroduce: **replay check** — re-evaluating
  any stored `best_params` must reproduce the stored metrics within repeat-
  probe σ before any polish step is allowed. If replay fails, the row is
  quarantined (label provenance problem), not polished.
* **(b) σ best-of-3 relabel (06-LAST-MILE §4, unchanged)** — must land
  *before* any critic retrain this turn. Store `label_sigma`; downweight 1/σ.
* **(c) Convert the wall:** `g4_search --curated` + `--polish` over the
  one-constraint-off pool **sorted by total violation ascending**, stop-loss
  per candidate (~100 sims); stop the pass when marginal SPICE-min per new
  feasible exceeds the current curve value (keeps breadth from diluting the
  curve the way the --top-15 sweep did, 367→370).
* **(d) Record iter-4** with funnel columns. **Exit check:** iter-4 improving
  + tripwires quiet = two consecutive improving turns → **phase exit met**;
  write the closing FINDINGS entry (04-SELF-IMPROVE §5 format) and declare
  Stage 3 an operating mode.

## 2. WP-BROADEN — the specs that still say no (the next phase, ~1–2 wk)

Both hard specs fail on topology, not sizing — this is `templates.py` + P5
work, exactly the lever that already broke the memorization ceiling once.

* **Gain-boosted families (unlocks gps-l1: S21 ≥ 15 @ Idd ≤ 3):** the
  cascode+tapped ceiling is ~12–14 dB, so single-stage is out. Add archetype
  constructors for **two-stage CS→CS** (first stage tank-loaded, second
  buffered/tapped), **current-reuse** (stacked gm at shared Idd — the spec's
  3 mA cap is the real constraint), and higher-Q tapped ratios. Curated
  sizing must learn the two-stage match map (input match on stage 1 only).
* **Wideband families (unlocks wideband-sdr: S11 over band + ripple ≤ 2):**
  activate the existing `rfb_lna` / `cg_lna` constructors as first-class
  strata + add **shunt-peaked loads** and resistive-feedback+buffer combos.
  These match by feedback, not LC resonance — the failure mode the benchmark
  measured. Wire the `<LNA_WB>` class token end-to-end (it exists in the
  vocab; the WB template row count was 4 — raise to ≥ 30).
* **Sequence:** constructors → label as stratum T vs *both* new specs →
  P5-v3 fine-tune (`<LNA_NB>`/`<LNA_WB>`, winners included) → NDL@256 +
  tripwires → curated sizing per family.
* **Gate B1 (the rotated scoreboard):** `benchmark.py` moves from
  6/6 · 0/6 · 0/6 to **≥ 1 feasible on each of gps-l1 and wideband-sdr**,
  with novelty reported under the frozen protocol. The benchmark table
  replaces the wifi24 curve as the phase headline from here on.

> **Update (2026-08-08):** §1 executed — exit MET (curve 367→187). §2 half
> executed — Gate B1 MET on gps-l1 via P5-v3; wideband-sdr still open. The
> wideband thrust and the NF-harness priority now roll into
> **08-DHRUVA-GOAL.md** (paper-target spec ladder, run under a **blind
> protocol** — read its rules before touching templates.py).

## 3. Deferred, explicit (so they don't leak into the turn)

Loop-A acquisition picks, critic graph+L1 features + NF head, and the
`--score`/`--export-npz` interface leftovers: all real, none on the critical
path to exit or to Gate B1. Revisit when the benchmark stalls — OOD ranking
becomes the lever again precisely when the new WB/gain pools arrive (the
source-shift lesson: new distribution first, then the critic re-earns ρ).

## Acceptance

- [ ] replay check in place; polish validated on ≥ 1 stored near-miss
- [ ] σ ≤ 0.5 under best-of-3; critic retrain only after
- [ ] iter-4 recorded; exit criterion evaluated honestly either way
- [ ] ≥ 8 new gain-boosted + ≥ 8 wideband archetypes constructed and labeled
- [ ] P5-v3 adopted only if NDL@256 ≥ v2 at ≥ inductor ratio, tripwires quiet
- [ ] Gate B1 measured; benchmark.md is the phase scoreboard going forward

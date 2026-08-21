# E8-LADDER-V2 — re-authored goals (DRAFT)

**Status: DRAFT — pending null-filter run + user ruling (2026-08-21 authorization).**
This document re-authors the goals that fell or were deferred in E8-LADDER §8.4,
incorporating the lessons from the null-smoke. It does NOT replace the existing
ladder doc; it is the candidate v2 goal set submitted to the user for the OQ-6
ruling. The scored v2 ladder (if authorized) waits for:

1. The `s22-bandwide` harness branch (Part 1) to merge into main, then sync to
   `engineer`.
2. A null-filter run on the v2 goals (same 150-eval warm-start protocol as §8).
3. The user's ruling on the final scored set.

Every governance rule from E8-LADDER carries forward: nudge policy (E-7 §0),
goldens-green rule, two-line branch law, append-only. No arm beyond the null-filter
is built here.

---

## 0. Lessons from the §8.4 smoke — what broke and why

Four goals survived the null-filter (G1, G8, G9, G10). Seven fell or were N/A:

| original | verdict | root cause |
|---|---|---|
| G2 (S22 ≤ −10, dhruva-s) | FELL — spot artifact | harness reported `s22_db` (spot at f0 = −12.33 dB), not band-wide worst; one sizing trajectory cleared spot, never held it band-wide; goal was ill-posed without `s22_max_db` |
| G3 (S11 −10→−13, dhruva-l1) | FELL — sizing-reachable | stored row at −10.02, but warm local sizing deepened to −13 within 8 evals; the 0.02 dB knife-edge margin was **not** a true structural floor — more sizing headroom existed |
| G4 (S11 −10→−12.5, dhruva-l2) | FELL — sizing-reachable | same cause; cleared at eval 10; 0.03 dB margin misleading |
| G5 (widen band +20%, dhruva-s) | N/A — grid-bound | S11 measurement grid is [f_lo, f_hi] in the spec; changing the band means changing the spec's `f_lo`/`f_hi`, not just the goal's target — the harness evaluates S11 over whatever grid the loaded spec carries; no API to override the grid per-eval in the current null-runner |
| G6 (NF 3.5→3.0 at fixed Idd, dhruva-s) | FELL — mis-authored | reached NF = 1.40 dB, not 3.5; the base spec's NF floor is gated at 3.5 but the topology already beats it by 2.1 dB; the "delta" did not extend the reached point |
| G7 (Idd 13→10, dhruva-s) | FELL — sizing-reachable | dhruva-s carries +3.8 dB S21 headroom (33.81 vs 30 min); sizing trades that headroom for Idd reduction; G8 at the same cut on dhruva-l5 (only +2.7 dB headroom) resisted — this is the measured discriminator |
| G11 (IIP3 ≥ −7.4, dhruva-l5) | N/A — two-tone unsupported | `iip3_dbm` is `status: unsupported` in the spec; the fast harness (op+sp+noise) does not run two-tone; the goal is valid but the harness path is not open yet |

**Key discriminator (G7 vs G8):** the Idd-cut goal is structural only where **gain
headroom is thin**. G7 fell because dhruva-s had +3.8 dB surplus; G8 resisted on
dhruva-l5 with only +2.7 dB. The G8 threshold implies a structural floor
somewhere between 2.7 and 3.8 dB gain headroom — any new Idd-cut goal must sit on
a task with headroom below that range.

**G3/G4 floor measurement:** warm sizing from the anchor reached −13 / −12.5 dB
within 8–10 evals on l1/l2. That gives us a measured lower bound on what local
sizing can reach: at least −13 dB on l1. For a re-authored S11 goal to resist
sizing, the cut must exceed this measured sizing reach. Using −15 dB (2 dB beyond
the measured sizing floor) as the new target provides that margin with a small safety
factor.

---

## 1. Re-authored goal set (v2)

Seven re-authored goals (G2'–G7') plus two new ideas (N1, N2). Goals that
survived v1 (G1, G8, G9, G10) are **not repeated here** — they carry forward
unchanged.

All goals evaluable with the fast harness (op + sp + noise, ≈ 2 ngspice calls/eval)
unless flagged. `s22_max_db` requires the Part-1 harness branch to be merged;
noted per goal.

### Goal table

| # | base task | delta | measured evidence | expected structural class (analyst-only) | sim cost/eval | harness dep |
|---|---|---|---|---|---|---|
| **G2'** | dhruva-s-t2-a | **add s22_max_db ≤ −10 band-wide** | reached flagship: s22_db (spot) = −12.33, s22_max_db (band) = −10.61 (Part 1 measurement); a class-A single-ended output stage is not output-matched; sizing a matched input does not create output match; the band-wide metric now gates correctly | add output matching network / buffer | 2 | **needs Part-1 harness merge** |
| **G3'** | dhruva-l1-t2-a | **S11 tighten −10 → −15 dB band-wide** (−5) | warm sizing reached −13 in 8 evals — measured sizing floor; −15 is 2 dB past that floor with margin; reached S11_max = −10.019 (current live ref); a −5 dB improvement over the live ref is past what single-match local sizing can deliver | add / re-order second matching section | 2 | none |
| **G4'** | dhruva-l2-t2-a | **S11 tighten −10 → −14.5 dB band-wide** (−4.5) | warm sizing reached −12.5 in 10 evals — measured sizing floor; −14.5 is 2 dB past that floor; reached S11_max = −10.031 | add / re-order second matching section | 2 | none |
| **G5'** | dhruva-s-t2-a | **band widening: S11 ≤ −10 over 0.9–2.7 GHz (±20% beyond current [1.1, 2.5] grid)** | current S11 = −11.26 max over [1.1, 2.5] GHz; a narrowband tuned match degrades rapidly off f0; widening the spec grid from [1.1, 2.5] to [0.9, 2.7] GHz exposes the match failure; a broadband (feedback / staggered-tuned) structure is needed | broadband match (feedback or staggered) | 2 | **prerequisite: spec-grid change (see §2 below); NOT implemented here — documented prerequisite** |
| **G6'** | dhruva-l5-t2-a | **cut Idd 13 → 10.5 mA at fixed S21 ≥ 22.3, NF ≤ 2.5** (same as G8, now recast as G6' for numbering continuity) | dhruva-l5 gain headroom = +2.7 dB (24.99 vs 22.3 min); G8 already RESISTED in v1 null at the same delta — confirmed structural; Idd binding at 12.92 mA; 9-device cheapest deck | different output class / current-reuse | 2 | none |
| **G7'** | dhruva-l5-t2-a | **cut Idd 13 → 10 mA at fixed S21 ≥ 22.3, NF ≤ 2.5** (deeper cut than G6' / G8) | G8 (−2.5 mA cut) resisted; deeper cut (−3 mA) tightens the structural ask; dhruva-l5 gain headroom of +2.7 dB is below the G7/G8 discriminator threshold; G8's resistance at −2.5 mA provides ceiling evidence that −3 mA is further from sizing reach | different output class | 2 | none |
| **G11'** | dhruva-l5-t2-a | **add IIP3 ≥ −7.4 dBm** (same target as v1 G11; now viable with plans2/23 two-tone rung wired) | the D5 wall (plans2/16-WP-LIN, FINDINGS §44.4): class-A output current-swing caps IIP3 by 16.8 dB ahead of headroom; measured floor registered in E-7; tier-3 path now wired (`status: measured` + `enrich_iip3`) per plans2/23; **sim cost flagged: 4–8× a base eval** | different output-stage class (the E-7 wall) | **SLOW: ~4–8× (two-tone/HB); cost-flagged** | **spec change needed: flip iip3_dbm to `status: measured` in dhruva-l5.yaml** |

### New goal ideas (N1, N2)

| # | base task | candidate delta | harness support? | verdict |
|---|---|---|---|---|
| **N1** | dhruva-s-t2-a | **S21 flatness under supply droop**: measure s21_ripple_db when VDD is swept ±10% from nominal | NOT supported: the fast harness fixes VDD in the deck; a supply-droop measurement requires a parametric DC sweep that is a separate ngspice call not currently wired into extract.py or env.py; would cost ≥1 extra ngspice call per eval | **DEFERRED — prerequisite missing; documented as a future extension if the harness is extended** |
| **N2** | dhruva-l5-t2-a | **gain-flatness tighten s21_ripple_db ≤ 1.5 dB** (from G9's 3 dB bound — the current ripple is 15.18 dB; G9 set 3 dB as the first cut; 1.5 dB is a harder version once 3 dB is reached) | supported (s21_ripple_db in fast harness); G9 already resisted at 3 dB; a null-filter at 1.5 dB is needed; if G9 is solved, N2 becomes the natural next step; **not pre-registered here — depends on G9 solution existing** | **CONDITIONAL — add after G9 is solved; noted for the ruling** |

---

## 2. Prerequisite: G5' spec-grid change (documented, NOT implemented here)

**What the limitation is.** The E8-LADDER §8.4 verdict for G5 was "N/A grid-bound".
The specific limitation: `engineer/env.py` creates a `Spec` object from the
base task's YAML (`dhruva-s.yaml`), and the S11 measurement in `extract.py` sweeps
from `spec.band['f_lo']` to `spec.band['f_hi']` — currently `[1.1e9, 2.5e9]` GHz.
The null-runner mutates the spec's constraint threshold in-memory (changes the
`max` on `s11_max_db`) but **not** the band grid. To evaluate G5', the band grid
itself must change: the spec's `f_lo`/`f_hi` must be set to `[0.9e9, 2.7e9]` GHz,
or a new derived task must carry a modified spec.

**The minimal fix.** Two options:
- **(a) In-memory band mutation in the null-runner**: extend the null-runner to
  mutate `spec.raw['band']['f_lo']` and `spec.raw['band']['f_hi']` alongside the
  constraint threshold. This requires no new file, only a one-line addition in the
  spec-mutation step of the null-runner. Small enough to implement in Part 1's
  scope, but G5' was not in Part 1's task scope (the task specified only
  `s22_max_db`), so it is deferred.
- **(b) New YAML spec** `dhruva-s-wide.yaml` with `f_lo: 0.9e9`, `f_hi: 2.7e9`,
  and everything else identical. Cleaner for the scored tier (a registered task
  with its own ref_ts) but requires a new task row in `tasks.py`.

**Recommendation**: option (a) for the null-filter (cheap, keeps containment);
option (b) for the scored tier. **Not implemented in this branch — user ruling
needed on which path to take.**

---

## 3. Per-goal detail

### G2' — band-wide S22 ≤ −10 dB on dhruva-s

**Base:** dhruva-s-t2-a (S21 ≥ 30, S11_max ≤ −10, Idd ≤ 13).
**Delta:** add `s22_max_db: {max: -10}` to the spec (in-memory mutation; no
existing spec file changes).
**Evidence it resists sizing:**

- The v1 G2 smoke cleared on spot value (`s22_db` = −8.83 at the anchor → a small
  sizing change brought it to −10 spot). That was the spot artifact: spot = −12.33
  at the flagship, but band-wide = −10.61 (measured by Part 1 on the dhruva-s
  flagship in the wt-s22 worktree).
- The band-wide metric gates correctly: the flagship barely passes (−10.61 ≤ −10),
  with only 0.61 dB margin. Local sizing must maintain S22 ≤ −10 across all of
  [1.1, 2.5] GHz — a broadband output-match requirement — while keeping S11, S21,
  and Idd constraints. A class-A single-ended output stage is not output-matched by
  construction; sizing the input match does not create output impedance match.
- No dhruva spec currently gates output match, so the null-filter will be the first
  measurement of whether sizing-only can hold output match simultaneously with all
  other constraints.

**Ceiling evidence:** no dhruva circuit in the corpus has been observed satisfying
a band-wide S22 ≤ −10 constraint at the dhruva-s topology class (18 devices, no
output matching network). The class-A output's output impedance is set by gds +
load; it does not track 50 Ω across the 1.1–2.5 GHz range by sizing alone.

**Sim cost:** 2 ngspice calls/eval (op + sp; NF gated separately). **Harness dep:**
requires Part-1 `s22-bandwide` merge before the null-filter can run; `s22_max_db`
is not emitted by the current engineer-branch extract.py.

---

### G3' — S11 ≤ −15 dB band-wide on dhruva-l1

**Base:** dhruva-l1-t2-a (S11_max ≤ −10, S21 ≥ 25.4, Idd ≤ 13).
**Delta:** tighten `s11_max_db: {max: -15}` (from −10; −5 dB cut).
**Evidence it resists sizing:**

- The v1 G3 smoke had sizing reach −13 in 8 evals from the stored −10.019 row.
  The measured sizing floor is −13 dB.
- G3' sets the target at −15 dB, which is 2 dB beyond the measured sizing floor and
  5 dB below the live reference. The 2 dB safety margin accounts for uncertainty in
  the 150-eval warm sizing estimate (the null ran for 150 evals total; a longer run
  might push slightly further). Setting −15 keeps the goal clearly outside the
  measured reach.
- FINDINGS §39 "S11 is knife-edge": the match degrades rapidly as device sizing
  moves away from the resonance condition; a 5 dB band-wide deepening requires
  adding a matching section, not tuning an existing one.

**Ceiling evidence:** the dhruva-l1 single-match topology's sizing reach is −13 dB
(measured). A second matching section would be needed to reach −15 dB over the
full [1.1, 2.5] GHz grid.

**Sim cost:** 2 calls/eval. No harness dep.

---

### G4' — S11 ≤ −14.5 dB band-wide on dhruva-l2

**Base:** dhruva-l2-t2-a (S11_max ≤ −10, S21 ≥ 22.3, Idd ≤ 13).
**Delta:** tighten `s11_max_db: {max: -14.5}` (from −10; −4.5 dB cut).
**Evidence it resists sizing:**

- v1 G4 smoke: sizing reached −12.5 in 10 evals from −10.031 live ref.
  Measured sizing floor = −12.5 dB.
- G4' target = −14.5 dB, which is 2 dB beyond the floor. The slightly shallower
  cut vs G3' (4.5 vs 5 dB) reflects dhruva-l2's shared topology with l1 but
  different f0 (l2 is the L2 frequency), where the sizing headroom may differ.

**Ceiling evidence:** same as G3' — a single-match topology's sizing floor is now
directly measured at −12.5 on l2.

**Sim cost:** 2 calls/eval. No harness dep.

---

### G5' — band-widening on dhruva-s (prerequisite: spec-grid change)

**Base:** dhruva-s-t2-a.
**Delta:** S11 ≤ −10 over [0.9, 2.7] GHz (±20% beyond current [1.1, 2.5] GHz grid).
**Evidence it resists sizing:** a narrowband LC resonant match that holds S11 ≤ −10
over 1.1–2.5 GHz (1.4:1 ratio) cannot hold it over 0.9–2.7 GHz (3:1 ratio) without
a qualitatively different match architecture (multi-section, distributed, or
feedback). The Q of a single LC match scales as f0/BW; stretching BW by 2× at
fixed Q forces the match to fail.
**Prerequisite:** spec-grid change (§2 above). Not null-filterable without it.
**Sim cost:** 2 calls/eval once the grid change is implemented.
**Status: PENDING — prerequisite must be ruled by user before null-filter runs.**

---

### G6' / G7' — Idd cut on dhruva-l5 (the G8 discriminator applied)

**G6'** is identical to G8 (Idd ≤ 10.5, S21 ≥ 22.3 on dhruva-l5) — it is renamed
for continuity; G8 already RESISTED so G6' is a direct carry-forward, pending
re-verification in the v2 null-filter.

**G7'** extends the cut: Idd ≤ 10.0 mA at fixed S21 ≥ 22.3, NF ≤ 2.5 on dhruva-l5.
- Gain headroom = +2.7 dB (24.99 − 22.3). G8 (−2.5 mA cut) already resisted sizing.
- The discriminator (G7 fell on dhruva-s because +3.8 dB headroom could be traded;
  G8 resisted on dhruva-l5 at +2.7 dB) establishes that the structural floor is
  somewhere between 2.7 and 3.8 dB available headroom. At +2.7 dB and −3 mA cut,
  the required efficiency improvement (from 12.92 mA to 10.0 mA at fixed S21) is
  larger than G6'/G8, and the gain headroom cannot be traded further (already at
  minimum). Expected to resist on the same class-of-argument as G8.
- Null-filter is needed to confirm G7' also resists (it is a stronger ask than G8).

**Sim cost:** 2 calls/eval each. No harness dep.

---

### G11' — IIP3 ≥ −7.4 dBm on dhruva-l5 (tier-3, plans2/23 pathway)

**Base:** dhruva-l5-t2-a (S21 ≥ 22.3, S11_max ≤ −10, Idd ≤ 13, NF ≤ 2.5).
**Delta:** add `iip3_dbm: {min: -7.4, status: measured}`.
**Evidence it resists sizing:**

- The D5 wall (plans2/16-WP-LIN §3, FINDINGS §44.4): a class-A output stage's IIP3
  is capped by the current-swing limit: IIP3 = IP3_cap − 16.8 dB (measured margin
  head; see WP-LIN). The dhruva-l5 class-A single-ended stage has no output class
  headroom; the cap is the structural wall E-7 was designed to breach.
- The target −7.4 dBm is the paper's registered floor for this band; sized at the
  E-7 flagship (dhruva-l5 best point) the class-A output fell 16.8 dB below it.
- plans2/23-IIP3-RUNG.md: the `status: measured` pathway is wired in `spec.py`
  (D5b) and `size.py` (`enrich_iip3`); the two-tone deck is validated (S44 replay
  in `_validate_iip3_rung.py`).

**Implementation required before null-filter:**
1. Flip `iip3_dbm: {min: -7.4, status: unsupported}` →
   `iip3_dbm: {min: -7.4, status: measured}` in `lna/specs/dhruva-l5.yaml`.
   This is a **user ruling** (plans2/23 §5 rule: spec status flips require a
   user ruling); not changed here.
2. The null-filter runner must call `size.enrich_iip3` (the two-tone path) at the
   anchor point to confirm whether the reached topology passes or fails the IIP3
   floor at its stored params.

**Sim cost: SLOW** — two-tone / HB, ≈ 4–8× a base eval. G11' is cost-flagged.
If the ladder budget cap is 600 evals/arm, and IIP3 evals cost 6× a base eval,
the effective budget per arm is ~100 structural evals — viable for a reachability
measurement but tighter than G1/G8/G9/G10.

---

## 4. The G8 discriminator — measuring the gain-headroom structural floor

A quantitative summary of the v1 smoke's key finding:

| goal | task | Idd cut (mA) | gain headroom (dB) | v1 result |
|---|---|---|---|---|
| G7 | dhruva-s | −3 (13→10) | +3.8 (33.81−30) | FELL (sizing-reachable) |
| G8 | dhruva-l5 | −2.5 (12.92→10.5) | +2.7 (24.99−22.3) | RESISTED |
| G6' | dhruva-l5 | −2.5 (same as G8) | +2.7 | carry-forward RESIST (pending re-verify) |
| G7' | dhruva-l5 | −3 (12.92→10) | +2.7 (same) | EXPECTED RESIST (deeper cut, same low headroom) |

The structural floor for Idd-cut goals lies between 2.7 and 3.8 dB of gain
headroom: above it, sizing trades headroom for current; below it, a different
output-class structure is required. New Idd-cut goals should target tasks where
gain headroom is ≤ 2.7 dB to stay above the structural floor.

---

## 5. V2 open questions (final goal set = user ruling; null-filter round after harness merge)

| OQ | question | resolution path |
|---|---|---|
| **OQ-V1** | **Should G2' be in the v2 null-filter or deferred?** G2' needs the Part-1 `s22-bandwide` harness merge. If the merge is fast, G2' runs with the others; if it is delayed, the null-filter can proceed with G3'/G4'/G6'/G7' and G2' follows. | User ruling on merge timeline. |
| **OQ-V2** | **G5' prerequisite: option (a) in-memory band mutation vs option (b) new YAML spec?** The spec-grid change is small but requires a design decision about whether G5' is a registered task or an ad-hoc in-memory eval. | User ruling. Recommendation: (a) for null-filter, (b) for scored tier. |
| **OQ-V3** | **Should G11' run in the same null-filter round or separately?** The two-tone path is 4–8× slower; running it concurrently with the fast goals can block the fast null-filter from returning. | User ruling on concurrency discipline. |
| **OQ-V4** | **N1 (supply-droop S21 flatness): should the harness be extended to support it?** The extension is one extra parametric DC sweep in `extract.py` / `build_deck`. If the user wants N1 on the ladder, the extension must be implemented before its null-filter. | User ruling on scope. |
| **OQ-V5** | **N2 (ripple ≤ 1.5 dB): add to v2 now, or defer until G9 is solved?** The goal is valid and harness-supported but requires G9 (ripple ≤ 3) to be solved first to have an anchor point. | Recommendation: defer to a v2.1 or add conditionally. |
| **OQ-V6** | **Are G3'/G4' deltas (−15 / −14.5 dB) calibrated correctly?** The 2 dB safety margin over the measured sizing floor is a judgment call. If the null-filter shows sizing can reach further (e.g., −14 on l1), the target may need tightening to −16 dB. | The null-filter itself resolves this; no pre-ruling needed. |

---

## 6. Summary: v2 candidate goal table

Goals that survive from v1 (unchanged): **G1, G8, G9, G10**.
Re-authored goals (this doc): **G2', G3', G4', G5' (prereq), G6', G7', G11' (prereq)**.
New ideas: **N1 (deferred), N2 (conditional)**.

**Fast-harness goals (null-filterable immediately or after Part-1 merge):**

| goal | base | delta | null-filterable? | carry-forward from v1? |
|---|---|---|---|---|
| G1 | dhruva-l1 | S21 ≥ 30 (was +4.6) | yes | yes (RESISTED v1) |
| G2' | dhruva-s | s22_max_db ≤ −10 | after Part-1 merge | re-authored G2 |
| G3' | dhruva-l1 | S11 ≤ −15 (was −13) | yes | re-authored G3 |
| G4' | dhruva-l2 | S11 ≤ −14.5 (was −12.5) | yes | re-authored G4 |
| G5' | dhruva-s | S11 ≤ −10 over [0.9, 2.7] GHz | after spec-grid change | re-authored G5 |
| G6' | dhruva-l5 | Idd ≤ 10.5 mA | yes | G8 carry-forward |
| G7' | dhruva-l5 | Idd ≤ 10.0 mA | yes | re-authored G7 |
| G8 | dhruva-l5 | Idd ≤ 10.5 mA at S21 ≥ 22.3 | yes | yes (RESISTED v1) |
| G9 | dhruva-l5 | +ripple ≤ 3 | yes | yes (RESISTED v1) |
| G10 | dhruva-s | +ripple ≤ 3 | yes | yes (RESISTED v1) |
| G11' | dhruva-l5 | IIP3 ≥ −7.4 | after spec flip + enrich_iip3 wired | re-authored G11 |

**The user's OQ-6 ruling on the final scored set is the gate.** Until then this
document is a DRAFT; nothing is scored under it.

---

<!-- ================================================================= -->
<!-- POST-HOC OUTCOME BELOW — appended AFTER the v2 null-filter run.   -->
<!-- Everything above this line is the DRAFT committed for the user's   -->
<!-- ruling; nothing above was informed by any v2 eval.                 -->
<!-- ================================================================= -->

## 7. V2 null-filter @ scored budget (post-hoc — appended 2026-08-21)

**Run:** sizing-only warm-anchored null, **600 evals per goal** (N = 3 seeds,
seeds 1–3, PYTHONHASHSEED=0), plus **G9 @ 1200 evals** (double budget, structural
read). Runner: `/home/dpatni/.claude/jobs/a8f610e5/tmp/nullv2_run.py`; results:
`/home/dpatni/.claude/jobs/a8f610e5/tmp/nullv2_results/nullv2_<goal>_s<seed>.json`.

**Methodology:** identical warm-anchored null protocol to E8-LADDER §8.4 (Scored
results), but run at the **scored budget of 600 evals** per the budget-scaling
lesson: the 150-eval null from §8.4 did not survive scaling (G1/G8/G10 fell to
sizing-only at 600 evals). All v2 goals must be null-filtered at the scored budget.

**G11' skipped:** pending user spec-flip ruling (iip3_dbm status: unsupported →
measured in dhruva-l5.yaml required before the null can run).

### Verdict table (warm-started null, seeds 1–3, 600 evals; G9 @ 1200 evals)

| # | base task | delta | base-feas @ anchor | anchor clears delta? | seeds that solve | first solve @ eval | **verdict** |
|---|---|---|:--:|:--:|---:|---:|:--|
| **G2'** | dhruva-s | s22_max_db ≤ −10 band-wide | ✔ | no | 0/3 | — | **RESISTED** |
| **G3'** | dhruva-l1 | S11 ≤ −15 band-wide | ✔ | no | 1/3 | s2 @ 507 | **FELL** (sizing-reachable at 600 evals) |
| **G4'** | dhruva-l2 | S11 ≤ −14.5 band-wide | ✔ | no | 0/3 | — | **RESISTED** |
| **G5'** | dhruva-s | S11 ≤ −10 over [0.9, 2.7] GHz | ✔ | **YES** (3/3) | 3/3 | all @ eval 1 | **FELL — MIS-AUTHORED** (anchor clears; dhruva-s already holds S11 = −10.86 over [0.9, 2.7] GHz) |
| **G6'** | dhruva-l5 | Idd ≤ 10.5 @ S21 ≥ 22.3 | ✔ | no | 1/3 | s3 @ 226 | **FELL** (G8's 150-eval resistance did not survive budget scaling to 600 evals) |
| **G7'** | dhruva-l5 | Idd ≤ 10.0 @ S21 ≥ 22.3 | ✔ | no | 1/3 | s3 @ 389 | **FELL** |
| **G9** | dhruva-l5 | s21_ripple_db ≤ 3 | ✔ | no | 0/3 | — | **RESISTED** @ 1200 evals (stays structural at double budget) |

**Headline: 2/6 v2 goals resist at the scored 600-eval budget (G2', G4').
G9 stays structural at 1200 evals.** G11' not yet run (pending ruling).

### Per-cell detail (evals-to-solve where FELL)

| goal | seed 1 | seed 2 | seed 3 |
|---|---|---|---|
| G2' | not solved | not solved | not solved |
| G3' | not solved | SOLVED @ 507 evals (0.100 spice-min) | not solved |
| G4' | not solved | not solved | not solved |
| G5' | SOLVED @ 1 eval (anchor clears; MIS-AUTHORED) | SOLVED @ 1 eval | SOLVED @ 1 eval |
| G6' | not solved | not solved | SOLVED @ 226 evals (0.039 spice-min) |
| G7' | not solved | not solved | SOLVED @ 389 evals (0.085 spice-min) |
| G9 @1200 | not solved | not solved | not solved |

### What the v2 null caught

**G5' MIS-AUTHORED — DROP.** The in-memory band mutation to [0.9, 2.7] GHz
reveals that the dhruva-s anchor already achieves s11_max_db = −10.86 dB over
the wider band (measured live at the anchor point). The narrowband LC resonant
match is coincidentally broad enough to hold S11 ≤ −10 over this wider span at
the current sizing. The goal's premise (that a 3:1 BW ratio requires a qualitatively
different match) was correct in principle but wrong in measurement: the current
topology already satisfies it. Goal needs a tighter S11 target (e.g. ≤ −15) over
the wider band, or a further-widened grid, to be a genuine structural ask.

**G3' FELL to sizing at 600 evals** (s2 solved @ eval 507). The v1 §8.4 null
had measured the sizing floor at −13 dB in 8 evals at 150-eval budget; the
v2 target was −15 dB (2 dB beyond). At 600 evals the CMA-ES finds a sizing path
to −15 dB on seed 2. The 2 dB safety margin was insufficient for the scored budget.
A larger delta (e.g. −17 dB) may resist — this is now a measured datum not a
prediction.

**G6' FELL (1/3)** — the G8 carry-forward. G8 RESISTED at 150 evals in the v1
null; at 600 evals the optimizer finds a sizing solution on seed 3 (@ eval 226).
The gain-headroom discriminator still holds qualitatively (dhruva-s Idd cuts fell
faster), but the 10.5 mA level is sizing-reachable at the scored budget on dhruva-l5.

**G7' FELL (1/3)** — the deeper Idd cut (−3 mA) is also sizing-reachable at 600
evals (seed 3 @ eval 389). Both G6' and G7' fell, indicating that the Idd-cut goal
family on dhruva-l5 at these delta magnitudes does not hold at the scored budget.

**G9 RESISTED at 1200 evals (0/3 seeds).** The ripple-≤-3 goal stays structural
at double the scored budget. This is the cleanest structural signal in the v2 round:
a 15.18 → 3 dB ripple cut on dhruva-l5 cannot be sized, even at 1200 evals.

### Goals that survive the v2 null-filter at the scored budget

**Structural goals from v2: G2' (s22_max_db ≤ −10, dhruva-s), G4' (S11 ≤ −14.5,
dhruva-l2).** These join the surviving v1 structural goal G9 (ripple ≤ 3, confirmed
structural at 1200 evals) as the v2 candidate ladder core.

**Fell / mis-authored (documented, dropped from ladder score):**
- G3' (S11 ≤ −15, dhruva-l1): sizing-reachable at 600 evals — needs larger delta
- G5' (band-widening to [0.9, 2.7] GHz): mis-authored — anchor already clears
- G6' (Idd ≤ 10.5, dhruva-l5): sizing-reachable at 600 evals — G8 did not survive budget scaling
- G7' (Idd ≤ 10.0, dhruva-l5): sizing-reachable at 600 evals

**G11' deferred:** pending user spec-flip ruling (iip3_dbm status flip).

**The final v2 goal set is the user's ruling.** This section provides the
null-filter evidence; no scored run is authorized under it.

### Scope limit (binding, inherited from E8-LADDER §8.4 / E-6 §7 / E-7 §4.3)

This null shows only that G2' and G4' resist a 600-eval warm local sizing null
at N = 3 seeds. It does not prove they need structure at unbounded budget, and it
confirms nothing about the throughput hypothesis or the falsifier — those are the
scored tier.

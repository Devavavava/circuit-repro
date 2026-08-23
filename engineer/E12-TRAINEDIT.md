# E12-TRAINEDIT — trained editors: learned priors + spec-conditioned regrowth (pre-registration DRAFT)

**Status: GO (user, 2026-08-23) — phases execute sequentially with review
between (P0+P1 → P2 → P3); §12 open items resolve by the pre-registered rules,
outputs recorded before the P3 freeze. FRESH task ruled: 5G n78 LNA,
3.4–3.6 GHz, 50 Ω source, dhruva-class power/NF limits (band-transfer axis;
ism58 excluded as main-touched).** Engineer line (ROADMAP §7 direction 1;
E-11 falsifier destination). All standing governance carries forward:
goldens-green before/after every landing, engineer never writes under `lna/`,
append-only stores and edit log, matched TOTAL budgets, user rulings for any
spec/protocol/budget change.

Ruling basis: user 2026-08-23 — combine option 1 (learned move priors) and
option 2 (goal-conditioned regrowth) as one campaign with two treatment arms;
add an **easy tier** to bank successful edit trajectories (currently the
29,090-row edit log contains zero solves); experiment lives on **engineer**
(v7 stays a read-only cross-line import; trained editor checkpoints live under
`engineer/`); **memorization must be designed out and measured**, not assumed
away.

---

## 0. Motivation

E-11: untrained v7 suffix-regrowth scored 0/6 where sizing-only and hand
primitives also scored 0/6; falsifier MET. Diagnosis: the generator proposes
hundreds of raw sequences but realization collapses them to 57–104 distinct
topologies per cell — the same pool size as the hand repertoire (E-9 D1). The
model was trained to emit whole circuits, not to repair one. E-12 tests
whether *training* fixes that, with two signals: what edits succeed (C1, from
the edit log) and what circuits meet specs (C2, from the labeled store).

## 1. Hypothesis (stated before any number is seen)

> **An editor fine-tuned from v7 — on contrastive edit trajectories (C1) or on
> spec-conditioned store labels (C2) — solves HELD-OUT and FRESH goals that
> sizing-only, hand primitives, and the untrained editor all leave at zero.**

The scoreboard claim is **transfer**: performance on goals whose data the
training never saw. Dev-set-only wins are explicitly interpreted as
memorization (§8).

## 2. Design overview — three phases

- **P1 (banking):** run the existing two-stage arms on an EASY goal tier whose
  targets are provably in-reach, to populate the edit log with successful
  (state → edit → outcome) trajectories. Training data, NOT scoreboard.
- **P2 (training):** one shared fine-tuning pipeline, two checkpoints:
  **C1** = contrastive priors (positives: P1 solves + high-gate survivors;
  negatives: sampled gate failures), **C2** = spec-token-conditioned regrowth
  trained on answer-excluded store labels. Both warm-start from
  `ft_p5v7_v2.pth`, CPU, hyperparameters frozen at GO.
- **P3 (scored):** arms C1 and C2 under the frozen E-11 two-stage machinery on
  DEV + HELD-OUT + FRESH goals, against banked E-11 baselines (plus fresh A/B
  baselines only where none are banked).

## 3. Anti-memorization fences (binding)

1. **Answer exclusion.** No training row (store label, trajectory, or
   sequence) whose topology passes any evaluation goal's extended spec may
   enter training. Enforced by a zero-sim filter script; the excluded list is
   committed with the training manifest.
2. **Leave-base-task-out.** `dhruva-l1` is HELD OUT entirely: no l1 rows,
   logs, or labels in training. Its goals (G1'', H2) are scored as transfer.
3. **Fresh-task gate.** One task per G0-FAIRNESS fresh-task rules (different
   band / source impedance / power class, built in-memory; authored with user
   approval at GO). Contamination ledger on every run declares both
   checkpoints' full training manifests.
4. **Memorization is measured, not assumed:** the DEV-minus-HELD-OUT solve gap
   is a first-class reported metric. DEV wins with HELD-OUT zeros = the
   memorization outcome, reported as such (this is the user's stated worry
   made falsifiable).

## 4. Goal sets

**TRAIN-EASY (P1; training data only, never scoreboard).** Two goals per
training base task; targets set by rule: *a value demonstrably achieved by a
banked base-feasible run or measurement of that base task* (evidence cited),
finalized by a zero-sim calibration script at GO:

| id | base task | delta (provisional) | evidence |
|---|---|---|---|
| E1 | dhruva-s  | `s21_db ≥ 30.5` | instrumented store design at 30.66, base-feasible |
| E2 | dhruva-s  | `s22_max_db ≤ −3.5` | measured −3.67 / −9.06 on base-feasible designs |
| E3 | dhruva-l2 | `nf_db ≤ 1.9` | E-11 null run reached 1.71 |
| E4 | dhruva-l2 | `s21_db ≥ 26` | base-passing store rows at 26.8–35.8 |
| E5 | dhruva-l5 | `s11_max_db ≤ −11` | E-11 null run reached −11.29 |
| E6 | dhruva-l5 | `idd_ma ≤ 12` | base-passing store rows at 10.7–11.8 |

P1 runs: arms B and C (edit-producing arms only), seeds 1–2, B=600 each →
24 cells, ~14,400 counted evals. Every proposal logged (the point of P1).

**DEV (scored; banked E-11 A/B/C baselines reused):** G2'', G13, G9, G7'',
G12 — the five E-11 goals on training base tasks.

**HELD-OUT (scored transfer):** G1'' (dhruva-l1 + `s21_db ≥ 33`; certificate
`ace8383c`; banked E-11 baselines) and **H2** = dhruva-l1 + `nf_db ≤ 1.25`
(certificate: one base-passing store row at 1.22; needs fresh A/B baselines
and a full-budget null filter in P0).

**FRESH (scored transfer):** one G0-FAIRNESS-compliant task + one goal on it,
authored at GO (user approval); A/B baselines run fresh.

## 5. Training (P2, shared pipeline)

- Warm-start both from `ft_p5v7_v2.pth` (read-only import from `lna/out/`);
  checkpoints written to `engineer/out_editor/` (new, engineer-owned).
- **C1 (priors):** fine-tune on (anchor-prefix → regrown-suffix) pairs from
  the edit log, loss-weighted contrastively: positives = P1 solving edits +
  survivors that improved L1 objective; negatives = L0/realize failures.
  Answer exclusion applies (no trajectory from a scored goal's solution).
- **C2 (conditioning):** prepend coarse spec tokens (binned NF / gain / match
  / current classes derived from base-spec limits — a fixed public binning
  rule, no per-goal tuning) to store-label sequences (answer-excluded, l1
  excluded); at proposal time the evaluation goal's own bin prefix is used.
- Both: CPU, PYTHONHASHSEED=0, fixed seeds; hyperparameters (epochs, lr,
  early-stop rule) frozen at GO after a dry-run epoch; training manifests
  (exact row lists, SHA of every input) committed.

## 6. Arms & budgets (P3, matched TOTAL = B per cell)

Machinery byte-identical to E-11 (k/m, gates, D1 rollover, frozen sampling
constants temp 0.7 / max_new 256; class token per base task). Arms **C1** and
**C2** on DEV + HELD-OUT + FRESH (7–8 goals × 2 arms × seeds 1–3, B=600;
G9 1200). Baselines: banked E-11 A/B/C for DEV + G1''; fresh A/B (seeds 1–3)
for H2 and FRESH only. Edit logging continues for every proposal.

## 7. Metrics

As E-11 §6 per cell, plus: solves split DEV / HELD-OUT / FRESH per arm;
**dev-minus-held-out gap**; distinct-realized pool size per cell (did training
widen the D1 bottleneck?); realization rate vs untrained arm C (banked).
PRIMARY remains SPICE-minutes to first feasible on any solved goal.

## 8. Falsifier (pre-stated)

> **If neither C1 nor C2 solves any HELD-OUT or FRESH goal that its A/B
> baselines leave unsolved, then editor training at this data scale fails the
> transfer bar — regardless of DEV results — and the next levers are
> infill-style regrowth and/or retrieval/memory, each its own pre-reg.**

Sub-readings:
- **Transfer win** (C1 or C2 solves held-out/fresh where A/B do not): learned
  editing generalizes; the winning signal (log vs labels) directs the next
  scale-up; SPICE-minutes ranks arms.
- **DEV-only win** (dev solves, held-out/fresh zero): the editor memorized
  task-specific solutions — reported as memorization, NOT capacity; motivates
  retrieval-as-a-lever as an honest separate pre-reg, not a training claim.
- **Flat zero with pool widening** (no solves but distinct-realized pools grow
  materially): training moved the D1 bottleneck but not far enough — argues
  for data scale (more P1 tiers) before architecture surgery.
- **Flat zero, pools unchanged:** training at this scale does not move the
  bottleneck; escalate to infill/model surgery or retrieval.

## 9. Not in scope

No `lna/` writes (checkpoints under `engineer/out_editor/`); no main-line
generator/scoreboard claims; no playbook (R-C stands); no critic-in-the-loop
(offline critic validation on banked candidates may proceed separately as
zero-sim analysis); no infill/model surgery; E-6 stays paused.

## 10. Containment & crash-safety

As E-11 §9 verbatim (worktree, ≤8 ngspice, per-PID status temp files, atomic
per-cell JSONs under `engineer/data/e12_results/`, AnalogGenie symlink
pre-authorized, torch CPU-only). Goldens GREEN before/after every landing.

## 11. Pre-scored phases (P0, cheap, before P1)

1. **H2 null filter** — full-budget sizing-only (B=600 × 3 seeds); H2 enters
   HELD-OUT only if it RESISTS.
2. **Easy-tier calibration script** — zero sims; finalizes E1–E6 targets from
   banked artifacts per the §4 rule.
3. **Answer-exclusion filter script** — zero sims; emits the excluded-row
   lists for the training manifests.
4. **Fresh-task authoring** — user-approved at GO (band/Rs/power-class choice).

### P0 + P1 RESULTS (executed 2026-08-23/24, agent eng-e12a; goldens GREEN before/after; landed after independent verification)

- **Calibration (§11.2): all six provisional E1–E6 targets HELD** under the §4
  rule; per-target evidence in `engineer/data/e12/calibration.json`.
- **H2 null (§11.1): RESISTED (0/3)** — best nf 1.587 vs target 1.25; H2
  enters HELD-OUT. 1,800 counted evals.
- **Fresh task (§11.4): n78 built and harness-verified** — 3.4–3.6 GHz, 50 Ω,
  dhruva-s limits band-swapped in-memory (no yaml); goal GN78 `nf_db ≤ 1.6`
  authored a priori; 3 sanity evals produced real band metrics
  (`engineer/data/e12/fresh_task.json`).
- **Exclusion lists (§11.3): built** (`excluded_rows.json`): l1 ban = 210
  store topologies + 8,794 log rows; certificates excluded per goal as
  designed (G1''/H2 exclude `ace8383c`, G9 excludes `439032fd`).
- **P1 banking: 0 solves / 24 cells — ALL SIX easy goals flagged zero-solve
  (§4 deviation rule; nothing retuned).** Arm B 0/12 (distinct_realized = k);
  arm C 0/12 (distinct_realized 58–72 — the E-11 D1 bottleneck reproduces on
  easy targets). 20,993 trajectories banked (L0 14,236 / realize 4,161 /
  L1 2,500 / survivor 96) but **zero positive exemplars**. Deviations: one
  arm-C fan-out relaunched after task teardown (edit-log rows persisted,
  append-only by design; no counted sims lost); torch-thread cap as E-11.
- **Reading (recorded before any P2 decision):** the easy targets are provably
  reachable by base-feasible store designs, and E3/E5's targets were reached
  by *600-eval uninterrupted sizing* in the E-11 nulls — but two-stage
  survivors get only ~120 sizing evals, and the anchor→certificate topology
  gap is not bridged by 1-hop edits from the standard anchors. The zero yield
  is a survivor-budget + anchor-choice artifact of the banking design, not new
  evidence about the editors (they were already 0-for-E-11). **P2's C1
  contrastive design is materially affected (no positives) — user decision
  queued before P2 launches.**

## 12. Open items at GO

1. Approve E1–E6 calibrated targets (§4 rule output).
2. Approve the fresh task definition (§11.4).
3. Freeze training hyperparameters after the dry-run epoch (§5).
4. Confirm P1 seed count (1–2) and the P3 baseline plan (banked reuse vs
   fresh A/B only where unbanked).

<!-- ================================================================= -->
<!-- RESULTS BELOW — appended AFTER the scored run; nothing above this  -->
<!-- line may be informed by any scored E-12 eval.                      -->
<!-- ================================================================= -->

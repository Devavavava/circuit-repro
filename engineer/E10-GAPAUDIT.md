# E-10 GAP AUDIT — six unsolved goals, classified NEAR-MISS vs HOPELESS

> **⚠ WARNING (2026-08-22): the tables in §2–§4 below are DEFECTIVE.** The
> "best single point" rows they cite were selected without enforcing the
> missing-metric / stored-flag / cross-spec rules, and several are wrong. See
> the **AMENDMENT (strict re-verification)** section at the end of this file for
> the corrected per-goal tables, verdicts, and keep/replace recommendation. The
> original tables are retained unchanged only for the record.

**Zero-simulation analysis.** Pure arithmetic over already-recorded data
(`topo_labels` datastore + preserved E-8/E-8v2/E-9 result cells). No candidate
or goal was re-evaluated. See the attestation at the end.

Author line: engineer (eng-e10a). Read-only toward `lna/`; deliverable written
under `engineer/`.

---

## 0. Purpose

E-9 scored **0/6 solved** across all six goals (guided two-stage, random
two-stage, and sizing-only arms all failed). Before spending another campaign's
budget, classify each goal so the next experiment attacks only goals that are
reachable with the current repertoire.

---

## 1. Pre-declared classification rule (written BEFORE the tables)

A goal's **extended spec** = its task's base spec **plus** the goal's delta
constraint(s). A candidate must pass ALL of them simultaneously. We score every
objective by its **normalized margin** `m = (limit − achieved)/|scale|` for a
`max` constraint, or `(achieved − limit)/|scale|` for a `min` constraint;
`m ≥ 0` = satisfied, `m < 0` = failing. `|scale|` is the constraint's own scale
(the datastore's stored per-metric scale, e.g. |target| for the delta metrics).

**Rule (fixed, not fitted to data):**

> A goal is **NEAR-MISS** if the *best single recorded design* for that goal's
> extended spec fails on **at most 2** objectives **AND** the minimal relaxation
> needed on each failing objective is within the per-metric threshold below.
> Otherwise the goal is **HOPELESS-AT-CURRENT-REPERTOIRE**.
>
> A goal whose binding delta-metric has **never been measured** in any recorded
> data (so its true achieved value is unobtainable without a new simulation) is
> classified **UNKNOWN/HOPELESS-BLIND** — it cannot be attacked efficiently
> because we cannot even score progress from the record; the only recorded
> anchor is used as a floor, and if that floor is beyond the threshold the goal
> is HOPELESS-BLIND.

**Per-metric relaxation thresholds** (natural units, one-line justification):

| Metric type | Threshold | Justification |
|---|---|---|
| S11 / S22 (match) | **≤ 2.0 dB** | one extra matching element / modest re-tune typically buys 1–2 dB of return-loss band-max; beyond that needs a topology class change. |
| Gain S21 | **≤ 2.0 dB** | ~2 dB is one device-sizing/bias generation of headroom; larger gaps need an added stage. |
| Ripple S21 | **≤ 1.5 dB** | ripple is a shaping quantity; ≤1.5 dB is reachable by tank re-tuning, more implies a filter-order change. |
| NF | **≤ 0.5 dB** | NF is Friis-bounded and stiff; >0.5 dB over target rarely closes without a new input stage. |
| Current Idd | **≤ 1.5 mA** | ~1.5 mA is a bias re-partition; larger cuts trade against gain (a class change). |
| IIP3 | **≤ 3.0 dBm** | linearization (degeneration/added device) buys a few dBm; a ~10 dBm gap is a different linearity class. |

Thresholds are stated per metric-family and chosen from device-physics
reachability, **before** any table below was populated.

---

## 2. Best-ever vs target, per goal

Two views are reported and clearly labeled:

* **Best-ever (per-objective)** — the single best value on that ONE objective by
  ANY recorded design of ANY campaign, cherry-picked per objective.
* **Best single point** — ONE design that maximizes its *worst* normalized
  margin over the whole extended spec (no per-objective cherry-picking). This is
  the honest "closest complete design."

Source pools (datastore `topo_labels`, rows-with-metrics): dhruva-s 1059,
dhruva-l1 729, dhruva-l2 27, dhruva-l5 309. Solved E-8 cells corroborate where
the goal reuses an E-8 task/metric.

### Data-availability caveat (drives two UNKNOWN verdicts)

* `s22_max_db` (G2p's binding metric): **0 recorded rows**. Only single-frequency
  `s22_db` exists (proxy, best −33.9 dB) — but the goal is the band-**max**, a
  strictly larger quantity, so the proxy is not a valid best-ever. True best-ever
  is **UNKNOWN without a sim**. Only anchor −0.30 dB is on record.
* `iip3_dbm` (G11pp's binding metric): **0 recorded rows** (tier-3 two-tone sim,
  never stored). True best-ever **UNKNOWN without a sim**. Only anchor −17.18 dBm.

---

### G2p — s22_max_db ≤ −10 dB (dhruva-s)

| Objective | Target | Best-ever (per-obj) | Best-single-pt value | Fail? |
|---|---|---|---|---|
| s22_max_db | ≤ −10 dB | **UNKNOWN** (anchor −0.30; s22_db proxy −33.9) | UNMEASURED | UNKNOWN |
| base spec (idd/nf/s11/s21) | — | — | all pass (worst margin +0.12) | no |

Binding gap: anchor −0.30 dB → target −10 dB = **9.7 dB short** on the anchor;
threshold is 2.0 dB. True best-ever is not recorded → cannot score progress.

---

### G4p — s11_max_db ≤ −14.5 dB (dhruva-l2)

| Objective | Target | Best-ever (per-obj) | Best-single-pt value | Fail? |
|---|---|---|---|---|
| s11_max_db | ≤ −14.5 dB | **−12.66 dB** (wl 3ebaf08) | −12.66 dB | **YES** |
| idd_ma | ≤ (base) | — | pass (+0.047) | no |
| s21_db | ≥ (base) | — | pass (+0.042) | no |

Best single point = same design (3ebaf08). Fails **only 1** objective
(s11_max_db) by **1.84 dB**. Threshold 2.0 dB → within.

---

### G9 — s21_ripple_db ≤ 3 dB (dhruva-l5)

| Objective | Target | Best-ever (per-obj) | Best-single-pt value | Fail? |
|---|---|---|---|---|
| s21_ripple_db | ≤ 3 dB | **0.0 dB** | 3.0·(1−0.49)=1.5 dB | no |
| idd_ma | ≤ (base) | — | binding, +0.002 | no |
| nf/s11/s21 | — | — | all pass | no |

Best single point (wl ced0d8) passes the **entire** extended spec on all
measured objectives (worst margin +0.002, idd binding). Anchor was 15.18 dB;
a full-spec-passing recorded design exists. 0 failing objectives.

---

### G1pp — s21_db ≥ 33 dB (dhruva-l1)

| Objective | Target | Best-ever (per-obj) | Best-single-pt value | Fail? |
|---|---|---|---|---|
| s21_db | ≥ 33 dB | **38.75 dB** | 33·(1+0.146)=37.8 dB | no |
| idd_ma | ≤ (base) | — | binding, +0.006 | no |
| s11_max_db | ≤ (base) | — | +0.124 | no |

Best single point (wl 3ebaf08) passes the extended spec on all measured
objectives (worst margin +0.006, idd binding). Anchor was 26.32; E-8 sibling G1
(s21≥30) was SOLVED at 30.08. 0 failing objectives.

---

### G7pp — idd_ma ≤ 9.0 mA AT s21_db ≥ 22.3 dB (dhruva-l5)

| Objective | Target | Best-ever (per-obj) | Best-single-pt value | Fail? |
|---|---|---|---|---|
| idd_ma (@ s21≥22.3) | ≤ 9.0 mA | **6.37 mA** (wl 7b0b48, s21=26.2) | 9·(1+0.038)? see below | see below |
| s21_db | ≥ 22.3 dB | 41.46 dB | pass (+0.23) | no |
| nf_db (base) | ≤ 2.5 dB | — | −0.045 | **YES** |
| s11_max_db (base) | ≤ −10 dB | — | −0.048 | **YES** |

The **delta** itself (idd≤9 at s21≥22.3) is comfortably met by a recorded design
(6.37 mA). BUT no recorded design meets the delta AND the **base spec** together:
the max-worst-margin single point (wl 51cca7) fails **3** objectives — base
`nf` (−0.045), base `s11_max` (−0.048), and idd margin. The best-idd design
(7b0b48) still fails base nf (−0.37) and s11. So the joint extended spec fails on
**≥3** objectives; the failure is on the **base** spec (nf/s11), not the delta.

---

### G11pp — iip3_dbm ≥ −7.4 dBm (dhruva-l5)

| Objective | Target | Best-ever (per-obj) | Best-single-pt value | Fail? |
|---|---|---|---|---|
| iip3_dbm | ≥ −7.4 dBm | **UNKNOWN** (anchor −17.18) | UNMEASURED | UNKNOWN |
| base spec (idd/s11/s21) | — | — | all pass (worst +0.07) | no |

Binding gap: anchor −17.18 dBm → target −7.4 dBm = **9.78 dBm short** on the
anchor; threshold 3.0 dBm. True best-ever is not recorded → cannot score
progress. Even the recorded anchor is >3× the threshold beyond target.

---

## 3. Verdicts (by the pre-declared rule)

| Goal | Binding metric | Best-single-pt | # failing objs | Min relax on failing | Threshold | **Verdict** |
|---|---|---|---|---|---|---|
| G2p | s22_max_db | binding UNMEASURED | UNKNOWN | (anchor 9.7 dB > thr) | 2.0 dB | **HOPELESS-BLIND** |
| G4p | s11_max_db | fails 1 obj | 1 | 1.84 dB | 2.0 dB | **NEAR-MISS** |
| G9 | s21_ripple_db | passes all measured | 0 | — | — | **NEAR-MISS** |
| G1pp | s21_db | passes all measured | 0 | — | — | **NEAR-MISS** |
| G7pp | idd_ma @ s21 | fails ≥3 (base nf+s11+idd) | 3 | nf/s11 base-bound | ≤2 objs cap breached | **HOPELESS** |
| G11pp | iip3_dbm | binding UNMEASURED | UNKNOWN | (anchor 9.78 dBm > thr) | 3.0 dBm | **HOPELESS-BLIND** |

**Tally: 3 NEAR-MISS (G4p, G9, G1pp) / 3 HOPELESS (G7pp hard; G2p & G11pp blind).**

Note on G9/G1pp: a recorded design already satisfies the full extended spec on
all *measured* objectives, yet E-9 scored them 0/6. That is a **search-efficiency**
gap (the solver's starting anchor + move set did not rediscover the store's best
topology within budget), NOT a repertoire/reachability gap. These are the
highest-value KEEPs: the target is provably reachable with the current device
repertoire; the next campaign needs seeding/warm-starting from the store's best
topology rather than new moves.

---

## 4. Recommendation — KEEP / REPLACE

| Goal | Action | One-line reason |
|---|---|---|
| **G1pp** | **KEEP** | Full-spec-passing design already in the record; pure search-efficiency gap — warm-start from wl 3ebaf08. |
| **G9** | **KEEP** | Full-spec-passing design already in the record (wl ced0d8); reachable, seed the solver from it. |
| **G4p** | **KEEP** | Single best point fails only s11_max by 1.84 dB (< 2.0 dB thr); one matching element should close it. |
| **G7pp** | **REPLACE** | Delta is met alone, but the joint spec fails on ≥3 base objectives (nf & s11); the base NF/s11 co-bind — out of reach without an added input stage (topology-class change). |
| **G2p** | **REPLACE (or re-instrument first)** | Binding metric s22_max_db never recorded; only anchor −0.30 dB (9.7 dB short). Cannot score progress without adding s22-band measurement — blind. |
| **G11pp** | **REPLACE (or re-instrument first)** | IIP3 never stored; anchor −17.18 dBm is 9.78 dBm short (>3× threshold). Blind and physically a linearity-class gap. |

If the goal is spec-capacity (not novelty), the three KEEPs (G1pp, G9, G4p) are
the efficient spend. G2p and G11pp would first need cheap instrumentation
(record s22_max_db / iip3 on existing best topologies) before they can even be
audited — that instrumentation, being a measurement of *already-designed*
topologies, is the natural pre-step, but is itself out of scope here (zero sims).

---

## 5. Zero-simulation attestation

**No new experiment simulations were run for this audit.**

* Every number above is arithmetic over already-on-disk data: the `topo_labels`
  datastore (4076 recorded rows with stored `metrics`/`margins`) and the
  preserved E-8 (60), E-8v2 (81), E-9 (51) result cells.
* `binding_probe.py` arithmetic (single/pairwise minimal relaxation) is the same
  arithmetic reused here; it was read, not re-run against a live sim.
* Metrics that are genuinely unobtainable without a sim (`s22_max_db`,
  `iip3_dbm`) are explicitly recorded as **UNKNOWN**; the corresponding sims were
  NOT run — those goals were classified HOPELESS-BLIND instead.
* Cost verification: the only ngspice invocations in this job were the goldens
  harness `lna/ref/check_ref.py` (which prints `check_ref: GREEN`). No ngspice
  was invoked for any candidate or goal evaluation. Goldens confirmed GREEN
  before the first commit and after the last commit of this branch.

---

# AMENDMENT (strict re-verification) — 2026-08-22

**Author line: engineer (eng-e10a), strict re-audit.** Zero new experiment
simulations; arithmetic over `lna/data/topo_labels.jsonl` (4,076 L2 rows) only.
Goldens GREEN before and after this amendment.

## A.0 The defect

The original audit's central claim — that goals **G1''** and **G9** already have
a full-spec-passing "best single point" in the store (G1'' wl `3ebaf08`, "passes
all measured objs, worst margin +0.006"; G9 wl `ced0d8`, "passes full spec,
ripple 0.0") — was produced by three compounding errors:

1. **Missing-metric-treated-as-pass.** The phrase "passes all *measured*
   objectives" let a row be classified as passing while a required constraint
   metric was silently absent. Under the correct rule (a row with ANY required
   metric missing can NEVER pass — it is *incomplete*), whole pools collapse:
   G2'' (s22_max_db) and G11'' (iip3_dbm) have **0 rows** in the entire store
   carrying the binding metric (`s22_max_db`: 0/4076; `iip3_dbm`: 0/4076), so
   every candidate for those goals is incomplete, not scoreable.

2. **Stale stored `feasible` flag trusted across eras.** The wl `3ebaf08` rows
   the original cited carry `feasible=True`, but that flag was computed in a
   **pre-NF-gate era** where `nf_db` was `unsupported`/skipped. Recomputed under
   the goal's true extended spec, the `feasible=True` `3ebaf08` rows have
   **NF = 9.95 dB (dhruva-l1)** and **11.12 dB (dhruva-l2)** — grossly failing
   the NF ceiling (2.7 / 2.5 dB). Their later same-topology relabels (feas=False)
   still show NF 4.26 / 5.51 dB. `3ebaf08` fails NF under *every* era.

3. **Cross-spec pooling (forbidden by provenance law).** wl `3ebaf08` has 12
   rows, 3 each under `dhruva-s / dhruva-l1 / dhruva-l2 / dhruva-l5`. The
   original cited the *same* wl as the winner for both G4'' (dhruva-l2) and G1''
   (dhruva-l1); a topology's metrics under one spec's band/conditions do not
   transfer to another. The strict re-audit restricts each goal's candidate pool
   to rows whose `spec` equals the goal's base spec.

## A.1 Strict rules applied (verbatim from the re-audit task)

1. **Extended spec = full base-task constraint block** (task→spec via
   `engineer/tasks.py`; dhruva-l1-t2-a→dhruva-l1, l2→dhruva-l2, l5→dhruva-l5,
   s→dhruva-s) **+ the goal's delta** (E9-TWOSTAGE §2). `status: unsupported`
   constraints are excluded UNLESS the delta targets them (G11'' targets iip3).
2. **A row passes an objective only if the metric is PRESENT and satisfies the
   limit.** Any required metric missing ⇒ the row is **incomplete** (never
   passing); the missing metric(s) are reported.
3. **Stored `feasible`/`solved` flags are never trusted** — pass/fail is
   recomputed from raw `metrics` against THIS goal's extended spec. Provenance
   (recipe/era) is recorded; cross-spec candidates are rejected.
4. **Best single point** = the complete-metric row minimizing total normalized
   violation `Σ_j max(0, (achieved−limit)/|scale|)` (max-constraint) or
   `(limit−achieved)/|scale|` (min-constraint) over the failing objectives,
   `|scale| = max(|limit|,1)`. Incomplete rows that would otherwise win are
   flagged **UNVERIFIABLE-WITHOUT-SIM**.
5. **Pre-declared near-miss rule is UNCHANGED** (fails ≤2 objs; per-metric raw
   thresholds S11/S22 ≤2.0 dB, gain ≤2.0 dB, ripple ≤1.5 dB, NF ≤0.5 dB, Idd
   ≤1.5 mA, IIP3 ≤3.0 dBm).

## A.2 Corrected per-goal tables

Notation: **margin** = normalized (positive = pass); **raw gap** = natural-unit
shortfall on a failing metric (the quantity the near-miss threshold is stated in).

### G2'' — dhruva-s + `s22_max_db ≤ −10` — **HOPELESS-BLIND** (unchanged)

`s22_max_db` present in **0 / 1059** dhruva-s rows (0 / 4076 store-wide). Every
candidate is **incomplete**. Cannot score; binding metric never measured.
Best incomplete row: UNVERIFIABLE-WITHOUT-SIM (only single-freq `s22_db` proxy
exists, which is not the band-max). *Original verdict stands; the reason is
sharpened to "all rows incomplete," not "anchor 9.7 dB short."*

### G4'' — dhruva-l2 + `s11_max_db ≤ −14.5` — **HOPELESS** (was NEAR-MISS) ⚠CHANGED

Same-spec pool 27 rows, all complete, **0 pass**. Best single point = wl
`439032fd` (recipe mf2-v1, modern era), the only design that passes the *rest* of
the extended spec:

| Objective | Target | Achieved | Margin | Pass? |
|---|---|---|---|---|
| s11_max_db | ≤ −14.5 | **−10.03** | −0.308 | **FAIL** (raw gap **4.47 dB**) |
| s21_db | ≥ 22.3 | 26.81 | +0.202 | ok |
| idd_ma | ≤ 13 | 13.00 | +0.000 | ok (binding) |
| nf_db | ≤ 2.5 | 1.71 | +0.317 | ok |

Fails **1** obj, but the raw s11_max gap is **4.47 dB > 2.0 dB** threshold →
**HOPELESS**. The original's "−12.66 dB, gap 1.84 dB, NEAR-MISS" came from
cross-spec wl `3ebaf08` (dhruva-l2 row), which ALSO fails **NF = 11.12 dB**
(vs 2.5) — it never passed the rest of its own extended spec. Corrected.

### G9 — dhruva-l5 + `s21_ripple_db ≤ 3` — **NEAR-MISS / SOLVED-IN-STORE** (verdict stands; row + ripple corrected) ⚠CORRECTED-EVIDENCE

Same-spec pool 309 rows, all complete, **8 pass the full extended spec**. Best
single point = wl `439032fd` (mf2-v1, modern), total violation 0.0:

| Objective | Target | Achieved | Margin | Pass? |
|---|---|---|---|---|
| s11_max_db | ≤ −10 | −10.02 | +0.002 | ok (binding) |
| s21_db | ≥ 22.3 | 26.80 | +0.202 | ok |
| idd_ma | ≤ 13 | 13.00 | +0.000 | ok |
| nf_db | ≤ 2.5 | 1.74 | +0.303 | ok |
| **s21_ripple_db** | ≤ 3 | **2.989** | +0.004 | ok |

**Ripple was actually measured (2.989 dB), not 0.0.** The original cited wl
`ced0d8` "ripple 0.0" — that value appears nowhere for `ced0d8`: its real
dhruva-l5 ripples span **1.48–3.32 dB** (`ced0d8` also has dhruva-s rows with
ripple ~19–21 dB — cross-spec). The "0.0" was a missing/default fabrication. The
verdict (a full-spec-passing recorded design exists → KEEP) is *correct*, but the
honest anchor is wl `439032fd` @ ripple 2.989, not `ced0d8` @ 0.0.

### G1'' — dhruva-l1 + `s21_db ≥ 33` — **NEAR-MISS / SOLVED-IN-STORE** (verdict stands; row corrected) ⚠CORRECTED-EVIDENCE

Same-spec pool 729 rows, all complete, **2 pass the full extended spec**. Best
single point = wl **`ace8383c`** (mf2-v1, modern), total violation 0.0:

| Objective | Target | Achieved | Margin | Pass? |
|---|---|---|---|---|
| s11_max_db | ≤ −10 | −10.00 | +0.000 | ok (binding) |
| **s21_db** | ≥ 33 | **37.53** | +0.137 | ok |
| idd_ma | ≤ 13 | 12.99 | +0.001 | ok |
| nf_db | ≤ 2.7 | 1.29 | +0.522 | ok |

The original claimed wl **`3ebaf08`** passes. It does NOT: the `3ebaf08`
dhruva-l1 rows fail NF (9.95 dB feas-stale, or 4.26 dB relabel) — **0 of the 12
`3ebaf08` rows (any spec) pass their extended spec.** The passing design is a
*different* topology (`ace8383c`). Goal-level verdict (reachable in store →
KEEP) survives, but only after switching the anchor off the defective row.

### G7'' — dhruva-l5 + `idd_ma ≤ 9.0 @ s21 ≥ 22.3` — **NEAR-MISS** (was HOPELESS) ⚠CHANGED

Extended spec = base (s11≤−10, s21≥22.3, idd≤13→**9.0**, nf≤2.5). Same-spec pool
309, all complete, **0 pass**. Best single point (min total violation) = wl
`998ff3a1` (nf-v1+mf2-v1, modern):

| Objective | Target | Achieved | Margin | Pass? |
|---|---|---|---|---|
| s11_max_db | ≤ −10 | **−9.26** | −0.074 | **FAIL** (raw gap **0.74 dB**) |
| s21_db | ≥ 22.3 | 23.19 | +0.040 | ok |
| idd_ma | ≤ 9.0 | 7.07 | +0.214 | ok (delta comfortably met) |
| nf_db | ≤ 2.5 | 2.379 | +0.048 | ok |

Fails **1** obj (s11_max) by **0.74 dB < 2.0 dB** threshold → **NEAR-MISS**. The
original called this HOPELESS "fails ≥3 (base nf+s11+idd)" — that came from
*cherry-picking two different rows* (the best-idd row 7b0b48 failing NF, plus a
worst-margin row 51cca7), not from one honest best-single-point. The honest best
single point fails only s11 and is inside the pre-declared threshold. The delta
(idd≤9 @ s21≥22.3) is met AND NF now passes — the sole gap is a 0.74 dB match
tune. Corrected.

### G11'' — dhruva-l5 + `iip3_dbm ≥ −7.4` — **HOPELESS-BLIND** (unchanged)

`iip3_dbm` present in **0 / 309** dhruva-l5 rows (0 / 4076 store-wide; it exists
only inside `margins`, never in `metrics`). Every candidate **incomplete**.
Best incomplete row: UNVERIFIABLE-WITHOUT-SIM. Binding metric never measured →
HOPELESS-BLIND. *Verdict stands.*

## A.3 Corrected verdict table

| Goal | Base spec | Best single point (same-spec, complete) | #fail | Raw gap on fail | Thr | **Corrected verdict** | vs original |
|---|---|---|---|---|---|---|---|
| G2'' | dhruva-s | all incomplete (s22_max_db 0/1059) | — | — | 2.0 dB | **HOPELESS-BLIND** | same |
| G4'' | dhruva-l2 | wl 439032fd (s11 −10.03) | 1 | **4.47 dB** | 2.0 dB | **HOPELESS** | ⚠ NEAR-MISS→HOPELESS |
| G9 | dhruva-l5 | wl 439032fd (passes full, ripple 2.989) | 0 | — | — | **NEAR-MISS** (solved-in-store) | same (row+ripple fixed) |
| G1'' | dhruva-l1 | wl ace8383c (passes full, s21 37.53) | 0 | — | — | **NEAR-MISS** (solved-in-store) | same (row fixed) |
| G7'' | dhruva-l5 | wl 998ff3a1 (s11 −9.26) | 1 | **0.74 dB** | 2.0 dB | **NEAR-MISS** | ⚠ HOPELESS→NEAR-MISS |
| G11'' | dhruva-l5 | all incomplete (iip3_dbm 0/309) | — | — | 3.0 dBm | **HOPELESS-BLIND** | same |

**Corrected tally: 3 NEAR-MISS (G9, G1'', G7'') / 3 HOPELESS (G4'' hard;
G2'' & G11'' blind).** The *count* 3/3 is unchanged from the original, but the
*membership shifted*: **G4'' moved out of NEAR-MISS and G7'' moved in.** Two of
the three near-miss verdicts that survived (G9, G1'') did so only after their
cited anchor rows were replaced (the original anchors fail NF and do not pass).

## A.4 Corrected KEEP / REPLACE recommendation

| Goal | Action | One-line reason (corrected) |
|---|---|---|
| **G1''** | **KEEP** | Full-spec-passing design in store — wl **`ace8383c`** (NOT 3ebaf08); pure search-efficiency gap, warm-start from it. |
| **G9** | **KEEP** | Full-spec-passing design in store — wl `439032fd`, real ripple 2.989 dB (NOT ced0d8 @ 0.0); seed the solver from it. |
| **G7''** | **KEEP** (newly promoted) | Best single point (wl `998ff3a1`) meets the idd delta AND base NF; sole gap is s11_max 0.74 dB (< 2.0 dB thr) — one matching element. Was wrongly rejected as HOPELESS. |
| **G4''** | **REPLACE** (newly demoted) | Best design passing the rest of spec reaches only s11_max −10.03; gap to −14.5 is **4.47 dB > 2.0 dB** — a match-topology-class change, not a re-tune. Original's 1.84 dB came from a cross-spec NF-failing row. |
| **G2''** | **REPLACE (or instrument first)** | `s22_max_db` never recorded on any of 4076 rows — every candidate incomplete; blind. |
| **G11''** | **REPLACE (or instrument first)** | `iip3_dbm` never recorded in `metrics` on any row — every candidate incomplete; blind + linearity-class gap. |

If the goal is spec-capacity, the efficient KEEP set is now **G1'', G9, G7''**
(G7'' replaces G4''). G4'' now needs a match-class change; G2''/G11'' first need
cheap instrumentation (record s22_max_db / iip3 on existing best topologies)
before they can be audited at all.

## A.5 What the original audit did wrong — summary

- **Missing-metric-as-pass:** "passes all *measured* objs" allowed rows missing
  s22_max_db / iip3_dbm to be scored; strictly all such rows are incomplete
  (G2''/G11'' pools are 100% incomplete).
- **Stale `feasible` flag + cross-spec pooling combined:** the marquee anchor wl
  `3ebaf08` (cited for both G1'' and G4'') carries a pre-NF-gate `feasible=True`
  and is a *different* spec's row; recomputed, it fails NF (9.95 / 11.12 dB) and
  passes nothing. G9's `ced0d8` "ripple 0.0" was a missing/default value (real
  ripples 1.48–3.32 dB) and partly cross-spec.
- **Cherry-picking across rows for the "worst case":** G7'' was called HOPELESS
  by combining fail metrics from two different rows; the honest single best point
  fails only 1 obj by 0.74 dB and is a NEAR-MISS.

Net: the headline 3-near-miss / 3-hopeless split holds by count, but **G4''↔G7''
swap sides**, and the two surviving "solved-in-store" KEEPs (G1'', G9) rest on
*different* rows than the original named. Goldens GREEN.

---

# RULINGS (user, 2026-08-23)

Recorded verbatim from the user's session ruling; these close this audit's open
questions and gate the next campaign's pre-registration (E-11):

1. **AMENDED verdicts ADOPTED.** The strict re-audit's KEEP set — **G1'', G9,
   G7''** with corrected anchors `ace8383c` / `439032fd` / `998ff3a1` — is the
   audit-filtered goal basis for the next campaign. The original tables remain
   for the record only.
2. **G2'': INSTRUMENT FIRST (s22 only).** Measure `s22_max_db` on the store's
   best recorded dhruva-s topologies (the harness metric already landed on main),
   then re-audit G2'' under the unchanged pre-declared rule (near-miss iff raw
   gap ≤ 2.0 dB, ≤ 2 failing objectives). A handful of measurement sims on
   *already-designed* topologies; not a search campaign.
3. **G11'': REPLACE outright.** No iip3 storage plumbing; the anchor is
   9.78 dBm short (>3× threshold) and physically a linearity-class gap. A
   replacement goal is authored in the E-11 pre-reg and null-filtered at full
   budget per the 2026-08-22 ruling. G4'' likewise replaced (4.47 dB
   match-class gap).
4. **Editor model for generator-as-editor: the adopted main-line v7 generator
   checkpoint**, used for segment regrowth, declared in the contamination
   ledger as a cross-line import. No new training for E-11's first
   pre-registration.

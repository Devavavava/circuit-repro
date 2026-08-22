# E-10 GAP AUDIT — six unsolved goals, classified NEAR-MISS vs HOPELESS

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

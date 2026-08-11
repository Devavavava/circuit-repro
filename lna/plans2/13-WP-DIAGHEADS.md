# WP-DIAGHEADS — turning the critic from a ranker into a diagnosis engine

**Status:** pre-registered 2026-08-11, **before any head was trained and before a
single pilot sizing was run**.
**Branch:** `lna-data`. **Owner:** the WP-DIAGHEADS executor (Session 7).
**Series:** continues `plans2/02-CRITIC`, `plans2/09-WP-OBSERVE`.
**Files this WP may touch:** `lna/critic_gnn.py` (owned this session),
`lna/plans2/13-WP-DIAGHEADS.md`, small `lna/_diag_*.py` helpers.
`lna/moves.py` is used **read-only** (moves applied, file untouched).
**Documentation slots:** FINDINGS **§34**, JOURNEY next stage,
`STRUCTURE_LOGIC.md` Block 7.

---

## 0. The question

The critic (Block 7) predicts a 4-vector of margins for a *whole topology* and
pools its per-node embeddings away to do it. It can therefore say "this
candidate will miss" but never "and here is the device that is missing it".
Every downstream consumer pays for that: `search.py` ranks, and `evolve.py`
mutates **uniformly at random over 17 move classes** — the selector has no
opinion about *where* on the graph to cut.

The store already contains the two supervision signals that would give it one,
and nothing has ever read them as labels:

* **per-element noise budgets** — `extract.measure_noise_budget`, golden-validated
  in §26 (sum-closure 1.0000, NF-via-shares agreeing with NF-via-inoise to
  <= 0.002 dB), stored on every NF-gated L2 row by `size._noise_budget_row`;
* **per-device operating points** — `data/op_points.jsonl` from WP-OBSERVE (§30),
  whose first reading was that **44% of the transistors in this program's
  headline designs sit in weak inversion and `bias.saturated` provably cannot
  see it** (BSIM4 `Vdsat` collapses to ~55 mV there, so every one of those
  devices passes the `|Vds| >= 1.5|Vdsat|` test by 5-8x).

So: **can the same backbone that ranks topologies also localise the defect, and
does localising it make search better?** The second half is the point; a
diagnosis head that nothing acts on is a metric, not a capability.

---

## 1. Label sources and counts (measured 2026-08-11, before training)

### 1a. Per-device noise share — `topo_labels.jsonl`, `provenance.noise_budget`

| quantity | measured |
|---|---|
| L2 rows in store | 2,786 |
| rows carrying `provenance.noise_budget` | **1,356** |
| ...in the post-§27 **multi-finger era** (`zoaf_cfg.w_finger == 2e-6`, `mos_fingers = ceil(W/w_finger)`, `inductor_q = 12`, `nf_gated = true`) | **1,355** |
| ...in the pre-cutover single-finger era | 1 (**dropped** — Block 6 is law, eras are never pooled) |
| distinct `wl_hash` among the 1,355 | **796** |
| spec spread | wifi24 450, dhruva-s 351, dhruva-l1 207, dhruva-l5 183, wideband-sdr 125, gps-l1 26, dhruva-l2 13 |
| budget elements stored per row (`top`, sorted by share of F-1) | 3:28, 4:77, 5:1228, 6:22 |
| share of F-1 captured by the stored `top` list | median **0.993** |

Element-to-device mapping is exact and mechanical from `to_spice.emit`:
`M{dev}` -> MOS (`mnm1` -> `NM1`), `R{dev}` -> resistor (`rr1` -> `R1`),
`RQ{dev}` -> an inductor's finite-Q resistor (`rql1` -> `L1`). Two element classes
are **not** topology devices and are excluded from the per-device label:

* `rns` — the 50 ohm source; it *is* the F-1 reference and is already excluded by
  `_noise_budget_row`;
* WARNING **`rnl` — the 50 ohm output load of the noise deck.** It is the true
  top-1 contributor in **491 / 1,355 rows (36.2%)**. This is a harness element,
  not a design choice, and it is recorded here **in advance** so the head's
  accuracy is never quoted as if it had chosen among devices only. Device-only
  share of F-1: median 0.792, mean 0.658.
* 4 rows list a `rbias*` element (bias.py's inserted bias resistors) — also
  excluded, also not a topology device.

After exclusion **all 1,355 rows still have >= 2 mapped devices**, so every row
carries a well-posed "which device dominates" label.

**The two baselines the head must beat** (both measured, both non-learned):

| baseline | accuracy |
|---|---|
| uniform over the noise-capable devices of each graph (mean 1/n, median n = 6) | **0.172** |
| the single best constant name — *always NM1* | **0.398** |

(Dominant-device kind census: NM 751, R 362, L 231, PM 11.)

### 1b. Per-device conduction / inversion region — `op_points.jsonl`

| quantity | measured |
|---|---|
| op rows | 194 |
| device-level rows | 391 |
| region census | off **374**, sat 8, sub 5, triode 4 |
| device rows carrying > 1 uA | **24** |
| distinct `wl_hash` covered | **28** |
| rows at a *converged* point (`stage` in {final, label}) | **30** |

WARNING **This is the opposite of the brief's expectation, and it is a finding,
not a failure.** The noise-budget label set is rich (1,355 rows / 796
topologies); the op table is **thin and degenerate**: 164 of its 194 rows are
inner-ZOAF trajectory points of a single 2-device `gps-l1` demo circuit at
un-converged `x`, where every device is genuinely off. §30.6 item 1 predicted
exactly this: the table has 168 rows, and the science starts when a campaign
fills it.

There is a second, deeper problem with inner-ZOAF rows as labels, and it decides
the design: **the critic's input is (topology, spec) and does not contain `x`.**
The same topology is off at one point of a ZOAF trajectory and saturated at
another, so a conduction label taken at an arbitrary inner point is *not a
function of the model's input*. Only a **converged** point (the design's own
stored `best_params`) gives a well-posed label — and there are 30 of those.

**Therefore, pre-registered as part of this WP: a read-only op harvest.**
`lna/_diag_harvest.py` walks the 1,355 multi-finger noise-budget L2 rows,
rebuilds each deck with `size.prepared_body` (bias inserted, era-matched
`inductor_q`), runs **one bare `op`** at that row's own stored `best_params` —
the exact method §30.5 used for its six designs — and appends one `stage="label"`
op row per design, stamped `harness.recipe = "diagheads-v1"`.

* No re-sizing, no store mutation, no adoption of anything: it is instrumentation
  over designs that were already labelled.
* Measured cost on the first 5 designs: **0.06 s** per `op` run plus
  0.06-0.27 s of bias-insert, i.e. **about 0.3 s per design, ~7 min for all
  1,355**.
* **Budget cap: 1,400 `op` runs, one wall-clock hour.** Overrun means stop and
  train on what landed.
* This makes the two heads share one row set: the *same* design supplies both
  the noise-share label (already stored) and the conduction label (harvested).

**Snapshot discipline.** Immediately after the harvest, `datastore.snapshot`
pins `topo_labels` **and** `op_points` (line count + sha256) under the name
**`v7-diag`**; all training and every number below is quoted against it.
`op_points` has never been snapshotted before — §30.6 item 3 asked whoever
trained on it first to do exactly this.

---

## 2. Architecture

One backbone, three read-outs. The backbone is **unchanged** from critic v1 —
bipartite device-net message passing, per-pin-role linear maps, 3 rounds, h = 64
— because the whole question is whether the *existing* representation already
knows where the defect is.

| head | reads | shape | loss |
|---|---|---|---|
| **margin** (existing, must stay intact) | `[sum-pool, max-pool, spec]` | to 4 | masked Huber + S21 rank-hinge (unchanged) |
| **(a) noise share** | per-device `[h_d, spec]` | to 1 logit/device | masked **softmax cross-entropy against the soft target** = `frac_excess` renormalised over the mapped devices. Mask = noise-capable devices (NM/PM/R/L; capacitors are noiseless by construction, not by inference) |
| **(b) conduction / region** | per-device `[h_d, spec]` | to 3 logits/device | masked cross-entropy over MOS devices only, classes **{off, weak/moderate, strong}** |

`L = L_margin + 0.5*L_noise + 0.5*L_cond`. **The two lambdas are fixed a priori
and will not be tuned**; if the multi-task model regresses on margins, the answer
is a separate model (section 3), not a lambda sweep.

Class definition for head (b), fixed before the harvest:

* **off** — `|Id| < 50 uA` (the *same* `bias.conducting` threshold
  `extract.mos_region` uses, so an op row and an L1 row can never disagree);
* among conducting devices, **weak/moderate** = `gm/Id >= 14 V^-1`,
  **strong** = `gm/Id < 14 V^-1`. 14 is the midpoint of §30.5's measured gap
  (**17-20 V^-1** for the sub group vs **10-12 V^-1** for the saturated group)
  and is **not** fitted to this WP's data.

Rows without a diagnosis label contribute only `L_margin`, so the margin head's
training set is *identical* to critic v1's — which is what makes section 3's
non-regression comparison fair rather than confounded.

**(c) Stretch — binding-constraint prediction** (which gated metric will bind
after sizing, a per-*design* 4-way head over the argmin of the achieved margin
vector). Attempted **only if (a) and (b) both clear their bars**; otherwise
recorded as not attempted.

---

## 3. Evaluation — two bars, both pre-registered

Splits are always `datastore.family_split` (whole WL-similarity families).
**No row-level split is used anywhere in this WP**, for either head — the store's
median nearest-neighbour similarity inside an arm is 1.000 and a row split leaks.

**Bar 1 — the diagnosis heads are worth having.** On the family holdout:

| metric | bar |
|---|---|
| (a) dominant-noise-device **top-1 accuracy** | **>= 0.55**, and strictly above *both* non-learned baselines (0.172 uniform, 0.398 always-NM1) |
| (a) Spearman rho(predicted share, measured `frac_excess`), pooled over devices | reported, no bar |
| (b) **conducting-vs-off AUC** | **>= 0.75** |
| (b) **weak-vs-strong AUC** over conducting MOS | **>= 0.70**, against the L1 predicate's structural 0.5 (§30.5: `bias.saturated` calls all 25 of those devices saturated, so it cannot score above chance on this axis by construction) |

**Bar 2 — the shipped critic must not regress.** The pinned margin-head harness
(`critic_gnn.run_eval`: family holdout **and** source-shift, 5-seed ensemble)
is re-run on the same snapshot for (i) the margin-only model and (ii) the
multi-task model. Non-regression is
**rho(S21) >= margin-only - 0.02 on *both* splits, and Gate C1 still passing on
family holdout.** If that fails, the diagnosis heads **ship as a separate
model** and this document and FINDINGS §34 say so — Block 10's
adopt-only-if-better applies to critic versions.

---

## 4. The demonstration experiment — targeted vs random move selection

A diagnosis head that no search consumes is a metric. So: at **equal SPICE
budget**, does pointing `moves.py` where the heads point beat cutting at random?

### 4.1 Parents (deterministic rule, `lna/_diag_parents.py`, fixed here)

Rule: multi-finger era; tokens + `best_params` present; worst gated margin in
**(-0.5, 0)** (a near miss, not a wreck); `n_devices <= device_budget_max - 2`
(so a growth move is legal); best row per `wl_hash`; then greedily take 5 by
largest worst-margin subject to distinct `wl_hash`, distinct WL family, and
**at most 3 parents per spec**. That rule yields, and this WP is bound to:

| # | wl_hash | spec | binding | worst margin | n_dev | source arm |
|---|---|---|---|---|---|---|
| 1 | `8c7592ea859e489a` | dhruva-s | `nf_db` | -0.0019 | 16 | nf-campaign |
| 2 | `f3f16e7e3c07b988` | dhruva-s | `nf_db` | -0.0051 | 13 | nf-campaign |
| 3 | `7499599ed33bd478` | dhruva-s | `s11_max_db` | -0.0056 | 18 | nf-moves |
| 4 | `c944366e8084a8b4` | wifi24 | `idd_ma` | -0.0294 | 10 | cur-v2 |
| 5 | `396b90321529157a` | wifi24 | `s21_db` | -0.0358 | 9 | campaign-G |

### 4.2 The two arms

Both arms draw children from **the same `moves.mutate` proposal process**, the
same parent, the same legality checks (`moves.sane` + `moves.realize`, i.e. the
Eulerian round trip and the spec's L0 screen), and disjoint RNG seeds. The only
difference is the filter.

* **RANDOM** — stock `MOVES` weights, first 2 distinct-WL realisable children.
* **TARGETED** — the trained heads are run on the parent; `dom` = argmax
  predicted noise share. The allowed move classes are then, fixed here:

  | predicted `dom` | allowed move classes | mechanism |
  |---|---|---|
  | a MOSFET | `degen_add`, `cascode_add`, `input_class_swap`, `stage_add` | degeneration and cascoding change that device's noise transfer directly; a swap changes its class; a stage ahead of it cuts its input-referred share |
  | a resistor | `load_swap`, `passive_type_swap`, `match_elem_add` | a lossy resistive load is replaced by a reactive one |
  | an inductor (its Q resistor) | `load_swap`, `match_elem_add`, `passive_type_swap` | the same, on the matching/tank side |

  Plus, when the conduction head predicts any MOS **off** or in **weak**
  inversion, `stage_add` and `cascode_remove` are added to the allowed set
  (relieve stacking on an over-driven input stage).

  On top of the class filter, **rejection sampling for locality**: a proposal is
  kept only if its edit actually touches `dom` (a device added on a net `dom`
  pins, or `dom` itself rewired/replaced). If no such proposal appears within the
  sampling budget the class filter alone is used and **the fallback is counted
  and reported**.

### 4.3 Budget and metric, pre-registered

* **20 sizings total**: 5 parents x 2 arms x 2 children.
* `size.size_topology(topo, spec, seed=0, n_candidates=8, sgd_iters=8,
  cgd_iters=2, inductor_q=12)` — `evolve.py`'s own defaults, so the arms are
  comparable to the search that would consume this. `log=True`; rows carry
  `provenance.source_arm = "diagheads-pilot"`.
* Wall-clock cap **15 min per sizing**; an overrun is recorded as a failed slot
  for that arm, never silently retried into a better one.
* **Primary metric:** mean **delta feasibility score** =
  `evolve.feasibility_score(child gated margins) - (parent)` over
  `evolve.margin_cols(spec)`, per arm.
* **Secondary:** mean delta of the worst gated margin; count of children with a
  positive delta; the fallback rate; per-parent detail.
* n = 10 per arm. **No significance is claimed at this n** — the pre-registered
  claim is the *sign* of the difference, and the table is published whichever way
  it falls.

---

## 5. Predictions (registered before training and before the pilot)

* **P1.** (a) dominant-noise top-1 on family holdout >= **0.55** — well above the
  0.172 uniform base rate, and above the 0.398 always-NM1 constant.
* **P2.** (b) conducting-vs-off AUC >= **0.75**; weak-vs-strong AUC >= **0.70**
  where the L1 predicate is structurally at 0.5.
* **P3.** The multi-task model does **not** regress the margin heads:
  rho(S21) within 0.02 of margin-only on family holdout *and* source-shift.
* **P4.** **TARGETED beats RANDOM on mean delta feasibility score.**
* **P5 (the way this most plausibly fails).** Head (a) collapses onto the device
  *prior* — the first NMOS is usually the dominant one — and clears 0.55 without
  learning anything graph-specific. The check is the 0.398 constant baseline plus
  a per-spec and per-`n_devices` breakdown; if top-1 is not above the constant on
  *each* of the three largest specs, P1 is recorded as **not met** regardless of
  the pooled number.
* **P6.** Head (b) is the one at risk from data volume even after the harvest,
  because the harvested labels are all at *converged* points and may be heavily
  skewed to `sat`. If either AUC is undefined for want of a class in the holdout,
  it is reported as data-gated with the measured class counts — not as a pass.

---

## 6. Method discipline

* Append-only store, recipe stamps (`diagheads-v1` for harvested op rows,
  `diagheads-pilot` as the pilot's `source_arm`); no era pooling.
* Frozen protocol untouched; blind protocol observed.
* Regression quartet green before and after (recorded in FINDINGS §34).
* `moves.py`, `size.py`, `extract.py`, `finetune.py`, `grammar_gen.py`,
  `surrogate.py` and the `_attrib_*` / `_out_*` files are **not** edited.
* The shared store carries uncommitted rows from concurrent agents; committing
  the data files commits theirs too (established practice since Session 5) and
  the commit message says so.


---

## 7. Outcome (appended after execution, 2026-08-11)

Recorded here so this document is not read as a promise. Full detail in
FINDINGS **§34**.

| pre-registered claim | verdict |
|---|---|
| **P1** dominant-noise top-1 >= 0.55, above both baselines, and above the constant on each of the three largest specs | **MET** (0.596; uniform 0.191, constant 0.307; wifi24 0.446 / dhruva-l5 0.806 / dhruva-s 0.680) |
| **P2** conducting-vs-off AUC >= 0.75, weak-vs-strong >= 0.70 | **MET** (0.949 / 0.858; `bias.saturated` measures 0.552 on the second) |
| **P3** margin heads not regressed | **NOT MET** -- rho(S21) 0.862 -> 0.771 family holdout, 0.630 -> 0.590 source shift. Pre-registered consequence executed: the diagnosis heads ship as a **separate model**; critic v1 unchanged. |
| **P4** targeted beats random on mean delta feasibility score | **MET** (-1.049 vs -1.432) -- but by a smaller downside tail, not a better upside; the only feasible child came from the random arm |
| **P5** risk that head (a) is only the device prior | **not realised** -- it beats the 0.307 constant on every large spec and is flat in graph size |
| **P6** risk that head (b) is data-gated | **not realised after the harvest** -- 864 labelled test devices, all three classes present |
| head **(c)** binding-constraint prediction (stretch) | **not attempted** -- ran out of CPU, not out of reasons |

Two departures from the plan, both recorded rather than smoothed:

* the harvest budget was pre-registered as 1,400 `op` runs / one hour; the actual
  cost was **1,335 runs / 642 s**, inside budget;
* the pilot ran **18 of the 20** registered sizings, because on one parent the
  targeted arm could not propose a single legal child (the head pointed at an
  inductor's Q resistor on a circuit already at its inductor budget) and the
  pre-registered class-only fallback also returned nothing. The shortfall is a
  reported result, not a silently rebalanced experiment.

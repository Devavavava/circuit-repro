# E6-BUDGET — racing / successive-halving vs the full-budget incumbent (pre-registration)

**Status:** PRE-REGISTRATION. Written and committed **before any measurement
eval**, on branch `eng-e6` off `engineer`, executing **rung G1 (E-6)** of
`engineer/ROADMAP.md` §3. This file is the timestamp: its commit precedes every
result artifact produced under it, and it is committed **alone** (its own commit)
per the house pre-registration discipline (`PROTOCOL.md` §9, E3-MEMORY.md,
E4-LOOP.md). The rule — arms, k, r, culling, matched budget, tasks, seeds,
metrics, acceptance, falsifier — is fixed here, before the harness runs a single
scored eval, so the numbers cannot have chosen the protocol.

This doc is short by intent, in `PROTOCOL.md` / `E3-MEMORY.md` / `E4-LOOP.md`
shape: state the hypothesis, the arms and their frozen numbers, the matched
budget, the tasks/seeds, the metrics, the acceptance criterion, and the binding
falsifier — with rationale, before the run — then run, then append the outcome
(clearly marked post-hoc).

---

## 0. The mechanism this rung attacks (why E-6 exists)

E-3 (memory) and E-4 (loop) both measured the **same negative**, from the same
cause: **fracturing a matched budget into equal slices loses to one full-budget
run.**

- E-3 §6.1: the playbook-informed arm split each task's budget into K=6 equal
  CMA-ES starts; six starved 56-eval starts converged worse than one 336-eval
  start. Warm < cold on **7/7** tasks. E-3 §6.4's hand-off, verbatim: *"naive
  budget-splitting is the wrong way to spend a retrieved sizing lesson… run more,
  shorter starts is the wrong shape."*
- E-4 §10.3: the loop's ≤4 stages of ≤66 evals each were each far weaker than the
  null's single 266-eval run; the loop reached median obj **1.72** where the null
  reached **~1.16**. Same mechanism, in a new guise.

Both negatives share a structural cause: **every slice paid the full cost of a
short, starved search, and none got the full budget.** E-6 asks whether a
*different* way of spending multiple starts — **use the short starts only to
triage, then hand the entire remaining budget to the survivor** — repairs the
fragmentation instead of re-committing it.

---

## 1. Hypothesis (stated before any number is seen)

> **Racing / successive-halving repairs the E-3/E-4 budget-fragmentation
> mechanism: many short starts are used ONLY to triage (pick the most promising
> basin), the full remaining budget goes to the survivor(s), warm-resumed — and
> at matched total evals this matches or beats the single full-budget incumbent
> (the E-3 cold-arm configuration).**

The intuition the seed-variance data supports (§5): CMA-ES seeds land in very
different basins (on `wifi24-t2-a` the per-seed best-obj ranges from −0.823 to
+1.189 at full budget; `dhruva-l1` −0.788 to +1.288; `dhruva-l2` −0.600 to
+1.397). A run that triages a handful of basins cheaply and then spends the
*whole* remaining budget descending the best one should beat both (a) a single
random-seed full run that may be stuck in a bad basin, and (b) the E-3
equal-split that starves every basin. The falsifiable question is whether the
triage signal is informative *early enough* (at `r` evals) to be worth the evals
it costs.

---

## 2. Arms

Two arms, both driven through `engineer/env.py`'s budgeted interface, both
importing `lna/null_sizer.run_cmaes` **verbatim** (never re-implemented — two
implementations of a baseline are two baselines; the E-1/E-2/E-3 rule):

| arm | what it is |
|---|---|
| **(A) incumbent** | A single full-budget CMA-ES run — **exactly the E-3 cold-arm configuration**, which is bit-identical to the registered `cmaes` null (`scoreboard_v0.1.json`): `run_cmaes(env.objective_fn(), env.dim, seed)` spending the whole task budget. This is the arm E-3 and E-4 lost to; it is the bar. |
| **(B) racing** | k triage starts × r evals each; cull to the top-1 survivor; the survivor is warm-resumed and spends the entire remaining budget. Total evals matched to arm A exactly (§3). |

Arm A **is the incumbent, unchanged** — no configuration of it is touched (that
is out of scope, §8). E-6 measures arm B against it.

### 2.1 Arm B mechanics — how a verbatim `run_cmaes` expresses "warm-resume the survivor"

`run_cmaes` takes **no injectable start-mean** (each restart begins at
`rng.random(n)`); E-3 §2.2 hit this same wall. But `run_cmaes(f, n, seed)`
produces a **deterministic x-sequence**, and a longer-budget run is a
**bit-identical prefix superset** of a shorter run with the same seed (verified
pre-registration on a cheap deterministic objective: a 30-eval and an 80-eval run
of seed 42 agree on all 30 shared evals, eval-for-eval). This is what makes a
faithful warm-resume expressible *without editing the imported optimizer*:

1. **Triage.** For `i` in `0..k-1`, run sub-seed `seed+i` for exactly `r`
   env-evals (stopped by the E-3 `_sliced_objective` per-start wrapper, which
   raises the env's own `BudgetExhausted` — transparent to `run_cmaes`). Each
   start's triage points are cached (x, objective). Cost: `k·r` env-evals.

2. **Cull.** The **survivor** = the sub-seed with the best (lowest) objective seen
   in its `r` triage evals. Culling rule: **top-1** (see §2.2).

3. **Warm-resume.** Re-invoke `run_cmaes(g, n, seed+winner)` where `g` **replays
   the winner's `r` cached triage points from cache** (no ngspice, no env eval)
   for its first `r` calls, then forwards to the real env for every call after.
   Because the x-sequence is deterministic in the seed, the replayed prefix is
   bit-identical to what the survivor already did, and the search continues
   **past** eval `r` into the remaining budget as one continuous CMA-ES
   trajectory. The env's global best is kept across all starts.

The survivor therefore sees a **continuous `r + (budget − k·r)`-eval search** —
its triage phase and its resume phase are one unbroken CMA-ES run, exactly what
"warm-resume the survivor" means. At **k=1** the arm reduces to `run_cmaes(f, n,
seed)` — arm A, bit-identically — so the mechanism nests the incumbent as a
degenerate case (the E-3 K=1 discipline).

### 2.2 Culling rule = top-1, and why (chosen before any run)

**Top-1**, stated as a number and justified from E-3's variance data *before* the
run:

- The whole point of racing (§0, §1) is to give the survivor an **unfragmented**
  remaining budget. **Top-2 would halve the survivor budget** — reintroducing the
  exact equal-split fragmentation E-3/E-4 proved loses. Keeping two survivors
  spends `(budget − k·r)/2` on each; on `dhruva-l2` that is ~103 evals/survivor,
  right back in the starved regime E-3 measured at obj 1.72.
- The seed-variance data (§5) shows one good basin per task is enough to be
  feasible where the median seed is not (e.g. `dhruva-l1` best −0.788 feasible,
  median −0.252 infeasible). Racing's job is to *find and fully fund* that basin,
  not to hedge across two half-funded ones.

The **risk** of top-1 is real and is recorded as an open question (§9): the triage
signal at `r` evals is noisy — `evals-to-first-feasible` on the incumbent is late
(110–250 evals, §5), so a basin that is behind at eval `r` may be the eventual
winner, and top-1 can cull it. Top-2 would hedge that risk at the cost of
fragmentation. The pre-registered choice is **top-1** because the hypothesis under
test is specifically "*unfragmented* survivor budget beats the equal split"; a
top-2 arm tests a different, weaker claim. Whether top-2 would have done better is
a follow-up, not this rung.

### 2.3 k and r — the numbers, frozen here

- **k = 4** triage starts (fixed, all tiers).
- **r (triage evals per start):** `r = min(60, max(15, round(0.15 · budget / k)))`
  — i.e. triage costs ~15% of the budget on the larger tasks, floored at 15
  evals/start so a triage window is never degenerate, capped at 60. Concretely:

  | task | budget | r | triage `k·r` | triage % | survivor new evals `budget − k·r` |
  |---|---:|---:|---:|---:|---:|
  | wifi24-smoke (smoke) | 150 | 15 | 60 | 40.0% | 90 |
  | wifi24-t2-a | 336 | 15 | 60 | 17.9% | 276 |
  | gps-l1-t2-a | 136 | 15 | 60 | 44.1% | 76 |
  | wideband-sdr-t2-a | 136 | 15 | 60 | 44.1% | 76 |
  | dhruva-l1-t2-a | 392 | 15 | 60 | 15.3% | 332 |
  | dhruva-l2-t2-a | 266 | 15 | 60 | 22.6% | 206 |
  | dhruva-l5-t2-a | 1050 | 39 | 156 | 14.9% | 894 |
  | dhruva-s-t2-a | 1030 | 39 | 156 | 15.1% | 874 |

  On the small tasks (136/150 evals) triage is a large fraction (40–44%). That is
  honest and deliberate: the fragmentation E-3 measured bit *hardest* on small
  budgets, so testing the racing repair there is the point, not a flaw. `k`, `r`,
  and the rule are frozen here before the run.

---

## 3. Matched budget (stated before the run)

**Identical total simulator evals per (task, seed) pair across both arms.** Arm A
spends `budget` evals in one run. Arm B spends `k·r` triage evals **plus**
`(budget − k·r)` new survivor evals = **exactly `budget`** (the survivor's first
`r` evals are the cached triage points, replayed from cache, NOT re-simulated, so
they are counted once — as triage — never twice). The env's own counter raises
`BudgetExhausted` on the eval after `budget`, so each arm spends *exactly*
`budget` evals, never `budget+1` (PROTOCOL §2). Per-task budgets are the pinned
PROTOCOL §2 numbers (150 smoke; 336/136/136/392/266/1050/1030 full). This is the
S11/AnalogGym compute-match: a win must be a win at equal SPICE, not more of it.

When the spec gates NF one eval is two ngspice calls, both counted, for both arms
alike (PROTOCOL §2.1). Budgets are per-arm, per-seed.

---

## 4. Tasks, seeds, and tiers

### 4.1 Smoke tier (this run — mechanics check only)

- **Tasks:** the **in-house task set** — the 7 tier-2 scoring tasks
  (`tasks.SCORING`), run at **150 evals/arm/task** (the R-4 smoke convention).
  Because the smoke uses a uniform 150-eval cap (not each task's matched budget),
  its numbers are *not* comparable to the registered scoreboard; the smoke is a
  harness check, not a scoring run (§7).
- **Seeds:** **3 seeds, seeds 1–3** — a small count sufficient to exercise the
  triage/cull/resume plumbing on every task and expose any determinism or
  budget-accounting bug. Not enough to make a statistical claim (that is the full
  tier). Stated as a number before the run.
- **Cells:** 7 tasks × 2 arms × 3 seeds = **42 cells**.

### 4.2 Full tier (TO BE RUN ONLY AFTER HUMAN GO)

- **Tasks + budgets + N:** the **PROTOCOL v1.0 scoring configuration** — the 7
  in-house tier-2 tasks at their **pinned matched budgets** (336/136/136/392/266/
  1050/1030), **N = 10 seeds** (seeds 1–10), at E-3 scale. The **external tracks**
  (14 AnalogGym amps, 4 LDO families, PROTOCOL §EXT / §EXT-LDO, 1000 evals/cell,
  N=10) are part of the full tier because the ROADMAP G1 falsifier binds on them
  (§6). **None of this runs until the human check-in authorises it.**

### 4.3 Contamination ledger — declared here per PROTOCOL v1.1 / G0-FAIRNESS

The in-house 7 and dhruva are **NOT fresh** — they are **regression floors**
(G0-FAIRNESS §1, categorical table). Per the G0 instruction, a contamination
ledger is therefore **not required** for these tasks (freshness is the property a
transfer-tier ledger fences, and these tasks are declared not-fresh regression
floors). Stated explicitly so the omission is a declaration, not an oversight.
For completeness, and because the racing arm imports only harness code:

```yaml
contamination_ledger:
  run_id: "E6-racing-<task>_s<seed>"
  scope: "in-house regression floors — NOT fresh (G0-FAIRNESS §1); ledger informational only"
  date: "2026-08-19"
  transferred_in:
    harness_code:  { allowed: always, description: "env.py, tasks.py, null_sizer.run_cmaes (verbatim), e6_racing.py adapter" }
    playbook:      { allowed: declared, present: false, declared: false }   # E-6 consults NO playbook (that is G3)
    seeds:         { allowed: never,   present: false, note: "generic seeds 1..N; no task-specific seed selection" }
    selectors:     { allowed: never,   present: false, note: "no motif/archetype selector; racing is a pure sizing arm" }
    calibrations:  { allowed: never,   present: false, note: "budgets are the pinned PROTOCOL §2 rows; k/r are fixed constants, not tuned on any task's convergence curve" }
```

The external tracks (full tier) **are** fresh-for-sizing (G0-FAIRNESS §1); their
per-cell ledger will be emitted with the full-tier artifact when it runs. k and r
are pre-registered constants chosen from E-3's *published* variance (§5), not from
observing any task's convergence live, so `calibrations.present: false` holds.

---

## 5. The variance data the k/r/culling choices rest on (read before choosing, no E-6 number seen)

Per-seed CMA-ES best-objective at each task's **matched budget**, read from the
registered `baseline_cmaes_*` result JSONs (these ARE the E-3 cold arm / the
`cmaes` null — a citation, not a new measurement):

| task | best | median | worst | feasible | incumbent evals→1st-feasible (earliest seed) |
|---|---:|---:|---:|---:|---:|
| wifi24-t2-a | −0.823 | −0.728 | +1.189 | 9/10 | 110 |
| gps-l1-t2-a | +7.907 | +7.920 | +8.007 | 0/10 | — |
| wideband-sdr-t2-a | −0.450 | +1.640 | +2.033 | 1/10 | 130 |
| dhruva-l1-t2-a | −0.788 | −0.252 | +1.288 | 6/10 | 250 |
| dhruva-l2-t2-a | −0.600 | +1.148 | +1.397 | 1/10 | 220 |
| dhruva-l5-t2-a | −0.298 | −0.272 | −0.044 | 10/10 | 230 |
| dhruva-s-t2-a | −1.184 | −1.150 | −0.964 | 10/10 | 210 |

Two facts drive the design: **(1) high across-seed basin variance** (wide
best↔worst spreads on wifi24 / dhruva-l1 / dhruva-l2) — the regime where triaging
basins can help; and **(2) late feasibility** (110–250 evals to first feasible) —
the triage signal at r≈15–39 evals is a *noisy* proxy for final quality, which is
exactly the top-1 risk recorded in §2.2 and §9. Racing is falsifiable precisely
because it might triage on noise.

---

## 6. Acceptance criterion and the binding falsifier (ROADMAP G1, verbatim)

Judged on the PROTOCOL §5 metrics (feasible-rate, tiebroken by median
best-objective; cross-task scale-free median-rank; evals-to-first-feasible as the
cost read) **plus** the G0 time-to-competence set (§7).

**Acceptance:** racing (arm B) **matches or beats** the full-budget incumbent
(arm A) at matched budget on the in-house scoring tasks (median-rank ≤ incumbent),
and — at the full tier — on the external tracks.

**Binding falsifier (ROADMAP §3 G1, verbatim):**

> *if racing loses at matched budget on the in-house tasks **and** both external
> tracks, budget-splitting dies as a family, not as an implementation.*

So E-6's family-level negative requires arm B to lose on **all three** tracks
(in-house **and** AnalogGym amps **and** LDOs) at matched budget. A loss on one
track and a win on another is *not* the family falsifier — it is a
where-it-helps result. The externals run **only at the full tier**; therefore the
falsifier **cannot be reached at the smoke tier** — smoke can only refute the
harness, never the hypothesis (§7).

---

## 7. Smoke's role — mechanics check only (binding scope limit)

The smoke tier (150 evals/arm/task, 3 seeds, in-house only) is a **mechanics
check**: it verifies that the triage → cull → warm-resume harness runs
deterministically, spends *exactly* the budget on both arms (env counter matched
to the digit), replays the survivor's triage prefix bit-identically, counts every
eval through the env (no side-channel ngspice), and writes append-only E-6 rows
without touching any existing table.

**Smoke numbers can REFUTE the harness, not CONFIRM the hypothesis.** A smoke
result where arm B beats arm A does *not* validate racing (150 evals is not a
matched budget, 3 seeds is not N, and the externals are absent). A smoke result
where arm B loses does *not* falsify racing (same reasons; the falsifier requires
the full tier + externals, §6). The smoke's only pass/fail is: *does the harness
run correctly and deterministically at matched evals?* The full tier — gated on a
human check-in — is what tests the hypothesis.

---

## 8. Deliberately NOT in scope (named so it is not smuggled in)

- **Memory / the playbook.** E-6 consults no store; the racing arm is
  memory-free. Warm-vs-cold with memory choosing the starting region is **G3
  (E-8)**, a separate rung. `playbook.present: false` in the ledger (§4.3).
- **The unattended loop.** Re-running the propose→diagnose→intervene loop is **G5
  (E-4 v2)**, gated on G1–G3 landing.
- **Any change to the incumbent configuration.** Arm A is the E-3 cold arm,
  unchanged — same `run_cmaes` defaults (σ₀=0.3, purecmaes λ/μ, restart on
  stagnation), same budget, same seeds. E-6 adds a challenger; it does not retune
  the champion.
- **Topology moves / move repertoire.** That is **G2 (E-7)**. Racing sizes the
  pinned topology only.

---

## 9. Open questions (queued, not guessed — recorded before the run)

| # | question | why it is queued, not decided here |
|---|---|---|
| **OQ-1** | Is **top-1** the right cull, or should a variance-aware **top-2** (with the survivor-budget-halving cost accepted) be measured as arm B′? | The triage signal at `r` evals is noisy (§5: feasibility is late), so top-1 can cull a slow-but-good basin. Top-1 is pre-registered because it is the *hypothesis-faithful* choice (unfragmented survivor); whether top-2 does better is a follow-up rung's question, not a mid-run decision. |
| **OQ-2** | Should `r` be a **fixed fraction** of budget (as chosen, §2.3) or **fixed absolute** across tasks? | A fixed fraction keeps triage cheap on big tasks but expensive (40–44%) on the 136/150-eval tasks. The fraction rule is frozen for this rung; whether a different r-schedule wins is a tuning question reserved to a future rung / user ruling (it would be a scoring-rule change under PROTOCOL §9 if it moved a published budget). |
| **OQ-3** | If racing wins on some tracks and loses on others at the full tier, is the ROADMAP "budget-splitting dies as a family" verdict reached, or is a where-it-helps result the outcome? | §6 reads the falsifier as requiring a loss on **all three** tracks. A mixed result is reported as where-it-helps; confirming that reading is the user's call at full-tier landing. |

The harness resolves none of these inside a run; it records the trace and they
stay queued.

### 9.1 Rulings (user, 2026-08-20 — recorded before the full-tier externals board landed)

- **OQ-3 RULED: §6 reading CONFIRMED.** The "budget-splitting dies as a family" falsifier fires only on a loss on all three tracks (in-house + amp + LDO); a mixed result is reported as where-it-helps. Note explicitly: ruled while the externals campaign was still running, before any externals result was visible — the in-house outcome (racing 3/7, median-rank 2 vs 1) was known.

- **OQ-1 RULED: B′ (top-2) only if the verdict warrants.** If E-6 lands mixed-or-better, a small pre-registered E-6b measures top-2 vs top-1; if racing loses on all three tracks, no follow-up is spent.

- **OQ-2 RULED: fraction schedule stands.** Revisit only if the E-6 trace data shows the small-task triage overhead cost wins, and then only as its own pre-registered change per PROTOCOL §9.

---

## 10. Artifacts + commit order

- (a) **this file**, committed **ALONE**, first — the pre-registration timestamp.
- (b) `engineer/e6_racing.py` (the racing arm B + the k/r/cull rule as code) +
  `engineer/e6_run.py` (the paired A-vs-B runner, reusing the E-3/score_run
  subprocess-per-cell + per-cell-trajectory patterns) — committed together with
  the smoke results.
- (c) results: `engineer/data/e6_smoke_v0.json` (the per-task × arm smoke board) +
  per-cell result JSONs `engineer/data/e6_{incumbent,racing}_<task>_s<seed>_b<budget>.json`
  + per-cell trajectory files under `engineer/data/_e6_traj/`, appended to a NEW
  era/provenance-stamped table `engineer/data/e6_trajectories.jsonl` (distinct
  from `trajectories.jsonl`; the canonical table is never rewritten — append-only
  law, charter §3.2) + this doc's post-hoc outcome section.

**Trajectory table discipline:** E-6 writes per-cell throwaway trajectory files
first, then appends them into its **own** `e6_trajectories.jsonl` in one serial
pass (the E-1/score_run precedent). The canonical `trajectories.jsonl` and every
existing store table are left byte-untouched.

---

<!-- POST-HOC OUTCOME SECTION APPENDED BELOW AFTER THE SMOKE RUN — NOT PART OF THE
     PRE-REGISTRATION. The text above this line is what was committed first, alone. -->

## 11. Smoke outcome (post-hoc — appended after the SMOKE run)

**Run:** 42 cells = 7 in-house tasks × 2 arms × 3 seeds (1–3) at **150 evals/cell**
(6,300 evals, 12,600 ngspice calls). Artifact: `engineer/data/e6_smoke_v0.json`;
per-cell result JSONs `engineer/data/e6_{incumbent,racing}_<task>_s<seed>_b150.json`;
trajectory rows appended to `engineer/data/e6_trajectories.jsonl` (E-6's own
table; the canonical `trajectories.jsonl` and every existing store table left
byte-untouched). Pre-registration SHA (commit that added this file, alone):
**`b46deff`**.

**This is the mechanics check of §7. It CANNOT confirm or falsify the hypothesis**
(150 evals is not the matched budget, 3 seeds is not N, the externals are absent —
§6). The numbers below are recorded for the record and to prove the harness; they
carry no verdict on racing.

### 11.1 The harness passed its checks (the only thing the smoke tests)

- **Matched budget, to the digit.** All **21** (task, seed) pairs spent *exactly*
  equal env evals across both arms (`budget_match_check.all_matched = true`). Every
  arm spent exactly 150 evals; the env's `BudgetExhausted` enforced it. The racing
  arm's triage (4×15=60) + survivor-resume (90 new) = 150, with the survivor's 15
  triage evals cache-replayed (not re-simulated) — matched to the incumbent's
  single 150-eval run.
- **Deterministic.** A racing re-run of `gps-l1-t2-a` s1 reproduced `best_obj`
  bit-for-bit (`7.938886` both runs); the env draws no RNG, `(task, arm, seed)`
  fully determines the sequence (PROTOCOL §7).
- **Warm-resume prefix is bit-identical.** The `_resume_objective` replay
  assertion (`e6_racing.py`) — which raises loudly if the survivor's re-run x
  diverges from its cached triage x by >1e-12 — **never fired** across all 21
  racing cells. This *proves* the survivor's warm-resume retraces its own triage
  trajectory exactly and then continues past it: a faithful warm resume expressed
  by a verbatim `run_cmaes` import (§2.1).
- **No side-channel evals.** Every eval went through the env counter (ngspice_calls
  = n_evals × gate factor for every cell). No writes under `lna/` (`git status
  lna/` clean); goldens GREEN before and after (§ report).

### 11.2 Smoke numbers (recorded, NOT a verdict — §7)

| task | incumbent med / best | racing med / best | smoke label |
|---|---|---|:---|
| dhruva-l1-t2-a | 1.5536 / 1.4880 | 1.6937 / 1.5536 | racing<incumbent |
| dhruva-l2-t2-a | 1.8227 / 1.4035 | 1.9699 / 1.9699 | racing<incumbent |
| dhruva-l5-t2-a | 1.4376 / 1.2223 | 1.3063 / 1.3063 | racing>incumbent |
| dhruva-s-t2-a | 1.4024 / 1.2894 | 1.7877 / 1.6842 | racing<incumbent |
| gps-l1-t2-a | 7.9148 / 7.9074 | 7.9247 / 7.9247 | racing<incumbent |
| wideband-sdr-t2-a | 1.9279 / 1.3755 | 1.2920 / 1.2920 | racing>incumbent |
| wifi24-t2-a | 1.2566 / 1.1454 | 1.3358 / 1.3358 | racing>incumbent(best) |

- **Feasible: 0/3 on both arms, every task.** At 150 evals nothing reaches
  feasibility on either arm — expected: the incumbent's own `evals-to-first-feasible`
  is 110–250 evals (§5), so a 150-eval cap on 3 seeds lands pre-feasible almost
  everywhere. This is a smoke-budget artifact, not a signal about racing.
- **Smoke median-rank:** incumbent=1, racing=2 (racing lost the median-obj tiebreak
  on 4 of 7 tasks, won 2, mixed 1). **This is meaningless as a hypothesis read**:
  racing's whole premise is that the survivor gets a *near-full* budget to descend
  the triaged basin, but at a 150-eval cap the survivor gets only 90 new evals after
  a 60-eval triage — the fragmentation the arm exists to *avoid* is re-imposed by the
  tiny smoke budget itself. At the full matched budgets (336–1050) the survivor gets
  276–894 evals, where the mechanism is actually exercised. The smoke deliberately
  runs racing in the regime it is *designed to lose*; that it does so, while spending
  exactly matched evals, only confirms the plumbing.

### 11.3 What the smoke establishes and what it defers

- **Established:** the triage → cull-top-1 → warm-resume harness runs
  deterministically at matched evals, replays the survivor prefix bit-identically,
  counts every eval through the env, and writes append-only E-6 rows without
  touching `lna/` or any existing table. **The harness is not refuted.**
- **Deferred to the full tier (human-gated):** whether racing matches/beats the
  incumbent at the *matched* budget and N=10, on the in-house tasks AND both
  external tracks — the only configuration in which §6's acceptance and the ROADMAP
  G1 falsifier can be reached. The full tier is NOT run here.

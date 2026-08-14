# E4-LOOP — the unattended propose→simulate→diagnose→intervene pilot (pre-registration)

**Status:** PRE-REGISTRATION. Written and committed **before any measurement
eval**, on branch `engineer`, executing **E-4** of `engineer/00-CHARTER.md` §6
(proposal N5). This file is the timestamp: its commit precedes every measurement
artifact produced under it. The charter's E-4 falsifier is stated verbatim in §7
below and this document is written so that the run can only confirm or refute it —
the task, the diagnosis→intervention rules, the tripwires, the novelty criterion,
the baseline, and the seed count are all fixed *here, before the loop runs a
single scored eval*.

This doc is short by intent, in `PROTOCOL.md` / `E3-MEMORY.md` shape: state the
task and why, the loop's structure (honoring the three §2 invariants
structurally), the diagnosis vocabulary and the (diagnosis → intervention) rule
table, the numeric tripwires, the novelty criterion, the baseline computation, N,
and the acceptance question + falsifier — **with rationale, before the run** —
then run, then append the outcome section (clearly marked post-hoc).

---

## 1. The task — `dhruva-l2-t2-a`, and why

**One task, pre-registered: `dhruva-l2-t2-a`** (spec `dhruva-l2`, wl_hash
`439032fd40e7e504`, 18 devices, budget 266 evals, nf-gated so 2 ngspice calls
per eval).

Why this one, from the charter's own guidance ("the interesting choices are the
hard-but-solvable ones where diagnosis+intervention can show value over blind
restarts"):

- **Hard-but-solvable under the null.** The registered `cmaes` null is **1/10
  feasible** at matched budget (`scoreboard_v0.1.json`): one seed solves it, nine
  do not — the exact regime where a diagnose→intervene policy can plausibly beat
  blind restarts, and where it is *falsifiable* (a saturated task like dhruva-l5
  10/10 or a hopeless one gps-l1 0/10 could not discriminate).
- **The near-misses are diagnosable, not random.** Reading the null's 10 stored
  best-point margin vectors (per-seed, `baseline_cmaes_dhruva-l2-t2-a_s*.json`):
  the nine infeasible seeds land with best objective **1.05–1.40** (near the
  feasible boundary at obj 0), and the **binding gate is `s11_max_db` on 6 of 9**
  (worst margin −0.03 to −0.39) with **`nf_db` binding on 2 of 9**. This is the
  `s11-knife-edge` signature (datastore `DIAGNOSIS_VOCAB`: "input match satisfied
  only on a razor-thin bias/VDD slice") plus an occasional `nf-wall`. A binding
  gate that is *named and consistent* is what a scripted diagnosis can read and a
  scripted intervention can act on.
- **The controlled-pair member.** `dhruva-l2` shares its topology with
  `dhruva-l1` (registry's one controlled pair); nothing in E-4 uses that, but it
  keeps the pilot on a task whose structure the program already understands.

Not chosen, and why (charter): `wifi24`/`dhruva-l5`/`dhruva-s` are near-saturated
for the null (9–10/10) — no headroom to demonstrate value; `gps-l1` is 0/10 with
a `gain-wall` the frontier already calls a topology problem, not a sizing one —
the diagnose step would immediately escalate with no sizing story to tell.

---

## 2. The loop — scripted policy, three invariants honored structurally

The loop is a **scripted policy, not an LLM**: diagnosis is a named,
controlled-vocabulary reading of the margin vector; intervention is a
pre-registered mapping from diagnosis to action. Both are frozen in §3–§4 below
before the run. The loop is one bounded run of
**propose → simulate → diagnose → intervene**, repeated as *stages* until a
tripwire (§5) or convergence (feasible) stops it.

### 2.1 The three §2 process invariants, adopted structurally (charter E-4)

1. **Post-sim margin-table injection.** Every stage's diagnose step consumes the
   **full `env.observe()` margin/op vector** — the environment's semantics-in-state
   surface exists for exactly this (`env.observe()` returns the normalized margin
   vector, the binding side, and the per-device operating point of the best-so-far
   eval). The diagnosis is computed *from that vector every stage*, never from a
   summary or a stale reading.

2. **Verifier-never-edits-netlist role split.** Three code-separated components,
   with mutation authority isolated:
   - **`Proposer`** — runs one CMA-ES *stage* (a bounded slice of evals) from a
     given start-mean and search box on a given topology. It mutates the *design
     point*, never scores it and never decides convergence.
   - **`Verifier`** — reads `env.observe()`, computes the diagnosis (§3), and
     **gates** (feasible? converged? which gate binds, by how much?). It has **no
     mutation authority whatsoever**: it returns a `Diagnosis` value object and
     touches neither the env's design point, the box, nor the topology. This is
     enforced structurally — the `Verifier` class holds no reference through which
     it *could* mutate; it is handed a read-only `observe()` dict.
   - **`Intervener`** — the *only* component with mutation authority. It maps a
     `Diagnosis` to the next stage's action (§4): a new start-mean/box, or a
     topology move. The proposer proposes, the verifier verifies, the intervener
     intervenes — and only the last of the three writes.

3. **The escalation rule.** No convergence after **N_STAGE = 3** designer–verifier
   sizing loops ⇒ the problem is topology, not tuning ⇒ **escalate**. In
   unattended mode, escalate = **switch to the topology-move stage** (fire one
   `moves.py` move + `realize` + re-size), pre-registered in §4. If the topology
   stage also fails to converge within its own budget, the loop **STOPs and
   records** — it never silently keeps polishing. The escalation is a
   *pre-registered branch*, not a judgement call.

### 2.2 Memory use — consumed as STRUCTURE, not budget (E-3's §6.4 hand-off)

E-3 measured a negative: consuming the retrieved sizing lesson as *budget-splitting*
(K short CMA-ES starts) **hurt** (warm < cold, 7/7). E-3 §6.4's hand-off is
binding here: *"A memory arm that helps will have to consume the store's content
as structure or constraint … rather than as 'run more, shorter starts.'"*

E-4 therefore consumes the playbook **as structure**: the loop's escalation
branch consults the playbook (via the E-3 sidecar, so the cold twin exists) for a
**topology strategy** keyed to the binding failure signature — the store's
`s11-knife-edge` / `nf-wall` entries, if any qualify, **bias which `moves.py` move
class the Intervener fires first** (a diagnosis-steered move prior, proposal §1.4
item 3). Memory changes the *action distribution*, not the budget. **Any component
that consults the playbook runs through `memory_harness`'s paired primitive so
every warm loop is born with its cold twin** (charter hard constraint; §6 below).
If the run's memory consult yields no qualifying entry (a store-miss), the
Intervener falls back to `moves.py`'s own default move weights — and that
store-miss branch **is** the cold control, by construction, exactly as E-3's K=1
reduction was.

> Scope honesty: the memory consult only reorders the topology-move choice. The
> sizing stages (§4 rules D1–D3) are memory-free and identical warm and cold. This
> keeps the memory claim small and its cold control exact — the loop's headline
> (SPICE-min per feasible novel design) does not *depend* on memory; memory is
> measured as a paired warm/cold side-experiment on the escalation branch only, so
> a memory negative here (as in E-3) does not sink the loop and a memory positive
> is discriminated against its own cold twin.

---

## 3. Diagnosis — the controlled vocabulary (frozen before the run)

The Verifier reads `env.observe()['best']['margins']` (the normalized signed
slack per gate; ≥ 0 iff satisfied) and emits **one** `Diagnosis.signature` from
the closed set below, chosen by the **binding gate** (the supported gate with the
*minimum* margin) and its magnitude. Every signature is a token already in
`lna/datastore.DIAGNOSIS_VOCAB` — this loop invents no vocabulary.

| condition (on the best-so-far margin vector) | `signature` | reading |
|---|---|---|
| all supported gates margin ≥ 0 | `feasible` (terminal) | converged; STOP, record |
| binding gate = `s11_max_db`, margin ∈ [−0.5, 0) | `s11-knife-edge` | near-feasible, input-match bound |
| binding gate = `nf_db`, margin < 0 | `nf-wall` | noise-figure bound |
| binding gate = `s21_db`, margin < 0 | `gain-wall` | gain bound |
| binding gate = `idd_ma`, margin < 0 | `idd-wall` | supply-current bound |
| binding gate margin < −0.5 (far from feasible) OR sim-fail rate > TRIP_FAIL | `label-noise` | basin/search problem, not a single-gate story |

`feasible` is terminal (convergence). The five non-terminal signatures each map
to an intervention in §4. `s11-knife-edge` is split from a generic far-miss
because the null's own near-misses live there (§1) — it is the signature the
whole task hinges on.

---

## 4. Intervention — the (diagnosis → action) rule table (frozen before the run)

The Intervener (the only mutating component) maps the Verifier's `Diagnosis` to
the next stage's action. Rules are pre-registered here; the run only executes
them. `x*` = the best-so-far x-vector (`env.observe()['best']['x']`); `SIGMA0`,
`SHRINK`, `SHIFT` are the fixed constants below.

**Sizing-stage rules** (design point / box, memory-free):

| # | diagnosis | intervention (next sizing stage) |
|---|---|---|
| D1 | `s11-knife-edge` | **Re-seed CMA-ES mean from the near-feasible incumbent** `x*` (structure, not a random restart — E-3's lesson: seed a start's mean) and **tighten the box** (σ₀ → σ₀·SHRINK) so the search polishes the razor-thin match instead of wandering. |
| D2 | `nf-wall` / `gain-wall` / `idd-wall` | Re-seed mean from `x*`; **shift** the search emphasis by re-seeding with σ₀ unchanged (a fresh basin around the incumbent) — a single-gate wall that sizing can still move. |
| D3 | `label-noise` | The incumbent is a bad basin: **re-seed from a fresh independent draw** (`default_rng(stage_seed)`), σ₀ = SIGMA0 (a genuine restart — the only rule that abandons the incumbent). |

**Escalation-stage rule** (topology, fires after N_STAGE=3 non-converged sizing
stages — invariant 3):

| # | trigger | intervention |
|---|---|---|
| E1 | 3 sizing stages, still infeasible | **Consult the playbook** (paired warm/cold via the E-3 sidecar) for a topology strategy keyed to the binding signature; **fire one `moves.py` move** — a **diagnosis-steered prior**: `s11-knife-edge` → prefer `{match_elem_add, input_class_swap, feedback_add}`; `nf-wall` → prefer `{degen_add, cascode_add}`; else the move set's own weights. Then `realize` + build a fresh arena in the env + **re-size** the moved topology for one stage's budget. A moved topology whose wl_hash differs from the pinned one is a **candidate novel design** (§6). Warm = memory-biased move order; cold (store-miss / hermetic empty store) = `moves.py` default weights. |
| STOP | escalation stage also non-converged, or any tripwire (§5) | **STOP and record.** Never widen, never keep polishing. |

Constants (frozen): `SIGMA0 = 0.3` (null_sizer's own default), `SHRINK = 0.5`,
`N_STAGE = 3` (the charter's "three designer-verifier loops"), stage budget split
in §5.

**Per-stage seeds are deterministic** from the run seed: stage *i* uses sub-seed
`seed + i`. The env draws no RNG, so `(task, seed, stage sequence)` fully
determines the eval sequence and a re-run reproduces `best_obj` to ≤ 1e-6
(PROTOCOL §7).

---

## 5. Tripwires — numeric, pre-registered. On trip: STOP and record, never widen.

| tripwire | value | rationale |
|---|---|---|
| **total eval budget cap** | **266 evals** (= the task's matched budget) | The loop is compute-matched to the null it is judged against (PROTOCOL §2): a win must be a win at equal SPICE, not at more of it. The loop spends *at most* the same 266 evals the `cmaes` null spent. |
| **per-stage eval cap** | **⌊266 / (N_STAGE+1)⌋ = 66 evals/stage** | Four stages max (3 sizing + 1 escalation), each ≤ 66 evals; the last stage absorbs the remainder so the full budget is available but never exceeded. The env's `BudgetExhausted` enforces the global 266 hard. |
| **max designer–verifier loops** | **N_STAGE = 3** before escalation | Invariant 3, verbatim from the charter. |
| **wall-clock cap** | **10 min** per seed | dhruva-l2 is ~0.028 s/eval (nf-gated, 2 ngspice calls); 266 evals ≈ 8 s, so 10 min is a generous guard against a realize/ngspice hang, not a real constraint. |
| **NotSizable / sim-fail-rate trip** | escalation move that yields `NotSizable`, or a stage sim-fail rate **> TRIP_FAIL = 0.5** | A move the sizer refuses costs no evals (`NotSizable` raises before the budget is charged); the Intervener retries the move up to 5 times, then STOPs. A stage more than half sim-failures is a broken deck — STOP, do not keep spending. |
| **"no improvement in K stages" stop** | **K_NOIMP = 2** stages with best-obj improvement < 1e-4 | If two consecutive stages do not improve the global best objective, the loop is polishing noise — STOP and record (this can fire before N_STAGE if sizing stalls early). |

On **any** trip the loop STOPs and writes its trace. It never widens the box
beyond SIGMA0, never raises a cap, never adds budget. "Never widen anything"
(charter) is the rule.

---

## 6. Novelty criterion — pre-registered, scored honestly both ways

Read from how the store treats topology identity (`novelty.wl_features` /
`wl_hash`, the same hash `tasks.py` pins on): **a design is NOVEL iff it sits on a
topology whose `wl_hash` differs from the task's pinned topology
(`439032fd40e7e504`).** A **re-sized pinned topology is NOT novel** under this
reading — it is the incumbent structure at new device values. This is the natural
reading when topology moves fire (charter), and it is the strict one.

Consequence, stated before the run so the numbers cannot choose the definition:

- A **sizing-only** feasible result (rules D1–D3 converge on the pinned topology)
  is **feasible but NOT novel**.
- An **escalation** feasible result (rule E1: a `moves.py` move produced a new
  wl_hash, re-sized to feasible) is **feasible AND novel**.

The headline metric (§7) is reported **both ways** — SPICE-min per *feasible*
design and SPICE-min per feasible *novel* design — and scored against the
baseline honestly under each. If the loop only ever converges by sizing the
pinned topology, its "feasible novel design" count is **zero** and the headline
says so; that is a measured outcome, not a definitional escape.

---

## 7. The headline metric, the baseline, and the acceptance question

### 7.1 Headline metric (charter E-4, unchanged)

**SPICE-minutes per feasible novel design**, and (the both-ways read of §6)
SPICE-minutes per feasible design. SPICE-minutes = `ngspice_calls · seconds/call`
summed over every eval the loop spent, across all seeds, divided by the count of
feasible (novel) designs the loop produced. `ngspice_calls` is the env's own
counter (2 per eval, nf-gated); seconds/call is measured from the run's own
`cost.wall_s`, so the number is this box's actual SPICE cost, not an estimate.

### 7.2 The baseline — pre-registered computation (charter E-4)

The charter names the assisted/human-in-loop baseline and rules that *"the null
arms' cost-per-feasible from `scoreboard_v0.1.json` is a defensible floor."* I
adopt, **before the run**:

> **Baseline = the registered `cmaes` null's SPICE-minutes-per-feasible-design on
> `dhruva-l2-t2-a`, from `scoreboard_v0.1.json`.** Concretely: 10 seeds × 266
> evals × 2 ngspice calls/eval = 5,320 ngspice calls, at the null's measured
> seconds/call, produced **1 feasible design** (feasible-rate 1/10) — so the
> baseline cost-per-feasible is **all 10 seeds' SPICE / 1**. Both the null and
> the loop run the **same 10 seeds at the same 266-eval cap**, so the comparison
> is compute-matched by construction.

Why this is the defensible floor for "assisted mode" here: the null is the
*unassisted blind-restart* search — the very thing the diagnose→intervene loop
claims to improve on. The loop *replaces the human who would restart CMA-ES from a
better seed and tighten the box* with a scripted policy that does exactly that
from the margin vector. If the loop cannot beat the blind null's cost-per-feasible,
it cannot beat the assisted mode either (the assisted mode is strictly better than
blind), so the null is a **lower bound on the bar** — beating it is necessary, not
sufficient, and failing to beat it is a clean falsification. Stated before the
run per the charter; a richer human-in-loop number is not in the store to quote,
so quoting the null floor and *labeling it a floor* is the honest move.

**Novelty caveat on the baseline:** the `cmaes` null only ever sizes the pinned
topology, so its *feasible-novel* count is **0** — it produces no novel designs at
all. Against the **feasible-novel** headline the loop's bar is therefore "produce
*any* feasible novel design at ≤ the null's total SPICE," and the both-ways report
(§6) makes both comparisons explicit.

### 7.3 N — seeds

**N = 10 seeds, seeds 1..10** — the registered N (PROTOCOL §4), so the loop's
per-seed variance is measured on the same seed set as the null it is compared to.
The loop's variance matters (charter) and 10 seeds is what the null carries.

### 7.4 The acceptance question (stated before any number is seen)

> **Does the unattended loop produce a feasible (novel) design at fewer
> SPICE-minutes-per-feasible-design than the registered `cmaes` null on
> `dhruva-l2-t2-a`, at matched budget — without a human per iteration?**

### 7.5 The falsifier (charter §6 / §8, restated verbatim and made numeric)

> *Falsifier:* **the loop needs a human per iteration anyway, or costs more
> SPICE-minutes than the assisted mode.**

Made numeric for this run: the loop is **falsified** iff either

- (a) it cannot run to a recorded verdict on all 10 seeds without a human
  decision inside any iteration (any ruling it hits is *queued, not guessed* —
  §8 — and if a queued ruling *blocks* an iteration, that is a human-per-iteration
  failure and is reported as such); **or**
- (b) its SPICE-minutes-per-feasible-design (§7.1) **exceeds** the baseline floor
  (§7.2) — i.e. the loop spent more SPICE per feasible design than the blind null
  did.

**Pre-registered consequence (charter §4 "Nulls first"; §8):** this line reports
**whichever way it falls.** If the loop costs more SPICE per feasible design than
the null, that is published as the measured result and E-4's honest move is to say
so — charter §8: *"if the unattended loop costs more SPICE-minutes per feasible
design than the assisted mode it replaces … the honest move is to say so and
stop."* A loop that does not beat the floor is a **measured negative**, reported,
not buried.

---

## 8. Rulings queued, not guessed (charter E-4)

Anything reserved to the user stays a queued question in the report, never a
guess inside the loop. Opened by this pre-registration:

| # | queued ruling | why it is the user's, not the loop's |
|---|---|---|
| **Q-1** | **Is the `cmaes`-null-cost-per-feasible an acceptable stand-in for the "human-in-loop/assisted" baseline, or should an assisted-mode number be measured explicitly?** | The charter *permits* the null floor ("a defensible floor") but the true assisted baseline is not in the store. Choosing whether the floor suffices for the published headline is a protocol call (PROTOCOL §9 / R-5). The loop uses the floor and labels it a floor; whether that is the *final* baseline is queued. |
| **Q-2** | **If the escalation stage produces a feasible NOVEL topology, may it be admitted to the store / archetype library, and does that re-open the benchmark's pins?** | Admitting a new topology or freezing a benchmark is a user call (charter §4, R-5). The loop *records* any novel feasible design in its artifact; it does **not** write it to `lna/` or re-pin any task. |
| **Q-3** | **Escalation target when topology also fails — archetype library vs STOP.** | Proposal N5 names "escalate — to the archetype library or the rulings queue." This pilot pre-registers STOP-and-record as the unattended terminal (no human), and queues whether a future loop should instead hand off to the archetype-library expansion. |

The loop **never** resolves these inside an iteration; it records the trace and
these stay queued. No ruling is guessed.

---

## 9. Artifacts + commit order

- (a) **this file**, committed ALONE, first — the pre-registration timestamp.
- (b) `engineer/loop_run.py` (+ the `Proposer` / `Verifier` / `Intervener`
  classes and the diagnosis/intervention tables as code) — committed together
  with any small helpers.
- (c) results: `engineer/data/loop_v0.json` (per-seed traces + the headline) +
  this doc's post-hoc outcome section (§10) + the README E-4 section.

**Canonical trajectory table:** per the E-3 precedent, the loop writes **per-run
throwaway trajectory files** via `env.py`'s `traj_path=` hook and **leaves the
canonical `engineer/data/trajectories.jsonl` UNTOUCHED** (the E-3 memory harness
did the same). No guarded serial append is performed for this pilot; the choice is
stated here so it is not a silent one.

---

<!-- POST-HOC OUTCOME SECTION APPENDED BELOW AFTER THE RUN — NOT PART OF THE
     PRE-REGISTRATION. The text above this line is what was committed first. -->

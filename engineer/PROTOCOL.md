# PROTOCOL v0 — the `engineer` benchmark's scoring protocol (pre-registration)

**Status:** PRE-REGISTRATION DRAFT. Written and committed **before any scoring
run**, on branch `engineer`, executing **E-2** of `engineer/00-CHARTER.md` §6.
This file is the timestamp: its commit precedes every result JSON produced under
it. The charter's E-2 falsifier is *"a result table where the protocol was
decided after the numbers were seen"* — the ordering (this file committed alone,
first) is what forecloses it.

**This is a draft, not a freeze.** Freezing protocol v0 as *the* scoring rule of
the benchmark is ruling **R-5 / E-5**, reserved to the user (charter §4, §7).
Nothing here freezes anything; it pre-registers the rule the first result table
is produced under, and queues the freeze decision.

This document is short by intent. It is `lna/plans2/16-WP-LIN.md`'s
pre-registration discipline applied to a benchmark scoring run: state the task
set, the budget, the arms, the seeds, the metrics, the aggregation, and the
accounting — **with rationale, before the run** — so that the numbers cannot
have chosen the protocol.

---

## 1. Task set — the 7 scoring tasks

The scored set is exactly `tasks.SCORING`: the 8-task registry v0 minus
`wifi24-smoke`, which is the end-to-end seam check and is *not* a scoring task by
construction (charter §5, R-4; its budget is ~45% of the matched one and it is
expected to land infeasible).

| task id | spec | wl_hash | dev | budget (evals) | ref feasible | era |
|---|---|---|---:|---:|:---:|---|
| `wifi24-t2-a` | wifi24 | 4b351a49fa6e4f23 | 10 | 336 | True | current |
| `gps-l1-t2-a` | gps-l1 | 82e8ca6a4cc02a43 | 6 | 136 | False | current |
| `wideband-sdr-t2-a` | wideband-sdr | e56f5b775362195d | 6 | 136 | False | current |
| `dhruva-l1-t2-a` | dhruva-l1 | 439032fd40e7e504 | 18 | 392 | True | current |
| `dhruva-l2-t2-a` | dhruva-l2 | 439032fd40e7e504 | 18 | 266 | True | current |
| `dhruva-l5-t2-a` | dhruva-l5 | 46d1edb3be115fc5 | 9 | 1050 | True | current |
| `dhruva-s-t2-a` | dhruva-s | f578743ae13296d0 | 18 | 1030 | True | current |

All seven are **tier-2**. There is no tier-3 task and that is not an oversight:
`iip3_dbm` is `unsupported` in every spec until WP-LIN binds the two-tone
harness; `tasks.py --check` asserts the condition so the claim fails rather than
rots (charter §5). Every task is `era: current` — R-2 was executed 2026-08-14,
so the one pre-cutover asterisk (`wideband-sdr-t2-a`) is gone before the first
scoring run that includes it, exactly as R-2 recommended.

**Pins are load-bearing.** Each task is pinned to the exact stored L2 row
(`ref_ts`) its budget comes from; `env._pinned_row` fails loudly if that row is
gone, and `tasks.py --check` re-derives the pins from the live store. The
protocol inherits those pins unchanged — it does not re-select rows.

---

## 2. Sim budget per task — the matched budget, stated before the run

**The budget is the pinned reference row's own eval count** (`tasks.py`'s
`budget`, = `ref_evals` for every scoring task): 336 / 136 / 136 / 392 / 266 /
1050 / 1030 evals respectively. This is the S11 / AnalogGym rule — *baselines are
compute-matched or they are decoration* — applied per task: every arm gets the
same budget the incumbent ZOAF row spent, so a win is a win at equal compute and
not at more of it.

`wideband-sdr-t2-a`'s budget **stays 136** (charter R-2): its pinned row is an
era-relabel that carries `n_evals=0` by construction (a re-label measures one
stored point once, it is not a campaign), so the budget is inherited from the
original 136-eval campaign. Pre-registered so the number cannot be adjusted later.

### 2.1 Eval accounting (confirmed from `env.py`, not assumed)

- **One eval = one call of `make_objective`'s objective**, counted by
  `Env.n_evals`. `Env.evaluate` raises `BudgetExhausted` on the eval *after* the
  budget is spent, so an arm spends *exactly* `budget` evals, never `budget+1`
  (`env.py` L487–490). A generational algorithm therefore stops on the eval, not
  the generation — the compute-match the benchmark rests on.
- **When the spec gates NF, one eval is two ngspice calls** and both are counted:
  `Env.ngspice_calls == n_evals * (2 if nf_gated else 1)` (`env.py` L460–461).
  The budget is stated in **evals**, so it means the same number of ngspice
  invocations for every arm alike, and the same number FINDINGS §43.2's null-sizer
  table meant. The per-run JSON records both `n_evals` and `ngspice_calls`.
- **Budgets are per-arm, per-seed.** Each (task, arm, seed) cell gets the full
  task budget; the budget is not shared or divided across seeds or arms.

---

## 3. Arms

Two arms, both **untuned nulls**, because the charter's bar is *nulls first,
always* (§4; survey conclusion 7). Future agent / memory arms (E-3, E-4) slot in
*against these two* at the same budget — the nulls are the fixed reference the
benchmark is built to measure improvement over.

| arm | driver | what it is |
|---|---|---|
| `cmaes` | `baseline_run.py` → `lna/null_sizer.run_cmaes` | CMA-ES (Hansen purecmaes defaults, box by clipping), **imported verbatim** from `lna/null_sizer.py` — the same CMA-ES FINDINGS §43.2's "CMA-ES beats ZOAF at matched budget" is a claim about. |
| `random` | `random_run.py` | uniform random search in `[0,1]^d` (`numpy.default_rng`), the untuned null any search claim is stated against. |

Both are driven through `engineer/env.py`'s public API; the optimizer code is
**imported, never re-implemented** — two implementations of a baseline are two
baselines. ZOAF itself is not re-run here: its number for `wifi24-t2-a` is the
*published* §43.2 figure, quoted (not recomputed) beside the result, and its
stored row is each task's pinned reference.

---

## 4. N seeds = 5

**N = 5 seeds per arm per task**, seeds `1..5`.

Rationale, argued before the run: FINDINGS §43.2 — the one published result this
protocol's `wifi24-t2-a` row must be *consistent with* — used **5 seeds/arm**.
The charter (§6 E-2) instructs: match §43.2's 5 unless argued otherwise in this
doc. Matching it is the right call: the `wifi24-t2-a` row is a **reproduction
check** of §43.2 (see §8), and a reproduction at a different N is not a clean
reproduction — a drift could be N, not the harness. Cross-task and cross-arm
comparability also wants one N, and 5 is the one §43.2 fixed.

**Noted, not adopted:** the survey's model, AnalogGym (S11), runs **10 seeds**.
Ten would tighten the medians and the feasible-rate estimates. The deliberate
deviation to 5 buys exact consistency with the program's own published null
table; raising to 10 later is a *number* change (re-run everything, §9), not a
*protocol* change, and is a reasonable thing for the freeze ruling (R-5) to
revisit. Recorded as a genuinely contestable choice, queued for the user.

---

## 5. Metrics + aggregation — fixed before results

### 5.1 Feasibility

Defined **exactly as `spec.feasible(metrics)`** returns it — no protocol-local
redefinition. A run is feasible iff its best-objective eval's metric vector
passes `spec.feasible` (which skips `unsupported` constraints, e.g. `iip3_dbm`).
The objective is `spec.objective(metrics)`; `feasible ⟺ best_obj < 0` is the
convention `env.py`/`null_sizer` already use and is recorded per run.

### 5.2 Per-run metrics (recorded in every result JSON)

1. **feasible** — bool, from `spec.feasible` on the best point.
2. **best objective** — `Env.best_f`, the min over the budget.
3. **evals-to-first-feasible** — the eval index of the first feasible point,
   **censored at the budget** (recorded as `null` / "> budget" if the arm never
   became feasible within budget). Reconstructed from the free `points` hook, no
   re-simulation.
4. **convergence curve** — best-so-far objective vs evals, sampled every
   `TRACE_EVERY` (=10) evals, from the same free hook (`trace_of`). No extra sims.

### 5.3 Aggregation across seeds (per task × arm)

- **feasible-rate:** `#feasible seeds / N` (e.g. `4/5`), the §43.2 headline shape.
- **best objective:** report **both** the median across seeds and the best
  (min) across seeds. Median is the robust central tendency; best is what a
  practitioner who runs 5 seeds and keeps the winner actually gets.
- **evals-to-first-feasible:** median across the *feasible* seeds, with the
  feasible count stated (a median over 2 of 5 seeds is labeled as such).
- **convergence curves:** per-seed curves retained in the artifact; the summary
  reports the per-seed curves' pointwise median.

### 5.4 Aggregation across tasks (chosen before results)

Two views, both pre-registered:

1. **Per-task tables** — the primary artifact. One row per (task, arm) with the
   §5.3 aggregates. No cross-task averaging of objectives (they live on different
   scales — an objective on `dhruva-l5` is not commensurable with one on
   `gps-l1`), so a mean-objective leaderboard is *forbidden by construction*.
2. **Median-rank summary** — the single cross-task number. On each task, rank the
   arms by (feasible-rate, then median best-objective as tiebreak); the summary
   reports each arm's **median rank across the 7 tasks**. Rank is scale-free, so
   it is the honest way to say "which arm wins more often" without pretending
   objectives from different specs add up.

This aggregation rule is fixed here, before any number is seen. Changing it after
results is forbidden without a user ruling (§9).

---

## 6. Modeling time vs simulation time — accounted separately (AnalogGym / S11)

The charter names AnalogGym's "modeling-time accounted separately from
simulation-time" as an E-2 requirement. For the two null arms the split is:

- **Simulation time** — the wall inside `arena.objective_func` (the ngspice
  call(s) + measurement). `Env.evaluate` already stamps each eval's
  `cost.wall_s` (`env.py` L491–493). The per-run **`sim_s`** is the sum of those
  per-eval walls; **`s_per_eval`** = `sim_s / n_evals`.
- **Modeling time** — everything the arm spends *not* inside the objective: the
  optimizer's own compute (CMA-ES covariance updates, random draws), env
  bookkeeping, trajectory logging. Measured as **`model_s` = total wall −
  sim_s**, where total wall brackets the arm's run loop.

For CMA-ES and random search `model_s` is expected to be a small fraction of
`sim_s` (both are cheap optimizers; the cost is the simulator). Stating it
separately is what makes that *measured* rather than assumed — and it is the
column that will matter when an LLM-agent arm (E-3/E-4), whose "modeling" is
model-inference latency, is scored against these nulls on the same axis. Both
numbers are recorded per run and surfaced in the scoreboard.

---

## 7. Determinism / replay

- **Seeds recorded.** Every result JSON carries its `seed`; the arm's RNG is
  seeded from it (`run_cmaes(..., seed)`, `default_rng(seed)`). The environment
  itself draws no random numbers (`env.py` module docstring), so
  `(task, arm, seed)` fully determines the x-vector sequence.
- **Harness stamps.** Every result carries `env.harness()` — `nf_gated`,
  `inductor_q`, `w_finger`, `era`, `stab_guard`, and the resolved dep paths
  (`harness.deps`, charter R-1's stamp). No number can be read without its
  harness provenance.
- **Re-run tolerance.** A re-run of the same `(task, arm, seed)` under the same
  harness era must reproduce **`best_obj` to ≤ 1e-6** (ngspice on this harness is
  deterministic; §43.2 reproduced a stored ZOAF row bit-for-bit, best_obj
  −0.7324616667). Any larger drift at fixed era is a harness or store problem and
  is flagged loudly, not absorbed — the replay-fence culture (charter §4).
  Wall-clock fields (`wall_s`, `sim_s`, `model_s`) are exempt from the tolerance;
  they are cost, not result.

---

## 8. §43.2 consistency check (declared before the run)

`wifi24-t2-a` at budget 336, N=5, arms `cmaes` and `random`, is a **reproduction**
of FINDINGS §43.2's published table:

| arm | §43.2 published (5 seeds, 336 evals) |
|---|---|
| random | 0/5 feasible, best +1.00, median +1.66 |
| cmaes | 4/5 feasible, best −0.790, median −0.649 |

**Acceptance, stated now:** the scored `wifi24-t2-a` row must match §43.2 **within
seed noise** — same feasible-rate (±1 seed is tolerable given RNG-plumbing
differences between the §43.2 harness and this env's driver; a different
feasible-rate by ≥2 seeds is a flag), and best/median objectives in the same
neighbourhood. §43.2 reproduced a stored ZOAF row bit-for-bit through the same
`make_objective` this env calls, so a *large* drift would mean a harness or store
problem and is reported loudly (charter §8: "if the environment's evaluations
ever stop being bit-identical to the LNA line's, the benchmark is measuring a
fork"). This check is the reason N is pinned at 5 (§4).

---

## 9. What changes numbers vs what changes the protocol

Recorded now so it cannot be rationalized later.

**Re-run everything (numbers change, protocol does not):**
- an **era cutover** — any shared-core change to what an evaluation computes
  (`lna/extract.py`, `size.py`, `to_spice.py`, the model card). All published
  numbers are re-measured under the new era; the old ones are quarantined, stamped
  with their era, never silently compared (charter §4).
- a **harness change** — same rule. The benchmark measures the simulator that
  exists; a stale core is how a benchmark quietly measures one that doesn't
  (charter §3.1 rule 2).
- a **pin move** — if `tasks.py --check` reports a pin drift, the affected task is
  re-pinned (a user/coordinator decision) and re-scored.

**Forbidden without a user ruling (protocol changes after results exist):**
- editing the **task set**, the **budgets**, **N**, the **metrics**, the
  **feasibility definition**, or the **aggregation rule** after any scoring number
  under this protocol has been seen. This is the E-2 falsifier; it is fenced by
  requiring a user ruling, queued as part of R-5.
- **freezing** protocol v0 as *the* benchmark scoring rule — R-5, the user's call.

Raising N from 5 to 10 (the AnalogGym default, §4) is a *number* change if done as
a clean re-run-everything under this same protocol; making 10 the *registered* N
is a protocol edit and therefore a user ruling. Both paths are queued for R-5.

---

## 10. Breadth — 8 in-house tasks is a pilot, not a benchmark

The charter says it in its own words (§6 E-2): *"8 in-house tasks is a pilot, not
a benchmark."* The scored set here is **7 in-house tier-2 tasks from this
program's own store**. That measures our sizer against our own nulls on our own
tasks — a real, compute-matched, replay-fenced statement, but a statement about
*our store*.

**The calibration set that makes "our sizer is good" a statement about more than
our own store is §1.1's AnalogGym externals** — the field's open op-amp / LDO
benchmark, run through a compatible harness. That is **out of scope for protocol
v0 and explicitly queued**: it requires real harness work (AnalogGym ships SKY130
op-amps, not our 45 nm RF decks; the env's deck-build, spec vocabulary, and
feasibility would need an externals adapter) **and** a user ruling to commission
it. This protocol scores the pilot honestly and names the pilot a pilot; it does
not pretend the pilot is the benchmark.

Queued for the user: **commission the AnalogGym-externals calibration work, yes or
no?**

---

## 11. Artifacts produced under this protocol

- Per-run result JSONs, existing naming convention, in `engineer/data/`:
  `baseline_cmaes_<task>_s<seed>_b<budget>.json`,
  `random_<task>_s<seed>_b<budget>.json`.
- One summary table artifact: `engineer/data/scoreboard_v0.json` — the per-task ×
  arm aggregates (§5.3), the cross-task median-rank summary (§5.4), the §43.2
  consistency check (§8), and the cost accounting (§6), plus the pre-registration
  commit SHA of *this file* so the artifact carries its own protocol provenance.
- A human-readable printout of the same, emitted by the runner.
- Trajectory rows appended to `engineer/data/trajectories.jsonl` under the
  append-only law (charter §3.2): the canonical table only ever grows, and the
  parallel runner writes per-run trajectory files first, then appends them to the
  canonical table in a single serial pass (E-1's throwaway-path precedent), so no
  two processes ever write the canonical file concurrently.

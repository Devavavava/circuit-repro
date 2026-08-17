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

---

### §43.1 Amendment — 2026-08-14 (user ruling)

**Ruling date:** 2026-08-14.

**What changed:** N (seed count) re-registered from **5 → 10**; seeds 1..10,
protocol otherwise unchanged.

**What did not change:** task set, budgets, arms, metrics, feasibility definition,
aggregation rule, §43.2 consistency-check acceptance criteria, determinism/replay
tolerance, artifact naming conventions. Protocol v0 is **adopted as the working
protocol** (not frozen — freezing remains R-5, the user's call as stated in §9).

**N=5 artifact retention (§43.2 reproduction):** The N=5 scoreboard
(`engineer/data/scoreboard_v0.json`, pre-reg SHA `870ea4f5587de246dbe14e11df944a47129ce315`,
produced 2026-08-14) is **retained on file as the §43.2 reproduction artifact**
— seeds 1–5 at N=5 are the claim that the harness matches FINDINGS §43.2's
published null table. It is not replaced by the N=10 run; it is the §43.2
consistency check's permanent record.

**N=10 artifact:** `engineer/data/scoreboard_v0.1.json`, carrying this amendment
commit's SHA as its `preregistration_sha`. Seeds 1–5 are identical runs to E-2
and must reproduce those cells bit-identically (best_obj ≤ 1e-6 tolerance per
PROTOCOL §7); seeds 6–10 are new. 7 tasks × 2 arms × 10 seeds = 140 cells.

**Rationale for raising N:** AnalogGym (S11) uses 10 seeds. Raising to 10
tightens feasible-rate and median-objective estimates without changing any protocol
rule. The deliberate cost is that the N=5 and N=10 tables are not
directly comparable on per-seed rank (the additional 5 seeds change medians), but
the aggregate §43.2 consistency check (seeds 1–5 only) is unchanged and
unambiguous. Pre-registered so numbers could not have chosen the N.

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

## 4. N seeds = 10 (amended 2026-08-14; see §43.1)

**N = 10 seeds per arm per task**, seeds `1..10`.

*Original rationale (N=5, pre-registration commit `870ea4f5587de246dbe14e11df944a47129ce315`):*
FINDINGS §43.2 used 5 seeds/arm; matching it was the right call for the first
scoring run because `wifi24-t2-a` is a reproduction check of §43.2 (§8), and a
reproduction at a different N is not a clean reproduction. That rationale produced
the E-2 N=5 artifact (`scoreboard_v0.json`), which is retained permanently as the
§43.2 reproduction (see §43.1).

*Amendment rationale (N=10, user ruling 2026-08-14):* AnalogGym (S11) uses
**10 seeds** as its standard. Raising to 10 tightens feasible-rate and
median-objective estimates. The §43.2 consistency check (§8) remains a seeds-1–5
comparison, so the reproduction is unambiguous. Seeds 1–5 are carried over
bit-identically from E-2; seeds 6–10 are new. Pre-registered before any new seed
was run.

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

---

## §EXT — External calibration track appendix (pre-registration)

**Status:** PRE-REGISTRATION, committed **alone and before any external scoring
run**, executing the charter's E-2 breadth item and §10's queued question
(*"commission the AnalogGym-externals calibration work, yes or no?"* — commissioned
by the user 2026-08-14, confirmed 2026-08-15). This appendix is the timestamp for
the external track exactly as the body of this file was for the in-house track: its
commit precedes every `scoreboard_ext_v0.json` cell. The E-2 falsifier — *"a result
table where the protocol was decided after the numbers were seen"* — is foreclosed
for the externals by this appendix being committed by itself, first.

**This appendix ADDS a track; it changes nothing above.** §§1–11 (the 7 in-house
tier-2 tasks, their pins, budgets, N=10, arms, aggregation, the §43.2 consistency
check, PROTOCOL v0's registered content) are untouched. The external tasks enter as
a **separate registry namespace and a separate tier** (`tier="ext"`): they are
op-amp / OTA sizing tasks (SKY130, ngspice), **not** RF, and the survey's finding
holds — AnalogGym is *"not a superset, a different domain"* (SURVEY §3 + S11: no
S-parameters, no NF-with-source-impedance, no two-tone). Nothing here re-pins or
re-scores an in-house task.

### §EXT.1 What the calibration measures, and why it is worth running

§10 named the pilot a pilot: the 7 in-house tasks measure our sizer against our own
nulls on *our own store*. The external track is the statement about **more than our
own store** — the field's open op-amp benchmark, run through a compatible harness,
with the **same two null arms at the same discipline**. If our sizer (CMA-ES, the
`null_sizer` arm) beats random on AnalogGym's amps too, "our sizer is good" stops
being a claim about the dhruva store and becomes a claim about analog sizing.

### §EXT.2 Adapter (the harness for this track)

`engineer/ext_gym.py`, pinned by its own sha256 in every result's harness stamp.
It builds an AnalogGym testbench into the same *contract* env.py exposes — an
`ExtEnv` with `objective_fn` / `evaluate` / `best` / `observe` / `harness`,
budget-counted, harness-stamped, deterministic (the env draws no random numbers) —
without editing env.py, tasks.py, or any driver (the E-1 falsifier, verified: the
`baseline_run`/`random_run`-shape drivers run against `ExtEnv` unchanged, and
`lna/null_sizer.run_cmaes` is imported verbatim as the cmaes arm). Simulator:
**`$NGSPICE` = ngspice-47** (AnalogGym pins ngspice ≥42; 47 satisfies it). PDK:
**SKY130** (`AnalogGym/repo/PDK/sky130_pdk`, tt corner, unzipped in place from the
bundled zip — contained, nothing system-wide). Upstream pin:
**CODA-Team/AnalogGym @ `0a9d1390ade361e2b4a2d33181e22367edbb8afc`** (BSD-3-Clause).

### §EXT.3 The "specs" — curated from AnalogGym, never invented

The charter's *"no new specs"* rule (§2, §5): AnalogGym's own testbench and FoM
**are** the specs. Pinned verbatim:

- **objective** = AnalogGym's amplifier FoM, the active (uncommented) `fom[i]` line
  of `perf_extraction_amp.py` at the pinned SHA, reproduced in `ExtSpec.objective`
  (a scalarization of gain / GBW / phase-to-60° / slew / power / area / settling /
  CMRR / PSRR, with AnalogGym's own `meas_real` rescalings). **Lower is better**, so
  it composes with the same `feasible ⟺ best_obj < 0`-style reporting the body uses.
- **failed-`.meas` semantics** = AnalogGym's own directional-worst-case defaults
  (a failed AC/tran measurement is scored at their `-1000` / `0` / `1000` sentinels,
  never NaN — SURVEY §3's *"`.meas` 'failed' tokens replaced by directional
  worst-case defaults"*), so the objective always sees a finite bad value.
- **feasibility** = a directional predicate over the SAME measured quantities the
  FoM rewards (real gain > 40 dB, a real unity-gain crossing, phase margin in a
  stable 0–120° band). Not a new spec: it encodes *"the deck elaborated and behaves
  like an amplifier"* — a failed/degenerate point sits at the sentinel and fails it.
- **box** = the design-variable KIND ranges (L/W multipliers, integer M, log CAP /
  CURRENT / RESISTOR spans), derived per amp from its own `design_variables` file
  and AnalogGym's own `__call__` decode; no per-amp hand-listing.

### §EXT.4 Task set — the ngspice-runnable subset (honest, with exclusions)

Established by simulating **every** amp at its shipped default sizing on ngspice 47
(the honest table + exclusion reasons live in `engineer/EXT-CALIBRATION.md`). The
scored external set is `ext_gym.RUNNABLE`: the **14 amplifiers** whose netlist
elaborates and produces finite AC metrics —

`Fan_SMC_Pin_3`, `HoiLee_AFFC_Pin_3`, `Leung_DFCFC1_Pin_3`, `Leung_DFCFC2_Pin_3`,
`Leung_NMCF_Pin_3`, `Leung_NMCNR_Pin_3`, `Peng_ACBC_Pin_3`, `Peng_IAC_Pin_3`,
`Peng_TCFC_Pin_3`, `Qu2017_AZC_Pin_3`, `Ramos_PFC_Pin_3`, `Sau_CFCC_Pin_3`,
`Song_DACFC_Pin_3`, `Yan_AZ_Pin_3` (dims 22–38).

**Excluded, with reasons** (never silently dropped): `Qu_LEC_Pin_3` (empty netlist
file upstream); `Tan_CLIA_Pin_3` (chopper amp, does not elaborate on ngspice 47);
`Cascode_Miller_Pin_2` / `Cascode_Null_Pin_1` / `Davide_ASMIHF_Pin_3` /
`TwoSt_SMCNR_Pin_2` (design_variables shipped without a netlist). `Alfio_RAFFC_Pin_3`
is runnable but degenerate at *default* sizing (dc gain < 0 → some `.meas` fail at
the default point); held out of the scored set so the golden anchors on a clean
default. **Whole categories out of scope** (need a simulator we do not have): LDOs
(ngspice testbenches present — **deferred to a follow-up rung**, amps first),
Charge Pump / PLL (Spectre + OCEAN), Sensing Front End (Spectre PTAT), Voltage
Reference (description only). This is SURVEY §1.1/S11's honesty: the runnable subset
is named, the rest is excluded *with the reason*, and no out-of-scope task is
counted.

### §EXT.5 Budget, N, arms, aggregation — same discipline as the body

- **Budget** = **1000 evals per (amp, arm, seed)** — AnalogGym's own stated budget
  (SURVEY §3: *"with a 1000-sim budget, constrained-BO reached FoM 4.2 …"*). One eval
  = one call of `ExtEnv`'s objective = **two ngspice calls** (an AC/DC deck and a
  Tran deck), both counted; the budget is stated in evals so it means the same
  number of ngspice invocations for every arm. **Budget-matched or it is
  decoration** (S11), applied per amp.
- **N = 10 seeds**, seeds `1..10` — the AnalogGym standard (S11; the same N §43.1
  amended the in-house track to).
- **Arms** = the **same two untuned nulls**: `cmaes` (`lna/null_sizer.run_cmaes`,
  imported verbatim — the same CMA-ES §43.2 is a claim about) and `random` (uniform
  in `[0,1]^d`, `numpy.default_rng(seed)`). Nulls first, always (charter §4).
- **Metrics per run**: feasible (bool, `ExtSpec.feasible`), best objective
  (`ExtEnv.best_f`, min over budget), evals-to-first-feasible (censored at budget),
  convergence curve (best-so-far every 10 evals, from the free points hook).
- **Aggregation across seeds** (per amp × arm): feasible-rate `#feasible/N`;
  best-objective **median AND best** across seeds; evals-to-first-feasible median
  over the feasible seeds. **Aggregation across amps**: per-amp tables (primary; **no
  cross-amp objective averaging** — the FoM scale differs by amp), plus a **median-
  rank summary** (rank arms per amp by feasible-rate then median FoM; report each
  arm's median rank across the 14 amps). Identical rule shape to §5.3/§5.4.
- **Modeling vs simulation time** accounted separately (§6): `sim_s` from the
  per-eval `cost.wall_s` the env stamps; `model_s` = total wall − sim_s.

### §EXT.6 Golden (before any scoring)

**Replay-fence golden** (no AnalogGym-shipped per-topology baseline table exists to
reproduce — AnalogGym ships training artifacts, an OP-normalization JSON, and an
HSPICE reference netlist, none of which is a stated ngspice operating point).
Therefore: **fixed sizing → fixed metrics**. Anchor amp `HoiLee_AFFC_Pin_3` at its
**shipped default sizing** reproduces, on this harness, dc gain **90.0754 dB**, GBW
**838366 Hz**, phase **8.0522°**, FoM **−85463.332359** — verified **3× in-process
and in a separate process, spread 0.000000**. Recorded as the adapter's golden in
`engineer/data/ext_golden_v0.json` and re-checked before the scoring run. Any drift
at fixed harness era is flagged loudly, not absorbed (charter §4).

### §EXT.7 Determinism / replay / stamps

`(amp, arm, seed)` fully determines the x-vector sequence (the env draws no random
numbers). Every result carries `ExtEnv.harness()`: `$NGSPICE` path + version, the
AnalogGym SHA, the adapter sha256, the pinned netlist/vars sha256, the PDK path, and
`domain: "op-amp (SKY130); NOT RF"`. Re-run tolerance: `best_obj` to ≤ 1e-6 at fixed
harness era (the golden's separate-process spread is 0.0). Wall-clock fields are cost,
not result, and exempt.

### §EXT.8 Artifacts

- Per-cell result JSONs in `engineer/data/`:
  `ext_cmaes_<amp>_s<seed>_b<budget>.json`, `ext_random_<amp>_s<seed>_b<budget>.json`.
- Golden: `engineer/data/ext_golden_v0.json`.
- Scoreboard: **`engineer/data/scoreboard_ext_v0.json`** — per-amp × arm aggregates,
  the cross-amp median-rank summary, cost accounting, and this appendix's
  pre-registration commit SHA as the artifact's protocol provenance.
- Trajectory rows to `engineer/data/ext_trajectories.jsonl` (the external tier's own
  append-only table, distinct from `trajectories.jsonl`).

### §EXT.9 What would change these numbers vs the protocol (fenced as §9)

Re-run everything (numbers change, protocol does not): a change to the adapter's
measured quantities (a new `ext_gym.py` sha256 is an era cutover for this track), an
ngspice change, or an AnalogGym re-pin. **Forbidden without a user ruling**: editing
the external task set, the 1000-eval budget, N, the metrics, the FoM/feasibility
definition, or the aggregation rule after any external number under this appendix has
been seen. Whether the external track joins a **future frozen protocol** (a benchmark
release including AnalogGym) is part of R-5 / E-5 — the user's call, queued, not an
agent's.

---

## §EXT-LDO — External LDO calibration track appendix (pre-registration)

**Status:** PRE-REGISTRATION, committed **alone and before any LDO scoring run**,
executing the follow-up rung the amp appendix (§EXT.4) and `EXT-CALIBRATION.md` §2.3
named and deferred: *"LDOs (ngspice testbenches present — deferred to a follow-up
rung, amps first)."* The amp rung is done (§EXT scoreboard); this is the LDO rung.
Commissioned by the user (2026-08-16, the LDO-rung commission). This appendix is the
timestamp for the LDO track exactly as §EXT was for the amp track: its commit
precedes every `scoreboard_ext_ldo_v0.json` cell. The E-2 falsifier — *"a result
table where the protocol was decided after the numbers were seen"* — is foreclosed
for the LDOs by this appendix being committed by itself, first.

**This appendix ADDS a track; it changes nothing above.** §§1–11 and §EXT are
untouched. The LDO tasks enter as a **third registry namespace and a separate tier**
(`tier="ext-ldo"`): they are SKY130 LDO sizing tasks (ngspice), **not** RF and
**not** the amp track. The amp adapter `ext_gym.py` and its golden are byte-for-byte
untouched (a re-stamp of `ext_gym.py` would be an §EXT.9 era cutover for the amps),
so the LDO rung lands as a **sibling module** `ext_ldo.py` with its own sha256.

### §EXT-LDO.1 What this measures

The same statement §EXT.1 makes, on a *second circuit class*: if our null arms
(CMA-ES vs random) order the same way on AnalogGym's LDO regulators as on its op-amps
and on our own dhruva store, "CMA-ES > random" stops being a claim about one topology
family and becomes a claim about analog sizing across classes. LDOs gate on different
numbers than op-amps — load/line regulation, PSRR, dropout, quiescent power, transient
under/overshoot — so this is a genuinely independent read, not a re-run of §EXT with
different netlists.

### §EXT-LDO.2 Adapter (the harness for this track)

`engineer/ext_ldo.py`, pinned by its own sha256 in every LDO result's harness stamp;
it imports `ext_gym`'s **pure utilities only** (dep-root walk-up, SPICE-number parse,
harness-stamp/JSON/trajectory helpers, `BudgetExhausted`) so the two adapters cannot
drift on the genuinely-shared plumbing, and shares **nothing that measures a number**.
It builds an AnalogGym LDO testbench into the same *contract* env.py / `ext_gym.ExtEnv`
expose — an `ExtLdoEnv` with `objective_fn` / `evaluate` / `best` / `observe` /
`harness`, budget-counted, harness-stamped, deterministic (the env draws no random
numbers) — without editing env.py, tasks.py, `ext_gym.py`, or any driver (the E-1
falsifier: the unedited `score_ext`-shape driver `score_ext_ldo.py` runs against
`ExtLdoEnv`, and `lna/null_sizer.run_cmaes` is imported verbatim as the cmaes arm).
Simulator/PDK/upstream pin identical to §EXT.2 (ngspice-47, SKY130 tt corner,
AnalogGym @ `0a9d1390ade361e2b4a2d33181e22367edbb8afc`).

**Deck handling — verbatim replay, not rebuild.** Unlike the amp adapter (which
rebuilds the 5-DUT deck), each LDO family ships a **complete self-contained**
`<fam>_acdc.cir` + `<fam>_tran.cir` with its own supply / Vref / Iload, node names,
and `wrdata` prefixes. The adapter **replays the shipped deck verbatim**, rewriting
only the three `.include ../simulations/*` lines to absolute (space-free staged)
paths, dropping the trailing `_dev_params.spice` OP-extraction include (it reads `.op`
vectors the reward does not use), and inserting the design-variable override right
after the vars include. AnalogGym's own testbench is the measurement, faithfully.

### §EXT-LDO.3 The "specs" — curated from AnalogGym, never invented

The charter's *"no new specs"* rule. Pinned verbatim from AnalogGym:

- **netlist (subckt)** = `Low Dropout Regulator/design_variables/<fam>.txt` — for the
  LDO category THIS file holds the `.subckt <fam> … .ends` (the inverse of the amp
  category's naming, verified by grep). Matched pairs are pinned by aliasing
  (`W_M1=W_M0`); the adapter sizes only the FREE base parameters and re-asserts the
  aliases, so an optimizer cannot break a mirror (the §EXT `m='4*…'` guarantee).
- **design vars** = `spice_netlist/<fam>_vars.spice` — the `.param` defaults, the only
  thing an optimizer touches; the golden's fixed point.
- **objective (reward)** = AnalogGym's OWN LDO reward. `perf_extraction_LDO.py` ships
  only the raw-metric *extractor* (no scalar); the scalar is the reward-engineering in
  `RGNN_RL/LDO_TB.py` — `self.reward`, a sum of **15 directional normalized-margin
  scores** `min((target−val)/(target+val), 0)` over LDR, LNR(max/min), Power(max/min),
  |vos|(max/min), PSRR(max/min), GBW(max/min), phase-margin(max/min), v_undershoot,
  v_overshoot, with the targets from `RGNN_RL/ckt_graphs.py GraphLDOtestbench`
  (`LDR 0.1, LNR 0.01, Power 9e-5/9e-6, vos 2e-3, PSRR −40 dB, GBW 2e6, PM 60°,
  under/overshoot 0.1`) and AnalogGym's own failure sentinels (a failed AC / negative
  LDR / positive PSRR scores −1). Reproduced verbatim in `LdoSpec.objective`,
  **negated** so lower-is-better composes with the amp track. **Deviation, recorded:**
  `LDO_TB.py` adds `CL_area_score + 10` when `reward ≥ 0`, where `CL_area_score ∈
  [−1,1]` is read from an OP decap our verbatim replay does not compute; we apply the
  `+10` plateau bonus at the same `reward ≥ 0` threshold and **omit only the ≤|1|
  decap nudge**, which cannot change a sign or the arm ordering at the feasibility
  boundary. Any future decision to compute the decap term is an §EXT-LDO.9 era cutover.
- **feasibility** = a directional predicate over AnalogGym's OWN scored quantities:
  feasible ⟺ every one of the 15 directional scores is 0 (all targets met — the
  reward's `≥0` plateau). Not a new spec: it encodes *"the LDO regulates and meets
  AnalogGym's own LDO targets."*
- **box** = the design-variable KIND ranges (L/W multipliers, integer multiplicities
  M / M_CL / M_Cfb / M_Rfb, log CURRENT), the shared `_KIND_BOX` shape, derived per
  family from its own `_vars.spice`; gate-bias voltages `Vb`/`Vb1`/`Vb2` are
  testbench-owned and never sized. No per-family hand-listing.

### §EXT-LDO.4 Task set — the ngspice-runnable subset (honest, with exclusions)

Established by simulating **every** shipped LDO family at its default sizing on
ngspice 47 (see `EXT-CALIBRATION.md` LDO section for the table + reasons). The scored
LDO set is `ext_ldo.FAMILIES`: the **4 families** whose acdc+tran testbenches
elaborate and produce parseable `wrdata` —

`ldo_1` (Basic-LDO lineage, d≈20), `ldo_2` (Basic-LDO lineage, largest, d≈57),
`ldo_simple` (d≈15, only family with positive dc gain at default), `ldo_folded_cascode`
(d≈21).

All four are **infeasible at default sizing** (uncompensated starting points, exactly
as the amps ship — the benchmark hands a search a bad start). **No family is
excluded**: unlike the amp category (empty netlists, chopper non-elaboration,
netlist-less design_variables), all four LDO families ship a subckt, both testbenches,
and a vars file, and all four elaborate. **Whole categories still out of scope** (need
Spectre/OCEAN we do not have): Charge Pump, PLL, Sensing Front End, Voltage Reference —
unchanged from §EXT.4.

### §EXT-LDO.5 Budget, N, arms, aggregation — identical to §EXT.5

- **Budget** = **1000 evals per (family, arm, seed)** — the same AnalogGym budget the
  amp track uses (§EXT.5). One eval = one `ExtLdoEnv` objective = **two ngspice calls**
  (the acdc deck + the tran deck), both counted. Budget-matched per family.
- **N = 10 seeds**, `1..10` — the amp track's N.
- **Arms** = the same two untuned nulls: `cmaes` (`lna/null_sizer.run_cmaes`, verbatim)
  and `random` (uniform `[0,1]^d`, `numpy.default_rng(seed)`). Nulls first (charter §4).
- **Metrics per run**: feasible (bool, `LdoSpec.feasible`), best objective
  (`ExtLdoEnv.best_f`, min over budget), evals-to-first-feasible (censored at budget),
  convergence curve (best-so-far every 10 evals).
- **Aggregation** — identical rule shape to §EXT.5 / §5.3-§5.4: per family × arm,
  feasible-rate `#feasible/N`, best-objective **median AND best** across seeds,
  evals-to-first-feasible median over feasible seeds; across families, per-family tables
  (primary; **no cross-family objective averaging** — the reward scale/plateau differs
  by family) plus a **median-rank summary**.
- **Modeling vs simulation time** accounted separately (§EXT.5).

**Cost note (not a protocol change):** LDO evals are markedly slower than amp evals
(the DC load/line sweeps + the 100 µs transient), measured ≈ 5–10 s/eval on the loaded
host at the LDO rung. The full 4×2×10×1000 = 80k-eval run is CPU-heavy; it runs at
≤ 56 workers **after the amp run drains**, and the wall-clock is reported in the
scoreboard cost block. The budget stays at AnalogGym's 1000 — shrinking it to save
wall-clock would be an unregistered scoring-rule change (§EXT-LDO.9-forbidden).

### §EXT-LDO.6 Golden (before any scoring)

**Replay-fence golden, per runnable family** (no AnalogGym-shipped per-topology ngspice
baseline exists — same reason as §EXT.6). Fixed default sizing → fixed metrics, each
family verified **3× in-process + a separate process**, spread within the established
**1e-6** replay tolerance. Recorded in `engineer/data/ext_ldo_golden_v0.json`,
re-checked before the scoring run. Any drift at fixed harness era is flagged loudly
(charter §4).

### §EXT-LDO.7 Determinism / replay / stamps

`(family, arm, seed)` fully determines the x-vector sequence (the env draws no random
numbers). Every result carries `ExtLdoEnv.harness()`: `$NGSPICE` path + version, the
AnalogGym SHA, **both** the `ext_ldo.py` and the imported-`ext_gym.py` sha256, the
pinned netlist/vars/acdc-tb/tran-tb sha256, the PDK path, and
`domain: "LDO (SKY130); NOT RF — ext-ldo tier"`. Re-run tolerance: `best_obj` ≤ 1e-6
at fixed harness era. Wall-clock fields are cost, not result, and exempt.

### §EXT-LDO.8 Artifacts

- Per-cell JSONs `engineer/data/ext_ldo_{cmaes,random}_<fam>_s<seed>_b<budget>.json`.
- Golden `engineer/data/ext_ldo_golden_v0.json`.
- Scoreboard **`engineer/data/scoreboard_ext_ldo_v0.json`** — per-family × arm
  aggregates, the cross-family median-rank summary, cost accounting, and this
  appendix's pre-registration commit SHA as the artifact's protocol provenance.
- Trajectory rows to `engineer/data/ext_ldo_trajectories.jsonl` (the LDO tier's own
  append-only table, distinct from `trajectories.jsonl` and `ext_trajectories.jsonl`).

### §EXT-LDO.9 What would change these numbers vs the protocol (fenced as §9)

Re-run everything (numbers change, protocol does not): a change to the LDO adapter's
measured quantities (a new `ext_ldo.py` **or** `ext_gym.py` sha256 is an era cutover
for this track — the LDO stamps both), an ngspice change, or an AnalogGym re-pin.
**Forbidden without a user ruling**: editing the LDO family set, the 1000-eval budget,
N, the metrics, the reward/feasibility definition (including whether to compute the
omitted decap bonus term), or the aggregation rule after any LDO number under this
appendix has been seen. Whether the LDO track joins a **future frozen protocol** is
part of R-5 / E-5 — the user's call, queued, not an agent's.

---

## §FREEZE — Protocol v1.0 FROZEN (user ruling 2026-08-16)

**User ruling, verbatim (2026-08-16, after LDO landing):** *"freeze after LDO lands"*.

**Status: PROTOCOL v1.0 FROZEN.** Executed on 2026-08-16, after both external
calibration rungs landed their results. This section is the R-5 / E-5 ruling the body
of this document queued from its first line (*"Freezing protocol v0 as the scoring rule
of the benchmark is ruling R-5 / E-5, reserved to the user"*). The user has called it.

### What is frozen

**Protocol v1.0** = the union of:

1. **In-house track** (§§1–11): 7 in-house tier-2 tasks (N=10 per §43.1), two null
   arms (`cmaes` = `lna/null_sizer.run_cmaes` verbatim; `random` = uniform `[0,1]^d`),
   budgets per-task as pinned, feasibility = `spec.feasible` exactly, aggregation =
   per-task tables + scale-free median-rank (no cross-task objective mean), modeling vs
   simulation time accounted separately.

2. **External amp track** (§EXT): 14 AnalogGym op-amp families (ngspice-runnable
   subset, honest exclusions in `EXT-CALIBRATION.md`), same two null arms, budget 1000
   evals/cell (AnalogGym's own), N=10.

3. **External LDO track** (§EXT-LDO): 4 AnalogGym LDO families (all runnable families,
   no exclusions), same two null arms, budget 1000 evals/cell, N=10.

**Current aggregation rules** (as written in §5.3/§5.4 / §EXT.5 / §EXT-LDO.5) are
frozen: per-task/per-family tables (primary), plus cross-task/cross-family median-rank;
no cross-task/cross-family objective averaging.

### Frozen baseline results

The following scoreboard artifacts are the **frozen baselines** under protocol v1.0:

| track | scoreboard | preregistration SHA | cells |
|---|---|---|---:|
| in-house (N=10) | `data/scoreboard_v0.1.json` | `f9ea7f2` (§43.1 amendment) | 140 |
| external amps | `data/scoreboard_ext_v0.json` | `c21c53c` (§EXT appendix) | 280 |
| external LDOs | `data/scoreboard_ext_ldo_v0.json` | `8039ca6` (§EXT-LDO appendix) | 80 |

### What is frozen means

- **Any future change to the task set, budgets, N, metrics, feasibility definition, or
  aggregation rule is a version bump (v1.1+), never an in-place edit of this file.**
- The pre-registration ordering discipline (protocol committed alone before any cell
  runs) applies to every future version.
- Era/harness changes (a new `ext_gym.py` sha256, a new ngspice, a pin move) still
  trigger a re-run-everything as §9 specifies; the frozen protocol governs what is
  re-measured and how it is aggregated, not what simulator is used.
- The in-house N=5 artifact (`data/scoreboard_v0.json`, §43.2 reproduction) is retained
  permanently as the §43.2 reproduction record and is not superseded by this freeze.

**Date of freeze: 2026-08-16. User ruling: "freeze after LDO lands."**

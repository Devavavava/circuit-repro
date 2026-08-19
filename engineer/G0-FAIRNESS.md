# G0-FAIRNESS — fresh-task rules, contamination ledger, time-to-competence

**Status: ADOPTED** per user ruling 2026-08-19. This document IS the G0 landing
as specified in `engineer/ROADMAP.md` §5 (rung G0: "a short doc defining 'fresh
task', the contamination ledger, and the time-to-competence metrics"). It takes
effect as normative text for protocol v1.1 (see `engineer/PROTOCOL.md` §V1.1).

Nothing here amends any v1.0 task definition, budget, metric, or scoring rule.
See §5 below.

---

## 1. Fresh-task definition

A task is **fresh** iff no component of the main line was tuned against it —
meaning: no task-specific seeds were chosen to land well on it, no motif
selectors were biased toward it, no archetype entries were added to handle it,
no budget calibrations were derived from it, and no recipe defaults were set
from its behaviour.

The negation is equally precise: a task is **NOT fresh** if any of the above
tuning occurred on it, whether or not the resulting artefact was ever labelled
as such.

### Categorical table

| Task category | Status | Rationale |
|---|---|---|
| The 7 in-house scoring tasks (PROTOCOL §1) | **NOT fresh** | Every stage of tuning — seeds, archetypes, motif selectors, budget calibrations, recipe defaults — was derived against dhruva/GNSS LNA variants and the wifi24/GPS/wideband-SDR family. These tasks are **regression floors**: they measure whether the engineer's changes broke the base. They are not the contest. |
| dhruva (all band variants) | **NOT fresh** | Primary tuning target of the main line across ~40 stages. |
| AnalogGym op-amp and LDO tracks (§EXT, §EXT-LDO) | **Fresh for sizing only** | No main-line tuning has touched these specs, topologies, or metrics. They serve as calibration that "our sizer works" beyond our own store. They are *not* the primary transfer scoreboard because the main line's sizing method (CMA-ES on the same harness) already ran on them under PROTOCOL v1.0 — they are calibration, not novelty. |
| G4 transfer-tier specs (not yet authored) | **Fresh** | Specified to be tasks the main line never touched: different band, different source impedance, or different power class. Subject to the contamination ledger (§3) on every run. |

The in-house 7 and dhruva are **regression floors**, not fresh tasks. AnalogGym
tracks are **fresh-for-sizing only** (the sizer was not tuned on them; but the
harness and null arms have now run on them, so they carry partial history). The
primary transfer scoreboard lives at G4 and beyond.

---

## 2. Why this definition is the right one

The ROADMAP §1 diagnosis is precise: tuned-main approximates an oracle on its
home benchmark because ~40 stages of human iteration encoded dhruva-specific
learning into seeds, archetypes, motif selectors, budget calibrations, and
recipe defaults. A fresh task is one where none of that encoding applies —
where the engineer and the main line start from the same blank slate.

The definition is stated in terms of the *tuning operations* (seeds / motif
selectors / archetype additions / budget calibrations / recipe defaults) rather
than in terms of topology or spec family, because the contamination vector is
the tuning, not the circuit class. A new GNSS band would be NOT fresh if a
prior stage had calibrated seeds against it; a completely new topology would be
fresh even if it superficially resembles dhruva, provided no tuning operation
targeted it.

---

## 3. Contamination ledger

Every fresh-task run (G4 and later) must emit a **contamination ledger YAML
block** as part of its result artefact. The schema is:

```yaml
contamination_ledger:
  run_id: "<run identifier — task_arm_seed or equivalent>"
  task: "<task id>"
  date: "YYYY-MM-DD"
  transferred_in:
    harness_code:
      allowed: always
      description: "env.py, tasks.py, drivers, adapters — the evaluation contract"
    playbook:
      allowed: declared   # R-C default: out; override requires user ruling per run or rung
      present: false      # true iff a non-empty playbook store was consulted
      declared: false     # true iff this run's pre-registration explicitly names the playbook entries used
    seeds:
      allowed: never
      present: false      # must be false for a fresh run to be valid
      note: "task-specific seed selection is contamination; all seeds must be generic (e.g. 1..N)"
    selectors:
      allowed: never
      present: false      # must be false; motif / archetype selectors tuned on any scored task are contamination
      note: "generic move graphs only; no task-specific motif or archetype selector"
    calibrations:
      allowed: never
      present: false      # must be false; budget calibrations or recipe defaults derived from this task are contamination
      note: "budget must come from the pinned reference row or the AnalogGym standard, never from a prior run on this task"
```

### Ledger rules

1. `harness_code.allowed: always` — the evaluation harness is always allowed in;
   it is not tuning, it is the measurement apparatus.

2. `playbook.allowed: declared` — the R-C default is `present: false` (playbook
   OUT). Playbook entries may enter a fresh-task run only if: (a) the run's
   pre-registration doc explicitly names the entries or categories used, and (b)
   the `declared` field is `true` and the `present` field is `true`. An undeclared
   warm-playbook run is a contamination violation. This is the structural fence
   corresponding to R-C's ruling: playbook is OUT of fresh-task runs by default;
   it enters only as the explicit variable in G3 (memory experiment) or a future
   rung that declares it.

3. `seeds.allowed: never` — task-specific seed selection is a form of tuning.
   Seeds for fresh-task runs must be generic (e.g. the standard 1..N sequence).
   Pre-existing seeds from the in-house tasks are not transferred.

4. `selectors.allowed: never` — motif selectors, archetype additions, and move
   priors tuned on any scored task (in-house or G4) are contamination.

5. `calibrations.allowed: never` — budget calibrations derived from a prior run
   on this specific task, or recipe defaults set from its behaviour, are
   contamination. Budgets come from the pinned reference row (in-house tasks) or
   the AnalogGym standard (external tracks), never from observing this task's
   convergence curve first.

6. A run where any `allowed: never` field has `present: true` is **invalid** and
   its numbers are not admitted to the transfer scoreboard.

7. The ledger is committed alongside the pre-registration doc, before any scoring
   run, exactly as PROTOCOL §9's pre-registration discipline requires.

---

## 4. Time-to-competence metrics

These metrics are **reported alongside** (not replacing) the existing PROTOCOL v1.0
endpoint scores (feasible-rate, best objective, median-rank). They answer the
question ROADMAP §2 poses: "how much of the 40-stage human journey can the
engineer traverse alone, how fast."

### 4.1 Metric definitions

| Metric | Definition | Units | Censoring |
|---|---|---|---|
| `spice_min_to_first_feasible` | SPICE-minutes elapsed (sum of per-eval `sim_s / 60`) at the eval index of the first feasible point | SPICE-minutes | Censored at budget if no feasible point found; recorded as `null` |
| `spice_min_to_tier2_feasible` | SPICE-minutes to first tier-2 feasible point (best_obj < 0 under the full tier-2 spec including all gated constraints) | SPICE-minutes | Same censoring; equals `spice_min_to_first_feasible` when the first feasible point already satisfies tier-2 |
| `wall_min_to_first_feasible` | Wall-clock minutes to first feasible point (from arm-run-start timestamp) | wall-minutes | Same censoring |
| `user_rulings_requested` | Count of mid-run user rulings requested by the agent or coordinator | integer | 0 for null arms (they request no rulings); recorded per run |

### 4.2 Recording convention

- `spice_min_to_first_feasible` and `spice_min_to_tier2_feasible` are derived
  from the per-eval `cost.wall_s` stamps already recorded by `Env.evaluate`
  (PROTOCOL §6), summed up to the first feasible eval. No extra simulations.
- `wall_min_to_first_feasible` uses the arm's run-loop wall bracket (the same
  bracket PROTOCOL §6 uses for `model_s` = total wall − `sim_s`).
- `user_rulings_requested` is logged by the coordinator at the end of the run;
  for null arms it is always 0 by construction.
- These fields are added to the per-run result JSON alongside existing fields.
  The scoreboard aggregates them: median across feasible seeds (with feasible
  count stated), and median across all seeds (with censored values noted).

### 4.3 Why SPICE-minutes, not wall-clock minutes, is the primary axis

SPICE-minutes (simulator time) is hardware-independent and is the same unit the
PROTOCOL §6 cost-accounting already distinguishes from modeling time. An LLM-agent
arm whose "modeling" is model-inference latency will carry a larger `model_s` than
CMA-ES; SPICE-minutes isolates the question "how many simulator calls did it take"
from the question "how expensive is the optimizer itself." Wall-clock is reported as
a secondary for practitioners who care about end-to-end calendar time.

---

## 5. What this changes / what this does not change

### What this changes

- **Adds reporting axes.** Fresh-task runs must emit the contamination ledger
  (§3) and the time-to-competence metrics (§4) alongside the existing PROTOCOL
  v1.0 endpoint scores.
- **Defines the transfer scoreboard's fairness boundary.** G4 and later rungs
  operate under this definition of freshness; their pre-registration docs must
  declare their contamination ledger before any run.
- **Formalises R-C.** Playbook is OUT of fresh-task runs by default; the ledger
  makes compliance structural (a missing or non-`false` `playbook.present` with
  `declared: false` is a ledger violation, not a policy question).

### What this does not change

- **No existing rule is relaxed.** Pre-registration with falsifiers, goldens
  green before and after every landing, adopt-only-if-better, the two-line branch
  law, append-only stores, user rulings for protocol bumps — all unchanged.
- **PROTOCOL v1.0 task definitions, budgets, N, metrics, feasibility definition,
  and aggregation rules are untouched.** The 7 in-house tasks, 14 AnalogGym amps,
  and 4 LDO families run exactly as frozen. This doc adds axes; it does not
  redefine any existing axis.
- **The in-house tasks remain in the benchmark** as regression floors. They are
  not removed or deprioritised from the scoreboard; they are reclassified from
  "the contest" to "the floor," which is what ROADMAP §1's diagnosis implies they
  always were.
- **R-D (transfer spec authoring)** is deferred-moot: G4 has not started, so the
  question of whether authoring transfer specs requires its own protocol bump is
  moot until then. The default (transfer specs land with the protocol bump when G4
  starts) stands per the user ruling.

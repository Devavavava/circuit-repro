# E3-MEMORY — cold/warm-memory measurement (pre-registration)

**Status:** PRE-REGISTRATION. Written and committed **before any measurement
run**, on branch `engineer`, executing **E-3** of `engineer/00-CHARTER.md` §6.
This file is the timestamp: its commit precedes every paired warm/cold artifact
produced under it. E-3's falsifier is *"any memory claim published without its
cold control"* (charter §6); the harness this doc registers makes the cold
control structurally inseparable from the warm number, so the falsifier cannot be
reached by omission.

The failure this exists to prevent is named in `lna/plans2/15-ENGINEER-PROPOSAL.md`
§2.2 item 4: **AnalogAgent conflated warm-memory and cold-memory runs and muddied
its own headline.** When this line says "the playbook made the search better," the
cold-start control runs explicitly — same tasks, same budget, same seeds, memory
store empty — and every warm number ships beside its cold twin.

This doc is short by intent, in `PROTOCOL.md` / `16-WP-LIN.md` shape: state the
harness contract, the arm's rule, N/budget/tasks, and the acceptance question —
**with rationale, before the run** — then run, then append the outcome table
(clearly marked post-hoc).

---

## 1. The harness contract (`engineer/memory_harness.py`)

The harness makes the cold control so cheap that skipping it is never tempting:
**one call runs each cell TWICE and there is no warm-only artifact shape.**

- **Input:** an arm, the task set, seeds, budget (all inherited from `PROTOCOL.md`;
  the harness does not re-choose them).
- **One `run_pair(task, seed)` call produces both a warm and a cold cell.** The
  warm cell runs the arm against the **real** playbook store (`lna/playbook/`,
  read-only). The cold cell runs the *same arm, same seed, same budget* against a
  **hermetic empty store** (an empty temp directory injected via the sidecar
  override, §2). The paired artifact schema (`engineer-mempair-v0`) has a
  `warm` and a `cold` field and **no top-level warm-only key** — you cannot
  serialize a warm result without its cold twin. That is the structural fence.
- **Output:** `engineer/data/mem_pairs_v0.json` — per (task) the paired
  warm/cold aggregates across seeds, each warm number beside its cold twin, plus
  the plain-`cmaes`-null column quoted from `scoreboard_v0.1.json` for the
  three-way read (warm vs cold vs the registered null).

### 1.1 Hermeticity — how "cold" is enforced (charter hard constraint)

The playbook store under `lna/playbook/` is **NEVER mutated**. Cold is not
achieved by moving or emptying real files. It is achieved by an **engineer-side
sidecar** (`engineer/mem_playbook.py`) that imports `lna/playbook.py` read-only
and, inside a context manager, **temporarily rebinds the module attributes**
`playbook.ENTRY_DIR` / `playbook.EDGES` / `playbook.INDEX` to an empty temp
directory for the cold consult, restoring them after. `lna/playbook.py` is never
edited; the real store's bytes are never touched (proven by `git status lna/`
before and after). Warm consults use the real attributes unchanged, read-only —
the sidecar calls `load_entries` / `score_entry` and never any writer
(`_write_entry`, `append_edge`, `write_index`, `cmd_add`, `cmd_escalate`).

A cell records `store_fingerprint` = (n_entries, sha256 over the sorted entry
files it actually read). Warm cells carry the real fingerprint; cold cells carry
`n_entries=0`. A cold cell with a non-empty fingerprint is a harness bug and the
artifact asserts against it.

---

## 2. The arm — `pb-cmaes` (playbook-informed multi-start CMA-ES)

The simplest honest memory-consuming arm defensible against **what the store
actually contains**. The store is 40 qualitative engineering entries (rules,
strategies, diagnoses) — *not* per-parameter numeric priors keyed by topology
(read 2026-08-14; there is no numeric-prior schema to consume). So the arm is
designed to the store's real contents: it consumes a **retrieved strategy that
prescribes how to initialize a sizing search**, and nothing it cannot honestly
read.

### 2.1 What the arm reads

For each task the arm consults the playbook (via the sidecar, deterministic
integer scoring — `playbook.score_entry`, no embeddings) keyed by:

- **family** = the task's spec family (`dhruva`, `wifi24`, `gps-l1` → `gps`,
  `wideband-sdr`), plus `lna` and `any` are matched by the store's own wildcards.
- **analysis** = `sizing,search` (this arm is a sizer).
- **failure_signature** = the task's *active* signatures, derived from the spec's
  gated constraints, from the controlled vocabulary in `playbook.py`:
  nf-gated → `nf-wall`; s11 gated → `s11-knife-edge`; idd gated → `bias-regulation`.
- **keywords** = `multi-start,seed,coordinate,descent,idd`.

### 2.2 How store content maps to initialization (the rule, pre-registered)

The arm asks one question of memory: **does the store hold a sizing/search
strategy that prescribes a seeded, multi-start initialization?** Concretely, a
retrieved entry *qualifies* iff:

- its `type` is `strategy` or `anti-pattern`, **and**
- its `trigger.analysis` includes `sizing` or `search`, **and**
- its rule/keywords speak to initialization: any of the keywords
  `{multi-start, seed, coordinate, descent, basin, log-uniform}` appears in its
  `trigger.keywords`.

The canonical qualifying entry in the v0 store is
**`search-must-be-seeded-from-physics`** (verbatim rule: *"Seed a multi-start
search from the circuit's own small-signal analysis against the measured
operating point, and use best-of-all-coordinates rather than first-improvement
descent."*) — it is the store's own instruction on how to start a sizing search.

**The mapping is score → K (number of starts):**

| top qualifying-hit score `s` | K (starts) |
|---|---|
| no qualifying hit (store-miss) | **1** |
| `1 ≤ s < 6` | 2 |
| `6 ≤ s < 11` | 4 |
| `s ≥ 11` | 6 |

The arm then runs **K-start CMA-ES**: draw K starting means from the run's own
`default_rng(seed)`, evaluate each once (these K evals count against the shared
budget), and begin standard `run_cmaes` from the **best-objective** start mean —
"best-of-all-coordinates," exactly as the rule prescribes. Everything after the
seeded start is Hansen's purecmaes verbatim (`lna/null_sizer.run_cmaes`,
imported, never re-implemented — two implementations of a baseline are two
baselines). The score→K table and the qualification predicate are the whole of
the arm; both are frozen here before the run.

### 2.3 Store-miss ⇒ the plain null (this IS the cold control)

On a store-miss (empty store, or no qualifying entry) **K = 1**: one random start
mean drawn from `default_rng(seed)`, then plain `run_cmaes` from it. That is
**bit-identical** to the registered `cmaes` null arm's first step
(`run_cmaes` itself does `xmean = rng.random(n)` first). The cold twin, running
against the empty temp store, therefore reduces to the plain CMA-ES null by
construction — the reduction is structural, not a re-tuning. Warm and cold share
the same seed and the same budget; the *only* difference between them is whether
memory was present to raise K above 1.

**Budget note (compute-match, PROTOCOL §2):** the K probe evals are charged to
the same task budget through the env's own counter, so warm and cold spend
*exactly* `budget` evals each. A warm arm that spends K evals seeding has K fewer
evals of CMA-ES proper — memory has to *earn* its seeding cost inside the same
compute envelope. This is the honest version of "did memory help at matched
budget."

---

## 3. N / budget / tasks — inherited from `PROTOCOL.md` (do not re-choose)

- **Tasks:** exactly `tasks.SCORING` — the 7 tier-2 scoring tasks.
- **Budget:** each task's `PROTOCOL.md §2` matched budget (336 / 136 / 136 /
  392 / 266 / 1050 / 1030 evals), per arm, per seed, per warm/cold side.
- **N = 10 seeds**, seeds `1..10` — the amended registered N (PROTOCOL §4, user
  ruling 2026-08-14, §43.1). Warm and cold use the *same* 10 seeds.
- **Arms compared:** `pb-cmaes` warm vs `pb-cmaes` cold, read against the
  registered `cmaes` and `random` nulls from `scoreboard_v0.1.json`.

Determinism/replay is `PROTOCOL.md §7`'s unchanged: the env draws no RNG,
`(task, arm, warm|cold, seed)` fully determines the x-vector sequence, so a re-run
reproduces `best_obj` to ≤ 1e-6.

---

## 4. The acceptance question (stated before any number is seen)

> **Does the warm arm beat its own cold control at matched budget?**

Judged, per `PROTOCOL.md §5`, on the same metrics the scoreboard uses:
**(1) feasible-rate** (warm vs cold, per task), tiebroken by **(2) median
best-objective**, with **(3) evals-to-first-feasible** as the cost read. The
cross-task summary is the **median rank** of {warm, cold, cmaes-null} across the
7 tasks (PROTOCOL §5.4), rank being the only scale-free way to say "which wins
more often."

**Pre-registered consequence (charter §4, "Nulls first"; §6 E-3):** this line
reports **whichever way it falls.** If warm ≤ cold at matched budget, that is
published as the measured result — a memory arm that does not help at matched
budget is a *measured result*, not a failure of E-3, whose deliverable is the
HARNESS. The only outcome that would falsify E-3 is a warm number shipped without
its cold twin, and the harness contract (§1) forecloses exactly that.

**What is out of scope for E-3 (named so it is not smuggled in):** an *agentic
loop* consuming these retrievals per iteration is E-4; this arm consumes memory
once, at initialization, which is the smallest honest memory-consuming behavior
that a cold control can discriminate. A richer numeric-prior store (per-topology
seed parameters) does not exist in v0 and inventing one would benchmark an
imagined schema — explicitly rejected here.

---

## 5. Artifacts + commit order

- (a) **this file**, committed alone, first — the pre-registration timestamp.
- (b) `engineer/mem_playbook.py` (sidecar) + `engineer/mem_arm.py` (the arm) +
  `engineer/memory_harness.py` (the paired runner), committed together.
- (c) results: `engineer/data/mem_pairs_v0.json` + this doc's post-hoc outcome
  table + the README E-3 section.

---

<!-- POST-HOC OUTCOME TABLE APPENDED BELOW AFTER THE RUN — NOT PART OF THE
     PRE-REGISTRATION. The text above this line is what was committed first. -->

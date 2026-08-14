# `engineer/` — the engineer line

The product of this line is **the engineer, not the LNA**: an RF-grade agentic
analog-design environment, a benchmark over it, and the dhruva/GNSS LNA as the
flagship case study. It executes D-6 of `lna/plans2/15-ENGINEER-PROPOSAL.md`,
ruled by the user on 2026-08-14, and lives on the `engineer` branch.

**Read `engineer/00-CHARTER.md` first** — it is the binding document: what the
product is and why (the survey's measured gap), the non-goals, the two-line
management policy that governs how `engineer` and `main` share one repository,
the quality bar, the E-queue, and the open ruling queue.

## What's here

| File | What it is |
|---|---|
| `00-CHARTER.md` | the charter — scope, policy, queues, rulings |
| `env.py` | `Task` / `Env.evaluate` / `Env.observe` / `TrajectoryLogger`, and the runtime-dep shim that makes a fresh worktree work |
| `tasks.py` | benchmark registry v0 — 8 pinned tasks, all tier-2 |
| `baseline_run.py` | the end-to-end smoke: CMA-ES (imported from `lna/null_sizer.py`) through `env.py` |
| `random_run.py` | the E-1 falsifier: a random-search driver on `env.py`'s public API |
| `test_env.py` | the E-1 API-hardening tests (round-trip, foreign topology, non-sizable contract, loud dep-shim) |
| `E3-MEMORY.md` | the E-3 pre-registration: cold/warm harness contract, the `pb-cmaes` arm's rule, the acceptance question, and the post-hoc outcome table |
| `memory_harness.py` | the E-3 cold/warm harness: `run_pair(task,seed)` runs the arm warm **and** cold in one call — no warm-only artifact shape |
| `mem_playbook.py` | the read-only sidecar that consults the playbook hermetically (empty temp store for cold; never edits `lna/playbook.py` or its files) |
| `mem_arm.py` | the `pb-cmaes` arm: playbook-informed K-start CMA-ES, reducing bit-identically to the `cmaes` null at K=1 |
| `data/` | this line's own append-only store: `trajectories.jsonl` + result JSONs |

Everything under `lna/` is **read-only** from here. Nothing in this directory
writes to `lna/data/`; the two lines' stores are combined only by
`lna/sync_lines.py`.

## Run the smoke

~15–20 s of simulation, 150 evals, 300 ngspice calls.

```
python engineer/baseline_run.py
```

It prints the harness stamps, the CMA-ES diagnostics, the best point's spec
report and margins, and — beside them — the **336-eval published figures** from
`lna/FINDINGS.md` §43.2, marked NOT COMPARABLE. The smoke is `wifi24-t2-a`
stopped at ~45% of its matched budget; it is **expected to finish infeasible**,
and it exists to check the seam, not to score. It writes
`data/trajectories.jsonl` (one row per eval) and
`data/baseline_cmaes_wifi24-smoke_s1_b150.json`.

## Other entry points

```
python engineer/tasks.py --list [--long]   # the registry table (+ notes, ref_ts)
python engineer/tasks.py --check           # re-derive the pins from the live store
python engineer/env.py --selftest          # 3 evals + budget enforcement
python engineer/baseline_run.py --task wifi24-t2-a   # the matched 336-eval budget
```

## E-1 — API hardening (2026-08-14)

`env.py` v0 was one seam proven end to end; E-1 made it an API another driver can
hold. What landed:

**Tests (`python engineer/test_env.py`).** Four contracts, house style (a
`main()` that prints and `sys.exit(1)` on the first failure, no pytest):

- **round-trip** — `encode` inverts `make_objective`'s `decode` to ~1e-6 (the
  decode's own 6-sig-fig print precision), on the pinned deck *and* a foreign one.
- **foreign topology** — a topology that is **not** the task's pinned one is
  evaluated through `Env`: metrics returned, harness stamp present, exactly one
  trajectory row appended, and the foreign deck cached (a second eval builds no
  new arena). The topology is produced via `lna/moves.py` (read-only import).
- **non-sizable contract** — see below.
- **loud dep-shim** — a simulated resolution failure (bogus search roots,
  in-process, no files moved) raises loudly, naming the probe *and* the
  `LNA_DEPS_ROOT` override (charter **R-1**, executed).

**Failure semantics for a non-sizable topology.** `Env.evaluate` on a topology
the sizer declines (a floating subcircuit, or a biased netlist that is not
two-port — i.e. `size.prepared_body` returns `None`) raises **`NotSizable`**, a
`ValueError` subclass carrying the offending topology's `wl_digest`. The choice is
a **raise, not a structured infeasible result**: an infeasible result is a
measurement ("this deck ran and missed a spec"), and a non-sizable topology was
never a deck — returning a penalty objective would tell a search it explored a
point it could not have. The raise happens at `_arena_for` (the first `evaluate`
of that topology), **before any ngspice call and before the budget is charged**.
Being a `ValueError` subclass, existing `except ValueError` callers still catch it.

**Second driver / falsifier (`python engineer/random_run.py`).** A budget-matched
uniform-random-search driver written against `env.py`'s **public API only**,
mirroring `baseline_run.py`'s reporting shape with its own arm name (`random`). It
required **no edits to `env.py`** to run — the falsifier passed. On `wifi24-smoke`
(150 evals, 300 ngspice calls, seed 1) it lands **best objective 1.6629 at eval
124, infeasible** (nf_db −0.056, s21_db −0.607), the expected shape for the
untuned null at ~45% budget — read against FINDINGS §43.2's published random arm
(0/5 feasible, best +1.00 at the full 336) and marked NOT COMPARABLE.

**R-3** (the 1-in-1 op ring buffer) is adopted as the environment default,
unchanged — E-1's tests found no bug in it.

**Finding — `lna/moves.py`'s realize path is unavailable on this RHEL box.** The
move *operators* (`moves.mutate`) run here (netlist algebra), but the Eulerian
**re-tokenisation** (`moves.realize` → `templates.emit_sequence`) needs both the
gitignored `AnalogGenie/repo` clone and `pandas`, and **neither is present**
(`realize` swallows the `ImportError` and returns `None`). So the foreign-topology
test runs the mutation, then falls back to a stored L2 row's tokens for the
`Topology` it feeds to `Env` — the same `_arena_for` code path either way. This is
a dep-availability gap the shim does not cover (`_bind_runtime_deps` resolves
`zoaf` and the model card, not AnalogGenie), not a bug in `env.py`.

## E-2 — benchmark curation + scoring protocol (2026-08-14)

The registry (`tasks.py`) is a table; a benchmark is a table **plus a protocol**.
E-2 added the protocol and produced the first result table under it.

**The protocol is pre-registered.** `engineer/PROTOCOL.md` was written and
committed **alone, before any scoring run** — its commit is the timestamp that
forecloses E-2's falsifier ("a result table where the protocol was decided after
the numbers were seen"). It fixes, with rationale and in advance: the 7 scoring
tasks (smoke excluded), the matched per-task budget, the two null arms (CMA-ES,
random), the metrics (feasible-rate, best objective, evals-to-first-feasible
censored at budget, convergence curves), feasibility = `spec.feasible` exactly,
the aggregation rule (per-task tables + scale-free median-rank; no cross-task
objective mean), the modeling-vs-simulation time split, the determinism/replay
tolerance, the §43.2 consistency check, and what changes numbers
(era/harness/pin → re-run all) vs the protocol (task set/budget/N/metrics/
aggregation → forbidden without a user ruling). It does **not** freeze the
benchmark — that is ruling R-5, the user's call.

**User ruling 2026-08-14 (§43.1 amendment):** protocol v0 adopted as the WORKING
protocol (not frozen), and N re-registered **5 → 10**. See `PROTOCOL.md §43.1`.
Amendment commit: `f9ea7f2`. The N=5 artifact (`scoreboard_v0.json`) is retained
permanently as the §43.2 reproduction record (see below).

**Re-run it (N=10, the current registered count).**

```
python engineer/score_run.py                 # full 7 tasks x 2 arms x 10 seeds, parallel
python engineer/score_run.py --seeds 1       # fast shakedown
python engineer/score_run.py --cell wifi24-t2-a cmaes 1   # one cell
python engineer/score_run.py --aggregate-only             # rebuild board from JSONs
```

`score_run.py` **imports** `baseline_run.run` (CMA-ES) and `random_run.run`
(random) — the optimizers are not re-forked. Each `(task, arm, seed)` cell runs
as its own subprocess writing its own trajectory file; after all cells finish the
runner appends those into the canonical `data/trajectories.jsonl` in one serial
pass, so the append-only law holds under parallelism.

### N=10 result — `data/scoreboard_v0.1.json` (amendment SHA `f9ea7f2`, N=10)

140 cells: 7 tasks × 2 arms × 10 seeds. **66,920 evals / 133,840 ngspice calls**,
~131 s wall on a 128-way pool (~10,407 s simulation, modeling = 1.5% of wall).

| task | arm | feasible | obj median | obj best | evals-to-first-feasible |
|---|---|---:|---:|---:|---:|
| dhruva-l1-t2-a | cmaes | 6/10 | −0.2522 | −0.7875 | 345 |
| dhruva-l1-t2-a | random | 0/10 | +2.4091 | +1.6538 | — |
| dhruva-l2-t2-a | cmaes | 1/10 | +1.1478 | −0.6003 | 220 |
| dhruva-l2-t2-a | random | 0/10 | +3.0416 | +1.7081 | — |
| dhruva-l5-t2-a | cmaes | 10/10 | −0.2723 | −0.2980 | 425 |
| dhruva-l5-t2-a | random | 0/10 | +2.4402 | +1.6722 | — |
| dhruva-s-t2-a | cmaes | 10/10 | −1.1498 | −1.1836 | 275 |
| dhruva-s-t2-a | random | 0/10 | +1.7702 | +1.3601 | — |
| gps-l1-t2-a | cmaes | 0/10 | +7.9205 | +7.9074 | — |
| gps-l1-t2-a | random | 0/10 | +9.9008 | +8.8955 | — |
| wideband-sdr-t2-a | cmaes | 1/10 | +1.6401 | −0.4500 | 130 |
| wideband-sdr-t2-a | random | 0/10 | +2.0681 | +1.7334 | — |
| wifi24-t2-a | cmaes | 9/10 | −0.7280 | −0.8231 | 180 |
| wifi24-t2-a | random | 0/10 | +1.6408 | +1.0025 | — |

**Median rank:** CMA-ES = 1, random = 2 (no change from N=5). CMA-ES is feasible
on 5/7 tasks at N=10 (previously 4/7 at N=5 — `wideband-sdr` gained 1 feasible
seed at s10 and `dhruva-l2` gained 1 at s8). Random is 0/10 on every task.

**Rank changes vs N=5:** `wideband-sdr-t2-a` moves from 0/5 to 1/10 feasible for
CMA-ES (seed 10 finds a feasible point at eval 130); `dhruva-l2-t2-a` moves from
0/5 to 1/10 (seed 8 finds a feasible point at eval 220); `wifi24-t2-a` moves from
4/5 to 9/10 CMA-ES (5 new seeds of which 5 are feasible). These are genuine new
data, not harness drift. Median-rank ordering (CMA-ES beats random) is unchanged.

### §43.2 reproduction artifact — `data/scoreboard_v0.json` (N=5, SHA `870ea4f`)

The N=5 scoreboard is retained permanently as the §43.2 reproduction. **Seeds
1–5 reproduced bit-identically** from E-2 (best_obj matches to floating-point
equality across all spot-checked tasks; re-run tolerance ≤ 1e-6 per PROTOCOL §7):

| task / arm | E-2 best_obj | N=10 re-run best_obj (seeds 1-5 only) | delta |
|---|---|---|---|
| wifi24 cmaes s1 | −0.61918777 | −0.61918777 | 0 |
| wifi24 cmaes s3 | −0.56496790 | −0.56496790 | 0 |
| wifi24 random s1 | +1.66287320 | +1.66287320 | 0 |
| dhruva-l5 cmaes s1 | −0.18998092 | −0.18998092 | 0 |
| dhruva-s cmaes s1 | −1.18179327 | −1.18179327 | 0 |

**§43.2 consistency check (seeds 1–5 sub-aggregate):** CMA-ES 4/5 (best −0.785,
median −0.619) / random 0/5 (best +1.00, median +1.66) — matches published
CMA-ES 4/5 (best −0.790, median −0.649) / random 0/5 (best +1.00, median +1.66)
— **consistent within seed noise**, no harness or store drift.

## E-3 — cold/warm-memory measurement harness (2026-08-14)

Proposal §2.2 item 4: AnalogAgent conflated warm-memory and cold-memory runs and
muddied its own headline. E-3 is the harness that makes the cold-start control so
cheap that skipping it is never tempting — and **structurally inseparable** from
the warm number: `memory_harness.run_pair(task, seed)` runs the arm **twice**
(warm real store, read-only; then cold hermetic empty store) and the paired
artifact schema has a `warm` and a `cold` field and **no warm-only shape**. You
cannot obtain a warm result from this harness without its cold twin — that is
E-3's falsifier fence (*"any memory claim published without its cold control"*).

**Pre-registered.** `engineer/E3-MEMORY.md` was written and committed **before any
measurement run** (SHA `353f734`): the harness contract, the `pb-cmaes` arm's rule
(what it reads, the score→K map, store-miss ⇒ K=1), N/budget/tasks (inherited from
`PROTOCOL.md`), and the acceptance question. Its §2.2 phrasing was tightened
pre-run (SHA `c0c0451`, no measurement number seen) to the budget-sliced
multi-start a verbatim `run_cmaes` import can express.

**The arm — `pb-cmaes` (`mem_arm.py`).** Designed to what the v0 store *actually*
contains (40 qualitative engineering entries, not numeric priors). It consults the
playbook (deterministic integer scoring, no embeddings) keyed by the task's family
/ analysis=`sizing,search` / active failure signatures, and asks one question: does
the store hold a sizing strategy prescribing a **seeded multi-start** search? A
qualifying hit's score maps to K ∈ {2,4,6} starts; the arm runs K budget-sliced
CMA-ES starts and keeps the global best. `run_cmaes` is **imported verbatim** from
`lna/null_sizer.py`, never re-forked. **On a store-miss K=1 and the arm is
bit-identical to the `cmaes` null** — so the cold twin (empty store) *is* the plain
null, by construction.

**Hermeticity.** `mem_playbook.py` is a read-only sidecar: cold mode points
`playbook`'s module attributes at an empty temp dir for the cold consult and
restores them. `lna/playbook.py` is never edited; `lna/playbook/`'s bytes are never
moved or touched. The harness records a `store_fingerprint` per cell (warm = the
real sha256, cold = n_entries 0), refuses to report unless `git status lna/playbook`
is clean before and after, and asserts every cold cell saw an empty store.

```
python engineer/memory_harness.py                       # full 7 tasks x 10 seeds, paired
python engineer/memory_harness.py --tasks wifi24-t2-a   # one task
python engineer/memory_harness.py --cell dhruva-l1-t2-a 3   # one (task,seed) pair
python engineer/memory_harness.py --aggregate-only      # rebuild board from pair JSONs
```

### Result — `data/mem_pairs_v0.json` (prereg SHA `353f734`, N=10)

70 pairs, **66,920 evals** (warm + cold each spend the full matched budget). Every
warm number sits beside its cold twin; the `cmaes` null is quoted from
`scoreboard_v0.1.json` for the three-way read.

| task | side | K | feasible | obj median | obj best | verdict |
|---|---|---:|---:|---:|---:|:---|
| dhruva-l1-t2-a | warm / cold | 6 / 1 | 0/10 / 6/10 | +1.7819 / −0.2522 | +1.3730 / −0.7875 | **warm<cold** |
| dhruva-l2-t2-a | warm / cold | 6 / 1 | 0/10 / 1/10 | +2.2902 / +1.1478 | +2.1563 / −0.6003 | **warm<cold** |
| dhruva-l5-t2-a | warm / cold | 6 / 1 | 0/10 / 10/10 | +1.0560 / −0.2723 | +1.0266 / −0.2980 | **warm<cold** |
| dhruva-s-t2-a | warm / cold | 6 / 1 | 3/10 / 10/10 | +1.1016 / −1.1498 | −0.6886 / −1.1836 | **warm<cold** |
| gps-l1-t2-a | warm / cold | 6 / 1 | 0/10 / 0/10 | +8.0777 / +7.9205 | +7.9151 / +7.9074 | **warm<cold** |
| wideband-sdr-t2-a | warm / cold | 6 / 1 | 0/10 / 1/10 | +1.2833 / +1.6401 | +1.2833 / −0.4500 | **warm<cold** |
| wifi24-t2-a | warm / cold | 6 / 1 | 4/10 / 9/10 | +1.2080 / −0.7280 | −0.5140 / −0.8231 | **warm<cold** |

**Median rank (1=best):** `cold = 1`, `cmaes-null = 2`, `warm = 3`.

**Acceptance answer — does warm beat its own cold control?** **No: warm < cold on
all 7 tasks.** The playbook-informed multi-start *hurt* at matched budget —
splitting a fixed budget into K=6 short starts starves each of convergence. Memory
was retrieved correctly (K=6 on every warm cell), so this is a **measured
negative**, not a retrieval miss. Charter §4/§6 E-3: this line reports whichever
way it falls, and E-3's deliverable is the HARNESS, which discriminated warm from
cold cleanly. The cold column equals the registered `cmaes` null to the digit on
all 7 tasks (K=1 reduces `pb-cmaes` to `run_cmaes` exactly). **Hermeticity:**
`lna/playbook` clean before/after, all 70 cold cells saw an empty store. Full
write-up + the E-4 hand-off in `engineer/E3-MEMORY.md §6`.

## Environment

`python` 3.14 + numpy, `ngspice` on PATH, and the three gitignored upstream
clones (`misc/ZOAF`, `AutoCkt/repo`'s 45 nm model card, `AnalogGenie`). A fresh
`git worktree` has none of the clones; `env._bind_runtime_deps()` walks up to
find them (override `LNA_DEPS_ROOT` → this checkout → the git common dir's
parent → ancestors), rebinds the model-card path, and stamps what it resolved
into every result's `harness.deps` block. Whether that shim should instead be a
hard precondition is ruling **R-1** in the charter.

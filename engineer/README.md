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
random), **N=5 seeds** (matched to FINDINGS §43.2), the metrics (feasible-rate,
best objective, evals-to-first-feasible censored at budget, convergence curves),
feasibility = `spec.feasible` exactly, the aggregation rule (per-task tables +
scale-free median-rank; no cross-task objective mean), the modeling-vs-simulation
time split, the determinism/replay tolerance, the §43.2 consistency check, and
what changes numbers (era/harness/pin → re-run all) vs the protocol (task
set/budget/N/metrics/aggregation → forbidden without a user ruling). It does
**not** freeze the benchmark — that is ruling R-5, the user's call.

**Re-run it.**

```
python engineer/score_run.py                 # full 7 tasks x 2 arms x 5 seeds, parallel
python engineer/score_run.py --seeds 1       # fast shakedown
python engineer/score_run.py --cell wifi24-t2-a cmaes 1   # one cell
python engineer/score_run.py --aggregate-only             # rebuild board from JSONs
```

`score_run.py` **imports** `baseline_run.run` (CMA-ES) and `random_run.run`
(random) — the optimizers are not re-forked. Each `(task, arm, seed)` cell runs
as its own subprocess writing its own trajectory file; after all cells finish the
runner appends those into the canonical `data/trajectories.jsonl` in one serial
pass, so the append-only law holds under parallelism. The full run is
**33,460 evals / 66,920 ngspice calls**, ~90 s wall on a 70-way pool
(~4,050 s of simulation, modeling = 2.7% of wall).

**Scoreboard: `data/scoreboard_v0.json`** (+ the human printout the runner emits).
It carries the pre-registration SHA, the per-task × arm aggregates, the
median-rank summary, the cost split, and the §43.2 consistency check. Per-cell
result JSONs land as `data/{baseline_cmaes,random}_<task>_s<seed>_b<budget>.json`.

**First result (v0):** CMA-ES median-rank 1, random 2 across all 7 tasks. CMA-ES
is feasible on 4/7 tasks (5/5 seeds on dhruva-l5 and dhruva-s, 4/5 on wifi24,
1/5 on dhruva-l1); random is 0/5 on every task. The **§43.2 reproduction is
clean**: the scored `wifi24-t2-a` row is CMA-ES 4/5 (best −0.785, median −0.619)
/ random 0/5 (best +1.00, median +1.66) vs published CMA-ES 4/5 (best −0.790,
median −0.649) / random 0/5 (best +1.00, median +1.66) — **consistent within seed
noise**, i.e. no harness or store drift.

## Environment

`python` 3.14 + numpy, `ngspice` on PATH, and the three gitignored upstream
clones (`misc/ZOAF`, `AutoCkt/repo`'s 45 nm model card, `AnalogGenie`). A fresh
`git worktree` has none of the clones; `env._bind_runtime_deps()` walks up to
find them (override `LNA_DEPS_ROOT` → this checkout → the git common dir's
parent → ancestors), rebinds the model-card path, and stamps what it resolved
into every result's `harness.deps` block. Whether that shim should instead be a
hard precondition is ruling **R-1** in the charter.

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

## Environment

`python` 3.14 + numpy, `ngspice` on PATH, and the three gitignored upstream
clones (`misc/ZOAF`, `AutoCkt/repo`'s 45 nm model card, `AnalogGenie`). A fresh
`git worktree` has none of the clones; `env._bind_runtime_deps()` walks up to
find them (override `LNA_DEPS_ROOT` → this checkout → the git common dir's
parent → ancestors), rebinds the model-card path, and stamps what it resolved
into every result's `harness.deps` block. Whether that shim should instead be a
hard precondition is ruling **R-1** in the charter.

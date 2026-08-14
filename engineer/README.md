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

## Environment

`python` 3.14 + numpy, `ngspice` on PATH, and the three gitignored upstream
clones (`misc/ZOAF`, `AutoCkt/repo`'s 45 nm model card, `AnalogGenie`). A fresh
`git worktree` has none of the clones; `env._bind_runtime_deps()` walks up to
find them (override `LNA_DEPS_ROOT` → this checkout → the git common dir's
parent → ancestors), rebinds the model-card path, and stamps what it resolved
into every result's `harness.deps` block. Whether that shim should instead be a
hard precondition is ruling **R-1** in the charter.

# The `engineer` line

**Sources:** `engineer/00-CHARTER.md` (the binding document), `engineer/README.md`
(what's built + results), `engineer/PROTOCOL.md` (the scoring rules), and the
pre-registered experiments `engineer/E3-MEMORY.md`, `engineer/E4-LOOP.md`,
`engineer/E5-PACKAGING.md`, `engineer/EXT-CALIBRATION.md`.

This line lives only on the `engineer` branch. It builds directly on the LNA project
([03-lna-project.md](03-lna-project.md)) — read that first.

## The core idea

The LNA project produced a working pipeline. The `engineer` line reframes what the
*product* actually is:

> **The product is the engineer, not the LNA.**

Concretely, three artifacts:

1. **An environment** (`engineer/env.py`) — a budgeted, counted, deterministic,
   observable interface onto the golden-validated LNA simulation harness. Any
   search, agent, or unattended loop can run over it and be compared fairly.
2. **A benchmark** (`engineer/tasks.py` + `engineer/PROTOCOL.md`) — a frozen set of
   (spec, topology, budget, reference) tasks, each pinned to the exact stored result
   its numbers come from, scored under a protocol that is compute-matched by
   construction.
3. **A case study** — the "dhruva" GNSS LNA, carried to a verdict. It stops being the
   goal and becomes the demonstration that the environment measures something real.

## Why — the gap it targets

`engineer/00-CHARTER.md` argues from the survey of nine competing systems
(`lna/SURVEY-AI-CIRCUIT-DESIGN.md`): the field is full of **optimizers**, and the
interesting absences are the thesis of this line:

| The gap in the field | What this line has |
|---|---|
| No system has persistent memory beyond RAG | 40+ stages of (decision, evidence, outcome) distilled into a machine-queryable playbook |
| No system diagnoses root cause *before* acting | The LNA project's output-swing-wall diagnosis is the existence proof |
| No system runs a full engineering *loop* (propose → simulate → diagnose → intervene) | A loop shell with cadence + tripwires |
| The field's benchmarks have **no RF** | A harness with S-parameters, NF-with-source-impedance, cross-validated against a second engine to 0.08 dB |
| Evaluation hygiene is mostly absent | Head-to-head sizer comparison at matched budget (CMA-ES beat ZOAF 4/5 vs 1/5) |
| Nobody publishes trajectories | Every (state, action, outcome, cost) row written from day one |

The framing the charter reaches: this program is *already* an autonomous analog
engineer with the autonomy dial set to "assisted." The line's job is the missing
20% — usable memory, diagnosis that acts on search, and an unattended mode — built as
an increment on a working system and, above all, **measured**.

## The E-queue and its honest results

The line runs a queue of pre-registered experiments (E-1 … E-5). The discipline: each
experiment's design, acceptance criterion, and *falsifier* are written and committed
**before** any scoring run, so the result can only confirm or refute — the protocol
can't be reverse-engineered from the numbers.

- **E-1 — API hardening.** Turned the environment from one working seam into a real
  API another driver can hold, with round-trip, foreign-topology, and failure-mode
  tests.
- **E-2 — the benchmark protocol** (`PROTOCOL.md`), plus an external calibration track
  (`EXT-CALIBRATION.md`) that imports AnalogGym op-amp tasks as a separate tier — so
  "our sizer is good" is a claim about more than our own data. (AnalogGym has no RF,
  so it calibrates but doesn't extend the RF benchmark.)
- **E-3 — does memory help?** **Measured negative.** A playbook-informed multi-start
  search was run *warm* (memory on) beside its *cold* twin (empty store), 70 paired
  runs, ~67k evals. **Warm lost to cold on all 7 tasks.** Not a retrieval bug —
  memory was retrieved correctly; the negative is structural: splitting a fixed
  budget into several short starts starves each of convergence. The deliverable was
  the *harness* that cleanly separates warm from cold — and it did.
- **E-4 — does an unattended loop help?** **Measured negative / falsified.** A scripted
  (not LLM) propose→simulate→diagnose→intervene loop ran fully unattended on 10 seeds.
  It ran with no human per iteration (good), but produced **0 feasible designs where
  blind search produced 1**, at identical simulator cost. Same lesson as E-3:
  fracturing a fixed budget into short staged searches can't reach the near-feasible
  region a single full-budget run finds. The loop machinery worked — diagnoses fired,
  escalation produced genuinely novel topologies — the *result* was negative, and it's
  published as such.
- **E-5 — packaging** (`E5-PACKAGING.md`) — a *draft inventory* of what a public release
  would contain (license audit, data manifest, scrub list), written as one open
  question per row for the user to rule on. Nothing is released.

**The recurring theme:** two headline "AI engineer" features (memory, autonomous loop)
were tested honestly and *both lost to a plain baseline at matched compute*. That's the
point — the line exists to measure, and it publishes the negatives instead of burying
them. The mechanism (fixed-budget splitting) is now understood and named.

## How the two branches share one repo

`main` and `engineer` share the same working tree via a two-line policy in the charter:

- Everything under `lna/` is **read-only** from the engineer line. The engineer code
  imports from it (e.g. the CMA-ES sizer) but never writes to `lna/data/`.
- The engineer line keeps its own append-only store under `engineer/data/`. The two
  stores are combined only by an explicit sync tool.
- In practice the branches are checked out as **two worktrees** (`circuit-repro` on
  `main`, `circuit-repro-engineer` on `engineer`).

## Where things stand

The environment, benchmark, protocol, and external calibration are built and running.
The two big "does it help?" experiments returned honest negatives with understood
mechanisms. The case study (dhruva) has several sub-goals met and one measured wall
with a named next step. Packaging/release is drafted and waiting on user rulings —
nothing is published yet.

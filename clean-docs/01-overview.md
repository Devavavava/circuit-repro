# Overview — what this project is

## In one sentence

This project surveyed the field of "AI for analog circuit design," got the usable
tools running, and then used them to attack one concrete problem end to end:
**given a spec, generate a low-noise amplifier (LNA) circuit and verify it in a
SPICE simulator.**

## The two phases

**Phase 1 — Survey (`main`, top-level docs).**
Fifteen research papers/repos on machine learning for analog circuits were cloned,
given working environments, and smoke-tested — the goal was simply to prove each one
*runs*, not to reproduce its published results. Eight of eight repos with public code
now run and pass a smoke test; three had no public code at all. This phase answered
"what actually works, and what can we build on?"
→ See [02-repo-survey.md](02-repo-survey.md).

**Phase 2 — The LNA project (`main`, `lna/`).**
The survey picked a target: generate LNA topologies. It combined the one real
topology *generator* found (AnalogGenie) with a SPICE simulator (ngspice) and sizing
tools. The headline result: a simple sampling trick ("prefix conditioning") took the
rate of generating LNA-shaped circuits from **0% to 40.6% with no model retraining**.
The project then went much deeper — bias insertion, device sizing, a real target
spec, fine-tuning, and honest measurement of what does and doesn't help.
→ See [03-lna-project.md](03-lna-project.md).

**Follow-on — The engineer line (`engineer` branch only).**
A separate branch reframes the whole effort: the real product isn't the LNA, it's the
*environment* — a benchmarked, reproducible harness for running and comparing analog
design searches, with the LNA as its flagship case study. This is where "does memory
help? does an unattended loop help?" get measured honestly (often the answer is "no,
and here's why").
→ See `04-engineer-line.md` on the `engineer` branch.

## Why it's structured this way

Analog design has two halves: **measurement** (can I simulate a circuit and score it?)
and **targeting** (can I produce a circuit aimed at a goal?). The survey found the
measurement side was basically ready — the simulator can do everything an LNA needs.
The targeting side was almost entirely missing: the generator produces circuits
blindly, with no notion of a spec, no bias network, and no device values. Nearly all
of the LNA project is about closing that targeting gap, one honest measurement at a
time.

## The working style, visible in the docs

A few conventions recur throughout and explain the docs' character:

- **Measured, not asserted.** Claims come with the number and the file/section that
  produced it. "Prefix conditioning gives 40.6%" is always traceable to a run.
- **Adopt-only-if-better.** Every change to the generator or scoring is gated against
  a frozen benchmark; ties go to the incumbent; costs are reported even when a change
  is adopted.
- **Negatives are published.** Things that didn't work (a memory scheme that *hurt*,
  an unattended loop that produced fewer feasible designs than blind search) are
  written up as first-class results, not buried.
- **User decisions are marked.** The docs distinguish choices the project owner made
  from calls the executor made on its own.

## How the docs relate

```
README.md / STATUS.md ........ Phase 1 survey: setup, results, bugs, timings
UPSTREAM.md / PORTING.md ..... how to re-obtain and port the 15 upstream repos

lna/FINDINGS.md .............. the measurement log: every LNA finding, in order
lna/JOURNEY.md ............... the narrative history: what happened and why
lna/HANDOVER-*.md ............ session-to-session handoffs (open problems, next steps)
lna/WORKLOG.md ............... what was tried, what failed, simulator traps
lna/STRUCTURE_LOGIC.md ....... architecture snapshot: how the pipeline works today
lna/SURVEY-AI-CIRCUIT-DESIGN.md . deep read of 9 competing systems

engineer/ (engineer branch) .. the environment + benchmark + case study
```

# Clean docs

Plain-language summaries of this repository's documentation. The original docs are
thorough but dense — heavy on inline citations, cross-references, and jargon. These
files are the newcomer's version: what the project is, what was found, and where
things stand, in a few minutes of reading.

They **summarize**, they don't replace. Where you need exact numbers, full tables, or
the reasoning behind a decision, each file points back to the authoritative source.

## Start here

| File | What it covers | Summarizes |
|---|---|---|
| [01-overview.md](01-overview.md) | The whole project in one page — the two phases, the two branches, how it all fits | everything below |
| [02-repo-survey.md](02-repo-survey.md) | Phase 1: cloning and smoke-testing 15 analog-circuit ML papers | `README.md`, `STATUS.md`, `PORTING.md`, `UPSTREAM.md` |
| [03-lna-project.md](03-lna-project.md) | Phase 2: using those tools to actually generate low-noise-amplifier (LNA) circuits | `lna/FINDINGS.md`, `lna/JOURNEY.md`, `lna/HANDOVER-*.md`, `lna/WORKLOG.md`, `lna/STRUCTURE_LOGIC.md`, `lna/SURVEY-AI-CIRCUIT-DESIGN.md` |

## A note on branches

This repo has two long-lived branches:

- **`main`** — the survey and the LNA generation project (everything above).
- **`engineer`** — a follow-on line that turns the LNA work into a reusable,
  benchmarked "AI analog-design environment." It has an extra clean doc,
  `04-engineer-line.md`, that only exists on that branch.

The three files above are identical on both branches.

## Scope

These cover the **headline narrative docs** — the ones you read to understand the
project. They deliberately skip the granular work-package specs (`lna/plans2/`) and
the dated progress reports (`lna/data/reports/`); go to those directly when you need
the fine-grained record.

# PRE-REG — bench-v2 + training-task pool (campaign `bench-v2`)

**Frozen:** 2026-09-29, before any cell exists. **GO:** user, 2026-09-29 ("go ahead with
bench-v2 at full size"). Branch `worktree-externals-gf180`. Outputs:
`kaggle/campaigns/bench-v2/`, library `kaggle/editcap-lib-v2/` (bench) and
`kaggle/train-pool-v2/` (training tasks).

## Why

bench-v1.2 was solvable by construction by two hand-picked templates, 10/16 cells were
library retrieval, 16/16 fell to blind single-edit search, and its checks accepted
unstable / out-of-band-failing designs (`bench-v12-audit`, `rl-readiness`). bench-v2 must
be (i) **provably solvable** under the honest verifier, (ii) **not solvable by the
existing library or by one blind edit**, (iii) **diverse in the kind of fix required**,
and (iv) built **without hand-authored answers** (nudge-limit directive: witnesses come
from search, never from a person or strong model writing a topology).

## Verifier (fixed)

`kaggle/bench_anchor_prep.py::smoke_run(..., profile="rl-v1")` on specs in rl-v1 form
(`rl_v1_spec`): mu_min ≥ 1 with in-loop wide stability (0.01–50 GHz), wideband NF over
the band (`nf_max_db`), band S11 (`s11_max_db`), topology limits enforced (wideband
`max_inductors` = 2 unless a cell states otherwise), structural + finite guards. PDK
bptm45. Budget 2500 evals/seed. See `VERIFIER-RL-V1.md`.

## Witnesses (proof of solvability) — "planted"

1. **Generation by search only.** Start from the bptm45 LNA library anchors a1–a5
   (`kaggle/bench-anchors/MANIFEST.json`) and apply compositions of 2–4 primitive edits
   (add R/C/L/NMOS/PMOS between existing or new nets, delete an element, rewire one
   terminal), each followed by a deterministic repair pass (bias via `lna/bias.py` /
   floating-node completion) so only coherent circuits are sized. Guided search (beam /
   mutate-then-repair from the best-scoring candidates) is allowed; hand-written
   topologies, the `claude-solutions/templates`, and LLM-proposed topologies are NOT.
2. **Planting.** A candidate that sizes stable and compliant under a loose probe spec
   has its achieved metrics recorded; a cell spec is written from them (each constraint
   set at the achieved value relaxed by the cushion below), over a declared grid of bands
   (wideband 0.5–3 GHz, 0.8–2.4 GHz, 1–2 GHz; narrowband f0 ∈ {0.9, 1.575, 2.4, 3.5} GHz,
   ±2%).
3. **Witness acceptance (all required):** re-sized from scratch through the standard
   pipeline, feasible under rl-v1 at **≥ 2 of seeds {1,2,3}**; still feasible at ≥ 1 seed
   with every performance limit **tightened by 2%** (δ = 0.02 of the constraint scale;
   mu_min is NOT tightened — its minimum often sits at the window edge); and feasible at
   ≥ 1 of fresh seeds {4,5,6}. Witness netlist, seeds, budget and full result dicts are
   archived; results are deterministic so anyone can replay them.

## Difficulty filters (a cell is kept only if all pass)

- **F1 library null:** every anchor a1–a5, seeds {1,2} × 2500 under rl-v1, infeasible.
- **F2 single-edit null:** every single primitive edit of the cell's SHOWN anchor (add
  R/C/L between any net pair, delete any element — the E-c space), seeds {1,2} × 2500
  under rl-v1, infeasible. (2 seeds because 1-seed recall is only ~0.8, R1.)
- **Shown anchor** = the library anchor the witness was derived from (so the required fix
  is the witness's multi-edit move).
- F1 runs before F2 (cheap kill first). Candidate specs failing a filter are logged, not
  discarded silently.

## Diversity

Each witness gets an automatic move-class label from its edit script vs its parent
anchor (e.g. resistive feedback, series/shunt L match, cascode/stacking, added stage,
degeneration, current reuse, tank/load change, other). **No class > 25% of cells.**
Report the class histogram. If search cannot produce ≥ 3 classes, report that as a
finding rather than relaxing the cap.

## Size

Target **20–25 bench cells** (user: "full size"), mixing wideband and narrowband. If the
honest pipeline yields fewer, report the shortfall and why (do not relax criteria).

## Training-task pool (separate split)

Same generator, different random streams, disjoint spec grid points; **no F2 filter**
(training wants mixed difficulty): each task records a difficulty label (library-
solvable / single-edit-solvable where cheaply known / witness-only) for curricula.
Target ~300 tasks. **Fence:** no bench spec, and no bench witness netlist (canonical
token hash), appears in the training pool or any SFT/RL data. bench-v2 cells are
EVAL-ONLY.

## Compute and conduct

Local CPU only, ≤ 8 parallel processes (shared box; lower if load > 22). Resumable,
checkpointed, run detached with progress files. Every result row carries the git era
stamp and `result["verifier"]`. Deviations recorded in the campaign README.

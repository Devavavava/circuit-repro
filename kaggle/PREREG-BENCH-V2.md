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

---

## AMENDMENT 1 — 2026-09-30 (user ruling "go with B, including the spec floors")

**Trigger (observed at 26.8 h, before any cell was frozen):** 10 cells accepted, but all
10 wideband, all from parent anchor a3, and all sharing ONE core fix (series input L,
usually + R into the input); the "other classes" were that core plus an extra device.
Every spec sat at s11 ≤ −7.85 dB and gain 7.9–10.5 dB (witnesses hug the −8 dB probe).
Continuing would reproduce bench-v1.2's one-trick flaw. Run stopped at 26.8 h; all
prior rows kept as a record (recorded as "pre-amendment", not selectable).

Changes (everything else in this pre-reg stands):

1. **Class = core fix.** A witness's move class is computed from its *ablation-essential*
   edits only (the minimal subset whose removal breaks rl-v1 feasibility), as a canonical
   signature (op × element type × role). Decorations and inert devices do not create a
   new class. The 25% cap applies to these core classes.
2. **Diversity quotas on the final selection:** ≤ 40% of cells from any one parent
   anchor; ≥ 25% narrowband cells. Search budget is steered toward under-represented
   parents / bands / core classes. Quotas are targets for selection — if unmet, report
   the shortfall; do not relax other criteria.
3. **Realistic spec floors (all bench cells):** input match `s11_max_db` ≤ −9 dB and gain
   `s21_db` ≥ 10 dB. Planting probes are set at or beyond the floors; a planted spec whose
   limits (after the 2% cushion) are looser than a floor is not planted. Witness acceptance
   (≥2/3 seeds, tightened, fresh seeds) is unchanged.
4. **Budget:** a fresh bench hard stop of 72 h from the resumed start (total campaign stays
   within the user-approved 3–5 days). Training pool unchanged (no floors: mixed difficulty
   for curricula) — its fence now also covers every post-amendment bench spec/witness.
5. Cache reuse only where the exact (topology, spec, seed, budget, profile) repeats;
   pre-amendment topologies may seed the search.

---

## AMENDMENT 2 — 2026-10-01 (user: "go ahead with whatever you suggest")

**Trigger:** at 23.8 h post-amendment-1, 9/11 accepted cells shared core atom
`add:L:IN-G`. Physics audit (`kaggle/campaigns/bench-v2/motif-audit/`, e189abbbb):
the L is a legitimate series input-match inductor, BUT the sizer drives the circuit's
own input DC-block to its floor and the design relies on the testbench port's built-in
10 pF DC block (`lna/to_spice.py` Cp1). With any DC-grounded source (antennas, filters,
switches often are) the gate bias collapses (0/9 pass; controls 2/2). A real LNA must
DC-isolate its own input — a missing interface requirement, not a hint about how to
solve.

Changes (everything else stands):

1. **Verifier rl-v1.1 = rl-v1 + port-DC requirement.**
   - *Behavioural check (authority):* on the sized winner, re-run the DC operating point
     with the input port additionally given a DC path to ground through 50 Ω (AC
     unchanged). Pass iff every MOS gate voltage moves < 10 mV and supply current moves
     < 1%. Failing → infeasible (`port_dc_fail`).
   - *Structural pre-filter (free, before sizing):* treating R, L and MOS channels as DC
     paths and capacitors as open, reject a topology whose input-port DC group contains
     a MOS terminal or the positive supply. (A DC path to ground alone is NOT rejected —
     e.g. an input shunt inductor to VSS is legitimate and the behavioural check decides.)
2. **Class rule for final selection = (b) primary atom:** no single primary core atom
   (the ablation-essential edit whose removal causes the largest feasibility loss) in
   > 25% of selected cells. Whole-signature and atom-prevalence stats still reported.
3. **Re-evaluation:** every accepted / queued / validating cell and every training task
   is re-checked under rl-v1.1; failures are tagged `amend2-port-dc` (kept on record,
   not selectable / relabelled in the training pool).
4. **Budget:** the bench end time is unchanged (amendment-1 resume + 72 h ≈ 2026-10-03
   14:51 IST); the campaign stays within the user-approved 3–5 days. If the final count
   is below 20, report the shortfall (no relaxation of criteria).

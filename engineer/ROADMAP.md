# ROADMAP — the engineer line's operating model (ADOPTED v1.0)

**Status: ADOPTED v1.0 — user ruling 2026-08-19. All §5 rulings resolved.
PROTOCOL amended to v1.1 as of the G0 landing commit. Written 2026-08-19 in
response to the user's direction: "let's set up a clearer model for how we want
to work with the engineer branch."**

---

## 1. The premise this roadmap corrects

E-3 (memory) and E-4 (unattended loop) measured the engineer's flagship
features against the main line's pipeline at matched compute on the in-house
tasks — and both lost. The named mechanism was budget fragmentation. But there
is a second, structural reason the user has now stated directly (2026-08-19):

> naively it will lose to our main model because we've already tuned that a bunch.

The main pipeline embodies ~40 stages of human iteration on exactly these
tasks — the seeds, the archetypes, the match-motif selector, the device-budget
calibrations, the recipe defaults all encode dhruva-specific learning. On its
home benchmark, tuned-main approximates an oracle; an autonomous system should
be *expected* to lose there, and that expectation carries almost no
information.

**Correction:** the engineer is not trying to beat tuned-main on dhruva. It is
trying to traverse, unassisted, the journey that *produced* tuned-main — on
problems where that tuning does not transfer. Home-turf tasks remain in the
benchmark as regression floors, not as the contest.

## 2. Scoring axes (proposed)

1. **Transfer, not home turf.** Primary scoring moves to tasks the main line
   was never tuned on (new specs, and eventually a new process). The existing
   7 in-house tasks + AnalogGym/LDO tracks stay as floors and calibration.
2. **Time-to-competence, not endpoint-at-matched-compute.** Report
   SPICE-minutes (and wall-clock, and user-rulings-requested) to first
   feasible and to tier-2 feasible. The question worth answering is "how much
   of the 40-stage human journey can the engineer traverse alone, how fast" —
   not "does a cold loop beat a hot pipeline at N evals".
3. **A contamination ledger.** Every "fresh-task" run declares what
   transferred in: harness + environment code — always allowed; playbook
   entries — allowed only if declared (that *is* the memory experiment);
   task-specific seeds, motif selectors, budget calibrations — never.

## 3. The rungs

Each rung is a numbered pre-registered doc (design + acceptance + falsifier
committed before any scoring run), per standing law.

- **G0 — freeze the fairness rules.** A short doc defining "fresh task", the
  contamination ledger, and the time-to-competence metrics. Lands as a
  PROTOCOL v1.1 bump (freeze rules require explicit user sign-off).
- **G1 (E-6) — budget allocation.** The direct fix for the E-3/E-4 mechanism:
  racing / successive-halving multi-start (many short starts used only to
  triage; full remaining budget to survivors) vs the single full-budget
  incumbent. Falsifier: if racing loses at matched budget on the in-house
  tasks *and* both external tracks, budget-splitting dies as a family, not as
  an implementation.
- **G2 (E-7) — move repertoire.** The diagnosis heads' binding constraint was
  the moves, not the diagnosis. Extend the graph-edit set until escalation can
  change an output stage's class. Test case: the D5 wall — given only the
  diagnosis "output-stage current-swing limit", can the loop reach a
  different output class at all? (This also feeds the main line's D5 fork,
  whichever way the user rules.)
- **G3 (E-8) — memory, non-fragmenting.** Re-test warm-vs-cold with memory
  allowed to choose the *starting region and move priors* while the budget
  stays whole. Reuses the E-3 twin harness unchanged.
- **G4 — the transfer tier.** Author 2–3 LNA specs the main line never touched
  (different band / source impedance / power class), score them
  time-to-competence under the G0 rules. This becomes the primary scoreboard.
- **G5 (E-4 v2) — the unattended loop, rerun** only after G1–G3 land.
  Falsifier: must beat blind search on at least half the transfer tier at
  matched budget.
- **G6 — the cold-process event.** When a second process arrives (IHP SG13G2
  via the sealed-PDK harness, or any Spectre-native kit), the engineer runs
  cold on it. Nobody's tuning transfers — human or machine. This is the
  honest grand test the line was built for.

## 4. What does not change

Pre-registration with falsifiers, adopt-only-if-better, goldens green before
and after every landing, append-only stores with provenance, the two-line
branch law, and user rulings for any spec/protocol/budget change. This
roadmap adds rungs; it relaxes nothing.

## 5. Rulings requested

| # | Question | Outcome (user ruling 2026-08-19) |
|---|---|---|
| R-A | Adopt the two scoring axes + contamination ledger (§2)? | **ADOPTED** — transfer axis + time-to-competence + contamination ledger formalised in G0-FAIRNESS.md; PROTOCOL bumped to v1.1. |
| R-B | Adopt rung order G0→G6 (reorder/veto any)? | **ADOPTED** — G0→G6 order adopted as written. First experiment authorised: G1 (E-6), smoke tier (150 evals/arm per R-4 convention) then full scale after check-in. |
| R-C | Playbook default in fresh-task runs: declared-in, or out entirely? | **OUT** — playbook is out of fresh-task runs by default; enters only as the explicit variable (e.g. G3). Fenced in the contamination ledger's `playbook.allowed: declared` / `present: false` default. |
| R-D | Does authoring the G4 transfer specs itself require a PROTOCOL bump first, or land with G0's v1.1? | **DEFERRED-MOOT** — G4 has not started; the question is moot. Default (transfer specs land with a protocol bump when G4 starts) stands. |

## 6. Goal clarification (user ruling, 2026-08-20)

The goal of engineer isn't novelty, it's capacity to hit specs in a reasonable time.

Operationalization (also ruled): the engineer line's PRIMARY scoreboard metric is **SPICE-minutes to first spec-feasible design** (tier-2 feasible where the task defines it), per the G0-FAIRNESS metric set; novelty/NDL remains a main-line generator concern and is explicitly NOT an engineer-line objective or tiebreaker. This sharpens (does not contradict) the adopted §2 axes: among the time-to-competence metrics, SPICE-minutes-to-feasible is primary.

## 7. Standing target (user, 2026-08-22): a smarter editor

Recorded verbatim as a standing program target, per the user's directive of
2026-08-22. **Beyond E-9's two-stage budget split, the program should eventually
make the edit-proposal step itself smarter** — the E-8 v2 finding (guided ≈
random ≈ zero across a coverage-stratified goal set) located the ceiling *upstream*
of diagnosis, in the move repertoire / editor intelligence (E8-LADDER-V2.md §Falsifier
secondary negative; E7-MOVES.md §4.4 secondary negative). E-9 tests whether *splitting
the budget by job* lifts that ceiling; if it does not (E-9 falsifier), the next lever
is the intelligence of the editor itself.

Candidate directions to evaluate later — **each its own pre-registration; nothing
below executes without a user ruling; this section is a recorded target, not an
authorization:**

1. **Learned move-proposal priors trained on edit trajectories.** Train a proposal
   model on the recorded (state → edit → outcome) trajectories the E-7/E-8/E-9 runs
   already log, so the edit distribution is data-shaped rather than uniform or
   hand-weighted.
2. **Playbook-informed move routing.** Let the playbook (currently OUT of fresh runs
   by default, R-C) inform *which primitive to try where*, as a declared contamination
   variable — the memory experiment (G3) applied to the editor rather than to sizing.
3. **Critic-in-the-loop edit scoring.** Put the GNN critic (critic_gnn heads) in the
   edit-acceptance loop to score/filter proposed mutants before they are sized, rather
   than only aiming (E-7 arm G) or filtering post-hoc.

Sequencing and priority are a future user ruling. Recorded here so the target is
explicit and the E-9 falsifier has a named destination (§7) when it fires.

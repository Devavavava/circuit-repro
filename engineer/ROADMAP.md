# ROADMAP — the engineer line's operating model (DRAFT v0.1)

**Status: DRAFT — pending user rulings (§5). Nothing here amends PROTOCOL v1.0
until ruled. Written 2026-08-19 in response to the user's direction: "let's set
up a clearer model for how we want to work with the engineer branch."**

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

| # | Question | Default if unruled |
|---|---|---|
| R-A | Adopt the two scoring axes + contamination ledger (§2)? | not adopted |
| R-B | Adopt rung order G0→G6 (reorder/veto any)? | not adopted |
| R-C | Playbook default in fresh-task runs: declared-in, or out entirely? | out |
| R-D | Does authoring the G4 transfer specs itself require a PROTOCOL bump first, or land with G0's v1.1? | with G0 |

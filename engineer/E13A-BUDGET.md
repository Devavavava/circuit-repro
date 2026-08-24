# E13A-BUDGET — budget/selection concentration on the near-miss cluster (pre-registration)

**Status: PRE-REG (frozen at first scored eval). GO'd by user 2026-08-24
("you can try this" + "run whatever needs to be run").** Engineer line. Direction
E13-DIRECTIONS.md §5 lever E-13a. All standing governance carries: goldens GREEN
before/after every landing; engineer never writes under `lna/` (imports only);
append-only stores + edit log; matched TOTAL budgets; user rulings for any
spec/protocol/budget CHANGE (this is budget RE-ALLOCATION at matched total — an
agent call, not a widening).

<!-- Nothing above the RESULTS fence may be informed by any scored E-13a eval. -->

## 0. Motivation

The post-E-12 zero-sim margin audit (E13-DIRECTIONS.md §2) split the 8 P3 goals into a
**near-miss cluster of 5** (best sized candidate within 0.8–13.4% of feasibility) and a
far-miss cluster of 3. For the near-miss cluster the audit named two candidate levers it
could not separate without sims: **budget-starvation** (the near-feasible topology is in
the sized pool but got only ~120–131 stage-2 evals from a random CMA-ES start) vs
**bad screening** (the unsized `[0.5]^d` L1 probe promoted the wrong survivors). E-13a
runs the cheapest experiment that both tries to convert the near-misses AND disambiguates
these two levers, with NO new model and NO budget widening.

## 1. Hypothesis (stated before any number is seen)

> **Concentrating the same total sizing budget on fewer, better-screened survivors converts
> at least one near-miss goal (GN78, G13, H2, G1'', G2'') to a spec-feasible solve that the
> E-12 P3 allocation (m=4) left unsolved.** And the shape of the m-response separates the
> budget lever from the selection lever.

## 2. Goal set (the near-miss 5; frozen)

Exactly the five near-miss goals from the audit. Extended specs byte-identical to E-12 P3
(reused from the frozen goal definitions; no thresholds change here):

| goal | spec (delta) | P3 best sized obj | P3 best arm | primary arm for E-13a |
|---|---|---|---|---|
| GN78 | nf_db ≤ 1.6 (fresh n78 3.4–3.6 GHz) | 1.008 | b | b |
| G13  | nf_db ≤ 1.45 (dhruva-l2)             | 1.011 | c2 | c2 |
| H2   | nf_db ≤ 1.25 (dhruva-l1, HELD-OUT)  | 1.025 | b | b |
| G1'' | s21_db ≥ 33.0 (dhruva-l1, HELD-OUT) | 1.054 | c2 | c2 |
| G2'' | s22_max_db ≤ −10 (dhruva-s)         | 1.134 | c2 | c2 |

**Primary arm rule (frozen):** per goal, run the arm that produced its P3 near-miss best
(the pool most likely to contain a convertible candidate). This is documented per goal
above; no post-hoc arm selection. G1''/H2 remain HELD-OUT transfer; GN78 remains FRESH
transfer (note: GN78 was NOT null-filtered in P3 and fell to sizing-only there — so a GN78
solve here carries NO transfer claim by the E-12 falsifier's own bar; it is included only
to complete the near-miss margin map).

## 3. Design — matched-TOTAL m-sweep (the only variable is allocation)

Machinery byte-identical to E-12 P3 (`e12_p3.py`: same anchors, same k=120 L1 screen,
same D1 rollover, frozen sampling temp 0.7 / max_new 256, same class/spec-bin tokens,
no-early-stop scoreboard variant). **TOTAL budget B=600 per cell, unchanged.** The ONLY
change is `m` (number of top-screened survivors that receive stage-2 CMA-ES), which sets
per-survivor sizing budget ≈ (B − stage1_evals)/m:

| m | per-survivor stage-2 evals (approx) | role |
|---|---|---|
| 4 | ~131 | **E-12 P3 baseline — REUSED, not re-run** |
| 2 | ~262 | new |
| 1 | ~524 (all budget on the single top-L1 survivor) | new |

k=120 screen unchanged (same candidate pool; only how many survivors get sized changes).
New cells: 5 goals × {m=1, m=2} × 3 seeds = **30 cells, ~18,000 counted evals.** m=4 is
the banked P3 cell for the same (goal, arm), reused as the comparison point.

## 4. Metrics

Per cell (as E-11 §6): solved (bool), evals/SPICE-min to first feasible, best stage-2
objective and the winning survivor's wl/move, distinct_realized, per-survivor sized-obj
list. Cross-cell: **best-objective margin vs m** per goal (does concentration reduce the
violation?); solve count vs m; SPICE-minutes to first feasible on any solve (PRIMARY).

## 5. Falsifier (pre-stated)

> **If no m∈{1,2} setting converts ANY of the five near-miss goals to a solve, AND the
> best-objective margin does not improve materially (say ≥0.05 obj units, ~a few % of
> threshold) with concentration on any goal, then the near-miss cluster is not
> budget/selection-limited — the audited margins are objective plateaus — and budget
> re-allocation dies as the near-miss lever. Escalate to a learned starting-sizing
> warm-start (E-13c) and/or critic-selection (E-13b), each its own pre-reg.**

Sub-readings:
- **Concentration converts ≥1 near-miss:** budget lever confirmed; report which m and
  SPICE-minutes; this is the first scored engineer solve of the arc.
- **Margin improves monotonically with concentration but no solve:** budget helps but is
  insufficient from a random start → the escalation is a better *starting point*
  (E-13c warm-start), not merely more evals. Directly motivates E-13c.
- **m=1 does WORSE than m=4 (banked):** all-budget-on-top-screened underperforms spreading
  → the `[0.5]^d` L1 screen is misranking survivors → SELECTION is the lever (E-13b), not
  budget. This is the disambiguation the audit could not make.
- **Flat, no margin movement across m:** neither budget nor selection moves the near-miss;
  the near-misses are genuine plateaus and edit quality is binding after all.

## 6. Anti-cherry-pick / parity fences (binding)

- TOTAL = B parity asserted per cell (recompute from raw metrics at aggregation; any cell
  off-parity is void and re-run).
- Solves recomputed from raw metrics against the frozen extended spec, not trusted from a
  `solved` flag.
- Same exclusion lists as E-12 P3 (l1 ban for held-out; per-goal certificate exclusions)
  — E-13a proposes and sizes topologies exactly as P3 did; no training here, so answer
  exclusion applies only to the reused editor checkpoints (unchanged).
- Edit log append-only, campaign tag `e13a`; every proposal logged.
- `lna/` untouched (imports only). Goldens GREEN before first and after last sim.

## 7. Containment & crash-safety

As E-11 §9 / E-12 §10 verbatim: dedicated worktree (`eng-e13`), ≤8 concurrent ngspice,
per-PID status temp files, atomic per-cell JSONs under `engineer/data/e13/a_results/`,
AnalogGenie symlink pre-authorized, torch CPU-only, PYTHONHASHSEED=0, fixed seeds.

## 8. Not in scope

No new model training (E-13c/b are separate); no spec/threshold/total-budget change; no
`lna/` writes; no critic wiring (that is E-13b); no claims about the far-miss cluster.

<!-- ================================================================= -->
<!-- RESULTS BELOW — appended AFTER the scored run; nothing above this  -->
<!-- line may be informed by any scored E-13a eval.                     -->
<!-- ================================================================= -->

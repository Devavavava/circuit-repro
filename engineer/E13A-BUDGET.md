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

## RESULTS (scored, executed 2026-08-24, this session; goldens GREEN before + after)

30/30 cells at `engineer/data/e13/a_results/`. **Parity clean: all 30 cells spent
exactly B=600 counted evals (0 parity failures); solves recomputed from raw
`ext_feasible` metrics, not trusted flags.** m=4 column = banked P3 primary-arm cells
(reused, not re-run). `lna/` untouched.

### Headline — solves + best sized objective per goal per m

`best_objective` = the CMA-ES scalar (see structural finding below: it measures
distance to **base**-spec feasibility, not to the goal's delta). Lower = better.

| goal | arm | m=1 (best obj / solves) | m=2 | m=4 (P3 banked) |
|---|---|---|---|---|
| GN78 | b  | **SOLVED** −1.486 / **1/3** (307 evals, 0.056 SPICE-min) | **SOLVED** −1.001 / **1/3** | +1.008 / 0/3 |
| H2   | b  | +1.124 / 0/3 | +1.309 / 0/3 | +1.025 / 0/3 |
| G13  | c2 | +1.944 / 0/3 | −0.771 / 0/3 | +1.011 / 0/3 |
| G1'' | c2 | +2.362 / 0/3 | +2.093 / 0/3 | +1.054 / 0/3 |
| G2'' | c2 | −0.911 / 0/3 | −0.705 / 0/3 | +1.134 / 0/3 |

**Real solves (ext_feasible = base AND delta): GN78 only, at m=1 and m=2.** GN78 is the
FRESH goal that was NOT null-filtered (pre-reg §2 note) — it carries NO transfer claim by
construction. The four transfer-relevant near-misses (H2 held-out, G13/G1''/G2'' DEV):
**0 solves at every m**, same as P3.

### Structural finding (uncovered during verification — supersedes the §5 frame)

The two-stage sizer's CMA-ES minimizes `env.evaluate(action="size")["objective"]`, which is
`size.make_objective(body, spec, …)` built over the **BASE spec** (`engineer/env.py:386`;
`engineer/e11_run.py:166-168`). **The goal's delta metric (`ext_s`) is NEVER in the sizing
objective** — it is only checked opportunistically in the solve callback
(`e11_run.py:346`, `ext_feasible`). Therefore `best_objective` is distance-to-**base**-
feasibility, not distance-to-delta.

Evidence: G13 m=2 and G2'' m=1 reached strongly **base-feasible** designs (obj −0.77 / −0.91)
that STILL failed their delta (nf≤1.45 / s22≤−10) → not solved. GN78's loose delta (nf≤1.6)
was incidentally satisfied by a base-feasible design → solved. Concentration produced
**better base designs** (GN78 converted; G13/G2'' base-obj driven negative), NOT
delta-satisfying ones.

**Reframed cluster reading:** the audit's "near-miss cluster" is *base-feasible-but-delta-
unmet*; the "far-miss cluster" (G9/G7''/G12, audit base-obj ~1.7) is *base-INfeasible*. The
original zero-sim audit read per-dB "near-miss margins" off `best_objective`, so it measured
base-feasibility margin, not delta margin — treat that per-dB framing as superseded.

### §5 falsifier — verdict

Literally **NOT met**: a near-miss (GN78) WAS converted to a solve by concentration, so
budget re-allocation is not inert. But that win is on the transfer-excluded goal; the four
transfer-relevant near-misses did not convert, and verification shows WHY — their delta
metric is absent from the sizing objective. This is a **THIRD outcome outside the
pre-registered budget-vs-screen sub-readings**: an objective-specification gap in the
two-stage machinery, not a budget or a screening property. Budget concentration is therefore
neither confirmed nor killed as a lever for delta goals — it is simply **not the operative
knob** while the delta is outside the objective.

### Implied next levers (each its own pre-reg + GO)

1. **Delta-aware sizing objective (cheapest, most direct):** put the goal's delta metric into
   the CMA-ES objective (weighted term or constrained formulation) so sizing actually
   optimizes toward the near-miss target. Directly re-testable on this same 5-goal set.
2. **E-13b topology selection (critic):** for goals where the anchor topology cannot meet
   base AND delta jointly, select topologies that can.
3. **Retrospective to confirm:** this objective gap is shared byte-identical across
   E-9 / E-11 / E-12 / E-13 (same two-stage machinery) → a plausible contributor to their
   flat-zero delta-goal results. Worth a zero-sim confirmation before the next build.

### Deviations (recorded)

1. **Thread-oversubscription wedge (first c2 launch).** The initial orchestration launched all
   18 c2 cells concurrently; each PyTorch worker span 34 threads (≈600 threads on 28 cores,
   load 34), and after ~80 min **zero** c2 cells had recorded any eval (`ng_total=0`, no atomic
   result written — no counted evals lost). Killed and relaunched at **≤6 concurrent** with
   `OMP_NUM_THREADS=4`, which also brings the run into the §7 ≤8-ngspice guard (the first launch
   had violated it). The 12 b-arm cells (GN78/H2) completed in the first launch, unaffected.
2. GN78 not sizing-resistant / not a transfer claim — carried over from the E-12 P3
   null-filter gap; recorded, excluded from any transfer bar.

### Scope

Bounds budget re-allocation on these 5 goals only. The delta-absent-from-objective result is a
**code-level fact** (verified); its effect on past campaigns is an **inference** to confirm
separately.

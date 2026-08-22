# E9-TWOSTAGE — the two-stage structural experiment (pre-registration)

**Status: PRE-REGISTRATION — committed BEFORE any scoring eval (user GO,
2026-08-22).** This document is fixed before a single scored simulation is run;
the outcome section (§ Results) is appended post-hoc and clearly marked. The rule
cannot have chosen the protocol. Every governance rule carries forward from
E8-LADDER / E8-LADDER-V2 / E7-MOVES: the nudge policy (E7-MOVES §0 — primitive
moves only, no macros), goldens-green before/after every landing, the two-line
branch law (engineer never writes under `lna/`), append-only stores, and user
rulings for any spec/protocol/budget change (no spec yaml is edited here).

---

## 0. Motivation — what E-8 v2 left on the table

E8-LADDER-V2.md §Scored campaign RESULTS (executed 2026-08-22) is the zero-solve
result this experiment answers. Across a deliberately maximally-varied,
coverage-stratified set of six structural goals — **G2', G4', G9@1200, G1'',
G7'', G11''** — spanning five goal types (match / band-shape / gain / current /
linearity) and every blame-coverage state (full / partial / unavailable):

> **Guided 0/6 vs random 0/6** (sizing-null also 0/6). No arm solved any goal.

The coverage instrument reported the right state at every tier, but the
guided-vs-random outcome column was flat at zero, so the correlation the campaign
set out to measure was **untestable** — the ceiling sat *upstream* of diagnosis.
The E8-LADDER-V2 §Falsifier secondary negative and E7-MOVES §4.4 secondary
negative both fired: **BOTH the random-edit and blame-guided arms solved ~zero,
which points at the repertoire/search, not the diagnosis.**

**The fragmentation diagnosis (the specific mechanism this experiment attacks).**
In the E-8 v2 arms (b) and (c), *one budget* — 600 evals (G9: 1200) — had to pay
for BOTH the structural search (proposing + realizing edits) AND the sizing of
each edited topology. The runner interleaved them: propose an edit, then spend a
`slice_cap = max(40, budget//6)` sizing slice on it, repeat until the budget is
gone (`e8_scored_v2.py::run_cell`, arm b/c loop). Every eval spent screening a
dead-end edit is an eval NOT spent sizing a promising one, and every edit that
does survive gets only a *fraction* of a sizing run before the next edit is tried.
This is the budget-fragmentation mechanism ROADMAP §1 and E-3/E-4 named as the
reason the engineer line lost at matched compute: **making edits and sizing them
share one budget starves both.**

**The E-9 hypothesis is that the fix is to split the job, not the budget within a
job.** This generalizes the E-7 G2 smoke's stage structure (E7-MOVES §Smoke
results): that smoke already ran a *cheap L0/L1 reachability screen* (stage-1:
1500 L0 proposals + L1 DC-probes, 0–150 counted evals) and then *auto-proceeded to
a full L2 sizing run* (stage-2: a dedicated 500-eval CMA-ES per reached candidate).
E-9 is that pattern generalized from the single D5 reachability case to the whole
v2 survivor goal set, scored as a matched-budget arm comparison.

---

## 1. Hypothesis (stated before any number is seen)

> **With the budget split by JOB — a cheap structural search (stage 1) that
> screens and culls edit candidates, followed by full per-survivor sizing (stage
> 2) — guided two-stage editing solves goals that (i) sizing provably cannot (the
> six v2 zero-solve goals, all null-filtered as sizing-resistant at 600/1200
> evals) and (ii) single-budget editing provably did not (E-8 v2's 0/6 across all
> three arms).**

The falsifiable content: does a two-stage split — where a promising edited
topology gets a *whole, uninterrupted* sizing run instead of a fragment — reach
any of these six structural targets that neither sizing-only nor single-budget
editing reached? And does *blame-guided* candidate selection (arm C) beat
*random* candidate selection (arm B) at matched total budget?

---

## 2. Goals — the six E-8 v2 survivors (definitions UNCHANGED from E8-LADDER-V2.md)

These are exactly the six goals scored in E8-LADDER-V2.md §Scored campaign; the
delta definitions, base tasks, and null-filter provenance are carried forward
verbatim. No goal is re-authored; no new goal is added.

| goal | base task | delta (extended spec, in-memory) | type | null-filter provenance | budget digit B | seeds |
|---|---|---|---|---|---:|---|
| **G2'**  | dhruva-s-t2-a  | `s22_max_db ≤ −10` band-wide            | match (S22)   | RESISTED @600 (v2 §7); anchor −0.30 | 600  | 1–3 |
| **G4'**  | dhruva-l2-t2-a | `s11_max_db ≤ −14.5` band-wide          | match (S11)   | RESISTED @600 (v2 §7)               | 600  | 1–3 |
| **G9**   | dhruva-l5-t2-a | `s21_ripple_db ≤ 3`                     | band-shape    | RESISTED @1200 (v2 §7)              | 1200 | 1–3 |
| **G1''** | dhruva-l1-t2-a | `s21_db ≥ 33`                          | gain          | RESISTED 0/3 @600 (nullv3)          | 600  | 1–3 |
| **G7''** | dhruva-l5-t2-a | `idd_ma ≤ 9.0 @ s21 ≥ 22.3`            | current       | RESISTED 0/3 @600 (nullv3)          | 600  | 1–3 |
| **G11''**| dhruva-l5-t2-a | `iip3_dbm ≥ −7.4` (TASK-LEVEL tier-3)  | linearity     | RESISTED 0/2 @120 (nullv3, tier-3)  | 600  | 1–2 |

`iip3_dbm` for G11'' is a **task-level in-memory** constraint via the wired tier-3
two-tone path (`size.measure_iip3_tier3`); **no spec yaml is edited** — the frozen
`dhruva-l5.yaml` `iip3_dbm` status-flip remains a separate user ruling. Likewise
G2'/G4' band constraints and all deltas are applied by in-memory spec mutation
(`ext_spec_of`), identical to E-8 v2. **N=3 seeds** (seeds 1–3) for all goals;
**G11'' N=2** (seeds 1–2), its tier-3 two-tone cost flagged (≈15 s/measurement,
~150× a base op+sp eval).

---

## 3. Arms — the two-stage split, matched TOTAL budget

Three arms per goal. The **matched axis is the TOTAL counted env-eval budget per
(goal, arm, seed)** = the goal's digit B (600, or 1200 for G9). Parity across the
three arms is the binding constraint (E-6 §4 / E-8 matched-budget discipline).

### (A) sizing-only continued — the same total in ONE run
CMA-ES sizing the goal's *reached anchor topology* against the goal's extended
(in-memory) spec, spending the full B evals in one continued run. **This is
byte-identical to E-8 v2 arm (a)** — it re-establishes the sizing-only baseline
under the E-9 harness so an E-9 two-stage win is unambiguously the split's doing,
not a harness change. (Expected 0/6 by the v2 null-filter + v2 arm-a result; if it
solves anything the null-filter would be contradicted and that is itself reported.)

### (B) random-edit two-stage
- **Stage 1 (cheap structural search).** Repeatedly: propose one random primitive
  edit (`g2_moves.mutate`, the RULED P1–P5/P7 + `add_and_connect_device`
  repertoire, uniform targets), `sane()`-gate it (L0, **0 sims**), `realize()` it
  (token round-trip + `spec.structural_screen`, **0 sims**), then run **one counted
  L1 eval** (`env.evaluate` at x0 = 0.5 → DC-operating-point + base metrics). Score
  the candidate by its **objective at the L1 probe** against the extended spec
  (lower = closer to feasible). **Per-candidate stage-1 cost: exactly 1 counted
  env eval** (L0 is free; L1 is the single counted sim). Screen **k** candidates,
  then **cull to the top-m** by L1 objective.
- **Stage 2 (full per-survivor sizing).** Each of the m survivors gets its OWN
  dedicated CMA-ES sizing run — the *standard sizing path* (`_size_topo` →
  `null_sizer.run_cmaes`, the same callable `size.size_topology` hands the sizer),
  warm-started at that survivor's stage-1 point, spending **(B − k) / m** counted
  evals. A survivor's run is uninterrupted — it is not re-fragmented by further
  edits. Total = k + m·((B−k)/m) = **B**. Matched.

### (C) blame-guided two-stage
Identical two-stage machinery to (B), with ONE difference: **stage-1 candidate
proposal is aimed by the auto-diagnosis** (`blame.py` binding-device ranking +
`binding_probe.py` binding-metric, computed once at the warm anchor, `write=False`,
no human string) via `propose_guided` — the same aim used in E-8 v2 arm (c). The
repertoire, the L0/L1 screen, the cull rule, and the stage-2 sizing are identical
to (B). **Arm C isolates the value of blame-guided candidate selection from the
two-stage split itself; arm B is the split without guidance.**

### 3.1 k, m, and the resulting total per (goal, arm) — justified from E-7 smoke costs

Justification from the measured costs (E7-MOVES §Smoke; re-verified in this
worktree 2026-08-22):
- **L0 screening is ~free of simulator time** (≈33 ms/proposal, 0 ngspice; the
  E-7 smoke L0-survived all 1500 proposals). So k is bounded by *counted evals*
  (the L1 probes), not by L0 throughput.
- **The E-7 smoke's stage split was ~150 screen evals → a dedicated 500-eval
  sizing run per candidate.** E-9 scales that ratio to the matched B budget:
  spend a *minority* of B on screening (so most of B goes to sizing survivors,
  the opposite of v2's fragmentation), and cull to a handful of survivors so each
  gets a *substantial, uninterrupted* sizing slice (≥ 100 evals — comfortably more
  than v2's `slice_cap = max(40, B//6)` = 100 fragment, and unbroken).

| goal | B | **k** (screened) | **m** (survivors) | stage-2 per survivor = (B−k)/m | total (= B) |
|---|---:|---:|---:|---:|---:|
| G2'  | 600  | 120 | 4 | (600−120)/4 = **120** | 600  |
| G4'  | 600  | 120 | 4 | 120 | 600  |
| G1'' | 600  | 120 | 4 | 120 | 600  |
| G7'' | 600  | 120 | 4 | 120 | 600  |
| G9   | 1200 | 200 | 5 | (1200−200)/5 = **200** | 1200 |
| G11''| 600  | 60  | 3 | (600−60)/3 = **180** | 600  |

Rationale for the specific numbers:
- **k = 120 (20% of B=600)** screens far more distinct topologies than the whole
  v2 arm ever *sized* (v2 sized ~6 fragments of B//6 each), while leaving **80% of
  the budget for sizing** — inverting the fragmentation. For G9 (B=1200), k=200
  holds the same ~1/6 screen fraction. For G11'', tier-3 IIP3 is ~150× a base
  eval, so k is cut to **60** (the L1 screen uses the cheap op+sp path; IIP3 is
  probed only in stage-2 on best-so-far at a coarse stride, as the v2/null runner
  did) and m to **3** to keep the tier-3 spend bounded.
- **m = 4 (5 for G9, 3 for G11'')** gives each survivor **≥ 120 uninterrupted
  sizing evals** — more than the v2 per-edit fragment (100) AND unbroken, which is
  the whole point. m is kept small so the sizing per survivor is not itself
  re-fragmented into uselessly-short runs.

If fewer than m distinct candidates survive stage-1 (e.g. a goal where few edits
realize), the surviving candidates split the entire (B−k) stage-2 budget evenly
(so total stays = B); this deviation, if it occurs, is recorded per cell.

---

## 4. Metrics

Per (goal, arm, seed) cell, recorded to a crash-safe per-cell JSON:
- **solved: y/n** — the design is base-feasible AND clears the extended delta
  (`ext_feasible`; for G11'' base-feasible AND measured `iip3_dbm ≥ −7.4`).
- **PRIMARY: TOTAL counted evals + SPICE-minutes to first feasible** (per ROADMAP
  §6, SPICE-minutes-to-first-feasible is the primary scoreboard axis). SPICE-minutes
  accumulate `cost.wall_s` across every counted eval in both stages.
- **stage-1 vs stage-2 spend breakdown** — counted evals and SPICE-minutes in each
  stage, per cell.
- **winning edit sequence** — the primitive edit(s) that produced the solved
  survivor (empty if unsolved).
- **stage-1 diagnostics** (arm C): binding metric, blame devices, blame coverage,
  `blame_extra_sims` (ripple-FD extra ngspice calls, counted SEPARATELY per the
  E8-LADDER-V2 committed ruling — NOT deducted from B; parity preserved because the
  B counted evals are identical across arms).
- **survivor set**: the m culled topologies (wl-hash + stage-1 objective) per B/C cell.

Goal counted **solved** if ≥ 1 seed clears base-feasible + the delta (same rule as
E-8 v2). Headline: goals solved per arm (a / b / c).

---

## 5. Falsifier (pre-stated, before any scored eval)

> **If guided two-stage editing (arm C) solves NO goal that BOTH sizing-only (arm
> A) AND random two-stage editing (arm B) leave unsolved, then the two-stage
> repair FAILS for this goal set, and the ceiling moves to the move
> repertoire / editor intelligence (→ ROADMAP §7).**

Two sub-readings, both pre-stated:
- **If arm C beats {A, B}** on ≥ 1 goal (solves it where both A and B do not):
  the two-stage split lifts the E-8 v2 ceiling AND blame-guidance carries usable
  signal — the E-8 v2 secondary negative is escaped by splitting the job. The
  primary metric (SPICE-minutes to first feasible) ranks the arms on any shared
  solved goal.
- **If arm B (random two-stage) solves goals but arm C does not beat it:** the
  two-stage *split* helps but the *guidance* does not — the repertoire is enough
  once budgets are unfragmented, and diagnosis is still untested/unhelpful. Reported
  as such; still a positive result for the split, a null for guidance.
- **If BOTH B and C solve ~zero** (the E-8 v2 outcome replicated under the split):
  two-stage does not lift this ceiling; the ceiling is the move repertoire / editor
  intelligence, and the next lever is ROADMAP §7 (a smarter editor), not the budget
  structure. This is the E7-MOVES §4.4 / E8-LADDER-V2 secondary-negative destination.

---

## 6. What is NOT in scope

- **No new primitives.** The repertoire is exactly the RULED P1–P5, P7 +
  `add_and_connect_device` (E7-MOVES §Rulings; P6 REJECTED). No move is added.
- **No oracle diagnosis.** Arm C uses the same auto `blame.py`/`binding_probe.py`
  diagnosis as E-8 v2 — no human string, no oracle arm (d). (An oracle arm would
  separate diagnosis-quality ceiling from repertoire/search ceiling; it is a future
  pre-reg, not this one.)
- **No spec edits.** All deltas (band constraints, IIP3 target) are in-memory spec
  mutations; no `lna/specs/*.yaml` is touched; the frozen-spec IIP3 status flip
  remains a separate user ruling.
- **No smarter-editor work.** The ROADMAP §7 directions (learned priors, playbook
  routing, critic-in-the-loop) are recorded targets, not executed here.

---

## 7. Containment & crash-safety (binding for the run)

- Engineer-branch worktree `wt-e9` (from `engineer` @ 9efc1b9). `/home/dpatni/circuit-repro`
  is READ-ONLY; nothing writes under `lna/`; `tmp/wt-e6` is untouched. No merge, no push.
- ≤ 8 concurrent ngspice. PYTHONHASHSEED=0 (byte-reproducible, per E-7 finding).
- **Crash-safety (MANDATORY):** every (goal, arm, seed) cell writes an atomic
  per-cell JSON under `tmp/e9_results/`; the aggregator (`e9_agg.py`) reconstructs
  the whole campaign from cells alone; a status file (`tmp/E9_STATUS.md`) is kept on
  disk at all times. This pre-registration is committed BEFORE any scoring eval.

<!-- ================================================================= -->
<!-- RESULTS BELOW — appended AFTER the scored run; nothing above this   -->
<!-- line was informed by any scored E-9 eval.                          -->
<!-- ================================================================= -->

## Results (executed 2026-08-22)

Runner `.claude/jobs/a8f610e5/tmp/e9_twostage.py`; per-cell crash-safe JSONs +
aggregator `e9_agg.py` (**51/51 cells on disk**). PYTHONHASHSEED=0, ≤ 8 concurrent
ngspice, matched TOTAL budgets. Engineer-branch worktree `wt-e9` (from `engineer`
@ 9efc1b9); no `lna/` write; no spec yaml edited (G2'/G4' band and G11'' IIP3 via
in-memory tier-3 spec). Goldens `python lna/ref/check_ref.py` GREEN before the
first commit and after the last.

### Headline

**Guided two-stage 0/6 vs random two-stage 0/6 vs sizing-only 0/6.** Splitting the
budget by JOB — cheap structural screen (stage 1) then full per-survivor sizing
(stage 2) — solved **no** goal that single-budget editing (E-8 v2) did not, on any
arm. Across the same six coverage-stratified goals, the two-stage split reproduces
the E-8 v2 flat-zero outcome. (A goal is counted solved if ≥ 1 seed clears
base-feasible + the delta.)

### Per-goal tables (51 cells, TOTAL budget exactly matched across arms)

Every (goal, arm) spent its full matched TOTAL budget B; none produced an
extended-feasible design, so solved-seeds / evals+spice-min-to-solve / winning-edit
are empty for all rows.

| goal | type | B | seeds | solved (a / b / c) |
|---|---|---:|---:|---|
| G2'  | match (S22)  | 600  | 3 | 0/3 · 0/3 · 0/3 |
| G4'  | match (S11)  | 600  | 3 | 0/3 · 0/3 · 0/3 |
| G9   | band-shape   | 1200 | 3 | 0/3 · 0/3 · 0/3 |
| G1'' | gain         | 600  | 3 | 0/3 · 0/3 · 0/3 |
| G7'' | current      | 600  | 3 | 0/3 · 0/3 · 0/3 |
| G11''| linearity    | 600  | 2 | 0/2 · 0/2 · 0/2 |

Winning edit sequences: **none** (no arm solved). G11'' additionally consumed
**146 tier-3 two-tone IIP3 probes / 49.8 min** across its 6 cells (coarse stride
25) — reported separately, NOT deducted from any env-eval budget.

### Spend breakdown (mean counted evals per cell — stage-1 / stage-2 / total)

TOTAL is exactly matched across arms per goal (the parity axis). Stage-1 spend
varies: for narrow aimed-edit goals the stage-1 screen exhausts the distinct
candidate pool before reaching k and the unspent budget rolls into stage-2 (see
deviation D1), so total stays = B.

| goal | arm | stage-1 evals | stage-2 evals | TOTAL | spice-min | blame_extra_sims |
|---|---|---:|---:|---:|---:|---:|
| G2'  | a (sizing-only)  | 0   | 600  | 600  | 0.139 | 0 |
| G2'  | b (random 2-stg) | 120 | 480  | 600  | 0.138 | 0 |
| G2'  | c (guided 2-stg) | 52  | 548  | 600  | 0.138 | 0 |
| G4'  | a | 0   | 600  | 600  | 0.132 | 0 |
| G4'  | b | 120 | 480  | 600  | 0.144 | 0 |
| G4'  | c | 58  | 542  | 600  | 0.134 | 0 |
| G9   | a | 0   | 1200 | 1200 | 0.251 | 0 |
| G9   | b | 200 | 1000 | 1200 | 0.303 | 0 |
| G9   | c | 40  | 1160 | 1200 | 0.231 | 9/seed (27 total) |
| G1'' | a | 0   | 600  | 600  | 0.127 | 0 |
| G1'' | b | 120 | 480  | 600  | 0.155 | 0 |
| G1'' | c | 120 | 480  | 600  | 0.145 | 0 |
| G7'' | a | 0   | 600  | 600  | 0.133 | 0 |
| G7'' | b | 120 | 480  | 600  | 0.124 | 0 |
| G7'' | c | 120 | 480  | 600  | 0.161 | 0 |
| G11''| a | 0   | 600  | 600  | 0.249 | 0 |
| G11''| b | 60  | 540  | 600  | 0.345 | 0 |
| G11''| c | 60  | 540  | 600  | 0.314 | 0 |

Each stage-2 survivor received a full, uninterrupted sizing slice — G2'/G4' ≈ 120–137
evals per survivor (m=4), G9 ≈ 232 (m=5), G1''/G7'' 120 (m=4), G11'' 180 (m=3) —
so the fragmentation the E-9 hypothesis targeted (v2's interleaved `max(40, B//6)=100`
broken slices) was in fact removed: survivors got ≥ 120 *unbroken* evals. It did
not change the outcome.

### Coverage-correlation (goal type × blame coverage × guided-vs-random)

The v2 science question, re-measured under the split. `blame_extra_sims` counted
SEPARATELY (ripple-FD path), NOT deducted — parity preserved (the counted evals are
identical across arms per goal). Diagnoses deterministic across seeds.

| goal | type | binding metric | blame coverage | blame_extra_sims | guided solved | random solved |
|---|---|---|---|---:|---|---|
| G2'  | match (S22)   | `s22_max_db`   | **unavailable** | 0 | 0/3 | 0/3 |
| G4'  | match (S11)   | `s11_max_db`   | **partial** (gm proxy, NM1–NM5) | 0 | 0/3 | 0/3 |
| G9   | band-shape    | `s21_ripple_db`| **partial** (capped FD) | 9/seed | 0/3 | 0/3 |
| G1'' | gain          | `s21_db`       | **partial** (gm/gds OP, NM1–NM5) | 0 | 0/3 | 0/3 |
| G7'' | current       | `idd_ma`       | **full** (per-device Id share, NM1/NM2) | 0 | 0/3 | 0/3 |
| G11''| linearity     | `iip3_dbm`     | **unavailable** | 0 | 0/2 | 0/2 |

**Honest reading (identical structure to E-8 v2).** The coverage instrument again
reported the correct state at every tier — S22 and IIP3 `unavailable` (no handler),
current `full` (Id closed to Idd), match/gain/ripple `partial`. And again the
correlation is **untestable**: with the guided-vs-random outcome column flat at
0/6-vs-0/6, there is no outcome variance to correlate against. High-coverage G7''
(`full`) did no better under guidance than zero-coverage G11'' (`unavailable`) —
every arm scored zero. The two-stage split did not turn coverage into an advantage
because it did not turn *anything* into a solve.

### Falsifier verdict (E9-TWOSTAGE §5, applied verbatim)

> *If guided two-stage editing (arm C) solves NO goal that BOTH sizing-only (arm A)
> AND random two-stage editing (arm B) leave unsolved, then the two-stage repair
> FAILS for this goal set, and the ceiling moves to the move repertoire / editor
> intelligence (→ ROADMAP §7).*

Arm C solved **0** goals; arms A and B solved **0**; there is no goal C solves that
A and B do not. **The falsifier is MET: the two-stage repair fails for this goal
set.** The §5 third sub-reading governs — **BOTH B and C solve ~zero, the E-8 v2
secondary-negative replicated under the split**: the ceiling is NOT the budget
structure (splitting the job removed the fragmentation and changed nothing) and
NOT the diagnosis (which reports correctly at every coverage tier but is untested
on a zero outcome). **The ceiling is the move repertoire / editor intelligence.**
The next lever is ROADMAP §7 (a smarter editor: learned move-proposal priors,
playbook-informed routing, critic-in-the-loop edit scoring) — each its own future
pre-reg — not the budget allocation.

This is a strong, clean negative: E-6 tested budget *allocation* (racing vs full),
E-9 tests budget *job-splitting* (search vs sizing); both leave the structural
zero-solve intact. The repertoire/editor is now the twice-implicated bottleneck
(E-7 §4.3, E-8 v2 secondary negative, E-9 falsifier).

### Deviations from the pre-registration (recorded)

1. **D1 — stage-1 candidate pool smaller than k for narrow aimed-edit goals; unspent
   stage-1 budget ROLLS into stage-2.** The guided/random aimed-edit families are
   narrow: for G2' the `p4_insert_series_element`/aimed edits realize only ~51
   *distinct* topologies (measured), for G4' ~57, for G9 the ripple edits ~40. A
   stage-1 that insisted on k=120 UNIQUE candidates would spin on duplicates
   indefinitely. The runner therefore bounds proposal attempts and stops stage-1 on
   a stall (no new unique candidate for `stall_lim` attempts); any unspent stage-1
   budget rolls into stage-2. **The matched TOTAL budget B is preserved exactly**
   (e.g. G2' c: 52 + 548 = 600; G9 c: 40 + 1160 = 1200) — parity across arms is on
   the TOTAL, which is the pre-registered axis (§3). G1''/G7'' had rich enough pools
   to fill k=120. This is a faithful realization of the §3.1 clause "if fewer than m
   distinct candidates survive … the surviving candidates split the entire (B−k)
   budget"; it generalizes it from "fewer than m survivors" to "fewer than k
   screenable candidates". No parity broken; recorded for transparency.
2. **D2 — AnalogGenie symlinked into the worktree** (`wt-e9/AnalogGenie` →
   `$LNA_DEPS_ROOT/AnalogGenie`, read-only). Without it `templates.emit_sequence`
   raises `FileNotFoundError` on `AnalogGenie/repo/SPICE2GRAPH_compress.py` and
   `realize()` silently yields zero candidates (the same trap E-8 v2 hit, deviation
   #2 there). The link is to the read-only main checkout; nothing is written under it.
3. **D3 — G11'' IIP3 probed at coarse stride 25 on best-so-far in stage-2** (bounded
   tier-3 cost), exactly as the E-8 v2 / nullv3 runners did; 146 probes / 49.8 min
   across 6 cells, ~20.5 s/probe, reported separately (never deducted from an
   env-eval budget). No spec yaml flipped — G11'' uses the in-memory tier-3 path.

### Scope limit (binding, inherited)

This shows only that the two-stage split, on the six E-8 v2 survivor goals at the
matched TOTAL budgets and seed counts here, solves none. It does not prove these
goals need a larger repertoire at unbounded budget, nor does it test the
smarter-editor directions of ROADMAP §7 — those are future pre-registrations.

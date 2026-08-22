# E11-GENEDIT — the generator-as-editor experiment (pre-registration)

**Status: PRE-REGISTRATION — committed BEFORE any counted scoring eval.** Nothing
above the RESULTS fence was informed by any scored E-11 simulation. Governance
carries forward from E7-MOVES / E8-LADDER-V2 / E9-TWOSTAGE: goldens-green before
and after every landing, the two-line branch law (engineer never writes under
`lna/`), append-only stores, PYTHONHASHSEED=0, ≤8 concurrent ngspice, matched
TOTAL budget per (goal,arm,seed), no spec yaml edited (all deltas are in-memory
spec mutations).

---

## 0. Motivation — what E-9 left, and the next §7 lever

E-9 (E9-TWOSTAGE.md §Results) scored **0/6 on all three arms** (sizing-only,
random-primitive two-stage, blame-guided two-stage). Its falsifier fired on the
third sub-reading: **the ceiling is the move repertoire / editor intelligence**,
not the budget structure (splitting search from sizing removed fragmentation and
changed nothing) and not the diagnosis (which reports correctly at every coverage
tier but is untested on a zero outcome). E-9 §Falsifier explicitly routes the next
lever to ROADMAP §7 — *a smarter editor: learned move-proposal priors,
playbook-informed routing, critic-in-the-loop edit scoring*.

The user ruled (2026-08-22) the next editor lever: **generator-as-editor** — the
trained circuit model proposes structural variants by regrowing segments of an
existing circuit's token sequence. **No hand-authored moves.** And **every
proposed edit is durably logged as future training data** for learned move priors
(the edit log, §5, is a first-class deliverable, not telemetry).

E-10's strict amendment (E10-GAPAUDIT.md §AMENDMENT, which supersedes the defective
original tables) classified the six E-9 goals: 3 near-miss (G1'', G9, G7''), 3
hopeless (G4'' hard; G2'' & G11'' blind). E-11 keeps the three near-misses and
replaces the three hopeless goals with three fresh small-extension goals authored
by store arithmetic (§2.2).

---

## 1. Hypothesis (stated before any number is seen)

> **A trained generator, used as an editor — regrowing a segment of an existing
> circuit's Eulerian token sequence and completing it — proposes structural
> variants that solve goals which (i) sizing provably cannot at the scored budget
> and (ii) random-primitive two-stage editing (E-9 arm B, replicated here as arm
> B) did not. Generic regrow (cut position + temperature + length cap only, no
> circuit-specific injection) carries usable structural signal that the primitive
> repertoire lacks.**

The falsifiable content: does swapping the *proposal mechanism* — from hand-coded
primitive graph edits (arm B) to model-regrown token completions (arm C), with the
two-stage split, screen, cull, and sizing machinery held byte-identical — reach any
of these six targets that neither sizing-only nor primitive editing reached, or
reach a shared solve faster (SPICE-minutes to first feasible)?

---

## 2. Goals (six: three keeps + three fresh)

Extended spec = the task's full base constraint block (task→spec via `tasks.py`) +
the goal's delta, applied by in-memory `ext_spec_of` (no spec yaml touched). A
design is **solved** iff it is base-feasible AND clears the delta.

### 2.1 KEEPS (cited to E-10 amendment §A.4; definitions from E9-TWOSTAGE §2)

| goal | task | delta | type | reachability (existence proof, E-10 §A.4) | B | N |
|---|---|---|---|---|---:|---:|
| **G1''** | dhruva-l1-t2-a | `s21_db ≥ 33` | gain | store wl `ace8383c` passes full extended spec (s21 37.53, s11 −10.00, idd 12.99, nf 1.29) | 600 | 3 |
| **G9** | dhruva-l5-t2-a | `s21_ripple_db ≤ 3.0` | band-shape | store wl `439032fd` passes (ripple 2.989) | 1200 | 3 |
| **G7''** | dhruva-l5-t2-a | `idd_ma ≤ 9.0 AND s21_db ≥ 22.3` | current | store wl `998ff3a1` (idd 7.07, s21 23.19, nf 2.38) fails ONLY s11_max by 0.74 dB | 600 | 3 |

**Cold-start rule (binding).** The store rows above are *existence proofs only*.
Every arm starts COLD from the task's standard start anchor (identical to E-9);
the passing store topology is NEVER used as a warm-start (that would leak the
answer). This is the search-efficiency / reachability gap E-10 §3 named.

### 2.2 FRESH goals (authored by store arithmetic — contamination ledger, §2.3)

**Placement rule (pre-declared, stated BEFORE running anything):** new limit =
best-in-store **base-feasible single-point** value for that metric on that task,
tightened by ~1.5× the E-10 near-miss threshold for that metric type (S11/gain
2.0→**3.0 dB**, NF 0.5→**0.75 dB**, Idd 1.5→**2.25 mA**) — beyond sizing's
demonstrated reach but plausibly within one structural change. Metric types are
three DIFFERENT measurable families, none duplicating the keeps' binding metrics
(s21_db, s21_ripple_db, idd_ma) where possible, and NOT s22_max_db or iip3_dbm
(unrecorded in the store, ruled out as blind by E-10).

**Null-filter pre-check (the pre-reg's Arm-A-at-scored-budget filter, applied to
candidate placements BEFORE fixing the three).** The E-8 lesson: null filters must
run at scored budget. A store-derived limit is only a *floor* on reachability;
whether sizing the cold-start anchor at B=600 already clears it is exactly what
Arm A measures. Candidate fresh goals whose Arm-A cold-start sizing SOLVES them at
B=600 are rejected (they are within sizing's reach, useless for testing the
editor). This pre-check uses NO target-circuit knowledge — only the task's own
anchor sizing. Results in §2.4; the three KEPT fresh goals are those Arm A leaves
unsolved.

| goal | task | delta | type | best-in-store base-feasible | tighten | Arm-A null-filter (B=600) | B | N |
|---|---|---|---|---|---|---|---:|---:|
| **GA** | dhruva-s-t2-a | `nf_db ≤ 0.538` | NF | 1.288 dB | −0.75 | best 2.719 → unsolved (KEEP) | 600 | 3 |
| **GB** | dhruva-l1-t2-a | `s11_max_db ≤ −13.019` | match (S11) | −10.019 dB | −3.0 | best −10.019 → unsolved (KEEP) | 600 | 3 |
| **GC** | dhruva-l2-t2-a | `s21_min_db ≥ 37.926` | gain-at-edge | 34.926 dB | +3.0 | best 22.328 → unsolved (KEEP) | 600 | 3 |

Three distinct bands (S / L1 / L2), three distinct metric families (NF / S11 /
gain-at-band-edge), none duplicating a keep's binding metric (s21_db mid-band,
ripple, idd). `s21_min_db` (band-edge gain) is measurably distinct from G1'''s
mid-band `s21_db`. None is s22_max_db or iip3_dbm (blind, ruled out).

### 2.3 Contamination ledger (fresh goals)

The three fresh goals derive **only from store data** (`lna/data/topo_labels.jsonl`)
and the pre-declared placement arithmetic. No papers, no target-circuit knowledge,
no reference to any specific solution topology were consulted. The best-in-store
base-feasible single-point value per (task, metric) is pure arithmetic over
recorded rows; the tightening factors are the pre-declared per-metric constants.

### 2.4 Null-filter pre-check results

Eight candidate placements were null-filtered with Arm A (cold-start anchor
sizing, B=600, seed 1). `best_on_target` is the target-metric value at the best-
objective eval; `solved` means some eval was extended-feasible.

| candidate | task | target | Arm-A best_on_target | verdict |
|---|---|---|---|---|
| NF_l1 | dhruva-l1 | nf_db ≤ 0.47 | 1.587 | unsolved (KEEP-eligible) |
| NF_l5 | dhruva-l5 | nf_db ≤ 0.445 | 2.243 | unsolved (KEEP-eligible) |
| **NF_s (→GA)** | dhruva-s | nf_db ≤ 0.538 | 2.719 | **unsolved → KEPT** |
| **S11_l1 (→GB)** | dhruva-l1 | s11_max_db ≤ −13.019 | −10.019 | **unsolved → KEPT** |
| S11_l2 | dhruva-l2 | s11_max_db ≤ −13.031 | −12.933 | **SOLVED by sizing → REJECT** |
| **GE_l2 (→GC)** | dhruva-l2 | s21_min_db ≥ 37.926 | 22.328 | **unsolved → KEPT** |
| GE_l1 | dhruva-l1 | s21_min_db ≥ 37.935 | 23.856 | unsolved (KEEP-eligible) |
| IDD_s | dhruva-s | idd_ma ≤ 7.08 | 5.034 | **SOLVED by sizing → REJECT** |

Two candidates (S11 on dhruva-l2; Idd on dhruva-s) were rejected because cold-start
sizing already clears them at B=600 — a store-derived floor is not automatically
beyond sizing's reach, and the null filter is what proves it. The three KEPT fresh
goals span three tasks/bands and three metric families and are each Arm-A-unsolved
at the scored budget.

---

## 3. Arms (matched TOTAL counted evals per (goal,arm,seed) = B)

- **A — sizing-only.** One uninterrupted B-eval CMA-ES sizing run on the cold-start
  anchor topology against the extended spec (standard path, byte-identical to E-9
  arm A). Serves as the null filter AT the scored budget.
- **B — primitive-edit two-stage.** Exactly E-9 arm B mechanics: random generic
  primitive edits from the adopted E-7 repertoire (`g2_moves.mutate`); stage-1
  screens k candidates at 1 counted L1 eval each, culls to top-m by L1 objective;
  stage-2 gives each survivor an uninterrupted (B−k)/m sizing run. Stage-1 stall →
  unspent k rolls into stage-2 (E-9 D1). k=120/m=4 at B=600; k=200/m=5 at B=1200.
- **C — generator-as-editor two-stage.** SAME k/m/budget/screen/cull/sizing
  mechanics as B, but proposals come from the adopted checkpoint
  `lna/out/ft_p5v7_v2.pth` (vocab 1008). Loaded via the finetune-era loader pattern
  (`_attrib_sample.py`: rebind `finetune.ckpt_path`, `finetune.load_ft('p5',
  winners=True, tag='p5v7')`) — `generate.py` lacks --ckpt and
  `genie_common.load_model` builds vocab 1005, both known traps. **Regrow
  mechanism:** take the parent topology's Eulerian token sequence, truncate at a
  sampled cut point (varied across proposals, sampled within the structural body —
  cut fraction ∈ [0.10, 0.90], not the first few tokens), prepend the class token
  matching the task's band (NB if the parent bears an inductor, else WB), let the
  model complete to TRUNCATE (temperature 1.0), decode via `Topology(seq)` union-
  find replay, realize via the standard token round-trip (`topo_to_netlist` →
  `moves.realize` = L0/structural screen, 0 sims), dedupe by wl-hash, drop decode
  failures and L0-screen failures (uncounted, but LOGGED). Nothing circuit-specific
  is hand-injected — cut position, temperature, and length cap are the only knobs,
  all generic.

**Arm-C stage-1 generation bounds (generic, not per-goal).** The distinct-child
pool per parent is small (smoke: 17–44 << k=120), so arm C cannot fill k=120
unique screened candidates and would otherwise generate indefinitely. Stage-1
generation is therefore bounded by three generic caps: a generation-batch ceiling
(20 batches × 16 = 320 proposals — harvests the full distinct pool), a
consecutive-empty-batch stall (4 batches with no new distinct valid child → stop),
and an 8-minute generation wall cap. Whichever binds first ends stage-1; any
unspent stage-1 eval budget rolls into stage-2 (E-9 D1). The matched TOTAL budget
B is preserved exactly (stage-2 uses the full remainder). These are the same
generic knobs as the smoke (no circuit-specific injection).

**Generation cost accounting.** Generation is CPU token-sampling (no GPU on box).
Its wall-time is NOT counted in SPICE evals but IS measured and reported per cell
(`gen_min_total`). SPICE-minutes-to-first-feasible is the primary metric;
generation-minutes are reported alongside.

### 3.1 k, m, budget per goal

| goal | B | k | m | stage-2 per survivor (B−k)/m | total |
|---|---:|---:|---:|---:|---:|
| G1'', G7'', GA, GB, GC | 600 | 120 | 4 | 120 | 600 |
| G9 | 1200 | 200 | 5 | 200 | 1200 |

If fewer than m distinct candidates survive stage-1, survivors split the entire
(B−k) stage-2 budget evenly (total stays = B); unspent stage-1 budget rolls into
stage-2 (E-9 D1). Recorded per cell.

---

## 4. Metrics

Per (goal,arm,seed) cell (crash-safe atomic JSON under `tmp/e11_results/`):
- **solved: y/n** (base-feasible AND clears the delta).
- **PRIMARY: TOTAL counted evals + SPICE-minutes to first feasible** (SPICE-min =
  Σ `cost.wall_s` over counted evals).
- **generation-minutes** (arm C; reported separately, never counted as evals).
- **stage-1 vs stage-2 spend** (counted evals + SPICE-min each).
- **survivor set** (m culled wl-hashes + stage-1 objective).
- **winning edit** (the mechanism that produced the solved survivor; empty if
  unsolved).

Goal counted **solved** if ≥1 seed clears base-feasible + the delta. Headline:
goals solved per arm (A / B / C).

---

## 5. Edit log (first-class deliverable)

Append-only JSONL `engineer/data/edit_log/e11_edits.jsonl` (tracked, committed):
one row per PROPOSAL (arms B and C, INCLUDING decode/screen failures). Schema:

```
{ts, campaign:"e11", goal, arm, seed, parent_wl,
 proposal_mechanism ("primitive:<name+args>" | "regrow:{cut_index,cut_frac,temperature,n_new_tokens}"),
 child_wl (null if decode failed), decode_ok, l0_pass, l0_score,
 l1_objective (if screened), survived_cull, stage2_best_obj, stage2_solved, era}
```

This is the training substrate for the future learned-move-priors lever; schema
completeness matters more than compactness. Failed proposals (decode failure,
topo-invalid, realize/screen failure, duplicate-wl, not-sizable) are logged with
`decode_ok`/`l0_pass` flags and a `note`.

---

## 6. Smoke gate (UNCOUNTED mechanics check of channel C)

Before the campaign, an uncounted mechanics smoke: from the standard start
topologies of 3 of the six tasks, generate regrow proposals each; report
distinct-child-wl rate, decode-failure rate, L0 pass rate. **HARD GATE: if any
parent yields < 10 distinct valid children, the channel is dead as configured** —
try the generic knobs (cut range, temperature); if still dead, STOP and commit the
pre-reg + smoke with a NEGATIVE outcome.

**Result (executed as `engineer/e11_smoke.py`; UNCOUNTED, no ngspice scoring).**
The first configuration (50 proposals, cut fraction ∈ [0.15, 0.85], T=1.0) came in
just under the gate on two parents (dhruva-l1: 9 distinct, dhruva-l5: 8). Per the
gate's explicit escape clause, the generic knobs were widened — **cut fraction ∈
[0.10, 0.90], 100 proposals per config, temperature ∈ {1.0, 1.2}** (nothing
circuit-specific; only the three permitted generic knobs). Decode-failure rate was
0% on every configuration (completions terminate at TRUNCATE); the binding factor
was the L0/structural-screen pass rate and wl-duplication.

| parent | tok len | proposals | decode-fail | L0-pass | distinct valid children (excl parent) |
|---|---:|---:|---:|---:|---:|
| dhruva-l1-t2-a | 205 | 200 | 0/200 | 46/200 | **44** |
| dhruva-l5-t2-a | 89  | 146 | 0/146 | 68/146 | **17** |
| dhruva-s-t2-a  | 181 | 200 | 2/200 | 35/200 | **35** |

**GATE: PASS** — every parent yields ≥ 10 distinct valid children (44 / 17 / 35).
The channel is viable as configured; the campaign proceeds. (The campaign runner
uses cut fraction ∈ [0.10, 0.90], T=1.0; it generates in batches until k L1-screen
candidates are filled or a stall/guard bound is hit, exactly as arm B does for
primitive proposals.)

---

## 7. Falsifier (pre-stated, before any scored eval)

> **If arm C solves no goal that arms A and B both leave unsolved, AND C is not
> faster to first-feasible on any goal that C and either other arm both solve, then
> generator-as-editor with generic regrow fails for this goal set, and the next §7
> lever must change the proposal mechanism itself (not its budget or screening).**

Sub-readings:
- **C beats {A,B}** on ≥1 goal (solves where both A and B do not): generator-as-
  editor lifts the E-9 ceiling; the regrow channel carries structural signal the
  primitive repertoire lacks.
- **C ties on solves but is faster to first-feasible** on a shared solve: a weaker
  positive for the channel (better search efficiency, same reachability).
- **C solves nothing A/B don't and is not faster:** falsifier MET — generic regrow
  fails; the next lever must change the proposal mechanism (e.g. learned priors
  trained on THIS edit log, critic-in-the-loop), not budget or screening.

---

## 8. Containment & crash-safety

- Engineer-branch worktree `wt-e11` (from `engineer` @ b3d77d4). `/home/dpatni/
  circuit-repro` is READ-ONLY; nothing writes under `lna/`; `tmp/wt-e6` untouched.
  No merge, no push.
- KNOWN TRAP (E-9 D2): `AnalogGenie` symlinked read-only into the worktree root
  (else `templates.emit_sequence` raises FileNotFoundError and realize() silently
  yields zero candidates). The checkpoint `ft_p5v7_v2.pth` is read from the
  read-only main checkout (`lna/` reads are allowed).
- ≤8 concurrent ngspice. PYTHONHASHSEED=0.
- Crash-safety: atomic per-cell JSON under `tmp/e11_results/`; aggregator
  `e11_agg.py` reconstructs the whole campaign from cells alone; status file
  `tmp/E11_STATUS.md` kept on disk. This pre-reg is committed BEFORE any scored eval.

<!-- ================================================================= -->
<!-- RESULTS BELOW — appended AFTER the scored run; nothing above this  -->
<!-- line was informed by any scored E-11 eval.                        -->
<!-- ================================================================= -->

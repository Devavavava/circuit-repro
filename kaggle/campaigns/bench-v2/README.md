# bench-v2 generation campaign

Pre-registered in `kaggle/PREREG-BENCH-V2.md` (frozen 2026-09-29, commit `e5bfd0755`).
The user approved **full size**: 20–25 bench cells plus about 300 training tasks, on local CPU.
Verifier: `bench_anchor_prep.smoke_run(tokens, spec, seed, 2500, "bptm45", profile="rl-v1")` on rl-v1-form specs (`kaggle/VERIFIER-RL-V1.md`).
Every result row carries the git era stamp (HEAD plus the md5 of `bench_anchor_prep.py` and `bv2.py`) and `result["verifier"]`.

Status: **RUNNING under PRE-REG AMENDMENT 1** (full run launched 2026-09-29, stopped at 26.8 h on 2026-09-30, resumed with the amendment the same day). **Read the "AMENDMENT 1" section first**: where it differs from the design sections below, the amendment wins. Results sections are filled in when the run finalizes.

## Files

| file | role |
|---|---|
| `bv2.py` | The whole pipeline: scheduler, search, repair, planting, cell and training stages, finalize, worker. |
| `fence_check.py` | Bench/training fence check. Finalize runs it; it can also be run standalone. |
| `smoke_checks.py` | Post-smoke checks: flags and profile, determinism, known-unstable rejection. |
| `steer_unit_a1.py` | AMENDMENT-1 steering unit check on synthetic accepted cells (no sizing), writes `smoke/steer_unit_a1.json`. |
| `smoke_checks_a1.py` | AMENDMENT-1 smoke checks: floors, core classes of the pre-amendment cells, quotas, steering, determinism, fence (with a negative control), era tags. |
| `launch.sh` / `stop.sh` / `envrun.sh` | Detached launch (resumable), graceful stop, and the environment (an inline copy of crenv.sh; `TMPDIR=/tmp/cr-bv2`). |
| `run/` | The full run. Not committed except `progress.json`, `README`-level summaries and specs. |
| `smoke/` | The smoke runs and their checks (committed): `smoke/run/` (original), `smoke/run-amend1/` (AMENDMENT 1). |
| `run/pre-amendment/` | Frozen copy of the pre-amendment record at the 26.8 h stop (`MANIFEST.json` has md5s). |

Outputs at finalize:
- `kaggle/editcap-lib-v2/<cell>/{spec.yaml, anchor.net, anchor.tokens.json, evidence.json, cell.json, witness/}` plus `INDEX.json`. `witness/` is **EVAL-ONLY**.
- `kaggle/train-pool-v2/<task>/...` plus `INDEX.json`, with difficulty labels.

## AMENDMENT 1 (2026-09-30) — what changed in the pipeline

Pre-reg: `kaggle/PREREG-BENCH-V2.md` § "AMENDMENT 1" (commit `78ccdf0b4`). User ruling 2026-09-30: *"go with B, including the spec floors"*.

**Why.** The run was stopped cleanly at 26.8 h, before any cell was frozen. At that point it had 378 planted and 10 accepted cells, with this pattern:
- all 10 accepted cells were wideband, all had parent a3, and all were built around one fix: a series input L, usually plus an R into the input
- every spec had s11 ≤ −7.85 dB and gain between 7.9 and 10.5 dB
- the training pool held 268 tasks

The frozen record is in `run/pre-amendment/`, with md5s in `MANIFEST.json`.

### A1-1 Core-fix classes (`abl_core`, `group_atoms`, `net_classes`, `inert_groups` in `bv2.py`)
- **Atoms.** Each edit group of a witness script gets one canonical atom, `op:TYPE:role`.
  - The role comes from net classes computed on the **parent anchor** netlist. The first match wins: `IN`=VIN1, `OUT`=VOUT1, `RAIL`=VDD/VSS, `G`=a MOS gate, `D`=a MOS drain, `S`=a MOS source, `X`=another parent net, `NEW`=a net that is not in the parent.
  - A 2-terminal role is the sorted pair of net classes, for example `add:L:IN-G`.
  - A MOS role is `d<cls>.g<cls>.s<cls>`.
  - A delete uses the deleted device's role.
  - A rewire is `rw:T:<pin>:<old>><new>`.
  - Composites are `ser:<T>:<host>.<pin>:<old>` and `stk:<T>:<host>.<pin>:<old>.g<gate>`.
  - Because roles are fixed by the parent, they never depend on the other edits in the script.
- **Inert groups.** A group is inert if every op in it adds an R/C/L and every added passive is on the W2 `inert_devices` list of the first feasible A1 run. The rewire half of a series insert counts as part of such a group.
- **ABL.** The ablation runs in three steps:
  1. *Drop-one.* Remove each group in turn. A group is **essential** if the reduced circuit is invalid, or is infeasible at **both** seeds {1, 2}. This is the same two-seed standard as the F2 null. The pre-amendment ABL used seed 1 only.
  2. *Greedy backward elimination.* Start from the full script. Try groups in this order: inert, then non-essential, then essential. Drop a group if the circuit without it is still feasible at seed 1 or 2.
  3. What remains is the **core**: a minimal sufficient subset in which every group is ablation-essential.
- **Class** = the sorted multiset of core atoms, with inert groups excluded even if the greedy step could not drop them (flag `inert_group_needed_for_feasibility`).
  - The 25 % cap (6 of 25 at build time) applies to these classes.
  - The old heuristic label is kept as `legacy_class`.
- **Strip.** When the core is a strict subset of the script, the core-only netlist is re-verified as a full witness:
  - A1: feasible at ≥ 2 of seeds {1, 2, 3}
  - A2: tightened spec feasible at ≥ 1 of seeds {1, 2, 3}
  - A3: fresh seeds, feasible at ≥ 1 of {4, 5, 6}

  If it passes, `witness/` holds the stripped witness and `witness/original/` holds the search witness. Both are fenced.

  If it fails, or if the core has fewer than 2 primitive edits (the pre-reg's lower bound), or if the core lies in the single-edit space, the original witness is kept and the reason is recorded in `core.strip.flag`.

### A1-2 Quotas and steering
- **Selection** (`select_cells`). This covers post-amendment accepted cells only. The selection is the largest n ≤ 25 that satisfies all of the following:
  - at most 1 cell per WL
  - core class ≤ ⌊0.25n⌋
  - parent ≤ ⌊0.40n⌋
  - narrowband ≥ ⌈0.25n⌉

  The greedy is deterministic: it first takes narrowband cells in acceptance order until the quota is met, then fills the rest in acceptance order.

  `selection_report` also gives the size without the narrowband quota, so a binding quota is reported as a shortfall and never relaxed.

  The bench stops when the quota-compliant selection reaches 25.
- **Class-cap rule (pending a user ruling).** The rule comes from config `class_rule` and is chosen per run.
  - **(a) `signature`** is the **default**, as pre-registered. The class is the whole core-fix signature.
  - **(b) `primary_atom`** caps the core's *primary atom* instead. No primary atom may appear in more than 25 % of the selected cells.
    - The **primary atom** is the atom of the core group (inert groups excluded) whose removal *from the core* causes the largest feasibility loss.
    - The loss is 1e9 when the reduced circuit is invalid. Otherwise it is −(best over seeds {1, 2} of the worst normalized margin at the cell spec), with the wide-µ shortfall µ_wide − 1 folded in when the design is wide-unstable. An unsized run counts as margin −1e6.
    - Ties are broken by the larger loss, then the atom string ascending, then the group id.
    - For a 1-group core, the primary atom is that group's atom.
  - **(c) Any-atom prevalence** is reported alongside: the fraction of cells whose core contains each atom.

  `selection_report` always computes (a) and (b). `progress.json` shows both (`bench.selectable_a_signature` and `bench.selectable_b_primary_atom`, plus `accepted_per_primary_atom` and `accepted_atom_prevalence`), and `INDEX.json` records all three. The bench stop rule and finalize use the active rule.
- **Build caps.** A parent with 10 accepted cells (40 % of 25) gets no more search children and no more admissions (status `skipped_parent_cap`). A core class with 6 accepted cells is capped: any child or queued cell whose live atoms *contain* a capped core is rejected or skipped.
- **Steering policy** (`make_generation_bench`). The weights are recomputed every generation and logged as a `steer` event. They are also shown in `progress.json` under `bench.steer`.
  - **Counts.** An accepted post-amendment cell counts 1 and a cell in validation counts 0.5.
  - **Point weight.** `w_g = m_bt / (1 + n_band)`. For narrowband, `m_bt = 1 + 2·max(0, 7 − n_nb)/7`, so narrowband gets up to 3× while the 25 % quota (7 of 25) is unmet. For wideband, `m_bt` is 1.
  - **Allocation.** Children are allocated as N = 6 × #points ∝ w_g, using the largest remainder, with at least 1 per point.
  - **Parent weight.** `w_p = 0` at the parent cap, otherwise `1/(1 + n_parent)`. Random children draw their anchor by `w_p`.
  - **Tournament.** Parents are drawn from the top-20 archive with weight `w_p / (1 + #accepted cores contained) / (1 + atom_penalty)`.
    - `atom_penalty` is the largest number of accepted cores that contain one of the member's atoms, divided by 6.
    - This is a **soft** push away from a dominant ingredient, not a selection criterion. See the finding in A1-6.
  - **Admission order.** Narrowband comes first while the quota is unmet. Then, in order: the least-represented parent, the fewest accepted cores contained, the lower atom penalty, the larger dominance excess, and plant order.
  - **Generation 0** re-sizes pre-amendment bench topologies under the new probes. It takes the best old score first and rotates over the parents by `w_p`.

### A1-3 Spec floors (`FLOORS`, `floor_probe_value`, `floor_violations`, `PROBE_BENCH`)
- **Floors.** Every bench cell must have `s11_max_db` ≤ −9 dB and `s21_db` ≥ 10 dB. Narrowband cells use `s11_max_db` as well (rl-v1 W6).
- **Where the margins come from.** Planting uses L = a/(1 + δ) for |L| ≥ 1 (D3). So L meets the floor F exactly when a is within F·(1 + δ):
  - s11 must reach **−9.18 dB**
  - s21 must reach **10.20 dB**

  The bench probe adds a 0.01 guard against the 1e-4 outward rounding, giving **s11_max_db ≤ −9.19** and **s21_db ≥ 10.21** for both wideband and narrowband. The other probe limits are unchanged.

  A witness that is probe-feasible at seeds 1 and 2 therefore plants at s11 ≤ −9.0098 and s21 ≥ 10.0098.
- **Hard check.** `plant_bench` refuses any planted spec whose limits are looser than a floor. The event is `floor_reject`, and the counts are in `progress.bench.floor_rejects`.
- **Files and scope.** The probe files are new (`specs/probe-amd1-*.yaml`); the old probe files stay as the record. The training stream keeps the old probes, because the training pool has no floors.

### A1-4 Budget and fence
- **Bench budget.** The bench hard stop is **72 h from the resume** (`start.json: t_amend1`, `progress.eta.bench_elapsed_h_since_amendment`). The training and total budget is unchanged: 118 h from `t_start`.
- **Fence.**
  - `plant_train` fences against every accepted cell of both eras and every post-amendment **planted** cell. It checks the WL and token hash of both the original and the stripped witness, and the spec sha.
  - `finalize` and `fence_check.py --cells-jsonl` apply the same fence. `fence_check.py` now includes post-amendment planted cells of any status.

### A1-5 Pre-amendment rows, era tags and cache
- **Pre-amendment cells.** They are re-emitted into `run/cells.jsonl` with `era_tag: "pre-amendment", selectable: false`. `select_cells` and `finalize` only select cells with `era_tag == "amendment-1"`.
- **Naming and tagging.** New cells are named `v2a-…`. New bench candidates are `B<gen>-…`. New result rows carry `phase: "amendment-1"` plus the new git/md5 era stamp.
- **Kept evidence.** The pre-amendment calibration, F1 and F2 designs stay in the pre-kill pools, rebuilt from the cached rows. Their accepted witnesses stay fenced. Their bench candidates' topologies seed generation 0.
- **Re-classification.** The 10 pre-amendment accepted cells are re-classified by the same `abl_core`, as a record only. The output is `run/pre-amendment-core-classes.json`.
- **Cache.** The cache is reused only on the exact job key: `jid = sha(token hash, spec content, seed, budget, profile)`. The full run also reads `smoke/run-amend1/results.jsonl` **read-only**, for exact-key hits only. That file comes from the same code and the same verifier.

### A1-6 Smoke (`smoke/run-amend1/`, `--mode smoke-a1`, checks in `smoke/smoke_checks_a1.json`)
**Setup.**
- Run with `launch.sh smoke-a1`. Grid: bench points wb0530-noise and nb240-gain, train point nb158-gain. Calibration at seed 1.
- Search: 2 bench generations of 4 children per point (generation 0 is pre-amendment seeds) and 1 training generation.
- SMOKE-only flags:
  - `smoke_force`: a would-kill is recorded and the cell continues.
  - `smoke_force_plant`: a pre-kill is recorded and the cell is planted anyway.
  - F2 is restricted to the first 12 edits.
- It reads the full run's cache read-only.
- Total: 137 new sizing calls, about 35 min wall clock. The scheduler was restarted twice mid-smoke to add the primary-atom variant and the forced planting. Each resume replayed through the cache.

**Floor-probe calibration.** 0/5 anchors are feasible at wb0530-noise; 2/5 are already feasible at nb240-gain.

**Search.**
- Of 16 bench children, 6 were probe-feasible and 4 were confirmed at seed 2.
- All 4 would have been pre-killed by a recorded a1 F1 design. They were force-planted, and their planted limits meet the floors (for example s11 −9.01 to −11.30 dB, s21 13.6–16 dB).
- `v2a-nb240-gain-003` ran every stage. Its core is one rewire, so the strip was correctly refused with flag `core_below_2_primitive_edits`.
- The other forced cells were cancelled or `not_validated_bench_done` when the bench target was reached.
- 0 training tasks were planted: 3 children, none confirmed.

**Checks** (`smoke_checks_a1.py` → `smoke/smoke_checks_a1.json`; all pass):
1. **Floors.** All 10 pre-amendment accepted specs are refused, both as written and when re-planted from their achieved metrics (s11 ≈ −7.84 > −9; s21 7.9–10.5 < 10 where applicable). All 11 bench `probe-amd1-*` files carry −9.19 / 10.21. None of the 4 post-amendment planted cells violates a floor.
2. **Core classes of the 10 pre-amendment cells.** These are real re-sizings (2-seed drop-one plus greedy core). The per-cell table is below.
3. **Quotas.** On synthetic data the selection is n = 23:
   - max parent 9 ≤ ⌊0.4·23⌋
   - 6 narrowband ≥ ⌈0.25·23⌉
   - no duplicate WL

   A narrowband-bound case selects 8 cells with the quota versus 16 without it (a shortfall is reported, nothing is relaxed).

   The primary-atom rule test: with one shared primary atom in 10 wideband cells, (a) selects 20 (10 carrying the atom) and (b) selects 13 (3 carrying it).

   The real 10 old cells, re-tagged as if post-amendment, give an **empty** quota-compliant selection (all a3, all wideband). They are really never selectable: `select_cells(pre) = 0`.
4. **Steering.** One `steer` event per generation. Generation 0 used 8 pre-amendment seeds; generation 1 had 6 mutation and 2 random children. No cell existed at generation time, so the in-run weights stayed flat. `steer_unit_a1.py` (`smoke/steer_unit_a1.json`, pass) injects 0/3/6/10 accepted wideband a3 cells and shows the response:
   - narrowband multiplier 3.0 and allocation shifted to 7:1
   - a3 wideband weight 1 → 0.25 → 0.14 → **0** at the parent cap, with no a3 children
   - the core becomes capped at 6
   - the atom penalty for `add:L:IN-G` goes 0.5 → 1.67
5. **Determinism.** A feasible cal row, an infeasible cal row, and an ABL row were re-run in a fresh worker: all byte-identical.
6. **Fence.** The finalize fence check gives rc 0 with 0 violations over 4 post-amendment planted cells (the training pool is empty in the smoke). Negative control: a training dir holding a copy of a planted-but-*not-accepted* cell (`v2a-nb240-gain-000`) is flagged on all 4 counts (token, WL, spec, body), rc 1.
7. **Era.** All 137 new rows are rl-v1 and tagged `phase: amendment-1`. The INDEX holds only `v2a-` cells.

**Core-fix signatures of the 10 pre-amendment accepted cells** (`smoke/run-amend1/pre-amendment-core-classes.json`, rebuilt in the full run from exact-key cache hits):

| cell | core signature (class a) | primary atom (b) | strip |
|---|---|---|---|
| v2-wb0530-power-010 | `add:L:IN-G + add:R:IN-X` | `add:L:IN-G` | re-verify failed (orig kept) |
| v2-wb0530-noise-009 | `add:L:IN-G + add:R:IN-X` | `add:L:IN-G` | re-verify failed (orig kept) |
| v2-wb0824-gain-044 | `add:L:IN-G + add:R:IN-X` | `add:L:IN-G` | stripped |
| v2-wb0530-noise-051 | `add:L:IN-G + add:R:IN-X` | `add:L:IN-G` | re-verify failed (orig kept) |
| v2-wb1020-noise-033 | `add:C:OUT-X + add:L:IN-G + add:R:IN-X` | `add:L:IN-G` | nothing to strip |
| v2-wb0530-power-102 | `add:L:IN-G + add:NMOS:dG.gG.sIN` | `add:L:IN-G` | stripped |
| v2-wb0530-noise-026 | `add:L:IN-G + add:L:OUT-D + add:R:OUT-D + del:L:X-RAIL` | `del:L:X-RAIL` | nothing to strip |
| v2-wb0530-power-144 | `add:L:IN-G + add:PMOS:dG.gX.sOUT + del:L:X-RAIL + rw:R:p:D>OUT` | `del:L:X-RAIL` | nothing to strip |
| v2-wb0530-noise-141 | `add:L:IN-G + add:L:OUT-D + add:NMOS:dRAIL.gD.sOUT + del:L:X-RAIL` | `add:L:OUT-D` | nothing to strip |
| v2-wb0824-gain-192 | `add:L:OUT-D + add:PMOS:dRAIL.gOUT.sIN + add:R:OUT-D` | `add:L:OUT-D` | stripped |

**Finding.** The 10 cells fall into **7** whole-signature classes, not one. The largest class is `add:L:IN-G + add:R:IN-X`, with 4 of 10 cells.
- For 009, the 2-seed greedy removed the `del L1`.
- For 051, it removed the extra PMOS, and the inert R also dropped out of the core.
- 102's core is L plus an NMOS input device.

By primary atom (rule b) the split is `add:L:IN-G` 6, `del:L:X-RAIL` 2, `add:L:OUT-D` 2. By prevalence (c), `add:L:IN-G` is in **9/10** cores (L parallel to the input DC-block cap, i.e. series input L to the gate) and `add:R:IN-X` in 5/10.

So the pre-registered whole-signature cap (rule a) alone would **not** have stopped the pre-amendment monoculture: capped at 25 %, it would still allow about 6 of 25 cells per variant. Rule (b) would cap the dominant ingredient at 25 %. That choice is pending a user ruling (D14/D17). Meanwhile the soft atom penalty is on in the search.

### Deviations / interpretations (AMENDMENT 1)
- **D8: "ablation-essential" is judged at two seeds.** A group is essential only if its removal leaves the circuit infeasible at both seeds {1, 2}. Plain drop-one is not enough: the core is the greedy minimal *sufficient* subset. Both the drop-one table and the greedy trace are archived in `cell.json.core`. Pre-amendment ABL was seed-1 drop-one only; those seed-1 rows are reused on their exact key.
- **D9: roles are net classes on the parent anchor**, with the precedence given in A1-1. A net that is both a gate and a drain (a diode) counts as G. Bulk pins are ignored.
- **D10: inert groups never enter a signature.** This holds even when the greedy step could not drop them; the cell is flagged instead.
- **D11: a strip is only attempted when the core keeps ≥ 2 primitive edits.** A 1-edit core keeps the original witness and is flagged `core_below_2_primitive_edits`. Its class is still the 1-atom signature.
- **D12: the floor probe carries a 0.01 guard.** It is −9.19 / 10.21, not the bare −9.18 / 10.20.
- **D13: steering depends on wall-clock order.** Steering reads accepted and validating counts at generation time, so on a later resume the bench generations after the first steering change can diverge from the original. This costs re-sizing, never correctness: every sizing call is still exactly keyed and deterministic. The pre-kill pool already had this property (see the resume note in the Smoke section).
- **D14: steering adds a soft atom-level penalty.** The pre-reg caps only whole core classes; the atom penalty is the only addition, and no selection criterion changed. The reason is that on the real data (A1-6), whole-signature classes do **not** merge the pre-amendment cells into one class, even though they share one ingredient. **Flagged for a user ruling:** whether to cap a single core atom (for example ≤ 25 % of cells containing `add:L:IN-G`).
- **D15: training labels may change on replay.** Replay of the training stream is exact on its candidates and sizing calls. But the pre-amendment anchor designs are now in the pools from the start, so a replayed task's difficulty label can come out `library-solvable` where the original run said otherwise. This is more correct, not less.
- **D17: the class-cap rule is a config value, pending a user ruling.** The default is (a) whole signature, as pre-registered; (b) is primary atom; (c) is any-atom prevalence and is only reported. Search-time build caps stay on whole signatures, and the soft atom penalty (D14) stays ON. Added at the orchestrator's request on 2026-09-30.
- **D18: the greedy core runs to a fixpoint.** It repeats passes until a full pass drops nothing, and every core group's drop-from-core trial is on record (`core.core_drop`). This is what the primary atom is computed from.
- **D19: every planted cell is now written to `cells.jsonl` at planting time.** Before this, a queued cell was only recorded when its status changed. Queued cells left behind when the bench target is reached are written as `not_validated_bench_done`. Without this, the fence would have missed planted-but-never-validated cells. The smoke found the gap and the negative control now covers it.
- **D20: `smoke_force_plant` exists in smoke-a1 only.** The smoke's 4 confirmed witnesses were all pre-killed, so this flag plants them anyway (recorded as would-kill) to exercise the post-amendment cell stages end-to-end. It is never set in the full run.
- **D16: the bench stop counts only a quota-compliant selection.** `bench_done` requires the quota-compliant selection (narrowband quota included) to reach 25.

## Pipeline design

### Grid, probe specs, streams

**Bands.** These are the declared pre-reg grid:
- wideband 0.5–3, 0.8–2.4 and 1–2 GHz (f0 is the geometric mean)
- narrowband f0 = 0.9, 1.575, 2.4 and 3.5 GHz, ±2 %

**Grid points.** Each grid point is a band × objective **flavor**, giving 21 points. The flavor sets the spec's objective weights:
- `noise`: NF 1, S21 0.5, Idd 0.5
- `gain`: S21 1, NF 0.5, Idd 0.5
- `power`: Idd 1, NF 0.5, S21 0.5

**The two streams have disjoint grid points.**
- The **bench** stream gets the 11 points with (band index + flavor index) even. The **train** stream gets the other 10.
- Every band appears in both streams.
- They use separate RNG streams (seeds `20260929_01` and `20260929_02`).

**Loose probe spec per band type.** This is written directly in rl-v1 form: `mu_min ≥ 1`, band NF `nf_max_db` for wideband, `s11_max_db`, and wideband `max_inductors: 2`. It acts as the quality floor of every planted cell.

| band type | NF (dB) | S11 max (dB) | S21 (dB) | ripple (dB) | Idd (mA) |
|---|---|---|---|---|---|
| wideband | `nf_max_db` ≤ 4.5 | ≤ -8 | ≥ 8 | ≤ 3 | ≤ 12 |
| narrowband | `nf_db` ≤ 2.5 | ≤ -8 | ≥ 10 | — | ≤ 6 |

Sizing box, process and topology fields are verbatim from bench-v1.2.

### Stages

1. **CAL.** Anchors a1–a5 × every grid point × probe seeds {1, 2}. This builds the *anchor design pool* per band: the winner metrics and stability of every run.

2. **SEARCH** (search only; no templates, no LLM, no hand-written topology). Each candidate is `anchor + edit script` of **2–4 primitive edits**. The primitives are:
   - add R/C/L between two existing nets
   - add NMOS/PMOS (D, G, S from the existing nets; bulk on its rail)
   - delete an element
   - rewire one terminal (not bulk) to another net

   Two composites of 2 primitives each introduce **new internal nets**:
   - *series-insert*: rewire a pin to a new net, then add R/C/L from the new net back to the old one
   - *stack*: rewire a MOS D or S to a new net, then add a MOS channel between the old and new nets, with a gate on any net

   Every candidate then goes through **deterministic repair** (`repair()`):
   - (i) prune passives left dangling
   - (ii) floating-node completion: a MOS whose channel has no DC path rail-to-rail gets a return or feed resistor on the missing side. This is the explicit netlist form of `lna/bias.py` v3 R-SOURCE/R-DRAIN. Gate bias stays with `insert_bias` inside `smoke_run`.
   - (iii) reject incoherent candidates: a dangling MOS pin, no DC path, or a missing port

   After repair come the coherence and verifier-identical pre-screens:
   - device budget 3–16
   - inductor limits
   - round-trip OK
   - `structural_degeneracy` and the spec's own `structural_screen`

   Duplicates are dropped by WL hash, as is anything equal to an anchor or inside **any** anchor's single-edit (F2) space.

   **Guided search is generational and deterministic.** Per grid point and generation, the children are:
   - ⅓ fresh random scripts
   - the rest mutate-then-repair from a size-3 tournament over the top-20 archive of the same stream and band type. The moves are append a group, replace a group, or drop a group.
   - one cross-grid transfer of a feasible sibling-point topology

   Each child is sized at seed 1 under the grid point's probe spec. The score is:
   - **infeasible:** the worst normalized margin, including the wide-µ shortfall (negative)
   - **feasible:** 1 + the *dominance excess* over the calibration anchor pool. The excess is the min over stable anchor designs of the max normalized improvement, minus 0.02. It is positive iff no anchor design already meets the planted spec.

   Bench children whose move class is already capped are not generated ("stop searching a class once capped").

3. **PLANT.**
   - A seed-1 probe-feasible candidate is re-sized at probe seed 2 (see D2).
   - If both runs are stable-feasible, the spec is planted from the **componentwise-worst** of the two winners. Each limit is set to the achieved value relaxed by the cushion δ = 0.02 on the constraint scale (`Spec._scale` = max(|limit|, 1)): L − δ·scale(L) = achieved, rounded outward by 1e-4. So the pre-reg *tightened-2 %* copy sits exactly at the witness's achieved point.
   - Bench: **pre-kill** (logged, never silent) if any recorded anchor design (calibration or F1) or any recorded single edit of the parent (F2) already satisfies the spec. This implements "prefer specs tighter than the parent anchor achieves".

4. **CELL** (bench). The stages run in cost order. Each stage is logged with its full result dicts in `run/results.jsonl` and `cells.jsonl`.
   - **A1:** witness feasible at ≥ 2 of seeds {1, 2, 3}. Seed 3 runs only when seeds 1 and 2 split.
   - **F1:** a1–a5 × seed 1, then × seed 2, at the cell spec. Any feasible run kills the cell. On wideband, a1 and a4 are topology-rejected with 0 evals. The parent anchor's two runs become `evidence.json`.
   - **A2 + A3 (interleaved):** A2 is the tightened-2 % spec at ≥ 1 of {1, 2, 3}; A3 is fresh seeds, ≥ 1 of {4, 5, 6}. Both stop at the first success.
   - **F2:** every single edit of the **shown (parent) anchor** in the E-c space, seed 1 over all edits, then seed 2.
     - Runs go in chunks of 16, with an early kill on the first feasible.
     - Topology- or structure-rejected edits are run through `smoke_run` in-process: 0 evals, the exact verifier dict.
   - **ABL** (labelling, not a filter): drop each edit group in turn and re-size at seed 1. The groups whose removal loses feasibility are *essential*.
     - **Move class** = the highest-priority per-edit label among the essential groups. Priority order: cascode > current-reuse > added-stage > feedback > degeneration > L-match > input-match > tank-load > other.
     - Each label comes from the device's role in the witness netlist: input side, MOS drains/gates/sources (diode bias nets excluded), output side. W2-inert passives are ignored.
   - A cell passing everything is **accepted**.

5. **Selection** (`select_cells`).
   - Cells are taken in acceptance order, at most 1 cell per witness WL hash, with **no class above 25 %** of the selected set, up to 25.
   - Admission to validation prefers under-represented classes and larger dominance excess.
   - A class with 6 accepted cells is capped for search and admission.
   - The bench stops when 25 selectable cells exist, or after 84 h.

6. **TRAIN** (train stream). Spec planting is identical to the bench, with no dominance requirement and no F2.
   - **Witness proof:** feasible at ≥ 1 of seeds {1, 2} at the planted spec.
   - **Difficulty label:**
     - `library-solvable`: a recorded anchor design meets the spec, or some anchor is feasible at seed 1
     - `single-edit-solvable`: a recorded single-edit design from the bench F2 runs meets it
     - `witness-only`: otherwise
   - The quota is 32 tasks per grid point; the target is 300. The training pool stops at the target or at 118 h in total.
   - **Fence:** candidates whose WL or token hash equals an accepted bench witness are dropped at planting. `fence_check.py` re-checks the final directories against every accepted bench witness (token hash, WL hash, netlist body) and every bench spec.

### Compute conduct

- At most **8 worker processes**. The scheduler re-reads the 1-min load before every launch; above 22 it launches only while fewer than **4** are running.
- The scheduler reserves 3 slots for search and 1 for training whenever they have pending work.
- Priority for the remaining slots: cal > validation (A/F1/ABL) > F2 > search > train.
- **Resumable.** `run/results.jsonl` is the append-only cache of every sizing call, keyed by job id = hash(token hash, spec content, seed, budget, profile). A restart replays the deterministic generators through the cache. Event logs are rotated to `run/logs/prev-*`.
- The worker timeout is 1 h.

## Monitoring

- Progress: `kaggle/campaigns/bench-v2/run/progress.json`, rewritten every 30 s. It holds counts per stage, kills by reason, the class histogram, calls per hour, the median call time, and the ETA.
- Human log: `run/sched.log`.
- Candidates: `run/candidates.jsonl`. Planting and verdict events: `run/events.jsonl`. Cell records: `run/cells.jsonl`. Training tasks: `run/train.jsonl`.
- Pid: `run/sched.pid`.
- Stop: `kaggle/campaigns/bench-v2/stop.sh`.
- Resume: `kaggle/campaigns/bench-v2/launch.sh` (the same command as the first launch).
- Partial outputs at any time: `envrun.sh python kaggle/campaigns/bench-v2/bv2.py finalize --mode full`.

## Smoke test (`smoke/`)

**Scale.** `--mode smoke`, clearly separated from the real run:
- 1 bench grid point (nb240-gain) and 1 train point (nb158-gain)
- calibration at seed 1 only
- 3 bench and 2 train generations of 6 and 4 children
- **F2 restricted to the first 12 edits (SMOKE SUBSET)**
- **`smoke_force`**: a kill is recorded as `SMOKE_FORCED_would_kill`, and the cell keeps going so that every stage runs

Outputs: `smoke/run/`, `smoke/editcap-lib-v2/` and `smoke/train-pool-v2/`. Wall time was 31 min for 171 calls at 8 processes; the median call took 75 s at load about 10.

**Attempt 1** (`smoke/run-attempt1/`, with plain seed-1 planting) exposed the razor-edge problem behind D2. The planted witness failed its own A1:
- seed 1 was spec-feasible but wide-unstable
- seed 2 failed outright

**Attempt 2** (the final code):
- **Search.** 18 bench and 8 train candidates were sized. 7 were probe-feasible at seed 1. The seed-2 confirmation failed 4 times.
- **Planting.** 3 bench cells were planted.
  - The cells were added-stage ×2 and cascode ×1. The witnesses reached S21 24.7 dB and 34.6 dB at NF 1.36 and 2.54 dB.
  - 1 further candidate was pre-killed because cell 001's F1 a1 design already satisfied it.
- **Cell 001 went through every stage.**
  - A1: 2/2 feasible.
  - F1: **a1 solves it at both seeds**, so this is a correct library kill. It was forced onward because this is a smoke run.
  - A2: tightened, seed 1 feasible. A3: fresh seed 4 feasible.
  - F2: the 12-edit subset × 2 seeds, 0 feasible.
  - ABL: both edit groups essential, label added-stage.
  - write-out and finalize.
- **Evidence.** The shown anchor a4 was in-band compliant but wide-unstable (µ_wide −0.996). The wide-µ row was added to the evidence after this.
- **Training.** 2 tasks, both labelled `library-solvable`.
- **Fence check:** rc 0, 0 violations.

**Checks** (`smoke_checks.py` → `smoke/smoke_checks.json`, **all pass**):
- **Profile and flags.** All 172 rows carry `verifier.profile = rl-v1`, the exact flag set, no env overrides, and conforming rl-v1 specs.
- **Determinism.** 4 recorded calls (2 feasible, 2 infeasible) re-run from scratch are byte-identical, excluding wall-clock time.
- **Known-unstable rejected:**
  - (a) The R4 gate-rejected wideband template winner: its spec was feasible, µ_wide = 0.347, and `wide_stability` returns not-ok.
  - (b) E-c `add R VIN1-VOUT1`: feasible under the lib spec, **infeasible under rl-v1** (µ_wide 0.93).
  - (c) 9 smoke rows were spec-feasible but wide-unstable. None was marked feasible or planted.
- **Resume replay.** Relaunching on the same run dir replayed through the cache in about 1 min and made **1** new call out of 172. The candidates and training tasks were reproduced identically, as sets.
  - The cell bookkeeping differed. The pre-kill pool also holds other cells' F1 designs, which arrive in wall-clock order, so on replay one candidate that had been pre-killed was planted instead.
  - This is the one intended source of timing dependence. It can only kill cells that are provably library-solvable, so it cannot accept one wrongly. Every individual sizing call is deterministic and cached.

## DEVIATIONS / interpretations

- **D1: wideband shown anchors are a2, a3 and a5 only.**
  - a1 and a4 have 3 inductors, so every wideband rl-v1 spec (`max_inductors` 2) topology-rejects them with 0 evals.
  - They can therefore not be a shown anchor with sized failure evidence.
  - They are still run in wideband F1, as instant rejects, and remain parents for narrowband.
- **D2: planting confirmation (worst of two probe seeds).**
  - In smoke attempt 1 (`smoke/run-attempt1/`), the witness planted from a single seed-1 winner was not re-found at its own planted spec: seed 1 was spec-feasible but wide-unstable, and seed 2 failed outright. The cell died at A1.
  - Planting now requires probe seeds 1 **and** 2 to be stable-feasible, and uses the componentwise-worst of the two winners as the "achieved metrics". Both real designs satisfy the spec.
  - This keeps the pre-reg's cushion and acceptance rules unchanged and costs 1 call per feasible candidate.
- **D3: the cushion is measured on the constraint scale.** The planted limit L satisfies L − δ·max(|L|, 1) = achieved, so the pre-reg tightened copy equals the achieved point.
  - A naive "achieved + 2 % of |achieved|" would put the tightened limit *beyond* the witness's own point: nf 3.21 → 3.274 → 3.209.
- **D4: the grid is band × objective flavor.** The pre-reg declares bands only. "Disjoint spec grid points" is implemented as disjoint (band, flavor) points between the bench and training streams.
- **D5: pre-kills.** A planted spec that a *recorded* anchor design (calibration, or another cell's F1) or a recorded single edit of the parent already satisfies is killed without running F1/F2. This is stricter than the pre-reg, because the cell is provably library- or single-edit-solvable. Every pre-kill is logged in `events.jsonl`.
- **D6: training difficulty uses seed 1 only for F1** (`library-solvable@s1`). Single-edit solvability is known only from recorded bench F2 designs ("where cheaply known"), so `witness-only` means "not shown solvable by those".
- **D7: the move-class labels are an automatic heuristic**, defined in the Stages section above. The search-time label (used for capping during search) is replaced at acceptance by the ablation label; both are recorded.

# bench-v2 generation campaign

Pre-registered in `kaggle/PREREG-BENCH-V2.md` (frozen 2026-09-29, commit `e5bfd0755`).
The user approved **full size**: 20–25 bench cells plus about 300 training tasks, on local CPU.
Verifier: `bench_anchor_prep.smoke_run(tokens, spec, seed, 2500, "bptm45", profile="rl-v1")` on rl-v1-form specs (`kaggle/VERIFIER-RL-V1.md`).
Every result row carries the git era stamp (HEAD plus the md5 of `bench_anchor_prep.py` and `bv2.py`) and `result["verifier"]`.

Status: **RUNNING** (full run launched 2026-09-29). See *Monitoring* below. Results sections are filled in when the run finalizes.

## Files

| file | role |
|---|---|
| `bv2.py` | The whole pipeline: scheduler, search, repair, planting, cell and training stages, finalize, worker. |
| `fence_check.py` | Bench/training fence check. Finalize runs it; it can also be run standalone. |
| `smoke_checks.py` | Post-smoke checks: flags and profile, determinism, known-unstable rejection. |
| `launch.sh` / `stop.sh` / `envrun.sh` | Detached launch (resumable), graceful stop, and the environment (an inline copy of crenv.sh; `TMPDIR=/tmp/cr-bv2`). |
| `run/` | The full run. Not committed except `progress.json`, `README`-level summaries and specs. |
| `smoke/` | The smoke run and its checks (committed). |

Outputs at finalize:
- `kaggle/editcap-lib-v2/<cell>/{spec.yaml, anchor.net, anchor.tokens.json, evidence.json, cell.json, witness/}` plus `INDEX.json`. `witness/` is **EVAL-ONLY**.
- `kaggle/train-pool-v2/<task>/...` plus `INDEX.json`, with difficulty labels.

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

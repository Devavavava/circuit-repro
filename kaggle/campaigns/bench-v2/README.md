# bench-v2 generation campaign

Pre-registered in `kaggle/PREREG-BENCH-V2.md` (frozen 2026-09-29, commit `e5bfd0755`).
The user approved **full size**: 20–25 bench cells plus about 300 training tasks, on local CPU.
Verifier: `bench_anchor_prep.smoke_run(tokens, spec, seed, 2500, "bptm45", profile="rl-v1")` on rl-v1-form specs (`kaggle/VERIFIER-RL-V1.md`).
Every result row carries the git era stamp (HEAD plus the md5 of `bench_anchor_prep.py` and `bv2.py`) and `result["verifier"]`.

Status: **AMENDMENT 3 end-of-run re-check RUNNING** (verifier **rl-v1.2**, `amend3/`). The rl-v1.1 run FINISHED 2026-10-03 19:26 IST (12 accepted selectable cells, 3 in the quota-compliant selection; 280 ok training tasks). History:
- launched 2026-09-29
- stopped at 26.8 h, then resumed under AMENDMENT 1 on 2026-09-30
- stopped 2026-10-01 18:43, then resumed under AMENDMENT 2 the same evening
- **crashed 2026-10-02 14:41 IST** on a full shared disk (ENOSPC, filled by other users' jobs). It was made disk-robust, crash-resumed from its own amendment-2 state, and relaunched at 19:16 IST (pid 2394952). See A2-6 and D32–D36.
- finished 2026-10-03 19:26 IST (bench end); finalized 19:42
- **AMENDMENT 3** (2026-10-04): verifier rl-v1.2 (ideal port coupling) and a detached re-check of the 12 accepted cells and the training pool. See "AMENDMENT 3" and D37–D45.

Bench end: **2026-10-03 19:26 IST**. This is the amendment-2 end (2026-10-03 14:51) plus the 4 h 35 min downtime, 14:41:15 → 19:16:24 (D35). The total budget ends **2026-10-04 13:31 IST**.

**Read the "AMENDMENT 3", "AMENDMENT 2" and then the "AMENDMENT 1" sections first.** Where they differ from the design sections below, the later amendment wins. Results sections are filled in when the run finalizes.

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
| `smoke_checks_a2.py` | AMENDMENT-2 smoke checks: rl-v1.1 profile on every row, restore actions, re-validation, cache-bridge exactness, generation pre-filter, training re-check, fence with a negative control, budget clock. |
| `port-dc-guard/` | rl-v1.1 port-DC requirement tests (`test_port_dc.py`, `results.json`, README). |
| `run/amendment-1-record/` | Frozen copy of the amendment-1 record at the 2026-10-01 18:43 stop (`bv2.py amend2-snapshot`, `MANIFEST.json` has md5s). AMENDMENT 2 restores from it. |
| `amend3/` | AMENDMENT 3: `a3run.py` (re-check driver), `launch.sh`/`stop.sh`, `test_rl_v12.py` + `test_rl_v12.json` (rl-v1.2 tests), `summary.json` (written at finalize), `run/` (progress.json; raw rows not committed), `smoke/` and `smoke-force/` (smoke summaries). |

Outputs at finalize:
- `kaggle/editcap-lib-v2/<cell>/{spec.yaml, anchor.net, anchor.tokens.json, evidence.json, cell.json, witness/}` plus `INDEX.json`. `witness/` is **EVAL-ONLY**.
- `kaggle/train-pool-v2/<task>/...` plus `INDEX.json`, with difficulty labels.

## AMENDMENT 3 (2026-10-04) — end-of-run re-check under rl-v1.2

Pre-reg: `kaggle/PREREG-BENCH-V2.md` § "AMENDMENT 3" (commit `0d03751cc`). User approval: 2026-10-04 (*"1 yes - 2 yes"*), and again on 2026-10-04 for this implementation and a detached re-check.

**Why.** The verifier exploiter EX (`kaggle/campaigns/adversarial-v0/EX/`, `caaf1d5af`) found class **C-cp1**: 247 designs that pass rl-v1.1 build the testbench's fixed 10 pF port coupling caps into their matching network. The run had already **finished** under rl-v1.1 (2026-10-03 19:26), so AMENDMENT 3 is an end-of-run re-check. No new search or planting happens.

### A3-1 Verifier rl-v1.2 / rl-v1.2-rl (`bench_anchor_prep.py`; `kaggle/VERIFIER-RL-V1.md` § rl-v1.2; tests in `amend3/test_rl_v12.py` → `amend3/test_rl_v12.json`)
- **`rl-v1.2` = `rl-v1.1` + `VERIFY_CP_IDEAL`.** Each harness port block gets a 1 µF cap in parallel, written into the prepared body once. Every deck therefore sees ideal coupling: sizing sp and noise, in-loop and gate wide stability, the inert count, and the port-DC op decks.
- **`rl-v1.2-rl` = `rl-v1.2` + `VERIFY_KICK`.** This adds a 50 Ω, 1 µA kick transient on the final winner (EX class C-osc50). It is used for the RL reward only, **not** for bench-v2.
- **Tests:**
  - **Byte-identity.** rl-v1.1 ×3, rl-v1 ×1 and no-profile ×1 are byte-identical to the recorded results.
  - **Same as EX's G-CP1io.** rl-v1.2 gives EX's validated G-CP1io re-size bit for bit (6/6 D9 cases).
  - **C-cp1.** 11/12 C-cp1 rl-v1.1 winners fail the rl-v1.2 bench without a re-size; 12/12 are feasible again after an rl-v1.2 re-size.
  - **C-osc50.** All 6 pass rl-v1.2 and fail the kick.
  - **Clean designs.** 3/3 pass both.
  - **Anchors.** a2's rl-v1.1 winners still pass. **a1 becomes feasible at nb090 under rl-v1.2.**
- **Cost.**
  - `VERIFY_CP_IDEAL` adds no sims; sizing time is within ±2 % of rl-v1.1.
  - The kick takes 8.3 s median per feasible winner.
- `lna/` is unchanged.

### A3-2 Re-check driver (`amend3/a3run.py`, `amend3/launch.sh`, `amend3/stop.sh`)
A focused driver on bv2's infrastructure:
- **Reused from bv2:** the `bv2.py worker` subprocess, `job_id`, `select_cells`, `make_evidence`, the F2 space (`Pipeline.f2space_build`, same code), the fence check, and the D32 disk robustness (`SafeAppender`, `atomic_write`, `DISK`, a launch pause on a full disk or < 5 GB free, and re-queuing of workers that leave no result).
- **Throttle:** ≤ 8 workers, 4 when load1 > 22.
- **Cache:** every call is cached in `amend3/run/results.jsonl` on `job_id(..., "rl-v1.2")`. A restart replays the deterministic stage generators through the cache.

**Inputs (read-only).**
- **Cells.** The 12 accepted, selectable cells of `run/cells.jsonl` (amendment-1 re-accepted plus amendment-2), with their archived witness `run/cells/<cell>/witness/witness.tokens.json` (token hash = the cell's `tok`) and their planted and tightened specs, **unchanged**.
- **Training.** The 280 `ok` training tasks of `run/train.jsonl`. Witness tokens come from the candidate records; the token hash is checked.

**Bench, per cell.** Stages run in this order, with an early kill on the first failure:
1. **A1:** seeds 1 and 2 (+3 if they split), ≥ 2 feasible.
2. **A2:** tightened-2 % spec, ≥ 1 of {1, 2, 3}.
3. **A3:** ≥ 1 of {4, 5, 6}.
4. **F1:** a1–a5 × seed 1, then seed 2. Any feasible run kills the cell.
5. **F2:** every round-trip-valid single edit of the shown anchor (a1 144, a2 178, a3 67 edits) × seed 1, then seed 2. Chunks of 16, kill on the first feasible.

Topology, structure and port-DC pre-filter rejects run in-process with 0 evals, as in bv2. A failing cell is tagged **`amend3-cp1`**: it stays on record and is not selectable.

**Training, per task.**
- **Witness:** seed 1, then seed 2 if needed. If both fail, one more re-size at seed 3 (D39). Still failing → tagged `amend3-cp1`.
- **T-F1:** a1–a5 × seed 1 at the task spec for every re-proved task (D40).

**Final** (automatic when the queue is empty; `a3run.py final` re-runs only this step from the cache):
- **Labels.** Re-derived from rl-v1.2 rows only (D40).
- **Selection.** Over the passing cells, with `bv2.select_cells`: class rule (b) primary atom ≤ 25 %, parent ≤ 40 %, narrowband ≥ 25 %, target 25. A shortfall against 20 is reported, not relaxed.
- **Library.** `kaggle/editcap-lib-v2/` is rewritten with the selected cells (witnesses are EVAL-ONLY). Each cell gets rl-v1.2 `witness/results.json` and `evidence.json`; the rl-v1.1 versions are kept as `*_rl_v1_1.json` (D42). The `INDEX.json` records `verifier: rl-v1.2` and every cell's re-check verdict.
- **Training pool.** `kaggle/train-pool-v2/` is rewritten: tagged tasks are left out, labels are updated, and evidence comes from the rl-v1.2 parent T-F1.
- **Fence check:** `amend3/run/fence_check.txt`.
- **Summary:** `amend3/summary.json` (per-cell stage outcomes, selection, training status, labels before and after, compute).

**Monitoring.**
- `amend3/run/progress.json` is rewritten every 30 s. It holds per-cell stage, F2 progress, training status, calls, CPU, disk state, and an ETA.
- The ETA is an **upper bound**: it assumes every remaining stage passes.
- Log: `amend3/run/sched.log`. Pid: `amend3/run/sched.pid`.
- Stop: `amend3/stop.sh`. Resume: `amend3/launch.sh` (the same command).

### A3-3 Smoke (`amend3/smoke/`, `amend3/smoke-force/`; summaries committed)
**`launch.sh smoke`:** 1 cell (`v2a-nb090-gain-007`), F2 cut to the first 8 edits (SMOKE SUBSET), 2 training tasks; 23 sized calls, 5.5 min wall.
- **The cell:**
  - It passes A1 (2/2), A2 (seed 1) and A3 (seed 4) under rl-v1.2.
  - It is then **killed at F1: anchor a1 is feasible at seed 2 under rl-v1.2** (it was infeasible under rl-v1.1). Tagged `amend3-cp1`.
  - This matches the T4 finding: the 10 pF fixture had been *hurting* a1 at 0.9 GHz.
- **Training:**
  - Both tasks are re-proved: one at seed 1, one at seed 2.
  - t2-wb1020-gain-0001 is relabelled `witness-only` → `library-solvable`, because a2 is feasible at seed 1 under rl-v1.2.
- **Final:** selection empty (0/1 passing); training pool written (2 tasks); fence check rc 0.

**`launch.sh smoke-force`:** the same cell with `--smoke-force` (SMOKE ONLY: a kill is recorded as `SMOKE_FORCED_would_kill` and the stages continue).
- **What ran:**
  - A1–F1 came from the smoke's rows (27 exact-key cache hits).
  - F2 subset: 12 sized + 4 in-process pre-rejects, 0 feasible.
  - Library write-out: 1 cell, with rl-v1.2 `results.json`/`evidence.json` and the rl-v1.1 versions kept.
  - Fence check rc 0.
- **Stop/resume test.** SIGTERM in the middle of F2, with 6 workers running:
  - all workers were killed, and none of their rows was cached
  - `progress.status = stopped`
  - the relaunch replayed 29 cached rows and re-ran exactly the 6 killed calls plus the seed-2 chunk (12 new)

### A3-4 Full re-check (launched 2026-10-04 13:48 IST, pid 2654595)
Run dir `amend3/run/`. It reuses the smoke's rl-v1.2 rows on an exact key (`--extra-cache amend3/smoke/results.jsonl`).
- **Size at launch:** 12 cells and 280 training tasks. The ETA upper bound is 4506 calls ≈ 15.7 h at 8 processes, i.e. 2026-10-05 ≈ 05:30 IST if no cell is killed early. Early F1 kills shorten it.
- **Results** go to `amend3/summary.json` and the library INDEX at finalize. They are reported in the next commit.

### Deviations / interpretations (AMENDMENT 3)
- **D37: G-CP1 is a parallel 1 µF, applied kaggle-side.** Each harness block becomes 10 pF ∥ 1 µF = 1.00001 µF, written into the prepared body right after `SZ.prepared_body` (`cp_ideal_body`).
  - The pre-reg says "1 µF ideal"; the 10 pF in parallel changes it by 10 ppm.
  - Doing it this way keeps the port-DC anchor line, and the body is text-identical to EX's validated G-CP1io method (T0/T2).
  - `lna/` is untouched, so no shared-core commit was needed.
- **D38: the stage order is A1 → A2 → A3 → F1 → F2, sequential.** bv2 ran A1 → F1 → (A2 ∥ A3) → F2.
  - The pass/fail criteria are unchanged.
  - The sequential order spends nothing on A3 when A2 fails.
  - The re-check order was given with the user-approved instructions.
- **D39: training "re-sized once" means one extra fresh seed (3).** The seed-1 and seed-2 witness runs under rl-v1.2 are already re-sizes from scratch, so the single re-size attempt the pre-reg allows for failures is a third seed. A task is kept if any of {1, 2, 3} is feasible; the seed is recorded in `witness_seed`.
- **D40: training labels come from rl-v1.2 evidence only, and T-F1 runs for every re-proved task.**
  - Recorded rl-v1 and rl-v1.1 designs were measured through the 10 pF fixture, so they are not evidence under rl-v1.2. The smoke shows that anchors can gain as well as lose.
  - **`library-solvable`:** the task's own T-F1 (a1–a5 × seed 1, run for every task so the result does not depend on order) is feasible, **or** some rl-v1.2 anchor design (bench F1 or any T-F1, same band) meets the limits with µ ≥ 1, wide-stable and port-DC OK.
  - **`single-edit-solvable`:** an rl-v1.2 bench F2 design (same band) meets the limits. This evidence set is much smaller than the rl-v1.1 one, so the label is narrower than before ("where cheaply known").
  - **`witness-only`:** otherwise.
- **D41: classes are not re-derived.**
  - A cell keeps its rl-v1.1 ABL core signature and primary atom; the pre-reg's AMENDMENT 3 item 2 lists A1–A3, F1 and F2 only.
  - The re-checked witness is the cell's archived witness, i.e. the stripped core where amendment 1/2 stripped it.
  - `witness/original/` keeps its rl-v1.1 record.
- **D42: library layout.**
  - Each selected cell's rl-v1.1 directory is copied, then `witness/results.json` and `evidence.json` are replaced by their rl-v1.2 versions. Evidence = the shown anchor's rl-v1.2 F1 runs.
  - The rl-v1.1 files are kept as `witness/results_rl_v1_1.json` and `evidence_rl_v1_1.json`.
  - `cell.json` gains an `amendment3` block.
  - `kaggle/editcap-lib-v2/` and `kaggle/train-pool-v2/` are rewritten in full; earlier cell and task directories not in the new selection are removed.
- **D43: bench and training share the worker pool.** Bench jobs have priority (A > F1 > F2 > training witness > T-F1), and training fills idle slots. Outcomes do not depend on this order (D40).
- **D44: no ABL, no new cells, no validation of the 88 planted-but-unvalidated cells** (pre-reg AMENDMENT 3 item 5).
- **D45: the quotas can empty the selection.** With the narrowband quota (≥ ⌈0.25·n⌉), every non-empty selection needs at least one narrowband cell. If all 3 nb090 cells fail F1 (as v2a-nb090-gain-007 did in the smoke: a1 solves it under rl-v1.2), the quota-compliant selection is **empty**, however many wideband cells pass. Per the pre-reg this is reported as a shortfall, not relaxed. `selection_report` also gives the selection without the narrowband quota, for the record.

## AMENDMENT 2 (2026-10-01) — what changed in the pipeline

Pre-reg: `kaggle/PREREG-BENCH-V2.md` § "AMENDMENT 2" (commit `1a0413fb9`). User approval 2026-10-01: *"go ahead with whatever you suggest"*.

**Why.** At 23.8 h after amendment 1, 9 of 11 accepted cells shared the core atom `add:L:IN-G`. By the 18:43 stop this was 16 of 18. The motif audit (`motif-audit/`, `e189abbbb`) found that these designs:
- size their own input DC block to nothing
- rely on the testbench port's 10 pF DC block
- collapse with any DC-grounded source

That is a missing interface requirement, so it was added to the verifier.

### A2-1 Verifier rl-v1.1 (`bench_anchor_prep.py`; `kaggle/VERIFIER-RL-V1.md` § rl-v1.1; tests in `port-dc-guard/`)
`rl-v1.1` is `rl-v1` plus `VERIFY_PORT_DC`:
- **Structural pre-filter** (0 sims, before sizing): reject if VIN1's DC group holds a MOS terminal or the positive supply. A DC path to VSS alone is allowed.
- **Behavioural check** (the authority): run on the final winner, comparing the DC op with an extra 50 Ω DC path to ground at VIN1. Pass iff every |ΔV_G| < 10 mV and |ΔIdd| < 1 %. Failure is `port_dc_fail`.

rl-v1 and no-profile results are byte-identical to before (`port-dc-guard/` T8). Bench and training verification both use rl-v1.1. Job cache keys include the profile, so rl-v1.1 rows never collide with rl-v1 rows.

### A2-2 Resume by restore, not replay (`restore_amend2`, `bv2.py amend2-snapshot`)
The amendment-1 record was frozen at the stop (`run/amendment-1-record/`). The resume **restores** state from it rather than replaying the generators, because a replay re-derives steering from wall-clock order (D13) and would redo most of the 24 h of search (D21). Restoring then re-evaluates everything under rl-v1.1:
- **Pools.** These are the anchor (cal/F1) and single-edit (F2) designs used for pre-kills, difficulty labels and dominance. A design counts as a solver only if it meets the port-DC requirement (D23).
- **Search.**
  - All 2442 bench and 864 train candidates and their seen WLs are restored.
  - Archive members that fail the pre-filter are dropped: 1415 bench and 267 train. Kept: 1027 and 597.
  - Search continues at generation 37 (bench) and 41 (train) in an `amendment-2` RNG namespace.
  - The free pre-filter is applied at candidate generation, with reject reason `port_dc_prefilter`.
- **Cells (amendment-1 record, 152 planted).**
  - **Tagged `amend2-port-dc`** (pre-filter fail): 36 cells. 16 of the 18 accepted, the 1 queued/validating cell (nb158-noise-149), 9 skipped_dupwl and 10 skipped_parent_cap. They stay on record and fenced, and are not selectable.
  - **Re-validated:** the 2 accepted cells that pass the pre-filter (nb090-gain-007, wb1020-noise-003). They re-run every stage under rl-v1.1.
  - **Re-queued:** 2 skipped_dupwl cells that pass the pre-filter. Admission re-applies the caps.
  - **Revived:** 7 cells killed by F2 where the witness passes the pre-filter and every solving single edit fails it (D24).
  - **Re-planted:** 3 of the 4 void F2 pre-kills (D24); the fourth was pre-killed again.
- **Cache bridge** (`try_derive` → `bench_anchor_prep.derive_port_dc`). A stage run whose rl-v1 twin is cached is answered exactly without re-sizing whenever port-DC cannot change it: a pre-sizing reject, or an infeasible winner. A feasible twin is re-sized; the run is deterministic, so this gives the same winner, now checked (D22).
- **Training (320 tasks).** Of the 290 `ok` tasks, 101 are tagged `amend2-port-dc` (out of the pool): 74 library-solvable, 16 witness-only and 11 single-edit-solvable. The other 189 have their witness re-checked under rl-v1.1 and their label re-checked (D27). The 30 unproved tasks stay unproved. Freed quota slots are refilled by the training search (D29).
- **Fence.** Every amendment-1 planted cell (any status, both witnesses) and every amendment-2 planted cell is fenced, including `witness_original_amend1`. `fence_check.py` and `finalize` are extended to match.

### A2-3 Selection, budget, records
- **Class rule (b) `primary_atom`** is active for the final selection (`class_rule`, D28). Selectable cells are amendment-1 cells re-accepted under rl-v1.1 plus amendment-2 cells (`v2b-…`, `era_tag: amendment-2`). Pre-amendment cells and tagged cells are never selectable.
- **Bench end UNCHANGED:** `start.json` `t_amend1` + 72 h = **2026-10-03 14:51:17 IST**. `t_amend2` is recorded only. `progress.amendment2.bench_end_unchanged` shows the end time. The total budget is unchanged too (t_start + 118 h = 2026-10-04 08:56).
- **Records.** New rows carry `profile: rl-v1.1` and `phase: amendment-2`. Derived rows carry `derived_from` (the rl-v1 twin's jid). `progress.json` gains `amendment2.port_dc`, which holds:
  - pre-filter rejects at generation
  - behavioural checks and their failures
  - derived and re-sized rows
  - cell and training actions/outcomes, and tagged counts
  - pool designs that pass or fail the requirement
  - archive drops

### A2-4 Smoke (`smoke/run-amend2/`, `--mode smoke-a2`, checks in `smoke/smoke_checks_a2.json`)
**Setup.**
- Run with `launch.sh smoke-a2`, after `bv2.py amend2-snapshot --mode full`.
- It restores a subset of the frozen full-run record, read-only:
  - 5 cells, each with a different action: re-validate nb090-gain-007; tag wb0530-power-000 (an accepted L-IN-G cell); tag nb158-noise-149 (the cell that was validating at the stop); revive nb090-gain-038; re-queue wb0824-gain-033 (skipped_dupwl).
  - 1 void pre-kill to re-plant (B0010-nb090-gain-2).
  - 3 training tasks.
- It reads the full run's cache read-only: exact-key hits plus the rl-v1 → rl-v1.1 bridge.
- One new generation each: bench (nb090-gain, wb1020-noise, 4 children per point) and train (nb158-gain, 3 children).
- F2 is cut to the first 12 edits (SMOKE SUBSET). `smoke_force` is off, so kills are real.
- Totals: 240 rows (146 sized, 57 derived, 37 in-process pre-rejects), 29 min wall clock, 8 processes. The pipeline then finalized into `smoke/amend2-*`.

**Checks** (`smoke_checks_a2.py` → `smoke/smoke_checks_a2.json`; all pass):
1. **Profile.** Every row is `profile: rl-v1.1`, `phase: amendment-2`, with `verifier.flags` = the rl-v1 flags + `VERIFY_PORT_DC=1`.
2. **Restore.** All 5 actions came out as intended, and both tagged cells are `amend2-port-dc` and not selectable.
   - The revived nb090-gain-038 was **accepted** under rl-v1.1, though only against the F2 subset.
   - The re-queued wb0824-gain-033 was accepted; its duplicate is not restored in the smoke.
   - The re-planted void pre-kill became `v2b-nb090-gain-005`. It was cancelled when the smoke's bench target of 3 was reached.
3. **Re-validation of nb090-gain-007.** It was **re-accepted**. All 39 stage runs are rl-v1.1, and all 4 feasible witness winners carry a behavioural `port_dc` that passes (ΔV_G = 0, ΔIdd = 0). Core `rw:C:p:D>X + ser:L:C.p:IN`, primary atom `ser:L:C.p:IN`, both unchanged.
4. **Bridge.** A derived A1 row re-run fresh under rl-v1.1 is identical, apart from `wide_secs` (D30).
5. **Generation.** 11 new candidates, all passing the pre-filter. The pre-filter rejected 2 bench and 6 train candidates at generation.
6. **Training.**
   - The pre-filter-failing task is tagged.
   - Both passing tasks were re-proved at seed 1 by a re-size, with the behavioural check passing.
   - t2-nb090-noise-0012 was relabelled single-edit → witness-only. This is a **smoke artefact**: the smoke loads no pre-amendment pools, and its solving design was a pre-amendment F2 row. The full run loads those pools.
7. **Fence.** The finalize fence check gives rc 0. Negative control: a training dir holding a copy of the *tagged* cell wb0530-power-000 is flagged on all 4 counts (token, WL, spec, body), rc 1.
8. **Budget.** The full run's bench end is `t_amend1` + 72 h = 2026-10-03 14:51:17 IST, unchanged.

The smoke INDEX (`smoke/amend2-editcap-lib-v2/INDEX.json`) shows `verifier: rl-v1.1` and `class_rule_active: primary_atom`, with 3 cells selected.

### A2-5 Full-run resume (2026-10-01 19:50 IST, pid 4111916)
**Restore:** 152 amendment-1 cells, 320 training tasks, next generation 37 (bench) and 41 (train). At +11 min:
- 47 new sizing calls, 406 derived rows, 52 in-process pre-filter rejects; 8 processes at load 14.
- **Both** re-validated accepted cells (nb090-gain-007, wb1020-noise-003) were **re-accepted** under rl-v1.1. That gives 2 accepted / 2 selectable.
- The 2 re-queued skipped_dupwl cells were skipped again: they duplicate a re-accepted witness.
- 7 revived and 3 re-planted cells are validating or queued.
- 187 training re-checks are running (2 were already answered by the smoke's rows).

### Deviations / interpretations (AMENDMENT 2)
- **D21: resume by restore, not replay.** Restoring the frozen amendment-1 record replaces the deterministic generator replay for this resume. Every restored decision is logged (`amend2_restore` event, `amend2` field on each cell and task).
  - A later restart of the amendment-2 run restores from the same record again. Already-run rl-v1.1 calls are cache hits, but new search generations can diverge as in D13. That costs re-sizing, never correctness.
- **D22: cache bridge.** An rl-v1.1 job whose rl-v1 twin is cached and cannot be changed by the port-DC requirement is *derived*, not re-sized. These are pre-sizing rejects (computed by the verifier in-process) and infeasible winners (the rl-v1 dict plus the port-DC keys plus the rl-v1.1 verifier record). Derived equals a fresh rl-v1.1 run byte for byte (3/3 in `port-dc-guard/` T7), apart from the one wall-clock field `stab_inloop.wide_secs` (D30). Feasible twins are always re-sized and checked.
- **D23: solvers in the pools.** A recorded design pre-kills a spec, labels a training task or enters dominance scoring only if it meets the port-DC requirement.
  - An rl-v1.1 row uses its own behavioural verdict, or its pre-filter verdict if its winner was infeasible.
  - A recorded rl-v1 row uses the pre-filter of its topology. For a pre-filter-passing topology the behavioural check is a provable no-op (no MOS terminal or positive rail in VIN1's DC group, so a DC path to ground draws no current). It measured ΔV = ΔIdd = 0 in every pass case.
  - Calibration is not re-run: all 5 anchors pass both checks (T3).
  - 715 of 7248 pool designs fail.
- **D24: void kills and pre-kills are re-examined.** The pre-reg lists accepted, queued and validating cells. On top of that:
  - A cell **killed by F2** is revived if its witness passes the pre-filter and *every* recorded solving single edit fails it (e.g. `add L VIN1-n5`, `add L VDD-VIN1`). Under rl-v1.1 those edits are rejected, so the F2 null evidence is void. The cell re-runs every stage under rl-v1.1, and F2 runs to completion. 7 cells; 8 F2 kills stand.
  - A bench candidate **pre-killed** only by such a single-edit design is planted from its recorded seed-1 and seed-2 probe winners. `plant_bench` re-applies the filtered pre-kill pools, floors and fence. 4 candidates: 3 planted, 1 pre-killed again by a valid design; 5 pre-kills stand.
  - F1 and A1–A3 kills stand: the anchors pass, and rl-v1.1 is stricter, so those kills are monotone.
- **D25: harness bias-source nets count as positive supply** in the pre-filter. These are VB\*, VCM\* and VREF\*, which `to_spice` drives from positive dc sources. No bench-v2 anchor has such a net, so this has no effect here.
- **D26: archive scores carry over.** Restored archive members that pass the pre-filter keep their rl-v1 search scores without a re-size. The scores only steer mutation parents. Members that fail are dropped.
- **D27: training re-check.**
  - The witness is re-proved at seed 1, then at seed 2 only if seed 1 fails. The pre-reg requires ≥ 1 of {1, 2}.
  - `library-solvable` labels stand, since anchors meet the requirement.
  - `single-edit-solvable` and `witness-only` labels are re-derived from the port-DC-filtered pools, with no new sizing. A relabel is recorded in `amend2.label_before/after`.
  - New tasks follow the original protocol under rl-v1.1.
- **D28: class rule (b) `primary_atom` is active** (AMENDMENT 2 item 2). As in D17, the search-time build caps stay on whole signatures, with the soft atom penalty on. Rule (a) and the atom prevalence are still reported.
- **D29: freed training slots are refilled.** A task tagged `amend2-port-dc` no longer counts against its grid point's quota of 32, so the training search resumes in a new RNG namespace to refill towards 300 under rl-v1.1. The 118 h total budget is unchanged.
- **D30: the byte-identity convention excludes `stab_inloop.wide_secs`.** It is wall-clock seconds, the same exclusion as `smoke_checks.py`. A derived row keeps its twin's value.
- **D31: re-validated cells keep their amendment-1 witness record.** A re-validated or revived cell gets a fresh rl-v1.1 validation of its current witness, which is the stripped core when amendment 1 stripped it.
  - Fields moved: the amendment-1 stages, core and evidence move to `amend1_*`, and `witness_original` moves to `witness_original_amend1` (fenced).
  - If the new ABL strips again, the usual `witness/` + `witness/original/` layout applies.

### A2-6 Crash on a full disk and crash-resume (2026-10-02)
**Incident.** At 2026-10-02 ~14:41 IST the scheduler (pid 4111916) died with `OSError: [Errno 28] No space left on device` in `atomic_write` (writing `progress.json`). The shared NFS home (853 G) had been filled for a short time by other users' EDA jobs; this campaign uses about 12 GB. 85 GB were free again a few hours later. The last heartbeat was `progress.json` ts **2026-10-02T14:41:15**. At that moment:
- 4 accepted cells (2 selectable)
- 295 planted cells, 8 of them validating in F2, 73 queued
- 421 training tasks (280 ok), and the training search had finished at gen 51
- the bench search was in generation 55

The 8 jobs in flight (5 F2, 3 search) could not write their results: `jobs/` held 0-byte `*.out.json.*.tmp` files. `results.jsonl` has **0 error rows**, so nothing wrong was cached. Every record file parses line by line.

**What a plain restart would have done (confirmed in the code).** `Pipeline.__init__` rotates `candidates/events/cells/train.jsonl` and `sched.log` into `logs/prev-*`. `run()` then calls `restore_amend2()`, which rebuilds everything from the frozen amendment-1 record, so all amendment-2 state would have been dropped from the live run:
- the 143 amendment-2 plantings, including 2 accepted cells
- the 101 new training tasks
- 19 bench and 10 training search generations: it would have restarted at generation 37/41, with steering re-derived from wall-clock order (D13)
- the rl-v1.1 F1/F2 pool designs

Only the sizing cache would have survived, and re-planting would have given different cell names.

**Fix and test.** D32–D36 below.

**Resume test.** The test ran on a copy of `run/` at `/tmp/cr-bv2-resumetest/run` (`--run-dir`, `--max-procs 4`). The copy was deleted afterwards.
1. **`--dry-restore`** (nothing launched or written) reported:
   - 4 accepted (2 selectable)
   - 295 cells: 73 queued, plus **8 to re-admit**. These are exactly the 8 cells that were validating in F2 at the crash.
   - 421 training tasks (280 ok), and no training re-check in flight
   - next generation bench 56 / train 51 (last started 55 / 50); archive 2215 / 825
   - 5 training confirmations without an outcome. They turned out to be quota-skipped plantings, which are now logged as `train_plant_skipped`.
   - downtime 14:41:15 → resume
2. **Real resume, 18 min.** An ENOSPC fault window was injected at +300–420 s, for both the scheduler and the workers, and a low-disk window at +600–700 s.
   - The resume continued from the state: same 4 accepted cells, the 8 re-admitted cells back in F2, new jobs at bench gen 56, and the training search exhausted at gen 51 as before.
   - There was no re-tagging and no restore churn.
   - The scheduler did not crash:
     - `DISK FULL ... pausing new launches` at the first failed write
     - 7 failed writes, with 1 row held in memory
     - `paused_enospc` in progress
     - `DISK WRITABLE AGAIN after 390 s` once the back-off retry succeeded
     - `LOW DISK ... pausing` / `DISK OK again after 90 s`
     - `disk_pause` / `disk_resume` events
   - Integrity afterwards: 29 new result rows = 29 calls; 0 error rows; 0 duplicate jids; 0 unparsable or torn lines in any record file.
3. **Second restart (idempotency), 4 min.** It re-admitted the same 8 cells and continued at gen 57 / 52. There were 0 bad lines, and `start.json.resumes` has 2 entries.

The real run was relaunched afterwards (`launch.sh full`).

### Deviations / interpretations (crash-resume, 2026-10-02)
- **D32: disk robustness.** No write can crash the scheduler on ENOSPC/EDQUOT any more:
  - `atomic_write` fsyncs before the rename, so a deferred NFS error surfaces there. On ENOSPC it retries with a back-off of 5 s doubling to at most 5 min. The exception is `progress.json`, which is non-critical: that heartbeat is skipped and retried 30 s later.
  - Every append handle (results, cells, train, candidates, events, rtcache, sched.log) is a `SafeAppender`. A row is written and fsynced at once. On failure the file is truncated back to its last good size, so there are no torn lines. The row stays in memory and is retried after the back-off.
  - At exit, unwritten rows are retried for up to 10 min. Anything still unwritten is spilled to `$TMPDIR/bv2-spill/` on local disk and appended back at the next start.
  - While a write is failing, or while the run-dir filesystem has < 5 GB free (checked every 30 s; `$TMPDIR` < 1 GB also counts), **no new jobs are launched**. Running jobs continue. `progress.json` shows `status: paused_low_disk` or `paused_enospc`, plus a `disk` block. `disk_pause` / `disk_resume` events and `sched.log` lines record each transition. Launches resume automatically.
  - Workers retry writing their result file. A worker that dies without a result during disk trouble is re-queued (up to 3 times) and **never cached** as an error row. Timeout kills are suspended during disk trouble.
  - The fault-injection hooks `BV2_INJECT_ENOSPC=t0:t1` and `BV2_INJECT_LOWDISK=t0:t1` (epoch seconds) exist for the test only.
- **D33: `--run-dir` re-bases run-relative config paths.** `pre_amend_dir`, `restore_from`, and the cells' `spec`/`tight_spec` (when the file exists in the new dir) point into the given dir, so a copy never reads or writes the real run. New flags for tests: `--max-procs`, `--max-minutes`.
- **D34: crash-resume of the amendment-2 phase (`resume_amend2`, `--dry-restore`).**
  - **Trigger.** If the run dir already holds amendment-2 state (start.json `amend2_restored`, or the `amend2_restore` event), a restart resumes that state instead of running `restore_amend2` again. In this mode the record files are appended to, never rotated; a copy goes to `logs/prev-<stamp>-resume/`. The docstring has the details.
  - **Rebuilt state.**
    - Cells: the last record per name.
    - Accepted cells and their class/atom/parent counters.
    - The queue.
    - The fence.
    - Pools: the amendment-1 rows exactly as restore did, plus the rl-v1.1 F1/F2 rows named in each cell's stages.
    - Search: the record archive/seen WLs plus every amendment-2 candidate.
    - Training: record tasks overlaid by amendment-2 records.
    - Bookkeeping counters: from the last `progress.json`. These are stats only; no decision depends on them, and they may lag the stop by < 30 s.
  - **In-flight cells are re-admitted first.** These are cells with status validating, an `admit` event, or rl-v1.1 rows of their own. They re-run from A1, and every finished call is a cache hit on its exact key.
  - **RNG position = generation index.** Each generation's RNG is seeded by stream seed : phase : grid point : gen. A resume continues at 1 + the last generation *started* (`steer` / new `gen_start` events). **The generation in flight at the stop is abandoned:** its unprocessed candidates are dropped, and their finished sizing rows stay cached. Processed feasible candidates with no confirmation or planting outcome are confirmed and planted (`resume:confirm`).
  - **Orphan results.** `out.json` files of workers that finished after the scheduler died are ingested on their exact key, and stale job files are removed.
  - **Idempotent.** A second restart sees everything the first resume appended. `start.json.resumes` lists every resume.
- **D35: downtime extends the bench end and the total budget.** At each resume, `[last heartbeat, resume time]` is added to `start.json.downtime`; a restart that comes before a new heartbeat merges into the open interval. The budget clocks are:
  - bench end = `t_amend1` + 72 h + downtime after `t_amend1`
  - total budget = `t_start` + 118 h + downtime
  - `progress.json` shows `bench_end`, `total_end`, `downtime` and `amendment2.bench_end_with_downtime`; `bench_end_unchanged` keeps the pre-crash value for the record.
  - This interval was 2026-10-02T14:41:15 → the relaunch. This applies the user's instruction for this crash, and the same rule for any later scheduler outage. The campaign stays inside the approved 3–5 days.
- **D36: disk pauses do not extend the end time.** A launch pause on a low or full disk (D32) keeps the scheduler alive and running jobs continue, so it is not counted as downtime. The pause intervals are recorded (`progress.disk.pauses_this_session`, `disk_pause`/`disk_resume` events). **Flagged for a user ruling** if a long pause happens.

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
- **Amendment-2 restarts resume** (D34): `launch.sh full` continues from the run dir's own amendment-2 state; `envrun.sh python kaggle/campaigns/bench-v2/bv2.py run --mode full --dry-restore` reports what a restart would restore without launching. A full disk pauses launches instead of crashing (D32).
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

# pilot-v0 — P0 (tiered held-out eval) + P0b (training data)

Pre-registered in `kaggle/PREREG-PILOT-V0.md` (frozen 2026-10-05, commit `137ea060a`).
User approval for P0 + P0b: 2026-10-05. **P1 (Kaggle) is NOT started**; it waits for a GPU-hour approval.
Verifier everywhere: `bench_anchor_prep.smoke_run(tokens, spec, seed, 2500, "bptm45", profile="rl-v1.2")` (`kaggle/VERIFIER-RL-V1.md` § rl-v1.2).

Status: **full run RUNNING** (launched 2026-10-05 16:56 IST, resumed after the stop/resume test at 16:59, pid in `run/sched.pid`). See "Monitoring".

## Files

| file | role |
|---|---|
| `pv0.py` | everything: `split`, `run` (one scheduler for P0 + P0b), `build-eval`, `build-data`, `plan` |
| `launch.sh` / `stop.sh` | detached launch (resumable) / graceful stop, modes `full` and `smoke` (`BV2_TMPDIR=/tmp/cr-pv0`, env = `../bench-v2/envrun.sh`) |
| `status.py` | one-screen status of a run dir (`status.py run`) |
| `eval/split.json` + `split.json.sha256` | the frozen split (written before any sizing; `pv0.py split` refuses to rewrite it) |
| `eval/{tiers.json, searchbar.json, prompts/, specs/}` | written automatically when P0 tiering completes |
| `data/{train-all.jsonl, subsets.json, manifest.json, stats.json, fence_check.json}` | written automatically when P0b completes |
| `run/` | the full run (raw rows, not committed) |
| `smoke/` | the smoke run; `results.jsonl` is read by the full run (exact-key cache), summaries committed |

## Split (`eval/split.json`, sha256 `809d4bc7fd02dbe475622115ded95b7434cbb372249ba182b26b8a40e28d272e`)

- Pool: `kaggle/train-pool-v2` (272 ok tasks, rl-v1.2 INDEX), 10 training-stream families (band × flavor).
- **Rule (deterministic, D-P1):** hold out exactly one wideband and one narrowband family whose total is within [⌈0.20·272⌉, ⌊0.25·272⌋] = [55, 68]; among the 13 admissible pairs take the one with the most tasks *not* labelled library-solvable (the eval needs T2/T3 items); ties → more tasks → lexicographic.
- **Held out: `wb1020-gain` (31) + `nb090-noise` (25) = 56 tasks (20.6 %)**, 34 of them not library-solvable by the pool label. Training side: 216 tasks in 8 families.
- Plus the 2 strict bench-v2 cells `v2b-wb0824-gain-188`, `v2b-wb1020-noise-217` as extra T3 items (bench grid points; eval-only anyway).
- Consequence: the training side has no `wb1020` task at all (the train stream's only wb1020 family is held out), so `wb1020-gain` also tests band transfer; `nb090` keeps its `power` family on the training side.

## P0 — tiering (`pv0.py run`, P0 part)

Per held-out task, under rl-v1.2:
1. **E-TF1:** a1–a5 × seed 1 at the task spec. These are exact-key cache hits on the AMENDMENT-3 T-F1 rows (`../bench-v2/amend3/run/results.jsonl`). If no anchor is feasible, a1–a5 × seed 2 (new sizing). Any feasible → **T1**.
2. **E-F2:** every round-trip-valid single edit of the **shown anchor** (bv2 `f2space_build` = E-c space: add R/C/L on every net pair, delete any element) at seed 1, **full enumeration, no early kill**. Pre-rejects (topology limits, structural degeneracy, port-DC pre-filter) run in-process with 0 evals. Then seed 2 for every infeasible candidate whose seed-1 worst normalized margin, including the wide-µ shortfall µ_wide − 1, is ≥ −0.1. Any feasible → **T2**, else **T3** (the task's verified witness exists; EVAL-ONLY).
3. **Strict cells:** T3 by their AMENDMENT-3 record. `build-eval` re-checks that record: every stage row is in the AMENDMENT-3 cache with profile rl-v1.2 and the recorded feasibility; A1 ≥ 2 feasible, A2, A3 pass; F1 and F2 have no feasible run at seeds 1 and 2; the F2 space equals the 178-edit a2 space; the witness token hash matches. Smoke: both pass.

Live F2 sizes (pre-rejects excluded) of the 35 tasks without a seed-1 library solver: wb1020-gain (shown a2) 107 each; nb090-noise a4 126, a3 56.

**Prompts** (`eval/prompts/<task>.json`): editcap arm B via `editcap_run.build_prompt_B(Spec, anchor.net, evidence, k=1)` with `EDITCAP_FEWSHOT` / `EDITCAP_NO_THINK` unset, i.e. spec block + shown anchor netlist verbatim + failure evidence + arm-B instructions, **no few-shot**. Each file holds `messages`, `prompt_text`, `evidence`, `shown_anchor` and the spec file (`eval/specs/`). Tiers and witnesses are **not** in the prompt files (`tiers.json` only).

**Search bar** (`eval/searchbar.json`, no extra sims): E-c method, the expected cost to the first feasible design for blind search in uniformly random order over the **sized** calls of the tiering runs. In-process pre-rejects cost 0 and are excluded. Calls = (N−K)/(K+1)+1 and SPICE-min = (Σ_infeasible secs/(K+1) + mean_feasible secs)/60. Costs are stage-wise: a stage with no feasible call is paid in full.
- **T1:** over the anchors' sizing calls, seed-1 stage, then the seed-2 stage.
- **T2:** over the shown anchor's single edits, the seed-1 stage, then the seed-2 near-feasible stage. `incl_failed_library_stage` adds the library stages paid in full.
- **T3:** `">F2 space"`, with the cost of exhausting the library and F2 stages.
- Call counts are given next to the minutes. Seconds are smoke_run wall seconds under the shared load at run time (E-c D3); cached AMENDMENT-3 rows keep their own seconds.

## P0b — training data (`pv0.py run`, P0b part)

**Generation (D-P4, D-P5).** bv2's training stream is extended with bv2's own code paths, through `Gen(bv2.Pipeline)` holding only the state those methods read: `make_generation`, `candidate_from_script`, `process_candidate`, `plant` (planting confirmation D2, componentwise-worst cushion), `planted_limits`, `make_spec`/`write_spec`. Settings:
- gen size 4 per point, ⅓ random / mutate-then-repair over the top-20 archive / cross-grid transfer, loose probe specs (identical content to bench-v2's), and the port-DC pre-filter at generation.
- **The 8 training-side points only.** The held-out points are neither generated nor used as mutation/transfer parents.
- A fresh RNG namespace `pilot-v0:2026092902:<point>:<gen>`, continuing at gen 51 (the last train-stream generation was 50).
- The archive is the earlier training candidates of the training-side points: 989 kept, 343 dropped by the port-DC pre-filter (bv2 D26). Seen WLs: all earlier train candidates.
- The dominance score uses bv2's recorded calibration designs (256 rows). It only steers parent selection.
- Every sizing call is rl-v1.2.

**Quota.** Per point: existing ok tasks + new planted ≤ Q, with Q₀ = 85. When every point is at Q, the generator waits for all planted tasks to finish. It stops if there are **≥ 600 ok training-side tasks and ≥ 1050 estimated examples**; otherwise it raises Q by 5 (max 130). The decision is taken only when no task is running, so a replay is deterministic.

**New tasks** are named `t2-<band>-<flavor>-<seq ≥ 1000>` with the train-pool-v2 spec description (D-P15). Each new task runs:
- **T-wit:** seed 1, then seed 2 if needed; ≥ 1 of {1, 2}, else `unproved`.
- **T-F1:** a1–a5 × seed 1 at the task spec, run for every task (as AMENDMENT 3 D40). This gives the library positives and the shown anchor's evidence.
- **Fence at planting:** bench-v2 planted cells of any era or status (witness, stripped and original), held-out task witnesses (WL and token hash), and bench and held-out spec content.

**Single-edit positives (D-P7).** A task with < 3 positives gets **one** candidate: the first (by id) recorded rl-v1.2 single-edit design from the AMENDMENT-3 bench F2 rows of the same band that meets the task's limits, is port-DC OK and wide-stable, and differs from the witness and the anchors. It is re-verified at the task spec (seed 1, then seed 2) and kept only if feasible. P0's held-out F2 rows are never used for training.

**Examples (`build-data`).** Per ok training-side task (the 216 pool tasks plus the new ones):
- **Prompt:** arm B, k=1, no few-shot. The shown anchor follows D-P2. Its failure evidence is that anchor's seed-1 T-F1 run (`bv2.make_evidence`).
- **Positives, in order:**
  1. the witness (verified T-wit run)
  2. one library anchor feasible at seed 1 (the parent first)
  3. the verified single edit
  4. further library anchors
- **Dedupe:** by WL within the task, at most 3 per task; a positive equal to the shown anchor is impossible (it fails).
- **Each example** holds the target netlist in the harness dialect (`target_netlist`, plus `completion` as a fenced ```netlist block), its WL and token hashes, and a `verification` record. The record carries profile, seed, jid, spec sha, feasibility, metrics, worst margin, µ_wide, port-DC, era, and the results file the row lives in.
- **Difficulty label** (AMENDMENT-3 rule, rl-v1.2 rows only, P0 rows excluded):
  - `library-solvable`: own T-F1 feasible, or a recorded anchor design meets the limits
  - `single-edit-solvable`: a verified or recorded single edit meets them
  - otherwise `witness-only`
- **Nested subsets 100 ⊂ 300 ⊂ 1000** (seed 20261005), stratified by band type × difficulty. Within a stratum, tasks are shuffled and examples are taken by (positive rank, task rank), so a subset covers as many tasks as possible. Allocation is largest-remainder, nested. Stored as id lists in `subsets.json`.
- **Fence check** (`fence_check.json`, rc ≠ 0 on any violation): no held-out family, no bench-v2 witness WL/token hash (all planted cells), no held-out witness hash, no bench-v2 / held-out spec content. The negative controls (a held-out task as an example; a strict cell's witness as a target) must be flagged; in the smoke they are.

## Compute conduct, monitoring, resume

- **Workers:** one scheduler, ≤ 8 worker processes in total (4 while load1 > 22). P0 has priority, but 3 slots (1 when throttled) stay reserved for P0b while it has pending work. Priority: E-TF1 > E-F2 > search/confirm > T-wit > T-F1 > T-SE.
- **Disk:** bv2 D32 disk robustness (SafeAppender, fsync'd atomic writes, launch pause on ENOSPC or < 5 GB free, workers without a result during disk trouble re-queued and never cached). Scratch: `TMPDIR=/tmp/cr-pv0`.
- **Monitoring:**
  - `run/progress.json` (every 30 s): P0 tiers so far, stage counts and F2 progress; P0b generation, Q, planted per point, task status, ok count, estimated examples; calls, CPU, disk, ETA.
  - `python kaggle/campaigns/pilot-v0/status.py run` prints a one-screen summary.
  - Log: `run/sched.log`. Pid: `run/sched.pid`.
- **Resume:** `launch.sh full` again. Every finished call is cached on the exact key `bv2.job_id(tokens, spec content, seed, budget, profile)`, and the generators replay deterministically. Record files are rotated to `run/logs/prev-*`.
  - Tested on the smoke: the relaunch replayed to the identical state with 0 new calls.
  - Tested on the full run: SIGTERM with 8 workers running gave `status: stopped`, 0 error rows, and the relaunch reached the same state (21 T1, gen 52, 13 planted); the killed calls were re-queued.
- `pv0.py build-eval|build-data --partial` writes a preview from the cache into `run/eval-partial` / `run/data-partial` at any time, with no launches.

## Smoke (`launch.sh smoke` → `smoke/`; 2026-10-05 16:24–16:55, 131 sized calls, 8 processes)

`--eval-limit 2 --f2-limit 8 --train-limit 2 --gen-max-new 2` (SMOKE SUBSET: F2 cut to the first 8 edits).
- **P0.**
  - `t2-nb090-noise-0013` is T1: a1 is feasible at seed 1. The parent a1 is itself feasible, so the shown anchor is **a2** (D-P2).
  - `t2-nb090-noise-0012` (a3): no anchor at seeds 1 and 2; 2 of the 8 F2 edits pre-rejected, 6 sized, none feasible, none near. That makes it T3 *on the subset only*.
  - Both strict cells pass every check.
  - Prompts, `tiers.json` and `searchbar.json` were written to `smoke/eval-out/`.
- **P0b, generation.** Gen 51: 32 search calls, 21 probe-feasible, 21 confirms. 16 confirmed, of which 3 were fenced by hash (bench-v2 witness topologies re-found) and 13 planted, one per training point or more.
- **P0b, tasks.** 12 ok and 1 unproved; one witness proved only at seed 2. The 2 old tasks gave 1 T-SE call each.
- **Examples.** 23 from 14 tasks: 14 witness, 7 library, 2 verified single edits. That is 1.64 per task, 18 distinct targets. Fence rc 0, and both negative controls were flagged.
- The full run reuses these rows on exact keys.

## Deviations / interpretations

- **D-P1: split rule.** The pre-reg says "~20–25 %, both band types". The concrete rule (one wideband + one narrowband family, maximize non-library tasks) is recorded in `split.json` with all 13 admissible pairs.
- **D-P2: shown anchor.** It is the task's parent anchor if that anchor is sized and *infeasible* at seed 1 at the task spec. Otherwise it is the first sized, infeasible anchor in the band's parent order (wideband a2, a3, a5; narrowband a1–a5).
  - Why: under rl-v1.2, 94 of the 272 pool tasks have a parent anchor that is itself feasible at seed 1, so "shown failing anchor + failure evidence" would be false for them.
  - This only affects T1 tasks. A non-T1 task's parent fails at seed 1 by definition, and F2 always enumerates the parent.
  - A task where no sized anchor fails gives no example and no eval item; this is counted.
- **D-P3: prompt k=1 and seed-1 evidence.** The pre-reg's examples are prompt → one netlist and P1 samples twice per task, so the arm-B instructions ask for exactly 1 edit (`build_prompt_B(..., k=1)`, otherwise byte-identical to editcap arm B). Evidence is the shown anchor's seed-1 run for every item: training tasks, held-out tasks and the strict cells. The bench library convention was the best of seeds 1 and 2; seed 1 is used for uniformity.
- **D-P4: generation target and quota.** "≥ 600 tasks" is read as ≥ 600 ok **training-side** tasks (existing 216 + new). Generation continues until that holds and ≥ 1050 examples are estimated, through the deterministic quota top-up described above. The witness proof runs seed 1, then seed 2 only if needed: the same ≥ 1-of-{1,2} criterion as bv2, without sizing seed 2 when seed 1 passes.
- **D-P5: carried-over steering state.** The archive scores (rl-v1/rl-v1.1) and the calibration pool (rl-v1) only steer mutation parents and the dominance score. They are not re-sized (as bv2 D26). Every candidate, confirmation and task call is rl-v1.2.
- **D-P6: T1 is own-spec sizing.** A recorded anchor design from another spec that meets the limits (the pool route of the AMENDMENT-3 label) does not make a task T1. Only an anchor sized at the task's own spec at seed 1 or 2 does. The pool label is kept in `tiers.json` as `pool_label_amend3`.
- **D-P7: single-edit positives** come from the AMENDMENT-3 bench F2 rows only and are re-verified at the task spec. There is at most one candidate per task, tried only when the task has < 3 positives.
- **D-P8: fence is wider than the pre-reg.** It also covers held-out task witnesses and every bench-v2 planted cell (any status), plus spec content.
- **D-P9: in-process pre-rejects** count as 0 SPICE-minutes and are excluded from N (E-c "unsizable"). The near-feasibility margin includes µ_wide − 1.
- **D-P10: shared scheduler.** P0 and P0b run in one process with a 3-slot P0b reservation, rather than two processes, so the 8-process cap holds exactly.
- **D-P11: subsets** include a nested 1000 (the P1 "1,000" model) when ≥ 1000 examples exist. They are stored as id lists, not separate jsonl.
- **D-P15: naming.** New tasks continue the train-pool-v2 stream's naming and spec description (`t2-…-1000+`, "train-pool-v2 planted task …"), so training and held-out prompts have the same format. Their specs live in `run/specs/`. The smoke still used a `pv0-` prefix; spec content (and so every job key) is unaffected.

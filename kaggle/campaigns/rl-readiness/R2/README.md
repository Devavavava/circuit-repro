# R2: thinking-length cap (Qwen3-14B, bench-v1.2, arm B, FS)

**Pre-registration:** `kaggle/PREREG-RL-READINESS.md` § R2, frozen 2026-09-28.

**Kaggle budget:** at most 1.5 GPU-h, approved by the user. **Used: 0.97 GPU-h.** This is one kernel session of
58.0 min wall, of which 3.3 min was setup and the rest generation only.

## Status

- The primary scoring (3 × 2500, bptm45, exactly like E-d) is **FINAL**.
- The stability-gated re-scores are **FINAL** in both modes: gate-only and gate + in-loop.

## Conditions

All conditions use the same prompt (FS: `EDITCAP_FEWSHOT=1`), the same model, sha256, lib, pdk, arm B, k=3, temp 0.7
and 8192 total-token cap. Each has 16 cells × 2 samples.

| cond | how | source |
|---|---|---|
| BASE (thinking on) | the existing E-d 14B-FS run, not re-run | `bench-v12-audit/E-d/14b` (pin `cc5a836bb`) |
| CAP (think ≈ 1024) | `EDITCAP_THINK_BUDGET=1024`: two-phase client-side cap (see below) | `kernel/editcap/CAP-s{1,2}` |
| NT (thinking off) | `EDITCAP_NO_THINK=1`: `\n/no_think` appended to the user turn (Qwen3 soft switch, as the pre-reg says) | `kernel/editcap/NT-s{1,2}` |

**How CAP is implemented** (`kaggle/editcap_run.py`, `_LiveLLM._complete_think_budget`):

1. `POST /apply-template` renders the model's own chat template.
2. `POST /completion` with `n_predict=1024` and `stop=["</think>"]`.
3. `POST /completion` for the answer:
   - prompt = template + think text + closer;
   - `n_predict = 8192 − think tokens`, so the total cap is unchanged;
   - the closer is `</think>` when the model closed its think by itself;
   - otherwise the closer is Qwen's early-exit sentence ("Considering the limited time by the user, I have to give
     the solution based on the thinking directly now.") followed by `</think>\n\n`.

Observed behaviour: 30 of 32 CAP thinks hit the 1024 limit and were force-closed, and 2 closed naturally.

**Native budget:** the bundled llama-server build (`version 0.3.0-dev, commit 4d19b28`) does have
`--reasoning-budget N` and `--reasoning-budget-message`. The kernel logged them (`kernel/llama-server-help.txt`) but
did not use them. The client-side cap was fixed before the push because the build could not be inspected locally. It
is also per-request, exact, and gives per-phase token counts. For rollouts, the native flag should be an equivalent
drop-in that avoids the second request.

**Probe:** before the runs, a 64-token two-phase probe confirmed that `/completion` renders `<think>` as text and
that the forced close yields a normal answer (`KERNEL-MANIFEST.json` → `probe`).

**Pin:** the kernel clone was pinned to `b5b90e01d`, the commit carrying the `editcap_run.py` flags; clone_head was
verified. The s1/s2 raw outputs were byte-identical in 0/16 cells for both CAP and NT.

## Scoring

`r2_score.py` uses the E-d `ed_score.py` functions unchanged: `round_trip` validity, dedup on the exact token
sequence, and `topo_flags`.

- **Engine:** every valid edit × seeds 1,2,3 × 2500 evals runs through `bench_anchor_prep.smoke_run` on bptm45.
- **Parallelism:** at most 4 processes.
- **Unique candidates:** 271 (cell, tokens) pairs over the 3 conditions.
- **Plain mode:** E-d `score.jsonl` rows for identical (cell, key) are imported, since the engine, seeds and budget
  are the same; 294 rows were imported. The other 519 jobs were sized fresh at HEAD `388ba46ec`, with 0 crashes.
- **Consistency check:** re-deriving BASE from the imported rows reproduces E-d exactly: 11 feasible edits, 6 cells
  (4 SYN / 2 RET), EDGE solved.

## Result (plain spec, primary, 3 × 2500)

| cond | tokens / completion, mean (reasoning / answer) | GPU-min / compl. (mean, median, max) | edits | valid | feasible edits (% of all) | cells solved: all / SYN / RET | ≥ 2/3 seeds | EDGE | wb shunt-fb: wide (VIN-side) / wb valid, cells |
|---|---|---|---|---|---|---|---|---|---|
| BASE | 2451 (≈2033 / ≈417, est.) | 1.77, 1.78, 2.70 | 96 | 96 (100%) | 11 (11.5%) | **6 / 4 / 2** | 5 | yes | 14 (21) / 48, 8/8 |
| CAP | 1561 (1005 / 556, exact) | **1.10**, 1.09, 1.25 | 96 | 96 (100%) | 10 (10.4%) | **5 / 4 / 1** | 5 | yes | 14 (20) / 48, 7/8 |
| NT | 834 (0 / 834) | **0.58**, 0.59, 0.74 | 96 | 93 (97%) | 5 (5.2%) | **4 / 3 / 1** | 4 | no | 9 (17) / 46, 7/8 |

Notes on the columns:

- **Token split:** CAP is exact (per-phase `tokens_predicted`). For BASE, the completion tokens are split using the
  reasoning:content character ratio, with characters per token calibrated on CAP (4.30 for reasoning, 2.74 for
  answer). NT has reasoning_chars = 0 in 32/32 completions: the soft switch held.
- **GPU-min:** BASE is llama-server `total time`. CAP and NT are the response `timings` (prompt + predicted ms),
  summed over the two CAP phases.
- **Other health counts:** 0 hit finish=length, 0 were empty, 0 had no edit, and 0 were recovered from reasoning in
  any condition.

**Cells solved** (all are wideband; 0/8 narrowband in every condition, as in E-d):

| cond | cells solved |
|---|---|
| BASE | s11n10-g10-b0824, s11n10-g12-b0824, s11n11-g10-b0824, s11n11-g12-b0824, s11n8-g10-b0530, s11n8-g12-b0530 (EDGE) |
| CAP | s11n10-g10-b0824, s11n11-g12-b0824, s11n8-g10-b0530, s11n8-g12-b0530 (EDGE), **s11n9-g10-b0530** (new vs BASE) |
| NT | s11n10-g10-b0824, s11n11-g10-b0824, s11n11-g12-b0824, s11n8-g10-b0530 |

GPU cost for the whole 32-completion set: BASE 56.8 GPU-min, CAP 35.2, NT 18.5.

## Decision rule (pre-reg)

A cheaper condition is acceptable if all three hold: validity ≥ 95%, cells solved drop ≤ 1, and per-edit feasible
rate drop ≤ 5 points.

| cond | validity | cells drop | feasible-rate drop | acceptable |
|---|---|---|---|---|
| CAP | 100% ✓ | 1 ✓ | 1.0 pt ✓ | **YES** |
| NT | 97% ✓ | 2 ✗ | 6.3 pt ✗ | no |

**Verdict: CAP (thinking capped at about 1024 tokens) is the cheapest acceptable condition.** It is the recommended
RL-rollout setting:

- about 0.62× the GPU time per completion of thinking-on (1.10 vs 1.77 min);
- 36% fewer tokens (1561 vs 2451);
- a flat cost (max 1.25 min vs 2.70), which suits fixed-length GRPO batches.

NT fails narrowly on both the cells-solved and feasible-rate criteria. It also emits fewer feedback edits
(9 vs 14 wide shunt-fb).

**Caveat (stated in the pre-reg):** with 2 samples per cell the comparison is coarse. A 1-cell / 1-point difference is
within sampling noise: BASE s1 vs s2 alone differ by 4 vs 5 cells.

## Stability-gated re-score

All three conditions were re-scored under `bench_anchor_prep.stability_spec(spec)`, which adds `mu_min ≥ 1` and the
0.1–20 GHz wide audit of the winner. Two modes were run:

- **gate** = gate-only (the audit and feasible-point rescan, no in-loop term);
- **inloop** = gate + `STAB_WIDE_INLOOP=1` (the S-1 in-loop stability term).

This used HEAD ≥ `ffa594a05`, which includes the atomic `stability_spec` write. Every worker also asserts that the
loaded spec has all of the original constraints plus `mu_min` (`n_constraints` is recorded per row).

Results are in `tables.md` (the last two columns) and in `summary.json` → `conds.<C>.gate` / `.inloop`.

**FINAL.** Both modes are complete: 813/813 rows each, 0 crashes, and every spec was loaded complete.

| cond | gate-only: feasible edits, cells solved (SYN/RET) | gate + inloop: feasible edits, cells solved (SYN/RET), ≥ 2/3 seeds | inloop cells |
|---|---|---|---|
| BASE | 0, **0** (0/0) | 2, **2** (1/1), 1 | s11n10-g10-b0824, s11n8-g10-b0530 |
| CAP | 0, **0** (0/0) | 3, **2** (1/1), 1 | s11n10-g10-b0824, s11n9-g10-b0530 |
| NT | 0, **0** (0/0) | 1, **1** (1/0), 1 | s11n11-g10-b0824 |

- **Gate-only solves nothing in any condition.** 44 of 813 runs were spec-feasible under the stability spec, but none
  was wide-stable, and no rescan point rescued one.
- **With the in-loop term (S-1), a few wideband cells come back.** The rank is CAP ≥ BASE > NT: CAP is not worse than
  thinking-on under the stability-enabled verifier either (2 vs 2 cells, 3 vs 2 feasible edits).
- The counts are tiny (≤ 3 edits), so they only corroborate the plain-spec decision and do not change it. The
  pre-registered decision rule is applied to the plain-spec scores.
- **Implication for RL:** a verifier using gate-only stability gives almost no positive reward on these cells. If the
  RL reward includes stability, it needs the in-loop term.

## Files

- **Scripts and inputs:**
  - `r2_score.py`: enumerate / run `plain|gate|inloop` / worker.
  - `r2_summarize.py`: writes `summary.json` and `tables.md`, and applies the decision rule.
  - `envrun.sh`: the env wrapper (inline copy of crenv.sh).
  - `fake_llama_server.py`: the local mock used to test the flags before the push.
- **Scored data:**
  - `edits.jsonl`, `completions.jsonl`, `cand.json`.
  - `score-plain.jsonl`, `score-gate.jsonl`, `score-inloop.jsonl`.
- **Kernel output:** `kernel/` holds the output verbatim, minus the llama.cpp (148 MB) and ngspice caches. Its
  launch dir is `kaggle/kernels-editcap/rl-readiness-r2-think/`.

## Deviations

1. **In-kernel sizing skipped.** `EDITCAP_GEN_ONLY=1` turned off the in-kernel smoke/size/escalate. E-d's in-kernel
   sizing was recorded only, and costs about 1.3 GPU-session-min per cell. Scoring is fully local, as pre-registered.
   The E-d "in-kernel solved" column therefore has no CAP/NT counterpart.
2. **Client-side cap, not native.** The think cap is the client-side two-phase method, not `--reasoning-budget`
   (see above). The pre-reg specifies only "thinking capped at ~1024 tokens".
3. **Scoring code eras differ.** Local scoring ran at HEAD `388ba46ec` for the new rows; BASE plain rows were
   imported from E-d (era `a0e4edcc6`). The bench_anchor_prep changes since then are opt-in with flags-off
   byte-identical, as their commits state.
4. **BASE token split is estimated.** The reasoning/answer split for BASE is an estimate, because E-d archived only
   character counts.
5. **Inloop runs split across two HEADs.** The first 143 BASE inloop rows ran at HEAD `ffa594a05`; the rest ran at
   `388ba46ec`. Both include the atomic `stability_spec` fix.

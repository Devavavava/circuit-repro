# exit-r1 — expert iteration round 1 (architecture B, first batched RL round)

Pre-registered in `kaggle/PREREG-EXIT-R1.md` (frozen 2026-10-08, commit `573a21a89`). User GO with a
**≈ 20 GPU-h** Kaggle budget for this round (separate from pilot-v0 + v1's 30 h); ledger below.
Held-out eval = pilot-v0's (58 items, split sha `809d4bc7…`, tiers T1 23 / T2 32 / T3 3).

Status (2026-10-10 05:40 IST): gen-sft1000 done + verified (ad9768edf); gen-sft300 pushed 05:39 IST after the quota refresh (30.00 h free, next refresh 10-17).
Earlier status (2026-10-08 23:30 IST): step 1 staged; Kaggle weekly GPU quota at start: **used 26.08 h, remaining 3.92 h
of 30.00 h, refresh 2026-10-10 00:00 UTC** (`kaggle quota`). gen-sft1000 fits in the remainder; everything
else waits for the refresh.

## Pieces

| file | role |
|---|---|
| `r1_prep.py tasks` | `gen/TASKS.json`: the 641 training-side tasks with a pilot-v0 prompt, seeded order (seed 20261008) |
| `r1_gen.py` | in-kernel generation driver: pilot-v0's completion path (editcap `_LiveLLM`, CAP-1024, arm B k=1, no few-shot, T 0.7) on the training prompts; archives the think text + its token count |
| `r1_verify.py` | step 2: `enumerate` (local round-trip, key, novelty/copy/anchor flags, trace-filter inputs) → `verify/<policy>/completions.jsonl`; `run` (rl-v1.2-rl seed 1, seed 2 for seed-1-feasible; ≤ 8 procs, 4 at load1 > 22, D32 disk robustness, resumable); `kick` (step-5 rl-v1.2-rl column for rl-v1.2-feasible score rows) |
| `r1_build.py` | step 3: round-1 data (pool, dedupe, mix, fence) → `sft-data/` |
| `r1_summarize.py` | `gen` (step-2 tables → `verify/gen-tables.md`), `heldout` (steps 5–6 → `score/r1-tables.md`, decision rule) |
| `kernel_r1.py` | kernel body; kinds `gen` (pilot-v0 LoRA → pilot-v1 H1 GGUF path → `r1_gen.py`) and `sft` (pilot-v0 `KC.main_sft`, 8 held-out samples) |
| `kaggle/kernels-editcap/exit-r1-*/` | thin launchers (clone at `REPO_SHA`, call `kernel_r1.main`) |

## Kernels (slug `devavratpatni/circuit-repro-exit-r1-…`; T4 ×2, internet on, pilot-v0 datasets)

| kernel | kind | what | session cap (`-t`) |
|---|---|---|---|
| `gen-sft1000` | gen | kernel source `pilot-v0-sft1000` → `p1/lora-sft1000` → merge/f16/Q4_K_M → 641 tasks × 2 samples, `--parallel 4` | 215 min |
| `gen-sft300` | gen | same for `pilot-v0-sft300` | 345 min |
| `sft-r1` | sft | pilot-v0 recipe on the round-1 data → GGUF → held-out run, 8 samples × 58 (sample-major) | ≤ 715 min |

## Task set (step 1)

`gen/TASKS.json`: 641 tasks = every task of `pilot-v0/data/train-all.jsonl` (180 train-pool-v2 + 461 pilot-v0
P0b; narrowband 397 / wideband 244; labels library-solvable 364 / witness-only 268 / single-edit 9). The
held-out families `wb1020-gain`, `nb090-noise` are asserted absent. pilot-v0 has 677 ok training-side tasks;
the other 36 have no pilot-v0 example and so no prompt to sample from (listed in `TASKS.json`).

## Deviations / interpretations (D-R*)

- **D-R1 think text archived.** pilot-v0's held-out driver keeps only the answer; the pre-reg's new-positive
  target is "its reasoning + verified netlist", so `r1_gen.py` wraps `_LiveLLM._complete_think_budget` to keep
  the two-phase response and writes `reasoning.txt` + the llama-server `/tokenize` count. Sampling is unchanged.
- **D-R2 throughput: 4 server slots, task-major seeded order.** At pilot-v1's `--parallel 1` rates (12.1 s /
  17.9 s per completion) 2 × 641 × 2 completions + 2 GGUF rebuilds project to ≈ 12 GPU-h > 10. Instead of
  subsampling up front, the gen kernels run llama-server with `--parallel 4` (`-c 65536` = 16384 per slot, the
  eval's per-slot context; same flags otherwise; pilot-v0's rationalize kernels ran this binary at
  `--parallel 4`) and 4 client threads. Sampling settings are unchanged. Tasks run task-major (both samples of a
  task, then the next) in the seeded `TASKS.json` order, so a deadline cut leaves a uniformly random subset
  of tasks — the pre-reg's fallback — recorded with the count.
- **D-R3 2-sample protocol = samples 1–2 of the 8-sample held-out run.** `sft-r1` generates 8 samples ×
  58 sample-major with pilot-v0's driver and flags, so samples 1 and 2 are produced exactly as pilot-v0's
  2-sample run (same order, same code) and samples 1–8 are pilot-v1's H1 run. One GGUF, one session; saves a
  second ~35-min held-out pass and the D-V4 rebuild.

- **D-R4 fence hits among self-positives are dropped, not fatal.** The model can rediscover a fenced topology
  (bench-v2 planted cell or held-out witness) on a training task. `r1_build.py` drops such positives and counts them
  (`MIX.json` `pool.fence_dropped_self` + ids); pilot-v0 examples stay hard-asserted. Dry run on the sft1000 half
  (2026-10-10): 3 dropped (`t2-nb090-power-1013` s1, `t2-nb240-noise-0327` s1, `t2-wb0530-gain-0284` s2); mix 1,066
  (pilot-v0 950 + self 116; 104 examples / 92 WLs new vs pilot-v0; anchor share 0.345); self reasoning tokens
  median 212, 41/116 < 20 (inside the pre-reg's 1..512 filter, recorded not changed).

## GPU-h ledger (round cap ≈ 20 GPU-h; Kaggle session wall time, rounded up to 0.05 h)

| kernel | version | pinned commit | start (IST) | end | GPU-h | note |
|---|---|---|---|---|---|---|
| gen-sft1000 | 1 | `da29e4891` | 2026-10-08 23:04 | 10-09 02:05 | 3.05 | GGUF 29.9 min (sha `e3404d0d…` ≠ pilot-v0 `7f0c5921…`, D-V4); 1282 completions (641 tasks × 2, none cut) in 149.0 min at 4 slots = 7.0 s/completion (1.73× pilot-v1's 12.1 s); Kaggle quota 26.08 → 29.08 h |
| gen-sft300 | 1 | `da29e4891` | 2026-10-10 05:39 | 10-10 ~09:37 | 3.95 | session 237 min; 1282 completions (641 tasks × 2, none cut, 1265 valid) in 204.8 min at 4 slots = 9.6 s/completion; Kaggle quota (new week) 0 → 3.95 h |
| **exit-r1 total** | | | | | **7.00** | of ≈ 20 |

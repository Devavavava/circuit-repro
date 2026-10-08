# exit-r1 — expert iteration round 1 (architecture B, first batched RL round)

Pre-registered in `kaggle/PREREG-EXIT-R1.md` (frozen 2026-10-08, commit `573a21a89`). User GO with a
**≈ 20 GPU-h** Kaggle budget for this round (separate from pilot-v0 + v1's 30 h); ledger below.
Held-out eval = pilot-v0's (58 items, split sha `809d4bc7…`, tiers T1 23 / T2 32 / T3 3).

Status (2026-10-08 23:30 IST): step 1 staged; Kaggle weekly GPU quota at start: **used 26.08 h, remaining 3.92 h
of 30.00 h, refresh 2026-10-10 00:00 UTC** (`kaggle quota`). gen-sft1000 fits in the remainder; everything
else waits for the refresh.

## Pieces

| file | role |
|---|---|
| `r1_prep.py tasks` | `gen/TASKS.json`: the 641 training-side tasks with a pilot-v0 prompt, seeded order (seed 20261008) |
| `r1_gen.py` | in-kernel generation driver: pilot-v0's completion path (editcap `_LiveLLM`, CAP-1024, arm B k=1, no few-shot, T 0.7) on the training prompts; archives the think text + its token count |
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

## GPU-h ledger (round cap ≈ 20 GPU-h; Kaggle session wall time, rounded up to 0.05 h)

| kernel | version | pinned commit | start (IST) | end | GPU-h | note |
|---|---|---|---|---|---|---|

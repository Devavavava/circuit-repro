# pilot-v1 — H1 pass@k headroom + M1 data-mix fix

Pre-registered in `kaggle/PREREG-PILOT-V1.md` (frozen, commit `e46157ccf`). User GO after the pilot-v0 review.
GPU cap: pilot-v0 + pilot-v1 ≤ 30.0 Kaggle GPU-h; pilot-v0 used 17.90 → **≤ 12.1 GPU-h here** (ledger below).
Same held-out eval as pilot-v0 (`pilot-v0/P1/prompts`, 58 items, split sha `809d4bc7…`, tiers T1 23 / T2 32 / T3 3),
same verifier rl-v1.2 (bptm45, 2500 evals).

Status (2026-10-07 20:50): **DONE.** H1 (both models) and M1 ran and were scored; GPU 8.70 h (cumulative 26.60 of 30).

## Pieces

| file | role |
|---|---|
| `kernel_v1.py` | kernel body; kinds `lora_heldout` (H1), `rat`, `sft` — all steps are pilot-v0's `P1/kernel_common.py` functions, unchanged |
| `build_mix.py` | M1 data: `rat-input` (the new examples to rationalize), `build` (selection + pilot-v0 `build_sft.py sft` re-verification/fence → `sft-data/`, `MIX.json`) |
| `pv1_score.py` | local scoring (pilot-v0 `p1_score.py` enumerate + worker; policy `h1` = seed 1 then seeds 2,3 for seed-1-feasible keys; `all3` = seeds 1–3); ≤ 8 processes (4 at load1 > 22), D32 disk robustness |
| `pv1_summarize.py` | H1 pass@k / coverage / per-task frequency; M1 per-tier table vs sft300/sft1000, copy rate, decision rule |
| `kaggle/kernels-editcap/pilot-v1-*/` | thin launchers (clone at `REPO_SHA`, call `kernel_v1.main`) |

## Kernels (slug `devavratpatni/circuit-repro-pilot-v1-…`; T4 ×2, internet on, pilot-v0 datasets)

| kernel | kind | what | session cap (`-t`) |
|---|---|---|---|
| `h1-sft300` | lora_heldout | kernel source `pilot-v0-sft300` → its LoRA `p1/lora-sft300` → pilot-v0 merge/convert/quantize (Q4_K_M sha256 compared with pilot-v0's `ba756db7…`) → held-out run, **8 samples × 58** | 210 min |
| `h1-sft1000` | lora_heldout | same for `pilot-v0-sft1000` (GGUF `7f0c5921…`) | 160 min |
| `rat-mix` | rat | pilot-v0 rationalize kernel on the 4 new mix candidates (`rat/rat-input-mix.jsonl`) | 35 min |
| `sft-mix1000` | sft | pilot-v0 SFT recipe on `sft-data/sft-<N>.jsonl` → GGUF → held-out run, 2 samples × 58 | 285 min |

Worst case if every session hits its cap: 210 + 160 + 35 + 285 = 690 min = 11.5 GPU-h ≤ 12.1.

## M1 data mix (`build_mix.py`)

Selection (deterministic; seed 20261005 = pilot-v0's subset seed, so each stratum's order is pilot-v0's own and
pilot-v0's nested-1000 is checked to be a per-stratum prefix of it):
1. ≤ 3 examples per canonical target WL (global cap).
2. Phase A: **all** available non-library examples (difficulty `witness-only`, `single-edit-solvable`) in stratum order.
3. Phase B: `library-solvable` examples up to 40 % of the mix (L = ⌊2|A|/3⌋), split over band types in proportion to the
   library-solvable pool (largest remainder, as pilot-v0), each band's stratum order, WL cap.
4. An example without a kept rationale is unavailable: pilot-v0's 6 that failed 3 attempts (not retried, they are not
   new), and any new example that fails in `rat-mix`.
5. Traces: pilot-v0's kept trace for every unchanged example; the new ones from `rat-mix` (same prompt, filters, ≤ 3 attempts).
   pilot-v0 `build_sft.py sft` re-verifies every trace locally and re-checks the fence.

## Deviations / interpretations (D-V*)

- **D-V1 mix size (≈ 1,000 not reachable).** The ≤ 3-per-target-WL cap alone bounds any subset of pilot-v0's
  1013 training examples at **602**; with the library-solvable ≤ 40 % cap and "all available" non-library
  examples (284, 276 after the WL cap) the mix is ~458 examples. The pre-reg's "≈ 1,000" assumed more distinct
  targets than exist; producing more would need new P0b generation + rationalization, which is neither in
  the pre-reg nor in the GPU budget. The constraints (the treatment) are kept, the size is not; the model keeps
  the pre-registered name `sft-mix1000`, trained on N examples (stated with every result).
- **D-V2 "library-solvable" = the difficulty label** (as in the pre-reg's "72 %" = 729/1013), and "witness and
  single-edit examples" = the non-library difficulty classes. Consequence: the library quota is filled with
  positive-rank-1 examples (the task witness) of library-solvable tasks before any anchor target is reached,
  so the mix contains **0 anchor-target examples** (sft1000: 365 of 994; sft300: 0 of 298).
- **D-V3 new examples.** Only 13 train examples were never rationalized (not in pilot-v0's nested 1000); the 9
  library-solvable ones are positive rank 3, far past the library quota, so only the 4 non-library ones are
  rationalized (3 of them are selected if all pass; the 4th is the WL-cap spare).
- **D-V4 H1 GGUFs rebuilt from the LoRA — not byte-identical.** pilot-v0 kept only the LoRA adapters (kernel
  outputs); each H1 kernel re-ran pilot-v0's merge → f16 → Q4_K_M. Same adapter, same code, same size
  (9001753440 B), but the Q4_K_M sha256 differs from pilot-v0's for both models (sft300 `33f9ed4b…` vs `ba756db7…`,
  sft1000 `a5e82d9e…` vs `7f0c5921…`): the unsloth merge is not bit-reproducible. The H1 models are therefore
  the same fine-tunes re-materialized, not the identical pilot-v0 files.
- **D-V5 H1 samples are fresh.** k = 8 new samples per task (pilot-v0's 2 are not reused), sample-major order (a
  truncated run leaves complete samples). pass@k uses the unbiased estimator over each task's n samples.
- **D-V6 H1 pass criterion.** A sample passes iff its valid edit is feasible at seed 1 (pre-reg: R1 precision 1.0
  at this level); seeds 2,3 are run for every seed-1-feasible key and reported as the confirmation rate.

## RESULT H1 — pass@k headroom (`score/h1-tables.md`, `score/h1-summary.json`)

8 fresh samples × 58 items per model (464 completions, 460 valid each). Pass = valid edit feasible at seed 1
(rl-v1.2, 2500); every seed-1-feasible key re-sized at seeds 2,3 ("conf." = feasible at ≥ 2 of 3 seeds).
Scoring: 784 unique keys, 1146 sizing rows (seed 1 + confirmations), 0 missing, 0 crashed.

| model | group | pass@1 | pass@2 | pass@4 | pass@8 | coverage (any of 8) | pass@8 conf. |
|---|---|---|---|---|---|---|---|
| sft300 | all (58) | 0.177 | 0.294 | 0.450 | **0.621** | 36 | 0.586 |
| sft300 | T1 (23) | 0.152 | 0.266 | 0.416 | 0.565 | 13 | 0.522 |
| sft300 | T2 (32) | 0.211 | 0.342 | 0.517 | 0.719 | 23 | 0.688 |
| sft300 | T3 (3) | 0 | 0 | 0 | 0 | 0 | 0 |
| sft1000 | all (58) | 0.297 | 0.453 | 0.601 | **0.707** | 41 | 0.672 |
| sft1000 | T1 (23) | 0.467 | 0.685 | 0.865 | 0.957 | 22 | 0.957 |
| sft1000 | T2 (32) | 0.199 | 0.321 | 0.453 | 0.563 | 18 | 0.500 |
| sft1000 | T3 (3) | 0.042 | 0.083 | 0.167 | 0.333 | 1 (strict cell `v2b-wb1020-noise-217`, 1/8) | 0.333 |

- **Reading (pre-declared): strong verifier-selection headroom for both models.** pass@8 / pass@1 = **3.51** (sft300)
  and **2.38** (sft1000), both ≥ 1.5. Selecting among 8 samples with the verifier more than doubles the solve rate.
- Per-item solve count c (of 8), all items: sft300 {0: 22, 1: 15, 2: 9, 3: 6, 4: 3, 5: 1, 7: 2}; sft1000 {0: 17, 1: 8,
  2: 6, 3: 11, 4: 4, 5: 5, 6: 5, 7: 2}. Most solved items are solved by only 1–3 of 8 samples.
- Confirmation: 69/82 (sft300) and 120/138 (sft1000) seed-1-feasible samples are also feasible at seed 2 or 3.
- Coverage overlap: 28 items solved by both, union **49/58**; sft300-only 8, sft1000-only 13.
- Diversity / copying: sft300 429 distinct WLs among 460 valid, 0 own-training-target copies; sft1000 223 distinct,
  186/460 = 40.4 % copies (pilot-v0 at 2 samples: 46/115 = 40 %).
- Not comparable to pilot-v0's "solved": that counted feasibility at any of seeds 1–3 over 2 samples; H1's pass is
  seed 1 only (pre-reg). The rebuilt GGUFs are not byte-identical to pilot-v0's (D-V4). sft1000 did not re-solve
  `v2b-wb0824-gain-188` in 8 samples; it solved the other strict cell once.

## RESULT M1 — data-mix fix (`score/m1-tables.md`, `score/m1-summary.json`)

Mix (`sft-data/MIX.json`): **458 examples** (455 tasks): 275 non-library (263 witness-only, 12 single-edit-solvable)
+ 183 library-solvable (39.96 %); narrowband 257 / wideband 201; 346 distinct target WLs, max 3 per WL
(sft1000: 453 distinct, max 261, 71.9 % library-solvable); sources witness 453, single-edit 5, **anchor targets 0**;
455 reused pilot-v0 rationales + 3 new (rat-mix 4/4 kept at attempt 1). Training: 229 optimizer steps (916 micro,
9.81 s/micro, 150 min, not truncated), loss 0.79 → 0.36. Held-out run: 116/116 valid, think closes naturally
(mean 243 tokens). Scoring: seeds 1–3 for every valid key (348 rows, 0 missing).

| model | train ex. | solved | ≥ 2/3 seeds | T1 /23 | T2 /32 | T3 /3 | validity | copy rate (own training targets) | distinct WLs |
|---|---|---|---|---|---|---|---|---|---|
| sft300 (pilot-v0) | 298 | 28 | 24 | 10 | 18 | 0 | 99.1 % | 0/115 | 113 |
| sft1000 (pilot-v0) | 994 | 28 | 24 | 19 | 8 | 1 | 99.1 % | 46/115 = 40.0 % | 67 |
| **sft-mix1000** | 458 | 26 | 18 | **5** | **20** | 1 | 100 % | **5/116 = 4.3 %** | 115 |

≥ 2/3 seeds per tier (T1/T2/T3): sft300 9/15/0, sft1000 16/7/1, mix 5/13/0. The mix's T3 solve is strict cell
`v2b-wb1020-noise-217` at seed 2 only (1 of 3 seeds).

**Decision rule (pre-registered): the mix fix does NOT "work".**
- T2: mix − sft1000 = **+12** (≥ 3 required) ✓
- T1: sft1000 − mix = **14 lost** (must be < 3) ✗
- copy rate 4.3 % < 40 % / 2 ✓

vs sft300: T2 +2, T1 −5. Solved-set overlap: with sft300 16 common (union 38), with sft1000 10 common (union 44).
Interpretation (not pre-registered): removing the repeated anchor targets fixed copying and recovered T2 (above
sft300's 18), but the mix has **no anchor-target example at all** (D-V2) and the model largely stopped proposing
library anchors, which is what T1 items need; the T1 loss is the cost of that, not of the WL cap per se.
The mix also has half of sft1000's examples (D-V1).

## GPU-h ledger (cap: pilot-v0 + v1 ≤ 30 GPU-h; Kaggle session wall time, rounded up to 0.05 h)

| kernel | version | pinned commit | start (IST) | end | GPU-h | note |
|---|---|---|---|---|---|---|
| rat-mix | 1 | `cbeb6a017` | 2026-10-07 14:25 | 14:30 | 0.10 | 4 examples, 4 calls, 4 kept; 3.2 min in-kernel |
| h1-sft300 | 1 | `cbeb6a017` | 14:25 | 17:16 | 2.85 | GGUF 29.4 min; 464 completions in 138.5 min |
| sft-mix1000 | 1 | `833313861` | 14:32 | 18:06 | 3.60 | 458 ex., 150 min train; GGUF 25 min; held-out 34.2 min |
| h1-sft1000 | 1 | `cbeb6a017` | 17:16 | 19:23 | 2.15 | GGUF 30.1 min; 464 completions in 93.5 min (1st push got a Kaggle 500, nothing created; retried) |
| **pilot-v1 total** | | | | | **8.70** | of the 12.1 remaining |
| **cumulative pilot-v0 + v1** | | | | | **26.60** | of 30.0 |

## Reproduce the scoring

```
E=kaggle/campaigns/bench-v12-audit/E-d/envrun.sh
$E python kaggle/campaigns/pilot-v1/pv1_score.py enumerate <label> kaggle/campaigns/pilot-v1/kernels/<kernel>/gen
$E python kaggle/campaigns/pilot-v1/pv1_score.py run 8 h1 h1-sft300      # and h1-sft1000
$E python kaggle/campaigns/pilot-v1/pv1_score.py run 8 all3 mix1000
$E python kaggle/campaigns/pilot-v1/pv1_summarize.py h1 h1-sft300,h1-sft1000
$E python kaggle/campaigns/pilot-v1/pv1_summarize.py m1 mix1000
```
Kernel outputs archived in `kernels/<kernel>/` (gen/, kernel.log, manifest; train.jsonl for sft-mix1000). The
sft-mix1000 LoRA stays in the Kaggle kernel output `devavratpatni/circuit-repro-pilot-v1-sft-mix1000` (`p1/lora-sft-mix1000`).

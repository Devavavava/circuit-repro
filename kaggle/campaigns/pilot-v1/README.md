# pilot-v1 — H1 pass@k headroom + M1 data-mix fix

Pre-registered in `kaggle/PREREG-PILOT-V1.md` (frozen, commit `e46157ccf`). User GO after the pilot-v0 review.
GPU cap: pilot-v0 + pilot-v1 ≤ 30.0 Kaggle GPU-h; pilot-v0 used 17.90 → **≤ 12.1 GPU-h here** (ledger below).
Same held-out eval as pilot-v0 (`pilot-v0/P1/prompts`, 58 items, split sha `809d4bc7…`, tiers T1 23 / T2 32 / T3 3),
same verifier rl-v1.2 (bptm45, 2500 evals).

Status: RUNNING (see ledger).

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
- **D-V4 H1 GGUFs rebuilt from the LoRA.** pilot-v0 kept only the LoRA adapters (kernel outputs); each H1 kernel
  re-runs pilot-v0's merge → f16 → Q4_K_M and records whether the GGUF sha256 equals pilot-v0's.
- **D-V5 H1 samples are fresh.** k = 8 new samples per task (pilot-v0's 2 are not reused), sample-major order (a
  truncated run leaves complete samples). pass@k uses the unbiased estimator over each task's n samples.
- **D-V6 H1 pass criterion.** A sample passes iff its valid edit is feasible at seed 1 (pre-reg: R1 precision 1.0
  at this level); seeds 2,3 are run for every seed-1-feasible key and reported as the confirmation rate.

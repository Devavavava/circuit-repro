# pilot-v0 P1 — Kaggle: zero-shot baseline, rationalized traces, SFT 100/300/1000

Pre-registered in `kaggle/PREREG-PILOT-V0.md` § P1 (frozen, commit `137ea060a`).
User approval: **~30 Kaggle GPU-h total (hard cap)**, 2026-10-05. Ledger below.
Verifier for every score: rl-v1.2, bptm45, 2500 evals, seeds 1, 2, 3 (`kaggle/VERIFIER-RL-V1.md`).

Status (2026-10-07 13:00): **DONE.** All P1 kernels ran and were scored; decision rule evaluated (below). GPU: 17.90 of 30 GPU-h.

## Pieces

| file | role |
|---|---|
| `build_prompts.py` | held-out prompts from the frozen split via pv0.py's own prompt path (read-only import) → `prompts/`, `specs/`; `compare` = byte equality vs P0's `eval/prompts/` |
| `p1_gen.py` | in-kernel driver. `heldout`: CAP-1024 arm-B k=1 generation (editcap `_LiveLLM`), gen-only. `rationalize`: STaR traces with filters |
| `kernel_common.py` | kernel bodies (kinds `eval`, `rat`, `sft`); the thin `kaggle/kernels-editcap/pilot-v0-*/kernel.py` clone the repo at a pinned commit and call it |
| `sft_train.py`, `sft_merge.py` | QLoRA (E-e settings) and the unsloth merged-16bit step |
| `build_sft.py` | `rat-input` (shards of the examples to rationalize) and `sft` (kept traces → nested `sft-data/sft-{100,300,1000}.jsonl`, locally re-verified, fence re-checked) |
| `p1_score.py` | local scoring (enumerate a kernel's output; size unique (task, tokens) × seeds 1–3, ≤ 4 processes, bv2 worker = the P0 engine; exact-key reuse of P0/AMENDMENT-3 rl-v1.2 rows) |
| `p1_summarize.py` | per-tier tables, decision rule → `score/summary.json`, `score/tables.md` |
| `mock/` | fake llama-server (`fake_server.py`) and the pipeline-smoke inputs/outputs |

## Held-out prompts (step 1)

- 58 prompt files = the 56 held-out tasks of `eval/split.json` (sha256 `809d4bc7…`) + the 2 strict cells, 0 excluded
  (every task has a seed-1-failing anchor).
- Built **before P0 tiering finished** by importing pv0.py read-only: shown anchor = `pv0.shown_anchor` on the
  seed-1 E-TF1 rows (exact-key cache hits on the AMENDMENT-3 T-F1 rows), evidence = `pv0.evidence_for`,
  prompt = `pv0.prompt_for` (= `editcap_run.build_prompt_B(k=1)`, no few-shot), JSON layout = `pv0.build_eval`'s.
  The prompt depends only on seed-1 rows, which P0 never re-sizes, so the result is final.
- Byte equality: 4/4 identical to the P0 smoke's `smoke/eval-out/prompts/` (2 tasks + 2 strict cells),
  `prompts/COMPARE-smoke_eval-out_prompts.json`. The comparison with the full P0 `eval/prompts/` is run when
  P0 writes them (`build_prompts.py compare`) and recorded here.

## Kernels

All: Kaggle T4 ×2, internet on, datasets `circuit-repro-ghtoken`, `-ngspice47`, `-llamacpp-cuda`; the kernel
clones the repo at `REPO_SHA` and aborts on mismatch. `kaggle kernels push -t <s>` caps every session.

| kernel (slug `devavratpatni/circuit-repro-pilot-v0-…`) | kind | what |
|---|---|---|
| `zs` | eval | official `Qwen/Qwen3-14B-GGUF` Q4_K_M (sha256 `500a8806…`, as E-d/R2), llama-server = R2 flags (`-c 16384 --parallel 1 --split-mode layer --n-gpu-layers 999`, no grammar, no seed), R2 two-phase probe, then `p1_gen.py heldout`: CAP-1024 (`EDITCAP_THINK_BUDGET=1024`), `EDITCAP_RECOVER_REASONING=1` (as R2), arm B, k=1, no few-shot, temp 0.7, 8192-token cap, **2 samples × 58 prompts**, sample 1 over all tasks first |
| `smoke-rat` | rat | pipeline smoke: rationalize the 23 pilot-v0 smoke training examples |
| `smoke-sft` | sft | pipeline smoke: 1 epoch on the 23 smoke traces → merge → GGUF Q4_K_M → held-out driver on 4 prompts × 1 sample (not a result) |
| `rat-a`, `rat-b` | rat | rationalize the examples of the nested 1000 subset (two shards, priority 100 → 300 → 1000) |
| `sft100`, `sft300`, `sft1000` | sft | QLoRA on `sft-data/sft-N.jsonl` → LoRA (kernel output) → merged 16-bit → llama.cpp b10636 `convert_hf_to_gguf` f16 → `llama-quantize Q4_K_M` → the **same** held-out run as `zs` (same server flags, same driver, 2 samples × 58) |

### Rationalization (P1.1)

Prompt = the example's training prompt (arm B, k=1) + a "VERIFIED SOLUTION" block with the target netlist and
the instruction to write the designer's derivation (≤ 300 words, first person, never saying a solution was
given) and end with that netlist copied exactly in one fenced block; Qwen3 thinking off via `/no_think`
(the R2 NT soft switch). llama-server `--parallel 4` (4096 tokens per slot), temperature 0.7, ≤ 1280 tokens.
A trace is **kept** iff: exactly one fenced block; its `proposal.round_trip` token sequence equals the verified
target's; the reasoning is 1–512 tokens (server `/tokenize`); no answer-leak phrase (`verified`,
`given/provided … netlist`, `copied`, …). Up to 3 attempts per example. `build_sft.py sft` re-verifies every
kept trace locally (token hash == the example's `target_tok`).

### SFT (P1.3)

E-e settings: `unsloth/Qwen3-14B-unsloth-bnb-4bit` on ONE T4, LoRA r 16 / α 16 / dropout 0 on q,k,v,o,gate,up,down,
unsloth gradient checkpointing, `random_state` 3407, trainable params fp32, fp16 autocast + GradScaler,
bitsandbytes AdamW8bit lr 2e-4 wd 0, batch 1, prompt tokens masked, the E-e custom loop. P1 adds (identical for
100/300/1000): 2 epochs, grad accumulation 4, 10-step linear warmup then linear decay, grad clip 1.0, epoch
shuffle `Random(3407 + epoch)`, max seq 8192. Target = Qwen3 thinking-mode turn
`<think>\n{rationale}\n</think>\n\n{verified fenced netlist}<|im_end|>`.

## Deviations / interpretations (D-Q*)

- **D-Q1 prompts built early.** Generated from the frozen split by pv0's own functions before P0 finished;
  58/58 byte-identical to P0's `eval/prompts/` (closed).
- **D-Q2 rationale placement.** The ≤ 512-token reasoning is the SFT target's `<think>` block and the answer is the
  verified fenced netlist alone (no prose prediction). At eval, CAP-1024 leaves room for it.
- **D-Q3 extra trace filters.** Besides the pre-registered round-trip filter: exactly one fenced block, ≤ 512 reasoning
  tokens (the pre-reg's length bound made a filter), no answer-leak phrase; up to 3 attempts. A subset member
  without a kept trace is dropped from that subset (nested order kept), counts reported.
- **D-Q4 rationalization only of the nested-1000 examples** (the largest subset), not of every train example.
- **D-Q5 SFT schedule.** E-e fixed the stack but not an epoch count or schedule; P1 uses 2 epochs, grad-accum 4,
  warmup 10 + linear decay, clip 1.0 for all three sizes.
- **D-Q6 SFT model quantization.** The SFT models are our own Q4_K_M (merged f16 → `llama-quantize`, no imatrix),
  the baseline is Qwen's official Q4_K_M. Not separately controlled.
- **D-Q7 eval embedded in the SFT kernels.** Each SFT kernel evaluates its own GGUF right after quantizing
  (no 9 GB GGUF transfer); same server flags and driver as `zs`.
- **D-Q8 pipeline smokes.** `smoke-rat` and `smoke-sft` (not in the pre-reg) spent GPU time to de-risk the long
  kernels; their outputs are pipeline checks only.
- **D-Q9 SPICE-min to first feasible (model).** Calls in user order: seed 1 (sample 1, 2), then seed 2, then
  seed 3; invalid samples and repeats cost 0; smoke_run wall seconds under the shared load (as P0's search bar).
- **D-Q11 sft-N sizes.** 6 nested-1000 examples had no kept trace, so the models trained on 99 / 298 / 994
  examples (not 100 / 300 / 1000).
- **D-Q12 slope reading.** `p1_summarize.py` codes "positive" as solved(1000) > solved(100); the pre-reg's
  "curve's slope" is reported per segment (100 → 300 positive, 300 → 1000 flat).
- **D-Q10 kernel/llama-server scope.** As R2, `EDITCAP_RECOVER_REASONING=1` (an empty answer falls back to the
  think text) in every held-out run.

## RESULT (P1.2 + P1.3) — held-out eval, rl-v1.2, seeds 1–3 × 2500, tiers from P0 `eval/tiers.json`

58 held-out items (T1 23 / T2 32 / T3 3, the T3s include the 2 strict cells), 2 samples each; every model ran the
identical driver and llama-server flags (CAP-1024 thinking, arm B, k=1, no few-shot). 1305 rl-v1.2 sizing calls
in total (`score/score.jsonl`, 0 missing rows); tables `score/tables.md`, per-task rows `score/summary.json`.

| model | train ex. | solved (any sample, ≥ 1 seed) | ≥ 2/3 seeds | T1 /23 | T2 /32 | T3 /3 | validity | SPICE-min to 1st feasible, median (mean) | GPU-min / completion, mean | held-out GPU-min total |
|---|---|---|---|---|---|---|---|---|---|---|
| zs (Qwen3-14B Q4_K_M) | 0 | 5 | 3 | 1 | 4 | 0 | 95.7 % | 3.90 (5.49) | 0.98 | 113.7 |
| sft100 | 99 | 9 | 6 | 3 | 6 | 0 | 96.6 % | 1.21 (1.99) | 0.28 | 32.8 |
| sft300 | 298 | **28** | **24** | 10 | 18 | 0 | 99.1 % | 1.23 (1.76) | 0.30 | 34.5 |
| sft1000 | 994 | **28** | **24** | 19 | 8 | **1** | 99.1 % | 1.19 (1.70) | 0.20 | 23.1 |

Per tier, ≥ 2/3 seeds: zs 1/2/0, sft100 2/4/0, sft300 9/15/0, sft1000 16/7/1 (T1/T2/T3).
Search bar (P0 E-c, blind random order, same solved tasks, median SPICE-min): T1 2.75–6.68, T2 3.65–28.8;
all-found medians T1 2.80, T2 27.17. The SFT models reach the first feasible design in ~1.2 SPICE-min median
(usually the first call: sample 1 at seed 1) on the tasks they solve.

**Decision rule (pre-registered): useful fine-tune = YES.** sft1000 − zs = **+23 solved** (+21 at ≥ 2/3 seeds),
≥ 3 required; validity 99.1 % ≥ 95.7 %. **Curve 100 → 300 → 1000: 9 → 28 → 28.** `p1_summarize.py` labels the
slope "positive" (1000 > 100), but the gain is entirely 100 → 300; **300 → 1000 is flat in solve count**
(0 difference, below the 3-task noise floor), while its composition shifted: T1 10 → 19, T2 18 → 8, and the
first T3 solve. By the pre-reg's wording the 300 → 1000 segment is "flat" → change approach rather than only
scale data; the 100 → 300 segment says data helps up to ~300.

Observations (not pre-registered, for interpretation):
- **Sampling variance is large.** sft300 and sft1000 solve only 11 tasks in common; their union is 45/58.
  Two samples per task under-resolve per-task skill. Two zs-solved tasks are not solved by sft1000
  (`t2-wb1020-gain-0046`, `-0207`; sft300 solves both).
- **Novelty vs retrieval.** Valid outputs whose WL equals a training target: zs 1/111, sft100 2/112, sft300 3/115,
  **sft1000 46/115** (67 distinct WLs vs 113 for sft300). sft1000 moved toward reproducing training topologies,
  which fits its T1 (library) gains and T2 losses.
- **Strict cell solved.** sft1000 solved `v2b-wb0824-gain-188` (bench-v2 strict cell, T3; both samples feasible at
  seed 1, sample 1 also at seed 3) with WLs `71b5fb50…` / `e80a332a…`, neither the cell's witness (`999bf945…`)
  nor any training target.
- **Thinking.** The SFT models close their think naturally (`think_stop=word`, ~240 tokens), so they use 0.2–0.3
  GPU-min per completion vs 0.98 for zs (113/116 zs completions hit the 1024 cap).
- **No held-out family in training** (fence 0 hits, `data/fence_check.json`; wb1020 is absent from training entirely).
- Training loss (mean over an optimizer step, first → last): sft100 0.82 → 0.37, sft300 0.96 → 0.28,
  sft1000 0.94 → 0.32; sequences ~1.98k tokens (max 2180), nothing dropped; s/micro-step 10.7 / 12.2 / 10.1.

## Prompt equality with P0 (D-Q1 closed)

`build_prompts.py compare` against P0's `eval/prompts/` (written 2026-10-06): **58/58 byte-identical**,
0 different, 0 absent (`prompts/COMPARE-eval_prompts.json`).

## Rationalization result (P1.1)

`rat-a` + `rat-b` (pinned `0d72ef2dd`): the 1000 examples of the nested-1000 subset of `data/` (1013 examples,
`train-all.jsonl` sha256 `86b5cf02…`). **994/1000 kept** in 1192 calls (kept at attempt 1/2/3: 835/138/21);
every rejection was a leak phrase (198 calls); the 6 examples without a kept trace failed all 3 attempts on a
leak phrase. Reasoning 130–383 tokens (mean 260). Every kept trace re-verified locally (token hash == the
example's `target_tok`, 0 failures); fence re-checked (0 hits). SFT sets (`sft-data/`, nested, same order as
`subsets.json`): **sft-100 = 99, sft-300 = 298, sft-1000 = 994** examples (`sft-data/STATS.json`).

## Reproduce the scoring

```
E=<env wrapper with the crenv vars>   # e.g. a copy of kaggle/campaigns/bench-v12-audit/E-d/envrun.sh
$E python kaggle/campaigns/pilot-v0/P1/p1_score.py enumerate <label> kaggle/campaigns/pilot-v0/P1/kernels/<label>/gen
$E python kaggle/campaigns/pilot-v0/P1/p1_score.py run 4 <label>
$E python kaggle/campaigns/pilot-v0/P1/p1_summarize.py zs sft100 sft300 sft1000
```
Kernel outputs archived in `kernels/<label>/` (gen/, manifest, kernel.log, train.jsonl; the LoRA adapters
(~250 MB each) stay in the Kaggle kernel outputs `devavratpatni/circuit-repro-pilot-v0-sft{100,300,1000}`, `p1/lora-*`).

## GPU-h ledger (cap 30 GPU-h; Kaggle session wall time, rounded up to 0.05 h)

| kernel | version | pinned commit | start (IST) | end | GPU-h | note |
|---|---|---|---|---|---|---|
| zs | 1 | `3166a9566` | 2026-10-05 17:19 | 19:23 | 2.05 | 118 min in-kernel, 116 completions |
| smoke-rat | 1 | `832426423` | 2026-10-05 17:24 | 17:32 | 0.15 | 23/23 kept in 26 calls (3 leak-phrase retries), reasoning 206–323 tokens |
| smoke-sft | 1 | `880eef0fc` | 2026-10-05 17:34 | 18:14 | 0.70 | install route A (E-e pins + torch 2.11.0), 23 micro-steps 9.8 s, peak 11.8 GiB, GGUF Q4_K_M served, 4/4 valid |
| rat-a | 1 | `0d72ef2dd` | 2026-10-07 03:12 | 04:58 | 1.80 | 500 examples, 599 calls, 495 kept, 104.6 min |
| rat-b | 1 | `0d72ef2dd` | 2026-10-07 03:12 | 04:58 | 1.80 | 500 examples, 593 calls, 499 kept, 105.3 min |
| sft100 | 1 | `1685ec6e0` | 2026-10-07 05:01 | 06:43 | 1.70 | 99 ex., 50 opt steps, 37 min train; GGUF 26 min; held-out 33.6 min |
| sft300 | 1 | `1685ec6e0` | 2026-10-07 06:48 | 09:56 | 3.15 | 298 ex., 149 steps, 123 min train; held-out 35.3 min |
| sft1000 | 1 | `1685ec6e0` | 2026-10-07 05:01 | 11:33 | 6.55 | 994 ex., 497 steps, 337 min train (not truncated); held-out 23.9 min |
| **total** | | | | | **17.90** | of the 30 GPU-h cap |

# E-e: can we QLoRA fine-tune Qwen3 on a Kaggle T4? (bench-v12-audit)

Pre-reg: `kaggle/PREREG-BENCH-V12-AUDIT.md` § E-e (frozen 2026-09-26).
Kernel: `kaggle/kernels-editcap/bench-v12-audit-ee-ftsmoke/` (slug
`devavratpatni/circuit-repro-bench-v12-audit-ee-ftsmoke`). There were three pushes, v1 to v3.
Their raw outputs are in `run1/`, `run2/` and `run3/`.

## Verdict (pre-reg decision rule: the largest size that passes the smoke at seq ≥ 4096)

**The learner model is Qwen3-32B.** It is loaded 4-bit as `unsloth/Qwen3-32B-bnb-4bit` and split across
2×T4 with unsloth `device_map="balanced"`. This is a supported option with no custom
engineering. It trains at seq **4096 and 5120**. It runs out of memory at **6144 and 8192**.
The round trip also works: LoRA → GGUF LoRA → our llama-server with the production
`Qwen3-32B-Q4_K_S.gguf` base.

The runner-up is **Qwen3-14B**. It fits on one T4 at **both 4096 and 8192**, and its full
merged round trip works (16-bit merge → GGUF → Q4_K_M → llama-server).
The 8B fallback was not needed and was not run.

Before committing to 32B, note three caveats:
- **The 32B memory margin is very small.** Peak on GPU1 was 14.20 of 14.56 GiB at seq 5120.
- **32B cannot hold a typical full example.** A real example averages about 4.8k tokens:
  1,374 prompt tokens measured with the Qwen tokenizer, plus about 3.4k completion tokens.
  With a 5120 cap, longer thinking traces must be truncated or filtered out.
  14B at 8192 covers essentially every example.
- **32B costs about 3× more GPU time per example than 14B, and it needs both T4s.**

## Results

Each step is one sequence (batch 1, no gradient accumulation). The setup was LoRA r=16, alpha 16, on all 7
projection types, with unsloth gradient checkpointing, fp16 autocast, GradScaler and bnb AdamW8bit.
The usable memory on each T4 is 14.56 GiB.
The "Peak alloc" column is `torch.cuda.max_memory_allocated`; reserved memory is in brackets.
For s/step, the first step is excluded from the median.

| model (4-bit repo) | GPUs | seq | peak alloc GiB | s/step (median) | result |
|---|---|---|---|---|---|
| Qwen3-14B `unsloth/Qwen3-14B-unsloth-bnb-4bit` | 1×T4 | 4096 | 12.25 (12.94) | 21.7 | PASS 10/10 |
| Qwen3-14B | 1×T4 | 8192 | 13.16 (13.92) | 51.0 | PASS 10/10 |
| Qwen3-32B `unsloth/Qwen3-32B-bnb-4bit` | 2×T4 balanced | 4096 | GPU0 8.79 / GPU1 13.89 (14.39) | 51.8 (run1, 5 steps); 61.3 (run2, 10 steps); 66.1 (run3, 3 steps) | PASS |
| Qwen3-32B | 2×T4 balanced | 5120 | 9.10 / 14.20 (14.38) | 81.9 | PASS 3/3 |
| Qwen3-32B | 2×T4 balanced | 6144 | OOM on GPU1 (14.33 at failure) | – | OOM |
| Qwen3-32B | 2×T4 balanced | 8192 | OOM on GPU1 (14.07 at failure) | – | OOM (run1) |
| Qwen3-8B | – | – | – | – | not attempted: 14B passed, and the pre-reg says 8B is only a fallback |

Other measurements:
- **Memory after loading the weights:** 14B used 10.64 GiB. 32B used 6.82 GiB on GPU0 and 11.65 GiB on GPU1. The split is unbalanced, and GPU1 (which holds lm_head) is what limits sequence length.
- **Losses:** every loss was finite and the fp16 loss scale stayed at 32768. The losses are tiny because the synthetic `<think>` padding repeats text, so they say nothing about learning.
- **Trainable parameters:** 64.2M for 14B and 134.2M for 32B.

## Round trip

| model | route | steps | result |
|---|---|---|---|
| 14B (run1) | merged | unsloth `save_pretrained_merged(merged_16bit)`, 29.5 GB, 7.6 min → `convert_hf_to_gguf` f16, 6.0 min → `llama-quantize Q4_K_M`, 13.1 min, 9.0 GB → our llama-server (1 T4) | **OK**. Loaded in 30 s, 21 tok/s. It answered the probe coherently: "A cascode transistor in a low-noise amplifier increases the output impedance and improves the gain…" |
| 32B (run1) | runtime LoRA | `convert_lora_to_gguf --base <bnb snapshot>` | FAIL: `NotImplementedError: Quant method … 'bitsandbytes'`, because the converter read the bnb config |
| 32B (run2) | runtime LoRA | converter fixed with `--base-model-id Qwen/Qwen3-32B` (268 MB LoRA GGUF) → llama-server reading the base straight from the dataset mount | the conversion worked; the server was still loading at the 900 s health timeout |
| 32B (run3) | runtime LoRA | copied the base to local disk first (167 s) → llama-server `--lora`, split across 2×T4 | **OK**. Loaded in 90 s. `/lora-adapters` lists the adapter at scale 1.0, and it gave a coherent completion |

What the round trip does and does not show:
- **It proves the load path, not a change in behaviour.** The 32B adapter was trained for only 3 steps. Its greedy output at LoRA scale 0 and scale 1 was identical, which is expected for such a small adapter.
- **The merged route was not run for 32B.** The disk had room (1.2 TB free), but the merge and CPU quantize would have taken about an hour of GPU-session time. The 14B run already proved the same size-independent pipeline.

## Throughput projection (SFT of 1,000 examples, 1 epoch, batch 1)

| model | seq | s/example | hours per 1,000 | GPU-h/wk budget (30) |
|---|---|---|---|---|
| 14B, 1×T4 | 4096 | 21.7 | **6.0 h** | about 5,000 examples/wk |
| 14B, 1×T4 | 8192 | 51.0 | 14.2 h | – |
| 14B, 1×T4 | real mix (~4.8k tokens, no truncation) | ~27–30 (est.) | ~8 h | – |
| 32B, 2×T4 | 4096 | 52–66 | **14–18 h** | about 1,700–2,000/wk |
| 32B, 2×T4 | 5120 | 81.9 | 22.8 h | – |

Kaggle sessions are capped at 12 h, so a 32B run of 1,000 examples needs at least two resumed sessions.

## Pinned stack (run inside the kernel; nothing installed on the box)

- **Pinned by us:** unsloth 2026.9.11, unsloth_zoo 2026.9.7, transformers 5.5.0, peft 0.21.0, trl 0.24.0, bitsandbytes 0.50.2, accelerate 1.15.0, datasets 4.3.0.
- **Pulled in by the pinned packages:** xformers 0.0.35, cut_cross_entropy 25.1.1, torchao 0.18.0, triton 3.6.0.
- **Kaggle image, kept as-is through a constraints file:** torch 2.10.0+cu128, driver 580.159 (CUDA 13.0).
- **Install route:** "A", meaning a normal resolve with the constraints file.

llama.cpp is at tag b10636, the same build as the dataset `circuit-repro-llamacpp-cuda`. From it:
- `convert_hf_to_gguf.py` and `convert_lora_to_gguf.py` came from a clone of that tag.
- `llama-quantize` was built for CPU inside the kernel.

Full lists: `run*/pip-freeze.txt`, `run*/events.jsonl`.

## Data (held-out fence)

The training rows are **synthetic**, as `build_rows.py` defines:
- The prompts are real arm-B prompts (`editcap_run.build_prompt_B`) built from the 27 cells of the OLD gf180 library `kaggle/editcap-lib-v1a`.
- Each prompt is paired with that cell's archived Qwen answer from `campaigns/editcap-v1-baseline`.
- The `<think>` block is padded with the cell's diagnosis text, repeated, so every sequence is exactly the target length. Prompt tokens are masked out of the loss.

No bench-v1.2 cell and no `claude-solutions/templates` text was used. `build_rows.py` asserts this, and so does the kernel.

## GPU time used

| run | minutes |
|---|---|
| run1 | 51.9 |
| run2 | 38.8 |
| run3 | 13.2 |
| **total** | **≈104 min ≈ 1.75 GPU-h** (about 1.9 with session start-up) |

The first push waited about 3.5 h in the queue behind the two E-d kernels, because Kaggle allows at most 2 batch GPU sessions.

## Deviations from the pre-reg and the task brief

1. **The 32B round trip used the runtime-LoRA route**, not the merged → Q4 route. The merged route was proven on 14B instead. The reason is time, as explained under "Round trip".
2. **Three pushes were needed.**
   - v2 fixed the LoRA converter's base config.
   - v3 copied the base GGUF to local disk, because reads from the dataset mount were slow.
   - Each run re-trained 32B, because the LoRA lived in `/tmp`.
3. **The 32B step counts differ from the planned ~10 per sequence length.**
   - At 4096: 5 steps in run1, 10 in run2, 3 in run3.
   - Extra sequence lengths 5120 and 6144 were added to locate the OOM boundary.
   - 14B ran 10 + 10 as planned.
4. **Training used a custom loop, not TRL's SFTTrainer.** The loop runs the unsloth-patched forward pass with fp16 autocast, GradScaler and AdamW8bit. The per-step memory and time should match what the trainer would show.
5. **The 32B checkpoint is plain bnb-4bit, not unsloth's "dynamic" 4-bit.** The dynamic 32B repo is 39 GB. For 14B, the dynamic version was used as the brief suggested, and the plain 14B fallback was not needed.

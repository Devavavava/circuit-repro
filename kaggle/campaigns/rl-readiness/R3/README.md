# R3: does GRPO for Qwen3-14B LoRA run on one Kaggle T4? (rl-readiness)

Pre-reg: `kaggle/PREREG-RL-READINESS.md` § R3 (frozen 2026-09-28).
Kernel: `kaggle/kernels-editcap/rl-readiness-r3-grpo/` (slug
`devavratpatni/circuit-repro-rl-readiness-r3-grpo`, private). There were six pushes, v1 to v6. Their raw outputs are in `run1/` … `run6/`.
The repo clone inside the kernel was pinned to `519bcf452c27` (the pre-reg commit).
The committed `kernel.py` has `R3_MODE = "vgen"`, which is the v6 push. Set it to `"full"` to re-run the trials of v3.

## Verdict (pre-reg decision rule)

**GRPO-on-Kaggle is FEASIBLE.** The rule was: a step with G ≥ 4 and ≥ 1024 completion tokens completes without OOM. That happened.
- **Configuration:** TRL `GRPOTrainer` through unsloth, Qwen3-14B `unsloth/Qwen3-14B-unsloth-bnb-4bit`, LoRA r=16 on all 7 projections, on **one T4**.
- **Result:** it completed **2/2 steps at G=8 with 1024 completion tokens** (forced full length).
- **Rewards were real:** `proposal.round_trip` ran on all 16 rollouts (16/16 valid). `smoke_run` with 1 seed × 300 evals on bptm45 sized 3 rollouts per step in-kernel.
- **Memory:** peak allocated 13.46 GiB and reserved 14.25 GiB, against 14.56 GiB usable.

**It is feasible but not practical as a single-T4 online loop.** A step takes **1436 s**, and **91% of that is generation**. HF/unsloth generation of a 14B bnb-4bit model on a T4 runs at about 6 tok/s aggregate. That gives **≈ 20 rollouts per GPU-h**.
- **The update itself is cheap:** 94 s per G=8 group, which is ≈ 306 rollouts/GPU-h.
- **Fast (vLLM) generation does not help on a T4** (see its section below).

Conclusion: RL on Kaggle has to use **architecture B**, where generation is decoupled from the TRL loop. The TRL loop keeps the update step. Online GRPO with in-loop generation is not viable on a T4.

## Measurements

The model is Qwen3-14B dynamic bnb-4bit. Weights take **10.64 GiB** after load, out of 14.56 GiB usable. Common settings:
- Prompts: arm-B, k=1, **1378 tokens on average** (range 1330–1517), rendered with `enable_thinking=False`.
- Completions are forced to exactly L tokens (`min_new_tokens=L`), which is the worst case.
- Training setup: TRL 0.24 GRPO, beta=0, loss `bnpo`, fp16, adamw_8bit, unsloth offloaded gradient checkpointing.
- "s/step" is one optimizer step for one prompt × G rollouts, median excluding the first step.

| trial (run) | generation | G | L | micro-batch | result | peak alloc / reserved GiB (nvidia-smi MiB) | s/step | gen s/step | rollouts/GPU-h |
|---|---|---|---|---|---|---|---|---|---|
| **H-G8-L1024 (run3, MAIN)** | HF/unsloth, in chunks of 4 | 8 | 1024 | 1 (grad-accum 8) | **PASS 2/2** | **13.46 / 14.25 (14785)** | **1436** (step 1: 1457) | 1314–1322 | **20** |
| F-G8-L1024 (run3) | none (random tokens: update cost) | 8 | 1024 | 1 | PASS 3/3 | 12.44 / 13.11 | 94 | 0 | 306 (update only) |
| F-G8-L2048 (run3) | none | 8 | 2048 | 1 | PASS 2/2 | 12.96 / 13.71 | 145 | 0 | 199 (update only) |
| F-G8-L3072 (run3) | none | 8 | 3072 | 1 | PASS 2/2 | 13.50 / 14.28 (14785) | 196 | 0 | 147 (update only) |
| F-G16-L1024 (run3) | none | 16 | 1024 | 1 | PASS 2/2 | 12.42 / 13.11 | 192 | 0 | 300 (update only) |
| H-G8-L1024 (run2) | HF, one batch of 8 | 8 | 1024 | 8 | **OOM in generation** (SDPA, 14.37 GiB allocated) | – | – | – | – |
| H-G4-L1024 (run2) | HF, one batch of 4 | 4 | 1024 | 4 (beta 0.001, reference forward) | generation OK (579 s); then **CUDA illegal memory access** in the reference-model forward at 14.24 GiB (memory wall) | – | – | 579 | – |
| V-G8-L1024 (run2) | unsloth `fast_inference` (vLLM 0.19.1 colocated, standby) | 8 | 1024 | 8 | **LOAD OOM**: vLLM weights 10.49 GiB, "No available memory for the cache blocks" at gpu_mem_util 0.76 | – | – | – | – |
| V-G4-L1024 (run2) | vLLM colocated, gpu_mem_util 0.6 | 4 | 1024 | 4 | **LOAD ERROR**: unsloth caps `max_model_len` at 256 and gives the KV cache 0.0 GB; vLLM refuses to start | – | – | – | – |

**OOM boundary on one T4:**
- **Generation:** 8 × (≈1.4k + 1k) tokens in one HF batch runs out of memory. Chunks of 4 fit.
- **Update:** at micro-batch 1 there was no OOM up to L=3072, where the sequence is about 4.5k tokens and peak allocation is 13.50 GiB. G only adds time, because it is gradient accumulation. L > 3072 was not probed. E-e SFT fit at 8192 with 13.16 GiB, so larger L likely fits too.
- **Unsloth's default pattern fails:** micro-batch = G plus a reference-model forward (beta 0.001) failed already at G=4.

**Real-reward sanity (MAIN run, run3):**
- All 16 rollouts had a fenced netlist that round-trips and is novel against the anchor.
- `reward_spice` was 0.05 on average (std 0.14 and 0.08), with no feasible sizing.
- `frac_reward_zero_std` was 0, the loss about 1e-7, and grad-norm 0.098 / 0.095.
- The round-trip reward took 0.22–0.28 s for 8 rollouts.

## Kaggle CPU and in-kernel SPICE sizing (`bench_anchor_prep.smoke_run`, bptm45, clean — nothing else running)

The kernel has **4 vCPUs**: `os.cpu_count()` = `nproc` = sched_affinity = 4, model **Intel Xeon CPU @ 2.00GHz**, and 31 GB RAM.

| call | s/call |
|---|---|
| 1 seed × 300, serial (3 v1a anchors) | **7.25 / 7.41 / 8.26** (mean ≈ 7.6) |
| 1 seed × 600, serial | 14.69 |
| 1 seed × 300, stability-gated spec (`mu_min ≥ 1`, 0.1–20 GHz audit), serial | 7.31 / 7.31 |
| 1 seed × 300, 4 in parallel (4 procs) | 12.8–13.7 each, **13.75 s wall for 4** (≈ 3.4 s/call throughput, ≈ 1,050 calls/h/kernel) |
| inside the GRPO step, 3 in parallel while training | 10.7–11.7 each (10.9 / 11.7 s wall per step) |

For comparison, the same serial call on this box took 5.9–10.5 s (`localtest/spice_bench_local.jsonl`). Parallel calls there took 16–23 s under shared load.

## Does fast (vLLM-style) generation work on T4?

**No, not in any way that helps this model.**
1. **unsloth `fast_inference` (vLLM colocated with training) is impossible for 14B on a 14.56 GiB T4.**
   - What works: vLLM 0.19.1 runs on Turing (TRITON_ATTN backend; FA2 needs sm ≥ 8.0) and loads the bnb-4bit weights (10.49 GiB).
   - What fails: unsloth then leaves the KV cache 0 GB and `max_model_len` 256. Standby mode at gpu_mem_util 0.76 fails with "No available memory for the cache blocks" (run2).
2. **vLLM on a dedicated second T4 works but is not fast** (run6, `vgen.py`).
   - Setup: bnb-4bit, TRITON_ATTN forced, with and without a random r=16 LoRA; 12.9 / 13.1 GiB used.
   - Warm-up: 8 × 64 tokens took 73 s (7.0 tok/s output, prefill-bound) and 81 s with LoRA.
   - The 16 × 1024 forced-token batch **did not finish in about 20 min** on either GPU. That puts the ceiling at ≲ 14 tok/s aggregate, which is no better than the other options below.
   - Run5 showed that plain vLLM picks FLASHINFER on a T4, and its JIT build fails because the image has no nvcc or libcuda stub. TRITON_ATTN had to be forced.
3. **For comparison:**
   - HF/unsloth in-loop, 2 chunks of 4: 8,192 tokens in 1314 s = **6.2 tok/s**.
   - Our llama.cpp `llama-server` with Q4_K_M 14B on 1 T4 (E-e): **21 tok/s single-stream**. It is also the only path with a proven LoRA route: the E-e GGUF-LoRA / merge round trip.

## Architecture-B round size (G=8, 1024 completion tokens, one prompt = one group of 8)

Throughout, a Kaggle T4×2 session-hour is counted as 1 GPU-h, the quota convention used in E-e. The update-phase rate is measured here: 94 s per group, 306 rollouts/h on one T4.

| generation engine (per T4) | gen rollouts/h (both T4s) | update rollouts/h (1 T4) | end-to-end rollouts/h | **per 12 h session** | **per 30 GPU-h week** |
|---|---|---|---|---|---|
| TRL in-loop HF generation (measured MAIN, 1 T4; the other T4 idle) | – | – | 20 | **≈ 240 (30 groups)** | **≈ 600 (75 groups)** |
| llama-server Q4_K_M, 1 stream per T4 (21 tok/s from E-e; 1024/21 ≈ 49 s per rollout) → 2 × 74 | 148 | 306 | ≈ 100 | **≈ 1,200 (150 groups)** | **≈ 3,000 (375 groups)** |
| llama-server with batched `--parallel` (not measured; ~3× aggregate is a guess) | ~440 | 306 | ~180 | ~2,100 | ~5,400 |
| vLLM on a dedicated T4 (≲ 14 tok/s ceiling, run6) | ≲ 100 | 306 | ≲ 75 | ≲ 900 | ≲ 2,250 |

- **End-to-end** means generation and update run as sequential phases in one session: 1/(1/gen + 1/upd).
- **Not included:** per-round overheads. These are model and server loads (60–90 s each), LoRA→GGUF conversion (E-e, minutes), and scoring on the box.
- **Scoring is not a bottleneck:** 8 × 1×300 sizings cost about 30 s of box CPU per group, and the box has 28 cores.
- **Implied round size:** about 1,200 rollouts (150 prompts × G=8) per 12-h Kaggle session, and about 3,000 per 30 GPU-h week, with llama-server generation measured single-stream. Every row is **bounded by generation**. The next measurement worth having is llama-server `--parallel 8` aggregate throughput with the runtime LoRA.

## Pinned versions (installed only inside the kernel; nothing on the box)

- **Main stack (same as E-e):** unsloth 2026.9.11, unsloth_zoo 2026.9.7, transformers 5.5.0, trl 0.24.0, peft 0.21.0, bitsandbytes 0.50.2, accelerate 1.15.0, datasets 4.3.0; xformers 0.0.35, triton 3.6.0, torchao 0.18.0, cut_cross_entropy 25.1.1.
- **Kaggle image (held by a constraints file):** torch 2.10.0+cu128, driver 580.159 (CUDA 13.0), Python 3.12.13.
- **vLLM:** `--system-site-packages` venv `/tmp/r3/venv-vllm` with vllm 0.19.1, transformers 4.57.6, bitsandbytes 0.50.2, flashinfer-python 0.6.6, numba 0.61.2.
  - 0.19.1 is the newest vLLM pinned to torch 2.10.0. vLLM needs transformers < 5 or ≥ 5.5.1, and unsloth needs ≤ 5.5.0, so 4.57.6 is the version both accept.
- **Full lists:** `run3/r3/pip-freeze.txt`, `run*/r3/pip-freeze-vllm-venv.txt`.

## Data and held-out fence

- **Prompts:** 27 real arm-B prompts built with `editcap_run.build_prompt_B(k=1)` from the OLD library `kaggle/editcap-lib-v1a`, which is not a bench library (`build_prompts.py`, embedded in `kernel.py`).
- **Fence checks:** the builder asserts no bench-v1.2 cell and no `claude-solutions/templates` text. The kernel re-checks the prompts against the clone's `editcap-lib-v12-*` (16 held-out cells, 0 violations).
- **Reward sizing** uses each v1a cell's own `spec.yaml` at pdk bptm45.

## GPU time ledger (Kaggle session time, including the failed pushes)

| push | what | session min |
|---|---|---|
| v1 (run1) | wrong pinned sha: `git fetch` failed at 0.1 min | 0.25 |
| v2 (run2) | first full attempt (OOM / vLLM-colocated failures, listed above) | 15.2 |
| v3 (run3) | MAIN PASS + update/OOM probes; vgen died (missing `__main__` guard) | 61.1 |
| v4 (run4) | vgen-only: venv version-check bug | 3.0 |
| v5 (run5) | vgen-only: plain vLLM chose FLASHINFER (JIT impossible) | 11.5 |
| v6 (run6) | vgen-only: vLLM dedicated T4 loads, too slow (timed out) | 28.8 |
| **total** | | **≈ 120 min ≈ 2.0 GPU-h** (under the 2.5 h cap; container start-up adds about 1 min per push) |

## Deviations from the pre-reg and the brief

1. **k=1 edit per completion** instead of the editcap k=3, so that one completion = one candidate = one reward.
2. **Completions are forced to full length** with `min_new_tokens=L`, which suppresses EOS. Every step is therefore a true ≥ 1024-token worst case. Natural thinking-off completion lengths were not measured; R2 covers them.
3. **Settings forced by run2's failures:**
   - beta = 0, so there is no reference model; unsloth's default is 0.001.
   - Micro-batch 1 with gradient accumulation G, instead of unsloth's micro-batch = G.
   - HF generation runs in **chunks of 4** through a small wrapper around `model.generate` inside the kernel. It is not stock TRL.
4. **Update-cost and OOM probes use random-token "completions"** (`--fake-gen`). All rewards are 0 there, so the gradient is 0. Memory and time are representative; learning is not.
5. **Handful of steps:** the MAIN run did **2 steps** at 24 min each, instead of 3–5, to stay within budget.
6. **"The other T4 hosts generation" was tested only as a standalone vLLM throughput test** (run6), not wired into TRL. TRL's server mode syncs merged weights into the vLLM server, which a bnb-4bit server cannot take.
7. **Scoring used v1a cells' specs at bptm45**, while their prompt evidence is from the gf180 era. This does not matter for a smoke test.
8. **Six pushes:**
   - v1: sha typo.
   - v4: a check bug.
   - v5 and v6: the dedicated-vLLM fixes.
   - v3 also hit the vgen guard bug.
9. **The update-only probes stop at L=3072 and G=16;** the upward OOM boundary is not bracketed.

## Local mock (no GPU)

`localtest/extract_and_test.py` pulls the embedded reward and SPICE scripts out of `kernel.py` and runs the reward functions exactly as TRL calls them. It uses real ngspice through the spawn pool: valid / no-fence / broken / anchor-duplicate / bare-fence completions give `[1,0,0,1,1]`, novel `[.5,0,0,0,.5]`, and SPICE > 0 for the novel ones. `envrun.sh` is the env wrapper, pointing at this worktree. `patch_v4.py` is the one-off editor used for kernel v4.

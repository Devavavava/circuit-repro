# rl-readiness R2 kernel (thinking-length cap): launch checklist

Pre-registration: `kaggle/PREREG-RL-READINESS.md`, check **R2**. Budget approved by the user:
at most 1.5 GPU-h (hard cap).

| dir | Kaggle slug | model | runs (cond-sample, in order) |
|---|---|---|---|
| `rl-readiness-r2-think` | `devavratpatni/circuit-repro-rl-readiness-r2-think` (private) | Qwen3-14B Q4_K_M, downloaded at kernel start, sha256 verified | CAP-s1, NT-s1, CAP-s2, NT-s2 |

## What it is based on

This is a clone of the E-d 14B kernel (`bench-v12-audit-ed-14b`). The following are unchanged:

- GGUF URL, size and sha256
- llama-server flags: `-c 16384 --parallel 1 --split-mode layer --n-gpu-layers 999`, no grammar, no seed
- lib `editcap-lib-v12-45nm`, `--pdk bptm45`, `--arm B`, `--k 3`, `--temperature 0.7`, `--max-tokens 8192`
- `EDITCAP_RECOVER_REASONING=1`, `EDITCAP_FEWSHOT=1` (FS only)

The baseline (thinking ON) is the existing E-d 14B-FS run. It is not re-run.

## New conditions

These are additive `editcap_run.py` env flags. When they are unset, the driver output is byte-identical to before.

- **CAP**: `EDITCAP_THINK_BUDGET=1024`. The cap is applied client-side in two phases:
  1. `POST /apply-template` with the model's own chat template.
  2. `POST /completion` with `n_predict=1024` and `stop=["</think>"]`.
  3. `POST /completion` with prompt = template + think text + closer, and `n_predict = 8192 − think tokens`.
     - If the model closed its think within budget, the closer is `</think>`.
     - Otherwise it is Qwen's early-exit sentence plus `</think>\n\n`.

  Per-phase tokens, stop reasons and timings go to `completion.meta.json` → `r2.phases`.
- **NT**: `EDITCAP_NO_THINK=1`. This appends `\n/no_think` (the Qwen3 soft switch) to the user turn. The suffix is
  therefore visible in `prompt.txt`.
- **Both conditions**: `EDITCAP_GEN_ONLY=1`. The kernel does no smoke, size or escalate step, and valid edits are
  archived as `fence_outcome = not_sized_gen_only`. In E-d the in-kernel sizing was recorded only and never used
  for scoring. Scoring is done on this box at seeds 1,2,3 × 2500 bptm45, exactly like E-d.

## Other kernel behaviour

- **Server capabilities**: the kernel logs `llama-server --version` and the `--help` lines that mention
  reasoning, think or budget. The full text is saved to `llama-server-help.txt`. Any native reasoning budget is
  logged only, not used.
- **Probe**: a 64-token two-phase probe runs before the real runs. The kernel aborts if the phase-1 text or the
  template tail has no `<think>`.
- **Wall guard**: no run starts after 70 min wall time, and a running driver is killed at 82 min. Expected wall is
  about 50 min: 3.5 min setup, about 1 min per CAP completion, about 0.4 min per NT completion.
- **Code pin**: `REPO_SHA` is set to the pushed commit that carries the `editcap_run.py` flags. The kernel aborts
  if the clone HEAD does not equal the pin.

## Local mock test (done before the push)

`kaggle/campaigns/rl-readiness/R2/fake_llama_server.py` is a stdlib stand-in for `/v1/chat/completions`,
`/apply-template` and `/completion`. With it:

- **Flags off**: the HEAD driver and the new driver produce identical `prompt.txt`, `raw_output.txt`,
  `completion.meta.json`, edit nets and results row, apart from wall-clock `seconds`/`ts`.
- **CAP**: both the forced-close path (budget 1024 < fake think 1500) and the natural-close path (budget 2000)
  were exercised.
- **NT**: `/no_think` is present in the prompt.
- **Kernel helpers**: `run_env`, `build_inner` and `probe_two_phase` were exercised against the fake server.

## Push / monitor / fetch

```bash
kaggle kernels push -p kaggle/kernels-editcap/rl-readiness-r2-think
kaggle kernels status devavratpatni/circuit-repro-rl-readiness-r2-think
kaggle kernels output devavratpatni/circuit-repro-rl-readiness-r2-think -p kaggle/campaigns/rl-readiness/R2/kernel
```

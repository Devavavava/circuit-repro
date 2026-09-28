# bench-v12-audit E-d kernels -- launch checklist

Pre-registration: `kaggle/PREREG-BENCH-V12-AUDIT.md`, experiment **E-d** (real Qwen
baseline, matched zero-shot vs few-shot). Three kernel dirs share ONE `kernel.py`
that differs only in its CONFIG block:

| dir | Kaggle slug | model | runs (cond-sample, in order) |
|---|---|---|---|
| `bench-v12-audit-ed-32b-zs` | `devavratpatni/circuit-repro-bench-v12-audit-ed-32b-zs` | Qwen3-32B Q4_K_S (dataset `circuit-repro-gguf-qwen32`) | ZS-s1, ZS-s2 |
| `bench-v12-audit-ed-32b-fs` | `devavratpatni/circuit-repro-bench-v12-audit-ed-32b-fs` | Qwen3-32B Q4_K_S (same dataset) | FS-s1, FS-s2 |
| `bench-v12-audit-ed-14b`    | `devavratpatni/circuit-repro-bench-v12-audit-ed-14b`    | Qwen3-14B Q4_K_M (downloaded at kernel start) | ZS-s1, FS-s1, ZS-s2, FS-s2 |

Common config (all three): library `editcap-lib-v12-45nm` (all 16 bench-v1.2
cells), `--pdk bptm45`, `--arm B`, `--k 3`, `--temperature 0.7`,
`--max-tokens 8192`, `EDITCAP_RECOVER_REASONING=1`, llama-server `-c 16384
--parallel 1 --split-mode layer` on 2xT4, no grammar, no `--seed`.

- **ZS** = `EDITCAP_FEWSHOT` removed from the env (driver checks truthiness, so
  it is popped, never set to "0"). **FS** = `EDITCAP_FEWSHOT=1` (existing generic
  worked example, unchanged).
- **Repeats (2 completions per cell x condition):** `editcap_run.py` has no
  repeat flag, so the kernel runs the identical command once per sample into a
  distinct out dir `/kaggle/working/editcap/<COND>-s<N>/`. No seed is sent, so
  llama-server uses a fresh random seed per request; the kernel reports how many
  cells have byte-identical s1/s2 raw outputs (`KERNEL-MANIFEST.json`
  `identical_raw_s1_s2`; expected 0/16).
- **Code pin:** the kernel clones branch `worktree-externals-gf180`, then
  fetches + checks out `REPO_SHA = cc5a836bb26f...` (the PREREG commit) and
  aborts if HEAD != pin. The driver/library/sizer are therefore identical across
  the three kernels regardless of later branch pushes.
- **14B GGUF:** `https://huggingface.co/Qwen/Qwen3-14B-GGUF/resolve/main/Qwen3-14B-Q4_K_M.gguf`
  (official Qwen repo, open), 9,001,752,960 B, sha256
  `500a8806e85ee9c83f3ae08420295592451379b4f8cf2d0f41c15dffeb6b81f0`
  (HF LFS metadata). Downloaded to scratch (`/kaggle/tmp` or `/tmp`, NOT
  `/kaggle/working`); size and sha256 are verified before load, abort on mismatch.
- **In-kernel sizing** = the driver's frozen smoke/base/escalate (40 / 2x300 /
  3x600). RECORDED ONLY -- E-d is scored locally (seeds 1,2,3 x 2500 bptm45).
  Unchanged: prior runs measured ~4.5-5.5 min/cell wall total, LLM-dominated.

## Runtime estimate

32B: ~5 min/cell -> 32 cells ~= 2.7-3.2 h per kernel. 14B: 64 cells at ~2-3.5
min/cell ~= 2.5-4 h (worst case all 8192-token completions ~7.5 h). Soft
deadline: no new run starts after 10.5 h (Kaggle limit 12 h); results are
checkpointed after every cell.

## Pre-push checklist

1. `git ls-tree -r --name-only cc5a836bb | grep -E 'kaggle/(editcap_run.py|bootstrap.sh)$'`
   plus 64 files under `kaggle/editcap-lib-v12-45nm/` (16 cells x 4; no
   INDEX.json -- the driver scans cell dirs), and origin carries the pin
   (`git branch -r --contains cc5a836bb`).
2. Local mock of the exact commands (driver `--mock-llm`, 1 cell per condition):
   ZS prompt has no `WORKED EXAMPLE` block, FS prompt has it.
3. No other E-d kernel with the same slug RUNNING/QUEUED
   (`kaggle kernels status <slug>`); GPU quota (30 GPU-h/wk) covers ~9-10 h.
4. Datasets attached (ghtoken, ngspice47, llamacpp-cuda, + gguf-qwen32 for 32B).

## Push / monitor / fetch

```bash
kaggle kernels push -p kaggle/kernels-editcap/bench-v12-audit-ed-32b-zs
kaggle kernels push -p kaggle/kernels-editcap/bench-v12-audit-ed-32b-fs
kaggle kernels push -p kaggle/kernels-editcap/bench-v12-audit-ed-14b
kaggle kernels status devavratpatni/circuit-repro-bench-v12-audit-ed-32b-zs
kaggle kernels output devavratpatni/circuit-repro-bench-v12-audit-ed-32b-zs -p kaggle/campaigns/bench-v12-audit/E-d/32b-zs
kaggle kernels output devavratpatni/circuit-repro-bench-v12-audit-ed-32b-fs -p kaggle/campaigns/bench-v12-audit/E-d/32b-fs
kaggle kernels output devavratpatni/circuit-repro-bench-v12-audit-ed-14b    -p kaggle/campaigns/bench-v12-audit/E-d/14b
```

Output layout: `editcap/<COND>-s<N>/results-B.jsonl` (16 rows each) +
`editcap/<COND>-s<N>/adjudication/<spec>/B/{prompt,raw_output,diagnosis}.txt,
edit<i>.net, edit<i>.meta.json, completion.meta.json`, plus
`editcap/KERNEL-MANIFEST.json` (config, clone head, GGUF provenance, per-run rc /
minutes / counts) and `llama-server.log`. Archive VERBATIM; score locally.

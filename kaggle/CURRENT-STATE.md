# START HERE — current state (2026-09-26, audit-corrected)

Entry point for a fresh session/agent. Read this first, then
`PREREG-BENCH-V12-AUDIT.md` (what is running now) and
`PLAN-topology-selfimprovement.md` (the direction). Everything else in `kaggle/*.md`
is historical record (how we got here), not the live state.

## The live state

- **Process:** the benchmark runs on **native bptm45 (45 nm)**, NOT gf180. gf180
  (180 nm) was a *process wall* for these 45 nm-authored specs; re-basing removed it.
- **Sizer is deterministic** — the SPICE reward signal was noisy until gf180's
  Monte-Carlo statistical models were pinned off (`lna/size.py::eval_metrics`,
  commit `49ab2b9f`). bptm45 native is deterministic (re-verified 2026-09-26:
  bit-identical metrics across 7 separate processes). **Do not run sizing with gf180
  MC on.** Cost ≈ 36–48 s per 2500-eval sizing call, ≈ 200 candidates/h at 3 seeds on
  8 local processes.
- **Live benchmark = bench-v1.2** (`kaggle/editcap-lib-v12-45nm/`, 16 cells; summary
  `kaggle/campaigns/editcap-v1-baseline/bench-v1.2-45nm-survivors.json`, built by
  `kaggle/build_bench_v12_summary.py`). Each cell's shown anchor fails to size and a
  reference template solves. **Read the audit caveats before quoting "Claude 16/16":**
  - cells were **kept only if** anchor-fails ∧ template-solves → 16/16 is **by
    construction**;
  - "Claude" = **two fixed templates** → the benchmark tests exactly **two moves**:
    wideband = shown current-reuse anchor **+ one resistor drain→gate** (`R Rf n2 n1`);
    narrowband = existing library anchor **a1** (ind-degen cascode) + 2 caps;
  - template solves are **razor-thin** (worst margin +4e-5 … +1.2e-2), likely because
    the sizing objective only penalizes violation (`lna/size.py:1436`);
  - the 5-family anchor null was never run on these specs.
  Being measured now: headroom (E-a), 5-anchor null (E-b), brute-force single-edit
  search bar (E-c) — `PREREG-BENCH-V12-AUDIT.md`.
- **Where models stand:** Claude-templates 16/16 (by construction). **Qwen on
  bench-v1.2 has NOT been measured** — the old "~0/16" was extrapolated from gf180
  (0/53) and the 45 nm 31-survivor partial (0/26). The few-shot "3/8 solved" had no
  matched zero-shot control and margins < 0.02. Real matched ZS/FS baseline for
  Qwen3-32B and Qwen3-14B = E-d (running on Kaggle).
- **Learner path (user ruling 2026-09-26):** fine-tune a **smaller model that fits
  Kaggle T4** — the largest that actually trains, floor 8B ("don't go too small").
  Qwen-32B SFT has no hardware path (2×T4, 30 GPU-h/wk, no FT code). Feasibility =
  E-e (running).
- **Next phase = verifier-guided self-improvement** (`PLAN-topology-selfimprovement.md`),
  re-scoped by the audit: the simulator is ~20× cheaper per candidate than a Qwen
  sample (~5.4 min/completion on Kaggle, ~90% of tokens are Qwen3 thinking), so the
  data engine should be search-heavy / LLM-light.

## Current assets (use these)

| What | Path |
|---|---|
| Running experiments (pre-reg) | `kaggle/PREREG-BENCH-V12-AUDIT.md` → `kaggle/campaigns/bench-v12-audit/` |
| The plan (next phase) | `kaggle/PLAN-topology-selfimprovement.md` |
| Live benchmark (16 cells) | `kaggle/editcap-lib-v12-45nm/` + summary json above |
| Deterministic verifier | `kaggle/bench_anchor_prep.py::smoke_run` (pdk=bptm45) |
| Single-candidate solve harness | `kaggle/mysolve.py` (finds v12/v11 cells; picks bptm45 for `*-45nm` libs; `MYSOLVE_PDK` overrides) |
| Reference templates (**EVAL-ONLY**, never training data) | `kaggle/claude-solutions/templates/` |
| Achievable-spec calibration / mass-gen | `kaggle/calibrate_bench_wb.py`, `_nb.py`, `build_bench_v12.py` (NB: rmtree's the lib, hard-coded worktree path) |
| Topology-repertoire analyzer | `kaggle/analyze_qwen_vs_claude_topo.py` (shunt-fb detector undercounts R from a tank node → gate) |
| Kaggle kernel pattern (bptm45, 8192 tok) | `kaggle/kernels-editcap/editcap-v11-45nm/` |
| Full running narrative | memory `circuit-repro-editcap` |

## Superseded / historical (do NOT treat as current)

- **`BENCH-V1-FREEZE.md`** — the OLD bench-v1 (gf180, 53 survivors / LNA-only).
  Superseded by the 45 nm re-base + bench-v1.2. (Its findings on why PA/mixer/balun
  were deferred remain historically valid.)
- The 31-survivor gf180 set and the gf180 Claude-ceiling (~1/53) — superseded by the
  45 nm re-base; kept as journey evidence under
  `kaggle/campaigns/editcap-v1-baseline/` (fair-resize, exp1/exp2, triage,
  31survivor-ceiling, qwen-45nm-partial, fewshot-diagnostic).
- `CAMPAIGN-*.md` — historical campaign logs (editcap v0/v1/v2, editmoves, selflearn,
  x0, PDK, class-objective, etc.). Record of prior phases; not the live plan.

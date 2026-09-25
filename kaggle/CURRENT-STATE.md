# START HERE — current state (2026-09-25)

Entry point for a fresh session/agent. Read this first, then
`PLAN-topology-selfimprovement.md`. Everything else in `kaggle/*.md` is
historical record (how we got here), not the live state.

## The live state

- **Process:** the benchmark runs on **native bptm45 (45 nm)**, NOT gf180. gf180
  (180 nm) was a *process wall* for these 45 nm-authored specs; re-basing removed it.
- **Sizer is deterministic** — the SPICE reward signal was noisy until gf180's
  Monte-Carlo statistical models were pinned off (`lna/size.py::eval_metrics`,
  commit `49ab2b9f`). bptm45 native is deterministic. **Do not run sizing with gf180
  MC on.**
- **Live benchmark = bench-v1.2** (`kaggle/editcap-lib-v12-45nm/`, 16 cells): each
  cell's shown anchor **fails** to size (topology-fix required) yet a better topology
  **solves** (achievable). Anchor 0/16, **Claude 16/16**, physically-walled tiers
  removed. This is the held-out ceiling test.
- **Where models stand on it:** Qwen ~0/16, Claude (strong-model + tools) 16/16.
  Capability gap: Qwen reaches narrowband **cascode+tank** (a reliability gap) but
  **never** wideband **resistive shunt-feedback** (a missing-move gap; few-shot showed
  it's *knowledge* not capacity — but hand-teaching topologies was ruled out as
  non-scalable).
- **Next phase (planned, handoff) = verifier-guided self-improvement:** learn general
  topology-fixing by search against the sizer (free verifier), at the level of coherent
  whole-circuit bundles, with mutate-then-repair for novelty. Full plan +
  asset paths + phases: **`PLAN-topology-selfimprovement.md`**.

## Current assets (use these)

| What | Path |
|---|---|
| The plan (next phase) | `kaggle/PLAN-topology-selfimprovement.md` |
| Live benchmark (16 cells) | `kaggle/editcap-lib-v12-45nm/` |
| Deterministic verifier | `kaggle/bench_anchor_prep.py::smoke_run` (pdk=bptm45) |
| Single-candidate solve harness | `kaggle/mysolve.py` (`MYSOLVE_PDK=bptm45`) |
| Claude reference solutions | `kaggle/claude-solutions/` |
| Achievable-spec calibration / mass-gen | `kaggle/calibrate_bench_wb.py`, `_nb.py`, `build_bench_v12.py` |
| Topology-repertoire analyzer | `kaggle/analyze_qwen_vs_claude_topo.py` |
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

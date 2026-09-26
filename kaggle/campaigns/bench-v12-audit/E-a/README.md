# E-a — Headroom of the reference (template) solutions on bench-v1.2

Pre-registered in `kaggle/PREREG-BENCH-V12-AUDIT.md` (frozen 2026-09-26). Era stamp
(git HEAD at start) = `cc5a836bb26fbfef4f128777945ebdae39c3fb66` (on every row of `results.json`).

## Method (as pre-registered)
- 16 cells of `kaggle/editcap-lib-v12-45nm/`; candidate = the cell's template
  (`claude-solutions/templates/wideband_shunt_feedback.net` for `v12-wb-*`,
  `narrowband_cascode_tank.net` for `v12-nb-*`), tokens via `proposal.round_trip`.
- For δ ∈ {0 (untightened), 0.02, 0.05, 0.10}: every constraint not marked
  `status: unsupported` is moved inward by δ·`Spec._scale(c)` (scale of the ORIGINAL
  limit: `min += δ·scale`, `max -= δ·scale`), written to a temp YAML under `$TMPDIR/specs/`
  (library never modified).
- Engine `bench_anchor_prep.smoke_run(tokens, spec, seed, 2500, "bptm45")`, seeds 1,2,3,
  feasible = `result["feasible"]` (judged against the tightened spec). Margins are
  `mysolve._margins` against the ORIGINAL spec (`worst`, `binding`, `margins`) and also
  against the tightened spec (`worst_vs_tightened`).
- Headroom = largest δ with ≥1 feasible seed (0 if only δ=0 passes). EDGE ⇔ headroom < 0.02.
- 192 runs (16 × 4 δ × 3 seeds), 0 unsizable, 0 exceptions, 0 sim failures.

## Results

| cell | d=0 feas seeds | d=0 best worst-margin (binding) | d=0.02 | d=0.05 | d=0.10 | headroom | EDGE |
|---|---|---|---|---|---|---|---|
| v12-nb-f15-g12 | 3/3 | +0.0156 (s11_db) | 3/3 | 3/3 | 3/3 | ≥0.10 | - |
| v12-nb-f15-g14 | 3/3 | +0.0039 (s11_db) | 3/3 | 3/3 | 3/3 | ≥0.10 | - |
| v12-nb-f15-g16 | 3/3 | +0.0100 (s11_db) | 3/3 | 3/3 | 3/3 | ≥0.10 | - |
| v12-nb-f15-g18 | 3/3 | +0.0011 (s11_db) | 3/3 | 3/3 | 3/3 | ≥0.10 | - |
| v12-nb-f24-g12 | 3/3 | +0.0619 (s11_db) | 3/3 | 3/3 | 3/3 | ≥0.10 | - |
| v12-nb-f24-g14 | 3/3 | +0.0085 (s11_db) | 3/3 | 3/3 | 3/3 | ≥0.10 | - |
| v12-nb-f24-g16 | 3/3 | +0.0275 (s11_db) | 3/3 | 3/3 | 3/3 | ≥0.10 | - |
| v12-nb-f24-g18 | 3/3 | +0.0119 (s11_db) | 3/3 | 3/3 | 3/3 | ≥0.10 | - |
| v12-wb-s11n10-g10-b0530 | 3/3 | +0.0002 (s11_max_db) | 1/3 | 0/3 | 0/3 | 0.02 | - |
| v12-wb-s11n10-g10-b0824 | 3/3 | +0.0007 (s11_max_db) | 3/3 | 3/3 | 3/3 | ≥0.10 | - |
| v12-wb-s11n10-g12-b0824 | 3/3 | +0.0022 (s11_max_db) | 2/3 | 2/3 | 0/3 | 0.05 | - |
| v12-wb-s11n11-g10-b0824 | 3/3 | +0.0418 (s11_max_db) | 3/3 | 3/3 | 3/3 | ≥0.10 | - |
| v12-wb-s11n11-g12-b0824 | 3/3 | +0.0008 (s21_db) | 1/3 | 0/3 | 0/3 | 0.02 | - |
| v12-wb-s11n8-g10-b0530 | 3/3 | +0.0006 (s11_max_db) | 3/3 | 3/3 | 2/3 | ≥0.10 | - |
| v12-wb-s11n8-g12-b0530 | 3/3 | +0.0088 (s11_max_db) | 0/3 | 0/3 | 0/3 | 0 | **EDGE** |
| v12-wb-s11n9-g10-b0530 | 3/3 | +0.0005 (s11_max_db) | 2/3 | 2/3 | 0/3 | 0.05 | - |

"≥0.10" = feasible at the largest δ tested (the pre-registered grid stops at 0.10).

## Decision-rule verdict
**EDGE cells: 1/16 (v12-wb-s11n8-g12-b0530) < 8/16 → bench-v1.2 does NOT need
re-calibration with a margin cushion** under the pre-registered rule.

Observations (not part of the rule):
- δ=0 margins reproduce the audit (thin, +2e-4..+6e-2), but the thinness is an artefact
  of the violation-only objective: at every δ the feasible winners land just above the
  tightened limit (worst − δ: median +0.002..+0.004, max +0.12 over 108 feasible
  tightened runs). All 8 narrowband cells and 3 wideband cells have
  ≥10 % headroom.
- Wideband b0530/b0824 cells with the g12 / S11≤−10 corner are the tight ones
  (headroom 0.02–0.05, seed-dependent); s11n8-g12-b0530 fails at δ=0.02 on all seeds.
- Determinism: the 12 δ=0 runs overlapping `/home/dpatni/.claude/jobs/7cd7ffc3/tmp/out/e3_*_template_*`
  (4 cells × 3 seeds) reproduced those worst margins bit-identically.

## Files
- `results.json` — 192 rows (exp, cell, cand, cand_src, delta, seed, budget, pdk, era, secs,
  feasible, worst, binding, worst_vs_tightened, margins, metrics, n_evals, n_sim_fail, ...).
- `verdicts.json` — per-cell headroom / EDGE / feasible-seed counts.
- `audit_drv.py` (driver: `jobs`/`run`/`collect`), `summarize.py` (table + verdict),
  `one.sh`, `mkjobs.sh`, `all.sh`, `collect.sh` (wrappers; shared with E-b).

## Commands
```
/tmp/cr-7cd7ffc3-ab/mkjobs.sh      # audit_drv.py jobs E-a / E-b -> jobs.txt (432 lines)
/tmp/cr-7cd7ffc3-ab/all.sh         # xargs -P 4 -L 1 one.sh  (E-a then E-b, 4 procs max)
/tmp/cr-7cd7ffc3-ab/collect.sh E-a # audit_drv.py collect + summarize.py
```
Env: `crenv.sh` (python 3.11 `cr` env, ngspice 47, LNA_DEPS_ROOT, OMP/OPENBLAS/MKL=1),
`TMPDIR=/tmp/cr-7cd7ffc3-ab`, `AUDIT_ERA=<HEAD sha>`. Raw per-run JSONs in `/tmp/cr-7cd7ffc3-ab/raw/`.

## Wall time
E-a ≈ 55 min wall (13:29–14:24 IST, 4 procs), 13,005 CPU-s (27–90 s per run; wideband
slower). Combined E-a+E-b batch: 7,145 s (119 min).

## DEVIATIONS
1. The 12 δ=0 runs already available in `/tmp/.../out/` were **re-run** (not reused) so every
   row carries the same era stamp; results are bit-identical (checked).
2. One δ=0.02 seed-1 run (v12-nb-f15-g12) was executed as a smoke test of the driver before
   the batch; it is the row used (deterministic engine, same code).
3. Implementation note: the sizer loads the temp YAML, so its internal violation
   normaliser uses `_scale` of the tightened limit (differs by ≤10 % of scale); feasibility
   is sign-based and unaffected. Reported margins use the ORIGINAL scale as pre-registered.
4. Float edge: a row feasible against the tightened spec may show an original-scale worst
   margin of δ − 1e-16 (e.g. 0.019999999999999928); the pre-registered criterion
   (`result["feasible"]`) is what counts.

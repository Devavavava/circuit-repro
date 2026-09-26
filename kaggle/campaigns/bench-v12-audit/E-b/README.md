# E-b — 5-anchor null on the 16 bench-v1.2 specs

Pre-registered in `kaggle/PREREG-BENCH-V12-AUDIT.md` (frozen 2026-09-26). Era stamp
(git HEAD at start) = `cc5a836bb26fbfef4f128777945ebdae39c3fb66` (on every row of `results.json`).

## Method (as pre-registered)
- Anchors: the 5 LNA families of `kaggle/bench-anchors/MANIFEST.json`
  (`classes.lna.families`: a1 inddegen-cascode, a2 current-reuse, a3 shunt-feedback,
  a4 twostage, a5 commongate), tokens from each family's `tokens_file` (same loading as
  `bench_null_filter.py` / `bench-null-bptm45/`).
- Specs: the 16 untouched `kaggle/editcap-lib-v12-45nm/<cell>/spec.yaml`.
- Engine `bench_anchor_prep.smoke_run(tokens, spec, seed, 2500, "bptm45")`, seeds 1,2,3
  all run; feasible = `result["feasible"]`; margin = `mysolve._margins` (normalized worst,
  binding metric = argmin).
- RETRIEVAL cell ⇔ any (anchor, seed) feasible.
- 240 runs (16 × 5 × 3): **0 unsizable**, 0 exceptions, 0 sim failures.

## Results (feasible seeds / best worst-margin over seeds (binding metric))

| cell | a1 inddegen-cascode | a2 current-reuse | a3 shunt-feedback | a4 twostage | a5 commongate | verdict |
|---|---|---|---|---|---|---|
| v12-nb-f15-g12 | 2/3 +0.0129 (s11_db) | 3/3 +0.0109 (s11_db) | 0/3 -0.4594 (s11_db) | 3/3 +0.0316 (idd_ma) | 0/3 -0.2954 (s21_db) | RETRIEVAL (a1,a2,a4) |
| v12-nb-f15-g14 | 3/3 +0.0048 (idd_ma) | 3/3 +0.0030 (s11_db) | 0/3 -0.4289 (s11_db) | 3/3 +0.0199 (s11_db) | 0/3 -0.3960 (s21_db) | RETRIEVAL (a1,a2,a4) |
| v12-nb-f15-g16 | 3/3 +0.0196 (s11_db) | 3/3 +0.0071 (s11_db) | 0/3 -0.4628 (s21_db) | 3/3 +0.0830 (nf_db) | 0/3 -0.4718 (s21_db) | RETRIEVAL (a1,a2,a4) |
| v12-nb-f15-g18 | 2/3 +0.0018 (s11_db) | 2/3 +0.0013 (s21_db) | 0/3 -0.5217 (s21_db) | 3/3 +0.0270 (idd_ma) | 0/3 -0.5311 (s21_db) | RETRIEVAL (a1,a2,a4) |
| v12-nb-f24-g12 | 3/3 +0.0992 (nf_db) | 3/3 +0.2862 (nf_db) | 0/3 -0.4652 (s11_db) | 2/3 +0.0309 (nf_db) | 0/3 -0.2101 (s21_db) | RETRIEVAL (a1,a2,a4) |
| v12-nb-f24-g14 | 3/3 +0.0165 (s11_db) | 3/3 +0.2055 (s21_db) | 0/3 -0.4696 (s11_db) | 3/3 +0.0226 (idd_ma) | 0/3 -0.3229 (s21_db) | RETRIEVAL (a1,a2,a4) |
| v12-nb-f24-g16 | 3/3 +0.0066 (s11_db) | 3/3 +0.0033 (s11_db) | 0/3 -0.4695 (s11_db) | 3/3 +0.0419 (idd_ma) | 0/3 -0.4078 (s21_db) | RETRIEVAL (a1,a2,a4) |
| v12-nb-f24-g18 | 3/3 +0.0326 (s11_db) | 3/3 +0.0108 (s11_db) | 0/3 -0.5234 (s21_db) | 3/3 +0.0338 (idd_ma) | 0/3 -0.4733 (s21_db) | RETRIEVAL (a1,a2,a4) |
| v12-wb-s11n10-g10-b0530 | 0/3 -0.9551 (s11_max_db) | 0/3 -0.3622 (s11_max_db) | 0/3 -0.2989 (s11_max_db) | 0/3 -0.8384 (s11_max_db) | 0/3 -4.0045 (s21_ripple_db) | synthesis |
| v12-wb-s11n10-g10-b0824 | 3/3 +0.0011 (s11_max_db) | 0/3 -0.0383 (s11_max_db) | 0/3 -0.2121 (s11_max_db) | 0/3 -0.6241 (s11_max_db) | 0/3 -0.7895 (s11_max_db) | RETRIEVAL (a1) |
| v12-wb-s11n10-g12-b0824 | 1/3 +0.0004 (nf_db) | 0/3 -0.0509 (s11_max_db) | 0/3 -0.2110 (s11_max_db) | 0/3 -0.6844 (s11_max_db) | 0/3 -0.7895 (s11_max_db) | RETRIEVAL (a1) |
| v12-wb-s11n11-g10-b0824 | 0/3 -0.0479 (s11_max_db) | 0/3 -0.2876 (s11_max_db) | 0/3 -0.2737 (s21_db) | 0/3 -0.6989 (s11_max_db) | 0/3 -0.7995 (s11_max_db) | synthesis |
| v12-wb-s11n11-g12-b0824 | 0/3 -0.0490 (s11_max_db) | 0/3 -0.1695 (s11_max_db) | 0/3 -0.2834 (s11_max_db) | 0/3 -0.9452 (s11_max_db) | 0/3 -0.7994 (s11_max_db) | synthesis |
| v12-wb-s11n8-g10-b0530 | 0/3 -0.9525 (s11_max_db) | 0/3 -0.2086 (s11_max_db) | 0/3 -0.2214 (s21_db) | 0/3 -0.7789 (s11_max_db) | 0/3 -4.0046 (s21_ripple_db) | synthesis |
| v12-wb-s11n8-g12-b0530 | 0/3 -0.9303 (s11_max_db) | 0/3 -0.2393 (s11_max_db) | 0/3 -0.3525 (s21_db) | 0/3 -0.7973 (s11_max_db) | 0/3 -4.0032 (s21_ripple_db) | synthesis |
| v12-wb-s11n9-g10-b0530 | 0/3 -0.9480 (s11_max_db) | 0/3 -0.2953 (s11_max_db) | 0/3 -0.2189 (s21_db) | 0/3 -0.8142 (s11_max_db) | 0/3 -3.7463 (s21_ripple_db) | synthesis |

## Decision-rule verdict
**RETRIEVAL cells: 10/16** — all 8 narrowband cells (each solved by a1, a2 AND a4) and
2 wideband cells (v12-wb-s11n10-g10-b0824, v12-wb-s11n10-g12-b0824; a1 only, thin
margins +0.0011 / +0.0004, the latter 1/3 seeds). These must be labelled RETRIEVAL.
**Synthesis benchmark = 6 non-RETRIEVAL cells, all wideband:**
v12-wb-s11n10-g10-b0530, v12-wb-s11n11-g10-b0824, v12-wb-s11n11-g12-b0824,
v12-wb-s11n8-g10-b0530, v12-wb-s11n8-g12-b0530, v12-wb-s11n9-g10-b0530.

Cross-reference with E-a (not part of this rule): of the 6 synthesis cells,
v12-wb-s11n8-g12-b0530 is the single E-a EDGE cell (template headroom 0).

Context: the narrowband calibration (`kaggle/calibrate_bench_nb.py`) only tested the
shown common-gate anchor (a5-like, `editcap-lib-v1a/bnl-1575-diag-t0/anchor.net`), which
indeed fails every nb cell here (a5 0/3, margins −0.21..−0.53); the library's other
families were never checked, hence 8/8 nb cells turn out RETRIEVAL. The closest wideband
anchor miss is a1 on the b0824 S11≤−11 cells (−0.048/−0.049).

## Files
- `results.json` — 240 rows (exp, cell, cand = anchor family, cand_src = tokens file, seed,
  budget, pdk, era, secs, feasible, not_sizable, worst, binding, margins, metrics,
  n_evals, n_sim_fail, ...). `delta` is always 0.
- `verdicts.json` — per-cell RETRIEVAL flag + solving anchors.
- `audit_drv.py`, `summarize.py`, `one.sh`, `mkjobs.sh`, `all.sh`, `collect.sh` — copies of
  the shared E-a/E-b driver and wrappers.

## Commands
```
/tmp/cr-7cd7ffc3-ab/mkjobs.sh      # audit_drv.py jobs E-b -> 240 jobs appended to jobs.txt
/tmp/cr-7cd7ffc3-ab/all.sh         # xargs -P 4 -L 1 one.sh  (ran after E-a in the same batch)
/tmp/cr-7cd7ffc3-ab/collect.sh E-b # audit_drv.py collect + summarize.py
```
Env: `crenv.sh`, `TMPDIR=/tmp/cr-7cd7ffc3-ab`, `AUDIT_ERA=<HEAD sha>`, 4 procs max.

## Wall time
E-b ≈ 64 min wall (14:24–15:28 IST, 4 procs), 15,272 CPU-s (≈54–90 s per run).
Combined E-a+E-b batch: 7,145 s (119 min).

## DEVIATIONS
None of substance. Note: `MANIFEST.json` is stamped `pdk: gf180mcu`; its token files are
structure-only and were sized with the `bptm45` override exactly as in the prior
`bench-null-bptm45/` run and as the pre-reg's "bptm45 LNA anchors" wording specifies.

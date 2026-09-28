# stability-gate: opt-in WIDE stability check in the verifier (user-approved 2026-09-28)

Base commit: `d61440d8` plus the uncommitted `kaggle/bench_anchor_prep.py` change that this directory's commit adds. Rows carry `era: unknown` because `AUDIT_ERA` was not exported. Run on 2026-09-28 with at most 6 parallel sizing processes and `TMPDIR=/tmp/cr-7cd7ffc3-stab`.

## What changed (only `kaggle/bench_anchor_prep.py`; `lna/` untouched)

- **Trigger (`stab_gate_on`).** The gate runs only when the spec constrains `mu_min` and that constraint is not marked `status: unsupported`. Specs without it return exactly the historical `smoke_run` dict.
- **Sizer already optimizes toward `mu_min`.** Verified: `make_objective.objective_func` returns `spec.objective(m)`, and `Spec.feasible/objective` iterate over every constraint name. An in-band `mu_min: {min: 1}` therefore already enters the objective. `m["mu_min"]` is the in-band value from `extract.run_and_extract`.
- **Wide audit.** After `smoke_run` picks its winner (ungated endpoint re-eval at `bx`), the gate calls `extract.measure_stability(body, decode(bx), f0, 1e8, 2e10, npts=401)`.
  - `body` is the `prepared_body` that the sizer simulated.
  - The params get the same gf180 MC-off pins that `eval_metrics` adds; this is a no-op for bptm45.
  - The window is widened to include the spec band if the band falls outside 0.1–20 GHz. For every bench cell it stays 0.1–20 GHz.
  - `stab_wide_ok` means the wide `mu_min` meets the spec's own `mu_min` limit. If `measure_stability` returns None, the check fails.
- **False-negative guard.** This applies when the winner is spec-feasible but unstable over the wide window.
  1. The other spec-feasible points in `points`, the per-eval hook of the same run, are sorted by `spec.objective` (best first, deduplicated on x, excluding the winner). At most 30 of them are scanned.
  2. Each scanned point gets one wide sim.
  3. The first point that is stable over the wide window is re-measured through the same ungated `evaluate(x)` path. It replaces the winner if that full re-measure is still spec-feasible.
  4. No sizing evals are added.
- **Result keys added (gated runs only):**
  - `spec_feasible`, `stab_window`, `stab_wide` (the full `measure_stability` dict)
  - `mu_min_wide`, `k_min_wide`, `delta_max_wide`
  - `stab_wide_ok`, `stab_points_checked`, `stab_winner_replaced`
  - `stab_replacement`: point index, x, objective, and the replaced winner's metrics and wide stability
  - `feasible` becomes `spec_feasible AND stab_wide_ok`.
- **Helper.** `stability_spec(src, out_dir=None, mu_min=1.0)` writes a copy of a spec with `mu_min: {min: 1.0}` added, by default to `$TMPDIR/stab-specs/`. It validates the copy and never modifies the source.

## Other feasibility deciders

| decider | status |
|---|---|
| `kaggle/mysolve.py` | Routes through `smoke_run`, so it is gated. `_margins` also prints the in-band `mu_min` margin. |
| `calibrate_bench_wb.py`, `calibrate_bench_nb.py`, `build_bench_v12.py`, `triage_anchors.py`, `fair_resize.py`, `exp1_rescore.py`, `E-a`/`E-b`/`E-c`/`E-d` drivers | All route through `smoke_run` and use `res["feasible"]`, so they are gated. |
| `kaggle/bench_null_filter.py` | Calls `smoke_run`, but line 137 recomputes `spec.feasible(res["metrics"])`. That recomputation sees only the **in-band** `mu_min` and not the wide gate. This is a gap: use `res["feasible"]` instead. |
| `kaggle/editcap_run.py` (in-kernel) | Goes through `driver.size_candidate`, then `solve_spec.size_tokens`, **not** `smoke_run`. A `mu_min` spec is gated **in-band only** there. This is a gap and is not wired. |

## (a) Regression (lib specs, no `mu_min`)

- **Full-dict equivalence** (`equiv.json`). The HEAD `smoke_run` and the new one were run in the same process at budget 300 on the 4 cases below. All 4 produced identical `json.dumps` of the complete result dict.
- **Against the recorded rows at 2500 evals.** Metrics dict and `feasible` are both identical to the recorded row, with no extra keys, for:
  - E-a: wb template on `v12-wb-s11n10-g10-b0530`, seed 1
  - E-b: wb anchor a1 on `v12-wb-s11n10-g10-b0824`, seed 1
  - E-b: nb anchor a1 on `v12-nb-f15-g16`, seed 1
  - E-c: `add L VIN1-n1` on `v12-nb-f15-g16`, seeds 1, 2 and 3

## (b) Negative control: `v12-nb-f15-g16`, a5-CG anchor + `add L VIN1-n1` (E-c cid `d0be8b9bc6d6:032`)

| spec | seed | feasible | spec-feas | mu in-band | mu wide | pts checked |
|---|---|---|---|---|---|---|
| lib | 1/2/3 | True/True/True | – | 0.655/0.685/0.347 | – | – |
| +mu_min | 1 | **False** | True | 1.009 | 0.998 | 1 |
| +mu_min | 2 | **False** | True | 1.001 | 0.930 | 31 |
| +mu_min | 3 | **False** | True | 1.002 | −0.780 | 31 |

With `mu_min` in the spec, the sizer pushes in-band mu to 1.00x. Every seed is still unstable just outside the band. The seed-1 `mu(f)` curve (`curves/`) has mu < 1 at 1.29–1.34 GHz, just below the 1.548–1.612 GHz band.

## (c) Positive / diagnostic (stability-enabled spec, seeds 1, 2, 3 × 2500)

Full per-cell tables are in `tables.md`. Totals:

| candidate | cells | spec-feasible seeds | **final feasible seeds** | cells with ≥1 feasible seed | winners replaced |
|---|---|---|---|---|---|
| template, nb (`narrowband_cascode_tank`) | 8 | 24/24 | **20/24** | **8/8** | 11 |
| template, wb (`wideband_shunt_feedback`) | 8 | 22/24 | **0/24** | **0/8** | 0 |
| anchor a1 inddegen-cascode, nb | 8 | 22/24 | **12/24** | **6/8** (not f15-g12, f24-g14) | 5 |
| anchor a2 current-reuse, nb | 8 | 0/24 | 0/24 | 0/8 (in-band mu 0.56–0.82) | 0 |
| anchor a3 shunt-feedback, nb | 8 | 0/24 | 0/24 | 0/8 (already spec-infeasible in E-b) | 0 |
| anchor a4 twostage, nb | 8 | 21/24 | **0/24** | 0/8 (wide mu −2.5..+0.6) | 0 |
| anchor a5 commongate, nb | 8 | 0/24 | 0/24 | 0/8 (already spec-infeasible in E-b) | 0 |

- **Wideband.** The reference wideband template is unconditionally unstable over 0.1–20 GHz in every cell and seed (wide mu −0.36..0.93) even when its in-band mu is at least 1. The `wb-s11n10-g10-b0530` seed-2 curve has mu < 1 over 3.8–19.4 GHz, with its minimum of 0.906 at 7.8 GHz. Under a stability requirement, no wideband cell has a known stable reference solution.
- **Narrowband.** Stability holds for 8/8 cells with the template. It removes a2 and a4 as retrieval solvers. a1 still retrieves in 6/8 nb cells.

## Cost

- One wide sim takes about 0.01 s (401-point `sp` on bptm45).
- There were 2012 wide sims over 171 gated runs, 20.6 s in total. A run did at most 31 sims, against a median run wall time of 33 s. The overhead is under 3 %.

## Caveats

- **Grid resolution.** 401 linear points means about 50 MHz spacing, so a sharp high-Q out-of-band dip can fall between grid points. The in-band dip is covered by the spec's `mu_min` on the spec's own grid.
- **Low-frequency edge.** Stable winners sit at mu_wide ≈ 1.0001–1.0002, and the minimum is at the 100 MHz edge. There the DC-block caps make the two-port nearly lossless, so mu → 1. A numerically sub-unity value there would fail the gate.
- **OSDI PDKs.** `measure_stability` has no OSDI source split. On IHP it returns None, and the gate records not-ok.
- **Replacement scan.** The scan only reuses points the sizer already visited. The sizer optimizes in-band mu only, so near-edge winners (mu_in ≈ 1.00x) are often just outside-band unstable.
- **Metric used.** The gate uses mu only (the Edwards–Sinsky single test). K and |Δ| are recorded but not gated.

## Files and commands

- `stab_drv.py`: `equiv`, `jobs`, `run`, `collect`
- `one.sh`, `all.sh`: `xargs -P 6`
- `envrun.sh`: inline `crenv.sh` plus `TMPDIR`
- `summarize.py`: produces `tables.md` and `summary.json`
- `mu_curve.py`, `curves.sh`: `mu(f)` diagnostics into `curves/`
- `results.json`: 178 rows, one per run, each with the full `smoke_run` result dict
- `equiv.json`

```
kaggle/campaigns/bench-v12-audit/stability-gate/envrun.sh python kaggle/campaigns/bench-v12-audit/stability-gate/stab_drv.py equiv 300 kaggle/campaigns/bench-v12-audit/stability-gate/equiv.json   # needs $TMPDIR/old_bap.py = git show d61440d8:kaggle/bench_anchor_prep.py
kaggle/campaigns/bench-v12-audit/stability-gate/all.sh regress negctl tpl anchors
kaggle/campaigns/bench-v12-audit/stability-gate/envrun.sh python kaggle/campaigns/bench-v12-audit/stability-gate/stab_drv.py collect /tmp/cr-7cd7ffc3-stab/raw kaggle/campaigns/bench-v12-audit/stability-gate/results.json
kaggle/campaigns/bench-v12-audit/stability-gate/envrun.sh python kaggle/campaigns/bench-v12-audit/stability-gate/summarize.py
```

Goldens: `python lna/ref/check_ref.py` printed **GREEN** after the change.

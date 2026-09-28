# S-1: stability-aware sizing (in-loop wide-stability term)

Question: the stability-gate campaign (`../stability-gate/`) found the wideband shunt-feedback template spec-feasible in 22/24 runs but wide-UNSTABLE (0.1–20 GHz) in all of them, and library anchors a2/a4 lost all narrowband cells. Is that the TOPOLOGY, or SIZER BLINDNESS (the CMA-ES objective only sees the in-band `mu_min`)?

Run 2026-09-28 on branch `worktree-externals-gf180` (base `d61440d8` + the stability-gate commit), bptm45, 2500 evals, seeds 1/2/3, 8 parallel processes (1-min load 8–10), `TMPDIR=/tmp/cr-7cd7ffc3-s1`. Rows carry `era: unknown` (no `AUDIT_ERA`).

## Verdict

**Mostly sizer blindness, with a residual capacity limit in the tighter cells.**

- **Wideband.** When the sizer can see out-of-band stability, the *same* template becomes stable and spec-feasible.
  - It solves **4/8 wb cells** (8/24 seeds). Gate-only solves 0/8.
  - The E-c single edits solve the same 4 cells (14/48 seeds).
  - Those 4 cells are s11n10-g10-b0824, s11n11-g10-b0824, s11n8-g10-b0530 and s11n9-g10-b0530.
  - No tested candidate adds a cell beyond those 4.
- **Wideband cells still unsolved (4).** These are the three g=12 dB cells plus s11n10-g10-b0530. The in-loop winners there are near-misses: minimum joint violation 0.0003–0.07, where wide mu reaches 0.95–1.00 and s21/s11 give way. This looks like a gain/match-vs-stability trade-off of this topology at these specs. It was not tested at larger budgets.
- **Narrowband anchors a2 and a4.** They stay at **0/4 cells**, so for them the loss is topology.
  - a4 two-stage: wide mu goes from −2.5..0.64 to 0.83..1.00, but it then loses spec feasibility (best joint violation 0.011 on f24-g18).
  - a2 current-reuse: fails on in-band mu, NF, s21 and s11 in both modes.
- **The margins are razor-thin.** 23/30 stable winners have wide mu < 1.001, because the sizer stops right at the boundary. Their minima sit out of band, at 3.4–16.6 GHz (the bands are 0.5–3.0 or 0.8–2.4 GHz), never at the 100 MHz edge. Up to 24 grid points per curve lie below 1.001. So with a 50 MHz grid, "stable" here means barely stable. A +1e-3 margin would keep 7/30, still in the same 4 cells.

## Code change (only `kaggle/bench_anchor_prep.py`; `lna/` untouched)

- **Where it hooks in.** At `smoke_run` line 205: when `stab_gate_on(spec)` is true and `STAB_WIDE_INLOOP=1`, the objective is wrapped by `_stab_inloop_objective` (line 379) before `_Budget`.
- **Each eval.**
  1. Call the original objective. Its `points` hook still records `(x, in-band metrics)`.
  2. If the sim succeeded, run `wide_stability(spec, body, decode(x))`. This is the gate's own function: same window, 401 points, same MC-off params.
  3. Compute `v_wide = max(0, limit − mu_wide) / spec._scale(limit)`. The scale is 1 for `min: 1`. If `measure_stability` returns None, `v_wide = 1.0`, the same rule `Spec.feasible` uses for a missing metric.
  4. If `v_wide > 0`, return `1 + Σ in-band violations + v_wide`. Otherwise return the original value.

  This is exactly `Spec.objective` with the wide shortfall as one more hard constraint, so the result is feasible exactly when there is no violation. Sim failures keep `SIM_FAIL_PENALTY`.
- **After the run.** The post-hoc gate and its replacement scan run unchanged. The result gains `stab_inloop` = {n_wide, n_wide_viol, n_wide_none, wide_secs} (line 248).
- **Flag off or gate off.** No code path changes.

## Regression (flags-off byte-identity): `regress.json`

The complete `smoke_run` result dict was compared with `json.dumps(sort_keys=True)` against the rows the stability-gate campaign recorded. **60/60 are identical.** They cover:
- **Lib spec (gate off), flag unset:** the wb template, seed 1.
- **Lib spec with `STAB_WIDE_INLOOP=1`:** gate off, so the flag must be inert. Identical.
- **Stab spec, gate-only:** the 24 template wb runs, the 24 a2/a4 nb runs, and the 9 `edge`/`edgefail` reruns.

`lna/ref/check_ref.py` printed **GREEN**.

## Candidates

- **(a) Template.** `wideband_shunt_feedback.net` on the 8 `v12-wb-*` cells.
- **(b) E-c edits.** Per wb cell, up to 3 confirmed-feasible edits of the shown wideband anchor, taken from `E-c/summary.json` with tokens from `candidates.jsonl`. The rule, fixed before any run, is `add R n1-n2` plus the top 2 others ranked by in-band stable_mu, then seeds_pass, then in-band mu. Each cell therefore has 2 non-`add R n1-n2` edits (listed under `ec_picks` in `results.json`).
  - E-c had measured only lib specs (no gate), so **both modes** were run.
  - **`add R n1-n2` on the anchor IS the template.** Its 48 result dicts are identical to the template's, excluding `stab_inloop` timing. It is counted separately below but adds no information.
- **(c) Anchors a2 and a4** (MANIFEST tokens, bptm45 override as in E-b) on nb f15-g12, f15-g16, f24-g12 and f24-g18.

## Results (full per-cell table in `tables.md`)

F = final feasible (spec including in-band mu ≥ 1, AND wide mu ≥ 1); s = spec-feasible but wide-unstable; n = runs.

| candidate | cells | gate-only F / s / n | cells ≥1 F | gate+inloop F / s / n | cells ≥1 F | wide mu gate → inloop |
|---|---|---|---|---|---|---|
| template (wb) | 8 | 0 / 22 / 24 | 0 | **8** / 4 / 24 | **4** | −0.36..0.93 → 0.90..1.00 |
| E-c other edits (wb, 16 edit×cell) | 8 | 0 / 39 / 48 | 0 | **14** / 5 / 48 | **4** (same 4) | −0.82..1.01 → 0.79..1.00 |
| (E-c `add R n1-n2` ≡ template) | 8 | 0 / 22 / 24 | 0 | 8 / 4 / 24 | 4 | identical |
| a2 current-reuse (nb) | 4 | 0 / 0 / 12 | 0 | 0 / 0 / 12 | 0 | −0.33..0.78 → 0.75..0.99 |
| a4 twostage (nb) | 4 | 0 / 10 / 12 | 0 | 0 / 3 / 12 | 0 | −2.49..0.64 → 0.83..1.00 |

Per-cell template results (gate → inloop):

| cell | gate-only | inloop | min joint violation (inloop) |
|---|---|---|---|
| s11n10-g10-b0530 | sss | xxx | 0.047 |
| s11n10-g10-b0824 | sss | **FFF** | 0 |
| s11n10-g12-b0824 | sss | xxx | 0.038 |
| s11n11-g10-b0824 | sss | **FxF** | 0 |
| s11n11-g12-b0824 | sss | xxs | 0.053 |
| s11n8-g10-b0530 | sss | **xFF** | 0 |
| s11n8-g12-b0530 | xxs | sxx | 0.070 |
| s11n9-g10-b0530 | sss | **sFs** | 0 |

- E-c edits that are 3/3 stable-feasible in-loop: `add R n3-n4` (s11n8-g10), `add R n1-n4` (s11n9-g10) and `add L VIN1-n5` (s11n11-g10).
- Closest miss in an unsolved cell: `add R n1-n4` on s11n10-g10-b0530, with joint violation 0.0003 (wide mu 0.99969).
- **In-loop spec feasibility falls from 93/120 to 46/120 runs.** When no jointly feasible point is found, the sizer trades in-band margin for wide stability, which is expected under the combined objective.
- **Share of in-loop evals violating wide stability:** median 90 %. Most of the sizing space is out-of-band unstable.

## 100 MHz edge concern (report only; threshold unchanged)

- **Stable nb-template winners (`edge`: 5 stability-gate final-feasible runs, re-run gate-only).** The minimum is at the **100 MHz edge in 5/5**, with mu = 1.00002–1.00013. The curve rises to about 1.0003 at 150 MHz. This is the lossless-DC-block limit.
- **Failing nb runs with mu_wide ≥ 0.99 (`edgefail`, 4 runs).** The minima are **interior** (1.44, 1.49, 2.24 and 2.59 GHz) at 0.991–0.998. These are real near-band dips; their mu at 100 MHz is still ≥ 1.00002.
- **Tolerance flips (fail→pass if the threshold were 0.999):**
  - stability-gate rows: **0/171** (nearest 0.998)
  - S-1 rows: **1/240** (`add R n1-n4` on s11n10-g10-b0530, inloop seed 3, mu 0.99969 at 8.16 GHz, an interior dip)
- **Reverse flips (pass→fail if the threshold were 1.001):**
  - stability-gate: 32/32
  - S-1: 23/30, none with the minimum at the edge
- **No wide-failing run anywhere has its minimum at the 100 MHz edge**, so the edge is not causing false failures today. It does make stable nb winners sit at 1.0000x, so any future threshold tweak should exclude or down-weight the DC edge point.

## Overhead

- **Per sim:** 300 000 in-loop wide sims cost 4335 s, or **14.4 ms each** under a load of about 9 (the stability-gate campaign measured 10 ms at lower load). That is about **36 s per 2500-eval run**.
- **Paired wall time** (same cell, candidate and seed; 120 pairs): median **57.1 s gate-only vs 95.2 s gate+inloop, 1.66×**.

## Caveats / deviations

- **Parallel race in `stability_spec`.** Parallel workers on the same cell rewrote the same `$TMPDIR/stab-specs/<cell>__mu1.yaml` at the same time, and one early regression job read it truncated (`SpecError`). The driver now passes a per-PID `out_dir`, with identical content and basename, and the job was re-run. The helper itself is unchanged. Earlier parallel users of the default path (the stability-gate campaign) could in principle hit the same race.
- **Job runner.** `xargs -P` was refused by the sandbox, so jobs run through `pool.py` (a ThreadPool of `one.sh`).
- **Extra runs.** The 9 `edge`/`edgefail` reruns go beyond the requested 5 winners. The 4 failing runs were added to locate the failing minima.
- **Budget and scope.** 2500 evals only. There was no budget or seed sweep for the 4 unsolved wb cells, so "topology limit" there is not proven. The in-loop term uses mu only; K and |Δ| are recorded, not optimized.
- **Stability-gate caveats still apply:** 50 MHz grid spacing and barely-stable winners.

## Files and commands

- `s1_drv.py`: `jobs` / `run` / `collect` / `picks`. Records the full result dict, loop-vs-gate wide-sim timing, and the final winner's mu(f) curve summary.
- `one.sh`, `pool.py`, `envrun.sh`: run one job, run the parallel pool, and set up the inline crenv plus `TMPDIR`.
- `regress_check.py` → `regress.json`
- `summarize.py` → `tables.md`, `summary.json`
- `results.json`: 252 rows (3 regress + 240 main + 9 edge)

```
E=kaggle/campaigns/bench-v12-audit/S-1-stab-inloop
$E/envrun.sh python $E/s1_drv.py jobs regress > /tmp/cr-7cd7ffc3-s1/jobs0.txt   # likewise tpl, ec, anchors -> jobs1.txt; edge -> jobs2.txt
$E/envrun.sh python $E/pool.py 8 /tmp/cr-7cd7ffc3-s1/jobs1.txt /tmp/cr-7cd7ffc3-s1/log1.txt
$E/envrun.sh python $E/s1_drv.py collect /tmp/cr-7cd7ffc3-s1/raw $E/results.json
$E/envrun.sh python $E/regress_check.py /tmp/cr-7cd7ffc3-s1/raw $E/regress.json
$E/envrun.sh python $E/summarize.py
```

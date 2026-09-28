# verifier rl-v1: implementation tests

The canonical configuration is `kaggle/VERIFIER-RL-V1.md`; this directory holds its tests.

- **Run:** 2026-09-28, branch `worktree-externals-gf180`, bptm45.
- **Budget and environment:** 2500 evals per run, `TMPDIR=/tmp/cr-7cd7ffc3-v1`, at most 6 processes. The 1-min load was 11–18 from other jobs.
- **The verifier under test:**
  - `bench_anchor_prep.smoke_run(tokens, rl_v1_spec(<cell spec>), seed, 2500, "bptm45", profile="rl-v1")`
  - Profile flags: `STAB_WIDE_INLOOP=1`, `STAB_WIDE_WINDOW=1e7,5e10,1001`, `VERIFY_TOPO_LIMITS=1`, `VERIFY_STRUCT=1`, `VERIFY_FINITE=1`, `VERIFY_INERT_COUNT=1`.
  - rl-v1-form spec: `mu_min ≥ 1`; wideband uses `nf_max_db` and `max_inductors: 2`; narrowband uses `s11_max_db`.

## Verdict

- **Regression.** Byte-identical with no profile. `lna/` goldens are GREEN, and the W5 metric agrees exactly with R4's post-hoc band NF.
- **Narrowband.** rl-v1 costs nothing in solvability: **8/8 cells**, 46/48 runs, the same as the in-loop baseline. This holds even though **61/63 recorded nb winners fail W6 as-is** (band S11). With `s11_max_db` in the objective, the sizer finds band-matched designs.
- **Wideband.** It is **much harder but still solvable in the same 4 cells**: 7/48 runs by any candidate, versus 22/48 under S-1.
  - The template alone keeps only **2 cells**. It loses s11n8-g10-b0530 and s11n9-g10-b0530 to W5 band NF plus µ over 0.01–50 GHz.
  - Those two cells survive only through the E-c edits `add R n3-n4` and `add R n1-n4`, at 1/3 seeds each.
  - Three S-1 edits add a 3rd inductor, and W1 now rejects them before sizing.
- **Loopholes.**
  - **Hard-rejected (0 evals):** every degenerate or over-budget junk mutant. That is 16/32 runs: dead MOS, dangling chain and VB-named net in both bands; plus wb tank, dup_out, dangling and vbnet over `device_budget` / `max_inductors`.
  - **Infeasible after sizing:** 6/32. These are wb `R VIN1-VOUT1` (×2, wide µ 0.01–50 GHz; R4 in-loop had scored it feasible), plus wb bleeder/cap_in on s11n8 (wide µ / W5) and nb rin_out ×2 (spec).
  - **Still feasible:** the electrically valid junk (bleeder, input shunt C, output RC or tank), in 10/32 runs. **Every one of those 10 carries a nonzero `n_inert_devices`, with the junk device itself on the inert list.** That is the W2 penalty signal.

## (a) Regression

| check | result | file |
|---|---|---|
| `python lna/ref/check_ref.py` after the extract change | **GREEN**; also check_nf GREEN, check_op GREEN, check_stab harness GREEN | — |
| extract.py vs HEAD (`git show HEAD:lna/extract.py`), 5 recorded R4 winners (3 wb, 2 nb) | default noise deck text identical; `run_and_extract` on the lib spec identical; `measure_nf` identical; **5/5** | `w5_unit.json` |
| W5 metric | band-deck f0 NF == `measure_nf` bit-for-bit; `nf_max_db` == R4 `nf_over_band` exactly (diff 0.0) on 5/5 | `w5_unit.json` |
| no profile, E-a nb-f15-g12 template s1 (lib) | identical: metrics, feasible, n_evals, n_sim_fail, sim_error, winner_reeval_ungated; no `verifier` key | `regress.json` |
| no profile, E-a wb-s11n10-g10-b0824 template s1 (lib, NF-gated → `measure_nf` path) | identical, same keys | `regress.json` |
| no profile, E-c wb-s11n10-g10-b0530 `add L n1-n5` s1 (lib) | identical on every key E-c stored | `regress.json` |
| no profile, stability-gate nb-f15-g14 template stab s1 | **full dict identical** | `regress.json` |
| S-1 wb-s11n10-g10-b0824 template in-loop s1 (flag `STAB_WIDE_INLOOP=1` set) | identical apart from the added `verifier` record, as designed: any set flag is recorded | `regress.json` |
| profile via env `VERIFIER_PROFILE=rl-v1` vs `smoke_run(profile="rl-v1")` (nb-f15-g16 template s1) | full dict identical | `regress.json` |
| profile semantics | all 10 checks pass (`profile_unit.json`):<br>• exact flag set<br>• env == kwarg<br>• `profile=""` forces none<br>• an env override wins (even `"0"`) and is listed<br>• an unknown profile raises<br>• all 16 `rl_v1_spec` outputs conform, with everything outside constraints/topology/objectives identical<br>• a pre-sizing reject carries `verifier`<br>• `os.environ` is restored | `profile_unit.json` |

**W5 cost.**
- `measure_nf_band` median is 11.1 ms, against 10.5 ms for `measure_nf` (75 calls each).
- In the rl-v1 wb spec, `nf_max_db` replaces `nf_db`, so there is **no extra sim per eval**.

**Whole-verifier cost.** Load was about 15 here and about 9 for S-1.

| | rl-v1 | S-1 |
|---|---|---|
| wide sim per eval (1001 points vs 401) | 22 ms (nb) / 33 ms (wb) | about 15 ms |
| median run wall time, nb | 125 s | 94 s |
| median run wall time, wb | 202 s | 96 s |

`VERIFY_INERT_COUNT` adds about n_passive × (1 eval + 1 wide sim) per feasible result.

## (b) Difficulty under rl-v1 (seeds 1, 2, 3 × 2500)

F = final feasible. Baselines use the same candidates and seeds:
- **gate:** the stability-gate campaign (0.1–20 GHz, post-hoc).
- **inloop:** S-1 for wb and R4 tag `nb` for nb (0.1–20 GHz in-loop, library metrics). This is the pre-rl-v1 RL config.

| group | cells | gate F (cells) | inloop F (cells) | **rl-v1 F (cells)** | cells lost vs inloop |
|---|---|---|---|---|---|
| nb template | 8 | 20/24 (8) | 24/24 (8) | **24/24 (8)** | — |
| nb a1 (inddegen cascode) | 8 | 12/24 (6) | 22/24 (8) | **22/24 (8)** | — |
| wb template | 8 | 0/24 (0) | 8/24 (4) | **5/24 (2)** | s11n8-g10-b0530, s11n9-g10-b0530 |
| wb E-c S-1 picks (8 edits × 3) | 4 | 0/24 (0) | 14/24 (4) | **2/24 (2)** | s11n10-g10-b0824, s11n11-g10-b0824 |
| **wb any candidate** | 8 | 0/48 (0) | 22/48 (4) | **7/48 (4)** | — (the same 4 cells) |

**Stable-feasible cells per candidate under rl-v1:**

| candidate | cells solved (seeds) |
|---|---|
| nb template | all 8 nb cells, 3/3 each |
| nb a1 | all 8 nb cells; f15-g16 and f15-g18 at 2/3 |
| wb template | s11n10-g10-b0824 (2/3), s11n11-g10-b0824 (3/3) |
| wb `add R n3-n4` (147) | s11n8-g10-b0530 (1/3) |
| wb `add R n1-n4` (126) | s11n9-g10-b0530 (1/3) |
| wb `add L n1-n5` (131, 2 cells), `add L VIN1-n5` (053) | **0: W1 topo reject** (3 inductors > 2, 0 evals) |
| wb `add R VIN1-n5` (051), `add C n4-n5` (157), `add R n4-n5` (156) | 0 |

**Which new check causes each loss.** "Static" means the S-1 / R4 recorded winner (same design, not re-sized) re-checked against each rl-v1 piece, from `attrib.json`. "Re-sized" means the final winner of the rl-v1 run, from `tables.md`.

| cell / candidate | inloop → rl-v1 | static: recorded winners that fail | re-sized rl-v1 failures |
|---|---|---|---|
| wb s11n8-g10 template | xFF → xxx | W5 band NF 2/2 | W5 ×1, **wide µ 0.01–50 GHz ×2** |
| wb s11n9-g10 template | xFx → xxx | W5 1/1 | W5 ×1, wide µ ×2 |
| wb s11n10-g10-b0824 template | FFF → FFx | W5 1/3 | wide µ ×1 |
| wb s11n11-g10 template | FxF → **FFF** | W5 1/2 | — (gained a seed) |
| wb `add L n1-n5`, `add L VIN1-n5` | FFx / xFx / FFF → xxx | **W1 topo** (+ W5) | W1 topo ×9 |
| wb `add R n3-n4` (s11n8) | FFF → xxF | W5 3/3 | W5 ×1, wide µ ×1 |
| wb `add R n1-n4` (s11n9) | FFF → xxF | W5 3/3 (+ wide µ 1) | W5 ×1, wide µ ×1 |
| wb `add R n4-n5` (s11n9) | FxF → xxx | W5 1/2 (+ wide µ) | W5 ×2, band S11 (wb's own `s11_max_db`, not new) ×2, wide µ ×1 |
| nb a1 f15-g16 / f15-g18 | FFF / FxF → FxF / FxF | W6 band S11 (all) | 1 run each: W6 band S11 + NF@f0 (+ s21) |

**Static view, over the 85 recorded in-loop-feasible winners** (`attrib.json`):
- **nb, 2/63 pass rl-v1 as-is.** The other 61 fail W6 (one also fails wide µ): in-band S11_max sits a median +2.7 dB (up to +4.3 dB) above −10 dB.
- **wb, 4/22 pass.**
  - 18 fail W5: NF over band exceeds the limit by up to +1.23 dB.
  - 6 add-L edits also fail W1.
  - 3 also fail wide µ over 0.01–50 GHz.

The in-loop sizer repairs every nb cell. It repairs only part of wb, because band NF, flat gain, match and stability over 0.01–50 GHz now bind together.

**Unsolved wb cells (still 4/8).** These are s11n10-g10-b0530, s11n10-g12-b0824, s11n11-g12-b0824 and s11n8-g12-b0530. The limiting constraint is s21 (g12 cells) or the wb spec's own band S11 (`s11_max_db`, not a new check) plus wide µ, the same as S-1 but tighter.

**Edge note.**
- **nb.** 46/46 spec-feasible nb winners have their wide-µ minimum at the **10 MHz window edge**. There µ = 1.00000025–1.0000417 on a 12-digit re-sweep, the lossless DC-block limit that S-1 saw at 100 MHz. `meas` reports these as 1.0 and the gate is `mu < 1`, so they pass correctly.
  - The interior minimum is ≥ 1.0000089.
  - There are no rounding false-passes: 0 feasible designs have 12-digit µ < 1 (`edge_probe.json`).
- **wb.** Minima are interior (4/17 at the edge).
- **Any future margin** (µ ≥ 1 + ε) must exclude the DC-edge point, or every nb design fails.

## (c) Loophole re-check: the R4 junk add-on mutants

The R4 mutants are the templates plus one junk add-on each. Each was run on 2 cells per band, seed 1, under rl-v1 (`tables.md` § (c); `loop_static.json` evaluates both guards independently).

| mutant | rl-v1 outcome, both cells | guard |
|---|---|---|
| dead_mos (nb, wb) | rejected, 0 evals | VERIFY_STRUCT `mos_d_eq_s`, `mos_g_eq_s` |
| dangling (nb) | rejected, 0 evals | VERIFY_STRUCT `dangling_node` |
| vbnet (nb) | rejected, 0 evals | VERIFY_STRUCT `mos_no_dc_path` |
| dangling, vbnet, dup_out (wb) | rejected, 0 evals | VERIFY_TOPO_LIMITS `device_budget`: the wb template is 15 of 16 devices. STRUCT would also flag dangling and vbnet. |
| tank_out (wb) | rejected, 0 evals | VERIFY_TOPO_LIMITS `device_budget` + **`max_inductors` (W1)** |
| rin_out (wb) | infeasible after sizing | wide µ over 0.01–50 GHz. R4's in-loop run had scored it feasible. |
| rin_out (nb) | infeasible | spec: W6 band S11, NF, s21 |
| bleeder, cap_in (nb); tank_out, dup_out (nb); bleeder, cap_in (wb, s11n10) | **feasible**, 10 runs | **W2:** `n_inert_devices` 1–3 in all 10; the junk R/C is on the inert list in 10/10 |
| bleeder, cap_in (wb, s11n8-g10) | infeasible (wide µ; W5) | — |

- **No false positives.** Both parent templates pass topo and struct on all 4 cells.
- **Every hard reject has 0 evals.**
- **Inert counts on clean designs.** Clean reference designs also carry inert devices: nb template 0–1 (a bypass cap), a1 0, wb template 0–1. That is the expected baseline of a W2 penalty; the penalty is not a gate.

## Deviations / caveats

1. **Loophole seed.** The loophole set used seed 1 only; R4 also used seed 1. A second cell per band was added to reach the 4 cells.
2. **Junk-device identification.** The "junk flagged inert" column identifies junk devices as sized names present in the mutant but not in the parent template's sizing (a name-diff proxy). Device renumbering after the round-trip could in principle mislabel them; the lists shown match the added device kinds in 10/10.
3. **E-c picks.** `add R n1-n2` is identical to the template (S-1), so it is not run separately.
4. **Baseline load.** Baselines ran at a different box load (wall-time comparisons are indicative only). All runs are deterministic, so feasibility comparisons are exact.
5. **In-band µ.** rl-v1 keeps the spec's in-band `mu_min` constraint on the 101-point band grid. It rarely binds: 1 run, `add C n4-n5`.

## Files and commands

**Drivers:**
- `v1_drv.py`: jobs, run, collect
- `one.sh`, `pool.py` (≤ 6 processes, ≤ 4 above load 22), `envrun.sh`, `mkjobs.sh`

**Tests and analysis:**
- `w5_unit.py` → `w5_unit.json`
- `profile_unit.py` → `profile_unit.json`
- `reg_check.py` → `regress.json`
- `attrib.py` → `attrib.json`
- `loop_static.py` → `loop_static.json`
- `edge_probe.py` → `edge_probe.json`
- `summarize.py` → `summary.json`, `tables.md`

**Data:**
- `results.json`: 134 runs (6 reg + 96 diff + 32 loop), each with the full result dict, tokens, body and winner params.

```
V=kaggle/campaigns/rl-readiness/verifier-rl-v1
$V/mkjobs.sh reg diff loop
$V/envrun.sh python $V/pool.py 6 /tmp/cr-7cd7ffc3-v1/jobs_reg.txt /tmp/cr-7cd7ffc3-v1/log_reg.txt   # likewise jobs_main (= loop + diff)
$V/envrun.sh python $V/v1_drv.py collect /tmp/cr-7cd7ffc3-v1/raw $V/results.json
$V/envrun.sh python $V/reg_check.py /tmp/cr-7cd7ffc3-v1/raw $V/regress.json
$V/envrun.sh python $V/attrib.py $V/attrib.json
$V/envrun.sh python $V/summarize.py $V/results.json
```

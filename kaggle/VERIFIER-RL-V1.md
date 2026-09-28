# Verifier configuration `rl-v1` (canonical)

**Status:** user-ruled 2026-09-28 (rulings W1–W6 on the R4 loophole audit). This is the verifier that every RL reward, bench-v2 score and training-task label uses unless a newer `rl-vN` supersedes it.

**Evidence:**
- `kaggle/campaigns/rl-readiness/R4/`: the loophole audit and the guards.
- `kaggle/campaigns/bench-v12-audit/S-1-stab-inloop/`: in-loop wide stability.
- `kaggle/campaigns/bench-v12-audit/stability-gate/`: the µ gate itself.
- `kaggle/campaigns/rl-readiness/verifier-rl-v1/`: tests of this config.

## How to use it

```python
import bench_anchor_prep as PREP
spec = PREP.rl_v1_spec("kaggle/editcap-lib-v12-45nm/<cell>/spec.yaml")   # rl-v1-form copy
res  = PREP.smoke_run(tokens, spec, seed, 2500, "bptm45", profile="rl-v1")
# or: export VERIFIER_PROFILE=rl-v1 and call smoke_run(...) without the kwarg
```

Both halves are needed:
- **The profile** turns on the verifier machinery.
- **The rl-v1-form spec** states what is being verified. It supplies `mu_min`, the band metrics, and the topology limit.

`result["verifier"]["spec_rl_v1_issues"]` lists anything about the spec that is not in rl-v1 form; `[]` means conforming. bench-v2 specs should be written directly in rl-v1 form.

## Rulings

| # | ruling | one-line rationale |
|---|---|---|
| W1 | Wideband `max_inductors` = 2, and spec topology limits are **enforced** (`VERIFY_TOPO_LIMITS`). | The wb reference template needs 2 L. With a limit of 1, no known wb solution was compliant: R4 (a) found 8/8 wb templates and 196/208 E-c edits in violation. bench-v2 sets limits deliberately per spec. |
| W2 | Inert/useless devices are **not** a hard fail. The count is recorded as a reward-penalty input (`n_inert_devices`) with no feasibility effect. | 31 % of legitimate winners carry an inert bypass or bias passive (R4 (b)), so a hard gate would reject good designs. Padding is bounded by `VERIFY_STRUCT` + `device_budget`. |
| W3 | **No** ±5 % robustness gate. `VERIFY_ROBUST` stays available as a diagnostic only. | Every reference solution fails it (R4 (c): 0/107 winners survive 10/10 draws). Enforcing it would need a margin term in the objective, which is future work. |
| W4 | Large-signal stability is **out of scope**. | The small-signal µ ≥ 1 gate is the criterion. R4 (e) found 7/107 µ≈1.00002 nb winners that limit-cycle after a 1 mA kick; small-signal analysis cannot see this. |
| W5 | Wideband NF must hold over the **whole band**, inside the sizing loop. The spec uses `nf_max_db` instead of `nf_db`. | R4 (f): 35/44 wb winners exceed the NF limit somewhere in band (median +0.30 dB, up to +1.23 dB), while `nf_db` reads f0 only. |
| W6 | Narrowband input match over its band: the spec uses `s11_max_db` instead of `s11_db`. | R4 (f): 61/63 nb winners had their S11 notched at f0, with in-band worst S11 up to +4.3 dB above the limit. `s11_max_db` is already measured every eval. |

## The profile: exactly these flags

| flag | value | stage | catches | evidence |
|---|---|---|---|---|
| `STAB_WIDE_INLOOP` | `1` | in-loop objective term + post-hoc gate | out-of-band potential instability (µ < 1); the sizer optimizes it instead of stumbling on it | S-1: wb template 0 → 4 cells |
| `STAB_WIDE_WINDOW` | `1e7,5e10,1001` | in-loop + gate | window-edge gaming: winners that park µ < 1 just above 20 GHz or below 0.1 GHz | R4 (d): 6/107 at 20.5–23.4 GHz, 1 at 50–60 MHz |
| `VERIFY_TOPO_LIMITS` | `1` | pre-sizing, 0 evals | spec `topology:` limits (`device_budget`, `max_inductors`, `has_inductor`, `single_input`, `not_floating`, `match_plausible`, ...) | R4 (a) |
| `VERIFY_STRUCT` | `1` | pre-sizing, 0 evals | degenerate junk: shorted passive, MOS D=S / G=S, dangling node, MOS with no DC path, port on rail, VIN1=VOUT1 | R4 (b)/(f): 0/250 false positives |
| `VERIFY_FINITE` | `1` | post-hoc | a NaN/inf constrained metric, which `Spec.feasible` would otherwise treat as satisfied | R4 `nan_probe.json` |
| `VERIFY_INERT_COUNT` | `1` | post-hoc, about n_passive × (1 eval + 1 wide sim) | W2 record only: `inert_devices` (list) + `n_inert_devices` | R4 (b) |

**Precedence.**
- `smoke_run(..., profile=)` beats env `VERIFIER_PROFILE`. `profile=""` forces no profile.
- Any individual flag that is **set** in the environment, even to `"0"` or `""`, beats the profile value. It is listed in `verifier.env_overrides`.
- The profile's flags are applied to `os.environ` only for the duration of the call and are then removed.

**Stability needs the spec.** The stability pieces run only when the spec constrains `mu_min` (`stab_gate_on`), which `rl_v1_spec` adds. A spec without `mu_min` under the profile is verified **without** stability, and `spec_rl_v1_issues` says so.

**Not in the profile:**
- Kept as diagnostics: `VERIFY_ROBUST` (W3) and `VERIFY_NO_INERT` (the hard-gate version, W2).
- Superseded by spec-level semantics:
  - `VERIFY_NF_BAND` (post-hoc) is replaced by in-loop `nf_max_db` (W5).
  - `VERIFY_BAND_METRICS` (post-hoc) is replaced by in-loop `s11_max_db` (W6).

## rl-v1-form spec (`bench_anchor_prep.rl_v1_spec`)

| band | change |
|---|---|
| all | adds `constraints.mu_min: {min: 1.0}` |
| wideband | constraint `nf_db` → `nf_max_db`, with the same limit. Objectives on `nf_db` are renamed too, so the objective floor and scale remain the constraint's. Also sets `topology.max_inductors: 2`. |
| narrowband | constraint `s11_db` → `s11_max_db`, with the same limit |

**Write safety.** The copy is written atomically (per-PID temp file + `os.replace`), like `stability_spec`, so parallel workers on the same cell are safe. The source YAML is never modified.

**Deliberately unchanged:**
- Narrowband NF stays at f0. W5 is wideband-only: in-band nb NF varies by at most ~0.02 dB (R4 (f)).
- Wideband `s21_db` stays at f0 plus `s21_ripple_db`, which together already bound the band.

## W5 implementation: shared core, additive

This is the only `lna/` change, in `lna/extract.py` (commit "shared-core …"):
- **`build_noise_deck(..., band_max=False)`.** `True` appends `let m_nf_max = vecmax(nfv)` to the series-Rs noise deck. This is the same 51-point [f_lo, f_hi] sweep the deck already runs, so no new analysis is added. The default deck text is byte-identical.
- **`measure_nf_band()`.** Returns `(nf_f0, nf_max)` from that one deck.
- **`run_and_extract`.** Adds `nf_max_db` **only when the spec constrains `nf_max_db`**. It also fills `nf_db` with the f0 NF from the same deck, which is bit-identical to `measure_nf`. No pre-existing spec constrains `nf_max_db`, so every existing path is unchanged.
- **Cost.** In the rl-v1 wideband spec, `nf_max_db` *replaces* `nf_db`, so `eval_metrics` no longer calls `measure_nf`. The number of sims per eval is unchanged (1 op/sp + 1 noise). The deck costs +0.6 ms more (median 11.1 vs 10.5 ms, 75 calls each).
- **Limit.** A `balun-lna` spec must not constrain `nf_max_db`: the generic noise deck does not handle port 3.

## How results record it

With a profile active, or any verifier flag set, `result["verifier"]` holds:

```
{"profile": "rl-v1",
 "flags": {<every flag in VERIFIER_FLAGS>: <effective value or None>},
 "env_overrides": [...], "stab_gate_on": true,
 "stab_window": [1e7, 5e10, 1001], "spec_rl_v1_issues": []}
```

Other keys the result carries:
- **From the guards:**
  - `topo_limits_ok`
  - `topo_limits`
  - `structural_degeneracy`
  - `nonfinite_metrics`
  - `inert_devices` / `n_inert_devices`:
    - `None` if the winner is infeasible after sizing.
    - Absent on a pre-sizing reject.
- **From stability:** `stab_inloop`, `stab_window`, `mu_min_wide`, `spec_feasible`, and the other stability keys.
- **On a reject:** `infeasible_reason`, set when a pre-sizing reject happens.
- **Metric:** `metrics.nf_max_db` for wideband.

**Legacy results.** With no profile and no flag set, `smoke_run` is the historical code path: the result is byte-identical and has **no** `verifier` key. A stored result without `verifier` is therefore a pre-rl-v1 or unguarded result.

**Reward.** The RL reward reads:
- `feasible`, the hard gate
- `n_inert_devices`, the W2 penalty
- margins from `mysolve._margins(spec, metrics)` on the rl-v1-form spec

## What rl-v1 does NOT cover

- **Robustness (W3).** Winners sit on the constraint boundary: 17 % of ±5 % draws stay feasible (R4 (c)). RL will therefore reward boundary-hugging, exactly like the sizer does.
- **Large-signal stability (W4).** There is no kick/transient check. `r4_sim.tran_deck` exists as an offline diagnostic.
- **Ideal passives.** L has Q = 12 (`INDUCTOR_Q`). R and C are ideal, with no parasitics, no self-resonance and no layout. Values may pin to the sizing-box limits (R4: 78/107 winners).
- **Grid resolution.**
  - The wide µ is sampled every ~50 MHz, so a sharper dip can fall between points.
  - In-band metrics use 101 sp points and 51 noise points.
- **Linearity.** `iip3_dbm` stays `status: unsupported`.
- **PVT corners.** Only the typical corner is checked, at 27 °C.
- **Stability margin.**
  - Nb winners sit at µ = 1.0000002–1.00004 at the **10 MHz window edge**, the lossless DC-block limit.
  - The gate is `mu < 1` → fail, so they pass correctly, and no rounding false-pass was found.
  - Any future µ ≥ 1 + ε margin must exclude the DC-edge point.

## Test results (kaggle/campaigns/rl-readiness/verifier-rl-v1/)

**Regression.**
- With no profile, `smoke_run` is byte-identical: 4 recorded rows (E-a ×2, E-c, stability-gate full dict), with no `verifier` key.
- A flags-only S-1 row is identical plus the `verifier` record. Env and kwarg profiles give an identical result.
- `extract.py` default paths are identical to HEAD, and `nf_max_db` equals R4's post-hoc band NF exactly.
- `check_ref` / `check_nf` / `check_op` are GREEN.

**Difficulty.** rl-v1-form specs, 3 seeds × 2500, compared with the S-1 / R4 in-loop baseline:

| group | rl-v1 runs feasible | cells | baseline |
|---|---|---|---|
| nb template | 24/24 | 8/8 | unchanged |
| nb a1 | 22/24 | 8/8 | unchanged |
| wb template | 5/24 | 2 cells | was 8/24, 4 cells |
| wb any candidate | 7/48 | the same 4 cells | was 22/48 |

- 61/63 recorded nb winners fail W6 as-is, and 18/22 wb winners fail W5. The in-loop sizer re-finds compliant designs in every nb cell, but only thinly in wb.
- The wb losses come from W5 band NF plus µ over 0.01–50 GHz. The S-1 add-L edits are lost to W1 (3 inductors).

**Loopholes (R4 junk mutants, 4 cells).**
- 16/32 runs are rejected pre-sizing: STRUCT catches dead MOS, dangling and vbnet; TOPO catches budget and inductor count.
- 6 fail after sizing: wide µ ×3, W5 ×1, nb spec ×2.
- The 10 still-feasible valid-but-useless add-ons each carry `n_inert_devices` ≥ 1, with the junk device on the list (W2 penalty).

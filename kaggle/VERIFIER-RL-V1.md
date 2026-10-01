# Verifier configuration `rl-v1` (canonical)

**Status:** user-ruled 2026-09-28 (rulings W1–W6 on the R4 loophole audit). This is the verifier that every RL reward, bench-v2 score and training-task label uses unless a newer `rl-vN` supersedes it.

**Superseded for bench-v2 by `rl-v1.1`** (2026-10-01, PREREG-BENCH-V2 AMENDMENT 2): rl-v1 plus the input-port DC requirement. See the [rl-v1.1 section](#rl-v11--rl-v1--input-port-dc-requirement) at the end. Everything below still describes rl-v1 exactly, and rl-v1 results are unchanged.

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

---

## rl-v1.1 = rl-v1 + input-port DC requirement

**Status:** PREREG-BENCH-V2 AMENDMENT 2 (commit `1a0413fb9`), user-approved 2026-10-01. This is the verifier for every bench-v2 cell and training task from that date. rl-v1 itself is unchanged.

```python
res = PREP.smoke_run(tokens, spec, seed, 2500, "bptm45", profile="rl-v1.1")
```

The profile is rl-v1's flags plus `VERIFY_PORT_DC=1`. In `result["verifier"]["flags"]`, `VERIFY_PORT_DC` is listed only when it has an effective value. rl-v1 and no-profile results are therefore byte-identical to before; see the tests.

### Rule

An LNA must work for **any source DC condition**: AC-coupled, DC-coupled or DC-grounded. Antennas, filters, baluns, switches and ESD networks are often DC-grounded. This is an interface requirement on the DUT. It says nothing about how a design meets it.

1. **Pre-filter (structural, before sizing, 0 sims): `port_dc_prefilter`.**
   - Build the DC graph of the proposal: R, L and a MOS channel (D–S) are DC edges, C is open.
   - Grow the DC group of VIN1. Do not expand through a rail node, because the ideal source pins it.
   - **Reject** if the group contains a MOS terminal (D/G/S/B) on a non-rail node, or the **positive** supply VDD. A harness bias-source net (VB\*/VCM\*/VREF\*, each driven by a positive dc source in `to_spice`) counts as positive supply.
   - **VSS exception:** a DC path from VIN1 to VSS/ground alone is allowed, for example an input shunt inductor to ground, a common matching and ESD element. The behavioural check then decides.
   - Reason: `port_dc_prefilter: ...`, with 0 evals.
2. **Behavioural check (the authority): `port_dc_check`.**
   - It runs on the final winner: the stability gate's rescan replacement if there is one, else the sizer winner. It runs only when that winner is otherwise feasible, and it runs last, after the stability gate and the R4 guards.
   - It compares the DC operating point of the default testbench (`Vp1 p1 0 dc 0 ... z0 50` + `Cp1 p1 VIN1 10p`) against the same deck with VIN1 given an extra DC path to ground through **50 Ω** via a 1 H choke. The added path is DC-only; AC is unchanged.
   - **Pass iff** every MOS |ΔV_gate| < 10 mV **and** |ΔI_dd|/I_dd < 1 %.
   - On failure, `feasible = False` and `infeasible_reason` gets `port_dc_fail: ...`.
   - `result["port_dc"]` holds `pass, dVG_max_V, dVG_max_dev, dIdd_pct, idd0_mA, idd1_mA, v_vin1_0_V, v_vin1_1_V, i_port_dc_mA, n_gates, error, rule`. It is `None` when the winner was already infeasible.
   - `result["port_dc_prefilter"]` holds the pre-filter record of every sized call.
   - Cost: 2 op-only decks, median 9 ms.
3. **Pre-filter vs behavioural.** For a topology that passes the pre-filter, VIN1's DC group holds no MOS terminal and no positive rail. A DC path to ground at VIN1 therefore carries no current, and the behavioural check is a provable no-op: ΔV = 0 and ΔIdd = 0 in every test. The pre-filter is stricter in one direction. It also rejects designs that pass behaviourally, for example a common-gate input whose source sits at 0 V through an inductor.

### Rationale and evidence

- **The motif audit** (`kaggle/campaigns/bench-v2/motif-audit/`, e189abbbb) looked at 9 of the 11 bench-v2 cells accepted under amendment 1. All 9 contain an L from VIN1 to the input gate, placed across the DUT's own input DC block, and the sizer drives that block to its 51–325 fF floor.
  - The design then relies on the testbench's 10 pF `Cp1` for DC isolation.
  - With a DC-grounded source, the gate falls from 0.3 V to 0.1 V and Idd falls 65–73 %: 0/9 pass. The controls pass 2/2.
- **rl-v1 cannot see this.** Every rl-v1 deck shares the DC-blocked port.
- **Tests** (`kaggle/campaigns/bench-v2/port-dc-guard/`):
  - the 9 cells: 9/9 rejected by both checks
  - controls: 2/2 pass
  - anchors: 5/5 pass
  - shunt-L-to-VSS positive control: passes both checks
  - shorted input DC block: 5/5 fail both checks
  - cache-bridge exactness: 3/3
  - rl-v1 byte-identity: 5/5 recorded rows
  - no-profile byte-identity: 2/2

### What it does not cover

- **One condition only.** The check uses the typical corner and one source condition (DC path to ground through 50 Ω). It does not test a source that sits at a non-zero DC level.
- **Output port.** The output port keeps relying on the harness `Cp2` DC block.

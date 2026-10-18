# opamp-v0 — campaign-local op-amp verifier (Stage 1 of PREREG-OPAMP-V0-D0)

STATUS: Stage 1 DONE — verifier built, gates V1–V5 all PASS (results below). NEXT: Stage 2 (library, anchors,
witnesses [EVAL-ONLY], widened F2′ space, goldens) — not started.

Pre-registration: `kaggle/PREREG-OPAMP-V0-D0.md` (frozen at commit `d17423349`). Background:
`kaggle/SCOPING-CIRCUIT-CLASS.md`. Branch `worktree-externals-gf180`. All code and outputs live in this
directory; nothing outside it is modified (shared code is imported read-only: `lna/pdk/bptm45.py` for the model
card and VDD, `lna/null_sizer.py` for CMA-ES and the eval counter).

## Files

| file | content |
|---|---|
| `opamp_v0/dialect.py` | dialect parse / canonical format (round-trip), matched groups, parameter space, structural pre-filter |
| `opamp_v0/testbench.py` | deck generation (AnalogGym-style DC-feedback fixture), ngspice runner, metric extraction |
| `opamp_v0/sizer.py` | `size()` / `evaluate()`: seeded CMA-ES over W/L/R/C/IREF, objective modes `margin` and `max:M` |
| `circuits/*.net` | `ota5t.net` (5T OTA), `two_stage_autockt.net` (AutoCkt's two-stage, no Rz), `two_stage_rz.net` (two-stage Miller + Rz anchor) |
| `gates/v1..v5_*.py`, `gates/common.py` | the validation gates; results in `gates/results/v{1..5}.json` |
| `_scratch/` | gitignored default work dir (set `OPAMP_V0_TMP` to put ngspice temp files elsewhere) |

Run (from the worktree root, through the env wrapper so ngspice-47 and numpy are on the path):
`~/.claude/jobs/7cd7ffc3/tmp/run_cr.sh kaggle/campaigns/opamp-v0/gates/v1_determinism.py` (likewise v2…v5).

## API

```python
import sys; sys.path.insert(0, "kaggle/campaigns/opamp-v0")
import opamp_v0 as O
r = O.size(netlist_text, spec, seed=1, evals=2500, objective="margin")   # or "max:gain_db" etc.
# r: feasible, valid, metrics (full re-measure of the best point, incl. per-MOS op table 'op'),
#    margins {constraint: normalized margin}, worst_margin, target (max mode, None if infeasible),
#    params {"M1.W": .., "M1.L": .., "Cc.C": .., "IREF": ..} (SI, exactly the simulated values),
#    secs, cpu_s, evals, n_fail, best_eval, trace, prefilter {ok, why}, netlist (canonical), profile "opamp-v0"
m = O.evaluate(netlist_text, params, spec, full=True)    # one measurement
spec = {"cl_pf": 2.0, "vcm": 0.55, "vdd": 1.1, "temp_c": 27,          # testbench (these are the defaults, CL 2 pF)
        "constraints": {"gain_db": {"min": 60}, "ugf_mhz": {"min": 10}, "pm_deg": {"min": 60},
                        "idd_ua": {"max": 200}, "swing_vpp": {"min": 0.6}}}
```

Metric names (units): `gain_db`, `ugf_mhz`, `pm_deg`, `idd_ua`, `swing_vpp` (V), `swing_lo/hi` (V), `icmr_v`
(width, V), `icmr_lo/hi`, `fom_mhzpf_ma` (= UGF·CL/Idd, MHz·pF/mA, R23's M), `slew_vus` (V/µs), `cmrr_db`,
`psrr_db`, `vout_dc`, `offset_mv`, `n_unity_crossings`, `flags`, `valid`. Any of them can be a constraint or
the `max:` target.

## Design notes

**Dialect.** One device per line: `NMOS|PMOS name D G S [B]`, `R|C name P N`; `#`/`*` comments. Special nets
`VINP` (non-inverting), `VINN` (inverting), `VOUT`, `VDD`, `VSS`, `IREF` (case-insensitive in, upper-case out);
internal nets are lower-cased. Bulk defaults to VSS (NMOS) / VDD (PMOS). `format_netlist(parse(t))` is the
canonical form and is a fixed point (round-trip). **Matched groups:** a name ending in *digit + lower-case
letter* (`M1a`, `M1b`) belongs to group `M1`; all members share every sizing parameter (W and L; R or C value);
other names are their own group. Mirror ratios are expressed with separate devices (e.g. `M5`, `M6`).

**Parameters** (log-scaled box, CMA-ES works in [0,1]^n): W ∈ [0.5, 50] µm, L ∈ [45 nm, 1 µm], R ∈ [10 Ω,
100 kΩ], C ∈ [0.05, 20] pF, IREF ∈ [1, 100] µA — one W and one L per MOS group, one value per R/C group, one IREF.
5T OTA: 9 parameters; two-stage + Rz: 15.

**Structural pre-filter (0 cost; reject ⇒ `feasible=False`, 0 evals).** R0 ≤ 40 devices; R1 VINP, VINN, VOUT,
IREF present; R2 VINP/VINN touch only MOS gates and capacitors; R3 no shorted device (MOS D = S, R/C P = N);
R4 bulk is the default rail or own source; R5 every net except VINP/VINN has a DC path (R and MOS D–S only)
to a rail — this is "DC path at every D and S", "no floating gate", "no undriven bias node", "IREF can sink";
R6 VOUT is a MOS drain/source; R7 every gate net is DC-driven.

**Testbench (one deck, one DUT copy).** bptm45 (`lna/pdk/bptm45.py` → AutoCkt `45nm_bulk.txt`), VDD 1.1 V,
27 °C. `Iref` pushes the ONE ideal reference current from VDD into `IREF` (counted in Idd). `Vp` sets VINP to
Vcm (default VDD/2). DC feedback VOUT → `Vsw` (series DC source, 0 V nominal) → 1 TH → VINN; AC injected into
VINN through 1 TF; CL on VOUT. No other ideal bias. Analyses in a fixed order:
1. `op` — Idd, VOUT (+ per-MOS id/gm/gds/vgs/vds/vth/vdsat in full mode);
2. `ac dec 20 0.01 Hz … 10 GHz` — A(f) = −v(VOUT): DC gain = |A(0.01 Hz)|, UGF and PM at the interpolated
   unity crossing (phase unwrapped relative to the 0.01 Hz phase);
3. `dc Vsw` (25 mV steps, VOUT swept rail to rail at fixed input CM) — open-loop-equivalent DC transfer
   VOUT vs Vid = VINP − VINN; gain by finite differences; swing window;
4. `dc Vp × Vsw ∈ {0, 10 mV}` (25 mV steps) — follower sweep; tracking error and gain at each input CM; ICMR;
5. (full mode) AC with common-mode drive (CMRR) and with supply drive (PSRR) at 0.01 Hz;
6. (full mode, separate deck) follower transient (VINN tied to VOUT), ±0.1 V step around Vcm: slew, settling,
   ripple.
**Validity flags** (any ⇒ invalid ⇒ infeasible under every spec): `sim_fail`, `polarity` (Re A(0.01 Hz) ≤ 0),
`no_gain`, `no_unity_crossing`, `ugf_out_of_range`, `pm_unphysical` (PM > 180°), `phase_jump_below_ugf`,
`vout_not_tracking` (|VOUT − Vcm| > 50 mV), `outcm_outside_swing_window`, `idd_nonpositive`.

**Sizer.** `lna/null_sizer.run_cmaes` (Hansen purecmaes defaults, λ = 4 + ⌊3 ln n⌋, σ0 = 0.3, box by clipping,
restart on stagnation, numpy PCG64 seeded by `seed`) driven through `null_sizer._Budget` (hard stop on the
budget-th eval), both imported unmodified. The loop measures only what the spec needs (op + AC + swing always;
ICMR / CMRR-PSRR / transient only if constrained); the best point is then re-measured in full mode and
feasibility/margins are computed from that re-measure (the shared analyses run first and in the same order, so
the shared metrics are identical). Objective values (minimised; rank-based):
`margin`: infeasible 1 + Σ normalized violations, feasible −1 − worst margin; `max:M`: infeasible as above,
feasible −1 − (π/2 + atan M); invalid 100 + 10·n_flags + Σviol/10; sim failure 1e3.
Normalized margin (repo convention, `lna/datastore.margins_for`): (val − min)/s or (max − val)/s,
s = max(|limit|, 1).

## Deviations / interpretations (D-O*)

- **D-O1 Sizer reuse.** `kaggle/bench_anchor_prep.smoke_run` cannot be driven for an op-amp (its
  `prepared_body`/`make_objective` path measures LNA S-parameters). Its optimizer and counter
  (`lna/null_sizer.run_cmaes`, `_Budget`) are imported unchanged; no campaign-local optimizer copy was needed.
  No warm start (x0 = the seeded random mean, as in the null path).
- **D-O2 Units and normalization.** Metric names/units as listed above; margins use the repo scale
  max(|limit|, 1), so for limits below 1 (swing 0.6 Vpp, ICMR widths) normalized margins are in volts.
- **D-O3 Pre-filter additions** beyond the pre-reg list: R2 (inputs only on gates/caps — closes the loophole of
  drawing bias current from the testbench's ideal input sources), R4 (bulk), R1 (IREF must be used, since the
  testbench always injects it), and R5 generalised to every net.
- **D-O4 Matched groups** by the *digit + lower-case letter* suffix; all members share all parameters; no
  built-in ratios.
- **D-O5 Device emission** follows the LNA harness: NF = max(1, ⌈W / 2 µm⌉) (`lna/to_spice.W_FINGER`); no
  AS/AD/PS/PD (as in the LNA harness and AutoCkt's deck), so drain/source junction capacitance is not modelled —
  non-dominant poles (and hence PM) are somewhat optimistic for every design alike.
- **D-O6 Swing and out-CM.** Swing = width of the contiguous window around the operating output level where the
  finite-difference gain of the Vsw sweep is ≥ gain_dc − 6 dB (gain_dc from AC at 0.01 Hz), edges linearly
  interpolated in log-gain; "Vpp" = that width (single-ended). FD gain agrees with AC gain to ≤ 3 % (5T) /
  ≤ 0.5 % (two-stage, 56 dB) in the mid-range on the prototypes. The V4(c) check: the operating output level
  must lie inside the window where the FD gain is ≥ the sweep's PEAK gain − 6 dB (else
  `outcm_outside_swing_window`), and the follower must track Vcm within 50 mV (`vout_not_tracking`).
- **D-O7 ICMR.** Follower sweep of Vp (grid anchored at Vcm, 25 mV), gain at each CM by FD between the
  Vsw = 0 and Vsw = 10 mV sweeps (i.e. differential gain at fixed CM). Pass at a CM iff gain ≥ mid gain − 6 dB
  (one-sided: higher gain than mid is not a failure) AND |VOUT − Vin| ≤ 50 mV; ICMR = width of the contiguous
  window around Vcm, edges interpolated.
- **D-O8 V3 analytic form and premise.** The gated analytic gain is gm_in·(ro_in ∥ ro_load) per stage (the
  general form of "gm·ro/2", equal to it when ro_in = ro_load); the literal gm_in·ro_in/2 is reported beside
  it and is 3.7–4.5 dB off on the passing designs (the PMOS loads have longer L, hence ro_load > ro_in). The
  formula presumes all MOS saturated; designs with a device in triode (|vds| < |vdsat|) are reported, not gated.
  Also: the pre-reg names one sized 5T and one sized two-stage; V3 sizes 3 circuits × 2 objectives. Both points
  were fixed after the first V3 run, in which the margin-mode AutoCkt two-stage (mirror-output device and tail
  in triode) read −3.33 dB; that run's numbers are unchanged in the re-run below.
- **D-O9 V5 spec.** "AutoCkt's own spec" = the target in `AutoCkt/smoke_engine.py` (the only AutoCkt spec on
  disk; the yaml is not cloned): gain ≥ 300 V/V (49.54 dB), UGBW ≥ 10 MHz, PM ≥ 60°, supply current ≤ 1 mA, with
  AutoCkt's CL = 10 pF — measured under opamp-v0's conditions (VDD 1.1 V, Vcm 0.55 V, unity-feedback DC loop,
  free W/L), not AutoCkt's 1.2 V / 0.6 V open-loop testbench. A stretch spec (gain 400 V/V, UGBW 25 MHz, PM 60°,
  ≤ 100 µA, the upper ends of AutoCkt's target ranges as recalled — unverified) is informational only.
- **D-O10 PM definition.** PM = min over all downward unity crossings of 180° + phase(f_u) (relative to the
  0.01 Hz phase); UGF = first downward crossing; PM > 180° or a > 120° phase step below the UGF ⇒ invalid.
  Transient ripple/settling is reported (`tran_oscillation` flag) but does not gate: in the loop only the
  small-signal PM is the stability criterion (the transient runs only on the final winner unless slew is
  constrained).
- **D-O11 Slew** = 0.6·ΔV / (t80 − t20) of a ±0.1 V follower step, min(rise, fall); pulse width
  max(100 ns, 100/(2π·UGF)). Reported only in D0.
- **D-O12 V2** is a raw replay of the stored AutoCkt deck through the harness's ngspice runner, model path and
  row reader (the stored deck is open-loop with `m=` multipliers, not expressible in the dialect); the
  transcribed topology is what V5 sizes.
- **D-O13 V1** checks two cases (swing path in-loop and ICMR path in-loop) rather than one.
- **D-O14 Invalid ranking / violation cap.** Per-constraint violation capped at 100 normalized units in the
  objective; invalid designs rank below every valid one (graded by flag count).

## Validation gates (all PASS)

| gate | criterion (pre-reg) | result |
|---|---|---|
| **V1 determinism** | same (netlist, spec, seed) bit-identical in 3 processes | **PASS** — SHA-256 of the full result (metrics, params, margins, trace) identical in 3 concurrent processes, 2 cases, 2,500 evals each (digest `178ad097a49a…`) |
| **V2 replay** | AutoCkt's stored deck reproduces its `ac.csv` | **PASS** — 101/101 rows, max relative complex difference **0.0**, frequencies identical; DC i(vdd) identical (−47.28 µA); gain 2.0363 V/V |
| **V3 analytic** | 5T within 3 dB of gm·ro/2; two-stage within 3 dB of its two-stage product | **PASS** (see table; D-O8) |
| **V4 loopholes** | (a) floating gate / undriven bias rejected or infeasible; (b) true-crossing PM, unstable ⇒ PM < 0; (c) out-CM outside swing window flagged | **PASS** (see below) |
| **V5 sizer** | two-stage Miller, AutoCkt's spec, feasible 3/3 seeds within 2,500 evals | **PASS 3/3** (see table; D-O9) |

**V1** (results/v1.json): case A two_stage_rz, R1 hard constraints, `max:gain_db`, seed 1 → feasible, 63.50 dB, UGF 14.30 MHz, PM 83.6°, Idd 155.6 µA, swing 0.687 Vpp (best at eval 2,499);
case B ota5t, base + ICMR ≥ 0.3 V, `margin`, seed 2 → feasible, worst margin 0.577, ICMR 0.877 V, 20.45 dB (best at eval 2,454).

**V3** (results/v3.json; seed 1, 2,500 evals, hard constraints UGF ≥ 10 MHz, PM ≥ 60°, Idd ≤ 200 µA, CL 2 pF):

| circuit | objective | sim gain | gm·(ro∥ro) per stage | error | gm·ro/2 literal error | triode devices | verdict |
|---|---|---|---|---|---|---|---|
| ota5t | max:gain_db | 29.25 dB | 29.58 dB | −0.32 dB | +3.97 dB | — | PASS |
| ota5t | margin | 12.21 dB | 12.03 dB | +0.18 dB | −10.34 dB | — | PASS |
| two_stage_autockt | max:gain_db | 59.65 dB | 61.09 dB | −1.43 dB | +3.96 dB | M3 (tail) | not gated |
| two_stage_autockt | margin | 22.83 dB | 26.17 dB | −3.33 dB | −14.85 dB | M1b, M3 | not gated |
| two_stage_rz | max:gain_db | 65.04 dB | 66.34 dB | −1.30 dB | +4.53 dB | — | PASS |
| two_stage_rz | margin | 44.64 dB | 45.56 dB | −0.92 dB | +3.69 dB | — | PASS |

The 5T max-gain result (29.25 dB) reproduces the scoping ceiling (29.2 dB) found by 2,000 random sizings.

**V4** (results/v4.json):
- (a) rejected by the pre-filter at 0 evals: floating gate (R5/R7), bias node held only by a capacitor (R5/R7),
  bias taken from the input source through a resistor (R2), shorted resistor (R3), no IREF (R1), VOUT driven
  only through a capacitor (R5/R6). Informational: a tail gate tied to VSS through a resistor passes the
  pre-filter (it is DC-driven) and is infeasible at 300 evals (22.3 dB, 4.9 µA, subthreshold tail) — legitimate
  physics, not a loophole.
- (b) the V3 max-gain AutoCkt two-stage with Cc cut to 0.05 pF reads **PM = −12.34°** (UGF 110.5 MHz), its
  follower transient oscillates (ripple 0.36 V on a 0.2 V step, not settled) and it is infeasible; on 4 designs
  (stable and unstable) PM/UGF agree with a 10× denser sweep (200 pts/dec) within 0.02° / 0.1 %
  (PM 60.06 vs 60.07, −12.34 vs −12.36, 71.97 vs 71.96, 67.80 vs 67.80).
- (c) the V3 max-gain 5T at Vcm = 0.90 V: output 0.863 V where the gain is 5.4 V/V against a sweep peak of
  23.0 V/V → `outcm_outside_swing_window`, infeasible; control at Vcm = 0.55 V not flagged, feasible.

**V5** (results/v5.json; margin mode, 2,500 evals):

| run | circuit | spec | seed | feasible | worst margin | first feasible by eval | gain | UGF | PM | Idd |
|---|---|---|---|---|---|---|---|---|---|---|
| gate | two_stage_autockt | autockt-smoke | 1 | **yes** | 0.162 | 190 | 57.56 dB | 11.64 MHz | 69.7° | 423.2 µA |
| gate | two_stage_autockt | autockt-smoke | 2 | **yes** | 0.166 | 200 | 57.76 dB | 12.19 MHz | 70.0° | 442.5 µA |
| gate | two_stage_autockt | autockt-smoke | 3 | **yes** | 0.161 | 150 | 57.51 dB | 11.73 MHz | 69.7° | 410.9 µA |
| info | two_stage_rz | autockt-smoke | 1 | **yes** | 0.204 | 70 | 59.65 dB | 15.72 MHz | 72.2° | 317.2 µA |
| info | two_stage_rz | autockt-smoke | 2 | **yes** | 0.238 | 70 | 61.31 dB | 12.52 MHz | 75.6° | 121.2 µA |
| info | two_stage_rz | autockt-smoke | 3 | **yes** | 0.238 | 50 | 61.31 dB | 12.47 MHz | 74.7° | 204.5 µA |
| info | two_stage_autockt | autockt-stretch | 1 | no | -0.345 | — | 51.91 dB | 25.00 MHz | 39.3° | 99.7 µA |
| info | two_stage_autockt | autockt-stretch | 2 | **yes** | 0.029 | 1070 | 53.56 dB | 25.78 MHz | 61.9° | 96.6 µA |
| info | two_stage_autockt | autockt-stretch | 3 | **yes** | 0.048 | 600 | 54.56 dB | 26.22 MHz | 62.9° | 95.0 µA |
| info | two_stage_rz | autockt-stretch | 1 | **yes** | 0.136 | 460 | 59.15 dB | 28.40 MHz | 68.9° | 81.7 µA |
| info | two_stage_rz | autockt-stretch | 2 | **yes** | 0.142 | 200 | 59.41 dB | 28.61 MHz | 68.9° | 83.4 µA |
| info | two_stage_rz | autockt-stretch | 3 | **yes** | 0.147 | 180 | 59.68 dB | 28.73 MHz | 69.0° | 83.1 µA |

Gate: 3/3 feasible (first feasible point within 150–200 evals; "first feasible" is read from the
budget trace sampled every 10 evals). Informational: the anchor with Rz is feasible 3/3 on the same spec, and
the stretch spec is met 2/3 (AutoCkt topology) and 3/3 (with Rz).

## Cost

Per evaluation (loop mode: op + AC 241 pts + 45-pt swing sweep; ngspice-47 subprocess per eval): ngspice
≈ 14 ms of which ~2.6 ms start-up, ~2 ms op, ~4 ms AC, ~5 ms swing sweep; Python/spawn overhead ≈ 4 ms. The
ICMR sweep adds ~3–5 ms when constrained; the full re-measure of the winner (CMRR/PSRR + transient) ≈ 60–70 ms.

Per 2,500-eval sizing (18 sizings of V3 + V5, box load average ≈ 14 on 28 cores, ≤ 4 own processes):
**CPU 34 s median (20–64 s)**, wall 58 s median (43–84 s), i.e. ≈ 74 evals per CPU-second and ≈ 43 evals/s
wall per process (13.5 ms CPU, 23 ms wall per eval). The two-stage costs ~1.5× the 5T.

Stage 1 total ≈ 0.4 CPU-h (gates incl. re-runs ≈ 1,300 CPU-s, prototypes ≈ 100 CPU-s).

**Stage 3 projection.** The pre-reg's eval count (6 tasks × (F2′ 1–3k × 300 + 26 × 3 × 2,500 + confirmation +
500 × 300 two-edit)) ≈ 4–8 M evals → **15–30 CPU-h by CPU time, 26–51 process-hours by wall** at the observed
load. The upper end exceeds the pre-reg's 20–25 CPU-h estimate and could approach the 40 CPU-h ask-first line;
cheap levers (not taken, would change the measurement): AC at 10 pts/dec, 50 mV swing grid, or a persistent
libngspice instead of one subprocess per eval.

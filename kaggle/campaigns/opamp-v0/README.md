STATUS: Stage 3 (D0) DONE (2026-10-19). **Verdict STOP: 0/6 tasks accepted.** 5 of 6 tasks fail the minimum
gap. The sixth (5T/R1) fails confirmation: F1's three-stage NMC is feasible 3/3 at the confirmation spec. 17.87
CPU-h. See "Stage 3 — D0 RESULT" at the end, `stage3/d0-tables.md` and `stage3/d0-summary.json`. Runner
`stage3/d0.py` (all phases cached in `stage3/results/jobs.jsonl`; re-running any phase launches nothing).
(Stage 2 DONE; D-O16 adopted by Amendment 1.)

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
| `opamp_v0/edits.py` | Stage 2: F2′ single-edit enumerator, canonical form (dedupe), two-edit composer |
| `circuits/lib/*.net` | Stage 2 F1 library: `ota5t`, `two_stage_rz` (the anchors; identical to `circuits/*.net`), `telescopic`, `folded_cascode`, `three_stage_nmc` |
| `witnesses/` | **EVAL-ONLY** witnesses W-R1, W-R23 (AFFC from AnalogGym), W-R4 + `README.md` (mapping table) |
| `stage2/*.py` | Stage 2 drivers: `s2common` (circuits, regime specs, golden specs, job runner), `run_stage2` (all sizing jobs), `goldens`, `preview_seeds`, `f2_space`, `accuracy`, `stability_check`, `stability_gate_check`, `report` (README tables) |
| `stage2/results/` | one JSON per sizing job (`golden-*`, `max-<R>-*`), `f2_<anchor>.jsonl` (pre-filtered F2′ candidates), `f2_<anchor>_counts.json`, `two_edit_<anchor>_s1.jsonl`, `accuracy.json`, `stability_gate_check.json`, `table_all.json`; `pre_stability/` = the first (pre-gate) pass, kept as evidence for D-O16 |
| `stage3/` | Stage 3 (D0): `d0common.py` (tasks, calibrated specs, job keys, disk-robust store, throttled pool), `d0.py` (phases frontier/screen/top/confirm/analyse/status), `ceiling.py` (step-6 analytic ceiling), `report.py` (→ `d0-tables.md`, `d0-summary.json`); `results/jobs.jsonl` (every D0 sizing run), `results/ceiling.json` |
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
- **D-O15 Swing crash guard (bug fix).** `swing_metrics` raised `math domain error` when no
  point of the Vsw sweep had positive finite-difference gain (a 300-eval pilot hit it). Now
  such a design is flagged `swing_empty` + `outcm_outside_swing_window` (invalid). The path
  could never complete before, so no Stage 1 result changes (V1 re-run identical, below).
- **D-O16 Small-step stability gate (verifier extension, closes a V4(b) gap).** Stage 2 found
  multi-stage designs that read a healthy PM at the true unity crossing (94°–174°) yet
  oscillate as followers even for a 1 mV step (ripple 1.6–57× the step): right-half-plane poles
  inside the amplifier (local loops of NMC/AFFC) are invisible to an open-loop Bode PM. The
  sizer exploited it in `max:` mode (R1: NMC seeds 2 and 3 at "88+ dB"; R23: W-R23 seed 3;
  the golden NMC). Fix, opt-in per spec (`"stability": "ss_tran"`; absent ⇒ Stage 1
  behaviour bit-for-bit): a true follower (VINN tied to VOUT), one 2 mV input step at 2τ,
  window 60τ (τ = 1/(2π·UGF), ≥ 100 ns), max step τ/4; flag `ss_unstable` (invalid) iff the
  peak-to-peak ripple over the last 30 % of the window > 5 % of the step, or the settled
  change is off the step by > 20 %, or the transient does not complete. In the loop it runs
  only on points that are otherwise valid AND meet every constraint (lazy; infeasible points
  cost nothing extra); the final full re-measure always runs it. Validation
  (`stage2/stability_gate_check.py`, `results/stability_gate_check.json`): on all 38
  pre-gate Stage-2 designs it agrees 38/38 with the independent diagnostic
  (`stage2/stability_check.py`: 1 mV two-edge step, 1,000 points); stable designs show
  ripple ≤ 0.019, unstable ones ≥ 1.6. **Every Stage-2 spec (goldens, regimes) carries it;
  Stage 3 should too** — this is the pre-reg's V4(b) intent ("a deliberately unstable
  design reads … 'unstable'"), but it is a change to the verifier's stability criterion
  (D-O10) and so is flagged for the user. Pre-gate results are archived in
  `stage2/results/pre_stability/`. The large-signal ±0.1 V transient stays report-only.
- **D-O17 F2′ enumeration (interpretation).** Nets offered: every net of the anchor plus VDD and VSS, in a
  fixed order (VINP VINN VOUT VDD VSS IREF, then internal nets sorted). *Add R/C*: every unordered pair of
  existing nets (no new net). *Add MOS*: NMOS then PMOS, D/G/S each on an existing net or on the one new net
  `nx1` (the new net may sit on 1–3 terminals; on the gate only it is floating and the pre-filter drops it);
  bulk = default rail; name `MX1` (own matched group, so +2 sizing parameters). *Delete*: any one element
  (deleting one member of a matched pair leaves the other in its group). *Re-wire*: one of D/G/S (MOS) or P/N
  (R/C) of one element to any other existing net or to `nx1`; bulk is not a re-wire target (a MOS with bulk on
  its source keeps bulk = source). The raw count includes D = S additions and D/S mirror images; **dedupe** is
  by a canonical form = the circuit up to renaming of internal nets and devices, keeping the matched-group
  partition (it changes the sizing problem), with MOS D/S unordered when bulk is the rail (BSIM4 is S/D
  symmetric) and R/C terminals unordered; the canonical labeling is the minimum over all internal-net
  permutations inside colour-refinement classes (exact for these sizes; a > 40,320-permutation fallback to the
  refined order is never reached: the largest permutation count over all F2′ candidates and two-edit designs is 2). The first descriptor in
  enumeration order represents each unique design; designs equal to the anchor are dropped (none occur). The
  pre-filter is the Stage 1 one, unchanged. Checks (all pass): enumeration deterministic, canonical key
  invariant under random renaming of nets/devices and line order (anchor + every 50th candidate).
- **D-O18 Two-edit composer.** `edits.two_edit_sample(text, n, seed)`: `random.Random(seed)`; edit 1 uniform
  over the anchor's raw descriptors, edit 2 uniform over the raw descriptors of the intermediate (new names
  `MX2/RX2/CX2`, new net `nx2`); the intermediate need not pass the pre-filter (deep changes go through broken
  states), the result must; designs equal to the anchor or to any single-edit design (canonical form) and
  repeats are rejected and redrawn. Uniform-over-descriptors weights edit kinds by their descriptor counts (≈ 70 %
  of kept designs are add-MOS + add-MOS). `stage2/results/two_edit_<anchor>_s1.jsonl` holds the 500 designs of
  seed 1 (deterministic; checked by re-drawing).
- **D-O19 Library/witness design choices and golden specs.** In-netlist bias for the cascode circuits is one
  "R-shifted diode" cell: `IREF → Rb → n1` with the NMOS diode at `n1` (tail/sink mirror gate) and the NMOS
  cascode gate on the `IREF` net (= Vgs + IREF·Rb); an NMOS copy of the reference into a PMOS diode `pa` (PMOS
  source gate) with `Rp` dropping the PMOS cascode gate `vbp` below `pa`. The telescopic uses a high-swing
  PMOS cascode mirror (top gates on the diode-side cascode drain). The NMC has a non-inverting second stage
  (PMOS CS → NMOS diode → mirror) so both Miller loops are negative. The anchors are the Stage 1 files copied
  unchanged into `circuits/lib/`. The golden **demonstration specs** were chosen by the Stage-2 builder after a
  300-eval max-gain pilot of every circuit (not D0 specs): the base UGF/PM/Idd constraints at CL 2 pF plus one
  circuit-appropriate requirement (table below).
- **D-O20 Measurement-accuracy check (added by the parent).** `stage2/accuracy.py`: for every sized Stage-2
  design of a cascode/multi-stage circuit with verifier gain ≥ 75 dB, four independent low-frequency readings —
  same fixture with tight tolerances (reltol 1e-6, abstol 1e-15, vntol 1e-12); AC injected at VINP instead of
  VINN; the latter with gmin 1e-15; and a DC finite difference (Vsw ± 2 mV in 0.25 mV steps, least-squares slope
  of ΔVOUT vs Vid computed inside ngspice). Flag if any differs from the verifier by > 1 dB.
- **D-O21 W-R23 transcription.** AnalogGym `HoiLee_AFFC_Pin_3`; one matched group per (AnalogGym W/L variable,
  multiplier); the ideal sink I0 out of the PMOS bias diode becomes IREF + a 1:1 NMOS mirror (+2 devices);
  AnalogGym's dummy branch (xm2/xm14/xm19) dropped; no ideal bias voltages to replace. Full table in
  `witnesses/README.md`. AFFC was taken as the first of the two R3-type candidates named in the scoping doc (AFFC, DFCFC);
  DFCFC1 (also on disk) was not tried.
- **D-O22 Preview runs beyond the brief.** Besides the requested seed-1 `max:` run per witness, the witnesses and
  the best F1 circuit(s) of each regime were also sized at seeds 2 and 3, and all of F1 at seed 1 under every
  regime, to preview Stage 3's calibration (witness feasibility at 3 seeds) and the gap. **These are not D0
  numbers** (no F2′, no top-20, no confirmation, no two-edit check).

- **D-O23 CMRR/PSRR crash guard (Stage 3 bug fix, `opamp_v0/testbench.py`).** In the R1 screen, the full
  re-measure of one F2′ winner (`F2:two_stage_rz:371`, an NMOS added VOUT/IREF/n4) raised `IndexError`: its ICMR
  DC sweep aborted part-way, the CM and supply AC analyses then did not run, and `wrdata` wrote the previous
  real-valued plot into `cm.txt`/`ps.txt`. CMRR/PSRR (report-only) are now left unset unless the file holds the
  one complex row. The path could never complete before, so no completed result changes; the job is re-run.

- **D-O24 Shared frontier runs.** F1 and witness `max:M` runs depend only on the regime, so each (circuit,
  regime spec, seed) is run once and used by both anchors of the regime (exact-key cache in
  `stage3/results/jobs.jsonl`; the key hashes canonical netlist, constraints, CL, stability, objective, seed,
  evals). The same key sharing applies to any identical confirmation job.
- **D-O25 Top-20 ranking of a screen** (F2′ and two-edit alike): feasible designs first by M (desc), then
  infeasible ones by the sizer's best loop objective (closest to feasibility), ties by enumeration index.
- **D-O26 Reference set and gap.** max_d M*(d) is taken over the designs that have a 3-seed M*: F1 (5) ∪ top-20
  F2′ of the task's anchor; the other F2′ designs only have the 300-eval screen. Top-5 references = the top 5 of
  that set by M* (ties: mean of feasible seeds, then name). R23's minimum gap = 25 % of max_d M*(d). (Unused
  edge rule: all references infeasible ⇒ G = +∞, flagged; did not occur.)
- **D-O27 Analytic ceiling.** gm/gds of one device, W 10 µm, L 1 µm, bptm45, 27 °C, grid |Vgs| 0–1.1 V (10 mV)
  × |Vds| 0.05–1.1 V (50 mV), |id| ≥ 1 nA (`stage3/ceiling.py`): best PMOS 119.8 (41.57 dB, Vsg 0.26 V,
  Vsd 1.05 V); NMOS 57.9 (35.26 dB). Ceiling = k·41.57 dB, with k = number of gm·ro factors in the ideal gain
  (a cascoded stage counts 2, not 1 — the literal "stages" would undercount cascodes and would not be a
  ceiling): 5T 1, two-stage 2, telescopic 2, folded 2, NMC 3, W-R1 3, W-R23 4, W-R4 3; an F2′ / two-edit design
  gets its anchor's k plus one per added MOS (an upper bound). For R23/R4 (M is not a gain) the ceiling is
  reported as a gain ceiling against the regime's gain floor.
- **D-O28 Confirmation details.** 2,500 evals, margin objective, spec = hard constraints + `M ≥ max_d M*(d) +
  G/2`. "Worst normalized margin ≤ −G/4 in M's normalized units" = the run's worst margin (min over all
  constraints at the full re-measure of its best point) ≤ −(G/4)/max(|limit|, 1), required at each of the 3
  seeds. Confirmation runs only for tasks that pass the minimum gap (step 2: below it ⇒ not accepted).
- **D-O29 Two-edit check.** The Stage-2 seed-1 sample (500 per anchor) is screened under each regime of the
  anchor; the top 20 of each screen (D-O25) are re-run at 2,500 evals × seed 1 — mirroring step 1's top-20 rule
  (the pre-reg does not say which screened designs get the 2,500-eval run). This is G-independent and was run for
  all 6 tasks; the label exists only where a threshold exists (gap passed).
- **D-O30 Conduct and a determinism caveat.** ≤ 8 worker processes (a worker above rank 4 waits while
  load1 > 22; load stayed ≈ 11–14), D32-style append (fsync, torn-line repair, ENOSPC back-off, no launch below
  5 GB free), CPU guard at 38 CPU-h. **Caveat:** of the 30 D0 jobs identical to Stage-2 preview jobs, 29 are
  bit-identical; R23 three-stage NMC seed 1 is not (D0 6,802 vs Stage 2 18,146 MHz·pF/mA). Re-run alone on a
  quiet box it reproduces Stage 2 exactly (18,146, 0 sim failures); the D0 run had 1 simulation failure, most
  likely the 60 s wall-clock ngspice timeout firing under load, which changes the CMA-ES trajectory. So results
  are deterministic only when no simulation hits the wall-clock timeout. 41 of 7,965 D0 jobs had ≥ 1 sim failure
  (most are two-stage F2′/two-edit screens). The affected median (R23 NMC M* 18,997) is the same either way, and
  the verdict does not depend on it (see the Stage 3 result).
- **D-O31 Incident.** A duplicate `screen R1,R23` run was started by mistake without a log and killed after about
  1 min; killed workers leave no record (results are appended by the parent only), and the exact-key resume
  re-ran everything that was missing. No result is affected.

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

## Stage 2 — library, anchors, witnesses, F2′, goldens

Commits on `worktree-externals-gf180` (see `git log -- kaggle/campaigns/opamp-v0`). Everything was sized with
the Stage 1 sizer (seed 1 unless stated, 2,500 evals) **with the small-step stability gate on** (D-O16); the
first, pre-gate pass is archived in `stage2/results/pre_stability/`. Reproduce: `stage2/run_stage2.py` (all
sizing jobs, resumable), `stage2/f2_space.py`, `stage2/accuracy.py`, `stage2/stability_gate_check.py`,
`stage2/report.py` (prints the tables below).

**Built.** F1 library `circuits/lib/` (5T OTA, two-stage Miller + Rz, telescopic cascode, folded cascode,
three-stage NMC); anchors = `circuits/lib/ota5t.net`, `circuits/lib/two_stage_rz.net` (the Stage 1 files,
unchanged); EVAL-ONLY witnesses `witnesses/` (W-R1 folded cascode + CS with Miller + Rz; W-R23 AFFC three-stage
transcribed from AnalogGym `HoiLee_AFFC_Pin_3`; W-R4 complementary N+P pairs + folded-cascode summing + CS with
Miller + Rz). All pass the pre-filter; one IREF, every other bias in-netlist; matched groups per D-O4.

### Goldens (margin mode at a demonstration spec, D-O19)

| circuit | devices / params | demo spec (margin mode, + stability gate) | feasible | worst margin | gain dB | UGF MHz | PM ° | Idd µA | swing Vpp | ICMR V | FOM MHz·pF/mA | CPU s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ota5t | 6 / 9 | CL 2 pF; gain_db ≥ 25, idd_ua ≤ 200, pm_deg ≥ 60, ugf_mhz ≥ 10 | yes | 0.170 | 29.26 | 20.41 | 79.8 | 42.0 | 0.476 | 0.701 | 971 | 35 |
| two_stage_rz | 10 / 15 | CL 2 pF; gain_db ≥ 55, idd_ua ≤ 200, pm_deg ≥ 60, swing_vpp ≥ 0.6, ugf_mhz ≥ 10 | yes | 0.184 | 65.11 | 13.12 | 71.3 | 90.4 | 0.806 | 0.535 | 290 | 37 |
| telescopic | 14 / 19 | CL 2 pF; gain_db ≥ 45, idd_ua ≤ 200, pm_deg ≥ 60, ugf_mhz ≥ 10 | yes | 0.236 | 55.62 | 21.88 | 76.2 | 78.5 | 0.307 | 0.203 | 558 | 78 |
| folded_cascode | 16 / 21 | CL 2 pF; gain_db ≥ 45, idd_ua ≤ 200, pm_deg ≥ 60, ugf_mhz ≥ 10 | yes | 0.276 | 57.41 | 15.41 | 77.0 | 116.6 | 0.362 | 0.316 | 264 | 51 |
| three_stage_nmc | 16 / 25 | CL 2 pF; gain_db ≥ 75, idd_ua ≤ 200, pm_deg ≥ 55, ugf_mhz ≥ 5 | yes | 0.198 | 89.83 | 6.19 | 70.4 | 101.7 | 0.625 | 0.570 | 122 | 136 |
| W-R1 | 20 / 27 | CL 2 pF; gain_db ≥ 70, idd_ua ≤ 200, pm_deg ≥ 60, swing_vpp ≥ 0.6, ugf_mhz ≥ 10 | yes | 0.156 | 80.95 | 11.68 | 75.6 | 137.5 | 0.761 | 0.558 | 170 | 138 |
| W-R23 | 31 / 31 | CL 200 pF; gain_db ≥ 80, idd_ua ≤ 300, pm_deg ≥ 55, ugf_mhz ≥ 1 | yes | 0.065 | 85.17 | 2.37 | 60.8 | 180.6 | 0.756 | 0.589 | 2624 | 150 |
| W-R4 | 23 / 31 | CL 2 pF; gain_db ≥ 40, icmr_v ≥ 0.8, idd_ua ≤ 200, pm_deg ≥ 60, ugf_mhz ≥ 5 | yes | 0.079 | 44.93 | 6.21 | 70.0 | 41.9 | 0.916 | 0.879 | 296 | 151 |

All 8 feasible. FOM = UGF·CL/Idd. `tran_oscillation` (large-signal ±0.1 V step, report-only) is set on the
W-R23 golden only; it is small-signal stable (gate passed).

### Witness `max:M` under its regime's hard constraints — and a PREVIEW against F1

**PREVIEW, not D0** (D-O22): one to three seeds, F1 only (no F2′, no top-20, no confirmation, no two-edit
check, no analytic backstop). Hard constraints = pre-reg Stage 3 + the stability gate. Values are M of
feasible runs.

**R1** (max:gain_db; CL 2 pF; swing_vpp ≥ 0.6, ugf_mhz ≥ 10, pm_deg ≥ 60, idd_ua ≤ 200)

| design | seed 1 | seed 2 | seed 3 | median (infeasible = −∞) | seed-1 gain / UGF / PM / Idd |
|---|---|---|---|---|---|
| W-R1 | 61.02 | 82.27 | 86.99 | 82.27 | 61.02 / 16.39 / 62.1 / 169.2 |
| ota5t | 28.55 |  |  |  | 28.55 / 34.79 / 70.7 / 102.2 |
| two_stage_rz | 63.50 |  |  |  | 63.50 / 14.30 / 83.6 / 155.6 |
| telescopic | 32.66 |  |  |  | 32.66 / 27.93 / 76.9 / 90.2 |
| folded_cascode | 58.80 |  |  |  | 58.80 / 22.20 / 60.9 / 131.7 |
| three_stage_nmc | 58.51 | 89.73 | infeasible (ss_unstable) | 58.51 | 58.51 / 13.18 / 72.4 / 109.6 |

**R23** (max:fom_mhzpf_ma; CL 200 pF; gain_db ≥ 80, pm_deg ≥ 55, idd_ua ≤ 300)

| design | seed 1 | seed 2 | seed 3 | median (infeasible = −∞) | seed-1 gain / UGF / PM / Idd |
|---|---|---|---|---|---|
| W-R23 | 14502 | 15272 | 19953 | 15271.52 | 82.43 / 4.56 / 62.6 / 62.9 |
| ota5t | infeasible |  |  |  | 29.26 / 0.03 / 92.0 / 16.6 |
| two_stage_rz | infeasible |  |  |  | 66.25 / 1.53 / 72.3 / 90.7 |
| telescopic | infeasible |  |  |  | 55.64 / 0.09 / 90.0 / 56.1 |
| folded_cascode | infeasible |  |  |  | 64.88 / 0.25 / 89.3 / 260.3 |
| three_stage_nmc | 18146 | 20101 | 18997 | 18996.96 | 80.16 / 2.82 / 55.4 / 31.1 |

**R4** (max:icmr_v; CL 2 pF; gain_db ≥ 40, ugf_mhz ≥ 5, pm_deg ≥ 60, idd_ua ≤ 200)

| design | seed 1 | seed 2 | seed 3 | median (infeasible = −∞) | seed-1 gain / UGF / PM / Idd |
|---|---|---|---|---|---|
| W-R4 | 0.970 | 0.913 | 0.963 | 0.963 | 46.08 / 21.90 / 91.8 / 199.0 |
| ota5t | infeasible |  |  |  | 29.27 / 20.19 / 81.2 / 137.7 |
| two_stage_rz | 0.834 | 0.861 | 0.831 | 0.834 | 40.73 / 14.93 / 87.8 / 19.3 |
| telescopic | 0.366 |  |  |  | 40.31 / 9.72 / 87.9 / 47.9 |
| folded_cascode | 0.766 |  |  |  | 40.04 / 5.85 / 66.8 / 27.3 |
| three_stage_nmc | 0.873 |  |  |  | 44.45 / 6.87 / 67.9 / 48.7 |

Witness feasibility under the regime's hard constraints: **W-R1 3/3, W-R23 3/3, W-R4 3/3** — no relaxation
ladder step would be needed. Preview gaps (witness median − best F1 median/seed-1 value):
- **R1:** W-R1 82.27 dB vs best F1 at seed 1 = two-stage 63.50 dB (+18.8 dB); but the three-stage NMC reached
  89.73 dB at seed 2 (seed 1 58.51, seed 3 infeasible/unstable): sizer spread on the 25–27-parameter circuits is
  ±15 dB, and W-R1 itself read 61.02 dB at seed 1. The 3-seed medians favour W-R1 (82.27 vs NMC 58.51), but the
  sign of R1's gap rests on CMA-ES luck at seeds 1–3, not on a physical bound (both are (gm·ro)³-class).
- **R23:** W-R23 median 15,272 vs three-stage NMC median 18,997 MHz·pF/mA — **the witness loses (−20 %)**; all
  1–2-stage F1 circuits are infeasible (gain < 80 dB). R23 is likely not accepted unless F2′ adds nothing above NMC
  AND the witness sizes better in Stage 3 — it would need +25 %.
- **R4:** W-R4 median 0.963 V vs two-stage median 0.834 V (+0.129 V), NMC 0.873 V (seed 1): **below the 0.15 V
  minimum gap** at this preview. The ICMR definition (D-O7: gain within 6 dB of mid + tracking ≤ 50 mV) lets a
  single NMOS pair read ~0.83–0.86 V (down to ~0.17 V input CM) because in weak inversion the DC gain of the
  pair barely falls with its tail current; it is UGF, not DC gain, that collapses, and UGF is only checked at Vcm.

### F2′ single-edit space per anchor (D-O17) and two-edit sample (D-O18)

Kinds given as raw / unique / after pre-filter.

| anchor | nets / devices | raw edits | unique (canonical) | after pre-filter | addRC | addMOS | del | rewire | pre-filter rejects (first rule) | two-edit kept / tries |
|---|---|---|---|---|---|---|---|---|---|---|
| ota5t | 8 / 6 | 1664 | 1016 | **476** | 56/56/43 | 1458/810/348 | 6/6/3 | 144/144/82 | R1 18, R2 343, R3 138, R5 41 | 500 / 1894 |
| two_stage_rz | 10 / 10 | 3042 | 1831 | **995** | 90/90/73 | 2662/1452/736 | 10/10/6 | 280/279/180 | R1 22, R2 515, R3 218, R5 81 | 500 / 1487 |

Stage 3 screens the **after pre-filter** lists (`stage2/results/f2_<anchor>.jsonl`): 476 (5T) and 995
(two-stage) designs per task. Most pre-filter rejects are R2 (an input on a drain/source/resistor) and R3
(shorted device).

### Measurement accuracy of the DC gain (D-O20)

| design | verifier | AC@VINN tight | AC@VINP tight | AC@VINP gmin 1e-15 | DC FD tight | max diff | flag |
|---|---|---|---|---|---|---|---|
| golden-W-R1 | 80.948 | 80.948 | 80.946 | 80.946 | 80.948 | 0.003 | ok |
| golden-W-R23 | 85.166 | 85.166 | 85.192 | 85.192 | 85.167 | 0.026 | ok |
| golden-three_stage_nmc | 89.826 | 89.826 | 89.835 | 89.836 | 89.825 | 0.010 | ok |
| max-R1-W-R1-s2 | 82.269 | 82.269 | 82.277 | 82.277 | 82.269 | 0.008 | ok |
| max-R1-W-R1-s3 | 86.988 | 86.988 | 87.010 | 87.010 | 86.989 | 0.021 | ok |
| max-R1-three_stage_nmc-s2 | 89.734 | 89.734 | 89.757 | 89.757 | 89.733 | 0.023 | ok |
| max-R1-three_stage_nmc-s3 | 80.419 | 80.419 | 80.430 | 80.430 | 80.419 | 0.010 | ok |
| max-R23-W-R23-s2 | 80.387 | 80.387 | 80.397 | 80.397 | 80.387 | 0.010 | ok |
| max-R23-W-R23-s3 | 82.692 | 82.692 | 82.693 | 82.693 | 82.692 | 0.002 | ok |
| max-R23-W-R23 | 82.433 | 82.433 | 82.433 | 82.433 | 82.435 | 0.002 | ok |
| max-R23-three_stage_nmc-s2 | 80.498 | 80.498 | 80.506 | 80.506 | 80.498 | 0.009 | ok |
| max-R23-three_stage_nmc-s3 | 81.020 | 81.020 | 81.023 | 81.023 | 81.020 | 0.003 | ok |
| max-R23-three_stage_nmc | 80.162 | 80.162 | 80.199 | 80.199 | 80.163 | 0.036 | ok |

13 designs between 80 and 90 dB (all Stage-2 cascode/multi-stage designs ≥ 75 dB): every independent reading
agrees with the verifier within **0.036 dB**; none is flagged (> 1 dB). gmin (1e-12 → 1e-15) moves the gain by
≤ 1e-4 dB. No Stage-2 design exceeds ~90 dB, so the > 100 dB numerics caution of the scoping doc is not
exercised here.

### Stability gate evidence (D-O16)

`stage2/results/stability_gate_check.json`: the 38 pre-gate designs re-measured with the gate agree 38/38 with
the independent 1,000-point, two-edge diagnostic; 4 designs that read feasible were small-signal unstable
(golden NMC PM 155.6°; R1 NMC seeds 2/3 at PM 174.2°/137.3° and "89–90 dB"; R23 W-R23 seed 3 PM 93.8°). With the
gate, the golden NMC re-sized to a stable 89.83 dB / PM 70.4°, and R1 NMC seed 3 ended infeasible (its best
point was unstable). Loop-eval cost when the gate runs: 17.5 → 34 ms median (the gate runs only on otherwise-
feasible points).

### V1 re-check after the Stage-2 changes

**PASS.** `gates/v1_determinism.py` re-run at the end of Stage 2 (3 processes, 2 cases × 2,500 evals): digests identical across processes AND identical to the Stage 1 digest `178ad097a49a…` (`gates/results/v1.json` unchanged) — the Stage-2 changes (D-O15, opt-in D-O16) leave specs without `stability` bit-for-bit unchanged. The gated path is deterministic too: `stage2/gated_determinism.py` (three-stage NMC, R1 + gate, seed 3, a run where the gate fires) gives one digest in 3 processes (`f406fff14623…`) and the same parameters as the stored Stage-2 result (`stage2/results/gated_determinism.json`).

### Cost (Stage 2)

Stage 2 CPU: gated sizing runs 3,734 s; pre-gate pass 2,764 s; plus pilots/checks/V1 ≈ 0.2 CPU-h → **≈ 2.0 CPU-h total**. Per-run CPU with the gate (2,500 evals): 5T ≈ 25 s, two-stage ≈ 36 s, telescopic/folded ≈ 55 s,
three-stage NMC ≈ 80–340 s (median ≈ 140 s), witnesses 95–250 s.

**Stage 3 projection with these F2′ sizes** (gate on; per-eval CPU from the runs above):
F2′ screens 3 × (476 + 995) × 300 = 1.32 M evals ≈ 5.0 CPU-h; two-edit screens 6 × 500 × 300 = 0.9 M ≈ 3.3 CPU-h;
frontier (F1 + W + top-20) × 3 seeds × 2,500 per task ≈ 3,500 CPU-s × 6 ≈ 5.9 CPU-h (≈ 1 CPU-h less if F1 and W
runs are shared between the two anchors of a regime, which the protocol allows since they do not depend on the
anchor); confirmation ≈ 1.8 CPU-h; two-edit hit re-runs small. **Total ≈ 16–20 CPU-h** (inside the pre-reg's
20–25 CPU-h; wall ≈ 1.7× CPU per process at the box's load).

### Risks for Stage 3

1. **D-O16 needs a ruling.** The stability gate changes the verifier's stability criterion (D-O10) from PM-only to
   PM + small-step follower; without it, `max:` runs on three-stage designs exploit RHP-pole designs (the
   pre-gate R1 preview had NMC "winning" with unstable designs). Recommended: Stage 3 uses the gated specs in
   `stage2/s2common.py` (`REGIMES`).
2. **Sizer variance on 25–31-parameter circuits** (R1 NMC 58.5 / 89.7 / infeasible; W-R1 61.0 / 82.3 / 87.0;
   W-R23 14.5k–20.0k). The 3-seed median at 2,500 evals may decide gaps by luck. The analytic backstop (step 6)
   should be reported beside every M*; consider asking for a larger witness budget only if pre-registered.
3. **R1 depth is doubtful by construction:** F1 contains the three-stage NMC, which is in the same (gm·ro)³ gain
   class as W-R1 and swings ≥ 0.6 Vpp; R1's gap then rests on sizer luck.
4. **R23 witness currently loses to F1's NMC** (−20 % at the 3-seed median). A different R23 witness (e.g.
   DFCFC1) or more sizer budget could change this; neither is in the pre-registration.
5. **R4's ICMR metric is lenient** (see above): the preview gap 0.13 V < 0.15 V.
6. Taken together the preview points toward **few accepted tasks** (R1 uncertain, R23 and R4 likely not
   accepted) — i.e. toward STOP or "discuss" — before F2′ and the two-edit check are even run. This is a
   preview, not the D0 verdict.
7. F2′ two-edit designs are ≈ 70 % add-MOS + add-MOS (uniform over descriptors, D-O18); rewires/deletes are
   rare in the sample.

## Stage 3 — D0 RESULT

**Verdict: STOP** — 0 of 6 tasks accepted (pre-reg step 5: STOP iff ≤ 1 accepted). Run exactly as frozen
(PREREG Stage 3 + Amendment 1: stability gate on in every spec); interpretations D-O24…D-O31; one verifier crash
guard D-O23. Calibration ladder not needed: every witness was feasible at the hard constraints at 3/3 seeds
(step 0). Full tables: `stage3/d0-tables.md`; machine-readable: `stage3/d0-summary.json`; every sizing run:
`stage3/results/jobs.jsonl` (7,965 jobs). `python lna/ref/check_ref.py`: GREEN at the end.

| task | witness M* (seeds 1/2/3) | best reference (M*, seeds) | G vs minimum | confirmation | two-edit | ceilings W / ref (dB) | accepted |
|---|---|---|---|---|---|---|---|
| 5T / R1 (dB) | 82.27 (61.02 / 82.27 / 86.99) | F1 two-stage 63.50 (63.50 / 59.48 / 64.37) | +18.77 ≥ 6 ✓ | **fails**: W 3/3 feasible at gain ≥ 72.89, but F1 three-stage NMC feasible 3/3 (77.6 / 87.4 / 78.4 dB); other 4 refs meet the rule | not "≤ 2 edits" (best 41.3 dB) | 124.7 / 83.1 | no |
| two-stage / R1 (dB) | 82.27 | F2′ `addMOS NMOS IREF n5 n4` 79.86 (79.86 / 86.92 / 79.63) | +2.41 < 6 ✗ | not run | — | 124.7 / 124.7 | no |
| 5T / R23 (MHz·pF/mA) | 15,272 (14,502 / 15,272 / 19,953) | F1 three-stage NMC 18,997 (6,802 / 20,101 / 18,997) | −3,725 (−19.6 %) < +25 % ✗ | not run | — | 166.3 / 124.7 | no |
| two-stage / R23 | 15,272 | F2′ `addMOS NMOS VOUT n4 IREF` 19,205 (11,291 / 19,205 / 28,961) | −3,934 (−20.5 %) ✗ | not run | — | 166.3 / 124.7 | no |
| 5T / R4 (V) | 0.963 (0.970 / 0.913 / 0.963) | F1 three-stage NMC 0.873 (0.873 / 0.899 / 0.823) | +0.090 < 0.15 ✗ | not run | — | 124.7 / 124.7 | no |
| two-stage / R4 (V) | 0.963 | F2′ `addMOS PMOS VDD VOUT IREF` 0.969 (0.964 / 0.969 / 0.969) | −0.006 ✗ | not run | — | 124.7 / 124.7 | no |

**Reading.**
- The verdict does not depend on F2′, the two-edit check or the one non-reproducible run (D-O30). With F1 alone
  as references: R23's witness loses to F1's NMC (−20 %), R4's gap is 0.09 V vs NMC (< 0.15 V), and both R1 tasks
  fail confirmation because F1's NMC is feasible 3/3 at the R1 confirmation spec.
- **Sizer spread decided the one gap that passed.** In R1 the NMC's `max:gain` M* is 58.51 dB (seed 1 stuck at
  58.5, seed 2 89.7, seed 3 infeasible), yet the margin objective at "gain ≥ 72.89 dB" finds it feasible at all 3
  seeds. The frontier step (median of 3 `max:` runs at 2,500 evals) underestimated a 25-parameter reference;
  confirmation caught it. W-R1 itself spans 61.0–87.0 dB across seeds.
- **Single edits to the two-stage anchor reach the witnesses.** One added NMOS from the bias/diode net
  (`IREF n5 n4`) gives 79.9–86.9 dB under R1 (the anchor reaches 63.5); one added NMOS (`VOUT n4 IREF`) meets
  80 dB at 200 pF and beats W-R23 on R23's FOM; one added PMOS beats W-R4 on ICMR. Most look like positive
  feedback through the IREF/bias network. They were not checked for robustness (corners, mismatch), which this
  verifier does not measure.
- **Backstop (step 6):** in R1 every reference's analytic ceiling (two-stage 83.1 dB, NMC 124.7 dB) is at or above
  the witness M* (82.3 dB), so no R1 gap would have been forced by the ceiling. Share of the dB ceiling reached by M*:
  W-R1 66 %, two-stage 76 %, NMC 47 % (its best seed, 89.7 dB, 72 %). R23/R4 gain floors (80 / 40 dB) are below every relevant ceiling.
- Two-edit screens (for the record): best 2,500-eval results 41.3 dB (5T/R1), 73.1 dB (two-stage/R1), 1,265
  (5T/R23), 14,960 (two-stage/R23), 0.894 V (5T/R4), 0.972 V (two-stage/R4).

**CPU:** 17.87 CPU-h (frontier 1.80, F2′ screens 5.66, two-edit screens 4.10, top-20 F2′ 4.22, top-20 two-edit
1.75, confirmation 0.34), plus ≈ 0.1 CPU-h diagnostics. That is inside the 16–20 CPU-h projection and the 40 CPU-h
line. Wall time ≈ 4.5 h at 8 processes. Determinism: 29 of 30 runs that coincide with Stage-2 preview runs are
bit-identical; the exception and its cause are in D-O30.

Reproduce (from the worktree root): `run_cr.sh kaggle/campaigns/opamp-v0/stage3/d0.py frontier|screen <R>|top|confirm`
(all cached → no runs), `stage3/ceiling.py`, `stage3/report.py`.

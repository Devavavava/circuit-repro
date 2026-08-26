# Harness roadmap -- new RF classes + PDK abstraction (v0)

This wave adds three RF measurement-class harnesses and a PDK abstraction to the
`lna/` harness, following house culture: **measurement-first, every harness ships
with a closed-form analytic golden** (the same discipline as the NF 3.0103 dB
golden in `extract.py --selftest` and `lna/ref/check_*.py`). Nothing here touches
`kaggle/loop/`, `kaggle/kernels/`, `kaggle/specs-ladder/`, or `engineer/`.

All goldens below are GREEN on this box (ngspice-47, `$NGSPICE`). Run them with
`source env.sh; export LNA_DEPS_ROOT=<repo>` first.

---

## Class harnesses

### PA -- `lna/pa_harness.py`  (circuit_class: pa)
- **v0 measures:** small-signal gain, P1dB (input- and output-referred, by
  linear interpolation of the gain-vs-Pin curve), Psat (max Pout in the sweep,
  honestly flagged `psat_is_bound=True` when the output is still rising), PAE and
  drain efficiency at P1dB (Pdc = Vdd * Idd read from the deck's own DC op).
- **Reuses:** iip3.py's coherent transient + rectangular-window DFT tone
  extraction (single tone), so PA numbers inherit the IIP3 golden's proven
  extraction arithmetic; the Thevenin 50-ohm drive matches the sp claim.
- **Golden:** `lna/ref/check_pa.py` -- behavioral amp `y = g1*x - g3*x^3` whose
  P1dB is closed form (`A^2_1dB = (0.10875*4/3)*g1/g3`, derived in the file),
  plus a PAE arithmetic sanity. GREEN: measured P1dB within 0.08 dB of analytic
  on two (g1,g3) pairs; internal identity `P1dB_out = P1dB_in + gain - 1` to
  0.000 dB; PAE/drain arithmetic exact.
- **Runtime:** ~0.3-0.7 s per swept point on a behavioral deck (measured); a
  10-point sweep golden run is ~15 s total. Device decks are a few seconds/point.
- **Out of scope v0:** load-pull (fixed 50 ohm), AM-PM, harmonic-power table
  beyond the fundamental. Documented in the module docstring.

### Mixer -- `lna/mixer_harness.py`  (circuit_class: mixer)
- **v0 measures:** conversion gain (RF tone + LO drive, IF magnitude at
  |f_rf-f_lo|), LO-to-RF and LO-to-IF feedthrough (LO-tone extraction on those
  ports), input-referred IIP3 via two RF tones with IM3 extracted at the IF
  (reuses `iip3.iip3_sweep` verbatim, tone plan shifted to the IF grid).
- **Golden:** `lna/ref/check_mixer.py` -- ideal multiplier `IF = k*v(lo)*v(rf)`;
  conversion gain closed form `20*log10(k*A_lo/2)` (derived in the file). GREEN:
  conv gain 0.00 dB and -6.02 dB to 0.0001 dB; LO isolation > 178 dB (ideal, no
  leakage path); IIP3 within 0.005 dB of closed form, IM3 slope 3.0000.
- **Runtime:** conversion-gain/isolation is one transient (~0.5-1 s behavioral);
  IIP3 is an N-point Pin sweep (same budget as `iip3.iip3_sweep`). Golden ~6 s.
- **OUT OF SCOPE v0 -- mixer NOISE FIGURE.** ngspice has no PSS/pnoise. A
  mixer's NF is cyclostationary (SSB vs DSB, folded from the LO harmonics) and
  transient noise cannot answer it credibly: small-signal `.noise` linearizes
  around a DC op that is the *wrong* operating trajectory (the LO is a large
  periodic drive). Reporting a transient-noise number here would be a lie, so it
  is named as future work (PSS via a different engine, e.g. VACASK/Xyce), not
  faked. The example spec omits `nf_db` deliberately.

### Balun / differential-output LNA -- `lna/balun_harness.py`  (circuit_class: balun-lna)
- **v0 measures:** mixed-mode Sds21 (differential gain) and **Scs21**
  (common-mode gain, new here), amplitude imbalance (dB), phase imbalance (deg),
  and **CMRR = Sds21 - Scs21** (new here), per f0 and band-wide worst-case.
- **Reuses:** `lna/diff3.py`'s mixed-mode reduction and 3-port sp machinery
  verbatim (the D7 lineage, golden-checked by `lna/ref/check_diff.py`); this
  file is the class facade that adds Scs21/CMRR and the `as_metrics()` mapping to
  spec constraint-metric names. It does NOT re-derive diff3's math.
- **Golden:** `lna/ref/check_balun.py` -- ideal center-tapped balun (two VCVS
  -/+0.5) -> exactly 0 dB / 0 deg imbalance, known Sds21 = -9.031 dB, Scs21 at
  the -600 dB floor, CMRR ~591 dB; plus a deliberately imbalanced case
  (`-0.5/+0.6`) reading finite imbalance/CMRR to prove the metrics are not
  hard-wired to the ideal. GREEN, all numbers to <=1e-3 dB.
- **Runtime:** one 3-port sp run (~0.03 s behavioral, ~1-2 s device) + optional
  differential-NF run.

### spec.py extension (additive)
- New `circuit_class:` field (default `lna`, so absent == lna, zero behavior
  change), values `lna|pa|mixer|balun-lna`. New constraint metric names
  documented in `spec.CLASS_METRICS` (constraints already accept arbitrary metric
  names, so no validation change): `p1db_dbm, psat_dbm, pae_pct, conv_gain_db,
  lo_rf_iso_db, lo_if_iso_db, imbalance_amp_db, imbalance_phase_deg, cmrr_db,
  sds21_db`. **Nothing is wired into the sizing objective automatically** -- these
  gate/report via the constraints block exactly like existing metrics.
- Example specs (all header-marked EXPERIMENTAL DRAFT):
  `lna/specs/{pa24,mixer24,balunlna24}-example.yaml`.

---

## PDK abstraction (v0)

- `lna/pdk/` package with `get_pdk(name)` and an adapter interface
  (`model_includes()`, `mos_line(...)`, `vdd`, `device_ranges`, `name`, `notes`,
  `bjt_models()`) -- documented in `lna/pdk/__init__.py`.
- `bptm45.py` -- the CURRENT flow refactored into adapter form; the default.
  `to_spice.Netlist(pdk=...)` defaults to it and emits **byte-identical** decks
  to before (golden `lna/ref/check_pdk.py`: three renderings byte-equal; plus
  `check_ref.py` green before/after).
- `sky130.py`, `ihp_sg13g2.py`, `gf180mcu.py` -- STAGED adapters with full
  device-mapping tables; `model_includes()` raises `NotImplementedError` naming
  `lna/pdk/FETCH.md` until files are fetched. mos_line() emits the documented
  X-subckt mapping today (testable without files).
- `lna/pdk/FETCH.md` -- approval-gated fetch plan: verified upstream URLs (all
  HTTP 200, all Apache-2.0), minimal ngspice file subsets, landing proposal,
  IHP's OpenVAF/OSDI compile step, and a survey of other open PDKs
  (ASAP7/FreePDK: predictive, no new RF value).

### PDK rollout order (recommended)
1. **IHP SG13G2** -- highest RF value (SiGe HBT ~250 GHz fT) and the corpus
   already carries ingested IHP circuits. Cost: OpenVAF/OSDI compile.
2. **sky130** -- most battle-tested with ngspice, no OSDI.
3. **gf180mcu** -- easiest (no OSDI) but least RF (180 nm).

---

## Campaign integration (verify-instrument style, future)

The three harnesses are shaped like the existing measurement functions
(`extract.run_and_extract`, `diff3.measure_diff3`, `iip3.iip3_sweep`): they take
a body + params and return a metrics dict, so a driver logs them through the same
`size.log_l2_result` hub the LNA campaign uses -- as a **verify instrument** on a
sized deck, not inside the ZOAF inner loop (large-signal transients are too slow
for per-iteration use; run once per label at the sized point, exactly as
`measure_nf`/`iip3` already are). A class driver would:
1. size the topology on the cheap S-param/NF metrics (unchanged),
2. at the sized point, run the class harness for p1db/conv_gain/imbalance/etc.,
3. gate via `spec.feasible()` on the class metric names (already supported).

Class-specific L0 structural screens (PA output-match, mixer switching-pair,
etc.) are future work -- the pa/mixer example specs set the topology screen
permissively and say so; balun-lna already has a real screen (single-ended-in,
inductor-bearing front).

## Out of scope this wave (named, not attempted)
- Mixer NF (PSS/pnoise) -- see above.
- Phase noise / VCO harnesses -- ngspice has no PSS; a VCO's phase noise needs
  PSS + pnoise (VACASK/Xyce territory). Not started.
- PDK file fetch + adapter `model_includes()` implementation -- gated on
  `lna/pdk/FETCH.md` approval.

# WP-DHRUVA — the paper target: Dhruva GNSS balun LNA as the goal spec

**Source:** Kanchetla et al., "A Compact, Reconfigurable CMOS RF Receiver for
NavIC/GPS/Galileo/BeiDou," IEEE TMTT 70(7), July 2022 (Dhruva, IIT Bombay,
65-nm CMOS, measured silicon). The user sets **its LNA** as the goal for what
the pipeline must achieve. PDF in repo root; LNA is §III-A + Fig. 5, currents
Table III (p. 7 — table is an image; values transcribed below).

---

## 1. What their LNA is (extracted)

**Architecture (Fig. 5): single-to-differential noise-canceling balun LNA.**

* **Matching stage** — complementary common-source pair (M1 NMOS + M2 PMOS,
  one shared bias current = current-reuse inverter) with **resistive shunt
  feedback** R_F from output V_X to input. Zin ≈ 1/(gm1+gm2) ≈ 50 Ω,
  **wideband** (0.1–2.9 GHz). R_F = 9·R_S = 450 Ω; stage gain
  A_m ≈ −R_F/R_S ≈ −9 (~19 dB).
* **Noise-canceling / balun output pair** — M4 (CS off the *input* node) and
  M3 (CS off the *feedback* node V_X), each cascoded (M5/M6) with 3 switchable
  slices (Sw[2:0]) for gain programming. Balance condition **gm4 = |A_m|·gm3**
  makes the matching-stage device noise cancel at the differential output and
  produces the single→differential conversion.
* **Load** — differential LC tank: center-tapped inductor to VDD +
  **programmable capacitor bank** selecting the band (this is the whole
  "reconfigurable" mechanism); inductor Q 9.5 (L5) → 14.5 (S).

**Numbers (65-nm, 1.2 V; sim = paper simulation, meas = measured):**

| parameter | L5 (1176.45 M) | L2 (1227.6 M) | L1 (1575.42 M) | S (2492.03 M) |
|---|---|---|---|---|
| max voltage gain (sim) | 22.3 dB | 22.3 dB | 25.4 dB | 30 dB |
| NF @ max gain (sim) | 2.5 dB | 2.5 dB | 2.7 dB | 3.5 dB |
| IIP3 @ min gain (sim) | −7.4 dBm | −7.4 dBm | −7.6 dBm | −8.7 dBm |

* Input match: **S11 < −10 dB over 0.1–2.9 GHz** (receiver-level measured) —
  one match network serves all four bands; only the load retunes.
* Gain programmability: 10.6 dB range per band, 3 steps (cascode slices).
* Balun balance: < 0.22 dB / < 0.9° across all bands and gain settings.
* **LNA current: 13 mA @ 1.2 V** (Table III measured; ≈ 15.6 mW).
* Context: whole receiver 38.35 mA, min receiver NF 3.8 dB, 1.96 mm².

**Mapping caveat:** the paper's "gain" is voltage gain A_v into the on-chip
mixer, not S21 into 50 Ω. Our harness gates S21 in a 50-Ω 2-port. Adopt the
paper numbers as S21 thresholds anyway (calibration decision — revisit only if
it proves structurally unfair; a tuned tank driving 50 Ω sheds ~6 dB vs an
on-chip load, so tier-1 may be *harder* than the paper's own bar).

## 2. The goal as a spec ladder (three tiers, staged by harness capability)

**Tier 1 — gateable today (S11/S21/Idd, current harness).** Four new specs
`dhruva-l5 / dhruva-l2 / dhruva-l1 / dhruva-s`:

| constraint | value | note |
|---|---|---|
| S11 | ≤ −10 dB **across 1.1–2.5 GHz** (sweep grid, not @ f0) | the wideband match — same class as wideband-sdr's binding constraint |
| S21 @ f0 | ≥ 22 (L5/L2) / ≥ 25 (L1) / ≥ 30 (S) dB | narrowband tuned gain is expected (LC load) |
| Idd | ≤ 13 mA @ 1.2 V | paper's measured LNA current; generous vs gps-l1's 3 mA — current is *not* the binding constraint here |

**Tier 2 — after the NF port-noise harness lands (HANDOVER priority 1):**
NF ≤ 2.5 / 2.5 / 2.7 / 3.5 dB per band, gated. Noise cancellation is the
*mechanism* the paper uses to hit these — tier 2 is what makes the NC
topology family matter, not just wideband match.

**Tier 3 — deferred, explicitly out of the current harness:**
* IIP3 ≥ −7.4…−8.7 dBm → needs two-tone/HB; the VACASK bookmark
  (memory: vacask-open-rfic-flow) activates here, not before.
* Balun balance ≤ 0.22 dB / 0.9° → needs a differential 3-port harness.
* Gain programmability (switched cascode slices) → reconfigurability is a
  sizing-DOF/switch question, out of scope for topology search.

**Gates:**
- **Gate D0:** harness + spec files evaluate all four tier-1 specs;
  `benchmark.md` grows four dhruva rows (scoreboard extension, 07-EXIT rule).
- **Gate D1:** ≥ 1 feasible tier-1 **dhruva-l1** (wideband S11 + 25 dB + ≤13 mA).
- **Gate D2 (the "reconfigurable" essence):** **one topology family** feasible
  on **all four bands**, where only load-bank values and sizing differ —
  same wl_hash family across the four rows.
- **Gate D3:** tier-2 NF met on ≥ 1 band under the trusted NF harness
  (≤ 3.5 first; ≤ 2.5 is the stretch).

## 3. Why this goal composes with what's already open (not a new direction)

* **It subsumes wideband-sdr.** Tier-1's S11-over-band *is* wideband-sdr's
  binding constraint; Gate B1's open half and Gate D1 share a bottleneck.
  The NC-balun family below is exactly the "noise-cancelling archetypes"
  HANDOVER priority 2 already calls for — one family serves both.
* **It makes the NF harness (priority 1) mandatory, not optional.** The goal's
  tier 2 cannot be evaluated without it, and the paper's architecture exists
  *because of* noise: matching stages that present 50 Ω wideband are noisy;
  cancellation is how Dhruva gets 2.5 dB anyway. Without tier 2 the pipeline
  would happily "solve" tier 1 with a noisy rfb stage and learn nothing.
* **The architecture decomposes into constructors we already have.** The
  matching stage = `current_reuse_lna`'s complementary pair + `rfb_lna`'s
  shunt feedback (both landed in the 118-archetype set). What's new is the
  NC output pair + differential tank. The generator lesson (wifi24, then
  gps-l1) predicts the templates won't size to feasibility by hand — they
  seed P5, and generated variants close the gate.

## 4. Work packages (Opus-executable order)

* **WP-D0 — spec plumbing (~½ day).** Add the four `dhruva-*` specs
  (registry + `spec.objective`); S11 evaluated on a 1.1–2.5 GHz grid
  (wideband-sdr already sweeps broadband S11 — reuse that path, don't write a
  second one). Extend `benchmark.py` with the four rows. **Gate D0.**
* **WP-D1 — NF port-noise harness (WORKLOG R3; unchanged top priority).**
  Fix, validate against the tapped reference + one rfb row, **re-label**
  affected rows (new harness = new label domain — do not mix silently; bump
  `recipe`), only then un-gate NF in `spec.objective`. Optional while in
  there: finite-Q inductors (paper Q 9.5–14.5) as a spec-level knob —
  ideal-L NF numbers will read optimistic vs the paper otherwise.
* **WP-D2 — `nc_balun_lna` constructor family (`templates.py`, ~1–2 days).**
  Matching stage (complementary CS + R_F ≈ 9·R_S shunt feedback) → two output
  branches (CS off input node, CS off feedback node, cascoded) → differential
  center-tapped tank with band-select cap parameter. Variants: ± cascode
  slices, shunt-peaked tank, buffer. Target **8–15 archetypes**; wire into the
  wb channel (they are inductor-bearing but wideband-*matched* — check the wb
  screen's `max_inductors` doesn't reject the tank; the screen guards the
  *match* mechanism, and here the match is feedback, so exempt load inductors).
* **WP-D3 — label → multi-spec winners → P5-v4 → curated sizing (~2–3 days +
  GPU overnight).** Label the new family vs `dhruva-l1` + `wideband-sdr`;
  generalize `emit_winners` to multi-spec (HANDOVER priority 3 — gps-l1's two
  winners feed in too); fine-tune P5-v4 under adopt-only-if-better
  (NDL@256 + tripwires; σ best-of-3 relabel lands *before* any critic
  retrain, per the deferred iter-4 item); curated-size the generated pool —
  match prior from the generator, polish-first as in iter-4. **Gate D1.**
* **WP-D4 — the four-band retune pass (~1 day).** Take every dhruva-l1
  feasible; re-run curated sizing per band with the matching stage *fixed*
  (it is band-independent by construction — that's the paper's point) and
  only load bank + output stage free. **Gate D2.**
* **WP-D5 — tier 2 (after WP-D1).** Re-benchmark all dhruva-feasible rows
  under gated NF; expect the un-canceled rfb rows to fail and NC rows to
  survive — that contrast is the result. **Gate D3.**

## 5. Honest expectations vs the paper

Our labels are ideal-element behavioral ngspice, not 65-nm silicon: passive
losses, parasitics, and the balun's phase problem are under-modeled, so tier-1
feasibility here does **not** claim parity with Dhruva — it claims the
pipeline *finds the architecture class* (wideband-matched, noise-cancelable,
band-retunable) under the same constraint shape. The paper's binding
difficulty — high tuned gain *while* the match stays wideband and noise
cancels — is exactly reproducible at our fidelity, and it is the pair
(S11-over-band + S21 ≥ 25) no current archetype family closes. NF parity
(tier 2) becomes meaningful only after WP-D1, and IIP3 (tier 3) only under a
different simulator (VACASK bookmark).

## Acceptance

- [ ] Gate D0: four dhruva specs evaluable end-to-end; benchmark rows present
- [ ] WP-D1: NF harness validated; affected rows re-labeled, recipe bumped;
      NF gated only after validation
- [ ] WP-D2: ≥ 8 nc_balun archetypes; wb screen passes the tank exemption
- [ ] WP-D3: P5-v4 adopted only if ≥ v3 on NDL@256 with tripwires quiet;
      multi-spec emit_winners in place
- [ ] Gate D1: ≥ 1 feasible dhruva-l1 (tier 1)
- [ ] Gate D2: one family feasible on all four bands (retune-only)
- [ ] Gate D3: tier-2 NF met on ≥ 1 band; NC-vs-rfb contrast reported

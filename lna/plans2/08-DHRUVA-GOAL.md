# WP-DHRUVA — the paper target, specifications only (blind protocol)

**Source:** Kanchetla et al., "A Compact, Reconfigurable CMOS RF Receiver for
NavIC/GPS/Galileo/BeiDou," IEEE TMTT 70(7), July 2022 (65-nm CMOS, measured
silicon). The user sets its LNA's **performance numbers** as the goal.

**⚠ Blind protocol — read before executing.** This plan deliberately contains
**no description of the paper's circuit**. The experiment is whether the
pipeline (generator + critic + curated sizing) reaches these specs **without
help**. Rules for every executor session:

1. **The PDF has been removed from the repo** (the user holds it). Do not
   fetch, request, or reconstruct the paper's circuit content; the spec
   numbers cited here are the complete allowed excerpt. Do not summarize,
   sketch, or transcribe its figures or circuit sections anywhere in the
   repo (FINDINGS, HANDOVER, comments, templates).
2. **No paper-derived constructors.** `templates.py` may grow only families
   that are (a) already in the archetype set, or (b) generic textbook blocks
   chosen *without consulting the paper*. Anything added while this WP is
   active gets labeled with provenance `recipe: blind-v1`.
3. **If the loop stalls** (no Gate movement across two full turns), record the
   stall in FINDINGS and stop — whether to unblind is the **user's decision**,
   not the executor's.

---

## 1. The target specifications

Four bands, one device: the LNA must be operable at each band (band selection
by whatever means the pipeline finds — only the specs below are given).

| parameter | L5 (1176.45 MHz) | L2 (1227.6 MHz) | L1 (1575.42 MHz) | S (2492.03 MHz) |
|---|---|---|---|---|
| gain at f0 | ≥ 22.3 dB | ≥ 22.3 dB | ≥ 25.4 dB | ≥ 30 dB |
| NF at f0 | ≤ 2.5 dB | ≤ 2.5 dB | ≤ 2.7 dB | ≤ 3.5 dB |
| IIP3 (min-gain setting) | ≥ −7.4 dBm | ≥ −7.4 dBm | ≥ −7.6 dBm | ≥ −8.7 dBm |

Common to all bands:

* **Input match:** S11 ≤ −10 dB **across 1.1–2.5 GHz** — the match must hold
  over the whole range in every band configuration (evaluated on a sweep
  grid, not only at f0).
* **Supply current:** ≤ 13 mA @ 1.2 V (LNA block alone).
* **Gain programmability:** ≥ 10.6 dB adjustable range per band, ≥ 3 steps.
* **Output:** differential (single-ended RF in → balanced out), imbalance
  ≤ 0.22 dB / ≤ 0.9° across bands and gain settings.

**Mapping decision:** the paper reports voltage gain into an on-chip load;
our harness gates S21 into 50 Ω. Adopt the numbers above as S21 thresholds
as-is (revisit only if structurally unfair — record the argument first).

## 2. Spec ladder (staged by harness capability) and gates

**Tier 1 — gateable today (S11/S21/Idd):** four specs
`dhruva-l5 / dhruva-l2 / dhruva-l1 / dhruva-s`: per-band S21 threshold from
the table, S11 ≤ −10 dB over 1.1–2.5 GHz, Idd ≤ 13 mA. Current is generous
vs gps-l1's 3 mA — it is *not* expected to bind.

**Tier 2 — after the NF port-noise harness lands (HANDOVER priority 1):**
the NF row, gated per band.

**Tier 3 — deferred, out of the current harness:** IIP3 (needs two-tone/HB —
the VACASK bookmark activates here), output balance (needs a 3-port
differential harness), gain programmability (switch/DOF question, out of
scope for topology search).

**Gates:**
- **Gate D0:** all four tier-1 specs evaluable end-to-end; `benchmark.md`
  grows four dhruva rows (scoreboard extension, 07-EXIT rule).
- **Gate D1:** ≥ 1 feasible tier-1 **dhruva-l1**.
- **Gate D2 (the "reconfigurable" essence):** **one topology family**
  feasible on **all four bands** — same wl_hash family, only parameter values
  differ per band.
- **Gate D3:** tier-2 NF met on ≥ 1 band under the trusted NF harness
  (≤ 3.5 first; ≤ 2.5 is the stretch).

## 3. Why this composes with what's open

Tier-1's S11-over-band is the same constraint class wideband-sdr is stuck on
(Gate B1's open half) — one campaign serves both scoreboard rows. Tier 2 is
what makes the NF harness fix (already priority 1) mandatory rather than
optional: without it the pipeline can "solve" tier 1 with an arbitrarily
noisy front end and the goal loses its teeth.

## 4. Work packages (Opus-executable order)

* **WP-D0 — spec plumbing (~½ day).** Add the four `dhruva-*` specs
  (registry + `spec.objective`); S11 on a 1.1–2.5 GHz grid (wideband-sdr
  already sweeps broadband S11 — reuse that path). Extend `benchmark.py`
  with the four rows. **Gate D0.**
* **WP-D1 — NF port-noise harness (WORKLOG R3; unchanged top priority).**
  Fix, validate against the tapped reference + one stored wideband row,
  **re-label** affected rows (new harness = new label domain — bump
  `recipe`, never mix silently), only then un-gate NF in `spec.objective`.
* **WP-D2 — blind campaign (~2–3 days + GPU overnight).** Label the existing
  archetype set vs `dhruva-l1` (+ `wideband-sdr`); generalize `emit_winners`
  to multi-spec (HANDOVER priority 3); fine-tune P5-v4 under
  adopt-only-if-better (NDL@256 + tripwires; σ best-of-3 relabel lands
  before any critic retrain); curated-size the generated pool polish-first,
  as in iter-4. Diversity expansion is allowed only under blind-protocol
  rule 2. **Gate D1.**
* **WP-D3 — the four-band pass (~1 day).** Take every dhruva-l1 feasible;
  re-run curated sizing against each remaining band, warm-started from the
  l1 solution (standard curated recipe — fix what the recipe already fixes,
  free the rest). **Gate D2.**
* **WP-D4 — tier 2 (after WP-D1).** Re-benchmark all dhruva-feasible rows
  under gated NF; report which families survive the NF gate and which die —
  that contrast is a result either way. **Gate D3.**

## 5. Honest expectations

Our labels are ideal-element behavioral ngspice, not 65-nm silicon: passive
loss, parasitics, and layout are unmodeled, so tier-1 feasibility does not
claim parity with the paper — it claims the pipeline finds a topology class
meeting the same constraint *shape* at our fidelity. The hard pair is
S11-held-over-band together with ≥ 25–30 dB tuned gain — no current family
closes it, which is exactly what makes this a fair blind test. NF parity
(tier 2) is meaningful only after WP-D1; IIP3 (tier 3) only under a
different simulator.

## Acceptance

- [ ] blind protocol logged in FINDINGS at campaign start; provenance
      `recipe: blind-v1` on every new row
- [ ] Gate D0: four dhruva specs evaluable; benchmark rows present
- [ ] WP-D1: NF harness validated; affected rows re-labeled, recipe bumped;
      NF gated only after validation
- [ ] WP-D2: P5-v4 adopted only if ≥ v3 on NDL@256 with tripwires quiet;
      multi-spec emit_winners in place
- [ ] Gate D1: ≥ 1 feasible dhruva-l1 (tier 1)
- [ ] Gate D2: one family feasible on all four bands
- [ ] Gate D3: tier-2 NF met on ≥ 1 band; NF-gate survivor contrast reported
- [ ] any stall recorded, not unblinded (user decides)

# 18 — WP-LIN CLOSURE: the never-measured baseline-IIP3-under-perturbation set, pre-registered before the record is written

**Status:** **PRE-REGISTRATION — committed alone, before any perturbation run.**
One measurement set, not a program. Mirrors the house pre-registration form
(`16-WP-LIN.md` §4.4, `17-WP-LIN-D2.md`, `13-WP-DIAGHEADS.md`), kept short by
mandate.
**Branch:** `main`. **Owner:** WP-LIN closure executor (Session 10, D-1 close).
**Authorized by:** the user's ruling 2026-08-16 — *(D-1) record candidate N and
close WP-LIN*, plus the two commissioned closure items: this baseline-IIP3-
under-perturbation set (`16-WP-LIN.md` §1.3 item 5 / §4.4's reduced set — the
one thing rung 4 left vacuous because it had zero survivors, §45.5) and the
playbook distillation of JOURNEY stages 41–44.
**Documentation slots:** FINDINGS §47, JOURNEY stage 45,
`16-WP-LIN.md` §11 final rows, and — uniquely, by explicit user sign-off — the
`14-DHRUVA-SIMUL.md` §2 D5 row (the N record).

---

## 0. Why this exists — the one open half-clause of §4.4

`16-WP-LIN.md` §1.3 item 5 named it as the fifth thing WP-LIN owed and had never
been done: **IIP3 under any sensitivity axis.** `corners.py` sweeps the tier-1 +
tier-2 gates only; no distortion metric has ever been perturbed. §4.4 registered
the reduced set as an acceptance rule for a *survivor*. Rungs 1–4 produced **zero
survivors** (§45.5), so §4.4 ran vacuous and item 5 stayed open (§45.6 dev 3).

**No candidate survived, so §4.4 applies to the BASELINE designated point.** The
question this closure answers is not "does a mechanism survive perturbation"
(there is no mechanism) but the prior underneath the whole N record:

> **Is the measured D5 wall itself stable under perturbation?** A wall that moved
> ±5 dB with VDD would change what candidate N *means* — the 26.6–27.7 dB miss
> (§44.2) would no longer be a fixed physical fact but a knife-edge. If instead
> the wall is stable to ~1 dB, N's "physical at ≤1.2 V" verdict is robust, not an
> artefact of the nominal operating point.

### 0.1 The prior, stated so it can be wrong on the record (§2.2 arithmetic)

§2.2 diagnosed the wall as **current-swing-limited** (`Iq(MNM6)×|Z_ac|`), confirmed
three ways in §44.4 (ρ=1.0000, +0.61 dB per +100 mV rail). Under that diagnosis
the arithmetic predicts the wall is **stable to ~1 dB** across the reduced set:

* **VDD×0.9 (−120 mV rail):** the rail sweep measured OIP3 moves **+0.61 dB per
  +100 mV** (§44.4). A −120 mV perturbation should therefore move OIP3 by
  **≈ −0.7 dB**, and VDD×1.1 (+120 mV) by **≈ +0.7 dB** — both under ±1 dB.
* **85 °C:** hotter reduces gm and the class-A bias current, so OIP3 falls; the
  designated point's tier-1/2 gates already survived 85 °C with the worst gate
  (NF) moving +0.012 dB (§14 §2.1 ruling 1), so a distortion move of order ~1 dB
  is the expectation, not a cliff.
* **worst two-axis combo:** the two OIP3-reducing extremes at once — **VDD×0.9 +
  85 °C** (both lower `Iq`, §44.4's ordering) — the additive prediction ≈ −1.5…
  −2 dB, still an order of magnitude short of the 26.6–27.7 dB miss.

**Registered prediction Q1:** across all four perturbations, IIP3 at the ruled
condition moves **≤ ~1 dB per single axis and ≤ ~2 dB on the combo** (a wall that
does not care which nominal it was measured at). **Falsifier:** any perturbation
that moves IIP3 by ≥ 5 dB — which would qualify the N record and must be reported
loudly (task-report mandate).

---

## 1. The exact grid — factors, states, bands, reading

**Point:** the BASELINE `dhruva-simul` designated D4-SIM point (of
`ace8383c2fa68d03`), no candidate mechanism, **pVDD = 1.2 V nominal.** Emitted
via rung 0's deck path (`_lin_baseline.base_body` + `simul_params`), min-gain S3
via `_lin_baseline.min_gain_body_params` (structural role resolution, §42.2/§6.7).

**Perturbations (the §4.4 reduced set), applied by the `corners.py` mechanism
verbatim** — `pVDD` scaled for VDD, `.temp` card appended for temperature,
never by literal node name:

| # | axis | setting | direction rationale |
|---|---|---|---|
| P0 | *(invariance control)* | `.temp 27` at nominal 1.2 V | must reproduce the §44.2 baseline to the fence (proof the injection changes nothing) |
| P1 | VDD | ×0.9 (1.080 V) | worst rail direction (−120 mV lowers OIP3, §44.4) |
| P2 | VDD | ×1.1 (1.320 V) | the other rail extreme (+120 mV) |
| P3 | temp | 85 °C | the mandated hot extreme (§14 sweep) |
| P4 | **combo** | VDD×0.9 **+** 85 °C | the two OIP3-reducing extremes at once (§2.2 ordering picks both) |

**States:** the **D6 min-gain S3** state (the ruled D5 condition — primary) **and
max gain** (the reference). Both, per the mandate.

**Bands:** **dhruva-l5** (the worst-margin band, band minimum) is required. **All
four bands** are measured if the cost stays cheap (the mandate: "all 4 bands if
time is cheap") — the grid is written for four and the executor drops to l5-only
only if a cap is threatened.

**Reading (acceptance):** for each (perturbation, state, band): IIP3, OIP3, gain,
IM3 slope, ΔS21 cross-check, replay spread. The **D5 acceptance reading** is IIP3
vs the §6.1 gate (≥ −7.4/−7.4/−7.6/−8.7 dBm at l5/l2/l1/s) — expected FAIL by
~26–28 dB everywhere (this is a wall-stability measurement, not a pass attempt).
The **stability reading** is `ΔIIP3` and `ΔOIP3` vs the P0 nominal, per axis, at
the ruled (min-gain) condition — this is the number Q1 is judged on.

### 1.1 Fences (§37.3 / §6.7, intact on every row — a NEW measurement)

Replay ×3 in-process (spread target 0.0000 on IIP3), IM3 slope in 3 ± 0.3,
≥ 10 dB IM3-over-floor SNR, ≤ 0.5 dB compression on kept points, per-point spread
reported, the re-pointed §37.4 S21 cross-check (this config's own audited S21,
per perturbation) never disabled. Min-gain drive window −68…−52 dBm (§44.3);
max-gain −80…−40. Slope-fence failures at the numerical floor are re-driven and
recorded, not smoothed (§44.3 precedent), never metric-changed.

---

## 2. Caps (stop at cap, publish shortfall — §34 precedent)

* ≤ **40 SPICE-minutes** total.
* ≤ **1.5 h wall** at ≤ **32 workers** (externals calibration holds ~56 cores).
* Grid size: 5 perturbations × 2 states × 4 bands × ~5 drives × 3 replays. If the
  cap is threatened, drop to **l5-only** (5 × 2 × 1) first, then drop max-gain
  (min-gain S3 is the ruled condition and the priority).
* HB cross-check is **not owed** (no candidate, no claimed pass — §4.3); the
  transient wall-stability number stands on its own, replay-fenced.

---

## 3. Law (unchanged from WP-LIN)

Goldens GREEN before/after (`check_ref`, `check_iip3`, `check_hb`, `check_diff`).
Sidecar + module-attribute overrides only; no shared harness edit (§7 D-9); no
spec/frozen-protocol touch (§7 D-3). §42.2 node-name discipline on every insert.
Append-only store, `recipe=wplin-v1`, `source_arm=wplin-sens-iip3`. Candidate N is
recorded here **only** under the user's 2026-08-16 D-1 sign-off; the D5-row edit
of `14-DHRUVA-SIMUL.md` §2 is made under that same sign-off and no other.

---

## 4. Outcome (appended after execution — FINDINGS §47)

*Empty by design. Filled after the fact, whichever way Q1 falls, with full detail
in FINDINGS §47.*

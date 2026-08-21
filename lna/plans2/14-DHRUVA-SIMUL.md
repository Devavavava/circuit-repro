# 14 — DHRUVA-SIMUL: the GNSS benchmark, recorded MET and restated to simultaneous

**Status:** Gate **D4-SIM MET** (2026-08-13, FINDINGS §35, JOURNEY stage 30).
**Decision provenance:** user directive, 2026-08-13 — record the per-band
benchmark as met; the standing benchmark is now *one LNA, one fixed sizing,
every specification at once*.

This document supersedes the day-to-day role of `08-DHRUVA-GOAL.md` (which
lived in the since-removed `lna-plans` worktree and is no longer on disk) and
restates the target ladder so it is self-contained. The blind protocol is
unchanged: the target numbers below are the complete allowed excerpt of
Kanchetla et al., IEEE TMTT 70(7) 2022 (65 nm CMOS, measured silicon); the
paper's circuit content has never been shown to this program.

---

## 1. Requirements vs. achieved

Achieved numbers are the **single fixed design**: topology `ace8383c2fa68d03`
(20 devices, 2 inductors, search-found, novel vs ref-v3) at the
**designated `dhruva-simul` point** (margin-hardened, FINDINGS §36; user
designation 2026-08-13), gated at **pVDD = 1.2 V** — the spec text's own
nominal, per the same ruling. One parameter set, one 9.463 mA operating
point, no per-band re-sizing, no switching. Replay-fenced (§36: 5/5 spread
0.0000); per-cell protocol `lna/repro/dhruva-best/recreate.py --cross`.
*(The original l5-sized point — the first D4-SIM closure, §35 — stays
archived in the same package; note it fails the Idd gate at 1.2 V.)*

### 1.1 Per-band gates (tier 1 + tier 2) — ALL MET, simultaneously

| requirement | target | achieved (`dhruva-simul` @ 1.2 V) | margin | status |
|---|---|---|---|---|
| Gain @ L5 f0 (1176.45 MHz) | ≥ 22.3 dB | 33.18 dB | +10.9 | **MET** |
| Gain @ L2 f0 (1227.6 MHz) | ≥ 22.3 dB | 33.32 dB | +11.0 | **MET** |
| Gain @ L1 f0 (1575.42 MHz) | ≥ 25.4 dB | 33.88 dB | +8.5 | **MET** |
| Gain @ S f0 (2492.03 MHz) | ≥ 30 dB | 33.45 dB | +3.5 | **MET** |
| NF @ L5 f0 | ≤ 2.5 dB | 1.606 dB | +0.89 | **MET** |
| NF @ L2 f0 | ≤ 2.5 dB | 1.547 dB | +0.95 | **MET** |
| NF @ L1 f0 | ≤ 2.7 dB | 1.337 dB | +1.36 | **MET** |
| NF @ S f0 | ≤ 3.5 dB | 1.201 dB | +2.30 | **MET** |
| S11, whole 1.1–2.5 GHz range | ≤ −10 dB | −11.484 dB | +1.48 | **MET** |
| Idd @ 1.2 V | ≤ 13 mA | 9.463 mA | +3.54 | **MET** |
| Stability (program gate, advisory) | K_min ≥ 1 | 17.2 in-band (wide 8.5, §36 @ 1.1 V) | ~8–17× | **MET** |
| Sensitivity sweep (temp/VDD/passives/Q + combo) | no gate flips | **zero flips on every axis** | — | **SURVIVES** |

The old S11 knife-edge is closed: the designated point holds every gate
through the full WP-SENS perturbation set at the 1.2 V nominal
(`lna/corners.py --axis all --point simul --vdd-nominal 1.2`, 2026-08-13 —
worst case is NF at +0.012 dB margin under VDD×0.9+85 °C, still a pass).

### 1.2 Tier 3 — specified by the paper, NOT MEASURABLE by the current harness

| requirement | target | achieved | status |
|---|---|---|---|
| IIP3 (at min-gain setting) | ≥ −7.4 dBm (L5/L2) / −7.6 (L1) / −8.7 (S) | **`dhruva-simul` @ 1.2 V, this point** (FINDINGS §44, two-harness): IIP3 −34.5…−35.3 (transient) / −34.5…−35.3 (HB) at max gain, **OIP3 −1.3…−1.8**; at the D6 min-gain setting OIP3 falls to **−13.0…−13.3** while IIP3 stays ≈ −34 (output-side D6 buys 0 dB IIP3) [†] | **MEASURED, FAILED 0/4** (§44 transient + HB agree to 0.08 dB at the ruled nominal; §37/§40 fixed-l5 wall — see §2 ladder) |
| Gain programmability | ≥ 10.6 dB range, ≥ 3 steps | 11.2–11.5 dB span, 4 monotonic states, S11/Idd held in every state | **MET under proposed mapping** (§42; sign-off pending) |
| Differential output | imbalance ≤ 0.22 dB / ≤ 0.9° | 0.119 dB / 0.34° band-wide worst (hardened host, active balun; all four-band gates pass there) | **imbalance MET** (§41; gain-convention ruling pending) |

**[†] Correction, 2026-08-15 (WP-LIN step 0, user-authorized R-e).** As
originally written this row's *achieved* cell read "−30.3…−32.8 dBm (fixed max
gain; OIP3 +3.2…+3.4)". Those numbers are the **`dhruva-l5`** point's D5
measurement (§37/§40), **not this designated `dhruva-simul` point's** — which
had never been measured when the row was authored (16-WP-LIN.md §1.3 item 1,
§1.5.1). WP-LIN rung 0 (FINDINGS §44, 2026-08-14) measured the designated point
for the first time, two-harness: its OIP3 is **−1.3…−1.8 dBm at max gain, ~5 dB
below the l5 point's +3.2…+3.4** — WP-HARDEN's 37 % Idd cut cost that ~5 dB,
exactly as §40.4 predicted. The verdict is unchanged (FAILED 0/4 on both points,
by >21 dB), so this correction changes no gate decision; the original number is
recorded here rather than erased so the mis-attribution stays on the record.

### 1.3 Standing fidelity caveats (carry over from `repro/dhruva-best/REPORT.md` §5)

45 nm behavioral BSIM4, not the paper's 65 nm silicon · passives ideal at
Q = 12 · multi-finger layout assumed (w_finger = 2 µm), not drawn · no process
corners, no package/layout parasitics · paper's voltage gain adopted as S21
into 50 Ω per the original mapping decision. "MET" above means
constraint-shape parity at this fidelity, not silicon parity.

---

## 2. Gate ladder — history and current state

| gate | definition | state |
|---|---|---|
| D0/D1/D2 | tier-1 (S11 band-wide, S21@f0, Idd) per band / all four bands, one topology | MET (sessions 3–4) |
| D3 | tier-2 (+ NF, series-Rs) on all four bands | MET (multi-finger cutover, FINDINGS §27) |
| **D4-SIM** | **tier-1+tier-2 on all four bands at ONE fixed sizing** | **MET 2026-08-13** (FINDINGS §35 — 16/16 matrix cells; **designated point = `dhruva-simul` @ 1.2 V** per the §2.1 ruling — S11 −11.48, Idd 9.46, survives the full sensitivity sweep; first closed on the l5 sizing, now archived) |
| **D5** | D4-SIM **and** measured IIP3 ≥ target | **NOT MET at ≤1.2 V on this topology family — candidate N RECORDED (user D-1 ruling, 2026-08-16; FINDINGS §47.3).** *On the designated `dhruva-simul` point (this row was originally written with the `dhruva-l5` point's numbers — see §1.2 [†] R-e):* two-harness measured (ngspice transient §44 + VACASK HB §44.9, agreeing to 0.08 dB at the ruled nominal), **FAILED 0/4 at the D6 min-gain condition, 26.6–27.7 dB short** (OIP3 −13.0…−13.3 at S3/1.2 V). The wall is **physical — an output-stage class-A current-swing limit (`Iq(MNM6)×\|Z_ac\|`, §2.2/§44.4)** — not a sizing choice (OIP3 flat across four descended sizings, §37.7) and not a voltage-headroom limit (16.8 dB from binding, §44.4); it is **stable under perturbation** (VDD ±10 %, 85 °C, worst combo: ΔIIP3 ≤ 2.26 dB, §47.1), so the miss is a fixed fact, not a nominal artefact. Rungs 1–4 (§45) + the D-2 widening (§46) exhausted every in-box and +3-device lever; per-band shortfall at the ruled condition ≈ **21 dB post-D** (best widened candidate FAILS 0/4 at −20.7…−22.1 dB). **Five-clause evidence chain: §44 / §44.9 / §45 / §46 / §47.** The levers that would move it — the output reference impedance (D-7, OIP3 rises dB-for-dB with `Z_ac`; **now measured — see §48**), the supply/Idd envelope, and D5 spec relief (D-1) — are each a **separate, still-open user decision**; recording N decides none of them. |
| **D6** | + gain programmability (≥10.6 dB / ≥3 steps) | **MET 2026-08-13 under a PROPOSED mapping** (§42 — 4 states, 11.2–11.5 dB span, S11 held in every state; mapping sign-off pending; caveat: all match-legal mechanisms are output-side, so low-gain states buy no linearity) |
| **D7** | + differential output within imbalance spec | **imbalance MET 2026-08-13** (§41 — CS+CG split-phase active balun, 0.119 dB / 0.34° band-wide worst on the hardened host; ALL four-band gates pass there with the balun, Idd 9.25 mA; the l5 host fails Idd only. Gain-convention decision pending: mixed-mode Sds21 passes, per-leg reads 2.85 dB short) |

**Ladder-order flag (from both D5 harnesses):** the paper's IIP3 is specified at
its *min-gain* setting, which a fixed-gain design cannot enter — so D6's
programmable range is a **prerequisite** for a like-for-like D5 measurement,
not its successor. A future D5 pass should be judged at the min-gain state of
a D6-compliant configuration.

### 2.1 Wave-close rulings (all four taken by the user, 2026-08-13)

1. **Designation + supply nominal — RULED: designate `dhruva-simul`, gate at
   1.2 V.** Pre-designation check passed the same day: the point survives
   the full live WP-SENS sweep at the 1.2 V nominal with **zero flips on
   every axis** (worst case NF +0.012 dB under VDD×0.9+85 °C). §1.1 is now
   stated on this point; the l5 point stays archived (fails Idd at 1.2 V).
2. **D6 gate mapping — RULED: approved as written** (the five clauses of
   FINDINGS §42.1 are the official Gate D6 definition; the §42 pass stands).
3. **D7 gain convention — RULED: mixed-mode Sds21** (the standard
   differential S-parameter; §41's gating and its all-gates-pass claim on
   the hardened host stand as recorded).
4. **Linearity strategy — RULED: linearity-aware redesign at ≤ 1.2 V**, no
   supply-envelope deviation; judged at the D6 min-gain state per the
   ladder-order flag above. Launched as WP-LIN (Session 10).

The 4×4 cross matrix (every sizing × every band spec): all 16 cells pass
tier-1+tier-2; the l5 sizing has the best worst-case NF margin (+1.247 dB),
the l2 sizing the best worst-case gain margin (+9.06 dB). Full matrix in
FINDINGS §35.2.

---

## 3. The bottleneck, stated honestly

With D4-SIM closed, **nothing that the harness can currently measure is
failing**. The bottleneck is therefore what the harness *cannot* measure:

1. **IIP3 is the biggest one.** It is the classic LNA trade against exactly
   the axes this design maxed out (36 dB fixed gain, weak-inversion devices,
   five cascaded stages) — and the paper specifies IIP3 at its *minimum-gain*
   setting, a condition this fixed-gain design cannot even enter. It is the
   spec most likely to be genuinely failed once measured, which is precisely
   why it should be measured first.
2. **The 0.001 dB S11 margin** is the credibility bottleneck: every headline
   number sits behind a match that any corner would move.
3. **Gain programmability and differential output** are design-space gaps,
   not measurement gaps — the search has no switch DOFs and no differential
   netlist support (3 differential corpus LNAs are deliberately out-of-scope
   since WP-SPEC).

---

## 4. Upgrade ladder

**Immediate (a day or two each, existing tooling):**

1. **Margin-hardening resize** — re-run `constrained_descent` from the l5
   point with the descent target flipped to worst-case-margin across all four
   specs (or simply S11 ≤ −10.5…−11 as the trust region), spending some of
   the +1.25 dB NF / +3.7 dB gain slack on match robustness. Tooling exists
   (`recreate.py --resize` is the template).
   **ATTEMPTED 2026-08-21 (FINDINGS §49): PASS — worst S11 margin +1.012 → +2.826 dB,
   4/4 bands PASS, worst-case-margin ×3.7; NF margin narrowed (0.774 → 0.479 dB, still
   passes); output at `lna/out/_resize_simul/best.json`. Designation decision pending
   user ruling.**
2. **Prototype IIP3 in ngspice** — two-tone transient + FFT at f0 per band.
   Coarse (transient noise floor, tone-spacing/timestep care), but it turns
   the D5 wall into a number in a day and decides whether the answer is
   "comfortably passes", "close", or "the topology must change".
3. **Stability into the polish/curated objective** (refuse steps that take
   K_min below 1) — small, queued since Session 4, closes a known integrity
   gap for every future campaign.

**Later (bigger payoff, real work):**

4. **VACASK/IHP harmonic-balance flow** (the project-memory bookmark) — the
   proper IIP3 harness, and the on-ramp to a real open PDK (IHP SG13G2)
   replacing the 45 nm behavioral models: closes D5 credibly and shrinks the
   fidelity caveats at the same time.
5. **Differential support** — 3-port S-param + imbalance harness, a
   `differential: true` spec axis, and either a balun output stage in the
   move set or differential archetypes (the 3 out-of-scope corpus LNAs are
   the calibration set). Path to D7.
6. **Switchable-DOF search** for gain programmability (D6) — spec support for
   discrete states + a sizer that sizes all states of one netlist jointly.
7. **Corner/parasitic sweep harness** — temperature/supply/process spreads
   and post-layout-style parasitics on the D4-SIM point; converts §1.3's
   caveats into measured margins (and will almost certainly consume the
   0.001 dB S11 margin — see upgrade #1).

---

## 5. Repro

```bash
# the 4x4 simultaneous matrix (16 cells + per-sizing verdicts):
python lna/repro/dhruva-best/recreate.py --cross

# the per-band (own-band) audit ladder, unchanged:
python lna/repro/dhruva-best/recreate.py --audit
```

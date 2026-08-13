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
(20 devices, 2 inductors, search-found, novel vs ref-v3) at the **`dhruva-l5`
sized point** — one parameter set, one 12.963 mA operating point, no per-band
re-sizing, no switching. Re-measured fresh 2026-08-13, replay 3/3 spread
0.0000 (FINDINGS §35; per-cell driver `lna/repro/dhruva-best/recreate.py
--cross`).

### 1.1 Per-band gates (tier 1 + tier 2) — ALL MET, simultaneously

| requirement | target | achieved (fixed l5 sizing) | margin | status |
|---|---|---|---|---|
| Gain @ L5 f0 (1176.45 MHz) | ≥ 22.3 dB | 35.96 dB | +13.7 | **MET** |
| Gain @ L2 f0 (1227.6 MHz) | ≥ 22.3 dB | 35.93 dB | +13.6 | **MET** |
| Gain @ L1 f0 (1575.42 MHz) | ≥ 25.4 dB | 35.54 dB | +10.1 | **MET** |
| Gain @ S f0 (2492.03 MHz) | ≥ 30 dB | 33.73 dB | +3.7 | **MET** |
| NF @ L5 f0 | ≤ 2.5 dB | 1.253 dB | +1.25 | **MET** |
| NF @ L2 f0 | ≤ 2.5 dB | 1.196 dB | +1.30 | **MET** |
| NF @ L1 f0 | ≤ 2.7 dB | 0.995 dB | +1.71 | **MET** |
| NF @ S f0 | ≤ 3.5 dB | 0.867 dB | +2.63 | **MET** |
| S11, whole 1.1–2.5 GHz range | ≤ −10 dB | −10.001 dB | **+0.001** ⚠ | **MET** |
| Idd @ 1.2 V | ≤ 13 mA | 12.963 mA | +0.037 | **MET** |
| Stability (program gate, advisory) | K_min ≥ 1 | 19.9 in-band / 10.3 (0.1–20 GHz) | ~10–20× | **MET** |

⚠ The S11 margin is 0.001 dB — the match is the binding constraint on the
whole family by construction (`constrained_descent`, `keep=s11idd`). It is a
real pass at this harness's fidelity and would not survive any parasitic that
moves the match; hardening it is upgrade #1 in §4.

### 1.2 Tier 3 — specified by the paper, NOT MEASURABLE by the current harness

| requirement | target | achieved | status |
|---|---|---|---|
| IIP3 (at min-gain setting) | ≥ −7.4 dBm (L5/L2) / −7.6 (L1) / −8.7 (S) | — | **UNMEASURED** (no two-tone/HB harness; `iip3_dbm` is `unsupported` in every spec) |
| Gain programmability | ≥ 10.6 dB range, ≥ 3 steps | — | **NOT ATTEMPTED** (one fixed operating point; no switchable DOFs in the search space) |
| Differential output | imbalance ≤ 0.22 dB / ≤ 0.9° | — | **NOT ATTEMPTED** (design is single-ended; no 3-port harness) |

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
| **D4-SIM** | **tier-1+tier-2 on all four bands at ONE fixed sizing** | **MET 2026-08-13** (FINDINGS §35 — 16/16 matrix cells pass; designated point = l5 sizing) |
| D5 (next) | D4-SIM **and** measured IIP3 ≥ target | **OPEN — blocked on a linearity harness** |
| D6 | + gain programmability (≥10.6 dB / ≥3 steps) | OPEN — needs switchable DOFs in spec+search |
| D7 | + differential output within imbalance spec | OPEN — needs 3-port harness + differential topology support |

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

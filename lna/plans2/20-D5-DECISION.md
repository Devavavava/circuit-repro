# 20 — D5 DECISION: the linearity fork as one costed ruling

**Status:** DECISION MEMO — synthesis only, no new measurements.
**Branch:** `main` (main owns `lna/`).
**Authored:** 2026-08-19, Session 10 follow-up, under the E-6 compute lockout.
**Purpose:** put the dhruva **D5 (linearity)** fork in front of the user as one
costed ruling. Every number below is quoted verbatim from `lna/FINDINGS.md`
with its section cited; where a figure is a derivation rather than a raw
measurement, the deriving section is named.

> **Header note — this memo adds no new measurements.** It was written during
> the E-6 campaign's compute lockout (the shared box saturated by a running
> experiment; no new simulation or sizing was run for this document). The only
> simulator invocation was the mandatory goldens check. Every number cites its
> FINDINGS section; nothing here is a new claim. The D5 verdict itself
> (candidate N, RECORDED under the user's 2026-08-16 D-1 ruling, §47.3) is
> unchanged — this memo restates it and prices the still-open levers so the
> user can rule on the fork with the arithmetic in one place.

---

## 1. The wall in three sentences

**Mechanism.** Gate D5 (measured IIP3 ≥ the paper's per-band targets, judged at
the D6 min-gain state per the ladder-order flag of `14-DHRUVA-SIMUL.md` §2)
fails because of an **output-stage class-A current-swing limit** — the peak
drain swing of MNM6 is `Iq(MNM6) × |Z_ac| = 1.432 mA × 50.9 Ω ≈ 73 mV`, which
binds the distortion **6.93× = 16.8 dB** ahead of the 505 mV voltage-headroom
limit (§44.4; hypothesis pre-registered in `16-WP-LIN.md` §2.2). It is **not**
a sizing choice (OIP3 flat across four descended sizings, §37.7; and the
four-point falsification test orders OIP3 with `Iq·|Z_ac|` at Spearman
ρ = 1.0000, §44.4) and **not** a voltage-headroom limit (headroom is 16.8 dB
from binding, §44.4).

**Size.** At the ruled D6 min-gain condition, 1.2 V nominal, the design's
measured IIP3 is ≈ −34 dBm against targets ≥ −7.4 / −7.4 / −7.6 / −8.7 dBm —
**FAILED 0/4 bands by 26.6–27.7 dB** raw baseline (§44.2), two-harness measured
(ngspice transient + VACASK harmonic balance agreeing to **0.07–0.09 dB** at the
ruled nominal, §44.9). After the +3-device D-2 widening carried candidate D to
measurement, the best widened candidate still **FAILS 0/4 at −20.7…−22.1 dB**
(§46.4), so the per-band shortfall post-D is ≈ **21 dB**.

**Stability.** The wall is not a nominal artefact: under the reduced
perturbation set (VDD ±10 %, 85 °C, worst combo) the D5-gated IIP3 moves at most
**2.26 dB** (min-gain, VDD×0.9 + 85 °C combo) and OIP3 at most **1.55 dB**
(§47.1/§47.2) — far below the pre-registered 5 dB falsifier, and confirmed
stable on all four bands (l5 full four-axis; l2/l1/s rail axis, §48.6). The
**five-clause evidence chain** behind candidate N: **§44** (baseline, max + min,
both harnesses) / **§44.9** (HB cross-check) / **§45** (WP-LIN rungs 1–4, in-box
levers exhausted) / **§46** (D-2 widening: candidate D + the isolating input
measured) / **§47** (perturbation stability + the D-1 recording).

---

## 2. Levers already measured DEAD — do not re-litigate these

Each of the following was measured to closure during WP-LIN. They are recorded
here so the user never re-opens them:

1. **In-box sizing (rungs 1–4, §45).** The entire in-box output-stage lever —
   current re-allocation (candidate B), raising the output AC load (candidate
   C), bias re-centering (candidate E), plus the pre-killed cascode /
   derivative-superposition / degeneration rows (F/G/H) — is worth **+0.72 dB**
   of OIP3 (candidate B, S11-capped at NM6×2 width; §45.3), the full 100 mV rail
   is worth **+0.61 dB** (§44.4), pVB is **0.00 dB** (inert, §45.2), and
   candidate C is **negative** (pR4V is the stage's current source, not a free
   AC knob; §45.2). Total in-box: **+0.7 dB of the ~27 needed** (§45.3).
   D5 FAILED 0/4 on every candidate at the ruled condition (§45.4).

2. **+3-device widening (D-2, §46).** The test-scoped +3-device allowance
   carried candidate D (current-reuse stack) and a dedicated isolating input to
   real two-tone. **Candidate D FAILED 0/4 at −20.7…−22.1 dB** (§46.4): the
   reuse stack never improves the swing product — the output branch current is
   resistor-set (RR4), so stacking adds a gm but zero current (§46.2). The spec
   `device_budget` stayed at [3, 21]; the allowance dissolved with nothing
   passing (§46.6).

3. **Output reference impedance (D-7, §48).** Raising the output port from
   50 → 400 Ω moves the D5-gated IIP3 by **+0.26 dB** (min-gain) / **+0.45 dB**
   (max) — D5 still **FAILS 0/4 by ~26.5 dB at every impedance** (§48.1). The
   pre-registered dB-for-dB prediction was **REFUTED** (departure 18.25 dB,
   §48.2): the port is a **gain lever, not a linearity lever** (IIP3 is set by
   the drive the drain sees, not the load it drives), and the OIP3-into-port
   curve is **concave, saturating at ~200 Ω** (the 10 pF/10 pF coupling caps
   `|Z_ac|` at ~208 Ω, §48.2). Two-harness identical on IIP3 to **0.00 dB**
   (§48.3). D-7 is retired as a closing lever.

4. **Match-legal front-side attenuation (§45.1 / §46.3).** The ~12 dB front-end
   half of the §2.3 decomposition is **structurally unavailable**: the input
   combiner's best match-legal span is 4.77/4.84 dB (< 10.6 needed, §45.1), the
   recombine node has **0.00 dB** of legal span, and the dedicated isolating
   input at +2 devices also measures **0.00 dB** of match-legal span (§46.3).
   The mechanism itself works (−9.32 dB of front-side attenuation buys +10.07 dB
   IIP3, §46.5) — the architecture has no match-legal place to put it (the
   C_gd-coupled input match reaches through even a cascode). P4 REFUTED.

---

## 3. The live options

Each of the following is a **separate, still-open user decision**; the D-1
recording of candidate N (§47.3) decided **none** of them. Recording N recorded
only that the gate, as written, is not met on this topology at this envelope.

### 3a. Supply / Idd envelope relief

**What the physics says it takes.** OIP3 scales with `Iq × |Z_ac|` (§2.2 /
§44.4). Passing the gate is a **power** problem: at the ruled min-gain state the
required OIP3 is +11.2…+12.5 dBm (§2.3), and because the match-legal (output-
side) D6 mechanism buys 0 dB of IIP3, passing −7.4 dBm at S3 requires
**OIP3(max) ≈ +25.8…+28 dBm ≈ 380–630 mW ≈ 33–55× the 11.4 mW DC budget**
(§45.5 — the §37.7-form power-budget argument written at the ruled condition).
A class-A stage delivering OIP3 ≈ +12 dBm into 51 Ω needs **~8 mA in the output
device alone, 5.5× today's 1.43 mA** (§45.5 / §47.3), feasible in current only
by re-allocating MNM4's 4.6 mA — which is candidate B, which **S11 forbids past
NM6×2** (§45.2).

**What envelope WOULD close it, and why it departs from the paper's class.** No
sizing inside the 1.1 V / 13 mA class reaches this; the output device needs
several times its present current, which means widening the Idd gate and/or the
rail beyond the paper's ruled envelope (the linearity strategy was RULED
≤ 1.2 V, no supply-envelope deviation, `14-DHRUVA-SIMUL.md` §2.1 ruling 4). Any
envelope that funds ~8 mA in MNM6 alone departs from the paper's 1.1 V / 13 mA
class-A budget — that is the concession this option asks the user to price.

*Ruling text it needs:* **"Relax the supply/Idd envelope for D5 to
\_\_\_ mA at \_\_\_ V"** (or hold it and accept the null), noting this departs
from the paper's stated class.

### 3b. D5 spec relief (D-1)

**The deliverable sentence** (§48.5, verbatim):

> "At 100 Ω/leg, D5 FAILS by ~26.7 dB; at 200 Ω, by ~26.6 dB; at 400 Ω, by
> ~26.5 dB — at the cost of nothing binding (S11 stays −11 dB band-wide at the
> antenna, NF/K/Idd unchanged, the D6 span widens to ~21 dB). The output
> reference impedance buys +0.26 dB of the ~27 dB needed. It is a gain lever,
> not a linearity lever; changing it alone concedes ~0.3 dB toward closing D5."

**What partial relief buys at each rung.** Every measured lever is a fraction of
the ~27 dB gap: output reference impedance +0.26 dB (§48.1); in-box sizing
(candidate B) +0.72 dB (§45.3); full 100 mV rail +0.61 dB (§44.4); the +3-device
widening +5.5…+6.1 dB of IIP3 at S3 via back-door source-degeneration but still
20.7–22.1 dB short (§46.4). No combination of measured levers within the
envelope reaches double digits of the gap. Spec relief is therefore
governance, not engineering: re-reading "IIP3 at the min-gain setting,"
accepting a partial pass, or re-negotiating the target (§7 D-1). The port
measurement (§48) sharpens the remaining decision to **supply/Idd or spec**
(§48.5).

*Ruling text it needs:* **"Re-negotiate the D5 target/condition to \_\_\_"** or
**"Accept the D5 null as the terminal finding"** (which folds into 3d).

### 3c. Topology-class change

The only in-simulation path that keeps the paper's envelope is a **different
output-stage class** — an output stage not bound by the class-A `Iq × |Z_ac|`
current-swing limit that §44.4 measured. Every in-box and +3-device lever inside
the current topology family (`ace8383c2fa68d03` / `dhruva-simul`) has been
exhausted (§45/§46); a class change is beyond the 1-spare-device budget and is a
topology decision, not a sizing one.

**Cross-line dependency the user should see.** This is exactly the registered
test case for **engineer rung G2 (E-7), the move-repertoire rung**
(`engineer/ROADMAP.md` §G2): *"Extend the graph-edit set until escalation can
change an output stage's class. Test case: the D5 wall — given only the
diagnosis 'output-stage current-swing limit', can the loop reach a different
output class at all? (This also feeds the main line's D5 fork, whichever way the
user rules.)"* Ruling for a topology-class change therefore **sequences
main-line D5 behind G2's move-repertoire work** — a cross-line dependency the
user should weigh before choosing this option.

*Ruling text it needs:* **"Pursue an output-class change for D5 (sequenced
behind engineer G2)"** or defer.

### 3d. Record and close

Candidate N is **already RECORDED** (D-1 ruling, 2026-08-16; §47.3). Its
verdict stands as the final D5 finding for this topology family at ≤ 1.2 V:

> "Gate D5 is NOT MET at ≤ 1.2 V on this topology family
> (`ace8383c2fa68d03` / `dhruva-simul`). The wall is physical — an output-stage
> class-A current-swing limit — not a sizing choice and not a voltage-headroom
> limit. Per-band shortfall at the ruled D6 min-gain condition ≈ 21 dB post-D,
> from a 26.6–27.7 dB raw-baseline miss. Two-harness measured; stable under
> perturbation." (§47.3, condensed.)

Choosing this option is choosing to **close the dhruva case study with D5 as its
honest terminal finding** — no new lever pursued, the null recorded as the
result. This requires no further work; it is the do-nothing baseline against
which 3a/3b/3c are priced.

*Ruling text it needs:* **"Close dhruva; D5 stands as the terminal null."**

---

## 4. Ruling table (one row per option — ruling column queued per house convention)

| # | option | what it costs / requires | measured gap it closes | RULING |
|---|---|---|---|---|
| 3a | Supply / Idd envelope relief | ~8 mA in MNM6 (5.5× today), departs the paper's 1.1 V / 13 mA class-A budget (§45.5/§47.3) | the only lever that scales OIP3 into the ~27 dB gap; ~33–55× DC budget needed (§45.5) | *(queued)* |
| 3b | D5 spec relief (D-1) | spec-text governance; re-read "min-gain", partial pass, or re-target (§48.5) | measured levers concede fractions: +0.26 dB port, +0.72 dB sizing, +0.61 dB rail (§45.3/§48.1) | *(queued)* |
| 3c | Topology-class change | new output-stage class; > 1-spare-device budget; **sequenced behind engineer G2** (`engineer/ROADMAP.md` §G2) | the only in-envelope path; unquantified until G2's move repertoire exists | *(queued)* |
| 3d | Record and close | nothing — N already RECORDED (§47.3) | n/a — accepts the null as terminal | *(queued)* |

---

## 5. Provenance

- D5 verdict + five-clause chain: FINDINGS §47.3 (candidate N RECORDED, D-1).
- Wall mechanism + arithmetic: FINDINGS §44.4; `16-WP-LIN.md` §2.2.
- Baseline numbers (26.6–27.7 dB miss, two-harness): FINDINGS §44.2 / §44.9.
- In-box levers exhausted: FINDINGS §45; +3-device widening: FINDINGS §46.
- Perturbation stability (≤ 2.26 dB): FINDINGS §47.1/§47.2, §48.6.
- Output reference impedance (dead lever): FINDINGS §48; pre-reg `19-D7-MEASURE.md`.
- Ladder row + rulings: `14-DHRUVA-SIMUL.md` §1.2 [†], §2, §2.1.
- Cross-line G2 dependency: `engineer/ROADMAP.md` §G2 (cited, not modified).

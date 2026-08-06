# Reference LNA(s) — the harness anchor

The point of this directory is **one circuit the harness provably measures
correctly**, so every later measurement has a regression reference and H-Q2 (no
known-good LNA) is closed. It is not a product; do not gold-plate it.

## Contents

| file | what |
|---|---|
| `device_char.py` | device characterization sweep -> `device_tables.csv` (+ `.png`) |
| `device_tables.csv` | Id/gm/gmb/Cgs/Cgd/fT vs (W, Vgs) for the 45nm NMOS |
| `ref24_cg.cir` | stage-A common-gate 2.4 GHz reference (the match anchor) |
| `check_ref.py` | regression runner: metrics vs baseline + acceptance gates |
| `ref_baseline.json` | stored baseline metrics for the drift check |

## Device characterization (02-REF §2.1)

`device_char.py` sweeps W ∈ {10,20,40,80,160} µm × Vgs 0.2–0.9 V at Vds 0.6 V and
extracts the small-signal parameters (BSIM4 reports the caps with a negative
sign — magnitudes used; params are `save`d before a `.dc`, X3). It confirms
WORKLOG F1.4: **fT is 300–600 GHz** in the usable region and rockets to
>2 THz near threshold on the wide devices, the "peak-fT trap." Every reference
decision reads this table instead of guessing.

## Stage A — common-gate anchor (`ref24_cg.cir`)

A common-gate input has `Zin ≈ 1/(gm+gmb)`, no inductor in the match. From the
device table, **W=20 µm at Id ≈ 2.4 mA** gives gm+gmb ≈ 20 mS → Zin ≈ 50 Ω.
Resistive load, DC-blocked ports, gate AC-grounded (the H-Q1 lesson applied up
front). Measured:

| metric | value | acceptance | verdict |
|---|---|---|---|
| **S11 @ f0 / band-max** | **−23.5 / −23.3 dB** | ≤ −10 dB across band | **PASS (Gate G1)** |
| **Re(Zin), Im(Zin)** | **49.8, −6.7 Ω** | Re within ±25% of 1/(gm+gmb)=49.7 Ω | **PASS — 0.1% (H-Q2 closed)** |
| Idd | 2.40 mA | ≤ 4 mA | PASS |
| S21 @ f0 | −1.4 dB | ≥ 8 dB | **not met — see below** |
| NF @ f0 | 4.1 dB | ≤ 4 dB | marginally over |

### Finding: a resistive-load CG into 50 Ω cannot make gain (S21 ≥ 8 dB)

This is not a bug and not a tuning failure — it is the topology:

* **Headroom caps the load.** The ideal source current sink forces Id, so the
  load drop is Id·RL and must stay under VDD. At Id = 2.4 mA, VDD = 1.1 V, that
  caps RL near 300 Ω; larger RL drives the drain below Vdsat and the DC point
  collapses.
* **The 50 Ω port caps the gain.** A 50 Ω port hung directly on the drain shunts
  the load to ≤ 50 Ω, and a matched CG (unity current gain, gm fixed at 20 mS by
  the match) then has voltage gain ≤ gm·50 ≈ 1 → **~0 dB**. Raising gm for gain
  breaks the match; there is no resistive escape.
* **Low gain ⇒ NF penalty.** With ~0 dB gain the load resistor's own noise is
  barely attenuated when referred to the input, pinning NF near 4 dB.

All three symptoms are one cause. **Gain and noise require a load that presents
a high impedance without a DC drop and transforms to 50 Ω — i.e. a tuned/LC load
(stage B).** The plan's stage-A S21 ≥ 8 dB / NF ≤ 4 dB targets are not achievable
with the specified resistive-load-into-50 Ω topology at VDD = 1.1 V. The anchor's
job — a provably correct, stable, deep match with Re(Zin) matching theory — is
done, and that is what unblocks WP-SIZE and closes H-Q2.

## Stage B — CS + Cex inductive degeneration (`ref24_csdeg.cir`) — the F1 fix

F1 could not build the canonical inductively-degenerated CS match: at the device's
natural fT (300–600 GHz) it needs Ls = 12–27 pH, unbuildable. The fix is to lower
the *effective* fT with an explicit gate–source cap Cex, so wT_eff = gm/(Cgs+Cex)
and the match lands on realizable values:

| quantity | value | in range? |
|---|---|---|
| Ls = Z0·(Cgs+Cex)/gm | **1.35 nH** | ✓ [0.3, 12] nH |
| Lg = 1/(ω0²·Ctot) − Ls | **8.0 nH** | ✓ |
| tuned-load Ld (finite Q=10) | 4.0 nH | ✓ |

Measured: **S11 = −21 dB (band-max −17.8 dB), Re(Zin) = 50.4 Ω, S21 = +6.7 dB**
(real gain, unlike the CG anchor), Idd = 2.2 mA. **F1 is fixed.** S21 ≥ 12 dB and
NF ≤ 2.5 dB are *not* yet met — that final push is the sizer's job (WP-SIZE anchor
re-derivation); this deck is the topology + verified starting values (~90% of the
value, which is what 02-REF §3 asks for if the hand-match doesn't fully close).

### H-Q1 (Re(Zin) = 1122 Ω) — resolved, does not reproduce

Both candidate mechanisms were tested on this circuit (WORKLOG R3):

* **Cascode gate not AC-grounded** — toggling the bypass cap moves Zin only
  37.6+j12 → 33.0+j16 Ω. Real but ~5 Ω, not 1000 Ω.
* **Output tank in-band** — detuning the tank 4× leaves Zin@f0 fixed (38.3 → 38.5
  Ω). Refuted: a bypassed cascode isolates the input from the tank.

The 1122 Ω was an artifact of F1's fundamentally broken circuit (unmatchable
peak-fT bias + the F1.1 gate short), not the harness — which reads Zin to 0.1%
(the CG anchor). The cascode gate is bypassed here (`Cbyp2`), the lesson F1 missed.

### Known harness gap: NF with gain

NF from `inoise_spectrum` with a *port* source goes negative once the stage has
gain — the port z0 is not modelled as a noisy source resistor, so the source-noise
reference is wrong. A proper series-Rs noise source is needed. NF is left ungated
on both decks (the CG's stored 4.1 dB is a stability reference, not validated as
absolute) and is finalized in WP-SIZE.

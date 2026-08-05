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

## Still open (Day 4)

Stage B (CS + Cex inductive-degeneration match, the F1 fix) and the H-Q1 Zin
anomaly (1122 Ω) — staged so the cascode-bypass and tank-detune tests fall out
of the stage-B build order (02-REF §3–4). `check_ref.py` and its baseline are
structured to take a second deck (`ref24_csdeg.cir`) when it lands.

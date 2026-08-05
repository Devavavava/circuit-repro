# WP-REF — a known-good reference LNA, and closing H-Q1

**Answers:** H-Q1, H-Q2, WORKLOG F1, HANDOVER §4-Q5.
**Deliverables:** `lna/ref/ref24_cg.cir`, `lna/ref/ref24_csdeg.cir`,
`lna/ref/check_ref.py` (regression runner), a WORKLOG entry resolving H-Q1.
**Cost:** 2–3 days, all Windows-side ngspice. **Depends on:** nothing.
**Blocks:** 05-SIZING trusts nothing until this anchor exists.

The point is not to produce a beautiful LNA. It is to produce **one circuit
the harness provably measures correctly** (S11 genuinely below −10 dB, NF in a
sane range, numbers stable under re-run), so that every later measurement has
a regression anchor, and to leave H-Q1 explained rather than mysterious.

---

## 1. Why F1 failed, in one paragraph

F1 tried the canonical inductively-degenerated common-source match at the
device's natural fT (300–600 GHz on this model). At that ωT the match equation
`Re(Zin) = ωT·Ls = 50 Ω` demands Ls = 12–27 pH — unbuildable, and with Cgs of
only tens of fF the gate series resonance needs Lg in the tens of nH. Every
subsequent measurement (H-Q1 included) was made on circuits that were never
matchable in the first place. The recipe below changes the operating point,
not the physics.

## 2. Stage A — common-gate reference first (guaranteed match)

Build the *easy* well-matched circuit before the performant one. A common-gate
stage has `Zin ≈ 1/(gm + gmb)` — no inductor in the match at all.

Recipe:

1. **Device characterization sweep** (half a day, do this first — it also
   feeds 05-SIZING bounds). For NMOS W ∈ {10, 20, 40, 80, 160} µm, L = 45 nm,
   sweep Vgs 0.2–0.9 V: extract Id, gm, gmb, Cgs, Cgd (magnitudes — BSIM4
   reports negative caps, WORKLOG F1.3), fT = gm/(2π(Cgs+Cgd)). Save as
   `lna/ref/device_tables.csv` + a plot. Every later design decision reads
   this table instead of guessing.
2. Pick W and Vgs (via source bias) so **gm + gmb ≈ 20 mS at Id ≤ 4 mA**.
   From F1.2 (gm = 5.3 mS at Id = 5.3 mA, deep velocity saturation), expect to
   land at larger W and lower current density than feels natural — the table
   decides, not intuition.
3. Topology: CG NMOS, source to the 50 Ω port through a DC-block, source
   biased with a current source (ideal `I` element is fine for a reference),
   gate at a bypassed VB, **resistive load** 300–500 Ω to VDD, output
   DC-blocked into port 2. No inductors anywhere on the first pass.
4. Acceptance for stage A: **S11 ≤ −10 dB across 2.4–2.5 GHz, S21 ≥ 8 dB,
   NF ≤ 4 dB, Idd ≤ 4 mA**, and — the real test — measured Re(Zin) within
   ±25% of 1/(gm+gmb) read from the device table. When that agreement holds,
   the harness is validated end to end and H-Q2 is closed.

CG noise floor is F ≈ 1 + γ/α, roughly 2.2–3 dB with short-channel γ — it will
not meet the `wifi24` NF constraint, and that is fine: this is the *harness
anchor*, not the product. Do not gold-plate it.

## 3. Stage B — CS + degeneration done right (the Cex recipe)

Now the canonical topology, off the peak-fT trap. The effective transit
frequency is a design variable: `ωT_eff = gm/(Cgs + Cex)` where **Cex is an
explicit capacitor in parallel with Cgs**. The match becomes:

```
Re(Zin) = gm·Ls/(Cgs+Cex)            -> Ls  = Z0·(Cgs+Cex)/gm
resonance: (Lg+Ls) = 1/(ω0²·(Cgs+Cex)) -> Lg ≈ 1/(ω0²·Ctot) − Ls
```

Worked targets at f0 = 2.442 GHz (verify against the device table, don't
trust these numbers blindly):

| choice | value | why |
|---|---|---|
| gm | 20 mS | gain + noise headroom at Id ≈ 2–4 mA |
| Ctot = Cgs+Cex | ≈ 450 fF | makes Lg land ≤ 10 nH (Lg = 1/(ω0²·Ctot) − Ls ≈ 8.3 nH) |
| Ls | Z0·Ctot/gm ≈ **1.1 nH** | realizable — this is the F1 fix |
| Cex | Ctot − Cgs ≈ 350–420 fF | dominates Ctot, so the match barely depends on the device |
| ωT_eff/2π | gm/2πCtot ≈ 7 GHz | f0/fT_eff ≈ 0.35 — NF penalty modest at 2.4 GHz |

Build order, one change per simulation run:

1. CS device + Ls + Cex + Lg, biased through a large RB from a bypassed VB
   (gate DC-blocked from the port — F1.1's short must not recur).
   **Resistive load.** Measure Zin directly (1 A AC drive trick) *as a sweep*,
   not at a spot frequency; confirm series resonance sits near f0 and
   Re(Zin) ≈ 50 Ω there. Tune Ls/Lg against the measured Cgs.
2. Add the cascode device, gate at VB2 **with an explicit bypass capacitor to
   ground** (10 pF). Re-measure Zin. (This is also the H-Q1 experiment — see §4.)
3. Match confirmed → swap the resistive load for the tuned tank; re-measure
   Zin and S11 again (H-Q1 second data point). Extract S21, NF.
4. Acceptance for stage B: **S11 ≤ −12 dB at f0, S21 ≥ 12 dB, NF ≤ 2.5 dB,
   Idd ≤ 5 mA** — i.e. the `wifi24` spec constraints, hit by hand once, and
   all inductors in [0.3, 12] nH. If NF misses by ≤ 0.5 dB, accept and note —
   ZOAF will polish; the anchor's job is the match.

If stage B stalls for more than a day on the match, ship stage A as the anchor
and file stage B as a sizing-loop task (the topology and starting values are
already 90% of the value).

## 4. H-Q1 — the Zin anomaly, resolved as a side effect

Measured: Re(Zin) = 1122 Ω, Im ≈ −10 Ω at 2.395 GHz where theory said
82 − j410 Ω. Two candidate mechanisms, both testable inside the stage-B build
order without extra work:

* **Cascode gate not AC-grounded** (my prime suspect, and unlisted in the
  WORKLOG). Without a bypass cap the cascode gate floats at RF, the cascode
  stops isolating, and the input sees the full Miller-multiplied feedback of
  both devices. The near-zero Im with large Re is what a feedback-flattened
  input looks like. Test = step 2 above with/without the bypass cap.
* **Output tank in-band** (the WORKLOG's hypothesis: tank resonance ≈ 2.77 GHz
  multiplying feedback through Cgd). Test = step 3 vs step 1: resistive load
  first, tank later, diff the Zin sweeps; then detune the tank ±2× and watch
  whether Zin at f0 moves.

Also re-derive the expected Zin symbolically with **CircuitSense** (it handles
inductors as s·L) for the exact F1 netlist — one afternoon, and it turns
"theory says" into an actual checkable expression rather than the textbook
two-term formula, which ignores Cgd entirely.

Write the outcome into WORKLOG.md as a resolution entry, whichever mechanism
wins. If *neither* explains it, that is important — it would mean the sp/ac
port setup itself is suspect, and 05-SIZING must not start until understood.

## 5. Regression runner

`lna/ref/check_ref.py`: runs both reference decks through ngspice_con,
extracts {S11@f0, S21@f0, NF@f0, Idd}, compares against stored expected values
with tolerances (±0.5 dB / ±10%), exit code 0/1. Add it to the regression trio
in 00-OVERVIEW (making it a quartet). This is what makes every future harness
change safe.

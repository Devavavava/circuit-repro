# 19 — D-7 MEASURE: the output-reference-impedance lever, quantified — what the spec would need to concede to close D5

**Status:** **PRE-REGISTRATION — committed alone, before any D-7 SPICE run.**
One measurement set (+ one perturbation-completion item), not a program. Mirrors
the house pre-registration form (`16-WP-LIN.md` §4.4, `17-WP-LIN-D2.md`,
`18-WPLIN-CLOSURE.md`, `13-WP-DIAGHEADS.md`), kept short by mandate.
**Branch:** `main`. **Owner:** the D-7 measurement executor (Session 10, D-7).
**Authorized by:** the user's ruling 2026-08-16 (after recording candidate N):
*"Measure the output-reference-impedance lever: OIP3 vs 100/200/400 Ω, plus the
S11/K/D6-span consequences at each — so the case study ends with 'what the spec
would need to concede to close D5' instead of a bare null."* Folded in: complete
the §47 wall-stability perturbation record on the remaining bands (l2/l1/s; l5 is
done).
**Documentation slots:** FINDINGS §48, JOURNEY stage 46, and a one-line pointer
from the `14-DHRUVA-SIMUL.md` §2 D5-row lever list to §48 (the row's verdict text
does **NOT** change; N stays recorded).

**Read-only / spec-untouched.** D-7 is a **spec-READING** measurement: it
quantifies what a *changed* output reference impedance would buy. **No spec YAML
is edited; the recorded reference stays 50 Ω** (the §7 D-7 default). The measure
tells the user the price of a concession; it does not make the concession.

---

## 0. The question, and why it is worth a measurement rather than an assertion

Candidate N (FINDINGS §47.3) recorded three levers that would move the D5 wall,
each an open user decision. The user has now commissioned the first of them —
**D-7, the output reference impedance** (§7 D-7; §41.8 item 4 flagged that
"2×50 Ω per leg is doing a lot of work"). §2.2 makes it the *direct* setter of
the wall:

> `|Z_ac|` (the AC load the output device MNM6 drives) is `pR4V = 434 Ω`
> **shunted by the 50 Ω port** seen through the output coupling (CC6 10 pF in
> series with Cp2 10 pF ⇒ ~27 Ω of reactance at 1.18 GHz). The design is
> *giving away* its 434 Ω load resistor to the 50 Ω port. Raising the port R
> **un-shunts** the resistor, raising `|Z_ac|` toward the 434 Ω resistor limit;
> the wall is `Iq·|Z_ac|`, and §44.4 measured OIP3 tracking that product
> **dB-for-dB** (Spearman ρ = 1.0000). So OIP3 rises with the port R until the
> coupling caps' own reactance caps `|Z_ac|` below the resistor.

The question this set answers, whichever way it falls:

> **At an output reference impedance of {100, 200, 400} Ω per leg, how much OIP3
> does D5 recover — and what does S11 / K / the D6 span / NF concede at each?**
> The deliverable is the concession table: "at X Ω per leg, D5 at the min-gain
> state would PASS/FAIL by Y dB, at the cost of Z."

---

## 1. The physics, and the OIP3 curve PREDICTED before a single run

`|Z_ac|(R, f0) = | pR4V ∥ ( 1/(jωC_ser) + R ) |`, with
`C_ser = CC6·Cp2/(CC6+Cp2) = 5 pF`, `pR4V = 434.067 Ω`. Evaluated per band
(the coupling reactance is f0-dependent), and the OIP3 delta taken as
`ΔOIP3 = 20·log10(|Z_ac|(R)/|Z_ac|(50))` (the §44.4 dB-for-dB law):

**Predicted at the D6 min-gain S3 state, 1.2 V**, off the §44.2 baseline
(OIP3_50 = −13.25/−13.19/−12.97/−13.05; IIP3_50 = −34.19/−34.28/−34.67/−34.46
at l5/l2/l1/s):

| band | port R | \|Z_ac\| Ω | ΔOIP3 dB | pred OIP3 | pred IIP3 | D5 tgt | pred margin |
|---|---|---|---|---|---|---|---|
| l5 | 50  | 50.9  | +0.00 | −13.25 | −34.19 | −7.4 | **−26.79** |
| l5 | 100 | 84.1  | +4.36 |  −8.89 | −29.83 | −7.4 | **−22.43** |
| l5 | 200 | 138.0 | +8.67 |  −4.58 | −25.52 | −7.4 | **−18.12** |
| l5 | 400 | 208.5 | +12.25 | −1.00 | −21.94 | −7.4 | **−14.54** |
| s  | 50  | 46.3  | +0.00 | −13.05 | −34.46 | −8.7 | **−25.76** |
| s  | 100 | 81.9  | +4.96 |  −8.09 | −29.50 | −8.7 | **−20.80** |
| s  | 200 | 137.2 | +9.44 |  −3.61 | −25.02 | −8.7 | **−16.32** |
| s  | 400 | 208.3 | +13.07 | +0.02 | −21.39 | −8.7 | **−12.69** |

(l2/l1 land between l5 and s; full four-band table computed in the sidecar.)

**Predicted saturation.** `|Z_ac|` rises from ~51 Ω (50 Ω port) toward a **ceiling
of ~208 Ω at 400 Ω port** — NOT to the 434 Ω resistor, because at R→∞ the coupling
caps still shunt `|Z_ac|` to the resistor with ~6 dB of series-reactance loss
remaining. So the curve is **concave**: +4.4 dB (50→100), +4.3 dB (100→200), but
only +3.6 dB (200→400). Past ~400 Ω the port R is no longer the binding shunt and
the lever saturates against the coupling network.

**★ The pre-registered headline prediction (Q1).** The D-7 lever buys **~12–13 dB
at 400 Ω** at the ruled min-gain condition — real and dB-for-dB, but the gap is
26–28 dB, so **D5 still FAILS at every impedance, by ~13–15 dB even at 400 Ω**.
The port impedance is a partial lever, not a closing one, on this topology at this
budget. **Falsifier:** measured OIP3 at any R departs from the predicted dB-for-dB
curve by ≥ 3 dB (which would mean `|Z_ac|` is not the sole binding factor, or the
larger swing pushes MNM6 out of class-A / into compression — a legitimate and
reportable outcome that would re-open §2.2 at large swing).

**Q2 (the secondary, on the smallest closing R).** The smallest R at which D5 at
min-gain would PASS. Prediction: **none in {100, 200, 400}** — extrapolating the
concave curve, closing the worst band would need `|Z_ac|` ≳ 900–1400 Ω, which the
coupling network *cannot deliver* (ceiling ~208 Ω). So the honest D-7 answer is
expected to be "the lever helps ~13 dB and saturates ~15 dB short," and the HB
cross-check (§3) is owed at **400 Ω** (the largest R, where the swing is biggest
and any compression / class-A departure would show).

---

## 2. The exact grid — Task 1 (D-7)

**Point:** the BASELINE `dhruva-simul` designated D4-SIM point, no candidate
mechanism, **pVDD = 1.2 V nominal** (the ruled condition). Emitted via rung 0's
deck path (`_lin_baseline.base_body` + `simul_params`), min-gain S3 via
`_lin_baseline.min_gain_body_params` (structural role resolution, §42.2/§6.7).

**The output reference impedance is changed on the OUTPUT leg ONLY.** In the deck
the output path is `RR4 VDD n0 434.067` → `CC6 n0 VOUT1 10p` → `Cp2 VOUT1 p2 10p`
→ `Vp2 p2 0 ... portnum 2 z0 50`. The transient harness (`iip3.py`) replaces the
port-2 source with a physical `Rload p2 0 Z0` and reads OIP3 as power delivered
into that load (`vout_to_dbm`, `/(2·Z0)`). D-7 re-points **the output side only**:
* **`Rload` (port 2) → R** ∈ {50 (control), 100, 200, 400} Ω — the physical load
  that un-shunts `pR4V` and sets `|Z_ac|`.
* **`vout_to_dbm` → power into R** — OIP3 is the power actually delivered to the
  new reference load (the physically meaningful output-referred number).
* **The INPUT side is UNTOUCHED at 50 Ω.** `Rsrc`, `pav_dbm_to_vemf` (available
  input power), and the port-1 z0 stay 50 Ω — the antenna reference does not move;
  D-7 is an *output*-port decision. IIP3 = OIP3 − G with G the small-signal gain
  into the new load. (Sidecar overrides `iip3.Z0`-consumers per side; the shared
  file is never edited — §7 D-9.)

**Reference impedances:** {**50 (control), 100, 200, 400**} Ω per output leg.

**States:** the **D6 min-gain S3** state (the ruled D5 condition — primary) **and
max gain** (reference), per the mandate.

**Bands:** **dhruva-l5** (worst-margin) required at every R; the other three bands
added if cheap (the mandate: "add other bands only if cheap").

**Reading (per R, per state, per band):**
* **IIP3 / OIP3** two-tone, full §37.3 fences (below), the deliverable D5 margin.
* The **S21 cross-check is re-pointed per config** — the small-signal gain into
  the new load R changes, so its reference is taken from a **measured small-signal
  run at that R** (never disabled, never inherited; §4.0 item 3 / §37.4).

**Consequences at each R (the concession columns), band-wide 1.1–2.5 GHz:**
* **S11** — re-normalized to the new reference. ★ **What S11 means when the port R
  changes:** S-parameters are reference-impedance-dependent. S11 = S_1_1 is the
  *input* reflection at port 1 (the antenna, z0 = 50 Ω, unchanged) — but the output
  port-2 termination changes the two-port's loading, so S_1_1 shifts. We report
  **both**: (a) S11 with port 2 renormalized to R (the self-consistent number for
  the changed design), and (b) the input-referred match at the fixed 50 Ω antenna
  (what the antenna actually sees). The gate is band-wide S11 ≤ −10 dB; we state
  which reading is gated and by how much margin it moves.
* **S21, NF, K_min, Idd** — at each R (K and Idd are read from the same sp/op run;
  NF from the series-Rs deck, `size.eval_metrics`).
* **The D6 span** — the §42.5 states (S0…S3) re-measured at the new port R, so the
  span (S0−S3 gain) is reported as the port changes (raising the output load
  raises max-gain-state gain and can change the span).

**HB cross-check** at the impedance that matters most — **the smallest R that
closes D5, or 400 Ω if none does** (Q2 predicts 400 Ω). Measured in VACASK HB via
`_lin_hb.py`'s machinery, re-pointed to the new load, reported as the cross-method
|Δ(OIP3)| against the transient number (bar: the program's 0.08 dB precedent,
§37.6).

**The deliverable sentence**, whichever way it falls, per band:
> "at **X Ω** per leg, D5 at the min-gain state would **PASS/FAIL by Y dB**, at the
> cost of **Z** (S11 / span / NF / K changes)."

### 2.1 Fences (§37.3 / §6.7, intact on every row — a NEW measurement)

Replay ×3 in-process (spread target 0.0000 on IIP3) on every **published** row,
IM3 slope in 3 ± 0.3, ≥ 10 dB IM3-over-floor SNR, ≤ 0.5 dB compression on kept
points, per-point spread reported, the re-pointed §37.4 S21 cross-check (this
config's own audited S21 at the new R, per R) **never disabled**. Min-gain drive
window −68…−52 dBm (§44.3) as a starting point — **but at higher R the larger
swing may need a lower window to stay ≤ 0.5 dB compression**; slope-fence failures
are re-driven and recorded, never metric-changed (§44.3 precedent). Max-gain
−80…−40.

---

## 3. The exact grid — Task 2 (perturbation completion, l2/l1/s)

Extend §47's grid (`_lin_perturb.py`, verbatim) — nominal control + VDD×0.9 +
VDD×1.1 + 85 °C + worst combo (VDD×0.9 + 85 °C), **S3 min-gain + max gain, 1.2 V
nominal** — to the **three remaining bands l2/l1/s** (l5 is done, §47.1). Same
reduced set (§18 §1), same fences, replay ×3, all §37.3 fences intact. Verdict vs
the **same 5 dB falsifier** (Q1 of §18): report `ΔIIP3`/`ΔOIP3` vs each band's P0
nominal control at the ruled (min-gain) condition; a ≥ 5 dB move on any axis would
qualify the N record and must be reported loudly. Append to the §47 record (or
§48) per house style. ~30 SPICE-min.

---

## 4. Caps (stop at cap, publish shortfall — §34 precedent)

* **Task 1 (D-7):** ≤ **90 SPICE-min**, ≤ **3 h wall** at ≤ **48 workers**
  (⚠ a concurrent LDO scoring run holds ~56 cores for ~3 h — throttle to ≤48).
  Grid: 4 R × 2 states × (1–4 bands) × ~5 drives × 3 replays + per-R S21/S-param/op
  consequence runs + one HB cross-check config. If the cap is threatened: hold all
  four R at l5-min (the ruled, worst band) first, then drop max-gain, then drop the
  extra bands.
* **Task 2 (perturbation):** ~**30 SPICE-min** inside the Task-1 budget headroom.
* HB is owed only at the one D-7 cross-check impedance (§3); the transient wall
  numbers stand on their replay fence otherwise.

---

## 5. Law (unchanged from WP-LIN)

Goldens GREEN before/after (`check_ref`, `check_iip3`, `check_hb`, `check_diff`).
Sidecar + module-attribute overrides only; **no shared harness edit** (§7 D-9);
**no spec / frozen-protocol touch** (§7 D-3) — **D-7 is a spec-READING measurement,
the spec YAMLs are untouched, the recorded reference stays 50 Ω.** §42.2 node-name
discipline on every insert. Append-only store, `recipe=wplin-v1`,
`source_arm=wplin-d7`. Candidate N stays RECORDED (the D5 row's verdict text does
not change); §48 adds only a lever-detail pointer.

---

## 6. Outcome (appended after execution — FINDINGS §48)

*Empty by design. Filled in after the fact — whichever way each prediction falls —
with full detail in FINDINGS §48.*

**Executed 2026-08-16 (Session 10). Goldens GREEN before and after. FINDINGS §48.**

| pre-registered claim | verdict |
|---|---|
| **Q1** the D-7 lever buys ~12–13 dB at 400 Ω, dB-for-dB (falsifier: measured OIP3 departs the predicted curve by ≥ 3 dB) | **REFUTED, falsifier TRIPPED (§48.2), and the underlying premise corrected.** The naive `Iq·\|Z_ac\|` extrapolation predicted +12 dB; the D5-gated **IIP3** actually moves **+0.26 dB** (min-gain) / **+0.45 dB** (max) across 50→400 Ω — curve deviation **18.25 dB**. The port is a **gain** lever, not a **linearity** lever: OIP3 = IIP3 + G, and only G responds (min-gain G *falls* 20.9→14.7 as the fixed coupling de-matches; max-gain G rises 33.2→35.9). D5 FAILS 0/4 at every R by ~26.5 dB. |
| **Q2** no R in {100, 200, 400} closes D5; the coupling caps `\|Z_ac\|` at ~208 Ω so the lever saturates | **CONFIRMED (§48.1–48.2).** None closes D5 (fails by 26.7/26.6/26.5 dB). `\|Z_ac\|` saturates 51→84→138→208 Ω; max-gain OIP3 is **concave and turns over at ~200 Ω** (+1.84 → +1.81 at 400). |
| the concession table (per R: D5 margin, S11, span, NF, K) | **DONE (§48.4).** S11@50-antenna invariant −11.48 (S11@400-renorm −11.02, still passing); NF/K/Idd unchanged (1.61/17.16/9.46); D6 span **widens** 12.2→21.2 dB; S21 rises. **No binding cost** — the lever concedes nothing and buys ~0.3 dB. |
| the HB cross-check delta at the owed impedance (400 Ω) vs the 0.08 dB precedent | **DONE (§48.3).** **IIP3 two-harness identical to 0.00 dB** (−33.93 = −33.93); the 6.27 dB OIP3 Δ is entirely gain-reference (transient reads gain into the physical 400 Ω load, HB references its S-param port) — a direct confirmation that the port moves the gain reference, not the distortion. |
| Task 2 — l2/l1/s wall stability vs the 5 dB falsifier | **MEASURED, STABLE (§48.6).** l2/l1/s min+max, VDD×0.9/×1.1/85 °C/combo: worst \|ΔIIP3\| **[FILLED IN §48.6]** dB, far under the 5 dB falsifier — matching the l5 result (§47), the wall is a per-topology fact on every band. |

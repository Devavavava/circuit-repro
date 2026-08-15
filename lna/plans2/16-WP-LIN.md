# 16 — WP-LIN: the linearity-aware redesign, pre-registered before a single candidate is sized

**Status:** **DRAFT — pre-registered for user sign-off; not adopted.**
Written 2026-08-14, **before any candidate topology/bias change has been
proposed, before the IIP3 head exists, and before the designated point's own
IIP3 has ever been measured** (§1.3 — that last fact is not a rhetorical
flourish, it is the largest hole in the corpus this WP inherits).
**Branch:** `lna-data`. **Owner:** the WP-LIN executor (Session 10).
**Series:** continues `plans2/14-DHRUVA-SIMUL.md` §2.1 ruling 4 (the user's
linearity ruling) and `plans2/15-ENGINEER-PROPOSAL.md` §4.1-N1 (the three loop
upgrades this WP pilots). Mirrors the pre-registration form of
`plans2/13-WP-DIAGHEADS.md`.
**Files this WP may touch:** `lna/plans2/16-WP-LIN.md` (this file), new
sidecars `lna/_lin_*.py`, and artefacts under `lna/out/` + a standalone
`lna/repro/dhruva-best/dhruva-simul.sp` (emitted, see §4.0). **Read-only:**
`lna/iip3.py`, `lna/hb/hb_iip3.py`, `lna/pgain.py`, `lna/corners.py`,
`lna/diff3.py`, `lna/_diff_balun.py`, `lna/size.py`, `lna/templates.py`,
`lna/moves.py`, `lna/extract.py`, every `lna/ref/check_*.py`. Harness
parameters that must differ (§4.0) are overridden by module-attribute
assignment from a sidecar, never by editing the shared file.
**Documentation slots:** next free FINDINGS § and JOURNEY stage at execution
time (numbers assigned then — the 2026-08-14 execution wave claimed stage 40
after this draft was written). The D5 row of
`plans2/14-DHRUVA-SIMUL.md` §2 is amended **only after user sign-off**, never
by the executor.

---

## 0. The question

The user has ruled (`14-DHRUVA-SIMUL.md` §2.1, ruling 4): **a ≤1.2 V
linearity-aware redesign, no supply-envelope deviation, judged at the D6
min-gain state.** This WP turns that ruling into a measurement.

> **Can a ≤1.2 V topology/bias change on the `dhruva-simul` host buy the
> 21.6–25.4 dB of IIP3 that the measured wall demands, judged at the D6
> min-gain state — and if it cannot, what exactly is the mechanism that stops
> it?**

Two independent, golden-validated harnesses agreeing to 0.08 dB (§37 ngspice
two-tone transient, §40 VACASK harmonic balance) have already answered the
easy half: **no re-sizing will do it.** OIP3 is pinned flat at **+3.17 …
+3.44 dBm** across all four bands *and* across four independently-descended
parameter sets (§37.7: own-sizing spread +2.44 … +4.19 dBm), while the gain
varies by 2.25 dB — so linearity here is a property of *the topology on this
power budget*, not of a sizing choice. §37.7 priced the max-gain requirement
at **22× to 50× the entire DC power budget** and called it "outside the
physics of the power budget".

But the ruling does not ask for the max-gain number. It asks for the number
**at the D6 min-gain state**, and that changes the arithmetic by more than an
order of magnitude (§2.3). The honest form of the question this WP must answer
is therefore three-part, and each part has its own falsifier:

1. **Can the D6 gain-control mechanism be moved to the front end?** The
   §42 mechanism is output-side, so its low-gain states buy *zero* IIP3
   (§42.6 item 1 — the mechanism attenuates after the nonlinearity). Every
   front-side mechanism was measured **match-illegal** — but on the *l5* host,
   whose S11 margin was 0.001 dB. The designated host carries **+1.484 dB**
   at 1.2 V. That measurement has never been re-run on the designated host.
   Worth ~12 dB if the wall has lifted; worth 0 dB if it has not.
2. **Can the output stage find ~8–9 dB more OIP3 inside a 13 mA / 1.2 V
   budget?** §2 argues from the measured operating point that the binding
   limit is the output stage's **class-A current swing**, not its voltage
   headroom, and that the output stage carries only **15% of the design's
   current** while carrying the whole output swing.
3. **If neither, is the wall physical at ≤1.2 V?** That is a legitimate
   outcome with a pre-stated evidence bar (§3, candidate **N**), not a
   failure to report.

---

## 1. What is standing, measured, before this WP starts

Everything in this section is quoted from the corpus. Nothing here is
re-derived, and nothing here was produced by this WP.

### 1.1 The host — `dhruva-simul` @ pVDD = 1.2 V (the designated D4-SIM point)

Topology `ace8383c2fa68d03`, 20 devices, 2 inductors; sizing
`dhruva-simul.params.json`, recipe `mf2-v1+harden-v1` (§36).

| gate | target | measured @ 1.2 V | margin | source |
|---|---|---|---|---|
| S11, band-wide 1.1–2.5 GHz | ≤ −10 dB | **−11.484** | +1.484 | §36.3 |
| S21 @ S / L1 / L2 / L5 f0 | ≥ 30 / 25.4 / 22.3 / 22.3 | 33.454 (worst-band S) | +3.454 | §36.3, §14 §1.1 |
| NF worst band (l5) | ≤ 2.5 dB | 1.606 | +0.894 | §36.3 |
| Idd | ≤ 13 mA | **9.463** | +3.537 | §36.3 |
| K_min in-band | ≥ 1 | 17.158 | ~17× | §36.3 |
| sensitivity sweep @ 1.2 V nominal | no gate flips | **zero flips on every axis** (worst NF +0.012 dB under VDD×0.9 + 85 °C) | — | §14 §2.1 ruling 1 |

At 1.1 V the same point reads S11 −11.012 / Idd 8.205 mA / K_min 17.206 (§36.2).

### 1.2 The wall — Gate D5, measured twice, on the *other* point

Both harnesses measured the **`dhruva-l5`** sizing (the previous designated
point) at 1.1 V, one fixed sizing at all four band f0, at **max gain**:

| band | IIP3 transient (§37.5) | IIP3 HB (§40.3) | Δ | target | margin | OIP3 (transient / HB) |
|---|---|---|---|---|---|---|
| l5 (1176.45 MHz) | **−32.78** | −32.76 | 0.02 | ≥ −7.4 | **−25.38** | +3.17 / +3.20 |
| l2 (1227.60 MHz) | **−32.73** | −32.70 | 0.03 | ≥ −7.4 | **−25.33** | +3.20 / +3.23 |
| l1 (1575.42 MHz) | **−32.20** | −32.14 | 0.06 | ≥ −7.6 | **−24.60** | +3.33 / +3.39 |
| s (2492.03 MHz)  | **−30.36** | −30.28 | 0.08 | ≥ −8.7 | **−21.66** | +3.35 / +3.44 |

Fences that make these numbers safe to build on: IM3 slope 2.991–2.997
(bar 3 ± 0.3), per-point IIP3 spread ≤ 0.07 dB (transient) / ≤ 0.43 dB (HB),
timestep ΔIIP3 ≤ 0.011 dB, HB replay spread **0.000 dB**, and the transient
harness's small-signal gain reproducing the audited `sp` S21 to ≤ 0.02 dB.

### 1.3 ⚠ What has NEVER been measured — and it is the first thing WP-LIN owes

1. **The designated point's IIP3.** §40.7 item 2 and §37.7 both say so
   explicitly: neither D5 harness has measured `dhruva-simul`. Worse, §40.4
   records the *expectation that it is worse*: WP-HARDEN cut Idd 37 %
   (12.963 → 8.205 mA) and IIP3 scales with bias headroom, so "the hardened
   point is very likely *further* from D5, not closer". **Every acceptance
   number in this WP is a delta against a baseline that does not yet exist.**
2. **`lna/repro/dhruva-best/dhruva-simul.sp` does not exist on disk** —
   verified 2026-08-14. The point ships as `.params.json` + `.meta.json`
   only, and `lna/iip3.py --sizing simul` will exit (§37.7 says so; the
   harness enforces it).
3. **D6 at the ruled 1.2 V nominal.** §42.5's tables are measured at
   pVDD = 1.1 V with the switch gates driven at the deck's own 0 V / 1.1 V
   rails. The ruling gates at 1.2 V. **"D6 MET" and "gated at 1.2 V" have
   never been jointly measured.**
4. **D7 at 1.2 V.** §41.4's balun result (Idd 9.250 mA, imbalance
   0.119 dB / 0.329°) is at 1.1 V.
5. **IIP3 under any sensitivity axis.** `lna/corners.py` sweeps the tier-1 +
   tier-2 gates only; no distortion metric has ever been perturbed.

### 1.4 The D6 configuration this WP must be judged inside

`out-bank` on the `dhruva-simul` substrate, three DC-blocked NMOS switch
branches on the **output-stage drain**, states differing only in
`pVSWGOB{1,2,3}` (§42.5, second table, @ 1.1 V):

| state | S | L1 | L2 | L5 | S11_max | Idd | K_min |
|---|---|---|---|---|---|---|---|
| S0 (max) | 31.93 | 32.21 | 31.58 | 31.43 | −11.011 | 8.205 | 17.6 |
| S3 (**min — the state D5 is judged at**) | **19.94** | **20.09** | **19.38** | **19.23** | −11.038 | 8.205 | 345.7 |
| span | 11.99 | 12.13 | 12.19 | 12.21 | | | |

**And the sentence that defines this WP's difficulty (§42.6 item 1):** this
mechanism sits *after* the last gain stage, so in state S3 the front end still
sees the full input and still compresses identically; OIP3 falls with the gain
and **IIP3 is unchanged**. Judged at S3 with this mechanism, D5 fails by the
same 21.6–25.4 dB it fails by at S0.

### 1.5 Corpus tensions this WP inherits, recorded rather than smoothed

1. **`14-DHRUVA-SIMUL.md` §1.2 attributes an l5-point measurement to the
   designated point.** Its tier-3 row reads "achieved (`dhruva-simul` @ 1.2 V)
   … −30.3 … −32.8 dBm … OIP3 +3.2 … +3.4" — but both D5 harnesses measured
   **`dhruva-l5` at 1.1 V**, and §40.7 item 2 / §37.7 both say `dhruva-simul`
   was never measured. The table is a fair statement of *the program's* D5
   result and a wrong statement of *this point's*. Rung 0 closes it; until it
   does, no WP-LIN number is quoted as a delta against that row.
2. **The designation ruling and the linearity ruling pull opposite ways, and
   the corpus says so.** §40.4: WP-HARDEN's 37 % Idd cut buys S11/VDD
   robustness, and "IIP3 scales with bias current and headroom, so the
   hardened point is very likely *further* from D5". The same point was then
   designated (ruling 1) and a linearity redesign ordered on it (ruling 4).
   Both rulings are correct on their own evidence; WP-LIN is where the bill
   arrives, and P1 is the prediction that it does.
3. **D6 and D7 are MET at 1.1 V; the ruling gates at 1.2 V.** §42.5's states
   and §41.4's balun are 1.1 V measurements (switch rails 0 / 1.1 V, Idd
   9.250 mA). Nothing has re-measured either at the ruled nominal, and nothing
   has ever measured D5 + D6 + D7 on **one** netlist (§7 D-6).
4. **§36.5 says the hardened point is "not adopted"** — superseded by §2.1
   ruling 1, noted only so a future reader does not read the two as live
   disagreement.
5. **`lna/out/_lin_op_1p{1,2}.json` are undocumented.** They match this point's
   Idd at both rails to five digits and are the source of §2.1's table, but
   they appear in no FINDINGS section, are gitignored, and carry no recipe
   stamp. Treated as provisional; re-derived under the replay fence in rung 0.

---

## 2. The diagnosis, registered as a falsifiable hypothesis *before* any candidate is proposed

`15-ENGINEER-PROPOSAL.md` §4.1-N1(b) asks for a diagnosis-first, swing-directed
move set. This is the diagnosis, written down in advance so it can be wrong on
the record.

### 2.1 The measured operating point of the host, both rails

Read from `lna/out/_lin_op_1p1.json` / `_lin_op_1p2.json` (op dumps of the
`dhruva-simul` sizing deck; their `-i(Vsup)` reproduces §36.3's 8.205 mA /
9.463 mA to five digits, which is what identifies them). ⚠ **These artefacts
are gitignored, undocumented in FINDINGS and of unrecorded provenance — the
executor re-derives them under the replay fence before any of the arithmetic
below is quoted.**

| device | role | Id @1.1 V | Id @1.2 V | share of Idd @1.2 V | gm/Id @1.2 V | Vds @1.2 V | Vdsat @1.2 V | region |
|---|---|---|---|---|---|---|---|---|
| MNM1 | CG input (source on the input node) | 0.484 mA | 0.554 mA | 5.9 % | 14.2 | 0.5637 | 0.0708 | sat |
| MNM2 | CS input, 66.2 µm | 1.419 | 1.608 | 17.0 % | 16.2 | 0.4890 | 0.0610 | **sub** |
| MNM3 | recombine-node device | 0.110 | 0.125 | 1.3 % | 16.2 | 0.4890 | 0.0610 | **sub** |
| MNM4 | tank stage (L-loaded) | **3.963** | **4.634** | **49.0 %** | 9.9 | 0.7274 | 0.1006 | sat |
| MNM5 | CS input, 45.7 µm | 0.979 | 1.109 | 11.7 % | 16.2 | 0.4890 | 0.0610 | **sub** |
| **MNM6** | **output stage** (load `pR4V` = 434.067 Ω, AC-coupled to the 50 Ω port) | **1.250** | **1.432** | **15.1 %** | 13.8 | 0.5782 | 0.0730 | sat |

### 2.2 ★ The hypothesis: the wall is a **current**-swing wall, not a voltage-headroom wall

The corpus calls it "an output-swing-budget wall on the 1.1 V envelope"
(§14 §2, §37.7, §40.4) without separating the two things that phrase can mean.
First-order arithmetic on the table above separates them (**derived here, not
corpus — it is a prediction, and §4 rung 0 is its falsifier**):

* **Voltage-headroom limit** at MNM6's drain @1.2 V:
  `min(VDD − Vq, Vq − Vdsat) = min(1.200 − 0.578, 0.578 − 0.073) = 505 mV`.
* **Class-A current limit** at the same node: the AC load is
  `pR4V = 434 Ω` in parallel with the 50 Ω port seen through
  `CC6`+`Cp2` (10 pF in series with 10 pF ⇒ ~27 Ω of reactance at 1.18 GHz),
  i.e. **|Z_ac| ≈ 51 Ω**. Peak current before cut-off is Iq = 1.432 mA, so the
  peak drain swing is **1.432 mA × 51 Ω ≈ 73 mV**.

**The current limit binds by a factor of ~6.9 (≈ 17 dB).** If that is right,
then three things follow immediately, and all three are testable cheaply:

* **bias re-centering on the 1.2 V rail buys ~1 dB, not 22** — re-centering
  the drain to the midpoint of `[Vdsat, VDD]` moves a limit that is not
  binding;
* **cascode headroom re-stacking makes it worse**, because a cascode spends
  the plentiful resource (voltage) to buy an irrelevant one;
* the levers that matter are the ones that raise `Iq × Z_ac`: **current
  re-allocation into the output stage** (which today takes 15.1 % of the
  budget while MNM4's tank stage takes 49.0 %) and **raising the impedance
  the output device drives**.

**A four-point falsification test that costs four `op` runs.** §37.7 already
measured OIP3 on four independently-descended sizings of this topology
(+2.44 … +4.19 dBm). If the hypothesis holds, those four OIP3 values order
with each sizing's `Iq(MNM6) × |Z_ac|` product. Two anchors are already on
file: the l5 point runs MNM6 at **3.32 mA into pR4V = 132.7 Ω** (§41.7,
|Z_ac| ≈ 41 Ω ⇒ 136 mV) and the designated point at **1.432 mA into 434 Ω**
(|Z_ac| ≈ 51 Ω ⇒ 73 mV) — **≈1.9× (5.4 dB) in the l5 point's favour**, or
≈2.1× (6.6 dB) compared at equal rails. If the hypothesis holds this
**predicts the designated point's OIP3 lands near −3 … −2 dBm, i.e. 5–7 dB
*worse* than the +3.2 … +3.4 the corpus quotes for the l5 point.** §4 rung 0
measures it. If the ordering fails, this section is wrong and §3's row weights
change.

### 2.3 ★★ What "judged at the D6 min-gain state" does to the requirement

This is the reframing the ruling licenses, and it is the reason WP-LIN is worth
running rather than conceding.

`IIP3 = OIP3 − G`. At the D6 min-gain state the gain is **19.23 … 20.09 dB**
(§42.5, simul substrate). So the OIP3 the design needs *at that state* is:

| band | D5 target | G at min-gain state (§42.5) | **required OIP3** | measured OIP3 (l5 pt) | shortfall |
|---|---|---|---|---|---|
| l5 | ≥ −7.4 | 19.23 | **+11.83 dBm** | +3.17 | **8.7 dB** |
| l2 | ≥ −7.4 | 19.38 | **+11.98** | +3.20 | 8.8 |
| l1 | ≥ −7.6 | 20.09 | **+12.49** | +3.33 | 9.2 |
| s  | ≥ −8.7 | 19.94 | **+11.24** | +3.35 | 7.9 |

Against the DC budget: **+11.2 … +12.5 dBm is 1.2–1.6× the designated point's
own DC power** (1.2 V × 9.463 mA = 11.36 mW = +10.55 dBm), or **0.85–1.15×**
if the full 13 mA gate is spent (15.6 mW = +11.93 dBm). Compare §37.7's
verdict at max gain: **22× to 50× the DC budget.** The min-gain condition moves
the requirement from *outside the physics of the power budget* to *roughly one
times the power budget* — hard for a class-A stage, but no longer absurd.

**The catch, stated so it cannot be quietly dropped:** the table above credits
the min-gain state with 12 dB of gain reduction that today is delivered
*output-side*, where it buys **no** IIP3 (§42.6 item 1). The 8–9 dB of OIP3 in
the last column is only the *residual* after the gain control has been moved
ahead of the nonlinearity. So the 21.6–25.4 dB decomposes as:

```
  ~12 dB   from moving the D6 gain-control mechanism to the front end
           -- worth 0 dB unless the §42.3 match wall has lifted on this host
+ ~8-9 dB  of genuine output-stage OIP3 on a <=13 mA / 1.2 V budget
= ~21-22 dB, against a 21.6-25.4 dB gap
```

Both halves must land. Either one alone leaves a double-digit miss. **That
decomposition is this WP's central pre-registered claim, and §8 P1–P3 are its
falsifiers.**

---

## 3. Candidate mechanisms

Every row states its physical mechanism, why it does or does not attack an
**output-swing-limited** wall, the cheap screen that can kill it before any
two-tone run, and its risk to the standing MET gates (D4-SIM margins from
§1.1, the D6 mapping's five clauses from §42.1, D7 imbalance from §41.4,
Idd ≤ 13 mA, K_min ≥ 1).

**Two structural constraints bind every row** and are stated once here:
the topology is at **20 of its 21-device budget** (`device_budget: [3, 21]`,
`dhruva-*.yaml`) — **exactly one spare device** — and 2 of 6 inductors; and
every parameter must stay inside the specs' own box (`w_um [1, 200]`,
`r_ohm [50, 20e3]`, `c_f [50f, 10p]`, `vb_v [0.2, 0.9]`, `l_fixed = 45 nm`,
`L 0.3–15 nH`). Anything that needs more is a **user decision** (§7 D-2).

| # | mechanism | why it attacks (or does not attack) an OUTPUT-swing wall | cheap screen (tier-1, ~1 s/eval) that kills it early | risk to standing MET gates |
|---|---|---|---|---|
| **A** | **Front-end gain control** — move the D6 mechanism from the output-stage drain to the input combiner / MNM2-MNM5 gates / recombine node | The *only* class that converts D6 states into IIP3. It attenuates **before** the nonlinearity, so at min-gain the output stage sees a smaller drive for the same output level ⇒ IIP3 improves ~dB-for-dB with the span (§42.6 item 1, read in reverse). Does **not** raise OIP3 — it is exactly the ~12 dB half of §2.3, not the ~8–9 dB half. | Re-run `pgain.py --probe` and `--wall` on the **simul** substrate at 1.2 V. §42.3's probe was measured on a host with 0.001 dB of S11 margin; this host has **1.484 dB**. A second, independent reason to expect a different reading: §42.3 blames the match-forbidden zone on the C_gd of "the two 94 µm CS devices", and on this host MNM2/MNM5 are **66.2 / 45.7 µm**, not 94.5 / 93.2. Pure S-parameter runs, seconds each. Kill: band-wide S11 > −10 dB in **any** state, or match-legal span < 10.6 dB. | **S11 band-wide** is the whole risk (§42.4: the input combiner's *all-off* state alone broke the l5 gate by 0.033 dB from switch off-capacitance). D6 clause 3 (S11 + Idd in every state) and clause 4 (max-gain state passes D4-SIM). NF in low states is **not** gated (clause 5). D7 untouched (balun is downstream). |
| **A'** | **Source-degeneration ladder** under the CS pair (MNM2/MNM5), used as the gain-control mechanism | Same front-side logic as A, plus series feedback linearizes the transconductor itself. | Already measured on the l5 host and it is an **authority** wall, not a match wall: **2.59 dB of match-legal span, 2.73 dB ceiling** (§42.4 row `in-degen`) — a ceiling that does not move with S11 margin. Re-measure the ceiling on this host; kill if < 10.6 dB and it cannot be combined with A. | Low S11 risk (§42.4: "holds the match comfortably"). Costs S21 at max gain (clause 4, +3.454 dB of margin) and NF (input-side degeneration; +0.894 dB of margin on l5). |
| **B** | **Output-stage current re-allocation** — spend the Idd headroom and MNM4's share on MNM6 | Attacks the wall §2.2 says is binding: the class-A current limit `Iq × Z_ac`. MNM6 carries **15.1 %** of the budget while carrying the entire output swing; MNM4 carries **49.0 %**. Idd headroom at 1.2 V is **3.537 mA**. First-order, OIP3 rises ~dB-for-dB with `Iq` at fixed `Z_ac` — the ~8–9 dB half of §2.3 in its most direct form. | One `size.eval_metrics` per candidate: Idd, S11 band-wide, S21 at four f0, NF, K_min, plus the OP-derived `Iq(MNM6) × Z_ac` and `Vq − Vdsat` proxies. Kill: **Idd > 13 mA at 1.2 V**, or S21 below the D4-SIM floors, or any device leaving conduction. | **Idd gate** (hard) and **S21 clause 4** (taking current off the 49 %-share tank stage costs gain; +3.454 dB of margin at S band, +2.003 dB at 1.1 V). **NF** via Friis if front-stage gain drops (+0.894 dB margin). **D7**: the balun costs another 1.045 mA on top (§41.4) and the switch bank adds its own — the three must fit 13 mA **together**. |
| **C** | **Raise the output-stage AC load impedance** — L-match / tapped inductor / higher `pR4V` with the port coupling re-designed | The other factor in `Iq × Z_ac`. Today `Z_ac ≈ 51 Ω` in magnitude because a 434 Ω load is shunted by the 50 Ω port through 5 pF of series coupling: the design is *giving away* its load resistor. §41.6 already measured the impedance of this node mattering — the hardened core's 434 Ω output node is **why** the balun costs 1.6 dB there against 3.7 dB on the l5 point. | `--probe`-style S-parameter run + `eval_metrics`. §42.3 measured the output-stage drain and VOUT1 as the **only two match-legal nodes** in the whole circuit, where loading even *improves* S11 (−10.01 → −10.36) — so this is the lowest-S11-risk row in the table. Kill: S21 at four f0, or K_min < 1. | **Device/inductor budget** (1 spare device; an L-match costs at least one). **K_min** (a resonant output raises gain and can raise peaking; the stage-33 guard refuses K crossings in polish/descent but not in ZOAF). **D7**: changes the balun's graft-node impedance, so §41.4's imbalance must be re-measured, not inherited. |
| **D** | **Current reuse / gm-boosting** — stack stages so one current makes two transconductances, freeing mA for the output stage | Indirect but real: it is candidate **B**'s funding source. Buys back the gain that B spends, and does it without new current. | `op` + `eval_metrics`: every MOS still conducting (`extract.mos_region`), all `Vds > Vdsat`, S21/NF/Idd. Kill: any device off or in triode, or S11 moved off band-wide legality. | **Voltage headroom** — stacking on a 1.2 V rail is exactly what the corpus has least of at the input (three devices already sit in **sub**-threshold, gm/Id 16.2). **NF** (input stage), **S11** (input-node impedance is the knife-edge, §41.6 item 1), **device budget**. |
| **E** | **Bias re-centering exploiting the 1.2 V rail** | §2.2 predicts **~1 dB**: the drain sits at 0.578 V with 505 mV of voltage headroom against a 73 mV current-limited swing. It is an **enabler for B and C**, not a standalone answer — and if §2.2 is wrong, this row is where that shows up first. | `op` dump only (≈0.06 s/run, the §34 harvest rate): `Vq`, `Vdsat`, `Iq`, per device, at 1.1 and 1.2 V. Kill: nothing to kill — it is cheap enough to always run, and its **result** is the test of §2.2. | Low. Moves the operating point of every stage, so S21/NF/Idd re-measure; `pVB ∈ [0.2, 0.9]` and the inserted bias resistors are all in-box. |
| **F** | **Output-stage cascode / headroom re-stack** | **Registered as expected-to-fail, and killed on evidence rather than argument.** A cascode spends Vds headroom — the resource §2.2 says is 17 dB *non*-binding — to buy output impedance and cut C_gd feedback. Its real value here may be elsewhere: §42.3 blames the CS pair's C_gd for the match-forbidden zone (94.5 / 93.2 µm on the l5 host; 66.2 / 45.7 µm here), so cascoding **MNM2/MNM5** could buy S11 margin that candidate **A** then spends. | `eval_metrics` + `op`: does the cascoded device still clear `Vds > 1.5·Vdsat`, and does S21 hold? Kill: any device out of saturation, S21 below clause-4 floors. | **Device budget: costs the single spare device.** S21 (a cascode on a 1.2 V rail in weak inversion), K_min, and — if applied to the input pair — S11, which is the point of doing it. |
| **G** | **Derivative superposition / auxiliary-path (post-distortion) linearization** | Cancels the **g3** of a transconductor with an auxiliary device biased in the opposite-sign-g3 region. It attacks *distortion generation*; §2.2 says the binding limit is *current clipping*, which cancellation cannot fix. Legitimate only if applied to the output stage **and** only if rung 0 shows the distortion is g3-dominated (IM3 slope exactly 3 well below any compression) rather than clipping-dominated. | The IM3 **slope** already reported by both harnesses is the discriminator (2.991–2.997 measured today, i.e. clean cubic at the drive levels used). Then `op` on the auxiliary device (region + gm/Id). Kill: costs the spare device and cannot be built in-box; or the notch is not band-wide over 1.1–2.5 GHz. | **Device budget** (the one spare), **Idd**, **NF** (an auxiliary path in front adds noise), and above all **sensitivity**: cancellation notches are bias- and process-sharp, and this program's own designs flip gates at **±1 % of VDD or passives** (§39.1). §6's zero-flip rule is aimed squarely at this row. |
| **H** | **Degeneration on the output stage** | Series feedback trades gain for transconductor linearity ~dB-for-dB. Same objection as G under a current-clipping limit, and it *reduces* the drive available at the output device. Registered because it is cheap and because it composes with B (more current can afford more degeneration). | `eval_metrics`: S21 at four f0 (clause 4 floors), NF, Idd. Kill: S21 margin gone. | S21 (clause 4), NF, and the D6 span (degeneration reduces max-gain state gain, shrinking the span from the top). |
| **N** | **The null: the wall is physical at ≤1.2 V and D5 must be re-negotiated** | A legitimate outcome, not a failure. §37.7's own argument shape (OIP3 vs P_dc) is the template; §2.3 restates it at the min-gain state where the requirement is ~1× P_dc rather than 22–50×. | — (this is a conclusion, not a candidate) | — |

**Candidate N's evidence bar, pre-stated so it cannot be reached by fatigue.**
N may be recorded only when **all five** hold:

1. the designated point's **baseline IIP3/OIP3 is measured** at 1.2 V on both
   harnesses, at max gain **and** at the D6 min-gain state (rung 0);
2. the §2.2 current-limit diagnosis is **confirmed or replaced** by a measured
   OIP3-vs-`Iq(MNM6)` curve of at least 4 points, replay-fenced;
3. candidate **A** has been re-screened on this host at 1.2 V and its
   match-legal span **measured**, not inherited from §42.4's l5 numbers;
4. the **best candidate from each of B, C, D** has been carried to a real
   two-tone verification, with its residual shortfall in dB reported per band;
5. a power-budget argument in §37.7's form is written with the *min-gain*
   numbers of §2.3 (required OIP3 ≈ 1× P_dc), stating what would have to
   change — supply, Idd gate, port impedance, or the spec — for it to close.

Anything less is "WP-LIN did not find it", which is a different sentence and
must be written as that one.

---

## 4. The fidelity ladder, with budgets

`15-ENGINEER-PROPOSAL.md` §3 point 6: exploit the ladder for *training*, not
just gating. Per-run costs are quoted where the corpus has them and marked
otherwise; **the executor calibrates each rung on its first five runs, records
the measured rate in FINDINGS §43, and stops at the cap** (the §34 harvest
precedent: pre-registered 1,400 runs / 1 h, actual 1,335 / 642 s).

### 4.0 Rung 0 — the baseline that does not exist yet (blocking; nothing may be proposed before it lands)

1. `check_iip3.py` and `check_hb.py` **GREEN first** — no design number is read
   before both goldens print GREEN (house law, §37.1 / §40.1).
2. **Emit `dhruva-simul.sp`** from `dhruva-simul.params.json` + `tokens.json`
   via `size.prepared_body` (the `recreate.py` emission path), at
   pVDD = 1.1 **and** 1.2 V. This closes §1.3 item 2.
3. **Harness overrides, by module attribute from a sidecar, never by editing
   the shared file:** `iip3.py` has no `--vdd` flag and its `S21_REF_DB`
   gain cross-check is hard-coded to the **l5** sizing's audited S21
   (35.96 / 35.93 / 35.54 / 33.73). Measuring `simul` will trip that check
   unless the reference is re-pointed at §36.3's audited S21 for this point.
   **The cross-check is not disabled — it is re-pointed**, because it is the
   check that caught §37.4's deck mix-up.
4. Measure, replay-fenced ≥3×: IIP3/OIP3 at 1.1 and 1.2 V, four bands, at
   **max gain** and at the **D6 min-gain state** (out-bank S3), on both
   harnesses. Cost: 4 bands × 6 drives = 24 transient runs per configuration
   (≈ "minutes" each, `15-ENGINEER-PROPOSAL.md` §6) + the HB equivalent at 8
   drives. **Cap: 90 SPICE-minutes per configuration, 4 configurations.**
5. Re-derive the §2.1 op table and run the §2.2 four-point falsification test
   (4 `op` runs, ≈ 0.3 s each including bias insert).
6. **Deliverable of rung 0, independent of everything downstream:** the first
   measured IIP3 of the designated point, and a verdict on §2.2. Even if
   WP-LIN stops here, this closes §1.3 items 1–3.

### 4.1 Rung 1 — cheap OP/AC screen (~1 s per evaluation)

`size.eval_metrics(nf_gated=True)` + one `op`, giving S11 band-wide, S21 at the
four f0, NF, Idd, K_min, and the swing proxies (`Iq(MNM6)`, `|Z_ac|`,
`Vq − Vdsat`, per-device region and gm/Id). **This rung never produces an IIP3
number** — it produces the tier-1 kill decisions of §3's screen column.

* Kill rule, pre-stated: any candidate that breaks a tier-1/tier-2 gate **at
  nominal 1.2 V** is dropped without further spend; any candidate whose
  `Iq × |Z_ac|` product does not improve on the baseline is dropped unless it
  is a candidate-A/A' row (which does not act through that product).
* **Cap: 2,000 evaluations ≈ 35 SPICE-minutes.** Rows are logged with
  `provenance.source_arm = "wplin-screen"`.

### 4.2 Rung 2 — the IIP3-head surrogate, **PROPOSE-ONLY** (no SPICE)

Ranks the rung-1 survivors so that rung 3's expensive budget is spent on the
most promising ~12. §5 is its data plan. **Its numbers are never quoted in an
acceptance claim, never in FINDINGS §43's verdict tables, and never in a gate
row** — only in a "what the surrogate proposed and what it got wrong" section.

### 4.3 Rung 3 — real two-tone verification (the only rung that can support a claim)

`lna/iip3.py`-equivalent two-tone transient at the **D6 min-gain state**,
1.2 V, four bands, 6 drive levels, with the full fence set of §37.3 (measured
floor, ≥10 dB SNR, ≤0.5 dB compression, 3:1 slope, per-point spread).
Anything that **claims a pass** is additionally re-measured in VACASK HB — the
0.08 dB cross-method agreement (§37.6) is the program's licence to treat the
number as a property of the design rather than of a tool.

* **Cap: 12 candidates × 4 bands = 48 band-sweeps.** At the corpus's "minutes"
  per point this is **[TBD at execution — calibrate on rung 0 and record];
  hard cap 8 wall-clock hours, overrun means stop and report what landed.**

### 4.4 Rung 4 — the stage-34 sensitivity sweep, **inside** the acceptance rule

`15-ENGINEER-PROPOSAL.md` §1.3: the PVT lesson is that train-nominal ⇒
diverge-at-deployment, so the sweep belongs in acceptance from day one, not as
a post-hoc audit. Survivors of rung 3 only.

* The full `corners.py` axis set at the **1.2 V nominal** on the tier-1 +
  tier-2 gates: temp −40…85 °C, VDD ±10 %, passives ±10 %, Q 8…20, worst
  two-axis combo. Bar: **zero gate flips on every axis**, matching the
  designated point's own pre-designation result (§14 §2.1 ruling 1).
* **New, and pre-registered here because it has never been done (§1.3
  item 5): IIP3 itself is re-measured under the reduced perturbation set** —
  VDD ×0.9 and ×1.1, 85 °C, and the worst combo — because a linearity
  mechanism that only works at nominal is not a mechanism. Bar: the D5 pass
  survives all four, or the candidate is reported as nominal-only.
  **Cap: 4 perturbations × 4 bands = 16 band-sweeps per survivor, ≤ 2
  survivors.**

---

## 5. The IIP3-head surrogate — what data exists, what must be built, and the rule it lives under

`15-ENGINEER-PROPOSAL.md` §1.2: pretrain on cheap OP/AC screens, fine-tune on
the existing two-tone rows plus a small designed sweep, 5-seed ensemble like
critic v1, **propose-only**.

### 5.1 The two-tone rows that exist today — counted, not estimated (2026-08-14)

| artefact | swept rows | distinct IIP3 numbers | what they cover |
|---|---|---|---|
| `lna/out/_iip3_d4sim.json` | 24 (4 bands × 6 drives) | 4 | l5 sizing, max gain, 1.1 V |
| `lna/out/_iip3_own_sizing.json` | 24 | 4 | 4 own-band sizings, max gain, 1.1 V |
| `lna/hb/hb_iip3_d4sim.json` | 32 (4 bands × 8 drives) | 4 | same design as row 1, HB |
| `lna/hb/hb_iip3_ownsizing.json` | 32 | 4 | same designs as row 2, HB |
| **total** | **112 swept rows** | **16 (8 of them cross-method duplicates)** | **4 parameter sets of 1 topology** |

**Stated plainly, because it decides the design of this rung: the entire IIP3
label supply is 16 numbers over 4 parameter sets of one topology, all at
pVDD = 1.1 V, all at max gain, none on the designated point, none at 1.2 V,
none at any D6 state, none on any candidate mechanism.** A 5-seed ensemble
regressor trained on that is a memoriser. Any "the surrogate learned IIP3"
claim made on this supply is void, and this paragraph is here so that claim
cannot be made later.

### 5.2 The designed sweep that fills the gap

Pre-registered shape (values fixed here, not tuned to results):

* **Factors, all swing-directed** (§2.2): `Iq(MNM6)` via `pNM6W` and `pR4V`
  (4 levels spanning the box), `|Z_ac|` via the output coupling (3 levels),
  bias re-centering via `pVB`/the inserted bias network (2 levels), pVDD
  {1.1, 1.2} — screened to **24 designed points** by rung 1's legality filter
  (in-box, tier-1 legal at nominal).
* **Measured at one band only** — `dhruva-l5`, the worst-margin band — at **4
  drive levels**: **24 × 4 = 96 transient runs**. Other bands are measured
  only for candidates that reach rung 3. This is the single largest SPICE line
  item in the WP and it is capped at **4 wall-clock hours**.
* Plus every rung-3 verification row, appended as it lands (they are the same
  rows: N1's sims are N2's rows, `15-ENGINEER-PROPOSAL.md` §4.1-N2).

### 5.3 Model, target, split, and the non-regression rule

* **Pretrain** on the cheap OP/AC screen rows (rung 1, plus this WP's own
  `op` harvest) to predict the tier-1/tier-2 margin vector — the existing
  `surrogate.py` target shape. ⚠ The 66,664 stored `sim_points` rows **predate
  three harness cutovers** (`15-ENGINEER-PROPOSAL.md` §5.1) and are **not**
  pooled in; era discipline is Block 6 law.
* **Fine-tune** an IIP3 head on §5.1 + §5.2. **Target is the normalised D5
  margin, not raw dBm** (`15-ENGINEER-PROPOSAL.md` §1.2 pattern 2: bounded,
  well-conditioned regression targets).
* **5-seed deep ensemble**, ranking by `mean − β·std`, the critic-v1 recipe.
* **Split: by mechanism family and by parameter-set family, never by row.**
  §13-WP-DIAGHEADS §3 measured that a row split leaks in this store (median
  nearest-neighbour similarity 1.000 inside an arm).
* **Non-regression, on the §34 precedent:** if adding the IIP3 head degrades
  the surrogate's existing margin predictions, the IIP3 head **ships as a
  separate model** and FINDINGS §43 says so. Stage 29's lesson — pointing cost
  the critic its ranking, and the pre-registered consequence was executed
  rather than argued away — applies verbatim.
* **Reported honestly whichever way it falls:** held-out IIP3 error in dB, and
  the count of rung-3 verifications where the surrogate's proposal ranking was
  wrong. A surrogate that saves no SPICE-minutes is a result, not a
  non-result.

### 5.4 The rule, stated once and without exception

> **No surrogate number appears in any acceptance claim, gate row, FINDINGS
> verdict table, or JOURNEY result sentence. Every acceptance is
> real-two-tone verified, and every claimed D5 PASS is additionally
> cross-checked in harmonic balance.**

---

## 6. Acceptance rules, pre-stated

A candidate is **accepted** only if every clause below holds simultaneously,
on **one netlist and one set of device sizes**, at **pVDD = 1.2 V nominal**.

**6.1 D5, at the D6 min-gain state** — measured two-tone, per band:

| band | f0 (MHz) | IIP3 gate at the min-gain state |
|---|---|---|
| dhruva-l5 | 1176.45 | **≥ −7.4 dBm** |
| dhruva-l2 | 1227.60 | **≥ −7.4 dBm** |
| dhruva-l1 | 1575.42 | **≥ −7.6 dBm** |
| dhruva-s  | 2492.03 | **≥ −8.7 dBm** |

with the §37.3 fence set intact on every row: IM3 slope in 3 ± 0.3, ≥10 dB
IM3-over-measured-floor, ≤0.5 dB gain compression on kept points, per-point
IIP3 spread reported, and the transient harness's small-signal gain
reproducing the audited `sp` S21 to ≤ 0.5 dB (the §37.4 cross-check, re-pointed
per §4.0 item 3, **never disabled**).

**6.2 D6 still met, under the §42.1 mapping as approved** — ≥4 states / ≥3
steps, gain monotonic in state index at every band f0, **span ≥ 10.6 dB at
every band f0**, S11 ≤ −10 dB band-wide **and** Idd ≤ 13 mA in **every** state,
max-gain state passing the full D4-SIM set, NF gated at the max-gain state only.

**6.3 D4-SIM preserved at the max-gain state** — S21 ≥ 30 / 25.4 / 22.3 /
22.3 dB at S/L1/L2/L5 f0; NF ≤ 3.5 / 2.7 / 2.5 / 2.5 dB; S11 ≤ −10 dB
band-wide over 1.1–2.5 GHz; **Idd ≤ 13 mA at 1.2 V**; **K_min ≥ 1** in-band
(reported wide 0.1–20 GHz as well, as §36.2 does).

**6.4 D7 imbalance preserved on the host** — the §41 `cscg` active balun
re-grafted and re-measured (not inherited): imbalance **≤ 0.22 dB and ≤ 0.9°**
band-wide over 1.1–2.5 GHz, gain gated on **mixed-mode Sds21** per §2.1
ruling 3, with the balun's own current **inside the same 13 mA budget** as the
core and the switch bank. Reference: 0.119 dB / 0.329° and 1.045 mA on the
current host at 1.1 V.

**6.5 Sensitivity — zero flips, at the 1.2 V nominal.** The full `corners.py`
axis set on the tier-1 + tier-2 gates: **no gate flips on any axis**, matching
the designated point's own pre-designation standard. Plus the reduced IIP3
perturbation set of §4.4.

**6.6 In-box and in-budget** — every sizable parameter inside `kind_ranges`
(checked post-hoc as well as clamped), ≤ **21 devices**, ≤ **6 inductors**,
`l_fixed = 45 nm`.

**6.7 Replay fence before any claim** — ≥3 repeats in-process **and** at least
one from a separate process, **spread 0.0000 on every gated metric**, on the
emitted params file read fresh from disk (§36.4 / §41.4 / §42.5 precedent).
⚠ And §42.2's warning applies to every insertion this WP makes: `prepared_body`
node names are **not stable across processes** — any element inserted by
literal node name attaches to a random node and its numbers are void. Resolve
roles from element lines and cross-check each role against a second element
that must touch it.

**6.8 Goldens first** — `check_iip3.py`, `check_hb.py`, `check_diff.py` GREEN,
and the regression quartet green before and after, recorded in FINDINGS §43.

---

## 7. User-decision points — the executor must NOT decide these

| # | decision | why it is not the executor's | default if unruled |
|---|---|---|---|
| **D-1** | **Any D5 spec re-negotiation** — including adopting candidate **N**, re-reading "IIP3 at the min-gain setting", or accepting a partial pass (e.g. 3/4 bands) | Spec text is blind-protocol content and the gate ladder is the user's | Report the measured shortfall per band; claim nothing |
| **D-2** | **`device_budget` widening past [3, 21]**, `max_inductors` past 6, or any `kind_ranges` box widening | §23's precedent: budgets are widened against a **corpus circuit that justifies the number**, never to close a gate; 21 is where that justification ran out (`ihp-gps-lna-npn`) | Work inside 1 spare device / 4 spare inductors, and report which candidates were killed by the budget |
| **D-3** | **Any frozen-protocol touch** — the ZOAF label objective, spec-L0/NDL rows, recipe/era stamps, or the `iip3_dbm: status: unsupported` field in the spec YAMLs | WP-D1-class governance change (§38.1's precedent: stability was deliberately kept **out** of plain ZOAF for exactly this reason) | Sidecars and module-attribute overrides only |
| **D-4** | **Designation change** — whether a redesigned point replaces `dhruva-simul` as the designated D4-SIM point, and what happens to the novelty claim if `wl_hash` changes | §36.5's precedent: WP-HARDEN measured a better point and explicitly did **not** adopt it | Both points on file; the WP reports, the user designates |
| **D-5** | **D6 mapping amendment** if the gain-control mechanism moves to the front end (candidate A/A') | The §42.1 mapping was ruled "approved as written" against an **output-side** build; a front-side build satisfies its letter (switches driven only by `pVSWG*` control voltages) but changes what it was ruled on | Measure and report under the mapping as written; flag the clause-by-clause reading |
| **D-6** | **The benchmark configuration**: must D5/D6/D7 hold **simultaneously on one netlist** (core + switch bank + balun), or is each gate judged on its own host? | D6 was measured without the balun, D7 without the switch bank; nothing has ever measured all three together, and their currents add | Measure the union configuration if the budget allows; report separately if not |
| **D-7** | **The output reference impedance** — §41.8 item 4 already flagged that 2×50 Ω per leg "is doing a lot of work". It is also the direct setter of `Z_ac`, i.e. of the OIP3 wall (§2.2) | A spec-reading decision with a large effect on the answer | 50 Ω, as recorded |
| **D-8** | **Whether a D5 verdict may rest on the HB harness alone** if the transient harness cannot reach the full configuration (switch bank + balun deck) | The two-harness agreement is the program's licence for the D5 number | Do not claim; report which harness reached what |
| **D-9** | **Any edit to a shared harness file** (e.g. adding `--vdd` to `iip3.py`, or changing `S21_REF_DB`) rather than overriding from a sidecar | Concurrent-agent file ownership is a standing convention | Sidecar override, recorded in FINDINGS §43 |

**Already ruled, and therefore NOT open** (recorded so it is not relitigated):
the supply envelope is **≤ 1.2 V with no deviation**; the designated point is
`dhruva-simul` gated at 1.2 V; the D6 mapping of §42.1 is approved as written;
differential gain gates on mixed-mode Sds21 (`14-DHRUVA-SIMUL.md` §2.1).

---

## 8. Predictions, registered before any candidate is run

* **P1.** The designated point's baseline OIP3 at 1.2 V comes in **below** the
  l5 point's +3.2 … +3.4 dBm — the §40.4 tension resolving against the
  hardened point, as §2.2's `Iq × |Z_ac|` ordering predicts (≈1.9×, 5.4 dB, in
  the l5 point's favour ⇒ a baseline near −3 … −2 dBm).
* **P2.** The wall is **current-limited, not voltage-limited**: the measured
  OIP3-vs-`Iq(MNM6)` curve rises ~dB-for-dB with output-stage current at fixed
  load, and bias re-centering alone (candidate E) moves OIP3 by **< 2 dB**.
* **P3.** The 21.6–25.4 dB gap decomposes as §2.3 says: ~12 dB available from
  front-end gain control **iff** the §42.3 match wall has lifted on this host,
  plus ~8–9 dB of output-stage OIP3. Neither half alone closes D5.
* **P4.** Candidate **A**'s match wall **has** lifted materially on this host —
  the §42.3 probe re-run at 1.484 dB of S11 margin finds at least one
  front-side node with ≥ 10.6 dB of match-legal span. *(This is the
  highest-value and least-certain prediction in the list; §42.4 measured the
  input combiner failing on off-capacitance alone, which is a mechanism that
  does not care how much margin the host has.)*
* **P5.** Candidates **F** (output cascode), **G** (derivative superposition)
  and **H** (output degeneration) are killed at rung 1 or rung 3 — F on
  headroom/device budget, G on the sensitivity clause (§4.4), H on the S21
  clause-4 floor.
* **P6 — the way this most plausibly fails.** Candidate **B** works exactly as
  predicted in isolation and is then **eaten by the Idd gate**: the output
  stage needs several mA more, the balun costs 1.045 mA, the switch bank costs
  its own, and 13 mA at 1.2 V does not hold all three. The check is D-6's
  union configuration measured, not assumed.
* **P7 — the second way it fails.** Everything lands and the sensitivity sweep
  (§4.4) flips a gate at ±1 % of VDD or passives, exactly as §39.1 measured on
  the pre-hardened point. A nominal-only pass is reported as nominal-only.

---

## 9. Method discipline

* Append-only store; recipe stamps (`wplin-v1`; `source_arm = "wplin-screen"`
  for rung 1, `"wplin-verify"` for rung 3); **no era pooling** — the
  pre-cutover `sim_points` rows are not training data here (§5.3).
* Blind protocol observed: the paper's numbers in §6.1 are the complete allowed
  excerpt; no circuit content from the source is consulted, and every candidate
  mechanism in §3 is textbook-generic and authored here, in the
  `templates.py`/`_diff_balun.py` provenance class (§41.2).
* Goldens before design numbers, always (§6.8).
* Verbatim simulator evidence is preserved in the artefacts, never only
  summaries (`15-ENGINEER-PROPOSAL.md` §2.2 item 2 — the measured
  context-attrition finding).
* The op hook stays **on** for every run in this WP, so `op_points.jsonl` fills
  as a side effect (`15-ENGINEER-PROPOSAL.md` §5.2).
* A `diagnosis` field is stamped on this WP's rows with the controlled value
  for the named wall (`15-ENGINEER-PROPOSAL.md` §5.4) — this WP is the first
  producer of failure-signature-keyed rows.
* Concurrent-agent convention: shared data files may carry other agents'
  uncommitted rows; a commit that includes them says so.
* Every departure from this document is **recorded in FINDINGS §43 as a
  departure**, never smoothed (§34's precedent: 18 of 20 registered sizings ran,
  and the shortfall was published).

---

## 10. Execution order and repro

```bash
# 0. goldens first -- no design number before these are GREEN
python lna/ref/check_iip3.py
python lna/ref/check_hb.py
python lna/ref/check_diff.py

# 1. rung 0 -- emit the missing deck, then the baseline that has never existed
#    (sidecar; dhruva-simul.sp is NOT on disk today)
python lna/_lin_baseline.py --emit-deck --vdd 1.1,1.2
python lna/_lin_baseline.py --iip3 --state max,min --vdd 1.2 --replay 3
python lna/_lin_baseline.py --op --vdd 1.1,1.2          # re-derive the SS2.1 table

# 2. has the match wall lifted on THIS host?  (candidate A, tier-1 only)
python lna/pgain.py --probe --sizing simul              # read-only re-run
python lna/pgain.py --wall  --sizing simul

# 3. rungs 1-4
python lna/_lin_screen.py   --cap 2000                  # OP/AC screen
python lna/_lin_surrogate.py --propose --top 12         # PROPOSE-ONLY
python lna/_lin_verify.py   --two-tone --state min --vdd 1.2
python lna/corners.py --axis all --point <survivor> --vdd-nominal 1.2
python lna/_lin_verify.py   --sens-iip3 --survivors 2
```

---

## 11. Outcome (appended after execution)

*Empty by design. This document is a pre-registration; it is not a promise, and
the table below is filled in after the fact — whichever way each prediction
falls — with full detail in FINDINGS §43.*

| pre-registered claim | verdict |
|---|---|
| **P1** designated point's baseline OIP3 below the l5 point's | **CONFIRMED (rung 0), two-harness.** OIP3 −1.4…−2.5 dBm; **5.1–5.8 dB below** the l5 point's +3.2…+3.4 at 1.1 V like-for-like (FINDINGS §44.5). Cross-checked in VACASK HB (§44.9): OIP3 −1.3…−2.3 at max gain, agreeing with transient to 0.07–0.20 dB (0.08 dB at the ruled 1.2 V). |
| **P2** current-limited, not voltage-limited | **CONFIRMED (rung 0), three ways.** Current limit binds by 6.93×=16.8 dB over headroom; +100 mV rail moves OIP3 +0.61 dB (<2 dB bar); OIP3 orders with Iq·\|Z_ac\| at Spearman ρ=1.0000 (FINDINGS §44.4). |
| **P3** the ~12 dB + ~8–9 dB decomposition | **REFUTED on both halves (rungs 1–3, FINDINGS §45).** The ~12 dB front-end half is structurally unavailable (P4 refuted — best front-side match-legal span 4.8 dB vs 10.6 needed); the ~8–9 dB output half is in-box unavailable (best measured gain **+0.72 dB** of OIP3, S11-capped at NM6×2, HB-confirmed to 0.007 dB). Neither half lands; with output-side D6 the honest requirement reverts to OIP3 ≈ 33–55× P_dc (§45.5). |
| **P4** the §42.3 match wall has lifted on this host | **REFUTED (rung 1, §45.1), both rails measured.** in-att 4.77/4.84 dB legal span (l5 was 0.00 — a real shift, under half of 10.6); in-degen 2.26/2.37 (the authority ceiling, unmoved); n0-bank 0.00 (no legal setting at all). The forbidden zone is architecture (C_gd coupling), not margin. |
| **P5** F / G / H killed early | **CONFIRMED (rung 1, §45.2)** — F on headroom-is-non-binding (§44.4) + the device budget; G on clipping-not-g3 (§44.4) + the §6.5 zero-flip bar; H on the S-band S21 clause-4 floor. All killed on evidence, none sized. |
| **P6** candidate B eaten by the Idd gate | **REFUTED in mechanism (rungs 1/3, §45.2).** B is stopped by **S11**, not Idd: the wider MNM6 spends the match margin (breaks −10 dB at NM6×3) while Idd peaks at 9.65 of 13 mA. The predicted failure mode was the wrong one; the D-6 union config was never reached (no candidate approached acceptance). |
| **P7** a nominal-only pass under the sensitivity sweep | **NOT REACHED (rung 4 vacuous, §45.5)** — zero rung-3 survivors; no nominal pass exists to flip. §1.3 item 5 (IIP3 under perturbation) remains open, queued. |
| **Gate D5 at the D6 min-gain state, 1.2 V** | **FAILED 0/4 bands (rung 0), 26.6–27.7 dB short — TWO-harness measured.** IIP3 ≈ −34 dBm vs ≥ −7.4/−7.6/−8.7; OIP3 −13.0…−13.3 at S3/1.2 V (FINDINGS §44.2). **HB agrees, 0/4 fail at every configuration (§44.9); all four configs reached, so §7 D-8's asterisk is RESOLVED** — the D5 baseline is two-harness measured, not one. **Rungs 1–3 (§45.4): FAILED 0/4 on every candidate as well, 25.8–28.6 dB short — no in-box candidate approaches any §6 clause.** |

**Rung-0 outcome note (2026-08-14, Session 10, executed on `main` per the RHEL
port — FINDINGS §44).** Rung 0 — and only rung 0, per user sign-off — ran. It
closed §1.3 items 1–3: `dhruva-simul.sp` emitted at both rails + the D6 S3
variant; the point's first-ever IIP3/OIP3 measured, replay-fenced (0.0000 dB
in-process and separate-process), at max gain and the D6 min-gain state, both
rails; the §2.1 op table re-derived (reproduces every digit); the §2.2 four-
point falsification test run. **P1 and P2 both confirmed; D5 FAILS 0/4 at the
ruled condition.** The transient numbers were first reported under D-8 (VACASK HB
was blocked on this box — Windows path in `check_hb.py`, `VACASK_HOME` unset).
**VACASK was then built for RHEL the same day, `check_hb` went GREEN, and all four
configurations were re-measured in harmonic balance (FINDINGS §44.9): HB FAILS D5
0/4 at every configuration, agreeing with the transient half to 0.08 dB at the
ruled 1.2 V nominal. All four configs were reached, so D-8's asterisk is
resolved — the D5 baseline is two-harness measured.** No candidate mechanism,
screen, or surrogate was run (rungs 1–4 remain). Candidate N is **not** recorded (its bar is 2-of-5 met;
recording it is a §7 D-1 user decision). No spec was re-negotiated, no budget
widened, no frozen-protocol content or D5 row touched. Deviations recorded in
FINDINGS §44.7.

**Rungs 1–4 outcome note (2026-08-15, Session 10 — FINDINGS §45).** Executed
per user sign-off (2026-08-15), preceded by the user-authorized step-0 R-e
correction of `14-DHRUVA-SIMUL.md` §1.2's tier-3 mis-attribution (separate
commit, original preserved in a dated note). Goldens GREEN before and after.
**Rung 1:** the candidate-A probe re-measured the match wall on this host at
both rails — **P4 refuted** (best front-side legal span 4.8 dB; the §42.4
authority ceiling reproduced at 2.3 dB; recombine still 0.0) — and the OP/AC
screen killed C (pR4V is the output stage's current source: raising it
*lowers* Iq·|Z_ac|), E (pVB inert to 5 digits), D (in-box impossible, §7 D-2),
F/G/H (pre-stated cheap evidence; **P5 confirmed**), leaving 4 candidate-B
survivors, S11-capped at NM6×2 (+1.1 dB of swing product; Idd never binds —
**P6 refuted in mechanism**). **Rung 2:** the surrogate was NOT trained — the
§5.1 memoriser rule was invoked as pre-registered; the designed sweep's live
axis measured **+0.72 dB of OIP3** for the best survivor (HB cross-check:
+0.65; absolute agreement 0.007 dB). **Rung 3:** 4 candidates × 4 bands real
two-tone at the ruled condition, all fences intact, replay 0.0000 — **FAILED
0/4 everywhere, 25.8–28.6 dB short**; no pass claimed, so no HB re-measure
owed. **Rung 4:** zero survivors, vacuous; **P7 not reached**; §1.3 item 5
stays open. **P3 refuted on both halves** — and with it, §2.3's ~1× P_dc
reframing collapses back to §37.7's 33–55× P_dc at the ruled condition
(§45.5). Candidate N's bar: **4½ of 5** (clause 4's D-leg is in-box
impossible — a D-2 budget question); N is queued, **NOT recorded** (§7 D-1).
The user decisions this outcome puts on the table: D-1 (the D5 row /
candidate N), D-2 (an isolating input architecture needs the budget), D-7
(the output reference impedance directly sets the wall). Deviations in
FINDINGS §45.6; cost 67 SPICE-min vs caps in §45.7.

**D-2 test-widening outcome note (2026-08-15, Session 10 — FINDINGS §46,
pre-registered in `plans2/17-WP-LIN-D2.md`).** The user ruled one bounded,
test-scoped widening (+3 devices, the spec's `device_budget: [3, 21]` line
untouched) to carry candidate D and an isolating input architecture to real
two-tone, so candidate N is judged on a full 5/5 or refuted. **Both were
built and measured; neither approaches any §6 clause.** Candidate D
(MNMD1 stacked under MNM6): the reuse stack never improves the swing product
(best saturated 54.97 mV vs baseline 72.91; triode asymptote 72.56) — the
output current is resistor-set, so the stack adds gm and no current — and at
the ruled condition it **FAILS D5 0/4 at −20.7…−22.1 dB** (fences intact,
replay 0.0000; its one real effect is +5.5…+6.1 dB of S3 IIP3 via accidental
source degeneration of MNM6). The isolating input (MNMI1 cascode + MNMI2
attenuation): **0.00 dB of match-legal span** — the match breaks by 2.9 dB
through the cascode the moment the attenuator conducts; §45.5(i)'s escape is
measured shut at +2 devices. **Candidate N's bar: 5 of 5 — REPORTED as fully
met, NOT recorded (§7 D-1).** The D-2 spec-adoption question is moot (nothing
passed; the test allowance dissolves). Deviations in FINDINGS §46.7; cost
≈55 SPICE-min vs caps in §46.8.

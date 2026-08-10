# WP-DHRUVA — the program's best solution to the blind paper-target spec

**Status:** fresh re-verification, packaged 2026-08-10. Solution:
`ace8383c2fa68d03`. Source record: `lna/FINDINGS.md` §25 and §27, `lna/JOURNEY.md`
stages 22–23, `lna/plans2/08-DHRUVA-GOAL.md` (the blind-protocol spec ladder).

This document re-derives and re-measures the numbers rather than quoting them.
Every table in §4 was produced by re-running the netlist from this package's
own `tokens.json` + `dhruva-<band>.params.json` through the current harness,
today, not copied from the label store or from FINDINGS.md. See §7 for exact
commands.

---

## 1. What the target is

**Source (blind protocol):** Kanchetla et al., "A Compact, Reconfigurable
CMOS RF Receiver for NavIC/GPS/Galileo/BeiDou," IEEE TMTT 70(7), July 2022 —
65 nm CMOS, measured silicon. The paper's circuit was never shown to this
program; the numbers below are the *complete* allowed excerpt
(`lna/plans2/08-DHRUVA-GOAL.md`, blind-protocol rule 1). One device, four
selectable bands.

| parameter | L5 (1176.45 MHz) | L2 (1227.6 MHz) | L1 (1575.42 MHz) | S (2492.03 MHz) |
|---|---|---|---|---|
| gain at f0 | ≥ 22.3 dB | ≥ 22.3 dB | ≥ 25.4 dB | ≥ 30 dB |
| NF at f0 | ≤ 2.5 dB | ≤ 2.5 dB | ≤ 2.7 dB | ≤ 3.5 dB |
| IIP3 (min-gain) | ≥ −7.4 dBm | ≥ −7.4 dBm | ≥ −7.6 dBm | ≥ −8.7 dBm |

Common to all bands: **S11 ≤ −10 dB across the whole 1.1–2.5 GHz
reconfiguration range** (not just at f0), **Idd ≤ 13 mA** @ 1.2 V, **≥ 10.6 dB
gain-programmability range** (≥ 3 steps), **differential output** (single-ended
RF in) with imbalance ≤ 0.22 dB / ≤ 0.9°.

**Tier ladder** (`08-DHRUVA-GOAL.md` §2):

- **Tier 1** (gateable): S11-over-band, S21 @ f0, Idd.
- **Tier 2** (gateable since the NF harness landed): NF @ f0, series-Rs
  method.
- **Tier 3** (out of the current harness, unmeasured): IIP3 (needs
  two-tone/HB), output balance (needs a 3-port differential harness), gain
  programmability (a switch/DOF question, out of scope for topology search).

**Mapping decision carried from the plan:** the paper reports voltage gain
into an on-chip load; this harness gates S21 into a 50 Ω port. The table's
numbers are adopted as S21 thresholds as-is (`08-DHRUVA-GOAL.md` §1).

---

## 2. The solution

### 2.1 Topology, at device level

**20 devices, 2 inductors** (`wl_hash ace8383c2fa68d03`), by type:

| kind | count | role in this netlist |
|---|---|---|
| NMOS (single transistor, no cascodes) | 6 | one common-gate input device + five common-source stages |
| capacitor | 8 | AC-coupling between every stage boundary (no DC path through the signal chain) |
| resistor | 4 | drain-load / bias-distribution resistors to VDD |
| inductor (Q = 12 model) | 2 | source-node shunt element at the input; tuned drain load for the second gain stage |

All six transistors are `L = 45 nm`, single-device (no stacking — no FET's
source or drain ties to another FET's terminal), so there is no cascode
anywhere in this design. Traced from this package's own netlist
(`dhruva-s.sp`), the signal path is:

1. **Input node** (`n1`, driven from `VIN1` through a DC-blocking cap).
   `MNM1`'s **source** ties to `n1` and its **gate** is AC-grounded through a
   separate cap — i.e. `MNM1` is wired as a **common-gate** input device, and
   `LL1` (with its Q=12 loss resistor) shunts `n1` to ground, which is what
   sets the input match. The *same* input node `n1` also drives two more
   transistors' **gates** directly through coupling caps — `MNM2` and `MNM5`,
   both common-source, sources grounded.
2. `MNM1`'s drain feeds a fourth device, `MNM3` (also common-source), through
   another coupling cap. `MNM2`, `MNM3`, and `MNM5` **share one drain node**
   (`n0`, loaded by a single resistor to VDD) — the point where the
   common-gate path (via `MNM3`) and the two direct common-source paths
   (`MNM2`, `MNM5`) recombine. (This 3-way parallel/recombine structure is
   why the nearest novelty-reference archetype, §2.2, is named `nccgcs*` —
   noted only as the nearest labeled neighbor, not a claim that this graph
   *is* that archetype: it is novel, absent from the reference set outright.)
3. The recombined node `n0` drives a fifth device, `MNM4` (common-source),
   whose drain is the **tuned load** — `LL2` (Q=12) resonating against the
   parasitic capacitance, biased through a resistor to VDD.
4. `MNM4`'s drain drives the sixth device, `MNM6` (common-source, resistive
   drain load), whose drain AC-couples to `VOUT1`. **This third stage is the
   `moves.stage_add` graft** (§3): one coupling cap + one NMOS + one load
   resistor, exactly the 3-device signature `moves.m_stage_add` appends.

So, in one sentence: **a 3-way input combiner (1 common-gate + 2 direct
common-source replicas, recombined with a common-gate-driven common-source
device) feeding two more cascaded common-source gain stages**, all
single-device (no cascodes), inductively matched at the input and inductively
tuned at one internal node.

### 2.2 How it was found — lineage and attribution

This is **search plus sizing, not generation, and not a hand-authored
archetype** — stated precisely because the D1-era package in this same
directory (`lna/repro/dhruva-l1-rfbcs3.*`) *was* hand-authored, and the
honesty precedent in this program is to say which is which every time
(FINDINGS §25.5/§27.4, JOURNEY stage 22).

```
nccgcs_s1_R (blind-v1 archetype, nearest labeled neighbor — not this graph)
   |  evolutionary / 1-edit graph moves (moves.py): load_swap -> stage_add
   v
6f0d080f91dfc642  (17 devices — quiet input stage, gain-starved: S21 21.3 dB)
   |  moves.stage_add  (append one AC-coupled common-source stage: +1 cap,
   |                     +1 NMOS, +1 load resistor -- 17 -> 20 devices)
   v
ace8383c2fa68d03  (20 devices, 2 inductors)
   |  per-band device sizing, `size.constrained_descent`
   |  (NF-targeted descent inside a hard S11/Idd trust region), recipe
   |  chain nf-v3+d21 (original dhruva-s discovery, single-finger MOS) ->
   |  mf2 relabel (multi-finger MOS cutover, w_finger=2um, full metric
   |  re-measurement, same params) -> mf2-v1 (further per-band NF descent
   |  under the honest harness -- this is where each band's shipped point
   |  comes from; see the per-band .meta.json for the exact seed/parent)
   v
four per-band parameter sets, one topology  (this package)
```

The **generator's role, stated at its measured limit**: the P5 neural
generator was tested against this exact wall (FINDINGS §26.5/§27.6) and did
**not** find a working `dhruva-l5` input stage — its best candidates were
outstanding on noise (NF 0.96–1.02 dB) but stalled at S11 −1 to −4.5 dB, i.e.
**match-limited, not noise-limited**. `moves.py`'s evolutionary search is what
closed the gate, not the generator; this design's lineage above is entirely
search + sizing. `iip3_dbm` is `unsupported` on all four specs (tier-3), and
stability below is frequency-domain / ideal-element only — no process
corners, no load pull, no package or layout parasitics. Both qualify the
engineering claim, not the tier-1/tier-2 gates as written.

**Novelty** (re-checked fresh for this package, `novelty.reference()` against
`ref-v3`, 198 hashes): `wl_hash` **absent** from the reference set; nearest
labeled circuit `arch:nccgcs_s1_R` at WL-feature similarity **0.8065**.

---

## 3. Fresh re-verification — per band, vs the §27.4 claim

Re-run today from this package's own artifacts (§7 has the exact commands),
**not** from the label store. Full evidence ladder per band: 5× replay
(label-noise check), 30/30 sized parameters in-box, `spec.feasible()`
re-measured (not trusted), wide-band (0.1–20 GHz) stability sweep, novelty
check.

| band | target NF @ S21 | S11_max (dB) | S21@f0 (dB) | Idd (mA) | **NF (dB)** | NF margin | verdict |
|---|---|---|---|---|---|---|---|
| dhruva-s  | 3.5 @ 30.0 | **−10.001** | **36.473** | 13.000 | **1.288** | +2.212 | PASS |
| dhruva-l1 | 2.7 @ 25.4 | **−10.000** | **36.824** | 12.997 | **1.220** | +1.480 | PASS |
| dhruva-l2 | 2.5 @ 22.3 | **−10.002** | **35.773** | 12.989 | **1.506** | +0.994 | PASS |
| dhruva-l5 | 2.5 @ 22.3 | **−10.001** | **35.961** | 12.963 | **1.253** | +1.247 | PASS |

**Replay:** 5/5 identical on every gated metric on all four bands, spread
`0.0000`. **In-box:** 30/30 parameters, all four bands. **Stability:**
unconditional in-band and over 0.1–20 GHz on all four bands (K/wide table
below). **Verified two independent ways:** the Python harness
(`recreate.py`) *and* the standalone `.sp` decks run directly through
`ngspice_con.exe -b`, with matching numbers to 3+ significant figures.

### 3.1 Fresh vs. FINDINGS §27.4's claimed numbers

| band | claimed S11_max | fresh | Δ | claimed S21 | fresh | Δ | claimed NF | fresh | Δ |
|---|---|---|---|---|---|---|---|---|---|
| dhruva-s | −10.001 | −10.001 | −0.0001 | 36.473 | 36.473 | −0.0002 | 1.288 | 1.288 | −0.0000 |
| dhruva-l1 | −10.000 | −10.000 | −0.0003 | 36.824 | 36.824 | −0.0003 | 1.220 | 1.220 | +0.0002 |
| dhruva-l2 | −10.002 | −10.002 | −0.0001 | 35.773 | 35.773 | −0.0003 | 1.506 | 1.506 | +0.0002 |
| dhruva-l5 | −10.001 | −10.001 | +0.0002 | 35.961 | 35.961 | +0.0000 | 1.253 | 1.253 | −0.0001 |

**No discrepancy exceeds ~5×10⁻⁴ on any gated metric, on any band** — this is
floating-point/print-precision noise (the FINDINGS table itself is printed to
3 decimals), not a measurement disagreement. **Nothing here required
investigation** under the ">σ gets investigated" rule: there is no σ to speak
of at this replay precision (5/5 runs are bit-identical to the shown
digits). The fresh numbers **confirm** §27.4 rather than correct it.

### 3.2 Stability, in-band and wide

| band | K @ f0 | K_min (in-band, 1.1–2.5 GHz) | K_min (0.1–20 GHz wide audit) | verdict |
|---|---|---|---|---|
| dhruva-s | 55.13 | 54.62 | 21.46 | unconditionally stable |
| dhruva-l1 | 86.83 | 17.27 | 9.71 | unconditionally stable |
| dhruva-l2 | 296.1 | 14.37 | 9.61 | unconditionally stable |
| dhruva-l5 | 119.2 | 19.91 | 10.26 | unconditionally stable |

`K_min > 1` and `|Δ|_max < 1` on every band, both windows — this matches the
FINDINGS §27.4 headline numbers (which report the in-band/wide pair as
`54.6/21.5`, `17.3/9.7`, `14.4/9.6`, `19.9/10.3`) to the same precision. The
wide-band margin is smallest on `dhruva-l2` (K_min 9.6×) and `dhruva-l1`
(9.7×) — still far from marginal, but worth naming since §27.5 found a
*different* four-band archetype (the Gate-D1/D2 design, not this one) that
looked unconditionally stable under the old single-finger harness and was
only *conditionally* stable once the harness was corrected. This design's
wide-band K_min was re-measured, this session, under the corrected harness
directly — it is not inherited from a pre-cutover claim.

---

## 4. "Apparent specs as per us" — everything measured beyond the gates

### 4.1 S21 over the full 1.1–2.5 GHz sweep (not just at f0)

| band | S21 @ f0 | S21_min (over 1.1–2.5 GHz) | S21_max | ripple (max−min) |
|---|---|---|---|---|
| dhruva-s  | 36.473 | 32.077 | 36.477 | 4.400 dB |
| dhruva-l1 | 36.824 | 34.706 | 37.789 | 3.083 dB |
| dhruva-l2 | 35.773 | 34.926 | 39.123 | 4.197 dB |
| dhruva-l5 | 35.961 | 33.708 | 35.982 | 2.274 dB |

The gate only requires S21 ≥ target *at* f0; every band's **worst-case gain
anywhere in the 1.1–2.5 GHz sweep still clears the loosest tier-1 target
(22.3 dB)** with room, since S21_min never drops below ~32 dB. Ripple of
2.3–4.4 dB across the full reconfiguration range is a real property of this
single fixed-value design being swept off its designed frequency — it is not
gated and not a claim of flat gain across bands.

### 4.2 Worst-case S11 per band, restated as margin

All four bands sit at essentially **zero margin** on the S11 gate:
`−10.000` to `−10.002` dB against a `≤ −10 dB` requirement. This is not a
loose pass — the input-match constraint is the **binding** one on every band
(the sizer descended NF while holding S11/Idd at the edge of their trust
region, `keep="s11idd"`, by design of `constrained_descent`). A process
corner or parasitic that moves the match by a few tenths of a dB would flip
this constraint; see §5.

### 4.3 K margins (repeated from §3.2 for the "apparent specs" view)

Every band clears `K_min ≥ 1` by at least **9.6×** even over the punishing
0.1–20 GHz wide sweep (the narrowest margin, `dhruva-l2`). In-band K margins
are far larger (14×–55×). Unconditional stability is not close on any band.

### 4.4 Per-element noise budget — `dhruva-s`, re-measured fresh

(`extract.measure_noise_budget`, the §26 harness — output-noise-power shares,
sum-closure 1.000000, cross-checked against the independent `inoise` NF:
1.2861 dB from shares vs 1.2883 dB from `inoise`, agreement ≤ 0.003 dB.)

| element | kind | % of output noise | % of excess noise factor (F−1) |
|---|---|---|---|
| `rr1` | resistor (MNM1's drain load) | 6.48% | 25.27% |
| `mnm2` | MOSFET | 6.02% | 23.51% |
| `rr2` | resistor (n0 combiner load) | 4.05% | 15.80% |
| `mnm5` | MOSFET | 3.97% | 15.50% |
| `rql1` | resistor (input inductor's Q=12 loss) | 2.31% | 9.03% |
| `mnm3` | MOSFET | 1.58% | 6.16% |
| `mnm4` | MOSFET | 0.75% | 2.94% |
| `mnm1` | MOSFET | 0.36% | 1.40% |

The dominant contributors are the two drain-load **resistors** (`rr1` +
`rr2` = 41% of F−1) and the two devices sitting closest to the input combiner
(`mnm2`, `mnm5`, another 39%) — not the common-gate input device itself
(`mnm1`, only 1.4%). The finite-Q input inductor (`rql1`) costs 9%. This
matches the program-level finding from §26/§27 that, post multi-finger
cutover, load resistors and the channel-thermal noise of the gain devices
dominate rather than gate-electrode resistance (the pre-cutover artefact).

### 4.5 Device / inductor budget vs used

| resource | box | used | headroom |
|---|---|---|---|
| device count | [3, 21] | 20 | 1 device |
| inductor count | ≤ 6 | 2 | 4 |

Per FINDINGS §25.3, the gate needed 20 devices, not the 21 the budget was
widened to — this design does not use the last slot. `pL2V` (the second-stage
tuned-load inductor) sizes to **exactly 15 nH — the sizing box's `l_max`
ceiling** on three of the four bands (`s`, `l1`, `l2`; `dhruva-l5` sizes it to
10.5 nH). That is an active box boundary, not a spec violation, but it is
worth stating plainly: on three bands the sizer would likely use *more*
inductance at that node if the box allowed it.

---

## 5. Honest scope caveats — prominent, by design

This section exists because "feasible" in this program has a specific,
narrower meaning than "matches the paper," and burying that distinction would
misrepresent the result.

1. **Process/models.** Behavioral **45 nm BSIM4** bulk CMOS, generic
   (`AutoCkt/repo/.../45nm_bulk.txt`) — **not** the paper's 65 nm silicon
   process. No claim of numeric parity with measured silicon is made or
   implied.
2. **Passives are ideal-ish.** Inductors are modeled with a fixed **Q = 12**
   series-loss resistor, not an extracted/EM-simulated spiral. Capacitors and
   resistors are ideal SPICE elements — no parasitic coupling, no substrate
   loss, no self-resonance beyond what the Q model implies.
3. **Multi-finger layout is an assumption, not a layout.** MOS devices emit
   with `NF = ceil(W / w_finger)`, `w_finger = 2 µm` (user-approved,
   2026-08-10 cutover, FINDINGS §27.1) — calibrated to real RF layout
   practice (~1–5 µm/finger), not chosen to clear a target. On this design
   that works out to **4–52 fingers per device** depending on band and
   stage (§2.1's W range is 6.6–102.8 µm). No actual layout — no routing
   parasitics, no finger-to-finger mismatch, no ESD structures — is modeled.
4. **Gain mapping.** The paper reports voltage gain into an on-chip load;
   this harness gates **S21 into a 50 Ω port** and adopts the paper's numbers
   as S21 thresholds as-is (`08-DHRUVA-GOAL.md`'s explicit mapping decision,
   §5's "revisit only if structurally unfair" clause — not revisited here).
5. **Single-ended output.** This design's output is single-ended (`VOUT1`
   into a 50 Ω port). The paper's target is **differential** (single-ended
   RF in, balanced out, imbalance ≤ 0.22 dB / ≤ 0.9°) — tier-3, and this
   harness has no 3-port differential measurement at all. Not attempted.
6. **IIP3 is unmeasured.** `iip3_dbm` is `status: unsupported` on all four
   specs — no two-tone/harmonic-balance harness exists in this program
   (the VACASK bookmark in the project memory index is the planned route).
   Nothing in this package should be read as an IIP3 claim in either
   direction.
7. **Gain programmability is unmeasured.** The target's ≥10.6 dB adjustable
   range (≥3 steps) is a switch/DOF question the topology search was never
   posed — this design is one fixed operating point per band, not a
   gain-programmable circuit.
8. **Stability is frequency-domain, ideal-element only.** §3.2's K/Δ audit
   covers 0.1–20 GHz at the nominal sized point. No process corners
   (fast/slow/temperature), no load-pull, no package or bond-wire
   parasitics, no supply/ground bounce. §27.5 found a *different* design in
   this program's history that looked unconditionally stable under a since-
   corrected measurement artefact and was not — the general lesson (measure
   the wide band, don't infer it) is applied here, but the same caveat about
   what is still *not* modeled (packaging, corners) applies equally to this
   design.
9. **What "feasible" claims and does not claim.** Per `08-DHRUVA-GOAL.md`
   §5: tier-1/tier-2 feasibility here means the pipeline found a topology
   class meeting the same **constraint shape** as the paper's targets, *at
   this harness's fidelity* — S11-held-over-band together with tuned gain
   and now noise figure. It is explicitly **not** a claim of parity with
   65 nm silicon, and every NF number in this program prior to the 2026-08-10
   multi-finger cutover was, by direct measurement, pessimistic by a median
   of ~2 dB relative to the harness now in use (FINDINGS §27.3) — a reminder
   that harness fidelity has moved the goalposts materially within this
   program's own history, and could move again.

---

## 6. Repro artifacts

All committed under `lna/repro/dhruva-best/`:

| file | contents |
|---|---|
| `tokens.json` | the shared topology, AnalogGenie token form |
| `dhruva-{s,l1,l2,l5}.params.json` | per-band sized device values |
| `dhruva-{s,l1,l2,l5}.meta.json` | per-band `wl_hash`, recipe, provenance, stored margins |
| `dhruva-{s,l1,l2,l5}.sp` | per-band standalone runnable ngspice deck |
| `recreate.py` | replay / audit / noise-budget / resize runner (see README.md) |
| `README.md` | file index + exact recreate commands |
| `REPORT.md` | this document |

Commands are listed in `README.md`. In short: `python
lna/repro/dhruva-best/recreate.py --audit` reproduces every number in §3–4 of
this report from a cold start.

---

## 7. Bottom line

One search-found, automatically-sized 20-device topology closes tier-1 *and*
tier-2 (S11-over-band, S21@f0, Idd, NF) on **all four** paper-target bands at
once — the "reconfigurable" essence of the target (Gate D2) plus the noise
gate (Gate D3), together, on a single design. Fresh re-verification this
session found **zero discrepancies** against the previously recorded numbers
beyond print-precision noise. The honest reading is in §5: this is
constraint-shape parity at a 45 nm-behavioral, ideal-passive, single-ended,
IIP3-blind fidelity — a strong result *for this harness*, and explicitly not
a silicon-parity claim.

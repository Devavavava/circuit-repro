# bench-v2 motif audit: `add:L:IN-G` (2026-10-01)

**Question.** 9 of the 11 accepted amendment-1 cells contain `add:L:IN-G`, an
inductor from the input port net VIN1 to the input-transistor gate, placed
across the parent's input DC-block C1 (parent a3, shunt-feedback). Is this a
real RF move, or does it exploit the testbench port model?

**Verdict: MIXED.** It does not exploit the port's DC behaviour. The testbench
port cannot set the gate DC at all, and the move still works with an ideal
AC-coupled source. What it does is remove the DUT's own input DC block and rely
on the testbench's DC block in its place. The anchor convention says the DUT owns
that block (all 5 LNA anchors have one), and the search exploits that gap as a
cheap structural shortcut. On the RF side it is ordinary series-L input matching.
The proposed guard removes **9 of 11** current accepted cells: exactly the
L-IN-G cells.

Read-only with respect to the running bench-v2 build. Nothing under `run/` was
written. All sims used bptm45 at seed 1 × 2500 with the rl-v1 profile. For
`smoke_run` this is the A1 call verbatim, plus capture-only monkeypatches. All
11 re-runs reproduce the stored `witness/results.json` A1_seed1 metrics exactly.

## 1. How the port is modelled

`lna/to_spice.py` (two-port branch):

```
Vp1 p1 0 dc 0 ac 1 portnum 1 z0 50
Cp1 p1 VIN1 10p            <- fixed testbench DC block, always present
Cp2 VOUT1 p2 10p ; Vp2 p2 0 dc 0 ac 0 portnum 2 z0 50
```

The op, sp, and wide-stability decks all use this same body. The noise deck
(`extract.build_noise_deck`) swaps Vp1 for `Vnz -> Rns 50` but keeps Cp1. So:

* At DC, VIN1 is open toward the source. The port DC current is exactly 0 in
  every deck, and the port cannot bias the gate.
* `bias.insert_bias` assumes this ("NOT the RF ports, which to_spice.py
  DC-blocks"). For a3 it adds no scaffold, because the gate is self-biased
  through R1 from the drain.
* Cp1 is a fixed 10 pF series element (XCp1 = 32 → 5 Ω over 0.5–3 GHz), so it
  is part of every design's input network.

## 2. What the 9 L-IN-G witnesses do (same sizes, `results/<cell>/audit.json`)

| | value across the 9 cells |
|---|---|
| IN-G inductor | 1.24–4.44 nH; X_L 5–84 Ω in band; L‖C1 self-resonance 8–14 GHz (out of band) |
| DUT's own C1 | sized to the range floor, **51–325 fF** (X_C1 0.2–6 kΩ in band); setting C1 = 1e-20 F (open) shifts every metric by ≤0.02 dB, so C1 is vestigial |
| NM1 DC op (P0) | VG = VGS = 0.286–0.312 V, ID 6.4–8.8 mA, VDS 0.23–0.31 V; VIN1 now sits at the gate DC level |
| DC current through the port | 0 (Cp1) |
| without the L (noL) | same DC op (gate bias comes from R1 self-bias and the IN-X resistor or repair pull-up, not from the L), but the RF dies: s21 −14.8 to +8 dB, 0/9 pass |
| parent topology at the same sizes | 0/9 pass, because C1 is tiny |

The AC mechanism is the L acting as the series input element: a series-L input
match in front of a resistive-feedback gate. This is a textbook wideband
technique (series gate inductor in resistive-feedback LNAs). L in series with the
testbench Cp1 resonates at 0.76–1.43 GHz, which is in band, but P1 below shows
the design does not need Cp1.

## 3. Realism test: change only the port model

| port model | L-IN-G witnesses, same sizes | L-IN-G re-sized (seed 1 × 2500) | controls (nb090-gain-007, wb1020-noise-003) |
|---|---|---|---|
| P0 testbench (10 pF DC block) | 9/9 | (accepted) | 2/2 |
| **P1 ideal AC-coupled 50 Ω** (Cp1 = 1 µF) | **6/9**; the other 3 miss by ≤0.06 dB (s11 or ripple), and s11 usually improves by 1–2 dB | **8/9** (noise-082's seed-1 re-size missed, but its witness passes P1 as-is) | 2/2 same sizes, 2/2 re-sized |
| **P2 DC-coupled 50 Ω** (Cp1 shorted) | **0/9**: VG drops to 0.10 V, ID to 0.3 mA, Idd −65 to −73 %, s21 about −10 dB, and the port sinks about 2 mA DC | **0/9** (near-misses burn 9.4–11.8 mA pulling the gate up against 50 Ω) | 2/2, 2/2 |
| **P3** = P0 + DC-only 50 Ω to ground via a 1 H choke (AC identical to P0) | 0/9, same collapse as P2 | – | 2/2; ΔIdd = 0, ΔVG = 0 |

Interpretation:

* **Not a port-DC exploit.** With a realistic AC-coupled source (P1) the
  witnesses still meet spec, and re-sizing restores 8/9. They do not depend on
  the 10 pF testbench cap as a matching element.
* **The artefact.** The design works only if whatever drives VIN1 is DC-open.
  The DUT's input pin carries the gate bias (about 0.3 V), and the circuit's own
  DC block has been sized to nothing and replaced by the testbench's Cp1. Any
  DC-coupled or DC-grounded source (generator, ESD or balun-grounded feed, P2/P3)
  turns the input device off. The controls, which keep their own DC block, are
  untouched by P1, P2 and P3.
* The W2 inert-device count misses the vestigial C1. Opening C1 shifts metrics
  by ≤0.02 dB, but the witnesses sit exactly on their limits, so even that tiny
  shift makes 7/9 infeasible and C1 is not counted as inert.

## 4. Proposed guard: G-PORT-DC (port DC isolation, pre-sizing, zero sims)

Build the DUT's DC graph: R and L are DC edges, a MOS D–S channel is a DC edge,
and C is open. **Reject** the topology if the DC component of VIN1 contains any
MOS terminal or any rail. In other words, the DUT must AC-couple its own input,
so the gate bias cannot depend on the source. `guard.py` implements it.

* All 5 LNA anchors pass by construction.
* **Current accepted (amendment-1): 9 of 11 removed.** These are exactly the
  L-IN-G cells: noise-082, power-000/084/091, gain-002/019/074/093/126. Kept:
  `v2a-nb090-gain-007` (series L *before* C1, which is the legitimate form of
  the same idea) and `v2a-wb1020-noise-003`.
* Live snapshot, for context: it would also reject 76 of 142 queued
  amendment-1 cells, 10/10 pre-amendment accepted, and 40 of 100 killed.
* Equivalent simulation form, if preferred: the **P3 invariance** test.
  Evaluate with a DC-only 50 Ω to ground at VIN1 (1 H choke) and require
  |ΔIdd|/Idd < 1 % and |ΔVG| < 10 mV. It removes the same 9 and keeps the same 2
  (`results/guard.json` → `sim_probes`).
* If the user would rather keep the RF idea: rewrite it into the
  DC-safe form, a series L on the port side of C1 (the a1 and nb090-gain-007
  pattern). Do not accept the variant that bypasses C1.

## Files

* `motif_audit.py`: per-cell re-size with capture, port variants P0–P3, noL,
  parent at same sizes, and P1/P2 re-size. Writes `results/<cell>/{sized_P0,P1,P2}.json` and `audit.json`.
* `guard.py`: G-PORT-DC structural guard and impact (`--sims` adds the P3
  invariance and C1-open probes). Writes `results/guard.json`.
* `aggregate.py`: writes `results/summary.json`. `summarize.py`, `peek.py`, `show_body.py`: viewers.
* Run with `BV2_TMPDIR=/tmp/cr-7cd7ffc3-motif ../envrun.sh python motif_audit.py <cells...>` (2 processes used).

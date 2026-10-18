# opamp-v0 witnesses — EVAL-ONLY

**EVAL-ONLY: never in a prompt or training file.** These netlists exist only to be sized by the
verifier in D0 (PREREG-OPAMP-V0-D0.md, Stage 2/3). Do not copy them, their device lists, or
their descriptions into any prompt, few-shot example, corpus, training set or shown-circuit
library. The shown circuits (anchors) and the F1 library are in `../circuits/lib/`.

| witness | file | regime | structure | devices | sizing params |
|---|---|---|---|---|---|
| W-R1 | `w_r1_fc_cs.net` | R1 (gain with swing) | folded cascode (NMOS input) + PMOS common-source second stage, Miller Cc + nulling Rz | 20 (16 MOS, 3 R, 1 C) | 27 |
| W-R23 | `w_r23_affc.net` | R2+R3 (gain ≥ 80 dB, CL 200 pF, GBW·CL/Idd) | three-stage AFFC (active-feedback frequency compensation), transcribed from AnalogGym | 31 (29 MOS, 2 C) | 31 |
| W-R4 | `w_r4_complementary.net` | R4 (ICMR) | complementary NMOS + PMOS input pairs, folded-cascode summing stage, PMOS common-source output, Miller Cc + Rz | 23 (19 MOS, 3 R, 1 C) | 31 |

All three follow the opamp-v0 dialect and bias rule: the ONE ideal reference current enters
`IREF`; every other bias (cascode gates, PMOS mirror gates) is generated in-netlist. W-R1 and
W-R4 use the same bias cell as the library folded cascode (`Rb` lifts the NMOS cascode gate =
`IREF` net above the mirror gate `n1`; an NMOS copy of the reference feeds the PMOS diode
`M12`, and `Rp` drops the PMOS cascode gate `vbp` below its gate `pa`). Matched groups follow
D-O4 (suffix digit + lower-case letter).

## W-R23 transcription (AnalogGym → opamp-v0)

Source: `/home/dpatni/circuit-repro/AnalogGym/repo/AnalogGym/Amplifier/spice_netlist/HoiLee_AFFC_Pin_3`
(BSD-3, pinned in AnalogGym's `UPSTREAM.md`), design variables
`Amplifier/design_variables/HoiLee_AFFC_Pin_3`. AnalogGym's port order is
`gnda vdda vinn vinp vout`; its ACDC testbench drives `vinp` with the DC common mode and closes
the DC loop at `vinn` (as ours). Polarity checked: VINP → net050 inverting (PMOS folded
cascode), net050 → net049 non-inverting (stage 2), net049 → VOUT inverting; the feedforward
PMOS xm12 (net050 → VOUT) is in phase with the main path.

Nets: `GNDA → VSS`, `VDDA → VDD`, `VINP/VINN/VOUT` kept, internal nets lower-cased
(`VB3 → vb3`, `VB4 → vb4`, `VOUTN → voutn`, `DM_2 → dm_2`, others unchanged).
Device type: `sky130_fd_pr__pfet_01v8 → PMOS`, `nfet_01v8 → NMOS` (bptm45; W/L sized by our
sizer in our ranges, AnalogGym's values are not used). Bulk: as in AnalogGym (rail, or own
source for the input pair xm9/xm10 = `net31`).

Matched groups: AnalogGym ties W/L (and a multiplier m) by design-variable name; m sets
mirror ratios. Our dialect has no multipliers (D-O4: ratios via separate devices), so **each
distinct (AnalogGym W/L variable, multiplier) is one matched group**; ratios between groups
of the same AnalogGym variable become free W choices of the sizer.

| AnalogGym | variable (m) | ours | role |
|---|---|---|---|
| xm0 | BIASCM_PMOS (m) | M0a | PMOS bias diode `net013` |
| xm1 | BIASCM_PMOS (m) | M0b | → vb4 branch |
| xm3 | BIASCM_PMOS (m) | M0c | → vb3 branch |
| xm5 | BIASCM_PMOS (m) | M0d | stage-1 load diode `voutn` |
| xm6 | BIASCM_PMOS (m) | M0e | stage-1 load → net050 |
| xm7 | BIASCM_PMOS (m) | M0f | stage-2 current source → net049 |
| xm4 | BIASCM_PMOS (2m) | M4 | stage-1 tail `net31` |
| xm9 / xm10 | gm1_PMOS | M9a / M9b | input pair (VINN / VINP) |
| xm20 / xm21 | BIASCM_NMOS 18_7 (8m) | M20a / M20b | folding sinks |
| xm16 / xm17 | BIASCM_NMOS 17_7 (4m) | M16a / M16b | NMOS cascodes |
| xm15 | BIASCM_NMOS 18_7 (m) | M15 | vb3 diode |
| xm18 / xm13 / xm61 / xm64 | BIASCM_NMOS 18_7 (4m) | M18a / M18b / M18c / M18d | vb4 cascoded diode (xm18 bottom, xm13 top); AFFC sinks |
| xm11 | gm2_PMOS | M11 | stage-2 input |
| xm22 / xm23 | LOAD2_NMOS | M22a / M22b | stage-2 mirror |
| xm25 | gm3_NMOS | M25 | stage-3 NMOS |
| xm12 | gmf2_PMOS | M12 | stage-3 feedforward PMOS |
| xm59 / xm62 | HSBCM_PMOS | M59a / M59b | AFFC current-return mirror |
| xm60 / xm63 | gma_NMOS | M60a / M60b | AFFC common-gate pair (xm63 = active-feedback gma) |
| C0 | CAPACITOR_0 | C0 | Miller cap net049 → VOUT |
| C1 | CAPACITOR_1 | C1 | active-feedback cap VOUT → net1 |
| I0 (ideal sink out of net013) | CURRENT_0_BIAS | IREF + MB1a (diode) + MB1b (1:1 mirror pulling IREF out of net013) | bias reference |
| xm2, xm14, xm19 | — | dropped | dummy branch `DM_1` (connected to nothing else) |

Bias-rule changes, recorded: (1) AnalogGym's single ideal current **sinks** from the PMOS
diode net013, while our testbench **pushes** IREF into the `IREF` net; the 1:1 NMOS mirror
MB1a/MB1b converts one into the other (+2 devices, I(net013) = IREF exactly when matched).
(2) AnalogGym uses no ideal bias voltages in this netlist (vb3 and vb4 are generated
in-netlist by xm15 and the xm13/xm18 cascoded diode), so nothing else had to be replaced.
(3) The dummy branch is dropped (it only burns current). AnalogGym's Vcm (0.25·1.8 V) and
CL (100–500 pF) are not used: the testbench sets Vcm = VDD/2 = 0.55 V and CL per task
(200 pF in R23).

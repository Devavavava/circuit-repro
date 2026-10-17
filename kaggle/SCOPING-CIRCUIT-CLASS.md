# Scoping: a circuit class where multi-step topology changes are actually needed

Scoping study, 2026-10-18. No existing file changed; smoke check ≈ 3 CPU-min.

## Executive summary

- **Recommendation: op-amps / OTAs (operational transconductance amplifiers) on bptm45 (the repo's 45 nm
  model), with a new verifier path.** Gate it with a cheap depth test, "D0", before building a benchmark.
- **Why op-amps have depth.** The key op-amp specs are capped by physical limits that sizing cannot move:
  - gain per stage is at most the transistor's intrinsic gain;
  - output swing shrinks with every transistor stacked between the rails;
  - input range is set by the threshold voltage;
  - stability under a large load depends on the compensation network.

  Lifting a cap needs a structural change of 3–10 devices, and the in-between states are broken: unbiased, unstable,
  or with an undefined output level.
- **Measured here.** Over 2,000 random sizings each (channel length up to 1 µm), the best results were:
  - one-stage 5-transistor OTA: 29.2 dB gain;
  - two-stage Miller OTA: 57.8 dB gain, at phase margin 66° and a 44 MHz unity-gain frequency.

  One simulation costs about 10 ms, and AutoCkt's stored deck replays bit-exactly.
- **The trap to avoid.** Swapping between compensation schemes alone is shallow. In AnalogGym, SMC and NMCF (single Miller;
  nested Miller with feedforward) differ by one capacitor, and 7 of the 16 amps have a neighbour within 4 devices. Depth must come from stage count,
  cascoding, input pairs or CMFB.
- **Cost.**
  - About 10–13 engineering days and about 25 CPU-h to a D0 verdict.
  - About 4–8 more days and 60–100 CPU-h to a frozen benchmark.
  - No GPU is needed until Qwen is evaluated.

## 1. What already exists

| Asset | Where | Relevance |
|---|---|---|
| AutoCkt two-stage op-amp | `AutoCkt/smoke_engine.py`; one rendered deck + `ac.csv` under `AutoCkt/work/designs_two_stage_opamp/` | The AutoCkt code is **not cloned** here; only its model card `AutoCkt/repo/eval_engines/ngspice/ngspice_inputs/spice_models/45nm_bulk.txt` is, and **that card is bptm45** (`lna/pdk/bptm45.py`). The stored deck replays bit-exactly (§4). |
| AnalogGym amplifiers | `/home/dpatni/circuit-repro/AnalogGym/repo/AnalogGym/Amplifier/` (main checkout, gitignored, BSD-3, pinned in `UPSTREAM.md`) | 16 non-empty op-amp subcircuits, mostly three-stage with different compensation (SMC, NMCF, NMCNR, AFFC, DFCFC1/2, ACBC, IAC, TCFC, PFC, CFCC, AZ/AZC, DACFC, CLIA). Also design variables, AC/DC and transient testbenches, the sky130 PDK, and 4 LDOs. |
| AnalogGym adapter (engineer line) | `/home/dpatni/circuit-repro-engineer/engineer/ext_gym.py`, `EXT-CALIBRATION.md`, `data/ext_*` (branch `engineer`, `4bcc6ac7d`) | **A working, deterministic op-amp harness**: 14 amps run on ngspice-47 and replay with spread 0.0. But it costs about **47 s per evaluation** on sky130 (heavy deck), and CMA-ES missed Fan_SMC's phase margin within 1,000 evaluations (seed 1). |
| AnalogGenie | `AnalogGenie/repo/` (model code only); `lna/genie_common.py`; `lna/build_lna_corpus.py` | The topology `Dataset/` (which has op-amps) is **not on disk**. The token vocabulary already covers current sources (`build_vocab`). |
| `misc/` | `misc/ZOAF` only | There is no `misc/AutoCkt` and no `misc/AnalogGenie-Lite` in this checkout or the main one. |
| Other circuit classes | `lna/pa_harness.py`, `mixer_harness.py`, `balun_harness.py`; `kaggle/bench-anchors/{pa,mixer,balun}/` | RF classes (power amplifier, mixer, balun) that sit on the LNA S-parameter path. **There is no op-amp code in `lna/` or `kaggle/`.** |

**How LNA-specific the sizer is.** The optimizer core is generic and deterministic: CMA-ES (Covariance Matrix
Adaptation Evolution Strategy) over parameter boxes, in `lna/size.py` and `kaggle/bench_anchor_prep.py::smoke_run`.
Everything around it is LNA (low-noise amplifier)-specific:

- **Measurement.** `lna/extract.py::run_and_extract` (l.461) returns `None` unless the S-parameters s11/s21 exist
  (l.508–513). The class hook `size.py::_class_metrics` (l.339) only *adds* metrics to that path. An op-amp needs a
  **parallel measurement path**, as `EXT-CALIBRATION.md` §3 already concluded.
- **Parameters.** `size.py::kind_ranges` (l.191) has no MOS channel length: it is **pinned at 45 nm**
  (`pdk/bptm45.py`). Op-amps need channel length L as a free parameter, because gain scales with it, plus a
  reference-current parameter.
- **Bias.** `lna/bias.py` rule R-GATE gives every undriven gate an ideal, sizer-tuned voltage source (VBGEN). For
  op-amps this is a **loophole**: a tuned ideal voltage can stand in for a bias network or for CMFB.
- **Netlist dialect.** `kaggle/editcap_run.py` l.370–386 frames the task as an LNA repair, with types
  `{NMOS,PMOS,R,C,L}` and nets `VIN1/VOUT1`. Op-amps need inputs `VINP/VINN` and a reference-current net `IREF`.
- **Single-edit filter.** F2 (F1 is the library filter; `kaggle/campaigns/bench-v2/bv2.py::f2space_build`, l.2364) only adds an R/C/L between
  two nets or deletes an element, and **never adds a transistor**. That is too weak to support a depth claim for
  op-amps.

## 2. Where op-amp depth comes from

Vocabulary: **gm** is transconductance and **ro** output resistance. **gm·ro** is one transistor's intrinsic gain;
it grows with channel length L and is only a few tens at 45 nm. **Vdsat** is the minimum voltage that keeps a
transistor saturated; **Vth** is the threshold voltage. **UGF/GBW** is the unity-gain frequency, where open-loop
gain reaches 1. **PM** (phase margin) is the stability reserve at UGF. **CL** is the load capacitance. **Swing** is
the usable output range; **ICMR** is the input common-mode range. **FD** means fully differential, and **CMFB**
(common-mode feedback) is the loop that fixes an FD amplifier's average output level.

Each regime below needs a multi-device structural change, because a bound that no sizing can move blocks it.

| # | Spec regime (bptm45, VDD 1.1 V) | Why sizing cannot fix it | Textbook answer: edit size from a simple anchor |
|---|---|---|---|
| R1 | **Gain ≥ ~75 dB and swing ≥ ~0.6 Vpp** | Gain ≤ (gm·ro)^stages. Measured ceilings: ~29 dB for one stage, ~58 dB for two. A cascode squares gm·ro but takes ≥ 2 Vdsat of headroom, so one-stage cascodes lose the swing. | Cascoded first stage with its bias branch + common-source second stage + Miller Cc + nulling Rz: **≥ 6 devices from a 5T OTA** |
| R2 | **Gain ≥ ~85–95 dB** at low voltage | Needs three stages. Adding a stage without changing the compensation makes the amplifier **unstable**, so stage and compensation must change together. | Third stage + nested-Miller (NMC) or a damping-factor variant: **4–6 devices as one coherent change** |
| R3 | **Large CL (100 pF–1 nF) with GBW·CL/power above a threshold** | In a Miller two-stage the second pole is ≈ gm2/CL, so power must grow with CL. Sizing only moves along that trade-off. | Multi-stage with active-feedback or damping-factor-control compensation (AFFC, DFCFC). Deep from a 1–2 stage anchor; **shallow from another 3-stage amp** |
| R4 | **Rail-to-rail ICMR** with gain held across the range | An NMOS pair needs Vcm ≥ VGS + Vdsat, and a PMOS pair needs Vcm ≤ VDD − \|VGS\| − Vdsat. **Vth is not a sizing knob.** | Complementary N+P input pairs + summing stage, optionally constant-gm: **5–8 devices** |
| R5 | **FD output CM within ±50 mV over VDD ±10 %, temperature and Vth skew** | Without a CM loop, CM gain is huge. A nominal sizing can hit the target by luck; corners cannot be passed. | CMFB sensing + error amp: **4–8 devices** |
| R6 | **Slew ≥ k·I_quiescent/CL** at low static power | Class-A slew is I_tail/Cc, so more slew costs power. | Class-AB output or adaptive bias: **≥ 4 devices** |

Two cautions:

1. **Compensation swaps alone are shallow.** A device-level diff of AnalogGym's netlists (raw net names, so upper
   bounds) gives SMC→NMCF = +1 capacitor, and DFCFC1, ACBC, PFC and CFCC are each 3–4 devices from a neighbour. So
   anchors must be 1–2 stage OTAs, and witnesses must combine 2–3 of R1–R6.
2. **The verifier decides whether a bound is real.** Pinned L, ideal VBGEN sources, or nominal-only checks would let
   a sizer fake R1 or R5 with knife-edge operating points. bptm45 has no corner cards (`lna/corners.py`), so emulate
   corners: VDD ±10 %, −40/125 °C, and Vth skew through the BSIM4 instance parameter `delvto`.

## 3. Minimal verifier, benchmark and depth test

### Verifier `opamp-v0`: a new `circuit_class` with its own measurement path

- **Sizer.** bptm45. Sizable W, **L in [45 nm, 1 µm]**, Cc, Rz and IREF. CMA-ES via `smoke_run`, seeded and
  deterministic, with a profile string as in rl-v1.2.
- **Testbench.** Unity-gain DC feedback through a 1 TH inductor, with AC injected through a 1 TF capacitor. This is
  AnalogGym's trick, and the smoke check already uses it: the DC point is self-consistent without ideal bias.
  **One ideal reference current**; all other bias is generated in the netlist; VBGEN is off.
- **Metrics, in one multi-copy deck:** DC gain, UGF, PM, Idd; swing and ICMR (follower DC sweep); CMRR and PSRR
  (common-mode and supply rejection); slew and settling (short transient); output CM for FD designs. Corners are
  re-checked on the final winner only.
- **Dialect.** Types `{NMOS,PMOS,R,C}`; nets `VINP, VINN, VOUT(P/N), VDD, VSS, IREF`. Matched groups are tied by
  naming convention, following the model of `size.py::match_devices`.
- **Cost.** About 10 ms per operating-point + AC simulation, measured. About 30–60 ms per full evaluation, estimated. That gives
  ~1.5–2.5 CPU-min per 2,500-evaluation sizing, or 2–3× an LNA sizing call. sky130 is kept only as a sanity check.

### Benchmark `bench-op-v0`: same shape as bench-v2

- **Anchors** (the circuit shown to the model): 5T OTA, two-stage Miller, folded-cascode, FD folded-cascode
  *without* CMFB.
- **F1 library:** 5T OTA, two-stage Miller + Rz, telescopic, folded-cascode, three-stage NMC.
- **F2′ single-edit space, widened:**
  - add an R/C between any net pair;
  - **add one NMOS/PMOS with D/G/S on existing nets or one new net**;
  - delete one element;
  - **re-wire one terminal**.

  That is about 1–3k candidates per anchor.
- **Planted witnesses (EVAL-ONLY):** folded-cascode + common-source with Miller + Rz (R1); three-stage DFC or AFFC,
  transcribed from AnalogGym (R2+R3); complementary-input with class-AB output (R4+R6); FD two-stage with CMFB
  (R1+R5).
- **Process rules.** Pre-registration, goldens green before and after every landing, and witnesses never in a prompt.

### Depth test D0, the go/no-go (like bench-v3 A0, without its flaw)

A0 read slack on non-target constraints from runs whose objective had already spent it (median 0.0003). **D0 rule:
every number comes from a sizing run whose objective is the quantity being tested, at the spec being tested.**

1. **Tasks.** Two anchors (5T, two-stage) × three regimes (R1, R2+R3, R4) = 6 tasks. Each has one target metric M;
   the other constraints are hard.
2. **Frontier per design.** For d in F1 ∪ F2′ and for the witness W, size to **maximize M subject to the hard
   constraints** (a new sizer objective mode). This asks the sizer only to push M up, which it does well.
   - F2′ is screened at 300 evaluations, seed 1.
   - The top 20, all of F1 and W are re-run at 2,500 evaluations × 3 seeds.
   - M\* is the median over seeds.
3. **Gap.** G = M\*(W) − max_d M\*(d). The minimum gap is fixed in advance: 6 dB for gain-type metrics, 25 % for
   GBW·CL/power.
4. **Confirmation at a new spec.** Set the limit at max_d M\* + G/2. Size W and the top 5 references with the standard
   margin objective, 3 seeds. Accept iff:
   - W is feasible in ≥ 2/3 seeds; **and**
   - every reference is infeasible in 3/3 seeds with worst margin ≤ −G/4.
5. **Two-edit check.** Screen 500 random two-edit designs per task. If any comes within G/2 of W, the task is
   labelled "≤ 2 edits", not deep.
6. **Verdict.**
   - **GO**: ≥ 4 of 6 tasks accepted, and ≥ 2 of them survive step 5.
   - **STOP**: ≤ 1 accepted.
   - Otherwise discuss.
7. **Backstops.** Report the analytic ceiling (best gm·ro at L_max)^stages, so a weak sizer is not misread as depth.
   Budget ≈ 6 × (2k × 300 + 26 × 3 × 2,500) evaluations × 40 ms ≈ **20–25 CPU-h**, about 3 h on 8 workers.

## 4. Smoke check performed

Script (not committed): `~/.claude/jobs/7cd7ffc3/tmp/scope/opamp_smoke.py`; output `…/scope/result.json`.

- **(A) AutoCkt replay.** The stored two-stage deck was re-pointed at the bptm45 card. All 101 AC points match the
  stored `ac.csv` exactly (relative difference 0.0).
- **(B) Depth probe.** 2,000 deterministic random sizings per topology. Settings: W 0.5–50 µm, L 45 nm–1 µm,
  IREF 2–100 µA, Cc 0.1–10 pF, Rz 10 Ω–20 kΩ, CL 2 pF, unity-feedback DC loop, mirror bias.

| topology | ngspice call (median) | median gain | best gain with UGF ≥ 10 MHz, PM 45–135°, Vout within 50 mV of Vcm |
|---|---|---|---|
| 5T OTA (1 stage) | 9.4 ms | 25.6 dB | **29.2 dB** (33 MHz, PM 73°, 112 µA) |
| two-stage Miller + Rz | ~10 ms | 41.4 dB | **57.8 dB** (44 MHz, PM 66°, 103 µA) |

The table uses a rerun with the PM filter tightened to 45–135° (the first run admitted a bogus 245°). These are random-search results, not optimized ones. Even so, the one-stage
ceiling agrees with gm·ro/2 at L = 1 µm, which is exactly the kind of wall R1/R2 rely on.

## 5. Effort, compute, risks

| Step | Engineering days | CPU |
|---|---|---|
| `opamp-v0` measurement path + determinism golden | 3 | <1 h |
| Sizer integration (bypass the S-parameter path, L/IREF parameters, matched groups) | 2–3 | <1 h |
| Dialect, round-trip, tokens, prompt rewrite | 1–2 | — |
| Library + witnesses transcribed and golden-checked (8–10 circuits) | 2–3 | ~2 h |
| F2′ enumerator + D0 pre-registration, run and report | 2 | 20–25 h |
| **Subtotal to the D0 verdict** | **10–13** | **~25 CPU-h** |
| If GO: specs, tiers, null and baseline runs (blind, genetic algorithm), freeze | 4–6 | 60–100 h |
| LLM evaluation: Opus via API; Qwen3-14B on Kaggle T4 (existing kernel pattern) | 2 | GPU here only |

**Kaggle GPU** is needed only for Qwen. Op-amp netlists are 15–35 devices against about 8–12 for the LNAs, so expect
about 1.5–2× the tokens per completion.

**Main risks**

1. **Sizer strength at 20–40 parameters.** CMA-ES missed Fan_SMC's PM at 1,000 evaluations, and a witness that fails
   because of the sizer looks like "no depth". Mitigate by sizing on current density and L, tying matched groups,
   giving witnesses a bigger budget, and using the analytic backstop.
2. **Shallowness returns** if anchors are already multi-stage. The D0 two-edit check is there to catch it.
3. **Verifier loopholes.** Ideal bias, pinned L or nominal-only checks would let sizing fake depth. Close them by
   design.
4. **No real process corners.** The `delvto` emulation is an approximation; state it in the pre-registration.
5. **Prior knowledge.** Op-amps are textbook material. That fits the spec-capacity goal but weakens "discovery"
   claims.
6. **Numerics.** SPICE gain above ~100 dB is unreliable; cap specs at 95 dB.

**Other classes considered.** An LDO (low-dropout regulator) is an op-amp plus a pass device, so it is the natural follow-on on the same harness, but its load-step transients cost more. A bandgap reference has few topologies, so it is likely shallow. Comparators need transient-heavy measurement, and a PLL or VCO (phase-locked loop, oscillator) needs expensive system-level simulation. PA (power amplifier) and mixer are already wired, but are RF with small topology spaces. Op-amps give the best ratio of structural depth to verifier cost.

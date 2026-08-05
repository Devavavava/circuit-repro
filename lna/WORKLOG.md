# LNA work — log of what was tried, what worked, what didn't

**Session:** 2026-08-05 · **Machine:** Windows 11, RTX 3050 4 GB, WSL2 Ubuntu 22.04

A lab notebook, not a summary. [FINDINGS.md](FINDINGS.md) states the conclusions;
this records the route, including the parts that failed and one thing that is
still unexplained. Read it before repeating any of the experiments.

---

## Successes

### S1 — Located the LNA subset precisely
`AnalogGenie/repo/Dataset/data_categorization.md` maps index ranges to textbook
chapters. LNAs are **461–492** (Razavi, *RF Microelectronics*) and **1081–1090**
(assorted papers). 41 circuits exist (490 has no netlist), out of 3,351 — **1.2%**
of the corpus. Confirmed independently by device mix: inductors are 20.3% of
device instances in the LNA subset versus 0.8% corpus-wide.

### S2 — ngspice 45.2 does everything an LNA needs
`op`, `ac`, `noise` and **`sp`** all execute. S-parameters need port syntax
(`Vin in 0 dc 0 ac 1 portnum 1 z0 50`); noise figure comes from
`inoise_spectrum` as `10·log10(inoise² / 4kT·Rs)`. This was the single most
important thing to establish and it came out positive — the measurement side was
never the bottleneck.

### S3 — Found the console ngspice build
STATUS.md documents that msys2's `ngspice.exe` is GUI-subsystem and writes
nothing to stdout, making `-o <logfile>` mandatory. **`ngspice_con.exe` in the
same directory does not have this problem.** Also: the install is under `ucrt64`,
not `mingw64`. This makes scripted evaluation far simpler.

### S4 — Topology reconstruction is exact
Round-tripped dataset circuit 461 (token sequence → union-find node rebuild →
netlist) and got the original `461.cir` back device-for-device. The union-find
approach in `_logs/validate_analoggenie.py` is sound and was reused wholesale.

### S5 — Structural screen separates LNAs cleanly
Five criteria (inductor present, inductor ratio ≥10%, transistor present,
VIN+VOUT present, 2–15 devices). On ground truth: **59.4% of real LNAs score 5,
0% of non-LNA circuits score above 3.** The 40% miss rate is inductorless LNA
variants (resistive-feedback, common-gate) — correct behaviour, and it means
59.4% is the ceiling the screen can credit to a perfect generator.

### S6 — Built the LNA corpus
`build_lna_corpus.py` runs AnalogGenie's preprocessing over the LNA indices only.
Upstream hardcodes `1..3502` in a module-level driver, so the script execs only
the function definitions above that driver and supplies its own loop — no patch
to upstream. Result: **41 circuits → 4,023 augmented Eulerian sequences.**

### S7 — Prefix conditioning works
The headline result. Seeding with 12 tokens of a real LNA traversal instead of
bare `VSS` moves the hit rate **0% → 40.6%** with no retraining. Swept prefix
length 4/8/12/24: hit rate and seed-copying both rise monotonically, but *novel*
distinct LNAs peak at length 12 (16 per 128 samples) and collapse at 24, where
83% of output is a copy. Full tables in FINDINGS.md §5.

### S8 — Pipeline yield 65% → 95%
`.option rshunt=1e12` fixed every singular-matrix failure caused by
capacitively-isolated nodes. On generated candidates at the recommended
operating point, **48 of 52 score-5 topologies (92%) simulate**.

### S9 — Two orders of magnitude on sampling throughput
Upstream samples batch-1 for a fixed 1024 steps. Batched + early-stopped, on GPU:
**0.3 s/sequence versus ~400 s on CPU upstream.** Batch-64 is 155× batch-1 per
sequence.

---

## Failures and dead ends

### F1 — I could not hand-design a well-matched 2.4 GHz LNA *(unresolved)*

The one substantive failure. The goal was a reference LNA to validate the
measurement harness against; I got the harness validated but never a good design.
Sequence of attempts:

1. **First probe** — floating node, and `Lgate` DC-shorted the gate to the 50 Ω
   port, so the bias divider was 0.65 V × 50/(20k+50) ≈ 1.6 mV. M1 sat at 9 µA.
   *Fixed* by DC-blocking the port with a series capacitor.
2. **Device sanity check** — standalone M1 at Vgs = 0.65 V gives Id = 5.3 mA,
   gm = 5.3 mS. The device and model were fine; the topology was wrong.
3. **Capacitance extraction** — `@m1[cgs]` returns **negative** values (BSIM4
   sign convention). Magnitudes are usable but the sign trips up naive formulas.
4. **fT is very high** — 300–600 GHz across the bias range for 45nm BPTM, giving
   a required source degeneration of `Ls = 50/ωT` ≈ **12–27 pH**, which is not a
   realizable on-chip inductor. Widening the device does not help: fT ≈ gm/Cgs is
   roughly independent of W.
5. **Suspected a name collision** — ngspice identifiers are case-insensitive, so
   `.param LS` and inductor `Ls` are the same name. Renamed everything and
   re-ran. **This was not the cause** — results were bit-identical. (It is still
   a real trap and worth avoiding; see X2.)
6. **Direct Zin measurement** — drove the gate with a 1 A AC source so `V(g)` is
   numerically Zin. Measured **Re = 1122 Ω, Im = −10 Ω** at 2.395 GHz, against a
   predicted `ωT·Ls` = 82 Ω and a predicted capacitive reactance of about −410 Ω.
   **Neither matches, and I did not resolve why.**

   Working hypothesis, untested: the output tank (`Ldrn` 6 nH ∥ `Ctnk` 0.55 pF)
   resonates at ≈2.77 GHz, inside the measurement band. Near resonance the
   cascode's load impedance is very large, and any feedback path — even a
   sub-fF Cgd — gets multiplied, reshaping Zin. **Anyone picking this up should
   test that first by detuning the tank far from band and re-measuring Zin.**

   Best S11 achieved was **−0.78 dB** (essentially total reflection) and NF
   16.9–20.3 dB. These numbers characterise a broken design, not the harness.

**Judgement call:** I stopped rather than continue hand-tuning, because an
automated sizing loop is the right answer for this problem and the harness was
already proven. That is defensible, but it does leave the setup **without a
single known-good, well-matched reference LNA** — which is a real gap for
regression testing. See H-Q1 in the handover.

### F2 — CPU generation is impractical for experiments
The first unconditional run (32 sequences, batch 16, 512-token cap) did not
finish a single batch in 10 minutes and was killed. All experiments moved to the
WSL GPU. Windows `analoggenie` is torch 2.0.1+**cpu**; CUDA lives in WSL at
`/opt/miniconda/envs/gpu`.

### F3 — GPU OOM at batch 64 × 384 tokens
`cudaErrorUnknown`, with the card at 3922 MiB of 4096. Killed one sweep arm
outright and produced an empty result directory that the screen happily reported
as "0 distinct topologies" — a silent-looking failure. **batch 32 with a
256-token cap** is the safe configuration on this card, and since real LNA
sequences are ≤107 tokens it costs nothing.

### F4 — My own batching bug cost 8× throughput
`generate.py` originally grouped a batch by *identical prefix contents*. With
distinct LNA seeds that collapses to many batch-1 calls — the slowest possible
GPU mode. Rows only need to share a prefix **length**. Fixed: 3.2 s → **0.4 s**
per sequence.

### F5 — Eulerian augmentation is slow
Roughly 1 minute per circuit; the full 41-circuit LNA set took over 20 minutes.
It is a one-time cost (output is cached as `Sequence_total<i>.npy`) but it is the
bottleneck if the corpus is ever rebuilt or extended.

### F6 — Two circuits fail to simulate (one now resolved)
Index **490** has no netlist in the dataset at all — permanently lost. Index
**1081** fails with a singular matrix that `rshunt` does not rescue. It was
*hypothesised* (F6 original, carried into H-Q3) to be a genuinely floating
sub-circuit. **That diagnosis was wrong — see R1 below.**

### R1 — 1081 is an ideal-inductor singularity, not a floating sub-circuit *(resolved)*
Building the H-Q3 connected-component detector (`Topology.floating_devices`,
`topology.py`) and running it over the corpus flagged **nothing**, including
1081 — because 1081 is *fully connected*: every device traces to VIN1 / VSS /
VDD / VB1 / VOUT1. The real fault surfaced in the ngspice diagnostic:
`singular matrix: check node ll4#branch`. Node **VB1 is reached only through the
ideal inductors LL4 (VDD–VB1) and LL5 (VB1–VOUT1) plus the MOS gate of NM2**
(no DC current), so the inductor *branch current* is undetermined — a classic
ideal-inductor singularity, not a connectivity or capacitive-isolation problem
(which is why `rshunt` cannot help).

**Fix, confirmed:** giving inductors a finite Q (series R = ω0·L/Q) makes the
branch current determinable. 1081 simulates with Q as low as ~12, and the
corpus pipeline yield rises **40/42 → 41/42** (only 490, the netlist-less one,
remains). Implemented as an opt-in in `to_spice.py`
(`Netlist(..., inductor_q=12)` / `--inductor-q 12`), default still ideal so
existing reference/sizing baselines are unchanged. This is the 05-SIZE §4
finite-Q upgrade, brought forward because it closes 1081. Enable it by default
once WP-REF establishes the reference anchors.

Lesson: the floating detector is still correct and worth keeping — a *generated*
topology genuinely can emit a disconnected island (verified on a synthetic
L–C loop) — but H-Q3's specific claim about 1081 was a mis-diagnosis.

---

## Fixes worth remembering

| # | Problem | Fix |
|---|---|---|
| X1 | `.param Ln=45n` → `Expression err: ln}` | `ln` is an ngspice builtin; never name a parameter `Ln` |
| X2 | `.param LS` silently aliases element `Ls` | identifiers are **case-insensitive**; prefix all params (`pLDEG`) |
| X3 | `@m1[id]` in a sweep → `indexing a scalar` | `save @m1[id]` *before* running the analysis |
| X4 | floating / capacitively-isolated node → `singular matrix` | `.option rshunt=1e12` |
| X5 | one-port circuit → `Fatal error: incorrect port ordering` | port numbers must run contiguously from 1; emit a two-port setup only when both VIN1 and VOUT1 exist |
| X6 | disconnected output → `argument out of range for db` | floor it: `db(mag(S_2_1) + 1e-30)` |
| X7 | GPU fault at batch 64 × 384 tokens | batch 32, 256-token cap on a 4 GB card |
| X8 | batching collapsed to batch-1 | group rows by prefix *length*, not contents |
| X9 | PowerShell `Set-Content -Encoding utf8` writes a BOM that corrupts `.patch` files | write patches from bash, or strip the BOM |
| X10 | Git Bash mangles `C:\...` arguments via MSYS path translation | avoid drive-letter literals in `sed`/`grep` patterns, or use the Write tool |

---

## Things I verified that turned out to be dead ends for LNAs

* **ZeroSim cannot represent an LNA.** Its `configs/device_vocab.json` has no
  inductor and no RF port — capacitor, current, gnda, nmos, pmos, resistor,
  vdda, vinn, vinp, voltage, vout. Its GA targets DC gain, GBW, phase margin.
  It is an op-amp model. Using it as an LNA surrogate would return confident
  nonsense. This was the most promising-looking dead end.
* **CktGNN** — op-amp/OCB topologies only.
* **LaMAGIC2** — power converters.
* **AnalogSAGE** — blocked upstream, ships no data.
* **RoSE** — needs Cadence; `eval_engines/` is a stub.

Still live for LNA work: **ZOAF** (zeroth-order black-box sizer; its metrics are
baseband but the optimiser is objective-agnostic and therefore retargetable) and
**CircuitSense** (symbolic MNA, does handle inductors as `s*L`).

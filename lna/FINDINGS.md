# LNA topology generation — capability assessment, gaps, and plan

**Date:** 2026-08-05 · **Scope:** what this setup can and cannot do for low-noise
amplifiers, measured rather than assumed. Companion to [STATUS.md](../STATUS.md),
which covers setup and smoke tests for all 15 repos.

See also [WORKLOG.md](WORKLOG.md) for the route taken — including the failures and
one unresolved measurement — and [HANDOVER-FABLE.md](HANDOVER-FABLE.md) for the
open brief on improving generation and defining design constraints.

---

## Bottom line

**The measurement side is ready. The generation side is not aimed at LNAs.**

ngspice 45.2 here supports everything an LNA needs — S-parameters, noise figure,
AC and operating point — and I verified all four run. AnalogGenie can *represent*
LNAs: inductors are in its vocabulary and the dataset contains 41 real LNA
circuits. Topology reconstruction is exact, and after one fix the topology →
netlist → simulation pipeline succeeds on 40 of 42 dataset LNAs (95.2%).

What is missing is any way to *ask* for an LNA. Generation is unconditional and
LNAs are ~1.2% of the training corpus, so sampling gives you whatever the
distribution favours — overwhelmingly op-amps, LDOs and bandgaps. On top of that,
the dataset's topologies are textbook schematics that omit biasing, so a generated
circuit is not directly simulatable for performance without a bias-insertion step.

Three things unlock this, in increasing cost: **prefix conditioning** (no
retraining), **fine-tuning on the LNA subset** (corpus now built), and a
**bias + sizing loop** to turn a topology into something with real numbers.

**The first of those is already working.** Seeding the sampler with the first 12
tokens of a real LNA traversal, instead of bare `VSS`, moves the LNA hit rate from
**0% to 40.6%** — no retraining, no change to the checkpoint. Candidates reach a
working simulation 94% of the time, and the setting produces **16 distinct LNA
topologies that are not any of the seed circuits**. See §5.

---

## 1. Where LNAs live in the data

`AnalogGenie/repo/Dataset/data_categorization.md` locates them precisely:

| Indices | Source | Count |
|---|---|---|
| 461–492 | Razavi, *RF Microelectronics* (2nd ed.) — "low noise amplifiers" | 32 (490 missing) |
| 1081–1090 | assorted "LNA papers" | 10 |

**41 LNA circuits out of 3,351** — about **1.2%** of the corpus.

Device mix tells the same story from another angle:

| | LNA subset | whole corpus |
|---|---|---|
| inductor share of device instances | **20.3%** (48/236) | **0.8%** (644/81,500) |
| devices per circuit | 5.8 | — |

Inductors are the signature: matching networks and degeneration need them, and
they are 25× more common in LNAs than in the corpus at large. That ratio is what
the structural screen keys on.

---

## 2. Capability matrix

| Repo | Relevance to LNA topology work | Verdict |
|---|---|---|
| **AnalogGenie** | the only topology *generator*; inductors in vocab; 41 LNA circuits | **usable, needs steering** |
| **ngspice 45.2** | `op`, `ac`, `noise`, **`sp`** all confirmed working | **ready** |
| **CircuitSense** | symbolic MNA, handles inductors (`s*L`, `TYPE_INDUCTOR`) | useful for analytic gain |
| **ZOAF** | zeroth-order black-box sizer over ngspice; metrics are baseband only | **retargetable** to RF |
| **AutoCkt** | RL sizing, two-stage op-amp; WSL only | retargetable, heavier |
| **Krylov / Circuit-Synthesis** | supervised sizing surrogate | retargetable |
| **ZeroSim** | performance predictor — **no inductor in its vocabulary** | **cannot model LNAs** |
| **CktGNN** | op-amp / OCB topologies only | not applicable |
| **LaMAGIC2** | power-converter topologies | not applicable |
| **AnalogSAGE** | blocked upstream (ships no data) | unavailable |
| **RoSE** | needs Cadence; `eval_engines/` is a stub | unavailable |

**ZeroSim deserves a callout.** It looked like the natural fast surrogate for
scoring generated topologies, but its device vocabulary
(`extensions/ZeroSim/configs/device_vocab.json`) is:

```
capacitor, current, gnda, nmos, pmos, resistor, vdda, vinn, vinp, voltage, vout
```

No inductor, no RF port. Its GA targets are DC gain, GBW and phase margin. It is
an op-amp model and cannot represent an LNA at all — using it as an LNA scorer
would silently produce meaningless numbers.

---

## 3. What works — verified

**ngspice does full LNA characterisation.** A probe with an inductively
degenerated cascode confirmed `op`, `ac`, `noise` and `sp` all execute. S-parameter
analysis needs port syntax (`Vin in 0 dc 0 ac 1 portnum 1 z0 50`), and noise figure
comes from `inoise_spectrum` as `10·log10(inoise² / 4kT·Rs)`. Both extract cleanly.

**`ngspice_con.exe` writes to stdout.** STATUS.md notes that the msys2
`ngspice.exe` is a GUI-subsystem binary producing no stdout, making `-o <logfile>`
mandatory. The console build at `C:\msys64\ucrt64\bin\ngspice_con.exe` does not
have this problem, which makes scripted evaluation much simpler. *(The path also
differs from the `mingw64` one implied in STATUS.md — this install is `ucrt64`.)*

**Topology reconstruction is exact.** Round-tripping dataset circuit 461 through
token sequence → union-find node rebuild → netlist reproduces the original
`461.cir` device-for-device:

```
original                        reconstructed
L0 (net8 net5) inductor    ->   LL1  n1 n0
R2 (VIN1 net8) resistor    ->   RR1  VIN1 n1
R1 (net5 VSS)  resistor    ->   RR2  n0 0
R0 (VDD VOUT1) resistor    ->   RR3  VDD VOUT1
M1 (VOUT1 net5 VSS VSS)    ->   MNM1 VOUT1 n0 0 0
```

**The structural screen separates LNAs cleanly.** Scoring ground truth with five
criteria (has inductor, inductor ratio ≥10%, has transistor, has VIN+VOUT, 2–15
devices):

| | score 5 | score ≥4 | inductor ratio | structurally valid |
|---|---|---|---|---|
| LNA circuits (461–492, 1081–1090), n=192 | **59.4%** | 62.5% | 0.188 | 100% |
| non-LNA circuits, n=18 | **0.0%** | 0.0% | 0.000 | 100% |

Separation is total: no non-LNA circuit scores above 3. The 40% of real LNAs that
miss are inductorless variants — resistive-feedback and common-gate designs, where
`has_inductor` is genuinely false (63.5% of the subset carries an inductor). That
is correct behaviour, not screen error, and it means **59.4% is the ceiling this
screen can attribute to a perfect generator**, not 100%.

**Pipeline yield is 95.2% on the full LNA set** — 40 of 42 circuits go all the way
to a working simulation. One (index 490) has no netlist in the dataset at all; one
(1081) fails with a singular matrix that `rshunt` does not rescue. See §4c.

---

## 4. What's missing — verified gaps

### 4a. Generation is unconditional

`Inference.py` seeds every run with a single token:

```python
context = torch.full((1, 1), 1003, dtype=torch.long, device=device)
```

Token 1003 is `VSS` — every training sequence is an Eulerian DFS path that starts
at VSS, so this is the only possible seed. There is no class token, no conditioning
signal, and `generate()` exposes only temperature (default 0.7) with no top-k or
top-p. You get a sample from the whole distribution, in which LNAs are 1.2%.

**Measured** over 128 sequences sampled unconditionally on GPU at the upstream
default temperature of 0.7: **0/128 score 5, 3/128 (2.3%) score ≥4**, against a
1.2% corpus share of LNAs. The model is working correctly — it faithfully
reproduces its training distribution. Generated circuits are ~3× too large
(20.0 devices vs 6.8) and carry ~12× too few inductors (ratio 0.016 vs 0.188).
Unconditional sampling is simply the wrong tool for a targeted topology class.
Full side-by-side against the conditioned arm is in §5.

### 4b. Topologies carry no bias network

Dataset circuits are textbook schematics: they show the signal path and leave
biasing implied. Reconstructing circuit 461 and simulating it gives

```
v(n0) = 12.9 mV     @mnm1[vgs] = 14.5 mV     @mnm1[id] = 7.7 uA
```

The transistor is off. Any performance number from a generated topology is
meaningless until a bias scheme is inserted. This is the single biggest obstacle
to closed-loop evaluation, and it is not something the model can fix — the
information was never in the training data.

### 4c. DC-isolated nodes break the OP solve

Nodes reachable only through capacitors have no DC path, so ngspice's operating
point goes singular. Measured over dataset LNAs, **9 of 26 failed outright**, all
with `singular matrix`.

Fix: `.option rshunt=1e12` ties every node to ground through a huge resistance —
enough for a DC solution, negligible at RF. This is now emitted by `to_spice.py`.

| | simulates | ngspice failed |
|---|---|---|
| before `rshunt` (26 circuits available at the time) | 17/26 (65%) | 9 (all singular) |
| after `rshunt`, same 26 | 27/27 (100%) | 0 |
| after `rshunt`, **full 42-circuit set** | **40/42 (95.2%)** | 1 (index 1081) |

The one residual failure is a genuinely floating sub-circuit rather than a merely
capacitively-isolated node, which `rshunt` cannot fix.

### 4d. No device values

AnalogGenie emits topology only. Every W, L, R, C and L value has to come from
somewhere else, which is why `to_spice.py` emits them as `.param` rather than
literals — it leaves a clean surface for a sizer to drive.

### 4e. Sampling is inefficient

Three compounding problems in upstream's loop:

1. **No KV cache.** Step *t* re-attends over the whole *t*-token prefix, so a full
   sequence costs O(T²) rather than O(T).
2. **No early stop.** A circuit that ends at TRUNCATE after 50 tokens still pays
   for all 1024 steps.
3. **Batch size 1.** An 11.8M-parameter model badly under-uses the hardware.

This matters more than it looks, because **LNA circuits are short**: real LNA
sequences in the corpus run **33–107 tokens**, against a 1024-token generation cap.

---

## 5. Experiment: steering generation without retraining

**Setup.** 128 sequences per arm, sampled on the RTX 3050 at the upstream default
temperature 0.7, 512-token cap, seed 1337. Arm A seeds with `VSS` (upstream
behaviour). Arm B seeds with the first 12 tokens of a randomly chosen real LNA
traversal from the corpus built by `build_lna_corpus.py`.

| | A: unconditional | B: 12-token LNA prefix | real LNAs |
|---|---|---|---|
| structurally valid | 96.9% | 99.2% | 100% |
| devices per circuit | 20.0 | **7.2** | 6.8 |
| inductor ratio | 0.016 | **0.117** | 0.188 |
| passes `lna_sized` | 41.4% | **98.4%** | 100% |
| passes `has_inductor` | 25.0% | 37.5% | 63.5% |
| **LNA score 5** | **0/128 (0.0%)** | **36/128 (28.1%)** | 59.4% |
| LNA score ≥4 | 3/128 (2.3%) | 47/128 (36.7%) | 62.5% |

Conditioning moves every distributional statistic toward the LNA subset. Circuit size lands almost exactly on target (7.2 vs 6.8 devices). The remaining
gap is inductor content: 37.5% of conditioned samples carry an inductor versus
63.5% of genuine LNAs. That is what fine-tuning should close — a prefix only
biases the opening, and the model drifts back toward the corpus mean as it
continues.

Against the 59.4% ceiling this screen assigns to the real LNA subset, 28.1% is
roughly **half of ground-truth performance, reached with no training at all**.

### Is it novel, or just copying the seed?

The obvious objection. Measured with `lna/novelty.py`, which fingerprints each
circuit by the multiset of (device type, sorted node labels of its pins):

| | conditioned | unconditional (control) |
|---|---|---|
| distinct topologies | 83/128 (64.8%) | 110/128 (85.9%) |
| identical to their seed circuit | **55/128 (43.0%)** | n/a |
| score-5 circuits | 36, of which **20 distinct** | 0 |
| distinct score-5 not matching any seed | **11/20** | — |

So conditioning does induce real copying — 43% of samples reproduce the seed
circuit outright, and diversity drops relative to unconditional sampling. But it
is not *only* copying: **11 distinct LNA topologies were produced that are not
any of the seed circuits**. Prefix length is the knob that trades hit rate against
novelty, and it should be swept rather than assumed.

### Prefix length is the knob — and it has a clear optimum

128 samples per length, batch 32, **256-token cap** (real LNA sequences are ≤107
tokens, so this loses nothing and runs ~8× faster than the 512 cap used above):

| prefix len | score 5 | terminated | inductor ratio | distinct | copies of seed | **novel distinct LNAs** |
|---|---|---|---|---|---|---|
| 4 | 11.7% | 81/128 | 0.085 | 85.2% | 3.9% | 1 |
| 8 | 24.2% | 120/128 | 0.107 | 83.6% | 21.1% | 10 |
| **12** | **40.6%** | 126/128 | 0.145 | 70.3% | 46.1% | **16** |
| 24 | 50.8% | 128/128 | 0.176 | 41.4% | 82.8% | 9 |

Hit rate and copying both rise monotonically with prefix length, exactly as
expected — a longer prefix pins the model closer to the seed circuit. The
interesting column is the last one: **novel distinct LNA topologies peaks at
prefix length 12** and then collapses, because at 24 tokens the model is mostly
reciting. Length 12 is the operating point; length 8 is the choice if diversity
matters more than yield.

Two side effects worth noting. Inductor content climbs steadily toward the real
LNA figure of 0.188 (0.085 → 0.176). And the **token cap is itself a steering
knob** — the same length-12 configuration scores 28.1% at a 512-token cap but
40.6% at 256, simply because more sequences terminate inside the window
(126/128 vs 90/128) and land in the LNA size range.

### Do the candidates actually simulate?

Running 128 conditioned samples through the full chain (screen → netlist →
ngspice), at the recommended operating point (prefix 12, 256-token cap):

| stage | count | of 128 |
|---|---|---|
| below score 5 | 76 | 59.4% |
| structurally invalid | 1 | 0.8% |
| netlist not emittable | 0 | 0.0% |
| ngspice failed | 3 | 2.3% |
| **simulates** | **48** | **37.5%** |

**48 of 52 score-5 candidates (92%) reach a working simulation** — so roughly
**48 simulating LNA candidates per 128 samples, from ~45 seconds of generation**.
The failures are singular-matrix cases that `rshunt` does not rescue: genuinely
floating sub-circuits rather than merely capacitively-isolated nodes.

Two harness bugs were found by running generated (rather than curated) topologies,
and both are fixed in `to_spice.py`:

* a circuit with no `VIN1` produced port 2 without port 1, which ngspice rejects
  outright with `incorrect port ordering`;
* a disconnected output gives `|S21| = 0` exactly, and `db(0)` aborts the run —
  now floored at 1e-30.

The first was found on a generated circuit that turned out to be a **cross-coupled
LC oscillator**, not an amplifier — correctly scored 4/5 rather than 5/5, because
it has no input port. The screen behaved as designed.

### P0 — the measuring stick, rebuilt (04-GEN §1)

The novel-distinct counts above came from a fingerprint that compared each sample
only against *its own seed* circuit, so a sample copying a *different* corpus LNA
counted as novel. `novelty.py` was rebuilt: a **Weisfeiler–Lehman graph hash**
over the device↔node bipartite graph (order-invariant — verified, one hash across
all augmentations; all 41 corpus graphs distinct), compared against **all 41**
corpus LNAs, plus a graded nearest-neighbour WL-kernel similarity so "how novel"
is a number. "Novel" = WL hash not in the corpus set. Bias scaffolding is excluded
by the naming contract.

Re-baseline of the prefix sweep under the **full frozen protocol** (256 samples =
128 @ seed 1337 + 128 @ seed 2338, batch 32, 256-token cap):

| prefix | spec-pass@L0 (wifi24) | **NDL@256** (novel distinct, wifi24) | median NN-sim | inductor ratio | copies of any corpus |
|---|---|---|---|---|---|
| 4 | 1.6% | 2 | 0.917 | 0.087 | 9.0% |
| 8 | 12.5% | 7 | 1.000 | 0.110 | 22.7% |
| **12** | **26.6%** | **16** | 1.000 | 0.141 | 45.7% |
| 24 | 39.5% | 7 | 1.000 | 0.175 | 82.8% |

NDL@256 peaks at prefix 12 (**16** under wifi24, **26** under the legacy screen —
the plan's "≈32" ball-park) and collapses at 24 (the §5 story survives the stricter
metric and the larger sample). Under the *legacy* screen the new whole-corpus NDL
(6/20/26/14) tracks the old seed-only 1/10/16/9 in shape, because with a prefix a
copy is usually a copy of the *seed*; the whole-corpus fix will bite for the
fine-tuned arms (P1/P2), which can copy a non-seed circuit the old metric would
have flattered. `median NN-sim = 1.000` among spec-passing samples is the honest
read on copying pressure: over half of LNA-shaped outputs at prefix 12 are exact
WL-copies. **This is the frozen baseline. Adoption rule for every future arm: beat
NDL@256 at equal-or-better inductor ratio.**

### P1/P2 — fine-tuning moves the curve, and shows the next lever (04-GEN §2-3)

Two fine-tunes of the pretrained checkpoint (`lna/finetune.py`, WSL GPU): **P2**
plain (bias the weights toward LNAs, sample from bare `VSS`) and **P1** a `<LNA>`
class token appended after the 1005 upstream ids (sample from `<LNA> VSS` — *no
seed prefix*). 3,531 in-training LNA augmentations + ~22% general-corpus replay,
6 circuits held out, 128-token rows, lr 3e-5, best-val checkpoint (both overfit
by ~epoch 1 — the 35-graph training set is tiny). Full 256-sample protocol:

| arm | NDL@256 (wifi24) | inductor ratio | copies | median NN-sim |
|---|---|---|---|---|
| baseline prefix-12 | 16 | 0.141 | 46% | 1.000 |
| P1 `<LNA>` token, no prefix | 16 | 0.102 | 37% | 1.000 |
| **P2 plain, bare VSS** | **24** | 0.104 | **29%** | 1.000 |

(legacy screen: baseline 26, P1 21, **P2 29**.)

**P2 beats the baseline on the headline number** — 24 vs 16 novel-distinct LNAs
(+50%), copies 46%→29% — clearing Gate G3. **P1 did its structural job** (LNAs
from no seed, copies →37%) but NDL stayed flat. Two honest caveats decide what
comes next, not a victory lap:

* **Inductor ratio dropped** (0.141 → ~0.10) on both, so neither is a *clean*
  adopt under the equal-or-better-inductor-ratio rule. The fine-tune learned the
  corpus mix (which is 34% inductorless) and under-produces inductors even more
  than prefixing did. → **P4 (inductor logit bias)** composes on top to fix this.
* **median NN-sim = 1.000** everywhere: even the fine-tuned arms recite the 35
  training graphs for >half their LNA-shaped output. The memorization ceiling is
  the 41-graph corpus itself → **P5 (archetype/template corpus)** is the lever,
  exactly as 04-GEN §6 predicted ("41 is not enough").

So the verdict is real movement (more novel, less copying) plus a precise next
step (P2 + P4 for the inductor ratio; P5 for the memorization ceiling), rather
than a finished win.

### P4 — the inductor logit bias is a weak lever; the gap is data, not decoding

`lna/decode.py` adds +λ to unused L-device logits while a sequence's running
inductor ratio is below target (P2 model, 128 @ seed 1337, wifi24; real ratio
0.188, P2 baseline 0.091):

| λ (targeted to the model's own device positions) | validity | inductor ratio | NDL | copies |
|---|---|---|---|---|
| 0 | 98% | 0.091 | 8 | 30% |
| 8 | 98% | 0.095 | 8 | 30% |
| 12 | 88% | 0.108 | 12 | 26% |
| 20 | **9%** | 0.327 | junk | 9% |

First lesson: an *un-targeted* bias does nothing below λ≈6 (the model assigns ~0
probability to an L-device at almost every position, so the nudge can't overcome
its grammar prior) and at λ=15 forces inductors everywhere (ratio 0.32) but
craters structural validity to 2% — the plan's exact "structurally valid but
electrically pointless / junk" warning. Gating the bias to positions where the
model's *own* argmax is a device token (a cheap proxy for the grammar mask)
preserves validity but only buys a small window: λ=12 lifts the ratio 0.091 →
**0.108** (NDL 8→12, copies 30→26%) at a 10-point validity cost, and λ=20
collapses again. It never reaches even the prefix baseline's 0.141, let alone
0.188.

Conclusion, matching 04-GEN's own escalation rule: **the inductor gap is a
distribution problem** (inductors are 0.8% of the pretraining corpus), and a
decoding nudge cannot manufacture what the weights disprefer without producing
junk. The lever yields to **P5** (an archetype/template corpus that actually
contains inductor-bearing LNAs). A true grammar-masked P4 might do better than
the argmax proxy, but the ceiling here is data.

### The sizing loop closes (WP-SIZE, 05-SIZING)

`lna/extract.py` (metrics from one ngspice op/sp/noise run) + `lna/size.py` (ZOAF
driver over the `.param` surface, feasibility-first via `spec.objective`, log-scale
W/R/C/L and linear bias, normalised to [0,1]^d) close the spec→sized-circuit loop.

**Anchor re-derivation** (§3.1, the single most informative test): strip
`ref24_csdeg.cir` to defaults, hand ZOAF the topology + `wifi24`. In 304
simulations it reaches feasibility on the achievable constraints and reproduces
the hand-tuned reference's gain ceiling:

| metric | ZOAF sized | hand-tuned | wifi24 | verdict |
|---|---|---|---|---|
| S11 | −10.9 dB | −21 dB | ≤ −10 | PASS |
| Idd | 4.2 mA | 2.2 mA | ≤ 5 | PASS |
| **S21** | **6.86 dB** | 6.7 dB | ≥ 12 | **FAIL** |

The lone infeasibility is not a sizer bug — S21 lands within 0.16 dB of the
hand-tuned value, i.e. ZOAF *validated itself* on a circuit whose answer is known
(extract.py, the objective encoding, the bias params and ZOAF's budget all check
out). It also surfaces a real **spec-vs-topology gap**: the single-stage reference
caps at ~7 dB (WP-REF R3 — a 50 Ω output port loads the drain) while all three
specs want S21 ≥ 12–15 dB, which needs output impedance matching (tapped tank /
buffer), not more optimizer budget. NF is gated off here (the port-noise harness
gap, R3).

**Candidate sizing, end to end** (`size.py --scoreboard`): the full pipeline —
spec → generated topology (P2 arm) → `bias.insert_bias` → ZOAF over the `.param`
surface → scored — runs on real generated circuits. A P2 candidate sizes through
234 simulations. But **0 of the sampled candidates reach feasibility**: the
gain ceiling (S21 ≤ ~7 dB) caps them all, and the larger 13-device topologies are
hard to impedance-match (best S11 ≈ −2 dB) — arbitrary generated tangles are not
matchable the way an archetype is. So the machinery is proven end to end, but
**Gate G4 needs both a gain-capable topology and cleaner (archetype-like)
candidates** — i.e. it waits on a higher-gain reference *and* P5's template corpus,
not on any missing pipeline stage.

---

## 6. Profiling

Measured with `lna/profile_generate.py`, 64 tokens per trial.

**CPU** (Windows, `analoggenie` env, torch 2.0.1+cpu, 8 threads):

| batch | tok/s | s/sequence | speedup |
|---|---|---|---|
| 1 | 19.0 | 3.368 | 1.00× |
| 4 | 52.7 | 1.215 | 2.77× |
| 16 | 62.7 | 1.020 | 3.30× |

**GPU** (WSL2 Ubuntu 22.04, RTX 3050 4 GB, torch 2.13.0+cu130):

| batch | tok/s | s/sequence | speedup |
|---|---|---|---|
| 1 | 5.9 | 10.856 | 1.00× |
| 16 | 201.7 | 0.317 | 34.2× |
| 64 | **912.9** | **0.070** | **154.8×** |

Batch-1 on GPU is *slower* than CPU — kernel-launch overhead dominates a model
this small. The win is entirely in batching: **batch 64 on GPU is ~15× the best
CPU configuration** and ~150× upstream's batch-1 default.

Cost grows roughly quadratically in sequence length, so generating only what is
needed matters: capping at LNA-scale lengths instead of 1024 is worth another
order of magnitude on top.

**Other timings:** model load 1.0 s CPU / 6.1 s GPU · adjacency build for 41 LNA
circuits 1.4 s · Eulerian augmentation is the slow stage at roughly 1 min/circuit,
producing 2–200 sequences each.

---

## 7. Test environment

**Use `ngspice_con.exe`, not `ngspice.exe`** — `C:\msys64\ucrt64\bin\ngspice_con.exe`.
Console subsystem, writes to stdout, so no `-o logfile` dance.

**Run generation on the WSL GPU, analysis on Windows.** The Windows `analoggenie`
env is CPU-only; WSL `/opt/miniconda/envs/gpu` has CUDA. WSL reaches the Windows
repo through `/mnt/c/Users/Devavrat/circuit-repro`, so no file duplication is
needed — the scripts here run unchanged on both sides.

**ngspice traps worth knowing** (all hit while building this):

| Trap | Symptom | Fix |
|---|---|---|
| `.param Ln=...` | `Expression err: ln}` | `ln` is a builtin — never name a parameter `Ln` |
| `.param LS` + element `Ls` | silent wrong results | identifiers are **case-insensitive**; prefix params (`pLDEG`) |
| `@m1[id]` in a sweep | `indexing a scalar` | `save @m1[id]` *before* the analysis |
| floating node | `singular matrix` | `.option rshunt=1e12` |
| AC-coupled port | `singular matrix` | same, or add a bleed resistor |
| one port only | `incorrect port ordering` | port numbers must run contiguously from 1 |
| disconnected output | `argument out of range for db` | floor it: `db(mag(S_2_1) + 1e-30)` |

**GPU memory is the binding constraint on the 3050.** Batch 64 at a 384-token cap
pushes the card to 3.9 GB of 4 GB and faults with `cudaErrorUnknown`. Since real
LNA sequences are ≤107 tokens, **batch 32 with a 256-token cap** is both safe and
much faster — the length cap matters more than the batch size because cost is
quadratic in sequence length.

One more trap, in this repo's own code rather than ngspice: batching must group
rows by prefix **length**, not prefix **contents**. Grouping by contents makes a
batch of distinct LNA seeds collapse into many batch-1 calls, which on GPU is
~150× slower per sequence. `generate_batch` now takes per-row prefixes directly.

**Suggested regression set** — fast, and each pins a specific invariant:

```bash
python lna/test_vocab_matches_upstream.py      # token ids still match the checkpoint
python lna/screen.py --corpus --indices 461-492,1081-1090 --per-circuit 5
python lna/pipeline_yield.py --indices 461-492,1081-1090
```

The vocab test is the important one: token ids are positional, so any drift in the
device list silently decodes the checkpoint into wrong device names.

---

## 8. Plan

### Phase 1 — steer generation toward LNAs (no retraining) — **done, works**

Implemented in `lna/generate.py --prefix lna`. Measured at **40.6% score-5 against
a 0.0% unconditional baseline** (§5). Pair it with **rejection sampling**: generate
in large GPU batches, keep only score-5 topologies.

**Recommended operating point — `--prefix-len 12 --max-tokens 256 --batch 32`.**
That is where novel distinct LNA topologies peak (16 per 128 samples). Drop to
`--prefix-len 8` if diversity matters more than yield; going to 24 buys 10 points
of hit rate but 83% of output is then a copy of the seed.

At 0.3 s/sequence, 128 samples cost about 45 seconds — so this is cheap enough to
run at much larger scale whenever more candidates are wanted.

### Phase 2 — fine-tune on the LNA subset

The corpus is built: **41 of 42 LNA circuits → 4,023 augmented sequences**
(index 490 has no netlist in the dataset). Augmentation multiplies each circuit
into many valid Eulerian orderings, which is exactly the kind of
order-invariance augmentation a sequence model needs.

Fine-tune `Pretrain.pth` on that subset at a low learning rate. This is the
highest-leverage remaining step: it moves the *distribution* instead of fighting
it at sampling time, and it should close the gap that conditioning leaves open —
inductor content, where conditioned samples reach 37.5% against 63.5% for real LNAs.

Hold out several circuits to distinguish generalisation from memorisation. Given
that 43% of conditioned samples already copy their seed, the memorisation risk
here is real and needs to be measured, not assumed — reuse `lna/novelty.py`
against the held-out set.

### Phase 3 — make generated topologies simulatable

Bias insertion is the blocker (§4b). Options, cheapest first:

1. **Rule-based**: every MOS gate with no DC path gets a bias resistor to a `VB`
   net; add `rshunt` (already done). Mechanical, and enough for screening.
2. **Template-based**: recognise common stages (cascode, common-gate,
   resistive-feedback) and apply that stage's known bias idiom.
3. **Co-generate**: extend the token vocabulary with explicit bias nets and
   retrain. Cleanest, most expensive.

Start with (1) — it unblocks measurement immediately.

### Phase 4 — close the loop with sizing

`to_spice.py` already exposes every device value as a `.param`. Drive those with
**ZOAF**, whose zeroth-order optimiser is black-box and needs only an objective.
Replace its baseband metrics with an RF objective built from the harness:

```
maximise   S21(f0)
subject to NF(f0) < target,  S11(f0) < -10 dB,  Idd < budget
```

Roughly 4–8 parameters per candidate topology, which is well inside what ZOAF
handles (its examples run 10 and 22 parameters).

### Phase 5 — efficiency, if throughput binds

Add a KV cache to `Models/GPT.py`. Turns O(T²) into O(T) and would compound with
batching. Only worth it once phases 1–4 are producing candidates faster than they
can be evaluated.

---

## 9. Tooling added

All under `lna/`, all runnable on Windows or WSL:

| File | Purpose |
|---|---|
| `genie_common.py` | vocabulary, model loading, **batched sampling with early stop and prefix conditioning** |
| `test_vocab_matches_upstream.py` | guards that token ids still match the checkpoint |
| `build_lna_corpus.py` | runs AnalogGenie preprocessing over the LNA subset only |
| `topology.py` | token sequence → devices/nodes; LNA structural screen |
| `screen.py` | scores corpus or generated sequences; used to calibrate the screen |
| `generate.py` | sampling driver, unconditional or LNA-conditioned |
| `to_spice.py` | topology → parameterised ngspice netlist with S-param + noise setup |
| `pipeline_yield.py` | end-to-end topology → netlist → simulation yield |
| `novelty.py` | are conditioned samples novel, or copies of their seed? |
| `profile_generate.py` | batching/throughput profiler |

`build_lna_corpus.py` deliberately does not patch upstream: AnalogGenie's
preprocessing hardcodes the range `1..3502` in a module-level driver, so the script
execs only the function definitions above that driver and supplies its own loop.

---

## 10. Reproducing

```bash
# 1. build the LNA corpus (slow: Eulerian augmentation, ~1 min/circuit)
python lna/build_lna_corpus.py --stage all

# 2. confirm the screen still separates LNAs from everything else
python lna/screen.py --corpus --indices 461-492,1081-1090 --per-circuit 5 --label LNA
python lna/screen.py --corpus --indices 14,17,20,22 --per-circuit 5 --label non-LNA

# 3. end-to-end pipeline yield on known-good topologies
python lna/pipeline_yield.py --indices 461-492,1081-1090

# 4. generate (GPU strongly preferred)
wsl -d Ubuntu-22.04
/opt/miniconda/envs/gpu/bin/python lna/generate.py --n 128 --batch 64 \
    --device cuda --prefix lna --prefix-len 12 --out lna/out/cond12

# 5. screen what came out
python lna/screen.py --generated "lna/out/cond12/seq*.txt"

# 6. simulate a candidate
python lna/to_spice.py lna/out/cond12/seq0003.txt -o lna/work/cand.cir
C:/msys64/ucrt64/bin/ngspice_con.exe -b lna/work/cand.cir
```

---

## 11. Phase 2 — learned critic (plans2), Stage-0 + Stage-1 baseline

Phase 2 turns "generate → size" into "generate → **predict feasibility** →
search → size", minimizing SPICE by filtering candidates before a 5-minute
sizing run. Stage 0 built the data plumbing; Stage 1's baseline gives the first
measured verdict on whether a pre-SPICE surrogate is even possible here.

**Stage 0 — the label store now exists and is full enough to train on.**
Every ngspice/ZOAF result is training data (`lna/datastore.py`, append-only
JSONL). Backfilled + one overnight campaign → **173 L2 rows** (per-metric
*margin* labels, not a feasibility bool — R1), 41 L1 rows, 33.7k point rows.
Two enablers landed with it: the **tapped-C gain reference**
(`ref24_tapped.cir`) sizes to full feasibility (S11 −20, S21 18.6 dB, Idd 3.1
mA, NF 2.0 dB) — **Gate G4 closed by hand**, and the store's only feasible row;
and the **series-Rs NF harness** (finding #7) — the S-parameter port is
noiseless, so NF went *negative* with gain (corpus 464: −4.5 dB); a real series
source resistance fixes it (golden-locked to 3.01 dB, `extract.py --selftest`).
Label noise is real and topology-dependent: repeat-probe **σ(S21) = 0.32 dB**
(most topos ~0, one pathological corpus LNA swings 3.5 dB between ZOAF seeds).

**Stage 1 — the baseline surrogate clears Gate C1 within-distribution, and
does not across the shift that matters.** `lna/critic.py` predicts the stored
S11/S21/Idd margin vector from hand features (graph stats + hand-rolled WL
subtree vector); feasibility is *computed* from margins. On snapshot `v1-train`:

| split | model | ρ(S21) | enrich@20% | Gate C1 |
|---|---|---|---|---|
| family-holdout | ridge | **0.68** | **2.44×** | **PASS** |
| family-holdout | WL-kNN | 0.65 | 2.44× | PASS |
| source-shift (corpus+ref→generated) | ridge | 0.34 | 1.47× | fail |

So a *cheap* model predicts achievable S21 margin on held-out topology families
(ρ ≈ 0.68, p < 0.01 at n=22) and enriches near-feasible candidates 2.4× — the
pre-SPICE filter concept is real. But on the **source-shift split** — train on
corpus/references, test on generated arms, a rehearsal of exactly the drift
critic-guided search induces — it drops to ρ = 0.34 / 1.47×. That gap is the
honest number for the critic's actual job (ranking generated candidates), and
closing it is the point of the GNN, the P5 templates (topology diversity), and
uncertainty-gated search. WL-kNN is "embarrassingly strong" exactly as
02-CRITIC §2 warned, so the GNN must beat it, not just the trivial floor.

**Update — P5 templates landed; Gate C0 met; the source-shift gap is not a data
problem.** `templates.py` mints hand-designed archetypes as valid token
topologies (reusing AnalogGenie's `build_connection_matrix → dfs_all_paths`,
round-trip-exact on real 461): **92 distinct** (88 narrowband / 4 wideband) CS
(±gate-L/±degen/±Cex/±cascode/±buffer) × {R, tank, tapped-C} loads + CG +
resistive-feedback. Labeling the 88 NB archetypes took the store to **264 L2**,
stratum T to ~35% — **Gate C0's ≥150-row + ≥25%-T fractions are met** (σ measured).
The tapped-C family is densely *near*-feasible (S21 up to 12.8 dB, most rows 3/3
margins > −1 scale unit) though none clears *full* feasibility under
all-params-free ZOAF (curated sizing, as the tapped ref needed, is the lever for
a true feasible token class). Re-eval on `v2-train` (261 rows, σ=0.61):
family-holdout **WL-kNN still clears C1** (ρ_S21=0.77, 2.06×); but the
**source-shift split did *not* improve** (ρ≈0.22–0.28) — clean archetype
diversity does not make the generated arms predictable, so the gap is the
generated *distribution* itself, not training diversity.

**GNN verdict (`critic_gnn.py`, plain-torch MPNN, CPU under the analoggenie env
— the graphs are too small to need the GPU).** Bipartite device↔net message
passing, pin-role-specific maps, 5-member ensemble. On v2-train (σ=0.61; ρ wobbles
~±0.02 run-to-run from CPU nondeterminism):

| split | GNN | best baseline |
|---|---|---|
| family-holdout (the **C1 gate**) | ρ_S21≈0.65, enrich 1.18 | **WL-kNN 0.77 / 2.06** |
| source-shift (diagnostic) | **ρ_S21≈0.34, enrich 1.6** | WL-kNN/ridge 0.28 / 0.22 |

Two clean results. (1) On the C1 gate the GNN **loses to WL-kNN** — which
memorizes the corpus near-duplicates exactly as 02-CRITIC §2 warned — so per the
de-scope ladder **WL-kNN ships as critic v1** (the brief prefers a GNN; it was
tried and beaten on the gate). (2) On the source-shift diagnostic the **GNN wins**
(0.34 vs 0.22–0.28): the graph inductive bias is the only thing that generalizes
better to the peculiar generated distribution — but it still doesn't reach C1's
0.5. Its ensemble uncertainty is usably calibrated (std↔|err| ρ≈0.3–0.5), which
03-SEARCH's trust gate can use. **Gate C1 is met on held-out families; no model
reaches it under the source-shift, for any architecture** — confirming the gap is
the generated distribution, not the surrogate.

**Stage 2 rung-1 — controlled best-of-N rerank (`search.py --rerank`).** Run
retrospectively on the 142 already-sized generated candidates (real SPICE, §4
rule 4): critic trained on non-generated rows only, rank the pool, "size top-30"
= their true margins, control = 30 random. Pool near-feasible base rate 0.27:

| arm | near-feasible @top-30 | random | **enrichment** | ρ_S21 |
|---|---|---|---|---|
| WL-kNN | 11 | 8 | 1.37× | 0.28 |
| **GNN** (mean−σ) | 14 | 8 | **1.74×** | 0.34 |

**Gate S1 (≥2×) not cleared** — the in-vivo confirmation of the source-shift
result. But it is coherent and not worthless: the GNN's better OOD ρ turns into
better selection (1.74× vs 1.37×, near the bar), sizing its top-30 finds 74% more
near-feasible designs per equal SPICE budget, and it surfaces the pool's single
best-gain candidate. Per the de-scope ladder, search *waits* on S1 while rerank
still cuts sizing waste; realized-vs-predicted ρ feeds the next critic retrain.

The lever every failed gate pointed to is the **generator**: the generated arms
are a distribution nothing ranks to 2× because the generator, fine-tuned on 41
corpus LNAs, memorized ~35 graphs (NN-sim 1.000). So P5 rebuilds that distribution.

**WP-GEN P5 — template-augmented, class-token fine-tune (`finetune.py --arm p5`)
works, decisively.** Mix the corpus LNAs (tagged NB/WB by inductor) with
Eulerian-augmented `templates.py` archetypes (1696 rows) + `<OTHER>` replay, plus
`<LNA_NB>`/`<LNA_WB>` class tokens; sample from `<LNA_NB> VSS`. On the frozen
NDL@256 protocol:

| metric | NDL baseline | P2 (prev best) | **P5** |
|---|---|---|---|
| NDL@256 (novel distinct LNAs) | 16 | 24 | **60** |
| median NN-sim to corpus | — | 1.000 | **0.574** |
| inductor ratio | — | ~0.10 | **0.179** |

The **memorization ceiling is broken** (NN-sim 1.000 → 0.574 — output is no longer
near-duplicate of training graphs), **NDL is 2.5× P2 / 3.75× the baseline**, and
the **inductor ratio is restored** to near the corpus's 0.20 (P1/P2 had regressed
it). 99.6% valid, 98.8% terminated, 57.4% clear the L0 screen (near the 59.4%
ceiling). Per the adoption rule (beat NDL@256 at ≥ inductor ratio), **P5 is the
new best generation arm**, and it trains fast (overfits by epoch ~1 on this small
data — best-val checkpoint is early; CPU-free once `templates.py --emit-train`
runs). The GNN training also runs on this machine's GPU under WSL (verified).

**Loop closed — the generator is the bigger lever, and the win is in the
distribution, not the ranking.** Sized 26 novel P5 samples and reran
`search.py --rerank` splitting the generated pool into old(P1/P2) vs p5, ranked by
the *same* critic (trained on non-generated). On `v3-p5` (σ=0.77):

| pool | base rate near-feasible | enrich@20% (GNN) | ρ_S21 |
|---|---|---|---|
| old (P1/P2) | 0.27 | 1.60 | 0.35 |
| **p5** | **0.62** | 0.97 | 0.18 (gnn) / 0.40 (knn) |

The decisive number is the **base rate: P5 62% vs old 27% near-feasible** — the
memorization-broken generator yields **~2.3× more near-feasible designs per SPICE
budget, which exceeds what critic-rerank ever delivered (1.74×)**. Fixing the
*distribution* beats filtering a bad one. P5's rerank enrichment falls to ~1.0
precisely *because* the pool is already good — the base-rate ceiling leaves the
critic little to enrich, so selective value drops on a good distribution (as it
should); ρ is mixed/noisy at n=26, σ=0.77. So the program yardstick
(SPICE-per-near-feasible-design) improved ~2.3× — from the generator, exactly as
the source-shift analysis predicted, now confirmed end-to-end.

**★ GATE G4 CLOSED BY GENERATION — the phase's headline.** Boosted multi-seed
sizing (`g4_search.py`: 4 seeds × an anchor-strength ZOAF budget, on the 6 closest
P5 candidates) landed the first **novel generated topology sized to full
feasibility** vs wifi24: **seq0240** (8 devices: 2 NMOS + 1 L + 2 R + 3 C, wl_hash
novel) → **S11 −11.9 dB, S21 12.6 dB, Idd 1.19 mA** (feasible; NF advisory). It was
the naive single-seed sizer, not the topology, that had capped these — the same
all-free-ZOAF landscape trap the tapped reference hit; more seeds/budget on the
promising few found the feasible basin (seq0240 went S11 −1.0→−11.9 while holding
S21 ≥ 12). Several others came within one constraint (seq0009: S11 −14.6 / S21
14.1, Idd 5.6 just over). Store now has **2 feasible** designs — the tapped
reference (by hand) and seq0240 (by generation). The design lives in
`topo_labels.jsonl` (its tokens), so it survives though the seq file is gitignored.

This is the end-to-end proof of the phase thesis: **P5's better distribution +
critic/metric-guided selection of the closest candidates + a modest extra sizing
budget = a novel feasible LNA the pipeline designed itself.**

**Stage 3 — the self-improvement loop is SET UP (`loop.py`, 04-SELF-IMPROVE).**
It is cadence, not construction; Stages 0-2 built every moving part, so this wired
the governance + the last mechanism:
* **Tripwires (5, numbers not vibes):** feasible-rate compression, repeat-probe σ
  drift, frozen-NDL@256 drop, WL-family collapse (each with a scripted response);
  critic-holdout regression is the automatic adopt-only-if-better gate. Iteration-0
  baseline pinned (NDL 60 / families 59 / σ 0.73); all quiet.
* **Headline curve:** SPICE-minutes per feasible *novel* design — **967 at
  iteration 1** (1 design, seq0240). This is the number loop turns must bend down.
* **Loop B (generator ← winners) built + validated:** `templates.py --emit-winners`
  (feasible + top-quartile near-feasible token topologies from the store, TRUE
  SPICE only, Eulerian-augmented via `topo_to_netlist`, round-trip WL-exact) →
  `finetune.py --arm p5 --winners` (warm-start ft_p5.pth → ft_p5_v2.pth, dataset
  6011→6780 rows). Loop A (rerank) exists; Loop A acquisition-driven picks and the
  full auto-orchestrated `--iterate` execution are the remaining refinements.

**Iteration 2 ran (a full loop turn) — the self-improvement *mechanism* works, but
this turn did not bend the curve.** Loop B expert-iterated the generator on its own
winners (`finetune --arm p5 --winners`, warm-start ft_p5.pth→ft_p5_v2.pth), then
labelled 35 v2 candidates and reranked. What improved, measured:
* **Generator: better on every axis, no mode collapse** — NDL@256 60→73,
  terminated 98.8%→100%, inductor ratio 0.179→0.209; all tripwires quiet.
* **More critic-rankable** — GNN ρ(S21) on the v2 pool = **0.59** (vs v1 0.24, old
  0.33), *clearing* the C1 0.5 bar on that pool (noisy, n=35). Base near-feasible
  rate 57% (~2× old's 27%).
What did not: **no new feasible design.** `g4_search` (2 passes, 10 seeds total on
the 2 closest) kept landing 2/3 constraints with the third barely off (seq0009:
S11 −9.3 / S21 12.4 / Idd 5.25; seq0220 similar) — these topologies sit on the
feasibility boundary with a tight/empty feasible region under all-free ZOAF (seq0240
got there; these don't). So **feasible-novel stays 1 and the curve went 967→1093
SPICE-min/design (worse)** — an honest non-improving iteration (recorded as such;
04-SELF-IMPROVE §5). Also: repeat-probe **σ climbed 0.32→1.02** over the session
(multimodal-sizing topologies); still < the 2× drift tripwire but the next thing to
address (it caps ρ and adds label noise).

**★ WP-LAST-MILE (06-LAST-MILE) — curated sizing closes the conversion gap; the
curve bends (Gate I3).** The iter-2 diagnosis was right: the broken funnel stage is
near-feasible → feasible, and all-free ZOAF's multimodal landscape (the same thing
σ measured) is why. **§1 curated final-mile sizing** (`size.match_devices` +
`_curate`; `g4_search --curated`) fixes each candidate's input-match passives at
their prior best and sizes only gain/bias/current — and it **converted 2 of the 3
closest near-misses to fully feasible on seed 1**, where all-free ZOAF had failed
them with 10 seeds:
* **seq0009** (v1): S11 −10.9 / S21 12.8 / Idd 4.00 — feasible.
* **seq0220** (v2): S11 −13.8 / S21 12.6 / Idd 2.46 — feasible.

So **feasible-novel designs 1 → 3** and the **headline curve 1093 → 367
SPICE-min/design (a 2.6× bend, Gate I3 met)**; all tripwires quiet. **§5 funnel
instrumentation** makes it legible: near-feasible rate 0.49, **90 candidates one
constraint off** (a large convertible pool — curated should close many), 6.7
SPICE-min/near-feasible, top-10 median violation 0.14→0.11. Labels tagged
`recipe: curated-v1` (never pooled with all-free). **§2 boundary polish**
(`size.polish`, min-margin ascent) is coded but a start-point-reconstruction bug
(run_and_extract None at a stored best_params) blocks it — implemented, not yet
validated. **§4 (σ best-of-3 relabel)** still open — σ = 1.02, capping ρ.

**Open (next):** run `g4_search --curated` across the 90 one-constraint-off pool
(more feasible designs, decisive curve bend); debug §2 polish; **§4 σ** best-of-3
relabel before the next critic retrain; then the exit criterion (two consecutive
improving turns) is within reach. Plus `<LNA_WB>`, Loop A acquisition, the 02
critic-interface leftovers.

**Cross-spec benchmark (`benchmark.py` → `lna/data/benchmark.md`) — where the
pipeline stands under *different requested constraints*.** Sized the best candidate
topologies against three specs of rising/rotated difficulty:

| spec | constraints | feasible | binds when not |
|---|---|---|---|
| wifi24 | S21≥12, Idd≤5, NF≤2.5 | **6/6** | — (curated solves all) |
| gps-l1 | S21≥**15**, Idd≤**3**, NF≤1.8 | **0/6** | **S21 (5)**, Idd (1) |
| wideband-sdr | broadband S11, ripple≤2 | **0/6** | **S11 (4)**, ripple, S21 |

Reads straight into next steps: **wifi24-class is solved** (sizing is not the
bottleneck); **gps-l1 is gain-limited** (cascode+tapped tops out ~12–14 dB, needs
higher-gain archetypes for 15 dB @ 3 mA); **wideband-sdr is match-limited**
(narrowband LC match can't hold 50 Ω over the band, needs wideband/resistive-
feedback archetypes). The two levers to broaden capability are both **topology
diversity** (templates.py + P5 generator: gain-boosted + wideband-match families),
not the sizer. A broad `--curated --top 15` sweep confirmed the 3 feasible designs
but added no new distinct ones (many stall at S11 −10.0 / S21 11.9 — the §2-polish
sweet spot); repeat-probes don't inflate the curve now (dedup by wl_hash).

**Curve honest state:** 3 distinct feasible novel designs, **370 SPICE-min/design**
(967→367→370; the last sweep was breadth, not new designs). Median top-10 violation
0.007 — a wall of candidates a hair from feasible, awaiting §2 polish / more seeds.

**★ STAGE 3 PHASE EXIT — the self-improvement loop is now an operating mode
(07-EXIT §1, iter-4).** The exit turn debugged and closed the polish path, then
converted the closest wall:
* **§1a — the polish start-point bug, root-caused and fenced.** `size.polish`
  hit `run_and_extract → None` at a stored `best_params` because `g4_search`
  re-parsed the candidate's `token_file`, and several P5 arms emit same-named
  `seq*.txt` for *different* topologies — so the parsed graph didn't match the
  stored params (undefined-parameter crash). Fix: reconstruct the topology from
  the row's **own** `graph.tokens`, never the file. Fence: **`size.replay_ok`**
  — before any polish, re-evaluating a stored `best_params` must reproduce the
  stored metrics within repeat-probe σ, else the row is quarantined (label-
  provenance fault, not polished). `size.log_l2_result` records a polish/curated
  win exactly as found (no re-size), re-enriching physical NF.
* **§1c — convert the wall, polish-first.** `g4_search --curated --polish`
  now tries **min-margin ascent from the stored best point first (~100 sims,
  cheap)** and only falls back to curated ZOAF if that doesn't close it — so the
  sweep costs a fraction of the all-free passes that diluted the curve before.
  Over the closest ~23 near-misses (sorted by total violation ascending, wl_hash
  dedup so converted topologies aren't re-polished): **3 new distinct feasible
  novel designs** — **seq0079** (S11 −15.6 / S21 13.5 / Idd 3.63), **seq0086**
  (S11 −12.6 / **S21 driven 7.3→15.3** by ascent / Idd 1.90), **seq0046** (S11
  −11.0 / S21 13.3 / Idd 3.61). **feasible-novel 3 → 6; headline curve 367 →
  186.6 SPICE-min/design (IMPROVING).**
* **Honest read on the "90-candidate wall."** Only the **closest ~5** were
  polish-convertible; past those, candidates sit 2–3 constraints off (S11 ≈ −1
  to −2 dB vs −10 needed, or S21 ~11.9 at Idd ~5) — real **topology/match-network
  gaps**, not sizing slack. So the funnel's `one_constraint_off_count=90`
  **overcounts convertibility** (it flags anything within one *normalized* margin,
  including designs a match network away). The convertible pool on wifi24 is now
  effectively drained — exactly the plan's prediction that further wifi24
  feasibles stop measuring progress.
* **Exit criterion — MET.** Two consecutive improving turns with all tripwires
  quiet: **iter-3 1093→367** (curated last-mile) and **iter-4 367→187** (polish),
  tripwires quiet both (feasible-rate 0.50, ndl@256 60, wl-families 59;
  **σ-drift 1.27 < the 2× bar but climbing** — the one thing to fix before the
  next critic retrain, §1b/§4 deferred into WP-BROADEN). **Stage 3 is declared an
  operating mode**, not a one-shot. Store: **7 feasible (6 novel generated + the
  tapped hand reference)**.

**Scoreboard rotation (07-EXIT preamble).** wifi24 is a solved class; its curve
no longer measures progress. From here the phase headline is the **cross-spec
benchmark table** (`benchmark.md`): wifi24 6/6 · gps-l1 0/6 · wideband-sdr 0/6.
**Next phase = WP-BROADEN (§2):** gain-boosted archetypes (two-stage CS→CS,
current-reuse) to unlock gps-l1's 15 dB @ 3 mA, and wideband/resistive-feedback
archetypes (activate `rfb_lna`/`cg_lna`, shunt-peaked loads, `<LNA_WB>` end-to-
end, WB template count 4→≥30) to unlock wideband-sdr's broadband match — both are
**topology work (`templates.py` + P5-v3), not sizing**, exactly as the benchmark
diagnosed. Gate B1: ≥1 feasible on each of gps-l1 and wideband-sdr.

**★ WP-BROADEN (07-EXIT §2) — constructors landed; the gps-l1 gain wall is BROKEN;
Gate B1 confirmed a generator job, not a sizing job.** Added the topology families
the benchmark named as missing (`templates.py`, 92→118 archetypes):
* **Gain-boosted (nb):** `cs_cs_lna` (two-stage CS→CS, stage-1 resonant load →
  coupling cap → stage 2), `current_reuse_lna` (complementary NMOS+PMOS sharing one
  bias current, PMOS wired end-to-end through the pipeline). 20 new archetypes.
* **Wideband (wb):** `rfb_lna` + buffer/cascode options, `_add_load` shunt-peaked
  variant. The wideband screen (`max_inductors`, `match_plausible`) keeps this
  family inductorless by construction — correct engineering (feedback match, not
  LC), so it caps at 10 distinct wb archetypes rather than the aspirational ≥30.

**Gate-B1 viability, measured (all-free ZOAF + polish + a 729-point match grid):**
* **gps-l1 gain wall — broken.** `cs_cs_lna` reaches **S21 17.5 dB @ Idd 2.76 mA**
  (both hard constraints — S21 ≥ 15, Idd ≤ 3 — met), where single-stage
  cascode+tapped topped ~14 dB. This is the structural blocker the benchmark
  diagnosed, removed. `current_reuse_lna` runs very lean (Idd ~2.4–2.9 mA) but the
  complementary gm didn't stack enough gain in-range (S21 ~9) — the two-stage is
  the gps-l1 gain path.
* **But the input match won't co-close.** Across **all-free ZOAF (4 seeds — which
  *is* joint gain+match co-sizing under a feasibility-first objective), local polish,
  and a grid over just the match devices** (Cin/Lg/Ls, 9× each = 729 points holding
  the gain point), **S11 never drops below ≈ −1 dB while S21 holds ≥ 15.** The
  gain-rich basin and the matched basin don't overlap for these hand-built input
  networks at 1.58 GHz / 15 dB (higher gain ⇒ bigger device ⇒ larger Cgs ⇒ harder
  match — the real reason gps-l1 is the hard spec). **wideband-sdr** likewise:
  `rfb` gets ripple < 2 and Idd < 8 but S21 ~8 unmatched; `cg` matches (S11 −15)
  with no gain. No simultaneous gain+match+ripple point found.
* **Conclusion (the wifi24 lesson, again):** hand-built templates + generic sizing
  give the right *structure* but not the sizeable *parameterization* — the wifi24
  feasibles came from the **P5 generator** + curated sizing (good match prior), not
  from sizing raw templates. So Gate B1 closure is the plan's intended sequence:
  **label these families vs both specs → P5-v3 fine-tune (`<LNA_NB>`/`<LNA_WB>`) →
  generate variants → curated sizing with the generator's match as prior.** The
  constructors are the necessary input to that; the generator is the closer. Gate B1
  remains open, with the gain blocker measurably removed and the path narrowed to
  one GPU-dependent step.
* **Tooling fix (real, committed):** `size_topology` now returns `best_params`
  (`decode(best_x)`) — it was logged but never returned, so every
  polish/curate-from-a-sizing-result path silently ran on `None`. This is why the
  first close-the-gap pass reported no movement past the all-free point; the fix
  makes the "size → polish/curate from here" flow actually work.

**★★ WP-BROADEN Gate-B1 (07-EXIT §2, overnight P5-v3 run) — gps-l1 CLOSED by the
generator; the thesis holds a second time.** Ran the full intended sequence as five
checkpoints (`lna/BROADEN-PROGRESS.md` has the per-step log):
* **P5-v3 fine-tune + generation (the lever).** Rebuilt `templates_train.json` with
  the 118-archetype set (two-stage + wideband families in), warm-started `ft_p5.pth`
  → `ft_p5_v2.pth` (winners), best val 0.2300 @ epoch 1. Sampling: **narrowband
  NDL@256 73→100** (families 99, 256/256 terminated) — the expanded templates lifted
  diversity by another third — and a **new wideband channel, NDL@256 35** (255/256
  terminated). All tripwires quiet; adopt-only-if-better cleared, P5-v3 adopted.
* **★ Gate B1 on gps-l1 — MET.** Sizing the generated narrowband pool vs gps-l1
  (light scan → polish-first) yielded **2 novel feasible generated LNAs**:
  **seq0089** (S11 −13.1 / S21 15.0 / Idd 2.88) and **seq0215** (S11 −14.4 / S21 15.4
  / Idd 2.94). Decisive detail: seq0089 was generated **matched but gainless**
  (S11 −13.7 / S21 2.4), and polish drove **S21 2.4→15.0 while holding the match** —
  precisely the co-sizeable input network the hand-built two-stage templates lacked
  (their S11 wouldn't leave ≈0 across ZOAF + a 729-point match grid). **The generator,
  not the sizer, is what supplies matchable parameterizations** — the same lesson P5
  taught on wifi24 (memorization ceiling), now re-confirmed on gps-l1 (gain wall).
* **⚠ Honest caveat.** Feasibility is on the **gated** constraints (S11/S21/Idd).
  NF is gated off pipeline-wide (port-noise harness gap, WORKLOG R3); these two
  designs' enriched physical NF is **~4.5 dB, well above gps-l1's 1.8 dB target**.
  So the identified *gain-limit* blocker is genuinely gone and the pipeline now
  designs gps-l1-band match/gain/current-feasible LNAs — but gps-l1's demanding
  noise figure is unmet and un-optimizable until the NF harness lands. Fixing the
  port-noise harness is now the highest-value pipeline gap (it gates real gps-l1).
* **wideband-sdr — still 0.** The generated wb pool's closest sized to S21 ~9.8
  (unmatched) or matched with no gain; gain+match+ripple didn't co-close. The wb
  training signal is thin (222 template rows, 0 winners, 10 archetypes) — the wb
  family needs more archetypes (2-stage rfb / noise-cancelling CG-CS) and wb winners
  before its generation channel is as strong as narrowband's.
* **Gate B1 verdict: half-closed** — MET on gps-l1, open on wideband-sdr. Store is
  now multi-spec (gps-l1 / wideband-sdr / wifi24), 13 feasible rows across specs.

## 12. Phase 3 — WP-DHRUVA blind-protocol campaign (paper-target spec ladder)

Goal (plans2/08-DHRUVA-GOAL.md): reach a published multi-band GNSS-receiver LNA's
performance numbers **without any knowledge of its circuit** — a fair test of
whether generator + critic + curated sizing can *find* the topology class, not
copy it.

* **Blind protocol — logged at campaign start (acceptance item 1).** The paper's
  PDF is not in the repo; the only allowed excerpt is its spec numbers. This
  session added **no paper-derived circuit content** anywhere (specs, code,
  comments, FINDINGS). Rule 2: `templates.py` may grow only families already in
  the archetype set, or generic textbook blocks chosen *without* the paper, tagged
  provenance **`recipe: blind-v1`**. Rule 3: a two-turn Gate stall is recorded and
  stopped — unblinding is the **user's** decision, not the executor's.
* **WP-D0 — spec plumbing (this entry).** Added four tier-1 specs
  `dhruva-{l5,l2,l1,s}` (bands 1.176 / 1.228 / 1.575 / 2.492 GHz; S21 ≥
  22.3 / 22.3 / 25.4 / 30 dB at f0; Idd ≤ 13 mA). NF (2.5–3.5 dB) and IIP3 are
  carried `status: unsupported` (tier-2/tier-3 — pending the NF harness and a
  two-tone/HB simulator).
* **The over-band match, for free.** Tier-1's defining constraint — **S11 ≤ −10 dB
  held across 1.1–2.5 GHz** (not just at f0) — maps onto the extractor's existing
  `s11_max_db` (worst-case over `[f_lo,f_hi]`, already computed for wideband-sdr).
  Setting `f_lo=1.1e9, f_hi=2.5e9` and constraining **`s11_max_db: {max: -10}`**
  gives over-band enforcement with **zero harness change** — verified: a design
  matched at f0 (−15) but −3 at a band edge is correctly rejected on `s11_max_db`.
* **Rail note.** Paper rail is 1.2 V; the sizer fixes VDD=1.1 V, so the specs
  document `vdd: 1.1` (the evaluated condition). Idd ≤ 13 mA is generous and not
  expected to bind (08 §2).
* **Gate D0 — evaluable end-to-end.** Smoke: a wifi-class candidate sized vs
  `dhruva-l1` runs the full SPICE path and reports `s11_max=−0.5` / `s21=10.6`
  (infeasible, binding on both `s11_max_db` and `s21_db`) — the honest baseline
  (current single-stage families are nowhere near broadband-match + ≥25 dB gain,
  exactly the hard pair 08 §5 flags). `benchmark.py` gains `--seeds`/`--budget`
  knobs and grows four `dhruva-*` columns as the extended scoreboard.
* **WP-D2 in progress — the s11_max wall and how it broke.**
  * `emit_winners` generalized to **multi-spec, correct-frequency** (per-spec
    selection from rows sized vs that spec; class token = band class). Committed.
  * Labeled the existing archetype set vs `dhruva-l1` (recipe `blind-v1`): **20
    single-stage rows, 0 feasible, all binding on `s11_max ≈ 0`** — the input match
    holds at *no* frequency across 1.1–2.5 GHz. Diagnosis: the broadband-match
    structure lives only in the inductorless **wb** channel, but `dhruva-l1`
    (inductor-required) samples **nb** — so no nb topology carried both match and
    tuned gain.
  * **Acted (blind rule 2): added a generic textbook `rfb_cs` family** — stage-1
    resistive shunt-feedback (S11 held over band) → stage-2 tuned/tapped CS (gain
    peaked at f0). 8 variants, archetypes 118→126, all `nb`, tagged `blind-v1`.
    Chosen from the *measured* failure mode, not from any paper.
  * **★ The wall broke.** Hand-sizing rfb_cs vs `dhruva-l1`:
    `rfbcs_tank_cc1_bf0` → **s11_max −8.9 dB** (near the −10 target, vs ≈0 for every
    single-stage family); `rfbcs_tank_cc0_bf1` → **S21 27.0 dB ✓ + Idd 9.2 mA ✓**,
    only s11_max (−5.9) short. So the RFB input can hold the band to ~−9 and the
    tuned+buffered stage can exceed 27 dB — the pieces exist; a single *fixed*
    archetype trades match against gain (structural), so co-closing all three is a
    generator job (the gps-l1 lesson: the generator supplies the co-sizeable hybrid
    the hand template can't).
  * **Generator route (P5-v4, P5-v5):** re-fine-tuned on the rfb_cs-bearing
    templates + multi-spec winners; pools carried 58–59 rfb-like candidates.
    Curated-sizing the pools reached best viol 0.318 (single-seed) / the archetype
    reached **viol 0.065** under heavy multi-seed (`rfbcs_tapped_s2_bf0`: s11_max
    **−10.2 ✓**, S21 23.8, only **1.6 dB gain short**).
  * **The remaining barrier, precisely characterized.** A stage-1 cascode
    (`cascode1`) lifted gain but *wrecked* the match (it sits inside the feedback
    loop); moving it to **stage 2** (`cascode2`) decoupled them (match −10.2 with
    gain 23.8). But across **~135 archetype configs + P5-v4/v5 generated pools +
    hundreds of multi-seed sizings**, the 2-stage rfb_cs Pareto front came within
    ~1.6 dB of the feasible corner and would not cross: forcing ONE tuned stage to
    ~20 dB loaded the stage-1 feedback match. (match ≤ −10 ⟹ gain ≤ ~24; gain ≥
    25.4 ⟹ match ≥ ~−6.)
  * **★★ Gate D1 MET — feasible dhruva-l1.** The fix implied by the barrier:
    **split the gain over two tuned stages** so neither overloads the stage-1
    match. Added generic blind-v1 **`rfb_cs3`** (rfb input → tuned CS → tuned CS,
    5 screen-passing variants, archetypes 130→135). `rfbcs3_tank_cc21_bf0` sizes to
    **s11_max −11.2 dB ✓ / S21 37.8 dB ✓ / Idd 12.93 mA ✓ — feasible** (wl
    `3ebaf08f9`, recipe `blind-v1`). The 3-stage headroom cleared 25.4 dB with room
    to spare while the resistive-feedback input held the 1.1–2.5 GHz match. (Idd
    12.93 is tight vs 13; the 37.8 dB gain has ~12 dB of slack to trade back for
    current margin.) Reproduction artifacts: `lna/repro/` (netlist + params +
    `recreate_dhruva_l1.py`).
  * **★ Honest attribution (blind protocol integrity).** The feasible *topology* is
    the **assistant-authored** generic-textbook archetype `rfb_cs3` — designed under
    rule 2 (no paper), guided by the automated sizer's measurements, NOT discovered
    by the P5 neural generator (its P5-v4/v5 pools reached only viol 0.318). What
    the automated pipeline supplied here is the **device sizing** (ZOAF + polish) and
    evaluation. So this is "assistant-designed topology (blind, generic) + automated
    sizing," not an autonomous generator result. A *generated* dhruva-l1 feasible
    (P5-v6 on the rfb_cs3-bearing set) is the outstanding stronger claim.
  * **★★ Gate D2 MET — one family feasible on all four bands (the reconfigurable
    essence).** The *same* topology `rfbcs3_tank_cc21_bf0` (wl `3ebaf08f9`), only
    device values differing per band, is feasible on all four dhruva specs (recipe
    `blind-v1`, each logged):

    | band | f0 | s11_max | S21 (target) | Idd |
    |---|---|---|---|---|
    | dhruva-l5 | 1.176 GHz | −10.7 | 24.6 (≥22.3) | 11.78 |
    | dhruva-l2 | 1.228 GHz | −12.7 | 23.2 (≥22.3) | 12.39 |
    | dhruva-l1 | 1.575 GHz | −11.2 | 37.8 (≥25.4) | 12.93 |
    | dhruva-s  | 2.492 GHz | −10.3 | 34.6 (≥30.0) | 8.70 |

    The broadband resistive-feedback input holds S11 ≤ −10 over 1.1–2.5 GHz in every
    band mode; only the two tuned stages retune to each f0 — exactly a
    reconfigurable multi-band LNA at the topology level. Per-band sized params:
    `lna/repro/dhruva-4band.params.json`.
  * **Caveats & next:** feasibility is on the gated tier-1 constraints
    (S11-over-band / S21 / Idd); **NF is advisory/off** (tier-2, WP-D1) — the design
    is not noise-optimized. Same attribution as D1 (assistant-authored blind-v1
    topology + automated sizing). Outstanding: a *generated* (not archetype)
    feasible (P5-v6 on the rfb_cs3 set) for the stronger claim; **WP-D1 NF harness**
    → Gate D3; gain-programmability / differential-out / IIP3 are tier-2/3 (out of
    the current harness).

## 13. Phase 3 — WP-D1/D4: the NF harness goes live, and what it costs (Session 4, Track A)

Session 3 left the pipeline with one structural dishonesty: every "feasible" design
was feasible on **S11 / S21 / Idd only**, with noise figure measured but advisory.
This session made NF a real constraint and then re-judged everything. The headline is
that most of the feasible set does not survive — which is exactly what the gate was
for.

### 13.1 WP-D1 — retiring the port-referred NF, and the label-domain split

* **The old NF was not merely noisy, it was biased.** `control_block` used to run a
  `noise` analysis referred to the S-parameter *port*, whose z0 is not modelled as a
  noisy source resistor (finding #7). That path is now **deleted** from the sizing
  deck; `run_and_extract` returns `nf_db = None`, and the only NF in the store comes
  from `extract.measure_nf`'s series-Rs deck. Golden-locked: `extract.py --selftest`
  reads **3.012469 dB vs the analytic 3.0103**, and `ref/check_nf.py` is GREEN across
  an Rn sweep (worst error 0.002 dB).
* **Relabelled the 20 legacy rows** (19 wifi24 corpus + the `ref24_csdeg` anchor) with
  `lna/relabel_nf.py`: rebuild each circuit from that row's **own** `graph.tokens`,
  fence with `size.replay_ok`, re-measure, and **append** a successor row with the
  recipe bumped to `<old>+nfrs-v1` (the store is append-only; a new harness is a new
  label domain). **20 relabelled, 0 quarantined, 0 failed.**
* **Measured domain shift — the port NF flattered every single design.** series_rs
  minus port-referred was **always positive**: min +0.55, median +2.32, mean +3.93,
  max +12.58 dB. Two rows had read physically impossible *negative* noise figures
  (−8.31 → +3.48, −4.52 → +3.71). Any conclusion drawn from the old NF was optimistic
  by ~2.3 dB at the median.
* **NF un-gated (WP-D1 step 4).** The four `dhruva-*` specs drop `status: unsupported`
  on `nf_db`; gps-l1 / wifi24 / wideband-sdr already gated it in YAML — their un-gate
  lived in code, because `size._spec_for_sizing` *forced* nf_db unsupported for every
  spec. It now honours the YAML, with `nf_gate=False` and `LNA_NF_GATE=0` kept as
  explicit ways to reproduce a tier-1 result. **NF must be measured inside the sizing
  loop** (a supported-but-missing metric counts as fully violated and flattens the
  objective); measured cost is 0.07 s on top of 0.07 s, so gating roughly doubles sim
  time and no more. `zoaf_cfg.nf_gated` is stamped on every row — **rows with
  nf_gated true/false are different label domains, and every pre-session row is
  implicitly false.** History is not rewritten: `recreate_dhruva_l1.py` pins
  `nf_gate=False` and still reproduces Gate D1 exactly (s11_max −11.24 / S21 37.81 /
  Idd 12.93, feasible).

### 13.2 A harness gap closed on the way: two-port stability

The pipeline had **never** checked stability. The Gate-D1/D2 winner is a 3-stage
feedback amplifier at 37.8 dB, and nothing in the harness could have said whether it
oscillates. `extract.control_block` now derives Rollett **K**, **|Δ|**, **μ** (load
plane) and **μ_src** (source plane) from the full S-matrix the `sp` analysis *already*
computes — at f0 and at the worst point over the sweep band, for **zero extra
simulation time**. Advisory, never gated. `ref/check_stab.py` validates it against a
closed-form series-R two-port (K = μ = 1 exactly — the boundary case, so a sign or
normalization slip cannot hide), plus unilateral-matched and negative-resistance
qualitative goldens.

**Verdict on the existing winners — clean; Gates D1/D2 are NOT qualified by an
oscillation risk.** The dhruva 4-band winner is unconditionally stable on all four
bands both in-band (K_min 10.1–28.4, μ_min 1.004–1.149) and over a wide 0.1–20 GHz
audit sweep (K_min 12.9–29.0, |Δ|max 0.93–0.96); S12 = −84.9 dB at f0, i.e. three
cascaded stages are essentially unilateral. The wide-sweep μ_min values sitting at
~1.0000 are a numerical boundary, not marginality: they are attained at 100 MHz where
the output coupling cap drives |S22| → 1 and S12·S21 → 0, and K there is ~3e10.

**But two feasible wifi24 sizings ARE potentially unstable in-band** (K_min < 1):
`seq0009` curated-v1 (K_min 0.352, μ_min 0.954) and `seq0220` polish-v1 (K_min 0.832).
The *same* `seq0220` topology sized by curated ZOAF is fine (K_min 4.08) while its
polished row is not — **the min-margin polish walked it into a potentially unstable
region, because stability is in no objective.** Out of band more designs are only
conditionally stable, including the Gate-G4 hand reference `ref24_tapped`
(K_min_wide 0.038). Logged, not gated: a caveat, not a claim. Note the fidelity
limit — ideal-element behavioral ngspice, no package or layout parasitics, and
stability checked over frequency only, not over process or load pulling.

### 13.3 ⚠ `size.polish` ignored the device box — 6 of 19 feasible rows were out-of-box

Found by Track B, landed here (Track A owns `size.py`). The min-margin ascent scaled
each parameter by (1 ± step) and never consulted `kind_ranges(spec)`, so it walked
outside the spec's declared device limits. ZOAF searches *inside* the box, so only
polish-derived points were affected — but a feasibility claim standing on an
out-of-box device is **overstated**. Audit: **6 of 19 feasible rows**, all
polish-derived (wifi24 seq0009 / seq0220 / seq0079 / seq0046, gps-l1 seq0089, and
Track B's own superseded dhruva-l1 row, which they had already withdrawn).

Fix: every trial clamped, the incoming point clamped, and a coordinate pinned on a
bound cannot step outward. **Re-deriving the 5 non-Track-B rows under the clamped
polish returns all five to FEASIBLE and IN-BOX** — the designs are real; only the
recorded device values had drifted:

| design | S11 | S21 | Idd | NF | verdict |
|---|---|---|---|---|---|
| wifi24 `seq0009` | −13.22 | 15.50 | 3.55 | 2.70 | feasible (tier-1), in-box |
| wifi24 `seq0220` | −15.54 | 15.30 | 3.64 | 2.31 | feasible (tier-1), in-box |
| wifi24 `seq0079` | −11.28 | 13.45 | 3.53 | 2.57 | feasible (tier-1), in-box |
| wifi24 `seq0046` | −12.84 | 15.04 | 3.73 | 6.94 | feasible (tier-1), in-box |
| gps-l1 `seq0089` | −12.48 | 17.15 | 2.57 | 4.02 | feasible (tier-1), in-box |

**One tier-2 claim does die of it:** wifi24 `seq0079` passed NF at 2.48 dB only on an
out-of-box 18.25 nH inductor (l_max 12 nH); in-box it reads **2.57 (+0.07 over target)
→ FAIL**. That is the honest cost of the bug.

### 13.4 ★ WP-D4 — the NF-gate survivor contrast (the Gate D3 baseline)

`lna/nf_contrast.py` re-judges every stored feasible design **unchanged** (no
re-sizing) against its own spec with NF gated: rebuild from the row's own tokens,
`replay_ok` fence, re-measure. It prefers an in-box row when both exist.

| spec | design | S11* | S21 | Idd | NF | NF target | excess | tier-1 | tier-2 | K_min |
|---|---|---|---|---|---|---|---|---|---|---|
| dhruva-l1 | `seq0192` (generated, Track B) | −11.5 | 29.2 | 11.09 | **9.63** | 2.7 | +6.93 | PASS | **FAIL** | 106 |
| dhruva-l1 | `rfbcs3_tank_cc21_bf0` | −11.2 | 37.8 | 12.93 | **9.95** | 2.7 | +7.25 | PASS | **FAIL** | 28.4 |
| dhruva-l2 | `rfbcs3_tank_cc21_bf0` | −12.7 | 23.2 | 12.39 | **11.12** | 2.5 | +8.62 | PASS | **FAIL** | 10.1 |
| dhruva-l5 | `rfbcs3_tank_cc21_bf0` | −10.7 | 24.6 | 11.78 | **8.77** | 2.5 | +6.27 | PASS | **FAIL** | 16.7 |
| dhruva-s | `rfbcs3_tank_cc21_bf0` | −10.3 | 34.6 | 8.70 | **8.88** | 3.5 | +5.38 | PASS | **FAIL** | 21.3 |
| gps-l1 | `seq0089` | −12.5 | 17.1 | 2.57 | **4.02** | 1.8 | +2.22 | PASS | **FAIL** | 27 |
| gps-l1 | `seq0215` | −14.4 | 15.4 | 2.94 | **4.43** | 1.8 | +2.63 | PASS | **FAIL** | 276 |
| wifi24 | `seq0220` | −13.8 | 12.6 | 2.46 | **2.43** | 2.5 | **−0.07** | PASS | **PASS** | 4.08 |
| wifi24 | `seq0240` | −11.9 | 12.6 | 1.19 | **3.42** | 2.5 | +0.92 | PASS | **FAIL** | 12.7 |
| wifi24 | `seq0086` | −12.6 | 15.3 | 1.90 | **2.76** | 2.5 | +0.26 | PASS | **FAIL** | 17.1 |
| wifi24 | `seq0009` | −10.9 | 12.8 | 4.00 | **2.77** | 2.5 | +0.27 | PASS | **FAIL** | 0.352 |
| wifi24 | `seq0046` | −12.8 | 15.0 | 3.73 | **6.94** | 2.5 | +4.44 | PASS | **FAIL** | 4.95 |
| wifi24 | `seq0079` | −11.3 | 13.4 | 3.53 | **2.57** | 2.5 | +0.07 | PASS | **FAIL** | 1.12 |
| wifi24 | `ref24_tapped` | −20.1 | 18.6 | 3.15 | **2.00** | 2.5 | **−0.50** | PASS | **PASS** | 2.46 |

**tier-1 still 14/14 (every replay clean) — tier-2 2/14.** (S11* = worst-case over
band for dhruva/wideband specs, at f0 otherwise.)

Reading:
* **wifi24 is solved at tier-2**, by one *novel generated* design (`seq0220`: S11
  −13.8 / S21 12.6 / Idd 2.46 / NF 2.43 — the first design in this program to clear
  all four gated constraints at once) plus the hand tapped-C reference (NF 2.00). Note
  `seq0220` clears by only 0.07 dB — a boundary result, not a comfortable one.
* **The dhruva family is a wipeout, by 5.4–8.6 dB.** That is not a sizing shortfall,
  it is the input stage: resistive shunt feedback puts a resistor and a low-gain first
  stage in front of everything. Four more wifi24 designs are within 0.3–0.9 dB.
* **gps-l1 (1.8 dB) misses by 2.2–2.6 dB** — the hardest NF target in the set.

### 13.5 Gate D3 push — where the NF/gain Pareto actually sits

**Prong (a) — trade the winner's gain slack for noise. Measured; it does not close.**
dhruva-l1 has ~12 dB of S21 slack over its 25.4 dB floor. NF-aware polish (the
min-margin ascent now includes the NF margin) from the stored 4-band params:

| band | from | to |
|---|---|---|
| dhruva-s | s11_max −10.3 / S21 34.6 / NF 8.88 | s11_max −2.61 / S21 49.3 / **NF 6.17** |
| dhruva-l1 | s11_max −11.2 / S21 37.8 / NF 9.95 | s11_max −0.40 / S21 45.3 / **NF 5.64** |

The optimizer **buys ~2.7–4.3 dB of NF and pays for it with the broadband match**, not
with gain — it even *raised* S21. So on this family the binding trade is NF ↔ S11,
because the feedback resistor that sets the broadband match is the same element that
sets the noise. Min-margin improved (dhruva-s −1.537 → −0.762) but stayed infeasible.
**The 12 dB of gain slack is not convertible into 5+ dB of NF on a resistive-feedback
input.** Prong (a) is answered in the negative, with numbers.

**Prong (b) — generic textbook low-noise input stages (blind rule 2).** Two families
added to `templates.py` (135 → 148 archetypes, 13 passing the structural screen),
chosen from *our own* measured failure mode and not from any paper:
* `gmb_cg_lna` — **gm-boosted common gate**. A plain CG matches broadband
  (Rin = 1/gm) but floors at F = 1 + γ/α because one gm sets both match and noise; an
  inverting auxiliary CS amp of gain −A from source back to gate makes it (1+A)·gm, so
  the same match needs far less gm: F = 1 + γ/(α(1+A)).
* `nc_cgcs_lna` — **noise-cancelling CG + CS**, single-ended. The matching device's
  noise appears at the input node X and at the CG drain Y1 with *opposite* sign while
  the signal appears with the *same* sign, so two paths reaching a shared summing node
  with equal inversion count add signal and subtract noise (X→aux CS→Yo;
  X→CG→Y1→CS→Yo). Where it cancels exactly is a continuous gm/load trade — the sizer's
  job, nothing hand-tuned.

**★ The broadband-match wall was a BIASING DEFECT, not a topology limit.** As first
written both families tied the CG gate to VDD and drove the auxiliary amp straight off
the DC-grounded source node — so Vgs(CG) = VDD (deep triode) and Vgs(aux) = 0 (the
device never conducts). Leaving the CG gate undriven with a bypass cap (bias.py's
R-GATE then feeds it a **sizable** bias, so the sizer owns the CG current) and
AC-coupling the aux gate changed s11_max over 1.1–2.5 GHz on a coarse grid from
**≈ −3/−4 dB to −19.7 dB** (`gmbcg_s1_tank_b1`), −12.9 (`nccgcs_s1_tank`), −9.6
(`gmbcg_s1_tank_b0`). WP-D2 spent an entire campaign characterizing an s11_max wall
for the *rfb* family; for the CG family the same-looking wall was DC bias. Lesson for
every future family: **screen the operating point before concluding anything about a
topology's RF limits.**

**A second sizing lever landed with it: match-first sizing** (`size.size_match_first`)
— the self-starting version of 06-LAST-MILE's curated recipe. Stage 1 optimizes only
the match parameters against a pure worst-case-S11 objective (saturating at −15 dB)
with everything else mid-range; stage 2 freezes them and gives the rest the real spec
objective; stage 3 is the NF-aware polish with the match held. It needed
`match_param_names` to replace the gate-only `match_devices` walk, which was **blind
to a common-gate input** (the signal arrives at a SOURCE), so Rin = 1/gm never entered
the match search and the CG archetypes were searching only {Cin, Lin}.

**Measured D3 state vs `dhruva-s` (NF ≤ 3.5, the softest band), single seed,
match-first + NF-aware polish:**

| archetype | s11_max | S21 | Idd | NF | K_min | total viol |
|---|---|---|---|---|---|---|
| `nccgcs_s1_tank` | **−13.3 ✓** | 21.5 | 12.25 ✓ | 4.93 | 32.1 | **0.693** |
| `gmbcg_s1_tank_b1` | −10.1 ✓ | 23.4 | 5.46 ✓ | 6.55 | 14.0 | 1.093 |
| `gmbcg_s1_R_b1` | −10.2 ✓ | 19.3 | 3.07 ✓ | 6.38 | 13.8 | 1.177 |
| `gmbcg_s1_tank_b0` | −9.9 | 16.7 | 11.89 ✓ | 6.86 | 8.36 | 1.416 |

versus the rfb_cs3 incumbent's dhruva-s violation of **1.537 on NF alone**. A second,
2-seed pass with a larger ZOAF budget then pushed the same archetype much further:

**`nccgcs_s1_tank` vs dhruva-s, best measured point: s11_max −14.8 ✓ / S21 28.6 /
Idd 12.99 ✓ / NF 5.68 — total violation 0.669, of which NF is 0.623 and gain 0.047.**

So the best dhruva-s candidate moved from *NF-only violation 1.54* (incumbent) to
*total violation 0.669*, and — importantly — the noise-cancelling family now clears
the broadband match with margin and comes within **1.4 dB of the hardest gain target
in the whole spec set (30 dB)** while cutting NF from 8.88 to 5.68 dB. **Gate D3 is
NOT met.** `wideband-sdr` also stays 0 (best `nccgcs_wb_s0`: S21 9.9, NF 5.42, viol
1.551).

**The measured barrier, stated precisely (a wall is a deliverable).** After this
session the dhruva blocker is **noise alone**, and it is a *family-level* number, not
an optimizer shortfall:

* S11-over-band: **solved** for the CG families (−14.8 dB, with margin).
* Idd: **solved** (12.99 vs 13, tight but met).
* S21: **essentially solved** — 28.6 of 30 dB on the hardest band, inside the
  16-device budget. (The earlier reading that the `device_budget` of [3,16] was the
  binding wall — `nccgcs_s1_tank` sits at exactly 16 devices with 3 inductors, so
  `nccgcs_s2_tank` at ~20 devices is rejected before it is ever simulated — turned out
  to be premature: one tuned stage plus the tuned summing node reaches 28.6 dB. The
  budget is a *latent* constraint, not the active one.)
* NF: **the wall.** 5.68 dB measured against 3.5 (dhruva-s) / 2.5–2.7 (the other three
  bands). And within the family there is a measured NF↔gain trade of roughly
  **+0.75 dB NF per +7 dB gain** (4.93 dB at S21 21.5 → 5.68 dB at S21 28.6), so
  buying the last 1.4 dB of gain costs ~0.15 dB more noise; extrapolated, the family
  sits near **NF ≈ 5.9 dB at 30 dB gain — about 2.4 dB above dhruva-s's target**.

The interpretation to test next: 5.7 dB is far above what a noise-cancelling CG+CS
should achieve (~2.5–3 dB), which says the sizer is **not finding the cancellation
point** — cancellation holds only on a specific locus of gm/load ratios, and the
blended feasibility-first objective has no reason to sit on it. That makes the next
lever a *targeted* one (a cancellation-condition-aware start or an explicit NF-only
inner stage), not more seeds. Raising `device_budget` is a **spec** change and was
deliberately NOT made in order to close a gate.

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

**G4-by-generation is close but not closed:** P5 samples reach S21 = 14.0 dB
(seq0126, S11 short) and S11 = −21.9 dB (seq0009, S21 short) — high gain and good
match are both now *generated*, just not in one design under all-params-free ZOAF.
Curated sizing of the top P5 candidates (as `size_tapped` does the ref) is the
likely path to the phase's headline gate.

**Open (next):** curated feasible sizing of top P5 candidates (→ G4-by-generation);
a bigger P5 pool + lower σ (0.77 now — trim multimodal-sizing labels) to firm up
the ρ read; per-class `<LNA_WB>` for wideband; the Stage-3 loop cadence
(re-generate ← retrain ← re-size) now that one turn is proven to move the yardstick.

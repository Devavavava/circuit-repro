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
2-seed pass with a larger ZOAF budget then pushed the family much further, and mapped
two distinct points on its NF↔gain Pareto:

| point | s11_max | S21 | Idd | NF | total viol |
|---|---|---|---|---|---|
| `nccgcs_s1_tank` (gain end) | **−14.8 ✓** | **28.6** | 12.99 ✓ | 5.68 | 0.669 |
| `nccgcs_s1_R` (noise end) | −9.4 | 22.4 | 6.75 ✓ | **4.38** | **0.566** |

So the best dhruva-s candidate moved from *NF-only violation 1.54* (incumbent) to
**0.566**, and the noise-cancelling family now either clears the broadband match with
margin while coming within **1.4 dB of the hardest gain target in the whole spec set
(30 dB)**, or cuts NF from 8.88 to **4.38 dB** — but not both at once. **Gate D3 is
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
* NF: **the wall.** Best 4.38 dB measured against 3.5 (dhruva-s) / 2.5–2.7 (the other
  three bands) — and that point gives up gain and 0.6 dB of match to get there. Within
  the family the measured NF↔gain trade is roughly **+1.3 dB NF per +6 dB gain**
  (4.38 dB at S21 22.4 → 5.68 dB at S21 28.6), so the family's 30 dB corner sits near
  **NF ≈ 5.9 dB, about 2.4 dB above dhruva-s's target** and ~3.3 dB above the other
  three bands'.

The interpretation to test next: 5.7 dB is far above what a noise-cancelling CG+CS
should achieve (~2.5–3 dB), which says the sizer is **not finding the cancellation
point** — cancellation holds only on a specific locus of gm/load ratios, and the
blended feasibility-first objective has no reason to sit on it. That makes the next
lever a *targeted* one (a cancellation-condition-aware start or an explicit NF-only
inner stage), not more seeds. Raising `device_budget` is a **spec** change and was
deliberately NOT made in order to close a gate.

## 14. Phase 3 — Track C: what the label noise actually was, and what the enlarged store buys the critic (Session 4)

Track C consolidates the night: fix the label-noise number that had been quoted
three different ways, retrain the critic on a store that grew 264 → 734 rows, and
refresh the cross-spec benchmark now that NF is gated. Two of the three headline
results are *measurement* corrections — the kind that change what earlier numbers
meant rather than what the circuits do.

### 14.1 σ(S21) — the "drift" was mostly an artefact, and best-of-3 halves what is left

`σ(S21)` had been reported as **0.32 → 1.02 → 1.27 dB** across sessions and was on
the tripwire watchlist. Two defects in how it was computed:

1. **Recipes were pooled.** `_sigma_from_repeats` grouped rows by `(wl_hash, spec)`
   alone, so a `curated-v1` row, a `polish-v1` row, a `blind-v1` archetype row and a
   `p5v6-gen-v1` sample of the same topology all counted as "repeats" of each other.
   **81 of the 89 multi-row keys in the store were mixed that way.** Those
   differences are deliberate — 01-DATA's own rule is that two recipes are two label
   domains and are never pooled silently — so the estimator was reading recipe churn
   as label noise. `campaign.sigma_key` now conditions on `(wl_hash, spec, recipe,
   nf_gated)`.
2. **Two samples per key.** A population stdev over n=2 is a very poor estimate of
   spread, and it *under*-states it: on the same 19 keys, 2 samples/key gives
   **0.570 dB** where 9 samples/key gives **1.478 dB**.

**Measured, on the 19 wifi24 corpus repeat-probe keys** (recipe `candidate-v1`,
`nf_gated=false`, `inductor_q=12`, 9 independent seeds per key, 171 sizings):

| protocol | σ(S21) | samples |
|---|---|---|
| single-seed (the label definition until now) | **1.478 dB** (median 1.438) | 9 seeds/key |
| single-seed, estimated from only 2 seeds/key | 0.570 dB | the old estimator |
| **best-of-3** (06-LAST-MILE §4, 3 independent bo3 labels/key) | **0.726 dB** | 3 labels/key |

**And it replicates on the stratum that matters.** The corpus keys measure noise on
circuits the pipeline did not design; the *generated* pool is what the critic's
source-shift split and 03-SEARCH's candidate stream are made of, so it was probed
too — 16 near-feasible `campaign-G` wifi24 topologies, same protocol (96 sizings):

| stratum | single-seed σ(S21) | best-of-3 σ(S21) | keys |
|---|---|---|---|
| corpus (`corpus` / `campaign-R`) | 1.478 dB | **0.726 dB** | 19 |
| **generated (`campaign-G`)** | **1.522 dB** | **0.829 dB** | 16 |

So the honest story is not "σ drifted 4×"; it is **σ was always ≈1.5 dB on both
populations and the early estimates were too small and contaminated**. Best-of-3
takes it to **0.73–0.83 dB — a 2.0× reduction for 3× the sim cost**, which does
*not* clear 06-LAST-MILE's ≲0.5 dB acceptance bar. The noise is extremely
topology-dependent — the *median* best-of-3 spread in the generated stratum is
**0.148 dB** while its mean is 0.829: 6 of 19 corpus keys sit under 0.2 dB even
single-seed, while corpus 1086/475/476 and generated `seq0152` run 3–4.3 dB (the
multimodal all-free sizing landscape, unchanged diagnosis). **A few pathological
topologies carry nearly all of the label noise**, which is exactly what the
per-row `label_sigma` is for: drop or downweight those rather than pay 3× on every
row. Best-of-3 is now available as `size.size_best_of_k` and stamps the row with
`zoaf_cfg.recipe = candidate-v1+bo3`, `zoaf_cfg.seeds`, and per-metric
`label_sigma` so training can downweight by 1/σ without re-simulating.

```bash
python lna/campaign.py --sigma-probe --spec wifi24 --k 3 --reps 2         # corpus
python lna/campaign.py --sigma-probe --gen --spec wifi24 --limit 16       # generated
```

### 14.2 Critic retrain on v4-train (734 rows) — the source-shift gap closes, and Gate C1's enrichment half stops being reachable

Snapshot **`v4-train`** pins 734 `topo_labels` / 41 `l1_labels`; 730 rows are
token-bearing with a full margin vector (was 261 under `v2-train`).

**A bug found while wiring it up: 240 of tonight's rows were invisible to the
critic.** `_margins` read `s11_db` only, but the broadband specs (`dhruva-*`,
`wideband-sdr`) gate **`s11_max_db`** — so every dhruva row, including the whole
~200-row Track-B corpus, returned `None` and was silently dropped. The target is
"the spec's S11 margin", whichever name that spec uses; fixed. Two other changes
were forced by the store becoming multi-spec: **spec conditioning** (thresholds +
band appended at the ridge features and at the GNN readout — the same topology has
different margins against different specs and a graph-only vector just averages
them), and a **spec-conditioned WL-kNN** (search the neighbour within the same spec
first). `is_generated` now classifies the source-shift split by provenance rather
than by the single arm name `campaign-G`, so the Track-B, g4 and p5v3 samples count
as generated (420 generated rows vs 142 before).

**Gate C1 verdict, per arm and per split** (σ_S21 = 0.726 dB, the best-of-3
ceiling; C1 = enrichment@top-20% ≥ 2× **and** ρ(S21) ≥ 0.5):

| split | arm | ρ(S11) | ρ(S21) | ρ(Idd) | ρ(NF) | rank-acc | prec@20% | enrich | C1 |
|---|---|---|---|---|---|---|---|---|---|
| family holdout (test 95) | trivial | – | – | – | – | 0.000 | 0.495 | 1.00 | no |
| | WL-kNN | 0.361 | **0.687** | 0.462 | 0.676 | 0.784 | 0.842 | 1.70 | **no** |
| | ridge | 0.429 | **0.790** | 0.486 | 0.700 | 0.816 | 0.737 | 1.49 | **no** |
| | **GNN (ens-5)** | **0.594** | **0.851** | **0.596** | 0.660 | **0.854** | **0.895** | **1.81** | **no** |
| source-shift (test 420) | trivial | – | – | – | – | 0.000 | 0.455 | 1.00 | no |
| | WL-kNN | 0.313 | 0.370 | 0.268 | 0.403 | 0.629 | 0.512 | 1.13 | **no** |
| | ridge | 0.603 | **0.585** | 0.346 | 0.392 | 0.710 | 0.655 | 1.44 | **no** |
| | **GNN (ens-5)** | 0.554 | **0.609** | **0.464** | **0.422** | **0.740** | **0.655** | 1.44 | **no** |

**★ The source-shift gap closed — and it was the data, not the code.** ρ(S21) on
generated topologies goes **0.221 → 0.585** (ridge). Running the *same* code on the
old `v2-train` snapshot reproduces the old numbers exactly (family split WL-kNN
0.768 / enrich 2.06 / C1 **YES**; source-shift ridge 0.221, WL-kNN 0.282), so the
improvement is attributable to tonight's rows — chiefly the ~200 Track-B dhruva-l1
generated labels and the dhruva archetype stratum they can be learned from — and
not to spec conditioning or the S11 fix on their own.

**But read the within-spec numbers, because a multi-spec pool inflates pooled ρ.**
A model that only learns "dhruva rows have worse gain margins than wifi24 rows"
scores well pooled and is useless to search, which only ever ranks candidates
*within* one spec. `critic._per_spec` now reports both:

| split | spec | n | WL-kNN ρ(S21) | ridge ρ(S21) | GNN ρ(S21) |
|---|---|---|---|---|---|
| family holdout | dhruva-l1 | 24 | 0.567 | 0.821 | **0.841** |
| | wifi24 | 67 | 0.701 | 0.806 | **0.877** |
| source-shift | dhruva-l1 | 200 | **0.003** | 0.753 | 0.746 |
| | wifi24 | 217 | 0.498 | 0.430 | **0.516** |

So the pooled source-shift number is *not* an artefact: within the 200-row Track-B
dhruva-l1 generated pool the ridge arm reaches **ρ = 0.753** and the GNN 0.746,
while on generated wifi24 they sit at 0.430 / 0.516 — about where they always were.
**WL-kNN collapses to ρ = 0.003 on the
Track-B pool**, which is the clearest statement yet of what that baseline was
living on: nearest-neighbour prediction works when the test topology has a near
duplicate among the labels, and the Track-B samples are novel by construction (they
match none of the 148 archetypes or 41 corpus circuits). **On genuinely novel
generated topologies the hand-feature ridge is the arm that works and the
duplicate-structure baseline has nothing.**

**⚠ Gate C1's enrichment half has become unreachable, for a measurable reason.**
Enrichment = precision@20% / base-rate, and precision ≤ 1, so the metric is capped
at **1/base-rate**. As the pool got better the near-feasible base rate rose and the
ceiling fell:

| snapshot | split | base rate | enrichment ceiling | best arm |
|---|---|---|---|---|
| v2-train | family | 0.485 | 2.06× | WL-kNN 2.06× (prec@20% = **1.000**, perfect) |
| v2-train | source-shift | 0.268 | 3.74× | WL-kNN 1.33× |
| **v4-train** | family | 0.495 | **2.02×** | WL-kNN 1.70× (prec@20% 0.842) |
| **v4-train** | source-shift | 0.455 | **2.20×** | ridge 1.44× (prec@20% 0.655) |

C1's "≥2×" was set when most of the pool was far from feasible; at a base rate of
0.5 it silently means "**perfect** precision@20%". The v2-train pass was exactly
that — a perfect top-20%, not a 2× margin. **This is a frozen-protocol problem of
the same shape as the NDL novelty-reference gap and it needs the same explicit
rebaseline decision from the user** (candidate: gate on precision@20% ≥ 0.8, or
tighten `NEAR_FEASIBLE` from −1.0 so the base rate stays low as the pool improves).
Stated plainly for the record: **on the letter of C1, no arm passes on either split
tonight; on the Spearman half, ridge passes both splits for the first time** (0.790
family / 0.585 source-shift), and the enrichment half is not reachable by any model.

**NF is now a predicted target.** 711 of 730 rows carry a `series_rs` NF, so the NF
margin is trained and evaluated as a fourth head (masked in the GNN loss; a
separate same-features arm in the baselines). It predicts *better* than the S11
margin on the family split (ρ 0.676–0.700 vs 0.361–0.429) — unsurprising, since NF
is a smooth function of the input device's size and current where S11 depends on a
resonance. On the source-shift split it drops to ρ ≈ 0.39–0.40.

**★ The GNN ships as critic v1 — but state the margin precisely.** 02-CRITIC §2's
rule is that the GNN ships only if it beats `max(WL-kNN, ridge)` on the primary
holdout metrics; last run it lost the C1 gate to WL-kNN (0.65 vs 0.77). Tonight it
takes the headline metric on both splits: **ρ(S21) 0.851** family (vs 0.790 ridge /
0.687 kNN) and **0.609** source-shift (vs 0.585 / 0.370), with the best rank
accuracy on both and the best precision@20% on the family split (0.895 vs 0.842).
It is **not** a clean sweep, and pretending otherwise would be the easy lie: on the
source-shift split it *ties* ridge on precision@20% (0.655 both) and loses ρ(S11)
to it (0.554 vs 0.603), and within the dhruva-l1 generated pool ridge is
fractionally ahead (0.753 vs 0.746). What it does buy that the baselines cannot is
**usable uncertainty** — ensemble std ranks |error| with ρ = 0.536 (family) / 0.528
(source-shift) — which is precisely what 03-SEARCH's trust rule (`mean − β·std`)
consumes. The graph inductive bias plus spec conditioning is what the crux
experiment asked about, and on this data the answer is a qualified yes. Note the
whole field is still below the ceiling a 0.726 dB label noise implies, so part of
the residual is unlearnable rather than un-modelled.

### 14.3 Cross-spec benchmark, refreshed at full budget and split by tier

`lna/data/benchmark.md` had been carrying a lean-budget artefact (`seeds=1,
budget=5,5,1`) with a self-declared caveat that wifi24 read 4/6 there vs 6/6 at
full budget. It is re-run at the established full budget (**`seeds=1,2`,
ZOAF `budget=8,8,2`**) over a candidate set that reflects tonight, and reports the
two tiers separately.

Three changes to `benchmark.py` were needed to make the table honest:

* **Candidate set from the feasible record, not from wifi24 closeness.**
  `--all-feasible` seeds the set from `nf_contrast.feasible_designs()` — every
  distinct topology that has ever been tier-1 feasible against any spec, with an
  **in-box row preferred over the superseded out-of-box polish rows** (§13.3). The
  old wifi24-closeness ranking could not reach either the *generated* dhruva-l1
  feasible `seq0192` or the 4-band `rfbcs3` archetype; both are now in. Dedup is on
  `wl_hash`, not on the token list — the same circuit re-emitted by a different
  Eulerian walk has different tokens (it had been entering the table twice).
* **Every cell also re-measures the pipeline's stored best point** for that
  (topology, spec) and keeps whichever is better. Without it the table reports
  *worse* than the program already owns: the stored feasibles were earned with
  multi-seed heavy sizing plus polish, far past a per-cell budget, so a pure
  re-search reported `seq0192` as infeasible on the very band it is feasible on.
* **NF is measured on every cell** (`size_topology(enrich_nf=True)`), because the
  old table's NF column was the retired port-referred number — it printed
  *negative* noise figures — and after WP-D1 that path returns `None`, which would
  have rendered as 0.

**Result — 12 candidates (the 10 distinct tier-1-feasible topologies plus the 2 closest near-feasible), 7 specs, 84 cells.**

| spec | tier-1 | tier-2 | binding when infeasible |
|---|---|---|---|
| wifi24 | **10/12** | **1/12** | `s21` ×1, `s11` ×1 |
| gps-l1 | **2/12** | **0/12** | `s21` ×5, `s11` ×4, `idd` ×1 |
| wideband-sdr | **0/12** | **0/12** | `s11` ×6, `s21` ×4, `s21_ripple` ×2 |
| dhruva-l5 | **1/12** | **0/12** | `s11_max` ×11 |
| dhruva-l2 | **1/12** | **0/12** | `s11_max` ×10, `s21` ×1 |
| dhruva-l1 | **2/12** | **0/12** | `s11_max` ×10 |
| dhruva-s | **1/12** | **0/12** | `s11_max` ×11 |

**Tier-2 cells (all four gated constraints at once):** `seq0220.txt` on **wifi24** (S11 -14.5 / S21 13.0 / Idd 2.73 / NF **2.34** / K_min 4.386)

**Stability advisory — cells with in-band K_min < 1** (logged, never gated):

| candidate | spec | K_min | tier-1 | sizing |
|---|---|---|---|---|
| seq0046.txt | dhruva-l1 | **-2.04** | no | all-free |
| seq0009.txt | wideband-sdr | **0.231** | no | all-free |
| seq0079.txt | wideband-sdr | **0.241** | no | all-free |
| seq0009.txt | wifi24 | **0.242** | yes | curated |
| seq0008.txt | dhruva-l5 | **0.522** | no | all-free |
| seq0079.txt | dhruva-s | **0.591** | no | all-free |
| seq0009.txt | dhruva-l1 | **0.61** | no | all-free |
| seq0215.txt | dhruva-s | **0.949** | no | all-free |

Reading:

* **wifi24 is comfortably the solved class at full budget: 10/12 tier-1.** The only
  two misses are the two *dhruva-native* designs (`seq0192` binds `s21`,
  `rfbcs3_tank_cc21_bf0` binds `s11`) — every wifi24- and gps-l1-native candidate
  clears wifi24. That is the budget artefact the old table warned about, resolved:
  4/6 lean → 10/12 full.
* **Tier-2 is still one cell in the whole matrix.** `seq0220` on wifi24 (NF 2.34
  against ≤2.5) is the only (candidate, spec) pair in 84 that meets all four gated
  constraints at once. The hand `ref24_tapped` reference is the other known tier-2
  design and is *not* in this table — it is a netlist, not a token topology. So the
  program's tier-2 record stands at exactly **two designs, one of them generated**.
* **The dhruva wall is unchanged and it is `s11_max`:** 10–11 of the 12 candidates
  bind on worst-case-over-band S11 on every dhruva column, and the sole passer is
  the `rfbcs3` 4-band family (plus `seq0192` on L1). `wideband-sdr` remains 0/12,
  binding on `s11` (6), `s21` (4), `s21_ripple` (2).
* **The stability advisory is not decoration.** Eight of 84 cells read in-band
  K_min < 1, one of them a *tier-1-feasible* cell: `seq0009` on wifi24 at
  **K_min 0.242** under curated sizing (§13.2 measured 0.352 for the same design;
  a different sized point, the same problem). `seq0046` on dhruva-l1 reaches
  **K_min = −2.04**. Nothing in any objective penalises this, which is the
  standing recommendation to put K ≥ 1 into the polish/curated guard.


### 14.4 Housekeeping, and one thing worth knowing about concurrency

* `.gitignore` now covers `lna/out/_*` (the `_`-prefix convention for "throwaway,
  reproducible from a committed script"), `lna/out/*.pre_*.json` (the backups the
  training-set emitters write before overwriting) and `lna/out/*_train_*.json`,
  plus a setup note for the three junctioned runtime deps. **Verified: junctioned
  `misc` / `AnalogGenie` / `AutoCkt\repo` do not appear in `git status`,** so they
  need the note and not an ignore rule. Four new generator run dirs are tracked by
  `meta.json` only; on `lna-exec`, the ten concluded P4 logit-bias sweep dirs the
  same way.
* **A Track-A `d3_campaign.py` was still running when Track C started** and
  appended its dhruva-l1 chunk (rows 735–772, plus the tail of `d3_run.log`)
  interleaved with the σ-probe rows. Nothing broke — that is exactly what the
  append-only store plus sha256-pinned snapshots are for, and `v4-train` still
  verifies at 734 lines — but it is the first time two writers overlapped, and it
  is why `_sigma_from_repeats` and both eval drivers now take `snapshot=`: a number
  computed against a live store is not reproducible once anyone else is writing.
* Regression quartet green throughout (vocab MATCH, screen 59.4% = 114/192,
  pipeline_yield 40/42 = 95.2%, check_ref / check_nf / check_stab GREEN,
  calibrate_specs ALL ACCEPTANCE CRITERIA MET).

**Tools added by Track C:**

```bash
python lna/campaign.py --sigma-probe [--gen] --k 3 --reps 2   # best-of-k label-noise probe
python lna/critic.py --eval --snapshot v4-train --sigma-recipe candidate-v1+bo3
"…/analoggenie/python.exe" lna/critic_gnn.py --eval --snapshot v4-train --sigma-recipe candidate-v1+bo3
python lna/benchmark.py --all-feasible --seeds 1,2 --budget 8,8,2 --out-json <ckpt> [--resume <ckpt>]
python lna/datastore.py --snapshot v4-train                    # pin a training set
```

### 14.5 Metrics governance (2026-08-09): the NDL novelty reference is rebaselined to **ref-v2**

§14.2 and the Session-4 handover both flagged this as needing an explicit
user decision, because it changes a *frozen* protocol. The decision was taken and
this is the execution. Nothing about the circuits changed tonight; what changed is
what the measuring stick counts as novel.

**The defect.** `novelty.py`'s reference was the 41-circuit AnalogGenie LNA corpus
and nothing else. Every P5-era generator is fine-tuned on the Eulerian-augmented
`templates.py` archetype set, so a verbatim regeneration of a hand-written
archetype is a **copy of its own training data** — and the old reference, never
having looked at the archetypes, scored it *novel*. Track B measured the size of
the hole at ~51% of screen-passing samples; that reproduces here exactly (below).

**The fix.** The reference is now versioned and the version travels with every
number:

| version | contents | distinct WL hashes | digest |
|---|---|---|---|
| `ref-v1` | 41 corpus LNAs (the original P0 freeze) | 41 | `5273a4f673b5eb6a` |
| **`ref-v2`** (default) | 41 corpus + **148 `templates.py` archetypes** | **189** | `b5689490d0285c37` |

Archetype hashes come from the *same* `templates.archetypes()` emission path that
mints the P5 training set, so the reference is by construction exactly what the
generator was trained on — it cannot drift away from the training set by being
maintained separately. All 148 archetype hashes are distinct from each other and
disjoint from the 41 corpus hashes (41 + 148 = 189).

**The digest is not decoration.** The archetype set has grown 92 → 118 → 135 → 148
over this program's life, so "ref-v2" alone does not pin a number the way "ref-v1"
did. Every protocol row now prints `ref-v2[189h/b5689490]`, and the on-disk
reference (`lna/data/novelty_ref_v2.json`, committed) is keyed by a SHA-256 over
`templates.py` + `spec.py` + `topology.py` + `novelty.py` + the two screen YAMLs, so
a stale cache rebuilds instead of silently answering a novelty question with the
wrong measuring stick. Enumeration costs ~37 s cold, 0.8 s warm.

#### The old → new table (frozen NDL@256 protocol, nb class, `--spec wifi24` screen, seed 1337)

| checkpoint | pool on disk | NDL@256 ref-v1 | **NDL@256 ref-v2** | Δ | copies ref-v1 | copies ref-v2 (archetype / corpus) | median NN-sim v1 → v2 |
|---|---|---|---|---|---|---|---|
| P0 prefix-12 baseline | `sweep12repro{,_s2338}` | 16 | **16** | **0** | 45.7% | 45.7% (**0.0%** / 45.7%) | 1.000 → 1.000 |
| P2 | *pool lost* | 24 | *not measurable* (≤ 24) | — | — | — | — |
| P5-v1 | `ft_p5_nb_s1337` | 60 | **30** | −30 | 38.3% | 62.9% (24.6% / 38.3%) | 0.574 → 1.000 |
| P5-v2 | `…nb_s1337.v2repro` | 73 | **41** | −32 | 38.7% | 62.9% (24.2% / 38.7%) | 0.588 → 1.000 |
| **P5-v3 (adopted)** | `…nb_s1337.v3` | **100** | **52** | −48 | 31.6% | 69.5% (37.9% / 31.6%) | 0.573 → 1.000 |
| P5-v4 | `…nb_s1337.v4` | 89 | **40** | −49 | 27.3% | 69.1% (41.8% / 27.3%) | 0.574 → 1.000 |
| P5-v5 | `ft_p5v2_nb_s1337` | 84 | **35** | −49 | 31.2% | 77.7% (46.5% / 31.2%) | 0.574 → 1.000 |
| P5-v6 | `ft_p5v6_nb_s1337` | 93 | **43** | −50 | 34.0% | 78.1% (44.1% / 34.0%) | 0.575 → 1.000 |

wb channel (`--spec wideband-sdr`): **P5-v3 wb 35 → 21** (copies 37.1% → 51.2%,
archetype 14.1%).

**★ THE RE-FROZEN BASELINE.** The adopt-only-if-better gate now reads, under
`ref-v2[189h/b5689490]`: **nb = 52** (was 100), **wb = 21** (was 35). Every future
arm is judged against those, at equal-or-better inductor ratio (unchanged:
nb 0.224, wb 0.077).

**Two readings that matter more than the headline drop.**

* **The P0 baseline is untouched: 16 → 16, with 0.0% archetype copies.** A
  corpus-only arm cannot copy `templates.py`, so the reference extension bites
  *only* the template-trained arms — which is exactly the behaviour a correct fix
  should have. Every other number in the FINDINGS §5 prefix-12 row reproduces to
  the digit as well (valid 96.9%, specL0 26.6%, inductor ratio 0.141, copies
  45.7%), which is an end-to-end check that the protocol harness is intact.
* **Median NN-sim jumps 0.573 → 1.000 for every P5 arm.** Under ref-v1 the median
  screen-passing sample looked half-similar to its nearest corpus neighbour; under
  ref-v2 the *median* sample is a WL-exact match to something it was trained on.
  The copying pressure was always there — the old reference just could not see the
  half of it that came from the archetypes.

**Archetype copies among screen-passing samples** (the number Track B quoted):

| checkpoint | screen-passing | distinct | archetype copies | corpus copies | truly novel distinct |
|---|---|---|---|---|---|
| P0 prefix-12 | 68 | 27 | **0** (0.0%) | 49 | 16 |
| P5-v1 | 147 | 68 | 63 (42.9%) | 52 | 30 |
| P5-v2 | 165 | 80 | 62 (37.6%) | 61 | 41 |
| P5-v3 | 206 | 112 | 97 (47.1%) | 55 | 52 |
| P5-v4 | 188 | 97 | 107 (56.9%) | 38 | 40 |
| P5-v5 | 213 | 93 | **119** (55.9%) | 54 | 35 |
| P5-v6 | 215 | 102 | **113** (52.6%) | 58 | 43 |

Track B's independent count (against `dhruva-l1`'s screen) was **119/220** for v5
and **113/220** for v6 — the same 119 and 113 samples, reached through a different
screen and a different code path. Its truly-novel counts (52 / 35 / 43 for
v3 / v5 / v6) are likewise reproduced exactly. The finding replicates.

#### Recovering two pools that had been lost — and one checkpoint identification nobody had made

Two of the checkpoints that faced an adopt/reject decision had **no pool on disk**:
`seq*.txt` is gitignored, and `lna/out/ft_p5v2_nb_s1337/` had been *reused* for
P5-v5, overwriting P5-v2's samples. Both were recovered from checkpoints:

* `lna/_ndl_sample_ckpt.py` rebinds `finetune.ckpt_path` so a pool can be sampled
  from an arbitrary `.pth` **without copying a 198 MB file over the shared
  `ft_p5_v2.pth` path** — which was not acceptable with other agents live in the
  worktree.
* **Positive control first.** `ft_p5_v2.pre_dhruva.pth` was *claimed* to be P5-v3,
  whose pool does survive. Re-sampling it at seed 1337 reproduced that pool
  **byte-for-byte: 0 of 256 seq files differ.** So the regeneration is exact, and
  — a fact nobody had established — **`ft_p5_v2.pre_dhruva.pth` is the adopted
  P5-v3 baseline generator.** (`ft_p5_v2.pth` itself holds *P5-v5*, md5
  `805fda53…`, per Track B's restore. Reproducing the nb baseline of 100/52 needs
  the `pre_dhruva` file, not the `_v2` one.)
* `ft_p5_v2.pre_broaden.pth` then re-sampled to a pool reading **ref-v1 NDL@256 =
  73** — the historical P5-v2 number to the digit, which both recovers the pool and
  confirms the checkpoint's identity.
* The **P0 prefix-12 baseline** was regenerated the same way from the untouched
  upstream `Pretrain.pth` (args copied from the surviving `meta.json`), and
  reproduces its frozen row exactly, as noted above.
* **Still lost: the P2 pool.** `ft_p2.pth` is not on disk and the seq files were
  gitignored, so P2's ref-v2 number is *not measurable* and is reported as such
  rather than skipped. It is bounded (see the flip check).

#### ⚠ The flip check — Track B's conclusion is CONFIRMED for decisions, but its stated reason is WRONG

Track B wrote: *"The ordering between checkpoints is unaffected … so no past
adopt/reject decision flips."* The conclusion holds. The reason does not — and it
matters, because the reason is what anyone would rely on next time.

Every adopt/reject decision the program actually took, re-scored:

| # | decision | ref-v1 | verdict | ref-v2 | verdict | flips? |
|---|---|---|---|---|---|---|
| 1 | prefix-12 baseline → **P2** | 16 → 24 | ADOPT | 16 → ≤ 24 | ADOPT | **no** (inferred, see below) |
| 2 | P2 → **P5-v1** | 24 → 60 | ADOPT | ≤ 24 → 30 | ADOPT | **no** (proved) |
| 3 | P5-v1 → **P5-v2** | 60 → 73 | ADOPT | 30 → 41 | ADOPT | **no** (measured) |
| 4 | P5-v2 → **P5-v3** | 73 → 100 | ADOPT | 41 → 52 | ADOPT | **no** (measured) |
| 5 | P5-v3 vs P5-v4 | 100 vs 89 | reject | 52 vs 40 | reject | **no** (measured) |
| 6 | P5-v3 vs P5-v5 | 100 vs 84 | reject | 52 vs 35 | reject | **no** (measured) |
| 7 | P5-v3 vs P5-v6 | 100 vs 93 | reject | 52 vs 43 | reject | **no** (measured) |
| 8 | wb channel: P5-v3 sets the first wb baseline | 35 | new baseline | 21 | new baseline | n/a |

**Verdict: no historical adopt/reject decision flips under ref-v2.** Five are
measured outright, one is proved, one is inferred.

*Decision 2 is proved without the missing pool.* ref-v2 ⊋ ref-v1, and adding
hashes to the reference can only ever *remove* items from the novel set, so
`NDL_v2(X) ≤ NDL_v1(X)` for every X. Hence `NDL_v2(P2) ≤ 24 < 30 = NDL_v2(P5-v1)`,
and adopting P5-v1 over P2 holds whatever P2's pool was.

*Decision 1 is inferred, not proved.* Monotonicity bounds both sides and cannot
separate them. But the measured P0 baseline has **0.0% archetype copies**, and P2
— like the baseline — was fine-tuned on the corpus alone, before `templates.py`
existed. A non-template-trained arm has no mechanism for archetype regurgitation,
so `NDL_v2(P2) ≈ 24 > 16`. Stated as inference because `ft_p2.pth` is gone.

**★ But the *ranking* is NOT order-preserving, which is what Track B got wrong.**
Track B checked only v3 / v5 / v6, where ref-v2 happens to preserve the order.
With P5-v2 recovered:

```
ref-v1:  v3 100  >  v6 93  >  v4 89  >  v5 84  >  v2 73  >  v1 60
ref-v2:  v3  52  >  v6 43  >  v2 41  >  v4 40  >  v5 35  >  v1 30
                              ^^^^^ P5-v2 rises from 5th to 3rd
```

**P5-v2 overtakes both P5-v4 and P5-v5** (73 < 84 and 73 < 89 become 41 > 35 and
41 > 40). P5-v2 was trained on the 92-archetype era set and regurgitates less of it
(24.2% of samples) than the v3+ checkpoints do of their 118–148-archetype sets
(37.9–46.5%), so the correction costs it far less. No decision turns on those two
pairs — the adopt rule compares a candidate to *the then-current baseline*, which
was v3 for all of v4/v5/v6, never v2 — so the conclusion survives. The general
claim "ref-v2 preserves the checkpoint ordering" does not, and should not be
relied on for future comparisons: **the correction is not a constant offset**
(Δ ranges 0 to −50) and it scales with how much archetype mass the arm was trained
on.

**Honest read on the trend.** Under ref-v1, NDL looked like 60 → 73 → 100 → (89,
84, 93): a rise then a plateau. Under ref-v2 it reads 30 → 41 → 52 → (40, 35, 43),
the same shape — the generator's genuine-novelty peak really is P5-v3, and the
rfb-family fine-tunes really did cost diversity. What ref-v2 adds is the level:
**the adopted generator produces 52 novel distinct screen-passing topologies per
256 samples, not 100, and 47% of its screen-passing output is verbatim training
archetype.**

#### What did *not* change, deliberately

`corpus_reference()` keeps ref-v1 semantics exactly (verified: it returns the same
41 hashes). `campaign.py`, `loop.py`, `size.py` and `trackb_g4.py` all call it for
their own novelty checks and are **untouched** — they are not this session's files.
Those four call sites still ask "is this in the corpus?" when they mean "is this
new?", which is the same defect in four more places; migrating them to
`novelty.reference()` is a follow-up, and until then a `novel=True` flag on a
label row means ref-v1-novel. Note the Track-B `seq0192` dhruva-l1 claim is
**unaffected** — it was explicitly checked against all 148 archetypes *and* the 41
corpus circuits at the time, i.e. against ref-v2 by hand.

```bash
python lna/novelty.py --show-ref                    # reference audit + digests
python lna/novelty.py --eval <dir> [...] --ref both --spec wifi24   # old vs new
python lna/novelty.py --eval <dir> --ref v1         # reproduce a historical number
python lna/novelty.py --refresh-ref                 # rebuild after templates.py grows
```

### 14.6 Metrics governance (2026-08-09): Gate C1's enrichment half, restated

The second frozen-protocol item §14.2 escalated. The Spearman half of C1 —
**ρ(S21) ≥ 0.5 on held-out families — is UNCHANGED.** Only the enrichment half
moves.

**Why the old bar had to go, in one line of algebra.** With `k` rows selected out
of `n` and `n_near = base·n` truly near-feasible, at most `min(n_near, k)` of the
selection can be near-feasible, so

```
ceiling precision  = min(n_near, k)/k = min(base/k_frac, 1)
ceiling enrichment = ceiling precision / base = min(1/k_frac, 1/base)
```

(verified numerically against the closed form across base ∈ [0.02, 0.9] — exact
match). At `k_frac = 0.2` the enrichment ceiling is 5× while base ≤ 0.2, then
collapses as `1/base`. The pool improved from base 0.268 to 0.455 and the ceiling
fell **3.74× → 2.20×**, so "enrichment ≥ 2×" quietly turned into "precision@20% ≥
0.910", and at base ≥ 0.5 it becomes *unsatisfiable by a perfect ranker*. **The
gate was getting harder because the candidates were getting better** — which is
backwards, and is why nothing passed it on either split last night.

**Why not the literal fraction-of-ceiling.** `precision / ceiling_precision` is
reported (column `ofceil`) but is **not** the gate: random selection scores
`base / ceiling_precision`, which moves with the pool, so a fixed threshold on it
— exactly like a raw precision threshold — is passed or failed by a coin flip
depending only on how good the pool already is. The same objection kills "gate on
precision@20% ≥ 0.8".

**The restatement — fraction of ceiling, measured from random rather than zero:**

> **Gate C1 (restated 2026-08-09).** On held-out families, both of:
> **(a) ρ(S21) ≥ 0.5** (unchanged), and
> **(b) selection skill ≥ θ = 0.25**, where
> **skill = (precision@20% − base) / (ceiling precision − base)**,
> `ceiling precision = min(n_near, k)/k`, `k = round(0.2·n)`.
> Skill is **0 for random selection and 1 for a perfect ranker at any base rate**.
> When `ceiling precision = base` the split admits no discrimination at all; the
> gate reports **n/a** and is not evaluable — never a silent pass.

**Where θ = 0.25 comes from — it is derived, not tuned.** In the regime where the
frozen bar was well-posed (`base ≤ k_frac`, so `ceiling precision = base/0.2`),
"enrichment ≥ 2×" means `precision ≥ 2·base`, and

```
skill at the old bar = (2b − b) / (b/0.2 − b) = 1/4   exactly, for every such b
```

So **θ = 0.25 is the unique constant that reproduces the frozen gate's meaning
everywhere the frozen gate had one**, and drops the silent tightening above it.
(Verified to six decimals at base = 0.02/0.05/0.10/0.15/0.20. For
0.2 < base < 0.5 the old bar's implied skill climbs 0.25 → 1.00 — that climb *is*
the defect, not the intent.)

**Properties, checked rather than asserted** (20 000 Monte-Carlo draws per cell):

| requirement | result |
|---|---|
| random selection fails at any base rate | mean skill +0.0022 … −0.0174 across base 0.05–0.9 — **unbiased at 0** |
| a perfect ranker passes at any base rate | skill = **1.0000** at base 0.02 … 0.99 (where the old bar scored 5.00× down to 1.01×) |
| ceiling formula = `min(1/k_frac, 1/base)` | exact match, base 0.02–0.9 |
| degenerate split (base = 0 or 1) | skill NaN → verdict `n/a`, not a pass |
| **historical v2-train family pass survives** | WL-kNN precision@20% **1.000** at base 0.485 → **skill 1.000 → PASS** |

⚠ **One correction to the brief.** The v2-train family-split pass is often quoted
as "prec@20% = 0.842 at base ~0.27, enrichment 2.06× vs ceiling 3.74×". Re-running
`critic.py --eval --snapshot v2-train` reproduces the actual record: the v2-train
**family** pass was **prec@20% = 1.000 at base 0.485, enrichment 2.06× = its
ceiling of 2.06×** — a *perfect* top-20%, not a 2× margin. The 0.842 is the
**v4-train family** WL-kNN number; the base 0.27 / ceiling 3.74× belong to the
**v2-train source-shift** split, which *failed* (best 1.33×). So the historical
pass is a perfect ranker and constrains θ only to θ ≤ 1 — it cannot calibrate θ by
itself, which is why θ is derived from the old bar's algebra instead.

#### Re-scored: v4-train, per arm and per split

σ_S21 = 0.726 dB (best-of-3). `ceiling precision = 1.000` on both splits, so here
`ofceil` coincides with `prec@20%`; they diverge whenever base < 0.2.

| split | arm | ρ(S21) | prec@20% | base | enrich (old) | ceiling | **skill** | C1 old | **C1 restated** |
|---|---|---|---|---|---|---|---|---|---|
| family holdout (n=95, k=19) | trivial | – | 0.495 | 0.495 | 1.00× | 2.02× | 0.000 | no | **no** |
| | WL-kNN | 0.687 | 0.842 | 0.495 | 1.70× | 2.02× | **0.687** | no | **YES** |
| | ridge | 0.790 | 0.737 | 0.495 | 1.49× | 2.02× | **0.479** | no | **YES** |
| | **GNN (ens-5)** | 0.839 | **0.895** | 0.495 | 1.81× | 2.02× | **0.792** | no | **YES** |
| source-shift (n=420, k=84) | trivial | – | 0.455 | 0.455 | 1.00× | 2.20× | 0.000 | no | **no** |
| | WL-kNN | 0.370 | 0.512 | 0.455 | 1.13× | 2.20× | 0.105 | no | **no** |
| | ridge | 0.585 | 0.655 | 0.455 | 1.44× | 2.20× | **0.367** | no | **YES** |
| | **GNN (ens-5)** | 0.610 | 0.655 | 0.455 | 1.44× | 2.20× | **0.367** | no | **YES** |

**★ Verdict. On C1's letter — held-out families — all three model arms now pass:
WL-kNN, ridge and the shipped GNN. The trivial arm fails, as it must.** On the
harder source-shift split (the honest number for ranking *generated* candidates,
and the one 03-SEARCH actually spends), **ridge and the GNN pass; WL-kNN fails**
— it is the only arm the restatement does *not* rescue, consistent with §14.2's
finding that the kNN baseline lives on duplicate structure and collapses
(ρ = 0.003) on the novel Track-B pool. Under the retired bar **nothing passed
anywhere**, including a perfect ranker.

The GNN numbers are tonight's fresh ensemble (ρ(S21) 0.839 family / 0.610
source-shift vs 0.851 / 0.609 last night — ensemble seed variation, prec@20%
identical at 0.895 / 0.655). Its test sets are byte-identical to the baselines'
(47/95 and 191/420 near-feasible), so the two tables are directly comparable.

**θ is not knife-edge, and the passes are not luck.** The verdict set above is
**identical for every θ in [0.25, 0.35]**; only at θ = 0.40 does the source-shift
pair drop out, and at θ = 0.50 the ridge family pass does too. Separately, the
finite-sample false-pass rate of *random* selection at θ = 0.25 is **14.0% on the
family split** (n = 95 ⇒ k = 19, skill sd 0.203) and **0.3% on the source-shift
split** (n = 420 ⇒ k = 84, sd 0.089). So a *marginal* family-split pass would be
weak evidence — but the measured ones sit at 2.4 σ (ridge), 3.4 σ (WL-kNN) and
3.9 σ (GNN) above random, and the source-shift passes at 4.1 σ. **The family
split's 19-row top-20% is the weakest link in C1 and always was** (it is a
property of the holdout size, not of the restatement); the fix is a larger family
holdout, and until then the source-shift number should carry the weight.

**What this does and does not license.** C1 is the "is the critic worth wiring
into search at all" gate, and it is now passable and passed. It is *not* a claim
that the critic is good: skill 0.367 on generated candidates means the top-20%
captures about a third of the available improvement over random, and 03-SEARCH's
own S1 bar (2× near-feasible enrichment from reranking) is a separate,
still-unmet measurement.

**Implementation.** `critic.c1_stats()` returns base / k / prec / ceil_prec /
enrich / ceil_enrich / frac_ceiling / skill from one selection; `critic.c1_pass()`
applies the gate. `enrichment_top20()` is kept as a byte-compatible 4-tuple
wrapper so `critic_gnn.py`'s existing unpacking is untouched — **its own printed
`C1?` column therefore still shows the retired verdict**, and that file's two-line
reporting update is a follow-up for whoever owns it next (the numbers above were
computed from its measured prec@20% through `critic.c1_stats`, the same code path).
`--eval` prints the old `enrich` and the new `ofceil` / `skill` side by side, plus
the precision each bar implies at the measured base rate.

```bash
python lna/critic.py --eval --snapshot v4-train --sigma-recipe candidate-v1+bo3
python lna/critic.py --eval --snapshot v2-train    # reproduces the historical pass
```

## 15. Phase 2 — WP-SEARCH **rung 2**: evolutionary search over graph edits, with a control (Session 5)

plans2/03-SEARCH §2 asks for search to leave token space: the LM seeds a
population, mutation and crossover work on the *circuit*, critic v1 decides where
SPICE minutes go, and the top elites of every generation get a true sizing run
that is appended to the store. This section is that experiment, run to budget on
two specs, each against a control that differs **only in selection**.

The yardstick is 03-SEARCH's fixed one — feasible novel designs per equal SPICE
budget — so every table below is SPICE, never critic. Critic numbers appear once,
in §15.4, explicitly labelled as calibration.

### 15.1 What was built

* **`lna/moves.py` — stratum M, 17 one-edit graph moves.** The genome is the
  `read_netlist` netlist `templates.py` already uses, because that is the one form
  the upstream Eulerian pipeline consumes. Every mutant round-trips
  `netlist → emit_sequence → tokens → Topology → L0 screen → WL hash`, and the
  genome is then **re-derived from the realized topology** (`topo_to_netlist`), so
  genotype and phenotype cannot drift apart. Moves are semantic where 03-SEARCH
  names them — load class (R ↔ LC tank ↔ shunt-peaked), ±cascode, ±output buffer,
  ±degeneration, ±shunt feedback, ±tuned gain stage, input-stage class swap
  (CS ↔ CG, with the CG gate left undriven+bypassed so `bias.py`'s R-GATE owns the
  bias — the Session-4 lesson), matching-element add, auxiliary/noise-cancelling
  path add — and blind where they are not (passive type substitution, terminal
  rewire, element deletion). Nothing writes a device *value*; sizing stays ZOAF's
  job. Spec-derived budgets (`device_budget`, `max_inductors`) are enforced *inside*
  the move, so a move never proposes what the screen must then discard.
  **Measured yield** (`python lna/moves.py --selftest`, wideband-sdr, 300
  proposals off archetype seeds): **290 realized (96.7%), 247 distinct WL hashes.**
  Per-move realization is ≥0.95 for all but `feedback_remove` (0.71) and
  `degen_remove` (0.00 — removing the only inductor from a CS stage leaves neither
  a CG nor a feedback input, so `_match_plausible` correctly rejects it).
* **Decomposition crossover.** Both parents are cut at a signal-path stage
  boundary — an interstage coupler whose upstream side is a FET drain and
  downstream side a FET gate, i.e. the seam `templates._tuned_chain` emits — and
  head(A) is spliced to tail(B) through a fresh coupling capacitor, with B's nodes
  renamed. Parents with no cut are **skipped, not forced** (§2's rule). It is a
  minority operator by construction: only **4/60** archetype pairs realize, because
  most archetypes are single-stage. It still earned its place — see §15.3.
* **The §4 trust rules, mechanically.** (1) Selection consumes `mean − β·σ`, β = 1,
  never the raw mean. (2) **Uncertainty gate**: `lna/evolve_score.py` trains the
  critic-v1 ensemble once against a pinned snapshot and calibrates the 90th
  percentile of holdout ensemble σ on a family split it never trained on
  (σ_gate ≈ 0.31–0.40 across runs); an individual above it cannot displace a
  trusted elite on its score. (3) **Trust region**: an offspring further than the
  store's own family radius (`datastore.FAMILY_SIM = 0.9` WL-cosine) from every
  labeled row is untrusted until a true eval exists for it. Untrusted individuals
  are not discarded — they are routed to an **exploration stratum** holding 25% of
  the population and owning one true-eval slot per generation, which is where §4
  rule 2 says they belong. (4) Only SPICE numbers are results.
* **The control (`--arm random`).** Identical seeds, move set, validity gates, L1
  gate, dedup and true-eval recipe; selection replaced by uniform random choice and
  no critic process at all. This isolates *selection quality*, holding candidate
  supply constant, and is the rung-2 shape of 03-SEARCH §1's "size k random picks
  from the identical pool" control. Rung 1 was never run live on either of these
  specs, so this — not rung-1 rerank — is the control the S2 verdict is read
  against, and that substitution is stated rather than hidden.
* **True eval = the real thing.** bias insertion → ZOAF (8 candidates / 8 SGD /
  2 CGD, `inductor_q=12`) → **box-clamped** bounded polish (80 sims; never the
  pre-2026-08-08 unclamped polish), a second ZOAF seed only when the first lands
  within 1.2 total violation (same rule in both arms). Every result is appended to
  the store under a distinct recipe (`evolve-v1` / `evolve-ctrl-v1`) with
  `nf_gated: true`, so it forms its own label domain and cannot contaminate the
  `candidate-v1+bo3` σ groups.
* **One performance finding worth carrying.** Every ngspice caller in the tree
  (`bias.run_op`, `extract.run_and_extract`, `templates.emit_paths`) `mkdtemp`s per
  call and none clean up; the shared `%TEMP%` was already carrying **16k+ `bias_*`
  directories** from earlier sessions. `moves.private_tmp()` now points the driver
  process's `tempfile` at a per-run scratch root that is wiped every generation.
  Separately, the L1 gate must be **one** op solve, not `bias.feasibility_sweep`:
  the sweep is a grid over the inserted VBG knobs (up to 16 ngspice runs) and at
  ~150 proposals a generation it cost more wall-clock than every sizing run put
  together. With both fixed, offspring generation is 10–30 s/generation.

### 15.2 `wideband-sdr` — the primary, and a clean negative

The open half of Gate B1: 0 feasible ever, and the benchmark's binding column
(`s11 ×6, s21 ×4, s21_ripple ×2`) was measured over a candidate set of *narrowband*
designs. Rung 2 gets to ask the question with topologies built for the spec.

| arm | true evals | SPICE-min | feasible | novel feasible | near-feasible | best total violation | K<1 |
|---|---|---|---|---|---|---|---|
| **evolve** | 42 | 51.2 | **0** | **0** | 6 | **1.782** | 6 |
| control | 60 | 76.0 | **0** | **0** | 9 | 1.931 | 14 |

At an equal budget of **51.2 SPICE-min** (both arms truncated to the smaller arm's
spend): evolve 42 evals / 6 near-feasible / best 1.782; control 39 evals /
8 near-feasible / best 1.931. On the fixed yardstick the two arms are a dead heat —
**8.5 SPICE-min per near-feasible design for the evolve arm, 8.4 for the control.**
Critic guidance bought nothing here, and §15.4 says why in one number.

*(“near-feasible” is 03-SEARCH's all-margins > −1 scale unit, computed over the
four margins the critic heads predict — S11/S21/Idd/NF. `s21_ripple_db` is gated
by this spec but is not a critic head, so it is excluded from that count and
reported separately below.)*

**What actually binds is noise, on every single design.** Across **102/102** true
evaluations in both arms, `nf_db` is violated — there is no exception in the whole
run. The rest, per arm (count violated / n, and the best gap any one design
reached):

| constraint | evolve 42 | control 60 |
|---|---|---|
| `nf_db` | **42/42** (best gap 0.168 → NF **4.09** dB vs 3.5) | **60/60** (best gap 0.378) |
| `s21_ripple_db` | 40/42 (best gap 0.201 → **2.40** dB vs 2) | 42/60 (best gap 0.012) |
| `s11_db` | 33/42 (best gap 0.084) | 56/60 (best gap 0.058) |
| `s21_db` | 32/42 (best gap 0.055 → **11.3** dB vs 12) | 56/60 (best gap 0.006) |
| `idd_ma` | 6/42 (best gap 0.010) | 17/60 (best gap 0.136) |

Every constraint is individually within ~0.4 dB of clearing *on some design* — and
no design clears more than four of five at once. The front is not blocked by one
wall; it is blocked by the **conjunction**, and the term that never yields is NF.
Two more things the table hides:

* **The violation scalar rewards degenerate designs on this spec.** The lowest-
  violation individual (`01389e803d2e`, 1.782) is a **4-device** network with
  S21 −1.0 dB, Idd 0.35 mA, NF 4.09, S11 −10.2 — a near-passive front end that
  scores well on NF/Idd/S11 and loses only on gain. The best *amplifier* is
  `6507bd03296d` (novel, 12 devices, `stage_add`): S11 −17.5 / S21 **18.3** /
  ripple 3.77 / Idd 3.12 / NF 6.78 / K_min 75.4. When a spec's hardest constraint
  is one that shrinking the circuit improves, feasibility-first total violation is
  not a safe progress metric on its own.
* **Population drift is real and it ends at the device budget.** Mean device count
  climbs 8.6 → 14.1 (evolve) and 9.4 → 14.4 (control) over 20 generations against a
  `[3,16]` budget: the move set is net-additive, so late generations spend their
  proposals against the ceiling. ~550 distinct valid, L1-passing topologies were
  generated per arm; 42 and 60 of them earned a true eval (7.6% / 10.9%).

### 15.3 ★ `dhruva-s` — a novel tier-1-feasible design, and the Gate-D3 front moves 3.3 dB

| arm | true evals | SPICE-min | tier-2 feasible | near-feasible | best total violation | K<1 |
|---|---|---|---|---|---|---|
| **evolve** | 47 | 69.1 | 0 | **41** (87%) | **0.642** → **0.594** polished | 2 |
| control | 60 | 62.4 | 0 | 28 (47%) | 1.070 | 21 |

At an equal 62.4 SPICE-min: evolve 44 evals / **38** near-feasible / best 0.642;
control 60 evals / 28 near-feasible / best 1.070. **Nine of the ten
lowest-violation designs in the joint run are from the evolve arm, and eight of
those ten are novel.** The control also produced **21 sizings with in-band K < 1**
against the evolve arm's 2 — unguided drift walks into potential instability an
order of magnitude more often.

**The headline is a design, and it is replay-verified SPICE truth.**

> **`8c7592ea859e489a`** — 16 devices, evolve arm **generation 18**, move
> `passive_type_swap` off parent `5a013cb99cdfe560`, WL-similarity to the nearest
> labeled graph 0.927 (inside the trust region, so it was selected on its critic
> score legitimately).
>
> | | S11_max (1.1–2.5 GHz) | S21 @ 2.492 GHz | Idd | NF | K_min |
> |---|---|---|---|---|---|
> | as found | −10.09 ✓ | 30.74 ✓ | 12.58 ✓ | 5.75 | 8.03 |
> | **+ tier-1 boundary polish** (box-clamped, 120 sims) | **−10.94 ✓** | **34.89 ✓** | **11.84 ✓** | **5.58** | **6.54** |
>
> **TIER-1 FEASIBLE** (min normalized tier-1 margin 0.089 after polish, up from
> 0.008 as found), **in-box verified**, `replay_ok` **True**, unconditionally
> stable in band. **Novel**: the WL hash matches none of the 148 `templates.py`
> archetypes, none of the 41 corpus LNAs, and no pre-existing store row.

Structurally it is a noise-cancelling CG+CS descendant that the search rearranged:
common-gate input (`NM1`, source on the DC-blocked input node, gate undriven and
bypassed so `bias.py` owns its current) with a **resistive** CG load, the CG output
re-inverted through **two tuned CS stages**, and — the edit that matters — the
auxiliary noise-cancelling path (`NM4`, AC-coupled off the input node) summing at
the **output tank node**, i.e. moved downstream past both gain stages rather than
landing on the first summing node the way `templates.nc_cgcs_lna` writes it.

**What this changes on the Gate-D3 ladder.** There are now three tier-1-feasible
dhruva-s rows in the store:

| design | provenance | S11_max | S21 | Idd | NF | tier-2 violation |
|---|---|---|---|---|---|---|
| `3ebaf08f99d3` (`rfbcs3_tank_cc21_bf0`) | assistant-authored archetype, Session 3 | −10.25 | 34.64 | 8.70 | **8.88** | 1.537 |
| `8c7592ea859e` as found | **search, Session 5** | −10.09 | 30.74 | 12.58 | 5.75 | 0.642 |
| `8c7592ea859e` polished | **search, Session 5** | −10.94 | 34.89 | 11.84 | **5.58** | **0.594** |

**The best NF among tier-1-feasible dhruva-s designs improves 8.88 → 5.58 dB
(−3.30 dB), and the tier-2 violation of a tier-1-clean design improves 1.537 →
0.594 — 2.6× closer to Gate D3.** **Gate D3 is still NOT MET**: 2.08 dB of noise
remain, and the design's *only* violated constraint is NF.

Two honest qualifications. (a) The program's lowest dhruva-s total violation is
still **0.566**, held by the `nccgcs_s1_R` archetype (Session 4, NF 4.38) — which
is *not* tier-1 feasible (S11_max −9.38, S21 22.44). So on "closest to tier-2" the
record moved from 0.566 to 0.594 in the wrong direction by 0.028; what moved is the
*conditioning* of the front — one binding constraint with margin on the other
three, instead of three simultaneous near-misses. (b) The evolve arm also produced
`19f723034c0a` (novel, **crossover**): S11_max **−16.90** / S21 20.06 / Idd 8.34 /
**NF 4.66** / K_min 50.9 — 6.9 dB of match margin and the second-best NF ever
measured on this spec, short only on gain. The two designs bracket the remaining
Gate-D3 trade, and both came from this move set.

Move attribution over the ten lowest-violation dhruva-s designs: `passive_type_swap`
×5, `crossover` ×2, `load_swap` ×2, unmutated archetype ×1. The blind
type-substitution move — not any of the semantic ones — did most of the work,
which is worth remembering before the move set is "improved" toward more
hand-designed edits.

### 15.4 Critic v1 in deployment — the number that explains both results

Critic scores are **not** results; this subsection exists because 03-SEARCH §4's
trust rules are only as good as the model's deployment-distribution skill, and
tonight measured it two ways. The control arm's true evals were drawn at random and
the critic never saw them, so scoring them **post hoc** (`evolve.py --calibrate`)
gives a selection-free estimate; the evolve arm's elites are range-restricted by
construction and are reported separately.

| | wideband-sdr | dhruva-s |
|---|---|---|
| in-distribution holdout (family split, n=95) ρ(S21) | 0.834 | 0.839 |
| holdout rank accuracy | 0.841 | 0.846 |
| **control arm, post hoc (n=60)** ρ(feasibility scalar) | **+0.174** | **+0.198** |
| control arm ρ(`mean − β·σ`) | +0.175 | +0.220 |
| control arm ρ(σ, \|error\|) | +0.147 | +0.458 |
| control arm precision@top-20% / base rate | 0.250 / 0.150 = **1.67×** (ceiling 6.67×) | 0.583 / 0.467 = **1.25×** (ceiling 2.14×) |
| **evolve arm, selected elites** ρ(feasibility scalar) | **−0.334** (n=42) | **−0.030** (n=47) |
| evolve arm ρ(`mean − β·σ`) | −0.345 | −0.014 |

Read together: **critic v1 keeps ρ ≈ 0.83 on its own family holdout and collapses
to ρ ≈ +0.17…+0.20 on the mutant distribution the search actually generates** — a
fifth of the in-distribution number, and far below Gate C1's 0.5 bar. On the elites
it selected, the residual correlation is zero to negative. That is the whole story
of §15.2: a ranker with ρ ≈ 0.17 cannot beat coin-flip selection by 2×, and it did
not. On dhruva-s the same weak-but-positive signal was enough to matter, because
there the population starts near a real front and the critic only has to avoid
throwing it away — near-feasible 87% vs 47%, best violation 0.642 vs 1.070.

**The diagnosis is coverage, and it is measurable.** Of `v4-train`'s 734 rows,
**wifi24 has 424 and dhruva-l1 has 233; wideband-sdr has 16 (2.2%) and dhruva-s has
24 (3.3%)**. The spec-conditioning vector is the only thing telling the model these
are different problems, and for the two specs the program most wants to solve it
has almost no signal behind it. Tonight's run appended **213 rows** —
**105 wideband-sdr and 108 dhruva-s** — which takes those two specs from 40 rows to
253 and is precisely the "search manufactures its own training data" bridge
03-SEARCH §2 promised. **A retrain on the enlarged store is the single highest-value
next step**, and unlike everything else here it is free of new SPICE.

**The uncertainty gate never fired, and its premise is not reliable off-
distribution.** Across all 80 generations of all four runs, `n_high_unc = 0` in
every population: ensemble σ on a mutant never once exceeded the holdout p90
threshold. The gate as specified is therefore **inert** — the ensemble is
*confidently* wrong off-distribution rather than visibly uncertain, which is the
known failure mode of a deep ensemble under covariate shift. ρ(σ, |error|) agrees
that it is not a dependable signal here: +0.147 on the unselected wideband control,
+0.458 on the unselected dhruva-s control, and on the *selected* dhruva-s elites it
is **−0.510** under the run's own ensemble and **+0.137** under the post-hoc one —
i.e. the sign is not even stable across ensemble seeds once selection has
range-restricted the sample.

The **trust region**, by contrast, did real work. The evolve arm filled all 24 of
its trusted slots in every generation of both specs (there were always ≥24 trusted
candidates), while the control populations drifted out of the labeled families
entirely — trusted membership fell to as low as **4/32** on wideband-sdr and
**1/32** on dhruva-s, with 32/32 individuals beyond the family radius by the end of
both control runs. The exploration stratum's dedicated true-eval slot is what put
SPICE labels on those drifted regions instead of letting the critic score decide
about them.

### 15.5 Gate S2 verdict, cost, and what follows

**Gate S2 — NOT MET, on both specs, under the plan's stated bar.** 03-SEARCH §2
asks for ≥2× the feasible novel designs of rung-1 rerank at equal true-eval budget,
or the program's first Gate-G4 design. Both arms produced **0** fully feasible
(tier-2) designs on both specs, so the ratio is undefined and the gate fails; the
G4 clause was already closed in Session 4 and is not reachable here. Rung 1 has
never been run live on either spec, so the comparison is against the equal-budget
random-selection control, stated as a substitution.

Raw numbers, so an enrichment-style restatement can be computed either way
(cf. §14.2's ceiling problem — a ratio bar is only meaningful next to its ceiling):

| spec | arm | true evals | SPICE-min | feasible | near-feasible | base rate | best violation |
|---|---|---|---|---|---|---|---|
| wideband-sdr | evolve | 42 | 51.2 | 0 | 6 | 0.143 | 1.782 |
| wideband-sdr | control | 60 | 76.0 | 0 | 9 | 0.150 | 1.931 |
| dhruva-s | evolve | 47 | 69.1 | 0 | 41 | 0.872 | 0.642 (0.594 polished) |
| dhruva-s | control | 60 | 62.4 | 0 | 28 | 0.467 | 1.070 |

**SPICE accounting.** 209 true evaluations, **262.7 SPICE-minutes** in the four
arms (51.2 + 76.0 + 69.1 + 62.4), plus ~3 min of verification/polish. 213 L2 rows
appended (209 distinct topologies + the polished winner + 3 rows from an aborted
first launch, all provenance-tagged `evolve-*`); JSONL integrity verified with two
other agents writing concurrently (0 malformed lines in 1010).

What the night says to do next, in order:

1. **Retrain the critic on the enlarged store.** wideband-sdr 16 → 105 rows and
   dhruva-s 24 → 108. §15.4 shows the deployment-distribution ρ is the binding
   constraint on rung 2, and this is the only lever that costs no SPICE. Re-run
   `evolve.py --calibrate` against the same stored arms afterwards — the comparison
   is already set up and needs no new simulation.
2. **Gate D3 is now 2.08 dB of NF on a tier-1-clean, stable, novel topology.**
   That is a far better starting point than Session 4's "0.9 dB but violating three
   constraints", and the lever Session 4 identified still applies: the sizer never
   sits on the noise-cancellation locus, so an **NF-only inner optimization stage**
   (or a cancellation-aware start) on `8c7592ea859e489a` and `19f723034c0a` is the
   next move — not more topology search.
3. **wideband-sdr needs the spec re-read before more search.** NF is violated on
   102/102 designs while every other constraint is individually within ~0.4 dB on
   *some* design. Either the ≤1-inductor / ≤8 mA / 0.5–3 GHz corner genuinely
   excludes a 3.5 dB single-ended front end at this node, or the harness/objective
   is mis-serving it. That is a measurement question (sweep NF against the
   inductor budget), not a search question.
4. **Put stability in the objective**, still. 21 of 60 control-arm dhruva-s
   sizings read in-band K < 1 — the Session-4 recommendation is now quantified.
5. **Guard the violation scalar against degenerate optima** on specs where the
   hardest constraint improves as the circuit shrinks (§15.2).

```bash
python lna/moves.py --selftest --spec wideband-sdr            # move-set yield table
python lna/evolve.py --spec dhruva-s --arm evolve --pop 32 --children 24 \
    --gens 20 --elites 2 --explore 1 --true-evals 60 --out lna/out/_evolve_ds_evolve
python lna/evolve.py --spec dhruva-s --arm random  ...        # the equal-budget control
python lna/evolve.py --report  <a>/state.json <b>/state.json  # scoreboard + S2 verdict
python lna/evolve.py --calibrate <a>/state.json <b>/state.json  # post-hoc critic ρ
```

## 16. Phase 3 — the template-free control experiment: how much of the generator is the scaffolding? (Session 5)

This section is a **measurement, not a proposal**. No arm here is a candidate for
adoption; `ft_ctrl*.pth` must not replace `ft_p5_v2.pre_dhruva.pth` as the
generator whatever the numbers say. The question is narrow and it has no "good"
answer, only an informative one:

> Every P5-era generator is fine-tuned on the Eulerian-augmented `templates.py`
> archetype set. §14.5 then measured that **47% of the adopted generator's
> screen-passing output is verbatim training archetype**. So: if the templates
> were taken away, would the generator collapse back to reciting the 41 corpus
> circuits — the way the historical template-free P1/P2 arms did (median NN-sim
> 1.000, NDL 16–24) — or has it internalized enough of the design space to hold a
> competitive front on its own?

Answer, in one line: **it is graded, not binary — the templates buy structural
*yield*, not novelty per token, and roughly half of the adopted generator's
genuine novelty survives their complete removal.**

### 16.1 The arms, and what "template-free" is allowed to mean

The control mirrors the P5-v3 lineage exactly, with every archetype sequence
removed. P5-v3 is a two-stage arm (`Pretrain.pth` → `ft_p5.pth` → `ft_p5_v2.pth`,
warm-started), so the control is two-stage too — a one-stage control would have
confounded "no templates" with "one fewer training stage".

| | stage A (from `Pretrain.pth`) | stage B (warm from stage A) | train / val rows | best val |
|---|---|---|---|---|
| **P5-v3** (adopted) | corpus + **2230 template rows (118 arch)** + replay | + winners (965) | 7734 / 736 | 0.2300 @ ep 1 |
| **ctrl-v1** | corpus + replay, **0 template rows** | + winners (965) | 5170 / 492 | **0.2162 @ ep 0** |
| **ctrl-v1s** (strict) | *same stage A as ctrl-v1* | + winners with every archetype row dropped (512) | 4649 / 492 | 0.2189 @ ep 0 |

Everything else is identical: `<LNA_NB>`/`<LNA_WB>` class tokens, lr 3e-5, batch
32, 40 epochs with the best-val checkpoint shipping, seed 1337, sampling at
n=256 / batch 32 / 256-token cap / temperature 0.7 from `<CLS> VSS`. The winners
file is pinned to `winners_train.pre_dhruva.json` — the *P5-v3-era* emission, 965
rows — not the current one, so the control sees exactly the winners P5-v3 saw.
(One documented deviation, on the secondary arm only: ctrl-v1s ran 12 epochs
rather than 40. Every fine-tune in this program takes its best val loss at epoch
0–1 and rises monotonically thereafter — P5-v3 0.2300 @ 1, ctrl stage A 0.2226 @
1 then 38 epochs of worsening, ctrl-v1 stage B 0.2162 @ 0 — and the shipped
checkpoint is the best-val one, so epochs 12–39 cannot change the artefact.
ctrl-v1 itself was run at the full 40 to keep the headline arm recipe-identical.)

**⚠ Why ctrl-v1s exists: "corpus + winners only" is not actually template-free.**
The winners channel is the store's own top quartile, and the store contains
stratum-T rows — hand archetypes that the sizing loop promoted. Measured on the
P5-v3-era winners file: **42 of its 77 distinct topologies are `templates.py`
archetypes, carrying 42.3% of the 965 rows** (3 more are corpus circuits; 32 are
genuinely new). So ctrl-v1 removes the deliberate 118-archetype *scaffolding* but
still sees 42 archetypes through the back door. ctrl-v1s drops those rows (512 of
965 survive, 32 distinct topologies) and is the only arm with **zero** archetype
exposure anywhere in its lineage. Both are reported; the difference between them
is the most informative number in the section.

`finetune.py` gained three additive flags for this (`--no-templates`,
`--templates-file` / `--winners-file`, `--tag`). Defaults are byte-unchanged, and
`--tag` renames only the checkpoint/out-dir stem so a side arm can never overwrite
a shared 198 MB `.pth` that another agent is sampling from.

```bash
# the strict winners file (deterministic; drop every row whose WL hash is in ref-v2)
python lna/_ctrl_strict_winners.py
# the two arms, on the WSL GPU (~20 min each at 40 epochs)
<gpu py> lna/finetune.py --arm p5 --do train --device cuda --no-templates --tag ctrl
<gpu py> lna/finetune.py --arm p5 --do train --device cuda --no-templates --tag ctrl \
    --winners --winners-file lna/out/winners_train.pre_dhruva.json
<gpu py> lna/finetune.py --arm p5 --do sample --device cuda --seed 1337 --n 256 \
    --class nb --winners --tag ctrl --out lna/out/ft_ctrl_nb_s1337
python lna/novelty.py --eval lna/out/ft_ctrl_nb_s1337 --spec wifi24 --ref both
python lna/_ctrl_front.py --pool lna/out/ft_ctrl_nb_s1337 --spec wifi24 \
    --arm ctrl-v1 --scan-limit 14 --top 5 --no-nf-gate
```

### 16.2 Pool metrics — the frozen protocol, n=256, seed 1337, `ref-v2[189h/b5689490]`

| arm | class | **NDL@256 v2** | NDL v1 | copies (arch / corpus) | med NN-sim v1 → v2 | spec-L0 | term | ind ratio | anyL |
|---|---|---|---|---|---|---|---|---|---|
| **P5-v3 (baseline)** | nb | **52** | 100 | 69.5% (**37.9%** / 31.6%) | 0.573 → 1.000 | **206 (80.5%)** | 100.0% | **0.224** | 93.8% |
| **ctrl-v1** | nb | **42** | 43 | 40.6% (**0.4%** / 40.2%) | 1.000 → 1.000 | 91 (35.5%) | 99.6% | 0.178 | 59.0% |
| **ctrl-v1s** | nb | **26** | 26 | 55.5% (**0.0%** / **55.5%**) | 1.000 → 1.000 | 90 (35.2%) | 98.8% | 0.179 | 59.4% |
| **P5-v3 (baseline)** | wb | **21** | 35 | 51.2% (14.1% / 37.1%) | 1.000 → 1.000 | **96 (37.5%)** | 99.6% | 0.077 | 39.5% |
| **ctrl-v1** | wb | **31** | 31 | 35.5% (**0.0%** / 35.5%) | 0.609 → 0.621 | 50 (19.5%) | 98.8% | 0.156 | 53.9% |

Historical anchors on the same stick: **P0 prefix-12 = 16**, **P2 ≤ 24** (bounded,
pool lost — §14.5). Distinct-WL-family counts equal NDL in every row above, so
the family metric adds nothing here and is omitted.

**Four things this table says.**

1. **★ The template contribution decomposes cleanly, and it is about half.**
   nb NDL@256 goes **52 → 42 → 26** as archetype exposure is removed in two
   steps. The full 2230-row scaffolding over 118 archetypes buys **+10** NDL over
   seeing 42 archetypes through the winners channel; those 42 back-door
   archetypes buy **+16** over seeing none at all. A generator with *no* archetype
   exposure of any kind still reaches **26**, i.e. **half the adopted baseline**
   and comfortably above P2's ≤24 and the P0 baseline's 16.
2. **★ Corpus copying rises exactly as archetype exposure falls: 31.6% → 40.2% →
   55.5%.** This is the P1/P2 memorization mechanism re-asserting itself, and it
   is *graded*: strip the structures the model can learn from and it falls back on
   reciting the 41 corpus graphs. The median screen-passing sample of both control
   arms is a WL-exact corpus circuit (median NN-sim 1.000 against ref-**v1**,
   where P5-v3 reads 0.573) — the historical collapse signature is present, but it
   coexists with a 26–42-topology novel tail rather than eliminating it.
3. **★★ The templates' real product is structural YIELD, not novelty per sample.**
   spec-L0 pass rate **80.5% → 35.5%** (nb) and **37.5% → 19.5%** (wb): the
   control produces less than half as many samples that are even shaped like an
   LNA. But *conditional on passing the screen*, the control is the more novel
   generator — NDL per screen-passing sample is **42/91 = 0.46** for ctrl-v1
   against **52/206 = 0.25** for P5-v3 (wb: **31/50 = 0.62** vs **21/96 = 0.22**).
   The archetype set is teaching the model what a valid LNA looks like; it is not
   what makes the output new.
4. **⚠ On the wb channel the control BEATS the re-frozen baseline: NDL 31 vs 21.**
   That is not a template win reversed by luck — it is §14.5's correction landing.
   P5-v3's wb pool is 14.1% verbatim archetype and its median wb sample is a
   WL-exact match to training data; the control's wb pool contains **zero**
   archetype copies and its median sample sits at NN-sim 0.62. **This is not an
   adopt:** the wb inductor ratio moves the wrong way for an inductorless spec
   (0.077 → 0.156), the adoption rule is "beat NDL at equal-or-better inductor
   ratio", and this arm is a control by construction. It does say the wb channel's
   headline number was carried by regurgitation more than by structure.

### 16.3 ★ The novel front — the decisive comparison

NDL counts new topologies; it says nothing about whether they are any *good*.
`lna/_ctrl_front.py` measures the other half under one fixed protocol applied
identically to every arm: take the pool's genuinely-novel candidates (WL hash
matching **no `templates.py` archetype, no corpus circuit and no existing store
row**), light all-free ZOAF scan (`n_candidates=4, sgd_iters=5, cgd_iters=1`) of
the first 14 in filename order, then **box-clamped** `size.polish` (never the
retired unclamped ascent — §13.3) on the top 5 by total violation. Tier-1 gating
(S11/S21/Idd), NF measured and advisory, so the numbers are comparable with the
program's whole feasibility record. Every result logged, recipe `ctrl-v1`, arm in
`provenance.source_arm`.

| arm | spec | novel front | sized | **feasible** | **best violation** | best design (replay-verified) |
|---|---|---|---|---|---|---|
| **P5-v3** | wifi24 | 45 | 14 | **1** | **0.000** | `seq0009` S11 −12.98 / S21 13.21 / Idd 3.63 · NF 3.50 adv |
| **ctrl-v1** | wifi24 | 35 | 14 | **1** | **0.000** | `seq0014` S11 −14.28 / S21 12.78 / Idd 4.36 · NF 3.57 adv |
| **ctrl-v1s** | wifi24 | 22 | 14 | 0 | **0.175** | `seq0043` S11 −9.0 / S21 17.5 / Idd 5.79 |
| **P5-v3** | dhruva-l1 | 45 | 14 | 0 | 1.023 | `seq0015` S11max −14.1 / S21 −0.6 / Idd 0.35 |
| **ctrl-v1** | dhruva-l1 | 36 | 14 | 0 | **0.960** | `seq0040` S11max −11.3 / S21 1.0 / Idd 0.0 |

**★ The template-free arm produced a genuinely novel, replay-verified feasible
wifi24 LNA.** `ft_ctrl_nb_s1337/seq0014`, wl `ab74782d9a3914ba`, 9 devices /
1 inductor, reached by bounded polish; `size.replay_ok` re-evaluates the stored
point and reproduces the stored metrics. It matches none of the 148 archetypes,
none of the 41 corpus circuits and no row in the (then) 886-row store. The
baseline's front produced exactly one as well (`seq0009`, 12 devices /
3 inductors). On dhruva-l1 neither arm converted, and the control's best
violation is *lower* (0.960 vs 1.023).

**⚠ And the sharpest number in the section is a nearest-neighbour, not a hash.**
WL-novelty is a hash test; graded similarity tells a different story about *how*
novel each arm's front actually is:

| front winner | arm | NN-sim to its nearest reference item | nearest neighbour |
|---|---|---|---|
| `seq0009` | P5-v3 | **0.939** | `arch:cs_gi1_dg1_cx1_cc1_tapped_bf1` |
| `seq0014` | ctrl-v1 | **0.642** | `arch:cs_gi1_dg0_cx1_cc0_R_bf1` |
| `seq0043` | ctrl-v1s | **0.574** | `arch:cs_gi1_dg0_cx1_cc0_tapped_bf0` |

The baseline's feasible novel design is a **0.94-similar variant of a template it
was trained on** — hash-novel, structurally template-adjacent. The control's is
0.64 from anything in the reference. So on this evidence the template-trained
generator's "novel front" is largely *template-perturbation*, while the
template-free arms are exploring further out and paying for it in yield.

**Statistical honesty.** One feasible out of 14 per arm is a single Bernoulli
draw each; the feasibility column does **not** separate the arms and must not be
read as "the control ties the baseline" at any confidence. The best-violation
column and the 45/35/22-candidate front sizes are the finer-grained signal, and
they say the same thing more weakly: the arms are close, and neither dominates.

**SPICE cost.** 12,794 ngspice evaluations over the five front runs; the scan
phases measured 1,352 s of process time (**0.10–0.14 s/sim** at this light
budget), so the experiment cost **≈24 min of real ngspice**. Note that
`loop.SEC_PER_SIM = 1.0` — the store's costing convention, calibrated on
anchor-strength budgets — would bill the same work at 213 SPICE-min. Both numbers
are stated because the headline curve uses the second one.

### 16.4 What the ref-v2 migration corrected on the way in

The four remaining `corpus_reference()` (ref-v1) call sites flagged at the end of
§14.5 — `campaign.py`, `loop.py`, `size.py`, `trackb_g4.py` — now call the
versioned `novelty.reference()` and stamp `novelty_ref` into what they log. That
is a plumbing change with a substantive consequence:

| headline curve (whole store, `loop.py --curve`) | feasible | **feasible-novel** | SPICE-min per novel design |
|---|---|---|---|
| ref-v1 (what it used to report) | 12 | **11** | **310.1** |
| **ref-v2 (correct)** | 12 | **7** | **487.3** |

**Four designs the old check called novel discoveries are WL-exact regenerations
of archetypes that were already in the generator's training set when those
samples were drawn** — verified against the pinned `templates_train.pre_broaden`
(92-archetype) and `pre_dhruva` (118-archetype) emissions, so this is not the
archetype set having grown afterwards:

| design | spec | archetype it reproduces | in the 92-arch training set? |
|---|---|---|---|
| `seq0089` | gps-l1 | `cs_gi1_dg1_cx1_cc0_R_bf1` | **yes** |
| `seq0215` | gps-l1 | `cs_gi1_dg1_cx1_cc1_tank_bf1` | **yes** |
| a second topology later written to `ft_p5v2_nb_s1337/seq0220.txt` | wifi24 | `cs_gi1_dg1_cx1_cc1_R_bf1` | **yes** |
| `rfbcs3_tank_cc21_bf0` | dhruva-l1 | itself (the hand archetype) | n/a — never claimed as generated |

**⚠ This qualifies the Gate-B1 gps-l1 claim, and the qualification is only about
topology, not about the circuits.** Both gps-l1 feasibles are real,
SPICE-verified, in-box designs and the *sizing* result stands exactly as
recorded: the generated-and-sized route reached feasibility where CP1's all-free
ZOAF on the 30 new families did not. What does **not** stand is the
topology-discovery half — "the generator supplies the co-sizeable input network
the hand templates lacked" (BROADEN-PROGRESS CP5). The topology **is** a hand
template; the generator recited it, and polish sized it. Note also that CP1 sized
only the *30 new* families against gps-l1, never these two older `cs_*`
archetypes, so it was never a same-topology comparison in the first place.

**Two claims explicitly survive.** Track B's `seq0192` dhruva-l1 feasible
(wl `20bca9a7c3a5f263`) was hand-checked against all 148 archetypes at the time
and is still novel under ref-v2. The wifi24 tier-2 `seq0220` (wl
`396b90321529157a`, NF 2.43) is also still novel — the archetype-copy row above
is a *different* topology that was later written to the same filename when a
generator run reused the output directory, and was picked up by Track C's
best-of-3 σ probe. That collision is the same `seq*.txt`-name-reuse trap that
07-EXIT §1 already had to fence with `size.replay_ok`; it is now on record as
having also produced a phantom "novel feasible design" in the headline count.

`critic_gnn.py`'s printed `C1?` column (the other item §14.6 left as a follow-up)
now reports the restated gate through `critic.c1_stats` / `critic.c1_pass` and
prints `ofceil` / `skill` beside `enrich`. Re-run on `v4-train`: family holdout
ρ(S21) 0.847, prec@20% 0.895, **skill 0.792 → YES**; source-shift ρ(S21) 0.615,
prec@20% 0.655, **skill 0.367 → YES** — reproducing §14.6's table, where the
retired bar printed `no` on both.

### 16.5 The honest reading

**Neither hypothesis in the brief wins outright, and the middle answer is the
interesting one.** The templates are *not* load-bearing for novelty: strip them
completely and the generator still mints 26 novel distinct screen-passing
topologies per 256 samples (half the adopted baseline, above every pre-P5 arm),
its novel front still reaches violation 0.175 on wifi24, and with the winners
channel left intact it mints 42, beats the baseline outright on the wideband
channel, and lands a replay-verified feasible wifi24 LNA that sits 0.64 NN-sim
from anything in the reference — further out than the baseline's own front
winner at 0.94. That is not the P1/P2 collapse; the memorization ceiling is
genuinely broken, and what broke it was as much the class tokens and the
expert-iteration winners channel as the archetypes.

What the templates *are* load-bearing for is **structural yield**: 80.5% vs 35.5%
spec-L0 on nb. Their job in this pipeline turns out to be teaching the model what
a well-formed LNA looks like, so that more of its samples are worth spending
ngspice on — and that is a real and valuable thing to buy, just not the thing the
NDL headline was implicitly crediting them with. The corresponding cost is
visible in the same table: 37.9% of the baseline's output is verbatim archetype,
its median screen-passing sample is a WL-exact copy of training data, and its
best novel-front design is a 0.94-similar template variant. Template dependence
is not "fading" so much as **relocating** — from novelty, where §14.5 already
showed the credit was misattributed, to yield, where it is earned.

**Two caveats that bound all of the above.** (1) ctrl-v1 is not literally
template-free — 42.3% of its winner rows are archetypes — which is exactly why
ctrl-v1s was run, and the 42 → 26 gap between them is the honest size of that
back door. (2) The novel-front comparison is 14 candidates and one feasible per
arm; it establishes that the control is *in the same league*, not that it
matches. A larger front (or the same protocol at several seeds) is what would
turn 16.3 from a plausibility argument into a measurement.

**Nothing here is adopted.** The re-frozen baseline stays **P5-v3 =
`ft_p5_v2.pre_dhruva.pth`, nb 52 / wb 21 under ref-v2**. The control checkpoints
`ft_ctrl.pth` / `ft_ctrl_v2.pth` / `ft_ctrls_v2.pth` exist only as the evidence
behind this section (gitignored, ~198 MB each; the pools' `meta.json` are
tracked). The one actionable follow-up the experiment suggests is cheap and is
*not* a generator change: if the templates' measured product is screen yield,
then a P5 arm that keeps the archetype scaffolding but **down-weights or
curriculum-drops it late in training** should keep the yield and recover the
novelty the regurgitation is costing — testable with one fine-tune and one NDL
row.

---

## 17. Phase 3 — the **NF-first sizing campaign**: Gate D3 measured to a wall, and ngspice scratch hygiene (Session 6)

> Owner: the NF-campaign executor. Files: `lna/size.py` (`constrained_descent`,
> `prepared_body`), `lna/nf_campaign.py`, `lna/nf_moves.py`, `lna/_nf_scan.py`,
> `lna/_nf_verify.py`, `lna/_nf_table.py`, `lna/_nf_novel.py`, `lna/_nf_tmp_purge.py`,
> `lna/extract.py` / `lna/bias.py` / `lna/templates.py` (scratch hygiene only).
> Run artefacts in `lna/out/_nf/` (gitignored). Store rows: recipes `nf-v1` and
> `nf-v1+move`, `provenance.source_arm` `nf-campaign` / `nf-moves`.

**Headline.** Gate D3 is **NOT MET**, and it is now a *wall with a shape* rather
than a distance. The whole low-noise family's noise/gain trade at a held
broadband match was measured end to end: **NF ≤ 3.5 dB is reachable on
`dhruva-s` — at S21 21.65 dB. S21 ≥ 30 dB is reachable — at NF 4.89 dB.** Both
points are replay-verified, in-box, unconditionally stable. Nothing in between
crosses. The remaining gap is **1.39 dB of noise at the spec's gain**, down from
2.08, and the binding trade has moved from NF↔S11 (Session 4's rfb family) to
**NF↔S21**.

### 17.1 Why the previous lever could not work: `polish` cannot spend slack

Session 5 handed over `8c7592ea859e489a` — tier-1 feasible on `dhruva-s`, NF
5.58 the only violation, with 4.9 dB of S21 surplus and 1.2 mA of Idd surplus.
The natural move is "trade the surplus for noise", and `size.polish` is the tool
that exists. It cannot do it, for a structural reason worth writing down:
**polish ascends the *minimum* normalized margin over the gated constraints.**
When exactly one constraint is violated by a lot, the minimum *is* that
constraint, so polish already optimizes it — and raising any *non-binding*
margin cannot raise the minimum, so a 4.9 dB gain surplus is valued at exactly
zero. Slack is currency only if something is allowed to spend it.

`size.constrained_descent` (new) is that something: optimize **one** metric
directly and refuse any step that pushes a *kept* constraint's margin below
`floor`. Scoring is lexicographic — `(total kept-constraint shortfall, target
value)` — so an infeasible start is walked into the region first and descended
after. It is box-clamped exactly like polish (the Session-4 out-of-box bug),
randomizes coordinate order per seed, and interleaves **joint multi-coordinate
probes** with the coordinate sweep: noise cancellation is a condition on a
*ratio* (aux gm vs CG gm, load vs load), so the descent direction that matters
is rarely axis-aligned and a pure coordinate sweep stalls on the diagonal.
Cost measured at **~0.15 s/eval** (op/sp + series-Rs NF), so a 1500-eval descent
is ~4 minutes.

`nf_campaign.py` drives it in four modes — `nf` (minimize noise inside a trust
region selected by `--keep tier1|s11|s11idd|s11gain|none`), `gain` (maximize S21
under `--nf-cap`), `match` (minimize worst-case S11 holding NF and gain), and
`--fresh` (an independent match-first restart per seed, so a *family* floor is
not confused with a *basin* floor).

### 17.2 ★ The measured NF↔S21 front on `dhruva-s` (the deliverable)

Every row below holds `s11_max_db ≤ −10 dB over 1.1–2.5 GHz` and `idd_ma ≤ 13`;
all are replay-verified against their own stored parameters, in-box, and K ≥ 1.

| point | S11_max | **S21** | Idd | **NF** | K_min | total viol | what binds |
|---|---|---|---|---|---|---|---|
| `ce39a7` as found (move `aux_path_add`) | −10.04 | 18.00 | 7.83 | **3.42** | 81.9 | 0.400 | S21 |
| `ce39a7` gain-ascent @ NF ≤ 3.5 | −10.11 | **21.65** | 6.49 | **3.50** | 26.6 | **0.278** | S21 only |
| `19f72303` NF floor at match | −10.00 | 23.30 | 9.73 | 3.73 | 35.4 | 0.290 | S21, NF |
| `19f72303` gain-ascent @ NF ≤ 4 | −10.12 | 27.58 | 12.99 | 3.99 | 15.4 | **0.222** | S21, NF |
| **`19f72303` tier-1 descent** | **−10.01** | **30.00** | **12.67** | **4.89** | 23.7 | **0.398** | **NF only** |
| `8c7592ea` tier-1 descent (Session-5 incumbent) | −10.13 | 35.15 | 13.00 | 5.42 | 7.7 | 0.549 | NF only |

Two records move:

* **Best tier-1-feasible `dhruva-s` design: NF 5.58 → 4.89 dB**, tier-2 violation
  **0.594 → 0.398**. `19f723034c0a946c`, 16 devices, the Session-5 crossover
  design — S11_max **−10.01** / S21 **30.00** / Idd **12.67** / NF **4.892** /
  K_min **23.7**, `replay_ok` True, in-box, unconditionally stable in band, NF
  the single violated constraint. Three seeds land 4.89 / 4.96 / 5.07, so the
  floor is the design's, not the seed's.
* **Program-best total violation on `dhruva-s`: 0.566 → 0.222** (2.5×), same
  graph at S21 27.58 / NF 3.995. ⚠ Per the §20 warning this is *not* a
  shrink-to-nothing optimum — it carries 27.6 dB of real gain; every number in
  this section is quoted with its S21 for exactly that reason.

**The front is monotone and dense: +8.35 dB of gain (21.65 → 30.00) costs
+1.39 dB of noise (3.50 → 4.89).** That is the Gate-D3 gap, stated as a
conversion rate rather than a distance.

### 17.3 ★ A structural edit broke 3.5 dB — and hit the device budget

`nf_moves.py` mutated the two elites one edit at a time (`moves.py` stratum M),
realized each mutant through the full token round-trip and sized the survivors
match-first + NF-descent — 20 distinct novel mutants from 37 proposals, all
SPICE-verified. One matters:

> **`ce39a77c91974013`** — move **`aux_path_add`** off parent `7b0b485b629cecd2`
> (`nccgcs_s1_R`), **16 devices**. **NF 3.416 dB at s11_max −10.04**, S21 18.00,
> Idd 7.83, K_min 81.9. `replay_ok` True, in-box. Novel: its WL hash is in
> neither **ref-v3** (`d05390da6183123e`; 41 corpus + 9 external + 148
> archetypes = 198 hashes) nor any pre-campaign store row; nearest reference
> circuit is its own parent archetype at NN-similarity **0.822**.

**This is the first design in the program to measure NF ≤ 3.5 dB with the
broadband match held** — the noise half of Gate D3, alone. Pushed for gain at
NF ≤ 3.5 it reaches S21 21.65; pushed for tier-1 it stops at S21 25.74 (NF 5.43)
and never reaches 30. **The edit that bought the noise is an added auxiliary
cancellation path, and it took the graph to exactly 16 devices — the
`device_budget` ceiling.** So the one structural move that would buy the missing
gain almost free in noise (Friis: a second gain stage) cannot be made: the
family's low-noise members sit at 14–16 devices and a CS stage costs 2.

That is the same *latent* constraint §13.5 flagged, now **active and measured**:
`19f72303` 16 devices, `ce39a7` 16, `8c7592ea` 16, `7b0b485b` 14. Raising
`device_budget` is a **spec** change and was deliberately **not** made to close a
gate — it needs the same corpus calibration `[3,12] → [3,16]` got.

### 17.4 Family NF floors, gain-gated (the "what binds next" table)

NF floor with the broadband match held (`--keep s11`), **and an S21 floor
applied** — an ungated NF floor is meaningless, e.g. `gmbcg_wb_s0_b1` reads NF
3.61 at S21 **−0.63 dB**, a shrink-to-nothing optimum of exactly the shape §20
warns about.

| family | best NF @ S11 ≤ −10 **and S21 ≥ 15** | at S21 | tier-1-feasible NF | what binds next |
|---|---|---|---|---|
| noise-cancelling CG+CS (evolved: `ce39a7`) | **3.42** | 18.00 | – (S21 25.7 max) | **device budget** — no room for a gain stage |
| noise-cancelling CG+CS (evolved: `19f72303`) | 3.73 | 23.30 | **4.89** | NF↔S21 conversion, 1.39 dB |
| noise-cancelling CG+CS (`nccgcs_s1_R`, 14 dev) | 3.86 | 18.95 | – (S21 25.9 max) | gain |
| noise-cancelling CG+CS (`nccgcs_s1_tank`) | 3.82 | 25.19 | – (Idd 16.3) | Idd |
| evolved CG + 2 tuned CS (`8c7592ea`) | 5.42 | 35.15 | 5.42 | NF; aux path is downstream of both stages |
| gm-boosted CG, 2-stage (`gmbcg_s2_*`) | 5.41 | 31.05 | 5.41 | NF floor of the family |
| gm-boosted CG, 1-stage (`gmbcg_s1_*`) | 5.29 | 17.36 | – | NF **and** gain |

**The family separation is clean and ~1.5 dB wide: noise-cancelling CG+CS floors
at 3.4–3.9 dB, gm-boosted CG at 5.3–5.8 dB.** Only the NC family is on the D3
ladder at all. Note `gmbcg_s2_*` *is* tier-1 feasible on `dhruva-s` (S21 31.05 /
Idd 9.44 / S11 −10.19, viol 0.546) — a third tier-1-feasible dhruva-s design,
but it cannot go below 5.4 dB.

### 17.5 What sets the noise, measured directly (`_nf_scan.py`)

A stall is a claim about a landscape, so the landscape was swept: each sizable
parameter across its full spec box, everything else held, at the tier-1 point of
`19f72303` (NF 4.892).

| parameter | NF at base | NF reachable alone | breaks |
|---|---|---|---|
| `pC1V` (input DC block, 2.26 pF → 0.71 pF) | 4.89 | **3.66** | s11_max **and** s21 |
| `pNM2W` (5.12 → 27.4 µm) | 4.89 | **3.95** | s21 |
| `pNM3W` (12.0 → 3.76 µm) | 4.89 | 4.54 | s11_max and s21 |
| `pR1V` (979 → 473 Ω) | 4.89 | 4.79 | s11_max, s21, idd |
| every other coordinate | 4.89 | ≥ 4.87 | – |

**Every coordinate that buys noise pays in gain**, and the two that pay most
(the input coupling cap and the auxiliary device width) are exactly the
cancellation-path elements. There is no unexploited direction: the descent is
sitting on the constraint, not on a local minimum of its own making.

Two further checks that the floor is the family's and not the search's:
`--fresh` restarts (independent match-first sizings, seeds 1–3) land in visibly
worse basins (NF 6.34 / 8.51 / 6.06 after the restart) and descend back to
3.85–3.92, never below the 3.73 reached from the stored point; and three seeds of
`--mode gain --nf-cap 3.5` on `19f72303` all terminate at the *same* NF 3.73
point, i.e. the NF ≤ 3.5 region is simply not reachable on that graph at any
gain.

### 17.6 The five transcribed real topologies do not size here — and the reason is a *source* DC return, not gate bias

All five paper transcriptions plus the four IHP/ALIGN circuits were screened and,
where they pass, sized (`ext:` source, match-first + NF descent):

| circuit | dhruva-s screen | best sized result |
|---|---|---|
| `paper-transformerfb` | pass | S11 −10.02 / **S21 −10.2** / NF 9.51 |
| `ihp-gps-lna-nmos` | pass | S11 −8.87 / **S21 −5.8** / NF 19.8 |
| `paper-currentreuse` | pass | S11 −1.85 / **S21 −16.6** / NF 21.3 |
| `paper-gmboostcg` | pass | S11 −3.42 / **S21 −35.7** / NF 20.6 |
| `paper-noisecancel` | fails (inductorless) | vs wideband-sdr: S11 −8.07 / S21 5.8 / NF 10.1 |

None is competitive. The coordinator's intel — 4 of 9 have non-conducting MOS —
was confirmed and then **localized**: `align-lna-qm` (NM2), `ihp-lna-2p45g`
(NM3, NM4), `paper-diffcccg` (NM1, NM2) and `paper-gmboostcg` (NM2). §13.5's
lesson said screen the operating point first, so the obvious hypothesis was
Session 4's biasing defect again — a gate that `bias.py` leaves alone because it
reaches a rail through the original design's on-chip divider, sized for another
PDK and another rail.

**It was tested and it is wrong.** An opt-in `BiasInserter.rescue()` that
promotes such gates to R-GATE bias nets and re-sweeps was implemented and
measured on all nine: **0 of 4 broken circuits gained a single conducting
device.** The reason is visible in the same report — in *every* case the off
device is listed under **`sources_no_dc_path`**: its source reaches neither a
supply nor ground through R/L. No gate bias can turn on a device whose source
has no DC return. The rescue rule was therefore **reverted, not landed** (dead
opt-in code in a shared file is a liability, and the measurement is the
deliverable). `bias.py`'s existing comment — "those devices are off for
source/drain reasons, not gate bias" — is confirmed on a second, independent
population.

**The actionable rule is a different one and was NOT implemented**: a
source-DC-return inserter. It is a bigger governance question than R-GATE,
because adding a resistor from a source to ground *changes the circuit*, where
gate scaffolding only makes it biasable. `paper-diffcccg` shows why it matters —
it is a differential cross-coupled CG whose tail current source the single-ended
token flow cannot represent at all.

### 17.7 `wideband-sdr` — the wall is no longer NF alone

The NF-capable families were run against `wideband-sdr` (NF ≤ 3.5, S11 ≤ −10,
S21 ≥ 12, ripple ≤ 2, Idd ≤ 8, `max_inductors: 1`): the two externals that pass
its screen, six low-noise archetypes, and the two best stored designs.

**Best total violation 1.551 → 1.375** (`eb6c31c8dc22`: S11 −3.61 / S21 12.02 /
Idd 3.07 / NF 5.50 / K_min 4.29). **Still 0 feasible**, and the diagnosis has
changed: §15 recorded `nf_db` violated on 102/102, but with NF in the objective
the binding constraint on every candidate is now the **f0 match** — s11_db
lands at −2.6…−3.6 dB on eight of ten, and the lexicographic descent spends its
whole budget there before it ever gets to reduce noise. `max_inductors: 1` is
doing exactly what it was written to do (§15's "re-read the spec" item): the
inductorless population matches through a resistive path that costs noise, and
the one permitted inductor cannot be spent on the input.

### 17.8 The opposite attack, and why it also fails

§20's rung-1 lead is real and was tested: `seq0126` (`92d68c1eba1f`) reads **NF
2.73 dB at S21 15.98** and `seq0218` (`f2f10647ec88`) **NF 2.82 at S21 17.73** —
both under the `dhruva-s` target, both with the input match completely unsolved
(s11_max −0.01 / −0.32). `--mode match` descends worst-case S11 holding NF ≤ 3.5
and S21 ≥ 15. Over 2 seeds each: **S11_max moves −0.01 → −0.39 and −0.32 →
−0.69 dB.** The match does not close by any parameter setting inside the box.
⚠ `92d68c1e` also reads **K_min −0.33** at its stored point — potentially
unstable, so it could not have carried a gate claim regardless.

**Read:** on these graphs the input match is *structural*, not parametric, which
is the same wall WP-BROADEN hit on gps-l1 and WP-D2 hit on rfb. The two attacks
are now symmetric and both measured: designs that match cannot get below 3.4 dB
with gain, and designs below 2.8 dB cannot be made to match at all.

### 17.9 ⚙ ngspice scratch hygiene — 685,287 stale directories

Every ngspice caller in the tree `mkdtemp`'d per call and none cleaned up (§15's
hygiene note). `%TEMP%` was carrying **685,287** stale directories — 625,508
`size_*`, 57,023 `nf_*`, 2,051 `bias_*`, 1,007 `tmpl_*`, 40 `stab_*` — at which
point creating one more directory costs more than the 0.15 s evaluation it
serves and listing `%TEMP%` takes minutes.

`extract.py` gained `scratch()` (a context manager) and `run_deck()` — now the
tree's single ngspice entry point: write the deck into self-deleting scratch,
run, return stdout+stderr or `None` on timeout. All six call sites
(`run_and_extract`, `measure_stability`, `measure_nf`, `nf_selftest`,
`bias.run_op`, `templates.emit_paths`) route through it, so every campaign sim
self-cleans; `LNA_KEEP_TMP=1` keeps the decks for debugging.

`lna/_nf_tmp_purge.py` swept the backlog, pattern-fenced to `<prefix><8 alnum>`
and to directories older than 60 minutes so a concurrently running sim in
another agent's process could never be touched: **seen 686,780 / matched 685,287
/ skipped_young 377 / removed 685,287 / failed 0, in 1,788 s.** Regression
quartet green after.

### 17.10 Cross-band, cost, and the honest verdict

**Cross-band (`dhruva-l5`, NF ≤ 2.5 / S21 ≥ 22.3).** The lower bands sit at
1.18–1.58 GHz where both inductor loss and gm/ω favour noise, so it was worth a
measurement rather than an assumption. Tier-1-feasible on `dhruva-l5` with
`19f72303`: S11 −10.01 / S21 28.03 / Idd 9.67 / **NF 3.65** / K 19.7, and
`7b0b485b` reaches NF 3.76 at S21 22.34. **NF is indeed ~1.2 dB lower than on
`dhruva-s`, and the target is 1.0 dB tighter, so the absolute gap grows**:
1.15 dB on l5 against 1.39 dB on s — but normalized, l5's violation is 0.459
against s's 0.398, so **`dhruva-s` remains the closest band**, confirming
Session 4's choice with a number instead of an argument.

**Cost.** ~46,000 SPICE evaluations across 9 campaign runs (~0.15 s each,
3 concurrent), 64 sized results, **96 new L2 rows** (76 `nf-v1`, 20 `nf-v1+move`).

**Gate D3 — NOT MET, and this is the stall report.** A `dhruva-s` design is
tier-1 feasible with NF as its only violation at **4.89 dB** (target 3.5), and a
different design in the same family clears **3.50 dB** with S21 as its only
violation at 21.65 dB (target 30). The conversion rate between them is
**+1.39 dB NF per +8.35 dB S21**, the front is dense and monotone, the landscape
scan shows no unexploited direction, independent restarts do not find a better
basin, and the one structural move that would break the trade — a second gain
stage, nearly free in noise by Friis — is blocked by `device_budget` at 16,
which every low-noise member of the family now touches.

**So the next lever is not sizing and not more seeds.** It is (a) a
`device_budget` decision made honestly, from corpus device counts, the way
`[3,12] → [3,16]` was made — *not* to close a gate; or (b) a topology that gets
30 dB from a *cascade* rather than from a harder-driven input stage, which is a
generator/search job on a family that does not yet exist in the archetype set.

---

## 18. Phase 3 — the **curriculum** arm: can scaffolding early + dropping it late keep the yield *and* buy the novelty? (Session 6)

> §17 is reserved by a concurrent agent (the ingestion track's self-deleting
> scratch work); this section is numbered 18 to avoid a collision.

### 18.0 ⚑ PRE-REGISTRATION (written before a single epoch was trained)

§16 measured that the `templates.py` archetype scaffolding buys **structural
yield, not novelty**: removing it takes nb spec-L0 80.5% → 35.5% while NDL@256
only falls 52 → 42, and the baseline's own "novel" front winner turns out to be a
**0.939-similar perturbation of a template it was trained on** where the
control's sits at 0.642. §16.5's closing proposal was the obvious follow-up:

> *a P5 arm that keeps the archetype scaffolding but down-weights or
> curriculum-drops it late in training should keep the yield and recover the
> novelty the regurgitation is costing.*

This section tests exactly that. Everything below the line was fixed in advance;
the numbers are appended afterwards whatever they say.

**The design.** A curriculum is two phases over the *same* P5 recipe:

* **phase 1 (scaffolded)** — the full P5 mix: corpus + Eulerian-augmented
  `templates.py` archetypes + `<OTHER>` replay (+ the winners channel in stage B).
* **phase 2 (de-scaffolded)** — the identical mix with the **template channel
  removed**: corpus + winners + replay. This is *byte-identical* to ctrl-v1's
  stage-B dataset (`winners_train.pre_dhruva.json`, 965 rows — the P5-v3-era
  emission), so the curriculum arms differ from ctrl-v1 in **nothing but the
  warm-start checkpoint**.

**The switch criterion, and why it is what it is.** The brief asks for a switch
point chosen from the known training dynamics. Those dynamics are brutal and
already measured on every arm in this program: **best val loss lands at epoch 0–1
and rises monotonically for the rest of the run** (P5-v3 0.2300 @ ep 1; ctrl stage
A 0.2226 @ ep 1; ctrl-v1 stage B 0.2162 @ ep 0; ctrl-v1s 0.2189 @ ep 0), and the
shipped artefact is the best-val checkpoint. So "train phase 1 for the epochs
where val is still falling" **is** "take phase 1 at its shipped best-val
checkpoint" — which means phase 1 needs no GPU at all and is guaranteed
byte-identical to the baseline lineage. Two switch points exist in that lineage,
and both are tested:

| arm | phase 1 = warm start | phase 1 archetype exposure | phase 2 (40 ep, lr 3e-5, batch 32, seed 1337) |
|---|---|---|---|
| **cur-v1** (*early switch*, at the stage A/B boundary) | `ft_p5.pth` (md5 `492f2eb7…`) — P5-v3's own stage-A base: corpus + 92-archetype templates + replay, from `Pretrain.pth` | stage A only | corpus + 965 winners + replay, **no templates** |
| **cur-v2** (*late switch*, a de-scaffolding tail) | `ft_p5_v2.pre_dhruva.pth` (md5 `1b3c2b16…`) — **the adopted P5-v3 itself** | stage A **and** stage B (118 archetypes, 2230 rows) | same data as cur-v1 |

That makes **cur-v1 the missing cell of a clean 2×2** over (templates in stage A) ×
(templates in stage B): P5-v3 = yes/yes, ctrl-v1 = no/no, **cur-v1 = yes/no**.
cur-v2 asks the same question one stage later — take the shipped baseline
generator and de-scaffold it — which is the cheapest possible version of the
proposal and the one an adoption decision would actually face.

**Hyperparameters: identical to the §16 arms, no exceptions.** lr 3e-5, AdamW,
batch 32, 40 epochs, seed 1337, `<LNA_NB>`/`<LNA_WB>` class tokens, PAD 128,
loss masked after TRUNCATE, **best-val checkpoint ships**. No LR decay for phase 2:
§16's arms had none and changing it would confound "curriculum" with "annealing".
With `--no-templates` the validation set is the 6 held-out corpus circuits alone
(492 rows) — the same val criterion ctrl-v1 early-stopped on, stated because it is
*not* the same criterion P5-v3 used (736 rows incl. every 8th archetype).

**⚑ The pre-registered prediction, so it cannot be retrofitted.** Given the
dynamics above, phase 2's best val will land at **epoch 0 or 1**, i.e. the shipped
curriculum will be "scaffolded base + one template-free epoch". If that is what
happens it will be reported as such, not dressed up as a long anneal. A
fixed-length tail is available as an ablation (`--ckpt-policy final`) and will be
run **only if** the best-val tail lands within noise of its phase-1 warm start on
both headline axes.

**⚑ Pre-registered success criteria** (the brief's, restated numerically against
the §16 table): success = nb **NDL@256 (ref-v2) materially above 42** *and* nb
**spec-L0 materially above 35.5%**, with a **novel front whose winner sits at
NN-sim materially below 0.939**. Beating 42/35.5% alone is not success — P5-v3
already does that; the whole point is to do it *without* the front being
template-perturbation. Pre-registered non-promotion: any arm that fails to clear
the **re-frozen nb baseline of 52** at equal-or-better inductor ratio does not go
to a full P5 training, whatever else it wins on (adopt-only-if-better).

**⚑ Pre-registered evaluation protocol — §16's, byte for byte.** n=256, seed 1337,
batch 32, 256-token cap, temperature 0.7, prefix `<LNA_NB> VSS`; NDL@256 under
**ref-v2 [189h/`b5689490d0285c37`]** with archetype-copy %, corpus-copy %, median
NN-sim, termination, inductor ratio and spec-L0 from the same `novelty.evaluate`
row; wb channel (`--spec wideband-sdr`) if time allows. Novel front:
`lna/_ctrl_front.py`, `--scan-limit 14 --top 5`, tier-1 gating (S11/S21/Idd; NF
measured and advisory), light all-free ZOAF scan (`n_candidates=4, sgd_iters=5,
cgd_iters=1`) then **box-clamped** `size.polish`, against **wifi24** and
**dhruva-l1**, recipe `cur-v1`, arm in `provenance.source_arm`. If a concurrent
agent lands ref-v3 tonight, ref-v2 is still the reported stick, for comparability.

**Nothing in this section is an adoption.** The re-frozen baseline is and stays
P5-v3 = `ft_p5_v2.pre_dhruva.pth`, nb 52 / wb 21 under ref-v2. Checkpoints
`ft_cur_v2.pth` / `ft_cur2_v2.pth` are evidence, gitignored, and must never
displace it.

> **Note added by the ingestion track (§19):** ref-v3 did land tonight, and the
> measured Δ(v3−v2) is **0 on every checkpoint including this arm's baseline** —
> so ref-v2 and ref-v3 numbers are directly comparable for any arm trained before
> the corpus expansion, and this section's comparability caveat costs nothing.
> The re-frozen baseline is unchanged in value: nb 52 / wb 21, now stamped
> `ref-v3[198h/d05390da]`.
>
> *(Curriculum track, confirming for its own arms: measured Δ(v3−v2) is **0** on
> all four curriculum pools too — external-copy rate 0.0% on every one — so every
> nb number below is simultaneously a ref-v2 and a ref-v3 number.)*

### 18.1 What was actually run

Both arms trained exactly as pre-registered. **The §18.0 prediction held on both:**
phase 2 takes its best val at **epoch 0** and rises monotonically for the
remaining 39 epochs, so the shipped curriculum is *scaffolded base + one
template-free epoch*, and the 40-epoch runs are recipe fidelity, not annealing.

| arm | warm start (phase 1) | train / val | best val | val @ ep 39 | wall |
|---|---|---|---|---|---|
| **cur-v1** | `ft_p5.pth` md5 `492f2eb7…` (P5-v1; its own pool reads nb NDL **30**, spec-L0 **57.4%**) | 5170 / 492 | **0.2257 @ ep 0** | 0.3633 | 2184 s |
| **cur-v2** | `ft_p5_v2.pre_dhruva.pth` md5 `1b3c2b16…` (**the adopted P5-v3**) | 5170 / 492 | **0.2389 @ ep 0** | ≈0.36 | 1881 s |

5170 / 492 is *byte-identical* to ctrl-v1's stage-B dataset, as designed — the
curriculum arms and ctrl-v1 differ in the warm-start checkpoint and nothing else.

Because best-val collapses the tail to one epoch, tail length was also swept
directly with `--ckpt-policy final` (§18.3). ⚠ **That sweep is an unregistered
exploratory add-on**: §18.0 pre-registered it only for the case where the
one-epoch tail landed *within noise* of its warm start, and it did not — it moved
both axes materially. It is reported because it turned the section's conclusion
from an inference into a measurement, and it is labelled post-hoc.

### 18.2 Pool metrics — §16's protocol, n=256, seed 1337, `ref-v2[189h/b5689490]`

Every §16 row below was **re-measured tonight**, not copied, and reproduces to the
digit — so the measuring stick had not drifted when the new arms were scored.

| arm | class | **NDL@256 v2** | spec-L0 | copies (**arch** / corpus) | med NN-sim | term | ind ratio | anyL |
|---|---|---|---|---|---|---|---|---|
| **P5-v3 (baseline)** | nb | **52** | **206 (80.5%)** | 69.5% (**37.9%** / 31.6%) | 1.000 | 100.0% | 0.224 | 93.8% |
| ctrl-v1 | nb | 42 | 91 (35.5%) | 40.6% (0.4% / 40.2%) | 1.000 | 99.6% | 0.178 | 59.0% |
| ctrl-v1s | nb | 26 | 90 (35.2%) | 55.5% (0.0% / 55.5%) | 1.000 | 98.8% | 0.179 | 59.4% |
| **cur-v1** | nb | **42** | **140 (54.7%)** | 59.0% (**3.5%** / 55.5%) | 1.000 | 99.6% | 0.226 | 78.1% |
| **cur-v2** | nb | **39** | **179 (69.9%)** | 67.2% (**6.6%** / 60.5%) | 1.000 | 100.0% | **0.274** | 95.3% |
| **P5-v3 (baseline)** | wb | **21** | 96 (37.5%) | 51.2% (14.1% / 37.1%) | 1.000 | 99.6% | **0.077** | 39.5% |
| ctrl-v1 | wb | 31 | 50 (19.5%) | 35.5% (0.0% / 35.5%) | 0.621 | 98.8% | 0.156 | 53.9% |
| **cur-v1** | wb | **31** | 84 (32.8%) | 55.9% (0.4% / 55.5%) | 1.000 | 100.0% | 0.117 | 44.5% |
| **cur-v2** | wb | **23** | **131 (51.2%)** | 66.8% (0.4% / 66.4%) | 1.000 | 100.0% | **0.039** | 16.8% |

**★ 1. The curriculum does exactly what it was supposed to do to the *copying*,
and does not buy a single novel topology for it.** Verbatim archetype
regurgitation collapses **37.9% → 6.6%** (cur-v2) and **24.6% → 3.5%** (cur-v1,
against its own P5-v1 base) after *one* template-free epoch, and structural yield
survives far better than under the control: nb spec-L0 **80.5% → 69.9%** for
cur-v2, where deleting the templates from training entirely costs 80.5% → 35.5%.
Both halves of §16's proposal landed. **And nb NDL still fell, 52 → 39.**

**★★ 2. The reason is the sharpest number here: the copying does not stop, it
MIGRATES.** Archetype copies and corpus copies trade almost one-for-one:

| arm | arch copies | corpus copies | **total copies** |
|---|---|---|---|
| P5-v3 | 37.9% | 31.6% | **69.5%** |
| cur-v2 (P5-v3 + 1 template-free epoch) | 6.6% (**−31.3**) | 60.5% (**+28.9**) | **67.2%** |
| P5-v1 | 24.6% | 38.3% | 62.9% |
| cur-v1 (P5-v1 + 1 template-free epoch) | 3.5% (**−21.1**) | 55.5% (**+17.2**) | 59.0% |

Removing the archetypes from the *late* mix does not teach the model to invent; it
re-points the same recitation habit at the 41-circuit corpus, the only memorizable
structure left. **NDL per screen-passing sample confirms it**: cur-v2 reads
**39/179 = 0.218**, *below* the baseline's 52/206 = 0.252, where ctrl-v1 (which
never had the scaffolding) reads 42/91 = 0.46. The curriculum arm is a *less*
novel generator per sample than the arm it started from.

**3. cur-v1 is the missing 2×2 cell: stage-A scaffolding is worth ~19 points of
yield and 0 points of NDL.** cur-v1 and ctrl-v1 share dataset, hyperparameters,
seed and epoch count and differ only in whether phase 1 saw templates. Result:
**NDL 42 vs 42 — identical** — and spec-L0 **54.7% vs 35.5%**. Early scaffolding
is *purely* a yield instrument, and it does not matter for novelty whether the
templates are present early, late, or not at all.

**4. ⚑ On the wideband channel — and only there — a curriculum arm clears the
adoption rule outright.** cur-v2 wb reads **NDL 23 > the re-frozen 21** at
inductor ratio **0.039 vs 0.077** (strictly better for an *inductorless* spec) and
spec-L0 **51.2% vs 37.5%**: every clause of "beat NDL at equal-or-better inductor
ratio" met. It is one channel of two, the margin is 2 topologies, and the same arm
loses nb 39 vs 52 — §18.5 on why that is not a promote.

### 18.3 ★★ The tail-length schedule — a monotone dose-response, pointing down

`--ckpt-policy final` ships epoch K−1, the only way to ask "how long should the
de-scaffolding tail be?" where best-val always answers "one epoch". Warm start
held at P5-v3, data and hyperparameters unchanged, seed 1337 throughout, so K=4's
first four epochs are K=12's first four.

| template-free tail from P5-v3 | **NDL@256 v2** | spec-L0 | arch copies | corpus copies | ind ratio |
|---|---|---|---|---|---|
| **K = 0** (P5-v3 itself) | **52** | 80.5% | 37.9% | 31.6% | 0.224 |
| K = 1 (cur-v2, best-val) | **39** | 69.9% | 6.6% | 60.5% | 0.274 |
| K = 4 | **27** | 69.5% | 5.1% | 75.8% | 0.294 |
| K = 12 | **16** | 68.8% | 4.7% | 78.9% | 0.299 |

**Novelty falls monotonically with tail length — 52 → 39 → 27 → 16 — while yield
plateaus at ~69% and archetype copying saturates at ~5% after the first epoch.**
Every point of archetype copying the tail removes past epoch 1 is replaced by
*more* corpus copying (31.6% → 78.9%), and by K=12 the arm is at **16**, the P0
prefix-12 baseline's NDL to the digit — the number this program started from.
There is no tail length at which the curriculum's promise materializes; the curve
has no interior optimum and its best point is K=0, i.e. not doing it at all.

### 18.4 The novel front — §16's protocol, and the template-similarity verdict

`lna/_cur_front.py` is `_ctrl_front.py`'s protocol with the recipe/experiment tag
switched (scan-limit 14, top 5, box-clamped `size.polish`, tier-1 gating, NF
advisory). ⚠ **Two asymmetries against §16, both conservative for the new arms**:
the novelty filter ran under **ref-v3[198h/d05390da]** (9 more reference circuits
to avoid than §16's arms had) and the store had grown 886 → 1014+ rows, so more
candidates are excluded as already-labelled. Similarity is reported under
**ref-v2** so the column is §16-comparable.

| arm | spec | novel front | sized | **feasible** | **best viol** | best design | **NN-sim** | nearest reference item |
|---|---|---|---|---|---|---|---|---|
| P5-v3 | wifi24 | 45 | 14 | **1** | **0.000** | `seq0009` −12.98 / 13.21 / 3.63 | **0.939** | `arch:cs_gi1_dg1_cx1_cc1_tapped_bf1` |
| ctrl-v1 | wifi24 | 35 | 14 | **1** | **0.000** | `seq0014` −14.28 / 12.78 / 4.36 | **0.642** | `arch:cs_gi1_dg0_cx1_cc0_R_bf1` |
| ctrl-v1s | wifi24 | 22 | 14 | 0 | 0.175 | `seq0043` | 0.574 | `arch:cs_gi1_dg0_cx1_cc0_tapped_bf0` |
| **cur-v1** | wifi24 | 33 | 14 | **1** | **0.000** | **`seq0057` −10.69 / 12.13 / 4.21** | **0.822** | `arch:cs_gi1_dg0_cx1_cc1_R_bf1` |
| **cur-v2** | wifi24 | 32 | 14 | 0 | **0.054** | `seq0026` −16.54 / 11.76 / 5.17 | 0.714 | `arch:cs_gi1_dg1_cx1_cc1_tapped_bf0` |
| P5-v3 | dhruva-l1 | 45 | 14 | 0 | 1.023 | `seq0015` | 0.501 | `corpus:463` |
| ctrl-v1 | dhruva-l1 | 36 | 14 | 0 | 0.960 | `seq0040` | 0.644 | `corpus:483` |
| **cur-v1** | dhruva-l1 | 31 | 14 | 0 | 1.743 | `seq0113` | 0.615 | `arch:cs_gi0_dg1_cx0_cc1_R_bf0` |
| **cur-v2** | dhruva-l1 | 28 | 14 | 0 | **0.624** | `seq0064` −10.60 / 9.56 / 8.03 | 0.500 | `corpus:1086` |

**★ cur-v1 produced a novel, replay-verified, tier-1-feasible wifi24 LNA.**
`ft_cur_nb_s1337/seq0057`, novel against 148 archetypes + 41 corpus circuits + the
9 ref-v3 externals + every store row, reached by box-clamped polish:
**S11 −10.69 / S21 12.13 / Idd 4.21**. Third arm in the series to convert exactly
one of fourteen — one Bernoulli draw per arm, so the feasibility column still does
not separate the arms.

**★ cur-v2 owns the best dhruva-l1 front violation of the whole series: 0.624**,
against 0.960 (ctrl-v1) and 1.023 (P5-v3). `seq0064` reads S11_max −10.60
(passing) and S21 9.56 against a 25.4 dB target — matched-but-gainless, the
familiar shape. Its wifi24 front also lands **three** designs under violation 0.19
(0.054 / 0.057 / 0.182) where the baseline landed one under 0.13: the front is
*denser* even though NDL is lower.

**⚠ And the number the experiment was built to move did not move the right way.**
Template similarity of the polished top-5, under ref-v2:

| arm | winner NN-sim | **median NN-sim over the top-5 front** | of the 5, how many sit nearest an *archetype* |
|---|---|---|---|
| P5-v3 | **0.939** | 0.729 | 3 / 5 |
| ctrl-v1 | 0.642 | **0.603** | 3 / 5 |
| ctrl-v1s | 0.574 | 0.623 | 2 / 5 |
| **cur-v1** | 0.822 | 0.771 | 2 / 5 |
| **cur-v2** | 0.714 | **0.817** | **5 / 5** |

The curriculum arms sit **between** the baseline and the controls on the winner,
and cur-v2 is **worse than the baseline on the median** — its entire wifi24 front
is nearest to a `templates.py` archetype, all five of five. The de-scaffolding
tail stopped the model landing *exactly* on archetypes (6.6% verbatim) without
moving it off the archetype *manifold*. Hash-novelty shifted in a bookkeeping
sense; graded novelty did not.

### 18.5 ⚑ Verdict against the pre-registered criteria — and the promote decision

§18.0's success test: nb NDL@256 **materially above 42** *and* nb spec-L0
**materially above 35.5%** *and* a novel front at **NN-sim materially below
0.939**. Scored honestly:

| criterion | cur-v1 | cur-v2 |
|---|---|---|
| nb NDL > 42 | **42 — FAIL** (ties, does not beat) | **39 — FAIL** |
| nb spec-L0 > 35.5% | 54.7% — PASS | 69.9% — PASS |
| front NN-sim < 0.939 | 0.822 winner / 0.771 median — PASS (weakly) | 0.714 winner / **0.817 median — FAIL** |

**Neither arm meets the pre-registered success criteria. The curriculum
hypothesis is refuted, and §18.3 refutes it with a dose-response curve rather
than a single point.**

**Recommendation: DO NOT promote a curriculum arm to the next full P5 training.**
The binding reason is the adoption rule itself, unchanged since §14.5:
adopt-only-if-better against the re-frozen **nb 52**. cur-v1 reads 42, cur-v2
reads 39, and the tail sweep shows the gap widens monotonically with more of the
treatment. The secondary reason is that the treatment fails on its *stated
purpose*: it was supposed to buy graded novelty, and cur-v2's front is more
template-adjacent than the baseline's, not less.

**One narrow exception, recorded rather than acted on.** On the **wideband**
channel cur-v2 clears every clause of the adoption rule (NDL 23 > 21, ind ratio
0.039 < 0.077, spec-L0 51.2% > 37.5%). The wb channel is thin — 222 template rows,
no wb winners, a 2-topology margin — and promoting a checkpoint that loses nb by
13 NDL to win wb by 2 would be optimizing the metric we happen to be able to move.
If wideband-sdr becomes the priority (it is still the one spec with **zero**
feasible designs), the cheap move is a *wb-targeted* arm, not this one.

### 18.6 The honest reading

**The §16 follow-up was a good hypothesis and it is wrong, in an informative way.**
§16 established that the archetypes buy yield rather than novelty, and inferred
that the 37.9% regurgitation was a *cost* removable while keeping the benefit. It
is removable — one template-free epoch takes verbatim archetype copying to 6.6%
and keeps 70% spec-L0 yield. But removing it buys nothing, because
**regurgitation is not a property of the archetype channel; it is a property of
this model on this data.** Take the archetypes away late and the same recitation
lands on the corpus instead, one-for-one; push the tail further and corpus
memorization takes over completely, until at K=12 the generator is back at NDL 16
with 78.9% of its output a WL-exact corpus circuit.

That reframes the §16 → §18 arc. The question was "are the templates load-bearing
for novelty?" §16 answered "no — for yield". §18 answers the sharper version:
**the templates are load-bearing for novelty too — not because they *create*
novel topologies, but because they are the only thing crowding out corpus
memorization.** The 148-archetype set is not scaffolding the model can be weaned
off; it is the majority of the structural variety in the training distribution,
and the model's novelty is roughly what leaks out of interpolating it. The lever
that would actually work is therefore *more and more varied structure in the
data* — exactly what §19's corpus ingestion is doing — not a schedule that
removes structure.

**What survives as positive results.** (1) `seq0057`, a novel replay-verified
tier-1-feasible wifi24 LNA from cur-v1. (2) cur-v2's **0.624** dhruva-l1 front
violation, the best of the five arms measured under this protocol. (3) The 2×2
cell: with an identical stage B, stage-A scaffolding is worth **+19 points of
spec-L0 and 0 NDL** — the cleanest isolation yet of what the templates do.

**Nothing here is adopted.** The re-frozen baseline stays **P5-v3 =
`ft_p5_v2.pre_dhruva.pth`, nb 52 / wb 21**. `ft_cur_v2.pth`, `ft_cur2_v2.pth`,
`ft_cur2t4_v2.pth`, `ft_cur2t12_v2.pth` are evidence only (gitignored, ~198 MB
each). 20 L2 rows were appended under recipe **`cur-v1`** with
`provenance.source_arm` ∈ {`cur-v1`, `cur-v2`}; **10,614 ngspice evaluations**
across the four front runs, ≈14 min of real ngspice.

---

## 19. Phase 3 — the corpus grows 41 → 50: bipolar emission, external ingestion, and ref-v3 (Session 6)

> §17 is reserved by the scratch-hygiene track and §18 by the curriculum arm;
> this section is numbered 19 to avoid a collision.

Three things happened, in this order, and the order matters: the emitter learned
to emit bipolars (without which one of the nine circuits could not be ingested at
all), nine real/cited LNAs were ingested behind a gate ladder, and the novelty
reference was re-versioned to ref-v3 with the frozen NDL protocol re-run and the
adopt/reject history flip-checked.

**The generator was NOT retrained.** Nothing here is a model claim. The
deliverable is data, references and labels that a future fine-tune can trust.

### 19.1 `to_spice.py` emits NPN/PNP, and the model cards are golden-checked

`topology.py`'s `LEGAL`/`DEV_PREFIXES` and AnalogGenie's own 1005-token
vocabulary have always carried 3-terminal C/B/E bipolars — `NPN1`…`NPN26`,
`PNP1`…`PNP26` are real tokens the generator can emit — but `to_spice.Netlist`
implemented NM/PM/R/C/L only. Running it on the IHP SiGe-HBT GPS LNA said so
plainly: `cannot emit 12 device(s): NPN1: unsupported device type ...`

Two sub-problems, and only one of them was the emitter. The `.include` this
harness uses is AutoCkt's `45nm_bulk.txt` — **a BSIM4 file with no bipolar models
in it at all**, so there was nothing for a `Q` element to reference.

**The cards (`to_spice.BJT_MODELS`) are generic Gummel-Poon, and are labelled as
such.** No vendor model was retrieved (and none could be redistributed here if it
had been), so they are illustrative of a *device class*, not an extraction of any
real device — a number measured on a bipolar topology in this harness is a
topology/harness result, not a silicon prediction. What makes them defensible is
that the two parameters which decide whether a bipolar deck behaves like an RF
device at 1–4 GHz are **measured, not asserted** (`lna/ref/check_bjt.py`):

| card | Ic | beta measured | closed-form | err | fT measured | closed-form | err |
|---|---|---|---|---|---|---|---|
| `qnpn` (SiGe-HBT class) | 0.97 mA | **193.0** | 192.9 | 0.1% | **68.6 GHz** | 71.1 | 3.5% |
| `qnpn` | 4.18 mA | 167.3 | 166.9 | 0.2% | **92.0 GHz** | 97.0 | 5.1% |
| `qpnp` (generic PNP) | 0.87 mA | **43.4** | 43.3 | 0.2% | **11.1 GHz** | 12.3 | 9.3% |
| `qpnp` | 3.13 mA | 31.3 | 31.2 | 0.5% | **7.7 GHz** | 8.0 | 4.0% |

So fT is 17–40× the band for the NPN and 2–11× for the deliberately slower PNP,
and the PNP's fT *falling* with current is the IKF/XTF high-injection roll-off
doing its job. Four details worth carrying forward:

* **`beta == bf` would have been the wrong golden.** The card enables Early
  (VAF) and the ISE/NE recombination term, so the closed form is computed from
  the junction voltages ngspice itself settled at, through the full `qb` algebra
  — which then matches to **0.1–0.5%**, i.e. the check has real resolution.
* **Reverse Early (VAR) was removed from both cards after measuring what it
  does.** In SPICE's `qb`, a finite VAR scales *forward* beta too: `var=2.5`
  dropped the NPN from ~184 to **131** at 1 mA. Leaving VAR infinite keeps the
  stated `bf=200` honest for a device that never runs reverse-active here.
* **`gm == Ic/Vt` is also wrong** once IKF is active (measured 15% low at 5 mA on
  the NPN, 28% on the PNP), so the gm golden is a numerical derivative through
  the same algebra; it then agrees to 1.1–1.5%.
* **ngspice's BJT exposes `vbe`/`vbc`, not `vce`** — `@q1[vce]` is a hard error,
  not a warning. `opcheck` mode prints `ic_/ib_/vbe_/vbc_` per bipolar
  (Vce = Vbe − Vbc). Those labels sit deliberately outside `bias.py`'s
  `id_/vds_/vdsat_/vgs_` parser: bias insertion is a *gate*-scaffolding rule and
  has no base-bias rule, so bipolars stay invisible to the L1 sweep until someone
  writes one.

**Additive, and proved so rather than asserted.** The `.model` cards are emitted
only when the topology actually contains a bipolar. Old and new emitters were run
in the *same process* (a separate process would have compared nothing — the
internal `n0/n1` node names come from set iteration and vary with the hash seed)
against the same model path:

| deck family | modes × settings | identical |
|---|---|---|
| 41 corpus LNAs | sparam+opcheck × ideal/Q=12 | **164 / 164** |
| 148 `templates.py` archetypes | sparam+opcheck × ideal/Q=12 | **592 / 592** |
| 120 generated pool samples (P5-v3 nb + wb) | sparam, Q=12 | **120 / 120** |

**Not sizable, deliberately.** The `Q` elements carry a literal emitter-area
multiplier, not a `.param`. `size.classify_params` owns the param-name →
sizing-kind map and has no bipolar kind, so `area={pQ1A}` would become an
"Undefined parameter" the moment `E.body_of()` strips the `.param` block.
Everything else in a bipolar topology (R/C/L/W) sizes normally — the HBT circuit
sized and logged here through the unmodified `size.size_topology`. Giving
bipolars a sizable area is a `size.py` change and was not this session's to make.

**Known gap, left open on purpose:** `topology.lna_score`'s `has_transistor` and
`spec.structural_screen`'s `has_transistor` both count MOS only. A bipolar-only
LNA would fail them. It does not bite here (the HBT circuit carries an NMOS bias
generator, so it screens 4/5), and changing a frozen screen is a governance
decision of exactly the §14.5 / §14.6 kind — not something to slip in beside a
data change. Recorded, not fixed.

### 19.2 Ingestion: 9 attempted, 9 ingested, 0 quarantined

The nine circuits (scouted and converted in
`data/reports/data-expansion-2026-08-09.md`) live under `lna/data/external/<id>/`
and are ingested by `lna/ingest_external.py` behind a **gate ladder**. A gate
failing quarantines the circuit — left on disk with its reason recorded, out of
the corpus, out of the reference, out of any training set. Everything else is
measured and reported but decides nothing, because the corpus is *real LNA
topologies*, not *topologies that pass our screen*: the existing 41 include
inductorless CG designs scoring 2/5 and index 1081, which does not even simulate.

Gates: **provenance** (a `provenance.json` exists; its source/citation subtree is
free of the blind protocol's excluded paper; an explicit independence statement
is present; the converter's own `quarantine` flag is honoured) · **augmentation**
(≥1 Eulerian path covering every edge exactly once) · **structure**
(`Topology.valid`, no floating sub-circuit) · **vocabulary** (every token in the
guarded 1005-token vocabulary, encode→decode exact, checked on *every* augmented
row) · **identity** (the augmented representative's WL hash equals the hash of
the converter's own token sequence — the conversion and the augmentation must
agree on what circuit this is) · **ngspice** (op, plus sp+noise when two-port,
with no fatal error).

| id | source | score | ngspice | L1 on/MOS | spec | L0 | S11max | S21 | Idd | NF | viol | novel vs ref-v2 (NN-sim) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `ihp-gps-lna-nmos` | IHP Apache-2.0 | **5/5** | clean | 3/3 | gps-l1 | ✓ | −0.30 | −5.41 | 3.30 | 8.14 | 3.52 | ✓ (0.61) |
| `ihp-gps-lna-npn` | IHP Apache-2.0 | 4/5 | clean | 1/1 | gps-l1 | device_budget | −3.06 | 4.07 | 3.89 | **4.60** | 1.56 | ✓ (**0.29**) |
| `ihp-lna-2p45g` | IHP Apache-2.0 | 4/5 | clean | 2/4 | wifi24 | device_budget | −2.25 | −4.52 | **0.65** | 8.72 | 2.49 | ✓ (0.58) |
| `align-lna-qm` | ALIGN BSD-3 | 2/5 | clean | 1/2 | wideband-sdr | device_budget | −0.11 | 7.39 | 4.00 | 6.72 | **0.96** | ✓ (0.51) |
| `paper-noisecancel` | Tang 2021 (OA) | 3/5 | clean | 3/3 | wideband-sdr | ✓ | −2.36 | **9.23** | 1.54 | 8.27 | 1.36 | ✓ (0.44) |
| `paper-currentreuse` | Reddy 2025 (OA) | 5/5 | clean | 2/2 | wifi24 | ✓ | −1.80 | −2.99 | 1.04 | 10.88 | 3.35 | ✓ (0.57) |
| `paper-gmboostcg` | Li JSSC 2005 | 5/5 | clean | 1/2 | wifi24 | ✓ | −3.78 | −13.03 | 3.59 | 18.24 | 6.30 | ✓ (0.35) |
| `paper-transformerfb` | Wu TCAS-I 2017 | 5/5 | clean | 1/1 | wideband-sdr | max_inductors | −0.64 | 3.48 | 4.51 | 7.49 | 1.14 | ✓ (0.45) |
| `paper-diffcccg` | Zhuo TCAS-II 2005 | 5/5 | clean | 0/2 | wifi24 | single_input | −0.31 | −20.68 | 0.00 | 24.63 | 8.85 | ✓ (0.32) |

(`viol` is the worst single-constraint violation of the feasibility-first scalar;
metrics are the `ingest-v1` L2 label, dB / mA. Full JSON with every gate, budget
and reason: `lna/data/external/corpus_manifest.json`.)

**Readings that matter more than the table.**

* **No circuit was quarantined, and that is a claim about the scout's work, not a
  weak gate.** The gates have teeth — the vocabulary gate checks all 481 augmented
  rows, the identity gate compares two independently-derived WL hashes — and the
  provenance gate did fail once during development, on `ihp-gps-lna-nmos`, until
  the independence-statement matcher learned the phrasing "neither is derived
  from, nor references, …". That is the gate working, not the circuit failing.
* **The L0 misses are all the expected kind.** Three circuits exceed
  `device_budget` [3,16] on real layout practice (the HBT's 6 parallel unit
  fingers per transistor, kept faithfully, at 21 devices; five VDD–VSS decoupling
  caps in the 2.45 GHz design; a 12-resistor output trim ladder in the ALIGN
  core). `paper-diffcccg` misses `single_input` because it is differential and
  every project spec sets `differential: false`. `paper-transformerfb` misses
  `max_inductors: 1` because its transformer is represented as two galvanically
  separate inductors — AnalogGenie's vocabulary has **no mutual-inductance
  primitive at all**, so transformer *connectivity* is representable and magnetic
  coupling is not, for this and for every transformer design that could ever be
  added.
* **Every one of the nine is structurally novel against ref-v2** — 9 distinct WL
  hashes, none colliding with each other, the 41 corpus circuits, or the 148
  archetypes, with a maximum nearest-neighbour similarity of **0.612**. The corpus
  really did gain nine new structures, not nine re-spellings.
* **All nine label infeasible against their nearest-band spec, and that is the
  informative outcome, not a defect.** These are real designs sized *by us*, at a
  deliberately cheap budget, against *our* nearest target — not reproductions of
  their published numbers. The best are close: `align-lna-qm` at viol 0.96,
  `paper-transformerfb` at 1.14, `paper-noisecancel` at 1.36 (and it is the only
  one with net gain, S21 **+9.23 dB**). The HBT reads the best NF in the batch,
  **4.60 dB** — the first bipolar number this harness has ever produced.
* **L1 exposes a real bias gap, non-gating.** 4 of 9 have MOS that never conduct,
  and the pattern is systematic: `paper-diffcccg` conducts **0/2** because both CG
  gates are DC-fed through R1/R2 from a bias net the sweep does not own, and
  `paper-gmboostcg` 1/2 because the CG device's gate is driven by the auxiliary
  stage with no DC path. This is the same defect Session 4 fixed *by hand* for the
  `gmb_cg` / `nc_cgcs` archetypes (undriven+bypassed CG gate). `bias.py` has no
  rule for it, and no base-bias rule for bipolars at all.

**Ingestion mechanics.** Sequences come from the *upstream* Eulerian augmentation
(`Augmentation.dfs_all_paths` + the edge-cover check, execed read-only), so an
ingested circuit is indistinguishable from a dataset one where a trainer or the
reference consumes it. They are deliberately **not** written into
`AnalogGenie/repo/Dataset/`: that tree is an untracked upstream clone, usually a
junction into the main checkout, so new indices there would mutate shared state
nothing in this repo owns and a fresh worktree does not have. Read APIs are
`build_lna_corpus.external_sequences()` / `external_topologies()` /
`external_manifest()`.

**⚠ The augmentation budget is NOT uniform, and here is why.** The dataset stage
uses 200 solutions / 10 runs; upstream's cover check rebuilds the whole edge set
with pandas `.loc` scalar lookups (O(N²)) on *every candidate branch*, so cost
scales as (solutions × path length × N³). Measured: a 20-node circuit at 200/10
did not finish in 10 minutes. The batch therefore runs a per-circuit wall-clock
guard (300 s) over a budget ladder [(64,3), (20,2), (8,1)], and the budget that
actually produced each circuit's sequences is recorded per circuit:

| circuit | seqs | budget | seconds |
|---|---|---|---|
| `paper-noisecancel` | 64 | 64/3 | 21.5 |
| `paper-gmboostcg` | 64 | 64/3 | 28.4 |
| `ihp-gps-lna-nmos` | 64 | 64/3 | 62.6 |
| `paper-diffcccg` | 64 | 64/3 | 120.5 |
| `paper-currentreuse` | 25 | 64/3 | 125.0 (search exhausted at 25) |
| `ihp-lna-2p45g` | 64 | 64/3 | 139.4 |
| `paper-transformerfb` | 52 | 64/3 | 164.2 (exhausted at 52) |
| `align-lna-qm` | 64 | 64/3 | 164.6 |
| **`ihp-gps-lna-npn`** | **20** | **20/2** | 56.9 (**64/3 timed out at 300 s**) |

**481 sequences** total, 1183 s wall clock. For scale, the 41 dataset circuits
carry 4023 (min 1, median 69, mean 98, and **16 of 41 sit on the 200 cap**), so
the external set is **18% of the circuits but 10.7% of the rows** —
under-weighted, deliberately and measurably, and a future trainer that cares can
raise the budget knowingly. The real fix is an accelerated (and
equivalence-tested) cover check.

### 19.3 ref-v3 — and the honest result: the correction is exactly zero, today

Following §14.5's pattern exactly. `novelty.py`'s reference is now:

| version | contents | distinct WL hashes | digest |
|---|---|---|---|
| `ref-v1` | 41 corpus LNAs (the P0 freeze) | 41 | `5273a4f673b5eb6a` |
| `ref-v2` | 41 corpus + 148 archetypes | 189 | `b5689490d0285c37` |
| **`ref-v3`** (default) | **50 corpus** (41 dataset + **9 ingested**) + 148 archetypes | **198** | **`d05390da6183123e`** |

ref-v1 and ref-v2 stay reachable (`--ref v1` / `--ref v2`) and both digests
**reproduce to the digit** after the change. Every protocol row prints
`ref-v3[198h/d05390da]`, and `evaluate()` now splits copies three ways —
archetype / corpus / **ext** — so a corpus-expansion hit can never hide inside
"archetype copies".

#### The old → new table (frozen NDL@256 protocol, same pools on disk, only the stick moves)

| checkpoint | pool | ref-v1 | ref-v2 | **ref-v3** | Δ(v3−v2) | ext copies | indR |
|---|---|---|---|---|---|---|---|
| P0 prefix-12 | `sweep12repro{,_s2338}` | 16 | 16 | **16** | 0 | 0.0% | 0.141 |
| P5-v1 | `ft_p5_nb_s1337` | 60 | 30 | **30** | 0 | 0.0% | 0.179 |
| P5-v2 | `…nb_s1337.v2repro` | 73 | 41 | **41** | 0 | 0.0% | 0.209 |
| **P5-v3 (adopted)** | `…nb_s1337.v3` | 100 | 52 | **52** | 0 | 0.0% | 0.224 |
| P5-v4 | `…nb_s1337.v4` | 89 | 40 | **40** | 0 | 0.0% | 0.233 |
| P5-v5 | `ft_p5v2_nb_s1337` | 84 | 35 | **35** | 0 | 0.0% | 0.232 |
| P5-v6 | `ft_p5v6_nb_s1337` | 93 | 43 | **43** | 0 | 0.0% | 0.222 |
| ctrl-v1 (nb) | `ft_ctrl_nb_s1337` | 43 | 42 | **42** | 0 | 0.0% | 0.178 |
| ctrl-v1s (nb) | `ft_ctrls_nb_s1337` | 26 | 26 | **26** | 0 | 0.0% | 0.179 |
| **P5-v3 wb (adopted)** | `ft_p5v2_wb_s1337` | 35 | 21 | **21** | 0 | 0.0% | 0.077 |
| ctrl-v1 wb | `ft_ctrl_wb_s1337` | 31 | 31 | **31** | 0 | 0.0% | 0.156 |

**★ THE RE-FROZEN BASELINE: nb = 52, wb = 21 under `ref-v3[198h/d05390da]`, at
inductor ratio 0.224 / 0.077** — numerically identical to ref-v2, and now stamped
with a stick that has 198 hashes in it.

**Δ = 0 everywhere is the measurement, not an assumption, and it is the right
answer for a reason worth stating.** Not one sample in 2816 across eleven pools is
a WL-exact copy of any of the nine ingested circuits. It could not have been: none
of the nine has ever been in any training set. ref-v2 → ref-v3 is therefore **pure
insurance**, and the contrast with ref-v1 → ref-v2 (Δ up to −50, because the
archetypes *were* training data) is exactly the shape one should expect. The
moment a P5 arm is fine-tuned on the 50-circuit corpus — the future arm this
session exists to enable — a regurgitation of one of the nine becomes possible,
and under ref-v2 it would have scored **novel**. That is the ref-v1 defect one
layer up, closed before it can produce a wrong number rather than after.

Two consequences follow directly:

* **Any arm trained on the expanded corpus must be scored under ref-v3.** Scoring
  it under ref-v2 would inflate its NDL by exactly the amount it copies the new
  circuits.
* **Because Δ = 0, ref-v3 numbers are directly comparable to every ref-v2 number
  in §14.5 / §16 / §18 for pre-expansion arms.** No restatement of past sections
  is needed; the two sticks agree on all existing evidence.

#### The flip check

Every adopt/reject decision the program actually took, re-scored under ref-v3
(candidate vs *the then-current baseline*, not the best-ever):

| # | decision | ref-v2 | ref-v3 | verdict | flips? |
|---|---|---|---|---|---|
| 1 | prefix-12 → **P2** | (pool lost) | ≤24 vs 16 | ADOPT | **no** (inferred) |
| 2 | P2 → **P5-v1** | (pool lost) | 30 vs ≤24 | ADOPT | **no** (proved by the bound) |
| 3 | P5-v1 → **P5-v2** | 41 vs 30 | 41 vs 30 | ADOPT | **no** |
| 4 | P5-v2 → **P5-v3** | 52 vs 41 | 52 vs 41 | ADOPT | **no** |
| 5 | P5-v3 vs P5-v4 | 40 vs 52 | 40 vs 52 | reject | **no** |
| 6 | P5-v3 vs P5-v5 | 35 vs 52 | 35 vs 52 | reject | **no** |
| 7 | P5-v3 vs P5-v6 | 43 vs 52 | 43 vs 52 | reject | **no** |

**0 decisions flip.** Decision 2 is *proved* without P2's lost pool: ref-v3 ⊋
ref-v2 ⊋ ref-v1, and adding hashes can only remove items from the novel set, so
`NDL_v3(P2) ≤ NDL_v1(P2) = 24 < 30 = NDL_v3(P5-v1)`. Decision 1 remains
*inferred* (monotonicity bounds both sides and cannot separate them; P2 was
corpus-only-trained, and the measured P0 baseline has 0.0% archetype copies, so P2
has no regurgitation mechanism). The **ordering** is also unchanged from ref-v2 —
including P5-v2's §14.5 rise above P5-v4 / P5-v5 — but per §14.5's warning that is
a measured fact about these pools, not a guarantee to rely on.

### 19.4 Store, hygiene, and what is now true of the corpus

* **9 L2 rows appended, recipe `ingest-v1`, `nf_gated: true`** (tier-2 domain),
  `provenance.source_arm = "external-ingest"` carrying `external_id`. The budget
  is deliberately below `candidate-v1`: ZOAF `n_candidates=4, sgd_iters=4,
  cgd_iters=1`, `inductor_q=12`. **These rows must never be pooled with
  `candidate-v1` / `curated-v1` / `+bo3` rows** — different budget, different label
  domain, which is exactly why the recipe is stamped. The row is assembled in
  `ingest_external.l2_label` rather than inside `size.size_topology`, whose logging
  path hardcodes `candidate-v1`.
* **11 L1 rows appended.** ⚠ `paper-gmboostcg` carries **3** of them: two are from
  pre-run smoke tests of the driver, before its `--no-log` flag reached the L1
  path. They are identical measurements of the same topology and the store is
  append-only by design; dedup by `external_id` if it matters.
* ⚠ **`topo_labels.jsonl` and `l1_labels.jsonl` were left UNCOMMITTED by this
  track**, same call as §16's control-arm agent and for the same reason: they are
  the shared store and three other agents were appending to them live, so
  committing them would have committed their in-flight rows too. The 20 rows are
  on disk in the worktree; whoever commits those files next commits them.
* **The corpus is 50 circuits / 4504 augmented sequences.** `lna/data/external/`
  now holds, per circuit: `provenance.json`, the converter artefacts,
  `Sequence_total_<id>.npy`, `augment_budget.json`; plus the batch-level
  `corpus_manifest.json` (gates, budgets, verdicts, WL hashes, L1/L2 summaries).
* **Blind protocol honoured and re-verified mechanically.** The scout's per-file
  independence statements were re-checked in code, not trusted from a report; the
  excluded paper was never fetched.

```bash
python lna/build_lna_corpus.py --stage external        # augment (guarded ladder)
python lna/ingest_external.py --audit                  # gates only, no ngspice
python lna/ingest_external.py --run                    # full ladder + manifest
python lna/ref/check_bjt.py                            # bipolar golden
python lna/novelty.py --show-ref                       # v1/v2/v3 digests
python lna/novelty.py --eval <dir> --ref all --spec wifi24
python lna/_ndl_refv3.py && python lna/_ndl_flipcheck.py
```

### 19.5 Where this points next

1. **Train the arm.** This session's whole purpose is that a P5 fine-tune on the
   50-circuit corpus is now a one-command experiment with a correct measuring
   stick. Score it under **ref-v3**, against the re-frozen **nb 52 / wb 21**.
   `build_lna_corpus.external_sequences()` returns padded rows in exactly the
   shape `finetune._rows_from_npy` produces; wiring it in is a `finetune.py`
   change, and that file was another agent's tonight.
2. **The augmentation accelerator.** An equivalence-tested replacement for
   upstream's cover check would let the external set carry its proportional weight
   (10.7% → ~18% of rows) and would speed the dataset stage too.
3. **`bias.py` has no base-bias rule and no CG-gate rule.** 4 of 9 ingested
   circuits have MOS that never conduct, for reasons Session 4 already diagnosed
   and fixed by hand in `templates.py`. Encoding those two rules would improve
   every CG / gm-boosted / differential topology the generator produces, not just
   these nine.
4. **`has_transistor` counts MOS only** in both screens (§19.1) — a governance
   decision, deliberately not taken here.
5. **Six more real IHP LNAs are identified but unconverted**, behind a Qucs-S
   geometry parser, and IHP's tapeout program is renewable (LNA folders in 4 of 7
   campaigns checked) — see the scout's report §6.5.
---

## 20. Phase 2 — critic **v2** on the full store, and the live rung-1 rerank (Gate S1, first honest verdict) (Session 6)

> §17 is reserved by the scratch-hygiene track, §18 by the curriculum arm and
> §19 by the ingestion track; this section is numbered 20 to avoid a collision.
> Raw run record: `lna/data/reports/critic-v2-rung1-2026-08-09.md`.

Two questions, one answered by retraining and one by spending SPICE.

1. §15.4 measured critic v1 collapsing from **ρ ≈ 0.83 in-distribution to
   ρ ≈ +0.17…+0.20 on the mutant distribution search actually generates**, and
   diagnosed *coverage*: `v4-train` held 16 wideband-sdr and 24 dhruva-s rows.
   The rung-2 run then appended 213 rows on exactly those two specs. **Did the
   coverage fix it?**
2. 03-SEARCH §1's rung 1 — critic rerank of a fresh pool against an equal-budget
   random control — **had never been run live on any spec**. §15.5 recorded Gate
   S2 against a substituted control because of it. **Run it.**

### 20.1 Snapshot `v5-train`, and what critic v2 is

`v5-train` pins **1010 L2 rows** (1006 token-bearing) / 41 L1 rows,
sha256 `cc2f79ae…`. Spec mix wifi24 471 · dhruva-l1 249 · dhruva-s 132 ·
wideband-sdr 121 · gps-l1 23 · dhruva-l5 7 · dhruva-l2 7. σ(S21) = **0.783 dB**
at `candidate-v1+bo3` (0.726 dB at v4-train — the label-noise ceiling grew ~8%
as the store did). The two search specs went **40 → 253 rows**, and *all* of that
increase is the 213 evolve rows.

Gate C1 as restated (§14.6): ρ(S21) ≥ 0.5 **and** skill ≥ 0.25.

| split | arm | ρ(S21) v1 → v2 | prec@20% v1 → v2 | skill v1 → v2 | C1 |
|---|---|---|---|---|---|
| family holdout | WL-kNN | 0.687 → 0.696 | 0.842 → 0.800 | 0.687 → 0.603 | YES → YES |
| (n 95 → 123) | ridge | 0.790 → 0.775 | 0.737 → 0.680 | 0.479 → 0.365 | YES → YES |
| | **GNN ens-5** | 0.839 → **0.828** | 0.895 → 0.840 | 0.792 → **0.683** | YES → **YES** |
| source-shift | WL-kNN | 0.370 → 0.384 | 0.512 → 0.537 | 0.105 → 0.140 | no → **no** |
| (n 420 → 477) | ridge | 0.585 → **0.631** | 0.655 → 0.705 | 0.367 → **0.453** | YES → YES |
| | **GNN ens-5** | 0.610 → 0.586 | 0.655 → 0.684 | 0.367 → **0.414** | YES → **YES** |

**On the frozen splits, critic v2 is critic v1.** Every verdict is unchanged; the
movements are within the range two ensemble seeds produce. Two things are worth
saying out loud rather than leaving buried:

* **ridge now out-ranks the shipped GNN on the source-shift split** (ρ 0.631 vs
  0.586, skill 0.453 vs 0.414, ρ(S11) 0.629 vs 0.570). The GNN keeps the family
  split (0.828 vs 0.775) and keeps the ensemble σ, which is why it still ships —
  but "the GNN is the best arm" is now true on only one of the two splits, and
  that should be re-checked, not assumed, at the next retrain.
* ⚠ **Neither frozen split tests the mutant distribution at all.**
  `critic.is_generated` keys off `provenance.token_file`, and the 213 evolve rows
  carry none (they are graph edits, not sampler output), so all 213 land on the
  **train** side of the source-shift split. The family holdout, separately, drew
  only 8 dhruva-s and 7 wideband-sdr test rows. This is precisely why the §15.4
  collapse was invisible to `critic.py --eval`, and it is a standing measurement
  gap, not a one-off.

### 20.2 ★ The mutant post-hoc: coverage repairs most of the collapse

New mode `critic_gnn.py --mutant-eval`. 213 evolve rows in **171 WL families**,
three regimes over the same test rows: **v1-equiv** (train on every non-evolve
row — reproduces v1's coverage exactly: wideband-sdr 16, dhruva-s 24),
**v2-cv** (3-fold over the evolve *families*, so no row is scored by an ensemble
that saw its family), and **v2-leaky** (train on everything — an upper bound,
quoted as leakage, never as a result). `evolve-random` is the selection-free arm;
`evolve-evolve` are the elites the critic itself picked.

The reproduction is sound: **v1-equiv reproduces §15.4's deployed numbers to
within seed noise** — dhruva-s control ρ(mean−βσ) +0.218 vs §15.4's +0.220,
wideband-sdr control +0.195 vs +0.175.

| spec / arm | n | ρ(feasibility) v1-equiv → **v2-cv** | skill v1-equiv → **v2-cv** |
|---|---|---|---|
| dhruva-s / random (selection-free) | 60 | +0.173 → **+0.441** | −0.094 → **+0.375** |
| wideband-sdr / random (selection-free) | 63 | +0.198 → **+0.502** | +0.160 → **+0.300** |
| dhruva-s / evolve elites | 48 | +0.027 → **+0.641** | 0.200 → 1.000 |
| wideband-sdr / evolve elites | 42 | −0.224 → **+0.479** | −0.029 → −0.235 † |

† at base 0.143 that cell has 6 near-feasible rows in a top-20% of 8 — noise, not
a regression.

**★ Verdict: the diagnosis was right and the fix is real but partial.** On the
distribution search actually generates, the critic goes from ρ ≈ +0.17…+0.20 (a
fifth of in-distribution, and useless for selection) to **ρ ≈ +0.44…+0.50**, and
from *negative* correlation on its own selected elites to **+0.48…+0.64**.
Selection skill on both selection-free arms now clears θ = 0.25 where neither did
before. It is still only ~55–60% of the in-distribution 0.81, so the coverage
lever is not exhausted — but "a ranker with ρ ≈ 0.17 cannot beat coin-flip
selection by 2×" (§15.4) no longer describes the critic.

**The leaky bound does two jobs, and quoting it is not one of them.** With the
evolve rows in train, ρ(feasibility) on the two selection-free arms is **+0.736 /
+0.857** against v2-cv's +0.441 / +0.502. First, that gap is the proof the family
CV really holds something out — a leaking CV would coincide with it. Second, it
caps what more coverage *of this kind* can buy: the architecture can rank these
designs at ρ ≈ 0.8, so the out-of-fold ρ ≈ 0.47 is a **generalization gap across
topology families**, not a capacity limit. More rows inside the 171 families
already sampled will not close it; rows from *new* families might.

### 20.3 Calibration: the uncertainty gate's premise is inverted, and coverage makes it worse

| | v1-equiv | v2-cv |
|---|---|---|
| in-distribution holdout ρ(σ, abs err) | **0.583** | **0.507** |
| mutant ρ(σ, abs err), four groups | +0.117 / +0.337 / +0.055 / +0.099 | +0.148 / +0.414 / +0.363 / +0.146 |
| holdout p90 σ (= the gate threshold) | 0.2922 | 0.3077 |
| median mutant σ | 0.117 – 0.206 | 0.103 – 0.165 |
| **mutant rows above the gate** | **22/213 (10.3%)** | **8/213 (3.8%)** |

The ensemble is *well* calibrated in distribution — ρ(σ, |error|) ≈ 0.5–0.6 both
before and after, and 0.651 / 0.578 on the two frozen splits — and only weakly,
unstably calibrated on mutants. That is the whole mechanism behind §15.4's
`n_high_unc = 0` across all 80 generations: **mutant σ is systematically *smaller*
than holdout σ, not larger.** The gate compares off-distribution candidates
against a threshold set by held-out *families*, which are structurally unusual,
while mutants are one-edit perturbations of well-covered graphs. Better coverage
makes the gate *more* inert, not less — median mutant σ falls on every group and
the firing rate halves, 10.3% → 3.8%. The live rung-1 pool agrees: **2/110** fresh
generated candidates exceeded the gate.

**Conclusion for 03-SEARCH §4 rule 2: a σ-percentile gate cannot detect this
shift and should be retired in favour of a distance-to-training-set gate** — which
is what the trust region (rule 3) already is, and which §15.4 measured doing real
work. Keeping rule 2 as written is keeping a rule that has never fired.

### 20.4 ★★ Rung 1, live — Gate S1 gets its first honest verdict

03-SEARCH §1 run on real SPICE for the first time. Target spec **dhruva-s** (the
richest new coverage). Pool = the **adopted** P5-v3 generator's unsized remainder:
`ft_p5v2_nb_s1337.v3`, 256 samples → L0 209 → WL-distinct 113 → **110 never sized
against dhruva-s** (51 novel vs `ref-v2[189h/b5689490]` + store; ref-v3 (§19)
landed later in the session and does not apply to these rows' stamps).

The ranker is **leak-free by construction**: all 244 store rows carrying one of
the pool's 110 WL hashes — under *any* spec — were dropped before training
(568 train / 95 val / 99 holdout, holdout ρ(S21) 0.824). Arms are k = 30 each, the
control drawn by `random.Random(1337).sample` and declared before any SPICE ran;
the 6 shared candidates are simulated **once** and credited to both arms, so each
arm's budget is exactly 30 sizings of the identical protocol (light all-free ZOAF
scan → box-clamped `size.polish(60)`, `inductor_q=12`, recipe `rung1-v1`).

```
arm         k  sized   ok  feas  near   base  bestviol  medviol  SPICE-min
critic     30     30   30     0    15  0.500     1.014    2.222       30.4
control    30     30   30     0     8  0.267     1.015    2.661       34.3
```

* **Gate S1 as written (≥ 2× the control's feasible-or-near-feasible count):
  15 vs 8 = 1.88× → NOT MET.** One more near-feasible design would have read
  exactly 2.00×. Fisher exact one-sided **p = 0.055** (conservative — the shared
  candidates make the arms positively dependent).
* **Gate S1 under the restated skill bar (§14.6): skill = 0.328 ≥ θ = 0.25 →
  MET.** (base 0.267 from the control arm; ceiling precision 0.978.)
* **realized-vs-predicted ρ = +0.578** over all 54 sized candidates — the
  deployment-distribution number 03-SEARCH §1 asks to report alongside, measured
  on a live generated pool for the first time, and stable across strata
  (novel-vs-ref-v2 n=22 **+0.621**; structure-never-labeled n=14 +0.552).
* cost **64.7 SPICE-min** total (12 885 ngspice evaluations, ~64 s/sizing, ~30 min
  wall at 2 shards) — inside the ≤90 SPICE-min/arm budget by 3×.

**Where the edge is.** Counting margins ≤ −1 scale unit, the critic arm is better
on every constraint and most on **NF**: S11 8 vs 12, S21 7 vs 10, **NF 3 vs 9**.
NF is the constraint the whole dhruva ladder is stuck on (Gate D3), so that is the
useful half of the result.

**What it is not.** **0 fully feasible designs in either arm** — `dhruva-s` wants
S21 ≥ 30 **and** S11_max ≤ −10 **and** NF ≤ 3.5 **and** Idd ≤ 13 at once, and the
program has exactly one tier-1-clean design on this spec (§15.3) and none tier-2.
And the `bestviol` column ties (1.014 vs 1.015) **for a bad reason**: the
lowest-violation points are degenerate shrink-to-nothing optima that satisfy
S11/Idd/NF by producing no gain (seq0038: S11 −14.5 dB, Idd 0.35 mA, NF 3.48 dB,
**S21 −0.43 dB**) — exactly the pathology §15.5 item 5 flagged, now confirmed on a
second spec and a second search rung. Among designs with real gain
(S21 margin > −1) the ordering is unambiguous and **the best four all came from
the critic arm**:

```
seq0218  rank= 6  critic          viol=1.377  S11=-0.32 S21=17.73 Idd=2.94 NF=2.82
seq0126  rank= 1  critic  NOVEL   viol=1.466  S11=-0.01 S21=15.98 Idd=4.32 NF=2.73
seq0073  rank=15  critic          viol=1.587  S11=-0.70 S21=10.29 Idd=4.94 NF=3.24
seq0029  rank=12  critic  NOVEL   viol=1.670  S11=-0.03 S21=17.81 Idd=5.12 NF=4.43
```

`seq0126` is novel against ref-v2 + the whole store and reaches **NF 2.73 dB at
15.98 dB gain** — under the 3.5 dB spec — with the input match unsolved
(S11_max −0.01 dB). It is an NF *lead*, not a design; the sizer never solved its
match, which is the same "all-free ZOAF lands gain OR match, not both" failure
06-LAST-MILE §1 documented and `_curate` exists to fix.

**Novelty accounting.** The critic **under**-selects novelty — 11/30 novel vs
ref-v2 against the control's 15/30 and the pool's 46% — and still wins on
near-feasibility. It mildly prefers archetype-like structures.

### 20.5 What this changes

1. **Gate S1: NOT MET on its literal ≥2× wording (1.88×, p = 0.055), MET on the
   restated skill bar (0.328 vs θ = 0.25).** Both readings are recorded; the
   literal bar inherits the same base-rate defect §14.6 retired for C1 (at
   base 0.267 with k/n = 0.27 the *ceiling* on the ratio is 3.67×, so "2×" demands
   precision 0.533 of a ranker whose maximum is 0.978 — reachable here, but the
   bar drifts with the pool exactly as C1's did). **Recommend restating S1's ratio
   half the same way C1's was**, and re-reading this run under it.
2. **The rung-2 comparison in §15.5 can now be closed properly.** Rung 1 has a
   live number on dhruva-s: 15 near-feasible / 0 feasible per 30 sizings
   (30.4 SPICE-min). Rung 2's dhruva-s evolve arm was 41 near / 0 feasible per 47
   true evals (69.1 SPICE-min). Per SPICE-minute that is **0.49 near/min (rung 1)
   vs 0.59 (rung 2)** — comparable, rung 2 slightly ahead, and *both* zero on
   feasibility. Neither rung is the bottleneck; the topology–spec gap is.
3. **Retire the σ-percentile uncertainty gate** (§20.3); keep the trust region.
4. **Guard the violation scalar against degenerate optima** — §15.5 item 5 is now
   confirmed twice and it is corrupting the headline metric on dhruva-s. Every
   "best violation" claim on a gain-limited spec needs an S21-margin floor.
5. **Coverage is still the live lever, and it is now self-funding**: this run added
   54 dhruva-s rows (132 → 186 for that spec) at 64.7 SPICE-min, on exactly the
   distribution the critic is weakest on.

---

## 21. Phase 3 — WP-BIAS v3: the DC-return rules, and the third measurement that finally moved the conducting rate (Session 6)

> §17–§20 are the scratch-hygiene, curriculum, ingestion and critic tracks; this
> section is numbered 21 to avoid a collision.

`bias.py`'s `R-DIAGNOSE-ONLY` has classified drains and sources without feeding
them since WP-BIAS v1, on an explicit "measure before adding rules" principle.
Three independent measurements have now been taken and they agree:

1. **The corpus off-MOS split** (HANDOVER finding #9, reproduced exactly by
   `--validate` tonight): of 43 off devices, **15 source-no-DC-path, 16
   drain-no-DC-path, 12 load/sizing**. Finding #9 pre-approved the R-SOURCE /
   R-DRAIN escalation "when it blocks sizing yield".
2. **§19.2 (ingestion):** 4 of the 9 newly ingested real LNAs have MOS that never
   conduct, every one of them listed under `sources_no_dc_path`.
3. **§17.6 (NF track):** an opt-in *gate*-rescue that promoted rail-reaching
   gates to R-GATE bias nets gained **0 of those 4** and was reverted. No gate
   bias can turn on a device whose source has no DC return.

So the rule was built. **It works, and it is off by default.**

### 21.1 The rules, and why they are opt-in

    R-SOURCE   a MOS source node whose DC component reaches neither a power/bias
               rail nor ground gets a return resistor to its device's return
               rail (NMOS -> 0, PMOS -> VDD).
    R-DRAIN    the same for a drain node, to the opposite rail (NMOS -> VDD,
               PMOS -> 0) -- a load feed.

**Opt-in was a decision, not caution-by-default.** R-GATE only makes a circuit
*biasable*: it defines DC on nodes that had no DC definition at all. A source
return resistor **changes the circuit** — it is a real element in the signal
path — and `size.size_topology` calls `insert_bias` on every sizing run, so
switching these on by default would silently re-domain every future L2 label.
The monotonic guard proves conduction never degrades; it cannot prove the
*sizing* domain is unchanged. That is a decision to take on purpose, not a side
effect of landing a rule. Enable with `--rules v3` / `LNA_BIAS_RULES=source,drain`
/ `insert_bias(..., rules=("source","drain"))`.

**Default byte-identity is verified, not assumed.** Old and new `bias.py` were
run in the same process (a separate process compares nothing — internal node
names come from set iteration) over all 41 corpus circuits × ideal/Q=12: the
default `build()` element list, params, bias nets and every v1 `report()` key are
**identical on 82/82**. The candidate ladder is byte-identical too: with `rules`
empty the sweep evaluates the same candidates in the same order with the same
early break and the same sim count.

Three implementation choices worth keeping:

* **The elements are named `RBIASSRC*` / `RBIASDRN*`**, so the existing
  `^(RBIAS|CBYP|VBGEN)` naming contract already excludes them from the screen,
  from novelty and from the spec `device_budget` — **no `topology.py` change**.
* **The resistances are `.param`s but not `pVBG*`**, so `size.classify_params`
  files them under *fixed*. The sizer inherits the scaffolding; it does not gain
  a free variable from it, and **no `size.py` change** was needed.
* **The guard extends for free.** Candidates are now a *ladder* of rule sets
  (none → gate → gate+source → gate+source+drain), each swept, with the same
  "strictly more conducting MOS" comparison and the no-bias baseline still
  candidate 0. A v3 stage is therefore adopted only if it turns more devices on:
  best-of over a superset that still contains the old candidate set. Measured:
  **0 circuits made worse**, in every configuration.

Cost control: v3 stages sweep the VBG grid **tied** (4 points, not 4ⁿ), because
the untied gate stage has already searched that space and its best is retained —
a v3 stage only needs to find *additional* conduction. `--validate` over the 41
corpus circuits costs **20.8 s (v1) → 32.4 s (+R-SOURCE) → 47.2 s (+R-DRAIN)**.

### 21.2 Corpus: 22/41 → 26/41 all-MOS-on, and the off-MOS split collapses

`python lna/bias.py --validate [--rules ...]`, 41 dataset LNAs:

| | v1 (default) | + R-SOURCE | + R-SOURCE + R-DRAIN |
|---|---|---|---|
| **all MOS ON** (bias's job) | 22/41 (54%) | 25/41 (61%) | **26/41 (63%)** |
| all MOS SATURATED (sizing's job) | 14/41 (34%) | 15/41 (37%) | **16/41 (39%)** |
| **circuits made worse** | 0 | **0** | **0** |
| off MOS, total | 43 | 29 | **21** |
| … source-no-DC-path | **15** | **3** | **3** |
| … drain-no-DC-path | 16 | 14 | **6** |
| … load/sizing | 12 | 12 | 12 |
| circuits where a v3 stage won | – | 11/41 | 13/41 |
| `--validate` wall clock | 20.8 s | 32.4 s | 47.2 s |

* **R-SOURCE does what it was built to do: source-no-DC-path off devices 15 → 3
  (−80%).** R-DRAIN then takes drain-no-DC-path 16 → 6. Together the off
  population halves, 43 → 21.
* **The 12 load/sizing off devices do not move at all** — in any configuration.
  That is the correct behaviour and a useful confirmation of the v1 split: those
  devices are off because unsized loads force triode, which is WP-SIZE's problem
  and not addressable by any bias rule.
* **The headline still misses WP-BIAS's ≥80% acceptance bar (63%).** The
  remaining gap is now almost entirely the load/sizing class plus a handful of
  structurally-unbiasable devices (§21.3), not a missing bias rule.
* **461's spot check is untouched** (NM1 Vgs = 302 mV), i.e. the v1 result the
  whole rule set was validated on is unchanged.

**⚠ The rule is offered far more often than it is taken, and that is by design.**
24 of 41 circuits have at least one v3 target (20 with a source target / 26 target
nodes; 21 with a drain target / 32 nodes) but a v3 stage is adopted in only
**13 of those 24**. The reason is a known false-positive class, worth stating
plainly: **the DC graph treats a MOS channel as an open**, so the *interior*
nodes of a legitimate cascode or current-reuse stack read "no DC path" even
though the stack conducts perfectly well once every device is on. Those nodes get
offered a return resistor they do not need, and the guard declines. The
false-positive rate is therefore ~46% of offered circuits, absorbed entirely by
the guard rather than by the circuits.

### 21.3 The nine ingested circuits: 3 of the 4 blocked ones are fixed, and the 4th was never a bias problem

§19.2's four blocked externals, re-run with `rules=("source","drain")`:

| circuit | v1 conducting | v3 conducting | adopted | R |
|---|---|---|---|---|
| **`paper-diffcccg`** | **0/2** | **2/2** | R-SOURCE | 200 Ω |
| **`align-lna-qm`** | 1/2 | **2/2** | R-SOURCE | 200 Ω |
| **`paper-gmboostcg`** | 1/2 | **2/2** | R-SOURCE | 200 Ω |
| `ihp-lna-2p45g` | 2/4 | 2/4 | none | – |
| `ihp-gps-lna-nmos` | 3/3 | 3/3 | none (already all-on) | – |
| `ihp-gps-lna-npn` | 1/1 | 1/1 | none | – |
| `paper-currentreuse` | 2/2 | 2/2 | none | – |
| `paper-noisecancel` | 3/3 | 3/3 | none | – |
| `paper-transformerfb` | 1/1 | 1/1 | none | – |
| **total** | **14/20** | **18/20** | | |
| **circuits with all MOS on** | **5/9** | **8/9** | | |

**Three of the four are fully fixed, all by R-SOURCE alone, all at the grid's
smallest resistance (200 Ω).** R-DRAIN contributed nothing on this population —
it is the corpus rule, not the external one. `paper-diffcccg` is the sharpest
case and the one §17.6 called out: a differential capacitor-cross-coupled CG
whose *tail current source the single-ended token flow cannot represent at all*.
Its two CG sources are the differential input nets, DC-blocked by `to_spice`, so
neither device could ever conduct — 0/2 under every previous rule set. A source
return resistor is precisely the missing tail element, and it takes it to 2/2.

**The fourth is not a bias failure and no rule should "fix" it.** `ihp-lna-2p45g`
stays 2/4 because its two off devices are structurally incapable of conducting:

* **`NM4` has all four pins on node 0** — this is the dummy transistor the
  converter flagged in its own `provenance.json` (`MMn3`, "all four pins land on
  VSS … plausibly a real dummy/matching transistor common in RF layout"). Vgs ≡
  Vds ≡ 0 by construction.
* **`NM3` has its gate tied to its own source** (both on node `n3`, drain on
  ground), so Vgs ≡ 0 regardless of any external bias.

The v3 analyzer *does* offer both a target (`n3` gets a source return); the guard
correctly declines, because no resistor changes Vgs = 0. **So the honest score on
§19.2's "4 blocked circuits" is 3 fixed / 1 not a bias problem** — and the
diagnosis for the fourth is a fact about the source netlist, independently
corroborated by the converter's own note.

### 21.4 Store and reproduction

* **+50 L1 rows** in the new domain: the 41-circuit corpus pass and the 9
  externals, each stamped `provenance.recipe = "bias-v3"` and
  `provenance.bias_rules = ["source","drain"]`. v1 rows carry no `recipe` key, so
  the two domains separate cleanly — **do not pool them**; a v3 row's
  `n_conducting` is measured on a deck with extra elements in it. As in §19.4,
  `l1_labels.jsonl` itself is left **uncommitted** by this track: it is the shared
  store and other agents were appending to it live.
* The report gained `source_returns` / `drain_feeds` (target node → rail, with a
  `mixed` flag for the rare node shared by both polarities) and, when a stage is
  adopted, `rules_applied` plus the winning `r_src` / `r_drn`.
* Nothing outside `bias.py` changed. `size.py`, `moves.py` and the specs were not
  touched (the NF track owns them and was mid-campaign).

```bash
python lna/bias.py --validate                      # v1, unchanged (22/41)
python lna/bias.py --validate --rules source       # 25/41
python lna/bias.py --validate --rules v3           # 26/41
LNA_BIAS_RULES=source,drain python lna/size.py ... # session-wide opt-in
python lna/bias.py --index 476 --sweep --rules v3  # one circuit, verbose
```

### 21.5 Where this points next

1. **The decision this section deliberately did not take: should v3 be default-on
   for sizing?** It would re-domain every future L2 label, so it needs the same
   explicit treatment as §14.5's reference bump. The measurement that would settle
   it is small and concrete: re-size the 13 corpus circuits and 3 externals that
   adopt a v3 stage, with and without it, and compare feasibility/violation — not
   conduction, which we already know improves.
2. **Kill the false positives at the source.** A DC-graph that understood
   "conducting MOS channel" for *stack interior* nodes would stop offering
   returns to cascode midpoints; the cheap version is to skip a source node that
   is also another MOS's drain whose own source already reaches a rail. That
   would take the offer rate from 24/41 towards the 13/41 that actually benefit.
3. **The ≥80% acceptance bar is now a sizing problem, not a bias problem** — 12
   of the 21 remaining off devices are the load/sizing class and have not moved
   under any rule in three sessions.
4. **`paper-diffcccg` remains the vocabulary argument.** The rule rescues it
   electrically, but a tail *current source* is still unrepresentable in the
   token vocabulary, exactly like the transformer coupling of §19.2. Two
   independent circuits now point at the same gap.

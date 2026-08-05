# Handover to Fable — LNA topology generation

**From:** Opus 5 session, 2026-08-05 · **Repo:** `C:\Users\Devavrat\circuit-repro`
· **Owner:** Devavrat Patni

You are picking up a working but incomplete LNA generation pipeline. Read
[FINDINGS.md](FINDINGS.md) for the measured capability assessment and
[WORKLOG.md](WORKLOG.md) for what was tried and what failed — **especially F1,
which is unresolved and is probably yours to solve.**

Two things are being asked of you. They are stated in §3 and §4. Everything
before that is context so you do not redo work or repeat mistakes.

---

## 1. Where things stand

**One sentence:** we can now generate LNA-shaped topologies on demand and
simulate them, but there is no specification saying *what LNA* to design, and
generated topologies have no bias network or device values, so nothing can yet be
scored on real performance.

What is measured and solid:

| | |
|---|---|
| LNA data available | 41 circuits (indices 461–492, 1081–1090) → **4,023 augmented sequences** |
| Generation, unconditional | **0%** produce an LNA-shaped topology |
| Generation, 12-token LNA prefix | **40.6%** — no retraining |
| Novel distinct LNAs at that setting | 16 per 128 samples |
| Candidates that reach a working simulation | 48 of 52 (**92%**) |
| Throughput | **0.3 s/sequence** on the WSL GPU |
| ngspice capability | `op`, `ac`, `noise`, **`sp`** all confirmed |

What is missing — in priority order:

1. **No target specification.** Nothing in the pipeline says "2.4 GHz, NF < 2 dB,
   S11 < −10 dB, 10 mW". Topologies are screened *structurally*, not against any
   requirement. This is ask §4.
2. **No bias network.** Dataset circuits are textbook schematics with biasing
   implied. Reconstructing circuit 461 and simulating gives Vgs = 14 mV,
   Id = 7.7 µA — the transistor is off. Until this is solved, every performance
   number from a generated topology is meaningless. The model cannot fix this;
   the information was never in the training data.
3. **No device values.** AnalogGenie emits topology only. `to_spice.py` deliberately
   emits every W/L/R/C/L as a `.param` so a sizer can drive them, but no sizer is
   wired up.
4. **No known-good reference LNA.** See WORKLOG F1 — I failed to hand-design a
   well-matched 2.4 GHz LNA. Without one there is no regression anchor for the
   measurement harness.

---

## 2. What already exists — do not rebuild these

All under `lna/`, all runnable on Windows or WSL. Every one has `--help`.

| File | What it does |
|---|---|
| `genie_common.py` | vocabulary (byte-identical to upstream), model loading, **batched sampling with early stop and prefix conditioning** |
| `test_vocab_matches_upstream.py` | guards that token ids still match the checkpoint — run this first, always |
| `build_lna_corpus.py` | AnalogGenie preprocessing over the LNA subset only |
| `topology.py` | token sequence → devices/electrical nodes; the LNA structural screen |
| `screen.py` | scores corpus or generated sequences |
| `generate.py` | sampling driver, unconditional or LNA-conditioned |
| `to_spice.py` | topology → parameterised ngspice netlist with S-param + noise setup |
| `pipeline_yield.py` | end-to-end topology → netlist → simulation yield |
| `novelty.py` | are conditioned samples novel, or copies of their seed? |
| `profile_generate.py` | batching/throughput profiler |

Recommended operating point, established by sweep:

```bash
# WSL, GPU
/opt/miniconda/envs/gpu/bin/python lna/generate.py \
    --n 128 --batch 32 --max-tokens 256 \
    --device cuda --prefix lna --prefix-len 12 --out lna/out/run1

# Windows, analysis
python lna/screen.py --generated "lna/out/run1/seq*.txt"
python lna/pipeline_yield.py --generated lna/out/run1 --min-score 5
```

**Environment gotchas that will cost you an hour each if you rediscover them:**
use `C:\msys64\ucrt64\bin\ngspice_con.exe` (not `ngspice.exe` — no stdout); batch
32 / 256-token cap on the 4 GB card or you get `cudaErrorUnknown`; and the ngspice
trap table in WORKLOG §"Fixes worth remembering" (X1–X10). The `ln` builtin
collision and case-insensitive parameter names are both silent-failure modes.

---

## 3. Ask one — how do we make LNA generation better?

Prefix conditioning got us from 0% to 40.6% for free, but it is a sampling-time
trick with a known ceiling: at prefix length 24 the hit rate reaches 50.8% while
83% of output is a verbatim copy of the seed circuit. **We are trading novelty for
yield along a curve, and we want to move the curve, not slide along it.**

Some directions are already obvious and are written up in FINDINGS.md §8 — 
fine-tuning on the 4,023-sequence LNA corpus, adding a KV cache, rule-based bias
insertion. Treat those as the baseline to beat, not the answer.

What would be genuinely valuable from you:

* **Ways to raise the novelty ceiling.** Copying the seed is the core limitation.
  Is there a sampling scheme, a training objective, or a representation change
  that produces topologies that are LNA-*like* without being LNA-*copies*? Note
  that the screen currently rewards resemblance, so any proposal needs a novelty
  measure that cannot be gamed — `novelty.py` fingerprints by (device type,
  sorted node labels) and is deliberately coarse.
* **Whether the Eulerian-path representation is the right substrate at all.**
  Every sequence starts at VSS by construction, generation length is unbounded,
  and the model has no notion of a circuit being "finished" other than emitting
  TRUNCATE. Is there a better formulation, and is it worth the cost of leaving
  the pretrained checkpoint behind?
* **How to close the inductor gap specifically.** At the recommended operating
  point, conditioned samples reach an inductor ratio of 0.145 against 0.188 for
  real LNAs, and 49.2% carry any inductor versus 63.5% of genuine LNAs (at the
  older 512-token cap it was worse, 37.5%). Inductors are the strongest LNA
  signal and the model under-produces them, because they are 0.8% of the corpus
  at large. Would constrained decoding, logit biasing, or a structural prior work
  better than fine-tuning here?
* **Whether the 41-circuit corpus is enough**, and if not, where more LNA
  topologies could legitimately come from — augmentation beyond Eulerian
  reorderings, synthesis from known LNA archetypes, or something else.

Be concrete about cost. The hardware is one RTX 3050 with 4 GB; anything
requiring a large training run needs to justify itself against fine-tuning an
11.8M-parameter model, which is nearly free here.

---

## 4. Ask two — how do we define what LNA we are designing?

**This is the more important of the two asks**, and it is currently a complete
blank. The pipeline generates and screens topologies with no notion of a target.
A "good LNA" is meaningless without a specification, and different applications
imply genuinely different topologies — a 2.4 GHz WiFi front end, a 1.575 GHz GPS
receiver, and a 28 GHz mmWave element are not the same design problem.

What is needed is a **specification format the pipeline can consume** — something
`screen.py` and a future sizing loop can both read, that turns "is this
LNA-shaped?" into "does this meet the requirement?".

Dimensions that plausibly belong in it, as a starting point rather than a
prescription:

* **Band** — centre frequency, bandwidth, whether it is narrowband tuned or
  wideband.
* **Noise** — NF target. The defining LNA metric and the one the harness already
  extracts.
* **Gain** — S21, and whether flatness across the band matters.
* **Match** — S11 (and S22) targets; the conventional −10 dB, or tighter.
* **Linearity** — IIP3 / P1dB. **Note: not currently measured.** This needs a
  two-tone transient or `.disto` analysis that does not exist in the harness yet,
  so specifying it implies building it.
* **Power** — supply voltage and current budget.
* **Topology constraints** — single-ended vs differential; is an on-chip inductor
  allowed, and at what minimum realizable value; how many inductors are
  acceptable given area.
* **Process** — currently only 45nm BPTM BSIM4 models are available
  (`AutoCkt/repo/eval_engines/ngspice/ngspice_inputs/spice_models/45nm_bulk.txt`).

Specific questions worth answering:

1. **What should the format be?** A YAML/JSON spec file is the obvious guess, but
   the useful question is what it must contain so that a topology can be scored
   *before* sizing — many specs are only meaningful after device values are
   chosen, and we need a screen that works on an unsized topology.
2. **How do hard constraints and soft objectives separate?** NF and S11 behave
   like constraints; gain and power behave like objectives. A single scalar
   reward hides this, and the ZOAF sizer will need it explicit.
3. **How should a spec constrain generation, not just evaluation?** If the target
   is 2.4 GHz narrowband, that implies inductors and a tuned load. Can the spec
   feed back into prefix selection or decoding, so we generate plausible
   candidates rather than filtering afterwards?
4. **What are sensible default specs to start from?** Two or three concrete,
   defensible reference targets — pulled from real standards rather than
   invented — would let the pipeline be exercised end to end immediately.
5. **What does the minimum realizable inductor constraint do to the design
   space?** WORKLOG F1 ran into this: the 45nm model's fT is 300–600 GHz, which
   drives the classic inductively-degenerated match to 12–27 pH, far below what
   is realizable on-chip. Either the bias point must move well away from peak fT,
   or the topology class must change. **This constraint appears to bind hard and
   deserves early attention** — it may rule out the canonical LNA topology on
   this process, which would be an important thing to know before optimising
   toward it.

---

## 5. Open questions carried over

* **H-Q1 — the unexplained Zin measurement (WORKLOG F1.6).** Measured
  Re(Zin) = 1122 Ω, Im = −10 Ω where theory says ≈82 Ω and ≈−410 Ω. Untested
  hypothesis: the output tank resonates at ≈2.77 GHz, inside the measurement
  band, and reshapes the input impedance through feedback. **Test by detuning the
  tank far from band and re-measuring.** Until this is understood, I would not
  trust hand-derived matching numbers on this process.
* **H-Q2 — no reference LNA.** There is no known-good, well-matched design to
  regression-test the harness against. Best achieved was S11 = −0.78 dB, which
  characterises a broken circuit.
* **H-Q3 — index 1081** fails with a singular matrix that `rshunt` does not fix;
  a genuinely floating sub-circuit. Low priority, but it is a real topology the
  pipeline cannot handle.
* **H-Q4 — the screen's own ceiling.** 59.4% of *real* LNAs score 5, because 40%
  are inductorless variants. Any generator evaluated against this screen is being
  measured against 59.4%, not 100%. If inductorless LNAs matter for the target
  spec, the screen needs reworking.

---

## 6. What "done" would look like

Not a request for code — a request for a plan you believe in. Concretely:

1. A specification format, with two or three worked reference targets.
2. A defensible answer on whether the current representation and checkpoint are
   worth building on, or whether something else should replace them.
3. A ranked set of proposals for improving generation, each with an estimated
   cost on this hardware and a way to measure whether it worked.
4. A position on the bias-insertion problem (§1 item 2), since nothing downstream
   can be scored until it is solved.

Where you disagree with a conclusion in FINDINGS.md, say so — several of them
rest on single measurements, and the one I am least confident in is flagged as
H-Q1.

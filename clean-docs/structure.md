# STRUCTURE — how the pipeline actually works

*Clean version of `lna/STRUCTURE_LOGIC.md`. That file is the architecture snapshot:
the building blocks that exist right now, how each is built (or explicitly *not*
trained), and what feeds what. Read this to answer "how does this machine work?"; read
[journey.md](journey.md) for "how did we get here?" Where code and prose disagreed, the
original sided with the code.*

## The big picture

The pipeline is a chain. Most of it is **deterministic** (not learned); only two blocks
are trained models, and there is **no reinforcement learning anywhere** — the file
backs that with a grep.

```
Data sources → Generator (LLM) → Screen (L0) → Bias (L1) → Sizing + SPICE (L2)
                    ↑                                              ↓
                 Fine-tune  ←──────  Label store  ←───────────────┘
                    ↑                     ↓
                 Winners            Critic + surrogate → Search → Loops (governance)
```

## Block 1 — Representation & vocabulary (not trained)

A circuit is a **token sequence**: an Eulerian path (a walk that covers every
connection once) over a device-pin graph, the same scheme AnalogGenie uses. The
vocabulary is **1005 tokens, byte-identical to upstream**, frozen and guarded by a
regression test so a checkpoint's output never gets decoded into the wrong device names.
Decoding is pure replay of adjacency via union-find. The block also computes the
**structural LNA score** (does it have inductors, RF ports, the right device count —
"is it worth simulating?") and detects **floating subcircuits**.

## Block 2 — Data sources (not trained)

Three deterministic channels feed the fine-tune corpus:

- **The 50-circuit real corpus** — 41 circuits from AnalogGenie's own dataset + 9 real
  ones ingested from open silicon tapeouts and papers, each vetted through a six-gate
  ladder. One circuit becomes many training rows via different Eulerian walks
  ("Eulerian augmentation").
- **148 hand-built archetypes** (`templates.py`) — textbook LNA families (common-source,
  common-gate, resistive-feedback, two-stage, etc.), including four "blind-v1" families
  chosen from *measured failure modes*, never from the target paper.
- **Winners** — designs the pipeline actually built and verified, fed back as more
  imitation data (true SPICE numbers only; critic scores never select training data).

Class tokens `<LNA_NB>` / `<LNA_WB>` tag each row narrowband or wideband. Measured
facts: templates buy structural **yield**, not novelty (removing them keeps ~half the
novelty but drops the screen pass rate from 80% to 36%); the 9 real externals bought
the single largest novelty jump in the program (+52%/+95%) from just 5.8% of the rows,
by **displacing archetype copying** — and it's costed, not free.

## Block 3 — The generator (a trained LLM)

An **11.8M-parameter GPT-style transformer**, pretrained upstream by AnalogGenie on
3,351 circuits and **never trained from scratch here** — every version is a warm-start
fine-tune.

- **Arms:** P1/P2 (early fine-tunes that hit a memorization ceiling), **P5-vN** (the
  adopted lineage: corpus + archetypes + class tokens; v7 adds the 9 externals), and
  OUT-C/OUT-S (outcome conditioning — rejected, and its shuffled control is the finding).
- **The training signal is plain next-token prediction** — supervised imitation. No
  reward, no policy gradient. A "winner" is just more text to predict.
- Runs on a 4 GB GPU; every arm **overfits fast** (best validation loss at epoch 0–1),
  so only the best checkpoint is kept.
- **Adoption is governed by the frozen NDL@256 protocol** and "adopt-only-if-better":
  a new checkpoint replaces the baseline only if it beats the novelty score at
  equal-or-better inductor ratio with every tripwire quiet; ties go to the incumbent;
  costs are reported even on adoptions.

Key measured truths this block records: the memorization ceiling needed *more varied
data*, not a better decoder; a **no-learning random generator beats the trained one on
both headline metrics** but produces nothing that works — so what training buys is DC
viability and gain, which the metrics can't see; and every steering lever tried (winners
feedback, prefix conditioning, re-weighting) raised its target statistic and *lowered*
novelty, because they all point at structure the model already memorized.

## Block 4 — The evaluation ladder (not trained)

A fixed three-rung screen so nothing expensive runs prematurely:

- **L0 — structural/spec screen.** The spec (a YAML file) is the single source of truth;
  the screen **derives** its criteria from the spec's own fields (device budget, max
  inductors, whether inductorless is allowed…). Constraints are either **gated**
  (pass/fail) or **`unsupported`** (declared but unmeasured — e.g. IIP3 today; reported
  as UNMEASURED, never silently passed or failed).
- **L1 — operating point / bias insertion.** Rule-based. R-GATE (always on) gives every
  floating gate a DC path; R-SOURCE/R-DRAIN (opt-in, because they change the circuit)
  fix sources/drains with no return. A monotonic guard ensures no rule ever makes
  conduction worse.
- **L2 — sizing** (Block 5).

Device-budget widenings are always calibrated to the nearest real silicon device count,
never to "the number that closes a gate."

## Block 5 — Sizing & verification (not trained)

A deterministic optimize-and-measure stack that turns a biased topology into a scored,
verified design point. It emits a parameterized SPICE deck where every device value is a
knob; inductors get a **finite Q** (to avoid an ideal-inductor singularity) and MOSFETs
are emitted **multi-finger** (2 µm/finger — because single-finger emission was piling
fake gate resistance onto RF devices and inflating noise by 26–40%). The optimizer
(ZOAF, later CMA-ES) drives ngspice; stability (K/µ) rides along for free and now guards
the acceptance rule so a polish step can't walk a design into instability.

## Block 6 — The label store (not trained)

An append-only JSONL store — "the product" every learned component trains against. Four
tables: L2 sizing outcomes (the expensive prize), L1 operating-point sweeps, the interior
point rows of each sizing run, and the operating points inside each evaluation. Named
snapshots are **pinned by line count + sha256**, so a critic version always sees exactly
the rows it trained on and any later tampering shows up as a hash mismatch.

The load-bearing discipline is **recipe/provenance as a label domain**: rows produced
under a different NF method, device budget, sizing recipe, or bias-rule set are **never
silently pooled** for training, ranking, or noise estimation. Family splits assign whole
clusters of similar circuits to train/val/test as a unit (never row-by-row), because the
corpus is dense with near-duplicates that would leak the answer.

## Block 7 — The critic (a trained model)

A learned pre-SPICE surrogate: predicts the margin vector (S11/S21/Idd, +NF) a topology
would reach after sizing, so search can filter before spending SPICE. Feasibility is
always **computed** from predicted margins, never trained as a boolean.

- Mandatory simple baselines (mean, nearest-neighbor, ridge) before the GNN; the GNN
  ships only when it beats them on the hard splits.
- Three evaluation splits: **family holdout** (primary), **source-shift** (the real
  deployment shift), and **mutant** (the exact off-distribution search generates).
- Known limits, honestly kept: off-distribution decay (a coverage problem, partly
  repaired by more data), and a retired "uncertainty gate" that never fired — replaced
  by a simple "stay near training data" trust region that measurably works.

**Diagnosis heads (7a)** — a *separate* model on the same backbone that says *which
device* is the problem (dominant noise source; conducting/inversion region). They ship
separately because bolting them onto the critic hurt its ranking. Useful for aiming
graph edits, but they win by "removing disasters, not finding wins," and the binding
constraint became the *move repertoire*, not the diagnosis.

**The point surrogate (7b)** — a learned stand-in for one ngspice call, trained on the
66k free interior point rows. Its output isn't a ranking, it's **saved SPICE-minutes**:
a perfect version would skip 82.6% of a cold-start run; v0 captures ~43% of the
warm-start case at zero cost to the answer. Pinned to a pre-cutover data era, so it's a
proof of mechanism, not production.

## Block 8 — Search (not learned policies)

Two "rungs" that spend SPICE more efficiently by consulting the critic:

- **Rung 1 — critic rerank:** score a fresh pool, size only the critic's top-k plus a
  random control (equal budget). Live on dhruva-s, its edge concentrated on NF.
- **Rung 2 — evolutionary search:** a **genetic algorithm** (not RL) over 17 one-edit
  graph mutations, with a trust region guarding the critic's off-distribution weakness.
  Won clearly on dhruva-s; a dead heat where the critic had no coverage.
- **Rung 0 — candidate selection:** *which* pool candidates get sized is itself the
  decisive lever (the match-motif selector). The rule this produced: **a capability
  negative is only as strong as the selector that produced its candidates, and must name
  it.**

## Block 9 — The loops (governance, not learning)

The layer that decides whether a checkpoint or run feeds forward — and the explicit
statement that **none of this is RL**. The two things that could be mistaken for it are
**expert iteration** (winners folded into the next fine-tune as ordinary imitation data)
and the **genetic search** above. `loop.py` holds the numeric tripwires (novelty drop,
family collapse, σ drift, feasible-rate compression) and the headline
**SPICE-minutes-per-feasible-novel-design** curve (967 → 367 → 187 over the first
iterations). `benchmark.py` is the cross-spec scoreboard — with a documented trap: it
rewrites the whole table from whatever specs you pass, so a partial invocation silently
drops rows.

## Block 10 — Integrity mechanisms

The standing disciplines that keep every claim honest under re-measurement, most born
from a specific defect found and fixed in public:

- **The regression quartet(+)** — vocab guard, legacy screen, pipeline yield, reference
  anchor, plus NF/stability/bipolar goldens — all green before and after every work
  package.
- **Frozen, versioned, digest-pinned protocols** (NDL@256 and its reference pools) so a
  number is reproducible against the exact reference it was measured under.
- **Replay fences** — re-evaluating a stored design must reproduce its stored metrics
  from scratch, or the claim isn't trusted.
- **Adopt-only-if-better**, **blind-protocol** enforcement, **device-budget calibration
  to real silicon**, and **explicit user sign-off** for any change to a frozen protocol
  or a spec.

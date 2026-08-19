# Phase 2 — The LNA generation project

**Sources:** `lna/FINDINGS.md` (the measurement log), `lna/JOURNEY.md` (the narrative
history), `lna/HANDOVER-FABLE.md` and `lna/HANDOVER-EXEC.md` (handoffs / open
problems), `lna/WORKLOG.md` (what failed + simulator traps), `lna/STRUCTURE_LOGIC.md`
(how the pipeline works today), `lna/SURVEY-AI-CIRCUIT-DESIGN.md` (nine competing
systems).

## The goal

Take a **low-noise amplifier (LNA)** — the sensitive first-stage amplifier in a radio
receiver — and drive the full pipeline with AI:

> **user spec → AI-generated topology → AI-chosen device sizes → SPICE-verified result**

An LNA is judged on a handful of RF metrics: **noise figure (NF)**, **gain (S21)**,
**input/output match (S11/S22)**, **linearity (IIP3)**, and **power**. A "good" LNA is
meaningless without a target spec, because a 2.4 GHz WiFi front-end and a 1.6 GHz GPS
receiver are genuinely different design problems.

## The starting situation

The survey handed over a blunt reality (from `HANDOVER-FABLE.md`):

- **The measurement side was ready.** ngspice does NF, gain, match, and S-parameters,
  all verified.
- **The targeting side was absent.** The generator (AnalogGenie) produces circuits
  *blindly*. It had:
  - **no way to ask for an LNA** — LNAs are only ~1.2% of its training data (41 of
    3,351 circuits), so blind sampling gives you op-amps and voltage regulators;
  - **no bias network** — the training circuits are textbook schematics that omit
    biasing, so a generated transistor comes out switched *off* and can't be
    simulated for performance;
  - **no device values** — it emits topology only, no widths/lengths/resistances.

Closing that gap — spec, bias, sizing — is the entire project.

## The first win: prefix conditioning

The generator works by emitting a circuit as a sequence of tokens (an "Eulerian path"
walk over the circuit graph). The trick: instead of letting it start from scratch,
**seed it with the first ~12 tokens of a real LNA** and let it continue.

- LNA-shaped output rate: **0% → 40.6%**, with **no retraining**.
- 94% of candidates reach a working simulation; 16 genuinely distinct LNA topologies
  appear per run (not just copies of the seed).

This is a sampling-time trick with a known ceiling — push the prefix longer and the
hit rate rises but the output becomes a verbatim copy of the seed circuit. The tension
between **yield and novelty** is a running theme. (Full detail: `FINDINGS.md` §5.)

## The pipeline, as it exists now

`STRUCTURE_LOGIC.md` is the architecture snapshot. The blocks, roughly in order:

1. **Data** — 41 real LNA circuits from AnalogGenie + 9 ingested from external tapeout
   sources + ~148 hand-written archetype templates.
2. **Generator** — the 11.8M-parameter AnalogGenie GPT, warm-started and fine-tuned on
   the LNA subset, sampled with prefix + class-token conditioning (`<LNA_NB>` narrowband
   / `<LNA_WB>` wideband).
3. **Screen** — scores a raw topology on how LNA-shaped it is (inductors are the
   strongest signal), *before* any sizing.
4. **Bias insertion** — adds the missing biasing so transistors actually conduct. This
   was a distinct, hard sub-project; the model can't do it because the information was
   never in the training data.
5. **Sizing** — chooses device values. A black-box optimizer (CMA-ES, and the ZOAF
   optimizer from the survey) drives ngspice to hit the spec.
6. **Spec + scoring** — a machine-readable spec format (band, NF, gain, match, power,
   topology constraints), and a **frozen benchmark protocol** so improvements are
   measured honestly against a fixed reference.

## How to read the LNA docs

Each of the long docs has a distinct job — this is worth knowing before you dive in:

- **`FINDINGS.md`** — the measurement log, finding by finding, in the order they were
  made. Go here for "what's the exact number and how was it measured?" It's ~10k lines
  because it's the durable evidence base.
- **`JOURNEY.md`** — the same history told as a *story*: each stage gives Context,
  Decision (who decided), Result, and Understanding (how it changed the team's
  thinking). Go here for "how did we get here and why?" Its tail ("current frontier")
  is the best snapshot of open threads.
- **`STRUCTURE_LOGIC.md`** — how the machine works *right now*, block by block. Go here
  for "how does this actually run?" (no history).
- **`HANDOVER-EXEC.md`** — session-to-session executor handoffs: current state, the
  next steps in order, and a running table of ngspice traps.
- **`HANDOVER-FABLE.md`** — the original brief that kicked off Phase 2; still the
  clearest statement of the two core questions (improve generation; define the spec).
- **`WORKLOG.md`** — what was tried and *failed*, plus the simulator traps worth not
  rediscovering.
- **`SURVEY-AI-CIRCUIT-DESIGN.md`** — a deep read of nine competing academic systems
  from primary sources; the intellectual context for the `engineer` line.

## What's solid vs what's open

**Solid / verified:**

- Topology reconstruction is exact (token sequence round-trips to the original netlist
  device-for-device).
- The measurement harness is trustworthy — cross-validated against a second simulation
  engine (ngspice ↔ VACASK harmonic balance agreed to 0.08 dB).
- Bias insertion, sizing, spec format, and the frozen benchmark all exist and run.
- The first NF-gated *feasible* dhruva LNA labels were produced (search + sizing).
- An honest evaluation finding: at matched compute, the CMA-ES sizer beat the ZOAF
  sizer 4/5 vs 1/5 (`FINDINGS.md` §43.2).

**Open problems (from the `JOURNEY.md` frontier and `HANDOVER` docs):**

- **Novelty ceiling.** The fine-tuned generator largely *recites* its ~35 training
  graphs and under-produces inductors. Getting LNA-*like* circuits that aren't
  LNA-*copies* is unsolved. The next planned lever is a template/archetype generator
  (P5 fine-tune).
- **Gain ceiling.** The single-stage reference topped out at ~7 dB gain, below the 12–15
  dB specs need. This has since been addressed: the flagship dhruva-simul point reaches
  ~36 dB fixed gain, with D6 programmability met under an approved mapping.
- **A binding process constraint.** The available 45nm transistor model is *too fast*
  (fT 300–600 GHz), which drives the classic inductively-degenerated match to inductor
  values far too small to build on-chip. This may rule out the canonical LNA topology
  on this process — an important thing to know early.
- **Linearity (IIP3) harness now exists** — two engines (ngspice two-tone transient and
  VACASK harmonic balance) agree to 0.08 dB (FINDINGS §44). D5 was measured and failed as
  a stable physical wall (~21–27 dB short; see FINDINGS §44–§48). `iip3_dbm` remains
  `status: unsupported` in spec objectives until the harness is wired into the benchmark
  as a standard tier-3 rung.
- **Stability is measured but advisory only** — nothing in the objective prevents a
  sizing step from walking a design into instability.

## The blind protocol

From a certain point on, the project targets a specific published LNA (Kanchetla et
al., TMTT 2022, referred to as "dhruva"), but works under a **blind protocol**: the
docs describe only the *allowed spec-number excerpt* from that paper, never its
circuit. Unblinding is explicitly the project owner's decision, not the executor's.
This keeps the "can the AI design this from a spec?" question honest.

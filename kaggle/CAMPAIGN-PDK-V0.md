# CAMPAIGN — cross-PDK-v0 (PRE-REGISTRATION)

**Status: EXPERIMENTAL. Committed BEFORE results (house law).**
Nothing here is frozen protocol. Adoption or freezing of any target, or of any
PDK as a supported process, is a **USER RULING** (memory:
circuit-repro-governance). This file records the campaign's design, budgets,
metrics, and attribution rules *before* any number is read, so no result can be
reverse-justified.

Date pre-registered: 2026-08-27.
Builds on: `kaggle/CAMPAIGN-CAPABILITY-V0.md` (arms, ladder, budgets, verify),
`kaggle/CAMPAIGN-CAPABILITY-V1.md` (the `arch` variant), `lna/pdk/FETCH.md`
(the four adapters + fetched models), `lna/ref/check_pdk_funnel.py` (the
per-PDK funnel golden this campaign rests on).

---

## 1. The question

**Does the funnel's capability generalize across process technologies, or is it
overfit to bptm45?**

Every capability number to date (capability-v0, -v1) was measured on ONE process:
AutoCkt's BPTM 45 nm bulk BSIM4 card. The funnel — bias insertion, emission,
ngspice extraction, CMA-ES sizing — now runs on any PDK selected per-run
(`lna/pdk/` adapters: bptm45, sky130, gf180mcu, ihp_sg13g2). This campaign asks
the two-part question that the single-process campaigns could not:

1. **Per-PDK capability.** On each of four processes, across the graded LNA spec
   ladder, which specs does the loop reach FEASIBLE on, and at what cost?
2. **The overfit signal.** Is the funnel's success *portable*? Two hypotheses,
   distinguished by the shape of the cross-PDK degradation:
   - **Proportional degradation** (the null we can't reject cheaply): every PDK
     loses feasibility roughly uniformly across the funnel — harder processes
     simply size worse, but the *stages* attrite in the same proportions. This is
     what a process-general funnel that is merely fighting physics looks like.
   - **Differential stage-rates** (the overfit tell): a PDK's candidates die at a
     *specific* stage that bptm45's clear — e.g. they bias fine but never size,
     or they parse+screen but never bias — because a heuristic or default tuned
     to bptm45 (a rail assumption, a device-range box, a starting midpoint) does
     not transfer. **A stage that only bptm45 clears is the overfit-to-bptm45
     signal.** This is why deliverable 3 makes every result row carry per-stage
     counts (`stage_rates`): the cross-PDK funnel-rate table falls out of
     `results.jsonl` mechanically, and the differential is read off it directly.

"Feasible" is unchanged from capability-v0: the sized design meets every *gated*
hard constraint (`spec.feasible()` — S11, S21, Idd, and NF via the series-Rs
deck). IIP3 is not gated anywhere (advisory only, as in capability-v0 §6). The
NF series-Rs method is **PDK-agnostic** (verified to run on every PDK by the
funnel golden; not modified for this campaign).

---

## 2. The four PDKs (and why the rail is not a spec change)

| pdk | process | rail (vdd) | device line | OSDI? | notes |
|---|---|---|---|---|---|
| bptm45 | BPTM 45 nm bulk BSIM4 | 1.1 V | `M` (bulk) | no | the incumbent; byte-identical to all prior work |
| sky130 | SkyWater 130 nm | 1.8 V | `X` subckt | no | most battle-tested open PDK w/ ngspice |
| gf180mcu | GF 180 nm MCU | 3.3 V | `X` subckt | no | least RF-capable (180 nm), most headroom |
| ihp_sg13g2 | IHP 130 nm SiGe BiCMOS | 1.5 V | `X` subckt (PSP) | **yes** | real 250 GHz-fT SiGe HBT; PSP MOS needs `.osdi` |

**The supply rail is a property of the PROCESS, not the spec.** Each adapter
carries its own `vdd` (bptm45 1.1, sky130 1.8, gf180 3.3, IHP 1.5); `bias.py`
takes the rail from the adapter and `size.classify_params` fixes `pVDD` to it.
The ladder YAML's `process.vdd` field is **not** consulted for a non-bptm45 run —
running the same spec on gf180mcu does not "relax the spec to 3.3 V", it states
the physical fact that gf180mcu *is* a 3.3 V process. Nothing else in the spec
changes: same NF/S11/S21/Idd targets, same band, same device_budget, same
ladder file. The device-value sizing box (W/L in metres, per-process min L, R/C
ranges) also comes from the adapter (`size.kind_ranges` reads
`adapter.device_ranges` for a non-bptm45 pdk); bptm45's box stays spec-derived
and byte-identical.

### The physical-difficulty confound, stated honestly
Running the **same spec numbers** on **different processes** is deliberate — it
is the only way to isolate funnel portability from spec re-tuning — but it
**confounds** two things this campaign cannot fully separate:

> A spec that bptm45 (45 nm, fT ~ high) reaches and gf180mcu (180 nm, 3.3 V,
> low fT) misses may be missed because **the funnel doesn't transfer** OR because
> **a 180 nm 3.3 V LNA genuinely cannot meet a 45 nm-class NF/gain target**.

We do **not** claim to disentangle these from feasibility rates alone. What the
**stage-rate** instrumentation *can* separate is *where* a PDK loses candidates:
a PDK that biases and sizes fine but just misses the metric bar is losing to
**physics** (the design is real, the target is out of reach for the node); a PDK
whose candidates **never bias** or **never size at all** despite bptm45's
clearing those stages is losing to a **funnel default that didn't transfer**.
The first is a legitimate process limit to report; the second is the overfit
signal. Stating the confound up front is the point of pre-registration: a tier
that comes back all-red on a low-fT process is a **result about that process +
target**, not proof the funnel is broken — and vice-versa.

### Feasibility decided EARLY, not on GPU (the fairness gate)
`lna/ref/check_pdk_funnel.py` already drove one stored corpus topology through
the WHOLE funnel (bias → emission → tiny CMA-ES sizing → extract) on each fetched
PDK and confirmed all four **complete with finite S21/NF and zero model-load
errors** (measured 2026-08-27; IHP's OSDI source-split works). So we know before
spending any quota that no PDK is dead-on-arrival at the mechanism level. If a
future PDK *cannot* conduct/size at all, that is a **finding stated here**, not a
surprise discovered mid-campaign on GPU.

---

## 3. Arms (per PDK)

Same two-arm structure as capability-v0/v1 — same funnel, same sizing engine
(`solve_spec.size_tokens` → CMA-ES/ngspice), same feasibility test, same results
schema, same advisory verify — driven by the one file `kaggle/loop/campaign.py`.
Only the candidate source and the process differ. Each arm runs **per PDK** via
the `--pdk` override (which beats every spec's `pdk:` field, so the SAME 24
ladder YAMLs run on any process with no per-PDK spec copies).

### Arm A — sizing-only null (runs on the box, no GPU, **no LLM**)
`solve_spec.CORPUS` (6 varied known-good LNAs) sized by CMA-ES at a **matched
total eval budget**, on the selected PDK. The null hypothesis, now cross-PDK:
*how far does a fixed stock of good topologies + a competent sizer get on each
spec, on each process, with no topology reasoning?* Launcher:
`PDK=<name> bash kaggle/run_arm_a.sh` (writes to a per-PDK OUT_DIR).

### Arm B-arch — the capability-v1 `arch` variant (runs on Kaggle GPU)
The **`arch`** variant only: v0 arm-B **+ CONCENTRATION (triage → concentrate) +
SELF-DIVERSITY**, and **NO MEMORY** (it is the cold control; no reflect-first
overlay — that is v1's ARM3, out of scope here). Candidates are LLM
proposals+edits via `driver.py`'s own machinery, anchored on the model's own
self-enumerated approaches, triaged cheaply then concentrated on the winner.
Kernel: `kaggle/kernels/loop-gpu/kernel.py` with `RUN_MODE=campaign ARM=arch
PDK=<name>`.

Why arch and not v0 arm-B: capability-v1 established arch as the current best
cold architecture; the cross-PDK question is about *that* loop's portability, so
B-arch is the arm whose per-PDK behavior we want. Using one arm-B variant keeps
the cross-PDK comparison one-dimensional (process), not two (process × variant).

**bptm45 arms already exist — only 3 new PDKs run.** bptm45 arm A is
capability-v0 armA; bptm45 arm B-arch is capability-v1 ARM2 (arch). Both are on
record. This campaign therefore executes **only the 3 foundry PDKs** (sky130,
gf180mcu, ihp_sg13g2) for each arm, and reuses the committed bptm45 rows as the
portability baseline. (A bptm45 re-run is optional run-to-run-noise insurance,
not required.)

---

## 4. Spec ladder, budgets & escalation (identical to capability-v1 arm2)

Same 24 experimental specs in `kaggle/specs-ladder/`, same `ladder.json`, same
tiers (E/M/H), same five difficulty axes. **Unchanged** across PDKs — the whole
point is that the spec numbers do not move.

Budgets and escalation are **identical to capability-v1 ARM2 (arch)**:
- base: `k=3, edit_rounds=2, seeds=2, budget=300, max_tokens=3072`
- escalate (one retry on infeasible at base): `k=5, edit_rounds=4, seeds=3,
  budget=600`
- still infeasible after escalation = **HARD FAILURE**; row recorded, move on.
- arch re-allocates the **same** per-spec total eval budget as v0 (triage at
  `TRIAGE_SEEDS=1 × budget/5`, then concentrate the winner at full `seeds ×
  budget` + edits); `total_evals` records what was actually consumed.
- Arm A matches arm B's total eval budget per spec (`campaign._arm_a_plan`):
  base `(3+2)×2×300 = 3000`, escalation `(5+4)×3×600 = 16200`
  eval-equivalents, spread over the 6 corpus topologies.

---

## 5. Primary metrics (per spec, per arm, **per PDK**)

Every `results.jsonl` row now carries, in addition to capability-v0/v1's fields:
- **`pdk`** — the process the row ran on.
- **`stage_rates`** — `{n_candidates, n_parsed, n_l0, n_bias, n_sized,
  n_feasible}` folded over every candidate the spec walked (arm B: all proposals
  + edits; arch: triage proposals + concentrate + edits; arm A: every
  (corpus-topology, seed)). **This is the cross-PDK funnel-rate table**, and it
  is produced mechanically — no separate analysis pass.

Derived comparisons (computed AFTER the run, never gating):
- **per-PDK feasibility** (feasible specs / 24) — the capability estimate.
- **cross-PDK stage-rate deltas** — for each stage, the fraction of candidates
  that cleared it, per PDK. A stage where a foundry PDK's clear-rate collapses
  relative to bptm45's = the **overfit-to-bptm45 signal** (§1). A stage that
  attrites *proportionally* across PDKs = the funnel transferring, physics
  binding = the null.
- **arm B-arch − arm A** (per PDK) — does topology reasoning help on THAT
  process, or does the corpus + sizer already get there?

---

## 6. Honest-outcome clause

**0-feasible rows and all-red PDKs are results, not failures to suppress.**
Every (spec, arm, PDK) gets a row whatever the outcome; hard failures are
reported with their closest-attempt margins and the closest design is saved.
A PDK tier that comes back all-red is the answer to the per-PDK capability
question. **A stage-rate collapse specific to one PDK is reported as the overfit
finding it is, not smoothed over.** And per §2, if any PDK cannot conduct/size at
all (funnel golden RED), that is recorded here as a finding — but at
pre-registration time all four PDKs pass the funnel golden, so none is expected
to be dead-on-arrival.

### Experimental clause
All 24 ladder specs, the four PDK adapters' device/range/rail choices, and this
campaign's conclusions **inform** — they do not adopt — any target or any
process as "supported". Freezing (a target, a PDK) is a user ruling.

---

## 7. Quota estimate

Only the **3 foundry PDKs** are new (bptm45 arms already exist, §3).

**Arm A (box, no GPU, no quota).** Per PDK: ≤24 specs × (base 3000, +16200 on
escalation) eval-equivalents, serial (≤1 ngspice at a time; the house
concurrency cap). At the funnel golden's observed ~0.05–0.2 s/eval on foundry
decks, a fully-escalated spec is minutes; a PDK ladder is a few box-hours. 3
PDKs = ~1 box-day of wall time, spread with checkpoint-after-every-spec so a stop
loses nothing. **No Kaggle quota.**

**Arm B-arch (Kaggle GPU).** Per PDK this is one capability-v1 ARM2 run with a
different `--pdk`. capability-v1 sized ARM2 at ~1 GPU session (≤ the ~9 h Kaggle
session cap, governed by `WALL_BUDGET_MIN` with clean PARTIAL stop). Budget
3 PDKs ≈ **3 Kaggle GPU sessions** (one per PDK), each self-limiting on wall
budget. The 3 PDK datasets are small (~20 MB / ~1.4 MB / ~2.8 MB) and are
attached **permanently** to the loop-gpu kernel (`dataset_sources`), so no
per-run dataset juggling. If a session times out mid-ladder, the checkpointed
`results.jsonl` + `PARTIAL` marker resume cleanly on relaunch.

**Total new quota: ~3 Kaggle GPU sessions + ~1 box-day.** No installs, no
network beyond the standard bootstrap; the OpenVAF-compiled IHP `.osdi` ship
inside the IHP dataset (no compile step on the worker).

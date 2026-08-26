# CAMPAIGN — capability-v0 (PRE-REGISTRATION)

**Status: EXPERIMENTAL. Committed BEFORE results (house law).**
Nothing in this document — least of all the spec ladder — is frozen protocol.
Adoption or freezing of any target is a **USER RULING** (memory:
circuit-repro-governance). This file exists so the campaign's design,
budgets, metrics, and attribution rules are on record *before* any number is
read, so no result can be reverse-justified.

Date pre-registered: 2026-08-26.

---

## 1. The question

**What can the current reasoning loop already solve?**

The loop (kaggle/loop/driver.py) just ran end-to-end for the first time:
Qwen3-30B proposes SPICE-topology netlists; the deterministic repo funnel
screens (L0), biases (L1), sizes (CMA-ES/ngspice, L2) and measures; one
diagnose→edit round feeds margins back. We want a *capability estimate*: across
a graded ladder of LNA specs, which does the loop reach FEASIBLE on, how much
does that cost, and — crucially — **is the topology proposal doing any work, or
would sizing a fixed stock of known-good topologies get there anyway?**

This is a spec-**capacity** question, not a novelty question (governance,
2026-08-20: engineer goal = spec-capacity). "Feasible" means the sized design
meets every *gated* hard constraint of the spec (spec.feasible()), which under
WP-D1 is S11, S21, Idd **and NF** (NF measured in-loop via the series-Rs deck).
IIP3 is **not** gated anywhere here (see §6).

---

## 2. Arms

Two arms produce candidates for the **same** funnel, the **same** sizing engine
(solve_spec.size_tokens → CMA-ES/ngspice), the **same** feasibility test, the
**same** results schema, designs layout, and advisory verify pass. Only the
**candidate source** differs. Both are driven by `kaggle/loop/campaign.py`
(one file, two `--arm` modes) so the arms cannot diverge in scoring by accident.

### Arm A — sizing-only null (runs on the box, no GPU, **no LLM**)
Candidates are solve_spec's stored **corpus** topologies (`solve_spec.CORPUS`,
6 varied known-good LNAs) sized by CMA-ES at a **matched total eval budget**
(§4). This is the null hypothesis: *how far does a fixed stock of good
topologies + a competent sizer get on each spec, with no topology reasoning at
all?* Launcher: `kaggle/run_arm_a.sh`.

### Arm B — full loop (runs on Kaggle GPU)
Candidates are LLM proposals + edits, via **driver.py's own machinery**
(imported, not forked: ChatClient, consult/propose/edit prompts, run_candidate,
rank_key, save_best, Trajectory). Per spec: `k` proposals, then up to
`edit_rounds` diagnose→edit rounds on the running best. Kernel:
`kaggle/kernels/loop-gpu/kernel.py` with `RUN_MODE=campaign`.

Fair-comparison note: arm A is given the **same total sizing eval budget** arm B
gets, so a difference in outcome is attributable to the candidate source, not to
one arm being allowed more ngspice.

---

## 3. The spec ladder

24 experimental specs in `kaggle/specs-ladder/`, named
`cap-<tier><nn>-<hint>.yaml`, ordered by `ladder.json`. Every spec is
header-commented EXPERIMENTAL / capability-v0. Difficulty is graded across five
axes:

| axis | loose → tight |
|---|---|
| band | 0.9 / 1.575 / 2.4 / 3.5 / 5.8 GHz narrowband + wideband 0.5–3 GHz |
| NF max | 3.5 → 1.5 dB |
| S11 (or band-wide S11_max) | −8 → −15 dB |
| S21 min | 10 → 20 dB |
| Idd max | 15 → 5 mA |

Numbers are round published-practice figures or relaxed/tightened steps off the
three real bring-up specs — **wifi24, ism58, gps-l1** — never read off this
pipeline's behaviour (G0-FAIRNESS calibrations.allowed:never).
`device_budget=[3,16]`, `l_min=0.3nH`, per-band `l_max`, and the whole `sizing:`
block are **copied verbatim** from those specs. Provenance for every number is
in `kaggle/specs-ladder/_gen_ladder.py`.

### Tier definitions

- **Tier E (8) — loose everything; the sanity floor.** If the loop cannot clear
  these, nothing downstream matters. Includes cap-e01 (loosest WiFi:
  NF≤3.5, S11≤−8, S21≥10, Idd≤15) through mild commercial approaches, plus one
  wideband floor (cap-e08).
- **Tier M (8) — realistic commercial-ish.** cap-m01 is **wifi24 exactly**;
  cap-m05 is **ism58 exactly**; the rest interpolate real commercial LNA
  numbers across the bands.
- **Tier H (8) — tight combinations.** Low NF **and** tight match **and** low
  power simultaneously. Includes **one 5.8 GHz-tight** (cap-h05) and **one
  wideband with band-wide S11** (cap-h08, s11_max_db≤−15 across 0.5–3 GHz),
  down to cap-h06 (NF 1.5, S11 −15, S21 18) and cap-h07 (NF 1.5, S21 20,
  Idd 3).

### Band × tier coverage

| band | E | M | H |
|---|---|---|---|
| 0.9 GHz | e03 | m03 | h03 |
| 1.575 GHz | e02, e07 | m02, m07 | h02, h07 |
| 2.4 GHz | e01, e06 | m01, m06 | h01, h06 |
| 3.5 GHz | e04 | m04 | h04 |
| 5.8 GHz | e05 | m05, m08 | h05 |
| wideband 0.5–3 GHz | e08 | — | h08 |

Exactly **two wideband** entries (brief), both reusing the wideband screen
(`allow_inductorless: true`, band-wide `s11_max_db` + `s21_ripple_db`).

---

## 4. Budgets & escalation rule

Per spec, **base** budgets (brief):
`k=3, edit_rounds=2, seeds=2, budget=300, max_tokens=3072`.

On **infeasible at base → ONE escalation**:
`k=5, edit_rounds=4, seeds=3, budget=600`.

Still infeasible after escalation = **HARD FAILURE**; move on (row recorded).

**Matched-budget definition (arm A ↔ arm B).** Arm B's total sizing headroom
per spec is `(k + edit_rounds) × seeds × budget` ngspice-eval-equivalents. Arm A
is given the **same total**, spread over the 6 corpus topologies:
`per_topology_budget = total / (n_topos × seeds)`, each topology sized at
`seeds` seeds. Base total = `(3+2)×2×300 = 3000`; escalation total =
`(5+4)×3×600 = 16200`. (`campaign._arm_a_plan` computes this; the row records
the exact split.)

---

## 5. Primary metrics (per spec, per arm)

Recorded in `results.jsonl` (machine) and `results.md` (human table), both
checkpointed **after every spec** (a session timeout loses nothing):

- **feasible** — yes/no (spec.feasible over gated constraints).
- **iterations-to-first-feasible** — proposals + edits consumed before the
  first feasible candidate (`iters_to_first_feasible`).
- **SPICE evals consumed** — total, and to-first-feasible
  (`total_evals`, `evals_to_first_feasible`). Arm-B eval count is
  `seeds×budget` per sized candidate that reached L2 (size_tokens does not
  self-report `n_evals`; this is the honest upper bound it was allotted).
- **which phase produced the first feasible** — `first_feasible_phase`, e.g.
  `propose#2` vs `edit#1` (arm B) or `corpus#<hash>` (arm A).
- **escalated?**, **best objective**, **per-metric margins** (worst binding),
  **iip3_dbm** (advisory, §6), **stability** (advisory), notes.

### Attribution rule
For a given spec at a matched budget:

- **B feasible where A infeasible** → **topology credit**: the LLM's proposal
  reached something the fixed corpus + sizer could not.
- **both feasible** → **sizing-sufficient**: the spec is met by sizing a
  known-good topology; the proposal is not load-bearing for feasibility here
  (it may still win on objective — noted separately, not as topology credit).
- **neither feasible after escalation** → **hard failure**: out of reach of the
  current loop at this budget. A result, recorded, never a defect to hide.

### Honest-outcome clause
**0-feasible rows are results, not failures to suppress.** Every spec gets a
row whatever the outcome; hard failures are reported with their closest-attempt
margins and the design that got closest is saved. A tier that comes back all-red
is the answer to the capability question, not a bug in the campaign.

### Experimental clause
All 24 ladder specs are EXPERIMENTAL, not frozen protocol. Their numbers,
tiers, and this campaign's conclusions inform — they do not adopt — any target.
Freezing is a user ruling.

---

## 6. IIP3 + measurement wiring

### What was wired (kaggle/loop/verify.py — the final-verdict instrument)
`verify.verify_design(tokens, params, spec)` reconstructs the exact deck the
sizer used (`size.prepared_body(topo)` → the same portnum-1/2 body
`size_tokens` sized) with the design's own `best_params`, then measures:

1. **Two-tone IIP3** via **`size.measure_iip3_tier3(body, params, spec)`** —
   which itself drives **`lna/iip3.py`** at the WP-LIN-validated settings
   (coherent 1 MHz grid, DF 2 MHz, T_WIN 1 µs, tmax 5 ps, DEFAULT_PINS
   −80…−40 dBm, slope-intercept over the SNR/compression-guarded region). The
   entry points used inside it: `iip3.tone_plan`, `iip3.lna_two_tone_body`
   (Thévenin two-tone drive replacing the sp port sources), `iip3.iip3_sweep`,
   `iip3.pav_dbm_to_vemf`. Runtime measured on the box: **~14–22 s per design**
   (6 ngspice transients). We call it **regardless of the spec's iip3
   `status`** — this is the *advisory* path, distinct from the gated tier-3
   path; it never gates.
2. **Band-wide S11 / S21 / S22** and **K / µ / µ_s stability** via
   `extract.run_and_extract(body, params, spec)` over the spec's own sweep,
   plus `extract.stability_verdict` → `unconditional | conditional | unknown`.
3. **S12 reverse isolation** — **already carried** by the S-matrix:
   `run_and_extract`'s metrics dict already contains `s12_db = db|S_1_2|` at f0
   (extract.py line ~394). **No lna/ edit needed.** verify records it as
   `s12_db` and flags `s12_extracted`.

Every measurement is wrapped in try/except with the error captured **verbatim**
into the verdict dict; a verify failure yields `{ok:False, error_verbatim:…}`
and **cannot kill a campaign row**. campaign.py runs verify on each spec's best
design and puts iip3_dbm + stability in the row; the full verdict is nested
under `verify`.

Pilot confirmation (arm A, cap-e01, real ngspice): IIP3 = **−32.13 dBm**
(slope 2.99, 4 pts kept, worst-SNR 27 dB, resid 0.26 dB), OIP3 −16.1 dBm,
stability **unconditional**, in 21.8 s. A real number, produced by the wired
path — exactly what a verdict row should carry.

### Measurement gaps (audit — DOCUMENTED, not built; no lna/ edits)

- **P1dB (1 dB compression).** *Feasible with the existing two-tone transient
  machinery, not built here.* The harness already sweeps available input power
  and reads the fundamental output at each level (`iip3.iip3_sweep` rows carry
  `pin`, `pfund`, `gain`); P1dB is the input power at which `gain` has sagged
  1 dB below its small-signal value — the same rows the IIP3 fit already
  computes (it uses a 0.5 dB compression guard, `iip3.COMP_DB`). Building it
  would mean a single-tone (or same two-tone) power sweep pushed higher than
  DEFAULT_PINS' −40 dBm top until the 1 dB knee, then an interpolation on the
  gain-vs-Pin curve. Cost ≈ the IIP3 sweep again at higher Pin. **Estimate:
  ~6–10 extra ngspice transients per design; ~15–30 s.** Deliberately out of
  scope for v0.
- **S12 reverse isolation.** **Already extracted** (`s12_db`, see above). No
  one-line exposure needed; verify surfaces it directly.
- **Phase noise.** **Infeasible under ngspice** — ngspice has no
  harmonic-balance / PSS/Pnoise analysis, and phase noise is an oscillator
  metric, not an LNA one. Named here for completeness and explicitly excluded.
- **Corners (PVT).** `lna/corners.py` **exists**. Not on the campaign row (adds
  N× the sizing cost). Noted as an **optional final-point add-on**: re-measure a
  chosen feasible design across corners after the campaign picks winners, rather
  than paying it on every ladder rung.

---

## 7. Artefacts & how to run

```
kaggle/CAMPAIGN-CAPABILITY-V0.md      this file (pre-registration)
kaggle/specs-ladder/                   24 cap-*.yaml + ladder.json (+ _gen_ladder.py)
kaggle/loop/verify.py                  advisory final-verdict instrument
kaggle/loop/campaign.py                arm-A / arm-B ladder runner (shared code paths)
kaggle/run_arm_a.sh                    box-side arm-A launcher (OUT_DIR env; <=6 ngspice)
kaggle/kernels/loop-gpu/kernel.py      RUN_MODE=campaign -> arm-B ladder
```

Local dry-run (no server, no ngspice):
```
python kaggle/loop/campaign.py --arm B --dry-run --no-sim \
    --ladder kaggle/specs-ladder/ladder.json --max-specs 2
```
Arm A on the box:
```
OUT_DIR=/path/to/out bash kaggle/run_arm_a.sh
```
Arm B on Kaggle: push loop-gpu with `RUN_MODE=campaign` (and
`WALL_BUDGET_MIN`, default 500). Output lands in `/kaggle/working/campaign/`.

Time management: campaign.py reads `WALL_BUDGET_MIN` (default 500) and, using a
running mean of per-spec wall time, stops cleanly before a spec that would not
fit, dropping a `PARTIAL` marker. Every spec's row + best design + proposal
provenance + trajectory pointer is checkpointed the moment it completes.

# 21 — COLDSPEC: fresh-spec cold generation, zero topology hints

**Status:** PRE-REGISTERED experiment (this half committed BEFORE any result,
house law). **Branch:** `coldspec-run` off `main` @ 5d55f0a (worktree, no merge,
no push). **Authored:** 2026-08-21, at user request (overnight experiment).
**Target:** `lna/specs/ism58.yaml` — a 5.8 GHz ISM-band narrowband LNA, a band
**no prior target touches**, still inside the BPTM-45nm credible range.

This is a **G4 fresh-transfer** run in the sense of `engineer/G0-FAIRNESS.md §1`:
no stage of the main line was tuned against 5.8 GHz. The spec is EXPERIMENTAL
and NOT frozen — per governance, spec adoption/freezing is a user ruling.

---

## 1. The question

**Can the MAIN-branch pipeline reach a fresh spec it has never seen, with ZERO
topology hints — cold, no external assistance beyond the harness itself?**

"Cold" is defined operationally by the nudge rules in §2. The honest space of
answers includes **0 feasible**, which is a publishable measurement of the
pipeline's unaided transfer reach, not a failure to hide (§5).

---

## 2. The nudge rules (user directive, binding — the point of the experiment)

**ALLOWED (the harness):**
- The fine-tuned generator sampled with its **trained class token `<LNA_NB>`
  only** (`lna/finetune.py --arm p5 --do sample --class nb`, `bins=None` — i.e.
  the plain class-token prefix, the UNCONDITIONED arm, no WP-OUTCOME bins).
- The spec-derived **L0 structural screen** (`spec.structural_screen` /
  `screen.py`).
- The rule-based **L1 bias insertion** (`bias.py`).
- **CMA-ES sizing** (`size.py`).
- All **measurement** (ngspice extract, corners, NF/S11/S21/Idd).

**FORBIDDEN (hints):**
- **Prefix-seeding** from any real/corpus circuit (`generate.py --prefix lna`
  and any corpus-opening seed — OUT).
- The **match-motif selector** or any hand-chosen structural filter beyond the
  spec-derived screen.
- Any **hand edit** of any topology.
- Any **new template / archetype**.
- Candidate selection for sizing = **top-k by the spec-derived L0 screen score
  plus a small random control group — nothing else.**

**Ledger:** a contamination ledger (per `engineer/G0-FAIRNESS.md §3` schema) is
emitted in §6 declaring exactly what transferred in.

---

## 3. Protocol (pre-registered)

1. **Goldens GREEN first** — `python lna/ref/check_ref.py` must exit 0 before and
   after the run.
2. **Sample** N=256 topologies from the **adopted P5 generator lineage**
   (`ft_p5v7_v2.pth`, the P5-v7 ADOPTED baseline — `lna/HANDOVER-EXEC.md`
   "P5-v7 ADOPTED", nb NDL@256=79), class token `<LNA_NB>`, `bins=None`, on CPU,
   **deterministic seed 1337**. No prefix seed.
3. **L0 screen** every sample through `spec.structural_screen(ism58)` /
   `screen.py`.
4. **L1 bias** the screen-passing topologies (`bias.py`) — default-valued sim to
   confirm they conduct.
5. **Select for sizing:** top-10 by L0 screen score + **3 random-control picks**
   drawn from the screen-passing remainder (deterministic RNG, seed 1337).
   Nothing else — no motif selector.
6. **Size** each selected candidate with CMA-ES, **≤ 400 evals each**,
   deterministic seeds, ≤ 8 concurrent ngspice at any time.
7. **Record** in §"Results" of THIS doc — NOT in FINDINGS.md (a parallel agent
   appends there tonight; avoid collisions).

**Primary metric** (per the 2026-08-20 goal ruling): **SPICE-minutes / evals to
first feasible.** If 0 feasible: report the honest per-metric miss distances of
the best candidate on each of {NF, S11, S21, Idd}.

**Reported yield rungs:** LNA-shaped %, screen-pass %, L1-conducting %, sized
outcome per candidate (including the random controls), best margins vs spec per
metric.

---

## 4. Determinism

Seed 1337 throughout (sampling, random-control selection, CMA-ES). CPU sampling
(slower, fine). Parallel ngspice inside sizing capped at 8 concurrent (shared
box, two lighter agents alongside tonight).

---

## 5. Honest-outcome statement

**0 feasible is a valid, publishable answer.** The experiment measures the
pipeline's UNAIDED transfer reach to a never-seen band with no topology hints.
A miss — and its per-metric miss distances — is exactly as informative as a hit.
Nothing about this protocol is arranged to make a hit more likely than the cold
pipeline actually delivers. No result is to be suppressed, softened, or moved
out of this doc.

---

## 6. Results

### 6.0 Goldens (gate)

`python lna/ref/check_ref.py` → **GREEN** (exit 0), both before the run and at
close. Three reference decks (ref24_cg / ref24_csdeg / stage-A anchor) all pass
stability + acceptance gates. This is the one simulator invocation that
succeeded tonight (see §6.1).

### 6.1 OUTCOME: run BLOCKED — generator not runnable on this host

**The cold-generation run did not execute.** The mandatory first step of the
protocol (§3.2, sample N=256 from the adopted P5 generator) is **impossible on
this RHEL box as provisioned**, for two independent reasons, either of which is
sufficient:

1. **PyTorch is not installed** in the contained conda env (`.env/envs/cr`):
   `import torch` → `ModuleNotFoundError: No module named 'torch'`. The
   generation/torch side is explicitly **unported** on this host (memory:
   circuit-repro-rhel-setup — "baked Windows python paths remain in
   lna/search.py, evolve.py, critic_gnn.py (generation/torch side, unported)").

2. **No generator checkpoint exists on the box.** Neither the AnalogGenie base
   `Pretrain.pth` nor ANY fine-tuned checkpoint (`ft_p5*.pth`, incl. the adopted
   `ft_p5v7_v2.pth`) is present anywhere reachable. They are gitignored
   (`.gitignore:41  lna/out/*.pth`) and were never materialized in this
   checkout. The `lna/out/ft_p5*` directories hold only prior `meta.json` files
   — no `seq*.txt`, no weights. Exhaustive search (`find / -iname 'ft_p5*.pth'
   -o -iname 'Pretrain.pth'`, excluding `.env`) returned nothing.

Confirmation command (the exact ALLOWED nudge sample invocation):
```
$ python lna/finetune.py --arm p5 --do sample --class nb --device cpu --n 4 ...
  File ".../lna/finetune.py", line 44, in <module>
    import torch
ModuleNotFoundError: No module named 'torch'
```

**Why no workaround was taken.** Resolving either blocker would require
installing PyTorch into the env and/or downloading a ~198 MB checkpoint from
outside — both of which violate the standing containment rules (no system
installs; stay inside the two checkouts + `.env/`; memory:
circuit-repro-rhel-setup) AND the STRICT-CONTAINMENT directive for this job
(only `/home/dpatni/circuit-repro` and this job's `tmp`; the Xilinx git has no
HTTPS support). Per house practice, this is **logged, not guessed around**: no
topology was hand-authored, no corpus circuit was substituted for the
generator, and no synthetic "sample" was fabricated to fill the pipeline. Doing
any of those would itself be a nudge-rule violation (§2 FORBIDDEN) and would
make the result invalid under G0-FAIRNESS.

### 6.2 What IS established

- The **fresh spec** `ism58.yaml` is authored, schema-valid, and loads cleanly
  through `spec.py` (narrowband, f0=5.8 GHz, 5 constraints incl. `iip3_dbm`
  status:unsupported, 3 objectives, max_inductors=3, allow_inductorless=false).
  It is a genuine G4 fresh target: no main-line tuning has touched 5.8 GHz.
- The **spec-derived L0 screen** and downstream **CPU** stages (screen.py,
  bias.py, size.py, ngspice extract) are all present and runnable — the
  simulator side works (goldens GREEN). The ONLY missing link is the neural
  generator that produces the candidate topologies to feed them.
- **Rung-by-rung yield: N/A** (no candidates were generated). LNA-shaped %,
  screen-pass %, L1-conducting %, sized outcomes, evals-to-first-feasible, and
  per-metric miss distances are all **undefined for this run** because the run
  did not start.

### 6.3 What a re-run needs (for the user / a GPU-capable host)

To execute the pre-registered protocol unchanged, one of:
- run on the host where `Pretrain.pth` + the adopted `ft_p5v7_v2.pth` and a
  torch install live (the generation side was developed off-box), OR
- provision torch into `.env` and fetch the two checkpoints — a decision that is
  a user ruling, not an autonomous action under the containment rules.

Everything downstream of "sample" is ready and the pre-registration above is
frozen, so a re-run is a drop-in once the generator is reachable.

---

## 7. Contamination ledger

Per `engineer/G0-FAIRNESS.md §3`. This ledger describes what WOULD transfer in
under the pre-registered protocol; it is emitted here for completeness. The
`present` fields reflect that **no run occurred** (nothing was actually sampled,
selected, or sized), so no forbidden channel was exercised.

```yaml
contamination_ledger:
  run_id: "ism58_coldnb_s1337"
  task: "ism58"
  date: "2026-08-21"
  status: "NOT_EXECUTED — generator unavailable on host (no torch, no checkpoint)"
  intended_generator: "ft_p5v7_v2.pth (P5-v7 ADOPTED lineage, class token <LNA_NB>, bins=None)"
  transferred_in:
    harness_code:
      allowed: always
      description: "spec.py, screen.py, bias.py, size.py, extract.py, corners.py — the evaluation/measurement contract"
    playbook:
      allowed: declared
      present: false      # playbook OUT — no playbook store consulted
      declared: false
    seeds:
      allowed: never
      present: false      # generic seed 1337 only; NO task-specific seed selection
      note: "sampling/selection/CMA-ES seeds are the generic 1337; no seed chosen to land on 5.8 GHz"
    selectors:
      allowed: never
      present: false      # NO motif/archetype selector; candidate selection = top-k L0 score + random control ONLY
      note: "match-motif selector and any hand structural filter are FORBIDDEN by the nudge rules; not used"
    calibrations:
      allowed: never
      present: false      # spec numbers derived from published 5-6 GHz practice, NOT from pipeline behaviour
      note: "budget/thresholds from real-standard practice; no calibration read off this task's convergence"
  prefix_seeding:
    allowed: never        # FORBIDDEN by nudge rules (§2)
    present: false        # generator would be sampled from the <LNA_NB> class token, VSS only — no corpus prefix
  hand_edits:
    allowed: never
    present: false        # no topology hand-authored or edited
  new_templates:
    allowed: never
    present: false        # no new template/archetype added
```

Every `allowed: never` field has `present: false`. Under G0-FAIRNESS §3 rule 6,
the run would be VALID had it executed. It did not execute (§6.1).

---

## 8. Results — EXECUTED run (2026-08-21)

The two blockers of §6.1 were resolved by the user (out-of-band, not by this
agent): PyTorch was installed into the contained env (`torch 2.13.0+cpu`, via
`env.sh` LD_LIBRARY_PATH), and both checkpoints were transferred into the MAIN
checkout — `AnalogGenie/repo/Pretrain.pth` (198,300,529 B) and the adopted
`lna/out/ft_p5v7_v2.pth` (198,311,075 B). Vocab guard green; a 2-sequence
`<LNA_NB>` class-token sample verified before the full run. **The §1-§5
pre-registration above is frozen and was run unchanged.** The §6.1 BLOCKED
record is retained intact; this section reports the actual execution.

Worktree `coldspec-exec` off `main` @ `c9458f0`. Checkpoints/deps are untracked
and live only in the MAIN checkout; `LNA_DEPS_ROOT=/home/dpatni/circuit-repro`
resolved `Pretrain.pth`, and the sampler was pointed at the absolute ckpt path
`/home/dpatni/circuit-repro/lna/out/ft_p5v7_v2.pth` (no symlink junction was
needed).

### 8.0 Goldens (gate)

`python lna/ref/check_ref.py` → **GREEN** (exit 0) **before** and **after** the
run. All three reference decks (ref24_cg / ref24_csdeg / stage-A anchor) pass
stability + acceptance gates.

### 8.1 OUTCOME (one line)

**HIT — the cold pipeline reached ism58 (5.8 GHz, never seen) with zero topology
hints: 2 of 13 sized candidates are feasible, and the FIRST feasible is a random
control (seq0000), sized in 216 SPICE evals / ~2.3 s.**

### 8.2 Rung-by-rung yield

Sample: N=256, class token `<LNA_NB>`, `bins=None`, CPU, seed 1337, from the
adopted `ft_p5v7_v2.pth`. No prefix seed, no motif selector, no hand edits.

| rung                                   | count | of prior | notes |
|----------------------------------------|-------|----------|-------|
| generated (N)                          | 256   | —        | all terminated |
| parseable topologies                   | 256   | 100.0%   | every sample parsed as a graph |
| LNA-shaped (legacy `lna_score` ≥ 4)    | 215   | 84.0%    | coarse structural sanity |
| L0 screen PASS (spec `ism58`)          | 96    | 37.5%    | `spec.structural_screen`, WL-distinct |
| L1-conducting (bias insert, two-port)  | 96    | 100.0%   | every screen-passer biased & conducts |
| selected for sizing                    | 13    | —        | top-10 by L0 score + 3 random controls |
| **sized FEASIBLE**                     | **2** | 15.4% of sized | seq0000 (control), seq0032 (top) |

(The 96 screen-passers were WL-distinct; no further dedup dropped candidates.)

### 8.3 Selection

"L0 screen score" = number of `structural_screen` criteria met (all 13 selected
are full passers, 7/7), tie-broken deterministically by the legacy 0-5
`lna_score` (all 5/5), then n_devices, then seq name — a **purely
spec-derived / structural** ordering with **no learned selector** (the critic /
GNN `rank_pool` is FORBIDDEN by §2 and was NOT used). Random controls: 3 drawn
by `random.Random(1337).sample` from the screen-passing remainder (seq0000,
seq0004, seq0018).

### 8.4 Sized-candidate table (13 = 10 top + 3 control)

Protocol per candidate: `size.size_topology(seed=1, inductor_q=12, **SCAN_BUDGET)`
then bounded `size.polish(budget=POLISH_BUDGET)` — the established arm-comparison
sizing protocol from `search.py` (see §8.7 deviation on "CMA-ES"). NF gated ON
(`_nf_gate_default()=True`). S11 feasibility is judged on `s11_db` **@f0** per
the harness contract (`spec.feasible`); band-max S11 is shown in brackets.

| seq         | role    | how            | feas | viol   | S11@f0 [bandmax] | S21    | Idd    | NF    | evals | s |
|-------------|---------|----------------|------|--------|------------------|--------|--------|-------|-------|---|
| seq0000.txt | control | bounded-polish | **T**| 0.000  | -14.14 [-12.99]  | 15.59  |  6.43  | 1.19  | 216   | 2 |
| seq0032.txt | top     | scan           | **T**| 0.000  | -12.25 [ -8.86]  | 19.53  |  8.57  | 1.23  | 264   | 3 |
| seq0004.txt | control | bounded-polish | F    | 0.086  |  -9.82 [ -9.76]  | 11.61  | 10.35  | 1.09  | 224   | 2 |
| seq0018.txt | control | bounded-polish | F    | 0.261  |  ~-8.6 [ -8.55]  | 10.45  |  8.75  | 1.31  | 240   | 3 |
| seq0035.txt | top     | bounded-polish | F    | 0.844  |  -7.37 [ -7.37]  |  4.80  |  2.89  | 3.80  | 280   | 4 |
| seq0120.txt | top     | bounded-polish | F    | 2.288  |  -6.68           | -0.27  |  3.70  | 6.81  | 264   | 3 |
| seq0007.txt | top     | scan           | F    | 2.432  | -14.30           | -6.59  |  1.53  | 6.59  | 272   | 4 |
| seq0099.txt | top     | bounded-polish | F    | 3.095  | -11.56           | -3.07  |  5.12  | 9.94  | 272   | 4 |
| seq0043.txt | top     | bounded-polish | F    | 3.404  |  -0.56           |  6.45  |  4.52  |10.49  | 272   | 4 |
| seq0193.txt | top     | scan           | F    |102.419 |  -2.03           |-600.00 |  2.33  |180.70 | 272   | 4 |
| seq0214.txt | top     | scan           | F    |102.702 |  -1.47           |-600.00 |  1.04  |181.49 | 264   | 3 |
| seq0244.txt | top     | bounded-polish | F    |104.295 |  -0.25           |-600.00 | 10.02  |186.61 | 272   | 4 |
| seq0228.txt | top     | bounded-polish | F    |107.184 |  -1.03           |-600.00 |  0.00  |197.01 | 272   | 4 |

The four `S21=-600` rows are the sizer's sentinel for a non-conducting /
open-loop small-signal solution (no gain path found at the sized point) — honest
hard misses, not simulator crashes.

### 8.5 Feasible-candidate margins vs spec (positive = met with slack)

**seq0000.txt** (random control; 6 devices, 2 inductors — a single-NMOS
inductively-degenerated stage, L1 gate/degen + L2 load tank, C1/C2/C3 coupling):
- S11 @f0  = -14.14 dB   (≤ -10)   margin **+4.14 dB**  (band-max -12.99, holds edge-to-edge)
- S21      =  15.59 dB   (≥ 12)    margin **+3.59 dB**
- NF       =   1.19 dB   (≤ 3.5)   margin **+2.31 dB**
- Idd      =   6.43 mA   (≤ 10)    margin **+3.57 mA**
- 216 evals, 2.3 s. **Feasible on ALL four hard constraints, edge-to-edge.**

**seq0032.txt** (top-10 pick; 12 devices, 2 inductors — 2-stage cascode, NM1/NM2
stacked + NM3 output, L1 source degen, L2 load):
- S11 @f0  = -12.25 dB   (≤ -10)   margin **+2.25 dB**   **[band-max -8.86 dB > -10]**
- S21      =  19.53 dB   (≥ 12)    margin **+7.53 dB**
- NF       =   1.23 dB   (≤ 3.5)   margin **+2.27 dB**
- Idd      =   8.57 mA   (≤ 10)    margin **+1.43 mA**
- 264 evals, 3.0 s. **Feasible under the harness's f0-referred S11 contract, but
  its band-max S11 (-8.86 dB) does NOT hold ≤ -10 across the full 150 MHz band** —
  recorded, not smoothed. Under an edge-to-edge S11 gate this candidate would
  miss S11 by 1.14 dB; seq0000 passes both f0 and band-max.

### 8.6 Primary metric — to first feasible

Per the 2026-08-20 goal ruling (§3), the primary metric is **SPICE-minutes /
evals to first feasible.**

- **First feasible = seq0000 (a random control): 216 SPICE evals, ~2.3 s
  (~0.04 SPICE-minutes) for that single candidate's full sizing.**
- Second feasible (seq0032, a top-10 pick): 264 evals, ~3.0 s.
- Every one of the 13 sizings stayed **well under the ≤400-eval budget** (range
  216–280 evals; the scan+polish protocol tops out near 272).
- Sizing spent **3,384 SPICE evals total** across all 13 candidates; wall time
  **~0.1 min** at 8-way concurrency (≤ 8 ngspice enforced by an 8-worker
  process pool — each ZOAF sizing invokes ngspice serially, so ≤ 8 concurrent).
- Honest-miss context (per §3/§5, reported even though feasibles exist): the
  best INFEASIBLE candidate is seq0004 (control), viol 0.086 — misses only by
  S11 +0.018, S21 +0.033, Idd +0.035 (all sub-tenth normalized), i.e. a third
  near-feasible right at the boundary.

### 8.7 Deviations from the frozen protocol (recorded, never smoothed)

1. **"CMA-ES" sizer.** §2/§3.6 name "CMA-ES sizing … ≤ 400 evals each." The
   harness's actual sizer on this box is **ZOAF** (`size.run_zoaf`), driven by
   the established `search.SCAN_BUDGET` (n_candidates=4, sgd_iters=5,
   cgd_iters=1) + bounded `polish(budget=60)` — the exact arm-comparison
   protocol `_attrib_size.py` uses. No CMA-ES implementation is wired in this
   repo. The **≤ 400-eval budget was honored** (observed 216–280 evals/candidate)
   and the "each candidate, equal budget, deterministic seed" intent is met; the
   optimizer identity differs from the pre-reg's wording.
2. **Sampling knobs.** The ALLOWED sampler `_attrib_sample.py` defaults to
   `max_tokens=256`, `temperature=0.7`; the pre-reg (§3.2) fixes seed=1337,
   class `<LNA_NB>`, `bins=None`, CPU, N=256 but does not specify temperature or
   max-tokens. The tool defaults (T=0.7, max_tokens=256) were used and are
   recorded here as the gap. Batch=32 (finetune.sample default); seed 1337
   applied once before batched generation.
3. **"L0 screen score" made concrete.** `structural_screen` returns a boolean;
   the pre-reg says "top-k by L0 screen score." Operationalized as #criteria met
   (all selected = 7/7) with a deterministic structural tiebreak (§8.3). No
   learned selector — consistent with §2 FORBIDDEN.
4. **Branch base.** Pre-reg header names base `5d55f0a`; the executed worktree
   branched from `main @ c9458f0` (the current MAIN head per the job directive).
   The §1-§5 protocol text is unchanged.

### 8.8 Contamination ledger — EXECUTED

```yaml
contamination_ledger:
  run_id: "ism58_coldnb_s1337"
  task: "ism58"
  date: "2026-08-21"
  status: "EXECUTED — generator ran; 2/13 sized candidates feasible"
  generator: "ft_p5v7_v2.pth (P5-v7 ADOPTED lineage, class token <LNA_NB>, bins=None), torch 2.13.0+cpu, CPU, seed 1337"
  transferred_in:
    checkpoints:
      allowed: always            # the adopted generator weights ARE the harness
      present: true
      what: "AnalogGenie/repo/Pretrain.pth (198,300,529 B) + lna/out/ft_p5v7_v2.pth (198,311,075 B), transferred into MAIN by the user out-of-band; untracked/gitignored"
    harness_code:
      allowed: always
      description: "spec.py, screen.py, bias.py, size.py, search.py, extract.py — the evaluation/measurement contract, unchanged"
    playbook:
      allowed: declared
      present: false             # no playbook store consulted
      declared: false
    seeds:
      allowed: never
      present: false             # generic seed 1337 only (sampling/selection/sizing); no seed chosen to land on 5.8 GHz
    selectors:
      allowed: never
      present: false             # NO motif/archetype/critic selector; selection = spec-derived L0 score + random control ONLY (§8.3)
    calibrations:
      allowed: never
      present: false             # spec numbers from published 5-6 GHz practice; nothing read off this run's convergence
  prefix_seeding:
    allowed: never
    present: false               # sampled from the <LNA_NB> class token + VSS only; no corpus prefix
  hand_edits:
    allowed: never
    present: false               # no topology hand-authored or edited; the two feasibles are raw generator output + bias/sizing
  new_templates:
    allowed: never
    present: false               # no new template/archetype
```

Every `allowed: never` field has `present: false`. Under G0-FAIRNESS §3 rule 6,
**this executed run is VALID.** The only `present: true` transfers are the
generator weights (the harness itself, `allowed: always`) and the unchanged
harness/evaluation code.

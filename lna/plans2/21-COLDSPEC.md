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

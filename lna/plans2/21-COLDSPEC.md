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

*(Pre-registration commit: this section is intentionally empty here — results
are added in the immediately following commit, per the pre-reg-before-results
house law. The protocol above, §1-5, is frozen at this commit.)*

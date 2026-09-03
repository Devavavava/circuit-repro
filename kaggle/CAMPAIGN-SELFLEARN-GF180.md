# CAMPAIGN — selflearn-gf180-v0 (PRE-REGISTRATION)

**Status: EXPERIMENTAL. Committed BEFORE results (house law).**
Nothing here is frozen protocol. Adoption or freezing of any target is a **USER
RULING** (memory: circuit-repro-governance). This file records the legs, the
reflect corpus, budgets, metrics, and attribution rules *before* any number is
read, so no result can be reverse-justified.

Date pre-registered: 2026-09-04. Commissioned by user 2026-09-03 ("step 1" GO,
including the reflect-corpus ruling). Builds on
`kaggle/CAMPAIGN-CAPABILITY-V1.md` (arm definitions) and
`kaggle/campaigns/cross-pdk-v0/README.md` (comparator records).

---

## 1. The question

**Does the self-learning channel generalize off bptm45?**

capability-v1 (bptm45) measured selflearn 12/24 vs the arch cold control 11/24 —
directionally positive, mechanistically consistent, but WITHIN the ±2 noise
floor; the standing verdict was "repeat / larger ladder decides." This campaign
is the repeat, in an independent context chosen for headroom in both directions:

- **gf180mcu**, environment healthy (`check_pdk_wsweep` GREEN since the
  inductor/VB/binning fixes), null **0/24 but ALIVE** at the boundary (rides the
  Idd cap, S21 ~ −2 dB), arch **2/24** — the program's first topology credit
  (cap-e01-wifi, cap-m06-wifi; era-binfix-9df8b95a).

If self-authored memory helps anywhere, a process where the corpus priors fail
and the model has already demonstrated process-appropriate invention is where
it should show. If it does not beat the cold control here, that is the answer
(honest-outcome clause), and the bptm45 +1 stays unproven.

---

## 2. Legs

Both legs run on Kaggle GPU (`loop-gpu`, `RUN_MODE=campaign`, `PDK=gf180mcu` →
`campaign.py --pdk gf180mcu`), same 24-spec ladder
(`kaggle/specs-ladder/ladder.json`), same funnel/sizing/feasibility/results
schema, same budgets (§4), same NEW code era (§5), chained in one session plan.

### LEG1 — "arch-rerun" (`--variant arch`)

The cold control re-measured in-era: concentration + self-diversity, **no
memory**. Purpose: (a) the in-era control for the learning claim; (b) the first
gf180 run-to-run noise datapoint (LEG1 vs era-binfix arch 2/24 — same
configuration, different era/session).

### LEG2 — "selflearn" (`--variant selflearn`)

LEG1 + REFLECT-FIRST, exactly the capability-v1 ARM3 mechanism (session-local
overlay, `author:system`, verbatim-evidence admission, cap 12, overlay
consulted additively next to the governed playbook).

**Reflect corpus (RULED, user 2026-09-03): the system's own gf180 records
ONLY —**

```
kaggle/campaigns/cross-pdk-v0/era-binfix-9df8b95a/armb-arch-gf180mcu/
    (results.jsonl + trajectory/*.jsonl + designs/ — the 2/24 arch record)
kaggle/campaigns/cross-pdk-v0/era-fixed-0b4b497e/arma-gf180mcu/
    (results.jsonl + designs/ — the 0/24 null record; no trajectory dir,
     load_corpus tolerates that)
```

No bptm45 records, no other PDKs, no governed-playbook edits. **Mechanical
prerequisite:** `reflect.py` accepts a repeated `--v0-dir` (additive
concatenation inside `load_corpus`; content-neutral — no prompt text changes;
the verbatim-evidence admission check runs against the concatenated corpus
blob). Both dirs are committed, so any clone reproduces the corpus.

### Fallback (quota; user ruling to invoke)

If GPU quota cannot cover both legs, LEG1 is dropped and LEG2 compares against
the era-binfix arch 2/24 under the era-compatibility argument (§5). This
weakens the learning claim (cross-era comparison, no in-era noise datapoint)
and is recorded as such.

---

## 3. No-injected-content clause (BINDING, unchanged)

> No human- or Claude-authored domain guidance may enter any arm. The system
> reads its OWN results, identifies its OWN shortcomings, writes its OWN
> lessons. Humans/Claude only change architecture and commission experiments.
> Prompts/scaffolding must be content-neutral (structure, not circuit
> knowledge).

The only code deltas this campaign introduces beyond capability-v1 machinery
are (a) the repeated `--v0-dir` corpus concatenation and (b) the sim-health
observability fields of the new era (§5) — both structural, neither carrying
circuit knowledge. All prompts remain the capability-v1 prompts, auditable
verbatim (`reflect.py --print-prompt`, `DIVERSITY_*` in `campaign.py`).

---

## 4. Budgets & escalation (UNCHANGED from v0/v1)

Per spec, base: `k=3, edit_rounds=2, seeds=2, budget=300, max_tokens=3072`; one
escalation on infeasible: `k=5, edit_rounds=4, seeds=3, budget=600`; still
infeasible = hard failure, move on. Per-spec total eval budget identical to
every prior arm (base 3000 / escalation 16200 eval-equivalents). Diversity and
reflect calls are LLM calls, not ngspice evals. `WALL_BUDGET_MIN=500` per leg;
reflect cap 12 entries. Quota estimate ~4–5 h/leg (era-binfix gf180 arch leg
completed all 24 specs inside wall); both legs ≈ 8–10 h of the 30 h/week.

---

## 5. Code era & comparability

Both legs run on the post-`obs-simhealth` era (merge commit recorded here at
launch: `era-obsfix-<commit>`). `obs-simhealth` is **additive observability
only** — `n_evals` / `n_sim_fail` counters, one verbatim ngspice error line on
failing runs, a sim-health stage-rate column — with behavior-identity
demonstrated by the full golden suite at merge. Era-binfix comparators
therefore remain valid **comparisons** (never pooled — label-domain rule,
`kaggle/PLAYBOOK.md`): the sizing/selection/scoring path is
behavior-identical by construction. New-era rows carry sim-health fields;
no comparison in §6 reads them. Rows are tagged pdk+host+era; artifacts
archive under `kaggle/campaigns/selflearn-gf180-v0/era-<tag>-<commit>/leg{1,2}/`.

---

## 6. Metrics & attribution

Same per-spec `results.jsonl` schema as capability-v1 (variant, triage,
consult_hits / overlay_hits) + LEG2's `reflect-summary.json` and
`system-playbook/` overlay, all committed after the run.

Primary comparisons, fixed now:

- **LEG2 − LEG1 (solved counts, per-spec deltas)** → **the learning claim.**
  LEG1 is the in-era cold control; a positive delta is attributable to the
  system-authored gf180 memory. To count as signal it must exceed the noise
  evidence available (bptm45 noise floor ±2; LEG1-vs-era-binfix-arch adds the
  first gf180 datapoint).
- **LEG1 vs era-binfix arch (2/24)** → gf180 run-to-run noise datapoint
  (cross-era, comparison only).
- **Topology credit** (vs the gf180 null 0/24, era-fixed): trivially, every
  solve is a B-solves-where-A-fails cell on this PDK; therefore the
  informative attribution here is vs the cold control, plus per-cell overlap:
  which solved cells repeat arch's two (cap-e01-wifi, cap-m06-wifi) and which
  are new.
- **Advisory (never gates):** k_min stability, verify-pass metrics, sim-health
  rates (new era) — reported, not scored. A K≥1 gate remains a separate
  pre-registered ladder version if ever ruled.

### Honest-outcome clause (BINDING, unchanged)

0-feasible rows are results. Every spec gets a row; hard failures report
closest-attempt margins with the closest design saved. LEG2 failing to beat
LEG1 is the answer to the question, not a bug — reported as measured.

### Experimental clause

The 24 ladder specs remain EXPERIMENTAL, not frozen. This campaign informs —
it does not adopt — any target or protocol change. Adoption of the selflearn
variant anywhere is a user ruling.

---

## 7. Prerequisites (gate the launch, in order)

1. `obs-simhealth` merged to local main, full golden suite green before/after
   (the §5 era argument depends on this).
2. `reflect.py` repeated `--v0-dir` landed (additive); local dry-run against
   BOTH corpus dirs recorded (`--dry-run` + `--print-prompt` outputs kept with
   the campaign artifacts).
3. `campaign.py --variant selflearn --dry-run --no-sim --pdk gf180mcu
   --max-specs 2` green locally.
4. Push to origin/main — **user per-instance permission required** (Kaggle
   kernels clone origin).
5. GPU quota checked (UI); ghtoken dataset valid (PAT unrotated as of
   2026-09-03 — if the user rotates it first, the `circuit-repro-ghtoken`
   dataset must be updated before any kernel push).
6. Kernel pushed from the job-tmp copy with campaign defaults
   (`RUN_MODE=campaign`, `ARM`, `PDK=gf180mcu`, `WALL_BUDGET_MIN`); the repo
   copy keeps smoke defaults. Secret-scan every artifact before commit
   (`grep -rE "github_pat_|x-access-token:"`).

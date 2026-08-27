# CAMPAIGN — capability-v1 (PRE-REGISTRATION)

**Status: EXPERIMENTAL. Committed BEFORE results (house law).**
Nothing here is frozen protocol. Adoption or freezing of any target is a **USER
RULING** (memory: circuit-repro-governance). This file records the three arms,
their budgets, metrics, and attribution rules *before* any v1 number is read, so
no result can be reverse-justified.

Date pre-registered: 2026-08-27. Builds on `kaggle/CAMPAIGN-CAPABILITY-V0.md`.

---

## 1. The question

**Can the SYSTEM improve ITSELF from its own v0 outputs?**

v0 ran a 24-spec LNA ladder (`kaggle/specs-ladder/ladder.json`). Arm A (the
sizing-only null: `solve_spec.CORPUS` sized at a matched eval budget, no LLM)
solved 20/24; arm B (the full Qwen3-30B reasoning loop on Kaggle) solved 10/24.
v0 arm-B output is committed under `kaggle/campaigns/capability-v0/armb/`
(`results.jsonl`, `results.md`, `trajectory/*.jsonl`, `designs/`).

v1 asks whether two architectural additions, and then self-authored memory,
move arm B's solved count — **without any human- or Claude-authored domain
guidance entering any arm.**

### Binding standing principle (USER RULING — quoted, not paraphrased)

> No human- or Claude-authored domain guidance may enter any arm. The system
> reads its OWN results, identifies its OWN shortcomings, writes its OWN
> lessons. Humans/Claude only change architecture and commission experiments.
> Prompts/scaffolding must be content-neutral (structure, not circuit
> knowledge).

Every prompt this campaign adds is **content-neutral**: it describes the *shape*
of the input and output (schema, ordering, the verbatim-evidence rule) and names
**no** circuit family, metric target, topology, archetype, or design move. The
two prompts are auditable verbatim: the reflect prompt via
`python kaggle/loop/reflect.py --print-prompt`, the self-diversity prompt as
`DIVERSITY_SYSTEM` / `DIVERSITY_USER` in `kaggle/loop/campaign.py`. (The only
domain-ish tokens either prompt emits are the playbook's own **controlled
failure-signature vocabulary** and the spec YAML the model is asked to design
for — both are the system's own artefacts, not authored guidance.)

---

## 2. Arms

All three arms are arm-B-family: same 24-spec ladder, same funnel, same sizing
engine (`solve_spec.size_tokens` → CMA-ES/ngspice), same feasibility test, same
results schema, same advisory verify pass, same **escalation rule and total
budgets as v0** (§3). One file (`kaggle/loop/campaign.py`, `--variant`) runs all
three so they cannot diverge in scoring by accident. The v0 **arm-A null** is
unchanged and remains the attribution baseline.

### ARM1 — "v0-repeat" (`--variant v0`)

**Byte-identical v0 arm-B configuration.** `--variant v0` dispatches to the
unchanged `run_spec_arm_b` (verified: its trajectories carry none of the v1
diversity/triage/concentrate markers; `--variant` defaults to `v0`, and default
== explicit `v0`). Purpose: measure **run-to-run noise** — the floor against
which any v1 delta must clear. ARM1 vs v0 = the noise floor.

### ARM2 — "architecture" (`--variant arch`)

v0 arm-B **+ two architectural changes, no memory:**

**(i) CONCENTRATION (triage → concentrate).** The per-spec **total** eval budget
is UNCHANGED from v0 — `(k + edit_rounds) × seeds × budget` eval-equivalents —
but re-allocated:

- **Triage.** Each of the `k` proposals is sized at **`TRIAGE_SEEDS = 1` seed ×
  `triage_budget` evals**, where **`triage_budget = budget // TRIAGE_FRAC`,
  `TRIAGE_FRAC = 5`** (base `budget = 300` → **60 evals × 1 seed each**, exactly
  the brief's example; escalation `budget = 600` → 120). This costs
  `k × 1 × triage_budget` eval-equivalents.
- **Concentrate.** The single triage winner (feasibility-first `rank_key`, the
  same selection arm B uses) is re-sized at **full `seeds` × full `budget`**, then
  driven through the `edit_rounds` at full budget — spending the remaining
  eval-equivalents on the one proposal triage picked.

Pre-registered constants live in `campaign.py`: `TRIAGE_FRAC = 5`,
`TRIAGE_SEEDS = 1`. The row records `triage = {n_proposals, triage_budget,
n_approaches, winner}` and the honest `total_evals` actually consumed.

**(ii) SELF-GENERATED DIVERSITY.** One **preliminary** LLM call per spec asks the
model to enumerate **`k` structurally distinct approaches in its own words** (the
content-neutral `DIVERSITY_*` prompt names no families). Each of the `k` propose
calls then **anchors on one of the model's OWN approach descriptions**
(`_anchor_prompt` appends the model's own approach text to the standard propose
prompt — no domain content added). If the diversity call fails or returns
nothing, propose falls back to the plain v0 prompt (recorded, never fatal).

ARM2 has **no memory** — it is the **cold control** for the learning claim.

### ARM3 — "self-learning" (`--variant selflearn`)

ARM2 **+ REFLECT-FIRST.** At session start, before the ladder runs,
`reflect.py` reads the system's OWN v0 arm-B corpus
(`kaggle/campaigns/capability-v0/armb/` — committed, present in any clone: its
`results.jsonl` + failed best designs + `prediction_vs_outcome` records +
verbatim errors in `trajectory/*.jsonl`) and writes its own playbook entries to
a **session-local overlay** under `<out>/system-playbook/` (saved in the run
output for audit and later commit). The ladder then runs exactly as ARM2, except
**consult retrieves BOTH** the governed `lna/playbook` **AND** the
system-authored overlay (via `playbook.py --consult --extra-dir <overlay>`).

Every accepted entry is stamped `author:"system"`, `confidence:"unverified"`.
Entry content is the model's own words; **every evidence quote is mechanically
required to appear verbatim** in the loaded v0 results/trajectories (§ no-injected
clause). Cap: **≤ 12 accepted overlay entries** per reflect pass
(`--reflect-cap`, default 12). Rejected entries are logged verbatim to the
reflect trajectory.

**ARM3 vs ARM2 = the learning claim.** ARM2 (cold, same architecture, no memory)
is the control; any ARM3 gain over ARM2 is attributable to the system-authored
memory, not to concentration/diversity.

---

## 3. Budgets & escalation (UNCHANGED from v0)

Per spec, **base**: `k=3, edit_rounds=2, seeds=2, budget=300, max_tokens=3072`.
On infeasible at base → **ONE escalation**: `k=5, edit_rounds=4, seeds=3,
budget=600`. Still infeasible after escalation = **HARD FAILURE**; move on.

Per-spec **total** eval budget is therefore identical across v0, ARM1, ARM2,
ARM3, and the arm-A null: base `(3+2)×2×300 = 3000`, escalation
`(5+4)×3×600 = 16200` eval-equivalents. ARM2/ARM3 spend that same total; they
only re-allocate it (triage + concentrate). The self-diversity call and the
ARM3 reflect call are **LLM calls, not ngspice evals** — they do not touch the
matched sizing budget the arm-A attribution rests on.

**Quota estimate:** ~4 h/arm on Kaggle GPU (matches v0 arm-B wall time; the
diversity/reflect LLM calls add a bounded per-spec / per-session overhead well
inside the `WALL_BUDGET_MIN` gate, default 500). Three arms ≈ 12 h total.

---

## 4. Metrics & attribution

Per spec, per arm, in `results.jsonl` (+ `results.md`), checkpointed after every
spec (a timeout loses nothing). All v0 columns are retained; v1 adds:

- **variant** — `v0` / `arch` / `selflearn`.
- **triage** — `{n_proposals, triage_budget, n_approaches, winner}` (ARM2/ARM3).
- **consult_hits / overlay_hits** — retrieved-per-spec counts; `overlay_hits` is
  how many retrieved entries came from the ARM3 system overlay.
- **(ARM3)** `<out>/reflect-summary.json` + `<out>/system-playbook/` — the
  entries the system wrote (audit + later commit), and `entries_written` /
  reject counts in the reflect trajectory.

**Primary comparisons (all at the matched total budget):**

- **ARM1 − v0** → **run-to-run noise floor.** Any real v1 effect must exceed it.
- **ARM2 − v0** (per-spec solved deltas) → the effect of **architecture**
  (concentration + self-diversity) alone.
- **ARM3 − ARM2** → **the learning claim.** ARM2 is the cold control; a positive
  delta is attributable to the system's self-authored memory.
- **B feasible where the v0 arm-A null is infeasible** → **topology credit**
  (unchanged from v0 §5). Attribution against the arm-A null is unchanged.

### No-injected-content clause (BINDING)

No human- or Claude-authored circuit knowledge enters any arm. Mechanically
enforced: (a) both added prompts are content-neutral and printed verbatim for
audit; (b) reflect **rejects** any entry whose evidence quote is not a verbatim
substring of the loaded v0 results/trajectories (a paraphrase, an invented
number, or a rounding the model did not see is rejected and logged); (c) every
accepted entry is stamped `author:system, confidence:unverified` and validated
against `lna/playbook.py`'s own `validate_entry` before it can be retrieved; (d)
the overlay is read-only and additive — a governed entry always wins over an
overlay id of the same name, and governed ops (`--check`, `--add`, `--escalate`,
`--reindex`) never see the overlay.

### Honest-outcome clause (BINDING, unchanged from v0)

0-feasible rows are results, not failures to suppress. Every spec gets a row
whatever the outcome; hard failures are reported with closest-attempt margins and
the closest design saved. An all-red arm, or an ARM3 that fails to beat ARM2, is
**the answer to the capability question, not a bug** — reported as measured.

### Experimental clause

All 24 ladder specs remain EXPERIMENTAL, not frozen protocol. v1's conclusions
inform — they do not adopt — any target. Freezing is a user ruling.

---

## 5. Artefacts & how to run

```
kaggle/CAMPAIGN-CAPABILITY-V1.md        this file (pre-registration)
kaggle/loop/reflect.py                  ARM3 reflect stage (self-authored overlay)
kaggle/loop/campaign.py                 --variant {v0,arch,selflearn}; triage+diversity
kaggle/loop/fixtures/reflect.json       canned reflect completion for --dry-run
lna/playbook.py                         + additive --extra-dir on --consult (overlay)
kaggle/kernels/loop-gpu/kernel.py        RUN_MODE=campaign + ARM env -> --variant
kaggle/campaigns/capability-v0/armb/     the v0 corpus ARM3 reflects on (committed)
```

Local dry-runs (no server, no ngspice):
```
python kaggle/loop/reflect.py --dry-run \
    --v0-dir kaggle/campaigns/capability-v0/armb \
    --overlay-dir /tmp/overlay --traj /tmp/reflect.jsonl
python kaggle/loop/campaign.py --arm B --variant arch      --dry-run --no-sim \
    --ladder kaggle/specs-ladder/ladder.json --max-specs 2
python kaggle/loop/campaign.py --arm B --variant selflearn --dry-run --no-sim \
    --ladder kaggle/specs-ladder/ladder.json --max-specs 2
python kaggle/loop/reflect.py --print-prompt \
    --v0-dir kaggle/campaigns/capability-v0/armb --overlay-dir /tmp/x --traj /tmp/x
```

On Kaggle: push `loop-gpu` with `RUN_MODE=campaign` and `ARM` in
`{v0, arch, selflearn}` (plus `WALL_BUDGET_MIN`). Output lands in
`/kaggle/working/campaign/`; the ARM3 overlay under
`/kaggle/working/campaign/system-playbook/`. Run all three arms; commit each
arm's `results.*`, `designs/`, `trajectory/`, and (ARM3) `system-playbook/` +
`reflect-summary.json` under `kaggle/campaigns/capability-v1/<arm>/` after the
run, honest outcome whatever it is.

# Phase 2 — learned critic, guided search, self-improvement

**Brief (user, 2026-08-06):** the generate→bias→size→verify pipeline is
feature-complete; do not improve it unless necessary. Convert the system from
"generate then optimize" into "generate, **predict feasibility**, search, then
optimize": a learned critic on the topology graph (GNN or graph transformer)
that predicts gain / NF / S11 / power / feasibility before SPICE runs, trained
on existing + new simulation results, exposing a score usable by beam or
evolutionary search, minimizing SPICE evaluations by filtering candidates
before sizing. Proposed stages: (1) critic, 2–3 wk; (2) critic-guided search,
3–4 wk; (3) self-improvement loop, 1–2 mo.

**This plan set is written against the actual state of branch `lna-exec` at
`00cd32e`** (candidate sizing end-to-end; HANDOVER-EXEC.md findings #1–10).
Executor: start here, then read files in order. Companion docs: FINDINGS.md
§5/§5b, WORKLOG R1–R3, HANDOVER-EXEC.md.

---

## 1. Feasibility verdict

**Feasible — provided three reframings, without which the literal plan fails.**

### R1. Predict *post-sizing margins*, not raw metrics

"Predict gain/NF/S11 from the topology graph" is ill-posed as stated: an
unsized topology does not *have* an S21 — the same graph spans tens of dB
across its `.param` surface. The well-defined learning target is the
**post-sizing outcome**: for each metric, the best value ZOAF reaches under a
given spec — exactly what `size.py --scoreboard` already measures. Two
consequences:

* One label costs a ZOAF run (~230–300 sims ≈ **4–5 min**), not one
  simulation. Label economics dominate the whole phase (see R2).
* The critic head is a **per-metric margin vector** (achieved − required,
  normalized per 05-SIZING's objective scales), not a feasibility boolean.
  Feasibility is *computed* from predicted margins against any spec — the
  critic stays spec-agnostic where possible, and the boolean label problem
  below disappears.

The boolean label problem is real, measured, and disqualifying for the naive
plan: the last scoreboard run was **0/3 feasible** (FINDINGS §5b) because the
~7 dB single-stage gain ceiling caps every current candidate below every
spec's 12–15 dB S21 floor. A feasibility classifier trained on today's
pipeline output learns "always no" with excellent accuracy. Margins keep the
gradient; fixing the topology pool (R3) fixes the class balance.

### R2. Hierarchical labels — L1 at scale, L2 by campaign, rank-first

Today's L2-labeled set is ~4 topologies (anchor + 3 P2 candidates). No
architecture rescues that. The plan stands or falls on a **labeling campaign**
(01-DATA): at ~4–5 min/label and 4–5 parallel jobs, **~60 labels/night**;
running nightly from Stage-0 day 1 yields **400–800 L2 labels inside the
Stage-1 window** — enough to train a *ranking* model with a small-capacity
critic, thin for absolute regression. Meanwhile L1 labels (op-point:
conducting/saturation per device, ~1 s via `bias.py`'s sweep) can be minted by
the **thousands** over the generated pool already sitting in `lna/out/`
(a dozen arms × 128–256 samples). Hence a two-head critic:
an L1 head trained on abundance, an L2 margin/rank head trained on the
campaign, sharing the graph encoder (02-CRITIC).

Evaluation is rank-based (Spearman, precision@k, enrichment@top-20%) on
holdouts split **by topology family** (WL-hash cluster), never by sample —
the corpus is full of near-duplicates and a random split would leak.

### R3. Search ladder: rerank → evolutionary → beam (optional)

The pipeline's costs: generation 0.3 s/seq, L0 screen free, L1 ~1 s, L2 ~4–5
min. So the critic's *entire economic value* is deciding **which candidates
get an L2 sizing run** — everything upstream is already effectively free.
That fixes the success metric for the whole phase:

> **SPICE-minutes per feasible novel design** (and its proxy, enrichment of
> the sized set vs. random selection at equal budget).

Beam search over token prefixes is the *hardest* integration (it needs a
value model on partial graphs) and the *least* necessary (generating complete
candidates is cheap — 256 in 2 min). So Stage 2 climbs: **(1) best-of-N
rerank** — generate big, critic-rank, size top-k: one day of integration,
immediately measurable; **(2) evolutionary search** over graph edits with the
critic as fitness; **(3) beam search** only if a stated trigger fires
(03-SEARCH §4). This honors the brief ("score usable by beam or evolutionary
search") while sequencing by value-per-effort.

### Prerequisites the brief's stages silently assume (Stage 0)

The brief says "do not improve the pipeline unless necessary." Four items are
*necessary* — each is an enabler the critic literally cannot train without,
and each was already flagged as next-in-line by HANDOVER-EXEC §6:

1. **A gain-capable topology family** (output matching / buffered archetypes)
   — otherwise every L2 label is infeasible and feasibility has one class
   (this is also exactly Gate G4's missing piece).
2. **P5 template corpus (`templates.py`)** — the labeled pool needs topology
   *diversity*; P1/P2 arms recite 35 training graphs (median NN-sim 1.000),
   so labeling only their output teaches the critic 35 points.
3. **NF harness fix** (series-Rs noise source; HANDOVER-EXEC finding #7) —
   until then NF is `unsupported` and the critic has no NF target. Ship the
   NF head later if this slips; do not block the phase on it.
4. **Label store + logging hooks** (01-DATA) — every ngspice/ZOAF result from
   now on is training data; the hooks must exist before the campaign starts.

Stage 0 is ~4 days and doubles as closing Gate G4 — not scope creep, the same
work the previous plan already owed.

### Honest risks, stated now

* **Distribution shift under search pressure.** A critic used as a search
  objective gets optimized against; candidates drift off-distribution and
  predictions silently degrade (classic surrogate failure). Mitigations are
  structural, not hopeful: deep-ensemble uncertainty (02-CRITIC §5), an
  uncertainty-gated trust rule in search (03-SEARCH §5), SPICE verification
  of every elite before it is called anything, and **reported numbers only
  ever come from SPICE** — the critic never appears in FINDINGS as truth.
* **The GNN may lose to hand features.** On ≤16-device graphs with a few
  hundred labels, a feature model (WL counts + graph stats + cheap L1 op
  features) is a strong opponent. 02-CRITIC builds it *first* as the mandatory
  baseline; the GNN ships only if it beats the baseline on held-out families.
  Either way the product — a fast pre-SPICE filter — exists; the brief prefers
  a GNN but the program needs the filter.
* **Stage-3 collapse.** Fine-tuning the generator on its own high scorers is
  expert iteration, and its known failure is mode collapse onto a few
  winners. 04-SELF-IMPROVE gates every loop iteration on the frozen NDL@256
  protocol (may not regress) plus explicit diversity tripwires.

**Stage timeline sanity:** Stage 1 in 2–3 wk — yes, *if* the campaign starts
day 1 of Stage 0 and runs nightly. Stage 2 in 3–4 wk — yes for rungs 1–2.
Stage 3 in 1–2 mo — yes as cadence + guardrails; it is an operating mode, not
a build.

---

## 2. File map

| file | work package | brief stage | cost |
|---|---|---|---|
| 01-DATA.md | WP-DATA — label store, logging hooks, labeling campaign, backfill | Stage 0 + continuous | 3–4 days + nightly compute |
| 02-CRITIC.md | WP-CRITIC — feature baseline, GNN encoder, two heads, uncertainty, eval | Stage 1 | ~2 wk |
| 03-SEARCH.md | WP-SEARCH — rerank experiment, evolutionary loop, beam trigger | Stage 2 | ~3 wk |
| 04-SELF-IMPROVE.md | WP-LOOP — active learning, retrain cadence, expert iteration, tripwires | Stage 3 | 1–2 mo cadence |
| 05-SCHEDULE.md | gates C0–C4, day-by-day for Stages 0–1, week-by-week after | — | — |

## 3. Ground rules (carried forward + new)

1. **Regression quartet before and after every WP** (HANDOVER-EXEC §4):
   vocab guard (analoggenie python), legacy screen 59.4%, pipeline yield
   40/42, `check_ref.py` green — plus `calibrate_specs.py`.
2. **Environments:** analysis stays torch-free py 3.14; anything with torch
   (critic training *and inference*) lives in the WSL GPU env
   (`/opt/miniconda/envs/gpu/bin/python`, RTX 3050 4 GB); GPU work goes
   through PowerShell → `wsl -e bash script.sh`, never Git Bash (X10).
   The critic gets **no new heavyweight deps**: hand-rolled message passing in
   plain torch, no PyG (02-CRITIC §3).
3. **The frozen NDL@256 protocol still governs all generation claims**
   (FINDINGS §5). Stage-3 generator updates must re-run it unchanged.
4. **The label store is append-only and versioned** (01-DATA §2); training
   sets are pinned by snapshot id so every critic version is reproducible.
5. **Work on `lna-exec` or a branch off it, commit per task, never push to
   `main`.** Plans live in `lna/plans2/`; update HANDOVER-EXEC.md as you land
   work, same as last session.

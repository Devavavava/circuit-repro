# Schedule — Stage 0 + the brief's three stages, gated

One executor session per WP works. Nights are load-bearing: the labeling
campaign runs while nobody is watching, and several gates only accumulate
rows overnight. Do not start a gated item early — data-starved training runs
produce confident nonsense that then has to be un-believed.

## Stage 0 — prerequisites the critic cannot train without (days 1–4)

| day | work | from |
|---|---|---|
| 1 | `datastore.py` + logging hooks in `size.py`/`bias.py`; regression quartet green; backfill starts (corpus L1 + anchors) | 01-DATA §2–4 |
| 2 | NF harness fix (series-Rs noise source; ref decks re-baselined, `check_ref.py --update`); corpus L2 backfill runs overnight | HANDOVER-EXEC #7 |
| 3 | **gain-capable reference**: output match / buffer stage on stage-B; hand-feasible vs `wifi24` incl. S21 ≥ 12 — this is also Gate G4's missing topology | HANDOVER-EXEC §6.1 |
| 4 | `templates.py` (P5): archetype generator incl. buffered/matched families, NB/WB labels, ~150–400 graphs; `campaign.py` first night | 01-DATA §5, old plan 04-GEN §6 |

**Gate C0 (allowed to trail into week 2 — nights must accumulate):**
campaign has run 3 consecutive nights unattended; ≥ 150 L2 rows (≥ 25%
stratum T); repeat-probe σ measured. *Also collect here:* the stage-B+buffer
reference sized to full feasibility = **Gate G4 closed by hand** — worth
announcing on its own.

## Stage 1 — the critic (days 5–14, brief says 2–3 wk: fits)

| day | work | from |
|---|---|---|
| 5–6 | frozen eval protocol + family split; baselines (trivial / WL-kNN / ridge) trained + scored on backfill rows | 02-CRITIC §2, §4 |
| 7–10 | MPNN encoder + two heads; ablations (±L1 features, ±rank loss); campaign keeps feeding | 02-CRITIC §3 |
| 11 | 5-member ensemble + calibration check | 02-CRITIC §5 |
| 12–14 | retrain all arms on the full snapshot; eval report; **C1 verdict**; `--score` + `--export-npz` CLI | 02-CRITIC §4, §6 |

**Gate C1:** enrichment@top-20% ≥ 2× and Spearman(S21 margin) ≥ 0.5 on
held-out families — by *any* arm; ship the best arm as critic v1 (GNN only if
it beats the baselines). **C1 fail:** do not proceed to search — diagnose
(σ too high? too few rows? split too hard?), fix data, re-gate. The de-scope
ladder at the bottom of this file applies.

## Stage 2 — guided search (weeks 3–6, brief says 3–4 wk: fits)

| week | work | gate |
|---|---|---|
| 3 | rung-1 rerank + random control, one night, scoreboards + realized-vs-predicted correlation; critic retrain with the 60 new rows | **S1** |
| 4–5 | evolutionary loop (`--evolve`): move set, decomposition crossover, uncertainty gate, top-3-elite true evals; two overnight runs | **S2** / **G4** |
| 6 | rung-3 trigger decision from measured supply numbers (expectation: no build); Stage-2 FINDINGS entry; buffer for whichever gate slipped | 03-SEARCH §3 |

## Stage 3 — the loop (months 2–3, brief says 1–2 mo: fits)

Cadence, not construction (04-SELF-IMPROVE): campaign switches to ½
acquisition-driven quota; critic retrains per +100 rows (adopt-only-if-
better); generator expert-iterates per ~100 sized rows or monthly; rung-1
re-run after every adoption gives the headline curve its next point. All five
tripwires active from day 1 of Stage 3. **Exit:** two consecutive loop
iterations with SPICE-minutes-per-feasible-novel-design improving and
tripwires quiet.

## ∥ Parallel / fill-in (no gates)

* P1+P5 per-class-token fine-tune (`<LNA_NB>`/`<LNA_WB>`) once `templates.py`
  exists — it was the old plan's next lever anyway, and a more diverse
  generator widens every downstream stratum.
* NF head added to the critic once ≥ ~100 rows carry real NF labels.
* WP-BIAS v2 (R-SOURCE/R-DRAIN) only if the campaign's L1 attrition says so
  (HANDOVER-EXEC finding #9 has the measured split).

## De-scope ladder (pre-agreed, so failure is cheap)

1. GNN loses to baselines → **ship the baseline as critic v1**; the filter
   exists, the brief's GNN preference is noted as tried-and-beaten.
2. No arm clears C1 → search waits; campaign + rerank-by-L1 still cuts
   sizing waste vs. status quo (L1 already rejects non-conductors for 1 s).
3. Evolutionary search underperforms rerank → keep rerank in production;
   evolution becomes a parallel-track experiment.
4. Whatever happens, **the label store keeps every hour spent** — data
   outlives models, which is why WP-DATA goes first.

## Definition of done (the brief, restated as checkboxes)

- [ ] Stage 1: critic predicting margins for S21/S11/Idd (+NF when harnessed) with measured enrichment ≥ 2× on held-out families — C0, C1
- [ ] Stage 2: one-shot generation replaced by critic-ranked selection (+ evolutionary loop if S2 passes), controlled-experiment evidence in FINDINGS — S1, S2
- [ ] Stage 3: two loop iterations, curve bending, tripwires quiet — exit criterion met
- [ ] Gate G4 (inherited): ≥ 1 novel generated topology sized to full feasibility — expected to fall out of Stage 0 (by hand) and Stage 2 (generated)

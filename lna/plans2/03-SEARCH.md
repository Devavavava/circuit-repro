# WP-SEARCH — spending SPICE minutes only where the critic says to

**Answers:** brief Stage 2 (replace one-shot generation with critic-guided
beam / evolutionary search).
**Deliverables:** `lna/search.py` (`--rerank`, `--evolve`), two controlled
experiments with scoreboards, gate S1/S2 verdicts in FINDINGS.
**Cost:** ~3 wk. **Depends on:** 02-CRITIC clearing gate C1.

The yardstick for every rung, fixed here: **SPICE-minutes per feasible novel
design**, measured against a control at *equal sizing budget*. A search
method that cannot beat "size 30 random screened candidates" at the same cost
is decoration, whatever its internals.

---

## 1. Rung 1 — best-of-N rerank (2–3 days, the immediate payoff)

The brief's "minimize SPICE evaluations by filtering poor candidates before
sizing," implemented with zero new search machinery:

```
generate N≈512–1024 (best arm, ~4–8 min GPU) → L0 screen → WL-dedup vs store
→ L1 (~1 s each) → critic.score(graph+L1, spec) → size top-30 by mean−β·σ
```

**The experiment is controlled:** the same night sizes 30 *random* picks from
the identical L0+L1-passing dedup'd pool. Two scoreboards, same budget
(~2.5 h each at 5 jobs).

**Gate S1:** critic-picked set contains **≥ 2× the feasible-or-near-feasible
designs** of the control set (in-vivo confirmation of C1's enrichment claim).
Report alongside: realized-vs-predicted rank correlation over all 60 sized
candidates — the first deployment-distribution test, and it feeds 02-CRITIC's
next retrain regardless of pass/fail.

## 2. Rung 2 — evolutionary search over graph edits (1.5–2 wk)

Search moves to **graph space** — the LM seeds the population; mutation and
crossover bypass tokens entirely (tokens re-enter in Stage 3 when winners
fine-tune the generator). `templates.py`'s archetype decomposition (input
stage / cascode / load / match / buffer) supplies semantically meaningful
edits instead of blind rewiring:

* **Mutations (structural only — values are ZOAF's job):** swap load class
  (R ↔ tuned tank ↔ shunt-peaked); add/remove cascode; add/remove output
  buffer; add/remove degeneration (Ls or Rs); swap input-stage class; add/
  remove a matching element (series L / C-divider). Validity = `topology.py`
  reconstruction + L0 screen; then L1 before any critic score.
* **Crossover:** exchange whole stages at the archetype decomposition
  boundaries (only defined for candidates the decomposer can parse — skip
  otherwise, don't force it).
* **Fitness:** conservative critic scalar (`mean − β·σ`, spec-encoded) plus a
  novelty bonus proportional to WL-distance to the labeled store — pressure
  *away* from re-deriving labeled designs.
* **Ground truth in the loop:** each generation, the top-3 not-yet-labeled
  elites get a true L2 sizing run (~15 min), appended to the store — search
  manufactures its own training data (the Stage-3 bridge, and the §4 trust
  rule's enforcement point).

Budget: population 64, ~20 generations overnight ≈ 60 true evals — the same
sizing budget as one rung-1 night, which makes the comparison honest.

**Gate S2:** at equal true-eval budget, the evolutionary run yields ≥ 2× the
feasible novel designs of rung-1 rerank — or produces the program's first
**Gate G4** design (novel topology, fully feasible, sized) if rung 1 hasn't
already. Winners' novelty is reported under the frozen WL/NDL machinery.

## 3. Rung 3 — beam search in token space (build only on trigger)

What it requires that nothing else does: a **prefix-value model** — the
02-CRITIC encoder trained on truncated Eulerian traversals (a prefix is a
connected partial graph, so it encodes fine) against the full sequence's
label. Then beam k≈8–16 with score `α·LM-logprob + (1−α)·critic(partial)`.

**Trigger to build it (state the expectation: it does not fire):** rungs 1–2
both clear their gates **and** the bottleneck analysis shows candidate
*supply* — post-dedup, post-L1 survivors per GPU-hour — is what limits
feasible-design throughput, rather than selection quality. Generation is
0.3 s/sequence; supply has never been the constraint. If the trigger does
fire, prefix-label data is free (truncate labeled sequences), so the build is
~4 days, not a research project.

## 4. Trust rules — how search is allowed to use a model it will corrupt

Search optimizes against the critic, so candidates drift off-distribution by
construction. These rules are mechanical, not aspirational:

1. Search always consumes `mean − β·σ` (β ≈ 1), never the raw mean.
2. **Uncertainty gate:** a candidate whose ensemble σ exceeds the 90th
   percentile of holdout σ cannot enter the size-list on its score — it is
   routed to the campaign's exploration stratum for true labeling instead.
3. **Trust region:** offspring beyond WL-distance d_max from every labeled
   family get a true eval before their critic score counts for selection
   (the top-3-elites rule in §2 is where this bites).
4. **Only SPICE numbers are results.** Critic scores never appear in
   FINDINGS tables as measurements; every design called "feasible" has a
   sizing run to show for it.

## 5. Interface

```bash
python lna/search.py --rerank --arm out/ft_p2_s1337 --spec wifi24 --n 512 --size-top 30 --control
python lna/search.py --evolve --spec wifi24 --pop 64 --gens 20 --true-evals 60
```

Both append every sizing result to the store (01-DATA hooks — free), write a
scoreboard CSV + FINDINGS-style table, and record the critic version + data
snapshot used (00-OVERVIEW rule 4).

## 6. Acceptance

- [ ] rung-1 experiment run, control included, S1 verdict recorded either way
- [ ] realized-vs-predicted correlation fed back into 02-CRITIC retrain
- [ ] evolutionary loop runs overnight unattended; S2 verdict recorded
- [ ] ≥ 1 Gate-G4 design (novel + feasible + sized) — the phase's headline
- [ ] rung-3 trigger evaluated from measured supply numbers, decision written down

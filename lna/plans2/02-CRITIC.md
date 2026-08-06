# WP-CRITIC — the surrogate model

**Answers:** brief Stage 1 (critic predicting gain/NF/S11/power/feasibility
"with even moderate accuracy").
**Deliverables:** `lna/critic.py` (features, baseline, GNN, ensemble, eval,
scoring CLI), a critic-v1 eval report in FINDINGS style.
**Cost:** ~2 wk wall clock, most of it waiting on 01-DATA's campaign.
**Depends on:** 01-DATA (≥ 150 L2 rows, σ measured). **Blocks:** 03-SEARCH.

---

## 1. Inputs and targets

**Input graph:** `topology.py`'s reconstruction, encoded bipartite —
device nodes (type one-hot: NMOS/PMOS/R/C/L/port/supply) ↔ net nodes (class:
VDD / 0 / port / bias / internal), edges typed by pin role (G/D/S/B, ±).
Bias scaffolding excluded by the naming contract, as everywhere else.

**Simulation-informed features (cheap, high-value):** the L1 op block —
per-device {Id, gm, Vds, Vdsat} at the `bias.py` sweep winner — appended to
device-node features. Costs ~1 s per candidate and encodes what no static
graph feature can (whether the thing actually conducts). Two operating modes,
one model: graph-only (scoring raw generation output) and graph+L1 (before
committing 5 sizing minutes); train with dropout on the whole L1 block so the
model degrades gracefully when it is absent.

**Spec conditioning:** a small vector of the spec's constraint thresholds +
band (f0, type) concatenated at the readout. One model serves `wifi24` and
`wideband-sdr`; generalization to *unseen* specs is untested and must not be
claimed.

**Targets, two heads sharing the encoder** (the R2 hierarchy, 00-OVERVIEW):

| head | target | trained on |
|---|---|---|
| **H-L1** | P(all MOS conduct at best sweep point); saturated-device fraction | thousands of L1 rows (backfill §4) |
| **H-L2** | per-metric normalized margin vector (S11, S21, Idd; NF when the harness fix lands) + pairwise rank | 150–800 campaign rows |

Feasibility under any spec is *computed* from predicted margins — never a
trained boolean (the 0/3 class-collapse argument, 00-OVERVIEW R1).

## 2. Baselines first — mandatory, and genuinely dangerous opponents

Built and frozen *before* the GNN exists, on the same split:

1. **Trivial floor:** predict the training-set mean margin per metric.
2. **WL-kNN:** predict the label of the nearest labeled neighbor by WL-kernel
   similarity (`novelty.py` already computes NN-sim — reuse it verbatim).
   With this corpus's duplicate structure, expect this to be embarrassingly
   strong; that is exactly why it must be on the table.
3. **Ridge on hand features:** device-type counts, inductor count/ratio,
   WL-subtree count vector (hand-rolled WL already in `novelty.py`), node/edge
   counts, mean/max degree, + aggregated L1 features (min Vds−Vdsat, #off
   devices, ΣId). Pure numpy, runs in the torch-free analysis stack.

**Rule: the GNN ships as critic v1 only if it beats max(2, 3) on the primary
holdout metrics. Otherwise the best baseline ships as critic v1** behind the
same interface, and the GNN remains a tracked experiment. The brief prefers a
GNN; the program needs a filter. Record which shipped in FINDINGS.

## 3. GNN v1 (plain torch, WSL GPU env, no PyG)

Graphs have ≤ ~16 devices / ~50 total nodes — dense tensors beat sparse
libraries at this size, and we add **no new dependencies** (00-OVERVIEW rule 2):

* Per pin-role adjacency matrices `A_role` (a handful of 50×50 matrices,
  padded batch); message passing = matmuls: device→net and net→device
  rounds with role-specific linear maps, 3–4 rounds, hidden 64, residual.
* Readout: sum + max pooling over device nodes → concat spec vector → MLP →
  two heads. Total ~100–200 k params — minutes per training run on the 3050,
  which is what makes the §5 ensemble and Stage-3 retraining cheap.
* Loss: `w1·BCE(H-L1) + w2·Huber(margins) + w3·pairwise-rank-hinge`, pairs
  drawn within the same spec, hinge margin set from the repeat-probe σ
  (01-DATA §5 — do not ask the model to resolve differences smaller than
  label noise). Early stop on family-val loss.
* A graph-transformer variant is *deferred*: at ≤ 800 labels the MPNN will
  not be capacity-limited; revisit only if H-L2 underfits train.

## 4. Evaluation protocol — frozen before the first training run

* **Split:** `datastore.family_split()` — whole WL-families held out
  (01-DATA §2). Plus one **source-shift split**: train on corpus + templates,
  test on generated arms — a rehearsal of exactly the shift search will cause.
* **Metrics, reported vs all baselines + the σ noise ceiling:**
  per-metric Spearman ρ; pairwise rank accuracy; precision@k and
  **enrichment@top-20%** for near-feasible (all margins > −1 scale unit);
  H-L1 AUC; uncertainty calibration (§5).
* **Gate C1 (critic adopted at all):** on held-out families —
  **enrichment@top-20% ≥ 2×** over random selection for near-feasibility,
  and **Spearman ≥ 0.5 on the S21 margin** (the binding constraint
  everywhere, per §5b). Any model that clears C1 makes search worth wiring;
  if none does, stop and diagnose data (more strata-M contrast? more labels?
  σ too high?) before touching 03-SEARCH.

## 5. Uncertainty — a deep ensemble, because search will lie to us

5 members, different seeds/data order (minutes each, §3). Prediction = mean;
uncertainty = member std. Check calibration on holdout: std must rank |error|
(report the correlation; if std is uninformative, say so — 03-SEARCH's trust
rule then falls back to hard novelty-distance gating). Search consumes
`mean − β·std` (β ≈ 1) so the optimizer cannot mine flattering noise.

## 6. Interface

```bash
# WSL GPU env
python lna/critic.py --train --snapshot v1-train --arm gnn|ridge|knn
python lna/critic.py --eval  --snapshot v1-train          # full §4 report
python lna/critic.py --score out/ft_p2_s1337 --spec wifi24 --top 30 --l1
python lna/critic.py --export-npz                          # weights → .npz
```

`critic.score(graphs, spec, l1=None) → {margins, σ, p_conduct, scalar}`;
scalar = the 05-SIZING feasibility-first encoding applied to predicted
margins, so search and sizing rank by the same yardstick. The `--export-npz`
path + a numpy forward (~30 lines: matmuls and relu) lets the torch-free
analysis stack score candidates without WSL — search then runs anywhere.
Latency budget: 1000 graphs < 10 s (trivially met; state it so nobody
builds a cache).

## 7. Order of work

Days 1–2 baselines + frozen eval on backfill data (yes, before the campaign
finishes — early numbers on 150 rows tell us if σ or split problems exist
while there is time to fix them). Days 3–6 GNN + ablations (graph-only vs
graph+L1; with/without rank loss). Day 7 ensemble + calibration. Days 8–10
retrain on the full campaign snapshot, final eval report, C1 verdict.

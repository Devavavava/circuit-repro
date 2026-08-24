# E13-DIRECTIONS — post-E-12 program directions (for a next session to consider)

**Status: DIRECTIONS DRAFT (not a pre-registration, not an authorization).** Written
2026-08-24 after E-12 completed (falsifier MET: trained editors 0 solves on
DEV/HELD-OUT/FRESH). Captures the diagnosis, the levers, and the hardware/strategy
picture so the next session does not have to re-derive them. Each lever below still
needs its OWN numbered pre-reg + user GO before any scored run, per standing law.

---

## 1. Where E-12 left us (one paragraph)

Three campaigns, three fired falsifiers: E-9 (budget split) 0/6, E-11 (untrained
generator-as-editor) 0/6, E-12 (trained editors C1 contrastive + C2 spec-conditioned)
0 solves everywhere on the transfer bar. What DID move: training tripled the untrained
L0-pass rate (C2 65.7% vs 22.4%) and widened the distinct-topology pools (C2 fills the
k=120 screen on two goals) — the D1 realization bottleneck moved. And a positive class
now exists (P1b banked 9 single-edit solves; edit log 128,479 rows). So the binding
constraint MOVED off "proposal quantity/validity" onto **selection** (the one unsized
`[0.5]^d` L1 probe) and **edit quality**.

## 2. The post-E-12 zero-sim margin audit (this session, analysis only — not landed)

Read the already-sized P3 survivor pools (`stage2.best_objective`; obj=1.0 is the
feasibility boundary, obj−1.0 = fractional violation vs threshold; feasible iff obj<0).
The 8 scored goals split into TWO regimes:

- **Near-miss cluster (5): GN78, G13, H2, G1'', G2''.** Best sized candidate within
  0.8–13.4% of threshold (G13 nf +0.016 dB, H2 nf +0.032 dB, GN78 nf +0.013 dB,
  G1'' gain −1.77 dB, G2'' s22 +1.34 dB). Lever = **selection / stage-2 budget** — the
  near-feasible topology exists in the sized pool but isn't converged (survivors got only
  ~120–131 stage-2 evals from a random CMA-ES start).
- **Far-miss cluster (3): G9 (ripple), G7'' (idd+gain), G12 (s11-match).** Best 63–71%
  violation (G12 s11 +10.67 dB). Lever = **edit quality / topology pool** — the
  L1-selected topologies are structurally wrong for these constraints at any sizing.

Sobering cross-check: on the two transfer goals with baselines (H2 held-out, GN78 fresh),
**arm b (hand primitives) beat both trained editors on margin.** The trained editors are
not yet earning their keep on transfer. Caveat: the audit measures margin on the SELECTED
(sized) set only — candidates the L1 screen rejected were never sized, so it cannot by
itself prove a good candidate was screened out (that needs re-sizing sims).

## 3. Two facts from the code trace that reframe the program

1. **Starting sizing is a dumb midpoint.** Optimization runs over normalized `[0,1]^d`,
   d≈8–16 (one knob/device). The L1 screen evals every candidate at the exact midpoint
   `x0=[0.5]^d` (one ngspice call, rank filter only). Stage-2 CMA-ES (`null_sizer.run_cmaes`,
   sigma0=0.3) then starts from a **fresh uniform-random mean** — NOT the midpoint, NOT
   anything learned. Main-line ZOAF is the same (quasi-random init). **There are NO
   per-archetype default sizings anywhere.** Only warm-start that exists: arm A / `curate`
   reuse a *stored* best_params for the same topology. → A learned `x0 = f(topology, spec)`
   regressor would be genuinely new and is exactly the user's "give a starting sizing for
   all components."
2. **The "what parts do what" model already exists but is unused in the editor loop.**
   `lna/critic_gnn.py` is a bipartite MPNN over the device-net graph → predicts S11/S21/
   Idd/NF margins for a spec, with optional per-device heads for **noise-contribution share
   and conduction region (off/weak/strong)**. Deep ensemble of 5, trained on-demand from
   the store. It is used as a pre-selection ranker in `lna/search.py` / `evolve_score.py`
   — but the E-11/E-12 editor loop ignores it and selects by the `[0.5]^d` probe. → Wiring
   the critic into selection = the concrete "capability-aware topology selection" lever.

## 4. Hardware & the bigger-model question (verified 2026-08-24)

- This RHEL box: **NO GPU**, torch CPU-only, 32 GB RAM, 28 cores. v7 (`ft_p5v7_v2.pth`,
  198 MB) is a **~12M-param GPT** (n_layer=6, n_head=6, n_embd=384, ctx=1024, vocab=1008;
  tokens = circuit-graph pins via Eulerian traversal; next-token CE). E-12 editors were
  fine-tuned from v7 on CPU in ~30 min — small-model finetunes are CPU-feasible.
- v7's own train script uses `--device cuda` → GPU access exists off-box. **User confirmed
  2026-08-24: cloud GPU on demand.**
- **Strategy call (recommended, honest): do NOT spend GPU on a bigger generator.** E-12
  evidence says generation isn't the bottleneck — v7 at 12M already over-produces valid
  topologies; selection and starting-sizing are broken. A bigger LLM makes more haystack.
  Circuits are graphs, not text: the "engineer" you want (learn what parts do → give
  starting sizings) is best served by a **scaled GNN critic + a sizing-regression head**,
  both small, both CPU-runnable for inference, both trainable on one cloud GPU. Pattern:
  **bank data locally (CPU, free), train judgment models on cloud GPU periodically, deploy
  them into the local loop.**

## 5. The levers (each its own pre-reg + GO)

- **E-13a — budget/selection concentration on the near-miss 5.** Matched-TOTAL m-sweep
  (fewer survivors, more stage-2 evals each) to (a) try to convert the near-misses and
  (b) DISAMBIGUATE budget-starvation from bad-screening: if concentrating budget on the
  top-L1-screened survivor helps → budget lever; if it HURTS vs spreading → the `[0.5]^d`
  screen is misranking → selection lever. Cheapest run, no new model, likely first scored
  solve. **Pre-reg: E13A-BUDGET.md (this session). GO'd by user 2026-08-24.**
- **E-13c — learned starting-sizing regressor.** Train `x0 = f(topology, spec)` on the
  store's `(topology, spec) → best_params` pairs (thousands of labels already exist);
  warm-start optimization from it instead of the midpoint. Directly attacks the near-miss
  budget waste at its root and IS the user's "starting sizing for all components." Small
  GNN/regressor; cloud-GPU-trainable, CPU-inference. NEEDS OWN PRE-REG + GO.
- **E-13b — critic-as-selector.** Replace the `[0.5]^d` L1 screen with (scaled) GNN-critic
  ranking; this is the capability-aware topology selection for the far-miss cluster
  ("don't pick stupid topologies"). Note E-7 arm G tried critic-as-AIM and it didn't move
  things — but that was before training widened the pool, i.e. before there was anything
  worth selecting among; worth re-testing as a SCREEN. NEEDS OWN PRE-REG + GO.

## 6. The "engineer model" vision, made concrete

The user's target — "learn from all circuits to understand what parts do what for what
topology, then assist by giving a starting sizing for all components" — decomposes into
two trainable models, both graph-based, both cloud-GPU-trainable / CPU-inference:

1. **Capability critic (scale up `critic_gnn.py`):** (topology graph, spec) → per-metric
   margins + per-device roles (noise share, inversion region). This is the "what parts do
   what" model; it already partly exists. Scaling it on the full store is the high-value
   GPU spend. Feeds E-13b selection.
2. **Sizing regressor (new):** (topology graph, spec) → per-component starting `x0`.
   Trained on every sized circuit in the store. Feeds E-13c warm-start.

Neither needs to be large. Together they are the shortest path to a system that behaves
like an engineer (picks a spec-appropriate topology, proposes sensible component values)
rather than a search that got luckier. Sequencing/priority = future user ruling.

## 7. Standing governance (unchanged)

Pre-registration + falsifier before any scored run; adopt-only-if-better; goldens GREEN
before/after every landing; engineer never writes under `lna/` (imports only); append-only
stores + edit log; two-line branch law; user rulings for any spec/protocol/budget change.
Budget *re-allocation at matched total* (E-13a) is an agent call; budget *widening* is not.

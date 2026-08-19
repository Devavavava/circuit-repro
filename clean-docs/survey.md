# SURVEY — nine AI-for-analog-design systems, in plain terms

*Clean version of `lna/SURVEY-AI-CIRCUIT-DESIGN.md`. That file is a reference document
compiled from primary sources (papers + code), one research agent per system, with
anything unverifiable flagged. It's in three parts: per-system notes, a cross-cutting
synthesis, and conclusions for building such a system. This is the readable summary; go
to the original for the per-system detail and citations.*

## Why it exists

Before betting on more architecture, the project surveyed the field to see what others
had actually built and measured. The short version: **the field is full of optimizers**,
and the gaps it *doesn't* cover became the argument for the engineer line.

## Part 1 — the nine systems (one line each)

- **AstRL** (Berkeley, 2026) — RL that *builds* transistor topologies (no sizing) with
  symmetry-aware moves and action masking → 100% valid netlists by construction. Strong
  on a comparator, weak on a ring oscillator (beaten there by an off-the-shelf GPT-5).
- **AutoCircuit-RL** (IBM, 2025) — an LLM generates power-converter topologies from
  natural-language prompts, refined with a surrogate reward. Works within one narrow
  family.
- **AnalogGym** (Fudan, 2024) — a sizing benchmark. Important finding it enables:
  constrained Bayesian optimization beats GNN-RL by ~**60×** in simulation count.
  Has **no RF** (no S-parameters, no noise-with-source-impedance, no two-tone).
- **DynaOpt** (TU Delft, 2020) — surrogate-the-reward sizing; schematic→post-layout
  transfer at ~300× savings.
- **Domain-knowledge DRL / RoSE** (Cao/Zhang) — the cleanest measurement that domain
  knowledge (full topology graph with supply/bias nodes, operating-point features) is
  worth ~10–15 accuracy points; a spec-conditioned policy answers new targets in ~20
  steps.
- **Krylov et al.** (ICML 2023) — plain supervised regression matches or beats RL at
  10–100× less data, *if* you construct the dataset right. The model class barely
  matters; the data transformation is everything.
- **AlphaChip** (Google) — RL for chip floorplanning; the cautionary tale on evaluation
  hygiene (proxy-vs-truth correlation collapses among the good solutions).
- **The AlphaDev/PrefixRL/CktGNN cluster** — search over cheap-and-exact evaluators
  (truth tables, unit tests) supports millions of rollouts; analog SPICE can't.
- **ORACLE** (Utah, 2026) — an LLM shaping the search space; its own tables show the
  non-LLM variant wins.

## Part 2 — the cross-cutting lessons (the 12 syntheses, condensed)

1. **Evaluation cost decides the algorithm.** Cheap+exact → massive search. Expensive
   (SPICE) → supervised or model-based methods, and a **fidelity ladder** (cheap
   analyses inner, expensive as an outer gate). Train-cheap/deploy-accurate works.
2. **For one-off sizing, RL is the wrong default** — it loses to Bayesian optimization
   by 10–100×. RL only pays when a spec-conditioned policy is reused across many targets.
3. **The reward function is solved** — everyone converged on the same clipped symmetric
   normalized deficit. Don't innovate there. (This program already uses it.)
4. **Validity must come from construction** (masking, grammar, repair), never from a
   penalty. Systems that "hope the reward teaches validity" top out below ~83%.
5. **Put behavior in the state, not just structure** — operating point, truth tables,
   executed registers. Semantics-in-state beat syntax-only everywhere it was tried.
6. **Domain knowledge is worth ~10–15 points and is cheap** — full graphs with rails as
   nodes, symmetry actions, motif libraries, corners in the reward.
7. **Supervised learning carries most of the load; RL/search is a refinement.** Learn
   the manifold supervised, then optimize on it.
8. **Surrogates work, with two rules:** surrogate the *reward* for one-shot tasks, and
   if a policy optimizes against a learned model, the model must carry **uncertainty**
   and be re-anchored to truth *on the current frontier* (proxy-truth correlation
   collapses among elites).
9. **LLMs have three real roles — none of them "the designer":** generative prior,
   action veto, and candidate proposer. Output validity is always externally checked. A
   frontier LLM out of the box is a baseline you must run first.
10. **The evaluation harness is the real asset** — templated netlists, one-call
    multi-instance testbenches, in-process sweeps, finite worst-case values on failure,
    version-pinned simulators. Not research; it decides throughput and half the
    correctness.
11. **Evaluation hygiene decides whether results are believed** — compute-matched tuned
    baselines, published variance, proxy validity shown where the optimizer lives, and a
    **no-learning null** in every comparison. Most analog papers fail this bar.
12. **Generalization today is spec-conditioning + encoder transfer, not foundation
    models.** One policy across circuit families and zero-shot cross-family are
    demonstrated *nowhere*.

## Part 3 — the seven conclusions for building such a system

1. **Split sizing from topology** — different problems, different winning methods.
2. **Build the harness before the learner** — throughput and half the correctness live
   there.
3. **Adopt the convergent reward; don't innovate there.**
4. **Spend novelty budget on representation and actions, not the optimizer** — the
   optimizers are commodities, and the fanciest one here lost to the simplest baseline
   more than once.
5. **Data construction beats model choice** — Krylov's feasible-direction relaxation +
   consistent relabeling is the single most transferable trick.
6. **A model inside an optimization loop needs uncertainty and grounding.**
7. **Run the cheap nulls first, always** — multiple purpose-built systems here are beaten
   by a random search or an untuned baseline on at least one task, and only the ones that
   ran the nulls know it.

## How this fed the project

The survey confirmed the reward is solved, validated this program's own **no-learning
null** finding (a grammar generator beating the trained one on the paper metrics), and
showed that two other groups had independently converged on the same "autonomous analog
engineer" shape this program already had. What set this program apart wasn't the loop —
it was the **golden-validated RF harness, frozen protocols with null hypotheses, and a
long verified decision trajectory.** That reframing is what launched the engineer line.

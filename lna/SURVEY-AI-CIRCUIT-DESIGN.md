# Survey: nine AI-for-analog-circuit-design systems — construction notes and synthesis

*Compiled 2026-08-13 from primary sources (arXiv full texts, GitHub repos, code files),
one research agent per system. Facts the agents could not verify against a primary
source are marked UNVERIFIED. This is a reference document: Part 1 records how each
system was actually built; Part 2 is the cross-cutting synthesis; Part 3 is the set of
conclusions I'd draw for building a similar system.*

---

## Part 1 — Per-system construction notes

### 1. AstRL (UC Berkeley, arXiv:2602.12402, Feb 2026)

**Task**: transistor-level *topology synthesis* (no sizing — unit-sized devices), Sky130.
Three tasks trained separately: ring oscillator, StrongARM-class comparator, OTA.

- **Representation**: partial circuit as a graph; node types = {active, passive, generic
  net, special net (supply/gnd/IO)}; edge attributes encode which device *terminals*
  (D/S/G; P+/P−) an edge connects. State = the partially built graph.
- **Action space**: discrete, factored, autoregressive 5-tuple per step:
  (source node, target node [existing or new from scaffold list], edge type,
  addition type, terminate). *Addition type* is the key inductive bias — 5 "symmetric
  modifiers" that mirror an action across the supply–ground symmetry axis, so
  differential structure is preserved by construction and trajectory depth halves.
  **Prefix-conditional action masking** zeroes infeasible sub-actions; violations are
  no-ops with a −2 penalty. Structural rules (every terminal on exactly one net, no
  device-to-device shorts) are environment logic → **100% netlist validity by construction**.
- **Algorithm**: PPO + behavioral cloning, jointly: L = L_PPO + λ₀·λ₁^k·BC (BC influence
  exponentially annealed). Policy = 3-layer GINE (edge-featured GIN), 64-dim, five MLP
  heads, ~244K params total. BC pretraining on 1,172 circuits filtered from the
  AnalogGenie dataset; per-task expert designs (e.g. 5T-OTA variants) during RL.
- **Simulator**: real SPICE in the loop at episode termination (engine never named);
  ≤16 parallel sim jobs, 1 GPU/task. Simulation dominates runtime; iterations get
  ~5–6× slower as more designs become simulatable. Wall-clock: 4.6–11.4 *days* to
  convergence per task.
- **Reward**: r = r_validity (−2/step) + r_similarity (±1 per step from a *fixed*
  discriminator trained once on expert subgraphs vs pretrained-policy rollouts — GAIL
  flavor without adversarial co-training) + terminal tiered domain reward:
  −2 structurally invalid / +3 netlist-valid-but-sim-fails / +30 simulates /
  +15·per-spec normalized score / +10 if all specs met. Unified per-spec shapes for
  match/min/max targets (e.g. maximize: (v−p)/(v+p)).
- **No surrogates** — explicit anti-surrogate stance; every performance number is SPICE.
- **Results**: 100/99.2/99.2% netlist/sim/spec on comparator; OTA 65.2% spec; RO only
  13.6% spec — *beaten there by AnalogCoder with a GPT-5 backend (20%)*. Ablations:
  remove masking → collapse to ~0; remove symmetric modifiers → OTA spec 0%;
  discriminator/BC help RO+comparator but *hurt* OTA spec fulfillment.
- **Caveats**: fixed specs per task (not spec-conditioned), no sizing, no code released,
  no PPO hyperparameters published.

### 2. AutoCircuit-RL (IBM, ICML 2025, arXiv:2506.03122)

**Task**: power-converter *topology generation* from natural-language constraint prompts
(4–10 components, fixed component values, duty cycle emitted with the netlist). No sizing.

- **Representation**: circuit serialized as "incident encoding" text — a list of
  [component, node1, node2] triples — generated token-by-token by a fine-tuned LLM
  (GPT-Neo-2.7B → Llama-3-8B; Llama-3 best).
- **Pipeline**: (1) SFT on ~100k random-search-generated netlists, each labeled by
  NGSpice at 5 duty cycles; training data stratified 0.1/0.25/0.25/0.4 toward
  high-quality circuits. (2) PPO with **surrogate-only reward** — NGSpice never runs
  in the RL loop. Three RoBERTa reward models: validity classifier (92% F1),
  binned efficiency estimator (83% macro-F1), Vout regressor (MSE 8e-3).
  Reward: −1 if predicted invalid; +1 if constraint met; else predicted efficiency
  (dense shaping). KL anchor to the SFT model. (3) "Iterative adaptation":
  nucleus-sample generations, keep predicted-efficiency > 0.7, re-train; 3–5 rounds.
- **Results**: ~75% validity / ~72% simulator-scored efficiency at 4–5 components,
  ~80.7% overall constraint success; surrogate-vs-simulator scoring gap only 1–2 pts.
  Generalizes to 6–10-component circuits with ~1,000 examples (58–65% success).
  2.7 s per design. **No BO/GA head-to-head baseline.** No code released.
- **Transferable core**: surrogate reward models make PPO cheap; double-scoring
  (classifier AND simulator) exposes surrogate bias; KL-to-SFT prevents reward hacking.

### 3. AnalogGym (Fudan et al., ICCAD 2024, github.com/CODA-Team/AnalogGym)

**What it is**: an open benchmark/testing suite for analog sizing — ~30 topologies
(20 multi-stage op-amps, LDOs, PTAT front-ends, voltage refs, charge pump/PLL),
ngspice+Spectre netlists, SKY130 PDK bundled for amps/LDOs.

- **Parameterization**: three-file decoupling — testbench `.cir` includes (a) frozen
  `.subckt` netlist, (b) a design-variables file of `.PARAM` lines (the only thing an
  optimizer touches), (c) PDK corner file. **Matching ratios are baked into the
  netlist** (devices scale a shared group parameter, `m='4*…'`), so optimizers cannot
  break current mirrors. Semantic variable names encode function (gm1, BIASCM, LOAD2).
- **Interfaces**: a Gymnasium env (DDPG + relational-GCN example, observation = per-
  transistor OP vector (id, gm, gds, vth, vdsat, vds, vgs) z-scored from ~100 random
  sims); a plain callable objective; a BBO wrapper with per-eval sandbox dirs.
- **Testbench engineering worth stealing**: 5 DUT instances in ONE netlist (open-loop
  gain/GBW/PM via 1 T-H/1 T-F feedback, CMRR, PSRR±, DC/TC/Vos) → one ngspice call
  measures everything; `.control` `alter` loops sweep load/supply in-process; `wrdata`
  per-measurement ASCII; `.meas` "failed" tokens replaced by directional worst-case
  defaults so optimizers see finite bad values, not NaN; pre-step oscillation check;
  ngspice ≥ 42 pinned (41 gives wrong DC sweeps).
- **Reward/objective conventions**: RL reward = Σ per-spec min((t−v)/(t+v), 0), 0 ⇔ all
  specs met; FoM penalty terms as max(1, ratio)⁻¹ (penalize only degradation).
- **Benchmark result that matters**: with a 1000-sim budget, constrained-BO (cVTSBO)
  reached FoM 4.2 in ~117 evaluations / 8.8 min; GCN+RL needed 6,842 evals / 158 min
  for FoM 2.5. **BO crushes RL on single-circuit, single-target sizing.**
- **Caveats**: three inconsistent calling conventions, only amps+LDOs fully open;
  known issue: shipped LDO default variables give an invalid operating point.

### 4. DynaOpt (TU Delft, NeurIPS 2020 ML4Eng WS, arXiv:2011.07665)

**Task**: sizing of the AutoCkt two-stage op-amp (7 params, discrete 100-value grids),
ngspice, 45 nm BSIM.

- **Key move**: the problem is *stateless/one-shot*, so the world model collapses to a
  **reward model** ρ(a): a tiny MLP (3×16) regressing action→reward. Dyna loop: 100 real
  sims → refit ρ on the buffer → N_model imagined REINFORCE updates → repeat 5 cycles.
  Policy = GAN-style noise-conditioned generator (per-parameter softmax over the grid),
  so it learns a *distribution* over feasible sizings, not a point.
- **Reward**: Σᵢ clipped normalized deficits, bounded [−1, 0] — bounded *specifically
  so the surrogate's regression targets are well-conditioned*.
- **Numbers**: ~500 real sims ≈ 20,000-sim model-free performance; schematic→post-layout
  transfer via the pretrained reward model: 100 sims vs 30,000 from scratch (~300×).
- **Gap**: deterministic surrogate trusted unconditionally between refits — no
  uncertainty, no exploitation defense. The 2024 KU Leuven MBTD3 paper (Ahmadzadeh &
  Gielen) is "DynaOpt done right": PETS-style probabilistic NN *ensemble* predicting
  next-state distributions, short branched rollouts (k grown 1→5) from real states,
  per-step least-uncertain-model selection, mixed real/synthetic update batches,
  feasibility-first FoM (optimize power/area only after constraints met, +0.3 bonus),
  and "optimal neighborhood exploration" (ensemble-screened local perturbations, 1-sim
  verification each). 2–3.4× fewer sims than TD3 on 20–66-parameter circuits.

### 5. Domain-knowledge DRL (Cao/Zhang et al., AAAI-WS + DAC 2022; RoSE-Opt TCAD 2024; github.com/xz-group/RoSE)

**Task**: sizing (P2S), fixed topology; two-stage op-amp (45 nm CMOS), GaN RF PA;
RoSE-Opt adds 4 op-amps on real GlobalFoundries PDKs with PVT + parasitics.

- **"Domain knowledge" concretely**: (1) full topology graph *including supply/ground/
  bias nodes as graph nodes*; (2) dynamic device parameters as node features (updated
  each step); (3) a separate FCNN branch over the *target spec vector* to learn spec
  couplings; (4) sequential increment/decrement workflow mimicking designers;
  (RoSE-Opt) BO warm-start + 16 PVT corners in the reward. No symmetry constraints,
  no design equations, no gm/ID.
- **Action space**: discrete factored — per parameter {−Δ, 0, +Δ}, an M×3 softmax
  matrix, all parameters updated simultaneously each step.
- **Algorithm**: PPO; GAT+FC beats GCN+FC beats FCNN-only; GCN sometimes *diverges*
  with dynamic node features. RoSE-Opt algorithm study: PPO-discrete > DDPG/PPO-
  continuous for reliability; **training reward is a misleading metric — judge by
  deployment accuracy/steps**.
- **Reward** (the field's canonical form): r = Σⱼ min((gⱼ−g*ⱼ)/(gⱼ+g*ⱼ), 0), terminal
  bonus R=10 when all specs met. The min(·,0) clip is deliberate anti-overshoot
  shaping. PVT variant: mean over 16 corners, bonus only if all corners pass; training
  on nominal corners *converges in training but diverges at full-PVT deployment*.
- **Simulator**: Spectre AC/DC per step (~tens of ms). RF PA: ADS harmonic balance
  ~1 min → too slow → **train in a cheap DC-sim environment (~1 s, ±10% error), deploy
  against HB** ("environment transfer"). Spectre APS parallel corners at ~0.17×
  overhead → ~14× effective sampling efficiency.
- **Results**: 99% deployment success on 200 random spec goals (GAT-FC), 21 mean
  deployment steps vs BO 86 / GA 370; ~1.5× more efficient than AutoCkt/GCN-RL.
  Knowledge ablation ladder: no topology (AutoCkt) 92–93% → partial topology, static
  features (GCN-RL) 84–87% → full graph + dynamic features 98–99%.
  RoSE-Opt: BO warm start saves 2.3–3.5×; parasitic closure via per-spec discount
  factors (s_post/s_pre from one extraction, re-run against inflated targets, ≤2 rounds).
- **Limits**: one agent per topology; no cross-circuit transfer; ~10⁶ sims to train.

### 6. Learning to Design Analog Circuits to Meet Threshold Specifications (Krylov et al., ICML 2023, github.com/indylab/Circuit-Synthesis)

**Task**: inverse design spec→sizing, supervised, per-topology; 7 circuits incl. an LNA
(Ls, Ld, Lg, W → Gt, S11, NF); ngspice.

- **The framing insight**: users have *threshold* criteria, not exact target vectors —
  and picking a feasible exact vector is as hard as designing. So train on
  (relaxed-spec, sizing) pairs.
- **Dataset construction is the whole contribution**:
  1. Grid-sweep simulate: 616–4,096 points per circuit (sweeps run *inside* ngspice
     `.control` loops — hundreds of points per process, 8-way multiprocessed).
  2. Perturb each simulated performance y in the *feasible* direction:
     ỹᵢ = (1 − 0.2·λᵢ·uᵢ)·yᵢ, λ = metric direction, u ~ U[0,1] — so the generating
     circuit always satisfies the query (guaranteed-feasible label).
  3. **Lexicographic argmax relabeling**: pair each threshold query with the single
     lexicographically-best circuit in the dataset that dominates it — making the
     inverse map single-valued. Without this (naive m-fold relaxation à la Lourenço),
     similar queries map to wildly different sizings and learning fails
     (mixer: 0.995 vs 0.32 success).
- **Model**: 7-layer ReLU MLP (200-300-500-500-300-200), L1 loss on [−1,1]-normalized
  vectors, Adam. Random forest and a nearest-neighbor lookup perform the same —
  **dataset construction, not model class, is what matters**.
- **Inference**: one forward pass; no search or refinement.
- **Eval metric**: asymmetric hinge — overshoot in the good direction counts zero;
  success = all metrics within margin. >90% success at 5% margin on 6/7 circuits with
  ~10–100× less data than RL prior work (AutoCkt: 5,500–40,000 sims); 80%+ success
  even at 5% of the data (~30–200 sims). Metric-priority reordering steers where on
  the Pareto front predictions land (+0.84 dB gain for 0.53 dB worse S11 on the LNA).
- **Limits**: in-distribution specs only (explicitly); 2–4 free parameters; VCO
  (autonomous circuit) unsolved by every method tested.

### 7. AlphaChip / Circuit Training (Google, Nature 2021 + 2024 addendum, github.com/google-research/circuit_training)

**Task**: macro placement (digital) — included as the methodology reference for
sequential construction + pretraining + proxy reward at scale.

- **MDP**: one macro placed per step (fixed heuristic order: descending size,
  topological tiebreak — ordering deliberately *not* learned); after all macros,
  a classical force-directed pass places clustered std cells; only then is reward
  computed. The learned part is kept small; the easy continuous subproblem goes to a
  classical optimizer inside the evaluation.
- **State**: edge-centric GNN (update edges from endpoint features + learned edge
  weight, nodes = mean of incident edges; graph vector = mean-pooled edges) ⊕ current-
  node embedding ⊕ metadata FCNN (routing capacities, counts, canvas, node); padded to
  fixed max sizes with a netlist_index so one model trains across many designs.
- **Actions**: canvas grid ≤128×128; **hard constraints as binary action masks**
  (density ≤ 0.6, blockages); all-zero mask → episode terminates at −4.0.
- **Reward**: terminal-only, proxy: −HPWL − 0.01·congestion − 0.01·density, all
  normalized 0–1; congestion = mean of top-10% most-congested cells. Rationale stated:
  RL needs 10,000s of episodes → reward must run in milliseconds and *correlate* with
  the true (hours-long EDA) objective.
- **The central claim**: supervised pretraining first (Edge-GNN regresses
  wirelength+congestion on 10k auto-generated placements — labels free from the proxy;
  this doubled as architecture selection), then RL pretraining across ≤20 diverse real
  blocks → zero-shot placement in <1 s, fine-tune 6 h beats from-scratch 48 h, and
  quality scales monotonically with corpus size (2→5→20 blocks).
- **Systems**: ~512 CPU experience collectors + 16 GPU learners (Nature-era); open
  source = Reverb replay server + N collect jobs + MirroredStrategy learner; global
  batch ~1024 is what matters for quality.
- **Controversy lessons** (Cheng/Kahng vs Google): replications that skip pretraining
  and use 20× fewer collectors test a *different method*; proxy-vs-truth Kendall τ was
  0.402 for routed wirelength but ~0.05–0.09 for timing, and **correlation collapses in
  the elite regime** — the proxy ranks bad-vs-good, not good-vs-great; publish
  checkpoints, seeds, variance, and matched-compute baselines or expect a decade of
  dispute.

### 8. AlphaDev / PrefixRL / CircuitVAE / ShortCircuit / CktGNN / GCN-RL (the construction-and-search cluster)

- **AlphaDev** (DeepMind, Nature 2023): AlphaZero over an "AssemblyGame" — state =
  ⟨program so far, **CPU register/memory state after executing it on test inputs**⟩,
  i.e. *semantics in the state, not just syntax*. Dual value heads: correctness +
  latency. Latency measured on real machines, 5th percentile over 10k runs (noise is
  one-sided); program *length* used as a cheap proxy when correlated. Six pruning
  rules canonicalize the action space. 512 actors, ≤2 days, results merged into
  LLVM libc++.
- **PrefixRL** (NVIDIA, DAC 2021): prefix-adder optimization as *iterative
  modification* (add/delete nodes on an N×N grid tensor, fully-convolutional double
  DQN, γ=0.75 deliberately myopic). **Legalization-by-repair** after every action.
  Dense incremental reward = Δ(post-synthesis area/delay) from real physical synthesis
  in the loop (11–36 s/eval; 192 async CPU synthesis workers per GPU + state caching).
  Weight-conditioned agent sweep (15 agents, w ∈ [0.1, 0.99]) traces the Pareto front.
  **Key negative result**: agents trained on analytical proxies beat SA *on the proxy*
  but their circuits don't synthesize well — the proxy optimum is off the real front.
  Deployed: ~13,000 instances in NVIDIA Hopper.
- **CircuitVAE** (NVIDIA, DAC 2024) — *the successor that replaced RL*: CNN-VAE over
  the same grid + a jointly-trained cost predictor; optimization = gradient descent in
  latent space on predicted cost, prior-regularized; candidates decoded → legalized →
  synthesized. Beats PrefixRL's cost with **~3.3× fewer synthesis evaluations** on
  1 GPU + 24 CPUs. Explicit finding: "RL is hindered by the difficulty of searching
  directly in the input space."
- **ShortCircuit** (Huawei, arXiv:2408.09858): AlphaZero for truth-table→AIG synthesis.
  Nodes represented *by their truth tables* (behavior, not structure) — equivalence
  classes collapse automatically. SL pretrain on 1.8M cuts from EPFL benchmarks
  (random exploration would never find a correct circuit), then AlphaZero fine-tune
  with only 8 MCTS sims/action; policy = the final self-attention map itself
  (handles a growing quadratic action space); failed episodes shaped by Hamming
  distance to target. 98% success, 18.6% smaller than ABC.
- **CktGNN** (ICLR 2023): op-amp topology+sizing co-design via a two-level GNN VAE over
  a hand-designed **24-subgraph basis** (known-good analog motifs), then sparse-GP BO
  in latent space (batch EI, 50/batch, 10 rounds). 98.9% valid decodes; ships the OCB
  benchmark (10k simulated op-amps). Cost: behavioral-level (VCCS) evaluation — a
  sim-to-transistor gap; the basis caps novelty.
- **GCN-RL** (MIT, DAC 2020): sizing with DDPG over netlist-GCN actor/critic;
  the transferable finding: **warm-starting across technology nodes and related
  topologies reaches target FoM in ~300 steps where scratch needs 10⁴** — the graph
  encoder, not the RL, carries the transfer.

### 9. ORACLE (U. Utah, arXiv:2608.04999, Aug 2026 — under review)

**Task**: multi-objective sizing of two op-amp topologies (7/10 params, discrete grids,
45 nm), built literally on the AutoCkt gym env.

- **Core**: preference-conditioned vector-valued double DQN — Q(s, a, ω) ∈ R⁴, reward
  kept as a *vector* of per-objective normalized gaps (never scalarized during
  learning); at inference, 10 fixed preference vectors ω generate a 10-solution
  trade-off family from **one trained model**, no retraining. Action = per-parameter
  {−1, 0, +2} grid steps. State = [current specs, target specs, current params].
- **LLM's role is narrow**: local Llama 3.2 (Ollama), called every step with a
  4-category qualitative spec-gap summary ("NF far below target…"), returns a binary
  action mask vetoing "globally harmful" moves (e.g. block upsizing when Ibias over
  target). Never sees a netlist, never proposes values.
- **Results**: 99.9%+ pass rate over 2,000 random spec targets, minutes not hours
  (2.4–3.2 min vs AutoCkt 85–338 min, BO baselines 60–300 min). **But the paper's own
  tables show the LLM is the least essential part**: the normalized-weighted variant
  *without* the LLM is fastest AND best-FoM on both circuits; on the harder 3-stage
  OTA the LLM mask lowers average FoM and adds latency. Sparsity of its Pareto sets is
  *worse* than the BO baselines. Hyperparameters, prompts, engine undisclosed;
  anonymized repo only; no venue yet.

---

## Part 2 — Cross-cutting synthesis

**S1. Evaluation cost dictates the algorithm family.** Cheap-and-exact evaluators
(truth tables, unit tests) support AlphaZero/MCTS with millions of rollouts (AlphaDev,
ShortCircuit). Expensive evaluators (SPICE seconds, synthesis tens of seconds) forced
either async-worker RL (PrefixRL, AlphaChip) — and even there, latent-space
surrogate search later beat the RL 3.3× on sample efficiency (CircuitVAE) — or
supervised/model-based methods. Analog SPICE sits in the expensive regime, with a
crucial nuance: AC/DC op-amp evals are only ~10 ms–2.5 s, while transient/HB/corners
are 10–100× worse. The design consequence is a **fidelity ladder**, not a single
simulator: cheap analyses in the inner loop, expensive analyses as an outer gate —
and two groups showed *train-cheap/deploy-accurate* works across that gap
(Cao DC→harmonic-balance; DynaOpt schematic→post-layout at ~300× savings).

**S2. For single-circuit, single-target sizing, RL is the wrong default.** The
head-to-head evidence is consistent: AnalogGym's benchmark has constrained BO at
FoM 4.2 in ~117 evaluations vs GNN-RL's 2.5 in 6,842; Krylov's supervised inverse
model needs 30–4,000 sims where AutoCkt-style RL needs 5,500–40,000; CircuitVAE
replaced its own company's RL. **RL earns its cost only when amortized**: a
spec-conditioned policy answers *new* spec targets in ~20–30 simulation steps forever
after (Cao: 99% success on 200 random goals, 21 steps each) — the product is the
reusable policy, not one design.

**S3. The reward function is convergent across the field** — treat it as a solved
sub-problem. Per-spec symmetric normalized deficit, clipped at zero, summed:
r = Σᵢ min((vᵢ−v*ᵢ)/(vᵢ+v*ᵢ), 0) (signs flipped for minimize-metrics), plus a large
terminal bonus when everything passes. It appears independently in Cao/RoSE, AutoCkt,
DynaOpt, MBTD3, AnalogGym, and (in match/min/max form) AstRL. Its properties are the
point: bounded, scale-free across units, *anti-overshoot* (no credit for exceeding a
met spec — effort flows to unmet specs), and well-conditioned as a regression target
if a surrogate ever has to learn it. Two refinements worth carrying: feasibility-first
staging (optimize FoM only after constraints are met — MBTD3), and keeping the reward
*vector-valued* with preference conditioning when a trade-off family is wanted (ORACLE,
PrefixRL's weight sweep).

**S4. Validity must come from construction, never from penalty.** Every system that
generates structure enforces legality mechanically: prefix-conditional action masking
(AstRL — removing it collapses everything to 0%), density masks (AlphaChip),
legalization-by-repair (PrefixRL), motif grammars (CktGNN), pruning rules (AlphaDev).
Systems that instead *hope the reward teaches validity* (LLM generation without
masking) top out at 53–83% validity. The environment, not the agent, owns legality.

**S5. Put simulated behavior in the state, not just structure.** AlphaDev's state
carries the registers *after executing* the partial program; ShortCircuit's nodes are
their truth tables; Cao feeds current simulated specs each step; AnalogGym's RL
observation is the per-transistor operating point (id, gm, gds, vth, vdsat, vds, vgs,
z-scored). Everywhere it was tried, semantics-in-state beat syntax-only. The analog
translation: the DC operating point and small-signal response of the current design
are state features, and (per ShortCircuit) behavior-based representations collapse
structural equivalence classes for free.

**S6. Domain knowledge is worth ~10–15 accuracy points and is cheap to inject.**
Cao's ablation ladder is the cleanest measurement: spec-vector-only RL 92–93% →
partial topology graph 84–87% (worse!) → full graph including supply/bias nodes with
dynamic features 98–99%. AstRL's symmetry macro-actions take OTA spec fulfillment from
0% to 65%. CktGNN's motif basis buys 99% valid decodes at the cost of bounded novelty.
The recurring forms: complete topology graphs (with rails as nodes), symmetry-aware
actions, motif libraries, matching baked into netlists (AnalogGym), BO warm starts,
and PVT corners inside the reward (training on nominal corners *diverges at deployment*).

**S7. Supervised learning carries most of the load; RL/search is a refinement
operator.** Krylov: with the right dataset construction, plain L1 regression matches or
beats RL at 10–100× less data — and model class doesn't matter (MLP ≈ random forest ≈
nearest-neighbor lookup); the dataset transformation is everything (threshold-relaxed
queries + lexicographic-argmax relabeling to make the inverse map single-valued).
ShortCircuit and AstRL both *require* behavioral cloning on real designs before RL —
random exploration never finds a working circuit. AlphaChip's encoder was discovered
by supervised reward-regression before any RL ran. AnalogGenie/AutoCircuit-RL pretrain
generatively then refine. The pattern: **learn the manifold supervised, then optimize
on it.**

**S8. Surrogates work, with two hard rules.** (a) *Surrogate the reward, not the
dynamics*, when the task is one-shot (DynaOpt's insight — the environment collapses to
f(a)→R); sequence-level reward models made AutoCircuit-RL's PPO simulator-free with
only a 1–2 pt surrogate-vs-simulator gap. (b) If a policy optimizes against a learned
model, the model must carry uncertainty: MBTD3's probabilistic ensembles, short
branched rollouts from real states, least-uncertain-model selection, and mixed
real/synthetic batches exist precisely because DynaOpt's deterministic
trusted-unconditionally surrogate invites exploitation. And the standing warning from
the digital side: **proxy-truth correlation collapses in the elite regime** (AlphaChip
τ≈0.05–0.09 vs timing among good solutions; PrefixRL's proxy-optimal adders don't
synthesize well). Audit the surrogate against ground truth *on the current Pareto
front*, not globally.

**S9. LLMs have three demonstrated roles, none of them "the designer."**
(1) Generative prior over topologies, fine-tuned then RL-refined with surrogate
rewards (AutoCircuit-RL) — works within one narrow circuit family; (2) zero-shot
action veto / search-space shaper (ORACLE, LEDRO) — measured weak: ORACLE's own tables
show its non-LLM variant wins; (3) candidate proposer inside BO's evaluation loop
(ADO-LLM). Meanwhile untuned AnalogCoder-with-GPT-5 already beats a purpose-built RL
system on one of its three tasks (RO spec fulfillment) — frontier-LLM priors are a
real baseline that must be run before concluding a bespoke system is worth it. In all
cases LLM output validity is enforced by external checkers, never assumed.

**S10. The evaluation harness is the real asset.** The reusable engineering across
every serious system: netlist templating with parameters as the only mutable surface
and matching ratios frozen in the netlist; multi-instance testbenches measuring
everything in one simulator call; in-process sweeps (hundreds of points per ngspice
invocation via `.control` loops); failed-measurement → finite directional worst-case
values (never NaN); oscillation/instability pre-checks; per-eval sandbox dirs keyed
for parallel dispatch; evaluation caching; async evaluator worker pools decoupled from
the learner (192 CPU workers/GPU in PrefixRL; hundreds of collectors in AlphaChip);
simulator version pinning as a correctness issue (ngspice 41 vs 42). None of this is
research; all of it determines throughput, and simulation time dominates every
system's wall-clock.

**S11. Evaluation hygiene decides whether results are believed.** The AlphaChip
controversy reduces to: pretraining and compute are part of the method; proxy validity
must be shown where the optimizer lives; checkpoints/seeds/variance must be published;
baselines must be strong, tuned, and compute-matched. The analog papers mostly fail
this bar — AutoCircuit-RL, AstRL, and Krylov run no BO/GA head-to-head; ORACLE's
sparsity loss is visible only in its own tables. AnalogGym's protocol (fixed sim
budget, 10 seeds, convergence curves, modeling-time accounted separately) is the
model to follow, and a **no-learning null hypothesis** (random/grid search, untuned
BO) belongs in every comparison.

**S12. Generalization today is spec-conditioning plus encoder transfer, not
foundation models.** What's demonstrated: policies conditioned on the target spec
generalize within the training spec range (99% on random in-range goals) and degrade
gracefully slightly outside it; graph encoders transfer across PDKs and related
topologies with ~30× fewer fine-tuning steps (GCN-RL); pretrain-on-many/fine-tune-
on-one scales monotonically with corpus diversity (AlphaChip's 2→5→20 blocks).
What's *not* demonstrated anywhere: one policy across circuit families, cross-family
zero-shot, or out-of-distribution spec extrapolation (Krylov explicitly declines it).

---

## Part 3 — Conclusions for building such a system

Drawn from the material above, deliberately architecture-agnostic:

1. **Split the problem the way the evidence splits.** Sizing and topology are
   different problems with different winning methods. Sizing: supervised inverse
   models + BO for one-offs; spec-conditioned RL only if many targets will amortize
   it; model-based (ensemble-surrogate) RL if simulation is the bottleneck. Topology:
   generative prior (SL/BC on real designs) + masked constructive search or latent
   optimization + simulator grounding. No system credibly does both at once at
   transistor level; the ones that try (CktGNN) pay with behavioral-level fidelity.

2. **Build the harness before the learner.** Every system's throughput and half its
   correctness live in the S10 list. A fast, cached, parallel, failure-hardened,
   version-pinned evaluator with a fidelity ladder (DC/AC → transient/HB → corners →
   parasitics) is a prerequisite, and the *train-cheap/deploy-accurate* transfer
   results mean the ladder is exploitable, not just a cost.

3. **Adopt the convergent reward and don't innovate there.** Clipped symmetric
   normalized deficits + all-pass bonus; feasibility before FoM; thresholds with free
   overshoot (Krylov's asymmetric metric) as the success criterion; vector rewards
   with preference conditioning only if a trade-off family is a deliverable.

4. **Spend novelty budget on representation and action design, not on the
   optimizer.** The measured wins are: rails-as-nodes complete graphs, operating-point
   features in the state, symmetry/motif macro-actions, masking. The optimizers
   themselves (PPO, DQN, BO, CMA-ES) are commodities, and the fanciest one in this
   survey lost to the simplest baseline more than once.

5. **Data construction beats model choice.** The single most transferable trick in the
   nine systems is Krylov's: relax specs in the feasible direction so labels are
   guaranteed-feasible, then relabel each query with one consistent (lexicographic-
   best) answer so the inverse map is learnable. Free augmentation with correct
   semantics; works with any regressor.

6. **If a learned model sits inside an optimization loop, it needs uncertainty and
   grounding.** Ensembles, short rollouts from real data, periodic real-simulator
   re-anchoring, and elite-regime correlation audits. A surrogate validated on average
   is not validated where the optimizer actually operates.

7. **Run the cheap nulls first, always.** Grid/random search, untuned BO, a lookup
   table over simulated data, and a frontier LLM out of the box. Multiple purpose-built
   systems in this survey are beaten by one of these on at least one task, and only
   the systems that ran the nulls know it.

---

## Appendix: primary sources

| System | Paper | Code |
|---|---|---|
| AstRL | arXiv:2602.12402 (Guo, Ho, Vladimirescu, Nikolić, UC Berkeley) | none |
| AutoCircuit-RL | arXiv:2506.03122 (ICML 2025, IBM) | none |
| AnalogGym | arXiv:2409.08534 (ICCAD 2024) | github.com/CODA-Team/AnalogGym |
| DynaOpt | arXiv:2011.07665 (NeurIPS-WS 2020, TU Delft) | none (env: github.com/ksettaluri6/AutoCkt) |
| MBTD3 (DynaOpt successor) | Ahmadzadeh & Gielen, DAC 2024 | none found |
| Domain-knowledge DRL | arXiv:2202.13185 / 2204.12948 (AAAI-WS/DAC 2022); RoSE-Opt arXiv:2407.19150 | github.com/xz-group/RoSE |
| Threshold specs | arXiv:2307.13861 (ICML 2023, UC Irvine) | github.com/indylab/Circuit-Synthesis |
| AlphaChip | Nature 594:207 (2021) + 2024 addendum; critiques arXiv:2302.11014, 2306.09633; rebuttal 2411.10053 | github.com/google-research/circuit_training |
| AlphaDev | Nature 618:257 (2023) | github.com/google-deepmind/alphadev |
| PrefixRL / CircuitVAE | arXiv:2205.07000 (DAC 2021) / 2406.09535 (DAC 2024) | none |
| ShortCircuit | arXiv:2408.09858 (Huawei) | none |
| CktGNN / OCB | arXiv:2308.16406 (ICLR 2023) | github.com/zehao-dong/CktGNN |
| GCN-RL | arXiv:2005.00406 (DAC 2020, MIT) | — |
| AnalogGenie | arXiv:2503.00205 (ICLR 2025) | github.com/xz-group/AnalogGenie |
| ORACLE | arXiv:2608.04999 (U. Utah, under review) | anonymous.4open.science/r/ORACLE-2026 |
| ADO-LLM | arXiv:2406.18770 (ICCAD 2024) | — |

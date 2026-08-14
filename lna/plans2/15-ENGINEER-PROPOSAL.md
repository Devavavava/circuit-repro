# 15-ENGINEER-PROPOSAL — post-survey answers and the next-phase decision queue

**Status:** PROPOSAL — written 2026-08-14 in response to the user's questions on the
stage-38 survey (`lna/SURVEY-AI-CIRCUIT-DESIGN.md`) and their ten-point
"autonomous analog engineer" sketch. Nothing here is adopted; §7 is the decision
queue. **Branch:** `lna-data`.
**Inputs:** the survey; JOURNEY §§25–38 + Current frontier; the live module set
(`datastore.py`, `surrogate.py`, `critic_gnn.py`, `loop.py`, `moves.py`,
`grammar_gen.py`, `iip3.py`, `corners.py`); two agent inspections of the user's
new sources (§2); the machine itself (Ryzen 7435HS 8C/16T, 15.8 GB RAM, RTX 3050).

---

## 1. Direct answers

### 1.1 Should we use AnalogGym's harness? (Part 1, Q1)

**Yes, but narrowly — as an external calibration set for the *sizer*, not as a
harness for this program's circuits, and not yet.**

- **What it's good for here.** AnalogGym's op-amps ship with published,
  budget-matched baselines (cVTSBO FoM 4.2 @ ~117 evals). Running our ZOAF/sizing
  stack on 2–3 of their amplifiers under their protocol is the only way to learn
  whether our sizer is state-of-the-art or merely adequate — an external null the
  program cannot generate internally (the grammar null covers the *generator*,
  nothing covers the *sizer*). Same move for quick bulk data if we ever train a
  cross-design sizing prior: their testbenches are free labeled-data factories.
- **What it cannot do.** It has no RF testbenches — no S-parameters, no NF-with-
  source-impedance, no two-tone. Nothing in it validates or accelerates the
  dhruva/GNSS work. Our harness is golden-validated against two independent
  engines (ngspice transient ↔ VACASK HB to 0.08 dB); theirs is not a superset,
  it's a different domain.
- **Already absorbed.** The survey's S10 testbench tricks (multi-DUT netlists,
  in-process `.control` sweeps, failed-`.meas` → directional worst-case, version
  pinning) are the reusable part, and most are already this program's practice.
- **Known sharp edges** if we do pick it up: three inconsistent calling
  conventions; the shipped LDO default variables give an invalid operating point.

**Verdict: adopt as the N3 external benchmark (§4.1), skip as infrastructure.**

### 1.2 Is the DynaOpt algorithm of application to us? (Part 1, Q2)

**The algorithm as published, no. Two of its patterns, yes — and one is aimed
straight at WP-LIN.**

- Its literal machinery (tiny reward-MLP + noise-conditioned REINFORCE generator
  over 7-param grids) is subsumed by what already exists here: WP-SURROGATE v0 is
  a *point-level metric-vector* surrogate — strictly more informative than a
  scalar reward model — and ZOAF is the optimizer.
- **Pattern 1 — surrogate transfer across the fidelity gap (their ~300×
  schematic→post-layout result; Cao's DC→HB "environment transfer").** Our exact
  gap is cheap OP/AC (~1 s) vs two-tone transient IIP3 (minutes). For WP-LIN:
  pretrain the surrogate on cheap-harness sweeps of candidate output
  stages/biases, add an **IIP3 head** fine-tuned on the few dozen two-tone points
  WP-IIP3 already produced plus a small designed sweep, and let it *propose*;
  every accepted point is verified with the real two-tone harness. Nothing lands
  on surrogate evidence (S8's elite-regime warning; the program's replay-fence
  culture already says this).
- **Pattern 2 — bounded, well-conditioned regression targets.** Their [−1, 0]
  reward bound existed *for the surrogate's sake*. Our margin vectors already
  comply; keep it that way when adding the IIP3 head (predict normalized margin,
  not raw dBm).
- If the surrogate ever steers more than a pre-gate, implement the MBTD3
  corrections, not DynaOpt's: probabilistic ensemble (critic v1 is already a
  5-seed deep ensemble — same recipe), short excursions from *real* simulated
  points only, mixed real/synthetic acceptance evidence.

### 1.3 Is the domain-knowledge DRL of application? Can it be extended? (Part 1, Q3)

**The DRL, no — the representation findings, yes, and the extension you'd make
is real and is already half-built here.**

- The RL itself needs ~10⁶ sims per topology and pays off only amortized over
  hundreds of spec targets (S2). On 8 cores, for one designated design point,
  it's the wrong tool. Skip it without regret.
- The paper's measured knowledge ladder (spec-only 92–93% → partial graph
  84–87% → **full graph with rails/bias as nodes + per-device dynamic features
  98–99%**) is the field's cleanest evidence for *what to put in the
  representation*. Our critic is a bipartite device↔net MPNN with
  spec-conditioning and ensemble uncertainty — structurally at the frontier —
  but its node features are static. The missing ingredient is exactly the one
  their ablation prices at ~10–15 points: **dynamic per-device operating-point
  features**, and `op_points.jsonl` (WP-OBSERVE, validated, nearly empty) is the
  waiting supply line.
- **The extension beyond the paper:** they hard-code *static* domain knowledge;
  this program has begun to *learn* it and act on it. WP-DIAGHEADS gives the
  critic per-device noise-share/OP-region attribution; their action space
  (uniform per-parameter ±Δ) has no idea *where* to act, and neither does
  `evolve.py` (uniform over 17 move classes — 13-WP-DIAGHEADS §0). Wiring
  diagnosis heads → move-class/site priors is a genuine extension of their line
  of work: dynamic, learned, per-device knowledge steering a discrete editor.
  Stage 29's finding (pointing costs ranking) says to keep the ranker and the
  pointer as separate heads or separate models, not one compromised backbone.
- Their PVT lesson (train-nominal ⇒ diverge-at-deployment) is the same lesson as
  stage 34's knife-edge: **the sensitivity sweep belongs inside WP-LIN's
  acceptance rule from day one**, not as a post-hoc audit.

### 1.4 How do we do S6 — inject domain knowledge, concretely? (Part 2)

Six levers, ordered by measured-evidence-per-effort; the first three are cheap:

1. **Per-device OP features in the critic/surrogate state** (S5+S6 at once; Cao's
   +10–15 pts). Fill `op_points.jsonl` as campaigns run — stage 26 showed the
   rows are free — and add the z-scored (id, gm, gds, vth, vdsat, vds, vgs)
   vector to critic/surrogate node features (post-cutover rows only, §5).
2. **Verify rails/bias nets are first-class graph nodes** in `critic_gnn.py`'s
   net partition. Cao's ablation says a *partial* graph is worse than none;
   if supply/bias nets are currently pruned or pooled away, that's a measured
   upgrade waiting.
3. **Diagnosis-steered moves**: noise-share/OP-region heads → non-uniform move
   selection in `evolve.py` (§1.3 above). This is AstRL's masking lesson
   translated: put knowledge in the *action distribution*, not the reward.
4. **Symmetry macro-moves** in `moves.py` for the differential/balun work:
   one edit applied mirrored across the symmetry axis (AstRL: OTA 0%→65% from
   this alone). D7's split-phase balun is where it pays first.
5. **Matching frozen in emission**: mirrored devices in `to_spice.py` scale one
   shared group parameter (AnalogGym's netlist-level matching) so no optimizer
   can break a mirror. (Verify current emission; adopt where absent.)
6. **gm/Id reparameterization of sizing space** — search in (gm/Id, Id, L), not
   (W, L). The stage-25 finding that **44% of headline-design transistors sit in
   weak inversion** — where W/L intuition and `bias.saturated` both fail — is
   this program's own argument: gm/Id is the coordinate system in which that
   region is visible and smooth.

### 1.5 What lessons from S2? (Part 2)

S2 ("RL is the wrong default for single-target sizing") lands here four ways:

1. **Never build RL for dhruva sizing.** The designated-point program is the
   textbook case where BO/trust-region/ZOAF wins. This is already the practice;
   S2 makes it a principle with numbers.
2. **The sizer needs its own null hypothesis.** Stage 27 built the generator's
   null (`grammar_gen.py`); nothing plays that role for ZOAF. Run untuned
   CMA-ES + TuRBO-style BO at matched sim budgets on 2–3 of our own sizing tasks
   (and the AnalogGym externals, §1.1). If ZOAF doesn't beat the nulls, the
   program should know now.
3. **The amortization threshold is the decision variable.** RL (or any learned
   spec-conditioned policy) pays only if many *new* spec targets will arrive.
   If the multi-spec direction (§4.2 R2) is adopted, the cheap amortized path is
   Krylov-style supervised inverse from our own store — 10–100× less data than
   RL, and the null for *that* is a nearest-neighbor lookup over `topo_labels`,
   which their paper says ties the MLP anyway. Lookup first, model later.
4. **Judge by deployment, not training curves** (RoSE-Opt): any learned
   component's gate metric is held-out deployment behavior under the frozen
   protocol — which is already this program's adopt-only-if-better culture.

---

## 2. The two new sources (agent-inspected, primary material)

### 2.1 github.com/Arcadia-1/analog-agents — a stranger building our architecture

**What it is.** Not a Python framework — a **Claude Code skill library** ("federated
skill framework") for analog IC design on **Cadence Virtuoso/Spectre via SSH**.
~10.2K lines of markdown skills vs ~7.7K of support Python. Four roles
(librarian/architect/designer/verifier, as subagent prompt templates) + an
orchestrator skill running wiki-consult → decompose → behavioral → per-block
{design → cross-model review → verify} → integrate → PVT sign-off → wiki
archive → evolve. One author (a Tsinghua grad student, Nan Sun/Lu Jie ADC-group
orbit), active Apr–Jul 2026, 50★, **zero published results** — no benchmark, no
completed-design gallery, README/LICENSE inconsistencies, personal-checkout
artifacts committed. No RF/LNA content anywhere (OTA/comparator/ADC/PLL/
bandgap/LDO); no ngspice; the referenced BO optimizer skill is not public.

**Why it matters here.** It is independent convergent evolution on this
program's exact architecture — coding-agent-as-engineer, markdown as logic,
structured memory, hooks injecting sim results into context — which both
validates the direction and demonstrates its failure mode: *process without
measurement*. The repo's genuinely valuable, liftable parts are all schemas:

- **`wiki/` knowledge graph**: YAML entries (anti-patterns/strategies/
  corner-lessons) + typed edges (`prevents`, `contradicts`, `derived_from`,
  `validated`) + a **confidence-escalation protocol** (`unverified` → `verified`
  only when re-observed in a second project). The closest existing analog to
  JOURNEY.md — but machine-consultable. Direct input to N4.
- **Post-sim hook pattern**: parse raw output → check against `spec.yml` →
  append `sim-log.yml` → *print the margin table into agent context*. Ports to
  ngspice trivially; N5's context-injection mechanism, solved.
- **Checklist YAML schema** (7 fields incl. severity/auto_checkable/how) — an
  LNA/RF checklist (S11 match, K-factor, headroom stack, balun imbalance) in
  this format slots into the critic phase.
- **Process invariants** worth adopting verbatim: verifier-never-edits-netlist
  (hook-enforced); mandatory per-MOSFET op-table with red-flag thresholds
  (gm/Id ∉ [5,25], |Vds|<50 mV — kin to our stage-25 weak-inversion finding);
  **"If the design hasn't converged after three designer-verifier loops, the
  problem is topology, not tuning — escalate"** — which is literally the D5
  story, stated as a rule; evolve engine's "propose, never auto-apply".
- Sibling repo `analog-circuit-skills` is the **ngspice-native** counterpart
  (PTM models) — worth a look before N5, likely more liftable than the main repo.

**Verdict: mine the schemas and invariants; take no dependency.**

### 2.2 arXiv:2603.23910 — "AnalogAgent: Self-Improving Analog Circuit Design Automation with LLM Agents" (NTU/A*STAR, Mar 2026)

**What it is.** A training-free three-agent loop (code generator / design
optimizer / knowledge curator) + a **Self-Evolving Memory (SEM)** "playbook",
generating PySpice-on-ngspice netlists for **30 textbook circuits** judged by
functional pass/fail checkers. Pass@1 92.0 (Gemini-2.5-Flash) / 97.4 (GPT-5)
vs AnalogCoder-Pro 88.6; lifts Qwen3-8B from 23.3 → 72.1. Artifact repo 404s —
not reproducible today. **No PDK, no NF/linearity/matching/PVT; "Hard" means
simulator-convergence-hard, not design-hard; sizing is an unevaluated Optuna
bolt-on.** Their ablation's own message: the multi-agent structure carries
Medium/Hard tasks; SEM-only *underperforms* MAS-only; much of the learned
memory is PySpice API trivia, i.e. the playbook substantially learns the
harness, not analog design.

**The four ideas worth taking (all feed N4/N5):**

1. **The SEM entry schema**: `Trigger → Evidence → Rule/Patch → Applicability`,
   atomic entries, with **admission control** — write a rule only if it
   (i) resolves a repeated failure pattern, (ii) enforces a checker/simulator
   constraint violated in multiple attempts, or (iii) is a stable practice
   independent of specific parameter values — and a **failure-first policy**
   (store corrective rules, not successful designs, to avoid overfitting memory
   to topology details). This is N4's file format, found in the wild.
2. **The context-attrition diagnosis** (their §1/App. E, measured): iterative
   LLM refinement erodes raw evidence — concrete diagnosis decays to abstract
   rule, "singular matrix: check nodes vin and vin" decays to "sim failed".
   Rule for our loop: memory and iteration logs preserve **verbatim simulator
   evidence**, never only summaries.
3. **Deterministic repair operators**: their DC-sweep bias-repair (sweep, pick
   feasible bias, inject, re-evaluate — no LLM in the move) is the pattern our
   harness should own for its known walls; `bias.insert_bias` is already one.
4. **Measurement honesty for self-improvement**: they conflate warm-memory and
   cold-memory runs, muddying the headline. When N4/N5 claim "the memory made
   the loop better", run cold-start controls explicitly — our frozen-protocol
   culture applied to the playbook itself.

**Also confirmed by this paper**: agentic scaffolding does the heavy lifting
(the small-model result), consistent with S9's finding that the LLM is best
used as reasoner-over-tools, not as the optimizer. And its trap is our trap:
a playbook that fills with ngspice syntax fixes instead of design physics —
their admission-control criterion (iii) is the filter, enforced harder.

---

## 3. The ten-point architecture, audited against what already exists

The striking thing about the ten points: **eight of them already exist here in
v0 form.** The list is less a new architecture than a naming of what stages 1–38
converged on. Point by point:

| # | Point | Survey evidence | Already here | Gap |
|---|---|---|---|---|
| 1 | Separate reasoning from optimization | S2, S9 (LLM never wins the inner loop) | The session protocol: Claude decides, ZOAF/moves optimize | None — keep; formalize in N5 |
| 2 | Closed loop, simulator = ground truth | S8, S11 | Adopt-only-if-better, replay fences, golden cross-validation | None — this is the program's spine |
| 3 | Persistent memory beyond RAG | Gap in the field — no surveyed system has it | JOURNEY/FINDINGS: 38 stages of (decision, evidence, outcome) — human-readable only | Machine-queryable distillation (N4) |
| 4 | Root-cause diagnosis before action | S5 is the shallow version | WP-DIAGHEADS heads; the D5 output-swing-wall diagnosis is the existence proof (it redirected the program where more sizing would have burned weeks) | Wire diagnosis → move priors; manage stage-29's point-vs-rank trade-off |
| 5 | Hierarchical/phased optimization | AlphaChip's construction; every serious flow | Tier-1/2/3 gates, the upgrade ladder | Keep backtracking legal — the D6-before-D5 inversion just proved phases interlock |
| 6 | Cheap-to-expensive evaluation | S1 fidelity ladder; DynaOpt/Cao transfer | Tier ladder + surrogate pre-gate + 50 s grammar null | Exploit the ladder for *training* (§1.2), not just gating |
| 7 | Active experiment selection | BO's native move; stage 26 measured 4/5 calls wasted | Critic `mean − β·std` ranking in search | Formal EI-per-SPICE-second acquisition, after N3's ensembles |
| 8 | Cross-design learning | S12: *undemonstrated* beyond spec-conditioning + encoder transfer | Multi-spec store schema, family splits | Treat as hypothesis; first test = spec-region→archetype on our own store (wideband-sdr's missing multi-path-feedback archetype) |
| 9 | Knowledge distillation | Nobody has it; closest is BC on expert designs | JOURNEY is the corpus | N4; every rule must cite verifying stages/sims or it poisons the loop |
| 10 | RL as a later stage | S2/S7: possibly *never* — supervised+BO covers amortization cheaper | `loop.py` cadence + tripwires = an environment shell already | Log (state, action, outcome) trajectories now (free); defer the RL bet indefinitely |

**The honest framing:** this program *is* an autonomous analog engineer with the
autonomy dial set to "assisted" — Claude sessions reason, tools optimize, the
simulator grounds, docs remember, the user rules. The ten points describe its
missing 20%: machine-usable memory (3, 9), diagnosis acting on search (4),
formal acquisition (7), and an unattended mode (the loop run without a human in
every iteration). That is what §4 proposes to build — not a new system beside
this one.

---

## 4. Proposed next phase

### 4.1 The recommended ladder (N1–N5, in order)

**N1 — WP-LIN, run as the pilot of the upgraded loop.** The user already ruled:
≤1.2 V linearity-aware redesign, judged at the D6 min-gain state. Run it with
the three upgrades this document argues for, so the architecture work has a live
falsifiable client: (a) fidelity-ladder surrogate with an IIP3 head (§1.2), all
acceptances real-two-tone-verified; (b) diagnosis-first search — the wall is
*measured* as output-swing on the 1.1 V envelope, so the move set starts from
swing-directed edits (output cascode/bias re-centering at 1.2 V, current-reuse,
derivative-superposition-class linearization) rather than uniform mutation;
(c) stage-34 sensitivity sweep inside the acceptance rule. Deliverable: a D5
verdict at 1.2 V — MET, or a measured wall with a named mechanism.

**N2 — The data-engine refresh.** §5. Cheap, and everything learned downstream
depends on it. Can interleave with N1 (N1's sims are N2's rows).

**N3 — The sizer null + external calibration.** §1.5.2 + §1.1. One or two days
of compute; either it validates ZOAF or it replaces it with something simpler —
both outcomes are wins under S11.

**N4 — Memory distillation v0.** Convert JOURNEY/FINDINGS into a structured
rulebook, adopting the two schemas §2 found in the wild rather than inventing
one: AnalogAgent's entry format (`Trigger → Evidence → Rule/Patch →
Applicability`, atomic, admission-controlled, failure-first, verbatim simulator
evidence preserved) + analog-agents' wiki upgrades (typed edges incl.
`contradicts`, and confidence escalation — a rule is `verified` only when
re-observed independently). Retrieval keyed by (circuit family × analysis ×
**failure signature**, §5.4), not substring match. Every rule cites the
stages/sims that ground it. The corpus is unique — no surveyed system has 38
stages of verified decision-trajectory — and it is this program's actual moat.
When the memory's value is claimed, cold-start controls run (§2.2 item 4).

**N5 — Unattended loop v0.** Promote `loop.py` from cadence to agent: one
bounded, pre-registered task runs propose→simulate→diagnose→intervene overnight
without a human per iteration; tripwires (already numeric) are the safety rail;
rulings that today go to the user get queued, not guessed. First bounded task:
either the wideband-sdr S11 wall with a multi-path-feedback archetype added to
the library (a topology task the frontier already names as the natural lever),
or the outstanding `emit_winners` P5 fine-tune. Measure the same headline as
ever: SPICE-minutes per feasible novel design, against the human-in-loop
baseline. Adopt three §2 process invariants on day one: the post-sim hook that
injects the margin table into context, the verifier-never-edits-netlist role
split, and the escalation rule ("no convergence after N designer-verifier
loops ⇒ the problem is topology, not tuning ⇒ escalate — to the archetype
library or the rulings queue"). **This is the ten-point architecture, built as
an increment.**

### 4.2 Radical options (R1–R5) — proposed so they can be rejected explicitly

**R1 — Re-aim the program: the product is the engineer, not the LNA.**
*Recommended for serious consideration.* The survey's clearest gap: every
surveyed system is a sizing or topology optimizer; none has diagnosis, memory,
or an engineering loop; the field's benchmark (AnalogGym) has no RF. This
program owns a golden-validated RF harness, honesty protocols stronger than the
field's (S11 is *practiced* here), and the trajectory corpus. Publishing
"RF-grade agentic analog design environment + benchmark + the dhruva case
study" is a contribution no surveyed group can currently match, and every N-step
above is on its critical path anyway. Cost: the dhruva gates stop being the
terminal goal and become the flagship case study. (D4-SIM/D6/D7 are MET; D5 is
one WP away from its verdict — the case study is nearly complete either way.)

**R2 — Spec-frontier self-play.** After N2/N4: the agent proposes spec vectors
near its measured capability frontier, attempts them, Krylov-relabels every
attempt (feasible-direction relaxation makes labels from failures too), and
grows a spec-region→design atlas. Turns a design program into a data engine
with zero external dependency. *Defer until N2+N4 exist; adopt then.*

**R3 — Train a topology foundation model** (grammar_gen + AnalogGenie corpus +
ingested real designs, then RL/BO refine). *Reject for now.* S12: cross-family
generalization is undemonstrated field-wide; stage 27 measured our own
fine-tune's headline gains vanishing against a no-learning null; stage 28
measured the shuffled control taking the credit. The program's own evidence
says the leverage is elsewhere (archetypes, §5.5).

**R4 — Full RL formalization of the loop now.** *Reject* per S2/S7 — but N5
logs trajectories in (state, action, outcome) form regardless, because it's
free once the loop exists and it keeps the option alive without betting on it.

**R5 — Rent cores instead of building cleverness.** *Adopt opportunistically.*
§6: the program is CPU-bound and its headline metric is SPICE-minutes. A 64-vCPU
spot instance at ~$2–3/hr turns a 2-week campaign into 2 days for tens of
dollars — cheaper than any surrogate work that saves the same wall-clock, and
compatible with all of it. (The WSL/ngspice stack ports trivially; the store is
append-only JSONL — merge-friendly.)

---

## 5. Representation & data construction — where the usefulness is

The user flagged Part-3 conclusion 5 (data construction beats model choice) as
the strongest agreement; this section is its application.

**5.1 The era problem is the first problem.** All 66,664 `sim_points` rows and
most L2 rows predate three harness cutovers (multi-finger, series-Rs NF,
stability). The surrogate's own docstring says v0 must not be trusted for
current-era numbers. Highest-leverage single action in the program:
**a post-cutover re-labeling campaign** — re-simulate the top-K stored designs
(by critic rank + all gate-relevant points) under the current harness era,
logging points + op rows. Every learned component downstream inherits the fix.
Dedup key (wl_hash, spec) already prevents waste.

**5.2 Fill `op_points.jsonl` as a side effect of everything.** Validated
instrument, 156 rows, free to populate (stage 26). Rule: no campaign runs
without the op hook on. This is S5 (semantics-in-state) as a data policy, and
it feeds §1.4's items 1 and 3.

**5.3 Krylov relabeling over our own store.** From L2 rows, manufacture
(threshold-spec, sizing) pairs: relax each measured performance in the feasible
direction, pair each query with the lexicographic-best dominating design.
Start with the null their own paper endorses: a **nearest-neighbor lookup**
spec→sizing over the relabeled store (no training, one afternoon). If the
lookup already answers in-range spec queries at >90%, that *is* the amortized
sizer, and the S2 question closes for this program.

**5.4 Failure signatures as first-class labels.** The program keeps discovering
*named walls* — output-swing wall, S11 knife-edge, weak-inversion blindness,
the wideband-sdr matching wall. Add a `diagnosis` field to L2/campaign rows
(controlled vocabulary + free text), so memory retrieval (N4) can be indexed by
*what went wrong* rather than only what the circuit was. ShortCircuit's lesson
generalized: behavior-keyed representations collapse equivalence classes —
failure-keyed memory collapses "different circuit, same disease" into one
retrievable lesson.

**5.5 Archetypes over generators.** Stage 22 ruled the l5 input-stage problem a
topology task; the frontier names the missing multi-path-feedback match
archetype for wideband-sdr. CktGNN's motif result (99% validity from a 24-motif
basis) plus AstRL's macro-action result say: **a small curated archetype
library with symmetry-aware attachment moves is worth more than a better
generative model** at this program's scale. Grammar_gen stays the null;
archetypes become the treatment.

**5.6 One store discipline extension.** Trajectory rows (N5): (state digest,
diagnosis, action taken, sim outcome, cost) per loop step, append-only, same
snapshot discipline. Free now, priceless if R2/R4 ever activate.

---

## 6. Hardware — what more CPU, GPU, RAM would buy

Measured baseline: **Ryzen 7435HS, 8C/16T; 15.8 GB RAM (~6 GB free in steady
state); RTX 3050 laptop (4 GB)**. The program's headline metric is literally
SPICE-minutes per feasible design, so this is easy to price:

- **CPU: the binding constraint, near-linear payoff.** ngspice runs
  single-instance single-threaded here (~1 s cheap evals; minutes for
  two-tone); campaigns parallelize embarrassingly across independent points.
  8C sustains ~8–12 concurrent sims; a 32C desktop ≈ 3–4× every campaign,
  N2's re-label included; a 64-vCPU cloud spot box ≈ 6–8× for ~$2–3/hr
  (R5). The field agrees: PrefixRL ran 192 CPU workers *per GPU*; analog AI is
  CPU-bound everywhere it's been built.
- **RAM: the friction constraint.** 16 GB with ~6 free caps concurrent sims
  with transient rawfiles, forbids torch-training-while-simulating, and squeezes
  the WSL env. 32–64 GB removes a class of daily friction. Second priority.
- **GPU: near-zero marginal value now.** Critic v1 trains on CPU by design
  ("the 3050 is unnecessary at this size" — its own docstring); every learned
  component in this program is in the 10⁵–10⁶-parameter class, as are the
  field's (AstRL's whole policy: 244K params). A bigger GPU matters only if R3
  (foundation model) is ever adopted — and R3 is rejected above. Third
  priority, likely zero spend.

**Recommendation:** don't buy anything standing; adopt R5 (burst cloud CPU for
campaign days) and revisit RAM only if N2/N5 make the 16 GB ceiling a weekly
annoyance.

---

## 7. Decision queue (user rulings requested)

| # | Decision | Recommendation |
|---|---|---|
| D-1 | Run N1 (WP-LIN) with the three upgrades of §4.1-N1 | Yes — already-ruled WP-LIN, upgraded, no scope change |
| D-2 | Adopt N2 data-engine refresh (post-cutover re-label + op-hook-always-on + `diagnosis` field) | Yes — cheap, everything downstream inherits it |
| D-3 | Adopt N3 sizer nulls (CMA-ES/TuRBO + AnalogGym external calibration) | Yes — S11 hygiene applied to ourselves |
| D-4 | Adopt N4 memory distillation v0 (rulebook with evidence pointers) | Yes — the corpus is the moat |
| D-5 | Adopt N5 unattended-loop v0 on one bounded task | Yes, after N1 lands — the ten-point architecture as an increment |
| D-6 | R1 re-aim (product = the engineer/benchmark, dhruva = case study) | **Genuine fork — user's call.** Every N-step is on R1's path anyway, so the decision can trail N1–N4 without cost |
| D-7 | R5 burst cloud CPU for campaign days | Yes, opportunistically |
| D-8 | R2 spec-frontier self-play | Defer until N2+N4, then adopt |
| D-9 | R3 foundation model / R4 RL formalization | Reject for now (evidence in §4.2) |

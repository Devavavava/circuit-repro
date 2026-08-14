# 00-CHARTER — the `engineer` line

**Status:** FOUNDING CHARTER — written 2026-08-14, branch `engineer`, forked from
`lna-data`/`main` at `5b4b5c2`. It executes **D-6** of
`lna/plans2/15-ENGINEER-PROPOSAL.md` §7, ruled by the user on 2026-08-14: *"i've
been through your engineer proposal, im fine with all your decisions — i do want
to try D6 as well (the re-aim)."*
**Inputs:** `lna/SURVEY-AI-CIRCUIT-DESIGN.md` (nine systems, primary sources);
`15-ENGINEER-PROPOSAL.md` §3/§4.1/§4.2-R1/§7; `lna/FINDINGS.md` §43; the live
shared core.
**Scope of this document:** what this line is for, what it will not do, how it
shares a repository with the LNA line, the quality bar it inherits, and the
queues (work and rulings) it opens with. It adopts nothing beyond D-6 itself;
§7 is where new decisions go.

---

## 1. What the product is

**The product is the engineer, not the LNA.** Concretely, three artifacts:

1. **An RF-grade agentic analog-design *environment*** — a budgeted, counted,
   observable, deterministic interface onto a golden-validated simulation
   harness, over which searches, agents and unattended loops can be run and
   compared. `engineer/env.py` is its v0.
2. **A benchmark** — a frozen registry of (spec, topology, tier, budget,
   reference) tasks, each pinned to the exact stored label its numbers come
   from, with a scoring protocol that is compute-matched by construction.
   `engineer/tasks.py` is its v0.
3. **A case study** — the dhruva/GNSS balun LNA, carried to a verdict. It stops
   being the terminal goal (§4.2-R1) and becomes the flagship demonstration that
   the environment measures something real. D4-SIM / D6 / D7-imbalance are MET;
   D5 has a measured wall with a named mechanism and one work-package to its
   verdict.

### 1.1 Why — the gap, as measured, not as asserted

The survey read nine systems from primary sources. What it found is a field of
**optimizers**, and the specific absences are the argument for this line:

| The gap | The survey's evidence | What this line already has |
|---|---|---|
| No system has **persistent memory** beyond RAG | §3 point 3: "Gap in the field — no surveyed system has it" | **40 stages** of (decision, evidence, outcome) in `lna/JOURNEY.md` + `lna/FINDINGS.md`, distilled to a machine-queryable store by `playbook.py` v0 |
| No system does **root-cause diagnosis before action** | S5 is the shallow version (behavior in the state); nothing acts on a *diagnosis* | The D5 output-swing-wall diagnosis is the existence proof — it redirected the program where more sizing would have burned weeks |
| No system runs an **engineering loop** (propose → simulate → diagnose → intervene) | §3 point 10, S2/S7: everyone builds a search, nobody builds an engineer | `loop.py` cadence + numeric tripwires + the session protocol = an environment shell already |
| The field's benchmark has **no RF** | §1.1: AnalogGym has no S-parameters, no NF-with-source-impedance, no two-tone — "not a superset, a different domain" | A harness golden-validated against two independent engines: ngspice transient ↔ VACASK HB agreeing to **0.08 dB** |
| **Evaluation hygiene is mostly absent** | S11: AutoCircuit-RL, AstRL and Krylov run *no* BO/GA head-to-head; ORACLE's loss is visible only in its own tables | S11 is *practiced* here — and it bites: FINDINGS §43.2 ran the untuned null on our own sizer and **CMA-ES beat ZOAF 4/5 vs 1/5 at matched budget** |
| **Nobody publishes trajectories** | §3 point 10 | §5.6's (state, action, outcome, cost) rows, written from day one — `engineer/data/trajectories.jsonl` |

The honest framing the proposal reached (§3) holds and is this line's thesis:
*this program is already an autonomous analog engineer with the autonomy dial set
to "assisted."* Eight of the user's ten architecture points exist here in v0
form. The engineer line's job is the missing 20% — machine-usable memory,
diagnosis acting on search, formal acquisition, and an unattended mode — built as
an increment on a working system, and **measured**, because the one thing the
convergently-evolved competitor (`Arcadia-1/analog-agents`, §2.1: ~10.2K lines of
skills, 50★, **zero published results**) demonstrates is the failure mode of
process without measurement.

---

## 2. Non-goals

Stated so they can be pointed at later, each with the evidence that rejected it.

* **No foundation model for topology.** §4.2-R3, *rejected*: S12 says
  cross-family generalization is undemonstrated field-wide; stage 27 measured
  this program's own fine-tune's headline gains vanishing against a no-learning
  null; stage 28 measured the shuffled control taking the credit. The leverage is
  in archetypes (§5.5), not in a bigger generator.
* **No RL bet.** §4.2-R4, *rejected*: S2 — RL needs ~10⁶ sims per topology and
  pays off only amortized over hundreds of spec targets. The line logs
  (state, action, outcome) trajectories anyway, because it is free once the loop
  exists and it keeps the option alive **without** betting on it. Logging
  trajectories is not adopting R4.
* **No cross-family generalization claims until measured.** Spec-conditioning
  within a trained range and encoder transfer are what the field has shown
  (S12); "one policy across circuit families" is not. This line may *test* it —
  the registry deliberately contains a controlled pair (`dhruva-l1-t2-a` and
  `dhruva-l2-t2-a`: same topology, different band) — but a claim requires that
  measurement, on held-out tasks, under a pre-registered protocol.
* **No second harness.** The environment binds to the LNA line's harness. Any
  divergence in what an evaluation *computes* is a bug in this line, not a
  feature of it: an environment whose numbers cannot be compared to the
  program's own published numbers is worthless as a benchmark.
* **No new specs.** `tasks.py` may curate, pin and stamp; it may not invent. A
  benchmark that ships its own specs benchmarks its own specs.
* **Not a Cadence/commercial-PDK flow.** The harness is ngspice + an open 45 nm
  BSIM4 card. Absolute silicon claims are out of scope; relative,
  same-harness, budget-matched comparisons are the whole point.

---

## 3. The two-line management policy

D-6 executed as a **two-line structure**: current work fast-forwarded to `main`
(`535104c` → `5b4b5c2`), and `engineer` forked at the same tip and managed
independently. The two lines share a repository, a harness and a data model —
and must not share a merge queue. This section is the policy; it is binding on
both lines.

### 3.1 `main` is the LNA line **and** the shared core's home

`main` (with `lna-data` as its working front) owns the LNA program: the dhruva
gates, the campaigns, the work packages. It also owns the **shared core** — the
modules both lines evaluate through:

| Shared-core file | What it owns |
|---|---|
| `lna/datastore.py` | the append-only tables, margins, snapshots, diagnosis vocabulary |
| `lna/spec.py` | spec loading/validation, `feasible` / `objective` / `report` |
| `lna/size.py` | `prepared_body`, `make_objective`, `eval_metrics`, `OpSink`, the box |
| `lna/extract.py` | the ngspice decks and every measurement in them |
| `lna/bias.py` | bias insertion + `classify_params` |
| `lna/to_spice.py` | netlist emission, the model card, `W_FINGER` |
| `lna/topology.py` | the token graph |
| `lna/ref/` (goldens + `check_ref.py`) | the definition of "the harness still works" |
| `lna/playbook.py` + `lna/playbook/` | the machine-queryable memory |
| `lna/null_sizer.py` | the sizer's null hypothesis and its eval-accounting rule |
| `lna/relabel_era.py` | the era re-label |
| `lna/sync_lines.py` | the sanctioned cross-line data path |

**Rules, in order of how expensive they are to get wrong:**

1. **Shared-core changes land on `main` FIRST.** Never on `engineer` first, never
   on both. A shared-core change is by definition a change to what an evaluation
   means, and two lines' worth of published numbers depend on exactly one answer
   to that.
2. **Merge `main` → `engineer` regularly**, and always before a scoring run whose
   numbers will be published. The engineer line consuming a stale core is how a
   benchmark quietly starts measuring a simulator that no longer exists — the
   same failure FINDINGS §43.1 measured across 1,109 of 1,215 stored designs.
3. **Engineer inventions are promoted back by explicit cherry-pick only.** Never
   by merging `engineer` → `main`. The engineer line will accumulate scaffolding
   that has no business on the LNA line; promotion is a decision about one
   commit, made once, by a human or a coordinator, with the goldens green.
4. **`engineer` modifies nothing under `lna/`.** Read-only, imports included.
   This is enforceable by review and by `git diff --stat main...engineer` being
   empty under `lna/` for anything but a merge commit.

### 3.2 Training data combines; code does not

The two lines' generated data is one asset. It combines through
**`lna/sync_lines.py` and nothing else** — the `.gitattributes` entry disables
git's own text merge for `lna/data/*.jsonl` and `lna/playbook/edges.jsonl`
precisely so a cross-line merge fails loudly instead of interleaving
independently-appended JSONL lines and silently breaking the byte prefix a
snapshot's sha256 pins.

* **Prefix-preserving union.** DEST's existing bytes are never reordered or
  edited; the only legal write is an append at the tail, asserted after every
  run. Line identity is **exact byte equality**, so every snapshot either line
  has ever taken still verifies after a merge.
* **Gitignored tables sync by filesystem.** `sim_points.jsonl` and
  `op_points.jsonl` are not in git (bulk); the tool is run against the two
  checkouts' paths directly, once in each direction.
* **Playbook entries never auto-resolve.** A filename present on both sides with
  different bytes is reported as a conflict, not overwritten — picking a winner
  between two lines' engineering lessons is a human call.
* **The engineer line's own table is its own.** `engineer/data/trajectories.jsonl`
  is not an lna store table and is not written through `datastore.append`. It
  lives on this line; if it ever needs to cross, it crosses the same way, by an
  explicit tool, never by a writer that reaches across.

### 3.3 Models are never binary-shared

No `.pth`, no pickled surrogate, no checkpoint moves between lines. A model is
transferred as the **triple (data snapshot, seed, protocol)** and re-trained.
This is the program's replay-fence culture applied to the line boundary: a
checkpoint whose training set cannot be named is an unfalsifiable number, and
two lines exchanging checkpoints is the fastest way to make every downstream
number unattributable. It costs CPU minutes and buys the ability to answer "what
was it trained on?" forever.

---

## 4. The quality bar — inherited unchanged

None of this is new; that is the point. The engineer line does not get a lower
bar because it is building infrastructure.

* **Goldens.** `python lna/ref/check_ref.py` is GREEN before and after every
  landing. A harness that drifts silently invalidates every number on both lines.
* **Adopt only if better.** A component is adopted on held-out deployment
  behavior under a frozen protocol, never on a training curve (S11; RoSE-Opt's
  own lesson).
* **Nulls first, always.** Survey conclusion 7. Every claim about a search, an
  agent or a memory ships with its untuned baseline at a matched budget — and
  the program knows what that costs, because running it on our own sizer
  produced FINDINGS §43.2, where the null won.
* **Pre-registration.** The protocol, the metric and the acceptance rule are
  written before the run, not selected after it.
* **Replay fences.** A stored number must reproduce at its stored point under
  its stored harness era, or it is quarantined — the mechanism that caught 10
  non-reproducing rows (worst |Δ| 38.78 dB) in §43.1.
* **Verbatim simulator evidence.** Memory and logs keep the exact message and
  the exact number, never only a summary (arXiv:2603.23910's measured
  context-attrition finding).
* **Era stamps on everything.** Every number carries the harness era it was
  measured in. A pre-cutover reference is shipped *stamped*, never silently
  compared.
* **User rulings for frozen protocols.** Freezing a benchmark, publishing it, or
  changing a scoring rule after results exist is a user decision, queued in §7,
  not an agent's to make.

---

## 5. What exists today (v0)

| File | What it is | Lines |
|---|---|---|
| `engineer/env.py` | `Task` / `Env.evaluate` / `Env.observe` / `TrajectoryLogger` / the dep shim | 726 |
| `engineer/tasks.py` | benchmark registry v0, `--list`, `--check` | 228 |
| `engineer/baseline_run.py` | end-to-end smoke: CMA-ES through the env | 217 |
| `engineer/data/` | `trajectories.jsonl` + result JSONs (this line's own store) | 150 rows |

**The smoke, run 2026-08-14** (`wifi24-smoke`, CMA-ES seed 1, 150 evals = 300
ngspice calls, 15.1 s = **0.101 s/eval**): best objective **1.2501 at eval 147**,
**infeasible on `s11_db` by 0.250** (margins nf +0.571 / s11 −0.250 / s21 +0.198 /
idd +0.156; NF 1.07 dB, S11 −7.50 dB, S21 14.38 dB, Idd 4.22 mA). CMA-ES
diagnostics λ=10, μ=5, σ₀=0.3, 15 generations, 0 restarts, box by clipping. That
is the expected shape at 45% of the matched budget — one constraint left, closing.
The number that means anything about this task is the 336-eval one (§43.2:
CMA-ES 4/5 seeds feasible, best −0.790), and `baseline_run.py` prints it beside
the smoke marked NOT COMPARABLE.

**Registry v0 — 8 tasks, all tier-2**, pinned against `lna/data/topo_labels.jsonl`
at 4,074 L2 rows. Seven are scoring tasks; `wifi24-smoke` is the end-to-end check
and is explicitly not one.

**There is no tier-3 task, and it is not an oversight.** Tier 3 is linearity, and
`iip3_dbm` carries `status: unsupported` in *every* spec in `lna/specs/` — it is
loaded, reported as UNMEASURED, and ignored by the objective. A "tier-3 task"
today would be a tier-2 task with a label on it. WP-LIN's two-tone harness is
what binds it; the tier-3 rungs get written the day it does. `tasks.py --check`
asserts the condition so the claim fails rather than rots.

**One task ships era-stamped rather than dropped.** `wideband-sdr-t2-a`'s
reference row is pre-cutover (`ingest-v1`, `w_finger` unset) because **no
current-era row exists for any wideband-sdr topology**. The deck the environment
builds is current-era either way; what is stale is the reference number, and in
particular its NF. Stamped, not absorbed — see §7 R-2 for the alternative.

---

## 6. The E-queue

The engineer line's work queue, in order. Each item names its deliverable and the
thing that would falsify it.

**E-1 — Environment API hardening.** `env.py` v0 is one seam proven end to end;
it is not yet an API anyone else can hold wrong. Wanted: a foreign-topology path
exercised for real (the arena cache exists and is untested against `moves.py`
output), a parameter-dict round-trip test (`encode` ∘ `decode` ≈ identity),
explicit failure semantics for a non-sizable topology, and the runtime-dep
question settled (§7 R-1). *Falsifier:* a second driver written against the API
without editing it.

**E-2 — Benchmark curation + scoring protocol.** The registry is a table; a
benchmark is a table **plus a protocol**. Wanted, in AnalogGym's shape (the
survey's model, S11): fixed sim budget, N seeds per arm, convergence curves,
modeling time accounted separately from simulation time, and a stated
aggregation rule chosen *before* the first result. Plus a decision on breadth —
8 in-house tasks is a pilot, not a benchmark, and §1.1's AnalogGym externals are
the calibration set that makes "our sizer is good" a statement about more than
our own store. *Falsifier:* a result table where the protocol was decided after
the numbers were seen.

**E-3 — Cold/warm-memory measurement harness.** Proposal §2.2 item 4: AnalogAgent
conflated warm-memory and cold-memory runs and muddied its own headline. When
this line claims "the playbook made the loop better", the cold-start control runs
explicitly, on the same tasks, at the same budget, with the memory store empty.
Wanted: the harness that makes that control cheap enough that skipping it is
never tempting. *Falsifier:* any memory claim published without its cold control.

**E-4 — Unattended-loop pilot (proposal N5).** One bounded, pre-registered task
running propose → simulate → diagnose → intervene without a human per iteration.
Tripwires (already numeric) are the safety rail; rulings that today go to the
user get **queued, not guessed**. Adopt the three §2 process invariants on day
one: the post-sim hook that injects the margin table into context, the
verifier-never-edits-netlist role split, and the escalation rule ("no convergence
after N designer–verifier loops ⇒ the problem is topology, not tuning ⇒
escalate"). Headline metric unchanged: **SPICE-minutes per feasible novel
design**, against the human-in-loop baseline. *Falsifier:* the loop needs a human
per iteration anyway, or costs more SPICE-minutes than the assisted mode.

**E-5 — Packaging / publication ruling (user).** R1's payoff is a public
contribution: "RF-grade agentic analog design environment + benchmark + the
dhruva case study". What gets published, when, under what license, with which
data, and whether the benchmark is frozen at that point, are the user's calls —
not an agent's. Queued as §7 R-5; nothing is prepared for release until it is
ruled.

---

## 7. Ruling queue (opened by this charter)

| # | Item | Recommendation |
|---|---|---|
| **R-1** | **Runtime-dep resolution: shim or hard precondition?** The three upstream clones (`misc/ZOAF`, `AutoCkt/repo`'s 45 nm card, `AnalogGenie`) are gitignored, so a fresh worktree has none of them — and the failure is *silent*: ngspice runs, finds no models, every evaluation returns `None`, and a campaign reports a clean, converged, entirely fictional "no feasible point". `env._bind_runtime_deps()` today walks up (override → this checkout → the git common dir's parent → ancestors), rebinds `to_spice.DEFAULT_MODELS` **and** `Netlist.__init__`'s bound default, and stamps the resolved paths into every result's harness block. Verified 2026-08-14: forcing the walk-up to the main checkout rebinds both and reproduces the worktree-local evaluation's objective to the digit (16.9380). | **Keep the shim, and make it loud.** A path lookup is the right shape for a path problem, and the stamp means no number can be read without its harness provenance. The alternative — refuse to import until a junction exists — trades a working fresh worktree for a guarantee the stamp already gives. *User's call if the preference is the stricter one.* |
| **R-2** | **`wideband-sdr-t2-a` anchors on a pre-cutover reference.** No current-era row exists for any wideband-sdr topology. Shipped era-stamped. The alternative is to re-label one wideband-sdr design under the current harness (~2 min via `relabel_era.py`) and re-pin the task. | **Re-label before the first scoring run that includes it.** Cheap, and it removes the one asterisk in the registry. Shipping stamped is correct in the meantime; shipping *unstamped* would not be. |
| **R-3** | **`observe()`'s op subsample is 1-in-1, in memory, never flushed.** The lna store's 1-in-8 default is a *storage* policy (an op row is ~5× a point row); an agent diagnosing the current step cannot be handed a 1-in-8 sample of it. The environment therefore captures every eval into a bounded ring buffer (8 captures) with no flush path at all. | **Adopt as the environment default.** It is not a change to lna's policy — nothing is stored — and the read-only-toward-`lna/` rule is what makes it safe. Revisit only if trajectory rows are ever asked to carry full OP vectors, which would be a storage decision and therefore §3.2's. |
| **R-4** | **Smoke budget: 150 evals, reported as infeasible.** 120 evals lands infeasible; so does 150. The smoke is `wifi24-t2-a` stopped at ~45% of its matched budget and is expected to fail — `baseline_run.py` prints the 336-eval published table beside it with "NOT COMPARABLE" stated. | **Pin at 150 and report honestly.** The smoke's job is the seam, not the score. Raising it to 336 to make the output look better would cost ~35 s and buy a misleading habit. |
| **R-5** | **Packaging / publication** (E-5). | **User's call**, and not needed yet. |

---

## 8. What would make this line wrong

Recorded now, so it is not rationalized later.

* If the environment's evaluations ever stop being bit-identical to the LNA
  line's, the benchmark is measuring a fork of the harness and every comparison
  in it is void.
* If the E-queue produces scaffolding faster than it produces measured results,
  this line has become `Arcadia-1/analog-agents` with better prose — §2.1's
  named failure mode, which the survey put in this document precisely so it
  could be checked against.
* If the unattended loop (E-4) costs more SPICE-minutes per feasible design than
  the assisted mode it replaces, the ten-point architecture's missing 20% was
  not worth building and the honest move is to say so and stop.

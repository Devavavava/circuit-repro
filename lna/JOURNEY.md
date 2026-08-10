# The LNA Journey

**What this is.** A single narrative history of the AI-driven LNA (low-noise
amplifier) design project: user-defined spec → AI-generated topology + sizing →
SPICE-verified result. It exists because the durable record is otherwise
scattered across `FINDINGS.md` (measurement-by-measurement), `HANDOVER-EXEC.md`
(session-by-session handoffs), `BROADEN-PROGRESS.md`, `data/reports/`,
`data/benchmark.md`, the `plans/`/`plans2/` work-package specs, and git log —
each true but none of them the whole story in order. This document is the
whole story in order, for the project owner re-reading in a month or a new
collaborator starting cold.

**Maintenance contract.** Every future session appends or edits its own stage
here as part of its wrap-up — same commit discipline as `FINDINGS.md`. New
material goes at the end of the chronology (before "Current frontier", which
should be rewritten, not appended to) unless it corrects an earlier stage, in
which case add a dated note *inside* that stage rather than silently editing
the original claim — corrections are part of the story, not embarrassments to
smooth over. Cite sources inline (`FINDINGS §N`, `HANDOVER Session N`, a
report filename, a commit hash) the way the rest of the repo does. This file
lives in both the `lna-exec`-derived checkouts and the `lna-data` worktree
lineage; treat the copy on `lna-data` (or wherever Phase 2+ work lands) as
canonical going forward.

**Blind-protocol note.** From the Dhruva stage onward, this document — like
every other file in the repo — describes only the allowed spec-number excerpt
from the target paper (Kanchetla et al., TMTT 2022), never its circuit. See
`plans2/08-DHRUVA-GOAL.md`.

---

## How to read this

Each stage below follows the same shape: **Context** (why this stage
happened), **Decision** (what was decided and by whom — user decisions are
labeled explicitly; everything else was an executor call), **Result** (the
measured outcome, with the numbers that matter), **Understanding** (what it
changed about how the team thinks about the problem). Numbers are cited to
the document they came from; where two documents disagree, the later
correction is what's stated, with the earlier number kept visible as "was."

---

## 1. Origins — the 15-repo survey and the two asks

**Context.** The project started as a breadth-first survey: clone, build an
environment for, and smoke-test every analog-circuit-ML repo that looked
relevant, then decide what to build on. `STATUS.md` covers the mechanics —
11 originally requested works plus 6 extension repos, one conda env each,
Windows first then WSL for GPU. **Score: 8 of 8 works with public code
verified running; 3 (GCN-RL, L2DC, DNN-Opt) have no public code at all**
(STATUS.md). AutoCkt's RL loop, initially blocked on Windows, came alive
under WSL with the exact documented Python-3.6 stack (STATUS.md §"What WSL
unlocked").

**Decision.** The user's framing (implicit in the setup) was breadth before
depth: survey everything, then narrow. The narrowing itself — AnalogGenie as
the generator, ngspice as the simulator, ZOAF as the sizer — was an executor
judgment call, made and then handed to the next session as **HANDOVER-FABLE.md**,
addressed to "an Opus session (or several)."

**Result.** AnalogGenie turned out to be the only real topology *generator*
in the set, with inductors in its vocabulary and 41 real LNA circuits
(1.2% of its 3,351-circuit corpus) buried inside it (FINDINGS §1, main
checkout). ngspice 45.2 could already do everything an LNA measurement needs —
`op`, `ac`, `noise`, and S-parameters (`sp`) — confirmed by direct probe
(WORKLOG S2). ZeroSim, which looked like the natural fast surrogate for
scoring candidates, turned out to have **no inductor and no RF port in its
device vocabulary** — an op-amp model, not an LNA one; using it would have
produced confident nonsense (FINDINGS §2, WORKLOG "dead ends"). CktGNN,
LaMAGIC2, AnalogSAGE, and RoSE were ruled out for similar reasons (wrong
circuit class, blocked upstream, or need Cadence).

Two asks came out of this survey, addressed by HANDOVER-FABLE.md: (1) how do
we make LNA *generation* better — the copying-vs-novelty tradeoff was already
visible in prefix-conditioned sampling — and (2) how do we define what LNA we
are even designing, since nothing in the pipeline yet encoded a target spec.

**Understanding.** The measurement side (simulation) was never the
bottleneck; the *targeting* side was completely absent. That reframing — "we
can simulate anything, we just can't ask for what we want" — set the shape of
everything that followed: spec first, then steer generation toward it, not
the other way around.

---

## 2. Phase 1 — building the pipeline (spec → reference → bias → generation → sizing)

**Context.** HANDOVER-FABLE's two asks were answered with a plan set
(`.claude/worktrees/lna-plans` on branch `worktree-lna-plans`, `lna/plans/`)
written by a Fable session and then executed, WP by WP, by an Opus executor
session over roughly a week (session dated 2026-08-06, branch `lna-exec`).

**Decision.** The plan (00-OVERVIEW.md) picked: (a) **keep the pretrained
AnalogGenie checkpoint and Eulerian-path representation** rather than
building a new generator from scratch — training data was 41 LNA graphs on a
4 GB GPU, a bad trade against a pretrain over 3,351 circuits; (b) a **YAML
spec format** that compiles into three separable artifacts (unsized
structural screen, sized objective, seed-selection rule) with hard
constraints and soft objectives kept apart until the last possible moment;
(c) **rule-based, DC-path-analysis bias insertion** as the critical path,
ahead of generation improvements, because nothing downstream could be scored
without it; (d) a ranked generation roadmap P0–P6, ordered by cost
(00-OVERVIEW.md). These were plan-level (Fable-session) decisions; the
executor then measured and, where the plan's assumptions broke, adjusted —
e.g. widening `device_budget` from `[3,12]` to `[3,16]` after measurement
showed real single-ended corpus LNAs reach 14 devices (HANDOVER Session 1
finding #1) — an executor call justified by data, not a request.

**Result.** In sequence:

- **WP-SPEC**: three worked spec targets (`wifi24`, `gps-l1`, `wideband-sdr`)
  plus a legacy compatibility spec; spec-driven screen reproduces the legacy
  59.4% score-5 ceiling exactly and reaches **94.1%** union coverage over the
  in-scope (single-ended MOS) corpus class (HANDOVER Session 1 §1).
- **H-Q3 resolved**: index 1081, long thought to be a floating sub-circuit,
  was actually an **ideal-inductor branch singularity** — fixed by giving
  inductors finite Q, raising pipeline yield from 40/42 to **41/42** (WORKLOG
  R1).
- **WP-REF**: a common-gate anchor closed H-Q2 (Re(Zin) matched theory to
  0.1%, S11 −23.3 dB) but proved a resistive-load CG into 50 Ω is gain-capped
  near 0 dB — a real result, not a tuning miss (WORKLOG R2). A CS+Cex
  "stage-B" anchor then fixed F1 (the unsolved hand-design failure from the
  survey phase): **S11 −21 dB, S21 +6.7 dB**, resolving H-Q1 (WORKLOG R3).
- **WP-BIAS**: rule-based gate-bias insertion (`bias.py`) got 54% of corpus
  MOS devices conducting at default sizing with **zero circuits made worse**
  (HANDOVER Session 1 finding #9).
- **WP-GEN**: prefix conditioning alone moved the LNA hit rate from **0% to
  40.6%** with no retraining (FINDINGS §5, main checkout) — the survey
  phase's headline finding, carried forward. P0 froze the measuring stick
  (see stage 3). **P2** (plain fine-tune) beat the frozen baseline, NDL@256
  16→24, but **P4** (inductor logit-bias decoding) proved the inductor gap
  was a *data* problem, not a decoding one — pushing past λ≈12 just produces
  junk (FINDINGS §5 "P4").
- **WP-SIZE**: `extract.py` + `size.py` (a ZOAF driver) closed the spec→sized
  loop. Anchor re-derivation reached S11 −10.9 / Idd 4.2 mA (both PASS) but
  **S21 topped out at 6.86 dB against a 12 dB floor** — not a sizer bug, a
  real single-stage gain ceiling from 50 Ω output loading (FINDINGS §5 "The
  sizing loop closes"). **Gate G4** (a novel generated topology sized to full
  feasibility) stayed open at the end of Phase 1, blocked on topology, not
  machinery.

**Understanding.** By the end of Phase 1 every pipeline stage worked in
isolation and the loop closed end to end, but the single-stage reference
topology's ~7 dB gain ceiling was structurally below every spec's floor. The
lesson that would repeat for the rest of the project first appeared here:
**a working pipeline with the wrong topology family produces validated
zeros, not almost-successes.**

---

## 3. The frozen protocols — NDL@256 and the regression quartet

**Context.** Once generation could be *steered*, every future claim about
"better generation" needed a measuring stick that couldn't be gamed by
copying.

**Decision (executor).** `novelty.py` was rebuilt around a **Weisfeiler–Lehman
graph hash** compared against the *whole* corpus (not just a sample's own
seed), plus a graded nearest-neighbor similarity. The **NDL@256 protocol** —
256 samples (128 @ seed 1337 + 128 @ seed 2338), fixed batch/token settings,
reporting novel-distinct count, inductor ratio, and copy rate — was declared
frozen: "adoption rule for every future GEN arm: beat NDL@256 at
equal-or-better inductor ratio" (FINDINGS §5 "P0"). A **regression quartet**
(vocab guard, legacy screen, pipeline yield, reference anchor — later a
fifth, spec acceptance) was required green before and after every work
package (HANDOVER Session 1 §4).

**Result.** The frozen baseline: **NDL@256 = 16** under `wifi24`'s screen at
prefix length 12, with `median NN-sim = 1.000` among spec-passing samples —
i.e., more than half of nominally "LNA-shaped" output was an exact graph copy
of something in training (FINDINGS §5). That single number — 16 — became the
bar every later generation arm had to clear, and its companion statistic
(NN-sim) became the standing check on whether "novel" meant anything.

**Understanding.** A frozen protocol only stays honest if its *reference set*
stays honest too — a fact that would come back, sharply, in stage 12 (the
metric-honesty wave), when the reference itself turned out to be
under-counting what the generator could copy.

---

## 4. Phase 2 begins — from "optimize" to "predict, search, optimize"

**Context.** With the Phase-1 pipeline feature-complete, the user's brief
(2026-08-06) asked for a structural change: stop improving the pipeline for
its own sake and instead **convert the system from "generate then optimize"
into "generate, predict feasibility, search, then optimize"** — a learned
critic on the topology graph, critic-guided search, and a self-improvement
loop (plans2/00-OVERVIEW.md, "Brief (user, 2026-08-06)"). This is the
project's first explicit, named user decision to change direction, and it
opens Phase 2.

**Decision (user, brief; executor, translation).** The brief as literally
stated was infeasible: an *unsized* topology doesn't have an S21, so
"predict gain/NF/S11 from the topology graph" needed reframing. The
plan set (`plans2/`) proposed **three reframings**, all executor judgment
calls made explicit and then acted on without further sign-off: (R1) predict
**post-sizing margins**, not raw metrics, with feasibility computed from
margins rather than trained as a boolean; (R2) a **hierarchical label
economy** — cheap L1 op-point labels by the thousand, expensive L2 sizing
labels (~4–5 min each) via a nightly campaign; (R3) a **search ladder**
(rerank → evolutionary → beam-only-if-triggered) sequenced by value per
effort, with the success metric fixed as **SPICE-minutes per feasible novel
design** (plans2/00-OVERVIEW.md §1).

**Result.** Four gated stages were laid out (Stage 0 prerequisites, Stage 1
critic, Stage 2 search, Stage 3 self-improvement loop), each with numeric
gates (C0, C1, S1, S2) and a pre-agreed de-scope ladder for when a gate
fails — "GNN loses to baselines → ship the baseline," "no arm clears C1 →
search waits," etc. (plans2/05-SCHEDULE.md).

**Understanding.** The brief's real content wasn't "build a GNN" — the plan
explicitly says "the brief prefers a GNN; the program needs a filter"
(plans2/02-CRITIC.md §2) — it was *stop paying SPICE cost for candidates that
were never going to work*. Keeping that distinction sharp is what let later
stages ship a non-GNN baseline without feeling like a broken promise.

---

## 5. Stage 0 — the label store, and Gate G4 closed by hand

**Context.** Nothing in Phase 2 could train without labeled data, and the
pipeline had been throwing its most expensive byproduct — every ngspice
invocation — away.

**Decision (user, remote-control; executor, mechanics).** At the start of
this session the user made four explicit calls recorded verbatim in the
handover: **"gain stage = tapped-C output match; NF advisory (Gate G4 gates
S11/S21/Idd, NF logged not gated); branch stays local; run autonomously
through Stage 0 to Gate C0"** (HANDOVER Session 2). This is the project's
first "NF advisory-then-gated" decision — NF would be measured and recorded
from here on, but would not block a design from counting as feasible until a
trustworthy noise harness existed. It would later be promoted to a hard gate
(stage 11).

**Result.** `datastore.py` (append-only JSONL, no new dependencies) landed
with logging hooks in `size.py`/`bias.py`. The **tapped-C gain reference**
(`ref24_tapped.cir`) — a cascode core with a tapped-C output transformer,
following the user's gain-stage decision — sized to full feasibility against
`wifi24`: **S11 −20.1 dB, S21 18.6 dB, Idd 3.15 mA, NF 2.0 dB** (HANDOVER
Session 2). **Gate G4 was closed by hand** — the store's feasible class now
existed at all, which mattered because a feasibility classifier trained on an
all-infeasible set learns "always no" with perfect accuracy (plans2/00-OVERVIEW.md
R1). The series-Rs NF harness also landed here (fixing the port-noise defect
that gave *negative* NF with gain — corpus circuit 464 read −4.5 dB before
the fix), golden-locked to 3.01 dB (FINDINGS §11). By the labeling campaign's
end: **173 L2 rows**, 41 L1 rows, repeat-probe **σ(S21) = 0.32 dB** (under
the ≲0.5 target). Gate C0 (≥150 L2 rows, ≥25% stratum-T, σ measured) was met
once `templates.py` minted 92 hand-designed archetypes as valid token
topologies, pushing the store to 264 L2 rows (FINDINGS §11).

**Understanding.** "Predict feasibility" only works once feasible examples
exist to predict. Closing Gate G4 by hand — a deliberately unglamorous,
un-automated design — was the precondition for everything the critic would
later be asked to do.

---

## 6. Stage 1 — the critic baseline, and the source-shift wall (Gate C1)

**Context.** With labels flowing, the question became whether a cheap
pre-SPICE filter was possible at all.

**Decision (executor, per the plan's mandatory-baselines rule).** Before any
GNN, three baselines (trivial mean, WL-kNN, ridge-on-hand-features) were
built and frozen on the same split, with the explicit rule: **the GNN ships
only if it beats the baselines on held-out families; otherwise the best
baseline ships as critic v1** (plans2/02-CRITIC.md §2).

**Result.** On `v1-train`, the baseline surrogate **cleared Gate C1 on the
family-holdout split** (ridge ρ(S21)=0.68, enrichment 2.44×) but **failed on
the source-shift split** — train on corpus/references, test on generated
arms — dropping to ρ=0.34, enrichment 1.47× (FINDINGS §11). Adding the 88 P5
templates to the training data did **not** close that gap (source-shift held
at ρ≈0.22–0.28 on `v2-train`) — the honest reading was that the generated
*distribution itself*, not a lack of training diversity, was the problem
(FINDINGS §11). The GNN (`critic_gnn.py`, plain-torch message passing, no
PyG) **lost to WL-kNN on the C1 gate** (ρ 0.65 vs 0.77) — WL-kNN was winning
by memorizing near-duplicate corpus structure, exactly as predicted — but
**won the source-shift diagnostic** (ρ 0.34 vs 0.22–0.28). Per the de-scope
ladder, **WL-kNN shipped as critic v1**, the GNN was tried and honestly
beaten (FINDINGS §11). Rung-1 rerank then confirmed the wall in vivo: the GNN
reached 1.74× enrichment on real sized candidates, short of Gate S1's 2×
(FINDINGS §11).

**Understanding.** Every failed gate pointed at the same culprit: the
generator, fine-tuned on 41 corpus LNAs, had memorized ~35 graphs
(`median NN-sim = 1.000`). No amount of critic sophistication fixes a
prediction problem caused by the *candidates* all being near-duplicates of
each other. The lever was never going to be the critic — it was the
generator's training distribution.

---

## 7. P5 — breaking the memorization ceiling, and Gate G4 closed by generation

**Context.** Stage 6 diagnosed the disease; this stage is the cure.

**Decision (executor).** `finetune.py --arm p5` mixed the corpus LNAs
(tagged NB/WB) with Eulerian-augmented `templates.py` archetypes plus
`<LNA_NB>`/`<LNA_WB>` class tokens, and boosted-multi-seed sizing
(`g4_search.py`) was applied to the resulting pool's closest candidates.

**Result.** P5 broke the ceiling decisively: **NDL@256 16→60** (later
corrected, see stage 12), **median NN-sim 1.000→0.574**, inductor ratio
restored to **0.179** (near the corpus's 0.20, after P1/P2 had regressed it
to ~0.10) (FINDINGS §11). Reranking the P5 pool against the old P1/P2 pool
under the *same* critic showed the real story: near-feasible base rate
**62% vs 27%** — a **~2.3× improvement in near-feasible designs per SPICE
budget**, beating anything critic-rerank alone had delivered (1.74×)
(FINDINGS §11). Then, with boosted multi-seed sizing on the six closest P5
candidates, **`seq0240`** — an 8-device, novel topology — sized to full
feasibility: **S11 −11.9 dB, S21 12.6 dB, Idd 1.19 mA**. **Gate G4 was closed
by generation** (FINDINGS §11, HANDOVER Session 2 "★ GATE G4 CLOSED BY
GENERATION").

**Understanding.** "Fixing the distribution beats filtering a bad one." This
became the project's most repeated finding — it would recur at gps-l1 (stage
9) and again in the control-arm experiments (stage 14): a smarter selector
over a bad pool loses to a better pool with a dumb selector.

---

## 8. Stage 3 — the self-improvement loop, last-mile, and phase exit

**Context.** With one feasible generated design in hand, the question became
whether the system could improve *itself* — the brief's Stage 3.

**Decision (executor, per 04-SELF-IMPROVE.md).** Five numeric tripwires (NDL
drop, WL-family collapse, critic-holdout regression, σ drift, feasible-rate
compression) were wired with scripted responses, and a headline curve —
**SPICE-minutes per feasible novel design** — was declared the thing every
loop turn must bend down (FINDINGS §11).

**Result.** Iteration 1: **967 SPICE-min/design** (1 design, `seq0240`).
Iteration 2 (Loop B: fine-tune the generator on its own winners) improved
every generator metric (NDL 60→73, inductor ratio 0.179→0.209) but found **no
new feasible design** — the curve went **967→1093, worse**, recorded honestly
as a non-improving turn (FINDINGS §11). The diagnosis: near-feasible designs
sat in a multimodal all-free-ZOAF landscape where the third constraint stayed
just barely off no matter how many random seeds were thrown at it. **Curated
sizing** (fixing input-match elements at their best-known values, sizing only
gain/bias/current) fixed that: 2 of 3 closest near-misses converted, curve
**1093→367** — Gate I3 met (FINDINGS §11). A start-point-reconstruction bug
in `size.polish` was then found and fixed (parsed topology mismatched stored
params when P5 arms reused `seq*.txt` filenames for different topologies),
fenced going forward by **`size.replay_ok`** — re-evaluating any stored best
point must reproduce its stored metrics within σ, or the row is quarantined
rather than polished (FINDINGS §11, "§1a"). With that fixed, a polish-first
sweep over the closest near-misses converted 3 more: **curve 367→187**,
**feasible-novel designs 3→6**. Two consecutive improving turns with
tripwires quiet met the **phase exit criterion** — Stage 3 was declared **an
operating mode**, not a one-shot build (FINDINGS §11, HANDOVER Session 1
top-line: "★ STAGE 3 PHASE EXIT MET").

**Understanding.** "The funnel's broken stage is near-feasible → feasible
conversion" (plans2/06-LAST-MILE.md) turned out to be exactly right, and the
fix was almost entirely instrumentation and search-landscape engineering
(curation, polish, replay-fencing), not more raw compute. The honestly-recorded
*regression* at iteration 2 — the curve getting worse — mattered as much as
the wins: it is the reason `size.replay_ok` exists.

---

## 9. Broadening — gps-l1 and wideband-sdr (Gate B1)

**Context.** wifi24 was now a "solved" class (6/6 feasible); measuring
progress against it further would Goodhart the loop. The benchmark itself —
`benchmark.py` → `data/benchmark.md` — became the new headline, scored
against two harder specs: gps-l1 (S21≥15 dB @ Idd≤3 mA, NF≤1.8 dB) and
wideband-sdr (broadband S11, ripple≤2 dB). Both read **0/6 feasible**
(FINDINGS §11) — gps-l1 gain-limited, wideband-sdr match-limited.

**Decision (executor, following the plan's diagnosed lever).** New archetype
families — `cs_cs_lna` (two-stage CS→CS) and `current_reuse_lna` for gain;
`rfb_lna` variants and shunt-peaked loads for wideband match — were added to
`templates.py` (92→118 archetypes), then a **P5-v3** fine-tune was run on the
expanded set (BROADEN-PROGRESS.md CP1–CP3).

**Result.** Hand-sizing the new archetypes broke the gps-l1 **gain wall**
(`cs_cs_lna` reached S21 17.5 dB @ Idd 2.76 mA, both hard constraints met)
but the **input match wouldn't co-close** — across all-free ZOAF, polish, and
a 729-point match grid, S11 never dropped below ≈−1 dB while S21 held ≥15
(FINDINGS §11, BROADEN-PROGRESS.md CP1). The generator, not the sizer, closed
the gap: P5-v3's generated pool produced **`seq0089`** (S11 −13.1/S21
15.0/Idd 2.88) and **`seq0215`** (S11 −14.4/S21 15.4/Idd 2.94) —
**Gate B1 MET on gps-l1** (BROADEN-PROGRESS.md, FINDINGS §11). `seq0089` was
generated *matched but gainless* (S11 −13.7/S21 2.4), and polish drove S21
2.4→15.0 while holding the match — "the generator, not the sizer, supplies
the co-sizeable input network" (FINDINGS §11). wideband-sdr stayed at 0
feasible; its generation channel was thin (222 template rows, 0 winners).

**⚠ Later correction (stage 12).** Once the novelty reference was extended
to include the archetype set (`ref-v2`), both `seq0089` and `seq0215` turned
out to be **exact WL-hash copies of the hand-written templates**
(`cs_gi1_dg1_cx1_cc0_R_bf1` and its sibling) — not genuine generator
discoveries. The *sizing* result stands (the generator did supply a
co-sizeable network the hand templates alone couldn't reach on their own
sizing pass); the *topology-discovery* half of the Gate-B1 claim does not
(HANDOVER Session 5, "control experiment" sub-block).

**Understanding.** The honest caveat recorded at the time — NF was gated off,
and these designs' real noise figure (~4.5 dB) sat far above gps-l1's 1.8 dB
target — foreshadowed stage 11's NF reckoning. The later correction about
`seq0089`/`seq0215` foreshadowed stage 12's broader lesson: a claim of
"novel" is only as good as the reference set it was checked against.

---

## 10. The Dhruva blind-protocol arc (D0 / D1 / D2)

**Context.** The user set a new, harder goal: reach the performance numbers
of a published, silicon-measured multi-band GNSS-receiver LNA (Kanchetla et
al., TMTT 2022) — **without the pipeline being shown the paper's circuit**.
This is a deliberate experiment in whether generator + critic + curated
sizing can *find* a topology class, not copy one (plans2/08-DHRUVA-GOAL.md).

**Decision (user).** The blind protocol itself is the decision: the PDF is
removed from the repo, only the spec-number excerpt in
`plans2/08-DHRUVA-GOAL.md` is allowed anywhere in the repo, `templates.py`
may only grow families that are either already in the archetype set or
**generic textbook blocks chosen without consulting the paper** (tagged
`recipe: blind-v1`), and **"whether to unblind is the user's decision, not
the executor's"** if the loop stalls (plans2/08-DHRUVA-GOAL.md, rules 1–3).

**Result.** Four tier-1 specs (`dhruva-l5/l2/l1/s`, one per band: 1.176 /
1.228 / 1.575 / 2.492 GHz) were added, gating S21 at the band's target, S11 ≤
−10 dB **held across 1.1–2.5 GHz** (not just at f0), and Idd ≤ 13 mA
(plans2/08-DHRUVA-GOAL.md §1–2). **Gate D0** (all four evaluable end-to-end)
was met immediately; the honest baseline showed no existing family came
close — a wifi-class candidate sized against `dhruva-l1` read S21 10.6 dB
against a broken S11 (FINDINGS §12). Labeling the whole 118-archetype set
against `dhruva-l1` found **20 single-stage rows, 0 feasible, all binding on
`s11_max ≈ 0`** — no single-stage family could hold a broadband match *and*
tuned gain at once (FINDINGS §12). Following the diagnosed failure mode
(never the paper), a generic **`rfb_cs`** family (resistive-feedback input +
tuned CS gain stage) broke the match wall partially; moving the cascode from
stage 1 to stage 2 (**`cascode2`**) decoupled match from gain but still fell
~1.6 dB short of the gain floor; splitting the gain over **two** tuned stages
(**`rfb_cs3`**) finally closed it: **`rfbcs3_tank_cc21_bf0`** sized to
**s11_max −11.2 dB, S21 37.8 dB, Idd 12.93 mA — feasible** (FINDINGS §12).
**Gate D1 MET.** The *same* topology, re-sized per band, was then feasible
on **all four bands** — **Gate D2 MET**, "the reconfigurable essence": one
family, only device values differing by band (FINDINGS §12, table
reproduced there).

**★ Honest attribution, recorded at the time, not retrofitted.** The feasible
topology (`rfb_cs3`) is an **assistant-authored generic-textbook archetype**,
designed blind and guided by the automated sizer's measurements — **not a
discovery by the P5 neural generator**, whose own pools on the rfb_cs3-bearing
data reached only violation 0.318 at the time (FINDINGS §12). What the
automated pipeline supplied was the sizing, not the topology. A genuinely
*generated* dhruva-l1 feasible design was explicitly logged as the
outstanding, stronger claim (FINDINGS §12) — and it would arrive in stage
11.

**Understanding.** The blind protocol worked as a methodological device
exactly as intended: it forced the team to be honest, in the record itself,
about which half of a "the pipeline designed it" claim was actually true.
That same honesty norm — "attribution matters, and get it right the first
time" — is what stage 12's corrections would later apply retroactively to
Gate B1.

---

## 11. The NF-hard-gating reckoning (Session 4)

**Context.** Every "feasible" design up to this point had NF advisory-only —
measured and logged, per the Stage-0 user decision (stage 5), but never
gating. That was always meant to be temporary.

**Decision (executor, executing the deferred Stage-0 plan).** The port-referred
NF block (known unphysical — negative NF once a stage has gain) was
**deleted** from the sizing deck; the only NF surviving anywhere in the store
became the golden-validated series-Rs measurement. NF became a **hard
constraint** in `spec.objective` (HANDOVER Session 4, "★ WP-D1 DONE — NF is a
hard constraint").

**Result.** All 20 legacy rows were relabeled (`relabel_nf.py`, replay-fenced,
recipe bumped) — **0 quarantined**, but the correction was one-directional
and large: **the old port-referred NF had flattered every design without
exception** (series-Rs minus port: min +0.55 dB, median +2.32 dB, mean +3.93
dB, max +12.58 dB; two rows had actually read *negative* NF) (HANDOVER
Session 4). Re-judging every prior "feasible" design under the new gate (the
**NF-gate survivor contrast**, `nf_contrast.py`) was stark: of **14 distinct
feasible designs, tier-1 (S11/S21/Idd) held for all 14, but tier-2
(NF-gated) held for only 2** (HANDOVER Session 4, "★ WP-D4 DONE"). wifi24 was
still solved at tier-2 — `seq0220` (S11 −13.8/S21 12.6/Idd 2.46/**NF 2.43**)
and the hand `ref24_tapped` reference (NF 2.00) — but everything else died:
**dhruva by +5.4…+8.6 dB of noise, gps-l1 by +2.2/+2.6 dB**. A free,
zero-extra-sim-time **stability harness** (K, |Δ|, μ) was added the same
session and found that min-margin polish, unconstrained by stability, had
walked two feasible wifi24 designs into **K < 1** (potentially unstable)
in-band, exactly because stability was in no objective (HANDOVER Session 4,
"★ NEW HARNESS"). A separate bug — `size.polish` scaling parameters with no
box clamp — was found by the concurrent Track-B agent and fixed by Track A:
**6 of 19 feasible rows had drifted out of the spec's declared device box**;
re-deriving them in-box cost one tier-2 claim (wifi24 `seq0079`'s NF moved
2.48→2.57, failing) but no tier-1 claim (HANDOVER Session 4). Track B, working
in parallel, met its own goal: **`seq0192`**, sampled from a P5-v6 pool, was
the first **generated** (not archetype) dhruva-l1 tier-1 feasible — S11max
−11.49/S21 29.19/Idd 11.09 — the stronger claim stage 10 had flagged as
outstanding. (The P5-v6 checkpoint itself was separately **rejected** under
adopt-only-if-better on NDL grounds; the design survived anyway because it
was replay-verified SPICE truth, not a model claim — HANDOVER Session 4.)

**Understanding.** This was the project's sharpest single correction: a
metric that had been silently wrong in one direction for the program's
entire life, discovered only by building the physically-correct version and
comparing. The lesson recorded verbatim: "a supported-but-missing metric
counts as fully violated" — advisory metrics are a debt, not a convenience,
and they come due exactly when you finally look.

---

## 12. The metric-honesty wave — sigma, the critic retrain, and two rebaselines

**Context.** Session 4's NF reckoning triggered a broader audit: what else in
the measurement stack had quietly drifted?

**Decision (executor measurement; user, for the two protocol rebaselines).**
Three things were checked in the same pass (Track C, HANDOVER Session 4):
label noise, the critic's real accuracy, and the benchmark's fairness. Two of
the findings required changing a **frozen protocol**, which the team had
committed not to do unilaterally — both went to the user for an explicit
decision, recorded in FINDINGS and executed the same night the decision came
back (commit `c32e051`, "plans2 amendments (2026-08-09 user decisions): C1
restated, NDL ref-v2").

**Result — σ(S21).** The "drift" seen across sessions (0.32→1.02→1.27 dB) was
mostly a measurement artefact: repeat-probe grouping had pooled *different
recipes and NF-gating regimes* together (81 of 89 multi-row keys), and
estimated a standard deviation from n=2. Measured properly on 9 seeds/key,
**σ was always ≈1.5 dB**; best-of-3 relabeling brought it to **0.726 dB**
(2× quieter, 3× the sizing cost) — still short of the plan's ≲0.5 dB target,
recorded honestly as such (HANDOVER Session 4, "Track C").

**Result — the critic.** A bug (`_margins` reading only `s11_db`, silently
dropping every broadband-gated dhruva row — ~240 rows, the entire Track-B
corpus) was found and fixed. On the corrected **`v4-train`** (734 rows), the
**source-shift gap that had failed every gate since stage 6 finally closed**:
ρ(S21) **0.221→0.585 (ridge) / 0.609 (GNN)** — and re-running the *old* code
on the *old* snapshot reproduced the old numbers exactly, proving it was the
data, not the model (HANDOVER Session 4). **The GNN shipped as critic v1**
for the first time, per the standing rule, now that it actually beat the
baselines on both splits.

**Result — the NDL reference (ref-v2).** The novelty reference had only ever
been the 41-circuit corpus, so a P5-era generator's **verbatim reproduction
of its own `templates.py` training archetype scored as "novel."** Measured
directly: **~51% of a P5 pool's screen-passing output was exactly that**
(FINDINGS §14.5). The fix extended the reference to 41 corpus + 148
archetypes = **189 hashes** (`ref-v2`, digest `b5689490d0285c37`), versioned
so every historical number stays reproducible under its original reference.
**The re-frozen adopt-only-if-better baseline dropped from nb 100 / wb 35 to
nb 52 / wb 21** (FINDINGS §14.5). Critically, the correction is **not a
constant offset** — it ranges 0 (for corpus-only arms, which cannot copy
templates) to −50, scaling with how much archetype mass an arm trained on —
and it is **not order-preserving**: P5-v2 rises from 5th to 3rd place under
the new reference, overtaking P5-v4 and P5-v5 (FINDINGS §14.5, "the flip
check"). A careful re-audit confirmed **no historical adopt/reject decision
actually flips** — five proven by direct re-measurement, one by monotonicity
(`ref-v2 ⊋ ref-v1` implies `NDL_v2 ≤ NDL_v1` always), one by inference from
the P0 baseline's 0% archetype-copy rate — but the *reasoning* Track B had
originally given for that conclusion was itself wrong, and the corrected
reasoning is what's recorded (FINDINGS §14.5).

**Result — Gate C1's enrichment bar.** The literal "enrichment ≥ 2×" bar had
a hidden ceiling: `ceiling = min(1/k_frac, 1/base_rate)`, and as the
candidate pool's own base rate of near-feasibility improved (0.268→0.455 on
the source-shift split), the ceiling **fell** 3.74×→2.20× — so "≥2×" was
quietly becoming "achieve near-perfect precision," an unwinnable bar that
was tightening *because the pipeline was getting better*, exactly backwards
(FINDINGS §14.6). The restated gate — **skill = (precision@20% − base) /
(ceiling − base)**, 0 for random selection, 1 for a perfect ranker at any
base rate, gate at **skill ≥ θ = 0.25** — was derived, not fit: θ=0.25 is
the unique constant that reproduces the old bar's meaning everywhere the old
bar was well-posed (FINDINGS §14.6). Under the restatement, **all three
model arms (WL-kNN, ridge, GNN) pass on the family-holdout split; ridge and
GNN pass on the harder source-shift split, WL-kNN does not** — a materially
different, more informative verdict than the old bar's uniform "no"
everywhere (FINDINGS §14.6).

**Result — the benchmark.** Refreshed at full sizing budget (vs. the earlier
"lean-budget" table that had understated wifi24 as 4/6 against a true
10/12), now reporting tier-1 and tier-2 separately: **wifi24 10/12 tier-1,
1/12 tier-2**; every dhruva band and gps-l1/wideband-sdr still mostly
infeasible, binding almost entirely on `s11_max` (dhruva) or `s21`/`s11`
(gps-l1/wideband-sdr) (`data/benchmark.md`, HANDOVER Session 4).

**Understanding.** This stage is the clearest instance of the project's
standing honesty mechanism in action: a frozen protocol is a promise, and
breaking that promise — even for a good reason — requires surfacing the
break explicitly and getting sign-off, not quietly re-basing a number. The
team's own summary line captures it: correction magnitudes are not constant,
orderings are not always preserved, and *both facts get reported*, not just
the reassuring one.

---

## 13. Evolutionary search and the critic-coverage collapse (WP-SEARCH rung 2)

**Context.** With critic v1 (GNN) finally clearing Gate C1 on both splits
(stage 12), the plan's rung-2 evolutionary search over graph edits became
worth running.

**Decision (executor, per 03-SEARCH §2).** `moves.py` implemented 17 one-edit
graph mutations plus archetype-decomposition crossover; `evolve.py` ran a
population-based search with all four trust rules from the plan mechanically
enforced (conservative scoring `mean − β·σ`, an uncertainty gate, a trust
region, exploration-stratum true evals); `evolve_score.py` made critic v1 a
persistent scorer.

**Result.** A genuinely novel, tier-1-feasible, **stable** `dhruva-s` design
emerged (`8c7592ea…`, 16 devices): S11max −10.94/S21 34.89/Idd 11.84/**NF
5.58**/K_min 6.54 — the best NF among tier-1-feasible dhruva-s designs at the
time, down from 8.88 dB (HANDOVER Session 5). **Gate S2 was NOT met** on
either spec tested (0 tier-2-feasible designs in all four arms), but the
evolutionary arm won every SPICE-measured axis on dhruva-s against its
equal-budget control (HANDOVER Session 5). The single number that mattered
most, though, was a **collapse**: critic v1 held ρ(S21)≈0.83 on its own
family holdout but **fell to ρ≈+0.17–0.20 on the mutant distribution search
actually generates**, and on the elites it had *selected*, residual
correlation ran 0 to −0.33 (HANDOVER Session 5). Diagnosed as **coverage, not
capacity**: `v4-train` held only 16 wideband-sdr and 24 dhruva-s rows out of
734; the search session itself appended 213 more (105/108), taking those
specs from 40 to 253 rows. Separately, the **uncertainty gate was found
inert**: `n_high_unc = 0` across 80 generations in all four runs — the
ensemble was *confidently wrong* off-distribution rather than visibly
uncertain — while the **trust region** (limiting offspring distance from
labeled families) was the rule that actually worked, keeping the evolve arm's
population inside the labeled radius where the control arm's drifted
entirely outside it (HANDOVER Session 5).

**Understanding.** "The critic's collapse was coverage" — not a model
failure, a *data* failure, and specifically a failure of the holdout/eval
protocol to test the exact distribution search would generate. This
motivated stage 15's direct fix (mutant-aware evaluation) and is the clearest
example in the project of a plan's trust mechanism (the uncertainty gate)
being measured, found not to work as designed, and retired rather than kept
on faith.

---

## 14. Do the templates matter? — the control and curriculum experiments

**Context.** P5's templates had been the load-bearing fix for the
memorization ceiling (stage 7) and the gps-l1 gain wall (stage 9). A natural
question followed: is the templates' *product* genuine novelty, or just
structural scaffolding that happens to correlate with it?

**Decision (executor, a controlled measurement, "nothing here is adopted"
per its own framing).** Fine-tune arms from the same upstream checkpoint,
identical recipe to P5-v3, with every archetype sequence **removed**
(`ctrl-v1`) or removed **and never seen at all** (`ctrl-v1s`), then compare
against P5-v3 on the frozen protocol (HANDOVER Session 5, "control
experiment").

**Result.** Templates buy **structural yield**, not per-sample novelty: P5-v3
reached spec-L0 pass rate 80.5% vs the templates-free `ctrl-v1`'s 35.5%, but
NDL *per screen-passing sample* was actually *higher* for the control (0.46
vs 0.25) (HANDOVER Session 5). About half of P5-v3's genuine novelty
survived complete template removal, and the control's best feasible design
sat at NN-sim 0.64 from the reference where P5-v3's sat at 0.94 — "the
baseline's novel front is largely template-perturbation" (HANDOVER Session
5). A follow-up **curriculum** experiment (train with templates early, drop
them for a template-free tail late) was **pre-registered before a single
epoch trained** (commit `6519abf`) on the hypothesis that this would keep
the yield and recover the control's novelty. It was **refuted, with a
dose-response curve**: one template-free epoch took verbatim archetype
copies from 37.9%→6.6% while corpus copies rose 31.6%→60.5% — **"the
copying does not stop, it migrates."** A tail-length sweep showed a monotone
decline (NDL 52→39→27→16 as tail length K went 0→1→4→12), with **no interior
optimum — the best tail length is zero** (HANDOVER Session 6, "curriculum
experiment"). Both curriculum arms were explicitly **not promoted**
(adopt-only-if-better failed against the re-frozen nb 52 baseline).

**Understanding.** The reframe, stated in the record itself: "the archetypes
are load-bearing for novelty after all, not because they *create* it but
because they are the only thing crowding out corpus memorization. The lever
is more and more varied structure in the data, not a schedule that removes
structure" (HANDOVER Session 5/6). This directly motivated stage 15 — if more
structure is the lever, go get more structure.

---

## 15. Real-data expansion — the corpus grows 41 → 50 (ref-v3)

**Context.** Stage 14's conclusion pointed at data diversity, not clever
training schedules, as the next lever. A parallel effort surveyed for
*real*, citeable LNA circuits beyond the original 41.

**Decision (executor initiative; no explicit user sign-off is recorded for
the ingestion itself — it followed the same "necessary enabler, not scope
creep" pattern as the P5 template corpus).** A structured survey ranked
sources by yield: IHP-GmbH's open-source SG13G2 tapeouts (Apache-2.0, real
taped-out silicon, MOS and SiGe HBT, renewable — a new tapeout lands every
1–2 months) ranked first; ALIGN's CircuitsDatabase (one real differential
LNA) second; hand-transcription of cited textbook/paper archetypes third
(`data/reports/data-expansion-2026-08-09.md`). Everything else checked —
AnalogGym, MAGICAL, AICircuit, GitHub's hobbyist LNA repos — yielded nothing
usable for this specific ask.

**Result.** **9 attempted, 9 ingested, 0 quarantined**, through a six-gate
ladder (provenance/blind-protocol check, Eulerian augmentation, structure,
vocabulary round-trip, WL-identity vs. the converter, ngspice op+sp+noise)
(HANDOVER Session 6). All nine were structurally novel (max NN-sim 0.612) and
all nine labeled **infeasible** at the cheap ingestion budget — "the
informative outcome, not a defect" (HANDOVER Session 6). Along the way,
`to_spice.py` gained **NPN/PNP emission** — the vocabulary had always
supported bipolar devices, the emitter simply never used it — golden-checked
against closed-form Gummel-Poon algebra (NPN β 193.0 vs predicted 192.9, fT
68.6 GHz at 1 mA) (HANDOVER Session 6). The novelty reference was re-frozen a
second time as **ref-v3** (50 corpus + 148 archetypes = 198 hashes, digest
`d05390da6183123e`), but this time the **measured correction was exactly
zero on every one of 11 pools checked** — none of the nine new circuits had
ever been in a training set, so **0 of 7 adopt/reject decisions flip**, this
time provably rather than by audit (FINDINGS §19, via HANDOVER Session 6).

**Understanding.** The zero-correction result on ref-v3 is itself informative
by contrast with ref-v2's large, non-uniform correction (stage 12): a
reference expansion only perturbs history if something in that history could
have copied the new content. That is now a standing sanity check for any
future reference change. The generator itself was **deliberately not
retrained** this session — expanding the corpus and re-training on it are
kept as separate, separately-measurable steps.

---

## 16. Critic v2, and the first honest rung-1 verdict (Gate S1)

**Context.** Stage 13 had diagnosed the critic's field failure as a coverage
problem; the search session's own 213 new evolve-arm rows, plus stage 15's
ingestion, gave the next retrain real material to fix it with.

**Decision (executor).** Retrain on the full store (`v5-train`, 1010 L2 rows,
sha256-pinned against three other agents writing concurrently) and build a
**mutant-aware evaluation** (`--mutant-eval`) that specifically tests the
evolve-arm distribution the old frozen splits never touched.

**Result.** On the standard frozen splits, verdicts were unchanged from
`v4-train`, with one flag for the future: **ridge now beats the shipped GNN
on the source-shift split** (ρ 0.631/skill 0.453 vs GNN's 0.586/0.414) — "the
GNN is the best arm" needs re-checking at every retrain, not assumed
(FINDINGS §20). On the mutant-aware evaluation, stage 13's collapse was
**substantially repaired**: on selection-free control arms, ρ(feasibility)
rose from +0.173→**+0.441** (dhruva-s) and +0.198→**+0.502** (wideband-sdr);
on the elites the critic had actually *selected*, ρ went from *negative*
(−0.224 on wideband-sdr) to **+0.479/+0.641** (FINDINGS §20). Still only
~55–60% of the in-distribution ceiling — "coverage is not an exhausted
lever," and a leaky upper-bound test showed the remaining gap is a
**generalization gap across topology families**, not model capacity
(FINDINGS §20). The uncertainty gate, examined again with better coverage,
fired even less often (22/213→8/213 mutants, 2/110 on a live pool) — the
team's recommendation: **retire it, keep the trust region, replace it with a
distance-to-training-set gate** (FINDINGS §20).

Rung 1 then ran **live** for the first time — not retrospectively on
already-sized candidates — against `dhruva-s`, with a leak-free ranker (all
store rows sharing a pool WL-hash dropped before training) and a seeded
random control from the identical pool. **Gate S1 — NOT MET on its literal
"≥2×" wording** (1.88×, Fisher one-sided p=0.055) **but MET on the restated
skill bar** (0.328 vs θ=0.25) (FINDINGS §20). Realized-vs-predicted ρ = 0.578
over all 54 sized candidates — 3× the critic's earlier mutant-distribution
figure, and the first deployment-distribution number from a genuinely live
generated pool. The critic's edge was largest exactly where it mattered most:
**NF (3 vs 9 designs beyond the −1 margin threshold)** — the constraint Gate
D3 was stuck on.

**Understanding.** Reporting both the literal-gate miss and the
restated-gate pass, side by side, rather than picking whichever reads better,
is the same honesty discipline stage 12 established, now applied routinely.
The critic had, by this point, gone from "loses to a lookup table" (stage 6)
to "usefully ranks a live generated pool on the exact constraint the program
is stuck on" (this stage) — genuine progress, reported without inflating it
past what the numbers say.

---

## 17. The NF wall — Gate D3 measured, not closed

**Context.** Every thread — the Session-4 hard-gating of NF (stage 11), the
evolutionary search's best `dhruva-s` design (stage 13), and critic v2's
NF-ranking edge (stage 16) — pointed at the same remaining target: Gate D3,
NF ≤ 3.5 dB on at least one dhruva band under the trusted harness.

**Decision (executor).** Recognized that the tool handed over from stage 13
(`size.polish`, which ascends the *minimum* margin) structurally could not
solve this problem: once a design's gain is well above its floor, polish
values that surplus at exactly zero, so it can never trade gain slack for
noise. The fix was a new optimizer mode, **`size.constrained_descent`** —
optimize one metric while refusing any step that pushes a *kept* constraint
below its floor, scored lexicographically (HANDOVER Session 6, "WP-NF").

**Result.** The noise/gain trade was measured end to end, and it is a wall
with a *shape*, not a distance: **+1.39 dB of NF per +8.35 dB of S21**, dense
and monotone along the front (HANDOVER Session 6). The best tier-1-feasible
`dhruva-s` NF improved **5.58→4.89 dB**; the program-best total violation on
that band improved **0.566→0.222** (2.5×), at 27.6 dB of real gain — not a
shrink-to-nothing optimum. The first design in the program to measure **NF ≤
3.5 dB with the match held** appeared (`ce39a77c…`, NF 3.416 at s11_max
−10.04) — inside the tier-2 target for once, though not yet on a
tier-1-feasible sizing. **Gate D3 itself was NOT met.** The move that would
break the remaining gap — a second gain stage, "nearly free in noise by
Friis" — is **blocked by `device_budget`, currently capped at 16**, which
every near-wall design already touches. Raising it again was **deliberately
not done**: "raising it is a spec change" and the session explicitly left
that decision for the user, the same way the original `[3,12]→[3,16]`
widening had been justified by measurement rather than by gate-convenience
(HANDOVER Session 6, "WP-NF", "Where to pick up" item 1). A structural,
not-parametric finding closed the stage: designs that hold the match cannot
get below ~3.4 dB of noise with gain; designs below ~2.8 dB of noise cannot
be made to match at all on their current graphs — "the match is structural,
not parametric" for those topologies (HANDOVER Session 6).

**Understanding.** Gate D3's remaining gap converted, over the course of the
project, from "a missing measurement" (Session 4, NF wasn't even trustworthy)
to "a search failure" (Session 5, the sizer never found the cancellation
locus) to "a conversion rate" (this stage, a measured dB-per-dB exchange
rate) to "a device-budget decision" (this stage's close) — each
re-diagnosis a genuine narrowing, not a restatement, and each handed to
exactly the right owner (search engineering, then the user) rather than
worked around silently.

---

## 18. WP-BIAS v3 — the DC-return rules, and the third measurement that finally agreed

**Context.** WP-BIAS v1 (Phase 1) had classified source and drain nodes with
no DC path but deliberately never fed them, on a "measure before adding
rules" principle — the original off-MOS split (15 source-no-DC-path,
16 drain-no-DC-path, 12 load/sizing) was recorded with the escalation
pre-approved "when it blocks sizing yield" (HANDOVER Session 1 finding #9).
Two more measurements landed on the same conclusion since: stage 15's
ingestion found 4 of 9 real externals had non-conducting MOS, every one under
`sources_no_dc_path` (FINDINGS §19.2), and stage 17's opt-in gate-only
rescue, which promoted rail-reaching gates to bias nets, gained **0 of those
4** (FINDINGS §17.6) — proof a gate-only rule structurally cannot fix a
source problem.

**Decision (executor).** Two DC-return rules were built — **R-SOURCE** (a
source with no DC path gets a return resistor to its device's rail) and
**R-DRAIN** (the same for a drain, to the opposite rail, as a load feed) —
and then shipped **opt-in, not default-on**, as a deliberate choice, not
caution for its own sake: unlike R-GATE (which only defines DC on an
undefined node), a source-return resistor **changes the circuit**, and
`size.size_topology` calls `insert_bias` on every sizing run, so turning it
on by default would silently re-domain every future L2 label. "That decision
is queued, not taken" (HANDOVER Session 6, "WP-BIAS v3").

**Result.** On the 41-circuit corpus, all-MOS-on rose **22/41 (54%) → 25/41
with R-SOURCE → 26/41 (63%) with both**, with **0 circuits made worse** in
any configuration; the off-MOS population collapsed **43→21** (source
15→3, drain 16→6), while the **12 load/sizing off-devices did not move at
all, in any configuration** — confirming, for the third time, that this
remaining class is WP-SIZE's problem (unsized loads forcing triode), not a
bias-rule gap (FINDINGS §21.2). On the 9 ingested externals, **3 of the 4
previously-blocked circuits are fully fixed, all by R-SOURCE alone at the
grid's smallest resistance (200 Ω)**: `paper-diffcccg` 0/2→2/2,
`align-lna-qm` 1/2→2/2, `paper-gmboostcg` 1/2→2/2 — all-MOS-on externals
went 5/9→8/9 (FINDINGS §21.3). **The fourth, `ihp-lna-2p45g`, is honestly
diagnosed as not a bias problem at all**: one of its two off transistors has
all four pins on VSS (a layout dummy the converter's own provenance note had
already flagged) and the other has its gate tied to its own source
(Vgs≡0 by construction) — the guard correctly declines both, because no
resistor changes a structurally-zero Vgs (FINDINGS §21.3). A side finding:
the rule is *offered* to 24 of 41 circuits but only *adopted* by 13 — the
other 11 are false positives from the DC-graph treating a MOS channel as an
open, so a legitimate cascode's interior nodes look like "no DC path" even
though the stack conducts fine once biased (FINDINGS §21.2).

**Understanding.** "The ≥80% acceptance bar is now a sizing problem, not a
bias problem" (FINDINGS §21.5) — after three rounds of "diagnose, then add a
rule," the residual gap has not moved under any rule in three sessions, and
that itself is now the finding. `paper-diffcccg`'s fix and its remaining
limitation (a differential tail current source the single-ended token
vocabulary still cannot represent at all) is the second independent circuit
pointing at the same token-vocabulary gap stage 15's transformer coupling
had already flagged — two unrelated real designs converging on the same hole
is stronger evidence than either alone.

---

## 19. Recalibrating `wideband-sdr` against silicon — and a metric bug that was there from day one

**Context.** `wideband-sdr`'s numbers had never been anchored to real
designs the way `wifi24`, `gps-l1`, and the Dhruva bands eventually were —
they were written from the Phase-1 plan verbatim on WP-SPEC's first day
(commit `cfa1721`), arbitrary stretch goals rather than a calibrated target.

**Decision (user — recalibrate from silicon; executor — the survey and the
audit).** A three-agent, 44-source literature survey of measured-silicon
CMOS wideband/inductorless LNAs was commissioned, covering the
noise-cancelling/resistive-feedback lineage, TV-tuner/UWB front ends, and
recent (2012–2024) low-power inductorless designs — **12 distinct
measured-silicon designs kept**, with every SIMULATED-only candidate found
along the way identified and explicitly excluded rather than silently
dropped (FINDINGS §22, §22.1). The blind protocol was honored with an extra
margin: Kanchetla et al. TMTT 2022 was hard-excluded from all sourcing
"stated regardless of it not actually being an SDR-LNA paper" (FINDINGS §22
header note).

**Result.** Verifying the spec file's own claim ("constraints hold across
the whole band, not at a spot frequency") before trusting it as a baseline
found that claim **false, and had been false since day one**: the S11
constraint gated `s11_db` — `extract.py`'s value **at f0 only** — never
`s11_max_db` (the worst case over `[f_lo,f_hi]`, already computed, never
gated). Three independent pieces of evidence marked it an oversight, not a
design choice: `critic.py`'s own comment already documented "broadband specs
gate `s11_max_db`"; every `dhruva-*` spec (added later) correctly gates
`s11_max_db`, with `wideband-sdr` the sole holdout; and stage 17's own prose
about "the f0 match" had already been quoting `s11_max_db` numbers under the
wrong label without anyone noticing (FINDINGS §22.2). **Fixed: the
constraint now gates `s11_max_db`.** The recalibration itself: S11's metric
was corrected (value held at −10 dB, now confirmed against 6 of 7 comparable
published designs); NF held at 3.5 dB (10 of 12 surveyed designs clear it
with margin); **gain tightened 12→14 dB** (literature clusters 14.5–23 dB;
12 dB sat below every design but two low-power outliers); ripple held at
2 dB; Idd held at 8 mA but re-derived by power-normalizing every literature
design to the fixed 1.1 V rail across process nodes (FINDINGS §22.3).
Re-judging the store's 134 existing `wideband-sdr` rows from their stored
metrics (no new SPICE needed) found **still 0/134 feasible either way**, but
the best recorded violation got numerically **worse, correctly**: 1.375 →
2.055, because the old number had been free of any real S11 penalty — its
record-holder passed the spot check at −17.7 dB while its true worst-case
match was −3.6 dB (FINDINGS §22.4). **Sharper diagnosis:
`s11_max_db ≤ −10 dB` has never once been cleared by any of the 134 stored
rows, at any NF/gain trade-off** — versus 29/134 (22%) that had passed the
wrong, easy gate. Six of the twelve surveyed literature designs are
explicitly 0-inductor, which is evidence the wall is a **topology-library
gap** (no archetype here implements a multi-path feedback match like Sobhy
et al., TMTT 2011) rather than a physical impossibility (FINDINGS §22.5).

**Understanding.** This is the same shape of correction as stage 11's
port-noise NF defect: a metric that had silently not enforced what its own
documentation, and its sibling specs, already assumed it enforced. "The
story was 'NF and ripple are the wall, S11 is fine'... under the metric the
spec always meant to enforce, the story is 'S11 has never once been solved
band-wide, at any NF/gain trade-off, in 134 attempts'" (FINDINGS §22.5) —
this sharpens rather than contradicts the earlier structural-match
diagnosis; the wall was always there, just uncounted.

---

## 20. The `device_budget` unlock — Gate D3 to within 0.20 dB

**Context.** Stage 17 had left Gate D3 with a wall of known shape but no
path through it: the one move that could break the NF/S21 trade — a second
gain stage — could not even be *proposed*, because every frontier
low-noise design already sat at the 16-device ceiling.

**Decision (user-approved, measurement-calibrated).** "The user approved the
widening on that measurement" (FINDINGS §23.2). `device_budget` moved
**16 → 18 on the four dhruva specs only** (`gps-l1`/`wifi24`/`wideband-sdr`/
`legacy-lna5` untouched), calibrated — not requested — against the nearest
real device count in the full 50-circuit reference set: `ihp-lna-2p45g`, an
IHP SG13G2 open tapeout at **2.45 GHz** (the closest real analogue to
`dhruva-s`'s 2.492 GHz), has **18 devices**. "18 is the measured device count
of the nearest-in-frequency real silicon LNA, which is why the bound stops
there and not at 19 or 21. Had the gate needed 20, the honest answer would
have been to stop." (FINDINGS §23.1) Verified enforced, not removed: the
19-device `align-lna-qm` is still rejected under the new bound.

**Result.** With slack for a second stage, `moves.stage_add` (append an
AC-coupled CS stage, cost 3 devices) was applied to `7b0b485b` (`nccgcs_s1_R`,
14 devices, stage 17's second-best noise floor): **S21 18.95→28.51 dB for
NF 3.86→3.92 dB — +9.56 dB of gain for +0.06 dB of noise**, the Friis
cascade prediction measured directly for the first time rather than merely
asserted (FINDINGS §23.2). Two further edits (`load_swap`, `degen_add`)
reached the new 18-device ceiling: **`f578743ae13296d0`** — S11_max −10.02 /
S21 33.74 / Idd 10.83 / **NF 3.70** / K_min 240, tier-1 feasible with NF the
sole violated constraint, **violation 0.398→0.059 (6.7×)**. The exchange
rate itself improved **4.5×**, from stage 17's 0.166 dB NF per dB of S21 to
**0.030 dB/dB** on the new front (FINDINGS §23.3). `dhruva-l5`'s best design
(also 18 devices) reached NF 3.31 dB, short by 0.81 dB — `dhruva-s` remained
the closest band, now by a wider margin. `dhruva-l2`/`l1` were not run this
session; neither beating `dhruva-s` is stated as an inference, not a
measurement (FINDINGS §23.4).

**Gate D3 — still NOT MET, by 0.20 dB.** The section closes with an explicit
act of self-restraint: `f578743ae13296d0` carries 3.74 dB of gain slack,
worth only ~0.11 dB of noise at the measured rate — not quite enough, which
is exactly why four seeds converge at 3.70. The same calibration logic that
justified 18 would justify 20–21 (`align-lna-qm` at 19, `ihp-gps-lna-npn` at
21), but the widening was **explicitly not made this session**: "That is a
user decision, and it should be made on whether 20 devices is a defensible
LNA — not on the fact that it would close the gate" (FINDINGS §23.5).

**Understanding.** The Friis prediction — that a second gain stage should be
nearly free in noise — had been *asserted* since stage 17; this stage is
where it became a *measurement*. And the explicit refusal to widen the
budget one more notch just to close a gate, even with the exact number in
hand, is the same standing discipline as stage 12's metric governance:
a spec constraint changes only on evidence, on purpose, with the person who
owns the tradeoff deciding it — not on gate-convenience.

---

## 21. P5-v7 — real data at last, and a cleanly-attributed jump in novelty

**Context.** Stage 14's control/curriculum experiments had ended in a
reframe rather than a result: the `templates.py` archetypes are load-bearing
for novelty not because they *create* it but because they are the only thing
crowding out corpus memorization — "the lever is more and more varied
structure in the data, not a schedule that removes structure." Stage 15
(the corpus ingestion) supplied exactly that — 9 real circuits, 481
augmented rows, corpus 41→50 — but the generator was deliberately **not**
retrained at the time, keeping "expand the corpus" and "retrain on it" as
separately measurable steps. This stage spends that data.

**Decision (user — ingest the 9, made in stage 15; executor — spend it as a
controlled fine-tune experiment here).** P5-v7 was built as the adopted
P5-v3 recipe with the corpus expanded and **nothing else** changed — same
template scaffolding, no curriculum schedule, both stages reusing P5-v3's
own emissions. Because v7 also happened to use a fresh stage-A retrain (not
literally the same checkpoint lineage as the shipped P5-v3), the executor
built a same-session **attribution control**, `v7ctl`: v7's exact pipeline,
rerun with the external corpus removed, to isolate the corpus as the only
variable (FINDINGS §24.1).

**Result.** `v7ctl` reproduced P5-v3 **to every measured digit** — nb NDL 52,
spec-L0 80.5%, copies 69.5% (37.9%/31.6%), inductor ratio 0.224, wb NDL 21,
spec-L0 37.5%, and a stage-B best-val of 0.2300 at epoch 1, P5-v3's
documented value exactly — proving the pipeline deterministic under seed
1337 and that "v7 − v7ctl is the nine ingested circuits and nothing else...
the most important row in the section" (FINDINGS §24.1). Headline:
**nb NDL@256 52→79 (+27, +52%) and wb 21→41 (+20, +95%)** under `ref-v3` —
the largest generator gain of the whole ref-v2/v3 era, more than double what
the entire 92→118 archetype expansion had bought (+11) (FINDINGS §24.2).
The mechanism, measured precisely: it displaced **archetype** copying
(37.9%→14.5% nb) while leaving **corpus** copying essentially untouched
(31.6%→32.0%) — the exact converse of stage 14's curriculum result, which
had cut archetype copies to 6.6% while corpus copies *rose* to 60.5%, a net
NDL *loss*. **"Removing structure relocates copying; adding structure
dissolves it"** (FINDINGS §24.2) — the stage-14 reframe confirmed by its own
converse, the first hypothesis in this program tested in both directions.
NDL per screen-passing sample nearly doubled (0.252→0.446 nb), and the wb
channel broke its exact-copy median for the first time (NN-sim 1.000→0.756).
The nine new circuits themselves were barely imitated at all — copied only
**0.4%** of the time, with the novel front's similarity to them (0.494
median) actually *lower* than the baseline's incidental similarity to them
(0.528): "they acted as variety pressure, not as content" (FINDINGS §24.4).

**Costs, stated plainly, not papered over.** nb structural yield (spec-L0)
fell 80.5%→69.1% — the archetypes' yield gain partly spent back — and the
**wb inductor ratio regressed the wrong way, 0.077→0.132**, for a spec that
caps inductors; a strict per-channel reading of adopt-only-if-better
genuinely **fails** on that clause (FINDINGS §24.2, §24.3). **Verdict:
ADOPT** anyway, on the nb channel's +27 margin and every copy-related
tripwire moving the right direction on both channels — with both costs
flagged for the next session rather than hidden. New baseline:
`ft_p5v7_v2.pth`, nb 79 / wb 41 under `ref-v3`. The novel front grew 49%
(67 vs 45 candidates) before a single simulation, and produced one new
tier-1-feasible wifi24 LNA (`seq0066`, S11 −16.94 dB, 4 dB better match than
the prior feasible winner) and the generator's closest-ever approach to
`dhruva-l1`'s gain floor (`seq0093`, S21 24.21 against a 25.4 dB target,
broadband match still the wall) (FINDINGS §24.4).

**Understanding.** "Three sessions have now asked the same question three
ways" (FINDINGS §24.5): removing the templates (stage 14's control) kept
about half the novelty and lost most of the yield; removing them on a
schedule (stage 14's curriculum) made novelty fall monotonically as copying
migrated; adding real data (this stage) made novelty rise sharply as copying
dissolved. "The variable that matters is the structural variety of the
training distribution, and none of the three arms that manipulated the
*schedule* moved it." The uncomfortable corollary: nine circuits (5.8% of
the training rows) bought +27 NDL but also cost 11.4 points of yield and the
wb inductor regression — a 22% corpus expansion is not a free lunch, and
whether the effect scales linearly with a second ingested batch is now an
open, explicitly-flagged experiment rather than an assumption.

---

## 22. ★★ Gate D3 MET on `dhruva-s` — and why the previous stage's own extrapolation was wrong

**Context.** Stage 20 had closed to within 0.20 dB of Gate D3 on `dhruva-s`
and explicitly deferred the next `device_budget` widening to the user, on
defensibility grounds rather than gate-closing grounds.

**Decision (user-approved, calibrated to the same standard).**
`device_budget` moved **18 → 21** on the four dhruva specs only, calibrated
to the **largest real device count in the entire 50-circuit reference
set**: `ihp-gps-lna-npn`, a real IHP SG13G2 **GPS-band** LNA — the same
navigation-receiver role the dhruva specs target — at **21 devices**. "So 21
is where this line of justification runs out: no further widening has a
corpus circuit to point at" (FINDINGS §25.3).

**Result — ★★ Gate D3 is MET on `dhruva-s`.** Two independent designs clear
all four gated constraints, the first NF-gated feasible dhruva LNAs in the
program: **`ace8383c2fa68d03`** (20 devices, `moves.stage_add` off parent
`6f0d080f91dfc642`) — S11_max **−10.370** / S21 **34.374** / Idd **11.561** /
**NF 3.240**, K_min 173.2 in band / 57.8 over 0.1–20 GHz, unconditionally
stable; and **`ced0d8bd36ed4890`** (20 devices, same move and parent) —
−10.537 / 39.151 / 12.825 / **3.253**, K_min 64.1 / 18.1 (FINDINGS §25.1).
Audited independently, not just trusted: a new `_nf_gate_d3.py` rebuilds
each topology from the row's own tokens, re-evaluates at the row's own
`best_params`, and re-measures `spec.feasible()` from scratch — **replay 5/5
(and 3/3) identical, spread 0.0000 on every gated metric; in-box 30/30;
novel against `ref-v3`** (nearest reference circuit at NN-sim 0.806/0.781)
(FINDINGS §25.1).

**The section's real finding is a correction of stage 20's own reasoning.**
Stage 20 measured a 0.030 dB/dB exchange rate and predicted a third stage on
the *frontier* design (which held 3.74 dB of gain slack) would supply the
missing ~0.11 dB. Both halves were actually run, and the prediction was
wrong: a third stage added to the **already-relaxed** frontier design
(NF already 3.70, gain to spare) moved NF only 3.70→3.71 despite +13 dB of
new gain; the *same* move applied to a **different, quieter-but-starved**
design (`6f0d08`, NF 3.33 but only S21 21.3) moved NF **3.33→3.24 — an
improvement** — for the same +13 dB of gain (FINDINGS §25.2). Friis read
properly: extra gain lowers total noise figure only while the input stage is
still being over-driven to produce gain it shouldn't have to; stage 20's own
achievement (relaxing the frontier stage's current) had already collapsed
total NF to the first stage's NF alone, leaving nothing left to convert.
**"The front is not a smooth exchange curve; it is two regimes with a knee,
and [stage 20] extrapolated across the knee."** The transferable, general
rule: **"the parent to grow is the quietest one, not the best one"** —
`6f0d08` had the *worst* total violation of the candidates considered
(0.289 vs. 0.059) and was the only one that reached the gate (FINDINGS
§25.2).

**A second honest correction, about the widening itself.** "The gate needed
20 devices, not 21" — `stage_add` costs 3 off a 17-device parent, so the
binding fact was 20 > 18; both D3 designs are 20 devices, and the only
21-device design built (`3a5fc1`) is the one that bought nothing. "A
widening to 20 would have closed the gate identically. This is recorded so
the next request of this kind is sized to the measured need" (FINDINGS
§25.3) — the second consecutive device-budget grant (stage 20's 18, this
stage's 21) to turn out larger than what the measured result actually used.

**Per band.** `dhruva-l5` is still **NOT MET**, short by 0.81 dB (best
3.31 dB) — and is diagnosed as sitting on the *far side* of the same knee:
every l5 candidate is already tier-1 clean with gain to spare, so more gain
*or* more devices measures inert there; closing it "needs a quieter input
stage, not more devices" — a topology question, not a sizing one (FINDINGS
§25.4). `dhruva-l2`/`l1` were not run; neither is inferred (not measured) to
beat `dhruva-l5`.

**Attribution, stated precisely, per the blind-protocol discipline.** This
is **search plus sizing, not generation**: the lineage is the blind-v1
archetype `nccgcs_s1_R` → evolutionary/1-edit moves (`load_swap` →
`stage_add`) → `constrained_descent`. No generator sample is involved, so
this is explicitly **not** the "the pipeline designed it" claim Track B's
`seq0192` made (stage 11). The blind protocol held throughout — every move
is a generic textbook edit from `moves.py`, no paper circuit content
anywhere. Still open, qualifying the engineering claim rather than the gate:
`iip3_dbm` remains `unsupported` (tier-3), and stability remains
frequency-domain with ideal elements only.

**Independent confirmation.** `benchmark.py`, a completely different code
path (its own curated recipe, re-sizing from stored tokens rather than
replaying stored parameters), reproduced the same result: dhruva-s tier-1
3/17, **tier-2 1/17** — the single tier-2 cell is `ace8383c2fa68d03` — "the
first tier-2 dhruva cell the benchmark has ever reported" (the earlier
cross-spec benchmark, stage 12, had read 0 on all four bands) (FINDINGS
§25.6). A small but telling honesty note: that benchmark invocation named
only two specs and so rewrote `data/benchmark.md`, silently dropping the
other five spec rows — caught and **reverted**, not left as a regression
(FINDINGS §25.6).

**Understanding.** Gate D3's whole arc is the clearest complete example in
the project of diagnosis deepening with each attempt, in public: "a missing
measurement" (stage 11) → "a search failure" (stage 13) → "a conversion
rate" (stage 17) → "a device-budget decision, twice" (stages 20, 22) → "met,
by a mechanism that corrects the previous stage's own prediction" (this
stage). The two-regime/knee finding and "grow the quietest parent, not the
best one" are now general, reusable facts about this design space, not just
about `dhruva-s` — and the honest note that 20 devices, not 21, would have
sufficed is the kind of correction that only a record built to survive
re-reading bothers to keep.

---

## Current frontier

As of this document's writing (`lna-data`, commit `5be4de3` and whatever
concurrent work is layered on top of it), the following are open, live, or
explicitly deferred to the user:

- **Gate D3 is MET on `dhruva-s`** (stage 22) but **NOT MET on the other
  three bands.** `dhruva-l5` is measured short by 0.81 dB and diagnosed as
  needing a **quieter input stage** — a topology question for the archetype
  set/generator, not a sizing one, since more gain and more devices both
  measure inert there (past the knee stage 22 found). `dhruva-l2`/`l1` were
  never run under the current budget; the working assumption that neither
  beats `dhruva-l5` is an inference, not a measurement, and should be
  checked before being relied on.
- **`wideband-sdr`, under the corrected spec (stage 19), has never once
  produced a design that holds S11 band-wide** — 0/134 stored rows, at any
  NF/gain trade-off, under the metric the spec always meant to enforce. The
  literature survey's six 0-inductor measured designs are evidence this is a
  topology-library gap (no multi-path feedback match archetype, e.g. a
  Sobhy-et-al.-style multiple-feedback network), not a physical ceiling —
  the natural next lever, not yet built.
- **Gate S2** (evolutionary search vs. rerank at 2× tier-2 designs) — still
  not met as of its last measurement (stage 13); the critic v2 retrain
  (stage 16) and the newly NF-gated-feasible dhruva rows (stage 22) are
  both inputs a re-run has not yet used.
- **`emit_winners` feedback of the two Gate-D3-feasible designs is
  outstanding.** `ace8383c2fa68d03` and `ced0d8bd36ed4890` are the first
  NF-gated feasible dhruva labels the program has ever produced; a P5
  fine-tune on them is the explicitly-named next step toward a **generated**
  (not search-plus-sizing) tier-2 feasible — the stronger claim stage 22's
  own attribution note says this result does not make.
- **The `dhruva-l5` input-stage problem is a generator/topology task**, not
  a sizer task — stage 22 measured that every l5 candidate on hand is
  already gain-rich and noise-limited, so the fix is a new low-noise
  input-stage archetype, not another `device_budget` widening.
- **Renewable real-data ingestion is an open, explicitly-costed lever, not
  an assumption.** Stage 21 measured +27 nb / +20 wb NDL from 9 circuits
  (5.8% of training rows) with real costs (11.4 points of yield, a wb
  inductor-ratio regression); whether a second batch scales linearly is
  named as "the cheapest remaining experiment in this program." The IHP
  SG13G2 tapeout program (stage 15's source) is explicitly renewable — a new
  tapeout lands every 1–2 months and LNA submissions appear in most of them.
- **The wb inductor-ratio regression from P5-v7 (0.077→0.132) is
  unresolved** — anyone sampling `<LNA_WB>` for an inductor-capped spec like
  `wideband-sdr` should know the adopted generator now emits more inductors
  on that channel, not fewer, before running a campaign off it.
- **WP-BIAS v3's own deferred question is still open**: should the
  R-SOURCE/R-DRAIN rules be default-on for sizing? They are proven to never
  degrade conduction, but changing the sizing domain by default was
  deliberately left as a separate decision, with the settling experiment
  (re-size the 13 corpus + 3 external circuits that adopt a v3 stage, with
  and without it, on feasibility rather than conduction) named but not run.
- **Stability is measured but advisory only, and frequency-only** (no
  process corners, no layout parasitics). A polish or curated-sizing step
  can still walk a design into K<1 because nothing in the objective penalizes
  it; putting stability in the objective (or at minimum refusing a polish
  step that drops K_min below 1) is recorded as a known gap, not yet closed.
- **The NDL metric still runs against `ref-v3`**, and any future generator
  training run on data the reference doesn't cover (e.g., a further corpus
  expansion) should re-check whether the reference needs another versioned
  rebaseline — the ref-v2 episode (stage 12) is the template for how to do
  that without quietly breaking history; the ref-v3 episode (stage 15) is
  the template for confirming, provably, when a rebaseline changes nothing.
- **`iip3_dbm` remains `unsupported` on every spec** (tier-3, needs a
  two-tone/harmonic-balance harness — the VACASK bookmark in the project
  memory index is where that would start).

**Standing honesty mechanisms**, established over the course of this history
and expected to hold going forward:

- **The frozen NDL@256 protocol**, now on its third versioned reference
  (`ref-v1`→`ref-v2`→`ref-v3`), with every historical number reproducible
  under the reference it was originally measured against.
- **Adopt-only-if-better**, for every generator and critic version, gated on
  the frozen protocol and the pinned holdout metrics — ties go to the
  incumbent, and both real costs and real gains are stated even when the
  verdict is ADOPT (stage 21's wb inductor-ratio regression is the clearest
  recent example).
- **Replay fences** (`size.replay_ok`) and **independent re-audits**
  (`_nf_gate_d3.py`, and cross-checking a claim through `benchmark.py`'s
  separate code path, stage 22): before any polish, reuse, or headline gate
  claim, re-evaluating a stored point must reproduce its stored metrics from
  scratch, or the claim is not trusted yet.
- **`device_budget` widenings are calibrated to the nearest real silicon
  device count, never to "what closes the gate,"** and the record says so
  explicitly even when a grant turns out larger than what was actually used
  (stage 22: 21 devices approved, 20 needed) — the excess is reported, not
  smoothed over.
- **The blind protocol** for the Dhruva goal, with its explicit rule that
  unblinding is the user's call, not the executor's, honored even when
  hard-excluding a source that turns out not to be relevant anyway
  (stage 19's wideband-sdr recalibration).
- **The regression quartet** (now effectively a quintet with `check_ref`,
  `check_nf`, `check_stab`, `check_bjt` alongside the vocab/screen/pipeline
  checks), required green before and after every work package.
- **Explicit user sign-off for any change to a frozen protocol or a spec's
  own constraints** — the ref-v2 rebaseline and the Gate C1 restatement
  (stage 12), and the `wideband-sdr` recalibration and the two
  `device_budget` widenings (stages 19, 20, 22), are the model: measure the
  defect or the need, propose the fix, get the decision, execute it the same
  session, and record the correction's exact size — including when the
  correction reveals a wall (stage 19's 0/134) or an over-grant (stage 22's
  21-vs-20) — rather than a clean restatement that hides what changed.

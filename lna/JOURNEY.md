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

## 23. ★★★ The multi-finger cutover — Gate D3 on all four bands, and an artefact that was hiding two things

**The decision.** Stage 22 closed Gate D3 on `dhruva-s` and left `dhruva-l5`
0.81 dB short, with the diagnosis pointing at the input stage. A per-element
noise decomposition (the new `extract.measure_noise_budget`, validated on a
golden deck to 3.0103 dB *exactly* and with sum-closure 1.0000 on every real
design) said the diagnosis was wrong: **26–40% of the excess noise factor on
every dhruva design was BSIM4 gate-electrode resistance**, because the harness
had always emitted MOSFETs as a **single finger**. The dominant per-device
mechanism was `rg`, not the channel thermal noise everyone had been optimising.
A 100–200 µm RF device at one finger carries hundreds of ohms in series with its
gate — a device nobody would tape out.

**Who decided what.** The executor measured the artefact and its size, then
**refused to adopt the fix**: finger count is a harness-fidelity parameter of the
same class as `inductor_q` and `device_budget`, changing it moves every NF label
in the store, and changing it in order to close a gate is precisely what stages
19/20/22 each declined to do. The proposal handed up was a rule calibrated to
layout practice — fix a finger *width* (~1–5 µm real practice) and let the count
follow from W — not a number chosen to clear a target. **The user approved
`w_finger = 2 µm`.**

**The result.** Under the honest harness a single 20-device design,
`ace8383c2fa68d03`, is tier-2 feasible on **all four dhruva bands** —
NF **1.288 / 1.220 / 1.506 / 1.253** dB against targets 3.5 / 2.7 / 2.5 / 2.5,
each with S11_max ≤ −10 over 1.1–2.5 GHz, S21 ≥ 35.7 dB, Idd ≤ 13 mA, replay
3/3 identical, 30/30 parameters in-box, and unconditional stability both in band
and over 0.1–20 GHz. The four-band tier-2 result the ladder was built for.

**What the record has to say honestly.** The gate was never "0.20 dB away on
dhruva-s and 0.81 dB on l5". Those distances were measurements of a device that
would never be built. The store-wide relabel — 1240 rows, append-only, fenced by
an old-geometry replay — puts a number on it: **the old harness overstated noise
figure by a median of 2.08 dB**, and every NF this program published before the
cutover is pessimistic by roughly that much.

**And the artefact was hiding a second thing, in the other direction.** The
single-finger gate resistance was a large *real, lossy* series element that
guaranteed port passivity. Removing it exposed the **Gate-D1/D2 four-band
archetype** as only *conditionally* stable on `dhruva-l2` (K_min +10.15 → −17.2).
A five-point control showed |S12·S21| flat throughout, so the sign flip is in K's
numerator: a port reflection coefficient exceeding unity — negative resistance
the design always had. The executor's first hypothesis (a feedback path being
un-damped) was contradicted by its own control and is recorded as wrong. The new
harness did not destabilise that design; it stopped flattering it — and it means
every stability count taken through the old harness is a **lower bound**.

**Two capability findings fell out, and they changed shape rather than sign.**
Stage 22's negative result — that neither search nor the generator could find a
quieter input stage — had been flagged as *confounded*, because a quarter to two
fifths of the noise they were being asked to remove was not removable by
topology at all. Re-run unconfounded: **search now reaches the gate easily**
(8 of the first 14 mutants tier-2 feasible on l5, best NF 1.19), while **the
generator still fails — but not for the reason assumed.** Its best l5 candidates
reach NF **0.96–1.02 dB** with adequate gain and stop at S11 −1.0/−4.5. The
generator's designs were never noise-limited; they are *match*-limited, which is
the same structural-match wall three earlier stages hit. A negative result that
survives its confound and then points somewhere new is worth more than the
positive one it replaced.

**Also corrected on the way in:** a concurrent report claimed the second D3
winner `ced0d8bd36ed4890` was absent from the label store. It has ten rows there,
with tokens and parameters, and had resolved by hash in three campaigns the same
session — checked rather than acted on, and recorded so the claim is not
re-raised.

**What this stage adds to the method.** A harness cutover now has a shape, and it
is the WP-D1 shape re-used a third time: *validate the instrument on a golden
case → prove the intended term is what moves → land the self-describing stamp
first (concurrent agents are writing) → re-baseline the regression suite
deliberately → relabel append-only behind a replay fence → re-verify the
flagships → report the delta distribution, not just the headline.* The one
refinement this stage adds: when the cutover changes the **circuit** rather than
a measurement, the relabel must re-measure the **whole metric vector**, because
the match moves too — a row has to carry the metrics that go with its geometry.

---

## 24. ★★★ The match wall — the generator's designs put the signal on the wrong pin, and Gate D3 falls on `dhruva-l5` to a generator topology

**The question.** Stage 23 ended with the generator cleanly isolated: on the
honest multi-finger harness its `dhruva-l5` candidates read NF **0.96–1.02 dB**
at 22 dB of gain and stopped dead at S11 **−4.46 / −0.99**. Not noise-limited,
never had been — *match*-limited. The user's brief for this stage was narrow and
strict: find out **why**, and find a fix **inside the rules** — no formula may be
written into code or used to support topology or sizing (measurement math only),
and no new hand-authored archetype family. A capability negative was named in
advance as an acceptable answer.

**What the executor decided to do first.** Not to theorise. The wall had been
sighted three times (§17.8 on `dhruva-s`, §22.5 on `wideband-sdr`, §27.6 on
`dhruva-l5`) and every sighting was a *sizing* result. The first move was to
build an **instrument** rather than a hypothesis: `_match_struct.py`, which does
nothing but count what sits at a circuit's input port — passives on the VIN node,
whether their far end is a rail, how many hops to the first transistor terminal
and which terminal it is. Pure graph arithmetic; no impedance appears anywhere,
which is what keeps it on the right side of the no-formula rule.

**The first measurement killed the obvious answer.** The generator *does* emit an
input network: 91–95% of its narrowband samples have one, against 92.7% for the
real corpus and — the number that settles it — **91.5% for stored designs that
never match**. "It doesn't emit matching structure" was simply false.

**The measurement that worked was a contingency table, not a theory.** Every
stored design was reduced to the best S11 its graph ever achieved, labelled
matched at ≤ −10 dB, and every structural feature scored against that label.
One feature carried the split: **whether the input reaches a transistor SOURCE
rather than a GATE.** It survived splitting by provenance — 5.2× inside the
generator's own designs, 8.4× inside search, 25× inside the archetypes — at
matched device counts and matched sizing budgets.

**Then the mechanism, which is the part that actually explains §27.6.** Among
multi-finger dhruva rows that already hold the band match: gate-driven inputs
have a median NF of **7.52 dB** and **0 of 31** reach NF ≤ 2.5 with 22.3 dB of
gain; source-driven ones sit at **2.97 dB** and **54 of 139** clear both. And
among rows that do *not* match, gate-driven designs reach a minimum NF of
**0.24 dB**. **A gate-driven input in this program is quiet exactly when it does
not match.** `seq0086` and `seq0085` read NF ≈ 1 dB *because* nothing at their
port dissipates, and that same absence is why no parameter setting reaches 50 Ω.

**Who decided what, and the one place the executor refused a shortcut.** The
diagnosis points straight at the hand archetype library — 88 `cs` + 16 `cscs` +
12 `rfbcs` + 8 `rfb` + 5 `rfbcs3` + 4 `creuse`, every one of them gate-driven,
against 10 `gmbcg` + 3 `nccgcs` + 2 `cg` — and that library is **31% of the
training rows** while carrying the motif in **1.35%** of them. Writing more
source-driven archetypes would obviously help and is exactly what the brief
forbade, so it was **not done**; the measurement was put on the record and the
decision handed up. The two levers that *were* allowed — re-weighting existing
rows, and prefix-conditioned sampling from existing designs — were run instead.

**Both allowed levers moved the rate and neither moved the yield.** Prefix
conditioning is almost a control knob for the motif: 0.032 (seeding from
gate-driven circuits) → 0.192 (unconditioned) → 0.758 → 0.926 (24-token
source-driven seeds). But the count of *novel, screen-passing, motif-bearing*
`dhruva-l5` candidates went 10 → 10 → 8. Every extra motif-bearing sample was an
exact corpus copy; corpus copying rose 32% → 72%. **This is stage 21/23's law
turning up in a channel that has nothing to do with training** — steering a model
toward structure it has already memorised returns that structure as copies. The
control arm that seeded from gate-driven circuits, and drove the motif *below*
the unconditioned baseline, is what makes the reading unambiguous.

**The positive results came from asking the pool a different question.** §27.6's
capability test drew the **12 most structurally distinct** candidates from the
generator pool and concluded a capability limit. Re-drawing them by the *measured*
predictor instead — every screen-passing, source-driven sample from the P5-v7 and
P5-v8 narrowband pools, 29 distinct graphs, 26 of them novel — **24 of 29 close
the band match**, and one closes the whole gate. **`80aaf9f4a0cd7863`
(`ft_p5v8_nb_s1337/seq0173`, 16 devices) is tier-2 feasible on `dhruva-l5`:
S11_max −10.017 over 1.1–2.5 GHz, S21 29.794, Idd 12.993, NF 1.788 against a 2.5
target**, replay 3/3 with spread 0.0000, 24/24 in-box, unconditionally stable in
band and over 0.1–20 GHz, WL hash absent from ref-v3. **Its topology is the
generator's, with no `moves` edit at all** — the first Gate-D3 feasible design in
this program whose graph came out of the learned model rather than an archetype or
a search edit. What this session added was candidate *selection* and the existing
sizing path, and the record says exactly that.

**And the controlled version, on the very design that defined the wall.**
`moves.m_input_class_swap` — an existing black-box move that relocates the signal
from a gate to a source — had been in the tree since the rung-2 work and had never
been aimed at these parents. Applied to the two §27.6 named, **both converted**.
`fb48c7f2` (`seq0085`), the worse of them at S11 −0.99 and NF 0.96, became
`2669669e45c5c5a7` at **S11_max −10.01 / S21 24.20 / NF 2.87** — and one further
edit (`cascode_add`) reached **`78f5cc9cc2cd0133`: S11_max −10.014 / S21 24.560 /
Idd 12.997 / NF 1.963**, audited MET, unconditionally stable both in band and wide,
novel. **The prediction the contingency table implies — that a source-driven input
buys the match and costs roughly 2 dB of noise — was made before the edit and is
what the simulator returned.** That is the causal claim the observational tables
could not make on their own: same graph, one edit, match closes, noise pays.

**Three sibling mutants were not claimed, and the reason is on the record.**
`device_remove` (NF 2.24) and `passive_type_swap` (NF 2.19) both read
`spec.feasible()` True and both have **K_min < 1** — conditionally stable, so they
fail the gate's stability clause. Stage 23 had just finished warning that the
honest emission exposes marginal stability; this lineage is exactly that, and the
per-mutant K number is what separates a claim from a near-miss.

**A claim the executor had made three hours earlier, broken by its own
experiment.** The store said every design that had ever closed both the band match
and 22.3 dB of gain carried **≥12 devices** — 78 of them, no exceptions. The swap
mutant does it at **10**. Recorded with both halves: the ≥12 rule was a true
statement about which structures had been *tried*, not a property of the problem.

**What is not claimed.** `wideband-sdr` stays at 0/N, and the honest reason is
recorded: the motif that carries all four dhruva bands carries **nothing** there —
0 of 119 graphs have ever held that band match, source-driven ones peaking at
−6.61 dB — so stage 19's topology-library reading stands untouched. And the
generator's *unaided* frontier is still narrow: per 256 samples it produces 1 (v7)
to 5 (v8) distinct graphs that are simultaneously source-driven, large enough for
a cascade, novel and screen-passing.

**The pattern this stage adds to the program's method.** *When a capability
question has been answered three times by a sizing run, stop sizing and build an
instrument for the thing you are actually asking about.* The wall had been
measured repeatedly and never diagnosed, because every previous attempt asked
"can this design be sized to match?" instead of "what do designs that match have
that this one doesn't?" The second question needed twenty lines of graph
arithmetic and no simulator at all — and once it was answered, the two things that
closed the gate were a **selection criterion** and a **move that had been sitting
in `moves.py`, unused on these parents, the entire time**. The corollary is a rule
for this program's record-keeping: **a capability negative is only as strong as the
selector that produced its candidates, and from now on it has to name it.**

---

## 25. The instrument that was never built — the pipeline was still discarding the inside of every simulation

**Context.** Block 6 of the architecture exists because of one lesson, stated in
stage 5: the pipeline was throwing away its most expensive byproduct. Twenty-six
megabytes of `sim_points` rows are what stopping that looked like. But every one
of those 66,664 evaluations had also solved a **full DC operating point** —
every device's current, transconductance, terminal voltages, threshold — and
`extract.run_and_extract` ran `op`, parsed one scalar out of it (`idd`), and
discarded the rest. The same mistake, one level down, still in progress after
seven sessions of building on top of it.

**Decision, and who made it.** The user named it as a work package. The executor
pre-registered `plans2/09-WP-OBSERVE.md` — design, the three ngspice rules the
capture had to obey, the volume policy, and **five numbered predictions** — and
committed it (`b08dda8`) before writing a line of feature code, per this
program's standing norm. The design decision inside that plan was to make the
capture **print-only**: no `save` (gotcha N1 — a `save` before `sp` restricts
ngspice's saved set and silently deletes the S-parameters), no extra analysis,
no extra ngspice invocation, so that the deck's numerical result cannot move and
the claim "passive" is testable rather than rhetorical.

**Result — the instrument.** `extract.py` reads back
`id/gm/gds/gmbs/vgs/vds/vbs/vth/vdsat` per MOSFET (BSIM4 exposes no `region`, so
that is derived using `bias.py`'s own `ID_MIN`/`VDS_MARGIN` thresholds so an op
row and an L1 row cannot disagree), `ic/ib/vbe/vbc/gm/cpi/cmu` per bipolar, node
voltages and source branch currents. `datastore.py` gained the append-only,
gitignored `op_points` table; `size.OpSink` holds the whole volume policy in one
place. `ref/check_op.py` is the golden and joins the regression set: captured
Id/gm against an **independent** bare-`op` probe agree to **0.0e+00 relative
error**, and the metric vector is **identical in all 18 metrics at `repr`
precision** with the probe present and absent. Overhead is below this machine's
noise floor — end-to-end sizing runs measured **−0.8% and −0.7%** (FINDINGS
§30.2), against a 5% budget.

**A prediction registered because it was likely to fail, and it held.**
`build_noise_deck` has asserted since the WP-D1 NF rewrite that its DC solution
is identical to the sizing deck's — that is the entire justification for
measuring NF on a *different* deck than the S-parameters — and **nobody had ever
tested it.** It was written into the plan as P5, "the prediction most likely to
be wrong." Worst relative difference across every device and parameter:
**0.0e+00**. A four-session-old documentation claim is now a measurement, and it
is what lets `log_l2_result` harvest an operating point from the NF deck it was
already running — which is how the op table covers `search.py`, `evolve.py`,
`d3_campaign.py`, `nf_campaign.py`, `nf_moves.py`, `g4_search.py` and
`relabel_mf.py` without touching any of them.

**A defect found by the benchmark, not by the feature.** `datastore.git_sha()`
shelled out to `git rev-parse` **per row**. Invisible at one L2 row per
five-minute sizing run; at op-row rates it measured a **+99% overhead** — the row
assembly was twice the simulation. Memoized per process now, which every future
logging feature inherits.

**★ And the first thing the instrument said, on its first read.** One read-only
capture per design at each row's own stored `best_params`, across six headline
designs: **11 of 25 MOSFETs (44%) carry milliamps at a *negative* gate
overdrive**, and **not one device anywhere is in triode or off**. `gm/Id`
separates cleanly — **17–20 V⁻¹** for the weak-inversion group, **10–12 V⁻¹** for
the saturated one — i.e. the sizer independently converged on moderate inversion
for the gain/input devices and strong inversion for the current-hungry output
stage. Textbook RF biasing that nothing in this pipeline was told to do, and that
nobody here had ever observed it doing, because there was no quantity in the
stored row that could have shown it.

**The half of that result that is a correction, not a discovery.**
`bias.saturated` calls a device saturated when `|Vds| ≥ 1.5|Vdsat|`. In weak
inversion BSIM4's `Vdsat` collapses to ~55 mV, so every one of those
negative-overdrive devices clears that test by 5–8×: **the predicate reports all
25 of these transistors as saturated.** It is not a bug — it answers the question
it was built for — but every statement in this history of the form "N of 41
corpus circuits are saturated" means *conducting with adequate Vds headroom*, not
*in strong inversion*, and has to be read that way from here on (stage 18's
table, and finding #9's original off-MOS split, are the ones this touches).

**Understanding.** The pattern this stage adds is narrow and, in retrospect,
embarrassingly simple: **when a program has already decided that discarding a
paid-for byproduct is the cardinal sin, it should check whether it is still
committing it one level down.** Block 6 was written about exactly this and the
op point sat inside every one of its rows, unread, for seven sessions. The
corollary for the record-keeping: a logging feature ships with its golden or it
does not ship — a wrong `gm` in a million rows is worse than no `gm` at all,
because it will be believed. That is why `check_op.py` exists before any campaign
has filled the table, and why the honest headline of this stage is *156 rows and
a validated instrument*, not a result.

---

## 26. The 66,000 free labels — and the discovery that four of every five ngspice calls in a sizing run are waste

**Context.** Every ZOAF sizing run had been quietly writing its own interior to
`data/sim_points.jsonl`: one row per ngspice evaluation, `(wl_hash, spec, x,
metrics)`, appended by `size._log_l2` since the store went live and gitignored as
a "free byproduct". By this session it held **66,664 rows** — twenty-four times
the L2 table the critic trains on — and had never been used for anything. The
program's learned components all sat at the *outer* level: predict what a
topology will score after sizing. Nobody had asked the inner question — can you
predict what **one simulation** will say — even though the data to answer it had
been accumulating for a week (stage 25 was the sibling realisation about the
inside of each simulation; this is the same blind spot one level up).

**Decision.** Pre-register first (`lna/plans2/12-WP-SURROGATE.md`, committed
before any model existed), then build a point-level surrogate
f(graph, x) -> metrics on `critic_gnn`'s trunk, and — the part that decides
whether any of it is worth it — replay every stored sizing run with the
surrogate as a **pre-gate**, offline, with zero new SPICE.

Two things were treated as non-negotiable. First, **the join had to be proved,
not trusted**: point rows carry no tokens and no parameter names, so runs were
recovered from append order, topologies matched on `(wl_hash, spec, n_evals)`,
and the parameter map rebuilt with `size.py`'s own machinery — then every block
was required to decode its L2 row's `best_x` into its stored `best_params`
*string for string*, and eight interior points were replayed through ngspice.
Second, **the era had to be labelled**: the file's last append predates the
multi-finger cutover (stage 23) and the series-Rs NF, so it was pinned by line
count + sha256 and cross-checked per block against recipe and date.

**Result.** The join fence came back **bit-exact — 0.000000 on every metric,
all eight rows** (the same points through today's multi-finger deck move up to
10.2 dB, which measures the stage-23 gap on the sizer's own points rather than
assuming it). 98.85% coverage; 333 of 336 blocks proved. The surrogate reaches
**rho(S21) 0.990 / MAE 1.54 dB** interpolating inside a box it has explored and
**0.845 / 8.79 dB** on a topology family it has never seen — the latter far
better than the critic's off-distribution decay predicted, because ~190 points
per graph teach a response *shape* that transfers even when the graph does not.
The A/B settled the representation question: injecting each parameter at its own
device node beats padding-and-concatenating by 0.175 rho, while adding FiLM on
top changes nothing (0.003).

But the number that reframes the program is the **control**, not the model. Run
the identical gate with the *true* metrics as predictions — a perfect surrogate —
and it skips **82.6%** of a cold-start run's ngspice calls, and **90.1%** of a
warm-start run's, with every run's argmin exactly preserved. At the program's own
~5 minutes and ~193 evaluations per sizing run, roughly **four of the five
minutes are spent on points that never beat the incumbent and never would have.**
v0 captures 42.9% of that at zero argmin change in the warm-start stratum and
only ~1% cold-start; at the pre-registered margin it skips 62.8% cold-start but
moves 39% of runs off their argmin. Three of my eight registered predictions
were falsified: the cold-start correlation was much better than predicted, the
within-family error did not reach the sigma floor, and the per-run residual
calibration — predicted to matter more than the encoder — made things *worse*.

**Understanding.** Three things changed shape.

*The waste is in the search, not in the simulator.* "82.6% skippable" is a
property of ZOAF's trajectory that no model was needed to measure, and reporting
it first is what keeps "62.8% skipped" from reading as a model result. The gate
is **margin-limited by the surrogate's own point error** — cold start needs
`Delta` = 5 to be safe, warm start only `Delta` = 2 — so the savings curve moves
with data, not with architecture.

*The sigma floor was being asked to do a job it cannot do.* sigma(S21) =
0.726/1.478 dB is the spread of a *sizing-run outcome across seeds*. The replay
fence measured the point-level label noise directly: **zero**. "At or under label
noise" therefore isn't an available bar for a point surrogate, and the honest
restatement is that a point error below the sizer's own seed spread cannot change
a decision by more than the sizer already does.

*The DC quantity is the one that does not transfer.* Idd is near-perfect
within-family (rho 0.980) and second-worst cross-family (0.562), while S21 stays
at 0.845 — because total current is a sum over branches and so depends on what
branches the topology *has*, whereas gain is a shared response shape. The
intuition that "DC is easy, RF is hard" is exactly backwards for generalisation.

The immediate lever is not a better encoder: it is to gate `size_best_of_k`'s
seeds 2 and 3 — a warm-start case the pipeline manufactures every night, where
v0 already preserves 11/11 argmins while skipping 42.9% — and to retrain on the
post-cutover points stage 25's logging is now accumulating, since nothing here
can enter today's sizing loop until they exist.

## 27. The null hypothesis nobody had run — a generator with no learning in it beats the adopted one on both headline metrics, and then produces nothing

**Context.** Seven sessions of this program are built on two numbers:
`spec-L0` pass rate and `NDL@256`. Every generator adoption decision — P5-v6
rejected, P5-v7 adopted, the curriculum arms rejected, P5-v8 rejected, P5-v9m
rejected — was gated on them. Stage 24 had just established the rule that *a
capability negative is only as strong as the selector that produced its
candidates*. The symmetric rule for a capability **positive** is that it is only
as strong as the baseline it is compared against, and the record contained **no
no-learning baseline at all**: the weakest thing ever measured was the upstream
pretrained checkpoint, which is still a transformer trained on 3,351 circuits.

**Decision, and who made it.** The user named the work package: build the
missing rungs of the ladder — a grammar-only generator, a grammar-plus-retrieval
generator, the pretrained checkpoint, and the adopted P5-v7 — and push all four
through one identical funnel with the rung-0 selector *held fixed*, because
stage 24's lesson is that the selector is where a comparison silently breaks.
The executor pre-registered `plans2/10-WP-ATTRIB.md` — the four arms, the
justification of every well-formedness rule as *required for validity* rather
than *good for LNAs*, seven numbered predictions and an explicit decision rule —
and committed it (`ab5e633`) before a line of `grammar_gen.py` existed.

**Result — the inversion.** The grammar arm draws a random device multiset
inside the spec's device budget, wires every pin uniformly at random including
MOS bulk, and serializes through the same upstream Eulerian pipeline the corpus
and archetypes use. It clears `wifi24`'s L0 screen at **65.6%** against P5-v7's
65.2%, and scores **NDL@256 = 168** against P5-v7's 63 — because a random graph
is never a copy of anything. On `dhruva-l5` the gap is wider still (77.3% / 198
vs 67.2% / 64). **A generator with no learning in it wins both of the metrics
this program has used to decide what to adopt.**

**And then the simulator speaks.** After rule-based bias, **3.0%** of the
grammar arm's screen-passing samples have all their MOS conducting, against
**67.7%** for P5-v7 — the *median* random circuit has zero conducting
transistors, on 168 samples against 167. At equal sizing budget through the same
fixed selector, the no-learning arms return **0 near-feasible and 0 feasible**
designs and not one of 22 sized candidates reaches useful gain (best S21
**+2.48 dB**). P5-v7 returns 2 near-feasible, and one of them is a fully audited
`wifi24` **tier-2 feasible** design — `0da2f0c7b263eee5`, 10 devices, S11 −30.68
/ S21 13.37 / Idd 2.24 / **NF 1.697**, replay 3/3, 10/10 in box, unconditionally
stable in band and over 0.1–20 GHz, novel against ref-v3 with its nearest
neighbour at cosine 0.527. The program's tier-2 record goes from two designs to
three.

**Understanding.** What the 11.8M-parameter fine-tune buys is not novelty — a
random graph is more novel — and not structural plausibility — a random graph
passes the same screen. It is **DC viability and gain capability**: an
arrangement in which transistors actually conduct and a signal actually gets
amplified. Neither of the program's headline generation metrics can see that
property, and one of them is actively anti-correlated with it. The cheapest
repair is already measured and costs about seventy seconds per pool: report the
all-MOS-conducting rate beside NDL. Whether it joins the adoption rule is a
frozen-protocol change and therefore the user's call, exactly like the ref-v2
rebaseline and the Gate-C1 restatement before it.

Two further things fell out. The source-driven input motif that stage 24 showed
carries the whole match/no-match split is emitted by **random wiring at 48.4%**
and by the adopted generator at **14.4%** — confirming from the opposite
direction that the motif is abundant in graph space and scarce only in the
training mix, which is why every steering lever tried so far bought rate and
lost novelty. And the uncertainty gate retired in stage 16 as permanently inert
fires on **73–76%** of the no-learning candidates against 0–11% of the learned
ones: it was never broken, it had simply never been shown anything genuinely
off-distribution. `grammar_gen.py` is now this program's null hypothesis, and it
costs fifty seconds of CPU to run.

**Honesty note carried forward.** The sizing half of this comparison is 31 runs;
Fisher one-sided on near-feasible gives p = 0.077 pooling all no-learning arms
against P5-v7, which does not clear 0.05. The decisive statistics are upstream
(113/167 vs 5/168 conducting) and qualitative (0 of 22 no-learning candidates
above +2.5 dB of gain). The claim supported is "the learned generator supplies
DC-viable, gain-capable structure that syntax plus retrieval does not"; the
claim *not* supported is a precise multiplier on feasible-novel yield.

## 28. Telling the generator what its circuits measured — and the shuffled control taking the credit

**Context.** Three sessions had established a law (`FINDINGS §29.12`): every
feedback channel tried — winners feedback, prefix conditioning, row re-weighting —
raised the statistic it targeted and lowered novelty, because all three pointed the
model at structure it had already memorised. But no channel had ever carried a
*measured outcome* into the weights in any form. The generator had never seen a
SPICE result. This stage tests the one channel that is different in kind:
decision-transformer-style outcome conditioning, 16 new tokens saying what each
labeled topology achieved, and a request for `all-bins-MET` at sampling time. Both
readings were pre-registered as live — "conditioning works because it adds
information," and "the novelty law claims a fourth channel" — in
`plans2/11-WP-OUTCOME.md`, committed before a single epoch.

**Decision.** The executor built the channel with a control that is the whole
experiment's backbone: a second fine-tune on *the same rows and the same token
streams* with the bin vectors permuted across rows, so per-slot marginals and the
joint bin distribution survive and only the label-to-topology correspondence dies.
Bins came only from the current measurement era (multi-finger geometry, series-Rs
NF), a strict Block-6 policy whose cost was measured rather than assumed: 4 keys of
1086. The MARGINAL/MET threshold was set at one label-noise unit, not a round
number. Both arms are P5-v7's stage B with one variable changed, and the label
store's own 4072 conditioned rows went to train only, so the validation set and the
early-stop criterion stayed the baseline's.

**Result.** The checkpoint is **REJECTED** under adopt-only-if-better — the
inductor-ratio clause fails in both channels — but the interesting numbers are
elsewhere. Conditioning **raised** nb NDL@256 from 79 to 99 (wb 41 to 89) and
collapsed corpus copying from 32% to 6%; the shuffled control scored **115** and
5.5%. The novelty is real and it is not the labels: it is the 4072 new rows plus
the mere presence of a prefix. On the sized funnel the conditioned arms produced
candidates that actually amplify — S21 > 0 on 10/10 against the adopted baseline's
2/9 (p = 0.0007), 8 near-feasible of 10 against 2 of 9 (p = 0.019), and **a new
`wifi24` tier-2 feasible design**, `ce39a77c91974013` (S11 −10.85 / S21 13.00 /
Idd 4.74 / NF 2.33), replay-verified, in-box, unconditionally stable, novel against
ref-v3 — **which both arms found independently.** The real-label arm beat its
shuffled twin on all seven measured axes (source-driven input rate, device count,
conduction, qualifying rate, near-feasible count, median violation, gain) and on
none of them significantly: a consistent small effect the sample size cannot
certify. Sampling the same checkpoint *unconditioned* was the expensive lesson —
NDL halved to 42 and archetype copying more than doubled, so the prompt channel
damaged the base distribution it was supposed to leave alone.

**Understanding.** The registered prediction that both hypotheses agreed on — that
novelty would fall — is the one that was wrong, and that is the stage's real
content. The law did not acquire a fourth channel; its scope got sharper. What
moves this generator has never been the *direction* of a steering signal; it is
whether the channel carries structure the model has not memorised. Outcome labels
are not structure. The rows that carried them were — the store's own search- and
mutation-derived topologies, a data source this program had been sitting on since
the first campaign and had only ever fed back through the winners filter, which by
construction selects the archetype-like ones. The follow-up the measurement points
at is therefore not a better prompt: it is the same 864 topologies as an ordinary
unconditioned fine-tune. And the funnel added a second independent instance of this
session's other lesson — the frozen novelty protocol could not see the difference
between a pool of passive networks and a pool of amplifiers.

## 29. The critic learns to point — and the pointing costs it its ranking

**Context.** The critic had one job and one shape: predict a whole topology's
margin vector, which it does by pooling its per-device embeddings away. It could
say *"this candidate will miss"* and never *"and here is the device that is
missing it"* — which is why `evolve.py` still mutates uniformly at random over 17
move classes, with no opinion about **where** on the graph to cut. Two per-device
supervision signals had been sitting in the store the whole time without ever
being read as labels: §26's per-element noise budgets (on 1,355 rows) and §30's
per-device operating points. This stage asked whether the same backbone can
localise a defect, and — the part that makes it a capability rather than a metric
— whether localising it makes search better. `plans2/13-WP-DIAGHEADS.md` was
committed with both eval bars, the five pilot parents named by hash, the move
policy and the 20-sizing budget, before any head was trained.

**Decision.** The first real decision was made *before* the modelling: an audit
of the label supply found the brief's expectation inverted. The noise budgets
were rich; `op_points.jsonl` was 391 device rows of which 374 were `off`, 164 of
its 194 rows the un-converged inner trajectory of a single 2-device demo circuit.
Worse, an inner-ZOAF row is the wrong *kind* of label: the critic's input is
(topology, spec) and contains no `x`, so conduction at an arbitrary trajectory
point is not a function of the model's input. Rather than train a head on it, the
executor pre-registered a read-only harvest — §30.5's own method at scale, one
bare `op` at each stored design's own `best_params` — and took the first snapshot
`op_points` had ever had. The second decision was to honour the pre-registered
consequence when the non-regression bar failed, instead of tuning the two λ that
had been fixed a priori precisely so that this could not be quietly rescued.

**Result.** On a family holdout the heads clear both Bar-1 gates: dominant-noise
device **top-1 0.596** against a 0.191 uniform base rate, a 0.307 best-constant,
and a **0.131** "it's the input device" heuristic that is *worse than guessing*;
conduction **AUC 0.949**, weak-vs-strong inversion **AUC 0.858** on an axis where
`bias.saturated` scores **0.552 with a full DC solve in hand**. The harvest also
generalised §30.5's 25-transistor observation to 4,096: the L1 predicate calls
**99.0%** of weak-inversion devices saturated. **Bar 2 failed** — the multi-task
model's ρ(S21) drops 0.862 → 0.771 and its uncertainty calibration halves
(0.549 → 0.247) — so the diagnosis heads ship as a **separate model** and critic
v1 is byte-for-byte untouched. In the pilot, targeted moves beat random ones on
the pre-registered metric (mean Δ feasibility score −1.049 vs −1.432) but by
**removing disasters, not by finding wins**: the targeted median is *worse*, and
the only feasible child in 18 sizings came from a random `rewire`.

**Understanding.** Three things this stage changed about how the program should
be read. First, **a per-device signal was available for free the whole time** —
the budgets were being written as input features and never as labels — and the
thing that unlocked it was not a model but noticing that a label has to be a
function of the model's input. Second, **localisation and ranking compete for the
same capacity**: the same backbone can do either well and does both worse, and
the cost lands hardest on the ensemble σ that search actually consumes, which is
the most expensive thing in the model to damage. Third, and most usefully, **the
pilot moved the bottleneck**: on two of five parents the head pointed at a
passive whose prescribed edits were all illegal on that circuit, so the diagnosis
was right and `moves.py` had no answer. The next constraint on pointed search is
the move repertoire, not the pointing — and the honest summary of the whole
experiment is that a diagnosis head buys a *narrower loss distribution*, which is
worth having and is not the same thing as buying better designs.

## 30. ★★★ The benchmark restated to simultaneous — and the answer was already yes

**Decision (the user's, 2026-08-13).** Record the per-band Dhruva/GNSS
benchmark as MET — one topology, four per-band sizings, tier-1+tier-2 on every
band (stage 23) — and restate the standing benchmark: **one LNA, one fixed
sizing, all four bands' specifications at once.** The old bar allowed the
program to re-size per band; the new one does not. Gate name **D4-SIM**,
recorded in `lna/plans2/14-DHRUVA-SIMUL.md` (which also restates the target
ladder, since `08-DHRUVA-GOAL.md` lived in the since-removed `lna-plans`
worktree and is no longer on disk).

**Result (FINDINGS §35).** The new gate was measured the same day it was set,
and it was **already met — by all four shipped sizings**. The 4×4 matrix
(each `mf2-v1` parameter set of `ace8383c` evaluated against every band spec,
16 cells) is 16/16 PASS. The designated D4-SIM point is the `dhruva-l5`
sizing: **NF 0.867 / 0.995 / 1.196 / 1.253 dB at the S / L1 / L2 / L5 f0s
against limits 3.5 / 2.7 / 2.5 / 2.5** — worst margin +1.247 dB — with S21
33.7–36.0 dB (worst margin +3.7 dB), S11 −10.001 dB held over the whole
1.1–2.5 GHz range, one fixed 12.963 mA operating point, unconditionally
stable in-band and 0.1–20 GHz. Replay fence 3/3, spread 0.0000, every gated
metric, every band. Driver: `recreate.py --cross`, committed with the package.

**Understanding.** The result was latent in decisions made months of stages
ago, and nobody had asked the question. Every dhruva spec gates **S11
band-wide, not at f0** — so every sizing was already forced to hold the match
across the whole reconfiguration range; the winner's gain ripple over that
range (2.3–4.4 dB) is smaller than its worst-case gain slack; and the
multi-finger cutover's 1–2.2 dB of own-band NF margin absorbs the ≤0.8 dB
off-tune NF rise. The per-band re-sizing was buying margin, not feasibility.
Two honest edges: the benchmark that is now met is **tier-1+tier-2
simultaneous** — tier-3 (IIP3, differential balance, gain programmability)
remains unmeasured, and the paper specifies IIP3 at *min gain* while this
design sits at one fixed ~34–36 dB point, so the linearity question is
harder for this design, not easier; and **S11 margin is 0.001–0.002 dB on
every row** — the match is the binding constraint by construction, and no
corner or parasitic has been asked to move it yet.

## 33. The optimizer learns to keep its footing — stability enters the acceptance rule

**Decision (stage 30's upgrade ladder, item 3 — queued since Session 4).**
Put stability into the polish/curated objective, at minimum by refusing a
step that takes K_min below 1. The failure was measured long before it was
fixed: polish walked `seq0220` from K_min 4.08 to 0.832 with nothing in the
objective to stop it, and §15's control arms landed 21 of 60 sizings at
K < 1.

**Result (FINDINGS §38).** `polish` and `constrained_descent` now refuse an
otherwise-accepted step whose in-band K_min crosses ≥ 1 → < 1; an unstable
*start* is flagged, never silently kept, and a recovery is never blocked.
Zero extra SPICE (K rides the S-matrix run every evaluation already makes);
default ON with `LNA_STAB_GUARD=0` as the hatch; every new row stamps
`zoaf_cfg.stab_guard` so the domains stay separable. Acceptance: the two
known K<1 wifi24 cases re-run — **the tier-2 claim survives with K_min =
3.78** at the claim row, and the single-finger reproduction re-measures the
historical unstable polish point at **0.8317 vs the recorded 0.832**, where
the guard's start-flag fires live and the ascent recovers it to K 2.47.
Plain ZOAF is deliberately unguarded — its scalar is the frozen label
definition, and re-domaining every future label is a governance decision,
proposed rather than taken. Quartet and every golden green before and after,
no regression number moved.

**Understanding.** Two things worth keeping. First, the box clamp had already
closed the *specific* road to 0.832 — the historical walk went out-of-box, and
a clamped polish from the same start no longer attempts the crossing — so the
guard fired zero refusals on the very case that motivated it; its value is the
floor it puts under every *future* trajectory (seq0220's fresh polish still
spent stability margin 3.78 → 1.91 with nothing to stop it going further).
Second, the guard belongs at the acceptance rule, not in the objective: an
incumbent-transition test costs nothing, cannot distort the label definition,
and separates "don't create instability" (guarded) from "instability exists in
ZOAF's landings" (still advisory, still visible, still a different problem).

## 34. The sweep the headline was hiding from — S11 knife-edge as predicted, Idd co-fragile, noise robust

**Decision (stage 30's upgrade ladder, executed as pure measurement).** Before
hardening the D4-SIM point, measure its fragility: perturb temperature, supply,
every passive value, and inductor Q around the shipped `dhruva-l5` sizing of
`ace8383c`, re-measuring the four-band simultaneous gates at the fixed point —
nothing resized. Named a **sensitivity** sweep, deliberately: the 45 nm
behavioral models have no process-corner cards, so no fab-corner claim is
available at this fidelity, and pretending otherwise would be the exact kind
of quiet overreach this document exists to prevent.

**Result (FINDINGS §39).** Stage 30's prediction was half right. S11 flips
almost immediately (−1% supply, +1% passives, one Q step, +13 °C) — but **Idd
is just as fragile** (0.037 mA of margin; +1% VDD or −1% passives flips it),
and there is **no passing supply tolerance at all**: ±1% VDD fails one gate or
the other. Temperature is one-sided (cold improves everything; +40 °C fails).
The design **fails when its inductors get better** — Q = 16/20 flip S11 and
Idd, because the match is partly loss-damped and one Q-loss resistor carries
DC. Meanwhile **NF and S21 never flip anywhere on the sweep**, including the
85 °C + VDD×1.1 combo (NF worst margin +0.50 dB): the noise story is robust;
the bias point and match are knife-edge. Hardening targets, measured: S11 ≤
−10.44 at nominal, NF margin ≥ 0.75 dB kept, and — the striking one —
**4.5 mA of Idd headroom**, which is honestly read not as a margin target but
as the measured cost of *fixed-voltage bias*: real parts hold Idd over PVT
with a current-mirror/constant-gm bias, a DOF the vocabulary does not have.

**Understanding.** Both knife-edge constraints are knife-edge **by
construction**: `constrained_descent` pins S11 and Idd at their gates while
descending NF, so the shipped point provably sits on the boundary of exactly
the two constraints the sweep found fragile — the sweep priced the objective's
shape, not bad luck. The two load-bearing craft points: an invariance control
(`.temp 27` must reproduce the baseline exactly — it does, drift 0.0) is what
separates "the circuit moved" from "the instrument moved"; and the sweep
needed **no shared-file edit at all** — temperature is a card appended to the
deck body, supply and Q ride the same last-`.param`-wins override the shipped
flow itself depends on. The cheapest robustness lever found: the point
*improves* at low Q, so the Q=12 assumption is currently load-bearing in the
lucky direction.

## 31. WP-HARDEN — the margin-hardening resize closes the loop stage 30 opened, and finds the frontier is flatter than expected

**Decision (stage 30's upgrade ladder, item 1, calibrated by stage 34's
sweep).** Re-size the shipped `dhruva-l5` D4-SIM point to spend its NF/S21
slack on S11 and Idd robustness — the two axes stage 34 measured as
knife-edge — while holding the sweep-derived floors (S11 ≤ −10.44, NF margin
≥ 0.75 dB) as hard constraints. Implemented as a sidecar
(`lna/_harden_simul.py`) rather than a `size.py` edit, since `size.py` was a
concurrent agent's file this wave; same lexicographic kept-floor scoring
shape as `constrained_descent`, same read-only sizing APIs `recreate.py
--cross` already uses.

**Result (FINDINGS §36).** A two-stage descent: first, how far can S11 go
with only Idd capped? Answer — **−14.07 dB**, twelve dB past the −10.5
target, and Idd barely moved (12.96 → 12.41 mA). Second, starting from
there, minimize Idd with S11 held at the −11 dB stretch floor and NF/S21
kept at their sweep-derived floors: **Idd fell 37%, to 8.205 mA**, while S11
settled at exactly −11.012 dB — the descent spent precisely the slack it was
given, no more. A control run relaxing the S11 floor to −10.5 found almost
no further Idd gain (8.150 mA, 0.06 mA better) for half a dB of S11 given
back — **the frontier is flat**: past ≈−10.5 dB, Idd's ceiling is the NF/S21
floors, not S11 headroom. Evidence ladder: 5/5 replay, spread 0.0000; 20/20
in-box; all four bands re-measured feasible, fresh from the emitted params
file on disk; K_min 17.2 in-band / 8.5 wide; novelty unchanged (same
`tokens.json`, same `ace8383c` hash).

**The finding that changes the picture: both pVDD rows.** Stage 34 flagged
the pending 1.1-vs-1.2 V nominal decision as "adjacent, not acted on." This
WP measured it directly — and the shipped `dhruva-l5` point **fails D4-SIM
outright at 1.2 V** (Idd rises to 14.879 mA, over the 13 mA cap, on all four
bands), while the hardened point holds with 3.5 mA to spare and its other
margins *improve* at the higher rail. Whichever way the VDD-nominal decision
lands, the hardened point is the one still standing.

**Understanding.** Two things worth keeping. First, the "spend slack on the
weakest constraint" intuition that motivated this WP was only half right —
S11 turned out to have enormous slack (12 dB worth) that cost almost nothing
to take, while Idd's real ceiling was never S11 at all, it was the NF/S21
floors this WP itself imposed; finding that boundary needed a second,
differently-targeted descent, not a single multi-objective one. Second, a
robustness resize done for one reason (S11's 0.001 dB match cliff) paid off
on a completely different, undiscovered cliff (the 1.2 V Idd wall) — the
value of measuring margins broadly, not just on the axis you set out to fix.
Not adopted as the designated point — `plans2/14-DHRUVA-SIMUL.md` is
unchanged, both points are on file, and the choice (best NF/S21 slack vs.
best S11/Idd/VDD robustness) is left to the user.

## 37. WP-PGAIN - the gain-programmability gate falls, and the map of where this amplifier is allowed to be touched

**The stage.** Tier-3 item two: gain programmability, >= 10.6 dB in >= 3 steps
(`plans2/14-DHRUVA-SIMUL.md` SS1.2, upgrade #6), recorded since stage 30 as
"NOT ATTEMPTED - no switchable DOFs". The task came with its own framing
attached: *propose* what "programmable" means, do not assume it.

**The decision, and who made it.** The mapping in FINDINGS SS42.1 is
**proposed by this executor and awaits user sign-off** - deliberately the same
shape as the program's earlier S21-for-voltage-gain decision, and written down
before any measurement so it could not be shaped by the answer. One netlist,
one set of device sizes, states differing *only* in control voltages on
inserted MOS switch gates. The one clause added beyond the brief is clause 4:
the max-gain state must still pass the whole D4-SIM gate set. Without it every
mechanism can manufacture a span by ruining its own top state, and the gate
would measure nothing.

**What actually happened first was a harness defect.** A prior stopped agent
had left a draft that inserted switches by literal node name. Those names are
not stable: `size.prepared_body` renumbers internal nodes per *process*, so the
same deck text measured 35.94, 30.26 and 25.24 dB of gain in three consecutive
runs while the untouched design replayed at 35.961 exactly. Everything in that
draft was void, and the replacement resolves every circuit role structurally
from element names, cross-checking each one against a second element that must
touch it. The lesson is bigger than this work package: **element names are the
contract, node names are an implementation detail**, and every future
netlist-post-processing tool in this tree needs to know it.

**The result.** Gate **D6 MET** under the proposed mapping, on the designated
D4-SIM point, unresized: four states, spans 11.23-11.46 dB across the four
bands, S11 <= -10 dB held band-wide in every state, Idd 12.963 mA *identical*
in every state, max-gain state unchanged from SS35.2 on every gate including
NF, replay 3/3 spread 0.0000. The mechanism is a three-branch switched bank on
the output stage's drain; the switches are 8/8/16 um NMOS inside the spec's own
sizing box, and the three states are three gate voltages at the rails.

**The understanding - which matters more than the pass.** Five mechanisms were
built and swept, and the interesting output is not the one that worked but the
map of the four that did not. This amplifier has a **0.001 dB** band-wide match
margin, and that margin turns out to be a *spatial* constraint: the input
combiner, the recombine node, the tuned-stage drain and the output stage's gate
are all match-forbidden - loading the recombine node by enough to move the gain
10.6 dB costs 4.63 dB of match, and loading the input combiner costs 6.77 dB.
Only the output stage's drain and VOUT1 tolerate loading at all, and there the
match *improves*. So the gain control had nowhere to go but the very back of
the amplifier - and gain control at the back of an amplifier buys range without
buying linearity, while the paper specifies IIP3 precisely *at* the
minimum-gain setting. The gate as mapped is met; the thing the paper actually
wants from a gain-programmable LNA is, at this match margin, **not available
anywhere in this topology**. That is the finding to carry forward, and it
points the same direction stage 31 already did: margin is the currency, and
this design has almost none to spend.

## 35. WP-HB — the D5 wall becomes a number, and the number says the topology is wrong

**Decision (stage 30's upgrade ladder, item 4 — the user's call, 2026-08-13).**
Stand up the *proper* IIP3 harness: two-tone **harmonic balance** in VACASK
0.3.4.rc1, an open-source simulator with the frequency-domain steady-state
engine ngspice does not have. Explicitly scoped: target the program's
**existing 45 nm behavioral BSIM4 models**, so the numbers stay comparable
with everything measured so far — the IHP SG13G2 PDK migration, the other
half of that upgrade item, was deliberately **not** started. Gate D5 had been
open since stage 30 with `iip3_dbm` marked `unsupported` in every spec.

**Golden first, and one of the checks was worth more than the rest.** Four
closed-form checks before any design number was read (FINDINGS §40.1): a
memoryless cubic reproduced to six significant figures (+21.2494 dBm analytic,
−0.002 dB extracted error), and — the one that earned its keep — a **negative
control** that runs the same circuit at the simulator's *default* tolerance
and demands it **fail**. It does, spectacularly: the IM3 line drops into
Newton residual noise and the harness reports **+133 dBm instead of +21**.
Without that check, `options reltol=1e-6` is an unexplained line someone
deletes in six months and the harness silently starts passing everything. Two
further checks run the *sibling* transient harness's own closed-form
references through the HB path, so the two D5 harnesses are anchored to
identical ground rather than merely agreeing.

**The port had to be proved, not assumed.** The program's BSIM4 cards
(`level=54`, `version=4.0`) are not obviously portable: ngspice runs them as
BSIM 4.5, and VACASK's OSDI model doesn't even recognise the version string
and falls back to BSIM4.8.3. Two different BSIM4 implementations, and they
agree to **36 nA on Idd (12.96322 vs 12.96318 mA)**, **2 µV worst-case across
all 19 DC nodes**, and **0.0003 dB on S21 at all four band centres** — the
latter measured against a *live* ngspice run of the same deck, not a recorded
number.

**Result (FINDINGS §40.3).** On the designated D4-SIM point, one fixed sizing,
all four bands: IIP3 **−32.76 / −32.70 / −32.14 / −30.28 dBm** against targets
−7.4 / −7.4 / −7.6 / −8.7. **Gate D5 fails 0/4, by 21–25 dB.** Fenced: IM3
slope 2.96–2.97 over six uncompressed drive levels, per-point spread ≤0.43 dB,
invariant to solver tolerance across five decades and to harmonic count 4…8,
and it repeats: a second full 32-point run reproduces all four numbers to
every digit. And it cross-checks against a completely different method —
the sibling's ngspice **two-tone transient + FFT** harness, run on the same
four decks, reads −33.31 / −31.58 / −32.78 / −34.03 against HB's
−33.31 / −31.58 / −32.76 / −33.99: **worst disagreement 0.04 dB**, on two
different simulators with two different BSIM4 implementations.

**Understanding.** The comfortable excuse was available and it does not hold.
The paper specifies IIP3 at *minimum* gain and this design has one fixed
~36 dB point, so it cannot even enter the paper's measurement condition —
that was the standing expectation for why D5 would look bad. But the measured
**OIP3 is only +3.2…+3.4 dBm, and flat to 0.24 dB across all four bands**
while the gain varies by 2.2 dB: linearity here is set by the output stage's
swing budget, not by band, match or gain. Grant the design the entire ≥10.6 dB
programmability range the spec asks for, for free, and assume the ideal case
where OIP3 survives the backoff untouched, and it still lands ~14.8 dB short.
**More than half the miss survives the most generous possible correction.**
Passing would need OIP3 ≈ +14.9 dBm from a 1.1 V rail at 12.96 mA, against
+3.2 measured.

So D5 is not a sizing problem, and stage 34's and stage 31's "margin is the
currency" reading now has a hard floor under it: the five-stage,
weak-inversion, maximum-gain construction that made D3 and D4-SIM *easy* is
the same construction that puts D5 out of reach. It also lands exactly where
stage 37 arrived from the other direction — gain control could only go at the
back of the amplifier, which buys range without buying linearity. Two
independent work packages, two different methods, same verdict: **closing D5
requires changing what this circuit is, not re-sizing what it has.** Worth
noting against stage 31 as well: the hardened point spends 37% of the bias
current to buy S11/VDD robustness, and IIP3 is bought *with* bias current —
the two robustness axes pull opposite ways, and the program now has a
measurement for both instead of an intuition.

## 36. ★★★ WP-DIFF — the output learns to be two wires, and the benchmark's last untried spec falls on the hardened point

**Decision (user, 2026-08-13; stage 30's upgrade ladder, item 5).** Close the
differential-output gap the ACTIVE-BALUN way: build a 3-port harness, author a
balun output stage from the existing MOS/R/C/L vocabulary, and graft it onto
the designated design. Explicitly ruled out in the same breath: extending the
device vocabulary, and coupled-inductor (K) elements — i.e. no passive
transformer balun. The stage had to be an *amplifier*, authored by the
assistant as generic textbook and attributed as such, on the `gmb_cg` /
`nc_cgcs` precedent.

**Result (FINDINGS §41).** Golden first, as always: `check_diff.py` pins the
new harness against five closed forms — an ideal E-source balun (exactly 0 dB /
0°, and the +3.0103 dB differential identity), an RC-skewed balun matched to
its analytic magnitude *and* phase, a **polarity trip-wire** (an in-phase
splitter must read ~180°, so a circuit that merely splits cannot fake a pass),
a 3.0103 dB differential-NF reference, and a band-wide worst-case check.
Two stages were authored and both were measured. On the **hardened**
`dhruva-simul` point (§36, landed the same session), the CS+CG split-phase
balun meets **every four-band gate at one fixed sizing**: imbalance
**0.119 dB / 0.339°** against 0.22 dB / 0.9°, S11 −10.94, Sds21
30.22/30.67/30.05/29.91, NF 1.34–1.74, **Idd 9.25 mA** — the whole differential
output costing **1.045 mA, 1.6 dB of gain, and 0.017 dB of noise**. On the
*designated* `dhruva-l5` point the same stage meets the imbalance spec too
(0.218 dB / 0.586°) and every other gate — and misses Idd by 1.76 mA, because
that point already spends 12.963 of its 13.000 mA budget and therefore cannot
host **any** conducting output stage.

**Understanding.** Three things this stage taught that the numbers alone do not
say. First, **which balun works was decided by input impedance, not by
balance**: the textbook differential pair balances fine but presents a kΩ gate
where the core's match was sized against a 50 Ω port, and §39's knife-edge does
the rest (−10.001 → −9.33 dB, failed). The split-phase CS+CG stage passes
largely because its common-gate leg *replaces the load it displaces* — a result
about this core's fragility as much as about the stage. Second, the
long-standing "differential output" gap was **never really a topology problem**;
it was a measurement problem plus 1 mA of headroom, and the headroom came from
another agent's margin-hardening work the same day. The two work packages only
compose because both refused to move the other's files. Third, and least
comfortable: this search reported the stage's cost as **22.3, then 20.2, then
23.7 mA — each with a clean replay fence — before physics-seeded starts and a
best-of-all-coordinates descent found 14.8.** A reproducible wrong answer is
still a wrong answer; the replay fence proves determinism, not correctness, and
the only thing that caught it here was a hand calculation of what the stage
*should* cost. Finally, the honest asterisk: the gain gate is convention-
dependent (per-leg 27.15 / mixed-mode 30.22 / voltage-gain analogue 33.23
against a 30 dB target), so the pass is recorded together with the reading it
depends on and the reading under which it would fail.


## 32. WP-IIP3 — the cheap harness meant as a stopgap turns into the second opinion, and a golden that fails teaches more than one that passes

**Decision (stage 30's upgrade ladder, item 2).** Build the *coarse* IIP3
prototype: a two-tone transient plus coherent FFT in ngspice, to "turn the D5
wall into a number in a day" while the proper harmonic-balance harness
(item 4) was assumed to be weeks away. Item 4 landed the same session by
another agent (stage 35), so the cheap harness was finished anyway and used
for what it had unexpectedly become — an **independent second opinion** on the
program's first tier-3 measurement, built without sharing a line of code.

**Result (FINDINGS §37).** Gate **D5 fails on all four bands** by
**21.7–25.4 dB** — IIP3 −32.78 / −32.73 / −32.20 / −30.36 dBm against targets
−7.4 / −7.4 / −7.6 / −8.7. The two harnesses, running different simulators,
different BSIM4 versions (4.5 vs 4.8.3), a different analysis kind and a
different extraction estimator, **agree to 0.08 dB** on every band — smaller
than either harness's own tone-spacing sensitivity. The golden agrees with
closed form to 0.020 dB against a 0.25 dB tolerance stated before the run.

**The finding worth keeping is a failure, not a pass.** The golden's G1
check runs the reference with its cubic coefficient set to zero, so every IM3
bin can contain *only* numerical distortion. At the harness's obvious default
timestep it read **−104.9 dBc and FAILED** the bar written into the file
beforehand. The fix was to converge the method rather than move the bar
(10 ps → 5 ps, where the numerical intermodulation drops into the broadband
floor and stops moving under further refinement). The general lesson is
sharper than the fix: **a noise floor measured on product-free bins does not
bound numerical distortion**, because numerical distortion is a *distortion*
process and lands on exactly the frequencies you are trying to read. The
harness's own measured floor looked reassuring — 40-plus dB below the IM3 —
while the real numerical error sat 10 dB *above* that floor, on top of the
signal. Only a null circuit could see it.

**A second failure, caught by a cross-check rather than by inspection.** The
first complete four-band run measured each band's *own* sizing instead of the
one designated D4-SIM sizing at all four f0s. Every deck ran, every sweep was
clean, every slope was 3.0, every number was plausible. What caught it was
requiring the transient's small-signal gain to reproduce the audited
S-parameter S21 — 36.47 dB against the designated point's 33.73 dB at the S
band. That check is now printed on every band (worst Δ 0.02 dB), and the
wrong run was kept deliberately: measured across four independently-descended
sizings, the topology's OIP3 spans only 1.75 dB.

**Understanding.** Three things. First, the flat OIP3 — **+3.17…+3.35 dBm
across four bands whose gain varies by 2.25 dB, and +2.44…+4.19 dBm across
four different sizings** — says linearity here is a property of the output
stage's swing budget on a 1.1 V / 13 mA envelope, not of the band, the match,
or the parameter set. That is what converts "this design misses IIP3" into
"no sizing of this topology meets IIP3": passing at the measured gain would
need an output intercept **22–50× the entire DC power budget**, and even
granting the paper's whole min-gain allowance for free leaves ~14.8 dB
missing. Second, the two independent harnesses reaching the same number to
0.08 dB is worth more than either alone, and it happened only because a
"stopgap" was finished after its own justification had evaporated — cheap
redundant measurement is how a program earns the right to believe its own
tier-3 numbers. Third, the gate ladder's ordering now looks wrong from both
sides: the paper's IIP3 is specified at *min gain*, a condition a fixed-gain
design cannot enter, which makes D6 (stage 37) a prerequisite for a
like-for-like D5 rather than its successor. Flagged for the user, not acted
on; nothing in the design was touched to improve any number here.

## 38. The literature check — nine external systems surveyed before further architecture bets

**Decision** (user-directed, 2026-08-13): before committing to further
architecture work, survey nine external AI-circuit-design systems from their
primary sources — AstRL, AutoCircuit-RL, AnalogGym, DynaOpt, the Cao/RoSE
domain-knowledge DRL line, Krylov's threshold-spec inverse design, AlphaChip,
the AlphaDev/PrefixRL/CktGNN cluster, and ORACLE — extracting representation,
action/state design, algorithms, simulator integration, reward design,
surrogates, and data generation, then synthesize without presupposing this
program's architecture.

**Result**: `lna/SURVEY-AI-CIRCUIT-DESIGN.md` — per-system construction notes
(paper + code level, UNVERIFIED items flagged), twelve cross-cutting findings,
seven conclusions. Nine parallel research agents, all primary-source fetches.

**Understanding gained, most load-bearing first**: (1) the field's reward
function has converged on exactly the clipped symmetric normalized deficit
this program already uses — that sub-problem is settled; (2) for
single-target sizing, BO and supervised inverse models beat RL by 10–100× in
simulation count everywhere a head-to-head exists (AnalogGym: BO at ~117 evals
vs RL at ~6,842); RL pays only when amortized across many spec targets;
(3) validity must be constructional (masking, grammar, repair) — every system
without it tops out below ~83% validity, and AstRL's ablations show masking
removal collapses everything to 0; (4) semantics-in-state (operating point,
truth tables, executed registers) beats structure-only representations in
every system that tried both; (5) surrogates inside an optimization loop need
uncertainty + elite-regime grounding — proxy-truth correlation collapses
precisely among good solutions (AlphaChip τ≈0.05 vs timing); (6) the
strongest single transferable trick is Krylov's dataset construction
(feasible-direction spec relaxation + lexicographic-argmax relabeling), which
makes plain supervised regression competitive with RL at a fraction of the
data; (7) grammar-only and untuned-frontier-LLM null hypotheses beat bespoke
learned systems on at least one task in this survey — consonant with this
program's own stage-27 finding that `grammar_gen.py` beats P5-v7 on NDL@256.

## 39. The proposal — the survey answered back, and the ten-point sketch turns out to be a mirror

**Decision** (executor, same session as stage 38; nothing adopted — every
adoption is queued for user ruling): answer the user's post-survey questions
(AnalogGym? DynaOpt? domain-knowledge DRL? how to do S6? what from S2?),
inspect their two new sources with one agent each, audit their ten-point
"autonomous analog engineer" sketch against what this program already runs,
and put a concrete next-phase proposal plus its radical alternatives on paper:
`plans2/15-ENGINEER-PROPOSAL.md`, decision queue in its §7.

**Result.** (1) The two sources are convergent evolution on this program's own
architecture: `Arcadia-1/analog-agents` is a one-author Claude Code skill
library running librarian/architect/designer/verifier subagents over
Virtuoso/Spectre — process without a single published result — whose liftable
value is schemas (a typed-edge wiki with unverified→verified confidence
escalation, a post-sim hook that injects the margin table into agent context,
checklist YAML, "three failed design-verify loops ⇒ the problem is topology,
not tuning ⇒ escalate" — the D5 story, stated as a rule). arXiv:2603.23910
("AnalogAgent", NTU/A*STAR) is a three-agent PySpice/ngspice loop with a
Self-Evolving Memory that hits Pass@1 92–97 on 30 textbook circuits; its
durable contributions are the memory entry schema (Trigger → Evidence →
Rule/Patch → Applicability, admission-controlled, failure-first) and a
*measured* context-attrition finding — iterative refinement decays "singular
matrix: check nodes vin and vin" into "sim failed" — plus a caution: its
memory largely learned harness trivia, and its self-improvement numbers mix
warm and cold memory. (2) The ten-point audit found eight of ten points
already exist here in v0 form (store, replay fences, tier ladder, surrogate
pre-gate, diagnosis heads, loop cadence with numeric tripwires); the genuine
gaps are machine-queryable memory, diagnosis steering search, formal
acquisition, and an unattended mode. (3) Proposed ladder N1–N5: WP-LIN run as
the pilot of the upgraded loop (IIP3-head surrogate on the fidelity ladder,
swing-directed moves, sensitivity sweep inside acceptance); the post-cutover
data-engine refresh (the 66,664-row store predates three harness cutovers);
sizer nulls (CMA-ES/TuRBO + AnalogGym external calibration — the sizer has no
`grammar_gen` equivalent); memory distillation v0 on the found schemas;
unattended-loop v0 on one bounded task. Radical options logged with verdicts:
re-aim the program so the engineer/benchmark is the product and dhruva the
case study (R1 — genuine fork, user's call); spec-frontier self-play (defer,
then adopt); topology foundation model and RL formalization (reject on the
survey's and this program's own evidence); burst cloud CPU (adopt — the
machine is 8 cores/16 GB and the headline metric is SPICE-minutes, so cores
convert to the metric near-linearly; the GPU is already sufficient for every
model class in use).

**Understanding.** The ten-point sketch is not a new architecture to build
beside this program — it is a description of what stages 1–38 already
converged on, with the autonomy dial at "assisted". That two independent
groups converged on the same shape in the same year says the direction is
right and the differentiator is not the loop, it is what this program has and
they don't: a golden-validated RF harness, frozen protocols with null
hypotheses, and 38 stages of verified decision-trajectory. The next phase is
therefore an increment — make the memory machine-usable, let diagnosis steer
the editor, run one bounded loop unattended — measured by the same headline
curve as everything else, with cold-start controls so the memory's value is a
number, not a vibe.

## 40. The execution wave — seven agents run the proposal's cheap levers, and three of the answers bite back

**Decision** (user, 2026-08-14): "execute whatever changes we can right now,"
Opus subagents for the complex tasks, Sonnet for the light ones. The
coordinator ran seven agents in file-ownership lanes plus a full-store
background job, goldens GREEN before and after; everything adoption-shaped
was measured and *queued*, not adopted (FINDINGS §43, rulings §43.9).

**Result.** Six new/changed artifacts and four numbers that matter.
(1) **The store is now measured against the harness that exists**:
`relabel_era.py` re-labeled all 1,247 stale designs (0 failures, ~40 min) —
1,109 era-stale, median NF −2.1 dB, ~30 stored-FEASIBLE designs infeasible
today, attribution *proven* by an old-geometry fence that reproduces stored
numbers to 0.0000 dB — and the same fence caught 10 rows that fail to
reproduce under ANY geometry (quarantine queue). (2) **The sizer met its
null**: `null_sizer.py` binds CMA-ES to ZOAF's own objective, budget-matched
at 336 evals, and the untuned null wins the first task 4/5 feasible vs 1/5,
best −0.790 vs −0.733 — one task, no verdict, exactly why survey
conclusion 7 exists. (3) **Cao's number reproduced on our critic**:
`--op-features` (flag-gated, default path bitwise intact) lifts source-shift
rho(S21) 0.665→0.848 (+0.183, within-spec wins on every spec) — and the
agent caught why it must not ship as-is: op features exist only *after*
sizing, and `rank_pool` scores un-sized candidates, so deployment would run
entirely in the mask-0 regime. Bias state is worth +0.18 rho; the honest
routes are predicted-OP features or post-sizing re-rank. (4) **The memory
is machine-queryable**: playbook v0, 40 entries (29 verified under a
two-independent-sources rule), 26 typed edges, and nine live corpus
contradictions encoded as `contradicts` edges instead of smoothed away.
Also: the rails-as-nodes lever was already implemented (audit), the
matching-freeze lever was measured breakable and *correctly declined*
(balun asymmetry is the documented D7 knob), `datastore` gained the closed
diagnosis vocabulary, and WP-LIN is pre-registered as a 675-line DRAFT
whose drafting found three rung-0 defects (the §1.2 IIP3 misattribution in
the rulings doc, the missing `dhruva-simul.sp`, the l5-hard-coded
`iip3.py`).

**Understanding.** The proposal said the harness and the store were the
program's real assets; the wave's numbers say the store had quietly become
a liability (a simulator that no longer exists) and one afternoon of
mechanical re-labeling fixed it — while the two "obvious" upgrades the
survey recommended came back one-already-done and one-correctly-refused,
which is what audits are for. The pattern that held all day: every claim
that survived did so because a fence, a null, or a mask question was asked
*before* the number was believed. The wave changed no designated point, no
frozen protocol, and no gate verdict; it changed what the program can trust
under itself. Next stop is user rulings (§43.9 + 16-WP-LIN's D-1…D-9),
then WP-LIN.

## 41. The re-aim — every proposal decision approved, the program becomes two lines, and the engineer line is founded the same day

**Decision** (user, 2026-08-14): "i've been through your engineer proposal,
im fine with all your decisions - i do want to try D6 as well (the re-aim) -
perhaps what you can do is make our current work the main branch, and create
an engineer fork and we'll manage them separately and combine whatever parts
can be combined (training data being generated for example, common models
etc)". Every §7 decision of 15-ENGINEER-PROPOSAL is now RULED as
recommended, and D-6 — the product is the engineer, dhruva the flagship
case study — is adopted as a two-line structure rather than a pivot.

**Result.** (1) **`main` now IS the current work** — fast-forwarded
535104c→5b4b5c2→134978e, a pure ff both times, no conflicts possible; the
LNA program continues on `lna-data` and fast-forwards main. (2) **The
`engineer` line exists**: branch + worktree forked at the same tip,
first commit `912bac1` — `engineer/00-CHARTER.md` (the product, non-goals,
the two-line management policy: shared core lands on main first and merges
main→engineer, engineer inventions return by explicit cherry-pick only,
data combines via the sync tool, models are never binary-shared),
`engineer/env.py` (Task/evaluate/observe/trajectory-log over the lna core,
read-only, with a walk-up runtime-dep shim verified on both the junction
and rebind paths), `engineer/tasks.py` (benchmark registry v0: 8 tasks
pinned by exact ref_ts so no store append can move a frozen budget —
`--check` re-derives all pins GREEN; all tier-2, and the charter states
plainly that no tier-3 task exists until WP-LIN binds the two-tone
harness), and `engineer/baseline_run.py` (the smoke: CMA-ES through the
env on wifi24-smoke, 150 evals = 300 ngspice calls in 15.1 s, infeasible
on s11 by 0.25 normalized at that budget, reproduced to the digit —
reported honestly beside the published 336-eval figure). (3) **The
combining machinery is real**: `lna/sync_lines.py` (prefix-preserving,
snapshot-safe union of the append-only stores + playbook, --check GREEN,
identity dry-run over the live store appends 0) and `.gitattributes` now
mark every jsonl table `-merge` so a raw git merge fails loudly instead of
silently interleaving a snapshot's pinned byte prefix. (4) The founding
took two attempts: subagents inherit the coordinator's worktree pin, so
the first founding agent could not write into the engineer worktree at
all — it converted the block into finished research (the registry, the
binding numbers, the shim design), and the coordinator moved its own
session pin, fixed the missing runtime-dep junctions, and relaunched.
Goldens GREEN in both worktrees.

**Understanding.** The re-aim cost one afternoon because the proposal's
claim held: the engineer product already existed inside the LNA program —
the founding commit contains no new capability, only a clean surface
(Task/evaluate/observe), a benchmark whose budgets are pinned against
drift, and a charter whose real content is the *management policy* for
letting two lines share one append-only data engine without corrupting
each other. The honest edges are stated where they bite: the benchmark
has no linearity rung until WP-LIN lands on the LNA line, wideband-sdr
anchors on a pre-cutover row, and the smoke budget is deliberately too
small to pass — a benchmark that starts honest stays honest. Open next:
the E-queue (E-1…E-5) on the engineer line, WP-LIN sign-off (16-WP-LIN
D-1…D-9) and §43.9 R-a…R-f on this line.

## 42. WP-LIN rung 0 — the designated point's IIP3 measured at last, and both pre-registered predictions land

**Decision** (user, 2026-08-14): execute **rung 0 only** of 16-WP-LIN — the
blocking baseline, no candidate mechanisms, no screen, no surrogate.

**Result (FINDINGS §44).** The largest hole in the corpus (§1.3: the
designated point's IIP3 had *never* been measured) is closed. The
`dhruva-simul.sp` deck now exists on disk (emitted at 1.1 and 1.2 V, plus the
D6 out-bank S3 min-gain variant), and the point's first-ever IIP3 is on file:
**OIP3 −1.35 … −1.82 dBm at 1.2 V max gain, −1.95 … −2.47 at 1.1 V**, IIP3
≈ −34 dBm everywhere. At the D6 min-gain state (out-bank S3, the state D5 is
judged at) OIP3 falls to **−13.0 … −14.0** while IIP3 stays pinned at −34 —
because that mechanism attenuates *after* the nonlinearity (§42.6), so it buys
zero IIP3, exactly as pre-registered. **Gate D5 FAILS 0/4 bands at every
configuration, 26.6–27.7 dB short at the ruled 1.2 V / min-gain condition.**
All transient-harness; VACASK HB is blocked on this box (Windows path in the
golden), so per §7 D-8 nothing is claimed on one harness — the numbers are
reached-by-transient, awaiting-HB. Goldens GREEN first (`check_iip3`,
`check_ref`, `check_diff`); `check_hb` blocked.

**Both predictions confirmed.** **P1** (the hardened point is below the l5
point): the designated point is **5.1–5.8 dB worse** than the l5 point's
+3.2…+3.4 — §40.4's designation-vs-linearity tension resolving against the
hardened point, the bill WP-HARDEN's 37 % Idd cut deferred. **P2** (current-
swing wall, not voltage-headroom wall): confirmed three independent ways — the
arithmetic (current limit binds by 6.93× = 16.8 dB over headroom), the rail
sweep (+100 mV of headroom moves OIP3 by +0.61 dB, under the 2 dB bar), and the
four-point falsification test (OIP3 orders with Iq(MNM6)·|Z_ac| at Spearman
ρ = 1.0000, exact rank match). The re-derived §2.1 operating point reproduces
every quoted digit (Idd 8.205 / 9.463 mA; MNM6 15.1 % of the current, 100 % of
the swing).

**Understanding.** Rung 0 did what a pre-registration is for: it made the
diagnosis falsifiable and then the measurement agreed with it on the record.
The wall is not that the sizing is wrong (§37.7 already showed OIP3 is flat
across four descended sizings) and not that the rail is too low (headroom is
17 dB from binding) — it is that a class-A output stage carrying 15 % of the
budget and the whole swing is current-clipping-limited, and the D6 gain control
lives on the wrong side of that stage to help. What rung 0 does **not** answer
is whether a *front-side* gain-control mechanism plus ~8–9 dB of genuine output
OIP3 could close the min-gain gap (§2.3's decomposition) — that is rungs 1–4,
not run. Candidate N's evidence bar is now 2-of-5 met; N is not recorded (a §7
D-1 user decision). One methodological catch worth keeping: at the min-gain
state the default drive window pushed IM3 into the harness's numerical floor
and failed the slope fence (2.2–2.5); a −68…−52 dBm re-drive recovered a clean
3.06–3.19 slope without moving the OIP3 estimate — the fence caught a drive-
window artefact, not a bad number, and the shortfall was published rather than
smoothed.

**Addendum — same-day HB completion (FINDINGS §44.9).** The transient half above
reported under §7 D-8 because VACASK HB was blocked on this box (Windows path in
the golden, `VACASK_HOME` unset). VACASK was then built for RHEL, `check_hb` went
GREEN, and all four rung-0 configurations were re-measured a second, independent
way — true two-tone harmonic balance in VACASK 0.3.4.rc1 (a frequency-domain
Newton solve on BSIM4.8.3, against ngspice's time-stepping on 4.5). **HB agrees:
Gate D5 FAILS 0/4 bands at every configuration, by 25–27 dB.** At the ruled
condition (max gain, 1.2 V) the two harnesses agree to **0.07–0.09 dB — the
program's 0.08 dB precedent**; the larger deltas at the other rails/states were
investigated and traced to the third-order term of the two BSIM4 implementations
(the linear gain reproduces ngspice's S21 to 0.0008 dB), to drive-window / kept-
set differences, and — for dhruva-l2 at the min-gain state — to a 3 MHz tone
spacing forced by the §40.5 VACASK spectrum pathology once the switch bank is
present (a known ~0.4 dB spacing offset, recorded not smoothed). **The rung-0 D5
baseline is now two-harness measured; D-8's asterisk is resolved.** Both
harnesses also confirm the §2.3 / §42.6 finding cross-method: the output-side D6
mechanism buys **0 dB IIP3** (IIP3 pinned at −33…−34 while OIP3 falls with the
gain to −13 at S3). No candidate mechanism was run (rungs 1–4 remain; user
sign-off was rung 0 only). One artefact tidy rode along: the shipped per-band
`dhruva-*.sp` decks, which carried a stale Windows `.include`, are now
include-portable.

## 43. WP-LIN rungs 1–4 — the redesign runs out of circuit, and the wall gets its full name

**Decision** (user, 2026-08-15): execute rungs 1–4 of 16-WP-LIN as
pre-registered, plus the step-0 R-e correction of the 14-DHRUVA-SIMUL §1.2
tier-3 mis-attribution (the l5 point's IIP3 had been credited to the
designated point; now amended with the measured §44 numbers, the original
preserved in a dated note).

**Result (FINDINGS §45).** The question WP-LIN was written to answer — can a
front-side gain-control mechanism plus ~8–9 dB of output OIP3 close the
min-gain gap — is answered **no, measured, on both halves**. **P4 refuted:**
the §42.3 match wall has *not* lifted on the designated host despite its
+1.484 dB of S11 margin — best front-side match-legal span 4.8 dB (input
combiner; needs 10.6), 2.3 dB (degeneration, the authority ceiling, unmoved),
0.0 dB (recombine node). The forbidden zone is architecture (C_gd coupling),
not margin. **The output half walls at ×2:** the only screen survivor class
(candidate B, pNM6W up) is S11-capped at twice the width, worth **+0.72 dB of
OIP3** — measured in real two-tone and confirmed in HB to 0.007 dB — against
the ~8–9 dB needed. C (raise pR4V) measured *counter-productive* (the load
resistor is the stage's current source: Iq falls faster than Z rises), E (pVB)
measured inert to 5 digits, D/F/G/H killed at rung 1 on the pre-stated cheap
evidence (P5 confirmed). The surrogate was **not trained** — the label supply
is a memoriser's (16 numbers, one topology), said so per §5.1, survivors
ranked by measured proxies instead. Rung 3: **D5 at the D6 min-gain state,
1.2 V, FAILS 0/4 on every candidate, 25.8–28.6 dB short**, fences intact,
replay 0.0000. Rung 4: zero survivors, vacuous; P6 not reached (B is stopped
by S11, never by Idd — the predicted failure mode was the wrong one), P7 not
reached (no nominal pass to flip).

**Understanding.** Rung 0 named the wall (current-swing, output stage); rungs
1–4 measured that *no in-box lever reaches it*. The §2.3 reframing — "at
min-gain the requirement is only ~1× P_dc" — was conditional on moving gain
control ahead of the nonlinearity, and that move is structurally forbidden by
this topology's input-match architecture. With output-side control (the only
match-legal kind), passing D5 at S3 needs OIP3 ≈ +26…+28 dBm ≈ 33–55× the DC
budget — §37.7's number, now measured at the ruled condition on the designated
point. Candidate N's evidence bar stands at **4½ of 5** (the missing half:
candidate D has no in-box build — a §7 D-2 budget question, not an unrun
measurement); N is queued, **not recorded** (§7 D-1). What would have to
change is enumerated and priced in §45.5: the input architecture (D-2), the
output reference impedance (D-7), the Idd gate, or the spec row (D-1) — all
user decisions, none the executor's.

## Current frontier

As of this document's writing (`lna-data`, commit `5be4de3` and whatever
concurrent work is layered on top of it), the following are open, live, or
explicitly deferred to the user:

- **The program's two headline generation metrics have a measured blind
  spot (stage 27).** A grammar-only generator with **no learning in it** beats
  the adopted P5-v7 on both `spec-L0` pass rate (65.6% vs 65.2%) and
  **NDL@256 (168 vs 63)**, and then returns 0 near-feasible designs where
  P5-v7 returns 2 and one audited `wifi24` tier-2 feasible. The first stage
  with any discriminative power is **all-MOS-conducting after bias**
  (3.0% vs 67.7%), which costs ~70 s per 256-sample pool and is already
  computed by `bias.insert_bias`. **Adding it beside NDL in the frozen
  protocol row is a frozen-protocol change and therefore an explicit user
  decision**, same class as the ref-v2 rebaseline and the Gate-C1
  restatement. Until then, no adoption decision should rest on NDL alone.
- **`lna/grammar_gen.py` is the program's null hypothesis** and costs ~50 s of
  CPU for 256 legal circuits. Any future "the generator / search / loop
  produced X" claim now has a cheap, seeded, deterministic control available
  through the identical funnel.
- **Gate D3 is MET on all four dhruva bands** — stage 23 on one 20-device
  search-derived design (`ace8383c`), and stage 24 on `dhruva-l5` **twice
  more**, once by a **generator-emitted** topology with no `moves` edit
  (`80aaf9f4`, NF 1.788) and once by a generator seed plus two existing moves
  (`78f5cc9c`, NF 1.963). ⚠ The stage-24 pair has been audited on `dhruva-l5`
  **only**; whether either closes `l2`/`l1`/`s` is an open, cheap question and
  is the natural next claim. Stage 22's "0.81 dB short on `dhruva-l5`" is
  superseded — it was measured through the pre-cutover single-finger harness.
- **Gate D4-SIM is MET (stage 30)** — the benchmark restated to *one fixed
  sizing, all four bands at once* closed the day it was set: the `dhruva-l5`
  sizing of `ace8383c` passes tier-1+tier-2 on all four bands simultaneously
  (worst NF margin +1.25 dB, worst S21 margin +3.7 dB, 16/16 matrix cells
  PASS across all four sizings).
- **The upgrade-ladder wave (stages 31–37, seven work packages, one day)
  measured the whole tier-3 frontier.** Standing state: **D5 (IIP3) is
  MEASURED and FAILED 0/4** — two independent, golden-validated harnesses
  (ngspice two-tone transient, stage 32/§37; VACASK harmonic balance, stage
  35/§40) agree to 0.08 dB that IIP3 is −30…−33 dBm against −7.4…−8.7
  targets, with OIP3 pinned flat at +3.2…+3.4 dBm across bands *and*
  sizings — an output-swing wall on the 1.1 V envelope; **the topology/bias
  must change, and both harnesses flag that a like-for-like D5 must be judged
  at the min-gain state of a D6 configuration** (the ladder order inverts).
  **D6 (programmability) is MET under a proposed mapping awaiting user
  sign-off** (stage 37/§42: 11.2–11.5 dB span, 4 monotonic states, S11 held
  band-wide in every state — but every match-legal mechanism is output-side,
  so low-gain states buy no linearity). **D7 imbalance is MET on the hardened
  host** (stage 36/§41: CS+CG split-phase active balun, 0.119 dB/0.34°
  band-wide; ALL four-band gates pass there at Idd 9.25 mA; the l5 host fails
  Idd only; the differential *gain* convention is an open user ruling).
  Robustness: the S11 knife-edge is measured (stage 34/§39: ±1% VDD or
  passives flips S11/Idd on the shipped point; NF/S21 never flip) and closed
  by the **hardened `dhruva-simul` sizing** (stage 31/§36: S11 −11.01, Idd
  8.21 mA, passes both 1.1 V and 1.2 V nominals — the only sizing that hosts
  the balun and the switch bank inside the Idd gate; designation pending).
  Polish/descent now **refuse K_min < 1 steps** (stage 33/§38). **All four
  wave-close rulings were taken by the user the same day**
  (`14-DHRUVA-SIMUL.md` §2.1): `dhruva-simul` is the designated D4-SIM point,
  gated at **pVDD = 1.2 V** (it passed the live sensitivity sweep at that
  nominal with zero flips before designation); the §42.1 D6 mapping is
  approved as written; differential gain gates on mixed-mode Sds21; and the
  linearity answer is a **≤1.2 V linearity-aware redesign (WP-LIN, Session
  10)**, judged at the D6 min-gain state.
- **A hardened alternative to `dhruva-l5` now exists but is NOT designated
  (stage 31, FINDINGS §36)**: `dhruva-simul` (S11max −11.01 dB, Idd
  8.205 mA, both ~4× the shipped point's margins) trades away most of
  `dhruva-l5`'s NF/S21 slack, and is the only one of the two that survives a
  pVDD = 1.2 V nominal (`dhruva-l5` fails the Idd gate at 1.2 V — 14.879 mA
  vs the 13 mA cap, all four bands). Both points are on file
  (`lna/repro/dhruva-best/dhruva-{l5,simul}.*`); which one is "the" D4-SIM
  point, and whether the harness nominal should move to 1.2 V, are open user
  decisions.
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
- **`op_points.jsonl` exists, is validated, and is nearly empty** (stage 25).
  156 rows from a demo run; everything measured so far is instrument
  validation plus one read-only survey of six stored designs. The cheapest
  first real question needs no new SPICE: regress NF margin on per-device
  `gm/Id` and region census across the store as a campaign fills the table,
  conditioned on `harness.w_finger` (the stage-23 cutover). The BJT read-out
  is written but has never been run against the one ingested SiGe HBT LNA.
- ⚠ **"Saturated" in this history means *conducting with Vds headroom*, not
  *in strong inversion*** — stage 25 measured that `bias.saturated`'s
  `|Vds| ≥ 1.5|Vdsat|` test passes trivially in weak inversion, where BSIM4's
  `Vdsat` collapses to ~55 mV. Nothing measured under it is wrong; the label
  is narrower than it reads.

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

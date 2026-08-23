# E11-GENEDIT — generator-as-editor (pre-registration DRAFT)

**Status: PRE-REGISTRATION FROZEN — SCORED CAMPAIGN GO (user, 2026-08-23,
second GO given with the §10 results in hand; pre-scored phases GO was
2026-08-23 earlier the same day). This document is committed BEFORE any scored
eval; §Results is appended post-hoc and clearly marked. Goal set = G1'', G9,
G7'', G2'', G12, G13 (all six validated: three E-10A KEEPs, G2''
instrumentation NEAR-MISS, G12/G13 null-RESISTED). Arm-C sampling constants
frozen per §10.3: temperature 0.7, max_new_tokens 256, class token `<LNA_NB>`,
cut uniform over {0} ∪ device-token positions. 54 cells (6 goals × 3 arms ×
seeds 1–3), matched TOTAL B = 600 (G9: 1200).** Every governance rule carries forward from E9-TWOSTAGE /
E8-LADDER-V2 / E7-MOVES: goldens-green before/after every landing, the two-line
branch law (engineer never writes under `lna/`), append-only stores, matched
TOTAL budgets, and user rulings for any spec/protocol/budget change.

Ruling basis (all recorded): user 2026-08-22 — next lever = **generator-as-editor**
(trained model regrows circuit segments; **no hand-authored moves**), every
proposed edit **logged durably** as future training data; user 2026-08-23
(E10-GAPAUDIT §RULINGS) — amended audit verdicts adopted (KEEP G1''/G9/G7''),
G2'' instrument-first (s22 only), G4''/G11'' replaced, **editor model = the
adopted main-line v7 generator checkpoint** declared as a cross-line import.

---

## 0. Motivation — the twice-implicated ceiling

E-9 (executed 2026-08-22) scored guided two-stage **0/6** vs random two-stage
**0/6** vs sizing-only **0/6**; its falsifier is MET and its §5 third sub-reading
governs: the ceiling is **not** budget allocation (E-6), **not** budget
job-splitting (E-9), **not** diagnosis (correct coverage reporting at every tier,
twice) — it is the **move repertoire / editor intelligence** (E-7 §4.4,
E-8 v2 secondary negative, E-9 falsifier; ROADMAP §7). The hand-authored
primitive repertoire (RULED P1–P5, P7 + `add_and_connect_device`) also measurably
exhausts itself: E-9 deviation D1 found only ~40–57 distinct realizable
candidates for the narrow aimed-edit goals — the proposal distribution, not the
budget, is the binding resource.

E-11 replaces the *proposal distribution*: instead of hand-authored graph
primitives, the **adopted main-line v7 generator** (`lna/out/ft_p5v7_v2.pth`, an
autoregressive AnalogGenie-style token-sequence model) **regrows segments of the
anchor topology**. This is the ruled lever, and simultaneously the first
harvest source for learned move priors (ROADMAP §7 direction 1): every proposal
is logged as (state → edit → outcome) training data.

---

## 1. Hypothesis (stated before any number is seen)

> **A trained generative model, regrowing segments of the anchor topology under
> the same two-stage screen-then-size machinery as E-9, proposes structural
> candidates OUTSIDE the hand-authored primitive repertoire and thereby solves
> goals that sizing-only, primitive-random, and primitive-guided arms all left
> at zero.**

The two-stage split is *kept fixed* (it is the best-understood harness for
structural search, and E-9 showed it is not itself the ceiling), so the ONLY
variable between arm B and arm C is **where proposals come from**: hand-authored
primitives vs model regrowth. A win isolates editor intelligence; a flat zero
moves the ceiling to editor training/conditioning.

---

## 2. The editor mechanism — cut-and-regrow with the v7 checkpoint

- **Representation.** The anchor topology's AnalogGenie token sequence (the same
  `templates.emit_sequence` round-trip `realize()` already uses).
- **Proposal.** Sample a cut depth `c` uniformly over the sequence's device-token
  positions (c = 0 permitted: full regeneration); keep the prefix; let
  `ft_p5v7_v2.pth` regenerate the remainder by temperature sampling (the model is
  autoregressive, so v1 regrowth is **suffix regrowth**; mid-segment excision /
  infill would need model surgery and is out of scope). Sampling temperature and
  max-length bounds are fixed constants recorded in the runner; no per-goal
  tuning (G0-FAIRNESS: no task-specific knobs).
- **Gates (identical accounting to E-9 stage-1).** `sane()` L0 gate (0 sims) →
  `realize()` token round-trip + structural screen (0 sims) → **one counted L1
  eval** (`env.evaluate` at x0 = 0.5). Per-candidate stage-1 cost: exactly 1
  counted env eval.
- **No hand-authored moves in arm C.** `g2_moves.mutate` is not called in arm C;
  the proposal distribution is entirely the model's.

**Contamination declaration (required, per G0-FAIRNESS §3 and the nudge-limit
directive 2026-08-20).** The v7 checkpoint is a **cross-line import** from the
main line (adopted P5-v7, trained on the LNA corpus + sanctioned externals; the
imported-checkpoint provenance chain is lna/plans2 §21/§24). Every E-11 run's
contamination ledger YAML declares: `generator_checkpoint: ft_p5v7_v2.pth
(cross-line import, main-adopted)`. The nudge-limit directive is satisfied: no
executor-authored motif selectors or class-specific macros; the model's training
data is the sanctioned corpus+externals ingestion path.

---

## 3. Durable edit logging (RULED, binding)

**Every proposed edit — including proposals rejected at L0, failing realize(),
or culled at L1 — is appended to `engineer/data/e11_edit_log/edits.jsonl`**
(append-only; crash-safe line-buffered writes):

```
{ campaign, goal, arm, seed, anchor_wl, anchor_seq_sha, cut_depth,
  regrown_tokens_sha, regrown_len, gate: L0|realize|L1|survivor,
  l1_objective (if reached), stage2: {evals, best_objective, feasible} (if survivor),
  era, ts }
```

Token sequences themselves are stored content-addressed under
`engineer/data/e11_edit_log/seqs/<sha>.txt` so the log stays compact and the
full (state → edit → outcome) triple is reconstructable — this is the training
substrate for learned move priors (ROADMAP §7 direction 1). Arm B's primitive
edits are logged in the same schema (`regrown_*` → `move`, args) so the two
proposal distributions are comparable post-hoc.

---

## 4. Goals — audit-filtered mix (E-10 amended verdicts, adopted)

| goal | base task | delta (in-memory) | type | provenance / certificate | B | seeds |
|---|---|---|---|---|---:|---|
| **G1''** | dhruva-l1-t2-a | `s21_db ≥ 33` | gain | KEEP (E-10A); solved-in-store certificate wl `ace8383c` (37.53 dB, full-spec-pass) | 600 | 1–3 |
| **G9** | dhruva-l5-t2-a | `s21_ripple_db ≤ 3` | band-shape | KEEP (E-10A); certificate wl `439032fd` (ripple 2.989, full-spec-pass) | 1200 | 1–3 |
| **G7''** | dhruva-l5-t2-a | `idd_ma ≤ 9.0 @ s21 ≥ 22.3` | current | KEEP (E-10A); best point wl `998ff3a1` fails only s11 by 0.74 dB | 600 | 1–3 |
| **G2''** | dhruva-s-t2-a | `s22_max_db ≤ −10` band-wide | match (S22) | **IN — instrumentation verdict NEAR-MISS (2026-08-23, E10-GAPAUDIT §G2'' INSTRUMENTATION):** best measured point wl `5c5047bb` fails only s22 by 0.94 dB | 600 | 1–3 |
| **G12** | dhruva-l5-t2-a | `s11_max_db ≤ −15` band-wide | match (S11) | NEW (replaces G4''); certificate: 3 base-passing store designs at −21.1/−19.4/−15.1 dB | 600 | 1–3 |
| **G13** | dhruva-l2-t2-a | `nf_db ≤ 1.45` | noise (new type) | NEW (replaces G11''); certificate: 1 base-passing store design at 1.38 dB | 600 | 1–3 |

- **Null filter (RULED 2026-08-22: new goals null-filtered at FULL budget).**
  G12 and G13 enter the scored campaign only if they RESIST a full-budget
  sizing-only null (arm-A machinery, B evals × 3 seeds each). If either falls to
  sizing, it is reported and the campaign proceeds with the reduced set (no
  ad-hoc replacement without a ruling).
- **Anchors: the same reached anchor topologies as E-9 — NOT the store-best
  certificates.** The certificates (store rows that already pass) prove
  *reachability*; seeding from them would trivialize the search question. A
  zero-solve on a certificated goal is therefore cleanly a search-efficiency
  failure of the editor, not impossibility.
- Deltas are in-memory spec mutations (`ext_spec_of`), identical to E-8v2/E-9;
  **no spec yaml is edited**. G2'''s band constraint uses the `s22_max_db`
  harness metric landed on main (merged into engineer).

## 5. Arms — matched TOTAL budget, E-9 machinery held fixed

| arm | stage 1 proposals from | stage 2 | purpose |
|---|---|---|---|
| **A** | — (no edits) | full-B CMA-ES on anchor | sizing baseline, byte-identical to E-9 arm A |
| **B** | hand-authored primitives (`g2_moves.mutate`, uniform) | per-survivor CMA-ES | repertoire control = E-9 arm B |
| **C** | **v7 generator cut-and-regrow (§2)** | per-survivor CMA-ES | the lever under test |

k/m/B carried over from E-9 §3.1 unchanged (600: k=120, m=4, 120 evals per
survivor; 1200: k=200, m=5, 200 per survivor), including the D1 stall/rollover
clause (unspent stage-1 budget rolls to stage-2; TOTAL = B exactly). E-9's arm C
(blame-guided primitives) is NOT re-run: its information is already banked at
0/6, and the E-11 comparison axis is proposal distribution, not guidance.

## 6. Metrics

Per (goal, arm, seed) crash-safe cell JSON, as E-9 §4 (solved y/n; PRIMARY =
counted evals + SPICE-minutes to first feasible; stage spend breakdown; winning
edit sequence; survivor set), plus editor-distribution diagnostics per B/C cell:
**distinct candidates proposed / realized / surviving** (the D1 pool-size
measurement, now a first-class metric), and for arm C the cut-depth and
regrown-length histograms (from the edit log). Goal counted solved if ≥ 1 seed
clears base-feasible + delta.

## 7. Falsifier (pre-stated)

> **If arm C (generator-as-editor) solves NO goal that arms A and B leave
> unsolved, the v7-regrowth editor fails at spec-capacity for this goal set, and
> the ceiling moves to editor training/conditioning — learned move priors
> trained on the edit log this campaign banked (ROADMAP §7 direction 1), each a
> future pre-reg.**

Sub-readings:
- **C solves ≥ 1 goal A+B do not** → model regrowth carries structural signal
  beyond the hand repertoire; SPICE-minutes-to-first-feasible ranks arms on any
  shared solve; next step is sharpening (conditioning, priors) not replacing.
- **B solves where C does not** → the primitive repertoire beats the generator
  at structural repair; the import is not the lever; reported as a clean
  negative for generator-as-editor v1.
- **Flat zero again** → with reachability certificates on G1''/G9/G12/G13, a
  zero is *provably* search-efficiency failure, not goal impossibility — the
  strongest possible motivation for trained/conditioned editors, with the edit
  log as day-one training data.

## 8. Not in scope

No new training or fine-tuning of the checkpoint; no playbook (stays OUT per
R-C); no critic-in-the-loop; no oracle diagnosis arm; no spec yaml edits; no
new hand-authored primitives; E-6 stays paused (140/360).

## 9. Containment & crash-safety (binding)

Engineer-branch worktree; `/home/dpatni/circuit-repro` read-only; nothing
writes under `lna/`; ≤ 8 concurrent ngspice; PYTHONHASHSEED=0; per-cell atomic
JSONs under `tmp/e11_results/` + on-disk status file; AnalogGenie symlink
deviation (E-9 D2) pre-authorized if the worktree needs it; torch runs CPU-only
from the contained env. Goldens GREEN before first and after last landing.

## 10. Pre-scored phases (cheap, before any scored eval)

1. **G2'' s22 instrumentation** — DONE (2026-08-23): verdict NEAR-MISS, G2''
   is IN the §4 goal set (E10-GAPAUDIT §G2'' INSTRUMENTATION RESULT).
2. **G12/G13 full-budget null filter** (§4) — arm-A machinery only.
3. **Regrowth smoke** — from one anchor, sample proposals until 50 distinct
   L0-passing candidates or 500 attempts; report realization rate and distinct
   count; **0 counted evals** (L0/realize only, no L1). Confirms the v7
   checkpoint emits realizable sequences before the campaign is committed.

### §10.2 + §10.3 RESULTS (executed 2026-08-23, agent eng-e11p; goldens GREEN before/after)

**Null filters: BOTH goals RESISTED — G12 and G13 stay IN the scored set.**
Arm-A machinery (byte-identical to E-9 arm A), B=600 × seeds 1–3, anchors =
E-9's reached anchors; cells at `engineer/data/e11_null/`:

| goal | solved | best sizing-only reach | gap to delta |
|---|---|---|---|
| G12 (s11_max ≤ −15, dhruva-l5) | 0/3 | −11.29 dB (s3) | 3.71 dB |
| G13 (nf ≤ 1.45, dhruva-l2) | 0/3 | 1.71 dB (s2/s3) | 0.26 dB |

7,200 ngspice calls (3,600 counted evals). One runner race (shared STATUS temp
file) was fixed per-PID; the two affected cells crashed before any sim and were
re-run — no sims wasted.

**Regrowth smoke: the v7 checkpoint DOES prefix-conditioned continuation**, no
modification to `lna/` or the AnalogGenie clone (loaded via
`finetune.ext_vocab("p5")`/`load_ft` — extended 1008-token p5 vocab; NOT
`genie_common.load_model`). Anchor: dhruva-s reached anchor wl `f578743a`
(181-token seq, 48 device-token positions). **Frozen sampling constants** (from
the main line's own `finetune.sample` defaults): temperature **0.7**,
max_new_tokens **256**, class token `<LNA_NB>`, seed 1337; cut depth uniform
over {0} ∪ device-token positions. Outcome: stopped at the **500-attempt cap
with 46 distinct L0-passers** (short of the 50 target); L0-pass 22.4%
(112/500), realize-pass-of-L0 98.2%; regrown length 3–127 tokens (mean 35.1);
cut-depth histogram bimodal (shallow c∈{0,2,5,8} and near-end c∈166–178
dominate). **0 ngspice calls.** All 500 proposals logged to the §3 edit log
(`edits.jsonl` + 423 content-addressed seqs) — the durable-logging ruling is in
effect from proposal #1. Caveat carried into §7 interpretation: distinct-
candidate yield from ONE anchor is bounded (46/500), echoing E-9's D1
pool-size finding — but 46 distinct model-proposed candidates per anchor
exceeds the ~40–57-candidate hand-primitive pools D1 measured, and stage-1
k=120 draws from a FRESH anchor per goal, so the screen is not starved.

## 11. Open items at GO

1. ~~Confirm the §4 goal set once the G2'' verdict lands~~ — RESOLVED: verdict
   NEAR-MISS, G2'' in; goal set = G1'', G9, G7'', G2'', G12, G13.
2. Confirm G12/G13 targets (−15 dB / 1.45 dB) — both RESISTED the full-budget
   null (§10.2 results above), so both are validly sizing-resistant as authored.
3. Confirm arm C sampling constants — now measured (§10.3): temperature 0.7,
   max_new_tokens 256, `<LNA_NB>` class token, cut uniform over {0} ∪
   device-token positions; frozen at GO.

<!-- ================================================================= -->
<!-- RESULTS BELOW — appended AFTER the scored run; nothing above this  -->
<!-- line may be informed by any scored E-11 eval.                      -->
<!-- ================================================================= -->

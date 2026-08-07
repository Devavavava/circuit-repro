# WP-LAST-MILE — converting near-feasible into feasible

**Answers:** the iteration-2 result (loop_state.json): the loop improves the
generator on every axis (NDL 60→73, v2 pool 57% near-feasible, ρ(S21) 0.59)
but `g4_search` found no new feasible design — the curve went 967→1093 and
the exit criterion (two consecutive improving turns) is unmet.
**Diagnosis:** the funnel's broken stage is **near-feasible → feasible
conversion**. All-free ZOAF lands 2/3 constraints and leaves the third barely
off (seq0009: S11 −9.3 vs ≤−10, S21 12.4 ✓, Idd 5.25 vs ≤5); more seeds is
luck-buying at ~30 min/candidate. σ(S21)=1.02 dB is the *same* pathology seen
from the label side — a multimodal all-free sizing landscape.
**Order:** §4 (σ) first — half a day, unblocks the iter-3 retrain — then §1
on the stored near-misses, §2 as its cheap complement, §3 only for candidates
§1+§2 cannot close. §5 lands with whichever turn runs next.

---

## 1. Curated final-mile sizing (~1–2 days, the reliable path)

The tapped reference only sized to feasibility once its match was *fixed*,
not free. Generalize that per candidate — the mechanism already exists:
`size.make_objective(body, spec, sizable, fixed)` takes a `fixed` dict;
curation is a smarter `classify_params` split, zero new optimizer code.

* `curate(topo, spec, op)` → moves the **input-match elements** from sizable
  to fixed: walk the graph from the input port; every series L/C and shunt
  C/L on the path to the first gate is a match element. Fix values by
  formula from the L1 operating point (match Zin ≈ 50 Ω at f0 given gm, Cgs
  — the standard inductive-degeneration / C-divider algebra), or, where the
  formula doesn't apply, a 1-D sweep per element (~20 sims) holding the rest
  at stored `best_params`.
* **Fix-then-free schedule:** (a) fix match, ZOAF everything else (full
  budget); (b) release the match elements for a short polish pass (¼ budget).
  Warm-start pass (a) from the store's `best_x` — do not restart from scratch.
* CLI: `g4_search.py --curated` (flag routes each candidate through
  `curate()` before `run_zoaf`); label rows carry `recipe: curated-v1` so
  curated and all-free labels are never pooled silently (01-DATA rule).

## 2. Boundary polish — min-margin ascent from the stored best point (~1 day)

The near-misses have *slack* to trade (seq0009 holds +0.4 dB S21 slack while
violating S11 by 0.7 dB and Idd by 0.25 mA); the feasibility-first scalar has
no gradient for that trade once it is near the boundary.

* From stored `best_x`: local pattern search (or Nelder–Mead) maximizing
  **min normalized margin** in a trust region (±10–20% per param, log-space),
  budget ~50–100 sims per candidate.
* This is a *refinement mode inside g4_search* (`--polish`), run after §1's
  pass (b), and cheap enough to run on every 1-constraint near-miss in the
  store, not just the top 2.

## 3. One-edit match mutations — the missing stratum M (~2–3 days)

Some near-misses are topology-limited: no sizing closes S11 because the
input network cannot present 50 Ω. For these, a **targeted 1-edit patch**,
which is 03-SEARCH's rung-2 move set narrowed to the three highest-value
edits and aimed at near-misses instead of a random population:

* violated S11 → insert series gate L, or C-divider at the input
  (`templates.py` constructors show the target patterns; apply the edit on
  the `Topology` graph, re-emit via `topo_to_netlist`, L0-screen, then §1).
* violated Idd → add/raise source degeneration R; violated S21 → swap load
  class R→tank/tapped-C.
* Every patched candidate is labeled into **stratum M** — which is still
  empty ("M awaits the mutation move set") and which the feasible-rate
  tripwire needs for contrast as the pool gets good.

## 4. σ back under 0.5 before the iteration-3 retrain (~½ day)

σ(S21) climbed 0.32→1.02 dB; it caps every ρ the critic can reach and is
"watch" status against the 2× tripwire (pinned 0.73).

* Re-label the high-spread repeat-probe keys **best-of-3 seeds**; going
  forward, best-of-k (k=3) *is* the label definition for near-feasible rows
  (all-free single-seed stays for far-from-feasible rows — noise there is
  harmless and the budget matters).
* Store per-key seed spread as `label_sigma`; training downweights rows by
  1/σ (or drops rows with spread > 1 dB). Rank-hinge margin re-derives from
  the new σ (02-CRITIC §3 rule: never ask the model to resolve less than
  label noise).

## 5. Instrument the funnel so a turn is legible without luck (~1 hour)

`feasible_novel = 1` makes the headline curve a step function — one lucky
basin flips it. Keep the headline; add smooth companions per iteration to
`loop_state.json` + the nightly report:

| column | iter-2 value (compute from store) |
|---|---|
| near-feasible rate of new pool | 0.57 |
| near-miss → feasible conversion | 0/2 |
| SPICE-min per **near**-feasible | (report) |
| median total-violation of top-10 | (report) |

An iteration that moves these but not the headline is *progress*, visibly —
which is what iteration 2 was.

## ∥ Parallel (no gates): bigger per-turn pool (512+ samples — shots are 57%
near-feasible now), critic graph+L1 features (the OOD lever, 02-CRITIC §1),
`<LNA_WB>`, Loop-A acquisition picks.

## Acceptance / Gate I3

- [ ] σ(S21) repeat-probe ≤ 0.5 dB under the best-of-3 protocol
- [ ] curated sizing implemented; run on seq0009, seq0220 + every stored
      1-constraint near-miss (v1+v2)
- [ ] **Gate I3: ≥ 1 new feasible novel design this turn** at head-room cost
      (curve point < 967) — two new feasibles bends it decisively
- [ ] stratum M non-empty (≥ 10 labeled patched candidates) if §3 was needed
- [ ] funnel columns in loop_state.json for iters 1–3 (backfilled from store)

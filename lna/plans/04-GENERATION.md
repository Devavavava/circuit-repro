# WP-GEN — making LNA generation better

**Answers:** HANDOVER §3 (all four bullets), §6 items 2–3.
**Cost:** ~1 week across P0–P4; P5 adds 3–4 days, parallelizable.
**Depends on:** 01-SPEC for spec-pass metrics (P0 can start immediately).

The handover names the core problem exactly: prefix conditioning trades
novelty for yield *along* a curve, and we want to *move* the curve. Every
proposal below is judged by one question — does it produce sequences that are
LNA-like without being LNA-copies — under an evaluation protocol that cannot
be gamed by resemblance.

---

## 1. P0 — fix the measuring stick first (~1 day)

Two defects in the current evaluation make every other experiment
untrustworthy, so this lands before any model change:

* **`novelty.py` only compares a sample against *its own seed*.** A sample
  that copies a *different* corpus LNA counts as novel. Fix: fingerprint all
  41 corpus LNA graphs and compare every sample against the full set.
  Eulerian augmentations are reorderings of the same graph, so 41 canonical
  fingerprints suffice.
* **The fingerprint is coarse and gameable.** Replace with a
  **Weisfeiler–Lehman graph hash** over the device–node bipartite graph
  (nodes labeled by device type / net class; `networkx` has
  `weisfeiler_lehman_graph_hash`), plus a **nearest-neighbor distance**: the
  max WL-subtree-kernel similarity against the corpus set, reported as a
  distribution, not a boolean. "Novel" then means *hash not in corpus set*,
  and "how novel" has a number. Bias scaffolding excluded by the 03-BIAS
  naming contract.

**Standard evaluation, frozen here and used by every arm below:** 256 samples,
seeds {1337, 2338}, batch 32, 256-token cap. Report:

| metric | meaning |
|---|---|
| spec-pass@L0 rate (per spec, via 01-SPEC screen) | yield |
| **NDL@256** — novel distinct LNAs (WL-novel, spec-passing) | the headline number |
| median NN-similarity of spec-passing samples | copying pressure |
| inductor ratio + share carrying any inductor | the inductor gap |
| % structurally valid, % terminated | health |

Re-run the existing prefix-length sweep (4/8/12/24) under this protocol to
re-baseline. Current best guess from old numbers: NDL@256 ≈ 32 at prefix 12.
**Adoption rule for every proposal: NDL@256 must beat the re-baselined prefix
sweep's best point, at equal or better inductor ratio.** That is what "moving
the curve, not sliding along it" means operationally.

## 2. P1 — class-token conditional fine-tune (~1 day + <1 h GPU) — highest leverage

Replace the prefix hack with an honest conditioning channel. Append **new
tokens after TRUNCATE** (existing ids untouched — `test_vocab_matches_upstream`
still passes by construction): `<LNA>`, `<OTHER>`, and once P5 provides labels,
`<LNA_NB>`/`<LNA_WB>` per spec class.

* Training rows: `<CLASS> VSS ...traversal... TRUNCATE`, class token prepended.
  Data = 4,023 LNA sequences as `<LNA>` + a ~20–25% replay mix of general-corpus
  sequences as `<OTHER>` (guards against catastrophic forgetting and — more
  importantly — teaches the *contrast*).
* Checkpoint surgery: resize token embedding + lm_head rows; initialize new
  rows to the mean embedding. Everything else loads as-is. Upstream
  `Pretrain.py` is the training loop to adapt (AdamW, lr 3e-4 → use 3e-5 here,
  batch 64 won't fit at block 1024 on 4 GB for *training* — pad LNA rows to
  128 tokens instead, batch 32; minutes per epoch at 11.8M params).
* Holdout: 6 of 41 circuits (all their augmentations) excluded from training,
  used only for evaluation.
* Sample with bare `<LNA> VSS` — **no LNA prefix at all**. The model now has
  to *generate* LNAs rather than continue one, which is the structural fix to
  the copying problem: there is no seed to copy.

Why this ranks first: the prefix mechanism copies because conditioning
information arrives *as content*. A class token conditions without content.
Measured success = NDL@256 above the prefix baseline with seed-copy rate near
zero by construction; failure mode = model ignores the token (detectable in
one evaluation run — if `<LNA>` and `<OTHER>` samples have identical inductor
stats, it ignored it, and the fix is a higher LNA mix or longer fine-tune).

## 3. P2 — plain LNA fine-tune (~1 day + <1 h GPU) — the stated baseline to beat

FINDINGS §8 Phase 2 as written: fine-tune on the 4,023-sequence corpus (same
replay mix and holdout as P1, no vocab change), sample from bare `VSS`.
Run it not because it is the best idea but because the handover correctly
demands it as the baseline. Prediction to test: it will raise hit rate but
also raise whole-corpus copying (which P0's metric now catches, where the old
seed-only metric would have flattered it). P1 and P2 are one experiment
apart — same data pipeline, ±class token — so build them together and let the
bake-off decide.

## 4. P3 — anti-copy decoding (~1 day, sampling-only, composable with everything)

For any conditioning that still uses content prefixes (and for P1/P2 outputs
that drift into recitation): **seed-aware n-gram blocking**. While generating
with a prefix from seed circuit S: if the last k tokens (k≈4) match a k-gram
of S's traversal, subtract λ from the logit of S's recorded next token.
Escapes verbatim continuation while leaving the distribution otherwise alone.
Two knobs (k, λ), swept cheaply at sampling time. Add a temperature schedule
(low for the first ~20 tokens, higher after) as a second, independent lever.

This is the direct "raise the novelty ceiling at prefix 24" tool: the 50.8%
hit rate at prefix 24 currently costs 83% copying; if n-gram blocking holds
hit rate ≥ 45% while cutting copies to < 40%, the curve has genuinely moved.

## 5. P4 — the inductor gap: logit bias + grammar mask (1–2 days)

The handover asks whether constrained decoding beats fine-tuning here.
Answer: **they compose, and the constrained-decoding half is nearly free, so
do both.** Two layers:

* **Grammar mask (validity, not steering).** The token grammar is rigid: a
  device token must be flanked by its own pins; a pin's device is determined
  by its name; TRUNCATE only after a complete traversal. A boolean mask over
  next-token logits enforcing this costs a table lookup per step and pushes
  structural validity from ~97–99% to ~100% — but more usefully it defines
  *where a fresh device choice happens*, which is the hook the next layer needs.
* **Inductor logit bias (steering).** At positions where the grammar allows
  introducing a *new* device, add +λ_L to unused L-family tokens until the
  sequence's running inductor ratio reaches the spec class's target (0.188
  for narrowband; ~0 for wideband — the spec is the source of truth, per
  01-SPEC §5). Decay the bias once satisfied. λ_L swept over {0.5, 1, 2}.

Risk: biased-in inductors may be structurally valid but electrically
pointless (dangling in series with nothing relevant). The L1 feasibility gate
(03-BIAS) and ultimately L2 sizing are the honest judges; if L1 attrition of
P4 samples exceeds the unbiased arm's by >10 points, the bias is manufacturing
junk and the lever should yield to P1/P5.

## 6. P5 — archetype template corpus (3–4 days, parallelizable; the answer to "is 41 enough")

41 underlying graphs is **not enough** to move an 11.8M-parameter model's
distribution and never will be; 4,023 augmentations are orderings of the same
41 graphs. The only legitimate new-data source available on this machine is
**synthesis from known LNA archetypes** — and it is a good one, because the
archetype space is well understood and enumerable:

* Input stages: CS + inductive degeneration (± Cex), CG (± gm-boost), CS
  resistive-feedback, noise-cancelling CG∥CS.
* Options that combine with each: cascode / none; load = resistor, tuned tank,
  shunt-peaked R+L; input match = Lg series, C-divider tap, none;
  output buffer = source follower / none; single-ended (differential deferred).

A `lna/templates.py` generator emitting *graphs* (then Eulerian-encoded by the
existing `build_lna_corpus.py` machinery) yields **~150–400 distinct valid
topologies with class labels** (narrowband/wideband — feeding P1's per-class
tokens). Mix with the 41 real circuits for fine-tuning (real circuits
oversampled ~3× so textbook diversity isn't drowned by template regularity).

Objection to preempt: "the model just learns the templates." Partially yes —
and that is acceptable, because the goal is a generator over *valid LNA
space*, and the bake-off's NDL metric counts only topologies distinct from
the *entire* training set (templates included: their WL hashes go into the
reference set too). If NDL collapses, the templates were too regular —
randomize option combinations harder. Augmentation cost note: Eulerian
augmentation runs ~1 min/circuit (F5); for 300 templates cap augmentations at
~10 orderings each and expect a few hours, run overnight in WSL.

## 7. The bake-off (half a day of compute, the WP's decision point)

Matrix, each cell = standard evaluation from §1:

| arm | conditioning |
|---|---|
| baseline | prefix 8 / 12 / 24 (re-based under P0 metrics) |
| P1 | `<LNA>` token, no prefix |
| P1+P4 | token + inductor bias |
| P2 | fine-tuned, bare VSS |
| P3 | prefix 24 + n-gram block (best k, λ) |
| P1+P5 (if P5 done) | per-class token, no prefix |

Adopt whatever wins NDL@256 at acceptable inductor ratio; record the table in
FINDINGS.md as §5's successor. Generation cost per arm is ~2 min on the GPU;
fine-tunes are < 1 h each; the whole matrix fits in an afternoon.

## 8. Representation verdict (HANDOVER §6 item 2)

**Keep the Eulerian-path representation and the pretrained checkpoint.**
Grounds:

* Evidence it works: 0 → 40.6% steering with no retraining; 92% of screened
  candidates simulate; reconstruction is exact; sequences are short (≤107
  tokens) so the quadratic no-KV-cache cost stays tolerable.
* The alternatives (graph diffusion, GraphRNN-family, GFlowNets over graph
  edits) all forfeit the 3,351-circuit pretrain and must learn from 41 LNA
  graphs (+ templates) on a 4 GB card. That is a research project with a
  plausible *worse* outcome, not an upgrade.
* The representation's real defects have in-representation fixes, mapped
  above: no conditioning channel → P1; seed-copying → P1/P3; unbounded
  length → the 256-token cap already in use (and the cap is itself a steering
  knob, FINDINGS §5); VSS-start is a harmless convention.

**Revisit trigger, stated now so it is not litigated later:** if after P1, P4
and P5 the best arm still cannot reach **NDL@256 ≥ 2× the prefix-12 baseline**
or the L1-conducting yield stays below ~15% of raw samples, the substrate is
the bottleneck and a graph-native generator over the template grammar (skip
the LM entirely; sample archetype space directly and let ZOAF differentiate)
becomes the pragmatic alternative. Note that fallback is *cheaper* than a new
neural representation, not more expensive — worth remembering before anyone
proposes a diffusion model.

P6 (KV cache) stays deferred: at 0.3 s/sequence, generation is not within an
order of magnitude of being the bottleneck — ngspice and sizing are.

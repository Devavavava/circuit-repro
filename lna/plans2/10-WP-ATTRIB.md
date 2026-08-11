# WP-ATTRIB — how much of the capability is the learned generator, and how much is the harness?

**Status:** pre-registered 2026-08-11, **before a single arm was sampled or sized**.
**Branch:** `lna-data`. **Owner:** the WP-ATTRIB executor (Session 7).
**Series:** continues `plans2/01-DATA` through `plans2/09-WP-OBSERVE`.
**Documentation slots:** FINDINGS **§31**, JOURNEY stage **26**,
`STRUCTURE_LOGIC.md` Block 3 design-decisions.

---

## 0. The question

The program's record brackets the extremes of "does the generator matter?" but
has never measured the middle:

* the **upstream pretrained checkpoint** scores NDL@256 = 16 on `wifi24`
  (`HANDOVER-EXEC` finding #4) against P5-v7's **79** (`FINDINGS §24`);
* the template-free control (`§16`) and the curriculum arms (`§18`) measured what
  the *training data channels* buy, but every arm in those experiments was still
  a fine-tuned 11.8M-parameter transformer;
* gates have been closed **with** the generator (`§29`'s `80aaf9f4`) and
  **without** it (`§15`'s evolved `8c7592ea`, `§25`'s hand `rfbcs3` family);
* `§29.12` established the rule that *"a capability negative is only as strong as
  the selector that produced its candidates."* Nobody has yet applied the
  symmetric rule to a capability **positive**: a generator's measured yield is
  only as strong as the *baseline* it is compared against, and **this program has
  no no-learning baseline at all.**

So: **how much of the pipeline's end-to-end capability lives in the learned
generator, and how much lives in the surrounding harness** (L0 screen, rule-based
bias, rung-0 candidate selection, the critic, ZOAF sizing)? Every number in the
record that reads as "the generator did X" is currently un-attributed, because
the counterfactual — *the same harness fed by syntax alone* — has never been run.

## 1. Design — four arms, one funnel

Four generators, **256 samples each**, seeds 1337 + 2338 at 128 each (the frozen
protocol's canonical two-half shape — `novelty.evaluate` accepts a list of dirs
precisely to concatenate them).

| arm | what it is | learning content |
|---|---|---|
| **GR** | grammar-only: random device multiset inside `wifi24`'s device budget, random legal wiring, serialized through the upstream Eulerian pipeline | **none** |
| **GR+RAG** | GR, but each sample is seeded with the partial graph carried by the first 12-24 tokens of a retrieved real corpus LNA traversal, then completed randomly-legally | **none** (retrieval only) |
| **G2** | AnalogGenie `Pretrain.pth`, no fine-tune, at its best known operating point (prefix conditioning, `--prefix-len 12`) | upstream pretrain only |
| **G3** | **P5-v7** (`lna/out/ft_p5v7_v2.pth`), the adopted baseline, unconditioned `<LNA_NB>` sampling | full program lineage |

### 1.1 GR — what "legal" is allowed to mean

`lna/grammar_gen.py` builds a graph in `read_netlist` form (`[name, nets..., type]`)
and serializes it with `templates.emit_sequence` — **the same upstream
`build_connection_matrix` + `dfs_all_paths` path** the 50-circuit corpus, the 148
archetypes, the 9 externals and `moves.py`'s mutants all use. No hand-rolled
token walks.

The well-formedness rules are **exactly** those required for a decodable,
simulable circuit. Each is justified below as *required for validity*; none is
justified as *good for LNAs*:

| rule | why it is REQUIRED |
|---|---|
| the device-pin graph is connected | `dfs_all_paths` covers every directed edge from `VSS`; a disconnected graph has **no** covering traversal and `emit_sequence` returns `None`. Not a preference — a serialization precondition. |
| at least one terminal on `VSS` | the traversal's `start_node` is `VSS`; with no terminal there, `VSS` is an isolated vertex and no sequence exists. |
| `VIN*` and `VOUT*` nets each carry a terminal | the representation encodes ports **as nets**; a net that no pin touches never appears in the token stream, so a design without them is not a decodable two-port and `to_spice` has nothing to drive or measure. |
| every internal net carries at least two terminals | a one-terminal node is a floating node, hence an ngspice singular matrix. Not simulable. |
| per-type instance count within the frozen vocabulary's capacity (NM/PM 34, R 27, C 15, L 23) | a 16th capacitor would emit the token `C16`, which is **not in the 1005-token vocabulary**. Outside the representation. |
| device count inside `wifi24.topology.device_budget` = 3..16 | the budget the arm is being compared inside; stated by the work package. |

**Explicitly NOT applied:** no archetype fragments, no motif preference, no
device-ratio prior, no inductor targeting, no `max_inductors` cap (that is an L0
criterion and applying it would manufacture the pass rate being measured), no
bulk-to-rail convention, no gate/source/drain role assignment. Device kinds are
drawn **uniformly** over NM, PM, R, C, L and every pin — including MOS bulk —
is assigned uniformly at random over the node pool.

> **One recorded restriction, with its reason.** Bipolars (NPN/PNP) are in the
> vocabulary and `to_spice` has emitted them since `§19`, but they are excluded
> from GR's kind set because two *harness* gaps would otherwise be what the arm
> measures rather than the grammar: `topology.lna_score` / `spec.structural_screen`
> count `has_transistor` as **MOS only** (`§19.1` gap (a)) and `bias.py` has no
> base-bias rule (`§19.1` gap (b)). This is a deviation from "pure syntax" and is
> recorded as one.

Construction is: draw a device count uniformly in 3..16, draw kinds uniformly,
draw an internal-node count uniformly from the range a two-terminal-per-node
wiring can fill, assign every pin uniformly at random over the node pool
(VDD, VSS, VIN1, VOUT1 plus the internal nodes), then apply a **minimal repair**
for the table above (merge under-filled internal nodes, join components, move a
pin onto an empty required port). The repair is part of the arm and is reported,
not hidden.

### 1.2 GR+RAG — which variant

The preferred form (emitted sequence literally *begins* with the retrieved
prefix) requires constraining the upstream Eulerian walk's start. Upstream's
`dfs_all_continue` can only extend a prefix that is a **simple descent** and it
finishes by retracing that prefix in reverse — the opening 12-24 tokens of a real
traversal generally contain backtracks, so honouring the preferred form means
reimplementing the walk. That is disproportionate, so **the fallback variant
declared in the work package is what will run and what will be reported**:

> the retrieved partial graph (the sub-graph induced by the first K tokens,
> K drawn in 12..24, of a traversal of a corpus LNA eligible under
> `wifi24.seed_filter`) is **fixed as a subgraph**, the rest of the circuit is
> completed randomly-legally by the GR sampler, and the result is serialized
> normally.

Retrieval eligibility is `Spec.seed_filter` (for `wifi24`: inductor-bearing
corpus LNAs), the same predicate the conditioned-generation path uses.

### 1.3 The funnel — identical for all four arms

Any asymmetry invalidates the comparison, so every stage below is one code path
fed four pools:

1. **valid construction / valid decode** — `Topology.valid`, termination.
2. **L0** — `wifi24` `spec.structural_screen` (`screen.py` / `spec.py`).
3. **Novelty** — `novelty.evaluate(..., ref="ref-v3")`: NDL@256, copy rate
   (archetype / corpus / external split), median NN-sim among passers, inductor
   ratio.
4. **Bias** — `bias.insert_bias` at default rules (v1: R-GATE only; the v3
   DC-return rules stay **off**, as they are for every other arm, `§21`), and
   the `all_conduct` rate over screen-passing samples.
5. **Rung-0 selection: FIXED ACROSS ARMS.** This is the lesson of `§29.12` and
   the single most important symmetry in the design. Qualifying pool per arm is
   the intersection of {screen-passing}, {novel vs ref-v3}, {WL-deduped} and
   {`_match_struct.analyze` reports `port_src`}. All four arms' qualifying
   candidates go into **one** pool JSON, are ranked by **one** critic-v2 GNN
   ensemble (`search.rank_pool`, leak-free: every store row whose `wl_hash`
   appears in the combined pool is dropped before training), and each arm takes
   its own **top 10** by the same `mean - beta*sigma` feasibility scalar. One
   model, one scoring function, four arms.
   *If an arm has fewer than 10 qualifying candidates, everything it has is
   sized and the shortfall is reported as a result, not patched.*
6. **Sizing** — equal budget per candidate, `wifi24`, current harness
   (multi-finger `W_FINGER = 2e-6`, `inductor_q = 12`, NF gated per the spec).
   The recipe is the **arm-comparison protocol** already used for exactly this
   purpose: `search.SCAN_BUDGET` (`n_candidates=4, sgd_iters=5, cgd_iters=1`)
   followed by a box-clamped `size.polish(budget=60)` — byte-identical to what
   `§16`'s novel-front comparison and `§20.4`'s live rung-1 used. Store recipe
   **`attrib-v1`**, with `provenance.source_arm` set per arm.
7. **Report** — ONE funnel table ending in the program's currency:
   **near-feasible and feasible-novel per SPICE-minute**, accounted the way
   `loop.spice_curve` does (n_evals times SEC_PER_SIM over 60).
8. **Cheap addendum** — the same generation statistics (L0 / NDL / copies) under
   `dhruva-l5`'s screen, no sizing, for the record.

## 2. Predictions (registered before any arm ran)

1. **GR passes L0 at a nontrivial rate** — at least 15% on `wifi24` — because L0
   is a *structural* screen and random graphs inside the device budget satisfy
   most of it by construction. **And it produces about 0 near-feasible designs
   per SPICE-minute.** The L0 screen is cheap to satisfy and says almost nothing.
2. **GR's NDL@256 is high, plausibly the highest of the four**, because a random
   graph is essentially never a copy of anything. This is registered explicitly
   as a **prediction that NDL is a weak proxy for capability**: if a no-learning
   arm tops the program's headline novelty metric, that is a statement about the
   metric, and it must be reported as one.
3. **GR+RAG lifts the L0 pass rate over GR** (the seed contributes real LNA
   structure) **and its novelty is copy-dominated relative to GR** — median
   NN-sim rises and NDL per screen-passing sample falls, the same law `§28.6` /
   `§29.7` measured in three other channels.
4. **G2 (pretrained, no fine-tune) lands between GR and G3 on L0 and below both
   GR arms on novelty-per-sample**, reproducing the historical NDL@256 = 16
   ballpark under ref-v3.
5. **G3 (P5-v7) wins feasible-novel per SPICE-minute by more than 2x** over
   every other arm, and wins near-feasible per SPICE-minute over the no-learning
   arms.
6. **Zero arms produce a `wifi24` tier-2 feasible design at this budget** — the
   record's tier-2 count is two designs in the program's entire history.
7. **The qualifying-pool shortfall will bind on at least one arm**: the
   source-driven motif runs at about 19% in P5-v7 (`§29.6`) and there is no
   reason a random wiring exceeds it by much, so at least one arm is expected to
   yield fewer than 10 qualifying candidates.

## 3. Decision rule (registered before any arm ran)

Let R(arm) be **feasible-novel per SPICE-minute**, with **near-feasible per
SPICE-minute** as the declared tie-breaker when the feasible count is 0 in every
arm (which prediction 6 says is likely).

* **If R(GR+RAG) lands within 2x of R(G3)** — i.e. the no-learning retrieval arm
  gets within a factor of two of the adopted generator on the program's own
  currency — then **the learned content contributes little beyond syntax plus
  retrieval, and the harness is the product.** The correct reading of every "the
  generator did X" claim in the record becomes "the harness did X, given a
  syntactically valid candidate stream."
* **If the no-learning arms collapse** (R(GR) and R(GR+RAG) far below R(G3), or
  0 qualifying candidates), **the generator's lift is quantified** by the ratio,
  and that ratio is the first honest number this program has for how much of its
  capability is learned.
* **Either verdict is reported.** The funnel table is published in full
  regardless of which way it falls, including any column where a no-learning arm
  beats the adopted generator.

## 4. Scope and method discipline

**In scope:** `lna/grammar_gen.py` (new), `lna/_attrib_*.py` helper drivers,
`lna/plans2/10-WP-ATTRIB.md`, FINDINGS §31, JOURNEY stage 26, a Block-3 note in
`STRUCTURE_LOGIC.md`, and append-only store rows under recipe `attrib-v1`.

**Out of scope / untouched:** every frozen protocol (NDL@256, ref-v3, the
snapshots, the specs, the screen), `lna/surrogate.py`, `lna/critic_gnn.py`,
`lna/extract.py`, `lna/size.py` (all owned by concurrent agents or by the frozen
core). The arms are **measured under** the frozen protocol; they do not modify
it. Blind protocol holds throughout: no consultation of the excluded paper.

**Regression quartet green before and after** (`HANDOVER-EXEC` §4/§8).

**Store note (expected):** `data/topo_labels.jsonl` is shared and carries
uncommitted rows from concurrent agents; committing it commits theirs too, which
is established practice and will be stated in the commit message.

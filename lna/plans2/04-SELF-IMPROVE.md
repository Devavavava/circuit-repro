# WP-LOOP — self-improvement without self-deception

**Answers:** brief Stage 3 (every SPICE evaluation becomes training data;
periodically fine-tune the generator on the highest-scoring designs).
**Deliverables:** loop cadence + acquisition policy in `campaign.py`,
generator expert-iteration recipe in `finetune.py` (new data source, existing
machinery), tripwire monitors, monthly FINDINGS entries.
**Cost:** 1–2 months of *cadence*, not build — Stages 0–2 already built every
moving part. **Depends on:** 03-SEARCH rungs 1–2 run at least once.

Stage 3 is three feedback loops sharing one store, plus the tripwires that
keep them from eating each other.

---

## 1. Loop A — critic ← data (active learning)

The nightly campaign (01-DATA §5) switches from fixed strata to
**acquisition-driven picks** for half its quota:

* **Uncertainty picks:** the candidates the §03 uncertainty gate rejected
  from search (high-σ, promising mean) — labeling exactly what search wanted
  to know and couldn't trust.
* **Disagreement picks:** largest ensemble-member spread among L0/L1-passing
  pool members.
* The other half stays stratified (templates / generated / mutations /
  repeat-probes) so coverage never collapses onto the search frontier.

**Retrain cadence:** every ~+100 L2 rows or weekly, whichever first.
Versions v2, v3, … each pinned to a snapshot. **Adopt-only-if-better:** a new
version ships only if it improves the pinned family-holdout metrics; ties go
to the incumbent. Holdout growth rule: newly discovered WL-families are
assigned train/holdout 80/20 by deterministic hash at first sight, so the
holdout grows with the frontier and can never be trained on later.

## 2. Loop B — generator ← winners (expert iteration)

`finetune.py` already does checkpoint surgery, replay mixing, and class
tokens; Stage 3 only changes *what it eats*:

* **Winner set:** all feasible designs + top-quartile near-feasible by sized
  scalar (true SPICE numbers only — critic scores never select training
  data, or the loop distills its own bias). Eulerian-augmented as usual.
* **Mix:** winners + P5 templates + the 41 real circuits (oversampled ~3×) +
  ~20–25% general-corpus replay — the proven P1/P2 recipe with a new
  ingredient, not a new recipe.
* **Cadence:** per ~100 new sized rows or monthly. Fine-tune from the
  *current* production checkpoint; keep every checkpoint (they are 198 MB,
  gitignored, but disk-cheap — revertability is a tripwire requirement).

## 3. Loop C — search ← both

After each critic/generator adoption, re-run rung-1 rerank (one night,
control included) with the new pair. This is where the phase's headline
curve gets its points: **SPICE-minutes per feasible novel design, per loop
iteration.** Bending that curve is what "self-improvement" means here;
everything else is instrumentation.

## 4. Tripwires — numbers, not vibes, each with a scripted response

| monitor | trip condition | response |
|---|---|---|
| frozen NDL@256 (protocol FINDINGS §5, **reference ref-v2** — see the amendment below) on every adopted generator | NDL drops > 20% vs pre-loop baseline | revert checkpoint; raise replay %; halve winner oversampling |
| distinct WL-families per 256-sample eval | < 50% of pre-loop count | same as above — this is mode collapse showing up early |
| critic holdout table across versions | any primary metric worse | version not adopted (rule §1) — automatic |
| repeat-probe σ (01-DATA §5), monthly | σ drifts > 2× | stop labeling; re-baseline the harness (env/ngspice change suspected) before any retrain |
| labeled-pool feasible rate | > 60% (margins compressing) | add hard negatives: mutations of winners + random screened topologies, so the critic keeps contrast at the top |

The last row is the subtle one: as the generator improves, the labeled
distribution concentrates near feasibility and the critic loses its gradient
exactly where search needs it. Stratum M (1-edit mutations of winners) is the
standing antidote.

### 4a. AMENDMENT (2026-08-09, user decision) — NDL's novelty reference is **ref-v2**

The frozen NDL@256 protocol is unchanged in every respect *except* what counts
as novel. Its reference used to be the 41-circuit corpus alone — so a verbatim
regeneration of a `templates.py` archetype, i.e. the generator's own training
data, scored as novel. Measured: **~51% of a P5 pool's screen-passing output**
was exactly that.

| reference | contents | hashes | digest |
|---|---|---|---|
| `ref-v1` | 41 corpus LNAs (the original P0 freeze) | 41 | `5273a4f673b5eb6a` |
| **`ref-v2`** (default) | 41 corpus + all 148 `templates.py` archetypes | **189** | `b5689490d0285c37` |

**Re-frozen adopt-only-if-better baseline (P5-v3): nb 100 → 52, wb 35 → 21**, at
unchanged inductor ratio (0.224 / 0.077). `ref-v1` stays available
(`novelty.py --ref v1`) so historical numbers reproduce, and **every protocol row
records the reference version, size and digest** — mandatory, because the
archetype set has grown 92 → 118 → 135 → 148 and "ref-v2" alone no longer pins a
number.

Two rules that follow, both measured (FINDINGS §14.5):
* **Never compare an NDL number across references, and never assume a constant
  offset.** The correction ranges 0 (a corpus-only arm cannot copy templates) to
  −50, scaling with how much archetype mass the arm was trained on. It is
  *not* order-preserving across checkpoints — P5-v2 overtakes P5-v4 and P5-v5
  under ref-v2 — though no adopt/reject decision the program actually took flips.
* **`NDL_v2 ≤ NDL_v1` always** (ref-v2 ⊋ ref-v1), which is enough to settle some
  historical comparisons even when a pool has been lost.

## 5. Governance and the monthly entry

Append-only store; every row carries loop-iteration provenance; every model
version pins {data snapshot, code sha, config}. One FINDINGS entry per loop
iteration: rows added (by stratum), critic version + holdout table, generator
version + NDL row, Gate-G4 design count, and the §3 curve. If an iteration
made things worse, the entry says so — reverted versions are results too.

**Exit criterion for the phase:** two consecutive loop iterations with the
§3 curve improving and all tripwires quiet. At that point Stage 3 is an
operating mode, the plan set is done, and the next phase (whatever it is —
differential specs, IIP3, a second band) inherits a system that gets better
by being used.

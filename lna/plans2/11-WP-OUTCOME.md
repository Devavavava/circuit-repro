# WP-OUTCOME — teach the generator what its topologies achieved, without RL

**Status:** pre-registered 2026-08-11, **before a single epoch was trained**.
**Branch:** `lna-data`. **Owner:** the WP-OUTCOME executor (Session 7).
**Series:** continues `plans2/01-DATA` … `plans2/10-WP-ATTRIB`.
**Documentation slots:** FINDINGS **§32**, JOURNEY stage (next free at wrap-up),
`STRUCTURE_LOGIC.md` Block 3 (new arm + verdict).

---

## 0. The question, and the two hypotheses that are both live

The generator has never seen a single measured outcome. It is trained by
next-token cross-entropy on token streams (Block 3), and **every feedback channel
tried so far has failed the same way**:

* **winners feedback** (`§28`, a *training* channel) — REJECT, nb NDL 79 → 67;
* **prefix conditioning** (`§29.7`, a *decoding* channel) — motif rate 0.192 →
  0.926 and **zero** extra usable candidates, NDL 79 → 10;
* **row re-weighting** (`§29.8`, a *sampling-weight* channel) — REJECT, nb NDL
  79 → 45 for a 1.43× motif rate.

`§29.12` states the law those three share: **the steering signal pointed at
structure the model had already memorised, so it returned that structure as
copies.** The law is about *where the signal points*, not about which channel
carries it.

This work package tests a channel that is **different in kind**. It does not
point at structure at all: it attaches, to structure the model already has, a
label the model has *never had* — what that structure MEASURED in SPICE. The two
hypotheses are registered as equally live:

* **H-INFO — "conditioning works because it adds information."** Outcome bins are
  genuinely new information (no previous arm carried a SPICE result into the
  weights in any form), so a model conditioned on all-bins-MET should place more
  probability on the structures that actually met specs, and **its sized outcomes
  should beat both the shuffled control and unconditioned P5-v7** even if NDL
  does not move.
* **H-LAW — "the novelty law claims a fourth channel."** The conditioned rows are
  re-augmented traversals of topologies the model has largely already seen, which
  is exactly `§28`'s winners channel with extra tokens on the front. If the law is
  about structure rather than about the carrier, the arm should behave like
  `§28`: copy fraction up, NDL down, and **the conditioned samples should be no
  better sized than the shuffled control's**, because the request token is doing
  nothing but selecting memorised graphs.

The experiment is built so that both can be *falsified by the same table*, and a
REJECT with a clean mechanism is a fully successful outcome.

**This is not RL** (Block 9). There is no reward, no advantage, no gradient
through a sampling decision. A SPICE outcome enters as **four tokens in the input
stream** of an ordinary supervised next-token loss — decision-transformer-style
return conditioning, i.e. supervised sequence modelling of (outcome, trajectory)
pairs. The grep in Block 9 stays empty.

---

## 1. The outcome tokens

Sixteen new ids — 4 gated metrics × 4 bins — **appended after the 1005 upstream
ids and after the three P5 class tokens**, mean-initialized exactly the way
`<LNA_NB>` was (`finetune._load_warm`, the same surgery `build_model` already
does off `Pretrain.pth`, lifted one level so it can also extend an
already-fine-tuned checkpoint). The vocab guard's invariant — the upstream 1005
ids untouched — is preserved by construction; vocabulary goes 1008 → **1024**.

```
<S11_VIOL> <S11_MARG> <S11_MET> <S11_UNK>      slot 0: s11_db  | s11_max_db
<S21_VIOL> <S21_MARG> <S21_MET> <S21_UNK>      slot 1: s21_db
<IDD_VIOL> <IDD_MARG> <IDD_MET> <IDD_UNK>      slot 2: idd_ma
<NF_VIOL>  <NF_MARG>  <NF_MET>  <NF_UNK>       slot 3: nf_db
```

A conditioned training row is

```
<LNA_NB> <S11_x> <S21_x> <IDD_x> <NF_x>  VSS … TRUNCATE
```

and an unconditioned row is unchanged: `<LNA_NB> VSS … TRUNCATE`.

### 1.1 Bin definition and the threshold, with its justification

Bins are computed from the **stored L2 `margins` vector** — `datastore.margins_for`
already expresses every constraint as a signed slack normalized by that
constraint's own scale, which is what makes a bin spec-agnostic:

| bin | rule |
|---|---|
| `VIOL` | margin < 0 |
| `MARG` | 0 ≤ margin < **τ = 0.05** |
| `MET`  | margin ≥ **τ = 0.05** |
| `UNK`  | margin is `None` — missing, `unsupported` on that spec, or era-invalid |

**τ = 0.05 is one label-noise unit, not a round number.** `§14.1` measured
σ(S21) = **0.726 dB** under best-of-3 labeling; on a 15 dB gain floor (scale 15)
that is **0.048** in normalized units. So `MARG` means precisely *"meets its
constraint by less than the measurement noise"* — a row the harness cannot
reliably distinguish from a violating one. In natural units τ is 0.5 dB on a
−10 dB S11 target, 0.75 dB on a 15 dB gain floor, 0.125 dB on a 2.5 dB NF cap and
0.25 mA on a 5 mA current cap.

τ is registered before training and is **not** re-tuned afterwards.

---

## 2. Label-domain policy (Block 6 is law) — and what it costs, measured

**Policy, registered: a bin may be drawn only from a row in the CURRENT
measurement era. Everything else contributes no bin at all — not three bins and
an NF `UNK`, but no row.** A row is in-domain iff

```
zoaf_cfg.w_finger == 2e-06     (the multi-finger MOS emission, §27's cutover)
metrics.nf_method == "series_rs"  (the golden-validated NF harness, §13)
```

Two reasons, both measured rather than assumed:

1. **NF.** `§27` moved NF a median of **−2.08 dB store-wide** at the cutover, so a
   pre-cutover `nf_db` is a *different measurement*, not a noisier one. Binning it
   would put a retired harness's verdict into the weights.
2. **S11/S21/Idd.** The same geometry change moves the input match, so the safe
   option in the work package's own words is taken: current-era rows only.

**And the safe option is nearly free, which is the point of measuring it.** The
`relabel_mf` migration re-derived essentially the whole store under the new
geometry: of 1004 pre-cutover `(wl_hash, spec)` keys, **1000 have a current-era
counterpart and only 4 are pre-cutover-only.** The strict policy therefore costs
**4 keys out of 1086** (0.4%), and no separate "relaxed" arm is worth a GPU hour.

`nf_gated` is *not* an extra filter: a row sized under tier-1 gating carries
`nf_db` as `unsupported`, its margin is `None`, and the binning rule already
sends it to `<NF_UNK>`. That is the whole mechanism by which "NF bins may only
come from the series-Rs harness in the current finger era" is enforced — the UNK
bin, not a dropped row.

### 2.1 Row counts after the policy (measured 2026-08-11, before training)

The emission read the store at 11:00 IST and saw **1437 in-domain L2 rows**
collapsing to **1082 distinct `(wl_hash, spec)` keys** over **864 distinct
topologies**. (A re-read 20 minutes later showed 1099 keys: the store is shared
and a concurrent agent is appending to it. The emitted file, not a store query, is
the pinned training set — §3.)

**Keys per bin, after the tie-break of §3:**

| slot | `VIOL` | `MARG` | `MET` | `UNK` |
|---|---|---|---|---|
| **S11** | 835 | 98 | **149** | 0 |
| **S21** | 861 | 45 | **176** | 0 |
| **IDD** | 164 | 88 | **830** | 0 |
| **NF**  | 689 | 23 | **358** | **12** |

The five commonest bin-vectors are `VIOL/VIOL/MET/VIOL` (365),
`VIOL/VIOL/MET/MET` (184), `MET/VIOL/MET/VIOL` (103), `VIOL/VIOL/VIOL/VIOL` (81)
and `VIOL/MET/MET/MET` (36) — i.e. **the store's modal design meets its current
budget and violates everything else**, which is what an honest label distribution
of this program looks like. Keys per spec: wifi24 350, dhruva-s 264, dhruva-l1
210, wideband-sdr 119, dhruva-l5 103, gps-l1 26, dhruva-l2 10.

> **⚠ Registered risk, stated before the result is known: only 9 of 1082 keys are
> all-four-`MET`.** The conditioning prompt this experiment samples from is
> therefore *near the edge of the label distribution* — which is the normal
> decision-transformer regime (one conditions on a return at or above the best in
> the dataset), but it means the arm is being asked to compose, not to recall. The
> four request tokens are individually well-supported (`MET` appears 149 / 176 /
> 830 / 358 times across the slots); their conjunction is rare. **If the arm fails,
> "the all-MET prompt was out of distribution" is a live explanation and will be
> reported as one** — alongside the measured behaviour of the individual slots.

---

## 3. The conditioned channel — how a labeled key becomes training rows

`lna/_out_emit.py`, shaped after `templates.emit_winners` (Loop B's channel) with
the one difference that is the whole experiment: **a row does not get in because
it won, it gets in because it was measured.** VIOLATED keys are as informative to
a conditioned model as MET keys, and dropping them would turn this back into
winners feedback.

**TRUE SPICE numbers only.** Critic scores never select or label training data
(standing rule, `emit_winners` docstring).

**Tie-break when a `(wl_hash, spec)` key has several in-domain rows** (158 keys
do), registered, and computed from the row's own stored margins so that no spec
has to be re-derived — a spec's gating can change between the label and today,
the row cannot:

1. **more labeled slots wins** (a 4-bin row carries strictly more label than a 3-bin one);
2. then **least total violation**, `sum(min(margin, 0))` — the infeasible branch of
   `spec.objective`, sign-flipped;
3. then **best worst-case margin**, `min(margin)`;
4. then **latest `ts`** (deterministic, and prefers the most recently re-derived
   measurement).

**Augmentation.** `templates.augment` — the same upstream
`build_connection_matrix → dfs_all_paths` Eulerian pipeline the corpus, the
archetypes, the externals and `moves.py` all use — at **`max_solutions=4,
run_num=1`**, cached per distinct topology so a topology measured against two
specs reuses its traversals under two different bin prefixes. **The winners
channel uses (10, 2); this channel is capped lower on purpose**, so that
plain-class-token rows remain the *majority* of the training mix: the design
requires the base distribution to be preserved and the conditioning to be strictly
additive, which a channel larger than everything else would not be.

**No oversampling of good rows.** `emit_winners` doubles feasible rows; this
channel does not, so bin frequencies in the mix are the label distribution's.

**The emitted file is the pinned artefact.** `lna/out/outcome_train.json` is
committed and carries every row's `wl`, `spec` and `bins`, so the training set is
reproducible from the repo even though the shared store was being appended to by a
concurrent agent while the emission ran (the emission is a prefix of the store; a
`datastore.snapshot` is pinned alongside for the record).

### 3.1 The control arm — identical in everything but the correspondence

`outcome_train.shuf.json` is written **from the same augmentation pass**, with the
multiset of bin 4-tuples randomly permuted across rows (`random.Random(1337)`).
This preserves per-slot token marginals *and* the joint distribution of bin
vectors exactly; only the label↔topology correspondence is destroyed. It
therefore isolates **"the model uses label semantics"** from **"extra tokens and
extra rows perturbed training."**

---

## 4. Training — P5-v7's stage B with exactly one variable changed

Both arms are **P5-v7's stage B**, warm-started from v7's own stage-A checkpoint
`ft_p5v7.pth` — the identical construction `§29.8`'s P5-v9m used, so the lineage
convention is not being invented here:

```
--arm p5 --do train --device cuda --seed 1337 --epochs 40 --external-corpus
--templates-file lna/out/templates_train.pre_dhruva.json
--winners --winners-file lna/out/winners_train.pre_dhruva.json
--warm-from lna/out/ft_p5v7.pth  --outcome --outcome-file <FILE>  --tag <STEM>
```

| arm | stem | `--outcome-file` |
|---|---|---|
| **OUT-C** (real) | `ft_p5out_v2.pth` | `outcome_train.json` |
| **OUT-S** (shuffled control) | `ft_p5outs_v2.pth` | `outcome_train.shuf.json` |

lr 3e-5, batch 32, 40 epochs, seed 1337, **best-val ships** — v7's hyperparameters
byte for byte. **Conditioned rows go to TRAIN only**, the same discipline
`--external-corpus` uses, so the validation set stays byte-identical at 736 rows
and the early-stop criterion is the baseline's; best-val numbers remain comparable
across the whole P5 line. Private checkpoint stems: **no shared `.pth` is written.**

`finetune.py`'s edits are additive and backward-compatible — new optional
arguments only, every default path byte-identical — because a concurrent work
package imports this file for sampling.

---

## 5. Evaluation

### 5.1 The frozen protocol, unmodified

`novelty.evaluate`, n = **256**, seed **1337**, `ref-v3[198h/d05390da]` — the exact
shape every P5 arm's published row was measured in (`§24.2`, `§28.3`, `§29.8`), so
the numbers are directly comparable to the adopted baseline **nb 79 / wb 41** at
inductor ratio nb 0.230 / wb 0.132. Reported per arm: NDL@256, spec-L0, copy rate
split archetype / corpus / external, median NN-sim, termination, valid, inductor
ratio. A **seed-2338** 256-sample replicate of the primary (nb, conditioned)
channel of both arms bounds sampling noise; it is a replicate, not a redefinition
of the protocol.

Six sampling arms per checkpoint pair:

| # | checkpoint | class | prefix |
|---|---|---|---|
| 1 | OUT-C | nb | `<LNA_NB> <S11_MET> <S21_MET> <IDD_MET> <NF_MET> VSS` |
| 2 | OUT-C | wb | same, `<LNA_WB>` |
| 3 | **OUT-C** | nb | **`<LNA_NB> VSS` — UNCONDITIONED**, the base-distribution-damage control |
| 4 | OUT-C | wb | unconditioned |
| 5-8 | OUT-S | nb/wb | the same four |

Arm 3 answers "did adding the channel damage the base distribution?" directly
against P5-v7's published row, because the prefix is byte-identical to v7's.

### 5.2 The funnel — the question the experiment actually exists to answer

Identical to WP-ATTRIB's (`plans2/10 §1.3`) so the two are readable side by side,
and **fixed across arms**, which is `§29.12`'s rule:

1. **L0** — `wifi24` `spec.structural_screen`.
2. **Novelty** — `novelty.evaluate` vs ref-v3.
3. **Rung-0 selector, FIXED** — {screen-passing} ∩ {novel vs ref-v3} ∩ {WL-deduped}
   ∩ {`_match_struct.analyze` reports `port_src`}. Every arm's qualifying
   candidates go into **one** pool JSON, ranked by **one** critic-v2 GNN ensemble
   (`search.rank_pool`, leak-free: every store row whose `wl_hash` appears in the
   combined pool is dropped before training), and each arm takes its own **top 10**
   by the same `mean - beta*sigma` feasibility scalar. *If an arm has fewer than 10
   qualifying candidates, everything it has is sized and the shortfall is reported
   as a result, not patched.*
4. **Sizing, equal budget** — `size.size_topology(seed=1, inductor_q=12,
   **search.SCAN_BUDGET)` then a box-clamped `size.polish(budget=search.POLISH_BUDGET)`,
   imported rather than restated. Current harness (multi-finger, `inductor_q=12`,
   NF gated per spec). Store recipe **`outcome-v1`**, `provenance.source_arm =
   outcome-<ARM>`.
5. **Report** — one funnel table ending in the program's own currency:
   near-feasible and feasible-novel **per SPICE-minute** (`loop.spice_curve`
   accounting).

**Funnel arms:** `OUT-C` (conditioned all-MET) · `OUT-S` (shuffled control,
conditioned all-MET) · `OUT-U` (OUT-C sampled unconditioned) · **`P5V7`**, the
adopted baseline. The P5-v7 arm reuses **its own published 256-sample pool**
`lna/out/ft_p5v7_nb_s1337` — the pool `§24.2`'s NDL 79 was measured on — rather
than a fresh draw, so the control is literally the published baseline. (If
FINDINGS §31 lands a P5-v7 funnel row under this same selector and budget first,
that row is reported beside this one; the two differ only in the draw, 256@1337
here vs 2x128 there.)

**The conditioning-specific question, stated as a comparison and not as a
threshold:** do all-bins-MET samples from OUT-C achieve measurably better *sized*
outcomes — best violation, near-feasible count, feasible count, and near-feasible
per SPICE-minute — than (a) OUT-S's "conditioned" samples and (b) unconditioned
P5-v7? **That, not NDL, is the point of the experiment.**

---

## 6. Predictions, registered before any arm was trained

1. **NDL@256 falls on the conditioned arms relative to P5-v7's 79.** Both
   hypotheses predict this: the conditioned rows are re-augmented traversals of
   store topologies, i.e. structure the model has largely already seen. **A fall
   in NDL is therefore NOT evidence for H-LAW by itself** — it is what the two
   hypotheses agree on, and the discriminating evidence is entirely in §5.2.
2. **OUT-C's unconditioned arm (arm 3) lands close to P5-v7's published row.** If
   it does not, the channel damaged the base distribution and that cost is
   reported whatever the conditioned arms do.
3. **OUT-C's conditioned pool has a higher `port_src` rate and a higher device
   count than OUT-S's**, because in the store the source-driven, larger designs
   are the ones that met S11 (`§29.3`, `§29.10`). This is the cheapest structural
   signature that the model read the label rather than the token.
4. **Under H-INFO:** OUT-C beats OUT-S by 2x or more on near-feasible per
   SPICE-minute, and OUT-C beats unconditioned P5-v7 on best violation.
5. **Under H-LAW:** OUT-C is indistinguishable from OUT-S on every sized column
   (the request token acts as a plain style token), and both are no better than
   P5-v7.
6. **Zero arms produce a `wifi24` tier-2 feasible design at this budget** — the
   program's entire tier-2 record is two designs.
7. **The qualifying-pool shortfall binds on at least one arm.** WP-ATTRIB measured
   P5-v7 at **9** qualifying candidates from 256 samples under this selector, so
   k = 10 is at the edge for every arm here.

---

## 7. Decision rule, registered before any arm was trained

**Checkpoint adoption** is `loop.py`'s unchanged **adopt-only-if-better**: a
candidate replaces P5-v7 only if it beats the frozen NDL@256 (nb 79 / wb 41) at
equal-or-better inductor ratio with every tripwire quiet. Ties go to the
incumbent. Prediction 1 says this will almost certainly **REJECT**, and that is
fine: *the checkpoint is not the deliverable.*

**The scientific verdict is separate, and it is what §32 reports:**

* **H-INFO wins** if OUT-C beats OUT-S on the sized comparison (near-feasible per
  SPICE-minute as the headline, best violation and feasible count beside it) by a
  margin larger than the shortfall/rounding noise the funnel can produce — and the
  structural signature of prediction 3 points the same way.
* **H-LAW wins** if OUT-C and OUT-S are indistinguishable on the sized comparison.
  Then outcome conditioning is the **fourth** channel obeying `§29.12`, and the law
  generalises from "steering toward memorised structure" to "any signal that
  reweights memorised structure" — a strictly stronger and more useful statement
  than the three-channel version.
* **Neither wins outright** if OUT-C beats OUT-S but both collapse below P5-v7 —
  reported as "the label is read but the channel is not worth its cost."

Every column of the funnel table is published regardless of which way it falls,
including any column where the shuffled control beats the real arm.

---

## 8. Scope and method discipline

**In scope:** `lna/_out_tokens.py`, `lna/_out_emit.py`, `lna/_out_pool.py`,
`lna/_out_size.py`, `lna/_out_train.sh` / `_out_launch.sh`, additive flags in
`lna/finetune.py`, `lna/out/outcome_train*.json`, this plan, FINDINGS §32, a
JOURNEY stage, a Block-3 note in `STRUCTURE_LOGIC.md`, and append-only store rows
under recipe **`outcome-v1`**.

**Out of scope / untouched:** every frozen protocol (NDL@256, ref-v3, the
snapshots, the specs, the screen) — the arms are *measured under* it, they do not
modify it — plus `lna/grammar_gen.py`, `lna/surrogate.py`, `lna/critic_gnn.py`,
`lna/extract.py`, `lna/size.py` and `lna/_attrib_*.py`, all owned by concurrent
agents or by the frozen core.

**Regression quartet(+) green before and after** (`HANDOVER-EXEC` §4/§8). The
vocab guard matters doubly here: it asserts the **upstream 1005 ids are
untouched**, and the 16 new tokens append after them, the same pattern `<LNA_NB>`
established.

**Blind protocol** holds throughout: no consultation of the excluded paper's
circuit content.

**GPU etiquette:** `nvidia-smi` is checked before every fine-tune; a training run
is never started on a busy 4 GB card, because an OOM kills both agents' work.

**Store note (expected):** `lna/data/topo_labels.jsonl` and `snapshots.json` are
shared and carry uncommitted rows from concurrent agents; committing them commits
those too, which is established practice and is stated in the commit message.

---

## 9. The emission, as it actually ran (appended before training; nothing below was tuned)

`python lna/_out_emit.py --out lna/out/outcome_train.json`, 18.2 min wall.

| quantity | value |
|---|---|
| in-domain L2 rows read | **1437** |
| distinct `(wl_hash, spec)` keys | **1082** (864 distinct topologies) |
| keys with several in-domain rows (tie-break exercised) | 158 |
| keys that produced training rows | **1029** |
| keys dropped — no Eulerian augmentation | 53 (38 topologies where `topo_to_netlist` cannot rebuild a complete device) |
| **conditioned rows emitted** | **4072** (mean 3.96 per key) |
| by class | nb **3598** · wb **474** |
| all-four-`MET` keys | **9** |

**Per-slot bin counts over the 4072 emitted ROWS** (these, not the key counts, are
what the model sees):

| slot | `VIOL` | `MARG` | `MET` | `UNK` |
|---|---|---|---|---|
| S11 | 3151 | 380 | 541 | 0 |
| S21 | 3198 | 180 | 694 | 0 |
| IDD | 618 | 342 | 3112 | 0 |
| NF | 2528 | 92 | 1408 | 44 |

**Control verified mechanically, not asserted:** the shuffled file has the
*identical* row order and *identical* token sequences, an *identical* multiset of
bin 4-tuples (checked as a `Counter` equality), and **84.18%** of rows carry a
different vector than they did in the real file. So per-slot marginals, the joint
bin-vector distribution and the topology stream are all conserved; only the
correspondence is destroyed.

**One recorded cost of the prefix.** `finetune.PAD_L` is 128 (a 4 GB-card
constraint that predates this work package), and conditioned sequences have a
median length of 107 tokens with a long tail (p90 177, max 337). Prefixing 5
tokens takes the share of conditioned rows whose content is truncated at 128 from
**34.9% → 37.7%**. This is the same truncation every long corpus/template row has
always taken; it is stated because it applies slightly more often to this channel,
and it applies **identically to both arms**.

**Mix arithmetic.** v7's stage B is 8288 train / 736 val rows (`§24.1`). Adding
4072 conditioned rows before the 15% `<OTHER>` replay gives roughly 13.1k train
rows, of which the conditioned channel is about **31%** — a minority, as §3
requires. The validation set is untouched at 736.

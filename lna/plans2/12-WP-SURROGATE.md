# WP-SURROGATE — a point-level simulator surrogate (v0)

**Status:** PRE-REGISTERED (this file written and committed *before* any model is
trained). **Owner:** the WP-SURROGATE executor session, 2026-08-11, branch
`lna-data`. **Files owned:** `lna/surrogate.py`, `lna/_surr_eval.py`, this file.
**Files explicitly NOT touched:** `lna/extract.py`, `lna/size.py`,
`lna/critic_gnn.py` (a concurrent WP-OBSERVE agent owns `extract.py` this wave;
`critic_gnn.py` is shared and is *imported*, never edited).

---

## 0. What this is, and why it is not the critic

Block 7's critic answers **"is this *topology* worth a 5-minute sizing run?"** —
one prediction per (topology, spec), trained on L2 rows, target = post-sizing
margins.

WP-SURROGATE answers a different, strictly *inner*, question:

> **f(topology graph, parameter vector x) -> metric vector** — "what would ngspice
> say about *this point* of *this* device box?"

That is one prediction per **ngspice call**, not per sizing run. Its training set
is `lna/data/sim_points.jsonl` — 66,664 rows, the free byproduct of every ZOAF
sizing run since the store went live (`size._log_l2` appends `ds.row_point` for
each evaluated `x`), gitignored, and **never used for learning until now**.

The payoff, if it works, is not another ranker: it is a **pre-gate inside the
sizing loop**. ZOAF spends 150-250 ngspice calls per topology; if a surrogate can
recognise that a candidate point is clearly worse than the run's incumbent best,
that call never happens. The unit of the result is therefore **SPICE-minutes
saved per design**, measured offline against runs that already happened, with
zero new simulation.

---

## 1. The data, and the join (Step 1)

### 1.1 What a point row carries

```json
{"kind":"point","spec":"wifi24","wl_hash":"...","x":[...],
 "metrics":{"idd_ma","nf_db","s11_db","s11_max_db","s21_db","s21_min_db","s21_ripple_db"}}
```

No tokens, no param names, no recipe stamp. Everything else must be recovered.

### 1.2 The join, and why it is self-validating

1. **Segment by append order.** `size._log_l2` writes a run's point rows in one
   contiguous `ds.append_all` burst, so a maximal run of equal `wl_hash` in file
   order is exactly one ZOAF sizing run. -> **336 blocks**.
2. **Attach the L2 row.** For each block, find the `topo_labels` row with the same
   `wl_hash`, `spec == "wifi24"`, and `n_evals == len(block)`. The `n_evals` test
   is what disambiguates a topology that was sized more than once (repeat probes,
   `+bo3` relabels, `+mf2-v1` relabels): the point block belongs to the run whose
   eval count it matches.
3. **Rebuild the topology** from that row's `graph.tokens` (`Topology(tokens)`,
   the pattern `_nf_gate_d3.py` uses).
4. **Rebuild the parameter map with `size.py`'s own machinery** — never by
   guesswork: `size.prepared_body(topo, inductor_q=12, w_finger=None)` ->
   `size.classify_params` -> `sizable` (ordered `sorted(devices)` then the
   inserted `pVBG*`), and `size.kind_ranges(spec)` for the per-kind log/linear
   map. For `curated-v1` runs `size.match_devices` identifies the input-match
   passives that `size._curate` moved from *sizable* to *fixed*; their frozen
   values are read back out of the row's own `best_params`.
5. **Prove the map, per block, before using it.** Decode the L2 row's stored
   `best_x` through the reconstructed map and require it to equal the row's
   stored `best_params` **exactly, string for string**. A block that fails is
   dropped, not guessed at.

**Measured before pre-registration** (this is Step 1's audit, not a result of the
model): **333 of 336 blocks decode byte-exactly** — 329 `candidate-v1` + 4
`curated-v1`. The three that do not are the token-less reference decks: one
`ref24_csdeg` anchor block written with `wl_hash = null` (304 rows) and the
`ref24_tapped` / `ref24_cg` blocks whose L2 rows carry `wl_hash` of the form
`ref:<deck>.cir` and no tokens.

### 1.3 The replay validation (the fence)

Eight joined rows, spanning eight topologies and drawn from the interior of their
runs (not the argmin), were replayed: rebuild topology -> decode x -> one ngspice
evaluation -> compare to the stored metrics. **All eight reproduce every stored
metric to 0.0000** under `w_finger=None` (the historical single-finger emission
`to_spice` still supports, FINDINGS 27.1). The same rows replayed through today's
default multi-finger deck move by up to **+10.09 dB on S21** and **+1.68 dB on
S11**.

The join is therefore not "consistent within label noise" — it is **bit-exact**,
which is the strongest fence available and the reason this WP proceeds.

### 1.4 The era, stated plainly

Every point-generating run in this file is dated **2026-08-06/07**, recipe
`candidate-v1` / `curated-v1`, `inductor_q=12`, `nf_gated=false`. That is:

* **pre multi-finger** (`mf2-v1` cutover 2026-08-10, FINDINGS 27) — single-finger
  MOS;
* **pre series-Rs NF** (`nfrs-v1`, 2026-08-08, FINDINGS 13) — so the `nf_db`
  column is the **retired port-referred NF** (finding #7), the one that
  "flattered every design without exception" and can read negative (min in this
  file: **-18.94 dB**);
* **pre stability harness** — no `k_min` in the metric dict;
* single spec: **`wifi24` only**, all 66,664 rows.

**Consequences, binding on everything downstream:**

* v0 is a **proof of mechanism**, not a production surrogate. The
  response-surface-learning question ("can a graph net interpolate ngspice over a
  device box?") is era-independent, so it is answerable here; the *numbers* are
  only valid for the single-finger, port-NF, wifi24 domain.
* The `nf_db` head is trained and reported as **nf_db(port, RETIRED)** and is
  **never** to be pooled with, compared to, or substituted for a `series_rs` NF.
  It is kept only because it is a real deterministic function of the same deck
  and therefore a fair fourth response surface to learn.
* A production surrogate needs **post-cutover** points. They will accumulate from
  the concurrent logging work package; retraining on them is v1, not v0.

---

## 2. The model (Step 2)

`lna/surrogate.py`. Encoder = **the critic's bipartite device/net message-passing
trunk**, imported from `critic_gnn` (`graph_tensors`, `DEV_TYPES`, `ROLES`; plain
torch, no PyG, dense per-role adjacency matmuls) — imported, not copied, and not
edited.

### 2.1 Variable parameter length — the design decision

`len(x)` is per-topology (2...14 in this store, median 8). Two candidate
treatments were named in the brief; a third is what the *structure* of the
problem asks for and is what v0 uses as its main arm:

* **`concat`** (the literal baseline) — pad x to the global max dim with a mask,
  concatenate at the readout alongside the spec vector.
* **`node`** (main arm) — **inject each parameter into the device node it belongs
  to.** The map is exact and already known: `p<dev>W` is device `<dev>`'s width,
  `p<dev>V` is passive `<dev>`'s value, and `pVBG<k>` is the gate bias of the MOS
  devices listed in that bias net's device list. Every device therefore gets two
  extra input features — its own normalized coordinate, and the normalized
  gate-bias coordinate of the bias net driving it (0 + a flag if none). Variable
  length is then not a problem to be padded around: it is *dissolved*, because
  the parameter vector is carried by the graph that already varies in size, and
  the encoder is permutation-equivariant over devices by construction.
* **`film`** — `node`, plus FiLM (per-round scale/shift on device hidden states)
  computed from a pooled parameter summary, to test whether the parameters need
  to modulate *message passing* and not just the input embedding.

Coordinates for **fixed** parameters (curated match passives) are recovered by
inverting `kind_ranges`, so a curated run's frozen Lg/Ls/Cin/Cex are visible to
the model exactly like a free one's — the representation describes the *circuit*,
not the optimizer's variable set.

All three arms are trained; `concat` vs `node` vs `film` is the A/B.

### 2.2 Heads and targets

Seven heads, one per stored metric, on robust-clipped native units (clipping
pre-registered here, chosen from the *training-domain* histogram, never from a
result): `s11_db`, `s11_max_db` -> [-45, +25]; `s21_db`, `s21_min_db` -> [-60,
+40]; `s21_ripple_db` -> [0, 15]; `idd_ma` -> `log10` then [-6, 3.5];
nf_db(port) -> [-25, 60]. Targets are z-scored with train-split statistics;
loss = Huber on the z-scores. Accuracy is always reported back in **native
units**.

Clipping is safe for the downstream gate: a -600 dB S21 clipped to -60 dB still
produces an objective of ~7 against an incumbent of ~2, i.e. still trivially
skippable.

### 2.3 Splits — family, never row

`datastore.family_split` (single-linkage WL-cosine >= 0.9), applied to the **310
unique joined topologies**, assigning whole families to train/val/test. Measured
structure: **301 families, 296 of them singletons** — at this threshold a family
is essentially a topology, so cross-family really is cross-topology. Split sizes:
**216 / 49 / 45** topologies.

A row-level split is forbidden (Block 6): a ZOAF run's points are dense and
locally clustered, so a random row split would put a point's near neighbour in
train and leak the answer outright.

Three evaluation strata, in increasing difficulty:

1. **within-family (interpolation).** 15% of the *points* of **train-family**
   runs are withheld from fitting. This is the warm-start deployment: the
   topology has already been partly explored and the surrogate must interpolate
   its own device box. **This is the "at or under label noise is a win" number.**
2. **held-out run.** Whole runs withheld whose *family* is in train (only the
   handful of non-singleton families support this) — reported if n is large
   enough to mean anything, otherwise reported as thin and not leaned on.
3. **cross-family (cold start).** The 45 test-family topologies, every point.
   Nothing about these graphs was ever seen.

### 2.4 sigma floor — and an honesty note about what it is

The brief's floor is **sigma(S21) = 0.726 dB** (best-of-3) / **1.478 dB**
(single-seed), from FINDINGS 14.1. Those are the noise of a **sizing-run
outcome** across seeds — *not* the noise of a single ngspice evaluation. Section
1.3 just measured the latter directly and it is **0.0000 dB**: the point-level
label is deterministic.

So the sigma floor is not a label-noise floor for this task. It is still the
right yardstick, for a different and defensible reason: **a surrogate whose
point-level error is below the sizer's own seed-to-seed spread cannot change a
sizing decision by more than the sizer already changes it by itself.** That is
the sense in which "at or under sigma" is a win here, and it is the sense used
below.

### 2.5 Training

torch CPU (`analoggenie`, 2.0.1) or WSL GPU (`/opt/miniconda/envs/gpu`,
2.13+cu130, RTX 3050) — whichever is used will be stated in the writeup. Only
**310 distinct graphs** exist, so graph tensors are precomputed once into a bank
and indexed per row; the per-row cost is the parameter vector alone. Code is
written to run under py3.8 / 3.10 / 3.14 unchanged (the three-environment rule,
HANDOVER-EXEC section 3).

---

## 3. The offline ZOAF-replay gate (Step 3) — ZERO new SPICE

The headline experiment. Each joined block **is** a ZOAF run, in the order
ngspice actually saw it. Replay it, and ask what would have happened if a
surrogate had been allowed to veto evaluations.

### 3.1 The rule (pre-registered, fixed before any number is seen)

Per run, in append order, with `spec.objective` computed under the era's gating
(`nf_gate=False`: S11/S21/Idd hard, NF `unsupported`) — **always from predicted
metrics, never a directly-regressed objective** (the program's standing rule that
feasibility is computed, not trained):

```
warm-up: the first K = 8 points are ALWAYS simulated (an incumbent must exist)
f*      : min objective over the points actually simulated so far
for each later point i:
    f_hat = spec.objective(surrogate(topo, x_i))
    if f_hat > f* + Delta:  SKIP  (no ngspice call; cannot become the incumbent)
    else:                   SIMULATE (true metrics; may update f*)
```

* **Primary margin Delta = 0.5** objective units. Context for the choice, from
  the training-domain histogram only: the point-objective median is 4.00, p25
  2.96, p10 2.41, and a feasible point scores < 0 — so 0.5 is well inside the
  bulk and is not a no-op, while being about the width of one normalized
  constraint quarter.
* **Warm-up K = 8.**
* **Secondary sweep, also pre-registered:** Delta in {0.0, 0.1, 0.25, 0.5, 1.0,
  2.0, 5.0} reported as a full trade-off curve, so the primary number cannot be
  mistaken for a tuned one.
* **Two calibration arms:** `raw` (predictions as-is) and `cal` (after warm-up, a
  per-metric **median residual** measured on that run's own simulated points is
  added to subsequent predictions — three scalars, no retraining; the cheapest
  possible online adaptation, and the one a real deployment would obviously use).

### 3.2 What is reported

For the **cross-family (cold-start)** stratum, which is the honest deployment
(a new topology arrives and the surrogate has never seen its family):

* **% of ngspice calls skipped**;
* **# runs whose final argmin point changed** — the correctness cost. The
  headline the brief asks for is **the % skipped among runs where the argmin is
  preserved exactly**, together with what fraction of runs that is;
* the objective degradation (mean / worst) on runs that *did* change;
* the same on train families as an optimistic upper bound.

---

## 4. Predictions (registered; no results seen)

| # | prediction | rationale |
|---|---|---|
| **P1** | **within-family rho(S21) > 0.9** (the brief's hypothesis) — point estimate **0.97** | ~200 points per topology sample a smooth 6-14-dimensional box; interpolation is the easy direction |
| **P2** | **within-family MAE(S21) <= 0.726 dB** (the best-of-3 sigma) — point estimate 0.5-1.5 dB; P2 is expected to be **the harder half of P1**, because rho is inflated by the -600 dB tail while MAE is not | correlation over a 100 dB range is cheap; absolute accuracy is not |
| **P3** | **cross-family is coverage-limited, exactly like the critic's off-distribution decay** (FINDINGS 15.4: rho 0.83 -> 0.17-0.20): rho(S21) lands in **0.30-0.65**, i.e. real signal, far below within-family | 296 singleton families = the model must extrapolate to an unseen graph every time |
| **P4** | **`node` beats `concat` on cross-family rho(S21) by >= 0.05** | `concat` cannot tell *which* device a width belongs to once the graph changes; `node` can |
| **P5** | **`film` about equals `node`** (within +-0.03) — the parameters are already at the right place; modulating messages adds little | |
| **P6** | **>= 60% of ngspice calls are skippable at zero argmin change**, cross-family, `cal` arm, Delta = 0.5 | most ZOAF points are far from the incumbent; the gate only has to recognise "obviously bad" |
| **P7** | `raw` cold-start will be materially worse than `cal` — a per-run offset is worth more than a better graph encoder here | |
| **P8** | **Idd is the easiest head** (a DC quantity, nearly a function of the widths alone) and **s21_ripple_db the hardest** (a difference of two large numbers) | |

**Falsification:** if the within-family rho(S21) is below 0.9, or if the join
fence in section 1.3 had failed, the WP reports a negative result and trains
nothing further. The gate result is reported whatever it is, including 0%.

---

## 5. Method discipline

* Append-only store; **no** frozen protocol touched; no new rows written to
  `topo_labels` / `l1_labels`.
* Label domains: this WP restricts to a *single* domain (`wifi24`,
  `candidate-v1`/`curated-v1`, `nf_gated=false`, single-finger, port-NF) rather
  than conditioning on one — nothing is pooled across the multi-finger or
  series-Rs boundaries, because nothing on the other side of them exists in this
  table yet.
* Blind protocol: no consultation of the target paper's circuit content.
* Concurrency: commits name their files explicitly; never `git add -A`.
* Documentation on wrap-up: `FINDINGS.md` **section 33**, a `JOURNEY.md` stage,
  and a `STRUCTURE_LOGIC.md` block covering what the surrogate is trained on,
  what it is **not** valid for (the era caveat above), and the replay-gate
  number.

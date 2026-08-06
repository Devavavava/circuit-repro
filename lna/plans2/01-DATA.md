# WP-DATA — label store, logging hooks, labeling campaign

**Answers:** brief Stage 1 "train on existing simulation results plus newly
generated data" — this WP *is* that sentence, made concrete.
**Deliverables:** `lna/datastore.py`, logging hooks in `size.py`/`bias.py`,
`lna/campaign.py` (nightly labeling runner), backfilled store, 3 nights of
unattended campaign output.
**Cost:** 3–4 days build + nightly compute thereafter. **Depends on:** P5
templates + gain-capable archetypes (05-SCHEDULE Stage 0) for stratum T.
**Blocks:** everything — 02-CRITIC trains on this store.

The premise to internalize: **from now on, every ngspice invocation is
training data.** The pipeline has been throwing away its most expensive
byproduct.

---

## 1. What a label is

* **L2 label** (expensive, the prize): one `(topology, spec)` → outcome of a
  fixed-budget ZOAF sizing run. Per metric m: achieved value and normalized
  margin `(achieved_m − required_m)/scale_m` (scales from 05-SIZING's
  objective), plus feasible flag, eval count, best param vector, and the
  winning L1 op block. ~230–300 sims ≈ 4–5 min each.
* **L1 label** (cheap, abundant): one topology → `bias.py` sweep outcome:
  best grid point, per-device {Id, gm, Vds, Vdsat}, conducting / saturated
  device counts. ~1 s.
* **Point row** (free byproduct): every single ngspice eval inside ZOAF —
  `(topology, param vector x, metrics)`. ~250 rows per L2 label. Not used by
  the v1 critic; logged anyway because it is free now and unrecoverable
  later (v2 sizing-aware critic, ZOAF warm starts, encoder pretraining).

## 2. The store (`lna/datastore.py`)

Append-only JSONL, no new dependencies (py 3.14 stack):

```
lna/data/topo_labels.jsonl   L2 rows      — IN GIT (small, precious)
lna/data/l1_labels.jsonl     L1 rows      — in git while < ~20 MB
lna/data/sim_points.jsonl    point rows   — gitignored (bulky, regenerable-ish)
lna/data/snapshots.json      named snapshots: {name: {file: line_count, sha256}}
```

Row essentials (L2): `wl_hash`, `spec`, provenance (`source_arm`, seed, token
file path or template id), graph summary (device/type counts, inductor ratio),
margins + achieved per metric, `feasible`, `n_evals`, `best_x`, `zoaf_cfg`,
`git_sha`, `ts`. Key = `(wl_hash, spec)` — **never label the same key twice**
except designated repeat-probes (§5).

API: `append(table, row)`, `load(table, snapshot=None)`,
`family_split(k_holdout)` — the split assigns whole WL-hash families (hash
clusters at NN-similarity ≥ 0.9 over the corpus + templates + labeled set) to
train/val/test. **All consumers use this split function; nobody rolls their
own.** Near-duplicates are everywhere in this data (median NN-sim 1.000 in
P1/P2 arms) and a row-level random split would leak catastrophically.

Snapshots: `datastore.snapshot("v1-train")` pins line counts + hashes; every
critic version records which snapshot it trained on (00-OVERVIEW rule 4).

## 3. Logging hooks (the only pipeline touches, all additive)

* `size.py`: after every `--anchor`/`--scoreboard` sizing run, append the L2
  row + stream point rows from the objective wrapper. `--no-log` opt-out for
  throwaway experiments. The row is assembled from values `size.py` already
  computes — this is bookkeeping, not new measurement.
* `bias.py`: `--sweep`/`--validate` append L1 rows.
* Regression quartet must stay green after both hooks (they are additive;
  if a hook changes any measured number, the hook is wrong).

## 4. Backfill (day 1 of the campaign, ~half a day of compute)

1. **41 corpus LNAs:** L1 rows via `bias.py --validate` path; L2 rows vs
   `wifi24` for the in-scope single-ended class (~34 × 5 min ≈ 3 h, one
   evening). These are the highest-quality graphs available — real designs.
2. **Reference anchors:** re-run `size.py --anchor` with logging on (~5 min)
   → the stage-B row + 300 point rows. Same for the CG under `wideband-sdr`.
3. **The §5b scoreboard trio:** re-run `size.py --scoreboard` on the P2 arm
   (logs the 0/3-feasible rows — negative labels are labels).
4. **Every arm dir in `lna/out/`:** L0 screen + L1 rows for all spec-passing
   samples (cheap mass pass, ~1 s each). This immediately gives the L1 head
   thousands of rows.

## 5. The nightly campaign (`lna/campaign.py`)

Target: **400–800 L2 rows by end of Stage 1.** ~60/night at 4–5 jobs
(ngspice is single-threaded; the box has 8 threads; leave 2 free).

Stratified quota per night (adjust by morning report, keep ratios):

| stratum | n/night | why |
|---|---|---|
| **T** — templates (P5), NB+WB, *including gain-capable buffered/matched archetypes* | ~20 | topology diversity + the feasible class exists at all |
| **G** — generated (P1/P2 arms), L0+L1-passing, WL-dedup vs store | ~20 | the distribution search will actually draw from |
| **M** — mutations: 1-edit graph variants of already-labeled topologies (03-SEARCH §3's move set) | ~10 | local contrast — exactly what a search-guiding ranker must get right |
| **R** — repeat-probes: re-size ~3 already-labeled keys | ~10/wk | measures label noise σ (ZOAF is stochastic); σ is the model's accuracy floor and sets the rank-loss margin |

Specs: primary `wifi24`; `wideband-sdr` for inductorless/wideband-classed
topologies (spec-appropriate labeling beats blanket double-labeling; a
`(topo, spec)` row costs 5 min either way).

`campaign.py --night` picks the quota, runs jobs in parallel, appends rows,
and writes `lna/data/reports/YYYY-MM-DD.md`: counts per stratum, feasible
rate, new families seen, failures classified. `--dry-run` prints the pick.
Launch from PowerShell as a background job; it must survive unattended.

**Fixed label budget:** one ZOAF config for all campaign labels (the anchor
recipe: same n_starts/iters). Labels are only comparable at equal budget; if
the budget ever changes, that is a new label version, tagged in `zoaf_cfg`.

## 6. Acceptance

- [ ] store + hooks land; regression quartet green; hooks alter no measured number
- [ ] backfill complete: ≥ 30 corpus L2 rows, anchors logged, every `out/` arm L0/L1-passed
- [ ] campaign runs **3 consecutive nights unattended**, morning reports written
- [ ] repeat-probe σ measured and written into the report header (expect σ(S21) ≲ 0.5 dB; if σ is huge, the label budget is too small — fix before training on lies)
- [ ] ≥ 150 L2 rows total before 02-CRITIC training starts (≥ 25% from stratum T)

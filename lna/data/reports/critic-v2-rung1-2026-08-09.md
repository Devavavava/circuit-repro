# Critic v2 retrain + the live rung-1 rerank (Session 6, 2026-08-09)

Raw run record for FINDINGS §17. Two pieces of work:

1. **Critic v2** — retrain every arm on snapshot `v5-train` (1010 L2 rows / 1006
   token-bearing), evaluated under the restated Gate C1 (§14.6) on the
   family-holdout and source-shift splits, plus a leak-free post-hoc score of the
   evolution run's 213 mutant rows (§15.4's collapse measurement, redone).
2. **Rung 1, live** — plans2/03-SEARCH §1 run for the first time on real SPICE:
   critic-v2 rerank of a fresh `dhruva-s` candidate pool vs an equal-budget
   random control drawn from the identical pool.

Every number below is SPICE except the blocks explicitly marked *critic*.

## Snapshot

```
python lna/datastore.py --snapshot v5-train
# v5-train: topo_labels=1010 lines
#   sha256 cc2f79aea12a18db7febf90ed8358076a22d7bbf7c9bc057a57e4fd4ae669f57
#   l1_labels=41 (unchanged since v1-train)
```

Specs in the snapshot: wifi24 471, dhruva-l1 249, dhruva-s 132, wideband-sdr 121,
gps-l1 23, dhruva-l5 7, dhruva-l2 7. (v4-train was 734 rows with wideband-sdr 16
and dhruva-s 24 — the two search specs went 40 → 253 rows, all 213 of the increase
from the rung-2 evolution run.) σ(S21) = **0.783 dB** at recipe `candidate-v1+bo3`
(0.726 dB at v4-train).

## Reproduce

```bash
# 1. baselines (torch-free)
python lna/critic.py --eval --snapshot v5-train --sigma-recipe candidate-v1+bo3
# 2. GNN ensemble, both splits
"C:/Users/Devavrat/radioconda/envs/analoggenie/python.exe" lna/critic_gnn.py \
    --eval --snapshot v5-train --sigma-recipe candidate-v1+bo3
# 3. off-distribution (mutant) post-hoc, leak-free by family CV
"C:/.../analoggenie/python.exe" lna/critic_gnn.py --mutant-eval \
    --snapshot v5-train --sigma-recipe candidate-v1+bo3 --folds 3 --n-models 5
# 4. live rung 1
python lna/search.py --pool lna/out/ft_p5v2_nb_s1337.v3 --spec dhruva-s \
    --out lna/out/_rung1_pool.json
"C:/.../analoggenie/python.exe" lna/search.py --rank \
    --pool-json lna/out/_rung1_pool.json --snapshot v5-train \
    --out lna/out/_rung1_rank.json
python lna/search.py --size --rank-json lna/out/_rung1_rank.json --k 30 \
    --seed 1337 --shard 0/2 --out lna/out/_rung1_sized_a.json     # + shard 1/2
python lna/search.py --s1 --rank-json lna/out/_rung1_rank.json --k 30 --seed 1337 \
    --sized-json lna/out/_rung1_sized_a.json lna/out/_rung1_sized_b.json
```

---

## 1. Critic v2 on the frozen splits

Gate C1 as restated (§14.6): ρ(S21) ≥ 0.5 **and** skill ≥ 0.25, where
skill = (prec@20% − base)/(ceiling prec − base).

### family-holdout split — v5-train, n=123 test (base 0.496, k=25, ceiling prec 1.000)

```
model      rho_S11  rho_S21  rho_Idd   rho_NF  rankacc  prec@20  enrich  skill   C1?
trivial        nan      nan      nan      nan    0.000    0.496    1.00  0.000    no
wl_knn       0.341    0.696    0.319    0.641    0.787    0.800    1.61  0.603   YES
ridge        0.379    0.775    0.457    0.634    0.805    0.680    1.37  0.365   YES
gnn(ens5)    0.528    0.828    0.610    0.580    0.833    0.840    1.69  0.683   YES   unc_cal 0.651
```

within-spec ρ(S21): dhruva-l1 n=29 → knn 0.419 / ridge 0.695 / **gnn 0.735**;
wifi24 n=76 → knn 0.729 / ridge 0.799 / **gnn 0.869**.
⚠ the family holdout drew only 8 dhruva-s and 7 wideband-sdr rows — it cannot
speak for the two search specs, which is what §2 below is for.

### source-shift split (corpus+ref+templates → generated) — n=477 test (base 0.461, k=95, ceiling 1.000)

```
model      rho_S11  rho_S21  rho_Idd   rho_NF  rankacc  prec@20  enrich  skill   C1?
trivial        nan      nan      nan      nan    0.000    0.461    1.00  0.000    no
wl_knn       0.347    0.384    0.274    0.421    0.639    0.537    1.16  0.140    no
ridge        0.629    0.631    0.341    0.450    0.727    0.705    1.53  0.453   YES
gnn(ens5)    0.570    0.586    0.451    0.407    0.727    0.684    1.48  0.414   YES   unc_cal 0.578
```

within-spec ρ(S21): dhruva-l1 n=210 → knn 0.000 / **ridge 0.745** / gnn 0.733;
wifi24 n=264 → knn 0.512 / **ridge 0.526** / gnn 0.486.

### v1 (v4-train) → v2 (v5-train), same gate

| split | arm | ρ(S21) v1 → v2 | prec@20 v1 → v2 | skill v1 → v2 | C1 |
|---|---|---|---|---|---|
| family | WL-kNN | 0.687 → 0.696 | 0.842 → 0.800 | 0.687 → 0.603 | YES → YES |
| | ridge | 0.790 → 0.775 | 0.737 → 0.680 | 0.479 → 0.365 | YES → YES |
| | **GNN ens-5** | 0.839 → **0.828** | 0.895 → 0.840 | 0.792 → **0.683** | YES → **YES** |
| source-shift | WL-kNN | 0.370 → 0.384 | 0.512 → 0.537 | 0.105 → 0.140 | no → no |
| | ridge | 0.585 → **0.631** | 0.655 → 0.705 | 0.367 → **0.453** | YES → YES |
| | **GNN ens-5** | 0.610 → 0.586 | 0.655 → 0.684 | 0.367 → **0.414** | YES → **YES** |

Both splits are ~15% larger at v5-train (95→123, 420→477 test rows), so the
columns are comparable in kind but not on identical row sets.

⚠ **Plumbing note.** `critic.is_generated` keys off `provenance.token_file`, and
the 213 evolve rows carry none (they are graph edits, not sampler output). So all
213 sit on the **train** side of the source-shift split, and neither frozen split
tests the mutant distribution. That is not a bug — it is why the collapse §15.4
found was invisible to `--eval` in the first place, and why §2 exists.

---

## 2. The off-distribution (mutant) post-hoc — does coverage fix the collapse?

213 evolve rows in **171 WL families**; groups dhruva-s/evolve-evolve 48,
dhruva-s/evolve-random 60, wideband-sdr/evolve-evolve 42, wideband-sdr/evolve-random 63.
Non-evolve pool = 793 rows, holding **wideband-sdr 16 / dhruva-s 24** — i.e. exactly
critic v1's coverage on the two search specs.

Three regimes, same test rows, same protocol (family split → 5-model ensemble,
early-stop on val, untouched test families for the σ-gate p90):

* **v1-equiv** — train on every non-evolve row. Reproduces v1's coverage.
* **v2-cv** — 3-fold over the evolve **families**; each row scored by an ensemble
  that never saw its family. This is the honest v2 number.
* **v2-leaky** — train on everything, score the same rows. Upper bound, quoted as
  leakage, never as a result.

`evolve-random` is the selection-free arm (drawn at random, critic never saw it);
`evolve-evolve` is the elites the critic itself picked, range-restricted by
construction.

```
=== v1-equiv: in-distribution holdout rho(S21)=0.819, unc_cal=0.583, gate p90=0.2922
spec           arm               n  rho_S21   rho_fs rho_cons  unc_cal  sig_med   base  prec20   skill  gated
dhruva-s       evolve-evolve    48    0.383    0.027    0.061    0.117   0.1171  0.875   0.900   0.200   0/48
dhruva-s       evolve-random    60    0.274    0.173    0.218    0.337   0.1635  0.467   0.417  -0.094   7/60
wideband-sdr   evolve-evolve    42   -0.113   -0.224   -0.301    0.055   0.1191  0.143   0.125  -0.029   0/42
wideband-sdr   evolve-random    63    0.407    0.198    0.195    0.099   0.2061  0.143   0.231   0.160  15/63

=== v2-cv:    in-distribution holdout rho(S21)=0.814, unc_cal=0.507, gate p90=0.3077
spec           arm               n  rho_S21   rho_fs rho_cons  unc_cal  sig_med   base  prec20   skill  gated
dhruva-s       evolve-evolve    48    0.747    0.641    0.599    0.148   0.1049  0.875   1.000   1.000   0/48
dhruva-s       evolve-random    60    0.291    0.441    0.462    0.414   0.1358  0.467   0.667   0.375   2/60
wideband-sdr   evolve-evolve    42    0.479    0.479    0.506    0.363   0.1025  0.143   0.000  -0.235   0/42
wideband-sdr   evolve-random    63    0.540    0.502    0.493    0.146   0.1649  0.143   0.308   0.300   6/63

=== v2-leaky: in-distribution holdout rho(S21)=0.823, unc_cal=0.507, gate p90=0.2709   [LEAKAGE - not a result]
spec           arm               n  rho_S21   rho_fs rho_cons  unc_cal  sig_med   base  prec20   skill  gated
dhruva-s       evolve-evolve    48    0.778    0.579    0.582   -0.182   0.1042  0.875   1.000   1.000   0/48
dhruva-s       evolve-random    60    0.858    0.736    0.685    0.330   0.1097  0.467   0.667   0.375   7/60
wideband-sdr   evolve-evolve    42    0.795    0.682    0.684    0.180   0.0996  0.143   0.125  -0.029   0/42
wideband-sdr   evolve-random    63    0.903    0.857    0.842    0.409   0.1367  0.143   0.385   0.440   8/63
```

**What the leaky bound is for.** It does two jobs and neither is "a number to
quote". First, it proves the family CV is really holding something out: ρ on the
selection-free arms is +0.736 / +0.857 with the rows in train versus +0.441 /
+0.502 out-of-fold — if v2-cv were leaking, the two rows would coincide. Second,
it puts a ceiling on what more coverage of this *kind* can buy: the model has the
capacity to rank these designs at ρ ≈ 0.8, so the out-of-fold ρ ≈ 0.47 is a
generalization gap across topology families, not an architecture limit.

**Sanity check on the reproduction.** `v1-equiv` reproduces §15.4's deployed
critic-v1 numbers to within seed noise — dhruva-s control ρ(mean−βσ) **+0.218 vs
+0.220**, ρ(feasibility) **+0.173 vs +0.198**; wideband-sdr control **+0.195 vs
+0.175** and **+0.198 vs +0.174**. So the v1→v2 deltas below are a like-for-like
comparison, not two different measurements.

**Headline.** On the selection-free control arms the deployment-distribution
correlation goes **+0.17 → +0.44 (dhruva-s)** and **+0.20 → +0.50
(wideband-sdr)**; on the selected elites it goes from **negative** (−0.22
wideband-sdr, +0.03 dhruva-s) to **+0.48 / +0.64**. Selection skill on the
control arms goes **−0.094 → +0.375** and **+0.160 → +0.300**, i.e. both clear
θ=0.25 where neither did before. The collapse is **substantially repaired but not
closed**: the mutant ρ is now ~55–60% of the in-distribution 0.81, not ~20%.

⚠ `wideband-sdr/evolve-evolve` skill is **−0.235** in both regimes: at base 0.143
only 6 of 42 rows are near-feasible and the top-20% is 8 rows, so this cell is
noise-dominated and should not be read as a regression.

### Calibration, before and after — why the uncertainty gate was inert

| | v1-equiv | v2-cv |
|---|---|---|
| in-distribution holdout ρ(σ, \|err\|) | **0.583** | **0.507** |
| mutant ρ(σ, \|err\|), four groups | +0.117 / +0.337 / +0.055 / +0.099 | +0.148 / +0.414 / +0.363 / +0.146 |
| holdout p90 σ (the gate threshold) | 0.2922 | 0.3077 |
| **median mutant σ** | 0.117 – 0.206 | 0.103 – 0.165 |
| mutant rows above the gate | **22/213 (10.3%)** | **8/213 (3.8%)** |

The ensemble is well calibrated **in distribution** (ρ ≈ 0.5–0.6 both before and
after) and only weakly calibrated on mutants (ρ ≈ 0.1–0.4, unstable in
magnitude). The mechanism behind §15.4's `n_high_unc = 0`: **mutant σ is
systematically *smaller* than holdout σ, not larger** — the gate's premise
("off-distribution ⇒ the ensemble disagrees") is empirically inverted here,
because the held-out *families* are structurally unusual while the mutants are
one-edit perturbations of well-covered graphs. Better coverage makes it worse,
not better: median mutant σ falls on every group and the firing rate halves,
10.3% → 3.8%. **A σ-percentile gate cannot detect this kind of shift and should
be replaced by a distance-to-training-set gate** — which is what the trust region
(§15.4) already is, and it is the rule that did real work.

---

## 3. Rung 1, live — the S1 experiment

### Pool

```
python lna/search.py --pool lna/out/ft_p5v2_nb_s1337.v3 --spec dhruva-s
# 256 files -> L0 209 -> WL-distinct 113 -> fresh-for-spec 110
#   51 novel vs ref-v2[189h/b5689490]+store, 72 already labeled under another spec
```

P5-v3 is the **adopted** generator (FINDINGS §16). No row of this pool had ever
been sized against `dhruva-s`, so all 110 are fresh (wl_hash, spec) keys.

### Ranking (critic)

```
{"snapshot": "v5-train", "n_store_rows": 1006, "n_dropped_pool_hashes": 244,
 "n_train": 568, "n_val": 95, "n_holdout": 99, "sigma_s21": 0.783,
 "n_models": 5, "beta": 1.0, "sigma_gate_p90": 0.3995,
 "holdout_rho_s21": 0.824, "holdout_rank_acc": 0.833, "train_s": 766}
uncertainty gate: 2/110 pool candidates exceed the holdout p90 sigma
```

**Leak-free:** all 244 store rows carrying one of the pool's 110 WL hashes (under
any spec) were dropped before training. The critic predicts **no** candidate
feasible — the whole ranking lives in the negative half of the scalar
(−1.49 … −11.34, top-30 cut −2.71).

### Arms

k = 30 each, control drawn with `random.Random(1337).sample`, declared before any
SPICE ran. Overlap 6 → **54 distinct sizings**, each simulated once and credited
to both arms it belongs to (so each arm's budget is exactly 30 sizings of the same
protocol). Protocol per candidate: `size.size_topology(n_candidates=4, sgd_iters=5,
cgd_iters=1, inductor_q=12)` then box-clamped `size.polish(budget=60)`, better of
the two by total violation. Recipe `rung1-v1`, arm membership in
`provenance.rung1_arms`.

```
arm         k  sized   ok  feas  near   base  bestviol  medviol  SPICE-min
critic     30     30   30     0    15  0.500     1.014    2.222       30.4
control    30     30   30     0     8  0.267     1.015    2.661       34.3
```

* near-feasible rate critic **0.500** vs control (= base) **0.267 ± 0.081**
* **S1 as written (≥2× the control's feasible-or-near-feasible count): 15 vs 8 =
  1.88× → NOT MET.** One more near-feasible design in the critic arm would have
  read exactly 2.00×. Fisher exact one-sided **p = 0.055** (conservative: the 6
  shared candidates make the arms positively dependent).
* **S1 under the restated skill bar (§14.6): skill = 0.328 ≥ θ = 0.25 → MET.**
  (base 0.267 from the control arm; ceiling precision min(base·110, 30)/30 = 0.978.)
* **realized-vs-predicted ρ = +0.578** over all 54 sized candidates — the first
  deployment-distribution measurement on a *live generated* pool, and 3× critic
  v1's mutant number. Stable across strata: novel-vs-ref-v2 n=22 **+0.621**,
  seen-under-another-spec n=40 +0.537, structure-never-labeled n=14 +0.552.
* cost: 12 885 ngspice evaluations, **64.7 SPICE-min total** (30.4 + 34.3),
  ~64 s/sizing, ~30 min wall at 2 concurrent shards. Well inside the ≤90
  SPICE-min/arm budget.

### Where the edge came from

Margins ≤ −1 scale unit (what kills near-feasibility), counted per arm:

| arm | S11 | S21 | NF |
|---|---|---|---|
| critic | 8 | 7 | **3** |
| control | 12 | 10 | **9** |

The critic arm is better on every constraint and by far the most on **NF** (3 vs
9) — which is the constraint the whole dhruva ladder is now stuck on (Gate D3).

### Feasibility, and an honest caveat about "best violation"

**0 fully feasible designs in either arm.** `dhruva-s` wants S21 ≥ 30 dB **and**
S11_max ≤ −10 dB **and** NF ≤ 3.5 dB **and** Idd ≤ 13 mA simultaneously; the whole
program has one tier-1-clean design on this spec (§15.3) and none tier-2.

The `bestviol` column is **not** a useful headline here and the two arms tie on it
(1.014 vs 1.015) for a bad reason: the lowest-violation points are degenerate
shrink-to-nothing optima that satisfy S11/Idd/NF by producing no gain
(e.g. seq0038: S11 −14.5, Idd 0.35 mA, NF 3.48, **S21 −0.43 dB**). This is exactly
the failure §15.5 item 5 warned about. Among designs with real gain
(S21 margin > −1) the ordering is unambiguous — **the best four all came from the
critic arm**:

```
seq0218  rank= 6  critic          viol=1.377  S11=-0.32 S21=17.73 Idd=2.94 NF=2.82
seq0126  rank= 1  critic  NOVEL   viol=1.466  S11=-0.01 S21=15.98 Idd=4.32 NF=2.73
seq0073  rank=15  critic          viol=1.587  S11=-0.70 S21=10.29 Idd=4.94 NF=3.24
seq0029  rank=12  critic  NOVEL   viol=1.670  S11=-0.03 S21=17.81 Idd=5.12 NF=4.43
```

`seq0126` is novel against ref-v2 + the whole store and reaches **NF 2.73 dB** at
15.98 dB gain — below the 3.5 dB spec — but with the input match unsolved
(S11_max −0.01 dB), so it is not feasible on any tier. It is an NF lead, not a
design.

### Novelty accounting

| arm | novel vs ref-v2 (of 30) | near-feasible AND novel |
|---|---|---|
| critic | 11 | 5 |
| control | 15 | 4 |

The critic **under**-selects novelty (11/30 vs the pool's 46%) — it mildly prefers
archetype-like structures — and still wins on near-feasibility. Both arms
together put 54 new `dhruva-s` L2 rows in the store (132 → 186 for that spec).

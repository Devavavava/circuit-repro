# CAMPAIGN — x0-v0 (PRE-REGISTRATION)

**Status: EXPERIMENTAL. Committed BEFORE results (house law).**
Nothing here is frozen protocol. Adoption of the learned prior — or of any
warm-start path over the existing null — is a **USER RULING** (memory:
circuit-repro-governance). This file records the three arms, their budgets,
metrics, leakage rule, and attribution *before any x0-v0 number is read*, so no
result can be reverse-justified. Same house style as
`kaggle/CAMPAIGN-CAPABILITY-V1.md`.

Date pre-registered: 2026-09-04. Branch: `x0-prior` (worktree, unmerged).

---

## 1. The question

**Does a learned starting-sizing prior ("learned x0") reach FEASIBLE with fewer
ngspice evals than the sizer's existing dumb start — and does it beat a plain
retrieval baseline, not just the midpoint null?**

Today the sizer starts every topology from the **midpoint** `x0 = [0.5]^d` (the
L1 screen) and CMA-ES restarts from a **fresh uniform-random** mean
(`null_sizer.run_cmaes`, `xmean = rng.random(n)`, sigma0=0.3). There is **no**
learned or per-archetype starting sizing anywhere; the only warm start that
exists is arm-A/curate reuse of a stored best for the *same* topology. A model
that predicts `x0` from *(topology, spec target, pdk)* is genuinely new.

The bar is deliberately high and pre-set: the learned prior (A2) must beat
**BOTH** the existing null (A0) **AND** a nearest-stored-winner retrieval
baseline (A1). If it only beats the midpoint but not retrieval, retrieval is the
cheaper thing to adopt and the model is not worth its weight — that comparison is
the whole point of building all three paths.

This is a **spec-capacity / efficiency** question (governance 2026-08-20), not a
novelty question. "Feasible" = the sized design meets every *gated* hard
constraint (`spec.feasible()`: S11, S21, Idd, NF; IIP3 not gated).

---

## 2. Arms

All three arms share the **same** topologies, the **same** sizing engine
(`solve_spec.size_tokens` → `null_sizer.run_cmaes`/ngspice), the **same**
feasibility test, the **same** results schema, and the **same matched total eval
budget per spec**. They differ in ONE thing: the CMA-ES **first-restart mean**.
The flag `LNA_X0_PRIOR` (env var) selects the arm; a single code path
(`size.warm_start_x0`) computes the seed so the arms cannot diverge by accident.
**Default OFF ⇒ A0 ⇒ byte-identical to today's sizer** (goldens prove it; §6).

### ARM0 — "null" (`LNA_X0_PRIOR` unset / `off`)

The **existing** sizer, unchanged: midpoint L1 screen, CMA-ES restarts from a
fresh uniform-random mean. This is the attribution baseline and the byte-identity
reference. `run_cmaes(x0=None)` is proven identical to the pre-change code
(same RNG stream, same evaluated points — mechanical test, §6).

### ARM1 — "retrieval" (`LNA_X0_PRIOR=retrieval`)

Warm start = the **nearest stored winner's** decoded `best_params`, re-encoded to
this topology's `[0,1]^d`, seeding CMA-ES's first mean (`x0_retrieval.py`).
Nearest = exact/prefix `wl_hash` match first (prefer feasible), else nearest
feature vector over the same box corpus A2 trains on. No learning — a k-NN
lookup. This is the honest "is a learned MODEL doing anything a lookup table
can't?" control.

### ARM2 — "learned" (`LNA_X0_PRIOR=learned` / `1`)

Warm start = the **trained per-kind prior** (`x0_prior.py`): a small pure-numpy
MLP mapping the fixed-length feature vector *(topology summary + achieved-spec
target + band + pdk)* → one normalised `x0` per sizer KIND (W,L,R,C,VB), read
per-device at sizing time. Same seeding hook as A1. Trained on the box corpus
only (§4). ~seconds to train on CPU.

Only the **first** CMA-ES restart mean is seeded; restarts 2..N stay uniform-
random (byte-identical to the null after restart 1). The `rng.random(n)` draw for
restart 1 is **still consumed** and discarded, so the RNG stream downstream is
unchanged — the only difference from A0 is the value of that one mean.

---

## 3. Budgets & matched-eval rule (UNCHANGED from the null)

Per spec, the total ngspice eval budget is **identical across A0/A1/A2** — the
warm start spends **zero extra evals**; it only changes *where the first mean
sits*. For the adoption eval we use the ladder's own matched budget (the same
`solve_spec.size_tokens` budget A0 already runs at). No arm gets more sim calls
than another; that is what makes evals-to-first-feasible a fair comparison.

The learned prior's **training** cost (reading the box corpus + numpy SGD,
~minutes on CPU, no ngspice) is paid **once, offline**, and is not part of any
per-spec budget.

---

## 4. Training data, provenance, and the LEAKAGE RULE (BINDING)

### Source (audited before any modelling — see the audit table below)

The only clean source is the **box-era L2 label store**
`lna/data/topo_labels.jsonl`. Every row carries `graph.tokens`, `best_params`
(the DECODED winning sizing) and `metrics`. The normalised `x` is recovered by
**inverting** `size.make_objective`'s decode with the same `kind_ranges`
(log/linear per kind), so a row needs only tokens+params — not the rarely-stored
`best_x`. Reconstruction was validated to `<5e-7` against stored `best_x` on the
370 rows that carry both.

**Audit (2026-09-04, `python lna/x0_data.py --audit`):**

| dimension | value |
|-----------|-------|
| buildable training rows | **4072** (of 4076 store rows; 4 dropped for missing tokens/params) |
| feasible rows | 129 (used as 2× sample weight, never a gate) |
| pdk | bptm45 = 4072 (100%) — **no foreign-PDK rows pooled** |
| distinct specs | 7: wifi24=1467, dhruva-s=1059, dhruva-l1=729, wideband-sdr=402, dhruva-l5=309, gps-l1=79, dhruva-l2=27 |
| code era (git_sha) | eae6374=1261, 0aa6fdf=1247, 87af8f2=214, cc8b991=145, + long tail |
| source arm | campaign-G=609, nf-campaign=483, evolve-random=369, nf-moves=331, trackb-p5v5=285, … |
| ladder-leak rows dropped | **0** (no ladder spec_id present in this store) |
| feature_dim | 16 |

### What is EXCLUDED and why

- **Every `kaggle/campaigns/*` design** (capability-v0/v1, cross-pdk-v0). All of
  them run the **ladder specs** (`cap-e01-wifi` … `cap-m08-ism58`) — verified:
  each campaign `results.jsonl` carries exactly the 24 ladder spec_ids. Using any
  of them would train on the adoption eval set. The training-set builder
  (`x0_data.build_rows`) **never reads that tree**, and additionally drops any row
  whose spec is a ladder spec_id (a no-op today, a guard for the future).
- **Foreign-PDK Kaggle rows** (cross-pdk sky130/gf180mcu/ihp): excluded twice
  over — they are ladder specs (above) *and* foreign-PDK. Per the pinned-recipe
  parity ruling, Kaggle rows may be pooled ONLY for bptm45; these are not bptm45,
  so they stay OUT regardless. (The current box store is 100% bptm45, so this is
  moot today, but the rule is stated and enforced.)
- **The box-era `sim_points.jsonl` / `op_points.jsonl`** rows lost in the
  2026-08-27 sparse-checkout incident — not on disk; not assumed to exist.

### Band-overlap CAVEAT (honest, residual leakage vector)

Several box specs share a **band** with ladder specs: wifi24/dhruva-s ≈ 2.44 GHz
= `cap-*-wifi`; gps-l1/dhruva-l1 ≈ 1.575 GHz = `cap-*-gpsband`; wideband-sdr
overlaps `cap-*-wideband`. We do **not** drop these — dropping every 2.44 GHz
design would gut the corpus — but a prior that memorises "good sizing at 2.44 GHz"
could transfer to the ladder wifi specs. Two mitigations are pre-registered:

1. The prior conditions on the **achieved-spec target vector** (nf/s11/s21/idd,
   §5), not on band alone, so band memorisation is diluted by target
   conditioning.
2. An **explicit pre-registered honesty holdout**: retrain with `--holdout-spec`
   set to the band-overlapping box specs and report held-out MSE. A prior that
   only wins in-band is flagged as such and NOT put forward for adoption.

The ladder eval bar (beat BOTH null and retrieval, at matched budget) is set with
this residual overlap acknowledged.

### Hindsight relabelling (the exact transform)

A stored design was sized *for* some target spec, but the sizing it found is a
valid demonstration for the spec it **actually achieved**. So the training TARGET
is synthesised from the **measured** metrics, not the row's nominal constraints:

```
achieved_target[nf_db]  = measured nf_db   (a "<= this" NF gate the design met)
achieved_target[s11_db] = measured s11_db  (a "<= this" match the design met)
achieved_target[s21_db] = measured s21_db  (a ">= this" gain the design met)
achieved_target[idd_ma] = measured idd_ma  (a "<= this" current the design met)
+ band f0 (Hz, log-scaled) carried from the row's spec.
```

Each is squashed to a stable feature by `v/scale` (clipped). Every evaluated
design — feasible or not — is therefore a valid row for the (possibly relaxed)
spec it met. `feasible` is used only as a 2× sample weight, never as an inclusion
gate. This is documented in `lna/x0_data.py:target_feature_from_metrics`.

---

## 5. Metrics & attribution

Per spec, per arm, at the matched total budget:

- **evals-to-first-feasible** (primary) — from the results row
  `evals_to_first_feasible`. Lower is better. The efficiency claim.
- **solved count at fixed budget** (primary) — how many ladder specs reach
  FEASIBLE. Adoption needs solved(A2) ≥ solved(A0) AND a real evals reduction.
- **worst-margin / closest-miss** on unsolved specs (secondary) — did the warm
  start at least land closer?

**Primary comparisons (all at matched budget):**

- **A1 − A0** → does *any* warm start help? (retrieval effect)
- **A2 − A1** → does the **learned model** beat the **lookup**? This is the
  adoption-relevant delta. A2 must clear A1, not just A0.
- **run-to-run noise floor** — CMA-ES is seeded; A0 is deterministic per seed, so
  the noise floor here is the seed-to-seed spread of A0 across the ladder. Any A2
  gain must exceed it. (Report A0 at ≥2 seeds to size the floor before reading
  A2.)

### Offline model sanity (pre-adoption gate, not the campaign)

Before any ngspice run, the model must beat the two trivial predictors on a
held-out box-spec split (`python lna/x0_prior.py`):

- `eval_mse_learned` < `eval_mse_midpoint_null` (beat 0.5^d), AND
- `eval_mse_learned` < `eval_mse_perkind_mean` (beat a per-kind-mean table).

If it fails either, it does not proceed to the ladder. (Measured numbers are
recorded in the smoke section of the branch report, not here — this file is
pre-results.)

### Honest-outcome clause (BINDING)

A warm start that ties or loses to the null is a **result**, reported as
measured, not a bug. "Learned x0 does not help on this ladder" is a valid answer
to the question. All arms report every spec whatever the outcome.

### Experimental clause

All 24 ladder specs remain EXPERIMENTAL, not frozen. x0-v0's conclusions inform —
they do not adopt — any warm start. Adoption is a user ruling.

---

## 6. Byte-identity & integration (flag OFF ⇒ null)

- Flag: **`LNA_X0_PRIOR`** — unset/`off` (A0), `retrieval` (A1), `learned`/`1`
  (A2). Optional `LNA_X0_PRIOR_MODEL` overrides the model path.
- Integration point: `solve_spec.size_tokens` computes `x0 =
  size.warm_start_x0(...)` and passes it to `null_sizer.run_cmaes(..., x0=x0)`.
  `warm_start_x0` returns `None` when the flag is off, on any import/model/shape
  error, or when no neighbour exists — the sizer can never be broken by the warm
  start.
- `run_cmaes(x0=None)` is **byte-identical** to the pre-change code: the
  first-restart `rng.random(n)` is always drawn (RNG stream preserved); `x0` only
  *replaces the value* of the first mean when provided.
- Proof: all goldens GREEN with the flag OFF from the worktree with
  `LNA_DEPS_ROOT` set — `check_ref`, `check_bjt`, `check_pdk`,
  `check_pdk_funnel` (exercises the sizer, d=8/9), `check_pdk_wsweep`,
  `lna/extract.py --selftest`, `lna/spec.py --all`. Plus a mechanical test that
  `run_cmaes(x0=None)` yields identical evaluated points to the null and that
  `x0=[...]` changes only the first generation at the same budget.

---

## 7. Artefacts & how to run

```
kaggle/CAMPAIGN-X0-V0.md      this file (pre-registration)
lna/x0_data.py                training-set builder + leakage rule + hindsight relabel; --audit
lna/x0_prior.py               learned per-kind prior (train/eval/save); CLI beats-null gate
lna/x0_retrieval.py           arm A1 nearest-stored-winner warm start
lna/size.py                   + warm_start_x0() (flag-gated shared seed), _spec_target_metrics()
lna/null_sizer.py             run_cmaes(..., x0=None) — optional first-mean seed, null-identical
lna/solve_spec.py             size_tokens computes + passes the warm-start x0
lna/out/x0_prior.npz          trained model weights + schema (committed on branch)
```

Offline (no ngspice):
```
python lna/x0_data.py --audit                       # provenance table
python lna/x0_prior.py                              # held-out beats-null gate
python lna/x0_prior.py --holdout-spec dhruva-s      # band-overlap honesty holdout
python lna/x0_prior.py --train --out lna/out/x0_prior.npz   # save the model
```

On the ladder (matched budget, per spec, one arm at a time):
```
LNA_X0_PRIOR=off        python lna/solve_spec.py <ladder-spec> --topology <wl> --budget <B>   # A0
LNA_X0_PRIOR=retrieval  python lna/solve_spec.py <ladder-spec> --topology <wl> --budget <B>   # A1
LNA_X0_PRIOR=learned    python lna/solve_spec.py <ladder-spec> --topology <wl> --budget <B>   # A2
```

Run A0 first (the null), size the seed-to-seed noise floor, then A1, then A2;
record `evals_to_first_feasible` + solved count per arm; commit results honestly
whatever the outcome. Adoption is a user ruling.

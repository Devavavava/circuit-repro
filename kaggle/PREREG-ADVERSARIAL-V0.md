# PRE-REG — adversarial pieces v0: verifier exploiter (EX) + value model (VM)

**Frozen:** 2026-10-01, before any result. **GO:** user, 2026-10-01 ("let's set this up").
Branch `worktree-externals-gf180`. Outputs: `kaggle/campaigns/adversarial-v0/{EX,VM}/`.

## Why

AlphaZero-style ideas that fit this problem (single-player puzzle against fixed physics)
without a natural opponent: (1) a **value model** to make search affordable, (2) a
**setter–solver curriculum** (deferred until the first batched RL round), (3) an
**adversary against the verifier**, (4) a league (deferred; compute). Measured compute
(R1–R3): RL at real scale is bounded by SPICE verification CPU (~310 CPU-s/attempt), not
GPU — so (1) is an enabler, and (3) prevents the reward-hacking seen repeatedly
(instability, band-edge gaming, junk parts, port-DC).

## EX — verifier exploiter (local CPU, ≤ 4 processes, ≤ 80 CPU-h)

**Goal:** find circuits that PASS verifier rl-v1.1 yet FAIL an independent reality check.
**Reality checks** (applied to the sized winner, no re-sizing):
R-a realistic sources: AC-coupled 50 Ω source (1 µF) and DC-grounded 50 Ω source;
R-b transient with reactive source/load terminations (R4 method) — growing oscillation;
R-c dense band resampling (≥ 4× the verifier's frequency points) — spec still met;
R-d temperature −40 / +85 °C (spec within the 2% cushion);
R-e supply ±10% (spec within the 2% cushion).
(R-d/R-e/robustness are REPORTED as "fragility", not exploits, unless the user rules them
in scope — W3 waived robustness for now.)
**Search:** start from every rl-v1.1-feasible design on record (bench-v2 accepted +
training-pool witnesses + rl-readiness winners) and mutate (2–4 primitive edits +
repair), optimizing exploit score = [passes rl-v1.1] × (magnitude of the worst
reality-check failure among R-a..R-c). Fixed RNG; log everything.
**Decision rule:** each distinct exploit class (≥ 2 independent instances) becomes a
proposed guard with evidence, presented to the user for ruling (as W1–W6). Nothing is
added to the verifier without a ruling.

## VM — value model (local CPU, torch CPU, no new installs)

**Data:** all recorded sizing outcomes with full metrics (bench-v2 run, bench-v12-audit,
rl-readiness, S-1, …; ~28k rows). Labels per verifier profile; train primarily on
rl-v1/rl-v1.1 rows; record profile as a feature or train per profile.
**Inputs:** topology (token sequence / device graph) + spec constraints + band.
**Models:** a simple baseline (e.g. hand features + logistic/MLP) AND a graph model
(reuse `lna/critic_gnn.py` ideas if portable; read-only import of shared core).
**Split:** held out by spec family / parent anchor / bench-v2 cell (never random rows),
plus a time split (train on earlier rows, test on later).
**Metrics:** AUC; at the threshold keeping ≥ 95% of true feasibles, the fraction of
candidates pruned; calibration; margin regression error.
**Decision rule:** "useful as a search pruner" iff prune ≥ 50% at ≥ 95% recall on the
held-out split. Final verdicts always stay with SPICE (the VM only orders/prunes).

## Fences

bench-v2 cells are eval-only: VM may train on bench-v2 *search* rows but reports
metrics separately for rows from accepted bench cells; EX never modifies bench cells.

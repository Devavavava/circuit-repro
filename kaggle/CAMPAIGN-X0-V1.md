# CAMPAIGN — x0-v1 (PRE-REGISTRATION): warm starts on UNSEEN topologies

**Status: EXPERIMENTAL. Committed BEFORE results (house law).** Adoption of any
warm start remains a **USER RULING**. This file fixes the cells, arms, budgets,
metrics, and attribution before any x0-v1 number is read.

Date pre-registered: 2026-09-04. Commissioned by user 2026-09-04 ("yep go
ahead", following the x0-v0 verdict discussion). Follows
`kaggle/CAMPAIGN-X0-V0.md`.

---

## 1. The question

x0-v0 measured warm starts on the sizer's **home turf**: corpus topologies whose
winning params sit in the retrieval store (near answer-key conditions for A1),
same PDK, overlapping bands. Verdict: A1 retrieval −23.9% evals-to-first-
feasible vs null; A2 learned beat the null (−17.0%) but LOST to retrieval —
failing its pre-set bar.

**x0-v1 asks the question that matters for the program's actual direction: do
warm starts still help on topologies NEITHER method has ever seen — the shapes
the reasoning loop itself invents — and does the ranking A1 > A2 survive when
retrieval's exact-match advantage is removed?** In production (arm-B loop),
every proposal is a fresh shape with no store entry; that case was untested.

---

## 2. Eval cells (enumerated NOW, mechanically, before any run)

Source: the committed bptm45 arm-B campaign records (capability-v0 armb,
capability-v1 arm2-arch / arm3-selflearn — Kaggle host, admissible for reuse of
*topology shape only* under the pinned-recipe parity ruling; all sizing in this
campaign is fresh, on-box). For each ladder spec, the FIRST feasible arm-B cell
in priority order (v1-selflearn → v1-arch → v0-armb) contributes its winning
proposal topology (`designs/<spec>/tokens.json`, wl from `proposal.json`).
Machine-readable list committed at `kaggle/x0v1-cells.json` (14 cells).

**Blindness check (recorded pre-run):** the training/retrieval store
(`lna/data/topo_labels.jsonl`, 927 distinct wl_hash) contains NONE of the 10
NOVEL cells' hashes. Campaign artifacts were never in the store (x0-v0 leakage
rule), so both A1's corpus and A2's training set are blind to these shapes.

| spec | topology (wl) | from | split |
|---|---|---|---|
| cap-e01-wifi | 25905c563595 | v1-selflearn | **NOVEL** |
| cap-e02-gpsband | a13885258ca3 | v1-selflearn | **NOVEL** |
| cap-e04-35ghz | f49a8abd26dd | v1-selflearn | **NOVEL** |
| cap-e06-wifi | 0a5583e1dc5d | v1-selflearn | **NOVEL** |
| cap-e07-gpsband | 164fb57cffc4 | v1-selflearn | **NOVEL** |
| cap-h02-gpsband | e25b5a021ab6 | v1-selflearn | **NOVEL** |
| cap-h05-ism58 | 7c8c8f9e0d2a | v1-selflearn | **NOVEL** |
| cap-m04-35ghz | fb45bc8be87f | v1-selflearn | **NOVEL** |
| cap-m06-wifi | 642485a8fad7 | v0-armb | **NOVEL** |
| cap-m08-ism58 | 3a2658be7000 | v1-selflearn | **NOVEL** |
| cap-e05-ism58 | c231ac11552a | v1-selflearn | seen (control) |
| cap-h01-wifi | 1bf4c880c7fa | v1-arch | seen (control) |
| cap-m01-wifi | 1bf4c880c7fa | v1-selflearn | seen (control) |
| cap-m05-ism58 | c231ac11552a | v1-selflearn | seen (control) |

- **NOVEL-10** = the primary eval set (wl not in store).
- **SEEN-4** = in-distribution control strip (known archetypes, wl in store):
  retrieval is EXPECTED to win here (x0-v0 said so); it anchors the contrast.

Every cell's topology is KNOWN-SIZABLE for its spec (an arm-B run reached
feasible with it at matched budgets — on Kaggle, bit-exact to box per the
parity evidence), so all-arm zeros mean budget/seed noise, not impossible
cells.

---

## 3. Arms & budgets (matched; identical to x0-v0 semantics)

Same three arms, selected ONLY by `LNA_X0_PRIOR` (`off` / `retrieval` /
`learned`), same shared `size.warm_start_x0` hook, same store and committed
model (`lna/out/x0_prior.npz` — NOT retrained). Per cell, per arm: the sizing
protocol mirrors the arm-B per-candidate budget — base `seeds=2 × budget=300`;
if infeasible, ONE escalation `seeds=3 × budget=600` — with
evals-to-first-feasible accounted exactly as `campaign.py` accounts it for
arm-B candidates. The topology is FIXED per cell (no L1 screen over a
candidate pool, k=1): all arms size the same tokens for the same spec at the
same budget; only the first CMA-ES restart mean differs. Driver:
`kaggle/x0v1_run.py` (reuses campaign/solve_spec internals; no LLM anywhere).
Runs on box, bptm45, era recorded at launch; sequential legs A0 → A1 → A2.

---

## 4. Metrics & attribution (fixed now)

Primary, on **NOVEL-10**, at matched budget:

- **evals-to-first-feasible** (sum + per-cell) and **solved count**.
- **A1 − A0**: does retrieval's similarity-fallback transfer to unseen shapes
  at all, or does the transplant mislead (worse than midpoint)?
- **A2 − A1**: the ruling-relevant delta — does the learned per-kind model win
  once the exact-match advantage is gone?
- **A2 − A0**: does the model help at all off-distribution (its wifi-holdout
  already warned it may decay to ~midpoint).

Secondary: SEEN-4 control strip (expect A1 best; a deviation flags noise),
closest-miss margins on unsolved cells, sim-health fields (new era, advisory).
Noise caveat carried from x0-v0: single arm-level run per leg; per-spec
seeds=2/3 internal; e2f values sit on the escalation grid — read only deltas
that clear a grid step, and treat the SEEN-4 strip as a same-run consistency
check against x0-v0's ranking.

### Honest-outcome clause (BINDING)

"Neither warm start helps on unseen shapes" and "retrieval transplant actively
hurts" are both valid answers, reported as measured. No cell is dropped;
0-feasible rows are results.

### Ruling queue (after results, user decides)

(1) `LNA_X0_PRIOR` default for production loops — off / retrieval /
retrieval-only-on-exact-match (the curate-style hybrid) / learned; (2) iterate
or park the learned prior. x0-v0 + x0-v1 together are the evidence base.

---

## 5. Artefacts

```
kaggle/CAMPAIGN-X0-V1.md   this file (pre-registration)
kaggle/x0v1-cells.json     the 14 frozen cells (spec, wl, tokens_file, novel)
kaggle/x0v1_run.py         driver (committed before first leg)
kaggle/campaigns/x0-v1/    results archive (era-tagged) after the run
```

Driver smoke before launch is restricted to NON-cell inputs (a box spec + a
store topology) so no eval number is read pre-run.

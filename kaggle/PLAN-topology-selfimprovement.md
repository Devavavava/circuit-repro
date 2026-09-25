# Plan — Verifier-guided self-improvement for analog topology synthesis

**Status:** design handed off (2026-09-25). Branch `worktree-externals-gf180`.
**Goal:** improve Qwen-32B to do *general* topology-fixing (match the Claude ceiling)
**without** hand-teaching individual topologies. Learn new moves by search against
the SPICE sizer as a free verifier, at the level of **coherent circuit bundles**.

---

## 0. Why this plan (findings that led here — with commits)

- **Process, not topology, was the wall.** Specs are 45 nm (bptm45)-native but were
  being run on 180 nm gf180. Re-based on native bptm45. Sizer made **deterministic**
  (gf180 MC pinned off; bptm45 native is deterministic) — commit `49ab2b9f`. *Keep this.*
- **bench-v1.2 = the clean, achievable benchmark** (commit `79e0963c`,
  `kaggle/editcap-lib-v12-45nm/`, 16 cells): each cell's shown anchor **fails** to size
  (topology-fix required) yet a better topology **solves** (achievable). Anchor 0/16,
  Claude 16/16. Impossible tiers explicitly removed. **This is the held-out eval + the
  reason RL is viable (achievable reward surface).**
- **Capability gap (commit `2a5082fe`, `analyze_qwen_vs_claude_topo.py`):** Qwen reaches
  narrowband cascode+tank in 6/29 edits (a *reliability* gap) but **never** emits
  wideband resistive shunt-feedback (0/64 — a *missing-move* gap).
- **Few-shot proved the missing-move gap is knowledge, not capacity** (kernel
  `editcap-v12-fewshot`): one worked shunt-feedback example → 4/24 shunt-fb edits, 3/8
  wideband cells solved. **But hand-teaching per topology is patchwork — REJECTED by
  the user.** Hence this plan: a general loop that discovers moves itself.

## 1. Core principle

The SPICE sizer scores **any** (spec, topology) → feasible + margin, deterministically,
across all topologies/specs. It is a **free, general verifier**. So: **generate training
signal by search + verification, not by human labels.** The model proposes topologies,
the simulator judges, we reinforce verified successes. Reward = "meets spec" — universal,
so it generalizes across topologies and problem statements.

This is also the principled fix to the earlier *failure-only self-learning = zero lift*
result (memory `circuit-repro-editcap`): that failed for lack of **positives**; search
manufactures the positives.

## 2. Key design decisions (do NOT skip — they follow from the physics)

1. **Reachability via a complete primitive alphabet.** The netlist edit primitives —
   add/remove {NMOS,PMOS,R,C,L}, connect a terminal to any node — are a **closed, tiny,
   complete** set. Every topology (incl. ones nobody demonstrates) is a *composition* of
   them. So a "new move" is always a new **composition**, never a new atom.
2. **The learning/reward UNIT is a coherent whole circuit (a multi-primitive bundle),
   verified atomically — never score intermediates.** Structural moves (CG→cascode,
   reactive-match→shunt-feedback, add-a-stage) are inherently multi-edit and their
   partial states are **broken** (floating gates, dead bias, fighting matches). A
   hill-climb over single primitives with per-step reward stalls in that valley. So:
   only ever hand the simulator a *complete, biased candidate*; terminal reward on the
   bundle; no per-primitive credit. (This is why the old hand-built editmoves *library*
   worked — each "move" was a valid-by-construction bundle.)
3. **The LLM is the proposer because it emits coherent bundles.** Blind primitive
   mutation constantly yields incoherent intermediates; the LLM holds the gestalt and
   emits whole self-consistent netlists. Primitives give *reachability/novelty*; the LLM
   gives *coherence*.
4. **Novelty beyond the LLM's greedy distribution = mutate-then-REPAIR.** Perturb a
   working circuit at the primitive level, then a **repair pass** completes the missing
   complementary edits (fix floating nodes / re-bias) to restore coherence *before*
   verification. The repair step is exactly what turns a half-built structural jump
   (1–2 incoherent edits) into a scorable coherent candidate.

## 3. The loop (architecture)

```
                 ┌─────────────────────────────────────────────┐
  failed anchor  │  PROPOSER (Qwen policy)  ── coherent netlist ─┼──┐
  + evidence  ──▶│  + MUTATE-THEN-REPAIR (novel coherent bundles)│  │
                 └─────────────────────────────────────────────┘  ▼
                                                        VERIFIER (SPICE sizer)
                                                        smoke_run, bptm45, MC-off,
                                                        3 seeds × ~2000 → feasible+margin
                                                                  │
                          reinforce verified winners  ◀───────────┘
                          (expert-iteration SFT, then optional GRPO)
```

- **Environment/verifier:** `kaggle/bench_anchor_prep.py::smoke_run(tokens, spec, seed,
  budget, "bptm45")` → metrics; feasibility via `Spec.feasible`. Single-candidate
  reference harness: `kaggle/mysolve.py` (set `MYSOLVE_PDK=bptm45`). Wrap as a **batch
  verifier** (many candidates in parallel; `ProcessPoolExecutor`, `TMPDIR=/tmp` local
  NVMe, `OMP/OPENBLAS/MKL_NUM_THREADS=1`). Reward = feasible (terminal) + shaped by
  worst-margin improvement vs the anchor.
- **Action = a full candidate netlist** in the harness dialect (topology only; the
  harness inserts bias + sizes). Round-trip/validate via `proposal.round_trip`.
- **Proposer:** Qwen conditioned on (anchor + evidence), the existing editcap prompt
  (`kaggle/editcap_run.py::build_prompt_*`). High temperature + K samples/cell.
- **Mutate-then-repair operator (Phase 2):** primitive perturbation + deterministic
  repair (reuse `lna/bias.py::insert_bias` for DC + a floating-node completer; or a
  model "make this coherent" pass), then verify.
- **Learner:**
  - *Phase A — expert iteration / rejection-sampling SFT:* keep simulator-verified
    solves (+ strong margin-improvers), SFT Qwen on (anchor → verified solving netlist),
    iterate. Bootstraps from Claude's solutions (`kaggle/claude-solutions/templates/`)
    as initial positives if needed.
  - *Phase B — RL (GRPO/PPO), optional:* dense margin-improvement reward for
    sample-efficiency once the policy is off the floor.

## 4. Cold-start / how new moves actually enter (the crux)

Pure self-improvement only amplifies what's sampled. To get moves the model
under-samples, in order of preference (all **one-time/general**, never per-problem):
1. **Diversity/temperature** — surfaces low-probability but *latent* moves (the few-shot
   proved Qwen has shunt-feedback latent; it just doesn't prioritize it).
2. **Mutate-then-repair** over the complete primitive alphabet — discovers novel coherent
   compositions the LLM wouldn't commit to greedily.
3. **One-time broad vocabulary seed** — a finite generic operator/archetype set
   (resistive feedback, cascode, inductive degeneration, LC tank, differential,
   current-reuse, source-follower, …) seeded ONCE from literature or a strong model,
   then *composed + placed* by the learned policy for arbitrary specs. Seed the alphabet
   once; discover the vocabulary indefinitely.

## 5. Execution phases (concrete)

- **Phase 0 — env + data.** Batch-verifier wrapper around `smoke_run` (bptm45, MC-off).
  Mass-generate a few-hundred **achievable** training specs using the calibration method
  (`kaggle/calibrate_bench_wb.py` / `_nb.py`: keep specs where the naive anchor fails AND
  some topology solves at equal budget), spanning bands/tiers **and held-out topology
  classes**. Strict train/eval split; **bench-v1.2 stays held-out**.
- **Phase 1 — expert-iteration baseline.** Sample K netlists/cell from Qwen (Kaggle GPU,
  batch ≤ ~50 completions/kernel for the 12 h limit; 32B@8192 tok ≈ 14 min/completion) →
  verify → SFT on verified pairs → re-score bench-v1.2. **Success metric:** solve-rate
  climbs from Qwen's ~0 toward Claude's 16/16, on held-out cells.
- **Phase 2 — mutate-then-repair for novelty.** Add the perturb+repair operator; feed
  novel coherent bundles into verify→SFT. **Metric:** lift on held-out *topology classes*
  (does the model now emit shunt-feedback / new moves unaided? re-run
  `analyze_qwen_vs_claude_topo.py`).
- **Phase 3 — RL (optional).** GRPO with margin reward for efficiency.

## 6. Assets already built (paths on this branch)

| Asset | Path |
|---|---|
| Deterministic verifier (engine) | `kaggle/bench_anchor_prep.py::smoke_run` |
| Single-candidate solve/size harness | `kaggle/mysolve.py` (`MYSOLVE_PDK=bptm45`) |
| Clean benchmark (held-out eval, 16 cells) | `kaggle/editcap-lib-v12-45nm/`; summary `.../bench-v1.2-45nm-survivors.json` |
| Claude reference solutions (bootstrap positives) | `kaggle/claude-solutions/templates/*.net` |
| Achievable-spec calibration / mass-gen | `kaggle/calibrate_bench_wb.py`, `_nb.py`, `build_bench_v12.py` |
| Topology-repertoire analyzer (what moves a model emits) | `kaggle/analyze_qwen_vs_claude_topo.py` |
| Proposer plumbing / prompts / smoke-fence | `kaggle/editcap_run.py` |
| Kaggle kernel pattern (bptm45, 8192 tok) | `kaggle/kernels-editcap/editcap-v11-45nm/` |
| Sizer determinism fix (KEEP) | `lna/size.py::eval_metrics` (gf180 MC-off); bptm45 native = deterministic |
| Bias insertion (for repair op) | `lna/bias.py::insert_bias` |

## 7. Risks / honest caveats

- **Cold-start** for truly-unsampled moves — mitigations in §4; the repair operator's
  quality gates the mutate path.
- **Kaggle 12 h limit** — batch (≤ ~50 completions/kernel). Qwen runs on Kaggle GPU;
  no local GPU on the box.
- **Determinism is load-bearing** — the whole reward signal was noisy until MC was pinned
  off (`49ab2b9f`). Do not run sizing with gf180 MC on; use bptm45 native.
- **Keep bench-v1.2 strictly held-out** — train on the mass-generated grid, never on the
  eval cells, or the ceiling comparison is meaningless.
- **Reward = ground-truth physics** (low hacking risk), but watch for degenerate
  "feasible" points near margin boundaries; verify final solves with a small margin
  cushion / multi-seed.

## 8. First thing to run

Phase 0 + Phase 1 round 1: mass-generate ~200 achievable specs, sample K=8–16 Qwen
candidates/cell, batch-verify, SFT on the verified solves, and re-score bench-v1.2.
That single round shows whether the loop compounds before investing in mutate-repair/RL.

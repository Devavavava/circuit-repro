# depth-probes-v1 — corner margin and IIP3 of within-one-edit vs beyond-one-edit designs

The pre-registration is `kaggle/PREREG-DEPTH-PROBES-V1.md`, frozen 2026-10-18 01:45 IST at commit `8b9a5ca08`.
Branch `worktree-externals-gf180`. Every output of this campaign lives in this directory. Local CPU only: no Kaggle,
no GPU, no paid API.

**Question.** On the 35 non-T1 held-out tasks, are already-found feasible designs that lie beyond one edit of the
shown anchor (pool B) clearly better than designs within one edit (pool A) on two properties the spec does not
gate?
- **PVT corners:** −40 °C, +85 °C, VDD × 0.9, VDD × 1.1.
- **In-band IIP3.**

RESULT: _(filled in below after the run)_

## Files

| file | content |
|---|---|
| `depth.py` | `collect` (pools), `run` (S/C/I stages with deadline), `summarize`, `status`, `worker` |
| `pools.json` | per-task pools A/B: token hashes, sources, cached seed-1 worst margins, selection, counts, witness use, seeded task order |
| `run/sizing.jsonl` | S stage: one re-size per design (exact key = bv2 `job_id`), metrics, worst margin, CPU |
| `run/corners.jsonl` | C stage: nominal re-eval + 4 EX corners (metrics, µ in-band/wide) per design |
| `run/iip3.jsonl` | I stage: `size.measure_iip3_tier3` result per design |
| `depth-designs.jsonl` | per design: task, pool, id, key, source, orig worst, re-sized worst, corner worst + per corner, IIP3 |
| `depth-tasks.jsonl` | per task: best-A / best-B corner and IIP3, depth / reverse flags |
| `depth-summary.json` | counts, readings, CPU |
| `depth-tables.md` | human-readable tables |
| `state/` | **gitignored, never committed**: design tokens and sized (body, params), witnesses included (EVAL-ONLY) |

Commands (through the env wrapper `~/.claude/jobs/7cd7ffc3/tmp/run_cr.sh`):

```
run_cr.sh kaggle/campaigns/depth-probes-v1/depth.py collect
run_cr.sh kaggle/campaigns/depth-probes-v1/depth.py run --deadline 1792302300 --kill-at 1792303020   # 11:15 / 11:27 IST
run_cr.sh kaggle/campaigns/depth-probes-v1/depth.py summarize
```

**Witnesses are EVAL-ONLY.**
- `depth.py` reads each witness netlist from its existing file at run time, via `a0.witness_tokens`.
- Witness tokens, and the sized netlist bodies of all designs, are persisted only under `state/`. That directory is
  gitignored and is not committed.
- Worker job files that carry tokens are written to `state/raw/` and deleted after each call.
- ngspice scratch decks live in the job temp dir (`~/.claude/jobs/7cd7ffc3/tmp/depth/tmp`) and delete themselves.
- Committed outputs carry token hashes, margins and metrics only. Nothing here may be put into an LLM prompt.

## Deviations / interpretations

- **D-P1: eligible set and A rows.** These reuse bench-v3 `a0.py` by import (unmodified): `eligible_tasks`,
  `spec_for` and `witness_tokens`. The eligible set is the 35 non-T1 items of `pilot-v0/eval/tiers.json`.
  - A = library a1–a5 ∪ every round-trip-valid single edit of the shown anchor (`pv0.load_f2space`).
  - Each design's row is looked up by exact key `bv2.job_id(tokens, spec, 1, 2500, "rl-v1.2")`.
  - Lookup is in the union cache `ga.load_caches` (pilot-v0 P0 + AMENDMENT-3 raw rows first, as in a0 D-A2), plus
    the GA results and the Opus score rows.
  - "Feasible" = the row's full feasibility flag (rl-v1.2, including port-DC).
  - Duplicate token keys are counted once. Missing rows: 0.
- **D-P2: "A's enumerated space".** It is the token keys of the 5 anchors plus every round-trip-valid single edit
  of the shown anchor, whether or not that edit was sized or feasible. A candidate B design with such a key is
  dropped (`B_in_A_space` in `pools.json`).
- **D-P3: B sources and labels, taken literally.**
  - GA: every sized seed-1 call of `baselines-v1/ga/run` whose row is feasible.
    - `runs.jsonl` stores tokens only for each run's `found` design. Every other call is replayed from its recorded
      origin (parent text + edit descs through `ga.edit_space`, the GA's own operator).
    - Each replay is verified against the recorded token key: 986 replays, 0 mismatches.
  - exit-r1: only labels `r1-8` and `r2-8`. `r1-2` and `r2-2` are excluded.
  - pilot-v1: only `h1-sft300` and `h1-sft1000`. `mix1000` is excluded.
  - pilot-v0 P1: every label (`zs`, `sft100`, `sft300`, `sft1000`).
  - baselines-v1 Opus: only `opus-4`. `opus-2` is excluded.
  - Tokens come from each campaign's `cand.json`, with key == `tokhash(tokens)` asserted.
  - A design found by several sources is one design, with its sources merged.
  - B membership requires the design's seed-1 rl-v1.2 row at the task spec (exact key) to be feasible.
- **D-P4: witness.**
  - The witness is used at seed 1 when its seed-1 row is feasible. Otherwise its seed-2 row is used, by exact key.
  - The seed-2 case covers 6 tasks: nb090-noise-0269, -0291, -0350, -0375 and wb1020-gain-0109, -0160. All 6 are
    feasible at seed 2.
  - For these 6 the re-size is at **seed 2**, the seed of the row. The design is infeasible at seed 1, so a seed-1
    re-size would not give the feasible witness the pre-reg asks for.
  - No witness key is in A's space.
- **D-P5: cap.** The "6 distinct designs with the highest original worst margin" cap is applied to the whole pool,
  witness included.
  - The original worst margin is `pv0.Runner.margin` of the cached row: `MS._margins` plus µ_wide − 1, the a0 D-A9
    definition. Ties go to the lower token key.
  - The witness falls outside B's top 6 on 9 tasks: nb090-noise-0269 and wb1020-gain-0010, -0045, -0065, -0067,
    -0108, -0159, -0161 and -0207. `pools.json` → `witness.selected` records this, and the unselected designs are
    listed per task.
  - Most wideband margins are ≈ 0.000x, because the sizer spends the slack (bench-v3 A0). So this ranking is weakly
    informative there.
- **D-P6: sizing and parameter capture.** The cached rows carry no sized parameters, so every selected design is
  re-sized once. No cache reuse is possible.
  - The re-size uses EX `ex_lib.sized_run_v11(tokens, spec, seed, profile="rl-v1.2")`. That is
    `bench_anchor_prep.smoke_run(tokens, spec, seed, 2500, "bptm45", profile="rl-v1.2")` verbatim, the bv2/pv1_score
    worker path, with EX's read-only capture of the final winner's params (the stability replacement if any, else
    the best x).
  - EX captures the body before rl-v1.2's `VERIFY_CP_IDEAL` rewrite. So the measured body is
    `PREP.cp_ideal_body(captured)`, the exact in-loop body.
  - Check: a nominal re-evaluation (EX `full_eval`) of (body, params) is stored with every corner row and reproduces
    the sized metrics.
  - The re-size is deterministic: the re-sized worst margin is compared with the cached one (see Result).
- **D-P7: corner worst margin (signed).** EX `corner_eval` reports violations clipped at 0, which cannot rank designs
  that pass. So it is used for the simulations only:
  - `.option temp=-40/85`, or `pVDD × 0.9/1.1`.
  - The full spec metrics, with NF at the temperature corners measured with the source resistor held at 27 °C, as
    EX does.
  - µ in-band and µ wide over the rl-v1.2 window, which equals the rl-v1.1 window (asserted).
  - From these, the signed margin per corner = min over the supported constraints except `mu_min` (MS._margins
    definitions and scale), µ_inband − 1 and µ_wide − 1.
  - A missing or NaN metric, or a failed simulation, counts as −1.0, which is EX's violation 1.0.
  - Corner worst = min over the 4 corners. "Passes all corners" = corner worst ≥ 0.
  - EX's 2 %-cushion flags are recorded but not used. The binary port-DC requirement is not part of the margin.
- **D-P8: IIP3.** The harness is `size.measure_iip3_tier3(body, params, spec)` with its defaults (the lna/iip3.py
  two-tone harness).
  - Tones at the spec band f0. For wideband specs this is the band's f0.
  - Pin −80…−40 dBm in 6 points, DF 2 MHz, tmax 5 ps, SNR ≥ 10 dB, compression ≤ 0.5 dB, slope-3 intercept.
  - It runs on the rl-v1.2 body, the same body that was used for feasibility.
  - `iip3.OUT` is patched at run time to the job temp dir, so `private_tmp` scratch does not land in `lna/out/`.
    No code was modified.
  - A failed measurement (`ok: false`) is recorded and excluded from best-of-pool.
- **D-P9: usable designs.** Only designs whose re-size is feasible and yielded params enter best-A or best-B.
- **D-P10: task order.** Tasks always run in the seeded random order `random.Random("depth-probes-v1")`, over the
  sorted task list. The pre-reg asks for this only if the projection exceeds the window; using it anyway is
  harmless when the run completes.
  - The 3-task smoke = the first 3 tasks of that order, so it forms part of the uniform prefix.
  - Stages are prioritized by task order, so a cut leaves complete tasks.
- **D-P11: readings.**
  - Computed over tasks with non-empty A and B whose selected designs are all measured (`complete`).
  - A metric needs a measured value in both pools: an IIP3 failure on every design of a pool would drop the task
    from that metric.
  - The control (A beats B) uses mirrored thresholds: A ≥ B + 0.10, or A passes all corners while no B design does;
    A ≥ B + 3 dB for IIP3.
  - "Gives depth" needs ≥ 10 tasks **and** B > A more often than A > B.
- **D-P12: scheduler.** `ga.Sched` cannot be reused unchanged, because its worker discards the sized params. An
  equivalent runner applies the same rules:
  - At most 8 heavy processes box-wide. Other jobs' `bv2.py worker` processes and other runners' `depth.py worker`
    processes are counted from /proc. The cap drops to 4 while load1 > 22.
  - No launch below the bv2 disk floors (5 GB on the output filesystem, 1 GB on TMPDIR).
  - Every stage (S = size, C = nominal + 4 corners, I = IIP3) is its own single subprocess, and its ngspice calls are
    sequential.
  - `--deadline EPOCH`: no stage job is launched at or after it. `--kill-at EPOCH` (default deadline + 12 min):
    running workers are killed with SIGKILL on their process group and write no row.
  - Exact-key resume: S is keyed by bv2 `job_id`; C and I are keyed by the same jid per stage file.
  - CPU per job = getrusage (self + children) of the worker.
- **D-P13: IIP3 sanity check** (pre-reg: 3 designs first). It was run on the top-ranked B design of the first 3
  ordered tasks, before the smoke; results below.

## RESULT (2026-10-18 03:53 IST; written by the parent session — the runner's agent died on a network error mid-run, the run itself completed)

Run complete before the pause window: 296/296 designs re-sized (all reproduce the cached feasibility and worst margin
within 1e-4), corners 296/296, IIP3 293/296 ok (292 with two-tone slope 3 ± 0.3). CPU 8.59 h. 32/35 tasks have
non-empty A and B (the 3 T3 tasks have no feasible A by construction).

| metric | eligible | B beats A | A beats B (control) | pre-declared verdict |
|---|---|---|---|---|
| corner worst margin (+0.10, or B passes all corners and no A does) | 32 | 4 | 2 | **no depth** (< 5) |
| IIP3 (+3 dB) | 32 | 5 | 8 | **no depth** (weak count, and the control fails: A > B more often) |

Readings and caveats:
- No design in either pool passes all four corners (every corner worst margin < 0; W3 again). The probe evaluates
  corners **on the nominal sizing without re-sizing**; the sizer has driven some nominal constraint to ~0 slack (the
  A0 lesson), so corner margin here mostly measures how far a nominal-optimal sizing falls off, not what a topology
  could reach if sized for corners. Same for IIP3: measured on small-signal-optimal sizings, not linearity-aware ones.
  So the result is "no depth in **as-sized** corner/linearity behaviour", not a proof that robustness- or
  linearity-aware sizing would show no depth (that would need multi-corner / IIP3-in-the-loop sizing, ~5x the cost
  per call).
- nb090-noise designs have very poor IIP3 (-15 to -40 dBm) vs wb1020-gain (about 0 dBm); the large B > A gaps (0322
  +22.9 dB, 0411 +15.0 dB) are tasks where pool A has only one feasible design.
- With the bench-v1.2 audit, bench-v2, exit-r1/r2, baselines-v1 and bench-v3 A0, this is the fourth independent sign
  that the LNA space under this verifier (bptm45, <= 2 L on wideband, ideal biasing, small-signal spec) is shallow.

> **⚠️ SUPERSEDED (2026-09-25).** This describes the OLD bench-v1 (gf180, 53
> survivors, LNA-only). It was re-based to native 45 nm (bptm45); the live
> benchmark is now **bench-v1.2** (`editcap-lib-v12-45nm/`, 16 achievable cells).
> See `CURRENT-STATE.md` and `PLAN-topology-selfimprovement.md`. Kept for history
> (the PA/mixer/balun-deferral reasoning below is still valid).

# editcap-bench-v1 — FROZEN 2026-09-18: LNA class only

**bench-v1 = the LNA topological-challenge set: 53 survivor cells / 22 excluded
(of 75).** User ruling 2026-09-18: ship LNA-only now; PA + mixer + balun deferred
to v1.1 (reasons below). This is a complete, valid benchmark deliverable.

## What bench-v1 is

75 candidate LNA specs (kaggle/bench-specs/lna/) each run through the frozen
null-filter: a sizing-only CMA null, 3600 evals/cell = seeds (1,2,3) × 1200,
no-escalate, against the cell's class anchors (5 LNA families,
kaggle/bench-anchors/lna/), pdk=gf180mcu. **Survivor iff NO (anchor, seed) run
reached feasibility** — i.e. a dumb sizer on a known-good anchor cannot solve
it, so the cell is a genuine TOPOLOGY challenge (the benchmark's purpose).
Verdicts in kaggle/bench-null/INDEX.json.

- **53 SURVIVORS (kept):** the topology-challenge cells (span bnl-09 900 MHz +
  harder wideband/gain/nf/power variants).
- **22 EXCLUDED (too easy):** all wider-band bnl-24/35/58 (2.4/3.5/5.8 GHz)
  diag/gain/power/lown variants — a tuner reaches these on the anchor alone.

Engine = bench_anchor_prep.smoke_run verbatim; era-bnull-* stamped per result;
sim-health clean (0 fails); goldens GREEN.

## Why LNA-only (the other three classes' status)

- **PA — SOUND but deferred (infrastructure, not science).** PA is a valid,
  reachable class (PAE hit 17.7% vs a 15% target in a trustworthy probe; a
  single seed completes in ~20 min standalone). BUT completing the 150-pair
  null on this shared box is bottlenecked: the repo is on NFS, and ~6-10
  concurrent legs block on I/O (56% idle cores, legs sleeping) so pairs stall.
  Deferred to v1.1, to be run at low concurrency or with off-NFS scratch.
  20/150 pairs completed (all survivors so far) live under kaggle/bench-null/pa/
  as partial evidence — NOT part of bench-v1.
- **mixer / balun — deferred, need target recalibration (not new anchors).**
  Root-caused: their +12 dB gain targets are physically UNREACHABLE on gf180 for
  ANY sketch (mixer single-ended-IF active mixing is conversion-LOSS, ~−9 dB
  best; balun bl-a1 already IS the canonical Blaakmeer gain topology, ~−1 dB
  balanced). A new mixer sketch (M1 current-reuse, kaggle/bench-anchors-v11/)
  scored WORSE (−18 dB). A PDK switch to native 45nm helps only +4-6 dB, still
  short. So v1.1 fix = recalibrate targets to the gf180-reachable envelope
  (mixer conv_gain ≥ ~−12 dB; balun sds21 ≥ ~+3-5 dB with looser NF/CMRR), NOT
  new sketches. Their on-disk null results are INVALID (a fixed nf bug +
  unreachable targets) and are NOT part of bench-v1. Balun nf bug fixed
  (c5d7d4db) for when v1.1 runs.

## v1.1 backlog (queued)

1. PA null completion — low-concurrency / local-scratch run of the 130 remaining
   pairs; fold PA cells into the benchmark.
2. mixer/balun target recalibration (user ruling on the exact new targets) +
   re-run their nulls with the balun nf fix.
3. (optional) gain-capable mixer anchor exploration — deprioritized; the
   evidence says recalibration is the real lever, not sketches.

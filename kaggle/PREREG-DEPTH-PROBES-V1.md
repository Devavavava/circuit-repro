# PRE-REG — depth probes v1: does linearity or corner robustness reward designs beyond one edit?

**Frozen:** 2026-10-18 01:45 IST, before any result. **GO:** user ("go ahead … I'll authorize any reasonable
experiment … always draw only from my subscription … make long tasks pause around 10 hours from now").
Local CPU only (no Kaggle, no paid API). **Hard pause: no new job starts after 11:15 IST 2026-10-18; everything
stopped cleanly and resumable by 11:30 IST**, with the resume command written in the README.
Branch `worktree-externals-gf180`. Outputs: `kaggle/campaigns/depth-probes-v1/`.

## Why

bench-v3 A0 (b7c0cc7c): on the held-out non-T1 tasks, library + one edit of the shown anchor matches the planted
witness even on the flavor metric (29/35). Under the current spec (small-signal S11/S21/NF/Idd/stability at
27 °C) the LNA space looks shallow. Two physically important properties are not in the spec: **linearity**
(IIP3; harness `lna/iip3.py`, `lna/size.py:943 measure_iip3_tier3`, never gated) and **PVT robustness**
(−40/+85 °C, VDD ±10%; `adversarial-v0/EX/ex_lib.py:350 corner_eval`; W3 waived it because only 4/1027 designs
pass). If designs beyond one edit are clearly better on either, that metric gives the bench depth.

## Population (35 tasks = the A0 eligible set: every non-T1 held-out task)

Per task, two pools of **already-found designs feasible at seed 1 under rl-v1.2 at the original spec**:
- **A (within one edit):** library anchors a1–a5 and single edits of the shown anchor (pilot-v0 P0 tiering rows;
  AMENDMENT-3 rows for the strict cells).
- **B (beyond one edit):** the planted witness (if feasible at seed 1; else its seed-2 row, recorded) and every
  other feasible design from existing scored runs whose token key is NOT in A's enumerated space: baselines-v1
  GA (`ga/run`), exit-r1 sft-r1 (`score/r1-8`), exit-r2 sft-r2 (`r2-8`), pilot-v1 H1 sft300/sft1000, pilot-v0 P1,
  baselines-v1 Opus (`opus-4`).
- Cap per pool per task: the 6 distinct designs with the highest original worst margin (ties by key). Tasks with
  an empty A or empty B are reported but excluded from the depth rates.

## Measurements (per design, at the task's original spec)

Re-size each design at seed 1 (rl-v1.2, 2500 evals; exact-key cache reuse allowed if it yields the sized
parameters) to obtain its sized parameters, then without re-sizing:
- **Corners:** EX `corner_eval` at −40 °C, +85 °C, VDD×0.9, VDD×1.1. Corner worst margin = min over the 4
  corners of the spec's worst normalized margin (performance) and of µ−1 (stability), as EX defines it.
- **IIP3:** in-band IIP3 (dBm) with the repo's two-tone harness, its default settings; sanity check first on
  3 designs (value in a plausible range, finite, slope check if the harness reports it); failures recorded.

## Readings (per metric, over tasks with non-empty A and B)

- **Depth on corners** for a task iff best-B corner worst margin ≥ best-A + 0.10, or best-B passes all corners
  (worst ≥ 0) while no A design does.
- **Depth on IIP3** for a task iff best-B IIP3 ≥ best-A IIP3 + 3 dB.
- Metric **gives depth** iff ≥ 10 tasks show it (and report the fraction); 5–9 ⇒ weak; < 5 ⇒ no depth from this
  metric. Also report the reverse (A beats B by the same thresholds) as a control — depth needs B > A more often
  than A > B.
- Positive ⇒ propose (for user review) bench-v3b with that metric as the objective, stretched as in
  PREREG-BENCH-V3 §8 but without any slack requirement on other constraints (the A0 lesson).

## Budget

≤ 12 designs × 35 tasks = 420 designs; ~1 sizing call (~90 CPU-s) + 4 corner evals + 1 IIP3 run each.
Estimate 20–35 CPU-h ≈ 3–5 h wall at 8 processes. ≤ 8 sizing processes on the box (4 if load1 > 22).
If the projection after a 3-task smoke exceeds the pause window, run tasks in seeded random order so a cut
leaves a uniform subset, and record it.

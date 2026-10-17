# PRE-REG — depth probes v1b: uniform-cushion sizing (does required slack reward designs beyond one edit?)

**Frozen:** 2026-10-18 04:05 IST, before any v1b result. **GO:** user's overnight authorisation ("any reasonable
experiment … subscription only … pause ~10 h from now"). Local CPU only. **Hard pause: no job starts after
11:15 IST 2026-10-18; all stopped and resumable by 11:30 IST.** Outputs: `kaggle/campaigns/depth-probes-v1b/`.

## Why

depth-probes-v1 (6069adb59) found no depth in corner margin or IIP3, but measured both on nominal sizings in
which the sizer has spent all slack (every design fails corners). The open question it leaves: if the spec
*demands* slack, do designs beyond one edit keep feasibility where library / single-edit designs lose it? This
is a uniform-headroom test and a proxy for robustness-aware sizing, with no shared-code change.

## Design

- Same 32 tasks and the same pools A (within one edit) and B (beyond one edit) as depth-probes-v1
  (`depth-probes-v1/pools.json`, ≤ 6 + 6 designs per task).
- **Cushioned spec C(c):** every performance limit of the task's original spec (S11 max, S21 min, NF max, Idd
  cap, S21 ripple if present) tightened by c × that metric's normalization scale (the scale `MS._margins` uses),
  in the stricter direction; stability (µ ≥ 1 in band, µ_wide ≥ 1), port-DC and topology limits unchanged.
  c ∈ {0.10, 0.20}. Written as new spec files (sha256 recorded).
- Re-size every design at C(0.10) and C(0.20), seed 1, rl-v1.2, 2500 evals (same worker path as v1).
- For every design feasible at C(0.20): corner worst margin on that sizing (EX `corner_eval`, −40/+85 °C,
  VDD ×0.9/×1.1), to see whether demanded slack buys corner robustness.

## Readings (pre-declared)

- Per task and c: **B-only** = some B design feasible at C(c) and no A design; **A-only** = the reverse.
- **Depth from required slack** iff, at c = 0.10 or c = 0.20, B-only ≥ 10 tasks AND B-only > A-only; 5–9 ⇒ weak;
  < 5 ⇒ none. Also report: tasks where nothing survives C(c) (the cushion is simply too hard).
- Corner add-on (descriptive only): number of designs feasible at C(0.20) that pass all four corners, by pool.
- Positive ⇒ propose (for user review) a bench whose tasks demand uniform slack c* with the reading's c.

## Budget

≤ 296 designs × 2 cushions ≈ 592 sizing calls (~90 CPU-s) + corners for the C(0.20)-feasible ones:
≈ 15–20 CPU-h ≈ 2–3 h wall at 8 processes (≤ 8 sizing processes on the box; 4 if load1 > 22).

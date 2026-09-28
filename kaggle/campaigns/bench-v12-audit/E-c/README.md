# E-c: brute-force single-edit search (the "dumb search" bar)

This is experiment E-c of `kaggle/PREREG-BENCH-V12-AUDIT.md` (frozen 2026-09-26).
- Era stamp (git HEAD at start): `cc5a836bb26fbfef4f128777945ebdae39c3fb66`
- Run: 2026-09-26 13:30:16 to 20:29:43 +0530, about **7.0 h wall** at 8 processes.
- Total sizing time: 55.3 process-hours over 2792 sizing calls (2168 screen + 624 confirm). No worker crashed or timed out.

## Verdict

**All 16/16 bench-v1.2 cells are SEARCH-TRIVIAL.** In every cell, at least one single primitive edit of the SHOWN anchor is confirmed feasible. Confirmed means feasible at seed 1 × 2500 with the deterministic re-run matching. Under the pre-registered decision rule, an LLM that solves a bench-v1.2 cell counts as showing topology reasoning only if it gets there in fewer SPICE-minutes than this search.

- **Wideband (8 cells).** Each cell has 8 to 38 confirmed feasible single edits, 196 in total. The template move `R Rf n2 n1` appears as `add R n1-n2` and is found in all 8 cells, but it is only one of many. Other feasible edits include resistive feedback from other nodes (`n1-n4`, `n0-n2`, `n2-n3`, `n2-n5`, ...), input shunt inductors or resistors (`L VIN1-VSS`, `L VDD-VIN1`, `R VIN1-VSS`), an input-to-output resistor (`R VIN1-VOUT1`), and more. The expected number of sizing calls to the first feasible edit under random order is **4.5 to 19.7**.
- **Narrowband (8 cells).** The shown anchor is a5 common-gate. One edit, `add L VIN1-n1` (an inductor from the input to the CG gate node), is confirmed feasible in all 8 cells: 3/3 seeds in 5 cells and 2/3 in 3. The two f24-g12/g14 cells also accept `add L VIN1-n2` and `add L VOUT1-n0` (1/3 seeds each). The expected number of sizing calls to the first feasible edit is 23 to 46.

## Per-cell table

Column definitions:
- `calls`: number of seed-1 sizing calls (×2500 evals).
- `fixed`: the pre-registered fixed enumeration order.
- `E[random]`: exact expectation under a uniformly random order of the sized candidates, `(N-K)/(K+1)+1` calls. The SPICE-minute version is `Σ_infeasible c_i/(K+1) + mean_feasible c_j`.
- `stable`: confirmed edits whose winner has `mu_min ≥ 1`. This is descriptive only; stability is not a spec constraint.
- `no-L`: confirmed edits that do not add an inductor.

The full lists of feasible edits and per-seed pass counts are in `table.md` and `summary.json`.

| cell | gen / rt-valid / sizable | confirmed (3/3 seeds) | stable | no-L | calls to 1st: fixed / E[random] | SPICE-min to 1st: fixed / E[random] | exhaust SPICE-min | SEARCH-TRIVIAL |
|---|---|---|---|---|---|---|---|---|
| wb-s11n10-g10-b0530 | 179/178/176 | 8 (4) | 4 | 4 | 43 / 19.7 | 56.2 / 26.0 | 232 | YES |
| wb-s11n10-g10-b0824 | 179/178/176 | 38 (24) | 9 | 20 | 3 / 4.5 | 4.2 / 6.4 | 249 | YES |
| wb-s11n10-g12-b0824 | 179/178/176 | 32 (18) | 3 | 15 | 3 / 5.4 | 4.2 / 7.8 | 255 | YES |
| wb-s11n11-g10-b0824 | 179/178/176 | 32 (21) | 9 | 16 | 3 / 5.4 | 4.4 / 7.4 | 243 | YES |
| wb-s11n11-g12-b0824 | 179/178/176 | 25 (14) | 5 | 11 | 3 / 6.8 | 3.3 / 7.4 | 192 | YES |
| wb-s11n8-g10-b0530 | 179/178/176 | 28 (21) | 6 | 17 | 1 / 6.1 | 1.1 / 6.6 | 191 | YES |
| wb-s11n8-g12-b0530 | 179/178/176 | 14 (6) | 2 | 7 | 39 / 11.8 | 42.0 / 15.1 | 225 | YES |
| wb-s11n9-g10-b0530 | 179/178/176 | 19 (9) | 6 | 11 | 31 / 8.9 | 33.5 / 10.2 | 202 | YES |
| nb-f15-g12 | 93/93/91 | 1 (1): add L VIN1-n1 | 0 | 0 | 33 / 46 | 22.0 / 31.1 | 62 | YES |
| nb-f15-g14 | 93/93/91 | 1 (1): add L VIN1-n1 | 0 | 0 | 33 / 46 | 21.8 / 30.5 | 60 | YES |
| nb-f15-g16 | 93/93/91 | 1 (1): add L VIN1-n1 | 0 | 0 | 33 / 46 | 22.1 / 31.3 | 62 | YES |
| nb-f15-g18 | 93/93/91 | 1 (1): add L VIN1-n1 | 0 | 0 | 33 / 46 | 21.8 / 30.5 | 60 | YES |
| nb-f24-g12 | 93/93/91 | 3 (1): L VIN1-n1 3/3; L VIN1-n2 1/3; L VOUT1-n0 1/3 | 1 | 0 | 33 / 23 | 21.8 / 15.7 | 62 | YES |
| nb-f24-g14 | 93/93/91 | 3 (1): L VIN1-n1 3/3; L VIN1-n2 1/3; L VOUT1-n0 1/3 | 0 | 0 | 33 / 23 | 22.0 / 15.5 | 61 | YES |
| nb-f24-g16 | 93/93/91 | 1 (0): add L VIN1-n1 2/3 | 0 | 0 | 33 / 46 | 22.6 / 32.4 | 64 | YES |
| nb-f24-g18 | 93/93/91 | 1 (0): add L VIN1-n1 2/3 | 0 | 0 | 33 / 46 | 24.1 / 34.1 | 68 | YES |

- **Candidates that were not sized.** The wideband anchor has one round-trip failure: `del L L1` (no Eulerian token path). Each cell has 2 unsizable candidates, which are the deletions that disconnect a port: `del C4` / `del C3` for wideband and `del C1` / `del C2` for narrowband.
- **Determinism.** 208/208 seed-1 confirm re-runs are bit-identical to the screen (the metrics dicts are equal).

## Notable observations and near-misses

- **Most wideband solutions are unconditionally unstable (`mu_min < 1`).** Only 44 of 196 confirmed wideband edits are stable. In some cells the template move `add R n1-n2` itself lands at `mu_min < 1`. The narrowband `add L VIN1-n1` solution is unstable in all 8 cells (`mu_min` 0.27 to 0.66).
  - Stability is not part of the bench spec, so this does not change the verdict.
  - If unconditional stability were required, 9/16 cells would still be SEARCH-TRIVIAL: all 8 wideband cells plus nb-f24-g12 (`add L VOUT1-n0`).
- **Margins are razor-thin**, consistent with the audit. The worst normalized margins of the feasible edits are mostly 1e-5 to 1e-2, usually binding on `s11_max_db` (wb) or on `s11_db` / `nf_db` (nb).
- **Wideband near-misses** (best infeasible; margins are normalized, so -0.0011 means 0.11% of scale, and not dB):
  - wb-s11n8-g12: `add R n2-n3` −0.0011, `add R n3-n4` −0.0015, `add R n0-n2` −0.0024 (all binding on `s21_db`)
  - wb-s11n10-g10-b0530: `add L VIN1-n1` −0.0086 (`s11_max_db`)
- **Narrowband near-misses are far.** The best infeasible candidates are −0.10 to −0.49 on `s21_db`, typically `add C VIN1-n1`, `add C VDD/VSS-n1`, `add L VOUT1-n0` or `add L VIN1-n2`. The shown CG anchor lacks gain, and only the input-to-gate inductor (a gate-driven reconfiguration) closes the gap.
- **The spec's `max_inductors` is not enforced by the engine.**
  - `topology.max_inductors` is 1 for wideband and 4 for narrowband. It is a generator/`moves.py` constraint, and `smoke_run` does not enforce it.
  - The wideband anchor and the wideband template already hold 2 inductors, so every wideband candidate is at or above the limit. L-add edits were therefore not filtered.
  - The wideband verdict holds with R/C-only edits (the `no-L` column is ≥ 4 in every wideband cell).
  - For narrowband, L-adds give 3 inductors, which is within the limit of 4.

## Commands

```
kaggle/campaigns/bench-v12-audit/E-c/run_ec.sh gen                                   # enumerate + round-trip -> candidates.jsonl
EC_ERA=cc5a836bb... kaggle/campaigns/bench-v12-audit/E-c/run_ec.sh run 8             # screens (wb cells first, then nb) + confirms
EC_ERA=cc5a836bb... kaggle/campaigns/bench-v12-audit/E-c/run_ec.sh confirm 8 wb      # wb confirms (see Deviations)
python kaggle/campaigns/bench-v12-audit/E-c/ec_analyze.py                            # -> summary.json, table.md
```

- `run_ec.sh` exports the `crenv.sh` variables inline and sets `TMPDIR=/tmp/cr-7cd7ffc3-c`.
- Each sizing call runs in its own subprocess (`ec_search.py worker CELL CID SEED`) with a 1800 s timeout. It calls `bench_anchor_prep.smoke_run(tokens, spec, seed, 2500, "bptm45")`, reads feasibility from `result["feasible"]`, and computes margins with `mysolve._margins`.
- Results are appended per call to `results.jsonl`, which makes the run resume-capable.

**Enumeration order.**
- Nets are sorted with Python string sort, and unordered pairs are generated with `itertools.combinations`.
- For each pair, the element types are tried in the order R, C, L. The new element is appended to the anchor as `TYPE {R,C,L}x a b`.
- Deletions come last, in anchor line order.
- Candidate `cid = <anchor md5[:12]>:<order>`.

**Files:**
- `candidates.jsonl`: each candidate's netlist, round-trip result and tokens.
- `results.jsonl`: every sizing call, with era, phase, secs, feasible, worst, margins and metrics.
- `summary.json` and `table.md`: the analysis.
- `run*.log`: driver logs.

## DEVIATIONS

1. **Execution order (as instructed for runs projected past 7 h).** Screens ran wideband cells first, then narrowband. After all 8 wideband screens were done (about 3 h 45 m), the projected total was about 7.1 h. I stopped the driver, ran the wideband confirmations (`confirm 8 wb`), then resumed the narrowband screens and confirmations (`run 8`).
   - The 8 narrowband screen calls in flight at the stop were killed unrecorded and re-run from scratch. The engine is deterministic, so this has no effect on results.
2. **Seed-1 confirm is a re-run.** The confirm phase runs seeds 1, 2 and 3, and seed 1 repeats the screen as a determinism check (208/208 identical). "Confirmed" means feasible at seed 1, as the task specifies. The number of seeds that pass (0 to 3) is also reported.
3. **SPICE-minutes are wall-seconds of `smoke_run` measured under shared load.** My 8 processes plus other users ran at 1-min load 8 to 15, so a call took 30 to 110 s against about 40 s in isolation. Absolute SPICE-minutes are therefore inflated by roughly 1.5 to 2.5× for wideband.
   - I added load-independent call counts to first feasible, fixed and expected. This was not pre-registered.
   - Unsizable candidates (under 1 s each) are excluded from the costs.
4. **Extra descriptive columns were not pre-registered.** These are the stability flag (`mu_min ≥ 1`), the no-L count, 3/3-seed counts and near-misses. The pre-registered decision rule and its verdicts are unchanged.
5. **`max_inductors` is not applied as a candidate filter.** The engine does not enforce it, and the wideband anchor already violates it (see above).
6. **One positive-control call was not recorded.** Before launch I ran the worker once by hand: wb-s11n10-g10-b0530, `add R n1-n2`, seed 1, feasible, 39.9 s. It is not in `results.jsonl`; the recorded screen reproduced it.

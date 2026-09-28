# R4: verifier loophole audit (rl-readiness, pre-reg `kaggle/PREREG-RL-READINESS.md` § R4)

Run 2026-09-28 on branch `worktree-externals-gf180` (base `12f399c4b`), bptm45, `TMPDIR=/tmp/cr-7cd7ffc3-r4`, at most 6 processes (4 sizing + 2 analysis while the 1-min load was above 22).

**Verifier under audit** (the RL config):
- `bench_anchor_prep.smoke_run(tokens, stability_spec(<cell spec>), seed, 2500, "bptm45")`
- with `STAB_WIDE_INLOOP=1`: the 0.1–20 GHz / 401-point wide µ runs in-loop and as the acceptance gate.

Full numbers are in `tables.md` and `summary.json`.

## Verdict

- **Not ready as-is.**
- Two exploit classes let a policy score without a better LNA, and both have tested opt-in guards:
  - **Junk padding.** Inert devices score feasible. Guard: `VERIFY_STRUCT`.
  - **Stability-window-edge gaming.** Guard: `STAB_WIDE_WINDOW`.
- Four spec-semantics gaps need a user ruling before RL, because the reference templates themselves fail them:
  1. The wideband `max_inductors` limit.
  2. NF is checked only at f0.
  3. The narrowband S11 match is checked only at f0.
  4. Winners are razor-thin under ±5 % perturbation.
- **The 0.1–20 GHz µ gate is about right.**
  - Widening or narrowing the window rescues none of the 17 designs it rejects.
  - Its failures are real linear instabilities: they grow from a 1 µA kick under reactive terminations. They do not oscillate in the 50 Ω bench.
  - It is slightly lenient in one respect: in-loop winners moved their µ<1 region to just above 20 GHz (6/107 winners, plus 1 at 50–60 MHz).

## What was run

- **Capture driver (`r4_drv.py`).** It wraps `SZ.make_objective` for instrumentation only, which leaves the result byte-identical. It keeps the prepared body, `decode`, and every external `evaluate(x)`, so the final winner's params are known. This covers both `bx` and the gate's replacement `x`.
- **216 sizing runs.** These go into `results.json` and include bodies and params.
  - **s1 (22):** re-runs of every S-1 in-loop final-feasible row.
  - **nb (72):** new in-loop runs of the nb template, anchor a1, and the E-c edit `add L VIN1-n1` × 8 cells × 3 seeds.
  - **ed (60):** the 20 E-d feasible Qwen edits × 3 seeds, in-loop.
  - **gf (12):** gate-only wb template and a4 designs, the source of gate-rejected designs.
  - **dir (10):** E-c `add R VIN1-VOUT1`, in both lib and in-loop mode.
  - **mut (16):** mutations.
  - **reg/reg2/reg3 and win50 (24):** regression and wide-window runs.
- **`r4_post.py` per design.** Designs are the 107 stable-feasible winners plus 17 gate-rejected ones. Metrics are re-evaluated through `SZ.eval_metrics` + `wide_stability`, and reproduce the recorded ones in **107/107**. Each design gets:
  - the operating point
  - an inert-passive test
  - 10 fragility draws
  - 5 stability windows
  - the S21 peak
  - NF over the band
  - 25 terminated transients
- **Static analysis (`r4_static.py`).** No simulation. It covers every recorded solution topology: 250 unique (cell, topology) pairs.

## (a) Spec topology limits: `max_inductors` is violated by every wideband solution

| source | solutions | violate a `spec.topology` criterion | cells with ≥1 compliant solution |
|---|---|---|---|
| reference templates | 16 | 8 (all wb, `max_inductors`) | 8/16 (nb only) |
| E-c confirmed edits | 208 | 196 (`max_inductors`) | 8/16 (nb only) |
| E-d feasible Qwen edits | 20 | 20 | 0/8 |
| S-1 stable winners | 14 | 14 | 0/4 |
| stability-gate winners (nb) | 14 | 0 | 8/8 |

- No other criterion ever fails over the 250 solutions. That includes `device_budget`, `has_inductor`, `not_floating`, `single_input` and `match_plausible`.
- The cause is that the wideband spec says `max_inductors: 1`, but both the shown wb anchor and the wb reference template carry **2** inductors. **No known wideband solution is spec-compliant.**
- **Guard: `VERIFY_TOPO_LIMITS=1`.**
  - Code: `kaggle/bench_anchor_prep.py` `topo_limits` / `_topo_reject`, called at the top of `smoke_run`.
  - It runs the spec's own `Spec.structural_screen` before sizing. A violation returns `feasible: False` with `infeasible_reason` and 0 evals. A pass adds `topo_limits_ok` and `topo_limits`.
  - Tested: the wb template is rejected in 0.0 s (`max_inductors`). The clean nb template result is identical to flags-off apart from the two added keys.
- **WAIVER / USER DECISION W1.** Either raise wb `max_inductors` to 2 (the template needs it), or keep 1 and accept that bench-v1.2 wb has no known compliant solution. Until then, `VERIFY_TOPO_LIMITS` would zero every wb cell.

## (b) Degenerate structures

- **Static scan, 250 recorded solutions.** Zero hits on every detector:
  - shorted passive, MOS D=S, MOS G=S, dangling node
  - MOS without a DC current path, floating island
  - port on a rail, VIN1=VOUT1
  - every solution has an input-side and an output-side MOS
- **Dynamic check, 107 winners.**
  - No MOS is below 1 µA. 27 designs have one MOS below 50 µA, the bias-mirror reference.
  - Idd ranges from 1.28 to 9.98 mA. No near-zero-current "amplifier" appears.
  - The bias sources (`VBGEN`, via 100 kΩ) carry 0 A in every winner.
  - A proposal net named `VB1` is renamed by the round-trip, so no ideal bias-rail supply can be smuggled in.
- **Direct passive VIN1–VOUT1:** 5 E-c solutions and 3 E-d solutions, all `R VIN1 VOUT1`.
  - In the recorded lib-spec winners it is **290–413 Ω and not inert** (opening it breaks feasibility). It is port-level resistive shunt feedback: the Rf of an inverting stage, closed through the coupling caps.
  - That is a legitimate feedback LNA, but it is wide-unstable (µ 0.39–0.64) and oscillates at 2.4–3.5 GHz under short/L terminations.
  - Under the RL verifier it scores **0/5**, so the stability gate already handles it.
- **Gain from passive resonance** is impossible: a passive network gives |S21| ≤ 1, and the specs need ≥ 10 dB. No winner has an out-of-band |S21| peak more than 0.41 dB above its in-band s21.
- **Exploit found by the mutations in (f): junk that the sizer renders inert scores feasible.**
  - Examples: a MOS with all pins on VSS, a dangling R-C chain, a MOS with no DC path.
  - **Guard: `VERIFY_STRUCT=1`** (`structural_degeneracy`). It is a pre-sizing reject with 0 evals.
  - Tested: 0 false positives on the 250 recorded solutions; catches `dead_mos`, `dangling` and `vbnet` in both bands. An end-to-end run rejects the dead-MOS mutant, and a clean topology is identical to flags-off plus one key.
- **Inert passives are common in legitimate winners.** 33/107 have at least one passive that can be opened while staying final-feasible: 21 C, 14 R, 9 L, mostly bypass/bias parts.
  - **Guard: `VERIFY_NO_INERT=1`.** It is implemented but **not recommended as a hard gate**, since it rejects 31 % of legitimate winners.
  - **WAIVER W2:** use it as a diagnostic or reward penalty only, and rely on `VERIFY_STRUCT` + `device_budget` against padding.

## (c) Fragility: winners sit on the constraint boundary

10 draws per design, each sized value × (1+U[−5 %,+5 %]), with a deterministic seed.

- **Overall:** 182/1070 draws (17 %) stay final-feasible. **0/107 designs survive 10/10 draws.** 7 survive ≥5/10, and 37 survive 0/10.
  - nb winners: 23 % of draws; wb S-1 winners: 8 %; E-d wb winners: 9 %.
  - The median winner worst margin is 0.002–0.003 (normalized).
- **What breaks:**
  - wide µ: 500 failing draws. The winners sit at µ = 1.0000x.
  - s11 (point or band): 518
  - s21: 182
  - in-band µ: 170
- **Guard: `VERIFY_ROBUST=N`**, with `VERIFY_ROBUST_PCT` (default 5) and `VERIFY_ROBUST_MIN` (default 0.5). It makes N perturbed re-evaluations of the final winner and is infeasible if the passing fraction is below the minimum.
  - Tested: the nb template gives 2/10 and is rejected.
- **WAIVER / USER DECISION W3.** Every reference solution fails a ±5 % robustness gate. Enforcing it needs the in-loop version, which is a new objective term like S-1, or a margin-based reward. Otherwise RL rewards boundary-hugging exactly like the sizer does.

## (d) Stability-window sensitivity (pass = µ_min ≥ 1)

| window | stable winners pass (107) | gate-rejected pass (17) |
|---|---|---|
| 0.1–10 GHz, lin 199 | 106 | 0 |
| **0.1–20 GHz, lin 401 (gate)** | **107** | **0** |
| 0.1–20 GHz, lin 3981 (5 MHz grid) | 104 | 0 |
| 0.01–50 GHz, lin 1001 | 99 | 0 |
| 0.01–50 GHz, dec 50/decade | 100 | 0 |

- **No gate-rejected design is a window artifact.** Every one fails in every window, including 0.1–10 GHz. Their µ<1 spans start at 0.1–10 GHz (14) or below 0.1 GHz (3).
- **Window-edge gaming.** 6 in-loop wb winners (E-d ×3, E-c ×3) have µ = 0.83–0.998 at **20.5–23.4 GHz**, just outside the window the in-loop term optimizes. One more E-d winner has µ 0.985 at 50–60 MHz, below the window.
- **Grid aliasing.** 3 nb winners dip to 0.99991–0.99999 between the 50 MHz points. This is negligible. One of them (nb-f24-g16 a1) is also the 8th 0.01–50 GHz failure.
- **Guard: `STAB_WIDE_WINDOW="1e7,5e10,1001"`** (`stab_window`). It widens the window for BOTH the in-loop term and the gate, at the same ~50 MHz spacing.
  - Re-sizing the 8 window-failing cases under it: **6/8 stay feasible and are stable over 0.01–50 GHz**; 2 lose feasibility.
  - Wall time rises to about 179 s vs 158 s, roughly +13 %.
  - A flags-off template run under the wide window is still feasible.
  - **Recommend turning it on for RL.**

## (e) Actual oscillation (transient, real terminations)

- **Method.** The deck is the sized body with each S-parameter port source replaced by a termination behind the same 10 pF DC block.
  - Terminations: 50 Ω, open, short, 3 nH, 1 pF, giving 5×5 pairs.
  - Kick: 1 mA × 10 ps current impulse into VIN1 and VOUT1 at 0.2 ns, starting from the DC operating point.
  - Run: 80 ns, trap integration. Any non-decaying case is re-run for 600 ns; confirmed oscillators are re-run with gear, get f_osc measured, and are re-run with a 1000× smaller kick (1 µA).
- **Detector validation (`osc_control`).** A cross-coupled LC VCO core (µ −0.98) oscillates at 1.9 V pp under open terminations and is killed by 50 Ω. A damped copy (µ 1.007) decays.

| population | 50 Ω / 50 Ω oscillates | oscillates under ≥1 reactive pair (600 ns, gear-confirmed) | from a 1 µA kick |
|---|---|---|---|
| gate-rejected (17) | **0/17** | 5/17 (f_osc 1.9–9.4 GHz, 0.4–2.1 V pp) | 5/5 still oscillate: **linear instability** |
| stable winners (107) | **0/107** | 7/107 (all nb-f24 template/a1, 2.1–3.0 GHz, up to 2.96 V pp) | 7/7 **decay**: large-signal hard excitation only |
| lib-spec `R VIN1-VOUT1` winners (5) | 0 | 3/5 (2.4–3.5 GHz) | 3/3 oscillate |

**Verdict on the gate:**
- Gate failures are not 50 Ω oscillators; they are "not unconditionally stable".
- Under reactive source/load impedances, which is what an LNA sees from an antenna or filter out of band, a third of them are real linear oscillators even in this coarse 25-point termination set. The rest have µ 0.93–0.99, with narrow unstable regions that the set does not hit.
- So µ ≥ 1 is the right criterion for an LNA: not too harsh.
- Its blind spot is large-signal. 7 µ≈1.00002 nb-f24 winners fall into a limit cycle after a 1 mA kick, which a small-signal gate cannot see.
- **WAIVER / PROPOSAL W4:** an optional post-hoc kick-transient check. About 5 terminations × 1 s per winner, using `r4_sim.tran_deck`. It is not implemented in the verifier; the user should decide whether large-signal stability is in scope.

## (f) Other loopholes

- **NF at f0 only** (`extract.measure_nf` reads one of the 51 swept points).
  - wb: **35/44 winners exceed the NF limit somewhere in the band**, by a median of +0.30 dB and up to +1.23 dB.
  - nb: 5/63, up to +0.016 dB.
  - **Guard: `VERIFY_NF_BAND=1`** (`nf_over_band`, one extra noise sim at the winner). Tested: it rejects the S-1 winner `add L n1-n5` on wb-s11n10-g10-b0824, seed 1 (3.97 dB > 3.0; 2.97 at f0). The S-1 template winner in that cell passes (2.96).
  - **USER DECISION W5:** does wideband `nf_db` mean over the band? If yes, it also needs to be in-loop, which is a one-line `vecmax(nfv)` change in `lna/extract.py` (not touched here).
- **Narrowband S11/S21 at f0 only.**
  - **61/63 nb winners have in-band (f0 ± 2 %) S11_max above −10 dB**, by a median of +2.7 dB and up to +4.3 dB. The match is a notch at f0.
  - s21 band minimum falls below spec in 4/63.
  - **Guard: `VERIFY_BAND_METRICS=1`.** It holds `s11_db`/`s21_db` over the band using the `s11_max_db`/`s21_min_db` that `run_and_extract` already measures, so it costs nothing. Specs that already state band semantics are skipped (wb: `s11_max_db` / `s21_ripple_db`).
  - Tested: it rejects the nb template.
  - **USER DECISION W6:** rename the nb constraint `s11_db` → `s11_max_db` in the specs, which makes it in-loop with no code change, or waive.
- **NaN.** `Spec.feasible` treats NaN as satisfied, because `nan > max` is False (`nan_probe.json`). The extraction regex cannot currently produce NaN: `nan`/`inf` give None, and `-nan`/`-inf` raise ValueError, which crashes the run rather than rewarding it. So this is latent.
  - **Guard: `VERIFY_FINITE=1`.** Tested: an injected NaN s21 is spec-feasible without the guard and rejected with it.
  - The proper fix belongs in `lna/spec.py`.
- **Values at range limits.** 78/107 winners pin at least one value: C-hi 44, R-hi 39, L-hi 28 (10–15 nH at Q=12).
  - The box binds, but the values are physical. This is reported, not guarded.
- **Adversarial mutations of the templates** (seed 1, RL verifier). **13/16 mutants that should not help still score feasible:**
  - bleeder R VDD–VSS (both bands)
  - shunt C at VIN1 (both)
  - dead MOS (both)
  - output shunt RC (both)
  - tank at output (both)
  - dangling chain (nb)
  - `R VIN1-VOUT1` (wb)
  - VB-named net (wb)

  In every case the sizer either renders the junk inert (R→20 kΩ, C→50 fF) or uses it as a legitimate element.
  - With `VERIFY_STRUCT` + `VERIFY_TOPO_LIMITS`: dead-MOS, dangling and vbnet are rejected in both bands (static), and wb tank/dangling/dup_out/vbnet exceed `device_budget`.
  - The rest (bleeder, input shunt C, output tank/RC, feedback R) are electrically valid circuits that the sizer neutralizes.
  - **WAIVER W2** applies: `VERIFY_NO_INERT` flags the bleeder and the input C.

## Guards implemented (all in `kaggle/bench_anchor_prep.py`, all opt-in)

| flag | stage | function (line) | test |
|---|---|---|---|
| `VERIFY_TOPO_LIMITS=1` | pre-sizing, 0 evals | hook :203; `topo_limits` :425; `_topo_reject` :433 | rejects the wb template; clean nb identical to flags-off + 2 keys |
| `VERIFY_STRUCT=1` | pre-sizing, 0 evals | hook :208; `structural_degeneracy` :464 | 0/250 false positives; catches 3 junk classes; end-to-end reject |
| `STAB_WIDE_WINDOW=lo,hi,n` | in-loop + gate | `stab_window` :576 (used by `wide_stability`) | 6/8 window-failing cases re-solved stable over 0.01–50 GHz |
| `VERIFY_FINITE=1` | post-hoc | hook :276; `_r4_posthoc` :344 | NaN injection rejected |
| `VERIFY_BAND_METRICS=1` | post-hoc, free | `_r4_posthoc` | nb template rejected (s11_max −6.99 dB) |
| `VERIFY_NF_BAND=1` | post-hoc, 1 sim | `nf_over_band` :318 | S-1 `add L n1-n5` winner rejected (3.97 > 3.0 dB) |
| `VERIFY_NO_INERT=1` | post-hoc, ~n_passive sims | `_r4_posthoc` | bleeder mutant rejected (pC4V, pR3V) |
| `VERIFY_ROBUST=N` | post-hoc, N sims | `_r4_posthoc` | nb template 2/10 rejected |

**Flags-off regression** (`regress.json`, 33/33 identical):
- The complete `smoke_run` dict was compared with `json.dumps(sort_keys)`, excluding only `stab_inloop.wide_secs`.
- Rows compared:
  - the 22 S-1 in-loop rows re-run
  - the E-c lib row (on the keys E-c recorded)
  - the stability-gate gate row
  - the S-1 template row, re-run after each edit stage (`reg`, `reg2`, `reg3`; `reg3` is on the final committed code)
- The post-hoc hook is also a no-op with its flags unset (`guard_unit.json`).
- `lna/ref/check_ref.py`: **GREEN**. `lna/` is untouched.

## Open user decisions (before any RL round)

- **W1:** wb `max_inductors` 1 vs the 2-inductor reference.
- **W2:** inert-device penalty (not a hard gate).
- **W3:** robustness (±5 %): add an in-loop or margin reward, or waive.
- **W4:** large-signal kick check, in scope or not.
- **W5:** NF over band for wideband.
- **W6:** nb S11 over band.

Recommended on for RL now:
- `STAB_WIDE_INLOOP=1`
- `STAB_WIDE_WINDOW=1e7,5e10,1001`
- `VERIFY_STRUCT=1`
- `VERIFY_FINITE=1`
- `VERIFY_TOPO_LIMITS=1`, once W1 is ruled.

## Deviations

1. **Load.** The 1-min load reached 23.7 from others' jobs, so the sizing pool was stopped at 46 runs and resumed at 4 in parallel. The runs are resume-safe and deterministic.
2. **Mutations** used seed 1 only (the plan was seeds 1–2) to save time.
3. **Transient verdict rule tightened after the first 46 designs.** "Oscillates" had required late ≥ 0.5 × mid; it now requires late ≥ 0.95 × mid, because slow high-Q rings were mislabelled. All verdicts are re-derived from the stored amplitudes with the final rule, and every non-decay was re-run for 600 ns (`tran_long.json`, 177 cases).
4. **Termination set.** The reactive set is a fixed 25-pair grid, not a search of the unstable Γ region. It therefore under-counts real oscillators among gate failures.
5. **Extra population.** E-c 'add L VIN1-n1' (the S-1 "negative control") under the RL verifier is feasible in **17/24 runs across 7/8 nb cells**. Gate-only had 0/3 on f15-g16, so this is sizer blindness again.
6. **Guards not in the pre-reg list** (window, band metrics, NF band, finite, robust, inert) were added because each maps to a found class. Each is opt-in.
7. **Regression rows** span code stages (`reg`/`reg2`/`reg3`). `reg3` (E-c lib, stability-gate gate, S-1 in-loop) ran on the final committed `bench_anchor_prep.py`; there were no edits after it. The 22 `s1` re-runs straddled the first edits and are identical anyway.

## Files

**Drivers:**
- `r4_drv.py`: jobs, run, collect
- `one.sh`, `pool.py`, `envrun.sh`, `mkjobs.sh`
- `r4_static.py` → `static.json`
- `r4_sim.py`: helpers
- `r4_post.py` → `post.json`
- `tran_long.py` → `tran_long.json`
- `osc_freq.py`, `osc_smallkick.py`, `osc_detail.py`, `osc_control.py`
- `mkmut.py` → `mutations.json`
- `static_mut.py`, `guard_static_test.py`, `guard_unit.py`, `nan_probe.py`
- `regress_check.py` → `regress.json`
- `summarize.py` → `summary.json`, `tables.md`
- `detail.py` → `detail.json`
- `watch.py`

**Data:**
- `results.json`: 216 sizing runs, with body, params and the full result.

```
R=kaggle/campaigns/rl-readiness/R4
$R/mkjobs.sh s1 nb ed gatefail dir mut reg reg2 win50            # -> /tmp/cr-7cd7ffc3-r4/jobs_*.txt
$R/envrun.sh python $R/pool.py 4 <jobs> <log>                    # sizing (one.sh)
$R/envrun.sh python $R/pool.py 5 <raw list> <log> one_post.sh    # per-design audit
$R/envrun.sh python $R/r4_post.py collect /tmp/cr-7cd7ffc3-r4/post $R/post.json
$R/envrun.sh python $R/tran_long.py /tmp/cr-7cd7ffc3-r4/raw $R/post.json $R/tran_long.json
$R/envrun.sh python $R/summarize.py /tmp/cr-7cd7ffc3-r4/raw
```

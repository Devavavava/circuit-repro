# adversarial-v0 / EX — verifier exploiter

Pre-reg: `kaggle/PREREG-ADVERSARIAL-V0.md` § EX (commit 307673caf). Verifier under test:
**rl-v1.1** (bench-v2 AMENDMENT 2: rl-v1 + port-DC pre-filter + behavioural port-DC check).
**Nothing here changes the verifier.** Every guard below is a proposal for the user's ruling.

## Bottom line

| class | mechanism | instances (roots / topologies) | qualifies (≥ 2 independent) | proposed guard |
|---|---|---|---|---|
| **C-cp1** | the testbench's 10 pF port blocks are part of the design's matching network | 247 (144 roots / 105 topologies) | **yes** | **G-CP1**: evaluate with ideal (1 µF) coupling at both ports |
| C-osc50 | internal oscillation in the verifier's own 50 Ω bench, invisible to µ | 6 (1 root / 2 topologies) | no (one family) | candidate G-OSC50: 50 Ω small-kick transient |
| C-grid-µ | narrow µ < 1 notch between the verifier's wide-µ grid points | 1 material (+ 51 immaterial dips, min µ 0.9968) | no | candidate: finer / log wide-µ grid |
| C-oscX | oscillates only into a 3 nH load, µ < 1 just above the 50 GHz window | 1 | no | — |
| port-DC (C-pdc) | DC-grounded source changes bias | **0** | — | already closed by rl-v1.1 |
| band-metric grid (R-c on S11/S21/NF/ripple) | spec met only on the grid points | **0** (max dense–grid gap 0.0005 dB) | — | none needed |

Fragility (R-d/R-e, reported only, W3): almost every rl-v1.1 winner is sized onto the
spec and µ boundary; only 4 of 1027 passing designs stay within the 2 % cushion and keep µ ≥ 1 at all four corners; 901/1027 have a gross failure (violation > 0.10 or µ < 0.98) at some corner.

## What was run

All sizing is rl-v1.1 `smoke_run` verbatim (bptm45, 1 seed × 2500 evals) with read-only
capture patches so the final winner's parameters are known (`ex_lib.sized_run_v11`; winner =
the stability replacement if any, else the budget's best x — the same capture as
`bench-v2/motif-audit`). Reality checks run on the sized winner without re-sizing
(`ex_lib.reality_checks`):

- **R-a** realistic sources: P1 AC-coupled 50 Ω source (`Cp1 10p → 1u`); P2 DC-grounded 50 Ω
  source (`Cp1 → 1 mΩ`). Full spec metrics + the verifier's wide µ.
- **R-b** R4 method verbatim: 5 × 5 {50 Ω, open, short, 3 nH, 1 pF} source/load terminations
  behind the 10 pF blocks, 1 mA × 10 ps kick, 80 ns trap; non-decaying cells re-run 600 ns,
  confirmed oscillators re-run with a 1 µA kick. FAIL = oscillates/grows from 1 µA (linear).
  1 mA-only limit cycles are `large_signal_only` (W4: not scored).
- **R-c** 4× dense resampling: in-band sp lin 401 (verifier 101), band noise 201 (51), wide µ
  4001 points over the 10 MHz–50 GHz window (1001).
- **R-d** −40 / +85 °C (NF source resistor held at 27 °C); **R-e** VDD × 0.9 / 1.1 — fragility only.

Magnitude = worst normalized violation `(limit − value)/Spec._scale` (µ shortfall `1 − µ`);
an exploit is a verifier PASS with R-a or R-c magnitude > 0.02 (the bench-v2 2 % cushion) or
any linear R-b oscillation (D1). exploit_score = [pass] × max(R-a, R-b, R-c).

### Check validation (`results/validate.json`, `validate.py`)

| check | known cases | result |
|---|---|---|
| R-a | 9 bench-v2 L-IN-G port-DC cells must fail P2; 2 controls must pass P1 + P2 | 11/11 (P2 Idd −65…−73 %, NF max +4…+8 dB normalized 4.3–7.7) |
| R-b | 8 R4 linear oscillators fail; 7 R4 1 mA-only limit cycles not scored; VCO core fails, damped copy passes | 17/17 |
| R-c | high-Q trap between verifier grid points added to 2 nb + 2 wb clean winners must be caught; clean copies pass | 4/4 (wb: grid 0.00 vs dense 1.37–1.47; nb: grid leak 0.009–0.015 vs dense 0.038–0.040) |
| R-d/R-e | 27 °C and VDD × 1.0 reproduce nominal metrics exactly | 4/4 |

A clean anchor-family winner passes R-a..R-c (the 2 controls; the 4 R-c negatives).

### Design sets

| set | what | n | rl-v1.1 pass |
|---|---|---|---|
| strict seeds | bench-v2 rl-v1.1-feasible rows (119, re-sized, all reproduce bit-exact) + rl-readiness rl-v1 winners re-judged under rl-v1.1 (63) | 182 | 182 |
| extended record (D5) | bench-v2 rl-v1-feasible rows whose topology passes the port-DC pre-filter, not in the strict set; deterministic sha1 sample; re-sized under rl-v1.1; not search parents | 250 | 248 |
| search phase 1 | 60 generations × 16 sized children (2–4 primitive edits + repair from the population; selection v2 from gen 4, D3) | 960 sized (3085 drawn) -> 308 pass, 115 with a material failure | |
| search phase 2 (D6) | 12 generations × 16, parents restricted to roots without an R-b instance, R-b-proximity tournament | 192 sized (428 drawn) -> 84 pass, 7 with a material failure | |
| guard-impact set (D7) | witnesses of the 14 bench-v2 cells currently `accepted` + the 280 `ok` training tasks, re-sized at their recorded seed on their own spec (79 reused from the sets above) | 294 | 4 cells + 280 training |

10 of the 14 `accepted` cells are pre-amendment cells whose topology FAILS the rl-v1.1 port-DC
pre-filter (they are pending bench-v2's own re-evaluation); they are outside the guard counts.

## Exploit classes

### C-cp1 — the harness's 10 pF DC blocks are part of the matching network (QUALIFIES)

**Plain language.** The verifier's testbench connects the 50 Ω source and load through
10 pF series capacitors (`Cp1`, `Cp2`). They were put there to keep the 50 Ω ports from
upsetting the circuit's bias. At the bench frequencies these capacitors are not small:
10 pF is 32 Ω at 500 MHz, 18 Ω at 900 MHz, 6.6 Ω at 2.4 GHz — comparable to the 50 Ω source.
The sizer therefore tunes the circuit's own input/output networks *together with* those
test-fixture capacitors. Almost every design already has its own input DC block (1024/1027), and
the sizer usually drives it to its 10 pF ceiling, so the effective series capacitance seen
in the verifier is ≈ 5 pF, not the ≈ 10 pF a real source connection gives (≥ 9.5 pF in 78 %
of C-cp1 instances, 62 % of the other designs). Replace the fixture with an ideal coupling
(what an antenna/filter with a large DC block, or a DC-isolated 50 Ω source, looks like) and
the match/noise trade moves (input side alone): S11 max shifts by 1–4 dB (worse by 0.7–1.2 dB
in the wideband probe winners, better in many training witnesses), NF / NF max +0.1…0.26 dB,
gain ripple +0.1…0.44 dB; whichever constraint was binding breaks. The design was co-designed with a part of the test fixture
that will not exist on a real board.

**Evidence.**
- R-a P1 (source side only) fails materially in 247 of 1027 verifier-passing designs;
  P2 (DC-grounded) never adds anything beyond P1 (0 designs with P2 > P1 + 0.02): it is the
  capacitor's reactance, not port DC. Worst metric: S11 max 95, NF@f0 58, NF max 42, S21 ripple 52.
- Frequency trend (the reactance argument): material share by band nb090 77/149, wb0530 29/74, wb0824 61/115, wb1020 42/90, nb158 10/111, nb240 6/120, nb350 2/160 — high at
  0.5–1 GHz, near zero at 3.5 GHz.
- Output side (diagnostic D8, `harness_diag.py`): `Cp2 → 1 µF` alone fails 589/1027 strictly, 367 materially;
  both blocks ideal (`P1io`) fails 355/1027 strictly, 264 materially (the two fixture effects partly cancel).
- Recoverable (D9, `resize_cp1.py`): re-sizing the same topology once with ideal coupling at
  both ports meets the spec for 34 of 41 (the failing accepted cell + a deterministic sample of 40 failing training witnesses); 7 training witnesses (4 nb090, 1 nb240, 2 wideband) do not re-size feasibly at one seed — the guard removes the fixture crutch, not capacity.

**Proposed guard G-CP1.** Evaluate the verifier testbench with ideal coupling at both ports
(`Cp1`, `Cp2` → 1 µF, or 10 pF ∥ 1 µF so the port-DC check's anchor line is unchanged; that is
how `resize_cp1.py` does it). Port DC stays covered by rl-v1.1's pre-filter + behavioural check
(the DUT carries its own DC block in 1024/1027 passing designs). Input-only variant G-CP1in
(`Cp1` only) is the pre-registered R-a; the both-ports variant is recommended because the
output fixture matters more (diagnostic above).

**Impact if adopted (no re-sizing; strict = any violation, material = > 0.02):**

| set | rl-v1.1 pass | G-CP1in strict / material | G-CP1io strict / material |
|---|---|---|---|
| accepted bench cells | 4 of 14 | 1 / 1 (v2b-wb0530-noise-166) | 1 / 1 (v2b-wb0530-noise-166) |
| training witnesses | 280 of 280 | 95 / 70 | 121 / 91 |

With re-sizing under the guard (D9 sample): 34 of 41 become feasible again, so most affected
tasks stay solvable and only need an honest re-size (bench-v2 would re-validate them); 7 of 40
sampled training witnesses (~18 %, so ≈ 20 of the 121) would likely lose their witness.

### C-osc50 — internal oscillation the µ test cannot see (does NOT qualify: one family)

S014 (bench-v2 nb350-noise confirm/search winner) and 5 search descendants (2 topologies):
oscillate at 18.5–24 GHz in the verifier's own 50 Ω/50 Ω bench from a 1 µA kick (600 ns, trap).
`results/rb_diag.json` (4 of them): a 4× finer time step confirms 4/4, gear integration 3/4
(G018-01 decays under gear's numerical damping); µ on the verifier grid ≥ 1 and µ within ±20 %
of f_osc (801 points) ≥ 1.00005. Mechanism (`osc50_mech.py`,
`results/osc50_mech.json`): the cascode transistor's gate is not AC-grounded — it shares the
inter-stage node that is fed from the cascode's own drain through the series C–L coupling to
the second stage. That is a feedback loop around the cascode device (a gate-inductance
common-gate oscillator). Cutting only that gate path (gate to a 10 kΩ/100 pF RF-grounded node,
same DC bias) stops the oscillation in 6/6; making the ports ideal does not (6/6 still
oscillate). Why the verifier passes it: Rollett/µ tests are valid only if the two-port has no
right-half-plane poles with 50 Ω terminations; AC/S-parameter analysis computes finite
S-parameters around an unstable bias point and never checks that premise.
Phase 2 (D6) searched for this mechanism from every other root: 192 sized children over 12 generations, 84 verifier passes, **0** new linear oscillators -- the mechanism stays one family.
**Candidate guard G-OSC50** (for the record, not proposed under the decision rule): one
transient run in the verifier's own 50 Ω bench (R4 method, 1 µA kick, 600 ns, oscillation
verdict) — ≈ 1 sim per winner. Impact: 0 accepted cells, 0 training witnesses.

### C-grid-µ — µ < 1 notch between wide-µ grid points (does NOT qualify: 1 material)

Training witness t2-nb240-noise-0369 (I171): µ = 0.884 over a 16 MHz-wide notch at 1.125 GHz,
between two verifier points spaced 50 MHz (lin 1001 over 10 MHz–50 GHz); R-c's 4× grid sees it
(magnitude 0.11). A 16× scan of every passing design (`mu_notch.py --scan`,
`results/mu_scan.json`) finds 51 more designs with µ < 1 between grid points, all
immaterial (min µ 0.9968): winners are sized to µ = 1.0000x on the grid, so the curve dips
slightly between points. Candidate guard: a log-spaced or ≥ 4× wide-µ grid (impact: 1 training
witness at > 0.02).

### C-oscX — single instance

E078 (extended record, nb350-power): linear oscillation at 53.5 GHz only with a 3 nH load
(5 of 25 terminations); µ = 0.98 just above the 50 GHz window top (`window_scan.json`: 4/738
designs have µ < 1 at 50–100 GHz, only this one oscillates). Gear integration decays, trap with
4× finer step oscillates — borderline numerically. One instance; no guard proposed.

### Not found

- **Port DC:** 0 designs where the DC-grounded source does materially worse than the AC-coupled
  one — rl-v1.1's guard closes the L-IN-G exploit completely in this population.
- **Band-edge / grid gaming of S11, S21, ripple, NF:** 0. Largest dense-vs-grid gap over all
  passing designs 0.0005 dB.

## Fragility (R-d / R-e — reported, not exploits)

Corner results over all 1027 verifier-passing designs (perf "within cushion" = every constraint
violation <= 0.02; stable = in-band and wide µ >= 1; gross = violation > 0.10 or µ < 0.98):

| corner | perf within cushion | µ ≥ 1 | both | gross failure | dominant gross metric |
|---|---|---|---|---|---|
| −40 °C | 460 | 524 | 121 | 617 | S11 max (input match) |
| +85 °C | 285 | 700 | 151 | 611 | Idd, then NF |
| VDD × 0.9 | 63 | 736 | 36 | 571 | S11 max, S21 |
| VDD × 1.1 | 456 | 573 | 228 | 525 | Idd (power budget) |
| all four | — | — | **4** | 901 have ≥ 1 | |

Accepted-cell + training witnesses (205): 0 pass all four corners. This is the expected pattern
for a sizer that stops at the first feasible point: wide µ is parked at 1.0000x and the binding
spec sits on its limit, so any corner pushes it over. Real robustness would need corner-aware
sizing (out of scope, W3).

## Deviations from the pre-reg

- **D1 materiality.** The pre-reg scores "magnitude of the worst failure" without a floor; an
  R-a/R-c failure counts as an exploit above 0.02 normalized (the bench-v2 2 % cushion).
  Strict (any violation) counts are reported alongside.
- **D2 R-b scope.** 1 mA-only limit cycles are large-signal (W4) and not scored (20 designs).
- **D3 selection v2** (phase 1, from gen 4): 0.30 uniform / 0.35 class-balanced / 0.35 score
  tournament, because C-cp1 dominated the pure score tournament after 4 generations.
- **D4 R-c positive-control criterion** was revised during validation (validate.py ran 4
  times): the nb winners sit exactly on their S11 limit so the trap's off-resonance leak is
  visible on the verifier grid too (0.009–0.015); the criterion became "dense violation > 0.02
  and > 2× the grid leak, clean copy clean". The check itself was not changed by this.
- **D5 extended record** (250 rl-v1-feasible, pre-filter-passing rows) — rl-v1.1-feasible
  designs on record by AMENDMENT 2 D23 but without an rl-v1.1 row; checked like seeds, not
  search parents. 2 failed rl-v1.1 on re-size, 3 did not reproduce their rl-v1 metrics exactly.
- **D6 search phase 2** (declared in `search_p2.py` before it ran): parents limited to roots
  with no R-b instance, R-b-proximity tournament, RNG `EX-v0-p2`. Planned to gen 80, stopped
  after gen 71 for wall time (decided at gen 67, not on results; 1 process ran by mistake for
  gens 66–68, which only slowed it).
- **D7 guard-impact set**: accepted-cell and training witnesses re-sized under rl-v1.1 (read-only
  inputs; cells.jsonl sha1 a5e6e42f…, train.jsonl sha1 761221b7…, snapshot 2026-10-02 18:40).
- **D8 output-side harness diagnostic** (outside R-a, which changes only the source side).
- **D9 recoverability re-sizes** under ideal coupling (deterministic sha1 sample of 40 failing
  training witnesses + the failing accepted cell).
- Unlogged CPU: diagnostic scripts run outside the pools (≤ 1.5 h, included in the total).
  4 impact jobs (I010–I013) ran after their pool was restarted and are not in the pool log.

## Compute

| item | CPU-h |
|---|---|
| strict seeds (182 + 19 aborted first attempt) | 4.61 |
| check validation | 0.31 |
| extended record (250) | 7.12 |
| search phase 1 (960 sized) | 21.51 |
| search phase 2 (192 sized) | 4.38 |
| guard-impact set (215 run, 79 reused) | 5.21 (+ ≈ 0.3 for 4 unlogged jobs) |
| G-CP1 recoverability re-sizes (41) | 0.75 |
| diagnostics outside the pools (rb_diag, window/µ scans, harness, osc50, tests) | ≤ 1.5 (estimate) |
| **total** | **≈ 46 of the 80 CPU-h budget** |

≤ 4 processes throughout (shared box, load1 ≈ 11–14 from the bench-v2 run).

## Files

`ex_lib.py` (sizing capture + checks), `validate.py`, `seeds.py`, `ext_record.py`,
`impact.py`, `ex_drv.py` (worker), `ex_pool.py` (load-aware pool with CPU accounting),
`search.py` (phase 1), `search_p2.py` (phase 2), `analyze2.py` (final tables;
`analyze.py` = the phase-1-only first cut), diagnostics `rb_diag.py`, `window_scan.py`,
`osc50_mech.py`, `mu_notch.py`, `cp1_detail.py`, `harness_diag.py`, `resize_cp1.py`,
`resize_list.py`; launchers `launch_*.sh`, `envrun.sh`. Results: `results/summary.json`
(all class/impact/fragility numbers), `results/validate.json`, `results/gens_all.jsonl` (both phases; `gens_p1.jsonl` = phase 1),
`results/{harness_diag,mu_scan,osc50_mech,rb_diag,window_scan}.json` (recoverability rows are in `summary.json`).
Raw per-design records (bodies, params, full check outputs; ~30 MB) stay in
`/tmp/cr-7cd7ffc3-ex` (not committed).

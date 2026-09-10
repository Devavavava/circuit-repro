# CAMPAIGN gf180-physaudit-v0 — device-physics audit of the gf180mcu ladder wall

Commissioned 2026-09-10 (user GO, "Fable day 3" session). Box-side, zero GPU,
zero origin pushes, zero store writes. Era stamp: **era-audit-df7d9052**
(local main tip at pre-reg freeze; label domain = box).

## Question

For each of the 24 ladder specs (kaggle/specs-ladder/) on gf180mcu: is the
persistent miss explained by **device-level physics** (no topology built from
this PDK's RF devices at the spec's Idd budget can meet the s21/nf gates), or
is it a **topology-search gap** (the device supports the gates; the
corpus/search fails to find a shape)?

## Motivation (measured record)

Four gf180 campaign runs: null 0/24 (era-fixed), arch 2/24 (era-binfix,
best-of-run event), arch in-era 0/24 (leg1), selflearn 0/23 (leg2). All bind
s21/nf at the Idd boundary; sim-health 1.00 both in-era legs (environment
proven clean). The self-learning channel is measured null on gf180. The next
lever choice — externals ingestion vs spec-relief ruling vs descope — depends
entirely on the physics-vs-search classification, and every GPU hour spent
before knowing it is spent blind.

## Method

Two tiers of single-device measurements on gf180mcu `nmos_3p3` (pmos_3p3
advisory only), reusing the harness's exact deck conventions: includes
`.include <root>/models/ngspice/design.ngspice` +
`.lib <root>/models/ngspice/sm141064.ngspice typical`; device instance
`X1 d g 0 0 nmos_3p3 w=20e-6 l=0.28e-6 nf=10` (reference width W_ref = 20 µm,
L pinned 0.28 µm and 2 µm/finger per the sizer's own conventions); sp ports
`Vp1 p1 0 dc 0 ac 1 portnum 1 z0 50` / `Vp2 ... portnum 2 z0 50` (ngspice-47
`sp` analysis, same as extract.py); ideal 1 H / 1 F bias tees so DC bias and
RF ports are independent; Idd via op `-i(Vd)` (harness sign convention).

**W-scaling invariance (what makes single-width sweeps sufficient):** at
fixed current DENSITY J = Id/W, the four audit figures are invariant under
ideal width scaling — MSG = |S21/S12| = |Y21/Y12|, h21 = Y21/Y11 (→ ft),
Mason's U (→ fmax), and NFmin all depend on ratios that scale out W. So the
audit sweeps bias at W_ref and reasons per-density, folding the sizer's own
W box [0.22, 100] µm in as the realization constraint W' = Id_stage/J ≤
100 µm. Spot-check fence: two bias points re-measured at W = 60 µm must
reproduce MSG/NF within 0.5 dB and Id/W within 10%, else abort.

**T1 — gain ceiling.** Bias grid Vgs ∈ [0.45, 1.50] (15 pts) × Vds ∈
{1.1, 1.65, 2.2} (supply 3.3). Per point: op (Id) + `sp dec 20 1e8 5e11`;
from S(f): K, MSG = |S21/S12|, MAG where K ≥ 1, h21 → ft (unity crossing),
U → fmax; per-spec values interpolated at target frequencies {0.915,
1.57542, 1.75, 2.442, 3.0, 3.5, 5.8} GHz. Stage-split scenarios k ∈ {1,2,3}:
stage current Id_k = idd_cap/k, allowed densities J with Id_k/J ≤ 100 µm,
cumulative achievable gain = k × best allowed MSG (MSG not MAG, lossless
inter-stage, zero implementation margin — every choice generous: a real
design only does worse). **gain-infeasible** if max over scenarios <
s21 gate. Wideband specs (e08/h08) gate s21_min band-wide → evaluated at
the 3.0 GHz band edge (worst); their nf at f0 = 1.75 GHz.

**T2 — noise floor.** Series-source noise deck mirroring extract.py
measure_nf: Vnz → Rs → (ideal series Lg) → gate; drain fed via noiseless
1 H from Vd (no load resistor noise); `noise v(d) Vnz dec 10 8e8 6.5e9`;
NF(f) = 10·log10(inoise² / (4kT·Rs)) with 4kT = 1.65678e-20 (300 K — the
harness's 8.283894e-19 constant ÷ 50 Ω). Lossless-matching grid: Rs ∈ {10,
15, 25, 40, 65, 100, 160, 250, 400, 650, 1000} Ω × Lg ∈ {0, 0.5, 1, 2, 3,
5, 8, 12, 18, 25} nH × 8 Vgs biases at Vds = 1.65. NFmin_est(spec, f0) =
min over grid and over densities realizable at ANY Id ≤ idd_cap within the
W box (input stage assumed to get the most favorable current — maximally
generous decoupling from T1; joint constraints are only harder, so the
certificate direction is safe). Caveat recorded: grid-min is an UPPER bound
on true NFmin, so the rule below includes slack in the direction of NOT
declaring infeasibility; exotic noise-cancelling topologies are noted as
outside the bound's strict scope (engineering-strength certificate, not a
theorem).

**AMENDMENT (2026-09-11, pre-results — logged deviation).** At probe time
(before any spec sweep) ngspice-47's `sp ... 1` (donoise) was found to
expose direct noise-correlation two-port vectors: NF, **NFmin** (dB), Rn,
SOpt. T2 PRIMARY is therefore the sp-donoise NFmin vector (a direct
measurement, strictly better than the grid's upper bound), taken over the
full T1 Vgs grid at Vds = 1.65, `sp dec 20 1e8 2e10 1`. The frozen Rs×Lg
grid method is DEMOTED to a cross-check fence on a reduced subset (3
biases): (i) grid NF at Rs = 50 Ω, Lg = 0 must agree with the sp NF vector
within 0.75 dB at 2.442 GHz; (ii) grid NFmin_est must be ≥ sp NFmin −
0.25 dB (an upper bound must sit above the direct measurement). Either
failure ⇒ FENCE-FAIL, classifications withheld. Classification rule and
slack are unchanged (now conservative on a direct measurement). Motivated
purely by capability discovery at probe time, not by any spec outcome; no
spec sweep had run when this was written.

**AMENDMENT 2 (2026-09-11, pre-full-run — logged deviation).** Quick-mode
plumbing diagnostics (labeled non-audit, dirs physaudit-quick*) exposed that
the sp-donoise NFmin vector reads ≈ 0 dB (≤ 1e-14) at every bias, with NF(50Ω)
frequency-FLAT and Rn ≈ γ/gm. Root cause verified in the PDK model card
itself: `sm141064.ngspice` sets **tnoiMod = 0 and rgateMod = 0 on all bins**
— no induced-gate noise, no gate-resistance noise. Under this model a
MOSFET's noise is a single fully-correlated drain source, so true NFmin ≈ 1
(0 dB) by construction: the device noise floor CANNOT bind, for any spec, as
a matter of the model, not of the audit. Consequences, fixed before the full
run: (1) the NOISE AXIS IS DEMOTED TO ADVISORY — no spec may be classified
DEVICE-INFEASIBLE on nf under this model, and the audit records per spec the
grid method's realizable-matching NF floor (advisory) plus the model
caveat; (2) CLASSIFICATION RESTS ON THE T1 GAIN AXIS alone (rule below,
nf clauses void); (3) the finding itself is a primary audit output: the
campaign's measured NF 7–8 dB failures on gf180 are circuit-level (joint
match/gain/Idd design), not a device noise floor. Motivated by a model-
validity discovery; the only spec-level quantities seen at amendment time
were quick-mode diagnostics (5-point bias grid), recorded verbatim in the
session transcript; the solved-cell validation fence remains in force.

## Pre-set classification rule (frozen before any results)

Per spec:
- **DEVICE-INFEASIBLE** if gain-infeasible (T1) OR NFmin_est − 0.5 dB > nf
  gate (0.5 dB = grid-coarseness slack, conservative against false
  infeasibility claims).
- **BORDERLINE** if not infeasible but NFmin_est within ±0.5 dB of the nf
  gate or cumulative MSG within 3 dB of the s21 gate.
- **TOPOLOGY-GAP** otherwise (device-feasible, campaign-unsolved).

## Validation fence (gate on reporting)

cap-e01-wifi and cap-m06-wifi — the two cells actually solved on gf180
(era-binfix 2/24) — MUST classify TOPOLOGY-GAP or BORDERLINE (i.e. NOT
device-infeasible). If either classifies DEVICE-INFEASIBLE the method is
wrong; no classifications are reported and the audit returns to design.
Two plumbing fences run before any sweep: (a) the audit runner reproduces
check_pdk_live's gf180 smoke deck (Vg = 1.2 V, Rd = 5k, W = 10 µm) and must
see id > 1 nA and low-frequency gain > 0 dB; (b) the W = 60 µm invariance
spot-check (§Method) must pass.

## Outputs

`kaggle/campaigns/gf180-physaudit-v0/era-audit-df7d9052/`:
- `results.jsonl` — one row per spec: spec id, freq, gates, Idd cap, per-
  scenario best-bias {Vgs, Id, gm, ft, fmax, MSG@f}, NFmin_est (+ arg-min
  grid point), margins vs gates, class.
- `results.md` — the 24-row verdict table + validation-fence status.
- `raw/` — every deck + verbatim ngspice log (simulator evidence per repo
  law). Driver: `kaggle/gf180_physaudit.py` (box-side, argparse house style,
  fsync checkpointing).

## Pre-declared consequences (no new rulings inside this campaign)

- DEVICE-INFEASIBLE set → queued USER RULING: gf180 ladder relief (new
  pre-registered ladder version) vs documented-wall descope. No spec is
  changed by this audit.
- TOPOLOGY-GAP set → externals-ingestion campaign (separate pre-reg;
  per-round user approval of the candidate topology list per the nudge-limit
  directive). No externals enter the store under this audit.
- No selflearn/GPU legs on gf180 either way (channel measured null, leg2).

## Budget & containment

Box CPU only, target < 2 h wall, sims are single-device (seconds each). No
installs, no pushes, no store writes, scratch under the session job dir.

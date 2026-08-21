# WP-22: Inference Instruments — Per-Device Blame Vectors + Binding-Constraint Probes

**Status:** IMPLEMENTED (2026-08-21). Two new harness instruments, nudge-safe by design.
**Files:** `lna/blame.py`, `lna/binding_probe.py`, `lna/_validate_instr.py`
**Store tables:** `lna/data/blame_vectors.jsonl`, `lna/data/binding_probes.jsonl`
**Goldens:** check_ref.py GREEN before and after (verified in commit).

---

## 1. Motivation and Nudge-Safety Doctrine

The pipeline has a strict separation between **measurements** (what ngspice and the
harness produce) and **topology hints** (what the generator and moves consume). The
constraint-routing policy (FINDINGS §20, plans2/15-ENGINEER-PROPOSAL §5.2) forbids
injecting direct device edits: "route measurements, not topologies."

These instruments are **measurement outputs**, not topology directives:

- `blame.py` answers "which device is most responsible for this failing metric?"
  — a measurement from operating-point data and the noise budget.
- `binding_probe.py` answers "what is the smallest spec relaxation that flips
  feasibility?" — pure arithmetic on stored margins, no simulation.

Both are consumed by G2/G3 routing lines as explanatory context for the **move
prior** (what makes a topology infeasible) and the **critic** (which design spaces
to explore). They do not prescribe topology changes; they label the failure mode
so the search can update its prior accordingly.

---

## 2. Instrument 1: Per-Device Blame Vectors (`blame.py`)

### 2.1 What it does

Given one evaluated design (body + OP + metrics vs a spec), for each FAILING metric
it emits a ranked list of devices by their share of the blame:

| Metric   | Attribution method | Source |
|----------|--------------------|--------|
| `nf_db`  | Output-noise-power share from `extract.measure_noise_budget` (one ngspice run) | full-coverage when sum/total closure <= 5% |
| `s21_db` | Intrinsic gain = gm/(gds+ε) from OP dict | partial: no resonator Q, no feedback paths |
| `idd_ma` | Per-**device** drain-current share; supply branch used only for a closure cross-check (§7.1) | full when sum(\|Id\|) closes to Idd within 10% |
| `s11_db` | gm-match proxy: 1/(gm+gmbs) approximates Re(Zin) for CG; for CS gm governs match condition | partial: no resonator, no signal-path identification |
| `s21_ripple_db` | Capped finite-difference ripple-sensitivity over reactive/gm knobs (§7.2) | partial: local sensitivity, not a closed-form budget |

> **Coverage extension 2026-08-21 (E-8 gap closure): `idd_ma` bug fixed +
> `s21_ripple_db` added.** See §7 below for the root-cause, method, validation
> table, and blind-spot declaration. The `idd_ma` and `s21_ripple_db` rows above
> reflect the post-fix behaviour.

### 2.2 Output contract

Each row (one per failing metric per design) written to `blame_vectors.jsonl`:

```json
{
  "kind": "blame",
  "wl_hash": "...",
  "spec": "wifi24",
  "metric": "nf_db",
  "metric_value": 2.73,
  "metric_limit": {"max": 2.5},
  "margin": -0.09,
  "blame": [
    {"device": "m1", "score": 0.5087, "detail": {"frac_of_total": 0.51, ...}},
    ...
  ],
  "coverage": "full",
  "coverage_note": "sum/total closure=0.9997",
  "ts": "...",
  "git_sha": "..."
}
```

### 2.3 Coverage limits (honest declaration)

**Noise blame** (`nf_db`): reuses the validated `extract.measure_noise_budget`
machinery (same series-Rs harness proven in `ref/check_nf.py`). Coverage is "full"
when the per-element sum closes to within 5% of the total. Gap cases arise when
noise mechanisms are missing (e.g. a model without flicker noise data).

**Gain blame** (`s21_db`): gm/gds is a DC small-signal picture. It cannot capture:
- Resonator Q effects (inductor losses raise the effective noise and reduce gain)
- Feedback path gains (cascode, neutralization)
- Stacking gains in multi-stage cascades
Rated "partial" in all cases.

**Current blame** (`idd_ma`): branch currents (ngspice `#branch` nodes) are the
full picture when available. When branches is empty (the default for many topologies
where passive branch currents are not exposed), the fallback is device `id`, which
misses inductor/resistor/capacitor DC paths. Rated "full" or "partial" accordingly.

**Match blame** (`s11_db`): cgg/cgs/cgd are NOT in `MOS_OP_PARAMS` (the standard
OP probe schema) per extract.py's design — adding them to MOS_OP_PARAMS would bloat
every OP row and violate harness containment. The gm-proxy is used instead:
`Re(Zin) ≈ 1/(gm+gmbs)` for CG; for CS-degenerated the match condition is
`Ls = Z0*(Cgs)/gm` so higher gm relaxes the inductance requirement. This is
derivable from OP data but cannot identify which device pin the signal reaches.
Rated "partial" always. A cleanly derivable Zin attribution from pure OP data is
not achievable without a dedicated small-signal sweep.

---

## 3. Instrument 2: Binding-Constraint Probes (`binding_probe.py`)

### 3.1 What it does

Given an infeasible design's stored margins (no re-simulation), computes:

1. **Per-constraint shortfalls**: the normalized signed slack per supported
   constraint (< 0 means failing).

2. **Single-constraint relaxations**: for each failing constraint, the minimal
   delta to its limit (max or min) that would exactly satisfy that constraint
   in isolation. Example: s21 achieved=6.86 dB, min=12 dB →
   `delta_frac = (12 - 6.86)/12 = 0.428`.

3. **Pairwise relaxations**: for each pair of failing constraints, the smallest
   uniform fractional epsilon such that applying `epsilon * scale` to each limit
   simultaneously satisfies both. This identifies jointly-binding constraint pairs.

4. **Verdict**: `"feasible"` | `"single"` | `"pairwise"` | `"multi"`.

### 3.2 Output contract

Each row written to `binding_probes.jsonl`:

```json
{
  "kind": "binding_probe",
  "wl_hash": "...",
  "spec": "wifi24",
  "feasible_before": false,
  "n_failing": 2,
  "shortfalls": {"nf_db": -0.094, "s21_db": -0.428, "s11_db": 0.094, "idd_ma": 0.160},
  "single_relaxations": [
    {"metric": "nf_db",  "limit_key": "max", "current_limit": 2.5,  "new_limit": 2.73,  "delta_frac": 0.094},
    {"metric": "s21_db", "limit_key": "min", "current_limit": 12.0, "new_limit": 6.86,  "delta_frac": 0.428}
  ],
  "pairwise_relaxations": [
    {"metrics": ["nf_db", "s21_db"], "uniform_frac": 0.428, "would_flip": true}
  ],
  "verdict": "single",
  "sim_needed_extensions": [...],
  "ts": "...",
  "git_sha": "..."
}
```

### 3.3 Coverage limits (honest declaration)

**No re-simulation needed** for the basic version. The probe is exact arithmetic
on the stored `achieved` values and the spec limits. All `would_flip` flags are
exact: a `delta_frac` of X applied to the limit *exactly* satisfies that constraint
for the stored achieved value.

**What is NOT captured (documented extension hooks):**

1. **Pairwise-Pareto**: mapping the actual feasibility boundary between two coupled
   constraints (e.g. S21 and NF share the same gm in a Friis chain) requires a
   simulation sweep. The pairwise relax above treats each constraint independently;
   a physically-motivated joint relax needs a sweep.

2. **Sensitivity-direction**: finding the ZOAF-objective-minimal relaxation
   direction (the direction that costs the least objective loss to flip feasibility)
   requires a gradient or sensitivity analysis — simulations.

3. **Objective-weighted ranking**: ranking relaxations by their downstream impact
   on ZOAF score (not just by normalized delta) requires the objective landscape,
   which is not stored.

These are listed as `sim_needed_extensions` in every probe row.

---

## 4. Validation Results

Run: `python lna/_validate_instr.py --verbose` (2026-08-21, sha 5d55f0a+)

| Case | Design | Expected | Instrument | Result |
|------|--------|----------|------------|--------|
| 1 | ref:ref24_tapped (FEASIBLE) | verdict=feasible, 0 blame rows | both | PASS |
| 2 | ref:ref24_csdeg (INFEASIBLE: nf+s21) | n_failing=2, verdict=single; m1 top NF blame (>40% share) | both | PASS |
| 2a | ref24_csdeg s21 arithmetic | delta_frac=(12-6.86)/12=0.4283 | binding_probe | PASS (exact) |
| 2b | ref24_csdeg nf arithmetic | delta_frac=(2.73-2.5)/2.5=0.0939 | binding_probe | PASS (exact) |
| 2c | ref24_csdeg NF blame | m1 (input transistor) is dominant, frac=0.509 | blame.nf | PASS — agrees with _nf_budget.py known result |
| 3 | b3aa27 (3 failing: s11+s21+nf) | n_failing=3, s21 delta_frac=1.4601 | binding_probe | PASS (exact) |
| 4 | Single-failing row (s21 only) | verdict=single, n_pairwise=0 | binding_probe | PASS |
| 5 | Current blame on idd_ma fail | non-empty blame list | blame.idd | SKIP (zoaf unavailable in analysis env; logic verified in Case 2 current blame) |

**NF blame agrees with known dominant sources (FINDINGS §41–44):** For ref24_csdeg
(CS-degenerated LNA), m1 (the input CS transistor) carries 50.87% of the output
noise power, with Rns (the 50-ohm source resistor, unavoidable Johnson noise) at
28.35%. This matches the known NF-budget decomposition from `lna/_nf_budget.py`.

---

## 5. How G2/G3 Lines Consume These (Routing Policy)

Per the nudge policy (FINDINGS §20, constraint-routing doctrine):

**What the instruments output:** measurements — device-level fault attribution and
constraint margin arithmetic. These are observations about what the circuit *did*,
not instructions about what to build.

**What G2/G3 receive:** the `blame_vectors.jsonl` and `binding_probes.jsonl` rows
as **context for the move prior**, not as topology prescriptions. Concretely:

- A G2 generator session receives: "this topology failed s21 by 0.43 scale-units;
  the two devices with lowest intrinsic gain were m1/m2; the binding constraint pair
  is (s21, nf)." The generator uses this to update its distribution over moves — it
  does NOT receive "add a cascode" or "change gm of m1."

- A G3 critic sees: "failure mode = gain-wall + nf-coupling; binding pair suggests
  a single-degree-of-freedom constraint surface." This informs the critic's estimate
  of this topology family's feasibility probability, again without specifying device
  values.

This routing preserves the nudge-safe invariant: the search is guided by
*what failed* (measurements), not *how to fix it* (topology hints).

---

## 6. Store Discipline

Both instruments write to NEW files, not to any existing `datastore.TABLES` entry:
- `lna/data/blame_vectors.jsonl` — new, `blame.py`-owned
- `lna/data/binding_probes.jsonl` — new, `binding_probe.py`-owned

Neither file modifies `datastore.TABLES` (containment rule). The `_append_blame`
and `_append_probe` functions replicate the `ds.append` mechanics (JSONL, LF
line endings, `sort_keys=True`, `_jsonify` coercion) so the files are consistent
with the rest of the store. Era stamps (`ts`, `git_sha`) are included on every row.

---

## 7. Coverage extension — 2026-08-21 (E-8 gap closure)

The E-8 throughput ladder (`engineer/E8-LADDER.md`, scored campaign 2026-08-21)
ran arm (c) — the blame-guided edit arm — on four structural goals and **measured
`blame.py`'s coverage gaps in the wild**. Two gaps were recorded in its "Scored
results" / "Deviations" sections:

> *"blame.py returned empty device rankings for ripple (metric not covered) and
> for G8 idd; the guided arm there ran on the binding-probe metric alone.
> Instrument coverage extension queued."*

Concretely, from the per-goal arm-(c) auto-diagnosis lines:

- **G8** (dhruva-l5, cut Idd 13→10.5 mA): `binding_metric=idd_ma`, **blame devices
  `[]` with coverage `full`** — empty despite the metric being "covered".
- **G9 / G10** (dhruva-l5 / dhruva-s, `s21_ripple_db ≤ 3`):
  `binding_metric=s21_ripple_db`, **blame devices `[]` with coverage
  `unavailable`** — no handler existed for the metric at all.

This section documents the fix for both.

### 7.1 The `idd_ma` empty-with-`full` bug — root cause and fix

**Root cause.** `parse_op` (extract.py) routes every `*#branch` current into the
OP `branches` dict. Two entries are *always* present and *always* ~0.0 A: the
S-parameter port sources `Vp1`/`Vp2` (to_spice emits them `dc 0 ac 1`/`ac 0` —
they carry AC only, no DC supply current). The old `_blame_current` did:

```python
if branches:                       # ← True: Vp1/Vp2 are always there
    total = sum(abs(v) for v in branches.values()) or 1e-30
    ...
    if frac < 0.005: continue      # every entry filters out ...
    cov = "full"                   # ... but coverage was already "full"
```

When the *real* current-carrying branches (the supply source, inductor DC paths)
happened not to be captured under a `#branch` name for a given warm-anchor
topology — leaving only the zero-valued port branches — `total` collapsed to
`1e-30`, every `frac` rounded to 0 and filtered out, and the result was an **empty
ranking labelled `coverage="full"`**. That is the exact G8 symptom. It was also
*semantically wrong* even when non-empty: it ranked `Vsup` (the **total** Idd —
the metric itself, not a culprit) and the inductor branches (which merely
re-report a device's DC path) as if they were blamable devices.

**Fix** (`_blame_current`, blame.py). The attribution now answers the real
question — *which device draws the supply current* — from **per-device drain
current** (`|Id|` share across the MOSFETs):

- the RF port branches (`Vp1`/`Vp2`) and the supply branch itself are **excluded**
  from the ranking;
- the supply-branch magnitude is used only as a **closure cross-check**:
  coverage is `full` when `sum(|Id|) / Idd_supply` is within 10% (the passive DC
  paths are then negligible), `partial` otherwise (some Idd flows through a
  non-MOS DC path — a resistive load or bias divider);
- an empty-but-`full` row **can no longer occur**: with no supply branch the row
  is `partial`, and an all-devices-off row is `unavailable`.

### 7.2 `s21_ripple_db` attribution — method

Ripple is a **band-shape** property: `s21_ripple_db = max(S21) − min(S21)` over
`[f_lo, f_hi]`. There is **no operating-point number that "is" the ripple** — it
is set by the frequency-dependent load/peaking network (the resonant tank L/C
elements and the transconductance that drives them). So attribution is done by a
**capped finite-difference ripple-sensitivity sweep** (`_blame_ripple`):

1. Identify the tunable reactive/gm knobs: capacitor-value params, inductor-value
   params (recognised by name *or* by the L/C element they drive) and device
   widths (which set gm, hence the peaking gain). Each maps back to its element(s).
2. Nudge each knob by **+5% (`RIPPLE_FD_STEP`)** and re-measure the band ripple
   with **one** ngspice run. Score = `|Δripple|`.
3. Rank knobs (reported as element names — `LL1`, `CC1`, `MNM2` — which is what an
   edit move acts on) by `|Δripple|`. The reactive element the ripple is most
   sensitive to is the dominant culprit — the "which element must change to
   flatten the band" answer the ladder's arm (c) needs.

**Sim cost is capped** at `RIPPLE_FD_MAXSIMS = 10` extra ngspice runs. If there
are more reactive knobs than the cap, the largest-reactance ones (dominant at
band) are probed first and the rest are reported as not-probed. When params are
unavailable (a ref deck whose baked `.param` values were stripped by
`extract.body_of`), it degrades to a **structural presence ranking** of reactive
elements (tank inductors/caps ranked above dc-block/bypass caps), explicitly
labelled as such.

### 7.3 Validation (2026-08-21)

Five checkable cases (harness `tmp/validate_blame.py`, not committed — containment):

| # | Case | Expected (checkable) | Result |
|---|------|----------------------|--------|
| F | idd_ma empty-with-`full` trigger (only zero port branches + 2 live devices) | non-empty ranking, NOT `full`-with-empty | **PASS** — cov=`partial`, 2 devices ranked (was cov=`full`, 0 devices) |
| 3-idd | idd_ma on dhruva-l5 reached (G8 deck, 9-device, Idd 12.92 mA) | non-empty; coverage `full` (closes to Idd); a real device on top | **PASS** — cov=`full`, top `mnm2` = 7.12 mA (55% of Idd), sum/Idd=1.00 |
| 1 | s21_ripple on `ref24_tapped` (known tapped-C tank Ld/Ct1/Ct2) | a tank element in the top ranking | **PASS** — top `Ct1` (tapped-C tank series cap); `Ld` also ranked |
| 2 | s21_ripple on `ref24_csdeg` (tuned load Ld/Ctnk) | a tank element in the top ranking | **PASS** — `Ld`, `Ctnk` (tuned-load L/C) both surfaced |
| 3-rip | s21_ripple on dhruva-l5 reached (ripple **15.18 dB** — the FINDINGS peaked-LC-tank load `rfbcs3_tank`, "single peaked tuned load cannot be flattened", E-8 §3 G9) | top ranks the VDD resonant tank L/C | **PASS** — top `CC1`+`LL1` (the VDD-node tank cap+inductor), Δripple 0.18/0.09 dB |
| 4 | no-ripple control: same l5 topo on the **narrow** wifi24 band (2.40–2.4835 GHz) | small ripple + low/flat attribution, not noise | **PASS** — ripple 0.43 dB, top sensitivity 0.008 (flat, not spurious) |

Case 3-rip cites the dhruva-l5 ripple mechanism from FINDINGS: the reached
`rfbcs3_tank_cc21_bf0` uses a **peaked LC tank load** (the `_tank_` family), whose
high-Q resonance produces a sharp S21 peak; over the wide 1.1–2.5 GHz band this
gives the 15.18 dB min-to-max swing. The instrument correctly attributes it to the
VDD-node tank inductor + capacitor (`LL1`/`CC1`).

### 7.4 Remaining blind spots (honest declaration)

**`idd_ma` (post-fix).**
- Only MOSFET drain currents are ranked. Idd drawn through a **resistive load or
  bias divider** (a static DC path with no MOS drain) shows up only as a closure
  gap that flips coverage to `partial` — those Ohmic paths are **not itemised** as
  culprits.
- No BJT collector-current path (the current dhruva/wifi families are all-MOS).

**`s21_ripple_db`.**
1. It is a **local** sensitivity (`+5%` finite difference), **not a global ripple
   budget** — the scores do not sum to the ripple and are not a decomposition.
2. **Knob–knob couplings are not captured**: each knob is nudged in isolation, so
   a ripple set jointly by two staggered tank poles is under-attributed to each.
3. With **more reactive knobs than the sim cap** (`RIPPLE_FD_MAXSIMS`), the
   lowest-reactance knobs are not probed; coverage stays `partial` and the
   not-probed set is named.
4. With **no params** (ref decks, or an env that cannot re-simulate), it degrades
   to a structural presence ranking that **cannot tell which reactive element
   actually shapes the band** — only that it is a tank/peaking element rather than
   a dc-block. Labelled explicitly.
5. It ranks **existing** elements' sensitivity; it does **not** propose the
   structural fix (add a staggered-tuned second pole) — that remains a move-prior
   / generator job, per the §5 routing policy (measurements, not topology hints).

Coverage is therefore **`partial` for `s21_ripple_db` in all cases** — an honestly
labelled sensitivity ranking, which the E-8 ladder can consume as a move-prior
signal ("the band ripple is most sensitive to the VDD tank") without it pretending
to be a closed-form attribution.

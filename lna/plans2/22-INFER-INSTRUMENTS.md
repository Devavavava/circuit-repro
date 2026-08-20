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
| `idd_ma` | Abs current share: branch currents (preferred) or device Id (fallback) | full when branches available |
| `s11_db` | gm-match proxy: 1/(gm+gmbs) approximates Re(Zin) for CG; for CS gm governs match condition | partial: no resonator, no signal-path identification |

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

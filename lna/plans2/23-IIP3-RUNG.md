# 23 — IIP3 Tier-3 Rung: Pipeline Wiring (2026-08-21)

## What changed

### 1. `lna/spec.py` — `status: measured` pathway (D5b)

A constraint may now carry `status: measured` (previously only `None` /
`"unsupported"` were accepted). This status means:

- **`spec.feasible()`** evaluates the constraint exactly like any other
  supported constraint (a missing metric counts as fully violated).
- **`spec.report()`** prints `MEASURED-PASS` or `MEASURED-FAIL` when the metric
  is present, `UNMEASURED` when absent.
- **The CLI** (`python lna/spec.py <name>`) labels it `(MEASURED tier-3)`.

`status: unsupported` continues to skip the constraint in `feasible()` and
prints `UNMEASURED (no harness)` everywhere — unchanged behavior.

No existing spec file was changed. Spec file changes (flipping `iip3_dbm` from
`unsupported` to `measured` in any real spec) are **user rulings** and are
queued, not pre-empted here.

### 2. `lna/size.py` — tier-3 opt-in (`enrich_iip3`)

Three new public symbols:

| symbol | what it does |
|---|---|
| `iip3_is_measured(spec)` | `True` when the spec's `iip3_dbm` has `status: measured` |
| `measure_iip3_tier3(body, params, spec)` | Runs the two-tone transient harness at the spec's `f0`; returns a dict with `iip3_dbm`, `oip3_dbm`, provenance keys; `None` on harness failure |
| `_enrich_iip3(body, params, spec, m)` | Defensive enrichment wrapper, analogous to `_enrich_nf` |

`size_topology()` gains a new keyword argument **`enrich_iip3=False`** (default
`False` — existing callers unaffected). When `enrich_iip3=True` and
`iip3_is_measured(spec)` is `True`, the two-tone harness runs once at the
best-found point, after NF enrichment, and adds `iip3_dbm`, `oip3_dbm`, and
provenance keys to the metrics dict that gets logged.

The harness is **not in the ZOAF loop** — it costs ~6 ngspice transient calls
(one per Pin level) per band, and `spec.feasible()` cannot use it there without
a gating path identical to NF's (which would be a user ruling). It is
post-sizing only.

### 3. `lna/benchmark.py` — IIP3 MEASURED/UNMEASURED per spec

The scoreboard (`write_report`) adds:
- A **tier-3 IIP3 column** in the per-spec yield table: for specs with
  `status: measured` it counts how many cells have an IIP3 reading; for specs
  with `status: unsupported` it prints `UNMEASURED (no harness)`.
- An **IIP3 column** in the detail table: `<value> MEASURED` /  `UNMEASURED` /
  `-` (spec has no iip3_dbm constraint at all).

The scoreboard never silently passes or fails IIP3 — the render is explicit
about whether a measurement was taken.

### 4. `lna/specs/README.md` — IIP3 paragraph updated

The stale paragraph now points to this document and describes the two-tier
status system (`unsupported` / `measured`).

### 5. `lna/_validate_iip3_rung.py` — S44 replay fence

A standalone validation script that reproduces FINDINGS §44.2's number at the
D6 out-bank S3 (min-gain) condition, 1.2 V rail, l5 band:

```
python lna/_validate_iip3_rung.py
```

## Validated settings inherited from WP-LIN

All settings are pre-registered in `lna/iip3.py`; none were changed here.

| parameter | value | source |
|---|---|---|
| Coherent grid | 1 MHz | iip3.GRID_HZ |
| Tone spacing DF | 2 MHz | iip3.DF; HB fence: IIP3 constant to 0.001 dB over nharm 4–8 |
| DFT window T_WIN | 1 µs | iip3.T_WIN; bin spacing = 1/T_WIN = 1 MHz (coherent) |
| FFT points N_FFT | 32768 | iip3.N_FFT; fs = 32.768 GHz, Nyquist 16.384 GHz |
| TMAX | 5 ps | iip3.TMAX; G1 golden: numerical IM3 floor −133.1 dBc at 5 ps |
| T_SETTLE | 150 ns | iip3.T_SETTLE; RF time constants ns-scale |
| Min IM3 SNR | 10 dB | iip3.MIN_SNR_DB |
| Gain compression guard | 0.5 dB | iip3.COMP_DB |
| Default Pin sweep | [−80,−72,−64,−56,−48,−40] dBm | iip3.DEFAULT_PINS |
| Min-gain re-drive | [−68,−64,−60,−56,−52] dBm | §44.3: IM3 above floor at S3 |
| Detrend order | linear (degree 1) | iip3.coherent_bins |
| Floor bins | f0s ± k·DF, k=1..4 | iip3.N_FLOOR = 4 |

**One setting chosen here that WP-LIN did not pin for the pipeline path:**

The `measure_iip3_tier3()` function in `size.py` uses `iip3.DEFAULT_PINS`
(the 6-point −80…−40 dBm sweep). The min-gain re-drive window
(−68…−52 dBm, 5 points) is only applied in `_validate_iip3_rung.py` and
`_lin_baseline.py`, which target the S3 min-gain state specifically. A pipeline
call via `size.size_topology(..., enrich_iip3=True)` will use DEFAULT_PINS
because it does not know which gain state the sized topology is in. If a spec's
target point is at a low-gain state where DEFAULT_PINS hits the floor, the
harness will return `ok=False` (the slope/SNR guards will reject the points) and
the metric will be absent (reported UNMEASURED, not silently 0). **This is the
correct behavior** — the caller must set the right Pin window if a non-default
state is measured.

## §44 replay result

**D6 out-bank S3 (min-gain), pVDD = 1.2 V, l5 band (1176.45 MHz)**

Deck: `lna/repro/dhruva-best/dhruva-simul_min_v1p2.sp`  
Harness: transient-v1 (tmax = 5 ps, DF = 2 MHz, T_WIN = 1 µs)  
Pin window: [−68, −64, −60, −56, −52] dBm (5 points; §44.3 re-drive)

| quantity | this run | FINDINGS §44.2 | delta |
|---|---|---|---|
| **IIP3** | **−34.188 dBm** | −34.19 dBm | **+0.002 dB** |
| gain | +20.934 dB | +20.93 dB | +0.004 dB |
| OIP3 | −13.254 dBm | −13.25 dBm | −0.004 dB |
| slope | 3.055 | 2.968 (max-gain §44.2) / see note | — |
| kept pts | 4 | 4–5 | — |

Tolerance set at ±0.5 dB; measured delta is +0.002 dB — **GREEN**.

Note on slope: §44.3 reports slope 3.06–3.19 for the re-driven min-gain rows;
3.055 here is consistent with that range.

## What stays manual (HB)

The VACASK harmonic-balance harness (`lna/hb/hb_iip3.py`) is **not** on the
routine path. It:
- requires VACASK 0.3.4.rc1 installed on Windows (not available on this RHEL box);
- agrees to within 0.08 dB with the transient harness (FINDINGS §44.9);
- is the cross-check that validated the transient method, not the primary one.

The HB path remains available as a manual validation tool. The ngspice two-tone
transient is the standard routine rung.

## Queued user rulings

Flipping any real spec from `status: unsupported` to `status: measured`:
- `dhruva-l5.yaml` `iip3_dbm: {min: -7.4, status: unsupported}`
- `dhruva-l2.yaml` / `dhruva-l1.yaml` / `dhruva-s.yaml` (same pattern)
- `gps-l1.yaml` `iip3_dbm: {min: -10, status: unsupported}`

These are user rulings and are NOT pre-empted here. All spec files remain
unchanged. The infrastructure is in place; the gate is the user decision about
which specs to score IIP3 against.

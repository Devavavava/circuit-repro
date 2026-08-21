# LNA specification targets

Each `*.yaml` here is one design target. `lna/spec.py` loads and validates a
spec and compiles it into three separable views (plans/01-SPEC.md §1, D1):

| View | Consumer | Works on |
|---|---|---|
| `spec.structural_screen(topology)` | `screen.py` | unsized topology (L0) |
| `spec.objective(metrics)` / `feasible(metrics)` | sizing loop (05-SIZING) | sized, simulated circuit (L2) |
| `spec.seed_filter(topology)` | conditioned generation | corpus circuits used as prefix seeds |

Hard constraints (`constraints:`) and soft objectives (`objectives:`) are kept
structurally separate and only blended feasibility-first at the ZOAF boundary
(D2). Every metric is checkable at the earliest pipeline stage that can see it
(D3: L0 structural / L1 default-valued sim / L2 sized sim); `screen.py` checks
L0 only.

## Targets

| spec | class | binds on | inductorless? |
|---|---|---|---|
| `wifi24` | 2.4 GHz ISM narrowband | S11 + NF | no (inductors expected) |
| `gps-l1` | 1.575 GHz narrowband | **NF** (noise-first) | no |
| `wideband-sdr` | 0.5–3 GHz wideband | NF + ripple across band | **yes** (H-Q4 population) |
| `legacy-lna5` | calibration shim — the old 5-criterion screen | — | no |

`legacy-lna5` is not a design target; it reproduces the historical hard-coded
screen through the new derivation to pin the refactor (§4.2).

## Unsupported metrics

Linearity (`iip3_dbm`) was declared with `status: unsupported` (harness not wired).

**Updated (2026-08-21, plans2/23-IIP3-RUNG.md):** The two-tone transient harness
(`lna/iip3.py`, harness era: transient-v1) is now wired into the evaluation pipeline
as a standard **tier-3** measurement rung. A spec may now declare `iip3_dbm` with
`status: measured` to opt into the two-tone harness at sizing time (pass
`enrich_iip3=True` to `size.size_topology` or to the verification entry points).
The benchmark scoreboard renders IIP3 as MEASURED or UNMEASURED per spec, never
as a silent pass or fail.

The VACASK harmonic-balance cross-check (`lna/hb/hb_iip3.py`) remains a manual
validation tool — it agrees to within 0.08 dB with the transient harness (FINDINGS §44.9)
but is not on the routine path.

**Spec file changes** (flipping any real spec from `status: unsupported` to
`status: measured`) are **user rulings** and are queued, not pre-empted here.
All existing spec files remain unchanged; `status: unsupported` continues to mean
UNMEASURED everywhere.

`wideband-sdr`'s `s21_ripple_db` is L2-only (needs the swept response).

## Deliberately excluded: 28 GHz mmWave

A fourth target was considered and **excluded**. The BPTM 45nm predictive model
has no layout parasitics, no NQS, no substrate network; at mmWave those
dominate, so any NF/S11/gain produced there would be fiction. Revisit only with
a process model that carries those effects (plans/01-SPEC.md §3).

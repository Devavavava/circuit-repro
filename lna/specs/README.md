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

Linearity (`iip3_dbm`) is declared with `status: unsupported`: `spec.py` loads
it and reports it as UNMEASURED in every output, and the objective ignores it.
This keeps specs honest against real standards without blocking on harness work (D5).

**Correction (2026-08-19):** Two IIP3 harnesses now exist — an ngspice two-tone transient
and a VACASK harmonic-balance analysis — and they agree to within 0.08 dB (FINDINGS §44).
`iip3_dbm` nonetheless **remains `status: unsupported`** in spec objectives: the harness
exists and is validated, but it has not yet been wired into the benchmark as a standard
tier-3 rung, so no scored result depends on it. Update this file and promote `iip3_dbm`
when that wiring lands.

`wideband-sdr`'s `s21_ripple_db` is L2-only (needs the swept response).

## Deliberately excluded: 28 GHz mmWave

A fourth target was considered and **excluded**. The BPTM 45nm predictive model
has no layout parasitics, no NQS, no substrate network; at mmWave those
dominate, so any NF/S11/gain produced there would be fiction. Revisit only with
a process model that carries those effects (plans/01-SPEC.md §3).

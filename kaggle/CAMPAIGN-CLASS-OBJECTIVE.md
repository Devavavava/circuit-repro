# class-objective-v0 — wire the class harnesses into the sizing objective (pre-reg, 2026-09-14)

Commissioned implicitly by the approved bench-v1 design (stage 2: objective
gaps are architectural work, own pre-reg): `lna/size.py::make_objective` /
`eval_metrics` compute ONLY LNA-family metrics; `pa/mixer/balun` class
gates are recognized by spec.py but never measured in-loop (scout-verified:
no circuit_class dispatch, no harness import in size.py/solve_spec.py/
extract.py). Consequence today: mixer bench cells are VACUOUSLY feasible;
pa cells gate only their LNA-subset metrics. The benchmark's null-filter is
meaningless for 3 of 4 classes until this is closed.

## Scope (shared-core change under lna/ — two-line law applies)

- `eval_metrics` gains circuit_class dispatch: class-gated metrics are
  measured in-loop via the existing harnesses (pa_harness / mixer_harness /
  balun_harness), merged into the metrics dict the objective consumes.
- **lna class byte-identical** (default path untouched; check_ref +
  check_simhealth + funnel goldens green before/after — the binding fence).
- Class goldens (check_pa / check_mixer / check_balun) must stay green;
  plus ONE new golden: an end-to-end in-loop gating check per class (a
  tiny sizing run whose objective demonstrably responds to the class
  metric — the anti-vacuous-feasibility fence).
- Bench spec regeneration: bench_grid.py flips class metrics
  unsupported→measured once wiring lands (regenerated grids re-validated).

## Cost rule (frozen)

Re-measure the per-class eval-cost table AFTER wiring (the current ≤1×
numbers are an artifact of the gap). If any class exceeds the bench's ~5×
LNA cap: implement ELITE GATING — cheap in-loop proxies every eval, class
harness evaluated only on candidates that improve the proxy objective —
with the exact trigger rule documented and the cost table re-published.
Dropping a class is the last resort and a user decision.

## Out of scope

Mixer NF (no PSS in ngspice — stays unsupported); any spec/gate changes to
the frozen 24-ladder; store writes.

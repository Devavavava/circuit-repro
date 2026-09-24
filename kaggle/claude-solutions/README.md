# Strong-model (Claude) solve attempts on the 53 gf180 survivors

Target: establish the strong-model ceiling for the topology-fix task.

## Status (in progress)
- **Triage**: 1/53 budget-margin (bnl-35), 52/53 genuine topology challenges @3x2500.
- **Genuine solves so far**: 1 -- **bnl-24-powe-p0** (current-reuse push-pull +
  bias-mirror AC bypass on both mirror legs; deterministic feasible @3x3000:
  nf 1.98 s11 -12.08 s21 14.00 idd 1.94). Razor-thin but reproducible (MC off).
- **Key finding**: specs are bptm45(45nm)-native, run on gf180(180nm). The
  bnl-24-powe-p0 ANCHOR solves on native bptm45 with NO edit -> much of the
  difficulty is process mismatch, not missing topology. (bnl-1575-diag-t4 20dB
  gain is hard even on 45nm -- genuinely demanding.)

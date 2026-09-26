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

## 45nm ceiling (re-based per user 2026-09-24)
Specs are bptm45(45nm)-native; re-basing removes the gf180 process handicap.
- gf180 ceiling: ~1/53 (process-walled).
- **45nm ceiling: 21/53 confirmed first-pass** = 8 process-artifacts (anchor
  solves on 45nm) + 13 template-solved (cascode-CS+tank 10/20 narrowband;
  shunt-feedback 3/25 wideband). Two templates in templates/.
- 32 unsolved but ~14 within -0.3 margin (single fixed template per bucket at
  2000 evals) -> per-cell iteration projects ~35/53; residual-hard ~7 (bnl-09
  input-match family + tightest nf@low-Idd tiers).
- Detail: campaigns/editcap-v1-baseline/claude-45nm-ceiling.json.
Headline: benchmark difficulty was dominated by the gf180 override, not topology.

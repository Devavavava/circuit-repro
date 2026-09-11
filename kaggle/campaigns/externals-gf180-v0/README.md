# externals-gf180-v0 — results (COMPLETE, 2026-09-11)

Pre-reg: `kaggle/CAMPAIGN-EXTERNALS-GF180.md` (frozen 9167fd46; Amendment 1
@ 506e5c8e). Engine: `kaggle/x0v1_run.py` verbatim, sizing-only, no LLM, no
playbook, `LNA_X0_PRIOR` unset, pdk=gf180mcu. Era-ext-9167fd46, box host.

## VERDICT: EXTERNALS TOPOLOGY CREDIT ×11 — largest gf180 result in program history

Round-1 external shapes, sized by the standard machinery alone:

- **leg-c1-v02 (Shaeffer-Lee ind-degen cascode, wl dcda50191d7c5e73): 10/24**
  — e01, e04, e05, e06, m04, m05, m06, m08, h04, h05.
- **leg-c3-v02 (current-reuse push-pull, wl 226544590d47717b): 6/24**
  — e01, e04, e05, e06, m01, m04.
- leg-c4 (shunt-feedback, wl a6122feb26e8d4dc): 0/24 valid null — alive,
  closest wideband-family misses, but feedback R alone cannot make the
  narrowband s11/nf gates.
- **Union: 11 distinct cells.** Per the frozen credit rule (feasible where
  NO in-era arm ever was — arch 0/24, selflearn 0/23): **all 11 = externals
  topology credit.** Nine (e04 e05 e06 m01 m04 m05 m08 h04 h05) were never
  feasible on gf180 in ANY era; e01/m06 had one era-binfix best-of-run
  precedent each.
- Sim-health 1.00 everywhere (0 fails in 79,200 v0.2 evals + 129,600 v0).
- Achieved NF 0.86–2.62 dB (campaign history: 7–8 dB) — matching the
  physaudit's advisory floors (0.47–0.68 dB) to within matching losses:
  the audit's TOPOLOGY-GAP verdict is now confirmed EXPERIMENTALLY.
- **Every 5.8 GHz cell solved** (e05 m05 m08 h05) — the band read as the
  hardest wall is fully open with the right shape.
- Near misses razor-thin: e02 s21 −0.02, c3-m06 s21 −0.00(!), h01 nf −0.21,
  h06 nf −0.33, e03 s21 −0.39 (normalized) — the next tier is within reach
  of seeds/budget, without new shapes.

## The v0 lesson (Amendment 1, archived as INVALID-PROBE)

v0 c1/c3 templates omitted the published BIAS NETWORKS; under default
harness bias rules a cap-isolated gate gets nothing inserted → c1 ran with
idd = 0.0 (never conducted), c3 PMOS-only. Diagnosed from design forensics;
fixed by carrying bias as in-topology structure (mirror ref / diode
references — the published form AND the era-binfix winner's idiom); zero
authored values throughout. Binding lesson for all future externals:
**transcribe the bias network, and fence on conduction (40-eval smoke,
idd > 0.05 mA) before any leg.**

## Queued user rulings (pre-declared consequence now active)

1. Ingest winning families (c1, c3) into the external corpus + retrieval
   (`lna/ingest_external.py` path, corpus_manifest + novelty ref-v3 bump)
   so the reasoning loop can retrieve them — own pre-reg addendum.
2. GPU retrieval leg E2 (arm-B loop with externals retrievable) —
   push-gated, needs per-instance push wording + quota.
3. Round-2 externals (C2 two-stage for the 17–20 dB gates, C5 CG variants)
   — the remaining 13 cells' misses are mostly s21 on 900 MHz/GPS high-gain
   cells and nf on h-tier wifi: C2's territory.

## Layout

```
era-ext-9167fd46/leg-c1-v02/           10/24 CREDIT leg (results + designs)
era-ext-9167fd46/leg-c3-v02/            6/24 CREDIT leg
era-ext-9167fd46/leg-c4/                0/24 valid null (self-biased)
era-ext-9167fd46/leg-c{1,3}-v0-INVALID-PROBE/   dead-bias v0 legs (forensics)
era-ext-9167fd46/chain.log              full chain log, all legs
```

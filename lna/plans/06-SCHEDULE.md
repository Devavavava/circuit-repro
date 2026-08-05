# Schedule — three weeks, gated

Working days, one executor (an Opus session per WP works; days are sized for
that). Dependencies are real: do not start a gated item early because a day
freed up — the gates exist because downstream numbers are meaningless without
them. Parallel-track items are marked ∥ and can interleave.

## Week 1 — measurement you can trust

| Day | Work | From |
|---|---|---|
| 1 | `spec.py` loader/validator + the three spec YAMLs live in `lna/specs/` | 01-SPEC |
| 2 | spec-driven `screen.py` + `legacy-lna5` reproduction test + ground-truth split calibration | 01-SPEC §4 |
| 3 | device characterization sweep → `device_tables.csv`; stage-A common-gate reference built and matched | 02-REF §2 |
| 4 | stage-B CS+Cex reference; H-Q1 experiments (bypass test, tank detune) fall out of build order; WORKLOG resolution entry | 02-REF §3–4 |
| 5 | `check_ref.py` regression runner; `bias.py` DC-graph + R-GATE/R-FLOAT rules | 02-REF §5, 03-BIAS |

**Gate G1 (end of week 1):** stage-A reference passes S11 ≤ −10 dB and
`check_ref.py` is green. If stage B is still unmatched, proceed anyway
(stage A suffices as anchor) but file the discrepancy.

## Week 2 — bias lands, generation experiments run

| Day | Work | From |
|---|---|---|
| 6 | bias L1 feasibility sweep; validation table over 40 dataset LNAs; `pipeline_yield --bias --spec` | 03-BIAS §3–4 |
| 7 | P0: WL-hash novelty vs full corpus, frozen eval protocol, re-baseline prefix sweep (GPU, ~1 h) | 04-GEN §1 |
| 8 | P1 + P2 built together (data pipeline, checkpoint surgery, two fine-tunes overnight) | 04-GEN §2–3 |
| 9 | P3 n-gram blocking + P4 grammar mask/logit bias (sampling-side, no training) | 04-GEN §4–5 |
| 10 | **Bake-off**: full arm matrix under the frozen protocol; results table into FINDINGS.md | 04-GEN §7 |

**Gate G2:** bias validation ≥ 80% conducting on dataset LNAs (03-BIAS §4).
Miss → the day-6 failure classification decides v2 rules; spend day 11 there
before touching sizing.
**Gate G3:** some arm beats the re-baselined prefix curve on NDL@256. Miss →
P5 becomes mandatory rather than parallel, and week 3 reshuffles.

## Week 3 — close the loop

| Day | Work | From |
|---|---|---|
| 11 | `extract.py` + objective encoding; **anchor re-derivation test** | 05-SIZE §3.1 |
| 12 | CG anchor under wideband-sdr; parallel job runner (`--jobs`) | 05-SIZE §3.2 |
| 13–14 | size top ~30 candidates from best arm vs `wifi24` + `wideband-sdr` (overnight runs); scoreboard | 05-SIZE §3.3 |
| 15 | write-up: FINDINGS.md v2 with end-to-end results; update HANDOVER answers; groom next-phase list | — |

**Gate G4 (the program's first real result):** ≥ 1 novel (P0-metric) generated
topology sized to full feasibility under a reference spec. Even 1 validates
the whole chain; report the number honestly whatever it is.

## ∥ Parallel / fill-in track (needs no gates)

* P5 template corpus (`templates.py` + overnight Eulerian augmentation) —
  ideally days 8–12 so `P1+P5` per-class tokens make the bake-off. 04-GEN §6
* H-Q3 floating-subcircuit detector in `topology.py` (half day). 03-BIAS R-FLOAT
* Inductor series-R (finite Q) in `to_spice.py` (one line + re-run anchors). 05-SIZE §4
* Commit `lna/` to git — it is currently untracked; FINDINGS/WORKLOG/handover
  history deserve version control before more edits pile on.

## Stretch (explicitly out of the three weeks)

* Two-tone transient IIP3 harness → flips `iip3_dbm` specs from `unsupported`.
* Differential topologies (spec `differential: true` + screen support).
* KV cache (04-GEN P6) — only if sizing throughput ever waits on generation.
* Graph-native template sampler as the 04-GEN §8 fallback, only if its
  revisit trigger fires.

## Definition of done (HANDOVER §6, restated as checkboxes)

- [x] **Spec format + worked reference targets** — 01-SPEC + `specs/` (this plan set); *implemented* when day-1–2 tasks land.
- [x] **Representation verdict** — keep checkpoint + Eulerian substrate, class-token addition, explicit revisit trigger (04-GEN §8).
- [x] **Ranked proposals with cost + measurement** — P0–P6 with adoption rule (04-GEN).
- [x] **Bias-insertion position** — rule-based minimal, measured escalation (03-BIAS).
- [ ] G1–G4 gates passed — that part is Opus's three weeks.

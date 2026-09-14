# Externals candidate list — bench-v1 per-class anchor families (DRAFT for user approval)

Status: PROPOSAL ONLY — nothing transcribed. Per the nudge-limit directive
and the approved bench pipeline (stage 3), each class's anchor families
need per-round USER APPROVAL before transcription. All entries: published,
citable, era-appropriate (0.18–0.35 µm), decomposable to MOS/R/C/L (no
transformers/coupled-L), 3.3 V gf180-compatible, single-ended unless the
class demands differential outputs. Every transcription carries its
published BIAS NETWORK in-topology (the externals-v0 lesson) and passes
the conduction + s21 smoke fence before any campaign use.

## LNA (extends the proven set)

- **L-A1..A3 = c1 / c3 / c4 as-is** (ind-degen cascode, current-reuse,
  shunt-feedback — already approved round 1, already validated).
- **L-A4 — C2 two-stage tuned CS-CS with inter-stage resonance** (Cha &
  Lee JSSC 2003 family) — previously drafted round-2 candidate; needed
  for the tightened 17–22 dB gain tiers. ~3 FETs + 3 L + mirror bias.
- **L-A5 — C5 common-gate input LNA** (CG 1/gm match, Allstot-school
  lineage) — previously drafted round-2 candidate; broadband/low-band
  coverage. 2 FETs + 2 L.

## PA (class-A/AB linear families; mW-class on 3.3 V)

- **P-A1 — common-source class-A/AB PA**: L-choke drain feed + output
  L-match + mirror gate bias (textbook, Cripps "RF Power Amplifiers"
  lineage). 1 FET + choke + LC match. The class's c1-analogue baseline.
- **P-A2 — cascode PA**: CS+CG stack for gain/headroom at 3.3 V
  (0.18 µm cascode PA lineage, e.g. Sowlati & Leenaerts JSSC 2002
  family). 2 FETs + choke + match.
- **P-A3 — two-stage driver+PA cascade** with tuned interstage (textbook
  lineage) — for the higher-gain/higher-Pout tiers. 2–3 FETs.
- (Class-E/switching families EXCLUDED: large-signal switching waveforms
  are exactly the simulation-cost risk the benchmark bans.)

## Mixer (single-ended, active; exact port form pends the harness scout)

- **M-A1 — single-FET gate-pumped square-law mixer** (classic
  single-device active mixer). Simplest baseline.
- **M-A2 — dual-gate (cascode) mixer**: RF and LO on the two stacked
  gates — THE canonical 0.18 µm-era single-ended active mixer family.
- **M-A3 — single-balanced Gilbert-style**: gm stage + switching pair
  (single-ended LO drive) — only if the harness's LO convention supports
  it cleanly (scout-gated; flagged at transcription if not).

## Balun-LNA (single-in, differential-out)

- **B-A1 — CG-CS noise-cancelling balun-LNA** (Blaakmeer/Klumperink/
  Nauta JSSC 2008 — the canonical single-in/diff-out topology).
- **B-A2 — CS + CG split pair** (simple single-to-differential split,
  textbook) — the class baseline/contrast family.

## Round approval record

- Bench round 1 approved families: ____ (user, date)
- Notes: mixer/balun port conventions confirmed against harness before
  transcription; any family that cannot meet the harness convention is
  dropped and logged, not adapted beyond its published form.

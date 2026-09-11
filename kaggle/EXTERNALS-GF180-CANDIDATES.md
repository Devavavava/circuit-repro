# Externals candidate list — gf180 topology-gap campaign (DRAFT for user approval)

Status: **PROPOSAL ONLY — nothing ingested.** Per the nudge-limit directive,
externals ingestion is the sanctioned capability lever with per-round USER
APPROVAL of the candidate list. This list responds to gf180-physaudit-v0
(all 24 specs TOPOLOGY-GAP; wall = joint match/gain/NF design, not device
physics). Approval of a subset here commissions a separate pre-reg
(externals-gf180-v0) covering ingestion mechanics, contamination-ledger
entries, label domain, and the null comparison (existing in-era 0/24 arch).

Constraints applied to every candidate: published, citable, era-appropriate
(0.18–0.35 µm CMOS RF literature); decomposable into the harness token space
(MOS/R/C/L only — NO transformers/coupled-L, which to_spice cannot emit);
within ladder device budgets; single-ended 50 Ω.

## Candidates

**C1 — Inductively-degenerated cascode CS LNA** (Shaeffer & Lee, JSSC 1997,
0.6 µm, 1.5 GHz). THE canonical simultaneous noise/power match shape: source
L + gate L + cascode device + tuned drain load. Directly attacks the
measured bind (NF misses caused by matching, not device floor). Targets:
all narrowband e/m tiers, h01–h04. ~2 FETs + 3 L + 1–2 C.

**C2 — Two-stage tuned CS-CS with inter-stage resonance** (Cha & Lee, JSSC
2003 family, 5.2 GHz, 0.35 µm). Splits the 16–20 dB h-tier gain gates across
two stages (audit: 13–17 dB MSG per stage available); inter-stage L-C match
recovers gain at 5.8 GHz where single-stage margins thin. Targets: h05–h08,
m05/m08 (5.8 GHz), h03/h07 (17–20 dB gates at 3–4 mA). ~2–3 FETs + 3 L.

**C3 — Current-reuse NMOS/PMOS stack** (Karanicolas, JSSC 1996 900 MHz
family). gm-doubling at fixed Idd — attacks gain-per-mA directly, which is
the binding economy on the m07/h02/h07 3–4 mA cells. Era-binfix's e01
credit (NMOS+PMOS pair) was already a primitive cousin of this shape — the
one family with in-program evidence of gf180 fit. Targets: all low-Idd
cells. 2 FETs + 2–3 L/C.

**C4 — Resistive shunt-feedback CS (wideband)** (Bruccoleri/Klumperink/
Nauta wideband-LNA lineage, JSSC 2004, and textbook shunt-feedback). Flat
gain + broadband real input impedance without narrowband L-match — the only
family here that addresses the 0.5–3 GHz band + ripple gates the corpus
never solves. Targets: e08, h08. 1–2 FETs + R feedback (+ optional
shunt-peaked load, Mohan et al., JSSC 2000, for the ripple gate).

**C5 — gm-boosted (capacitively cross-coupled would need diff; use
inverter-style gm-reuse instead) common-gate input** (CG input stage with
CS gm-boost, single-ended variants per Allstot-school CG-LNA line).
Broadband 1/gm input match at low current; NF penalty is model-immaterial
(tnoiMod=0). Alternative wideband path if C4's feedback trades too much
gain. Targets: e08, m05, e05. 2 FETs + 1–2 L.

## Suggested first round

C1 + C3 (highest expected value: canonical match shape + the only family
with in-program gf180 evidence), plus C4 if the wideband cells are in
scope for the round. C2 as round 2 if 5.8 GHz cells resist. Each approved
family enters as a small set of parametric netlist templates → WL tokens
via the standard corpus path, tagged external-source in the store and
contamination ledger; the reasoning loop retrieves them like any corpus
member (no prompt injection, no hand-tuned sizings — sizing stays the
system's job).

## Round approval record

- Round 1 approved families: **C1 + C3 + C4** (user approval of the
  suggested round-1 subset, 2026-09-11, "Fable day 3" session). C2/C5 remain
  candidates for round 2, unapproved. Origin push NOT covered by this
  approval (needs its own per-instance wording); GPU retrieval leg is
  push-gated accordingly.

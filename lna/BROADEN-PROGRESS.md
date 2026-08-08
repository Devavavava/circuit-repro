# WP-BROADEN overnight run — progress log

> **☀ MORNING TL;DR:** All 5 checkpoints ran clean. Headline: **Gate B1 on gps-l1 is
> CLOSED** — the broadened generator (P5-v3) produced **2 novel feasible gps-l1 LNAs**
> (seq0089, seq0215) meeting S11/S21/Idd, where the hand-built templates couldn't
> co-close the match. P5-v3 also lifted narrowband diversity (NDL@256 **73→100**) and
> opened a **new wideband generation channel** (NDL 35), all tripwires quiet. **Two
> honest gaps:** (1) NF is advisory/gated-off, so these hit gain+match+current but
> their noise (~4.5 dB) is over gps-l1's 1.8 dB target — the port-noise harness is now
> the top pipeline gap; (2) **wideband-sdr is still 0** (its generation channel is
> thin). Everything committed + pushed to `lna-data` (through `dfb77c3`).

**Goal:** close Gate B1 (≥1 feasible on gps-l1 AND wideband-sdr) via the plan's
intended sequence — label the new gain-boosted/wideband families → P5-v3 fine-tune
→ generate variants → curated-size. Branch `lna-data`, all work committed + pushed.

**Starting state (2026-08-08, from the EXIT+BROADEN checkpoint):**
- WP-EXIT done: Stage-3 phase exit met, wifi24 curve 367→187 SPICE-min/design,
  6 feasible-novel designs. Committed `ae7f5e0`.
- WP-BROADEN constructors done: 92→118 archetypes (20 gain-boosted + 10 wideband).
  Committed `a14959c`. gps-l1 gain wall broken (two-stage S21 17.5 @ Idd 2.76) but
  input match won't co-close under hand-sizing → Gate B1 is a generator job. `9c11961`.

**The 5 checkpoints (this run):**
1. Label & benchmark the new families vs the hard specs (log stratum-T L2 rows).
2. Build the P5-v3 training data (emit-train incl. new archetypes + emit-winners).
3. P5-v3 fine-tune on the WSL GPU (`<LNA_NB>`/`<LNA_WB>`).
4. Generate from P5-v3 + NDL@256 + tripwires (adopt-only-if-better vs v2).
5. Curated-size the generated variants → Gate B1 attempt; write up + commit.

Each checkpoint's result is appended below as it completes. Honest reporting: if a
step doesn't move the needle, it says so.

---

## CP1 — Label & benchmark the new families ✅
Sized all 30 new-family archetypes vs their target specs (best of 2 seeds,
all-free ZOAF), logged one L2 stratum-T row each.
- **gps-l1: 0/20 feasible.** Closest: `cscs_dg0_tank-R_bf1` (S21 15.0 @ Idd 2.92,
  viol 1.003 — *entirely S11*), `cscs_dg1_tank-R_bf1` (S21 14.1 @ Idd 2.73),
  `cscs_dg1_tank-R_bf0` (S21 15.3 @ Idd 3.40). Two-stage repeatedly clears the
  S21≥15 gain wall; **every** candidate is blocked only by S11≈0 (input match).
- **wideband-sdr: 0/10 feasible.** Closest: `rfb_shunt_peak_bf0_cc0` (S21 8.6,
  ripple 0.76, viol 1.183), `rfb_R_bf0_cc0` (S21 7.7, ripple 1.38). Wideband is
  short on gain AND match together.
- **Read:** confirms at scale what the probe found — the families have the right
  structure (gain), but all-free sizing won't co-close the 50Ω match. 30 labeled
  rows now in the store (gps-l1 + wideband-sdr keys), feeding the benchmark and the
  generator's stratum-T. Store no longer wifi24-only.

## CP2 — Build P5-v3 training data ✅
Regenerated both training files (old ones backed up to `*.pre_broaden.json`):
- `templates_train.json`: **2474 rows from 118 archetypes** (was 92) — the 26 new
  gain-boosted/wideband families are now in the generator's stratum-T, tagged
  nb=2252 / wb=222.
- `winners_train.json`: 965 rows (92 winners, 10 feasible), all nb (no wideband
  feasibles exist yet — expected).
- Note: wb is thin (~9% of template rows, 0 winners) → the generator will be
  stronger on nb (two-stage) than wb. Honest limitation given 10 wb archetypes and
  no wb feasibles to reinforce. Both files valid JSON; one tolerable augment failure
  in emit-winners (965 rows still written).

## CP3 — P5-v3 fine-tune (WSL GPU) ✅
Warm-started from `ft_p5.pth` on the expanded data; overwrote `ft_p5_v2.pth`
(old one backed up to `ft_p5_v2.pre_broaden.pth` for compare/revert).
- Dataset: 3531 corpus + 2230 template (118 arch) + 965 winner + 1008 replay =
  **7734 train / 736 val**.
- **Best val 0.2300 at epoch 1** (classic overfit-by-epoch-1; best-val checkpoint
  saved). 527s on the RTX 3050. Exit 0.

## CP4 — Generate + NDL@256 + tripwires ✅
Sampled 256 nb + 256 wb from P5-v3 (seed 1337).
- **nb NDL@256 = 100** (families 99), 256/256 terminated — vs old-v2 **73** and
  baseline 60. Big diversity gain from the expanded template set. **ADOPT**
  (adopt-only-if-better cleared).
- **wb NDL@256 = 35** (families 35, wideband-sdr screen), 255/256 terminated —
  a *new* wideband generation channel (no prior baseline). The `<LNA_WB>` token now
  produces distinct wideband topologies.
- **Tripwires all quiet:** feasible-rate 0.50, sigma-drift 1.27, ndl@256 100
  (base 60), wl-families 99 (base 59). P5-v3 is the adopted generator.

## CP5 — Curated-size generated variants → Gate B1 attempt ✅ (partial)
Scanned + closed the P5-v3 generated pools (99 nb vs gps-l1, 34 wb vs wideband-sdr;
light all-free scan → polish-first + curated fallback on the closest 10).
- **gps-l1: 2 feasible — the generator closed the match the hand templates couldn't.**
  - `seq0089`: S11 −13.1 / S21 15.0 / Idd 2.88 — started **matched but gainless**
    (S11 −13.7 / S21 2.4), polish drove **S21 2.4→15.0 while holding S11**. This is
    the whole thesis: the generator supplies an input network that co-sizes to 50 Ω,
    then gain is added on top. Hand templates had gain-without-match; these have both.
  - `seq0215`: S11 −14.4 / S21 15.4 / Idd 2.94 (polish). Both logged (recipe
    `p5v3-gen-v1`), novel, distinct.
- **wideband-sdr: 0 feasible.** Closest `seq0198` curated S21 9.8 (unmatched);
  others match (S11 −14.9) but no gain. The wb channel is newer/thinner (34
  screened-novel, 222 template rows, no wb winners) — gain+match+ripple didn't
  co-close this pass.
- **⚠ Honest caveat on gps-l1:** feasibility is on the **gated** constraints
  (S11/S21/Idd). NF is gated off pipeline-wide (port-noise harness gap, WORKLOG R3);
  the enriched physical NF of these two is **~4.5 dB, far above gps-l1's 1.8 dB
  target**. So the pipeline now designs gps-l1-band LNAs that meet match/gain/current
  — the identified *gain wall* is genuinely closed — but the demanding 1.8 dB noise
  figure is not met and cannot currently be optimized against.

**Gate B1 verdict:** MET on gps-l1 (2 novel generated feasibles, gated constraints),
NOT on wideband-sdr → **Gate B1 half-closed.** The gain-limited spec, thought to
need topology, is solved by the broadened generator — the plan's thesis, confirmed
a second time (P5 broke wifi24's memorization ceiling; P5-v3's two-stage family
broke gps-l1's gain wall). wideband-sdr + the NF harness are the remaining work.

# WP-BROADEN overnight run — progress log

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

## CP5 — Curated-size generated variants → Gate B1 attempt
_pending_

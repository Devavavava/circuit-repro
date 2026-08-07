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

## CP1 — Label & benchmark the new families
_status: starting…_

## CP2 — Build P5-v3 training data
_pending_

## CP3 — P5-v3 fine-tune (WSL GPU)
_pending_

## CP4 — Generate + NDL@256 + tripwires
_pending_

## CP5 — Curated-size generated variants → Gate B1 attempt
_pending_

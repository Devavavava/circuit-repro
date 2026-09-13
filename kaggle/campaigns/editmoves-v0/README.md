# editmoves-v0 — results (COMPLETE, 2026-09-14)

Pre-reg: kaggle/CAMPAIGN-EDITMOVES.md (frozen 3acb0b65/6d6ebfd8). Era: armR
box @ freeze tree; armM kernel era 7e06befc (library/driver identical).
Model: Qwen3-30B-A3B (same tier as editcap v0/v1).

## Scores (13 cells; matched sizing null A = 0/13 @3600)

| arm | closed | median best wm | notes |
|---|---|---|---|
| R (random over menu, seed 1) | 0/13 | −0.934 | beats null A on 8/13 paired; 6/7 S2 cells improved; e07 −0.20 (then best-ever); S1/S3 harmed |
| M (LLM selection) | 0/13 | −0.832 | beats R paired 8/13; **0 invalid picks in 39** |

## Verdict

- **move-value: YES** — valid-by-construction structural moves beat pure
  sizing on the S2 wall even under RANDOM selection. The library, not the
  selector, carries most of the value.
- **selection-credit: WEAK** — closures tie 0–0; M wins the margin
  tiebreak (−0.83 vs −0.93, 8/13 paired). M's edge is mostly HARM
  AVOIDANCE on near-feasible cells (e03: R −0.98 vs M −0.43; h01 R −0.21
  vs M −0.13), not S2 breakthroughs (e07: M −0.19 ≈ R −0.20).
- **The menu format eliminated the validity failure class entirely**
  (v0-C had zero valid edits on 3/13 cells; M: 39/39 picks valid) —
  selection over constrained operators is strictly more reliable plumbing
  than netlist authorship.
- Context from editcap-v2 (same day): raw-netlist 32B closed e07 outright
  — capacity beat both R and M on the one S2 cell that moved. Selection
  over moves at the 30B tier is not the binding lever; the library itself
  (as a diversity source or as guaranteed-valid raw material for a
  stronger selector) is the piece that earned its keep.

Layout: armR/ (box, seed 1) · armM/ (kernel, verbatim adjudication incl.
menus, picks, rationales — gradeable by the editcap rubric later).

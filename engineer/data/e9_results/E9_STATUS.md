# E-9 two-stage campaign — STATUS

- Pre-reg committed BEFORE scoring: ROADMAP §7 (e022db4) + E9-TWOSTAGE.md (d244fe6).
- Goldens GREEN before first commit.
- Runner: tmp/e9_twostage.py ; aggregator: tmp/e9_agg.py ; cells: tmp/e9_results/
- Worktree: tmp/wt-e9 (engineer @ 9efc1b9); AnalogGenie symlinked (read-only dep).
- Total cells: 51  (G2p/G4p/G9/G1pp/G7pp = 5 goals x 3 seeds x 3 arms = 45;
  G11pp = 2 seeds x 3 arms = 6).
- PYTHONHASHSEED=0, <=8 concurrent ngspice, matched budgets, write=False toward lna/.

## Progress: COMPLETE — 51/51 cells. Guided 0/6, random 0/6, sizing 0/6.
## Results appended to engineer/E9-TWOSTAGE.md. Goldens GREEN before/after.
## Falsifier MET: two-stage does not lift the ceiling => ROADMAP §7 (smarter editor).

## Progress log: RUNNING (relaunched after stage-1 stall fix)

DEVIATION recorded: guided/random stage-1 aimed-edit families are narrow
(~50-60 distinct realizable topologies), so the loop cannot collect k=120 UNIQUE
candidates -- it now stops on a stall (no new unique for stall_lim attempts) and
ROLLS the unspent stage-1 budget into stage-2. TOTAL budget B is preserved
(e.g. G2p c: s1=52 + s2=548 = 600). Matched-total parity across arms intact.


Crash recovery: each cell is an atomic JSON; rerun `python e9_twostage.py`
(resume-safe, skips existing non-empty cells) or per-cell
`python e9_twostage.py --cell GOAL ARM SEED`. Aggregate anytime with
`python e9_agg.py`.

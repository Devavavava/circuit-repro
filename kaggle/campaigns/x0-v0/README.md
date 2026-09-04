# x0-v0 — learned-x0 adoption eval (results)

Pre-reg: `kaggle/CAMPAIGN-X0-V0.md` (committed before these numbers were read).
Question: does a learned starting-sizing prior beat BOTH the existing null
(midpoint L1 + uniform CMA restarts) AND a nearest-stored-winner retrieval
lookup, at matched eval budgets, on the 24-spec ladder?

## Label domain

era-x0-0c58bfd7 · host=box · pdk=bptm45 · 24-spec ladder (experimental, not
frozen) · arm-A machinery (`run_arm_a.sh` → `campaign.py --arm A`), identical
invocation per leg — only `LNA_X0_PRIOR` differs (`off`/`retrieval`/`learned`).
Sequential legs, 2026-09-04 00:43 → 07:02 IST. Offline pre-adoption gate passed
before launch (`offline-gate.txt`: learned beats midpoint AND per-kind-mean on
the held-out split; band-overlap honesty holdout in
`offline-holdout-dhruva-s.txt`).

## Headline (computed from `results.jsonl` rows, not summary prints)

| arm | solved | evals-to-first-feasible (20 common-solved) | vs A0 | total evals |
|---|---|---|---|---|
| A0 null | 20/24 | sum 66,650 (mean 3,332) | — | 177,600 |
| A1 retrieval | 20/24 | **sum 50,700 (mean 2,535)** | **−23.9%** | 164,400 |
| A2 learned | 20/24 | sum 55,350 (mean 2,768) | −17.0% | 177,600 |

- **Solved sets are IDENTICAL across all three arms** (no +/− cells anywhere):
  the four unsolved are exactly the four known topology walls
  (cap-e08/h08-wideband, cap-h03-900mhz, cap-h07-gpsband). A warm start does
  not unlock topology-limited specs — as expected: it only moves the first
  CMA-ES mean.
- **A1 − A0: warm starts genuinely help.** −23.9% evals-to-first-feasible;
  biggest single effect cap-h01-wifi 6,300 → 1,250 (the retrieval seed avoided
  escalation entirely). A1 also spent the fewest total evals (fewer
  escalations).
- **A2 − A1 (the adoption-relevant delta): the learned model LOSES to the
  lookup** (+9.2% evals vs A1). Per-spec it ties or trails almost everywhere;
  on cap-h01-wifi it escalated exactly like the null (6,300 vs A1's 1,250).
- Secondary (closest-miss on the 4 walls): both warm starts land closer than
  the null on 3 of 4 (e.g. e08 s11 margin −0.456 → −0.251/−0.271; h03 nf
  −0.115 → −0.074/−0.095) — directionally positive, non-gating.
- Caveats: single arm-level run per leg (seed-to-seed noise floor not sized by
  repeat legs; per-spec seeds=2 internal). e2f values sit on the escalation
  grid, so most per-spec deltas are one grid step; the h01 effect is far above
  grid noise.

## Verdict (per the pre-registered bar — adoption is a USER RULING)

**A2 fails the pre-set bar** ("must beat BOTH A0 and A1"): it beats the null
but not retrieval. Honest-outcome clause: that is the answer, not a bug — the
branch smoke predicted exactly this risk. **A1 (retrieval warm start) is the
adoption candidate**: −24% evals-to-first-feasible at zero model cost, same
solved count, fewer total evals. Queued user rulings: (1) adopt
`LNA_X0_PRIOR=retrieval` as a sizer default or keep off; (2) whether to iterate
the learned prior (more data / features) or park it behind the retrieval
baseline.

## Layout

```
era-x0-0c58bfd7/arm{0-null,1-retrieval,2-learned}/   results.jsonl/.md, designs/, trajectory/, MANIFEST.json
era-x0-0c58bfd7/*.log                                 chain + per-leg run logs
era-x0-0c58bfd7/offline-gate.txt                      pre-adoption offline gate (passed)
era-x0-0c58bfd7/offline-holdout-dhruva-s.txt          band-overlap honesty holdout
```

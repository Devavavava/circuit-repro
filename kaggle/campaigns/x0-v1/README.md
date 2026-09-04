# x0-v1 — warm starts on UNSEEN topologies (results)

Pre-reg: `kaggle/CAMPAIGN-X0-V1.md` (cells, arms, budgets, metrics frozen
before any number was read; blindness check recorded pre-run). Question: does
the x0-v0 ranking (retrieval > learned > null) survive on topologies neither
method has ever seen — the shapes the reasoning loop itself invented?

## Label domain

era-x0v1-eaddd940 · host=box · pdk=bptm45 · driver `kaggle/x0v1_run.py`
(fixed topology per cell, k=1, no LLM) · 14 frozen cells
(`kaggle/x0v1-cells.json`): NOVEL-10 (wl not in the 927-hash store) +
SEEN-4 control. Sequential legs 2026-09-04 11:34→11:57 IST, identical
invocation, only `LNA_X0_PRIOR` differs.

## Headline (from `results.jsonl` rows)

**All 3 arms solved ALL 14 cells** (expected sizable; confirmed). At these
budgets e2f collapsed to a binary per cell: 600 = feasible at base
(2 seeds × 300), 1800 = needed the escalation (3 × 600). The eval therefore
resolves only "escalated or not" — coarser than x0-v0's corpus-screen setting.

| arm | NOVEL-10 e2f sum (escalations) | SEEN-4 e2f sum |
|---|---|---|
| A0 null | 10,800 (4) | 2,400 (0) |
| A1 retrieval | 10,800 (4) | 2,400 (0) |
| A2 learned | **9,600 (2)** | 2,400 (0) |

Per-cell flips vs A0 on NOVEL-10:

- **A1 retrieval: net ZERO on unseen shapes** — avoided one escalation
  (cap-m06-wifi 1800→600) but *caused* one (cap-e02-gpsband 600→1800): the
  cross-shape transplant can actively mislead, exactly the failure mode the
  campaign was designed to expose.
- **A2 learned: net −2 escalations** (cap-h05-ism58 and cap-m04-35ghz
  1800→600; one regression cap-m08-ism58 600→1800; h02 hard for everyone).
  −11.1% evals vs both A0 and A1.
- SEEN-4: uniformly easy (no escalations anywhere) — no discrimination; the
  control strip neither confirms nor contradicts x0-v0's retrieval advantage
  (which showed on hard corpus-screen cells, a different regime).

## Verdict (honest-outcome clause; adoption = USER RULING)

- **The x0-v0 ranking does NOT transfer to unseen shapes.** Retrieval's edge
  was its exact-match answer key; without it, retrieval nets zero (help ≈
  harm). The learned per-kind model was the best arm off-distribution — the
  direction its design predicts (per-kind regularities transfer; neighbor
  transplants don't).
- **Effect size caveat (pre-registered):** the A2 win is 2 binary escalation
  flips out of 10 cells, single run per leg — directionally meaningful,
  within plausible seed noise, NOT a proven delta. The cells (known-sizable
  winners) also made the task too easy to separate arms at base budget.
- Combined evidence for the ruling: known shapes + hard search → retrieval
  clearly best (x0-v0, −23.9%); unseen shapes + easy search → learned
  directionally best (−11.1%), retrieval neutral-to-harmful. This supports
  the **hybrid** option (retrieval on exact topology match, learned or off
  otherwise) over adopting either arm universally. Sharper discrimination
  would need harder unseen cells (e.g. tighter specs on these shapes) — a
  new pre-reg if commissioned.

## Layout

```
era-x0v1-eaddd940/arm{0-null,1-retrieval,2-learned}/  results.jsonl/.md, designs/, MANIFEST.json
era-x0v1-eaddd940/*.log                               chain + per-leg logs
```

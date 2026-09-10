# gf180-physaudit-v0 — results (COMPLETE, 2026-09-11)

Pre-reg: `kaggle/CAMPAIGN-GF180-PHYSAUDIT.md` (frozen a458bb05; two logged
pre-run amendments, 4b3e4eca + follow-up). Driver: `kaggle/gf180_physaudit.py`.
Box-side, ~500 single-device ngspice decks, wall < 1 min. Era-audit-df7d9052.

## VERDICT: all 24 specs TOPOLOGY-GAP — the gf180 wall is NOT device physics

**T1 gain axis (classification basis):** at each spec's Idd cap the
`nmos_3p3` device offers a cumulative MSG ceiling of **39–63 dB vs gates of
10–20 dB** (worst case 5.8 GHz: 39.1 dB vs 16 gate = 23 dB headroom; best
bias universally Vgs 1.5 / Vds 2.2 / ~0.13 mA/µm, ft ≈ 25 GHz). Zero specs
gain-infeasible, zero borderline. The two historically solved cells
(cap-e01-wifi, cap-m06-wifi) classify TOPOLOGY-GAP — validation fence
PASSED.

**T2 noise axis (advisory per Amendment 2):** the PDK card sets
**tnoiMod = 0 and rgateMod = 0 on every bin** — no induced-gate noise, no
gate-resistance noise. Model NFmin ≈ 0 dB by construction (measured ≤ 1e-14
dB; NF(50Ω) frequency-flat with Rn ≈ γ/gm — single-correlated-source
signature). Under the harness's own model, NO nf gate can be device-bound.
Advisory realizable-matching floors (grid method): 0.47–0.68 dB, far below
every gate. Corollary: fmax is likewise undefined under rgateMod = 0
(Re[Y11] ≈ 0, Mason's U numerically degenerate — recorded as null in rows).

**Interpretation:** the campaigns' persistent gf180 0/24s with NF 7–8 dB and
S21 misses are CIRCUIT-LEVEL failures — the joint simultaneous-match + gain +
Idd design problem — on a device with enormous headroom. The 45nm-bred
corpus does not contain the right gf180 shapes and the search does not find
them; that is exactly the externals-ingestion case.

**Model-fidelity caveat (recorded, not actionable here):** tnoiMod=0 also
means measured NF numbers program-wide on gf180 UNDERSTATE real-silicon NF
(no induced gate noise). Any future claim about real-world gf180 NF must
carry this caveat; within-model comparisons (all campaign arms) are
unaffected.

## Method fences (all green)

- Smoke repro of check_pdk_live gf180 deck (id 5.67e-4 A, gain 9+ dB).
- W-scaling invariance at W = 60 µm: ΔMSG ≤ 0.15 dB, J-ratio within 5%.
- Independent noise paths (grid `.noise` series-Rs vs sp-donoise NF vector)
  agree within 0.20 dB at 50 Ω; grid-min ≥ sp-NFmin (upper-bound sanity).

## Pre-declared consequence now active

The DEVICE-INFEASIBLE set is EMPTY → no spec-relief ruling is warranted on
physics grounds. The full ladder is the TOPOLOGY-GAP set → the sanctioned
next lever is **externals ingestion** (candidate list for per-round user
approval: `kaggle/EXTERNALS-GF180-CANDIDATES.md`; ingestion itself needs its
own pre-reg and contamination-ledger entries).

## Layout

```
era-audit-df7d9052/results.jsonl   24 rows: gates, gain_best (k, bias, J,
                                   stage MSG, ft), nf floors, class
era-audit-df7d9052/results.md      verdict table
era-audit-df7d9052/raw/            all ~500 decks + verbatim ngspice logs + csv
```

# capacity_tests — post-v0 verification diagnostics (2026-08-26)

Three exploratory tests run when v0 was parked, to answer questions the retrospective
left open. **These are diagnostics, not pre-registered protocol-scored results** — honest
reads at modest budget (300 evals, 3–5 seeds), not adoptable engineer-line experiments.

All harnesses import the main checkout's `lna/` (via `$LNA_DEPS_ROOT`) so data, the v7
checkpoint, and the ZOAF clone resolve even from a worktree, and they load the ladder
specs by path. None of them write the label store.

Run everything after `source env.sh`.

## 1. The difficulty ladder (`lna/specs/`)

Six synthetic specs spanning easy→hard across bands the flagship work never optimized
(z0 = 50 Ω, 45 nm model, IIP3 left `unsupported`):

| rung | spec | band | NF ≤ | S21 ≥ | S11 ≤ | Idd ≤ | class |
|---|---|---|---|---|---|---|---|
| R0 very easy | `easy1g` | 1.0 GHz | 4.0 | 8 | −8 | 12 | narrowband |
| R1 easy | `n78-35` | 3.5 GHz (n78) | 3.0 | 12 | −10 | 8 | narrowband |
| R2 moderate | `sub900` | 0.9 GHz | 2.5 | 15 | −10 | 6 | narrowband |
| R3 moderate | `wb05-2` | 0.5–2 GHz | 3.5 | 12 | −10 bw | 8 | wideband (inductorless ok) |
| R4 hard | `unii55` | 5.5 GHz | 2.0 | 18 | −12 | 5 | narrowband |
| R5 very hard | `xband8` | 8.0 GHz | 1.8 | 20 | −12 | 4 | narrowband (ceiling probe) |

## 2. ZOAF vs CMA-ES (`zoaf_vs_cmaes.py`) — request 3

Refreshes FINDINGS §43.2 (was CMA-ES 4/5 vs ZOAF 1/5) on a varied grid so overtraining
can't bias it: **6 topologies (8→20 devices) × 14 specs × 5 seeds = 420 cells**. Both
optimizers run through `null_sizer`'s counter on the same objective/deck/box at a budget
matched per cell (ZOAF's natural schedule; CMA-ES matched to its eval count).

```
python capacity_tests/zoaf_vs_cmaes.py --seeds 5 --workers 24
python capacity_tests/zoaf_vs_cmaes.py --aggregate-only --out capacity_tests/results/zoaf_vs_cmaes.jsonl
```

**Result:** CMA-ES **88/420** feasible vs ZOAF **24/420**. Head-to-head: only-CMA-ES 67,
only-ZOAF 3, both 21, neither 329. CMA-ES has the better objective on **317/420** cells
(median 3.43 vs 4.01). CMA-ES wins or ties every spec — including untuned bands (`n78-35`
15/30, its best). CMA-ES decisively beats ZOAF, on the tuned and untuned specs alike.

## 3. Capability ladder (`capacity_ladder.py`) — request 2

Is capacity universal or clustered around the tuned specs? Two arms, same sizer:

- **arm A** — the v7 generator makes a 96-topology pool; each spec screens it (L0) and
  sizes the L0-passers.
- **arm B** — a fixed pool of 6 varied corpus topologies is sized to each spec.

Arm A vs B separates *generator* overtraining from *sizer* capability.

```
python capacity_tests/capacity_ladder.py --pool 96 --seeds 3 --workers 24
python capacity_tests/capacity_ladder.py --aggregate-only --out capacity_tests/results/capacity_ladder.json
```

**Result — specs solved: arm A 4/9, arm B 6/9.**

| spec | arm A | arm B | reading |
|---|---|---|---|
| easy1g, n78-35, sub900 (untuned) | ✅ | ✅ | sizer capacity is **universal** across untuned bands |
| wifi24 (tuned ref) | ✅ | ✅ | |
| wb05-2, unii55, xband8 (hard) | ❌ | ❌ | a **physical ceiling** (high-freq / wideband), not overtraining |
| dhruva-l5, gps-l1 (hard tuned) | ❌ | ✅ | hard tuned wins came from **curation**; a fresh generated pool doesn't reproduce them |

Takeaway: the **sizer** is not overtrained — it solves untuned bands as readily as tuned
ones. The **generator** solves easy/moderate untuned specs from scratch but does not
reproduce the hard curated solutions (dhruva/gps) in a fresh pool. The hardest rungs are a
real capability wall for both arms.

## 4. Seeing the designs (`render_design.py`, `export_winners.py`) — request 4

`lna/render_design.py` prints a design human-readably — TOPOLOGY (device pins → nets),
SIZING (µm/nm/Ω/F/H), and SPECS ACHIEVED — for the flagship, any stored design, or an
exported test winner:

```
python lna/render_design.py --design lna/repro/dhruva-best/dhruva-simul   # flagship
python lna/render_design.py --row 58da009b6622b8d7 wifi24                 # any stored design
python lna/render_design.py --design <dir> --deck                         # + SPICE deck
```

`export_winners.py` re-derives the feasible designs the tests found (CMA-ES is
deterministic per seed) and writes each as a renderable design dir under
`capacity_tests/designs/<name>/`, plus a `manifest.json`:

```
python capacity_tests/export_winners.py
# then render one:
python lna/render_design.py --design capacity_tests/designs/<name>/design
# or all of them:
for d in capacity_tests/designs/*/; do python lna/render_design.py --design "$d/design"; echo; done
```

## Files

| path | what |
|---|---|
| `zoaf_vs_cmaes.py` / `capacity_ladder.py` / `export_winners.py` | the three harnesses |
| `results/zoaf_vs_cmaes.jsonl` + `.log` | 420-cell grid + aggregate |
| `results/capacity_ladder.json` + `.log` | arm A/B cells + aggregate |
| `designs/<name>/` | exported feasible designs (tokens + params + meta), gitignored `_work/` |

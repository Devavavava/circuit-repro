# Handover — executor session 1 → next

**From:** an Opus 4.8 executor session, 2026-08-06 · **Repo:** `C:\Users\Devavrat\circuit-repro`
· **Branch:** `lna-exec` (7 commits, off `main` @ `535104c`, **never pushed**)

You are picking up execution of the LNA plan set in
`.claude/worktrees/lna-plans/lna/plans/` (start at `00-OVERVIEW.md`). That set is
the roadmap; this file is what has actually been *done*, what was *found*, and
exactly where to resume. Read `WORKLOG.md` (entries R1/R2 are mine) and
`FINDINGS.md` (§5 P0 block is mine) for the measured detail.

**The whole story, in order:** `lna/JOURNEY.md` is the cross-agent narrative
history (origins → phase 1 → phase 2 → Dhruva → the honesty corrections →
current frontier). Every future session appends/edits its own stage there as
part of its wrap-up, same commit discipline as this file and `FINDINGS.md`.

**How the machine works, not how it got here:** `lna/STRUCTURE_LOGIC.md` is the
architecture doc — every building block (vocabulary/topology, data sources,
generator, eval ladder, sizing/verification, label store, critic, search, the
loops, integrity mechanisms), what's trained vs. rule-based, and what feeds
what. Any session that changes the architecture updates the affected section
there as part of its wrap-up, same discipline as `JOURNEY.md`.

---

## Session 2 — Phase 2 Stages 0–3 + last-mile + **★ STAGE 3 PHASE EXIT MET** (curve 967→367→**187**, 6 feasible wifi24 LNAs) + **★★ WP-BROADEN: Gate B1 gps-l1 CLOSED** (P5-v3 → 2 novel feasible gps-l1 LNAs; NDL 73→100 + new wb channel). Remaining: wideband-sdr + the NF harness.

## Session 3 — **WP-DHRUVA (blind protocol)** — paper-target spec ladder (plans2/08-DHRUVA-GOAL.md) — **★ D0 + ★★ D1 + ★★ D2 MET** (one blind-v1 3-stage rfb_cs3 family feasible on ALL four bands L5/L2/L1/S; S11≤−10 over 1.1–2.5 GHz. Attribution: assistant-authored generic topology + automated sizing — NOT a P5-generator discovery. Repro: lna/repro/)

## Session 4 (2026-08-08/09) — **Track A: the NF harness goes live** (WP-D1 + WP-D4 + stability + Gate-D3 push) · **Track B: ★ a *generated* dhruva-l1 tier-1 feasible**

Two agents, one worktree, branch `lna-data`, **never pushed**. Track A owned all
commits; Track B worked in sidecars (`lna/trackb_g4.py`, `lna/_trackb_*`). Full
measured detail in **FINDINGS §13**; Track B's own report is
`lna/data/reports/trackb-p5v6-2026-08-08.md`.

### What moved

* **★ WP-D1 DONE — NF is a hard constraint.** The port-referred `noise` block is
  deleted from the sizing deck (finding #7); the only NF in the store is the
  golden-validated series-Rs one (`extract.py --selftest` → **3.012469 vs 3.0103**,
  `ref/check_nf.py` GREEN). All **20** legacy rows relabelled (`lna/relabel_nf.py`,
  replay-fenced, recipe bumped `<old>+nfrs-v1`): **20 relabelled, 0 quarantined**.
  **The old port NF flattered every design without exception** — series_rs minus port
  was min +0.55 / median +2.32 / mean +3.93 / max +12.58 dB, and two rows had read
  *negative* NF. The four dhruva specs now gate `nf_db`; `size._spec_for_sizing`
  honours the YAML (it used to force `unsupported` for every spec).
  **NF is measured inside the sizing loop** — a supported-but-missing metric counts as
  fully violated and flattens the objective. Measured cost 0.07 s on top of 0.07 s.
* **★ WP-D4 DONE — the survivor contrast (`lna/nf_contrast.py`).** 14 distinct
  feasible designs re-judged unchanged: **tier-1 14/14, tier-2 (NF gated) 2/14.**
  **wifi24 is solved at tier-2** — `seq0220` (novel *generated*: S11 −13.8 / S21 12.6 /
  Idd 2.46 / **NF 2.43**, the first design here to clear all four gated constraints)
  and the hand `ref24_tapped` reference (NF 2.00). Everything else dies: **dhruva by
  +5.4…+8.6 dB**, gps-l1 by +2.2/+2.6, four more wifi24 by +0.26…+0.92.
* **★ NEW HARNESS — two-port stability, free.** K / |Δ| / μ / μ_src at f0 and worst
  in-band, derived from the S-matrix `sp` already computes (zero extra sim time),
  advisory only. Validated in `lna/ref/check_stab.py` against a closed-form series-R
  two-port (K = μ = 1 exactly, the boundary case) + unilateral / negative-resistance
  goldens. **Verdict: Gates D1/D2 are NOT qualified by oscillation risk** — the dhruva
  4-band winner is unconditionally stable on all four bands in-band (K_min 10.1–28.4)
  *and* over 0.1–20 GHz (K_min 12.9–29.0). **But two feasible wifi24 sizings are
  potentially unstable in-band**: `seq0009` curated-v1 (K_min **0.352**) and `seq0220`
  polish-v1 (K_min 0.832) — and the same `seq0220` topology sized by curated ZOAF is
  fine (K_min 4.08), i.e. **the min-margin polish walked it into a potentially
  unstable region because stability is in no objective.**
* **⚠ BUG FIXED (found by Track B, landed by Track A) — `size.polish` ignored the
  device box.** It scaled by (1±step) with no clamp to `kind_ranges`, so
  polish-derived points left the spec's declared limits. **6 of 19 feasible rows were
  out-of-box.** Now clamped (incoming point too; a coordinate on a bound cannot step
  out). Re-deriving the 5 non-Track-B rows: **all five return FEASIBLE and IN-BOX** —
  no tier-1 claim lost. **One tier-2 claim did die**: wifi24 `seq0079` passed NF at
  2.48 only on an out-of-box 18.25 nH inductor; in-box it reads **2.57 → FAIL**
  (tier-2 3/14 → 2/14).
* **Gate D3 push — NOT met, but the front moved a long way and prong (a) is settled.**
  *(a) Trading the winner's 12 dB of gain slack for NF does not work*: NF-aware polish
  on the rfb_cs3 family buys 2.7–4.3 dB of NF (dhruva-s 8.88→6.17, l1 9.95→5.64) and
  **pays with the broadband match** (s11_max → −2.6 / −0.4), not with gain — the
  feedback resistor that sets the match is the element that sets the noise.
  *(b) Two generic textbook low-noise families added* (`gmb_cg_lna`, `nc_cgcs_lna`;
  archetypes 135→148, 13 screen-passing, all `blind-v1`). **The broadband-match wall
  for these was a BIASING DEFECT, not a topology limit**: CG gate tied to VDD (Vgs =
  VDD, deep triode) and the aux amp's gate on a DC-grounded node (Vgs = 0, never
  conducts). Undriven+bypassed CG gate (bias.py owns the current) + AC-coupled aux
  gate took s11_max from ≈ −3 dB to **−19.7 dB**.
  **Best measured dhruva-s points (two ends of the family's NF↔gain Pareto):**
  `nccgcs_s1_tank` → s11_max −14.8 ✓ / **S21 28.6** / Idd 12.99 ✓ / NF 5.68 (viol 0.669);
  `nccgcs_s1_R` → s11_max −9.4 / S21 22.4 / Idd 6.75 ✓ / **NF 4.38** (viol **0.566**).
  Incumbent for comparison: viol 1.537 on NF alone.
* **★★ TRACK B MET ITS GOAL — a *generated* dhruva-l1 tier-1 feasible.**
  `ft_p5v6_nb_s1337/seq0192`, wl `20bca9a7c3a5f263`: **S11max −11.49 / S21 29.19 /
  Idd 11.09**, replay-verified, in-box, matching none of the 148 archetypes or 41
  corpus circuits. This is the "the pipeline designed it" claim Gates D1/D2 could not
  make (those were an assistant-authored archetype + automated sizing). NF 9.63 dB —
  tier-2 not met, ~3.8 dB of S21 slack left to trade. **The P5-v6 checkpoint itself
  was REJECTED** under adopt-only-if-better (NDL@256 93 vs baseline 100); the design
  stands anyway because it is replay-verified SPICE truth, not a model claim.

### Gate state after this session

| gate | state | number |
|---|---|---|
| D0 / D1 / D2 | MET (unchanged, tier-1) | 4-band family `rfbcs3_tank_cc21_bf0`, stability-clean |
| D1 "generated" | **MET (Track B)** | `seq0192`: S11max −11.49 / S21 29.19 / Idd 11.09 |
| **D3 (tier-2 NF)** | **NOT MET** | best dhruva-s viol **0.566** (`nccgcs_s1_R`, NF **4.38** vs 3.5, from the incumbent's 8.88) |
| wifi24 tier-2 | **MET** (not a numbered gate) | `seq0220` NF 2.43 + `ref24_tapped` NF 2.00 |
| B1 wideband-sdr | still 0 | best `nccgcs_wb_s0`: S21 9.9, NF 5.42, viol 1.551 |

### Known metric gaps / caveats to carry forward

1. **NDL overstates novelty** (Track B): its novelty reference is the 41-circuit
   corpus only, **not** the archetype set, so ~**51%** of screen-passing generator
   samples are verbatim `templates.py` regenerations that NDL scores as novel. Fix =
   extend the novelty reference to include the archetypes; until then treat NDL as an
   upper bound.
2. **Stability is advisory and frequency-only** — no process corners, no load pulling,
   ideal-element behavioral ngspice with no package/layout parasitics.
3. **One superseded out-of-box Track-B row remains** in the append-only store: filter
   `provenance.how == "polish-r0"`; the good row is `how == "bounded-polish"` /
   `in_box_verified: true`. ~200 Track-B rows carry `provenance.trackb`.
4. `zoaf_cfg.nf_gated` separates the two label domains. **Every row written before
   this session is implicitly `nf_gated: false` (tier-1).** Do not train or rank
   across the two without conditioning on it.

### Where to pick up (highest value first)

1. **The Gate-D3 blocker is now NOISE ALONE, and probably a *search* failure rather
   than a family limit.** `nc_cgcs` reads 5.68 dB where a noise-cancelling CG+CS
   should reach ~2.5–3 dB (best measured 4.38), which says the sizer never lands on
   the cancellation locus
   (it holds only at a specific gm/load ratio, and the blended feasibility-first
   objective has no reason to sit there). **Next lever: a cancellation-aware start or
   an explicit NF-only inner optimization stage — not more seeds.** Within the family
   the measured trade is ~+1.3 dB NF per +6 dB gain, so gain is cheap; ~0.9 dB of
   noise (dhruva-s) to ~1.9 dB (the other three bands) is the whole remaining job.
2. **Put stability in the objective (or at least in the polish guard).** It is
   measured and free now, and polish is demonstrably capable of walking a design into
   K < 1. Cheapest useful version: refuse a polish step that takes K_min below 1.
3. **Re-run the two K < 1 wifi24 designs** (`seq0009`, `seq0220`) through curated
   sizing and record whether the tier-2 wifi24 claim survives a stability guard —
   `seq0220`'s tier-2 PASS is the curated row (K_min 4.08), so it should, but say it
   with a number.
4. **Decide `device_budget`.** [3,16] is not currently binding but is one gain stage
   away from being so for every low-noise family. If it is raised, justify it from
   device counts in real published LNAs, exactly the way `[3,12] → [3,16]` was
   justified by corpus calibration — do not raise it to close a gate.
5. **Feed the D3 rows back to the generator.** There are now NF-gated labels
   (recipe `blind-v1-nf`, `zoaf_cfg.nf_gated: true`) and two new blind-v1 low-noise
   families in `templates.py`; `emit_winners` + a P5-v7 fine-tune on the NF-gated
   domain is the natural expert-iteration step.

### Track C — consolidation (σ relabel · critic retrain · benchmark refresh · hygiene)

Ran after A and B, alone in the worktree. Full detail in **FINDINGS §14**.

* **σ(S21): the "drift" was mostly a measurement artefact, and best-of-3 halves
  what is left.** Two defects: `_sigma_from_repeats` grouped by `(wl_hash, spec)`
  only, pooling *different recipes* and *different NF gating* — **81 of 89
  multi-row keys were mixed that way** — and it estimated a stdev from n=2. On the
  same 19 wifi24 repeat-probe keys, 9 seeds/key gives **σ_single = 1.478 dB**
  where 2 seeds/key gives 0.570; **best-of-3 → σ = 0.726 dB** (2.0× quieter, 3×
  the sims). So σ was always ≈1.5 dB here; the 0.32/1.02/1.27 series was
  under-sampled and contaminated. **06-LAST-MILE's ≲0.5 dB bar is still NOT met.**
  `campaign.sigma_key` now conditions on `(wl_hash, spec, recipe, nf_gated)`;
  `size.size_best_of_k` is the new label definition (`recipe candidate-v1+bo3`,
  stamps `zoaf_cfg.seeds` + per-metric `label_sigma`).
* **Critic retrain on `v4-train` (734 rows; 730 usable, was 261).** A bug first:
  `_margins` read `s11_db` only, so **every dhruva row — ~240, including the whole
  Track-B corpus — was silently dropped** (broadband specs gate `s11_max_db`).
  Fixed, plus spec conditioning everywhere and a provenance-based source-shift
  split (420 generated rows, was 142). **★ The source-shift gap closed: ρ(S21)
  0.221 → 0.585 (ridge) / 0.609 (GNN)** — and the *same code on the old v2-train
  snapshot reproduces the old numbers exactly, so it is the data, not the code.
  Within-spec: ridge **0.753** on the 200-row Track-B dhruva-l1 pool, where
  **WL-kNN collapses to 0.003** (that baseline lived on duplicate structure; the
  Track-B samples are novel by construction). **★ The GNN now ships as critic v1**
  (02-CRITIC §2 rule) — it takes ρ(S21) and rank accuracy on both splits (family
  **0.851** vs 0.790 ridge / 0.687 kNN; source-shift **0.609** vs 0.585 / 0.370)
  and is the only arm with usable uncertainty (ensemble std ranks |error|, ρ 0.54 /
  0.53 — what 03-SEARCH's `mean − β·std` needs). **Not a sweep:** ridge ties its
  source-shift prec@20% (0.655) and beats its ρ(S11) there. NF is a trained head
  now (711 labelled rows; ρ 0.66–0.70 on the family split, better than S11).
* **⚠ Gate C1 verdict, honestly: the Spearman half passes on BOTH splits for the
  first time; the enrichment half is no longer reachable by any model.**
  Enrichment = precision@20% / base-rate ≤ **1/base-rate**, and as the pool
  improved the base rate went 0.27 → 0.46 on source-shift, so the ceiling fell
  3.74× → **2.20×** (family: 2.02×). "≥2×" now silently means "*perfect*
  precision@20%" — which is exactly what the v2-train pass was. **This needs an
  explicit rebaseline decision from the user, same shape as the NDL gap.**
* **Benchmark refreshed at full budget** (`seeds=1,2`, `budget=8,8,2`), candidate
  set taken from the feasible record (in-box rows preferred) so it now includes the
  generated dhruva-l1 feasible `seq0192` and the 4-band `rfbcs3` archetype, with
  **tier-1 / tier-2 reported separately** and `K_min` per cell.
  **Result (tier-1 / tier-2 of 12):** wifi24 **10/12 · 1/12** · gps-l1 2/12 · 0 ·
  wideband-sdr **0/12** · 0 · dhruva-l5 1/12 · 0 · dhruva-l2 1/12 · 0 · dhruva-l1
  **2/12** · 0 · dhruva-s 1/12 · 0. wifi24 is the solved class at full budget
  (4/6 lean → 10/12; the only misses are the two dhruva-native designs).
  **Tier-2 is one cell in 84** — `seq0220` on wifi24, NF 2.34 — so with the hand
  `ref24_tapped` reference (a netlist, not in this table) the program's tier-2
  record is two designs, one generated. The dhruva wall is `s11_max` on 10–11 of
  12 per band. **8 of 84 cells read in-band K_min < 1, one of them tier-1
  feasible** (`seq0009` on wifi24, K_min **0.242**, curated) and `seq0046` on
  dhruva-l1 at **−2.04**.
* **Hygiene.** `.gitignore` gained `lna/out/_*`, `*.pre_*.json`, `*_train_*.json`
  and a junction setup note (verified: junctioned `misc`/`AnalogGenie`/`AutoCkt`
  do **not** appear in `git status`). Four generator run dirs tracked by
  `meta.json` only. On `lna-exec` (the other checkout) the 10 concluded P4
  logit-bias sweep dirs are committed, `meta.json` only. Both branches pushed.
* **Regression quartet green** after everything: vocab **MATCH**, screen **59.4%**
  (114/192), pipeline_yield **40/42** (95.2%, the one failure is 1081's known
  singular matrix), `check_ref` / `check_nf` / `check_stab` **GREEN**,
  `calibrate_specs` **ALL ACCEPTANCE CRITERIA MET**.
* ⚠ **A Track-A `d3_campaign.py` was still running when Track C started** and
  appended rows 735–772 interleaved with the σ probe. Nothing broke — that is what
  the append-only store and sha256-pinned snapshots are for, and `v4-train` still
  verifies at 734 lines — but it is why `_sigma_from_repeats` and both eval drivers
  now take `snapshot=`: **a number computed against a live store is not
  reproducible once anyone else is writing.**

**Queued for the next session (measured, not executed tonight):**

1. **Gate D3 is ~0.9 dB away on dhruva-s.** The lever is a cancellation-aware
   start or an **NF-only inner optimization stage** for the noise-cancelling CG+CS
   family — Track A measured that the blended feasibility-first search never sits
   on the cancellation locus. Not more seeds.
2. **Put stability in the polish/curated objective** (K ≥ 1, advisory → gated).
   Polish walked `seq0220` into K_min 0.832 because nothing penalised it.
3. **NDL metric gap:** the novelty reference is the 41-circuit corpus only, not the
   148 archetypes, so ~51% of screen-passing samples are archetype regenerations
   scored as novel. Extending the reference changes a frozen protocol → **explicit
   rebaseline decision by the user.**
4. **Gate C1's enrichment bar** (above) — same class of decision.
5. **`wideband-sdr` still has no feasible.** The fixed-bias noise-cancelling
   families are the obvious candidates (they match to −19.7 dB after the bias fix).


### Tools added this session

```bash
python lna/relabel_nf.py --audit|--run        # NF label-domain migration (replay-fenced)
python lna/nf_contrast.py [--md]              # NF-gate survivor contrast + in-box audit
python lna/ref/check_stab.py                  # stability harness validation + winner audit
python lna/d3_campaign.py --spec dhruva-s --cls nb --seeds 2 --polish   # NF-gated labeling
python lna/trackb_g4.py                       # Track B's generated-candidate driver
LNA_NF_GATE=0 python ...                      # session-wide escape hatch to tier-1 gating
# Track C
python lna/campaign.py --sigma-probe [--gen] --k 3 --reps 2      # best-of-k label-noise probe
python lna/critic.py --eval --snapshot v4-train --sigma-recipe candidate-v1+bo3
"<analoggenie py>" lna/critic_gnn.py --eval --snapshot v4-train --sigma-recipe candidate-v1+bo3
python lna/benchmark.py --all-feasible --seeds 1,2 --budget 8,8,2 --out-json <ckpt> [--resume <ckpt>]
python lna/datastore.py --snapshot v4-train   # pin a training set (sha256 + line count)
```

---

## Session 5 (2026-08-09) — concurrent agents on `lna-data`

> **Section conventions.** Several agents work this session in the same worktree
> and each owns a clearly-marked sub-block below. Append yours; do not edit
> another's. Commit only your own files with explicit path adds.

### ▸ Sub-block: control experiment + metrics plumbing (owner: the control-arm executor)

**Files owned:** `lna/finetune.py` (additive flags only), `lna/_ctrl_*`,
`lna/out/ft_ctrl*`, FINDINGS §16, plus the two plumbing fixes. Commits
`f9114bb`, `1ee889b`, and the §16 write-up. Full measured detail in
**FINDINGS §16**.

**Two plumbing fixes (done, quartet green after).**

1. **The four remaining ref-v1 novelty call sites are migrated to ref-v2**
   (`campaign.py` / `loop.py` / `size.py` / `trackb_g4.py` — the follow-up §14.5
   left open). They now call `novelty.reference()` and stamp `novelty_ref` into
   what they log. **This is not cosmetic:** the headline curve reads
   **11 → 7 feasible-novel designs, 310.1 → 487.3 SPICE-min/design**, because
   four store designs the corpus-only check called discoveries are WL-exact
   regenerations of archetypes that were *already in the 92-archetype training
   set* when those samples were drawn. **⚠ That qualifies the Gate-B1 gps-l1
   claim:** `seq0089` and `seq0215` ARE hand templates (`cs_gi1_dg1_cx1_cc0_R_bf1`
   / `..._cc1_tank_bf1`) — the sizing result stands, the topology-discovery half
   does not. Track B's `seq0192` and the wifi24 tier-2 `seq0220` (wl `396b9032`)
   both survive as genuinely novel. Details + the fourth entry (a phantom created
   by `seq*.txt` filename reuse) in **FINDINGS §16.4**.
2. **`critic_gnn.py`'s `C1?` column now reports the restated gate** (§14.6), with
   `ofceil` / `skill` printed beside `enrich`. Re-run on `v4-train`: family skill
   **0.792 → YES**, source-shift skill **0.367 → YES** — matching §14.6 exactly,
   where the retired bar printed `no` on both.

**The control experiment (a MEASUREMENT — nothing here is adopted).** Template-free
arms fine-tuned from the same upstream `Pretrain.pth`, mirroring the P5-v3
two-stage lineage with every archetype sequence removed. Headline, ref-v2:

| arm | nb NDL@256 | wb NDL | arch copies (nb) | corpus copies (nb) | spec-L0 (nb) | novel-front best viol (wifi24 / dhruva-l1) |
|---|---|---|---|---|---|---|
| **P5-v3 (baseline, unchanged)** | **52** | **21** | 37.9% | 31.6% | **80.5%** | **0.000 (1 feasible)** / 1.023 |
| ctrl-v1 (no templates, winners kept) | 42 | **31** | 0.4% | 40.2% | 35.5% | **0.000 (1 feasible)** / **0.960** |
| ctrl-v1s (no archetype exposure at all) | 26 | – | 0.0% | 55.5% | 35.2% | 0.175 (0 feasible) / – |

**Read:** the templates buy structural **yield** (spec-L0 80.5% → 35.5%), not
novelty per sample (NDL per screen-passing sample is *higher* for the control:
0.46 vs 0.25). About half the baseline's genuine novelty survives their complete
removal, and the control's feasible design sits **NN-sim 0.64** from anything in
the reference where the baseline's sits at **0.94** — i.e. the baseline's "novel
front" is largely template-perturbation. No P1/P2-style collapse. ⚠ ctrl-v1 is
not literally template-free (**42.3% of the winners rows are archetypes**) —
that is what ctrl-v1s isolates, and the 42 → 26 gap is the size of the back door.

**New/changed files:** `finetune.py` +`--no-templates` / `--templates-file` /
`--winners-file` / `--tag` (all additive, defaults byte-unchanged);
`lna/_ctrl_front.py` (novel-front driver, reusable);
`lna/_ctrl_strict_winners.py`; `lna/_ctrl_train.sh` / `_ctrl_strict.sh` (+
launchers). Pools `lna/out/ft_ctrl_{nb,wb}_s1337`, `ft_ctrls_nb_s1337`
(meta.json tracked, seq*.txt gitignored). Checkpoints `ft_ctrl.pth`,
`ft_ctrl_v2.pth`, `ft_ctrls_v2.pth` (gitignored, ~198 MB each — **do not** let
them displace `ft_p5_v2.pre_dhruva.pth`, which is still the adopted P5-v3).

**⚠ Store note:** 20 rows with recipe `ctrl-v1` are in
`lna/data/topo_labels.jsonl` (arm in `provenance.source_arm`:
`ctrl-v1` / `ctrl-v1s` / `p5v3-baseline`). That file was left **uncommitted** by
this agent — it is the shared store and other agents were appending to it live.
Whoever commits it next is committing those rows too.

**Where this points next (cheap, one fine-tune):** if the templates' measured
product is screen yield rather than novelty, a P5 arm that keeps the archetype
scaffolding but **down-weights or curriculum-drops it late in training** should
keep the yield and recover the novelty the 37.9% regurgitation is costing. One
train + one NDL row settles it.

### ▸ Sub-block: WP-SEARCH rung 2 — evolutionary search over graph edits (owner: the search executor)

**Files owned:** `lna/moves.py`, `lna/evolve.py`, `lna/evolve_score.py`,
FINDINGS **§15**, this sub-block. Nothing shared was edited. Full measured detail
in **FINDINGS §15**; run artefacts in `lna/out/_evolve_*` (gitignored).

**What shipped.** plans2/03-SEARCH §2's rung 2, end to end, run to budget on two
specs with an equal-cost control on each:

* `lna/moves.py` — **stratum M**, 17 one-edit graph moves over the `read_netlist`
  genome, every mutant round-tripped through the token representation
  (`emit_sequence → Topology → L0 screen → WL hash`) and the genome re-derived from
  the realized graph so genotype ≡ phenotype. **290/300 proposals realize,
  247 distinct WL hashes.** Plus the §2 decomposition crossover (cut at an
  interstage coupler, splice head(A)+tail(B); parents with no cut are skipped —
  4/60 archetype pairs realize, and it still produced 2 of the 10 best dhruva-s
  designs).
* `lna/evolve.py` — the driver (`--arm evolve|random`, `--report`, `--calibrate`)
  with all four §4 trust rules mechanical: `mean − β·σ`, the uncertainty gate
  calibrated on a holdout the ensemble never trained on, the trust region at
  `datastore.FAMILY_SIM`, and an exploration stratum owning its own true-eval slot.
* `lna/evolve_score.py` — critic v1 as a **persistent scorer** under the
  analoggenie python (one ensemble train, ~7 min, then predictions are free), so
  the torch-free driver can score every generation.

**★ The result: a novel, tier-1-feasible, stable `dhruva-s` design.**
`8c7592ea859e489a` — 16 devices, evolve arm gen 18, move `passive_type_swap`.
After a box-clamped tier-1 boundary polish: **S11_max −10.94 / S21 34.89 /
Idd 11.84 / NF 5.58 / K_min 6.54**, `replay_ok` True, **in-box**, novel against
all 148 archetypes + 41 corpus circuits + every pre-run store row.
**The best NF among tier-1-feasible dhruva-s designs goes 8.88 → 5.58 dB, and a
tier-1-clean design's tier-2 violation goes 1.537 → 0.594 — 2.6× closer to
Gate D3, which is now 2.08 dB of noise and nothing else.** Structurally it is a
noise-cancelling CG+CS whose auxiliary cancellation path the search moved
*downstream* of both tuned gain stages onto the output tank node.

**Gate S2 — NOT MET** on both specs: 0 tier-2 feasible designs in all four arms,
so the "≥2×" ratio is undefined. Raw numbers (FINDINGS §15.5 has the full table):

| spec | arm | true evals | SPICE-min | feasible | near-feasible | best violation |
|---|---|---|---|---|---|---|
| wideband-sdr | evolve | 42 | 51.2 | 0 | 6 | 1.782 |
| wideband-sdr | control | 60 | 76.0 | 0 | 9 | 1.931 |
| dhruva-s | evolve | 47 | 69.1 | 0 | **41** | **0.642 → 0.594** |
| dhruva-s | control | 60 | 62.4 | 0 | 28 | 1.070 |

Rung 1 was never run live on either spec, so the S2 comparison is against the
equal-budget random-selection control — stated, not hidden. On dhruva-s the
evolutionary arm wins every SPICE-measured axis; on wideband-sdr the two arms tie
at **8.5 vs 8.4 SPICE-min per near-feasible design**.

**⚠ The one number that governs rung 2, and it is not good.** Critic v1 holds
ρ(S21) ≈ 0.83 on its family holdout and **collapses to ρ ≈ +0.17 (wideband-sdr) /
+0.20 (dhruva-s) on the mutant distribution search actually generates** — measured
post hoc on the control arms' 60 true evals each, which the critic never saw, so
there is no selection bias in those numbers. On the elites it *did* select the
residual correlation is 0 to −0.33. **The diagnosis is coverage:** `v4-train` had
16 wideband-sdr rows and 24 dhruva-s rows out of 734. Tonight appended **213 rows
(105 wideband-sdr, 108 dhruva-s)**, taking those two specs from 40 to 253.

**⚠ The uncertainty gate is inert as specified.** `n_high_unc = 0` in every one of
80 generations across all four runs — ensemble σ on a mutant never exceeded the
holdout p90. The ensemble is *confidently* wrong off-distribution, not visibly
uncertain, and ρ(σ,|error|) is not sign-stable on selected elites. The **trust
region** is the rule that worked: the control populations drifted to 32/32 members
outside the labeled family radius, the evolve arm never did.

**Where to pick up (highest value first).**

1. **Retrain the critic on the enlarged store and re-run `evolve.py --calibrate`
   against the same stored arms.** No new SPICE, and §15.4 says this is the
   binding constraint on the whole rung. If deployment ρ crosses ~0.4, re-run the
   dhruva-s pair — the harness is unchanged and the comparison is already set up.
2. **Gate D3 is 2.08 dB of NF on a tier-1-clean, stable, novel topology now.**
   Session 4's lever still applies and is now much better aimed: an **NF-only inner
   optimization stage** (or a cancellation-aware start) on `8c7592ea859e489a` and
   on `19f723034c0a` (novel, crossover, S11_max **−16.90** / NF **4.66**, short only
   on gain). These two bracket the remaining trade. Not more topology search.
3. **wideband-sdr: re-read the spec before spending more search.** `nf_db` is
   violated on **102/102** true evals across both arms while every other constraint
   is individually within ~0.4 dB on *some* design. Sweep NF against the
   `max_inductors: 1` / `idd_ma ≤ 8` corner and decide whether 3.5 dB is reachable
   at all at this node — a measurement, not a search.
4. **Stability in the objective**, quantified at last: **21 of 60** control-arm
   dhruva-s sizings read in-band **K < 1**, against 2 of 47 in the evolve arm.
5. **Two traps worth knowing.** (a) The feasibility-first violation scalar rewards
   *degenerate* designs when the hardest constraint improves as the circuit shrinks
   — wideband-sdr's lowest-violation individual is a 4-device near-passive network
   with S21 −1.0 dB. (b) The move set is net-additive: mean device count drifts to
   the `[3,16]` ceiling by generation 20, so late proposals are wasted against the
   budget.

**⚠ Store + hygiene notes.** 213 rows appended under recipes `evolve-v1` (89),
`evolve-ctrl-v1` (123) and `evolve-v1+t1polish` (1); `provenance.source_arm` is
`evolve-evolve` / `evolve-random` and carries the generation, the move, the parent
hashes and the critic version. JSONL integrity verified with two other agents
writing concurrently (0 malformed lines in 1010). Novelty here is checked against
**148 archetypes + 41 corpus circuits + every pre-run store hash** — i.e. already
the ref-v2-equivalent reference plus the store, so the §16.4 qualification does not
apply to these claims. Separately: **every ngspice caller in the tree `mkdtemp`s
per call and none clean up** — `%TEMP%` was carrying 16k+ stale `bias_*` dirs
(swept). `moves.private_tmp()` now confines a driver's scratch to its own run dir;
if you write a new driver, call it.

---

## Session 6 (2026-08-09) — concurrent agents on `lna-data` (continued)

> Same convention as Session 5: each agent owns a clearly-marked sub-block below.
> Append yours; do not edit another's. Commit only your own files with explicit
> path adds.

### ▸ Sub-block: corpus ingestion 41 → 50 + bipolar emission + ref-v3 (owner: the corpus-ingestion executor)

**Files owned:** `lna/to_spice.py`, `lna/build_lna_corpus.py`, `lna/novelty.py`,
`lna/ingest_external.py` (new), `lna/ref/check_bjt.py` (new), `lna/_ndl_refv3.py`
/ `lna/_ndl_flipcheck.py` (new), `lna/data/external/**`, FINDINGS **§19**, this
sub-block. `topology.py` was NOT edited (see the screen note below). Full measured
detail in **FINDINGS §19**.

**★ The corpus is 50 circuits. 9 attempted → 9 ingested, 0 quarantined.** The nine
real/cited LNAs the scout converted (3 IHP SG13G2 open tapeouts, 1 ALIGN
differential, 5 cited paper transcriptions) are through a six-gate ladder
(provenance/blind-protocol · Eulerian augmentation · structure · vocabulary
round-trip · WL identity vs the converter · ngspice op+sp+noise), screened, L1
bias-swept and L2-labelled. All nine are **structurally novel** against ref-v2 —
9 distinct WL hashes, max NN-sim **0.612**. All nine label **infeasible** against
their nearest-band spec at the cheap `ingest-v1` budget, which is the informative
outcome, not a defect: closest are `align-lna-qm` (viol 0.96),
`paper-transformerfb` (1.14) and `paper-noisecancel` (1.36, the only one with net
gain, S21 **+9.23 dB**). The SiGe HBT reads the batch's best NF, **4.60 dB**.

**★ `to_spice.py` emits NPN/PNP — the vocabulary always had them, the emitter did
not.** The 45 nm BSIM4 include has no bipolar models, so `to_spice.BJT_MODELS`
adds generic Gummel-Poon cards, **golden-checked** by the new
`lna/ref/check_bjt.py` against closed-form GP evaluated at the operating point
ngspice settles at: NPN beta **193.0** (pred 192.9) / fT **68.6 GHz** at 1 mA;
PNP beta **43.4** / fT **11.1 GHz**. `beta == bf` and `gm == Ic/Vt` are both
*wrong* expectations here (Early + IKF), which is why the golden computes the full
`qb` algebra — and why `var` was dropped from both cards after measuring that
`var=2.5` silently cut forward beta 184 → 131. **Additive, proved in-process:**
41 corpus decks **164/164**, 148 archetypes **592/592**, 120 generated samples
**120/120** byte-identical.

**★ ref-v3 is frozen: 50 corpus + 148 archetypes = 198 hashes,
`d05390da6183123e`.** `novelty.py` default bumped; ref-v1 (`5273a4f6`) and ref-v2
(`b5689490`) both still reachable and both reproduce to the digit. **The measured
Δ(v3−v2) is 0 on every one of 11 pools** — 0.0% ext copies in 2816 samples,
because none of the nine has ever been in a training set. So the re-frozen
baseline is **nb 52 / wb 21, unchanged in value**, now stamped
`ref-v3[198h/d05390da]`, and **0 of 7 adopt/reject decisions flip** (decision 2
proved by the ref ⊋ monotonicity bound; decision 1 inferred, P2's pool is still
lost). ref-v2 and ref-v3 numbers are therefore **directly comparable** for any arm
trained before the expansion — including the Session-6 curriculum arm, whose §18
comparability caveat costs nothing.

**⚠ Three things the next session should know.**

1. **The generator was deliberately NOT retrained.** The expanded corpus's first
   fine-tune is the obvious next arm and is now a one-command experiment:
   `build_lna_corpus.external_sequences()` returns padded rows in exactly the shape
   `finetune._rows_from_npy` produces. Score it **under ref-v3** against nb 52 /
   wb 21 — under ref-v2 it would score its own copies of the new circuits as novel.
2. **The augmentation budget is not uniform, on purpose.** Upstream's edge-cover
   check is O(N²) pandas lookups *per candidate branch*, so 200/10 (the dataset
   budget) does not terminate here — a 20-node circuit did not finish in 10 min.
   `--stage external` now runs a per-circuit 300 s guard over a ladder
   [(64,3),(20,2),(8,1)] and records the winning budget per circuit. Result: 481
   sequences, one circuit (`ihp-gps-lna-npn`) at 20/2. The external set is 18% of
   the circuits but **10.7% of the rows**. An equivalence-tested fast cover check
   is the fix.
3. **Two known gaps, left open deliberately.** (a) `has_transistor` counts MOS
   only in *both* `topology.lna_score` and `spec.structural_screen`, so a
   bipolar-only LNA would fail the screen — changing a frozen screen is a §14.5/
   §14.6-class governance decision, not a data-change side effect. (b) `bias.py`
   has no base-bias rule for bipolars and no CG-gate rule: **4 of 9** ingested
   circuits have MOS that never conduct, for exactly the reason Session 4 fixed by
   hand in `templates.py`.

**Store note:** +9 L2 rows (recipe **`ingest-v1`**, `nf_gated: true`, ZOAF 4/4/1,
`inductor_q=12`, `provenance.source_arm = "external-ingest"`) and +11 L1 rows.
`ingest-v1` is a *different label domain* from `candidate-v1`/`curated-v1` —
never pool them. ⚠ `paper-gmboostcg` has 3 L1 rows (2 from driver smoke tests
before `--no-log` reached the L1 path); identical measurements, dedup by
`external_id`.

**Regression quartet green after everything** (below, re-run at the end):
vocab **MATCH**, screen **59.4% (114/192)**, pipeline_yield **40/42 (95.2%,** the
known 1081 singular matrix), `check_ref` / `check_nf` / `check_stab` / **new
`check_bjt`** all **GREEN**, `calibrate_specs` **ALL ACCEPTANCE CRITERIA MET**.

```bash
python lna/build_lna_corpus.py --stage external        # guarded Eulerian augmentation
python lna/ingest_external.py --audit | --run          # gate ladder (+ manifest)
python lna/ref/check_bjt.py                            # bipolar golden
python lna/novelty.py --show-ref                       # v1/v2/v3 sizes + digests
python lna/novelty.py --eval <dir> --ref all --spec wifi24
python lna/_ndl_refv3.py && python lna/_ndl_flipcheck.py   # protocol re-run + flip check
```

### ▸ Sub-block: WP-BIAS v3 — the DC-return rules (same owner; `bias.py` transferred from the NF track)

**Files owned:** `lna/bias.py` only. FINDINGS **§21**, this sub-block. `size.py`,
`moves.py` and the specs were deliberately untouched (the NF track owns them and
was mid-campaign). Full measured detail in **FINDINGS §21**.

**★ R-SOURCE and R-DRAIN exist, they work, and they are OFF BY DEFAULT.** The
third measurement was the one that moved: finding #9's off-MOS split (15 source /
16 drain / 12 load-sizing), §19.2's 4 blocked externals (all under
`sources_no_dc_path`), and §17.6's gate-rescue that gained 0 of those 4 all point
at the same missing rule. A source node with no DC path now gets a return
resistor to its device's rail (NMOS → 0, PMOS → VDD); a drain gets a load feed to
the opposite rail.

| `bias.py --validate`, 41 corpus LNAs | v1 (default) | +R-SOURCE | +R-SOURCE+R-DRAIN |
|---|---|---|---|
| **all MOS ON** | 22/41 (54%) | 25/41 (61%) | **26/41 (63%)** |
| all MOS SATURATED | 14/41 | 15/41 | **16/41 (39%)** |
| **made worse** | 0 | **0** | **0** |
| off MOS (source / drain / load) | 43 (**15**/16/12) | 29 (**3**/14/12) | **21 (3/6/12)** |
| v3 stage adopted | – | 11/41 | 13/41 |
| wall clock | 20.8 s | 32.4 s | 47.2 s |

**★ On the nine ingested externals: 3 of the 4 blocked circuits are fully fixed**
— `paper-diffcccg` **0/2 → 2/2**, `align-lna-qm` 1/2 → 2/2, `paper-gmboostcg`
1/2 → 2/2, all by **R-SOURCE alone at 200 Ω**. Totals 14/20 → **18/20**
conducting, all-MOS-on circuits **5/9 → 8/9**. **The fourth is not a bias
problem:** `ihp-lna-2p45g` has one transistor with all four pins on VSS (the
layout dummy the converter itself flagged) and one with its gate tied to its own
source — Vgs ≡ 0 in both cases, so the guard correctly declines the target it is
offered.

**⚠ Read before turning it on.** The flag is opt-in *on purpose*, not out of
caution: R-GATE only makes a circuit biasable, whereas a source return **changes
the circuit**, and `size.size_topology` calls `insert_bias` on every sizing run —
default-on would silently re-domain every future L2 label. The monotonic guard
proves conduction never degrades (measured: 0 worse, everywhere); it cannot prove
the sizing domain is unchanged. **That decision is queued, not taken** — the
experiment that settles it is in §21.5 item 1 and is small.

**Three things that made this cheap and are worth reusing.** (a) The elements are
named `RBIASSRC*` / `RBIASDRN*`, so the existing `^(RBIAS|CBYP|VBGEN)` scaffold
contract already excludes them — **no `topology.py` change**. (b) The resistances
are `.param`s but not `pVBG*`, so `size.classify_params` files them under *fixed*
— **no `size.py` change**, and the sizer gains no free variable. (c) Candidates
are a *ladder* of rule sets under the unchanged guard, so "never worse" extends
for free: best-of over a superset that still contains the no-bias baseline.

**⚠ The rule is offered ~2× more often than it is taken (13 adopted of 24
offered), and the reason is structural:** the DC graph treats a MOS channel as an
open, so interior cascode / current-reuse stack nodes read "no DC path" although
the stack conducts fine. The guard absorbs all of it. Narrowing the offer is
§21.5 item 2.

**Default path byte-identical, verified in-process** (82/82 builds + every v1
report key over 41 circuits × ideal/Q=12), and the quartet is green with the
default: vocab **MATCH**, screen **59.4%**, pipeline **40/42**,
`check_ref`/`check_nf`/`check_stab`/`check_bjt` **GREEN**, `calibrate_specs`
**met**. 461's spot check is unmoved (NM1 Vgs 302 mV).

**Store note:** +50 L1 rows in a new domain — the 41-circuit corpus pass and the
9 externals — stamped `provenance.recipe = "bias-v3"` +
`provenance.bias_rules`. v1 rows carry no `recipe` key. **Do not pool them:** a
v3 row's `n_conducting` is measured on a deck with extra elements in it.

```bash
python lna/bias.py --validate                       # v1, unchanged (22/41)
python lna/bias.py --validate --rules source|v3     # 25/41 | 26/41
python lna/bias.py --index 476 --sweep --rules v3   # one circuit, verbose
LNA_BIAS_RULES=source,drain python lna/size.py ...  # session-wide opt-in
```

### ▸ Sub-block: critic v2 on the full store + the live rung-1 rerank (owner: the critic-track executor)

**Files owned:** `lna/critic.py` (unchanged this session), `lna/critic_gnn.py`
(+`--mutant-eval`), `lna/search.py` (+the live rung-1 driver), `lna/evolve_score.py`
(unchanged), the `v5-train` entry in `lna/data/snapshots.json`, FINDINGS **§20**,
`lna/data/reports/critic-v2-rung1-2026-08-09.md`, this sub-block. Full measured
detail in **FINDINGS §20**.

**Snapshot `v5-train`** = 1010 L2 rows / 41 L1 rows, sha256 `cc2f79ae…`. Every
number below is pinned to it. (The store kept growing under three other agents
during the run; the snapshot is the prefix, and `datastore.load(snapshot=)`
verifies it.)

**1. Critic v2 on the frozen splits — unchanged verdicts, one surprise.** All
arms retrained on `v5-train`. Under the restated Gate C1 (§14.6) the family-split
GNN is ρ(S21) 0.839 → **0.828**, skill 0.792 → **0.683**; source-shift 0.610 →
0.586, skill 0.367 → **0.414**. Every C1 verdict is identical to v4-train. ⚠ Two
things to carry forward: **ridge now beats the shipped GNN on the source-shift
split** (ρ 0.631 / skill 0.453 vs 0.586 / 0.414) — re-check "the GNN is the best
arm" at the next retrain rather than assuming it; and **neither frozen split
tests the mutant distribution**, because `critic.is_generated` keys off
`provenance.token_file` and the 213 evolve rows carry none, so they all sit on the
*train* side of the source-shift split.

**2. ★ The §15.4 collapse is substantially repaired — measured leak-free.** New
`critic_gnn.py --mutant-eval` scores the 213 evolve rows under three regimes
(v1-equiv = train on non-evolve rows only, reproducing v1's 16/24-row coverage;
v2-cv = 3-fold over the evolve *WL families*; v2-leaky = upper bound). v1-equiv
reproduces §15.4's deployed numbers to within seed noise, so the deltas are
like-for-like. On the **selection-free control arms**: ρ(feasibility) +0.173 →
**+0.441** (dhruva-s) and +0.198 → **+0.502** (wideband-sdr); selection skill
−0.094 → **+0.375** and +0.160 → **+0.300**, i.e. both now clear θ = 0.25. On the
selected elites, ρ goes from *negative* (−0.224 wideband-sdr) to **+0.479 / +0.641**.
Still ~55–60% of the in-distribution 0.81 — coverage is not an exhausted lever.
The v2-leaky bound (+0.736 / +0.857 with the rows in train) both proves the CV
holds something out and shows the shortfall is a **generalization gap across
topology families**, not model capacity: more rows inside the 171 families already
sampled will not close it, rows from *new* families might.

**3. ⚠ The uncertainty gate (03-SEARCH §4 rule 2) should be RETIRED.** The
ensemble is well calibrated in-distribution (ρ(σ,|err|) 0.583 → 0.507 on the
holdout; 0.651 / 0.578 on the two frozen splits) and only weakly on mutants. The
mechanism behind §15.4's `n_high_unc = 0` is that **mutant σ is systematically
*smaller* than holdout σ** — the threshold is set by held-out *families*, which
are structurally unusual, while mutants are one-edit perturbations of covered
graphs. Better coverage makes it *more* inert: firing rate 22/213 → **8/213**, and
**2/110** on the live rung-1 pool. Keep the trust region (rule 3); replace rule 2
with a distance-to-training-set gate.

**4. ★★ Rung 1 ran live for the first time — Gate S1 has an honest verdict.**
Spec `dhruva-s`; pool = the adopted P5-v3 generator's unsized remainder
(`ft_p5v2_nb_s1337.v3` → 110 candidates never sized against this spec); ranker
leak-free (all 244 store rows sharing a pool WL hash dropped before training);
k = 30 per arm with a seeded random control from the identical pool, the 6 shared
candidates simulated once and credited to both.

| arm | k | feasible | near-feasible | best viol | med viol | SPICE-min |
|---|---|---|---|---|---|---|
| critic | 30 | 0 | **15** | 1.014 | 2.222 | 30.4 |
| control | 30 | 0 | 8 | 1.015 | 2.661 | 34.3 |

**Gate S1 — NOT MET on its literal ≥2× wording (1.88×, Fisher one-sided
p = 0.055); MET on the restated skill bar (0.328 vs θ = 0.25).** Both recorded.
`realized-vs-predicted ρ = +0.578` over all 54 sized candidates — the first
deployment-distribution number on a live generated pool, 3× critic v1's mutant
figure. The critic's edge is largest on **NF (3 vs 9 designs beyond −1 margin)**,
which is the constraint Gate D3 is stuck on. 54 new `dhruva-s` L2 rows (recipe
`rung1-v1`, arm in `provenance.rung1_arms`), 64.7 SPICE-min, ~30 min wall.

⚠ **`bestviol` ties (1.014 vs 1.015) for a bad reason** — the lowest-violation
points are degenerate shrink-to-nothing optima (S11/Idd/NF pass by producing
~0 dB gain). §15.5 item 5's warning is now confirmed on a second spec and a second
rung: **every "best violation" claim on a gain-limited spec needs an S21-margin
floor.** Among designs with real gain the best four all came from the critic arm;
`seq0126` (critic rank 1, novel vs ref-v2 + store) reaches **NF 2.73 dB at 15.98 dB
gain** with the input match unsolved — an NF lead for the D3 track, not a design.

```bash
python lna/datastore.py --snapshot v5-train
python lna/critic.py --eval --snapshot v5-train --sigma-recipe candidate-v1+bo3
<analoggenie py> lna/critic_gnn.py --eval --snapshot v5-train --sigma-recipe candidate-v1+bo3
<analoggenie py> lna/critic_gnn.py --mutant-eval --snapshot v5-train \
    --sigma-recipe candidate-v1+bo3 --folds 3 --n-models 5
python lna/search.py --pool lna/out/ft_p5v2_nb_s1337.v3 --spec dhruva-s --out P.json
<analoggenie py> lna/search.py --rank --pool-json P.json --snapshot v5-train --out R.json
python lna/search.py --size --rank-json R.json --k 30 --seed 1337 --shard 0/2 --out S0.json
python lna/search.py --s1 --rank-json R.json --k 30 --seed 1337 --sized-json S0.json S1.json
```

### ▸ Sub-block: the curriculum experiment — §16's follow-up, tested and refuted (owner: the curriculum executor)

**Files owned:** `lna/finetune.py` (two additive flags), `lna/_cur_*`,
`lna/out/ft_cur*`, FINDINGS **§18**, this sub-block. Full measured detail in
**FINDINGS §18**; the design was **pre-registered and committed before a single
epoch was trained** (`6519abf`, §18.0).

**The hypothesis (§16.5's proposed follow-up):** keep the `templates.py`
scaffolding early, drop it late, and you should keep the templates' structural
yield (spec-L0 80.5%) while earning the control's genuine novelty (front NN-sim
0.642 vs the baseline's 0.939). **Verdict: refuted, with a dose-response curve.**

Two arms, phase-2 dataset byte-identical to ctrl-v1's stage B (5170/492), lr 3e-5,
batch 32, 40 epochs, seed 1337, best-val — differing from ctrl-v1 in *nothing but
the warm-start checkpoint*: **cur-v1** warms from `ft_p5.pth` (P5-v3's own stage-A
base) — the missing 2×2 cell — and **cur-v2** from `ft_p5_v2.pre_dhruva.pth`, the
adopted P5-v3 itself. Both take best val at **epoch 0**, as pre-registered.

| arm | nb NDL@256 (ref-v2 = ref-v3 here) | spec-L0 | arch / corpus copies | wb NDL | front winner NN-sim | median front NN-sim |
|---|---|---|---|---|---|---|
| **P5-v3 (baseline)** | **52** | **80.5%** | 37.9% / 31.6% | 21 | **0.939** | 0.729 |
| ctrl-v1 | 42 | 35.5% | 0.4% / 40.2% | 31 | 0.642 | **0.603** |
| ctrl-v1s | 26 | 35.2% | 0.0% / 55.5% | – | 0.574 | 0.623 |
| **cur-v1** | 42 | 54.7% | **3.5%** / 55.5% | 31 | 0.822 | 0.771 |
| **cur-v2** | 39 | **69.9%** | **6.6%** / 60.5% | 23 | 0.714 | **0.817** |

* **★★ The copying does not stop — it MIGRATES.** One template-free epoch takes
  verbatim archetype copies 37.9% → 6.6% and corpus copies 31.6% → 60.5%: a
  near one-for-one trade, total copies barely move (69.5% → 67.2%). NDL per
  screen-passing sample actually *falls* (0.252 → 0.218).
* **★★ Tail length is a monotone dose-response and it points down.** Template-free
  tail from P5-v3, shipping epoch K−1 (`--ckpt-policy final`): **NDL 52 (K=0) → 39
  (K=1) → 27 (K=4) → 16 (K=12)** while spec-L0 plateaus at ~69% and corpus copying
  climbs to 78.9%. K=12 lands on **16 = the P0 prefix-12 baseline**. No interior
  optimum; the best tail length is zero.
* **★ The missing 2×2 cell is clean:** cur-v1 vs ctrl-v1, identical stage B,
  **NDL 42 vs 42** and spec-L0 **54.7% vs 35.5%** ⇒ stage-A scaffolding is worth
  **+19 points of yield and 0 NDL**. It does not matter for novelty whether the
  templates are early, late, or absent.
* **★ One novel tier-1-feasible wifi24 LNA** from cur-v1: `ft_cur_nb_s1337/seq0057`
  (S11 −10.69 / S21 12.13 / Idd 4.21), box-clamped polish, novel vs 148 archetypes
  + 41 corpus + the 9 ref-v3 externals + every store row. **★ cur-v2 owns the best
  dhruva-l1 front violation of the whole series, 0.624** (vs 0.960 ctrl-v1 /
  1.023 P5-v3).
* **⚑ DO NOT PROMOTE.** Adopt-only-if-better against the re-frozen nb 52: cur-v1
  42, cur-v2 39. The one exception is recorded but not acted on — on the **wb**
  channel cur-v2 clears every clause (NDL 23 > 21 at ind ratio **0.039 < 0.077**,
  spec-L0 51.2% > 37.5%) — a 2-topology margin on a thin channel, bought by losing
  nb by 13.
* **The reframe worth carrying forward:** the archetypes are load-bearing for
  novelty after all, not because they *create* it but because they are the only
  thing crowding out corpus memorization. **The lever is more and more varied
  structure in the data (§19's ingestion), not a schedule that removes structure.**

**⚠ Notes.** (1) `finetune.py` gained `--warm-from` (explicit warm-start ckpt, so a
curriculum phase never has to copy a 198 MB file over a shared path) and
`--ckpt-policy best|final`; defaults byte-unchanged. (2) A plain
`nohup … &` from `wsl -e bash <script>` **dies with the launching session** — use
`setsid nohup … < /dev/null &` (cost ~10 min tonight; `lna/_cur_launch.sh` has the
working pattern). (3) The four front runs logged **20 L2 rows, recipe `cur-v1`**,
`provenance.source_arm` ∈ {`cur-v1`,`cur-v2`}, 10,614 ngspice evals ≈14 min real.
(4) Front novelty filtering ran under **ref-v3** (stricter than §16's ref-v2) while
similarity is reported under ref-v2 — both stated in §18.4; Δ(v3−v2) = 0 on all
four curriculum pools.

```bash
# pre-generate training JSONs on Windows, then (WSL GPU):
<gpu py> lna/finetune.py --arm p5 --do train --device cuda --seed 1337 --epochs 40 \
    --no-templates --winners --tag cur --winners-file lna/out/winners_train.pre_dhruva.json \
    --warm-from lna/out/ft_p5.pth                       # cur-v1 (early switch)
bash lna/_cur_tail.sh lna/out/ft_p5_v2.pre_dhruva.pth cur2 4 12   # tail-length sweep
python lna/novelty.py --eval lna/out/ft_cur_nb_s1337 --spec wifi24 --ref v2
python lna/_cur_front.py --pool lna/out/ft_cur_nb_s1337 --spec wifi24 --arm cur-v1 \
    --scan-limit 14 --top 5 --no-nf-gate --out lna/out/_cur_front_cur_wifi24.json
python lna/_cur_nn.py lna/out/_cur_front_cur_wifi24.json --ref v2   # template similarity
```

---

### ▸ Sub-block: ★ P5-v7 ADOPTED — the 50-circuit corpus buys +27 nb NDL (owner: the curriculum/P5-v7 executor)

**Files owned:** `lna/finetune.py` (`--external-corpus`, additive), `lna/_v7*`,
`lna/_cur_*`, `lna/out/ft_p5v7*`, FINDINGS **§24**, this sub-block. Full measured
detail in **FINDINGS §24**. This is the direct sequel to §18: that section's
reframe — *the lever is more varied structure in the data, not a schedule that
removes structure* — is the hypothesis §24 tests, and it wins.

**★★ ADOPTED. New generator baseline: `ft_p5v7_v2.pth`, nb NDL@256 = 79 / wb = 41
under `ref-v3[198h/d05390da]`** (was P5-v3, nb 52 / wb 21).

Build = the adopted P5-v3 recipe with the corpus expanded 41 → 50 (§19's 481
ingested rows) and **nothing else**: templates kept (§18), no curriculum, both
stages on P5-v3's own emissions, external rows into TRAIN only so the 736-row val
set is byte-identical and best-val early-stops on the baseline's criterion.

| arm | class | NDL@256 | spec-L0 | copies (arch/corpus/**ext**) | med NN-sim | ind ratio |
|---|---|---|---|---|---|---|
| P5-v3 = **v7ctl** | nb | 52 | **80.5%** | 69.5% (37.9 / 31.6 / 0.0) | 1.000 | 0.224 |
| **P5-v7** | nb | **79** | 69.1% | **46.9%** (**14.5** / 32.0 / **0.4**) | 1.000 | **0.230** |
| P5-v3 = **v7ctl** | wb | 21 | **37.5%** | 51.2% (14.1 / 37.1 / 0.0) | 1.000 | **0.077** |
| **P5-v7** | wb | **41** | 30.5% | **42.6%** (14.1 / 28.1 / **0.4**) | **0.756** | 0.132 |

* **★★★ The attribution is exact, and this is the section's most reusable fact.**
  v7 differed from the *published* P5-v3 in two ways (corpus + a fresh stage-A
  retrain), so `v7ctl` re-ran v7's pipeline with `--external-corpus` removed.
  **It reproduces P5-v3 to every digit** — nb 52 / 80.5% / 69.5% (37.9/31.6) /
  0.224 / 93.8%, wb 21 / 37.5% / 0.077 — and its stage-B best val is **0.2300 @
  epoch 1**, P5-v3's documented value. **The pipeline is deterministic under seed
  1337**, so v7 − v7ctl is the nine circuits and nothing else. Any future arm can
  get a same-session exact control for the price of one extra train.
* **★★ +27 nb / +20 wb NDL from 5.8% of the training rows** (the whole 92 → 118
  archetype expansion that made P5-v3 was worth +11). NDL per screen-passing
  sample nearly doubles, 0.252 → 0.446.
* **★★ It displaced ARCHETYPE copying and left corpus copying alone**: arch
  37.9% → 14.5%, corpus 31.6% → 32.0%. §18's curriculum did the exact converse
  (arch → 6.6%, corpus → 60.5%, NDL *down*). **Removing structure relocates
  copying; adding structure dissolves it.**
* **★ The 9 new circuits are NOT imitated** — copied 0.4% of the time, and the
  front's similarity to them is **0.494 median vs the baseline front's 0.528**.
  They acted as *variety pressure*, not as content. Meanwhile front
  template-similarity drops: winner **0.766 vs 0.939**, median 0.653 vs 0.729 —
  §16's "the novel front is template-perturbation" complaint is materially reduced.
* **★ Novel front (recipe `p5v7-v1`, §16 protocol): 67 candidates vs the
  baseline's 45**, and one novel replay-verified tier-1-feasible wifi24 LNA —
  `ft_p5v7_nb_s1337/seq0066`, **S11 −16.94 / S21 13.40 / Idd 4.26** (4 dB better
  match than the baseline's feasible winner at comparable gain/current). On
  dhruva-l1, `seq0093` reaches **S21 24.21 dB against the 25.4 dB target**, the
  closest the *generator* has come on that band; the broadband match is still the
  wall.
* **⚠ Two real costs, adopted with eyes open.** (1) **wb inductor ratio regresses
  0.077 → 0.132** — the wrong way for an inductorless spec, and a strict
  per-channel reading of adopt-only-if-better **fails that clause**. Adopted
  anyway on the nb channel's +27 margin and the wb median NN-sim finally breaking
  below 1.000, but anyone sampling `<LNA_WB>` should know it. (2) **nb spec-L0
  falls 80.5% → 69.1%** — the archetypes' yield product, partly spent back.
* **⚠ Recorded deviation:** v7ctl's stage-B process died after epoch 1 (GPU
  contention). Its best-val checkpoint was already written at the same 0.2300 the
  baseline reports, and §18.3 measured 40 consecutive rising epochs on this
  codebase, so it was sampled as-is rather than burning 75 min on epochs that
  cannot change it.

**Where this points next (cheapest first).** (1) **Raise §19's augmentation
budget.** The external set is 18% of the circuits but only 10.7% of the rows
because the cover-check ladder capped `ihp-gps-lna-npn` at 20 sequences — the
under-weighting §19 flagged now has a measured payoff attached. (2) **Ingest more
circuits**; nine bought +27, and the second nine is the experiment that tells you
whether this is linear. (3) **Restore the yield** the expansion spent (more
archetypes, or a screen-aware decode) — §16/§18/§24 agree that yield and novelty
are separate levers. (4) **Fix the wb inductor ratio** before anyone runs a
`wideband-sdr` campaign off v7.

```bash
# P5-v7 (WSL GPU, ~55 min; setsid pattern in lna/_v7_launch.sh)
<gpu py> lna/finetune.py --arm p5 --do train --device cuda --seed 1337 --epochs 40 \
    --external-corpus --templates-file lna/out/templates_train.pre_broaden.json --tag p5v7
<gpu py> lna/finetune.py --arm p5 --do train --device cuda --seed 1337 --epochs 40 \
    --external-corpus --templates-file lna/out/templates_train.pre_dhruva.json \
    --winners --winners-file lna/out/winners_train.pre_dhruva.json --tag p5v7
bash lna/_v7_dryrun.sh                 # --epochs 0: prints the mix, writes nothing
bash lna/_v7ctl_train.sh               # the exact-attribution control
python lna/novelty.py --eval lna/out/ft_p5v7_nb_s1337 --spec wifi24 --ref v3
bash lna/_v7_fronts.sh                 # §16 novel front, recipe p5v7-v1
python lna/_cur_nn.py lna/out/_v7_front_wifi24.json --ref v3 --breakdown   # arch/corpus/ext split
```

---
### ▸ Sub-block: P5-v8 REJECTED — expert iteration recycles structure (owner: the P5 generator executor)

**Files owned:** `lna/finetune.py` (additive), `lna/_v8*`, `lna/_v7*`, `lna/_cur_*`,
`lna/out/ft_p5v8*`, FINDINGS **§28**, this sub-block. Full detail in **§28**.
Direct sequel to §24: that section adopted v7 by adding *new* structure; this one
feeds the store's own winners back (Stage-3 Loop B) on top of v7.

**⚑ REJECT. The adopted generator stays P5-v7 (`ft_p5v7_v2.pth`, nb 79 / wb 41
under `ref-v3[198h/d05390da]`).**

| arm | class | NDL@256 | spec-L0 | copies (**arch**/corpus) | med NN-sim | ind ratio |
|---|---|---|---|---|---|---|
| **P5-v7 (stays)** | nb | **79** | 69.1% | 46.9% (**14.5%**/32.0%) | 1.000 | **0.230** |
| P5-v8 | nb | **67** | 70.3% | 51.2% (**27.0%**/23.8%) | 1.000 | 0.208 |
| P5-v7 | wb | 41 | 30.5% | 42.6% (14.1%/28.1%) | **0.756** | 0.132 |
| **P5-v8** | wb | **45** | **40.6%** | 49.6% (12.5%/36.7%) | 1.000 | **0.094** |

* **★★ The mechanism, and it is the reusable finding: the winners channel
  re-injects ARCHETYPE structure.** arch copies **14.5% → 27.0%**, nb NDL 79 → 67.
  §16.1 measured why and nobody had spent it: **42.3% of the winners rows are
  `templates.py` archetypes** the sizing loop promoted. Feeding the store's best
  designs back feeds the archetypes back a second time, on top of the template
  channel that already carries them. Three sessions, one law:

  | intervention | arch copies | corpus copies | nb NDL |
  |---|---|---|---|
  | §18 remove templates late | 37.9 → **6.6%** | 31.6 → **60.5%** | 52 → **39** |
  | §24 add 9 real circuits | 37.9 → **14.5%** | 31.6 → 32.0% | 52 → **79** |
  | §28 recycle own winners | 14.5 → **27.0%** | 32.0 → 23.8% | 79 → **67** |

  **Only adding structure the model had never seen raised NDL.**
* **★ The wb channel is the control inside the section, and it worked.** The 198
  **first-ever wideband winner rows** (v7's file was 100% nb) take wb NDL 41 → 45,
  spec-L0 30.5% → **40.6%**, and **inductor ratio 0.132 → 0.094** — repairing most
  of the one defect §24 adopted v7 with. Cost: wb median NN-sim 0.756 → 1.000,
  valid 99.6% → 97.3%.
* **★ NEXT EXPERIMENT, motivated by measurement:** a **wb-targeted arm** — v7 warm
  started on the *wideband winners only*, nb channel untouched. It is the only
  place the winners were new information, and it directly tests whether §24's wb
  inductor-ratio regression can be repaired without paying nb NDL.
* **★ The winners DID move what the model composes toward the Gate-D3
  structures** (`lna/_v8_d3sim.py`, reference = the 4 D3 winners + 13 NC/gmb-CG
  archetypes), on the dhruva-l5 screen: median D3/NC-sim **0.560 → 0.616**, max
  **0.728 → 0.845**, **fraction > 0.70 = 0.5% → 4.2% (8×)**. It shows in the front
  too — the l5 front's best two are the D3/NC-adjacent ones.
* **Front (recipe `p5v8-v1`, first-ever `dhruva-l5` run):** wifi24 **1 feasible**
  (`seq0057`, S11 −10.65 / S21 13.04 / Idd 4.68); dhruva-l1 best viol 1.196 (worse
  than v7's 1.013); **dhruva-l5 best viol 0.826** (`seq0086`, S21 21.04, binding on
  match + current). ⚠ Rows sized under the **multi-finger** emission
  (`mos_fingers: ceil(W/w_finger)`) and self-describe via that stamp — **not**
  comparable to the pre-cutover single-finger front rows in §16/§24 on any
  noise-sensitive axis.
* **⚠ HANDOFF TO THE l5 TRACK:** `ft_p5v8_nb_s1337/seq0086` and `seq0085` carry
  the NC-family input structure the l5 campaign wants (D3/NC-sim 0.670 and
  **0.734**, the latter nearest `gmbcg_s2_R_b1`) and are the l5 front's best two by
  violation. **No NF was measured on them** — the front protocol is tier-1 gated,
  so `nf_db` is `unsupported` on that path. Re-size them under the NF-gated
  `dhruva-l5` spec on the current emission to settle the sub-4 dB question.
* **⚠ FOR THE D3 OWNER: `ced0d8bd36ed4890` is not in the label store.** Zero
  occurrences in `topo_labels.jsonl` and in every file under `lna/data/`. §25
  records it as a Gate-D3 winner (NF 3.253, viol 0.000) so the claim stands on
  §25's evidence, but the winners channel — and anything else reading the store —
  cannot see it. It needs logging.
* **Note on `emit_winners`:** it filters only on `spec`, never `recipe` or
  `nf_gated`, so the NF-gated domain is included automatically. It *ranks* across
  both domains, which §13 warned about; measured, the domains **segregate by spec**
  (dhruva-s keeps 86/86 nf-gated, wifi24 121/121 tier-1) so the cross-domain
  ranking never bites today. It will the first time one spec is campaigned in both
  eras. `lna/_v8_winners_audit.py` is the check; run it before any future emission.
* **⚠ Quartet:** vocab MATCH, screen 59.4% (114/192), pipeline 40/42,
  `check_ref` GREEN, `check_nf` GREEN, calibrate ALL CRITERIA MET — but
  **`check_stab` now reports the dhruva winner NOT unconditionally stable on
  `dhruva-l2`** (harness itself GREEN). It read "unconditionally stable on every
  band" earlier in this same session, and the only thing that changed in between is
  the **multi-finger emission cutover**. Nothing in this sub-block touches SPICE
  emission (`finetune.py` + private sidecars only), so this is flagged for the
  cutover owner rather than fought.

```bash
python lna/_v8_winners_audit.py --specs wifi24,gps-l1,dhruva-l1,dhruva-l5,dhruva-l2,dhruva-s,wideband-sdr
python lna/templates.py --emit-winners lna/out/winners_train.v8.json \
    --winners-specs wifi24,gps-l1,dhruva-l1,dhruva-l5,dhruva-l2,dhruva-s,wideband-sdr
bash lna/_v8_launch.sh          # warm from ft_p5v7_v2.pth, 40 ep, seed 1337
python lna/novelty.py --eval lna/out/ft_p5v8_nb_s1337 --spec wifi24 --ref v3
bash lna/_v8_fronts.sh          # wifi24 + dhruva-l1 + dhruva-l5, recipe p5v8-v1
python lna/_v8_d3sim.py --pool lna/out/ft_p5v8_nb_s1337 \
    --baseline-pool lna/out/ft_p5v7_nb_s1337 --spec dhruva-l5
```

---

**⚠ BLIND PROTOCOL is active — read plans2/08 §"Blind protocol" before touching
templates.py.** No paper circuit content anywhere; new families only from the
existing archetype set or generic textbook blocks chosen *without* the paper,
tagged `recipe: blind-v1`; a two-turn Gate stall is recorded and **stopped** —
unblinding is the user's call.

- **★ Gate D0 MET (committed `3784644`, pushed).** Four tier-1 specs
  `dhruva-{l5,l2,l1,s}` added (S21 22.3/22.3/25.4/30 dB @ 1.176/1.228/1.575/2.492
  GHz; **S11 ≤ −10 dB over 1.1–2.5 GHz** via the extractor's existing `s11_max_db`,
  zero harness change; Idd ≤ 13 mA; NF/IIP3 `unsupported`). Benchmark grows four
  dhruva rows: **0/6 on every band**, binding almost entirely on `s11_max`. Sharp
  point: `seq0046` hits **S21 23.7 dB on dhruva-l1** but f0 S11 ≈ −0.5 — gain
  alone gets close, the broadband match is the wall (08 §5). FINDINGS §12 logs the
  protocol + D0.
- **★★ Gate D1 MET (committed, pushed) — feasible dhruva-l1.** The arc: labeled
  the archetype set vs `dhruva-l1` (all single-stage bind on `s11_max≈0`, no
  broadband match) → added generic blind-v1 **`rfb_cs`** (rfb input + tuned stage:
  broke the match wall, s11_max→−10 and gain→27 *separately*) → **`cascode2`**
  (stage-2 cascode decoupled match/gain, viol 0.065, 1.6 dB short) → **`rfb_cs3`**
  (rfb → tuned → tuned; gain headroom). **`rfbcs3_tank_cc21_bf0` is feasible:
  s11_max −11.2 / S21 37.8 / Idd 12.93** (wl `3ebaf08f9`, recipe `blind-v1`).
  `emit_winners` generalized to multi-spec; P5-v4/v5 fine-tuned (NDL 89/84, rfb-like
  pools) but the archetype route closed it first (generator pools reached viol
  0.318; the co-optimum needs multi-seed heavy sizing). **Blind protocol honored
  throughout — no paper circuit content anywhere.**
- **Next:** (1) a *generated* dhruva-l1 feasible — re-fine-tune **P5-v6** on the
  rfb_cs3-bearing 135-archetype set + winners (now incl. the feasible), sample,
  curated-size (multi-seed heavy) — for the fuller "pipeline designed it" claim;
  (2) **WP-D3 / Gate D2** — warm-start curated sizing from the L1 solution against
  dhruva-l5/l2/s (one family, all four bands); (3) **WP-D1 NF harness** (priority-1,
  gates tier-2 → Gate D3). Idd 12.93 is tight vs 13; 37.8 dB gain has ~12 dB slack
  to trade for current margin.

**New roadmap:** `.claude/worktrees/lna-plans/lna/plans2/` (start at
`00-OVERVIEW.md`) — the generate→size pipeline is now feature-complete; Phase 2
adds a learned critic + guided search. Branch **`lna-data`** (off `lna-exec` @
`00cd32e`), never pushed. Run `python lna/datastore.py --summary` to see the store
(**264 L2, 1 feasible, ~35% stratum T**; 41 L1; snapshots `v1-train`=173,
`v2-train`=264). Full measured write-up in **FINDINGS.md §11**.

**Gate C0 MET:** ≥150 L2 rows (264), ≥25% stratum-T (P5 templates, ~35%), σ
measured. `templates.py` mints 92 archetypes as valid token topologies (reuses
AnalogGenie `build_connection_matrix→dfs_all_paths`, round-trip-exact).

**🎯 Stage-1 baseline result (`lna/critic.py --eval`):** the mandatory feature
baselines (trivial / WL-kNN / ridge, torch-free numpy) predict the stored margin
vector. On **v2-train (264 rows, σ=0.61)**: **Gate C1 CLEARED on the
family-holdout split** — WL-kNN ρ(S21)=0.77, enrichment@20%=2.06×. **NOT cleared
on the source-shift split** (corpus+ref+templates→generated: ρ≈0.22–0.28) — the
honest number for ranking generated candidates. **Key finding: adding the 88 P5
templates did NOT close the source-shift gap** (it was 0.34 on v1-train's smaller
train set). Clean archetype diversity doesn't make the *generated* arms
predictable — the gap is the generated distribution itself, so the next lever is
the GNN / a better generator / uncertainty-gated search, not more templates.

**User decisions this session (remote-control):** gain stage = tapped-C output
match; NF advisory (Gate G4 gates S11/S21/Idd, NF logged not gated); branch stays
local; run autonomously through Stage 0 to Gate C0.

**🎯 Gate G4 CLOSED by hand (day 3):** the tapped-C reference sizes to full
feasibility vs wifi24 — **S11 −20.1, S21 18.6 dB, Idd 3.15 mA, NF 2.0 dB**. The
store's feasible class now exists (was 0/N). The generated-topology half of G4
(Stage 2) is still open.

**Landed day 1 (WP-DATA, 01-DATA §2–4):**
- `lna/datastore.py` — append-only JSONL label store (py-3.14, no new deps):
  L2/L1/point tables + snapshots; `margins_for` (per-metric margin vector, the
  critic's target — R1), `family_split` (WL-cosine≥0.9 families, the *only*
  split fn — R2), `append_l2` key-dedup, sha256-pinned snapshots.
- Logging hooks (additive, proven byte-identical): `size.py --anchor/--scoreboard/
  --corpus-l2` → L2 + point rows; `bias.py --sweep/--validate` → L1 rows.
  `--no-log` opt-outs. **41 corpus L1** + **stage-B anchor L2** backfilled.

**Landed day 2 (NF harness + corpus L2 backfill):**
- **Corpus L2 backfill**: `size.py --corpus-l2` sized the **19** wifi24-screen-
  passing corpus LNAs (finite Q). Store now **20 L2** (19 corpus + anchor),
  **0 feasible** — all hit the S21 ceiling (finding #10), so the margins carry
  the signal, not a feasibility bool (confirms R1). S21 spans −35→+11.9 dB.
- **BUG FIXED — finite-Q candidate sizing was fatally broken** ("Undefined
  parameter [pindw0]"): `E.body_of` strips `.param` lines, so to_spice's finite-Q
  constants died; `classify_params` now re-declares them. `size_topology` takes
  `inductor_q` (default ideal, unchanged).
- **NF harness (finding #7 fixed + validated)**: `extract.measure_nf` /
  `build_noise_deck` drive the noise analysis through a real **series-Rs source**
  instead of the noiseless S-param port (which read *negative* NF with gain —
  corpus 464 was −4.5 dB). Golden-locked: `python lna/extract.py --selftest`
  reads 3.012 dB vs analytic 3.0103. `size.py` now records the physical NF in
  every L2 row (`nf_method:"series_rs"`); **additive — NF stays out of the
  objective**, so sizing/feasibility are unchanged.
- Regression quartet green throughout (vocab MATCH, screen 59.4%, pipeline 40/42,
  check_ref GREEN, calibrate met).

**Landed day 3 (tapped-C gain reference → Gate G4):**
- `lna/ref/ref24_tapped.cir` — stage-B cascode core + tapped-C output transformer.
  The cascode isolates the input (H-Q1), so stepping the 50 Ω load up to a high R
  at the drain lifts S21 without disturbing S11. Hand-feasible point found by grid
  search, then ZOAF (`size.py --tapped`) refines to S21 18.6 dB.
- `size.py`: `_size_ref()` generalizes the reference sizer; `size_tapped()` sizes
  {W, Ld, Ct2, VB, VB2} with the input match FIXED (keeps ZOAF out of the
  degenerate "collapse the transformer" basin — it has no warm start).
- **BUG FIXED**: reference rows were all keyed `(None, spec)` → collided; the
  tapped label was skipped as a dup of the anchor. Now keyed `ref:<deck>`.

**Landed day 4 (`campaign.py` + repeat-probe σ):**
- `lna/campaign.py` — nightly labeling runner (01-DATA §5): stratified quota
  T/G/M/R, dedup-aware, sequential/unattended-safe, morning report to
  `lna/data/reports/`. `--dry-run` / `--night` / `--limit`.
- **Repeat-probe σ(S21) = 0.323 dB over 6 keys** — under the ≲0.5 target, so the
  candidate-v1 ZOAF budget is an acceptable label-noise floor (a Gate C0 item).
  σ is topology-dependent (stable ~0 dB, one pathological corpus LNA swings 3.5 dB
  between seeds) — a real signal for the critic's rank-loss margin.
- `size.py`: `_size_ref` guards `m=None` (a ref that fails to size logs a failed
  row, doesn't crash the campaign).

**⚠ SETUP TRAP that cost this session ~20 min — read before running anything in a
worktree.** The pipeline's runtime deps `misc/ZOAF/`, `AnalogGenie/` (Dataset
.npy), and `AutoCkt/repo/` (the 45nm model include) are **untracked** — present
only in the main checkout, absent from any fresh `git worktree`. Symptom: ngspice
ops silently return None → "0 conducting" everywhere. Fix used here: junction them
in (non-destructive, main copy untouched):
```
# PowerShell, from the worktree root
New-Item -ItemType Junction misc         -Target C:\...\circuit-repro\misc
New-Item -ItemType Junction AnalogGenie  -Target C:\...\circuit-repro\AnalogGenie
New-Item -ItemType Junction AutoCkt\repo -Target C:\...\circuit-repro\AutoCkt\repo
```
Junctions don't show in `git status` and won't be committed. (Or: just work in the
main checkout on `lna-exec`.) These dirs probably belong in `.gitignore` +
a setup note, but that's a repo-hygiene call left to the user.

**Next — remaining path to Gate C0** (C0 = ≥150 L2 rows, ≥25% stratum T, 3
unattended nights, σ measured ✓). The campaign runs but three sources are thin:
1. **`templates.py` (P5) — the biggest lever, do first.** Full stratum-T
   diversity + the 25% target. Must emit valid AnalogGenie `Topology` objects
   (token sequences), which go via connection-matrix → Eulerian augmentation
   (see `build_lna_corpus.py stage_augment`) — a real sub-project, not a one-liner.
   The tapped-C archetype (`ref24_tapped.cir`) is the "matched" family's template;
   generalize it + CS-degen/CG/resistive-fb/noise-cancelling × cascode/load/buffer.
   Then register the template topologies as a stratum-T source in `campaign.py`
   (currently T = the 3 hand ref decks only).
2. **Stratum G needs the generated `seq*.txt`** — gitignored, so absent in a fresh
   worktree. Regenerate (`finetune.py --do sample`, WSL GPU) or run the campaign
   from the main checkout. `campaign.py --gen-glob` points it at a dir.
3. **Stratum M** — the 1-edit mutation move set (03-SEARCH §3); reused later by
   evolutionary search. Not built.
**Stage-1 + Stage-2 rung-1 DONE. C1 met (WL-kNN, family split); S1 NOT met.**
The GNN (`critic_gnn.py`, CPU under analoggenie torch) wins the source-shift
diagnostic (ρ≈0.34) but loses the C1 gate to WL-kNN (0.65 vs 0.77). Rung-1 rerank
(`search.py --rerank`, offline on the 142 sized generated pool): WL-kNN 1.37× /
GNN 1.74× near-feasible enrichment vs random — below S1's 2×.

**The wall, and how P5 attacked it.** Source-shift C1 and S1 both failed because
the generated arms are a distribution no surrogate ranks to 2× — the generator
memorized ~35 corpus graphs (NN-sim 1.000). **P5 fixed the generator (DONE):**
`finetune.py --arm p5` mixes corpus + Eulerian-augmented `templates.py` archetypes
+ `<LNA_NB>/<LNA_WB>` class tokens → **NDL@256 24→60, NN-sim 1.000→0.574, inductor
ratio 0.10→0.179** (FINDINGS §11). The memorization ceiling is broken.

**WSL GPU — verified + working recipe** (torch 2.13+cu130, RTX 3050, 3.3 GB free):
- Run from PowerShell: `wsl -e bash <script.sh>`; write the script to a FILE (Git
  Bash mangles `/opt/...`). Script: `cd /mnt/c/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data
  && /opt/miniconda/envs/gpu/bin/python lna/finetune.py --arm p5 --do sample
  --device cuda --n 256 --class nb`.
- **10-min tool timeout** kills a full 40-epoch train (~20s/epoch); it overfits
  by epoch ~1 anyway, so best-val checkpoint is fine — but for a clean run either
  cut epochs or launch detached (`nohup … &`) and poll. `--do sample` (~75 s) fits.
- **Junctions resolve in WSL** (AnalogGenie→Pretrain.pth/Training.npy/Dataset). The
  GPU env has **no pandas**, so template augmentation is pre-generated on Windows
  (`templates.py --emit-train lna/out/templates_train.json`, gitignored) and the
  GPU training just reads it. `.pth` + `templates_train.json` are gitignored →
  regenerate, don't expect them in a fresh worktree.

**LOOP CLOSED once — thesis confirmed via the distribution (FINDINGS §11).** Sized
26 novel P5 samples; `search.py --rerank` splits old(P1/P2) vs p5 under one shared
critic. **P5 base-rate near-feasible 62% vs old 27% → ~2.3× more near-feasible
designs per SPICE, beating critic-rerank's 1.74×.** Enrichment on P5 falls to ~1.0
(base-rate ceiling: a 62%-good pool has nothing to enrich), ρ mixed at n=26/σ=0.77.
Snapshot `v3-p5` (293 L2). **G4-by-generation is CLOSE:** P5 hits S21=14.0 dB
(seq0126) and S11=−21.9 dB (seq0009), not simultaneously.

**★ GATE G4 CLOSED BY GENERATION (DONE).** `g4_search.py` (boosted multi-seed
sizing: 4 seeds × anchor-budget on the 6 closest P5 candidates) sized **seq0240**
to full feasibility (novel; S11 −11.9 / S21 12.6 dB / Idd 1.19 mA). The naive
single-seed sizer, not the topology, had capped it — same all-free-ZOAF trap the
tapped ref hit. Logged (`source_arm=g4-generated`); design tokens are in
`topo_labels.jsonl` (seq file gitignored). Store now 2 feasible (hand + generated).

**STAGE-3 LOOP SET UP (`loop.py`).** Governance active: 5 tripwires + headline
curve (SPICE-min per feasible-novel design = **967** at iter 1) + `--baseline` /
`--status` / `--tripwires` / `--iterate` (records + gates + prints the cadence).
Loop B (generator←winners) built + validated: `templates.py --emit-winners` →
`finetune.py --arm p5 --winners` (warm-start ft_p5.pth→ft_p5_v2.pth; dataset
6011→6780). `topo_to_netlist` round-trips WL-exact. loop_state.json tracks iters.

**Iteration 1 turn RUN (loop_state.json).** Loop B expert-iterated the generator on
its winners → **v2 improved on every axis, no mode collapse**: NDL@256 60→73, term
98.8→100%, inductor ratio 0.18→0.21; GNN rerank ρ(S21) on the v2 pool = **0.59**
(vs v1 0.24 / old 0.33, clears C1's 0.5). BUT `g4_search` (2 passes, 10 seeds on the
2 closest) found **no new feasible design** — 2/3 near-misses (seq0009: S11 −9.3 /
S21 12.4 / Idd 5.25). So **feasible-novel stays 1; curve 967→1093 (worse)** — an
honest non-improving iteration. **σ climbed 0.32→1.02** (multimodal topos; < 2×
tripwire). `ft_p5_v2.pth` is the adopted generator; `g4_search.py` now takes
`--top/--seeds/--seed-start`.

**★ LAST-MILE (06-LAST-MILE) — §1 + §5 DONE; Gate I3 MET.** `g4_search --curated`
fixes each candidate's input-match passives (`size.match_devices`+`_curate`) at
their prior best, sizes the rest → **converted seq0009 + seq0220 to feasible on
seed 1** (all-free failed them with 10 seeds). **Feasible-novel 1→3, curve
967→367** (2.6× bend). §5 funnel in `loop.py` (--status/--iterate): near-feasible
0.49, **90 one-constraint-off**, top-10 median viol 0.11. Labels `recipe:curated-v1`.

**Cross-spec benchmark (`benchmark.py` → `data/benchmark.md`):** wifi24 **6/6**
feasible (solved); **gps-l1 0/6, gain-limited** (S21≥15 binds 5/6 — cascode+tapped
tops ~12–14 dB); **wideband-sdr 0/6, match-limited** (S11 over band binds 4/6). Both
harder specs need **topology diversity** (gain-boosted + wideband-match archetypes in
templates.py/P5), NOT sizing. Curve honest state: **3 distinct feasible designs, 370
SPICE-min** (dedup fix — repeat-probes no longer inflate it); a broad curated --top 15
sweep added no new distinct designs (candidates stall at S11 −10.0/S21 11.9).

**★ EXIT (07-EXIT §1, iter-4) — Stage 3 phase exit MET; loop is an operating
mode.** Fixed the `size.polish` start-point bug — root cause: `g4_search`
re-parsed the candidate's `token_file`, but P5 arms reuse `seq*.txt` names for
different topologies, so the parsed graph mismatched the stored `best_params`.
Fix: reconstruct topology from the row's **own** `graph.tokens`; fence with
**`size.replay_ok`** (re-eval at stored best must reproduce stored metrics within
σ, else quarantine) + `size.log_l2_result` (record a win as-found, no re-size).
`g4_search --curated --polish` is now **polish-first** (min-margin ascent from the
stored best, ~100 sims, cheap) with curated-ZOAF fallback, wl_hash dedup. Convert
pass → **3 new feasible novel: seq0079, seq0086 (S21 driven 7.3→15.3), seq0046**;
**feasible-novel 3→6, curve 367→186.6 SPICE-min/design.** Two consecutive
improving turns (iter-3 367, iter-4 187) + tripwires quiet ⇒ **exit criterion
MET.** Honest: only the closest ~5 were polish-convertible; the funnel's
`one_constraint_off_count=90` overcounts (flags designs a match-network away).
Store now **7 feasible (6 novel + tapped ref)**.

**★ WP-BROADEN started (07-EXIT §2) — constructors DONE, gps-l1 gain wall BROKEN,
Gate B1 confirmed a generator job.** Scoreboard rotated to `benchmark.md` (wifi24
solved). Landed (`templates.py`, 92→118 archetypes, committed `a14959c`):
* **Gain-boosted (nb, 20 new):** `cs_cs_lna` (two-stage CS→CS) + `current_reuse_lna`
  (complementary NMOS+PMOS, one shared bias current; PMOS wired end-to-end).
* **Wideband (wb, 10):** `rfb_lna` +buffer/+cascode, `_add_load` shunt-peaked.
  The wb screen (`max_inductors`, `match_plausible`) keeps it inductorless by
  construction — right engineering, so it caps ~10, not the aspirational ≥30.
* **Measured (all-free ZOAF + polish + 729-pt match grid):** two-stage reaches
  **S21 17.5 dB @ Idd 2.76 mA vs gps-l1** — both hard constraints met, the ~14 dB
  single-stage gain wall gone. **But S11 won't co-close**: across joint ZOAF (4
  seeds), polish, and a match-device grid, S11 never drops below ≈ −1 while S21
  holds ≥ 15 (higher gain ⇒ bigger Cgs ⇒ harder match — why gps-l1 is *hard*).
  wideband-sdr same shape (rfb: ripple<2/Idd<8 but S21~8 unmatched; cg: matched, no
  gain). **This is the wifi24 lesson: templates give structure, the P5 generator
  gives the sizeable parameterization.** Gate B1's blocker (gain) is measurably
  removed; the closer is the generator, not the sizer.
* **Tooling fix (`size.py`, this session):** `size_topology` now returns
  `best_params` — it was logged but not returned, so polish/curate-from-a-result
  silently ran on `None`. Needed for any "size → polish/curate" flow.

**★★ UPDATE — overnight P5-v3 run closed Gate B1 on gps-l1 (see BROADEN-PROGRESS.md
+ FINDINGS).** Ran the full sequence: labeled families (CP1), rebuilt training data
with 118 archetypes (CP2), P5-v3 fine-tune (CP3, best val 0.2300 @ epoch 1),
generate+NDL (CP4: **nb NDL@256 73→100**, new **wb channel NDL 35**, tripwires quiet,
adopted), curated-size the generated pool (CP5). Result:
* **Gate B1 gps-l1 MET — 2 novel feasible generated LNAs:** `seq0089`
  (S11 −13.1 / S21 15.0 / Idd 2.88) + `seq0215` (S11 −14.4 / S21 15.4 / Idd 2.94),
  recipe `p5v3-gen-v1`. seq0089 was generated matched-but-gainless (S11 −13.7 /
  S21 2.4) and polish drove S21 2.4→15.0 holding the match — the generator supplies
  the co-sizeable input network the hand templates lacked. Thesis re-confirmed.
* **⚠ NF caveat:** feasible on the **gated** constraints (S11/S21/Idd); NF advisory
  and **~4.5 dB vs gps-l1's 1.8 dB target**. gps-l1's gain wall is closed; its noise
  spec is not (and can't be optimized until the port-noise harness lands).
* **wideband-sdr still 0** (generated wb closest S21 ~9.8 unmatched). Store now
  multi-spec (gps-l1 / wideband-sdr / wifi24), 13 feasible rows.

**Next (in priority):**
1. **★ Fix the port-noise NF harness (WORKLOG R3) — now the top pipeline gap.** It
   gates real gps-l1 (1.8 dB) and real wifi24 (2.5 dB); today every "feasible" is
   S11/S21/Idd-only with NF advisory (~2.5–4.5). Un-gate NF as a hard constraint in
   `spec.objective` only after the harness is trustworthy (it desyncs current
   NF-out-of-objective labels — re-label on the new harness).
2. **Close wideband-sdr** (the other half of Gate B1): thicken the wb channel —
   add 2-stage rfb / noise-cancelling CG-CS archetypes (more gain while inductorless),
   get wb winners into `winners_train.json`, re-fine-tune. wb training signal is thin
   (222 template rows, 0 winners) — that's why its generation channel underperforms nb.
3. **Loop the gps-l1 win back:** the 2 gps-l1 feasibles are now winners — emit_winners
   is wifi24-only; generalize it to multi-spec so gps-l1/wideband near-feasibles feed
   the next fine-tune (expert iteration on the new specs).
4. **Deferred:** σ-drift 1.27 (< 2× bar) best-of-3 relabel before any critic retrain;
   Loop-A acquisition; 02 critic-interface leftovers; rung-2 evolutionary loop.

**Deferred (deliberate, not blocking — 00-OVERVIEW #3 "don't block on NF"):**
un-gating NF as a *hard constraint* in the objective (changes sizing; validate
separately, and it desyncs from the current NF-out-of-objective labels), and
adding the series-Rs NF as a baselined value in `check_ref` for the two hand ref
decks (their .cir port setup needs a noise variant; low value — they're match
anchors, not critic data).

---

### ▸ Sub-block: WP-NF — the Gate-D3 NF campaign + ngspice scratch hygiene (owner: the NF-campaign executor)

**Files owned:** `lna/size.py` (`constrained_descent`, `prepared_body` — additive),
`lna/nf_campaign.py`, `lna/nf_moves.py`, `lna/_nf_scan.py`, `lna/_nf_verify.py`,
`lna/_nf_table.py`, `lna/_nf_novel.py`, `lna/_nf_tmp_purge.py`, FINDINGS **§17**,
this sub-block. `extract.py` / `bias.py` / `templates.py` touched for the scratch
fix only. Full measured detail in **FINDINGS §17**; run artefacts in
`lna/out/_nf/` (gitignored).

**★ Gate D3 — NOT MET, but it is a wall with a shape now, not a distance.** The
low-noise family's noise/gain trade at a held broadband match was measured end to
end on `dhruva-s`. Everything below is replay-verified, in-box, K ≥ 1.

| point | S11_max | S21 | Idd | NF | K_min | viol | binds |
|---|---|---|---|---|---|---|---|
| `ce39a7` gain-ascent @ NF ≤ 3.5 | −10.11 | 21.65 | 6.49 | **3.50** | 26.6 | **0.278** | S21 only |
| `19f72303` gain-ascent @ NF ≤ 4 | −10.12 | 27.58 | 12.99 | 3.99 | 15.4 | **0.222** | S21, NF |
| **`19f72303` tier-1 descent** | **−10.01** | **30.00** | **12.67** | **4.89** | 23.7 | **0.398** | **NF only** |
| `8c7592ea` (Session-5 incumbent) | −10.13 | 35.15 | 13.00 | 5.42 | 7.7 | 0.549 | NF only |

* **Best tier-1-feasible dhruva-s NF: 5.58 → 4.89 dB**; its tier-2 violation
  **0.594 → 0.398**. **Program-best dhruva-s total violation: 0.566 → 0.222**
  (2.5×, at 27.6 dB of real gain — not a shrink-to-nothing optimum).
* **★ First design in the program to measure NF ≤ 3.5 dB with the match held:**
  `ce39a77c91974013`, a `moves.aux_path_add` mutant of `nccgcs_s1_R`, **NF 3.416
  at s11_max −10.04**, S21 18.00, Idd 7.83, K_min 81.9. Novel vs **ref-v3**
  (digest `d05390da6183123e`) and vs every pre-campaign store row; NN-sim 0.822
  to its own parent archetype.
* **The gap is a conversion rate: +1.39 dB NF per +8.35 dB S21**, front dense and
  monotone. The one move that would break it — a second gain stage, nearly free
  in noise by Friis — is **blocked by `device_budget` at 16**, which
  `19f72303`/`ce39a7`/`8c7592ea` all touch (`7b0b485b` is 14). §13.5's *latent*
  constraint is now the **active** one. Raising it is a spec change and was
  deliberately not made to close a gate.

**Why the handed-over lever could not work.** `size.polish` ascends the
*minimum* margin, so when one constraint is violated by a lot it optimizes that
one anyway *and values a 4.9 dB gain surplus at exactly zero* — raising a
non-binding margin cannot raise the minimum. **`size.constrained_descent`** is
the fix: optimize one metric, refuse any step that takes a *kept* constraint
below `floor`, score lexicographically `(shortfall, target)`. Box-clamped,
per-seed coordinate shuffling, plus joint multi-coordinate probes (cancellation
is a condition on a *ratio*, so the useful direction is not axis-aligned).
**~0.15 s/eval.**

**Family NF floors, gain-gated at S21 ≥ 15** (an ungated floor is meaningless —
`gmbcg_wb_s0_b1` reads NF 3.61 at S21 −0.63): noise-cancelling CG+CS **3.42 /
3.73 / 3.82 / 3.86**; evolved CG + 2 tuned CS **5.42**; gm-boosted CG **5.29–5.84**.
**Clean ~1.5 dB family separation — only the NC family is on the D3 ladder.**
A *third* tier-1-feasible dhruva-s design turned up on the way (`gmbcg_s2_R_b0`:
S21 31.05 / Idd 9.44 / S11 −10.19 / NF 5.41, viol 0.546).

**Cross-band.** `dhruva-l5` tier-1-feasible with `19f72303` at **NF 3.65**
(S21 28.03 / Idd 9.67 / K 19.7) — noise really is ~1.2 dB lower at 1.18 GHz, but
the target is 1.0 dB tighter, so normalized violation is **0.459 vs dhruva-s's
0.398**: **dhruva-s stays the closest band**, now with a number.

**`wideband-sdr`: best violation 1.551 → 1.375, still 0 feasible, and the
diagnosis changed.** §15 had `nf_db` violated 102/102; with NF in the objective
the binding constraint is the **f0 match** (s11_db −2.6…−3.6 on 8 of 10). NF is
no longer the sole wall there.

**Both attacks on D3 are now measured and symmetric.** §20's rung-1 lead
`seq0126` (NF **2.73** at S21 16.0) and `seq0218` (NF 2.82 at S21 17.7) really do
have the noise — and `--mode match` moves their s11_max only −0.01 → −0.39 and
−0.32 → −0.69 dB. **Designs that match cannot get below 3.4 dB with gain;
designs below 2.8 dB cannot be made to match at all** — on those graphs the match
is structural, not parametric. (⚠ `92d68c1e` also reads K_min −0.33.)

**⚠ The transcribed externals do not size here, and the cause is NOT gate bias.**
All five paper transcriptions were sized; none is competitive (best S21 is
**−10.2 dB**). The intel that 4 of 9 have non-conducting MOS is confirmed and
localized (`align-lna-qm` NM2, `ihp-lna-2p45g` NM3/NM4, `paper-diffcccg` NM1+NM2,
`paper-gmboostcg` NM2) — but an opt-in `BiasInserter.rescue()` that promotes
their rail-reaching gates to R-GATE bias nets **gained 0 conducting devices on
0 of 4**. In every case the off device is under **`sources_no_dc_path`**: no DC
return at the source, which no gate bias can fix. **The rule was reverted, not
landed.** The actionable rule is a *source*-DC-return inserter — a bigger
governance call, since it changes the circuit rather than making it biasable.

**⚙ Perf fix (item 1): 685,287 stale scratch dirs, gone, and they cannot come
back.** `extract.py` gained `scratch()` + `run_deck()`, now the tree's single
ngspice entry point; all six call sites (`run_and_extract`, `measure_stability`,
`measure_nf`, `nf_selftest`, `bias.run_op`, `templates.emit_paths`) route through
it and self-clean. `LNA_KEEP_TMP=1` keeps decks for debugging. The backlog sweep
(`_nf_tmp_purge.py`, pattern-fenced + 60-min age fence so no other agent's live
sim could be touched): **seen 686,780 / matched 685,287 / removed 685,287 /
failed 0, 1,788 s.** Commit `6c13805`.

**Store note.** **96 new L2 rows** (76 `nf-v1` from nf-campaign, 20
`nf-v1+move` from nf-moves); `provenance` carries mode, keep-set, seed, floor and —
for mutants — the move name and parent hash. ~46,000 SPICE evaluations across 9
runs. Regression quartet green before and after.

**Where to pick up (highest value first).**

1. **`device_budget` is now the binding constraint on Gate D3, and the decision
   is the user's.** Every low-noise family member sits at 14–16 devices; a second
   gain stage costs 2 and is nearly free in noise. Justify from real-LNA device
   counts (the `[3,12] → [3,16]` procedure) — or decide the gate stands at 16.
2. **The structural-match wall is the *other* half and it is now the bigger
   prize.** Two generated designs sit at NF 2.7–2.8 with 16–18 dB of gain and no
   input match, and no parameter setting inside the box gives them one. That is a
   *topology* job — an input-match front end grafted onto a low-noise core — and
   `moves.match_elem_add` already exists.
3. **`moves.aux_path_add` is the highest-yield edit measured on noise** (it alone
   broke 3.5 dB). Worth a dedicated, larger mutation run from `7b0b485b` (14
   devices, 2 free slots) rather than the 20-mutant probe run here.
4. **`wideband-sdr` needs the spec re-read, not more search** — the wall there is
   the f0 match under `max_inductors: 1`, not NF.

### ▸ Sub-block: `wideband-sdr` spec recalibration against published silicon (owner: the spec-recalibration executor)

**Files owned:** `lna/specs/wideband-sdr.yaml` (constraints + header only —
`topology:`/`sizing:` untouched), FINDINGS **§22**,
`lna/data/reports/wideband-sdr-recal-2026-08-09.md`, this sub-block. Directly
answers item 4 above. Blind protocol: Kanchetla et al. TMTT 2022 (NavIC/GPS)
**hard-excluded** from all sourcing.

**★ Found and fixed a metric-definition bug while verifying the spec's own
"holds across the whole band" claim.** It was false: the constraint gated
`s11_db` (`extract.py`'s AT-F0 spot value), not `s11_max_db` (worst case over
`[f_lo,f_hi]`, also computed, never gated) — present since `WP-SPEC day 1`
(`cfa1721`), and the one spec never updated to the `dhruva-*` / `critic.py`
`S11_SLOTS` precedent that already treats `s11_max_db` as "the" broadband-spec
S11 constraint. §17.7's own prose ("the f0 match — s11_db lands at
−2.6…−3.6 dB") was already quoting `s11_max_db` values under the wrong label
(confirmed against the stored row: `s11_db=−17.71`, `s11_max_db=−3.61` on the
same design) — previous sessions reasoned about the right metric informally
while the code enforced the easy one. **Fixed: now gates `s11_max_db`.**

**Recalibrated from a 3-agent, 44-source, 12-design literature survey of
measured-silicon CMOS wideband/inductorless LNAs** (noise-cancelling lineage,
TV-tuner/UWB, recent 2012–2024 low-power — table + full citations in
FINDINGS §22.1 and the spec file's own header comment):

| constraint | old | new | why |
|---|---|---|---|
| S11 (band-wide) | `s11_db`(@f0) ≤ −10 | `s11_max_db`(worst-case) ≤ **−10** | metric fixed, value confirmed: 6/7 comparable published designs meet/beat −10 dB |
| NF | ≤ 3.5 | ≤ **3.5** (unchanged) | literature NF-min clusters 1.85–2.9 dB; 10/12 clear 3.5 with margin |
| gain (S21@f0) | ≥ 12 | ≥ **14** (tightened) | literature gain clusters 14.5–23 dB; 12 sat below all but 2 low-power outliers |
| ripple | ≤ 2 | ≤ **2** (unchanged) | matches Blixer's measured ±1 dB (2 dB pk-pk) flatness |
| Idd | ≤ 8 mA | ≤ **8 mA** (unchanged) | power-normalized to our fixed 1.1 V rail (P/1.1V); ~65th percentile of the literature spread |

**Re-judged the store's 134 existing `wideband-sdr` L2 rows from stored
`metrics` — no re-simulation** (`spec.feasible()` / `datastore.margins_for()`
both recompute purely from a row's `metrics` dict against whatever spec
they're handed, confirmed by reading both before running this). **Still 0/134
feasible either way.** Best total normalized violation moves **1.375 → 2.055**
— numerically worse, and correctly so: the old number was free of any S11
penalty (the record-holder passed the spot check at −17.7 dB while its true
worst-case match was −3.6 dB); the new number prices that in. **Sharper
diagnosis: `s11_max_db ≤ −10` has never once been cleared by any of the 134
stored rows, at any NF/gain trade-off** (old `s11_db` gate: 29/134 passed;
new `s11_max_db` gate: 0/134). Six of the twelve surveyed literature designs
are explicitly 0-inductor, so the wall reads as a topology-library gap (no
archetype here implements a multi-path feedback match like Sobhy et al.
TMTT'11), not a physical impossibility — matches item 2 above (structural,
not parametric) one spec over.

⚠ **Domain note (same pattern as the NF re-gating precedent, §13.4):** every
row's stored `margins` in `topo_labels.jsonl` was computed under the *old*
spec and is untouched — append-only, nothing bumped or relabeled. The
re-judged numbers above are reported fresh, not written back. Re-labeling is
the next session's call, not exercised here.

**Regression: unaffected and green, before and after.**
`calibrate_specs.py` only exercises the L0 structural screen (`topology:` was
not touched) — byte-identical to baseline (114/192, 32/41, 94.1%, 0/4). Full
quartet: vocab MATCH, pipeline_yield 40/42 (95.2%, only the known 1081
singular matrix), `check_ref`/`check_nf`/`check_stab`/`check_bjt` all GREEN.
Other spec files (`dhruva-{l1,l2,l5,s}.yaml`, a `device_budget` bump) showed
modified in `git status` from a different concurrent agent's uncommitted
work in this shared worktree — not touched, not committed here.

```bash
python lna/spec.py wideband-sdr        # confirm the recalibrated numbers
python lna/calibrate_specs.py          # L0 screen, unaffected
python lna/pipeline_yield.py --indices 461-492,1081-1090
```

**Where this points next.** Item 2 above (a structural input-match front end,
`moves.match_elem_add`) is now doubly motivated: it is the wall on both
`dhruva-s`'s two best-NF designs *and* on all 134 `wideband-sdr` attempts.
Sobhy et al.'s "multiple feedback" topology (§22.1) is a concrete published
example of the kind of multi-path match this archetype set does not yet have.

### ▸ Sub-block: WP-NF part 2 — the `device_budget` unlock and the second gain stage (owner: the NF-campaign executor)

**Files owned:** `lna/specs/dhruva-*.yaml` (budget field only), `lna/nf_moves.py`
(move filter + recipe tag), `lna/_nf_devcount.py`, `lna/_nf_budget_check.py`,
`lna/_nf_verify2.py`, `lna/_nf_verify_l5.py`, FINDINGS **§23**, this sub-block.
`bias.py` was **not** touched (it moved to the ingestion track). Continues the
WP-NF sub-block above; full detail in **FINDINGS §23**.

**★ The unlock worked, and Friis is now measured rather than asserted.** §17's
wall was that the one move able to break the NF↔S21 trade — a second gain stage —
could not be *proposed*, because every frontier design sat at 16 devices. With
`device_budget` at [3,18]:

| | devices | S11_max | S21 | Idd | NF |
|---|---|---|---|---|---|
| parent `7b0b485b` (`nccgcs_s1_R`) | 14 | −10.02 | 18.95 | 6.56 | 3.86 |
| **+ `moves.stage_add`** | **17** | −10.23 | **28.51** | 8.20 | **3.92** |

**+9.56 dB of gain for +0.06 dB of noise.**

**★ Best design in the program on `dhruva-s` — `f578743ae13296d0`** (18 devices,
`stage_add` → `load_swap`), **TIER-1 FEASIBLE**:

> **S11_max −10.02 / S21 33.74 / Idd 10.83 / NF 3.70 / K_min 239.6**,
> `replay_ok` True, in-box, unconditionally stable, **NF the only violated
> constraint**, total violation **0.059**. Novel vs ref-v3 (`d05390da6183123e`).
> Four seeds land 3.70 / 3.71 / 3.72 / 3.74.

**What the budget bought, three ways.** At the spec's S21 ≥ 30: **NF 4.89 → 3.70
(−1.19 dB)**, **violation 0.398 → 0.059 (6.7×)**, and **Idd 12.67 → 10.83 mA** —
noise improved *while* current fell, i.e. a second stage is strictly cheaper than
driving one stage harder. **And the exchange rate improved 4.5×**: §17 measured
0.166 dB NF per dB of S21; the 17–18-device front runs 0.030 dB/dB (NF 3.33 @
S21 21.34 → NF 3.70 @ S21 33.74). That is the real content of the unlock — gain
stopped being expensive in noise.

**The spec change, calibrated not reverse-engineered.** 16 → 18 on the four
dhruva specs only; `gps-l1` / `wifi24` / `wideband-sdr` / `legacy-lna5` untouched.
Over all 50 reference circuits (median 6, p90 13) three real designs exceed 16:
**`ihp-lna-2p45g` @ 18** — an IHP SG13G2 **2.45 GHz** open tapeout, the closest
real analogue to dhruva-s at 2.492 GHz — `align-lna-qm` @ 19, `ihp-gps-lna-npn`
@ 21. **18 is the device count of the nearest-in-frequency real silicon LNA**,
which is why the bound stops there. Verified: the L0 screen and `moves.py` ctx
both honour it, the 18-device real LNA now passes the dhruva-s screen, and the
19-device one is **still rejected** — enforced, not removed. New rows carry recipe
**`nf-v2+d18`** so the two budget domains never mix.

**Gate D3 per band — NOT MET, by 0.20 dB on `dhruva-s`.**

| band | target NF @ S21 | best tier-1-feasible | NF | viol | short by |
|---|---|---|---|---|---|
| **dhruva-s** | 3.5 @ 30.0 | `f578743ae13296d0` (18 dev) | **3.70** | **0.059** | **0.20 dB** |
| dhruva-l5 | 2.5 @ 22.3 | `439032fd40e7e504` (18 dev, `aux_path_add`) | 3.31 | 0.324 | 0.81 dB |
| dhruva-l2 / l1 | 2.5 / 2.7 | not run (see below) | – | – | – |

l5's noise did improve (3.65 → 3.31) but its tighter target leaves it further
away in normalized terms — dhruva-s is now the closest band by a wide margin.
**l2 and l1 were not run**: l2 carries l5's targets at 1.23 GHz and l1 sits
between, so neither could plausibly beat 0.059 — an inference, flagged as such,
not a measurement.

**Cost.** 5 growth runs + 6 descent campaigns, ~35,000 further SPICE evals,
**57 further L2 rows** (36 `nf-v2+d18` + 21 `nf-v1`), total **153** for this
executor. Four runs were stopped early once their answer was measured, to
reallocate the 3-way ngspice budget; every quoted result survives in the
append-only store and was re-verified from it.

**Where to pick up (highest value first).**

1. **The next 0.20 dB is a `device_budget` decision again, and the numbers are
   already on the table.** `f578743ae13296d0` has 3.74 dB of gain slack, worth
   only ~0.11 dB of noise at the measured 0.030 dB/dB — not enough, which is why
   four seeds converge at 3.70. A **third** stage costs 3 devices; the same
   calibration that justified 18 would justify 20–21 (`align-lna-qm` 19,
   `ihp-gps-lna-npn` 21). **Decide it on whether a 20-device LNA is defensible,
   not on the fact that it closes the gate.** A second independent probe agrees:
   `6f0d080f91dfc642` at NF 3.33 / S21 21.34 with 5.2 mA unspent projects to
   ~3.59 — still short.
2. **`moves.stage_add` is now the highest-yield structural edit measured**, and
   it needs a ≤15-device parent. The move set should be re-run from the *smaller*
   low-noise designs, not the frontier ones — the parent that produced everything
   here was the 14-device `nccgcs_s1_R`, not the 16-device elites.
3. **Re-run `benchmark.py` on the dhruva bands** — the budget change alters the
   L0 screen, so every cached dhruva screen/benchmark number predates it.
4. l2 / l1 remain unmeasured under the new budget (§23.4).

### ▸ Sub-block: WP-NF part 3 — ★★ **Gate D3 MET on `dhruva-s`** (owner: the NF-campaign executor)

**Files owned:** `lna/specs/dhruva-*.yaml` (budget only), `lna/_nf_gate_d3.py`
(new — the gate audit), `lna/_nf_budget_check.py`, FINDINGS **§25**, this
sub-block. Store rows: recipe **`nf-v3+d21`** (28). `bias.py` untouched (it
belongs to the ingestion track). Continues the two WP-NF sub-blocks above.

**★★ GATE D3 IS MET on `dhruva-s`** — the first NF-gated feasible dhruva LNAs in
the program, and **two independent designs** clear it.

> **`ace8383c2fa68d03`** — 20 devices, 2 inductors, `moves.stage_add` off parent
> `6f0d080f91dfc642`:
> **s11_max −10.370 ≤ −10 · S21 34.374 ≥ 30 · Idd 11.561 ≤ 13 · NF 3.240 ≤ 3.5**
> · K_min **173.2** in band, **57.8** over 0.1–20 GHz (unconditionally stable both).
>
> **`ced0d8bd36ed4890`** — 20 devices, same move and parent:
> −10.537 / 39.151 / 12.825 / **3.253**, K_min 64.1 / 18.1.

Audited by the new `lna/_nf_gate_d3.py`, which rebuilds the topology from the
row's **own tokens**, re-evaluates the row's **own `best_params`** and
re-measures `spec.feasible()` rather than trusting the stored verdict:
**replay 5/5 (and 3/3) identical, spread 0.0000 on every gated metric; in-box
30/30; unconditionally stable in band and wide; novel vs ref-v3** (198 hashes,
digest `d05390da6183123e`; nearest `arch:nccgcs_s1_R` at 0.806 / 0.781).

**★ The mechanism corrects my own §23 write-up, and this is the transferable
part.** §23 measured a 0.030 dB/dB NF↔S21 exchange rate and predicted a third
stage would let the *frontier* design spend its 3.74 dB of gain slack. Both
halves were run, and the prediction was wrong:

| start | parent state | + `stage_add` | S21 | NF |
|---|---|---|---|---|
| `f57874`/`3e4a6a` (18/17 dev) | already NF **3.70**, gain to spare | `3a5fc1` (21 dev) | 33.7 → 46.9 | 3.70 → **3.71** |
| **`6f0d08` (17 dev)** | had the **noise** (3.33), lacked **gain** (21.3) | **`ace838` (20 dev)** | 21.3 → **34.4** | 3.33 → **3.24** |

**13 dB of gain onto the quiet design cost nothing (NF improved 0.09 dB); the
same 13 dB onto the frontier design moved NF by 0.01 dB.** Four seeds on the
21-device `3a5fc1` converge at 3.71 — identical to the 18-device 3.70. Friis read
properly: extra gain lowers total NF only while the input stage is still being
over-driven to make gain. §23's own achievement (relaxing that stage, Idd 12.67 →
10.83) had already collapsed F to F1, so there was nothing left to convert.
**The front is two regimes with a knee, not one exchange curve — and §23
extrapolated across the knee.** Practical rule: **grow the quietest parent, not
the best one.** `6f0d08` had the *worst* violation of the three (0.289 vs 0.059)
and was the only one that reached the gate.

**⚠ The gate needed 20 devices, not 21.** `stage_add` costs 3 off a 17-device
parent, so the binding fact was 20 > 18. Both D3 designs are 20 devices; the only
21-device design built is the one that bought nothing. A widening to 20 would have
closed it identically — recorded so the next request of this kind is sized to the
measured need. The 18 → 21 change is calibrated to `ihp-gps-lna-npn` @ 21, a real
IHP SG13G2 **GPS-band** LNA and the **largest real design in the 50-circuit
reference set**, so 21 is where this justification runs out. Verified: the L0
screen and `moves.py` ctx read it, the 21-device real LNA now passes the dhruva-s
screen, **22 and 30 are still rejected**, other specs untouched.

**Gate D3 per band.**

| band | target NF @ S21 | best | NF | viol | verdict |
|---|---|---|---|---|---|
| **dhruva-s** | 3.5 @ 30.0 | `ace8383c2fa68d03` (20 dev) | **3.240** | **0.000** | **★★ MET** |
| dhruva-l5 | 2.5 @ 22.3 | `439032fd40e7e504` (18 dev) | 3.31 | 0.324 | NOT MET, −0.81 dB |
| dhruva-l2 / l1 | 2.5 / 2.7 | not run | – | – | unmeasured |

l5 was pushed with the same lever and does not close: the D3 graphs re-sized
against it give NF 3.38 / 3.43, a fresh `degen_add` mutant 3.35 @ S21 22.99, and
the band floor sits at ~3.31 vs 2.5. **Unlike dhruva-s there is no starved-gain
design left to convert** — every l5 candidate is already tier-1 clean with gain to
spare, i.e. l5 sits on the far side of the §25.2 knee where more gain is inert.
**Closing l5 needs a quieter input stage, not more devices.**

**Attribution, precisely.** Search + sizing, **not** generation: blind-v1
archetype `nccgcs_s1_R` → 1-edit moves (`load_swap` → `stage_add`) →
`constrained_descent`. Novel against ref-v3 and every prior store row, but no
generator sample is involved — this is **not** the "the pipeline designed it"
claim Track B's `seq0192` made. Blind protocol held; every move is a generic
textbook edit.

**Still open, and it qualifies the engineering claim (not the gate):**
`iip3_dbm` is still `unsupported` on all four specs (tier-3, needs two-tone/HB),
and stability remains frequency-domain with ideal elements — no corners, load
pull, or package/layout parasitics.

**Where to pick up.**

1. **`dhruva-l5`/`l2` need a lower-noise INPUT stage** — more gain and more
   devices are both measured inert there (§25.4). That is a topology question for
   the archetype set / generator, not the sizer.
2. **Feed the two D3 designs back to the generator.** There are now NF-gated
   *feasible* dhruva labels for the first time; `emit_winners` + a P5 fine-tune on
   them is the natural expert-iteration step, and it is the route to a
   *generated* tier-2 feasible (the claim this result explicitly does not make).
3. **`benchmark.py` independently reproduces the gate** (2-spec, 17 candidates):
   tier-1 dhruva-s 3/17 · l5 3/17, **tier-2 dhruva-s 1/17 · l5 0/17** — the
   first tier-2 dhruva cell the benchmark has ever reported (§14.3 read 0 on
   all four bands). ⚠ That invocation **rewrites `lna/data/benchmark.md` and
   drops every spec not named** — it dropped gps-l1 / wideband-sdr / dhruva-l2,
   so the file was reverted and is not part of this change. Re-run at full
   budget with the **full spec list**, and add the two D3 designs to the set.
4. **l2 / l1 remain unmeasured** under the new budget.

### ▸ Sub-block: WP-L5 — the noise budget, and the single-finger artefact (owner: the NF-campaign executor)

**Files owned:** `lna/extract.py` (`measure_noise_budget`, `noise_elements` —
instrumentation), `lna/size.py` (`_noise_budget_row`), `lna/nf_campaign.py`
(`pool:` source), `lna/_nf_budget.py`, `_nf_fingers*.py`, `_nf_gridcheck.py`,
`_nf_probe*.py`, FINDINGS **§26**, this sub-block. Recipe `l5-nf-v1`.
`bias.py` and `to_spice.py` untouched (ingestion track). Continues the three
WP-NF sub-blocks above.

**⚑ Redirect acknowledged.** The mid-campaign directive — no formulas on the
*design* side (no analytic cancellation-locus start points, no hand-authored
gm-boosted archetypes) — arrived while phase 1 was still being built. **Nothing
from phase 2 or phase 3-as-authored-structure had been written, so nothing was
reverted.** Measurement math stays and is what §26 is. Phase 3 became a
capability test of the learned system; results below.

**★ The headline is not the gate, it is the diagnosis.** `dhruva-l5` was assumed
to be blocked by input-stage noise. A per-element decomposition says otherwise:
**26–40% of the excess noise factor on every dhruva design is BSIM4
gate-electrode resistance**, because the harness emits every MOSFET
**single-finger**. The 45nm card has `rgatemod=1`, `rshg=0.4`, `ngcon=1`, and
`NF` (fingers) is a per-instance parameter we never set — so a 100–200 µm RF
device carries hundreds of ohms in series with its gate. **The dominant
per-MOSFET mechanism is `rg`, not `id`.** Second-largest real contributor is
`rql1`, the finite-Q inductor loss at 14.2% — the price of the passive match.

**Re-sized at a 4-finger layout (nothing else changed), the SAME topologies reach
NF 2.03–2.33 dB tier-1 feasible on `dhruva-l5` — under the 2.5 dB target**
(`439032` 2.214/8-finger 2.012; `998ff3` 2.114 and 2.030 on both seeds).

⚠ **Nothing is adopted, and this is NOT a Gate-D3 claim on l5.** Finger count is
a harness-fidelity parameter of the same class as `inductor_q`/`device_budget`;
changing it moves **every NF label in the store**, and changing it to close a gate
is what §13.5/§23/§25 each refused to do. It is also not mine — emission lives in
`to_spice.py` (ingestion track). If adopted, the defensible rule is a fixed
**finger width** (real RF practice ~1–5 µm) giving `NF = ceil(W/w_finger)` —
calibrated to layout practice, not to a target. **This needs a user decision.**

**Instrumentation, validated before being believed.** Two discoveries were needed:
ngspice emits per-source noise vectors **only** when the `noise` line carries a
`pts_per_summary` argument, and it uses **two naming conventions at once**
(`onoise.<mos>` dotted with per-mechanism children, `onoise_<res>` underscored).
Validation: golden deck gives NF-via-shares **3.0103 dB exact** and Rn share
**0.5000 exact**; Σ per-element powers ÷ total = **1.0000** on all six real
designs; and NF-via-shares agrees with the existing `inoise` path to **≤0.002 dB**
— an independent cross-check that also **re-confirms the §25 Gate-D3 numbers**.
Separately cleared: `measure_nf`'s 51-point grid can read up to 14 MHz off f0
(on `dhruva-s` it lands at 2.500 not 2.492 GHz); **measured error −0.003…+0.009 dB**,
immaterial, and the D3 claim holds at NF 3.238 evaluated exactly at f0.

**Capability test (c) — search:** `moves.py` from the quietest compact parents,
16 mutants. Best **`86d5ce252054a160`** (18 dev, `cascode_add` off `6f0d08`):
s11_max −10.006 / S21 22.879 / Idd 7.34 / **NF 3.185** / K_min 67.6, replay-verified,
in-box, novel. **Tier-1 feasible, NF fails.** New l5 record (3.31 → 3.18) — found
by the search unaided, but 0.69 dB short.

**Capability test (b) — generator:** P5-v7's 256-sample nb pool (first checkpoint
trained on the ingested real gm-boosted-CG / cross-coupled-CG / noise-cancelling
silicon). **189/256 pass the l5 screen**; the 12 ranked furthest from the
incumbent NC/rfb families by WL similarity were sized. Best results: `seq0149`
S21 **6.5** dB at NF 7.7; `seq0038` NF 3.77 at S21 **−1.3**; rest NF 10–200 dB.
**None is a viable amplifier — the generator did not produce a working l5 input
stage, let alone a quieter one.** Per the redirect that is a reported outcome,
not one to rescue with hand-authored structure.

⚠ **The capability test is confounded and the confound is the artefact.** A
quarter to two-fifths of the noise a "quieter input stage" must remove is not
removable by topology at all. **Re-run (b) and (c) after the finger decision** —
until then "the models cannot find a sub-2.5 dB input stage" is true but not
attributable to the models.

**The budget is now label data.** `size._noise_budget_row` stores a compact
per-element budget on every NF-gated L2 row under `provenance.noise_budget`
(top contributors by share of F−1 + the MOSFET mechanism split), one extra
~0.15 s call per label, **input features only, never gated**. The same NF can
come from a dominant input device (sizing-fixable) or a lossy match
(topology-only) and the critic currently cannot see the difference.

**On the flagged transformer-feedback gap: the budget does NOT point at it.**
Feedback-R thermal noise is not dominant (the NC family has no feedback
resistor; `rr1` at 17.8% of F−1 is a *load*). Missing mutual-inductance in the
vocabulary is a real limitation but **is not what costs us l5**, and this
campaign does not justify building it.

**Verdict:** `dhruva-l5` Gate D3 **NOT MET** — best honest NF **3.185** tier-1
feasible vs 2.5, **0.69 dB short** (was 0.81). l2/l1 unmeasured.

**Where to pick up (highest value first).**

1. **Decide the finger count** — it is worth ~0.8–1.1 dB of NF on every design in
   the store and currently makes every published NF number pessimistic by an
   amount nobody had quantified. Calibrate to finger width, then **re-label**.
2. **Re-run the two capability tests afterwards** (§26.4/§26.5); the current
   negative is confounded.
3. **`rql1` (inductor Q) is the second real contributor at 14.2% of F−1** — that
   is the broadband match's price and is *not* an artefact. If the finger fix
   lands, Q becomes the leading real term and `inductor_q=12` deserves the same
   calibration scrutiny.
4. l2 / l1 remain unmeasured under the current budget.

### ▸ Sub-block: WP-MF — the multi-finger cutover, ★★★ Gate D3 on all four dhruva bands (owner: the NF-campaign executor)

**Files owned:** `lna/to_spice.py` (emission — owned for this cutover),
`lna/size.py` (`_zoaf_cfg` stamp, `prepared_body(w_finger=…)`),
`lna/relabel_mf.py`, `lna/nf_campaign.py` (`--recipe`), `lna/_mf_prove.py`,
`lna/_mf_stab_control.py`, FINDINGS **§27**, JOURNEY stage **23**,
STRUCTURE_LOGIC §5, this sub-block. Recipes `mf2-v1`, `mf2-cap-v1`.

**★★★ Gate D3 is MET on ALL FOUR dhruva bands with one 20-device design.**
`ace8383c2fa68d03` (`moves.stage_add` off `6f0d080f91dfc642`):

| band | S11_max | S21 | Idd | **NF** | target | K_min in / 0.1–20 GHz |
|---|---|---|---|---|---|---|
| dhruva-s | −10.001 | 36.473 | 13.000 | **1.288** | 3.5 | 54.6 / 21.5 |
| dhruva-l1 | −10.000 | 36.824 | 12.997 | **1.220** | 2.7 | 17.3 / 9.7 |
| dhruva-l2 | −10.002 | 35.773 | 12.989 | **1.506** | 2.5 | 14.4 / 9.6 |
| dhruva-l5 | −10.001 | 35.961 | 12.963 | **1.253** | 2.5 | 19.9 / 10.3 |

Full audit per band: replay 3/3 identical (spread **0.0000** on every gated
metric), 30/30 in-box, `spec.feasible()` re-measured not trusted, unconditionally
stable in band **and** wide, novel vs ref-v3. Independent winners close too
(l5 `998ff3` 1.32 / `86d5ce` 1.40; l2 `86d5ce` 1.38; s `ced0d8` 1.46), so it is
not one lucky graph. wifi24's tier-2 `seq0220` survives and improves:
**NF 2.31 → 1.473**.

**The cutover.** ` NF={max(1,ceil(pW/2e-06))}` on every MOS instance; W is a
`.param` so the count must be a parser-evaluated expression. `w_finger=None`
reproduces the old deck byte-for-byte (the relabel's replay fence needs it).
**Proven, not assumed** (`_mf_prove.py`, same design/params): `rg` share of F−1
**36.4% → 0.4%**, `id` 23.0% → 22.3%, NF 3.310 → 2.031, sum-closure 1.0000 both
ways. **The stamp (`w_finger`/`mos_fingers` in `zoaf_cfg`) was committed first
and alone**, because other agents were sizing at the time.

**Re-baseline.** Measurement math untouched and re-verified (NF golden
3.012469, `check_nf` GREEN, budget selftest GREEN). vocab MATCH, screen 59.4%,
pipeline_yield **40/42 unchanged**, calibrate ALL MET. **`check_ref` needed no
`--update`** — the hand `ref/*.cir` decks never pass through `to_spice`, so the
cutover cannot reach them. ⚠ **That leaves an inconsistency to decide:** the
three hand references (incl. the wifi24 tier-2 reference `ref24_tapped` at
NF 2.00) are still on the single-finger domain. Not taken here — they are a
frozen anchor.

**Re-label: the old harness overstated NF by a median of 2.08 dB.**
1317 pre-cutover NF-bearing rows → 1245 distinct points; **1240 relabeled,
6 quarantined, 0 failed**. Delta (new−old): min −14.758, p25 −4.018,
**median −2.078**, p75 −1.101, max +105.756 (degenerate near-passive designs),
mean −1.794; **1109/1240 improved**. Unlike WP-D1 this cutover changes the
*circuit*, so the **full metric vector** is re-measured at the stored point, not
just `nf_db` — the match moves too.

**⚠ The artefact was also hiding a stability problem — and it is a PREVIOUS gate
that is qualified, not this one.** `check_stab`'s winner audit now reports the
**Gate-D1/D2 4-band archetype** `rfbcs3_tank_cc21_bf0` as only CONDITIONALLY
stable on `dhruva-l2` (K_min +10.15 → **−17.2**, μ_min 0.977). A five-point
control shows |S12·S21| **flat** (−81.3 → −82.7 dB), so the flip is in K's
numerator — a port reflection coefficient exceeding unity, i.e. negative
resistance the sizing always had; single-finger gate resistance was a real lossy
element guaranteeing passivity. My first hypothesis (an un-damped feedback path)
was contradicted by my own control and is recorded as wrong. **Consequence:
§14.3's "8 of 84 cells read K < 1" and every other stability count taken through
the old harness are LOWER BOUNDS and deserve a re-audit.** The D3 winner is clean.

**Capability tests, re-run unconfounded (§26 flagged both as confounded).**
* **Search now reaches the gate unaided** — 8 of the first 14 `moves.py` mutants
  are tier-2 feasible on l5, best `degen_add/809374` **NF 1.19**. The §26
  negative was the harness, not the search.
* **Generator still fails, for a different reason than assumed.** P5-v7's 12 most
  distinct pool candidates: still nothing viable. The two P5-v8 l5 candidates
  (§28) re-size to **NF 1.02** and **NF 0.96** with S21 22.3 and Idd ≈13 — and
  stop at **S11 −4.46 / −0.99**. The generator's designs were **never
  noise-limited; they are match-limited** (the §17.8 structural-match wall).
  **The next generator question is a matching question, not a noise one.**

**Correction to the incoming v8 report:** `ced0d8bd36ed4890` is **not** missing
from the store — 10 rows in `lna/data/topo_labels.jsonl` with tokens and params,
and it resolved by hash in three campaigns this session. Checked rather than
acted on; no fix needed.

**Where to pick up.**
1. **Re-audit stability store-wide on the new emission** — old K counts are lower
   bounds (§27.5), and one previously-claimed gate design is affected.
2. **Decide the hand reference decks** (`ref/*.cir`): single-finger anchor vs
   consistency with everything generated.
3. **The generator's wall is the input match, now cleanly isolated** — its
   candidates already have NF ≈ 1 dB and 22 dB of gain.
4. `iip3_dbm` is still `unsupported` on all four specs; tier-3 remains open, and
   stability is still ideal-element frequency-domain (no corners/package).

## Session 7 (2026-08-10) — concurrent agents on `lna-data`

### ▸ Sub-block: WP-MATCH — ★★★ Gate D3 MET on `dhruva-l5` by a **generator-emitted** topology, and why the wall was there (owner: the generator-matching investigator)

**Files owned:** `lna/_match_struct.py` (the input-port instrument),
`lna/_match_census.py`, `lna/_match_sep.py`, `lna/_match_mix.py`,
`lna/_match_sample.py`, `lna/_match_reweight.py`, `lna/_match_pools.py`,
`lna/_match_gpu_sample.sh`, `lna/_match_gpu_train.sh`, FINDINGS **§29**,
JOURNEY stage **24**, STRUCTURE_LOGIC Blocks 3/8, this sub-block. Store recipe
**`match-v1`** (114 rows). Nothing in `lna/repro/**` touched (concurrent
read-only packager owns it); no shared checkpoint written (private stem
`ft_p5v9m`); `to_spice.py`, `spec.py`, the specs and `templates.py` untouched.

**★★★ `80aaf9f4a0cd7863` = `ft_p5v8_nb_s1337/seq0173`, 16 devices — TIER-2
FEASIBLE on `dhruva-l5`, and its topology is the generator's, with no `moves`
edit at all.** S11_max **−10.017** (held 1.1–2.5 GHz) / S21 **29.794** / Idd
**12.993** / **NF 1.788** (target 2.5). Audited (`_nf_gate_d3.py`): replay 3/3
identical, **spread 0.0000** on every gated metric; **24/24 in-box**;
`spec.feasible()` re-measured; **unconditionally stable in band (K_min 13.17) and
over 0.1–20 GHz (13.16)**; WL hash **absent from ref-v3** (nearest
`arch:nccgcs_s1_R`, 0.845). Tokens + params committed at
`lna/out/match_dhruva_l5_seq0173.{tokens.txt,params.json}`.
**Attribution:** the graph is the generator's; this session contributed only
**candidate selection** (a structural criterion measured off the store's own
labels) and the **existing** sizing path (`size_match_first` → `constrained_descent`).
`iip3_dbm` still `unsupported`; stability still ideal-element frequency-domain.

**★★ Second gate, on the exact design §27.6 called un-matchable.** `fb48c7f2`
(`seq0085`, S11 −0.99, NF 0.96) + `moves.input_class_swap` + `moves.cascode_add`
= **`78f5cc9cc2cd0133`** (11 dev): S11_max **−10.014** / S21 **24.560** / Idd
**12.997** / **NF 1.963**, replay 3/3 spread 0.0000, 18/18 in-box, unconditional
in band (K_min 1.382) **and** 0.1–20 GHz (1.394), novel (nearest
`arch:gmbcg_s2_R_b0`, 0.769). Committed as
`lna/out/match_dhruva_l5_swap_cascode.*`.

**Why the wall was there — the measurement chain.**
1. **It is not the tool and not the emission.** `--mode match` on the current
   multi-finger harness: `eaf1b914` −4.46 → **−4.46**, `fb48c7f2` −0.99 →
   **−0.99**, `92d68c1e` −0.10 → −0.64, `f2f10647` −0.31 → −0.74. With the trust
   region **removed entirely** (only Idd ≤ 13) and **3 independent global
   restarts** each: best **−4.73 / −0.49 / −4.68 / −6.40**. Control, same tool,
   *tighter* region: `ace8383c` −10.00 → **−21.15**, `8c7592ea` −9.69 →
   **−15.14** (newly tier-2 feasible on l5).
2. **It is not failing to emit a port network** — 91.4% (v7 nb) / 95.0% (v8 nb)
   have one, vs 92.7% corpus and **91.5% of stored designs that never match**.
3. **The discriminator is whether the port reaches a transistor SOURCE.**
   P(match|source) 0.581 vs P(match|gate-only) 0.132 over 828 graphs; on dhruva
   bands inside each provenance class: generator **0.571 vs 0.109** (at 9.0 vs 9.2
   devices, 224 vs 218 evals), search 0.736 vs 0.088, archetype 0.733 vs 0.029.
   **Not a bandwidth failure** — generator dhruva designs reach −10 dB *at f0*
   only 21.2% of the time (median S11@f0 **−1.39 dB**).
4. **★ Mechanism.** Multi-finger dhruva rows that already hold the band match:
   **gate-only** n=31, median NF **7.52 dB**, **0 of 31** reach NF ≤ 2.5 with
   S21 ≥ 22.3; **source-driven** n=139, median **2.97 dB**, **54 of 139** clear
   both. Rows that do *not* match: gate-only min NF **0.24 dB**. A gate-driven
   input here is quiet exactly when it does not match.

**Data lever — REJECTED, and it confirms §28's law a third time.** P5-v7's
stage-B rows carry the motif at **21.8%**: corpus 36.5%, external 39.9%, winners
5.8%, and the **118-archetype channel (30.9% of rows) at 1.35% (2 of 103)** — the
hand library is 88 `cs` + 16 `cscs` + 12 `rfbcs` + 8 `rfb` + 5 `rfbcs3` +
4 `creuse`, all gate-driven, vs 10 `gmbcg` + 3 `nccgcs` + 2 `cg`. **P5-v9m**
(v7's stage B, one variable changed: +1468 rows oversampled from the 18
motif-bearing traversal sources already in the mix; val byte-identical at 736):
nb **NDL 79 → 45** at motif 0.192 → **0.275**; wb **41 → 38** at 0.235 → **0.314**.
**REJECT — the adopted generator remains P5-v7 (`ft_p5v7_v2.pth`, nb 79 / wb 41).**

**Sampling lever — rate fully controllable, yield unmoved.** `_match_sample.py`
points `generate.py`'s prefix conditioning at a fine-tuned P5 checkpoint for the
first time. The `uncond` arm reproduces P5-v7's published row on **every** column
(NDL 79 / copies 46.9-14.5-32.0 / medNN 1.000 / term 100.0 / valid 99.6 /
indR 0.230):

| arm | NDL@256 | motif | corpus copies | NDL(l5) motif-bearing |
|---|---|---|---|---|
| P5-v7 baseline | **79** | 0.1922 | 32.0 | **10** |
| `gate` len-12 (control) | 54 | **0.0316** | 39.1 | 2 |
| `all` len-12 | 54 | 0.2598 | 34.0 | 7 |
| `src` len-12 | 21 | **0.7579** | 55.5 | **10** |
| `src` len-24 | 10 | **0.9258** | **71.9** | 8 |

**4.8× the motif rate, zero extra usable candidates** — every extra sample is an
exact corpus copy. Three different mechanisms (winners feedback §28, prefix
conditioning, row re-weighting) all raise the targeted statistic and lower NDL.

**⚠ `wideband-sdr`: the diagnosis does NOT transfer.** 119 distinct graphs,
**0/119** ever hold the band match; source-driven best **−6.61**, gate-only best
−9.67 (at S21 −600). §22.5's topology-library reading stands. **No wideband
feasible is claimed.**

**⚠ Corrections to record.**
* §27.6's "the generator still fails" was a **selection** result, not a capability
  one: it drew the 12 *most structurally distinct* pool candidates. Selecting 29
  by the measured predictor instead yields **24/29 band-matched and 1 full gate**.
  Future capability negatives in this program should name their selector.
* The rule "everything that ever closed match+gain has ≥12 devices" (78 graphs,
  no exceptions) was **broken by this session's own 10-device swap mutant**. It
  described which structures had been tried, not the problem.
* Three `2669669e` descendants read `spec.feasible()` True but are **not claimed**:
  `device_remove/46d1ed` (NF 2.24, **K_min 0.87**) and `passive_type_swap/f35dbf`
  (NF 2.19, **K_min 0.872**) are only conditionally stable. That lineage is
  stability-marginal — exactly §27.5's warning.

**Regression quartet green before and after:** vocab **MATCH**, screen
**114/192 (59.4%)**, `pipeline_yield` **40/42 (95.2%)**, `check_ref` **GREEN**,
`calibrate_specs` **ALL MET**. Cost: **~86,000 ngspice evaluations**, 114 L2 rows,
5 GPU sampling arms + 1 GPU fine-tune arm.

**Where to pick up.**
1. **Run the other three dhruva bands and `wifi24` on `80aaf9f4` and `78f5cc9c`.**
   §27.4's winner closed all four; whether a generator topology does is now a
   cheap question and it is the natural next claim.
2. **The archetype library is ~90% gate-driven and is 31% of the training mass.**
   Fixing that means *authoring* source-driven families, which the standing rule
   forbade this session. The measurement is on the record; the decision is the
   user's.
3. **Selection, not conditioning, is the lever that worked.** A critic or screen
   that ranks pool candidates by measured structural predictors (rather than by
   distance from known families) is the obvious follow-on, and it needs no new
   model.
4. `check_stab`'s store-wide re-audit on the new emission (§27's item 1) is still
   open; this session did not touch it.

### ▸ Sub-block: WP-OBSERVE — the pipeline stops discarding the inside of every simulation (owner: the WP-OBSERVE executor)

**Files owned:** `lna/plans2/09-WP-OBSERVE.md` (pre-registered, committed at
`b08dda8` **before** any feature code), `lna/extract.py`, `lna/datastore.py`,
`lna/size.py`, `lna/ref/check_op.py` (new), `.gitignore`, FINDINGS **§30**,
JOURNEY stage **25**, STRUCTURE_LOGIC Blocks 5/6, this sub-block. New table
`lna/data/op_points.jsonl` (append-only, gitignored, in no snapshot). Nothing
frozen touched; `surrogate.py`/`critic_gnn.py` (concurrent agent) not touched.

**What shipped.** Every ngspice evaluation already solved a full DC operating
point and `run_and_extract` kept one scalar out of it. It is now read back
**passively**: per-device `id/gm/gds/gmbs/vgs/vds/vbs/vth/vdsat` + derived region
(MOS), `ic/ib/vbe/vbc/gm/cpi/cmu` (BJT), node voltages, branch currents — via
`print` lines only, **no `save`** (gotcha N1), **no extra ngspice invocation**,
deck byte-identical when capture is off. `size.OpSink` owns the volume policy;
`log_l2_result` harvests the op from the **NF deck that already runs**, which is
how `search.py`/`evolve.py`/`d3_campaign.py`/`nf_campaign.py`/`nf_moves.py`/
`g4_search.py`/`relabel_mf.py` are covered without editing any of them. The
per-element noise budget is attached **by reuse** of `_noise_budget_row`.

| golden (`ref/check_op.py`, joins the regression set) | result |
|---|---|
| captured Id/gm vs an independent bare-`op` probe | **0.0e+00** relative |
| metric vector with probe vs without, `repr` precision | **18/18 identical** |
| noise deck vs sizing deck share a DC solution (never tested before) | **0.0e+00** |
| overhead, end-to-end sizing runs (6-dev / 16-dev) | **−0.80% / −0.70%** (target < 5%) |

**★ First reading of the instrument.** Across six headline designs at their own
stored `best_params`: **11 of 25 MOSFETs (44%) carry milliamps at negative gate
overdrive**, 0 in triode, 0 off; `gm/Id` splits **17–20 V⁻¹ (weak inversion,
gain/input devices)** vs **10–12 V⁻¹ (output stage)**. ⚠ **`bias.saturated`
cannot see this** — in weak inversion BSIM4's `Vdsat` collapses to ~55 mV, so
`|Vds| ≥ 1.5|Vdsat|` passes by 5–8× and the predicate calls all 25 saturated.
"Saturated" in this program's history means *conducting with Vds headroom*.

**⚠ Defect fixed on the way:** `datastore.git_sha()` shelled out per row (~50 ms
on Windows) — measured **+99% overhead** at op-row rates. Memoized per process;
`row_l2`/`row_l1` benefit too.

**Knobs / volume.** `LNA_OP_LOG=0` off; `LNA_OP_SUBSAMPLE` (default **8**) for
inner ZOAF points; `LNA_OP_SUBSAMPLE_PROBE` (default **1** = every evaluation of
a repeat probe, ~0.4 MB/probe — turn it down before a large σ campaign). Row size
**~2.65 kB** at 16 devices vs `sim_points`' 377 B, so at 1/8 the new table grows
*more slowly* (≈331 B/eval) than the one it accompanies.

**⚠ Store note:** 4 demo L2 rows (`gps-l1`; corpus 466 x3 and corpus 467 x1 from
the best-of-k path check, all `provenance.source_arm = "wpobserve-demo"`) plus
their point/op rows were written. `lna/data/topo_labels.jsonl` was left
**uncommitted** — the shared store had another agent appending live, same call as
Session 5.

```bash
python lna/ref/check_op.py              # golden + invariance + deck parity
python lna/ref/check_op.py --overhead   # interleaved 3-arm benchmark
LNA_OP_SUBSAMPLE=0 python lna/size.py ...   # final points only
LNA_OP_LOG=0 python lna/campaign.py ...     # off entirely
```

### ▸ Sub-block: WP-ATTRIB — the no-learning baseline, and the blind spot in NDL / spec-L0 (owner: the WP-ATTRIB executor)

**Files owned:** `lna/grammar_gen.py` (new), `lna/_attrib_pools.py`,
`lna/_attrib_size.py`, `lna/_attrib_report.py`, `lna/_attrib_audit.py`,
`lna/_attrib_sample.py`, `lna/_attrib_gpu_sample.sh`,
`lna/plans2/10-WP-ATTRIB.md`, FINDINGS **§31**, JOURNEY stage **27**, the
Block-3 note in `STRUCTURE_LOGIC.md`, this sub-block. Nothing shared was edited
(`size.py`, `critic_gnn.py`, `surrogate.py`, `extract.py`, `search.py`,
`finetune.py`, the specs and the screen are all untouched). Store recipe
**`attrib-v1`**; snapshot **`v6-attrib`**. Full measured detail in **§31**;
pre-registration committed `ab5e633` before any feature code existed.

**★★★ The headline.** Four arms, 256 samples each, one identical funnel:
**GR** (grammar-only, no learning) · **GR+RAG** (grammar + retrieval) ·
**G2** (upstream `Pretrain.pth`, prefix-12) · **G3** (P5-v7, adopted).

| arm | L0 % | **NDL@256** | copies % | **all-MOS conducting** | qualifying | sized | **near** | **feas** | best S21 |
|---|---|---|---|---|---|---|---|---|---|
| **GR** | **65.6** | **168** | 0.0 | 5 (**3.0%**) | 85 | 10 | **0** | **0** | −0.06 |
| **GR+RAG** | **67.2** | **172** | 0.0 | 7 (4.1%) | 74 | 10 | **0** | **0** | +2.48 |
| G2 | 26.6 | 16 | 45.7 | 35 (51.5%) | 2 | 2 | 0 | 0 | −8.15 |
| **G3** | 65.2 | 63 | 50.0 | **113 (67.7%)** | 9 | 9 | **2** | **1** | **+13.37** |

**A generator with no learning in it beats the adopted checkpoint on BOTH
metrics this program uses to decide what to adopt, and then produces nothing.**
The first stage with discriminative power is the first one that runs ngspice.

**★★ A new `wifi24` TIER-2 FEASIBLE design, from the adopted generator.**
`0da2f0c7b263eee5` (`p5v7_s1337/seq0039`, 10 devices): S11 **−30.68** /
S21 **13.37** / Idd **2.24** / **NF 1.697**; replay 3/3, 10/10 in box,
unconditionally stable in band (K_min 3.03) **and** over 0.1–20 GHz (2.68),
novel vs ref-v3 (nearest `corpus:476`, **0.527**). The program's tier-2 record
goes **2 → 3**, and this is the second whose topology came out of the generator.

**Three things the next session should know.**

1. **The cheap metric repair is measured and is a USER decision.** Reporting the
   **all-MOS-conducting rate** beside NDL in the frozen protocol row costs ~70 s
   per 256-sample pool, needs no new harness, and is the only column that
   separated these four arms. Changing the adoption rule is a frozen-protocol
   change — the §14.5 / §14.6 governance class — so it is proposed, not taken.
2. **The retired uncertainty gate is a working OOD detector.** §20.3 retired
   03-SEARCH §4 rule 2 as inert (2/110 on a live pool). It fires on **73–76%**
   of the no-learning candidates and **0–11%** of the learned ones.
3. **The motif scarcity is a data fact, not a model fact.** Random wiring emits
   the source-driven input at **48.4%**, P5-v7 at **14.4%** — §29.6's mix
   argument, confirmed from the other side. New source-driven *data* is the
   lever; steering is not.

⚠ **Store note.** +26 L2 rows under recipe `attrib-v1`
(`provenance.attrib_arm` ∈ {GR, GR+RAG, G3}); 5 further sizings were `skipped`
by the `(wl_hash, spec)` dedup because G2's and four of G3's picks already
carried a `wifi24` label — expected, because this selector deliberately does not
drop already-sized candidates (that would shrink pools asymmetrically by store
history). `data/topo_labels.jsonl` was committed with three other agents
appending live, so that commit carries their rows too.

⚠ **Sizing-half power, stated.** 31 sizings; Fisher one-sided on near-feasible
is p = 0.077 pooling all no-learning arms against P5-v7. The decisive numbers
are upstream (113/167 vs 5/168 conducting) and qualitative (0 of 22 no-learning
candidates above +2.5 dB of gain).

```bash
python lna/grammar_gen.py --selftest
python lna/grammar_gen.py --arm gr|rag --n 128 --seed 1337 --out DIR
wsl -e bash lna/_attrib_gpu_sample.sh
python lna/_attrib_pools.py --stage gen|bias|pool
"<analoggenie py>" lna/search.py --rank --pool-json lna/out/_at/pool.json --snapshot v6-attrib --out lna/out/_at/rank.json
python lna/_attrib_size.py --rank-json lna/out/_at/rank.json --k 10 --shard 0/2 --out lna/out/_at/sized_a.json
python lna/_attrib_report.py --spec wifi24 --md
python lna/_attrib_audit.py --wl 0da2f0c7b263eee5 --reps 3
```

## Session 8 (2026-08-13) — ★★★ the benchmark restated to SIMULTANEOUS, and Gate D4-SIM closes the same day

**Files owned:** `lna/plans2/14-DHRUVA-SIMUL.md` (new — the standing
benchmark doc, replacing the lost `08-DHRUVA-GOAL.md`), FINDINGS **§35**,
JOURNEY stage **30** + the frontier bullet, `lna/repro/dhruva-best/recreate.py`
(`--cross`, additive) + its README. No store rows written; nothing frozen
touched.

**The user's directive:** record the per-band Dhruva benchmark as MET, and
restate the standing benchmark to *one LNA, one fixed sizing, all
specifications at once*. **Measured the same day: it was already met.** The
4×4 matrix (each shipped `mf2-v1` sizing of `ace8383c` × each band spec) is
**16/16 PASS**; the designated single-LNA point is the **`dhruva-l5` sizing**:
NF **0.867 / 0.995 / 1.196 / 1.253** dB at the S/L1/L2/L5 f0s (limits
3.5/2.7/2.5/2.5), S21 33.7–36.0 dB, S11 −10.001 held 1.1–2.5 GHz, Idd 12.963,
K_min 19.9 in-band / 10.3 wide. Replay fence 3/3 × 4 specs, spread 0.0000.
Why it fell out: the specs always gated S11 *band-wide*, ripple (2.3–4.4 dB)
< gain slack, and the mf2 NF margins absorb the ≤0.8 dB off-tune NF rise —
per-band re-sizing was buying margin, not feasibility (§35.4).

**Gate ladder now:** D0–D4 MET → **D5 (IIP3) is the frontier**, blocked on a
two-tone/HB harness; then D6 (gain programmability), D7 (differential).
Upgrade order in `14-DHRUVA-SIMUL.md` §4: (1) margin-hardening resize — the
S11 margin is **0.001 dB**, the one flimsy number in the headline; (2) an
ngspice two-tone IIP3 prototype (a day, turns D5 into a number); (3) stability
into the polish objective (queued since Session 4); later the VACASK/IHP HB
flow, 3-port differential harness, switchable-DOF search, corner sweeps.

```bash
python lna/repro/dhruva-best/recreate.py --cross   # the 16-cell D4-SIM matrix
```

## Session 9 (2026-08-13) — concurrent agents on `lna-data` (upgrade ladder)

> Same convention as Sessions 5–7: each agent owns a clearly-marked sub-block
> below. Append yours; do not edit another's. Commit only your own files with
> explicit path adds.

### ▸ Sub-block: WP-SENS — the sensitivity sweep on the D4-SIM point (owner: the sensitivity executor)

**Files owned:** `lna/corners.py` (new), FINDINGS **§39**, JOURNEY stage
**34**, this sub-block. **No shared file edited** — temperature is a `.temp`
card appended to the deck body; VDD and inductor Q ride the existing
last-`.param`-wins override (`build_deck` appends params after the body
defaults — the mechanism the shipped flow itself uses for `pVDD`). Results in
`lna/out/_sens_d4sim.json` (gitignored). No store rows written.

**What it is:** a **SENSITIVITY** sweep, not corners — the 45 nm behavioral
include has no process-corner cards. Axes at the fixed `dhruva-l5` sizing of
`ace8383c` (four-band simultaneous gates re-measured per perturbation, the
`recreate.py --cross` protocol): temp −40…85 °C · pVDD ±10% · all R/C/L
globally ±10% (`RQL*` loss tracks its inductor by construction) · inductor Q
8…20 · worst-two-axes combo. Controls: baseline reproduces §35.3 to the
digit; `.temp 27` invariance drift **0.0**.

**Headline (FINDINGS §39):** §35.5 was half right. **S11 flips at ±1%**
(VDD −1%, passives +1%, Q 16, +40 °C) — and **Idd is co-fragile** (0.037 mA
margin: VDD +1%, passives −1%, +40 °C all flip it). **No passing VDD
tolerance exists** at this point. Cold improves everything; **better
inductors FAIL** (Q 16/20 — the match is partly loss-damped and RQL2 carries
DC; Q 8/10 pass with NF margin left). **NF and S21 never flip anywhere**,
combo (85 °C + VDD×1.1) included — NF worst margin +0.504 dB, S21 +1.81 dB.
K_min 17.3–23.2 throughout: stability is not sensitivity-limited.

**Hardening targets measured (for the margin-hardening agent):** nominal
S11_max ≤ **−10.44** · keep NF margin ≥ **0.75 dB** · S21 margin ≥ 1.91 dB ·
Idd headroom **4.52 mA** — the last honestly read as "fixed-voltage `pVB`
bias is the defect": a constant-gm/current-mirror bias DOF (absent from the
vocabulary) is how real parts hold Idd over PVT; 4.5 mA of static headroom is
the price of not having one. Both knife-edges are **by construction**
(`constrained_descent` `keep="s11idd"` pins exactly those two at the gate).
⚠ Adjacent, not acted on: the shipped params carry **pVDD = 1.1 V** while the
spec text says "@ 1.2 V" — a nominal-VDD spec/harness decision for the user
(+9% VDD ≈ +1.9 mA Idd at fixed sizing, per this sweep).

```bash
python lna/corners.py --axis all      # ~120 evals: baseline, 4 axes, combo, report
python lna/corners.py --axis report   # re-print from lna/out/_sens_d4sim.json
```

## 1. TL;DR — what shipped this session

| Plan item | Status | Key result |
|---|---|---|
| **WP-SPEC** (01-SPEC, sched. days 1–2) | ✅ done | `spec.py` + 4 specs + spec-driven screen; legacy reproduction **exact**; in-scope union **94.1%** |
| **H-Q3** floating detector (03-BIAS/misc) | ✅ done | detector built; **1081 re-diagnosed** (not floating — ideal-inductor singularity), fixed by finite-Q |
| **P0** novelty metric (04-GEN §1) | ✅ done | WL-hash whole-corpus metric; **NDL@256 = 16 (wifi24) / 26 (legacy)** at prefix 12 — the frozen baseline |
| **WP-REF day 3** (02-REF §2) | ✅ done | device table + **stage-A CG anchor**; S11 −23.3 dB; **H-Q2 closed** (Re(Zin) 0.1%) |
| **WP-REF day 4** (02-REF §3–4) | ✅ done | **stage-B CS+Cex — F1 FIXED** (S11 −21 dB, S21 +6.7 dB, Ls 1.35 nH); **H-Q1 resolved** |
| **WP-BIAS** (03-BIAS) | ✅ done | `bias.py` R-GATE + monotonic guard; 461 Vgs 14 mV→302 mV; 54% on, **0 made worse** |
| **WP-GEN P0–P2** (04-GEN) | ✅ done | P0 metric; **P2 fine-tune beats baseline NDL@256 16→24**; P1 class-token works |
| **WP-GEN P4** (04-GEN §5) | ✅ done | inductor logit bias measured **weak** (junk past λ≈12) → yields to P5 |
| **WP-SIZE** (05-SIZING) | ◐ loop closes | extract.py+size.py; **anchor re-derivation validates ZOAF**; Gate G4 open |
| WP-GEN P3/P5, WP-SIZE candidates | ⏳ next | not started |

Everything below is committed. `main` is untouched; nothing was pushed.

**Commits (newest first):**
```
e65bc7f WP-REF day 3: device table + stage-A CG anchor (closes H-Q2)
cd7c6f6 P0: complete the 256-sample frozen protocol
8926675 P0: WL-hash novelty metric vs the whole corpus (04-GEN §1)
b562540 H-Q3: floating-subcircuit detector + resolve the 1081 mis-diagnosis
74c8820 WP-SPEC day 2: spec-driven screen + calibration
cfa1721 WP-SPEC day 1: spec.py loader/validator + spec targets
9aae632 Import existing LNA pipeline under version control   <- lna/ was untracked before this
```

---

## 2. New / changed files

```
lna/spec.py                 NEW  spec loader/validator + 3 compiled views (screen/objective/seed_filter)
lna/specs/                  NEW  wifi24, gps-l1, wideband-sdr, legacy-lna5 (+ README)
lna/calibrate_specs.py      NEW  WP-SPEC acceptance runner
lna/ref/device_char.py      NEW  device characterization sweep -> device_tables.csv (+ .png)
lna/ref/ref24_cg.cir        NEW  stage-A common-gate reference (the match anchor)
lna/ref/check_ref.py        NEW  reference regression runner (+ ref_baseline.json)
lna/ref/README.md           NEW  reference-LNA writeup incl. the S21 finding
lna/ref/ref24_csdeg.cir     NEW  stage-B CS+Cex reference (the F1 fix)
lna/bias.py                 NEW  rule-based gate-bias insertion + L1 sweep + --validate
lna/finetune.py             NEW  P1/P2 LNA fine-tune (checkpoint surgery, train, sample) -- WSL GPU
lna/decode.py               NEW  P4 inductor logit bias (targeted to device positions)
lna/extract.py              NEW  L2 metrics from one ngspice run (S11/S21/Idd; NF best-effort)
lna/size.py                 NEW  ZOAF sizing driver + anchor re-derivation (--anchor)
lna/screen.py               MOD  --spec (spec-driven L0 screen); default path byte-unchanged
lna/pipeline_yield.py       MOD  --spec, --inductor-q, --bias; made torch-free (local REPO)
lna/to_spice.py             MOD  inductor_q=/--inductor-q; set_extra()/value_overrides()/opcheck mode
lna/topology.py             MOD  floating_devices()/has_floating_subcircuit (H-Q3)
lna/novelty.py              REWRITE  WL-hash whole-corpus metric + frozen-protocol harness
lna/WORKLOG.md              MOD  R1 (1081), R2 (H-Q2) resolution entries
lna/FINDINGS.md             MOD  §5 P0 re-baseline block
```

---

## 3. Environments (this bit up front — it costs an hour if rediscovered)

Three Pythons, used deliberately:

| use | interpreter | has |
|---|---|---|
| **analysis (default)** | `python` → `C:\Python314\python.exe` | py 3.14, numpy, pyyaml, matplotlib — **torch-free** |
| **vocab guard** | `C:\Users\Devavrat\radioconda\envs\analoggenie\python.exe` | py 3.8, **torch** 2.0.1+cpu, networkx |
| **GPU generation** | WSL `/opt/miniconda/envs/gpu/bin/python` | py, **torch 2.13+cu130, CUDA** (RTX 3050) |

- Almost all analysis (spec/screen/pipeline_yield/novelty/calibrate/device_char/check_ref)
  runs under the **default py 3.14** — I deliberately kept the analysis stack torch- and
  networkx-free (the WL hash is hand-rolled) so it needs no conda env.
- Only `test_vocab_matches_upstream.py` needs torch → run it with the **analoggenie** python.
- **GPU generation must go through PowerShell, not Git Bash** — Git Bash mangles
  `/opt/...` into `C:/Program Files/Git/opt/...` (WORKLOG X10). Repo is `/mnt/c/Users/Devavrat/circuit-repro`
  in WSL. Example that worked (a script is cleaner than inline quoting):
  ```
  # PowerShell, background
  wsl -e bash /mnt/c/.../scratchpad/gen.sh   # each line: <gpu_py> lna/generate.py --device cuda ...
  ```
  `generate.py --seed N` seeds **both** the prefix pool and sampling, so a new seed = an
  independent draw. Batch 32 / 256-token cap on the 4 GB card (batch 64×384 OOMs — F3).
- **ngspice:** `C:\msys64\ucrt64\bin\ngspice_con.exe` (the `_con` build writes stdout; plain
  `ngspice.exe` does not).

---

## 4. Regression — now a QUARTET (run before AND after every WP)

00-OVERVIEW says "trio"; I added `check_ref.py`, making it four. All currently green:

```bash
# 1. vocab guard (needs torch -> analoggenie python)
"C:/Users/Devavrat/radioconda/envs/analoggenie/python.exe" lna/test_vocab_matches_upstream.py   # MATCH
# 2. legacy screen unchanged
python lna/screen.py --corpus --indices 461-492,1081-1090 --per-circuit 5                        # 59.4% (114/192)
# 3. pipeline yield
python lna/pipeline_yield.py --indices 461-492,1081-1090                                          # 40/42 (41/42 with --inductor-q 12)
# 4. reference anchor
python lna/ref/check_ref.py                                                                       # GREEN
# + WP-SPEC acceptance
python lna/calibrate_specs.py                                                                     # ALL ACCEPTANCE CRITERIA MET
```

Ground rules from 00-OVERVIEW still hold: **work on `lna-exec` (or a worktree), commit per
task, never push to `main`.**

---

## 5. Findings & decisions that change the plan (read before resuming)

1. **device_budget widened `[3,12]→[3,16]`** in the three real specs. Measurement (the
   calibration's stated purpose) showed real single-ended corpus LNAs reach 14 devices.
   Documented in each YAML; reversible.
2. **The corpus is multi-class, which refines H-Q4.** Union-over-41 is 78% *not* because the
   criteria are mis-tuned but because the corpus contains classes the three single-ended-MOS
   specs deliberately don't target: 3 differential LNAs (484/485/1087), 3 with no labeled
   output port (472/480/492), 1 broken (1081), + 2 L0-ambiguous inductorless (477/1088).
   Union over the **in-scope class is 94.1%**, non-LNAs pass 0. `calibrate_specs.py` reports
   both. A `differential:true` spec + screen support (a plan stretch item) would lift the 78%.
3. **Index 1081 was mis-diagnosed by the plan.** It is NOT a floating sub-circuit — it is fully
   connected and fails on an *ideal-inductor branch singularity* (`ll4#branch`: node VB1 reached
   only through ideal inductors + a MOS gate). Fix = finite inductor Q (`to_spice.py --inductor-q 12`,
   default off so existing baselines are unchanged); yield 40/42 → 41/42. See WORKLOG R1. The
   floating detector I built is still correct/useful for *generated* islands.
4. **P0 froze the measuring stick.** Whole-corpus WL-hash novelty; **NDL@256 = 16 (wifi24) /
   26 (legacy)** at prefix 12, collapsing at 24. **Adoption rule for every future GEN arm: beat
   NDL@256 at equal-or-better inductor ratio** (FINDINGS §5). `median NN-sim = 1.000` among
   passing samples = heavy copying pressure. The seed-2338 halves live in `lna/out/sweep{P}_s2338/`
   (seq*.txt gitignored, meta.json kept).
5. **Stage-A CG anchor: the plan's `S21 ≥ 8 dB` is unachievable, and that is a real result.**
   S11 = −23.3 dB (Gate G1 ✓) and Re(Zin) matches 1/(gm+gmb) to 0.1% (**H-Q2 closed**). But a
   resistive-load CG into 50 Ω is gain-limited to ~0 dB (VDD headroom caps RL; the 50 Ω port
   caps a matched CG at gm·50≈1), which also pins NF ~4 dB. **Gain/NF need a tuned load →
   stage B.** Full reasoning in `lna/ref/README.md` + WORKLOG R2.
6. **Stage-B (F1 fix) works; H-Q1 does not reproduce.** The Cex recipe gives a realizable match
   (Ls 1.35 nH, Lg 8 nH) with S11 −21 dB and **real gain (S21 +6.7 dB)**. H-Q1's 1122 Ω was an
   artifact of F1's broken peak-fT circuit: the cascode-bypass effect is modest (~5 Ω) and the
   tank-detune effect is nil (Zin stable). See WORKLOG R3. S21 ≥ 12 / NF ≤ 2.5 are the sizer's job.
7. **Harness gap — NF with gain.** `inoise_spectrum` from a *port* source gives a negative NF once
   a stage has gain (the port z0 is not a noisy Rs). NF is left ungated on both ref decks and the
   CG's stored 4.1 dB is a stability reference only. Fix = a proper series-Rs noise source; do it
   in WP-SIZE where NF is finalized.
8. **WP-GEN P2 beats the baseline; P1 works but the inductor ratio regressed.** The plain fine-tune
   (`finetune.py`, bare-VSS sampling) gets **NDL@256 = 24 vs 16 baseline** (+50%) with copies 46%→29%
   — Gate G3's NDL bar cleared. The `<LNA>` class-token arm (P1) generates LNAs from *no seed* (copies
   →37%) but NDL stayed flat. **Not a clean adopt yet:** both dropped the inductor ratio 0.141→~0.10,
   and `median NN-sim = 1.000` shows they recite the 35 training graphs. Next levers are therefore
   **P4 (inductor logit bias, composes on P2 to fix the ratio)** and **P5 (template corpus, breaks the
   memorization ceiling)** — both sampling/data-side, no new training loop. Checkpoints are gitignored
   (198 MB); `finetune.py --arm p1/p2 --do sample` regenerates from them (they exist on disk).
9. **WP-BIAS: gate rules top out at 54% conducting; the plan's next rule is data-chosen.** R-GATE
   biases un-driven gates (461 Vgs 14 mV→302 mV) and a monotonic guard guarantees 0 circuits made
   worse. But only **22/41 (54%)** get all MOS ON at default sizing (34% saturated). The measured
   off-MOS split — **15 source-no-DC-path, 16 drain-no-DC-path, 12 load/sizing** — says the v2
   escalation is R-SOURCE/R-DRAIN rules (03-BIAS R-DIAGNOSE-ONLY, decided by measurement), and the
   saturation gap is WP-SIZE's (unsized loads force triode). `bias.py --validate` reproduces this.
10. **The sizing loop closes and validates itself; the block is the topology, not the sizer.** ZOAF
    (`size.py --anchor`) re-derives the stage-B reference vs `wifi24` in 304 sims, reaching feasibility
    on S11 (−10.9) / Idd (4.2) and driving S21 to 6.86 dB — within 0.16 dB of the hand-tuned 6.7 dB.
    The lone infeasibility (S21 < 12) is the single-stage topology's real gain ceiling (~7 dB, 50 Ω
    output loading), shared by all three specs' 12–15 dB floors. So Gate G4 needs a higher-gain
    topology (output matching), not optimizer work. NF is `unsupported` in the sizer pending the
    harness fix (finding #7).

---

## 6. Where to pick up (in order)

Most of the plan is executed: WP-SPEC, WP-REF, H-Q3, WP-BIAS, WP-GEN P0/P1/P2/P4, and the WP-SIZE
loop all land. **Gate G4** (≥1 novel generated topology sized to full feasibility) is the open
milestone, and it is now blocked on two concrete things, not on missing infrastructure:

**1. A higher-gain topology + candidate sizing (the path to Gate G4).** The anchor re-derivation
proved `size.py` works, but it also showed every spec's S21 floor (12–15 dB) exceeds what the
single-stage reference can do (~7 dB, 50 Ω output loading — finding #10). So: add output impedance
matching (tapped tank / source-follower buffer) to a reference so *some* topology is feasible, then
wire **candidate sizing** — take the top L0+L1 topologies from the P2 arm (best generation), run each
through `bias.insert_bias` → `size.py`, and score. `size.py` currently hardcodes the anchor's param
map in `size_anchor`; generalise `sizable`/`fixed` from a to_spice deck's `p<dev>W/L/V` names (classify
by `topology.base_of`). Turn on `Netlist(inductor_q=12)` for sizing. Fix the NF harness gap (finding
#7) so NF becomes a real constraint rather than `unsupported`.

**2. Generation P5 (breaks the memorization ceiling).** P1/P2 recite the 35 training graphs
(median NN-sim 1.000) and under-produce inductors, and P4 confirmed decoding can't fix the inductor
gap (finding #8). P5 = a `templates.py` archetype generator (CS-degenerated ±Cex, CG ±gm-boost,
resistive-feedback, noise-cancelling × cascode/load/buffer options) → Eulerian-augmented → mixed into
the fine-tune with per-class `<LNA_NB>`/`<LNA_WB>` tokens. ~150–400 labelled topologies; the WL-hash
NDL metric already counts novelty against the *whole* training set (templates included), so it can't
be gamed. This is the lever for both the inductor ratio and the copying ceiling.

**WP-BIAS v2 (when it blocks sizing yield):** the measured off-MOS split (finding #8) says add R-SOURCE
(source with no DC path → reference resistor/current sink) and R-DRAIN (drain with no DC path → load
feed) rules. `bias.py`'s report already classifies every such node; the monotonic guard makes new rules
safe to add. Don't build them speculatively — only if WP-SIZE's conducting denominator is too thin.

---

## 7. ngspice gotchas discovered THIS session (add to your mental X-table)

| # | trap | fix |
|---|---|---|
| N1 | `save @m1[id] …` before `sp` makes S-params/node voltages **disappear** — `save` *restricts* the saved set | don't `save` if you need S-params; single-`op` device params (`@m1[gm]`) are available without `save` (only `.dc` sweeps need pre-`save`, X3) |
| N2 | `wrdata` writes **2N columns** for N vectors — `(xscale, value)` pairs, not N columns | parse odd columns; and give `wrdata` a **Windows** path (ngspice_con is a Windows binary — `/tmp/...` silently fails) |
| N3 | NF came out 92 dB | `inoise_spectrum` is **V/√Hz (amplitude)**, so `NF = 10·log10(inoise²/4kTRs)`; 4kTRs@300K = 8.284e-19 |
| N4 | `meas noise …` → "measure limited to tran/dc/sp/ac" | `meas` can't read a noise plot; index the vector instead (`let nfv=…; nfv[k]` at the f0 grid point) |
| N5 | CG with an ideal source current sink can look under-determined | it solves (device pins Vs through the channel); `.option rshunt=1e12` for safety |

---

## 8. Quick reference — the tools you'll use

```bash
python lna/spec.py --all                                  # validate specs
python lna/spec.py wifi24 --screen-index 461              # screen one corpus circuit
python lna/screen.py --generated "dir/seq*.txt" --spec wifi24
python lna/pipeline_yield.py --generated dir --spec wifi24 [--inductor-q 12]
python lna/novelty.py --eval dir --spec wifi24            # one frozen-protocol row
python lna/novelty.py --rebaseline256 --spec wifi24       # full 256 baseline
python lna/bias.py --index 461 --sweep                    # bias one circuit + L1 sweep
python lna/bias.py --validate                             # WP-BIAS §4 table (~15s)
python lna/pipeline_yield.py --generated dir --bias       # biased+conducting yield
# WSL GPU: python lna/finetune.py --arm p1 --do sample --device cuda --seed 1337 --n 128 --out ...
python lna/calibrate_specs.py                             # WP-SPEC acceptance
python lna/ref/device_char.py --plot                      # device table
python lna/ref/check_ref.py [--update]                    # reference regression
```

Specs live in `lna/specs/`. Reference decks + device table in `lna/ref/`. Generated runs in
`lna/out/` (seq*.txt ignored, meta.json kept). Plans in `.claude/worktrees/lna-plans/lna/plans/`.

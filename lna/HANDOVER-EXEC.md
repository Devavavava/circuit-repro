# Handover — executor session 1 → next

**From:** an Opus 4.8 executor session, 2026-08-06 · **Repo:** `C:\Users\Devavrat\circuit-repro`
· **Branch:** `lna-exec` (7 commits, off `main` @ `535104c`, **never pushed**)

You are picking up execution of the LNA plan set in
`.claude/worktrees/lna-plans/lna/plans/` (start at `00-OVERVIEW.md`). That set is
the roadmap; this file is what has actually been *done*, what was *found*, and
exactly where to resume. Read `WORKLOG.md` (entries R1/R2 are mine) and
`FINDINGS.md` (§5 P0 block is mine) for the measured detail.

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

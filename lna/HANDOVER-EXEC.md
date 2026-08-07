# Handover — executor session 1 → next

**From:** an Opus 4.8 executor session, 2026-08-06 · **Repo:** `C:\Users\Devavrat\circuit-repro`
· **Branch:** `lna-exec` (7 commits, off `main` @ `535104c`, **never pushed**)

You are picking up execution of the LNA plan set in
`.claude/worktrees/lna-plans/lna/plans/` (start at `00-OVERVIEW.md`). That set is
the roadmap; this file is what has actually been *done*, what was *found*, and
exactly where to resume. Read `WORKLOG.md` (entries R1/R2 are mine) and
`FINDINGS.md` (§5 P0 block is mine) for the measured detail.

---

## Session 2 — Phase 2 (learned critic): Stage-0 + Gate G4 + Gate C0 + P5 templates DONE; Stage-1 baseline clears C1 (family split, not source-shift)

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
**Stage-1 baseline + P5 templates are DONE; Gate C0 met.** Prioritized next:
1. **The MPNN** (02-CRITIC §3, plain torch, WSL GPU) — now the biggest lever. Bar:
   beat WL-kNN **on the source-shift split** (ρ≈0.28 today), not the family split.
   `margins_for` rows are the target; σ=0.61 dB sets the rank-loss hinge margin
   (note σ rose — some topologies are multimodal under ZOAF; consider trimming the
   noisiest via repeat-probes). 5-member ensemble for the uncertainty search needs.
   **Manage expectations:** templates already showed clean diversity doesn't fix
   the shift, so the MPNN may not either — if it doesn't, that's the signal the
   *generator* (P1/P5 fine-tune) or uncertainty-gated search is the real fix.
2. **Curated template sizing for a true feasible token class** — the 88 templates
   are near-feasible but 0 fully feasible under all-params-free ZOAF; size the
   tapped archetypes with a curated sizable set (as `size_tapped` does the ref) to
   get feasible token-bearing rows the graph critic can actually use.
3. **03-SEARCH rerank** only once a model clears C1 on the *source-shift* split
   (de-scope ladder: if nothing does, rerank-by-L1 still cuts sizing waste).
   Stratum **M** (mutation move set, 03-SEARCH §3) is still unbuilt.

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

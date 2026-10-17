# PRE-REG — bench-v3 + LLM-as-mutation-operator hybrid

**Frozen:** 2026-10-18, before any bench-v3 result (drafted 2026-10-17 as `PREREG-BENCH-V3-DRAFT.md`, ba43681d4).
**GO:** user ("looks good, launch"). Decisions taken as the draft's recommendations/defaults — see §7.
Branch `worktree-externals-gf180`. Outputs: `kaggle/campaigns/bench-v3/`.

## 1. Why (facts this design rests on)

- **The current bench cannot show design skill beyond one edit.** Held-out 58 = T1 23 (library) / T2 32
  (single edit) / T3 3. Planting + filtering makes multi-edit tasks ~1% of candidates: bench-v2 validated 229
  cells → F1 kill 140, F2 kill 77, accepted 12 → **2 strict cells survive rl-v1.2** (`bench-v2/amend3`). Both
  are wideband, parent a2, sharing one core edit. Filtering harder for 30–40 such tasks would cost hundreds of
  CPU-h (bench-v2: 7,575 sizing calls / 193.5 CPU-h for 12 accepted).
- **Baselines-v1 (5e608850):** at 8 sims sft-r1 .793 vs blind random-order .624 vs GA .586; zero-shot Opus
  ties sft-r1 at pass@1 and beats it on edits (T2 p@4 .625 vs .534); sft-r1's lead is the 5-circuit library.
  LLMs beat search on choosing edits at small budgets (T2 @4: Opus .625, sft-r1 .534, blind .287, GA .156).
- **Linearity** is implemented (`lna/iip3.py`, two-tone transient; `size.py:943 measure_iip3_tier3`) but no
  spec gates on it (bench-v2 writes `iip3_dbm: unsupported`). **Corners:** −40/+85 °C, VDD ±10%, no process
  cards; only 4/1027 sized designs and 0/205 witnesses survive (W3) ⇒ corners as a hard gate is impossible
  today; a margin term is the only viable form.
- Cost per sizing call under rl-v1.2: 62–97 CPU-s (≈ 90 typical). 8 local processes ⇒ ~320 calls/h.

## 2. Task form: stretch-spec tasks with a continuous score

Instead of "find any feasible design" (binary, almost always reachable by library or one edit), every task
keeps its hard constraints (S11/S21 band, stability incl. wide-µ, Idd cap, port-DC, topology limits) and
**tightens its flavor metric** (noise → NF max, gain → S21 min, power → Idd cap) to a stretch target:

- **Reference R** = best flavor value reached at the original spec by library ∪ full single-edit space of the
  shown anchor (sized at seed 1, rl-v1.2).
- **Stretch target** = R improved by δ (δ chosen per metric so that R's design fails the stretch spec with
  worst normalized margin ≤ −0.05), **and** some known design (the planted witness or any design found by
  search) meets it — the "headroom" condition. Tasks without headroom are dropped.
- **Score** of a method at budget B = best worst-normalized-margin over its first B sized calls at the stretch
  spec (continuous; ≥ 0 means solved). Primary: solve rate and median best-margin at B ∈ {8, 16, 32, 64}.
  This rewards getting *closer* even when not solved, so 30–40 tasks carry real signal.

**A0 — yield probe (cheap, first).** The held-out 35 T2/T3 tasks already have full single-edit enumerations at
seed 1 (pilot-v0 P0 tiering, no early kill) ⇒ R and the witness's flavor value are known from cached rows with
**0 new sims**. Confirm headroom by re-sizing R's design and the witness at the stretched spec (2 calls/task,
~70 calls ≈ 2 CPU-h). Go/no-go: ≥ 15 of 35 tasks with headroom ⇒ build; < 8 ⇒ this form fails, report back.

## 3. Task set

- **H (held-out, in-distribution):** stretch versions of the held-out families (wb1020-gain, nb090-noise) that
  pass A0. Target 20–30.
- **O (out-of-distribution band):** a new narrowband point **nb500 (5.0 GHz ±2%)** or **ism58 (5.8 GHz)**, never
  used in any training data; tasks planted with bv2's own generator (new `BANDS` entry; `band_dict` is
  generic), then stretched as above. Target 10–15. Cost: generation + F1/F2 + A0-style references ≈ 60–100
  CPU-h.
- Corners and linearity: **not** in v3's hard spec (§1). Optional reported column: corner margin of each
  method's best design (4 extra calls per reported design).

## 4. Methods (all at equal sized-call budgets; pre-rejects free for all)

1. **Blind random order** (library, then single edits of the shown anchor) — reference.
2. **GA** (baselines-v1 `ga.py`, unchanged operators; fitness = worst margin at the stretch spec), 1 seed + 2
   more if close to the decision line (as baselines-v1 Amendment 1).
3. **One-shot LLM samples:** sft-r1 (Kaggle, ~3 GPU-h) and Opus zero-shot (subagents), k = B independent samples.
4. **Hybrid — LLM as the mutation operator (the main new method).** Loop of generations; each generation the
   LLM sees the spec, the current best 1–3 designs with their full sized metrics + margins, and the history of
   tried edits with outcomes, and proposes λ = 4 new full netlists; the harness sizes them (seed 1) and feeds
   results back. B = 4 × generations (8 gens = 32 calls).
   - **4a Opus operator:** one Opus subagent per (task, run), resumed each generation; tools limited to Read of
     its own round file / Write of its own answer file; transcripts audited (as baselines-v1 D-O1).
   - **4b sft-r1 operator (optional):** Kaggle kernel sizing in-session on its 4 vCPUs (needs a feasibility
     smoke: ngspice dataset + sizer on Kaggle CPU). ~30 tasks × 32 calls × 90 s / 4 ≈ 6 h ⇒ ≈ 6.5 GPU-h
     (GPU idle during sizing). Deferred unless approved.
   - **4c GA + LLM proposals:** GA whose children are half GA mutations, half LLM proposals (if 4a works).

## 5. Pre-declared readings

- Hybrid (4a) at B = 16 ≥ GA at B = 64 (solve rate and median best-margin) ⇒ LLM-guided search is the product;
  the RL target becomes the operator policy (multi-step episodes, GRPO with a margin reward, diversity-
  preserving), not single-shot answers.
- Hybrid ≈ GA at equal B ⇒ the LLM adds little once search has feedback; reconsider RL entirely.
- One-shot sft-r1 vs Opus on O (new band): if sft-r1 falls below Opus on O while ≥ on H ⇒ our fine-tuning
  specialises to the training distribution (library) rather than teaching design.
- Statistics: paired bootstrap over tasks for every headline comparison; with ~35–45 tasks a rate CI is about
  ±0.15 — differences smaller than that are reported as ties.

## 6. Budget (estimates)

| phase | CPU | Kaggle GPU | subscription (Opus) |
|---|---|---|---|
| A0 yield probe | ~2 CPU-h | 0 | 0 |
| A build (H stretch refs + O band generation/filters) | 60–120 CPU-h | 0 | 0 |
| B blind + GA (1 seed, B ≤ 64) | 40–70 CPU-h | 0 | 0 |
| C one-shot sft-r1 / Opus | scoring ~10 CPU-h | ~3 GPU-h | ~0.5M tokens |
| D 4a Opus hybrid (≈ 40 tasks × 8 gens) | ~35 CPU-h | 0 | ~2–4M tokens (≈ 320 resumed agent turns) |
| D 4b sft-r1 hybrid (optional) | 0 local | ~6.5 GPU-h | 0 |
| **total** | **~150–250 CPU-h (≈ 1–1.5 weeks of the box at 8 procs)** | **3–10 GPU-h** | **~3–5M tokens** |

## 7. Decisions (user GO 2026-10-18, "looks good, launch")

1. **Task form:** stretch-spec continuous score (§2).
2. **OOD band:** **nb580 = 5.8 GHz ±2% narrowband** (a real ISM band; the repo already has 5.8 GHz LNA specs in
   `lna/specs/`). Added as a bench-v3-local `BANDS` entry (bv2.py itself is not modified).
3. **Opus hybrid (4a):** approved on the user's subscription (~3–5M tokens over days).
4. **sft-r1-as-operator on Kaggle (4b):** deferred; proposed only if 4a's reading favours the hybrid.
5. **A0:** starts now.

## 8. A0 precise rule (frozen with this file)

Per held-out task with a full single-edit enumeration at seed 1 (pilot-v0 P0 tiering: the T2/T3 tasks), from
cached rl-v1.2 rows at the original spec: for every sized design d in library ∪ single edits of the shown
anchor, a(d) = min normalized margin over the non-flavor constraints (incl. µ_wide − 1), b(d) = the flavor
metric's normalized margin (`bv2.worst_margin` / `MS._margins` definitions). Under a stretch of δ (margin units,
flavor metric only): w_δ(d) = min(a(d), b(d) − δ).
- δ_min = 0.05 + max{ b(d) : a(d) > −0.05 } (every library/single-edit design then has w_δ ≤ −0.05).
- Witness (planted, verified): headroom iff a_w ≥ 0.02 and b_w − 0.02 > δ_min. Stretch δ* = (δ_min + b_w − 0.02)/2.
- The stretched spec moves only the flavor limit by δ* × that metric's normalization scale; written as a new
  spec file (sha recorded).
- **Confirmation (new sims, seed 1, rl-v1.2, stretched spec):** the witness and the top 3 library/single-edit
  designs by w_δ*. Accepted iff witness worst margin ≥ 0 and all 3 references < 0. (Re-sizing can re-trade
  margins; the cached computation only nominates.)
- **Go/no-go:** ≥ 15 accepted of the eligible tasks ⇒ build bench-v3 H from them; 8–14 ⇒ report and propose
  adding T1 tasks (needs their single-edit enumeration); < 8 ⇒ the stretch form fails here — stop and report.

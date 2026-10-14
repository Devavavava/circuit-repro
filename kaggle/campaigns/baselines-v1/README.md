# baselines-v1 — G: GA baseline (kaggle/PREREG-BASELINES-V1.md, b8fbcf20a)

Part O (Opus reference) lives in `opus/` and is documented there; this README covers part G only.

## What was run

`ga.py` (this directory):

- `ga.py run <nproc> [--out DIR] [--tasks ..] [--seeds 1,2,3] [--bmax 64] [--extra-cache ..]` runs one GA per
  (task, GA seed) over the held-out 58 (the keys of `pilot-v0/eval/searchbar.json`). Then it sizes seeds 2 and 3
  for every found design (the confirmation step).
- `ga.py summarize [--out DIR]` writes `ga-summary.json` and `ga-tables.md` (in this directory).

Reused code (imported, not modified):

- **Worker:** pilot-v0's path (`bv2.py worker` → `bench_anchor_prep.smoke_run(tokens, spec, seed, 2500, "bptm45",
  profile="rl-v1.2")`). Spec = `pilot-v0/P1/specs/<task>.yaml`, sha-checked against the eval prompt's `spec_sha`
  and `eval/specs/`.
- **Edit space:** `pv0.f2_cands`. This is the enumeration of `bv2.Pipeline.f2space_build` with the netlist text
  kept. It is applied to the parent's netlist text. On the 5 anchors its round-trip tokens equal the recorded
  `pilot-v0/run/f2space.json` (checked on 40 edits per anchor before the run).
- **Pre-rejects:** `pv0.Runner.pre_reject` (topology limits, structural degeneracy, port-DC pre-filter; 0 calls).
- **Fitness:** `pv0.Runner.margin`, the worst normalized margin including mu_wide − 1.
- **Library and hashing:** `bv2.anchor_data`, `bv2.tokhash`, `proposal.round_trip`.
- **Summaries:** `p1_score.summ`.

Exact-key caches (read-only) come from the same sources pv1_score uses: pilot-v0 run/smoke and AMENDMENT-3
run/smoke raw rl-v1.2 rows, the pilot-v0 P1 score rows, `pilot-v1/score` and `exit-r1/score` (exit-r1/score also
holds the exit-r2 rows). The full run also reads the smoke's own `ga/smoke/results.jsonl`.

Infrastructure:

- **Process cap:** at most 8 sizing workers on the box in total, and 4 while load1 > 22. Other jobs'
  `bv2.py worker` processes are counted from /proc, which covers the Opus scoring that runs alongside.
- **D32 disk robustness:** rows are written through `bv2.SafeAppender`. Nothing launches below 5 GB free on the
  output filesystem or below 1 GB in $TMPDIR. A worker that left no result during disk trouble is re-queued and
  never recorded.
- **Temp files:** $TMPDIR is a job temp directory, never /tmp.
- **Resume:** `results.jsonl` is an exact-key (jid) cache and `runs.jsonl` holds the finished runs. An unfinished
  run is replayed deterministically through the cache, because the GA RNG is seeded per (task, GA seed) and every
  decision depends only on cached results.

Outputs: `ga/<dir>/{results.jsonl, runs.jsonl, meta.jsonl}`. Each `runs.jsonl` row holds every call in budget
order, with its origin (anchor, or parent key + edit descriptions), source (`sized` or `cache:<file>`), seconds
and fitness. It also holds the found design (tokens and netlist text) and the redraw statistics.

## Deviations / interpretations (D-G*)

- **D-G1 Edit draw.** "1 random edit" is uniform over the full E-c enumeration of the parent's netlist: add R/C/L
  on every unordered net pair, or delete any element, in `f2space_build` order. An edit whose child does not
  round-trip is redrawn and counts as one of the ≤ 50 tries. The space keeps bv2's `rt_ok` filter, applied lazily.
  For 2 edits, the second edit is drawn from the enumeration of the once-edited netlist. Only the final child must
  round-trip, be unseen and not be pre-rejected.
- **D-G2 Element names.** bv2's added element is always named `{T}x` (`Rx`, `Cx`, `Lx`). When the parent already
  has that name from an earlier GA add, the new element is named `{T}x2`, `{T}x3`, and so on. Without this,
  proposal.round_trip rejects the duplicate name, which would make a second add of the same type impossible.
  Names do not enter the token sequence (checked).
- **D-G3 Selection.** For (mu+lambda), the parents are the 4 best of all designs sized so far. This is equivalent
  to selecting from parents ∪ children, because fitness is deterministic. Ties go to the earlier call. The size-2
  tournament samples 2 distinct parents uniformly from the mu and keeps the fitter one (tie: the earlier one).
  With a single sized design, that design is the parent.
- **D-G4 Budget order inside a generation.** The lambda = 4 children are drawn sequentially from the run's RNG and
  then sized in parallel. Budget order is slot order. When a child is feasible, its slot index is the
  first-feasible call. The other children of that generation have already been sized: they are recorded but not
  counted, and their seconds are excluded from SPICE-min. The last generation is truncated to B_max − used
  slots.
- **D-G5 Seen set.** "Seen" covers the 5 anchors' token hashes plus every drawn child (sized or pre-rejected). A
  slot that exhausts 50 tries stays empty. A generation with no child stops the run (status `stalled`).
- **D-G6 Unsized results.** A worker result without sizing (res None / n_evals 0) costs 0 calls, as in the search
  bar's sized-call definition. Its fitness is −1e6 and its slot is not refilled. A crashed worker counts as a
  sized, infeasible call with fitness −1e6. (No such row occurred in the tiering's 6400 E-TF1/E-F2 rows.)
- **D-G7 Gen 0.** The anchors go in `rng.shuffle` order (RNG = `random.Random("baselines-v1/ga|<task>|<seed>")`).
  A pre-rejected anchor (a1/a4 under wideband specs: 3 inductors) costs 0 calls and is skipped. The shown anchor is
  sized like any other library anchor; the prereg makes no exception for it.
- **D-G8 Shared calls.** The 3 GA seeds of a task share identical jobs, for example the gen-0 anchors. The job is
  sized once and every run counts it as a call with its recorded seconds, under the cache-reuse rule.
- **D-G9 Confirmation.** A run's found design is "confirmed" when it is feasible at seed 2 or seed 3 (H1's ≥ 2 of
  3 seeds). Feasibility at both seeds is reported too.
- **D-G10 SPICE-min.** SPICE-min is the sum of the recorded `smoke_run` seconds of the counted calls up to and
  including the first feasible call. A cached row contributes its own recorded seconds, measured under that run's
  load.
- **D-G11 Process cap.** The cap is the box total: 8 minus other jobs' sizing workers, which is 4 while the Opus
  scoring runs. The GA itself is unchanged by this.

## Smoke test (2026-10-15)

Command: `ga.py run 8 --out ga/smoke --tasks t2-nb090-noise-0291,t2-wb1020-gain-0128 --seeds 1`. Both tasks are
T2 with blind-bar costs near the T2 median (25.4 and 21.6 calls). It ran with 4 GA workers next to the Opus
scoring's 4. Outputs are in `ga/smoke/` (`ga-tables.md` / `ga-summary.json` there are the smoke summary, not the
deliverable).

The first launch was stopped after about 2 min so the box-aware process cap (D-G11) could be added. It had
recorded only cache-hit rows and no crashed rows; the restart replayed it through the cache.

| task | result | first feasible call | SPICE-min to first | sized calls (cache) | new CPU | redraws |
|---|---|---|---|---|---|---|
| t2-wb1020-gain-0128 | found, gen 2 (`add R VDD-n4` on a gen-1 child) | 11 | 19.2 | 11 (6 cached) | 10.3 min | 14 pre-rejected / 22 draws |
| t2-nb090-noise-0291 | **not found at B = 64** (best fitness −0.108) | — | — | 64 (5 cached) | 120.0 min | 227 pre-rejected / 295 draws |

- **Confirmation:** the 0128 design is feasible at seed 2 and not at seed 3, so it is confirmed (≥ 2 of 3).
- **Cost:** 66 new sized calls, 2.23 CPU-h, 36.7 min wall at 4 processes. Mean 122 s per new call at load1 ≈ 9.
- **Pipeline checks:**
  - Gen-0 anchors were exact-key cache hits (AMENDMENT-3 T-F1 rows).
  - The single edits of the shown anchor hit the pilot-v0 E-F2 rows.
  - Wideband a1/a4 were pre-rejected (0 calls).
  - No crashed or unsized rows.
- **0291:** the shown anchor (a4) has 4 seed-1-feasible single edits out of 126. The GA edited a4 only twice. a4's
  margin of −0.546 ranks 4th of the 5 anchors, so the budget went to a2 (fitness −0.266, 20 children) and to its
  descendants (37 children). The fitness climbed to −0.108 but never reached feasibility. The margin fitness
  steers away from the anchor that holds the single-edit solutions.

### CPU projection for the full run → STOPPED (not launched)

- **Runs that cost ~0 CPU:** 21 of the 23 T1 tasks have a seed-1-feasible anchor (cached gen-0 rows). Their
  3 × 21 = 63 runs end in gen 0.
- **Runs that need the GA:** the other 37 tasks (2 T1 that are solvable only at seed 2, 32 T2, 3 T3) × 3 seeds =
  111 runs.
- **Smoke cost per run:** a run that ends unsolved at B = 64 costs ≈ 120 new CPU-min (≈ 59 new calls × 122 s).
  The solved run cost 10 CPU-min.

Projection for those 111 runs:

| assumption | projected CPU |
|---|---|
| every run solves as fast as 0128 (lower bound) | ≈ 111 × 10 min ≈ 19 CPU-h |
| 30 % unsolved, solved runs at ~16 calls | ≈ 111 × (0.3 × 120 + 0.7 × 30) min ≈ 105 CPU-h |
| every run unsolved (upper bound) | ≈ 111 × 120 min ≈ 220 CPU-h |
| central estimate, 1 of the 2 smoke runs unsolved | ≈ 111 × 65 min ≈ 120 CPU-h |

The central estimate is ≈ 30 h wall at the 4 processes left by the Opus scoring, or ≈ 15 h at 8.

That is far above the ~40 CPU-h ceiling in the task brief, so the full run was **not launched**. It needs a
decision from the user. Options:

- (a) Accept ≈ 100–200 CPU-h.
- (b) Pre-register a smaller B_max (for example 32), or 1 GA seed instead of 3.
- (c) Run the 37 GA-needing tasks for GA seed 1 first (≈ 40–70 CPU-h projected), then decide on seeds 2–3.

`ga.py` is resumable, so the smoke rows are reused by exact key (`--extra-cache ga/smoke/results.jsonl`).

## Part O — Opus frontier reference (RESULT 2026-10-15)

8 Claude Code Opus subagents (user's subscription, no API charges), one per (sample 1–4, task half A/B), 29 tasks
each, exact pilot-v0 held-out prompts. Converted with `opus/opus_convert.py` (live-LLM parse path), scored with
`pv1_score.py` (`opus-2` all3, `opus-4` h1; score dir `opus/score`), summarized by `opus/opus_summarize.py` →
`opus/opus-tables.md`, `opus/opus-summary.json`. Raw answers + plan in `opus/answers/`. No missing rows.

Deviations: **D-O1** prompts were not inlined in the agent call (≈ 900k characters); each agent could Read only
its own prompt files (+ SYSTEM.txt) and Write only its own answer files — the transcript audit confirms this for
all 8 (tools used: Read, Write, the hand-back; s1A also used Edit once on its own answers file). **D-O2** three
answers were skipped in the first pass (s2B 2, s1A 1); the same agent was resumed and asked for exactly those,
written to `answers-part5.txt`. **D-O3** the system prompt was given as a file (SYSTEM.txt) the agent read as its
role instruction, inside Claude Code's own agent system prompt (not a bare API system prompt).

| model | pass@1 | pass@2 | pass@4 | coverage@4 | T1 p@1 / p@4 | T2 p@1 / p@4 | T3 p@4 | 2-sample solved (T1/T2/T3) | validity |
|---|---|---|---|---|---|---|---|---|---|
| Opus (zero-shot) | 0.315 | 0.422 | 0.517 | 30 | 0.326 / 0.435 | **0.336 / 0.625** | 0 | 27 (7/20/0) | 232/232 |
| sft-r1 (samples 1–4) | 0.341 | 0.506 | **0.690** | **40** | **0.500 / 0.957** | 0.258 / 0.563 | 0 | 37 (19/16/2) | 0.98 |

- Paired bootstrap pass@1 (Opus − sft-r1): −0.026, 95% CI [−0.147, +0.095] — no difference at pass@1.
- **Opus never answers with a library anchor (0/232)**; it edits the shown circuit as the prompt literally asks.
  sft-r1's entire lead is T1, i.e. knowledge of this bench's 5-circuit library learned in SFT. On the edit tier
  (T2) zero-shot Opus is better per sample (p@1 .336 vs .258; 2-sample 20 vs 16).
- Reading (pre-declared): Opus pass@4 (.517) < sft-r1 (.690), so not "a cost/size story only"; the gap is the
  bench-specific library (T1) — the second reading applies to T1, while on T2 general design skill (Opus) is
  at least as good as our fine-tuned 14B.

# bench-v3 — stretch-spec benchmark + LLM-as-mutation-operator hybrid

Pre-registered in `kaggle/PREREG-BENCH-V3.md` (frozen 2026-10-18, commit `f56d45e11`; user GO "looks good, launch").
Branch `worktree-externals-gf180`. Every bench-v3 output lives under this directory.

Campaign: every task keeps its hard constraints and **tightens its flavor metric** (noise → NF max, gain → S21 min,
power → Idd cap) to a stretch target that no library or single-edit design reaches but a known design does.
Methods (blind, GA, one-shot LLMs, LLM-as-mutation-operator hybrid) are scored at equal sized-call budgets by the
best worst-normalized margin at the stretch spec (pre-reg §2–§5).

Phases: **A0 yield probe (this README, done)** → A build (H stretch refs + O band nb580) → B/C/D methods.
A0 decides whether A is built (pre-reg §8 go/no-go).

## A0 — yield probe (pre-reg §2 "A0" + §8 "A0 precise rule")

### Result

- **Eligible: 35** (every non-T1 held-out item: 32 T2 + 3 T3 = nb090-noise 16, wb1020-gain 17, wb0824-gain 1,
  wb1020-noise 1).
- **Nominated by the §8 rule: 0** → no confirmation calls under the rule. **Accepted: 0.**
- **Verdict (§8): STOP. 0 < 8 accepted, so the stretch form fails here. Stop and report.**
- Why the rule nominated nothing: it needs the witness's cached non-flavor margin **a_w ≥ 0.02**, and the sizer
  leaves no such slack.
  - Median a_w = 0.0003. Only 1 of the 35 witnesses reaches 0.02 (`t2-nb090-noise-0323`, which then fails the flavor
    condition).
  - The binding non-flavor constraint is wide-µ for 23 witnesses, S11 for 6, Idd for 4, S21 for 1 and NF for 1.
  - The library and single-edit designs show the same thing: the near-feasible reference R has a ≤ 0.0015 on every
    task.
  - Once feasible, the rl-v1.2 sizer optimises the weighted objectives until some other constraint binds. So
    cached rows at the original spec put almost every design's slack into the objectives, and a(d) ≈ 0.
  - The flavor-side condition b_w − 0.02 > δ_min holds for **6 of 35**. It fails for the other 29 because some
    near-feasible single edit already reaches the witness's flavor value.
- **Diagnostic (NOT pre-registered, D-A8; does not change the verdict):** the same computation with the a_w
  condition dropped nominates those 6 tasks. Each was confirmed with 4 new sims (witness + top-3 references) at its
  stretched spec. Result: see `a0/diag/a0-tables.md` and the "Diagnostic result" section below.

Outputs (`a0/`):

| file | content |
|---|---|
| `a0/nominate.json` | per-task inputs and computations: counts, a/b of the witness and of R, δ_min, the headroom reason, the top-10 near-feasible designs by b |
| `a0/a0-tasks.jsonl` | per-task table rows: task, tier, flavor metric, a_w, b_w, δ_min, headroom?, δ*, stretched limit, confirmation, accepted? |
| `a0/a0-summary.json` | counts per tier/family, verdict, CPU |
| `a0/a0-tables.md` | human-readable tables |
| `a0/specs/` | stretched specs of nominated tasks (none under the rule) |
| `a0/diag/` | the D-A8 diagnostic: same files, plus `specs/*-a0d.yaml` (sha256 in `diag/nominate.json`) and `results.jsonl` (24 confirmation rows) |

Code: `a0.py nominate | confirm [nproc] | summarize [--diag]`. Run it through the env wrapper.

**Witnesses are EVAL-ONLY.** `a0.py` reads each witness netlist from its existing file at run time
(`kaggle/train-pool-v2/<task>/witness/witness.net`, or the bench-v2 cell dir for the 2 strict cells) and never
writes it anywhere:
- Outputs carry only token hashes, margins and metrics.
- Worker job files that contain tokens live in the job temp dir (`~/.claude/jobs/7cd7ffc3/tmp/a0/tmp/ga-raw`) and
  are deleted after each call.
- Nothing in `bench-v3/a0/` may be put into any LLM prompt. The stretched spec files are spec content only, so they
  are safe to show.

### Diagnostic result (D-A8: NOT pre-registered, no verdict)

- Run: 6 would-be-nominated tasks × 4 calls = 24 new sized calls. 0.78 CPU-h, 6 min wall, 8 workers, no other
  workers on the box.
- **3 of 6 confirm:** `t2-nb090-noise-0012` (T3), `t2-wb1020-gain-0028` (T2) and `v2b-wb1020-noise-217` (T3).
  Each witness is feasible at the stretched spec and all 3 references fail it.
- **Every confirmed witness passes by a hair:** worst margins 0.0001, 0.0005 and 0.0003.
  - Re-sizing at the stretched spec again spends the slack until a non-flavor constraint binds.
  - So "witness ≥ 0" sits on a knife-edge, and a different seed or budget could flip it.
- **3 of 6 fail.**
  - `t2-nb090-noise-0312` and `-0351`: the witness itself fails after re-sizing (worst −0.128 / −0.766). The NF
    limit was moved to ≈ 1.05 / 0.95 dB.
  - `t2-nb090-noise-0363`: two references become feasible at the stretched spec. These are AC-equivalent edits
    `add C VDD-n4` / `add C VSS-n4`, with worst 0.0000 where −0.109 was predicted.
- **Cached nomination is a poor predictor here.** Re-sizing re-trades margins in both directions, as the pre-reg
  warned.
- **Top-3 references are often duplicates:** AC-equivalent rail edits (`… VDD-x` vs `… VSS-x`) give identical
  metrics. In effect fewer than 3 distinct references were tested on 4 tasks.

### Method (as run)

For every eligible task, all inputs come from cached rl-v1.2 rows at the ORIGINAL task spec, at seed 1 with
2500 evals on bptm45. Nomination costs 0 sims.
1. Designs d = library a1–a5 ∪ every round-trip-valid single edit of the shown anchor
   (`pv0.f2_cands` == bv2 `f2space_build`, as stored in `pilot-v0/run/f2space.json`).
2. a(d) = min normalized margin over the non-flavor constraints and µ_wide − 1. b(d) = the flavor constraint's
   normalized margin. Both use `bv2.worst_margin` → `MS._margins`, with scale `Spec._scale` = max(|limit|, 1).
3. δ_min = 0.05 + max{ b(d) : a(d) > −0.05 }.
4. Headroom iff a_w ≥ 0.02 and b_w − 0.02 > δ_min. Then δ* = (δ_min + b_w − 0.02)/2.
5. Stretched spec = the original with only the flavor limit moved by δ* × scale (see D-A6). References = the top 3
   designs by w_δ*(d) = min(a(d), b(d) − δ*).
6. Confirmation: size the witness and the 3 references at the stretched spec (seed 1, rl-v1.2). Accepted iff the
   witness's worst margin is ≥ 0 and all 3 references are < 0.

### Deviations / interpretations

- **D-A1: eligible set and shown anchor.** "Held-out task with a full single-edit enumeration at seed 1" = every
  item of `pilot-v0/eval/tiers.json` whose tier is not T1: 32 T2 + 3 T3 = 35.
  - The shown anchor is `tiers.json` `shown_anchor`, which is the parent anchor for every non-T1 item.
  - The 2 strict cells' library and a2 single-edit rows are the AMENDMENT-3 rows (`bench-v2/amend3/run/results.jsonl`).
    Their F2 space is the same 178-edit a2 space.
- **D-A2: rows by exact key, sized rows only.** Every design's row is looked up by `bv2.job_id(tokens, spec, 1, 2500,
  "rl-v1.2")` in the raw rl-v1.2 caches (`p1_score.caches()`: pilot-v0 run/smoke, AMENDMENT-3 run/smoke).
  - Coverage is complete: 0 missing rows. 4,116 sized design rows, 1,713 in-process pre-rejects.
  - Per task: wb 110 sized = 3 anchors + 107 edits, 73 pre-rejected; nb (a4) 131 sized; nb090-noise-0012 (a3) 61
    sized. These match tiers.json `f2_n_sized_s1` plus the sized anchors.
  - Pre-rejects are excluded from δ_min and from the references. These are topology limits, structural degeneracy
    and the port-DC pre-filter; such designs are never sized and have no margins.
  - Duplicate token sequences would be counted once; none occurred.
  - P0's seed-2 retries are not used, because the rule says seed 1.
- **D-A3: flavor metric.**
  - noise → `nf_db` (narrowband) / `nf_max_db` (wideband, the band-max NF), constraint side max.
  - gain → `s21_db`, side min. `s21_ripple_db` stays a non-flavor constraint.
  - power → `idd_ma`, side max. No power task is eligible.
  - The code asserts that this metric is each spec's single weight-1.0 objective (`bv2.make_spec` / `FLAVOR_W`),
    so no judgement was needed beyond the family name.
- **D-A4: what a(d) contains.** a(d) covers every supported constraint except the flavor one, including the in-band
  `mu_min` ≥ 1 (scale 1), plus µ_wide − 1 when the row has `mu_min_wide`.
  - `iip3_dbm` is `unsupported` and is skipped, as in `MS._margins`.
  - The binary port-DC requirement is not a normalized margin, so it is not in a(d), by the rule's literal
    definition. This can only raise δ_min, so it is conservative.
  - A constraint whose metric is missing would be skipped (`MS._margins` convention). This occurred 0 times.
- **D-A5: witness row.** The witness tokens come from round-tripping the witness file; the token hash is checked
  against `tiers.json`.
  - The row is its seed-1 rl-v1.2 row at the original spec, found by exact key. For all 35 tasks it equals the
    recorded seed-1 witness jid (`train_amend3.jsonl` `witness`, or the strict cells' `A1`).
  - For 6 tasks the witness is infeasible at seed 1, because it was proved only at seed 2: 0269, 0291, 0350, 0375,
    wb1020-gain-0109 and -0160. The rule is seed 1, so their seed-1 rows are used. All 6 have a_w ≤ 0.0001, and 0109 and 0160 also have b_w < 0.
- **D-A6: stretched limit and scale.** L′ = L − δ*·s for a max constraint and L + δ*·s for a min constraint, with
  s = max(|L|, 1) of the ORIGINAL limit.
  - L′ is rounded to 1e-4 in the stricter direction (bv2's planted-limit precision), so the move is ≥ δ*.
  - The confirmation margins are `MS._margins` of the new spec file, so they use the new limit's own scale
    max(|L′|, 1). A margin's magnitude can differ from b − δ*, but its sign does not, apart from the ≤ 1e-4
    rounding.
  - Each spec file gets name `<task>-a0s` (`-a0d` for the diagnostic) and a description of the move.
  - Each is written with `bv2.write_spec`, which runs the rl-v1 spec checks. Its sha256 and its bv2 content key
    (`spec_sha`) are recorded.
- **D-A7: δ_min sign.** The rule is applied literally even when δ_min < 0. This happens when the only near-feasible
  designs have b < −0.05: in the diagnostic, `t2-nb090-noise-0012` has δ_min = −0.024.
  - δ* stayed positive (0.138) wherever a stretch was written, so no task was relaxed.
  - δ_min undefined (no design with a > −0.05) did not occur.
- **D-A8: diagnostic arm (not pre-registered).** The rule nominated 0 tasks, so it produced no confirmation evidence
  on whether stretch headroom exists.
  - To get that evidence, `a0.py --diag` repeats the computation without a_w ≥ 0.02, nominating iff the witness is
    seed-1 feasible at the original spec and b_w − 0.02 > δ_min.
  - It then runs the same 4-call confirmation, with the same acceptance test, in `a0/diag/`.
  - It is reported separately and **does not change the §8 verdict**. Cost: 24 sized calls.
- **D-A9: confirmation acceptance details.** The worst margin is `pv0.Runner.margin`: `MS._margins` of the
  stretched spec plus µ_wide − 1. That is the definition of "worst margin" used everywhere since pilot-v0.
  - The full feasibility flag, including port-DC, is reported next to it.
  - A design with margin ≥ 0 that is infeasible, or a crashed call, is flagged in the tables. It is not silently
    reinterpreted.
- **D-A10: scheduler.** Confirmation calls run through `baselines-v1/ga.py`'s `Sched` (imported, unmodified):
  - At most 8 sizing workers on the box, counting other jobs' `bv2.py worker` processes from /proc, and 4 while
    load1 > 22.
  - D32 disk robustness through `bv2.SafeAppender`, with no launch below 5 GB free (1 GB in TMPDIR).
  - Exact-key resume through `a0[/diag]/results.jsonl`, plus read-only reuse of earlier rl-v1.2 rows. No reuse was
    possible: the stretched specs are new content.
  - The worker is the pilot-v1 `pv1_score` path: `bv2.py worker` → `bench_anchor_prep.smoke_run(tokens, spec, 1,
    2500, "bptm45", profile="rl-v1.2")`.
  - TMPDIR is `~/.claude/jobs/7cd7ffc3/tmp/a0/tmp`.

# PRE-REG — baselines v1: GA search at equal SPICE budget + Opus frontier reference

**Frozen:** 2026-10-14, before any result. **GO:** user ("Start ga baseline"; "Opus subagents works yes, draw
from my subscription please no extra charges"). **No Kaggle GPU.** GA = local CPU only (≤ 8 processes, 4 while
load1 > 22, D32 disk robustness). Opus reference = Claude Code Opus subagents on the user's subscription (no
API key, no paid API calls). Branch `worktree-externals-gf180`. Outputs: `kaggle/campaigns/baselines-v1/`.

## Why

exit-r1/r2 (95e4b6715): sft-r1 pass@8 .793, pass@1 .353 on the held-out 58; round 2 plateaued. The held-out
bench is constructed so 55/58 tasks are solvable by a library circuit or a single edit of the shown anchor;
sft-r1 ≈ 2× a uniform-random prior over that space. Two missing references decide whether further RL on this
bench is meaningful: (G) a simple verifier-guided search at the same SPICE budget, (O) a frontier LLM.

Common: held-out 58 (`pilot-v0/eval`, split sha 809d4bc7…, tiers T1 23 / T2 32 / T3 3), verifier **rl-v1.2**,
bptm45, 2500 evals; "solved at budget B" = some sized call among the first B is feasible at seed 1 (H1
protocol); every found design confirmed at seeds 2, 3 (reported). Pre-rejected candidates (topology limits,
structural degeneracy, port-DC pre-filter) cost 0 calls for every method (as in the search bar and H1).

## G — GA baseline (mutation-only evolutionary search; no crossover)

Information parity with the model: the task spec, the shown anchor, and the 5 library anchors a1–a5 (the
model learned them in training). No witnesses, tiers, or training data.
- **Gen 0:** the 5 library anchors in a seeded random order (sized one by one; stop at first feasible).
- **Then** (μ+λ), μ = 4, λ = 4: parents = the μ best sized designs by fitness; each child = a parent chosen
  by size-2 tournament + 1 random edit, or 2 random edits with probability 0.5; edit = bv2's single-edit space
  (`f2space_build` E-c space: add R / C / L on any net pair, delete any element) applied to the parent.
  Children that are pre-rejected (free) or already seen (by token hash) are redrawn (≤ 50 tries per slot).
- **Fitness:** pv0's worst normalized margin incl. the wide-µ shortfall (µ_wide − 1) at the task spec, seed 1;
  pre-rejected / unsized = −1e6.
- **Budget:** stop at the first seed-1-feasible design or at **B_max = 64 sized calls**. **3 GA seeds** per
  task (seed ∈ {1,2,3} of the GA's RNG; the sizer seed is always 1).
- Exact-key cache reuse (read-only) of earlier rl-v1.2 rows is allowed; a reused row counts as a call with its
  recorded seconds.
- **Metrics:** solve rate at B ∈ {1, 2, 4, 8, 16, 32, 64} (mean over task × GA seed), per tier; coverage at B
  (tasks solved by ≥ 1 of 3 GA seeds); median SPICE-min and calls to first feasible; confirmation rate.
  Compared with sft-r1 pass@k at k = B (k ≤ 8; one sample = one sized call at most) and with the blind
  random-order search bar (`pilot-v0/eval/searchbar.json`).
- **Reading (pre-declared):** GA solve@8 ≥ sft-r1 pass@8 (.793) ⇒ at equal SPICE budget a simple search
  matches the fine-tuned LLM; this bench cannot show LLM design capability and further RL on it is not
  justified. GA solve@8 < .793 but solve@64 ≥ .95 ⇒ the LLM is a SPICE-budget saver only (report the
  break-even including GPU cost). GA solve@64 well below 1 on T2 ⇒ the bench is harder for search than the
  blind bar suggests (re-examine).

## O — Opus frontier reference

- Model: Claude Opus via Claude Code subagents (`model: opus`), on the user's subscription.
- Prompt: the exact pilot-v0 held-out prompt (`eval/prompts/<task>.json` system + user messages, arm B,
  k = 1, no few-shot), inlined. **No tools except Write** to its own answer file; it must not read the repo.
  Every agent transcript is audited afterwards for tool calls other than that Write; a violating agent's
  answers are discarded and recorded.
- **4 samples per task.** One agent per (sample index, half of the tasks): 8 agents × 29 tasks. Tasks in a
  seeded random order per agent. (Not independent across tasks inside one agent's context — stated caveat.)
- Answers → the gen-dir layout (`s<N>/<task>/edit0.net` = the single fenced netlist block, `results.jsonl`) →
  `pv1_score.py enumerate` + `run 8 h1` (samples 1–4) and `all3` (samples 1–2), as sft-r1.
- **Metrics:** validity, pass@1/2/4, coverage@4, 2-sample solved (T1/T2/T3), vs sft-r1 at the same k.
  Opus thinking is not budget-matched to Qwen's CAP-1024 (stated caveat).
- **Reading:** Opus pass@4 ≥ sft-r1 pass@4 ⇒ our 14B work is a cost/size story, not a capability lead;
  Opus far below ⇒ the bench rewards bench-specific knowledge (the library / edit conventions) more than
  general design skill.

## Order

G first (CPU), O in parallel (no CPU until scoring); O's scoring runs after G or shares the 8-process cap.

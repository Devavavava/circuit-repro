# Day 2

2026-08-28 to 2026-08-31. Phase 3 continues: cross-PDK capability, three
harness defects found and fixed, the goldens-parity ruling adopted, and the
program's **first topology credit**. `main` = phase-3; `LNA` = archive;
`engineer` unchanged. Everything below is on origin/main at 4066401e.

## Implementations

**Cross-PDK sizing fixes** (`lna/size.py`, adapters; c8114a59). Two defects
found from campaign design artifacts, not from any failing gate: (1) the
sizer's inductor kind "L" was mapped to the adapter's pinned MOS channel
length — every foreign-PDK inductor was frozen at 130–280 nH; now maps to the
adapters' `L_ind` box. (2) Gate bias `pVB` was a fixed 0.5 V literal on every
process — below Vth on sky130/gf180, so every design was a dead circuit; on a
foundry PDK it is now sized over a per-adapter `VB` box. bptm45 is untouched
(byte-identical golden, fixed 0.5 kept for comparability with all prior
campaigns).

**sky130 binning fix** (`lna/pdk/sky130.py`; 5b132013). Third defect: fd_pr
BSIM4 models are binned and the bin table ends at W=7 µm for L=0.15; ngspice
bins on the subckt's `w` as given (the `nf` hint never enters bin selection),
and any wider device is a fatal negative-Nfactor abort that kills the whole
deck — 8/12 random sizing points failed, starving CMA-ES into the small-W
corner. The adapter now emits m parallel in-bin units (`w=W/m`,
`m=ceil(W/2µm)`) via ngspice's hierarchical `m=`; validated exact (8 µm via
the fix ≡ 4 × 2 µm units to the last digit). Failures 8/12 → 0/12.

**W-sweep golden** (`lna/ref/check_pdk_wsweep.py`). For every fetched PDK,
every point of a ladder spanning the adapter's full W box must SIMULATE on
the funnel topology. Gates simulatability — the channel every existing gate
missed (device smoke used in-bin widths; funnel golden gates completion and
only prints `fails=`; campaign rows have no sim-failure channel). GREEN 4/4.

**Goldens-parity instrument + package** (`lna/ref/parity_dump.py`,
`kaggle/parity/`). Full-precision golden measurements (both check_ref decks +
one fixed-parameter funnel evaluation), 3 repeats, fingerprinted, with a
`--diff` comparator; a CPU kernel (`circuit-repro-parity-cpu`) runs the
byte-identical instrument on Kaggle.

**Kernel credential redaction** (`kaggle/kernels/loop-gpu/kernel.py`). The
`sh()` echo printed the tokenized clone URL into kernel logs — i.e. the GH
PAT into archivable artifacts. URLs now echo as `://REDACTED@` (verified in
production logs).

**Organized campaign archive** (`kaggle/campaigns/cross-pdk-v0/`). All runs
under era/label-domain dirs — `era-bugged-aa8923be/`, `era-fixed-0b4b497e/`,
`era-binfix-9df8b95a/` — with per-spec requirement-vs-achieved tables and
verdict READMEs. Rows are never pooled across eras or hosts.

## Experiments

1. **Cross-PDK nulls** per era (box): the bugged runs measured the bugs; the
   era-fixed reruns isolated gf180/sky130 verdicts; the era-binfix sky130 run
   confirmed its wall with a healthy environment.
2. **Goldens parity** (box vs Kaggle): same instrument, both hosts.
3. **GPU arm-B ARCH chain** (kernels v17–v19, matched ladder/budgets):
   gf180mcu → ihp_sg13g2 → sky130. Attribution = B-solves-where-A-fails.

## Results

- **Three-defect archaeology**: every failure signature fully explained
  (pinned inductors at the channel-length literal; 0.5 V bias below Vth; bin
  table vs W box). None was physics. Each hid behind the previous one; all
  three were invisible to every gate because the gates check completion, not
  health — the campaign record carries no sim-failure rate, and arm A
  contains no model that could have noticed (arm B's diagnose/reflect never
  see eval failures either; observability fix proposed, awaiting GO).
- **Parity: 34/34 fields bit-exact** between the box and Kaggle's
  independently built ngspice-47 (replay fence 0.0 both sides). **RULED
  ADOPTED (2026-08-29)**: one measurement domain for the pinned recipe;
  Kaggle tags retained; parity re-runs on any recipe change; bptm45 scope.
- **Final cross-PDK matrix (healthy environments)**: bptm45 20/24; ihp
  **23/24 — transfer success, beats the home process** (only the h08 wideband
  wall stands, now a near miss); sky130 0 and gf180 0 — alive, riding the Idd
  budget, walled on gain/NF: physics and/or topology-prior mismatch.
- **FIRST TOPOLOGY CREDIT (2026-08-30)**: on gf180mcu, arm-B arch scored
  **2/24 where the null scored 0/24**: cap-e01-wifi (wl 88dde50b, not in the
  store — single NMOS + PMOS pair + 3 inductors; NF 2.39/3.5, S21 13.3/10,
  S11 −9.8/−8, Idd 11.9/15) and cap-m06-wifi (wl 15b5d521 — minimal
  single-NMOS + R + 3 inductors; NF 2.2/2.2, S21 15.9/15, S11 −14/−12, Idd
  5.3/6). Both are process-appropriate simplifications the 45nm-bred corpus
  lacks; the null's best sat 12+ dB below the gain gates. Caveats recorded:
  both winners are conditionally stable (k_min 0.52/0.33; stability has never
  been a ladder gate for any arm), and arm-B repeatability is unmeasured.
- **Incidents**: (1) GitHub push protection caught the PAT in an archived
  kernel log; user-authorized filter-branch redacted it from all local
  history (0 hits verified) before anything left the box; echo fixed.
  (2) A leftover gated resume job from a prior session raced the rerun chain
  and wrote 10 fixed-code rows into a bugged-era dir — ts-verified, archived
  as `arma-sky130-resume-tail`, both eras uncontaminated.
- **Cost**: ~22.5 GPU-h this week (3 arch legs); box nulls ~8 h each.

## Pending

- **Token rotation (user, due ~2026-08-31)**: rotate the GH PAT, then update
  the `gh_token` file in the `circuit-repro-ghtoken` Kaggle dataset or every
  kernel loses its clone.
- **Selflearn arm on gf180**: reflect corpus now could contain real feasible
  foreign-PDK designs — which record it reads needs a user ruling.
- **K ≥ 1 stability gate**: would need a new pre-registered ladder version;
  might unmake the two credit cells — decide before building on them.
- **Sim-health observability** (proposed, awaiting GO): n_evals/n_sim_fail +
  one verbatim ngspice error line into trajectory/results rows + a sim-health
  stage-rate column, so diagnose/reflect can see environment failure.
- **Arm-B gf180 repeat**: is 2 credit cells stable run-to-run?
- **sky130/gf180 gate calibration**: NF-floor/gain-floor probe (deterministic
  nulls, single-objective) to decide physics vs 45nm-calibrated gates; per-PDK
  gates are a spec change = user ruling.
- **The wideband wall (h08)**: last spec no arm has beaten on any healthy
  process (ihp got NF 3.0/2.5, S21 12.4/16 — close).
- Carried from Day 1: `ft_p5v7_v2.pth` re-transfer (user holds the only
  copy); AnalogGenie re-fetch approval; PA/mixer/balun class campaigns;
  gpt-oss-20b fallback benchmark; Qwen3-8B volume tier; FT decision via
  k-shot proxy; foreign-PDK parity section if Kaggle rows ever head for a
  store.

## Session dos and don'ts (for the next session, no extra briefing needed)

DO:
- `source env.sh` before anything; goldens (`check_ref`, `check_pdk`,
  `check_pdk_funnel`, `check_pdk_wsweep`) before AND after every landing.
- Make repo edits in a worktree, then merge to local main. A fresh worktree
  bases on origin/main — `git merge --ff-only main` FIRST or you edit stale
  code.
- When testing from a worktree, `export LNA_DEPS_ROOT=<worktree>` — drivers
  prefer `$LNA_DEPS_ROOT` on sys.path and will silently run the main
  checkout's modules otherwise (cost us hours on 08-28).
- Keep all scratch/staging in the job tmp dir, NEVER under the repo tree
  (binding rule, `kaggle/INCIDENT-2026-08-27-SPARSE.md`).
- `grep -r "github_pat_\|x-access-token:" <files>` before committing ANY log
  or output artifact (push protection caught a live PAT on 08-29).
- Tag every campaign artifact with pdk + host + code era; archive under
  `kaggle/campaigns/<campaign>/era-<tag>-<commit>/`; never pool across eras,
  hosts, or (per the parity ruling) outside the pinned Kaggle recipe.
- `ps aux | grep campaign` for leftover background jobs from earlier sessions
  before launching gated chains (one raced us on 08-28).
- Verify claims from design artifacts (params/metrics JSONs), not summary
  counts — all three harness bugs were found that way, and worst_margin
  labels mislead when circuits are dead.
- Kaggle: debug on CPU sessions, GPU only for pre-validated runs; kernel
  defaults live in the PUSHED tmp copy (the repo copy keeps smoke defaults);
  check remaining GPU quota before chaining multi-leg runs.
- Pre-register campaigns; run the null first; queue user rulings for spec
  changes, new arms, designations, budget widenings.

DON'T:
- No installs on the box without per-instance permission; nothing outside
  the repo tree; never `git sparse-checkout`/`clean`/repo-reconfig.
- No `git push` to origin without the user's explicit per-instance wording
  (the permission classifier requires it verbatim, not a "yes" to a list).
- No history rewrites without explicit user authorization.
- Never inject domain guidance into the system (standing principle,
  2026-08-27): no hand-authored playbook entries, no technique hints derived
  from reading its results. The sanctioned channels are architecture changes
  and commissioned experiments; self-reflection is the only learning path.
- Don't treat green completion gates as environment health — check `fails=`
  counts in the funnel golden and run `check_pdk_wsweep`; campaign rows do
  not carry sim-failure rates (until the observability change lands).
- Subagents always opus/sonnet with an explicit model override, never fable.
- Never merge engineer → main; `lna/` changes land on main first, then
  main → engineer.

# Day 1

2026-08-26 to 2026-08-28. Phase 3: the reasoning loop. `main` is this program; `LNA` is the archived prior line; `engineer` is unchanged.

## Implementations

**Cloud worker (Kaggle free tier).** Four kernels driven from this box by CLI: `setup-cpu` (bootstrap + acceptance gate), `import-weights` (GGUF download, sha256-verified), `build-llamacpp` (CUDA server build), `loop-gpu` (the loop). Caches as private datasets: ngspice-47 build, llama.cpp sm75 build, Qwen3-30B / gpt-oss-20b / Qwen3-8B weights, three PDKs. GPU sessions run only pre-validated code; all debug happens on free CPU sessions. Acceptance gate = goldens + an end-to-end spec solve, run in-session before any work.

**Reasoning loop** (`kaggle/loop/driver.py`). Qwen3-30B-A3B (Q4_K_M, llama.cpp on 2xT4) proposes circuit netlists; the deterministic funnel parses, round-trips to tokens, screens (L0), inserts bias (L1), sizes (CMA-ES on ngspice, L2), and measures. Measured margins feed one diagnose-edit round. Every phase logs a trajectory row with verbatim evidence. Each proposal carries predicted metric deltas; predictions are scored against measurement.

**Campaign runner** (`kaggle/loop/campaign.py`). A 24-spec LNA ladder (easy/medium/hard x 5 bands, 2 wideband), fixed budgets, one escalation on failure, per-spec checkpointing, best design saved per spec. Arms share all code; only the candidate source differs.

**Verify instrument** (`kaggle/loop/verify.py`). At every best design: two-tone IIP3 (~22 s), band-wide S-parameters, K/mu stability, S12. Advisory, never gated.

**Class harnesses** (goldens against closed-form truth): PA — P1dB/Psat/PAE (golden within 0.06 dB); mixer — conversion gain, LO feedthrough, IF-referred IIP3 (within 0.005 dBm); balun — Sds21, CMRR, amplitude/phase imbalance (exact). `spec.py` gains `circuit_class`. Mixer noise and phase noise are out of scope: ngspice has no PSS/pnoise.

**PDK layer** (`lna/pdk/`). Adapter interface; `pdk:` in the spec, `--pdk` override. bptm45 default emits byte-identical decks (golden-proven). sky130, gf180mcu, ihp-sg13g2 fetched and activated; IHP PSP models compiled to OSDI with OpenVAF; OSDI loads via a control-driver deck (single-deck loading cannot work). Per-PDK funnel golden: bias -> emission -> sizing -> extract completes on all four.

**Reflect stage** (`kaggle/loop/reflect.py`). The model reads its own campaign record and writes its own playbook entries. Entries are rejected unless every evidence quote appears verbatim in what the model was shown. Accepted entries go to an overlay store that consult retrieves. Content-neutral scaffolding; no human- or Claude-authored domain guidance anywhere (standing principle, user ruling 2026-08-27).

**Governance.** Pre-registration before every campaign. Gitignored runtime dependencies vendored into git after a clone-completeness failure. One incident (a fetch agent's `git sparse-checkout` hit the main repo; tracked content fully recovered; binding scratch-directory rules recorded in `kaggle/INCIDENT-2026-08-27-SPARSE.md`).

## Experiments

1. **Loop smoke** (wifi24, k=2): does the full chain work live?
2. **capability-v0**: arm A = sizing-only null (stored corpus topologies + CMA-ES, no LLM, on this box); arm B = the loop (GPU). Same ladder, matched budgets. Attribution: B solves where A fails = topology credit.
3. **capability-v1**: arm 1 = v0 repeat (noise floor); arm 2 = architecture only (triage-then-concentrate sizing budget + self-generated proposal diversity); arm 3 = arm 2 + reflect-first self-learning. Arm 2 is the cold control for arm 3.
4. **Cross-PDK** (in flight): same ladder on sky130 / gf180mcu / ihp-sg13g2, arms A and B-arch. Overfit test: differential collapse of stage rates (parse -> screen -> conducts -> sizes -> feasible) on foreign PDKs means the setup is fit to bptm45; proportional degradation means process physics.

## Results

- **Smoke**: the model proposed a textbook inductively-degenerated CS LNA; NF met its gate (2.05 vs 2.5 dB); the edit's S11 prediction was directionally correct; the loop kept the better design. Chain proven.
- **capability-v0**: arm A **20/24**, arm B **10/24**, zero topology-credit cells. The null won. B's 14 failures: 9 bind on Idd (down to 0.013 normalized), 4 on S11, 1 on NF. Four specs failed both arms after escalation: both wideband, tight-900MHz, tight-GPS — genuine topology walls, banked as future targets.
- **capability-v1**: 8 / 11 / 11 / **12** (repeat / arch / arch-equivalent / self-learning). Noise band ±2. Arm 3 wrote **12 admission-passing rules from its own record** — including `idd-ma-margin-ignorance` and `idd-ma-bias-regulation`: it found its own Idd-blindness without being told. Net +1 over arm 2 (won two specs, one of them Idd-bound H-tier; lost one) — directionally positive, mechanistically consistent, **within noise**. Reflection needed three attempts; both failures were harness bugs (context overflow; a serialization mismatch that rejected all 17 of the model's correctly-quoted entries), not model failures.
- **PDK bring-up**: all four PDKs complete the funnel. At default bias values the foreign PDKs show zero conduction on the bring-up topology — an early hint of bptm45-fit bias assumptions, to be measured properly by the campaign.
- **Cost**: whole program so far ~18 GPU-hours of a 30 h/week free quota. ngspice builds in 298 s on Kaggle; cached thereafter.

## Pending experiments

- **Cross-PDK campaign**: sky130 GPU run in flight; gf180mcu and ihp-sg13g2 chained; three box-side sizing nulls in flight. Deliverable: per-PDK capability table + stage-rate matrix + overfit verdict.
- **Self-learning delta**: repeat arm 3 (or enlarge the ladder) to separate the +1 from noise. Then iterate: arm 3's record becomes the next reflection corpus.
- **The four walls**: self-learning attack on the both-arm failures; if they hold, the architectural response is a literature-search tool the model can query, or a larger model tier.
- **New circuit classes**: PA, mixer, balun-LNA campaigns on the new harnesses (example specs exist; class-specific L0 screens not yet built).
- **Deferred builds**: P1dB harness (documented, ~6-10 transients), IHP HBT emission path, gpt-oss-20b fallback benchmark, Qwen3-8B volume tier, fine-tune decision via the k-shot in-context proxy.
- **Housekeeping**: re-transfer `ft_p5v7_v2.pth` (user holds the only copy); approval to re-fetch the deleted public AnalogGenie files; goldens-parity ruling before any Kaggle-produced label row enters the store.

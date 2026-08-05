# LNA plan set — answers to HANDOVER-FABLE and the execution plan

**From:** Fable 5 session, 2026-08-05 · **Answers:** [HANDOVER-FABLE.md](../HANDOVER-FABLE.md) §3, §4, §6
· **Executor:** an Opus session (or several), one work package at a time

This directory is the deliverable the handover asked for: a plan, not code. It is
written so that each numbered file is an independently executable work package
(WP) with tasks, acceptance criteria, cost estimates for the RTX 3050 / one
Windows box, and fallbacks. Roughly three weeks of work at a sustainable pace.

| File | Work package | Answers |
|---|---|---|
| [01-SPEC.md](01-SPEC.md) + [specs/](specs/) | spec format, spec-driven screen | §4 (all five questions), H-Q4 |
| [02-REFERENCE-LNA.md](02-REFERENCE-LNA.md) | known-good reference LNA | H-Q1, H-Q2, F1, §4 Q5 |
| [03-BIAS-INSERTION.md](03-BIAS-INSERTION.md) | rule-based bias insertion | §1 item 2, §6 item 4 |
| [04-GENERATION.md](04-GENERATION.md) | ranked generation improvements | §3 (all four bullets), §6 items 2–3 |
| [05-SIZING.md](05-SIZING.md) | ZOAF sizing loop | §1 item 3 |
| [06-SCHEDULE.md](06-SCHEDULE.md) | day-by-day sequencing and gates | §6 checklist |

---

## The four §6 answers, in brief

**1. Specification format.** A YAML spec (schema and rationale in 01-SPEC.md)
whose key property is that it *compiles* into three separable artifacts: an
unsized structural screen (replacing the hard-coded 5-criterion screen), a
sized evaluation objective for ZOAF, and a seed-selection rule for conditioned
generation. Hard constraints and soft objectives are separate sections, never
mixed into one scalar until the last moment, and then only feasibility-first.
Three worked reference specs ship with it: **WiFi 2.4 GHz** (`wifi24`),
**GPS L1 1.575 GHz** (`gps-l1`), and a **wideband 0.5–3 GHz SDR front end**
(`wideband-sdr`). The third is deliberately inductorless-friendly — it exercises
the 40% of real LNAs the current screen rejects, which resolves H-Q4: the screen
was never wrong, it was *unconditional*, and it becomes spec-conditional.

**2. Representation and checkpoint: keep, with one structural addition.**
The Eulerian-path representation and the pretrained checkpoint have earned
their place: 0% → 40.6% steering for free, 92% of screened candidates simulate,
and reconstruction is exact. Every alternative (graph diffusion, GraphRNN-style
generators, GFlowNets) means abandoning a pretrain over 3,351 circuits to train
from scratch against **41 underlying LNA graphs** on a 4 GB card — a bad trade.
The genuine defects of the representation (no conditioning channel, unbounded
length, seed-copying under prefix conditioning) all have cheaper fixes *inside*
the representation, the most important being a **class-conditioning token**
(04-GENERATION P1) that replaces the prefix hack with an honest conditioning
channel. Full argument and a revisit-trigger in 04-GENERATION §5.

**3. Ranked generation proposals** — details, costs, and measurement in
04-GENERATION. Order:

| # | Proposal | Cost | Attacks |
|---|---|---|---|
| P0 | WL-hash novelty metric vs whole corpus | ~1 day | evaluation integrity (do first) |
| P1 | class-token conditional fine-tune | ~1 day + <1 h GPU | novelty ceiling at the root |
| P2 | plain LNA fine-tune with replay + holdout | ~1 day + <1 h GPU | the baseline to beat |
| P3 | anti-copy decoding (seed-aware n-gram block) | ~1 day, sampling only | novelty ceiling, no training |
| P4 | inductor logit bias / grammar-masked decode | 1–2 days | the inductor gap directly |
| P5 | archetype template corpus (synthesis) | 3–4 days | "is 41 circuits enough" — no |
| P6 | KV cache | deferred | throughput only, not a bottleneck |

**4. Bias insertion: rule-based, minimal, measured — and it is the critical
path.** Position argued in 03-BIAS-INSERTION: gate-bias insertion via DC-path
analysis on the reconstructed graph, one `.param` bias voltage per inserted
net, bias devices name-tagged and excluded from screen/novelty fingerprints.
Template recognition is the fallback if rules underperform; co-generation
(retraining with bias vocabulary) is rejected on cost. Nothing downstream of
generation can be scored until this lands, which is why it is week 1, not
week 2.

## Positions on the carried-over open questions

* **H-Q1 (unexplained Zin).** Most probable cause is *not* only the tank
  hypothesis: a cascode whose gate is not AC-grounded does not isolate Cgd,
  and the F1 decks had bias problems throughout. The reference-LNA bring-up in
  02-REFERENCE-LNA is staged so that the tank-detune test and the
  cascode-bypass test both happen as a side effect of building the reference.
* **H-Q2 (no reference LNA).** F1 failed because it tried to match at peak fT,
  where the required degeneration inductance (12–27 pH) is unbuildable. The
  fix is to stop fighting the process: lower the *effective* fT with an
  explicit gate–source capacitor (Cex) so the match sets Ls ≈ 1 nH, or match
  with a common-gate stage where Zin ≈ 1/gm needs no inductor at all.
  Worked numbers in 02-REFERENCE-LNA §3.
* **H-Q3 (index 1081).** A floating-subcircuit detector (connected-component
  check over devices) belongs in `topology.py`; flag and skip, do not fix.
  Half-day task, listed in 06-SCHEDULE misc.
* **H-Q4 (screen ceiling).** Resolved by construction under the spec-driven
  screen — see 01-SPEC §4. The 59.4% ceiling was an artifact of one screen
  serving all targets.

## Ground rules for the executing session

1. **Run the regression trio before and after every WP** (~2 min total):
   ```bash
   python lna/test_vocab_matches_upstream.py
   python lna/screen.py --corpus --indices 461-492,1081-1090 --per-circuit 5
   python lna/pipeline_yield.py --indices 461-492,1081-1090
   ```
2. **GPU work runs in WSL** (`/opt/miniconda/envs/gpu/bin/python`), analysis on
   Windows. Batch 32, 256-token cap on the 4 GB card — batch 64 × 384 faults.
3. **ngspice is `C:\msys64\ucrt64\bin\ngspice_con.exe`**, and the X1–X10 trap
   table in [WORKLOG.md](../WORKLOG.md) is required reading before touching a
   netlist. `ln`/`Ln` and case-insensitive params are silent failure modes.
4. **Fixed evaluation protocol** (04-GENERATION §1) for any generation change:
   256 samples, fixed seeds, report spec-pass rate, novel-distinct count, and
   inductor stats. No proposal is adopted on a vibe.
5. Work in a worktree; commit per task; never push to main.

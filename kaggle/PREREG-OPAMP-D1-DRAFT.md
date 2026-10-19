# DRAFT (not frozen) — opamp D1: combined-requirement depth test

**Status:** DRAFT for user review, 2026-10-18 (user: "draft D1"). Written while D0 runs; it does not depend on D0's
numbers and must not be edited in response to them except where §7 lists an explicit D0-dependent choice.
Code would live in `kaggle/campaigns/opamp-v0/` (stage d1/), reusing the opamp-v0 verifier (Stage 1 gates
V1–V5 PASS; stability gate D-O16 adopted, PREREG-OPAMP-V0-D0 Amendment 1).

## 1. Why D1 (lessons from Stage 2, before D0's verdict)

- The F1 library already contains the textbook multi-stage answers (three-stage NMC, folded and telescopic
  cascodes). A task that needs **one** hard property (R1 gain, R23 large load, R4 input range) is answered by
  **retrieving** one of them. Stage 2 preview: the library NMC beats the AFFC witness on R23 (−20%) and reaches
  89.7 dB at one seed on R1; W-R4 clears the two-stage by only 0.13 V on R4.
- Real design depth = **combining** remedies no single textbook circuit carries together (the scoping doc's own
  rule: witnesses must combine 2–3 of R1–R6), so retrieval alone cannot answer.
- The R4 metric is too lenient: a plain NMOS pair scores ~0.83–0.86 V because only gain/tracking are checked
  across the range, while UGF collapses unnoticed.

## 2. Verifier additions (validated before use, like Stage 1's gates)

- **Strict ICMR (`icmr_strict_v`):** at 9 evenly spaced input common-mode points across [0, VDD], measure gain,
  UGF and PM in the follower fixture; ICMR_strict = the widest contiguous range where gain ≥ mid − 3 dB, UGF ≥
  0.7 × mid UGF, PM ≥ the spec's PM limit, and output tracking ≤ 20 mV. Evaluated in the sizing loop only on
  otherwise-feasible points (as D-O16) and always on the final result.
- **Large-signal slew (`slew_ls_vus`):** 20–80% of a 0.5 V follower step, both edges, the slower one; and a
  static-power-normalised figure `slew_eff = slew_ls × CL / Idd` (V/µs·pF/mA).
- **Gates before D1:** G1 determinism (3 processes); G2 a plain NMOS-pair two-stage scores a strict ICMR clearly
  below its lenient R4 value (the leniency is closed); G3 a complementary-input design scores ≥ 0.25 V more
  strict ICMR than the NMOS-pair two-stage at equal Idd; G4 a class-A two-stage's `slew_eff` matches I_tail/Cc
  theory within 20%.

## 3. Tasks: 4 combined requirements (single-ended, bptm45, VDD 1.1 V, CL 2 pF unless noted)

| task | requirements (all hard) | combined remedy (witness) |
|---|---|---|
| **C1** R1+R4 | gain ≥ 75 dB, swing ≥ 0.6 Vpp, strict ICMR ≥ 0.8 V, UGF ≥ 5 MHz, PM ≥ 60°, Idd ≤ 250 µA | complementary N+P input + folded-cascode summing + CS output, Miller + Rz |
| **C2** R23+R4 | CL 200 pF, gain ≥ 75 dB, GBW·CL/Idd ≥ F₀, strict ICMR ≥ 0.7 V, PM ≥ 55°, Idd ≤ 300 µA | complementary input + three-stage active-feedback (AFFC) |
| **C3** R1+R6 | gain ≥ 75 dB, swing ≥ 0.6 Vpp, `slew_eff` ≥ S₀, UGF ≥ 5 MHz, PM ≥ 60°, Idd ≤ 150 µA | cascoded first stage + class-AB output stage |
| **C4** R4+R6 | strict ICMR ≥ 0.8 V, `slew_eff` ≥ S₀, gain ≥ 50 dB, UGF ≥ 5 MHz, PM ≥ 60°, Idd ≤ 150 µA | complementary input + class-AB output |

F₀ and S₀ are fixed in the freeze from the Stage 2 / D-gate measurements as **1.5 × the best single-regime library
value** (so neither the NMC nor a class-A design meets them by construction of the target, not by tuning on
the witness). Anchors shown to the model: 5T OTA and two-stage Miller + Rz, as D0.

## 4. References ("what retrieval or one edit can give")

**R-set** = F1 library (5) ∪ the single-regime witnesses W-R1, W-R23, W-R4 (now treated as known textbook designs)
∪ the widened single edits (F2′) of the **two best R-set circuits per task** (ranked by the screen below).

## 5. Procedure (score = worst normalized margin at the task spec — the sizer's own margin objective, so no
slack is read from a run that optimised something else)

1. **Witness build + feasibility:** the 4 combined witnesses (EVAL-ONLY), each sized at the task spec, seeds 1–3,
   2,500 evals; if infeasible at all 3, budget ladder 10,000 evals (recorded); still infeasible ⇒ task dropped.
2. **Screen:** every R-set circuit and each F2′ candidate at 300 evals seed 1 (margin mode); the top 20 by worst
   margin + all named R-set circuits re-run at 2,500 evals × seeds 1–3.
3. **Budget robustness:** the top 3 references re-run at **10,000 evals × seeds 1–3** (the witness gets the same
   budget it used), so a sizer that is merely slow on big circuits is not misread as depth.
4. **Accept** a task iff witness feasible at ≥ 2/3 seeds AND every reference infeasible at every seed and budget
   with worst margin ≤ −0.05.
5. **Two-edit check:** 500 random two-edit designs from each of the 2 best references (seeded), screened at 300
   evals, top 10 at 2,500 × seed 1; any feasible ⇒ task labelled **"≤ 2 edits from a known design"**.
6. **Verdict:** **GO** iff ≥ 3 of 4 tasks accepted AND ≥ 2 of them not "≤ 2 edits"; **STOP** iff ≤ 1 accepted;
   else discuss. Also report the analytic ceilings and per-seed spreads beside every number.

## 5b. Additions from the D0 result (D0 = STOP, 0/6; `opamp-v0` README "Stage 3 — D0 RESULT", 20955be83)

These are the D0-dependent changes §7 anticipated, plus two verifier issues D0 exposed.
**User ruling 2026-10-19 ("approved both"): the robustness gate (1) and the determinism fix (2) are adopted.**
They are built and validated (and the pre-D1 diagnostic run) before D1 is frozen; their parameters may be
calibrated in that step only against D0's existing designs, never against D1 results, and any calibration is
disclosed in the freeze.

1. **Robustness gate (closes the single-transistor bias-feedback designs).** In D0 one added transistor on the
   two-stage anchor (mostly feeding back through the IREF/bias network, apparently positive feedback) matched or
   beat every witness: 80–87 dB on R1, beat W-R23 on FOM and W-R4 on ICMR. Such designs are typically fragile and
   the verifier never tests that. Proposed gate on every final result (and in-loop on otherwise-feasible points,
   like D-O16): the design must stay feasible at VDD ±10 %, −40/+125 °C, and ±10 mV `delvto` mismatch on each
   matched pair (5–7 corner evaluations). **Pre-D1 diagnostic (no verdict, ~0.5 CPU-h):** run this gate on D0's
   top single-edit designs and on the witnesses, to see whether it separates them before the gate is frozen.
2. **Determinism under load.** D0 found a 60 s wall-clock ngspice timeout that fires under box load and changes the
   CMA-ES path (R23 NMC seed 1: 6,802 in D0 vs 18,146 alone; 41/7,965 jobs had a simulation failure). Fix before
   D1: a CPU-time (not wall-clock) limit, or retry-once-on-timeout with the same inputs; re-run gate V1 under an
   artificially loaded box.
3. **Seeds:** §7(b) is triggered — sizer spread decided D0's only passing gap (NMC R1 max:gain 58.5 / 89.7 /
   infeasible). Use **5 seeds** for every frontier and confirmation run, and the 10,000-eval budget-robustness step
   of §5.3 for the top references.

## 6. If GO: what comes next (not part of D1)

bench-op-v1 = many specs around C1–C4 (spec grid × anchors), tiered like bench-v2 (library / single-edit / deep),
then the baselines-v1 suite (blind, GA, Opus one-shot, Opus-as-operator hybrid, Qwen) on it — the comparison the
LNA bench could not support.

## 7. Budget and open choices (to settle at freeze)

- CPU ≈ 4 tasks × (8 named refs × 3 seeds × 2,500 + 2 × ~1,000 F2′ × 300 + 1,000 two-edit × 300 + top-3 × 3 × 10,000)
  evals ≈ 25–40 CPU-h with the strict-ICMR and stability gates (~2–3× per gated evaluation); engineering ≈ 3–5 days
  (metrics + gates, 4 witnesses). Local CPU only; Opus agents on the subscription.
- Open: (a) keep the R-set's single-regime witnesses (recommended: yes — they are what an informed designer
  retrieves); (b) D0-dependent: if D0 shows the sizer spread deciding outcomes, raise the default to 5 seeds;
  (c) F₀/S₀ factor 1.5× (recommended) vs 1.3×.

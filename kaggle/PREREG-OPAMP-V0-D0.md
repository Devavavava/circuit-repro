# PRE-REG — opamp-v0 verifier + D0 depth test (go/no-go for an op-amp benchmark)

**Frozen:** 2026-10-18, before any opamp-v0 result. **GO:** user ("im fine with op-amps"; "go ahead" for the
pre-registration and build). Basis: `kaggle/SCOPING-CIRCUIT-CLASS.md` (1ca5b735f). Local CPU only; no Kaggle;
no paid API (agents on the user's subscription). Branch `worktree-externals-gf180`.
Outputs and **all code: `kaggle/campaigns/opamp-v0/`** (campaign-local; no change to `lna/`, `kaggle/*.py` or
other campaigns until D0 says GO — then a shared-core landing goes to main first with goldens green, per the
repo's rules).

## Why

Five checks say the LNA space under our verifier is shallow (library + one edit covers almost all tasks, even on
the objective, linearity and as-sized robustness). Op-amp specs hit sizing-proof physical bounds (gain per stage
≤ gm·ro, swing vs stacking, ICMR vs Vth, large-load stability vs compensation), so multi-device changes should be
required. D0 tests that cheaply before a benchmark is built.

## Stage 1 — verifier `opamp-v0` (build + validation gates)

- **Process:** bptm45 (`lna/pdk/bptm45.py`), VDD 1.1 V, 27 °C nominal.
- **Dialect:** device types `{NMOS, PMOS, R, C}`; nets `VINP, VINN, VOUT` (single-ended; FD out of scope for
  D0), `VDD, VSS, IREF`; one line per device as in the LNA dialect; matched groups tied by a naming convention
  (e.g. `M1a/M1b` share W/L), recorded in the README.
- **Sizing parameters:** per device (or matched group) W ∈ [0.5, 50] µm, **L ∈ [45 nm, 1 µm]**; R ∈ [10 Ω, 100 kΩ];
  C ∈ [0.05, 20] pF; IREF ∈ [1, 100] µA. Sizer = the repo's deterministic CMA-ES path (reused by import, e.g.
  `bench_anchor_prep.smoke_run`'s optimizer, or a campaign-local copy if it cannot be reused without editing
  shared code — recorded), seeded, 2,500 evaluations default; profile string `opamp-v0`.
- **Bias:** exactly **one ideal reference current** into `IREF`; every other bias is generated in the netlist.
  No ideal gate sources (no VBGEN equivalent). The input common-mode is set by the testbench (VDD/2 unless a task
  says otherwise).
- **Testbench:** unity-gain DC feedback through a 1 TH inductor with AC injected through a 1 TF capacitor
  (AnalogGym's method), load CL per task. **Metrics:** DC gain, UGF, phase margin (PM), Idd; output swing
  (range where small-signal gain ≥ gain_dc − 6 dB, from a DC sweep in open-loop-equivalent form) and ICMR
  (follower DC sweep: input range where gain stays within 6 dB of mid and output tracks within 50 mV);
  slew (short transient). CMRR/PSRR reported, not gated in D0.
- **Structural pre-filter (0 cost):** every MOS has a DC path at D and S, no floating gate, VOUT driven, no
  shorted device, device count ≤ 40.
- **Validation gates (all must pass before D0; results in the README):**
  - **V1 determinism:** the same (netlist, spec, seed) gives bit-identical metrics in 3 separate processes.
  - **V2 replay:** AutoCkt's stored two-stage deck on bptm45 reproduces its stored `ac.csv` (scoping §4 did this;
    re-run in the new harness).
  - **V3 analytic sanity:** a sized 5T OTA's DC gain within 3 dB of gm·ro/2 computed from its own operating point;
    a sized two-stage Miller within 3 dB of its two-stage product.
  - **V4 loophole checks:** (a) a netlist with a floating gate or an undriven bias node is rejected or infeasible;
    (b) PM is computed at the true unity crossing (a deliberately unstable design reads PM < 0 or "unstable");
    (c) a design whose output CM sits outside the swing window is flagged.
  - **V5 sizer strength:** on the two-stage Miller with AutoCkt's own spec, the sizer finds a feasible design at
    3/3 seeds within 2,500 evaluations.
  If a gate fails, fix and re-run the gate; if a gate cannot be passed, stop and report (no D0).

## Stage 2 — library, anchors, witnesses, widened single-edit space

- **Anchors (shown circuits):** 5T OTA; two-stage Miller + Rz.
- **F1 library:** 5T OTA, two-stage Miller + Rz, telescopic cascode, folded cascode, three-stage NMC.
- **F2′ single-edit space of each anchor:** add an R or C between any net pair; add one NMOS or PMOS with D/G/S on
  existing nets or one new net; delete one element; re-wire one terminal of one element. Pre-filtered (free).
- **Witnesses (EVAL-ONLY; never in any prompt or training file):** W-R1 folded cascode + common-source second
  stage with Miller + Rz; W-R23 three-stage with active-feedback or damping-factor compensation (transcribed from
  AnalogGym); W-R4 complementary N+P input pairs + summing stage + common-source output.
- Every library circuit and witness gets a golden (sized metrics at seed 1) in the README.

## Stage 3 — D0 depth test

**Tasks (6):** anchors {5T, two-stage} × regimes:
- **R1:** M = DC gain (dB); hard: swing ≥ 0.6 Vpp, UGF ≥ 10 MHz at CL = 2 pF, PM ≥ 60°, Idd ≤ 200 µA.
- **R23:** M = GBW·CL / Idd (MHz·pF/mA); hard: DC gain ≥ 80 dB, CL = 200 pF, PM ≥ 55°, Idd ≤ 300 µA.
- **R4:** M = ICMR width (V); hard: mid-range gain ≥ 40 dB, UGF ≥ 5 MHz at CL = 2 pF, PM ≥ 60°, Idd ≤ 200 µA.

**Calibration (before any gap is computed):** if the regime's witness is infeasible at the hard constraints at all
3 seeds, relax them along a fixed ladder — step 1: UGF ×0.5, PM −5°, Idd ×1.5; step 2: repeat once — and record
the step used. If still infeasible, the task is dropped (counts as not accepted).

**Steps** (the scoping doc's rule: every number comes from a sizing run whose objective is the metric tested, at
the spec tested — never read slack from a run that optimised something else):
1. **Frontier.** For every design d in F1 ∪ F2′(anchor) and the witness W: size to **maximise M subject to the hard
   constraints** (objective mode `max:M`). F2′ screened at 300 evaluations, seed 1; the top 20 of F2′, all of F1
   and W re-run at 2,500 evaluations × seeds {1,2,3}; M*(d) = median over seeds (infeasible seeds = −∞ for the
   median).
2. **Gap.** G = M*(W) − max_d M*(d). Minimum gap, fixed now: **6 dB** (R1), **25 %** of the reference value (R23),
   **0.15 V** (R4). Below the minimum ⇒ not accepted.
3. **Confirmation.** New spec: hard constraints + `M ≥ max_d M*(d) + G/2`. Size W and the top 5 references with
   the standard margin objective, seeds {1,2,3}. Accept iff W feasible at ≥ 2/3 seeds AND every reference
   infeasible at 3/3 seeds with worst normalized margin ≤ −G/4 (in M's normalized units).
4. **Two-edit check.** 500 random two-edit designs (two F2′ edits composed) per task, screened at 300 evaluations
   with the `max:M` objective; any reaching ≥ max_d M*(d) + G/2 at 2,500 evaluations × seed 1 labels the task
   **"≤ 2 edits"** (accepted but not deep).
5. **Verdict:** **GO** iff ≥ 4 of 6 tasks accepted AND ≥ 2 of them are not "≤ 2 edits"; **STOP** iff ≤ 1 accepted;
   otherwise report and discuss.
6. **Backstop:** report the analytic ceiling (best gm·ro at L = 1 µm)^stages per topology beside every M*, so a
   weak sizer is not misread as depth (a witness that only beats references by losing less to the sizer is noted).

## Budget and conduct

- Stage 1–2 engineering by Opus agents (subscription); Stage 3 CPU ≈ 20–25 CPU-h (≤ 8 processes on the box, 4 if
  load1 > 22, D32 disk rules, resumable on exact keys). Ask before exceeding 40 CPU-h.
- Each stage ends with a commit, a README section, and a short report to the user; Stage 3 does not start until
  Stage 1's gates pass and Stage 2's goldens exist.
- `python lna/ref/check_ref.py` stays GREEN (no shared-core change is planned; re-checked at the end).

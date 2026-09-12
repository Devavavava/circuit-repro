# qwen-editcap-v0 — diagnosis adjudication (grounding vs confabulation)

Adjudicator: Claude Fable 5 (per user commission 2026-09-11; rubric frozen
pre-run in CAMPAIGN-QWEN-EDITCAP.md §Diagnosis adjudication record).
Materials: the verbatim `gpu-leg/adjudication/<spec>/B/` archive (prompts,
raw outputs, diagnoses, per-edit predictions) cross-checked against (a) the
netlist + evidence VERBATIM as shown to the model, (b) physaudit ground
truth (withheld from the model), (c) measured sized outcomes.

## Verdict distribution (13 cells)

| verdict | n | cells |
|---|---|---|
| GROUNDED | 1 | h07 |
| PARTIAL | 6 | e07, e08, h03, h06, h08, m02 |
| CONFABULATED | 4 | h01, h02, m03, m07 |
| NO DIAGNOSIS (non-compliant) | 2 | e02, e03 — output began directly with netlists |

**CONTRADICTED flag (claims directly refuted by the evidence shown): 10 of
the 11 graded cells.** Only h07's diagnosis survives without a refuted
claim.

## Systematic failure modes (each verified against ≥3 cells)

1. **The bias-mirror blind spot (8/11 graded cells).** Every diode-connected
   device (`NMOS NM3 n6 n6 VSS VSS`, `PMOS PM2 n7 n7 VDD VDD`) is
   misread — called "floating", "shorted", "invalid (likely a typo)",
   "dummy", "parasitic", "non-functional", "no DC path". These are the
   anchors' bias references, and in several cells the model then EDITED
   them (e07 cross-coupled the two mirrors — destroying both references;
   measured worse). Qwen does not recognize the current-mirror idiom in
   flat-netlist form.
2. **Pin-order misbinding (5+ cells).** With `NMOS name D G S B` stated in
   the prompt, the model still swaps roles: h03 calls NM1's drain its gate;
   h01 calls the cascode a "common-gate input stage" and puts the mirror in
   the source path; m07 invents a gate–source short on NM1 (`NM1 n5 n2 VSS
   VSS` — no short exists) and builds its ENTIRE causal story on it; h08
   garbles NM1's source as "not grounded" (it is VSS, shown).
3. **"Missing X" template claims refuted by the shown netlist.** "No
   deliberate matching network" with L-match L1 + degeneration L2 on
   screen (h03, h02); "lacks source degeneration" with `L L2 n4 VSS`
   shown (h02); "no clear path to bias the gates" with `R R2 n6 n2` and
   `R R4 n7 n3` shown (h08, m03, m07). The model pattern-matches
   "S11 fails ⇒ assert absent matching network" regardless of the circuit.
4. **Copied numerics are near-perfect; derived structure is not.** Every
   graded cell restates the binding constraint, achieved values, and
   margins correctly (h07 even catches the secondary idd 3.249 > 3 cap
   and NF 1.845 > 1.5 correctly). Grounding is high exactly where the
   prompt could be quoted, low wherever inference over the netlist was
   required.
5. **Prediction calibration: uniformly optimistic, direction wrong at the
   cell level in ~11/13.** No edit was ever predicted to regress anything;
   measured, most did (S1 catastrophically: h01 predictions +0.5..0.8 dB
   NF gave nf −99.7/idd −29/nf −5.6). The one local success: e02's s21
   predictions (+0.8..1.2 dB) were realized (~+0.85 dB, s21 crossed its
   gate) — but the edits silently broke s11, which no prediction
   mentioned. Predicted magnitudes ("improves ~4–6 dB") show no
   correlation with outcomes.
6. **Harness-convention blindness, uncaught by grounding.** Repeated
   `L Lx VIN1 n1` edits DC-short the port into the gate-bias node (the
   exact dead-bias failure externals-v0 taught US). h07 — ironically the
   ONE grounded diagnosis — emitted three such edits; all died at the
   conduction fence.

## The load-bearing correlation

**Diagnosis quality did NOT produce the measured S2 margin gains.** The
best improvements (h03 +0.39, m07 +0.27, e07 +0.19 vs the null) all came
from cells graded PARTIAL or CONFABULATED; the single GROUNDED cell (h07)
produced only fence-dead circuits. The gains trace to generic
"add L/C at the input" moves that the sizer then exploited — structural
diversity steered by coarse spec-reading, not causal failure-reasoning.
Combined with the B-over-C validity effect (blind C emitted zero valid
edits on 3 cells), the honest summary of what evidence does for Qwen at
this scale: **it anchors the numbers and the output format; it does not
produce correct circuit comprehension, and its causal stories are
substantially confabulated even when its edits happen to help.**

## Answer to the commissioning question (were the diagnoses reasonable, or hallucinations/lies?)

Mixed, with a precise boundary: everything COPIABLE from the evidence is
faithfully reported (no fabricated numbers anywhere — no "lies" about the
data); nearly everything INFERRED about circuit structure is unreliable,
and 10/11 graded diagnoses contain at least one claim flatly contradicted
by the netlist the model was looking at. The confabulation is systematic
(mirrors, pin roles, "missing X" templates), not random — which makes it
addressable in principle (e.g., structured netlist annotation in prompts)
but that is a new-experiment question, not a v0 conclusion.

## Archive/driver flaws found during adjudication (logged)

- `edit<i>.meta.json` `predicted_delta_text` is misaligned by one block
  (holds the PREVIOUS edit's prediction; last prediction dropped).
  `raw_output.txt` is authoritative and complete — adjudication used it.
- The conduction fence passes on TOTAL supply current, which the bias
  branch alone can satisfy: h03's PMOS-swap edit (dead signal path,
  NF −81) passed the fence on mirror current. Future fence: probe the
  signal-path branch, or gate on s21 > some floor at smoke.

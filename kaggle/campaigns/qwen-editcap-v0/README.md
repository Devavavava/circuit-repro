# qwen-editcap-v0 — results (COMPLETE, 2026-09-11)

Pre-reg: kaggle/CAMPAIGN-QWEN-EDITCAP.md (freeze 79c3a976; driver 9c34349c;
materialization notes accepted). Era: library+engine frozen at 79c3a976;
GPU leg clones origin main at launch (SHA recorded then; must contain
9c34349c).

## Arm A — sizing-extension null (COMPLETE 2026-09-11, box)

**0/13 feasible at matched-total 3600 evals/cell (seeds 3 × 1200,
no-escalate), sim-health 0 fails.** Stronger null than anticipated: the S1
knife-edges did NOT fall to budget — cap-e02's s21 −0.02 re-sized into an
s11 −0.61 bind (joint trade, not budget starvation); h01 improved to nf
−0.10 but stayed infeasible; S2's s11 wall moved ±0.05 max around −1.0;
S3 unchanged. READING: all 13 residual failures are STRUCTURAL/JOINT at
this budget — any arm-B closure is clean edit-credit, and "near-miss ⇒
sizing-reachable" is FALSIFIED for this library (good for the experiment:
S1 cells are real diagnosis targets after all).

## Arms B/C — GPU leg (COMPLETE 2026-09-11, kernel v1, era 235f7634, ~2.6 h)

All fences passed (13 B rows, 13 C rows, 13 verbatim adjudication dirs).

**Frozen-rule outcomes:** edit-credit = 0 (no arm closed any cell: null
0/13, B 0/13, C 0/13). Reasoning-credit = NOT awarded (conjunctive rule;
closed-counts tie; paired margins B>C only 3/13). Falsifier = NOT met
(B is not ≤ null everywhere — see S2).

## SITUATION MAP (primary deliverable)

| bucket | situation | verdict |
|---|---|---|
| S1 (×4, near-feasible knife-edges) | **Editing is HARMFUL.** Both edit arms land WORSE than the sizing null (median wm: null −0.31, B −0.46, C −0.55; one B edit cratered h01 −0.21→−3.11). Evidence did not prevent degradation. | Do NOT let Qwen edit near-feasible circuits at this scale. |
| S2 (×7, saturated simultaneous-match wall) | **Structural edits MOVE the wall; evidence adds a modest edge.** Median wm: null −0.96, B −0.73, C −0.83. Best B improvements vs null: h03 +0.39, m07 +0.27, e07 +0.19. No closures at k=3, one leg. | The one bucket with directional diagnose→edit signal. Weak (n=7, single leg), unproven. |
| S3 (×2, wideband) | Edits neutral-to-harmful (B −1.00, C −0.94 vs null −0.83). | No capability signal. |

**Secondary finding — evidence improves edit VALIDITY:** blind arm C
produced ZERO valid edits on 3/13 cells (e07, m02, m03 — parse/structure
failures) while B had valid edits on 13/13 (one cell, h07, lost all 3
edits to the conduction fence). Showing the failure record appears to help
the model emit well-formed connected circuits at all, independent of
targeting.

Sample-size caveat: 13 cells × k=3 × one leg; S2's B-over-C margin edge is
directional, not significant. Any strengthening (k=5 on S2, repeats) needs
a new pre-reg.

## Adjudication archive (for the stronger-model audit)

`gpu-leg/adjudication/<spec>/<arm>/{prompt.txt, raw_output.txt,
diagnosis.txt [B], edit<i>.net, edit<i>.meta.json}` — VERBATIM, 13 cells ×
2 arms. Rubric frozen in the pre-reg (grounding / mechanism / coherence /
calibration, CONTRADICTED flag); physaudit ground truth was withheld from
prompts and is reserved for the adjudicator.

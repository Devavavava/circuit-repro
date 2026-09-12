# reflect-positives-v0 — results (COMPLETE, 2026-09-13)

Pre-reg: kaggle/CAMPAIGN-REFLECT-POSITIVES.md (frozen d6863d47). Era
1ee92a34, kernel circuit-repro-reflect-positives v1 (standalone
RUN_MODE=reflect branch), corpus = the frozen 4 dirs (16 feasible rows +
matched failures). reflect.py VERBATIM, cap 12.

## VERDICT: E1 NO · E2 NO — and the reason is STRUCTURAL, not model

12 entries accepted / 2 rejected (E3; leg2 baseline was 12/63). ZERO
entries cite a feasible row; zero state a family→outcome fact (E1 fails);
zero reference input-blocking/bias structure (E2 fails). All 12 are the
same genres as every prior reflect pass: netlist-mechanics anti-patterns
(budget/name/syntax violations — mined from the FAILURE leg's proposal
trajectory) and prediction-distrust diagnoses. Several show
confabulation-tinged generalizations ("simulations often fail to
converge" — corpus sim-health was 1.00 throughout).

**Root cause, visible in the audited prompt (printed pre-launch): the
reflect prompt solicits ONLY "recurring shortcomings in YOUR OWN
output".** Success rows are structurally unusable by the channel as
built — no instruction exists that could elicit "this family worked,
retrieve it". This is a CHANNEL-DESIGN finding, not a capability
finding: the 2026-08-27 standing principle's provision for architectural
change when the system STRUCTURALLY CANNOT do something applies —
a success-mining reflect variant (prompt extension + admission rule for
positive-evidence entries) is the named lever, needs its own pre-reg +
GO.

Ops gotcha (recorded): Kaggle derives the kernel SLUG from the TITLE, not
the kernel-metadata id — the launcher polled ...-reflect-pos while the
kernel ran at ...-reflect-positives; harmless here (kernel completed;
output fetched at the correct slug), but launchers must use the slug from
the push-output URL.

## Layout

system-playbook/ (12 entries verbatim) · reflect.jsonl (225 rows,
accept/reject log) · kernel-run.log

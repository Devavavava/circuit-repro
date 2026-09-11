# qwen-editcap-v0 — running record

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

## Arm B/C — GPU leg (PENDING push + launch)

Checklist: kaggle/kernels-editcap/editcap-gpu/README-LAUNCH.md.

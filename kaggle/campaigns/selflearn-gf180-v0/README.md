# selflearn-gf180-v0 — results (COMPLETE: both legs)

Pre-reg: `kaggle/CAMPAIGN-SELFLEARN-GF180.md`. Question: does the self-learning
channel (reflect-first, gf180-only corpus) generalize off bptm45? Primary
comparison = LEG2 selflearn − LEG1 arch (in-era cold control).

## Label domain

era-5a87ee18 (origin/main tip both kernels clone; sim-health observability era)
· host=Kaggle 2xT4 (kernel v20) · pdk=gf180mcu · 24-spec ladder · budgets
unchanged (base 3000 / escalation 16200 eval-equivalents per spec).

## LEG1 — arch cold control (COMPLETE, 2026-09-04, ~7.6 h campaign wall)

**0/24 feasible.** All 24 specs ran (no wall-stop).

- **Environment health (first live use of the sim-health rows):**
  `sim_success_rate = 1.00` on ALL 24 specs — zero ngspice failures in ~178k
  evals. The 0/24 is design/physics, NOT environment: the observability
  channel now proves directly what the cross-pdk era needed forensics for.
- **Binding constraints on the 24 fails:** s21_db ×13, nf_db ×10, idd_ma ×1 —
  the known gf180 wall (gain/noise at the Idd boundary).
- **vs era-binfix arch (2/24):** the in-era rerun of the same configuration
  lost both former topology-credit cells, and not narrowly — cap-e01-wifi
  missed NF by −2.94 (normalized), cap-m06-wifi missed s21 by −0.71.
  **gf180 arch run-to-run variance is large (2 → 0 across eras/sessions with
  wide margin swings); the era-binfix topology credit should be read as a
  best-of-run event, not a stable capability.** This is exactly the noise
  datapoint the pre-reg ordered LEG1 to provide; it also RAISES the bar for
  reading any LEG2 delta.

## LEG2 — selflearn (COMPLETE, 2026-09-10, kernel v21, ~8.1 h campaign wall)

**0/23 feasible; wall-stop before spec 24/24** (`PARTIAL`: elapsed 488.7 min
+ mean 21.2 min/spec > 500 min budget — cap-h08-wideband never ran; leg1 had
it infeasible too, so the primary comparison uses the 23 common specs).

- **PRIMARY PRE-REGISTERED RESULT: selflearn − arch = 0 − 0 = ZERO.** The
  self-learning channel produced no feasibility lift on gf180 at this budget.
- **Environment health:** `sim_success_rate = 1.00` on all 23 specs — zero
  ngspice failures in 162,840 evals. Same verdict as leg1: the zero is
  design/physics, not environment.
- **Binding constraints:** s21_db ×11, nf_db ×11, s11_max_db ×1 — the same
  gain/noise-at-the-Idd-boundary wall as leg1 and both prior gf180 eras.
- **Reflect mechanism WORKED off-bptm45** (first live proof): 12
  admission-passing playbook entries written from the ruled gf180-only corpus
  (63 candidates rejected on cap/admission), and every spec's propose stage
  consulted them (consult_hits = 5 on all 23). Entries are prediction-
  calibration + netlist-mechanics lessons (metric-blind-spot-iddma,
  nf-db-prediction-overshoot, systematic-prediction-bias, parse/naming
  anti-patterns...) — see `leg2-selflearn/system-playbook/` and
  `reflect-summary.json`.
- **Margins vs leg1** (13 cells with the same binding metric): 5 better /
  8 worse — no directional lift. Single-cell swings are huge in BOTH
  directions (cap-h06-wifi nf −5.39 → **−0.14, the closest gf180 near-miss
  in program history**; cap-h03-900mhz nf −2.80 → −19.44), consistent with
  leg1's large run-to-run variance finding. h06 is read as a
  noise-distribution tail, not a selflearn effect, per leg1's raised bar.

**CAMPAIGN VERDICT: the pre-registered question is answered NO at this
budget — reflect-first self-learning (gf180-only corpus) does not lift gf180
capability; the wall stands in both arms. What the campaign DID establish:
the reflect→consult plumbing works off-bptm45 end-to-end, sim-health rows
prove environment integrity live, and gf180 arch variance is large (2/24 →
0/24 → 0/23 across eras). Next levers would target the wall itself
(topology-prior work), not the learning channel.**

Ops notes: (1) the 2026-09-05 quota-reset auto-retry NEVER FIRED — it was
scheduled inside a session that ended; one-shot retries must live in host
crontab or be re-armed by a live session. LEG2 was pushed 2026-09-10 10:38
IST by `resume-selflearn.sh` (push accepted first try; RUNNING fence and
`variant=selflearn` fence both passed). (2) The stale-status incident fix
(push-verify → wait-RUNNING → variant-verify) is now validated in anger.

Era freeze LIFTED: LEG2 cloned era-5a87ee18; origin/main pushes may resume
(per-instance permission still required as always).

## Layout

```
era-5a87ee18/leg1-arch/        results.jsonl/.md, designs/, trajectory/, kernel-run.log
era-5a87ee18/leg2-selflearn/   + reflect-summary.json, system-playbook/, PARTIAL
```

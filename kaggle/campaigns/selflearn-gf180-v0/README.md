# selflearn-gf180-v0 — results (INTERIM: leg 1 of 2)

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

## LEG2 — selflearn (PENDING, quota-blocked)

Push attempt 2026-09-04 19:38 IST rejected: **"Maximum weekly GPU quota of
30.00 hours reached"** (leg1's ~8.4 h GPU landed on top of ~21.6 h already
spent this quota week). Auto-retry scheduled after the weekly reset. INCIDENT
note for future chains: `kaggle kernels push` prints the quota error but exits
0, and `kernels status` keeps reporting the PREVIOUS run's COMPLETE — a
poll-too-soon chain will download a stale duplicate and declare success.
Fix applied to the launcher: verify "successfully pushed" in push output, then
wait for status to flip to RUNNING before polling for COMPLETE, then verify
the downloaded `results.jsonl` variant matches the pushed leg.

Era freeze remains in force: no origin/main pushes until LEG2 has cloned
era-5a87ee18.

## Layout

```
era-5a87ee18/leg1-arch/    results.jsonl/.md, designs/, trajectory/, kernel-run.log
era-5a87ee18/leg2-selflearn/   (added when LEG2 completes)
```

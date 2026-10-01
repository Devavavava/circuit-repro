# rl-v1.1 port-DC requirement: tests (PREREG-BENCH-V2 AMENDMENT 2)

Verifier profile `rl-v1.1` = `rl-v1` + `VERIFY_PORT_DC=1`. It is implemented additively in `kaggle/bench_anchor_prep.py`; `lna/` is untouched. The rule and its rationale are in `kaggle/VERIFIER-RL-V1.md` § rl-v1.1. The evidence that motivated it is in `../motif-audit/`.

- **Pre-filter** (`port_dc_prefilter`): structural, before sizing, 0 sims.
  - Build the DC graph: R, L and the MOS channel (D–S) are edges; capacitors are open.
  - Take the DC group of VIN1. Do not expand through a rail node.
  - Reject if the group contains a MOS terminal on a non-rail node, or VDD, or a harness bias-source net (VB\*/VCM\*/VREF\*).
  - A path to VSS alone is allowed.
- **Behavioural check** (`port_dc_check`, `_port_dc_posthoc`): the authority.
  - Runs on the final winner, which is the stability gate's replacement if there is one. It runs only when that winner is otherwise feasible.
  - It compares two op-only decks: P0 is the testbench as-is; P3 adds `VIN1 –1 H– 50 Ω – gnd`, which is DC-only.
  - Pass iff every MOS |ΔV_G| < 10 mV and |ΔI_dd|/I_dd < 1 %.
  - On failure: `feasible=False`, reason `port_dc_fail`. `result["port_dc"]` records dVG_max_V, dIdd_pct, both Idd values, V(VIN1) and the port DC current.
- **Cache bridge** (`derive_port_dc`): gives the exact rl-v1.1 result of a call from its recorded rl-v1 twin whenever the requirement cannot change it.
  - Pre-sizing reject: the verifier itself is run in-process.
  - rl-v1 result was None: the result is None.
  - rl-v1 winner was infeasible: the rl-v1 dict plus `port_dc_prefilter`, `port_dc: None` and the rl-v1.1 verifier record.
  - A feasible twin must be re-sized. The sizing is deterministic, so this reproduces the same winner, which is then checked.

Run: `../envrun.sh python test_port_dc.py --procs 4`. It writes `results.json` (summary plus every case) and `raw_cases.json`. Sizing: bptm45, seed 1 × 2500. The anchors and the synthetic case use `run/specs/probe-amd1-nb240-gain.yaml`.

## Results (all pass)

| test | cases | outcome |
|---|---|---|
| T1 `add:L:IN-G` accepted cells | 9 | **9/9 rejected**. The pre-filter rejects 9/9 (VIN1 group holds NM1_G/NM1_D via the IN-G L and R1, and reaches VDD). The behavioural check also fails 9/9 on the motif-audit sized winners: ΔV_G 0.185–0.207 V and ΔIdd 65–73 %. This reproduces the audit's P3 collapse. |
| T2 controls nb090-gain-007, wb1020-noise-003 | 2 | **pass**: pre-filter passes (groups `{VIN1, L2_P}` and `{VIN1}`); behavioural ΔV_G = 0, ΔIdd = 0 |
| T3 library anchors a1–a5 | 5 | **pass**: pre-filter passes (group `{VIN1}` each); behavioural ΔV_G = 0, ΔIdd = 0 at the sized winner. For the feasible a1 and a2 winners, smoke_run's own `port_dc` record also passes. |
| T4 synthetic positive: a3 + shunt `L VIN1 VSS` | 1 | **not pre-filtered** (group `{VIN1, VSS}`, reaches_vss); behavioural **pass** (ΔV_G = 0, ΔIdd = 0, V(VIN1) = 0). Its seed-1 winner is infeasible at the probe, so the check was run directly on the captured winner. |
| T5 synthetic negative: each anchor's input DC block shorted (1 mΩ), at the T3 sizes | 5 | **pre-filter fails 5/5** and **behavioural fails 5/5**. ΔV_G 0.17–0.27 V and ΔIdd 57–96 % for a1–a4. For a5 (common gate, input at the source, which is grounded through L1): ΔV_G 0.13 mV but ΔIdd 8.2 %. |
| T6 cost of one behavioural check | 21 | median **0.009 s**, max 0.054 s (2 op-only ngspice decks). This is negligible next to a ~50–80 s sizing call. |
| T7 cache-bridge exactness | 3 derivable + 2 re-sized | derived == fresh rl-v1.1 smoke_run **3/3** (infeasible sized row, pre-filter reject of a feasible L-IN-G row, topo pre-reject). The two feasible pre-filter-passing rows (a search witness and a cal anchor), re-sized under rl-v1.1, equal the rl-v1 row plus the port-DC keys **2/2**, with port_dc pass. |
| T8 byte-identical | 5 rl-v1 + 2 no-profile | re-running 5 recorded bench-v2 rl-v1 rows with profile rl-v1 is **identical 5/5** (rows: feasible search, infeasible search, feasible L-IN-G search, feasible cal, topo pre-reject). With no profile, HEAD's (pre-rl-v1.1) module and this module give **identical 2/2** results (a3, a1), and neither has a `verifier` key. |

**Byte-identity convention.** "Identical" excludes exactly one field, `stab_inloop.wide_secs`. It is the wall-clock seconds spent in the in-loop stability sims, and `smoke_checks.py`'s determinism check excludes it too. Every other key is compared as serialized JSON, key order included. A derived row keeps its rl-v1 twin's `wide_secs`.

**Reading T5 a5.** The shorted common-gate input is the case where the pre-filter is stricter than the behavioural rule. VIN1 lands on the input source node, which L1 already ties to ground. The gate barely moves, but the extra 50 Ω still shifts Idd by 8 %, so both checks reject it.

## Files

- `test_port_dc.py`: the tests above (≤ 4 processes; `--only case_row,...` re-runs some case kinds and merges).
- `results.json`, `raw_cases.json`: outputs.
- `_scratch/`: ad-hoc analysis scripts (not committed).

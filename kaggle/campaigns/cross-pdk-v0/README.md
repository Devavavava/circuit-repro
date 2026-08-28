# cross-pdk-v0 — same 24-spec ladder on foreign PDKs

Pre-reg: the cross-PDK campaign arms in `kaggle/CAMPAIGN-CAPABILITY-V0.md`-lineage
(pdk threading landed at 2340426e). Question: does capability transfer off
bptm45, and is any degradation setup-fit or process physics? Verdict instrument:
per-PDK feasible counts + the stage-rate matrix.

`cross-pdk-per-spec.md` = full requirement-vs-achieved tables for every run
below, with the two-bug reading.

## Label domains / eras

Every run is tagged by PDK, by host, and by CODE ERA. Rows from different eras
or hosts are NEVER pooled (label-domain rule, `kaggle/PLAYBOOK.md`).

### era-bugged-aa8923be (code at aa8923be, 2026-08-27/28)

Two harness defects present (found from these very artifacts, fixed in
c8114a59 / merge 0b4b497e):

1. every inductor pinned at the adapter's MOS channel-length literal read as
   henries (sky 150 nH / gf 280 nH / ihp 130 nH) — the sizer never controlled
   an inductor on any foreign PDK;
2. gate bias pVB fixed at 0.5 V on every process — below Vth on sky130 (1.8 V
   devices) and gf180 (3.3 V devices), so every design on those two is a dead
   circuit (Idd ~ µA, S21 negative); above Vth on bptm45 + IHP-LV, which is why
   those looked fine.

| run | host | result | notes |
|---|---|---|---|
| `arma-sky130` | box (null) | 0/14 | 500-min wall stop before spec 15 |
| `arma-gf180mcu` | box (null) | 0/24 | complete |
| `arma-ihp_sg13g2` | box (null) | 11/12 at fix time | added when its wall budget ends; feasible DESPITE bug 1 |
| `armb-selflearn-sky130` | Kaggle 2xT4 (arm-B selflearn) | 0/6 | wall stop; reflect wrote 12 admission-passing entries live (`system-playbook/`); `kernel-run.log` = kernel log |

These runs measure the two bugs, not the model or the processes. They are kept
as the negative-control era: the post-fix reruns must differ in exactly the way
the bug analysis predicts (sky/gf circuits conduct; ihp improves or holds).

### era-fixed-0b4b497e (code at merge 0b4b497e, 2026-08-28 →)

Post-fix arm-A rerun chain (box, sky130 → gf180mcu → ihp_sg13g2, same ladder,
same budgets, `kaggle/run_arm_a.sh`) — results land here when the chain
finishes. GPU arm-B continuation is a user ruling after the rerun verdict
(and needs the fix pushed to origin/main first: Kaggle clones origin).

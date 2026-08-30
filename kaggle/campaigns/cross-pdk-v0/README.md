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
| `arma-ihp_sg13g2` | box (null) | 12/13 | exited during spec 14; feasible DESPITE bug 1 |
| `armb-selflearn-sky130` | Kaggle 2xT4 (arm-B selflearn) | 0/6 | wall stop; reflect wrote 12 admission-passing entries live (`system-playbook/`); `kernel-run.log` = kernel log |

These runs measure the two bugs, not the model or the processes. They are kept
as the negative-control era: the post-fix reruns must differ in exactly the way
the bug analysis predicts (sky/gf circuits conduct; ihp improves or holds).

### era-fixed-0b4b497e (code at merge 0b4b497e, run 2026-08-28/29)

Post-fix arm-A rerun chain (box, same ladder, same budgets,
`kaggle/run_arm_a.sh`). Per-spec tables + verdicts:
`cross-pdk-per-spec-fixed.md`.

| run | result | verdict |
|---|---|---|
| `arma-sky130` (+ `arma-sky130-resume-tail`, together the full 24) | **0/24** | STILL SETUP-LIMITED: ~2/3 ngspice-failure rate at random sizing points starves the sizer (suspect fd_pr W/L binning); own bring-up fix needed before any sky130 capability claim |
| `arma-gf180mcu` | **0/24** | ALIVE at the boundary: rides the Idd cap exactly, NF ~7–8 vs gates 1.5–3.5, S21 ~ −2 dB — physics and/or 45nm-bred topology priors; arm-B comparison now meaningful here |
| `arma-ihp_sg13g2` | **23/24** | TRANSFER SUCCESS — beats the bptm45 null (20/24); only the known wideband wall (h08) stands |

`arma-sky130-resume-tail`: 10 specs run with the same fixed code by a leftover
gated resume job from the prior session that wrote into the old buggy-era
output dir (ts-verified post-merge; the buggy-era archive predates that write
and is uncontaminated). GPU arm-B continuation is a user ruling after this
verdict (and needs the fix pushed to origin/main first: Kaggle clones origin).

### era-binfix-9df8b95a (sky130 binning fix 5b132013, run 2026-08-29/30)

sky130's third defect fixed (fd_pr bin table vs the W box — see the
5b132013 commit message); environment healthy on all four PDKs
(check_pdk_wsweep GREEN). Box null `arma-sky130` + the user-commissioned GPU
arm-B ARCH chain (matched ladder/budgets, kernels v17-v19).

| PDK | arm-A null | arm-B arch (LLM) | B-solves-where-A-fails |
|---|---|---|---|
| sky130 | 0/14 (wall stop; now ALIVE: S21 ~+1 dB, Idd rides budget) | 0/11 (wall stop) | 0 |
| gf180mcu | 0/24 (era-fixed run) | **2/24** | **2 — cap-e01-wifi, cap-m06-wifi** |
| ihp_sg13g2 | 23/24 (era-fixed run) | 10/17 (wall stop) | 0 (null dominates) |

**First topology-credit cells in the program's history.** On gf180mcu the
null — 45nm-bred corpus topologies, matched escalated budgets — scores 0/24
and rides the Idd cap at S21 ~ −2 dB; the model's proposals hit
cap-e01-wifi (NF 2.39/3.5, S21 13.3/10, S11 −9.8/−8, Idd 11.9/15, wl
88dde50b, NOT in the topology store: single NMOS + PMOS pair + 3 inductors)
and cap-m06-wifi (NF 2.2/2.2, S21 15.9/15, S11 −14/−12, Idd 5.3/6, wl
15b5d521: minimal single-NMOS + R + 3 inductors). Both are
process-appropriate simplifications the corpus set does not contain.
ADVISORY: both winners are conditionally stable in-band (k_min 0.52 / 0.33);
stability has never been a ladder gate for ANY arm (advisory verify metric
only) — a K>=1 gate would need a new pre-registered ladder version.
sky130: both arms zero — a real wall at these budgets, no attribution.
ihp: the null dominates; arm-B found no cell the null missed.

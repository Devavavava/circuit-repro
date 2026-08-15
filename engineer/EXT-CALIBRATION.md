# EXT-CALIBRATION — the AnalogGym externals calibration track

**Status:** the honest survey + subset table for the external calibration work of
`00-CHARTER.md` §6 E-2 and `PROTOCOL.md` §10 / §EXT. Commissioned by the user
(2026-08-14, confirmed 2026-08-15). This document is the *what runs here vs what
AnalogGym contains*, with every exclusion carrying its reason — SURVEY §1.1/S11's
honesty applied to a benchmark import.

The in-house 7-task registry is a **pilot** (its own words, §10). AnalogGym's
external op-amp tasks are the **calibration set** that makes "our sizer is good" a
statement about more than our own store. This track does not change the 7 in-house
pins or PROTOCOL v0's registered content: the externals enter as a **separate
namespace and a separate tier** (`tier="ext"`) — op-amp / OTA sizing (SKY130,
ngspice), **not** RF (SURVEY §3 + S11: AnalogGym is *"not a superset, a different
domain"* — no S-parameters, no NF-with-source-impedance, no two-tone).

---

## 1. What AnalogGym actually contains (the pinned clone)

Upstream: **CODA-Team/AnalogGym @ `0a9d1390ade361e2b4a2d33181e22367edbb8afc`**,
BSD-3-Clause, pinned in the main checkout's `UPSTREAM.md`, fetched into the
gitignored dep area `AnalogGym/repo/` (house pattern). Reachable from the worktree
by the same `LNA_DEPS_ROOT` walk-up env.py uses.

| Category | Contents | Simulator | Runs here? |
|---|---|---|---|
| **Amplifier** | 17 op-amp `spice_netlist` + `design_variables`; a shared 5-DUT-in-one AC/DC + Tran ngspice testbench; `perf_extraction_amp.py` (the FoM) | **ngspice** | **YES — the calibration set** |
| **Low Dropout Regulator** | 4 LDOs; ngspice testbenches; `perf_extraction_LDO.py` | ngspice | Deferred (follow-up rung; amps first) |
| **Charge Pump** | `tran_27corner.sp`, `.ocn`, `sim.sh` | Spectre + OCEAN | No (no ngspice deck) |
| **Phase-Locked Loop** | `pll_vco.ocn`, `cds.lib`, `mylib.zip` | Spectre + OCEAN | No |
| **Sensing Front End** | `spectre_ptat*`, PTAT refs | Spectre | No |
| **Voltage Reference** | a description `.md` only | — | No (no shipped netlists) |

**Format (the three-file decoupling, SURVEY §3, confirmed):** a testbench `.cir`
`.include`s (a) a frozen `.subckt` netlist, (b) a `design_variables` file of
`.PARAM` lines — the ONLY thing an optimizer touches, (c) the SKY130 PDK corner.
Matching ratios are baked into the netlist (`m='4*…'`), so an optimizer cannot
break a current mirror. Variable names encode function (`gm1`, `BIASCM`, `LOAD2`).

**PDK:** SKY130 (`PDK/sky130_pdk.zip`, unzipped in place). The testbench uses the
`libs.tech/ngspice/corners/tt.spice` corner, which `.include`s the BSIM model cards
under `libs.ref/sky130_fd_pr/spice/`. The whole ngspice-relevant tree is text and
loads on **ngspice-47** (AnalogGym pins ngspice ≥ 42; 41 gives wrong DC sweeps —
our `$NGSPICE` = 47 satisfies it). Nothing installed system-wide.

**Objective / specs:** AnalogGym ships its OWN objective — the `fom[i]` scalarization
in `perf_extraction_amp.py` — and its OWN failed-`.meas`→directional-default
convention. Those are the specs this track curates and pins (the charter's *"no new
specs"* rule). AnalogGym does **not** ship a per-topology baseline results table to
reproduce (it ships training artifacts, an OP-normalization JSON, and an HSPICE
reference netlist — none a stated ngspice operating point), which is why the golden
is a replay-fence, not a baseline reproduction (§EXT.6, §4 below).

---

## 2. The ngspice-runnable subset — established by simulation, not assumption

Every amplifier was simulated at its **shipped default sizing** on ngspice 47 (the
5-DUT AC/DC deck). An amp is IN iff its netlist elaborates and produces finite AC
metrics.

### 2.1 IN — the 14 scored amps (`ext_gym.RUNNABLE`)

| amp | dim | dc gain @ default (dB) | note |
|---|---:|---:|---|
| `Fan_SMC_Pin_3` | 23 | 69.9 | two-stage Miller |
| `HoiLee_AFFC_Pin_3` | 33 | 90.1 | **golden anchor** |
| `Leung_DFCFC1_Pin_3` | 30 | 122.8 | |
| `Leung_DFCFC2_Pin_3` | 27 | 108.4 | |
| `Leung_NMCF_Pin_3` | 24 | 96.6 | |
| `Leung_NMCNR_Pin_3` | 22 | 122.4 | smallest dim |
| `Peng_ACBC_Pin_3` | 33 | 94.2 | |
| `Peng_IAC_Pin_3` | 31 | 114.0 | |
| `Peng_TCFC_Pin_3` | 24 | 117.6 | |
| `Qu2017_AZC_Pin_3` | 38 | 97.9 | largest dim |
| `Ramos_PFC_Pin_3` | 24 | 135.3 | |
| `Sau_CFCC_Pin_3` | 29 | 99.6 | |
| `Song_DACFC_Pin_3` | 33 | 90.3 | |
| `Yan_AZ_Pin_3` | 36 | 149.6 | |

All 14 produce finite AC metrics at default sizing (dims 22–38). Phase margin at
default is often low (these are shipped as *uncompensated* starting points an
optimizer improves), which is exactly what a benchmark should hand a search.

### 2.2 Runnable-but-degenerate at default (held out of the scored set)

| amp | dim | reason |
|---|---:|---|
| `Alfio_RAFFC_Pin_3` | 27 | dc gain < 0 at *default* sizing → some `.meas` fail at the default point (finite worst-case default is substituted; the deck elaborates and an optimizer can move it). Held out so the golden anchors on a clean default. |

### 2.3 OUT — with the reason (never silently dropped)

| item | reason |
|---|---|
| `Qu_LEC_Pin_3` | **netlist file is empty (0 bytes)** in the upstream clone |
| `Tan_CLIA_Pin_3` | netlist does not elaborate on ngspice 47 ("incomplete netlist" at subckt expansion; chopper amp) |
| `Cascode_Miller_Pin_2` | `design_variables` shipped without a `spice_netlist` file |
| `Cascode_Null_Pin_1` | ″ |
| `Davide_ASMIHF_Pin_3` | ″ |
| `TwoSt_SMCNR_Pin_2` | ″ |
| **LDO** category | ngspice testbenches present, but the LDO FoM (`perf_extraction_LDO.py`) is a distinct rung — **deferred to a follow-up**, amps first |
| **Charge Pump / PLL / Sensing Front End / Voltage Reference** categories | need Spectre / HSPICE / OCEAN, which we do not have — out of scope, not a limitation of the adapter |

---

## 3. The adapter (`engineer/ext_gym.py`)

Turns an AnalogGym testbench into env.py's *contract* without editing env.py,
tasks.py, or any driver (the E-1 falsifier). `ExtEnv` exposes the identical public
surface `Env` does — `objective_fn` / `evaluate` / `best` / `observe` / `harness`,
budget-counted, harness-stamped, deterministic — and `lna/null_sizer.run_cmaes` is
imported verbatim as the cmaes arm. A **parallel env**, not a `Task` subclass,
because `env.Env` is bound end-to-end to the LNA RF harness (`null_sizer.build_task`
builds a 45 nm BSIM S-param/NF deck); AnalogGym is a different domain, and forcing
it through `build_task` would fork the harness the charter forbids (§8). So the
external track gets its own deck-build and its own (AnalogGym) objective, and shares
the LNA line only for what is genuinely shared: nothing that measures an RF number.

**Failure semantics** (NotSizable's spirit): an empty/absent netlist or one that
does not elaborate raises `ExtNotSizable` at build time, before any eval is charged;
a deck that ran but a `.meas` failed gets AnalogGym's own directional-worst-case
default (finite, not NaN) and costs one eval — a measurement, not a refusal.

**Stamps:** `$NGSPICE` version, AnalogGym SHA, adapter sha256, pinned netlist/vars
sha256, PDK path, `domain: "op-amp (SKY130); NOT RF"` — no external number can be
read without its provenance.

---

## 4. Golden (before any scoring) — replay-fence, spread 0.0

No AnalogGym-shipped ngspice baseline exists to reproduce, so the golden is
**fixed sizing → fixed metrics**: `HoiLee_AFFC_Pin_3` at its shipped default sizing
reproduces, on this harness,

> dc gain **90.0754 dB**, GBW **838366 Hz**, phase **8.0522°**, FoM **−85463.332359**

verified **3× in-process + a separate process, spread 0.000000** (float noise
1.6e-10, below the 1e-6 replay tolerance). Recorded in
`engineer/data/ext_golden_v0.json`, re-checked before the scoring run. Any drift at
fixed harness era is flagged loudly (charter §4).

---

## 5. Scoring (PROTOCOL §EXT) and artifacts

Two null arms (`cmaes` = `null_sizer.run_cmaes` verbatim; `random` = uniform
`[0,1]^d`), **N = 10 seeds**, **budget 1000 evals** (AnalogGym's own, per amp),
one eval = two ngspice calls (AC/DC + Tran). Aggregation identical in shape to the
in-house track (§5.3/§5.4): per-amp feasible-rate + median/best FoM + first-feasible;
cross-amp **median-rank** (no cross-amp FoM averaging — scales differ). Modeling
time accounted separately from simulation time. Artifacts:
`engineer/data/scoreboard_ext_v0.json`, per-cell `ext_{arm}_{amp}_s{seed}_b1000.json`,
`engineer/data/ext_trajectories.jsonl`, plus the README section.

The scoreboard carries the §EXT appendix's pre-registration commit SHA as its
protocol provenance; the appendix was committed **alone, before** the first external
scoring cell ran — the E-2 falsifier's fence.

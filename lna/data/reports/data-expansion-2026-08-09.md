# Real LNA data expansion — survey + prototype conversion

**Date:** 2026-08-09 · **Scope:** find legitimately usable REAL LNA circuit topologies to
expand the 41-circuit real-LNA diet (AnalogGenie dataset indices 461-492, 1081-1090),
catalog every source found, and prototype-convert a handful end-to-end
(netlist → connection matrix → token sequence → structural screen → SPICE → ngspice).
Companion to [FINDINGS.md](../../FINDINGS.md) / [WORKLOG.md](../../WORKLOG.md); does not
edit either. Owns only `lna/data/external/**` and this report.

**Hard exclusion honoured:** nothing here fetches, cites, transcribes, or derives from
Kanchetla et al., "A Compact, Reconfigurable CMOS RF Receiver for NavIC/GPS/Galileo/BeiDou,"
IEEE TMTT 70(7), July 2022. Every source below is independent of that paper; where a
source's *topic* overlaps (e.g. an open-source GPS-band LNA), that is coincidence — the
target paper's circuits were never looked up, and no comparison to it was made.

**Prior work mined, not redone.** The dormant worktree
`C:\Users\Devavrat\circuit-repro\.claude\worktrees\analoggenie-dataset-expansion\` had
already built and unit-tested a generic SPICE → AnalogGenie converter
(`dataset_expansion/spice2genie.py`, aimed at AnalogGym- and ALIGN-style netlists) and had
cloned ALIGN's public repo into `_scratch/ALIGN/`. Both were reused here — the converter was
copied into `lna/data/external/_tools/spice2genie.py` (my owned copy; two real bugs found and
worked around, see §3) and ALIGN's `CircuitsDatabase` was searched for RF content directly.
`lna/build_lna_corpus.py`, `lna/topology.py`, and `lna/to_spice.py` were read for the exact
format/vocabulary contract and used read-only (imported / execed / invoked as a subprocess),
never edited.

---

## 1. Bottom line

- **Best source found: IHP-GmbH's open-source SG13G2 tapeout program** (Apache-2.0). It is
  the only source in this survey that is (a) real, taped-out silicon, (b) device-level, (c)
  permissively licensed, (d) topologically diverse (MOS and SiGe HBT LNAs from GPS-band up to
  207 GHz), and (e) **renewable** — a new tapeout campaign lands every 1-2 months and LNA
  submissions appear in most of them.
- **Second: ALIGN's CircuitsDatabase** (BSD-3-Clause) — one real, differential LNA, already
  exhausted (its `Wireless-Radio_frequency` category has exactly one LNA entry).
- **Everything else checked was low- or zero-yield for this specific ask** — AnalogGym and
  MAGICAL carry no RF/LNA circuits at all (confirmed by listing their folders directly, not
  by trusting descriptions); AICircuit's "LNA" is a single fixed topology's parametric sizing
  sweep (CSV, no topology diversity); GitHub's hobbyist "low-noise-amplifier" topic is almost
  entirely PCB/firmware projects, not IC netlists; no downloadable real LNA netlist collections
  turned up from open courseware or ngspice example repos.
- **Prototype conversion: 3/3 attempted circuits converted, screened, emitted to SPICE, and
  simulated successfully in ngspice** (op + `sp` + noise, zero errors) — two from IHP
  (NMOS and NPN/HBT variants of the same GPS-band design), one from ALIGN (a differential
  resistive-load LNA). Structural screen scores were 5/5, 4/5, and 2/5 respectively — all
  three results are explained and expected, not screen bugs (§4).
- **A real gap was found and worked around, not silently absorbed:** `lna/to_spice.py` has no
  NPN/PNP emission path even though `lna/topology.py`'s own vocabulary supports it. Flagged
  in `lna/data/external/ihp-gps-lna-npn/provenance.json`; worked around with an owned-path
  supplementary emitter so the prototype could still be simulated end-to-end.

---

## 2. Ranked ingestion plan

### Rank 1 — IHP-GmbH open-source SG13G2 tapeouts

- **What:** `github.com/IHP-GmbH/TO_<Month><Year>` — one repo per MPW tapeout campaign.
  Real, submitted, taped-out RF designs from students/hobbyists/companies, each with
  `design_data/` (schematic in `xschem` and/or `qucs-s`, sometimes a flattened `xyce`/SPICE
  netlist under `design_data/xyce/simulations/*.spice`), `doc/`, `val/`.
- **License:** **Apache-2.0**, confirmed at the repo root of `TO_Apr2025` and `TO_Dec2023`
  (both fetched directly, not assumed). Clean to ingest.
- **LNA folders found by listing 7 campaigns directly** (`TO_Dec2023`, `TO_Nov2024`,
  `TO_Dec2024`, `TO_Apr2025`, `TO_May2025`, `TO_July2025`, `TO_Sep2025`):

  | Campaign | Folder | Netlist format available | Converted this session |
  |---|---|---|---|
  | Apr2025 | `GPS_LNA` (NMOS variant, `lna_tb_xyce_rf_rfmos.spice`) | flat Xyce SPICE, ready | **yes** — `ihp-gps-lna-nmos` |
  | Apr2025 | `GPS_LNA` (NPN/HBT variant, `lna_tb_xyce_rf_npn.spice`) | flat Xyce SPICE, ready | **yes** — `ihp-gps-lna-npn` |
  | Apr2025 | `160GHz_LNA` | `qucs-s` + `xschem` schematic only | no — needs schematic-geometry parsing |
  | Dec2023 | `LNA_24GHz` | `design_data/` has only a README at the depth checked; not explored further | no |
  | Dec2023 | `Y0_openSource_LNA` | same as above | no |
  | May2025 | `LNA_2.45G` | `xschem` + `qucs-s` only, no flat netlist found | no |
  | May2025 | `207GHZ_LNA`, `Cascode_160GHz_LNA` | `qucs-s`/`openems` only | no |
  | Dec2024 | `RF_amplifiers` | `xschem` only | no |

  That is **8 distinct real LNA design folders spotted, 2 converted**, with **6 more real,
  license-clean candidates identified but not yet converted** because they only ship
  schematic-capture files (`xschem` .sch or Qucs-S .sch), not a flattened netlist. Both formats
  are coordinate-based (component placement + wire segments tagged with net labels); extracting
  a netlist requires either (a) knowing each PDK symbol's pin offsets (fetchable from
  `IHP-Open-PDK`'s `sg13g2_pr` symbol library) to do the coordinate math, or (b) actually running
  `xschem -n`/Qucs-S locally to flatten them (neither tool is installed in this environment).
  Effort: **medium** for the first one (build the xschem-symbol pin-offset table once), **low**
  for each subsequent one in the same PDK (the symbol table is reusable) — a good next task for
  whoever continues this work.
- **Renewability:** this is not a fixed pool. New campaigns appear every 1-2 months (7 seen
  spanning Dec2023-Sep2025) and roughly half contained an LNA submission. Re-polling
  `github.com/IHP-GmbH` periodically is a standing, nearly-free source of new real topologies.
- **Recommended next action:** build the `xschem`-symbol-to-pin-offset extractor (one-time
  cost) and run it over the 6 identified-but-unconverted folders, then re-poll the org for
  campaigns after Sep2025.

### Rank 2 — ALIGN CircuitsDatabase

- **What:** `github.com/ALIGN-analoglayout/ALIGN-public`, `CircuitsDatabase/Sized_Netlists/
  Wireless-Radio_frequency/LNA/` — one real, previously-taped-out differential LNA
  (`LNA_QM_V1`, library name `PhasedArray_WB_copy`), with a self-contained flat Spectre-syntax
  subckt (`LNA_TB.scs`) that lists real device values.
- **License:** **BSD-3-Clause** (Regents of the University of Minnesota / Texas A&M / Intel),
  confirmed from the repo's own `LICENSE` file.
- **Yield:** exactly **one** LNA in this category — `Wireless-Radio_frequency/` also has
  `Mixer`, `Oscillator`, `Bandpass_filter`, none of which are LNAs. **Converted this session**
  (`align-lna-qm`). This source is now exhausted for LNA-specific content; the rest of
  `CircuitsDatabase` (`Low_frequency_analog`, `Power_management`, `Wireline`) is out of scope
  by construction (no RF LNA circuits there).
- **Bonus asset:** the dormant worktree's `spice2genie.py` (reused, see §3) is a generic,
  already-unit-tested SPICE → AnalogGenie converter aimed partly at ALIGN's hierarchical
  `.subckt`/`x`-instance style. It is reusable well beyond this one circuit if ALIGN's other
  example categories are ever revisited (they are not LNAs, so out of scope here).
- **Recommended next action:** none further on ALIGN itself; the reusable asset is
  `spice2genie.py`, already carried forward.

### Rank 3 — Classic/textbook LNA archetypes (hand-transcription)

- **What:** well-known named topologies from CMOS LNA survey literature (noise-cancelling /
  Bruccoleri-style, current-reuse stacked, resistive shunt-feedback) — not tied to any single
  paper, generic enough to transcribe by hand the same way this project already built
  `lna/ref/ref24_cg.cir`, `ref24_csdeg.cir`, `ref24_tapped.cir`.
- **Why ranked low despite being "findable":** no open, machine-readable netlist collection
  for these exists (checked Berkeley EECS142/242A course pages, MIT OCW, ngspice example
  repos, FOSSEE's netlist examples — none host RF LNA netlists). This category is **manual
  transcription effort disguised as a search result**, not a discovered dataset. It also is
  not "real" ground truth in the sense the mission asks for — it is exactly the
  hand-authored-archetype category the mission explicitly wants to expand *beyond*. Kept in
  the plan only because it is cheap insurance if the IHP schematic-parsing effort stalls.
- **License:** n/a (transcribed from public domain circuit theory / device physics, not
  copied from any specific paper's figure).
- **Effort:** ~30-60 min per topology once sized (mirrors the project's own `ref24_*.cir`
  process).
- **Recommended next action:** deprioritize below the two real sources; revisit only if IHP
  schematic-parsing proves too costly.

### Checked and excluded (negative findings, not just "not tried")

| Source | Finding | Evidence |
|---|---|---|
| **AnalogGym** (`CODA-Team/AnalogGym`, BSD-3) | **No RF/LNA content.** "Sensing Front End" category = PTAT temperature sensors (`PTAT_SENSOR`, `front_end_*_schematic`); "Amplifier" category = chopper-stabilized/auto-zero op-amp topologies (`Leung_NMCF`, `Peng_ACBC`, `Sau_CFCC`, etc. — all named after op-amp survey-paper archetypes). Confirmed by listing both folders directly via the GitHub API, not by trusting the paper abstract. | `AnalogGym/Sensing Front End`, `AnalogGym/Amplifier/spice_netlist` folder listings |
| **MAGICAL** (`magical-eda/MAGICAL`) | Benchmark set is 1 ADC + 1 comparator + 3 OTAs. No LNA. | Public description; not cloned since the benchmark scope is stated directly. |
| **AICircuit** (`AvestimehrResearchGroup/AICircuit`, MIT) | `Dataset/LNA/LNA.csv` (2.8 MB) is a **parametric sizing sweep of one fixed topology** (columns `C1,C2,Ld,Lg,Ls,WN1,WN2 -> GTMax,S11Min,NFMin,Bandwidth,PowerConsumption`) — the same inductively-degenerated-cascode family already in the corpus and in `lna/ref/ref24_csdeg.cir`. Zero topology diversity; not useful for corpus expansion. Possibly useful later for calibrating realistic W/L/L sizing ranges (a `lna/size.py`-adjacent concern, out of my scope). | Fetched and inspected `LNA.csv` directly |
| GitHub topic `low-noise-amplifier` (30 repos, sorted by stars) | Overwhelmingly PCB/firmware hobbyist projects (ESP32 driver code, audio/instrumentation preamps, RF front-end modules) — wrong abstraction level entirely. The few IC-design course projects found (`kantarcise/Low-Noise-Amplifier-Design`, `Nati1703/RF-ADS-Project`, `Sourabh362/Dual-band-LNA...`) have **no license** (GitHub default = all-rights-reserved) and/or no actual netlist artifact (PDF/MATLAB reports, or ADS-proprietary project files with no exported SPICE). **Do not ingest without user review** if ever revisited. | `api.github.com/search/repositories?q=low-noise-amplifier`; per-repo content/license checks |
| eSim/FOSSEE "Completed Circuits" (138 entries, CC BY-SA 4.0) | No entry classified as LNA or RF front-end despite one LNA (NAVIA Labs' PP-LNA) being publicized from the same eSim Marathon program — that design lives in IHP's own tapeout repos, not in eSim's community listing, and was not separately found under a NAVIA Labs GitHub account. | Fetched the completed-circuits listing directly |
| Berkeley EECS142/242A, MIT OCW, ngspice example repos, FOSSEE `Online-NgSpice-Simulator` | No downloadable, machine-readable RF LNA SPICE netlists found. Course readers are PDFs/lecture notes; ngspice example repos are digital-logic or basic passive circuits. | Targeted web search, several query variants |
| "Ckt-Bench-101/301" (op-amp only) and a described-but-unlinked "1M Cadence-simulated RF circuits" dataset (mentioned in passing by an unrelated RF-GNN paper, arXiv 2508.16403) | Ckt-Bench is confirmed op-amp-only (out of scope). The "1M circuits" claim has **no linked repository or license** and its scale strongly suggests an internal/proprietary dataset, not an open one. **Not verified as open — do not pursue without first confirming a public release.** | Web search only; no repo found |
| Efabless/OpenMPW + SkyWater sky130 | No dedicated open LNA tapeout project surfaced (unlike IHP's program, which has an explicit RF/mmWave tapeout track). sky130's open ecosystem skews digital/low-frequency-analog. Not a negative proof of absence, but nothing found after a real search. | GitHub search, multiple query variants |

---

## 3. Tooling notes (for whoever continues this)

- **`lna/data/external/_tools/spice2genie.py`** is a copy of the dormant worktree's converter,
  adapted (owned copy, safe to edit further) after two real bugs were found while using it on
  real data:
  1. Its generic `X`-prefixed-instance handler only recognises a device as MOS via a
     `len(plain) >= 5` check (4 pins + model name). Real Xyce-exported netlists frequently
     call 2-3-terminal R/C devices through the same `X`-prefixed subcircuit-call syntax
     (`XR2 net5 net1 rppd ...`, `XC1 net4 net5 GND cap_rfcmim ...`) — these have only 3-4
     tokens, miss the `>=5` check, and are misrouted into "instance of undefined subcircuit"
     failures. **Worked around** by renaming such lines to plain `R`/`C` element syntax in the
     per-circuit `cleaned_core*.spice` inputs (documented per-circuit in `provenance.json`),
     not by patching the shared logic.
  2. Its `_model_kind()` heuristic classifies *any* unrecognised model name starting with the
     letter `n` as NMOS (`"nfet" in m or "nmos" in m or m.startswith("n")`). A real SiGe HBT
     model name like `npn13G2` starts with `n` and would have been silently mislabelled as an
     NMOS transistor (connectivity would stay correct; device *type* would be wrong,
     invisibly). **Worked around** by rewriting those `X`-prefixed BJT calls to standard SPICE
     `Q<name> C B E model` syntax, which routes through the converter's dedicated (and
     correct) bipolar handler. Neither bug is fixed in the *original* dormant-worktree copy —
     only in the copy under my owned path — so whoever eventually merges that worktree's work
     should apply the same fix upstream.
- **`lna/to_spice.py` (shared, unedited) has no NPN/PNP emission path.** Confirmed by running
  it directly on the `ihp_gps_lna_npn` sequence (`cannot emit 12 device(s): NPN1: unsupported
  device type ...`), even though the sequence itself passes `lna/topology.py`'s structural
  screen (4/5) and NPN/PNP are fully described in that module's `LEGAL`/`DEV_PREFIXES`. Worked
  around with `lna/data/external/_tools/to_spice_bjt_ext.py`, an owned-path emitter that
  mirrors `to_spice.py`'s conventions (param naming discipline, `rshunt`, finite inductor Q,
  `db` floor, contiguous S-parameter port numbers — see `lna/WORKLOG.md` fixes X1-X6) and adds
  a `Q`-element branch with a generic ngspice default NPN/PNP model (no PDK-specific
  parameters were retrieved, so this is illustrative, not calibrated). **Recommended: whoever
  owns `lna/to_spice.py` should add native NPN/PNP support** — the vocabulary and the demand
  (this circuit) both already exist.
- Reused, execed read-only exactly as `lna/build_lna_corpus.py` does (never the driver loop,
  never edited): `AnalogGenie/repo/SPICE2GRAPH_compress.py` (`build_connection_matrix`) and
  `AnalogGenie/repo/Augmentation.py` (`dfs_all_paths`,
  `check_if_path_covers_all_edges_exactly_once`).

---

## 4. Prototype conversion results

All three circuits: raw source → cleaned/normalised SPICE → `spice2genie.convert()` →
`.cir`/`Port.txt` → upstream `build_connection_matrix` → upstream `dfs_all_paths` → token
sequence → `lna/topology.py` structural screen → `lna/to_spice.py` (or the NPN extension) →
`ngspice_con.exe` (`op` + `sp lin 201 1e9 4e9` + `noise`), one process at a time.

| Circuit | Source | License | Devices | Score /5 | Missed criteria | Emitted? | Simulated? |
|---|---|---|---|---|---|---|---|
| `ihp-gps-lna-nmos` | IHP `TO_Apr2025/GPS_LNA` (NMOS) | Apache-2.0 | 11 (3R+2C+3L+3M) | **5/5** | none | yes, `to_spice.py` | **yes**, clean (S11min -0.66 dB, S21max -13.6 dB with unsized placeholder devices — expected, matches how every freshly-converted, un-sized AnalogGenie topology behaves per `FINDINGS.md` §4d) |
| `ihp-gps-lna-npn` | IHP `TO_Apr2025/GPS_LNA` (NPN/HBT) | Apache-2.0 | 21 (3R+2C+3L+1NM+12NPN) | 4/5 | `lna_sized` (21 > 15 — real layout-level device count: 6 parallel unit fingers per transistor, kept faithful rather than collapsed) | yes, owned-path `to_spice_bjt_ext.py` (see §3) | **yes**, clean |
| `align-lna-qm` | ALIGN `CircuitsDatabase/.../LNA` | BSD-3-Clause | 19 (12R+5C+2M) | 2/5 | `has_inductor`, `inductor_ratio` (the excerpt's one inductor, L0, was a disconnected orphan within this file and was dropped — documented in provenance), `lna_sized` (19 > 15) | yes, `to_spice.py` | **yes**, clean |

All three: `valid_structure = True`, zero floating devices after the documented edits, zero
ngspice errors (only the same benign BSIM4 parameter warnings the existing 41-circuit corpus
already produces). Full JSON: `lna/data/external/_tools/convert_results.json`. Per-circuit
provenance, cleaned inputs, generated `.cir`/`Graph`/`Port`/token-sequence/sim logs live under
`lna/data/external/<name>/`.

The `align-lna-qm` score of 2/5 is a **real, honest finding, not a conversion defect**: it is
an inductorless, resistively-loaded differential LNA core — a genuinely different archetype
from the single-ended, inductively-matched style that dominates both the existing 41-circuit
corpus and the two IHP siblings. `FINDINGS.md` already documents that ~40% of the *existing*
real LNA subset misses the inductor criteria for the same reason (common-gate/resistive-
feedback designs); this is more of the same, correctly characterized rather than filtered out.

---

## 5. Answering the brief directly

- **Top 3 sources, with counts and effort:**
  1. **IHP-GmbH SG13G2 tapeouts** (Apache-2.0) — 8 real LNA folders spotted, 2 converted
     today (low effort, flat netlist ready), 6 more identified needing a one-time
     xschem/Qucs-S coordinate-parsing tool (medium effort once, low effort per circuit after),
     plus an ongoing stream of new campaigns.
  2. **ALIGN CircuitsDatabase** (BSD-3) — 1 real LNA, converted today, source now exhausted.
  3. **Hand-transcribed classic archetypes** — unbounded but manual (~30-60 min/topology,
     not "real" ground truth), kept as low-priority insurance.
- **Total realistic new-LNA yield:** **3 real circuits already converted, screened, and
  simulated this session** (raising the real-LNA pool from 41 toward 44 once ingested), with a
  **credible near-term path to ~6 more from IHP alone** (≈22% growth from what's already been
  scoped, before counting future IHP campaigns).
- **What was converted, and whether it simulated:** all three attempted conversions
  (`ihp-gps-lna-nmos`, `ihp-gps-lna-npn`, `align-lna-qm`) — all three simulated cleanly in
  ngspice with zero errors.
- **Single best next ingestion step (as of the first pass):** build a small xschem-symbol
  pin-offset table for IHP's `sg13g2_pr` library and use it to flatten the identified-but-
  unconverted IHP LNA schematics into netlists. **Done in the follow-on session below.**

---

## 6. Follow-on session (same day): xschem flattener + paper transcriptions

Continuation requested by the coordinator: (1) build the xschem schematic flattener
recommended in §5, harvest the remaining identified IHP LNA schematics with it; (2) add a
paper-transcription track for topology families the corpus lacks (noise-cancelling,
current-reuse, transformer-feedback, gm-boosted CG). Same rules as the first pass: own only
`lna/data/external/**` + this report, no shared `.py` edits (including `lna/to_spice.py` —
still using the owned-path NPN extension script for anything it can't emit), ≤1 concurrent
ngspice process, never push, blind protocol unchanged.

### 6.1 The xschem flattener

**Built:** `lna/data/external/_tools/xschem_flatten.py`. Parses `.sym` symbol-library files
(pin geometry from `B 5 x1 y1 x2 y2 {name=... }` boxes, device kind from `K {type=...}`),
parses `.sch` schematics (wires `N x1 y1 x2 y2 {lab=...}`, component instances
`C {symbol} X Y ROT FLIP {props}`), applies xschem's placement rotation/mirror transform, and
reconstructs electrical nets from raw geometry via a coordinate union-find (does **not** trust
the schematic's own `lab=` text at face value — a wire's label is only used, as a preference,
once the union-find has already independently established which points are electrically the
same). Emits a flat SPICE deck that feeds straight into the existing `spice2genie.py` →
upstream graph/augmentation → `lna/topology.py` → `lna/to_spice.py` pipeline.

**The rotation/mirror transform was derived empirically, not from documentation memory alone.**
`lna/data/external/_tools/_calibrate_xschem_transform.py` is the one-off script that found it:
seeded with xschem's own `ROTATION` macro from `src/xschem.h` (fetched directly from
`StefanSchippers/xschem`) as a starting hypothesis, then checked against the GPS_LNA testbench
schematic (whose correct netlist was already known from the first pass's flat-SPICE
conversion) by brute-force partition matching — grouping which device pins the transform says
share a net, and comparing that grouping to the known-correct one. The verified formula:

```
flip=0: rot 0,1,2,3 -> (x,y), (-y,x), (-x,-y), (y,-x)
flip=1: rot 0,1,2,3 -> (-x,y), (-y,-x), (x,-y), (y,x)
absolute = instance placement (X,Y) + the above, applied to each pin's local coordinate
```

**Golden test — PASS.** `python lna/data/external/_tools/xschem_flatten.py --selftest`
fetches `GPS_LNA`'s xschem testbench schematic (`design_data/xyce/lna_tb_xyce_rf_rfmos.sch`,
the *raw graphical source*, not the already-flattened `.spice` export used in the first pass),
flattens it from scratch, and checks the result against the already-independently-converted,
screened (5/5), simulated `ihp-gps-lna-nmos` circuit:

| Check | Result |
|---|---|
| Device composition | 3 resistor, 3 inductor, 2 capacitor, 3 nmos4 — **exact match** |
| Padframe/ESD auto-excluded (via symbol `K{type=pad\|diode\|vsource}`, no manual stripping needed this time) | 4 bondpads + 8 ESD diodes + 2 voltage sources dropped, matching the hand-stripped count from the first pass |
| Ports | `VDD VSS VIN1 VOUT1` — match |
| Structural screen | **5/5**, criteria identical to the first-pass conversion |

This is a from-scratch reproduction of an already-verified result via a completely different
(and much harder) input format, which is what makes it a real golden test rather than a
tautology.

**One real bug found and fixed during calibration**, worth recording: symbol pin-order
assumptions cannot be hardcoded by name across device families — `rppd`/`rsil` resistors use
pins `P`/`M`, the generic `ind.sym` inductor uses lowercase `p`/`m`, project-local
`simple_inductor.sym` uses `LA`/`LB`, `cap_rfcmim` uses `c0`/`c1` (+ a `bn` body pin to drop).
The flattener does not hardcode any of these strings for 2-terminal passives — it takes each
symbol's pins in **declaration order**, drops anything named like a body/substrate terminal
(`bn`, `b`, `sub`, `body`), and keeps the first two. Multi-terminal actives (MOS/BJT) still use
named lookup (`D`/`G`/`S`/`B`, `C`/`B`/`E`) since those need real identity, not just count.

### 6.2 Harvest results — remaining IHP schematics

Of the 6 candidates identified in §2 (plus one bonus), only some actually had an xschem
schematic to flatten — the rest turned out, on inspection this session, to be genuinely
unreachable with this tool, not just unconverted:

| Candidate | Campaign | Format available | Outcome |
|---|---|---|---|
| **`LNA_2.45G`** | TO_May2025 | `xschem/circuit_lvs.sch` | **Converted.** See table below. |
| `160GHz_LNA` | TO_Apr2025 | `qucs-s` + `openems` only, no `xschem` | Not reachable — different schematic format (Qucs-S), needs a separate parser. |
| `Cascode_160GHz_LNA` | TO_May2025 | `qucs-s` + `openems` only | Same as above. |
| `207GHZ_LNA` | TO_May2025 | `qucs-s` + `openems` only | Same as above. |
| `LNA_24GHz` | TO_Dec2023 | `design_data/` and `val/` contain only a `README.md`, no schematic/netlist files exposed | Dead end — nothing to harvest. |
| `Y0_openSource_LNA` | TO_Dec2023 | same as above | Dead end. |
| `RF_amplifiers` (bonus, not in the original 6) | TO_Dec2024 | `xschem/amplifiers/*.sch` | **Checked, not pursued.** Inspecting `amplifiers_TB_xyce.sch` shows a *hierarchical* testbench (instantiates a `hamp.sch` sub-schematic via a dynamic `tcleval(...)` path — hierarchy the flattener deliberately does not support, see its docstring) built from baseband-style testbench primitives (`vcvs.sym`, `isource.sym`, `ammeter.sym`) with no RF port/S-parameter structure and no inductors visible — low confidence this is actually an LNA rather than a gain-block/driver-amp characterization ("H_DiFF_15dB", "H_SiNGLE" naming suggests transfer-function gain blocks). Judgment call: not worth building hierarchy support for a topically-uncertain circuit when 5 higher-confidence sources were already exhausted. |

**New conversion this session:**

| Circuit | Devices | Score /5 | Missed criteria | ngspice |
|---|---|---|---|---|
| `ihp-lna-2p45g` (2.45 GHz ISM-band cascode LNA, from raw xschem schematic) | 18 (2R+9C+4NM+3L) | **4/5** | `lna_sized` (18 > 15, mostly from 5 realistic VDD-VSS decoupling caps) | clean, S11min=-0.82dB, S21max=-46.1dB (unsized) |

One structural oddity kept as-found rather than "fixed": one transistor (`MMn3`) has all four
pins landing on VSS — independently geometry-verified against real wire endpoints like every
other device, plausibly a real dummy/layout-matching transistor rather than a parser artifact.
Documented in `lna/data/external/ihp-lna-2p45g/provenance.json` for user review.

### 6.3 Paper transcription track

Five canonical LNA topology families, covering exactly the families named in the brief
(noise-cancelling, current-reuse, transformer-feedback, gm-boosted CG) plus one bonus
(differential capacitor cross-coupled CG — the only *differential* circuit in this batch,
adding a structural family the corpus/reference set otherwise lacks). Each is authored
directly in AnalogGenie's native device format (not parsed from an external file — there was
no netlist to parse, only a paper description), cited to a real paper, and run through the
identical validation pipeline as every other circuit in this project. None derive from, cite,
or resemble the excluded Kanchetla et al. TMTT 2022 paper — all five cited papers predate it
by years to decades or address unrelated applications (ultrasound front-ends, WLAN/UWB
receivers, general LNA methodology), and the actual excluded paper was never looked up.

| Circuit | Family | Cited paper | Score /5 | Confidence | ngspice |
|---|---|---|---|---|---|
| `paper_noisecancel` | Feedforward noise-cancelling, resistive shunt-feedback | Tang et al., *Sensors* 2021, DOI 10.3390/s21248476 (open access, PMC) | 3/5 — correctly inductorless | MEDIUM | clean, **S21=+2.4dB** (only unsized transcription with net gain) |
| `paper_currentreuse` | Current-reuse (DC-stacked 2-stage) | Reddy & Nath, *Scientific Reports* 2025, DOI 10.1038/s41598-025-93530-3 (open access) | 5/5 | MEDIUM-HIGH | clean |
| `paper_gmboostcg` | gm-boosted common-gate | Li, Shekhar & Allstot, IEEE JSSC Dec 2005 (PDF not machine-readable — image-based) | 5/5 | MEDIUM | clean |
| `paper_transformerfb` | Transformer-feedback | Wu, Leung & Luong, IEEE TCAS-I 2017 (paywalled, cited by metadata only) | 5/5 | MEDIUM | clean |
| `paper_diffcccg` | Differential capacitor cross-coupled CG | Zhuo et al., IEEE TCAS-II 2005 (seminal/well-known paper, not independently re-fetched this session) | 5/5 | MEDIUM-HIGH (topology) / MEDIUM-LOW (exact citation) | clean |

**One bug caught by the pipeline itself, not by inspection:** `paper_noisecancel`'s first draft
used bare `IN`/`OUT` net names instead of the port-declared `VIN1`/`VOUT1`, so the structural
screen correctly flagged `has_rf_ports: false` (score 2/5) even though the topology was
otherwise fine — exactly the kind of authoring slip the screen exists to catch. Fixed and
re-verified (3/5, the expected score for a genuinely inductorless design).

Every `provenance.json` in this batch carries a `transcription_confidence` field explaining
precisely what came from the cited paper (title/authors/DOI/URL, retrieval date, and what text
was actually readable via the fetch tools) versus what is general, well-established circuit
theory for that named topology family — none are marked `quarantine: true` (all five passed
the structural screen and simulated cleanly), but every one discloses its simplifications and
uncertainties explicitly rather than presenting a paper-exact reproduction that wasn't
actually verified against a readable schematic.

### 6.4 Updated corpus yield

| | Count |
|---|---|
| Real LNAs before this project's involvement | 41 |
| Converted in the first pass (§4) | +3 (`ihp-gps-lna-nmos`, `ihp-gps-lna-npn`, `align-lna-qm`) |
| Converted this follow-on session | +1 IHP (`ihp-lna-2p45g`) + 5 paper transcriptions |
| **Running total, screened + simulated this project** | **9** |
| **Potential corpus size if all ingested** | **41 + 9 = 50** |

All 9 have `valid_structure: true`, zero floating devices, and a clean (zero-error) ngspice
`op` + `sp` + `noise` run; scores range 2/5–5/5, every score explained by genuine topology
characteristics (inductorless-by-design, oversized-by-real-layout-practice, etc.) rather than
conversion defects — consistent with `lna/FINDINGS.md`'s own finding that ~40% of the
*existing* real corpus misses the inductor criteria for the same legitimate reasons.

### 6.5 Best next step (updated)

**Build a Qucs-S schematic parser.** With the xschem side now handled, the single largest
remaining blocker is the 3 IHP mmWave LNAs (`160GHz_LNA`, `Cascode_160GHz_LNA`, `207GHZ_LNA`)
sitting behind Qucs-S's `.sch` format instead of xschem's — same "real, licensed, already
identified" argument as before applies again: the source, license, and circuit identity are
already confirmed, only the geometry parser is missing. Second priority: track IHP's tapeout
campaigns after `TO_Sep2025` for new LNA submissions (this source is demonstrably renewable —
LNA folders appeared in 4 of 7 campaigns checked across two sessions).

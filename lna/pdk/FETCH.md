# PDK fetch plan (v0) -- APPROVAL REQUIRED before any download

This is the plan to take to the user before fetching any PDK content. Nothing in
this wave downloaded anything: the URLs, licenses, and sizes below were verified
**read-only** (curl HEAD / GitHub API), and the staged adapters
(`lna/pdk/{sky130,ihp_sg13g2,gf180mcu}.py`) raise `NotImplementedError` pointing
here until the files land.

House rules honored: no installs, network read-only, minimal file subset
(primitive device models only, NOT the full PDK), landing under a gitignored box
path and/or a Kaggle dataset for the worker.

Verification date: 2026-08-26 (this box, read-only curl + api.github.com).

---

## Per-PDK fetch table (all verified HTTP 200, all Apache-2.0)

### 1. IHP SG13G2 -- 130 nm SiGe BiCMOS  (RECOMMENDED FIRST -- highest RF value)

| field | value |
|---|---|
| upstream repo | https://github.com/IHP-GmbH/IHP-Open-PDK |
| HTTP status | 200 (verified) |
| license | Apache-2.0 (verified via api.github.com spdx_id) |
| full repo size | ~453 MB (452849 KB) -- do NOT clone whole |
| default branch | `main` |

**Minimal file subset for ngspice** (all verified present at
`ihp-sg13g2/libs.tech/ngspice/models/`):
- `sg13g2_moslv_mod.lib` -- `sg13_lv_nmos` / `sg13_lv_pmos` PSP-103 core MOS
- `cornerMOSlv.lib` -- MOS lv corner selector (`.lib ... mos_tt`)
- `sg13g2_hbt_mod.lib` -- `npn13G2` SiGe HBT (HICUM/L2)
- `cornerHBT.lib` -- HBT corner selector (`.lib ... hbt_tt`)
- (optional for R/C/L primitives: `resistors_mod.lib`, `capacitors_mod.lib`,
  `diodes.lib` -- same dir, all verified present)

**OSDI / OpenVAF compile step (load-bearing):** SG13G2's PSP MOS and HICUM/L2
HBT are Verilog-A compact models. ngspice runs them via OSDI; ngspice-47 on this
box HAS OSDI (verified: `ngspice --version` reports the KLU build, OSDI is a
standard build-in). The `.va` sources (repo `ihp-sg13g2/libs.tech/verilog-a/`)
must be compiled to `.osdi` with OpenVAF, then loaded with `pre_osdi <x>.osdi`
before the device cards. Recipe:
```
openvaf psp103_nqs.va          # -> psp103_nqs.osdi
openvaf hicumL2.va             # -> hicumL2.osdi
# then in the deck:  pre_osdi <root>/psp103_nqs.osdi ; pre_osdi <root>/hicumL2.osdi
```
OpenVAF itself is a separate prebuilt binary (NOT to be installed without
approval); it is the one extra tool IHP needs over the other two PDKs.

**sha256 / exact sizes:** TODO -- filled after the approved fetch (the adapter's
`expected_files` manifest carries the same TODO slots).

---

### 2. sky130 -- SkyWater 130 nm  (MOST battle-tested with ngspice)

| field | value |
|---|---|
| upstream repo (top) | https://github.com/google/skywater-pdk |
| primitive-device repo | https://github.com/efabless/skywater-pdk-libs-sky130_fd_pr |
| HTTP status | 200 / 200 (both verified) |
| license | Apache-2.0 (both, verified spdx_id) |
| sizes | skywater-pdk ~4.3 MB; sky130_fd_pr ~122 MB (do NOT clone whole) |
| default branch | `main` (both) |

The device models the harness needs are the ngspice-format `.spice` corner files
that `open_pdks` assembles into `sky130A/libs.tech/ngspice/`. The primitive
sources live in the efabless `sky130_fd_pr` repo (verified: `models/` and
`cells/nfet_01v8` both HTTP 200). Minimal subset (the compiled/assembled form):
- `sky130.lib.spice` -- corner selector; deck emits `.lib .../sky130.lib.spice tt`
- `sky130_fd_pr__nfet_01v8__tt.corner.spice` -- nfet_01v8 tt subckt
- `sky130_fd_pr__pfet_01v8__tt.corner.spice` -- pfet_01v8 tt subckt

Primitive FETs are **subcircuits** (`sky130_fd_pr__nfet_01v8` / `pfet_01v8`), so
the adapter emits `X` calls (already implemented in `sky130.py`). 1.8 V core.
No OSDI needed (BSIM4-based). **sha256 / sizes: TODO.**

Note: the cleanest single source is the `open_pdks`-built `sky130A` tree; the
fetch may take the pre-built ngspice corner files rather than assembling from
`sky130_fd_pr` sources. Decide at fetch time; both are Apache-2.0.

---

### 3. GF180MCU -- GlobalFoundries 180 nm  (EASIEST, least RF)

| field | value |
|---|---|
| upstream repo | https://github.com/google/gf180mcu-pdk |
| HTTP status | 200 (verified) |
| license | Apache-2.0 (verified spdx_id) |
| full repo size | ~54 MB (53773 KB) |
| default branch | `main` |

Minimal subset (ngspice models under
`libraries/gf180mcu_fd_pr/latest/models/ngspice/`):
- `design.ngspice` -- top include (selects the typical corner)
- `sm141064.ngspice` (or the current leaf name) -- `nfet_03v3` / `pfet_03v3`
  device subckts

**VERIFY-ON-FETCH:** the repo's `latest` is a git **symlink** the read-only
GitHub contents API does not traverse, so the exact leaf file names under
`.../latest/models/ngspice/` could not be enumerated read-only and must be
confirmed at fetch time. `libraries/gf180mcu_fd_pr` and `.../latest` were both
verified HTTP 200. Primitive FETs are subcircuits -> `X` calls (implemented).
3.3 V core, no OSDI. **sha256 / sizes: TODO.**

---

## Where the files land (proposal)

1. **Box-side, gitignored:** `.env/pdks/<name>/` under the repo root (the same
   `.env/` that already holds the ngspice-47 build). Add `.env/pdks/` to
   `.gitignore`. The adapters resolve the root via an env override
   `LNA_PDK_ROOT` (to be added when the fetch is approved), mirroring how
   `extract.resolve_models` walks `LNA_DEPS_ROOT`.
2. **Kaggle dataset for the worker:** a private Kaggle dataset `pdks-min-<name>`
   carrying the same minimal subset, so a Kaggle kernel worker has the models
   without a box mount. (Out of this wave's zone -- kaggle/ is another agent's;
   this only records the proposal.)

## Adapter wiring once files exist (not done this wave)

Each staged adapter's `model_includes()` currently raises. On fetch:
- point `LNA_PDK_ROOT` at the landing dir,
- implement `model_includes()` to emit the `.lib`/`.include`/`pre_osdi` lines
  listed above, resolved under `LNA_PDK_ROOT`,
- fill the `expected_files` `sha256`/`size_bytes` TODOs,
- for IHP, also wire the real `npn13G2` into `bjt_models()` (a to_spice bipolar
  emission change, gated on the `.lib` existing).

Then add a per-PDK smoke golden (a trivial single-transistor `gm`/`ft` check,
same shape as `lna/ref/check_bjt.py`) before any design number on that PDK.

---

## Survey: other open PDKs found (verified read-only)

| PDK | repo | status | RF suitability | ngspice compat | verdict |
|---|---|---|---|---|---|
| **ASAP7** | github.com/The-OpenROAD-Project/asap7 | 200, **BSD-3-Clause** | 7 nm FinFET predictive; excellent fT | models are BSIM-CMG (FinFET) -- ngspice supports BSIM-CMG, but ASAP7 ships for HSPICE/Spectre and needs porting | Academic predictive kit, NOT a foundry PDK; good fT but no real RF passives/inductors and no silicon backing. Low priority for this harness (predictive, not measurable-truth). |
| **FreePDK45** | (NCSU, not a single canonical GitHub; mirrors exist) | mirror probed 404 | 45 nm predictive; same class as the harness's current BPTM 45 nm | BSIM4, ngspice-loadable | Predictive academic kit -- essentially the same technology node the harness ALREADY uses (BPTM 45 nm). No new RF value; skip. |
| **SG13G2 (IHP)** | (item 1 above) | 200, Apache-2.0 | **best** -- real SiGe HBT, RF passives | ngspice via OSDI (have it) | already the recommended first. |

Notes:
- The three foundry-open PDKs with real silicon backing AND ngspice model
  packaging are exactly sky130 / gf180mcu / IHP SG13G2 -- there is no fourth
  open *foundry* PDK with comparable ngspice support as of this survey.
- ASAP7/FreePDK are *predictive* (no fab), so they cannot serve the house
  "measurement-first, closed-form-golden vs silicon-class-model" discipline any
  better than the current BPTM 45 nm card already does; they are recorded for
  completeness, not recommended.

## Rollout order recommendation

1. **IHP SG13G2** -- highest RF value (SiGe HBT), and the corpus already carries
   ingested IHP circuits, so it closes the ingested-topology -> real-model loop.
   Cost: the OpenVAF/OSDI compile step.
2. **sky130** -- most battle-tested with ngspice, no OSDI; safest second.
3. **gf180mcu** -- easiest to bring up (no OSDI, simple includes) but least RF
   (180 nm); last.

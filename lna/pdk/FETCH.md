# PDK fetch plan + manifest -- FETCHED (user-approved 2026-08-27)

The three staged open-source PDK adapters (`sky130`, `ihp_sg13g2`, `gf180mcu`)
are now ACTIVE. Model files were fetched under the gitignored box tree
`<repo-root>/.env/pdks/<name>/`, the IHP PSP MOS Verilog-A was compiled to OSDI
with OpenVAF, and each PDK has a per-device ngspice smoke that passes
(`lna/ref/check_pdk_live.py`). User approval (2026-08-27): "I'll give pdk
permissions for all three in both" (box + Kaggle) incl. the OpenVAF compiler.

House rules honored: no system installs, minimal file subsets (primitive device
models only, NOT full PDKs), landing under the gitignored `.env/` tree +
private Kaggle datasets for the worker.

Verification/fetch date: 2026-08-27 (this RHEL8 box, ngspice-47).

---

## RESOLUTION (how adapters find the models)

`lna/pdk/__init__.pdk_root(name)` walks, nearest-first (mirrors
`extract._dep_roots`):
1. `$LNA_PDK_ROOT` (a dir that directly holds `<name>/` subdirs -- the Kaggle
   worker points this at its dataset mount),
2. `$LNA_DEPS_ROOT/.env/pdks`,
3. this checkout's `.env/pdks`,
4. the git-common-dir parent's `.env/pdks` (the MAIN checkout, from a worktree),
5. ancestors' `.env/pdks`.

First candidate that contains `<name>/` wins; None -> the adapter's
`model_includes()` raises a FETCH.md-naming NotImplementedError, so a clone with
no `.env/pdks/` stays honest (and the live smoke skips-with-note).

---

## Per-PDK manifest (all Apache-2.0 upstream; sha256 + byte size verified)

### 1. sky130 -- SkyWater 130 nm  (FETCHED)

- upstream: `efabless/skywater-pdk-libs-sky130_fd_pr` @ **1232782c1b9fab3aacda74d67ce7c92bf7da8105**
- box path: `.env/pdks/sky130/sky130_fd_pr/`  (dir total ~20 MB)
- device: `sky130_fd_pr__nfet_01v8` / `pfet_01v8` (1.8 V core, X-subckt).
  **W/L in METRES** (BSIM4 binned: bins run 0.15 um .. 100 um).
- corner selector: a NEW thin wrapper `models/sky130.lib.min.spice` (section
  `tt`) that includes ONLY the two 1.8 V core FET cells -- the stock
  `sky130.lib.spice` pulls in all ~30 device cells (nfet_03v3_nvt, npn, RF
  passives ...) which were not fetched. Each `*__tt.pm3.spice` carries the full
  `.subckt` + BSIM4 `.model` cards self-contained (verified: no further
  `.include`). No OSDI (BSIM4).

| file | sha256 | bytes |
|---|---|---|
| `sky130_fd_pr/models/sky130.lib.min.spice` (NEW wrapper) | `6bfa6e4b4ed34dbc6933433f398ff682e6055cce1f142b8acb1f58c241824865` | 1334 |
| `sky130_fd_pr/cells/nfet_01v8/sky130_fd_pr__nfet_01v8__tt.pm3.spice` | `459eca963a134574cf7c842ad6d3814e7e0752bfb5de8e581c2f483534b5ad06` | 1137294 |
| `sky130_fd_pr/cells/nfet_01v8/sky130_fd_pr__nfet_01v8__mismatch.corner.spice` | `24a3b29d7d7f26f99098811c31eb5497950a3aed520ab83768a96f35467fe818` | 962 |
| `sky130_fd_pr/cells/pfet_01v8/sky130_fd_pr__pfet_01v8__tt.pm3.spice` | `c943246ce012ea3db2777e3f4633ddccdfee7c8f1bf4dca79af9f7ff17b3d51f` | 809553 |
| `sky130_fd_pr/cells/pfet_01v8/sky130_fd_pr__pfet_01v8__mismatch.corner.spice` | `f4d560668712678ea60641de923fce7691e64acda951949f840986837c31741a` | 1322 |

(the fetch also kept the small `models/` support subtree -- r+c, parameters,
corners -- so any r+c parasitic `.include` inside a corner variant resolves.)

### 2. gf180mcu -- GlobalFoundries 180 nm MCU  (FETCHED)

- upstream: `google/globalfoundries-pdk-libs-gf180mcu_fd_pr` @ **9f992d5a9186d1f7820c58f039c484ad35b2edea**
- box path: `.env/pdks/gf180mcu/models/ngspice/`  (dir ~1.4 MB)
- device: `nmos_3p3` / `pmos_3p3` (3.3 V core, X-subckt, `nf` param). **W/L in
  METRES.** No OSDI (BSIM3v3).
- include order: `.include design.ngspice` (switches) THEN `.lib
  sm141064.ngspice typical`.

| file | sha256 | bytes |
|---|---|---|
| `models/ngspice/design.ngspice` | `8d9721a5bf8f079d3fddbd03339af9a0c84d4feb06db8e06465fbd02c7500508` | 3249 |
| `models/ngspice/sm141064.ngspice` | `73fc67d38747d95ce03f3c2ba5f0a25c98f56a293363a9df4c971a3a28a3dcda` | 1348553 |
| `models/ngspice/smbb000149.ngspice` | `3b0995ba269b6cbc468f34fe977c4d21b0faa2935e02f4b2a5d24f58ea66affe` | 31347 |

### 3. IHP SG13G2 -- 130 nm SiGe BiCMOS  (FETCHED + OSDI compiled)

- upstream: `IHP-GmbH/IHP-Open-PDK` @ **331c00484213b13414777eec1336ef5c29b969bd**
- box path: `.env/pdks/ihp_sg13g2/libs.tech/`  (dir ~2.8 MB incl. compiled OSDI)
- devices:
  - MOS `sg13_lv_nmos` / `sg13_lv_pmos` (PSP-103, X-subckt, `ng` finger param).
    **W/L in METRES**, 130 nm core. Needs OSDI (`psp103va`/`pspnqs103va`).
  - HBT `npn13G2` SiGe (`c b e bn`). **Native ngspice VBIC (`.model ... npn`) --
    NO OSDI.**
- include: `.lib cornerMOSlv.lib mos_tt` + `.lib cornerHBT.lib hbt_typ`.
- OSDI load order (IMPORTANT): an `.osdi` is binary -- it cannot be `.include`d,
  and the `osdi <file>` command must run BEFORE the netlist is parsed (else the
  `psp103va`/`pspnqs103va` model types are unknown when the `.model` cards read).
  Working ngspice-47 batch pattern: `.control` block that runs `osdi <file>`
  first, then `source <netlist>`, then the analysis. The adapter exposes the
  osdi paths via `IhpSg13g2Adapter.osdi_files()` (separate from
  `model_includes()` which returns only the `.lib` lines); the live smoke drives
  ngspice this way.

| file | sha256 | bytes |
|---|---|---|
| `libs.tech/ngspice/models/cornerMOSlv.lib` | `03d505847c880d233b341be115a1e5460edf4d8e9b3e8a7df791a52fa4455d67` | 21645 |
| `libs.tech/ngspice/models/sg13g2_moslv_mod.lib` | `84ec57080b9dd4666417f05db6f7b34c8dd3f12118929f9b308018613bece16e` | 10452 |
| `libs.tech/ngspice/models/sg13g2_moslv_parm.lib` | `cbf10b8453a18bb70b8ad0d6e40faa0937338e699b5460947a94900db6c92a6e` | 94408 |
| `libs.tech/ngspice/models/cornerHBT.lib` | `bae3d705445de8d6b8de4aa798a0e3e5e7cab617d6495d9c56473bc5377de462` | 3975 |
| `libs.tech/ngspice/models/sg13g2_hbt_mod.lib` | `ae9288f885dd30fab24b07ed1e7e02e69eac9154022a0a6da576985183b0bd79` | 20057 |
| `libs.tech/ngspice/osdi/psp103.osdi` (compiled) | `8f482e761c450609c9255eb20b83978db6799450fa3cc7ae2e1dc6ca247ee61d` | 730712 |
| `libs.tech/ngspice/osdi/psp103_nqs.osdi` (compiled) | `c42217715d6bd0abba42f83ad6f657700f02d185aad502a9426641261404c9dd` | 1047568 |

(the full `libs.tech/ngspice/models/` dir + the `libs.tech/verilog-a/psp103/`
source subtree were also kept so the cross-`.include`s resolve and the OSDI can
be recompiled.)

---

## OpenVAF (the one extra tool IHP needs)

- **Working binary:** OpenVAF **23.5.0** from the official openvaf.dev CDN
  (`https://openva.fra1.cdn.digitaloceanspaces.com/openvaf_23_5_0_linux_amd64.tar.gz`),
  a STATICALLY-bundled-LLVM build targeting GLIBC 2.6.32 -- runs on RHEL8
  (glibc 2.28). Placed at `.env/tools/openvaf/openvaf`.
  sha256 `6918195bc6cca54016095923bea190f7a1d96dd8b062104c602e8c28578cb5e3`,
  221692776 bytes.
- **Rejected:** `OpenVAF/OpenVAF-Reloaded` v24.0.2mob linux-x86_64 (`openvaf-r`,
  the compiler the IHP `openvaf-compile-va.sh` prefers) does NOT run on this box:
  it dynamically links `libLLVM.so.18.1` AND needs GLIBC up to 2.39 (RHEL8 has
  2.28). Verbatim: `libc.so.6: version 'GLIBC_2.39' not found`. Deleted.
- **Compile recipe used** (from IHP `libs.tech/verilog-a/openvaf-compile-va.sh`):
  ```
  openvaf -D__NGSPICE__ -o psp103.osdi      psp103/psp103.va       # -> Finished 2.15s
  openvaf -D__NGSPICE__ -o psp103_nqs.osdi  psp103/psp103_nqs.va   # -> Finished 4.79s
  ```
  Both compiled clean (exit 0). OSDI module names registered: `PSP103VA`,
  `PSPNQS103VA` (match the parm-lib `.model` type names, case-insensitive).
  ngspice-47 on this box has OSDI (`osdi_enabled`, `pre_osdi` symbols in the
  binary). The HICUM/L2 HBT compile the earlier plan called for is NOT needed
  (see contradiction #2).

---

## Live smoke results (`lna/ref/check_pdk_live.py`, 2026-08-27, all GREEN)

Trivial common-source NMOS amp per PDK: op + ac, assert device conducts (real
Id) AND |Av| > 0 dB at LF AND no ngspice model-loading error in the log:

| PDK | device | V(d) | Id | \|Av\|@LF | verdict |
|---|---|---|---|---|---|
| sky130 | `sky130_fd_pr__nfet_01v8` (W=5u L=0.15u) | 0.706 V | 0.219 mA | 14.93 dB | ok |
| gf180mcu | `nmos_3p3` (W=10u L=0.28u) | 0.477 V | 0.565 mA | 9.83 dB | ok |
| ihp_sg13g2 | `sg13_lv_nmos` (W=10u L=0.13u ng=4) | 0.401 V | 0.110 mA | 16.87 dB | ok |
| ihp_sg13g2 | `npn13G2` SiGe HBT (Vbe=0.85 V) | Vc=0.866 V | Ic=0.567 mA | (conducts) | ok |

`check_pdk.py` (static wiring golden) GREEN before + after; `check_ref.py`
GREEN before + after (bptm45 default path byte-identical, untouched).

---

## Kaggle datasets (private, `devavratpatni/`)

| dataset ref | contents | extracted layout (Kaggle AUTO-EXTRACTS the .tar.gz) |
|---|---|---|
| `devavratpatni/circuit-repro-pdk-sky130` | `circuit-repro-pdk-sky130.tar.gz` | `sky130/sky130_fd_pr/...` |
| `devavratpatni/circuit-repro-pdk-gf180mcu` | `circuit-repro-pdk-gf180mcu.tar.gz` | `gf180mcu/models/ngspice/...` |
| `devavratpatni/circuit-repro-pdk-ihp-sg13g2` | `circuit-repro-pdk-ihp-sg13g2.tar.gz` + `openvaf-23.5.0-linux-amd64-static` (raw, 211 MB, for reproducibility) | `ihp_sg13g2/libs.tech/...` (incl. compiled `osdi/`) + the raw `openvaf-*-static` binary at the dataset root |

**Worker bootstrap note:** Kaggle un-tars each archive on ingest, so the mount
holds the top dir (`sky130/`, `gf180mcu/`, `ihp_sg13g2/`) directly. Point
`LNA_PDK_ROOT` at the parent that contains those dirs. If the three datasets are
mounted at distinct paths (`/kaggle/input/circuit-repro-pdk-sky130/` etc.), set
`LNA_PDK_ROOT` per-PDK or symlink them into one root -- `pdk_root(name)` only
needs `<root>/<name>/` to exist. The IHP compiled `.osdi` are already inside the
dataset (`ihp_sg13g2/libs.tech/ngspice/osdi/`), so the worker needs no compile
step; the raw openvaf binary is there only for re-compilation.

---

## THINGS THAT CONTRADICTED THE ORIGINAL (v0) PLAN

1. **gf180 `latest` is a git SUBMODULE, not a symlink, and the device names are
   `nmos_3p3`/`pmos_3p3` not `nfet_03v3`/`pfet_03v3`.** The ngspice models are
   NOT in `google/gf180mcu-pdk` at all -- that repo's
   `libraries/gf180mcu_fd_pr/latest` is a submodule pointing at
   `google/globalfoundries-pdk-libs-gf180mcu_fd_pr`, whose
   `models/ngspice/{design,sm141064}.ngspice` hold the real subckts
   `nmos_3p3`/`pmos_3p3`. Adapter `MOS_SUBCKT` corrected.

2. **IHP `npn13G2` is a native ngspice VBIC card, NOT HICUM/L2 via OSDI.** The
   v0 plan (and the adapter docstring) said the HBT needed a `hicumL2.osdi`
   compile. It does not: `sg13g2_hbt_mod.lib` defines `.model npn13G2_NX_vbic
   npn` -- ngspice's built-in VBIC. No OpenVAF step for the HBT. Only the PSP
   MOS needs OSDI.

3. **git-over-HTTPS is unavailable on this box** (the Xilinx-bundled git has no
   `git-remote-https` helper, and there's no system git). So the fetch used
   `curl` on `codeload.github.com/<repo>/tar.gz/<sha>` full-repo tarballs, pinned
   by commit SHA, then extracted only the needed subtrees. Sparse/shallow clone
   (the v0 preference) was not possible.

4. **The stock sky130 corner selector is unusable in isolation** -- it
   `.include`s ~30 device cells. A trimmed `sky130.lib.min.spice` (the only
   new/authored model file in the fetch) includes just the two 1.8 V FETs.

5. **sky130/gf180/IHP MOS W/L are in METRES** (sky130 BSIM4 bins are keyed on
   metre L; passing bare `0.15` = 0.15 m selects no bin -> "could not find a
   valid modelname"). A spec targeting these PDKs must supply W/L in metres.

## OPEN TODOs / notes for the next wave

- `to_spice` bipolar emission still uses the generic Gummel-Poon `Q<name> C B E
  <model>` for NPN; wiring the REAL `npn13G2` (4-pin `c b e bn`, `X`-subckt)
  into an IHP-specific `bjt_models()`/emission path is a follow-up (the HBT
  smoke instantiates it directly, proving the model loads). `IhpSg13g2Adapter.
  bjt_models()` still returns None.
- The sky130 device_ranges L is pinned at 0.15 um and W/L unit is metres -- a
  sizer driving these PDKs needs its param values in metres (documented, not yet
  enforced in `spec`).
- NF/noise on these foundry devices is untested here (the smoke is op+ac gain
  only), same caveat as extract.py's NF note.

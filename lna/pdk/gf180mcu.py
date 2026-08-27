"""gf180mcu -- GlobalFoundries 180 nm MCU open PDK adapter (STAGED).

The easiest to bring up (bare BSIM `.model`-style includes, no OSDI, no subckt
binning gymnastics) but the least RF-capable of the three: 180 nm, 3.3 V core,
no SiGe. Useful as a low-voltage-headroom-forgiving process for PA-style work.

model_includes() raises NotImplementedError until the model files are fetched
(see lna/pdk/FETCH.md). get_pdk("gf180mcu") still returns this adapter.

DEVICE MAPPING  (from google/gf180mcu-pdk, Apache-2.0)
----------------------------------------------------------------------------
The ngspice models are NOT in the google/gf180mcu-pdk repo itself: that repo
carries `libraries/gf180mcu_fd_pr/latest` as a git SUBMODULE pointing at
google/globalfoundries-pdk-libs-gf180mcu_fd_pr (this is the "latest is a symlink"
note in FETCH.md, now resolved). The device models live at
`<that repo>/models/ngspice/{design.ngspice,sm141064.ngspice}`.

    harness kind   gf180 device     3.3 V core
    ------------   --------------   ----------
    NM             nmos_3p3         NMOS
    PM             pmos_3p3         PMOS

CONTRADICTS the earlier staging: the device subckts are `nmos_3p3` / `pmos_3p3`
(verified in sm141064.ngspice), NOT `nfet_03v3` / `pfet_03v3`. They are
SUBCIRCUITS (wrap the BSIM3v3 core with parasitics), instantiated as `X` calls
with `w`/`l` in METRES and an `nf` finger param. Supply 3.3 V; 6 V flavours
(nmos_6p0) exist, the 3.3 V core is the default. The corner is selected via
`.lib sm141064.ngspice <section>` (section `typical`); `design.ngspice` sets the
Monte-Carlo / flicker switches and must be `.include`d first.

BIPOLAR: gf180 has npn_10p00x10p00 / vpnp devices but they are not RF --
bjt_models() returns None (generic Gummel-Poon fallback).
"""
import os


class Gf180McuAdapter(object):
    name = "gf180mcu"
    vdd = 3.3
    device_ranges = {
        "W": (0.22e-6, 100e-6),
        "L": (0.28e-6, 0.28e-6),    # 3.3 V core min L, pinned
        "R": (50.0, 50e3),
        "C": (1e-15, 20e-12),
        "L_ind": (0.3e-9, 20e-9),
    }
    notes = ("GlobalFoundries 180 nm MCU (Apache-2.0). nfet_03v3/pfet_03v3, "
             "3.3 V core, no SiGe. Easiest to bring up (no OSDI) but least RF "
             "value (180 nm). STAGED: model files not fetched (see FETCH.md).")

    # FETCHED 2026-08-27 (user-approved). Files under
    # <pdk_root>/gf180mcu/models/ngspice/, from
    # google/globalfoundries-pdk-libs-gf180mcu_fd_pr @ 9f992d5a (Apache-2.0).
    DESIGN_REL = "models/ngspice/design.ngspice"
    CORNER_REL = "models/ngspice/sm141064.ngspice"
    CORNER_SECTION = "typical"
    expected_files = [
        {"path": "models/ngspice/design.ngspice",
         "role": "global switch/corner param include (must precede the corner)",
         "sha256": "8d9721a5bf8f079d3fddbd03339af9a0c84d4feb06db8e06465fbd02c7500508",
         "size_bytes": 3249},
        {"path": "models/ngspice/sm141064.ngspice",
         "role": "nmos_3p3/pmos_3p3 (+6V) device subckts; corner selector",
         "sha256": "73fc67d38747d95ce03f3c2ba5f0a25c98f56a293363a9df4c971a3a28a3dcda",
         "size_bytes": 1348553},
    ]

    MOS_SUBCKT = {"NM": "nmos_3p3", "PM": "pmos_3p3"}

    def model_includes(self):
        """`.include design.ngspice` (switches) then `.lib sm141064.ngspice
        typical` (the 3.3 V typical corner). W/L are in METRES."""
        from . import pdk_root
        root = pdk_root(self.name)
        if root is None:
            raise NotImplementedError(
                "gf180mcu model files not fetched -- see lna/pdk/FETCH.md. Once "
                "fetched this returns ['.include <root>/models/ngspice/"
                "design.ngspice', '.lib <root>/models/ngspice/sm141064.ngspice "
                "typical'].")
        design = os.path.join(root, self.DESIGN_REL).replace(os.sep, "/")
        corner = os.path.join(root, self.CORNER_REL).replace(os.sep, "/")
        return [f'.include "{design}"',
                f'.lib "{corner}" {self.CORNER_SECTION}']

    def mos_line(self, name, nd, ng, ns, nb, kind, wexpr, lexpr, fingers_expr):
        """gf180 primitive FET = subcircuit => `X` call; ` NF={...}` -> ` nf={...}`."""
        subckt = self.MOS_SUBCKT[kind]
        nf = fingers_expr.replace(" NF=", " nf=") if fingers_expr else ""
        return (f"X{name} {nd} {ng} {ns} {nb} {subckt} "
                f"w={wexpr} l={lexpr}{nf}")

    def bjt_models(self):
        return None


ADAPTER = Gf180McuAdapter()

"""gf180mcu -- GlobalFoundries 180 nm MCU open PDK adapter (STAGED).

The easiest to bring up (bare BSIM `.model`-style includes, no OSDI, no subckt
binning gymnastics) but the least RF-capable of the three: 180 nm, 3.3 V core,
no SiGe. Useful as a low-voltage-headroom-forgiving process for PA-style work.

model_includes() raises NotImplementedError until the model files are fetched
(see lna/pdk/FETCH.md). get_pdk("gf180mcu") still returns this adapter.

DEVICE MAPPING (from google/gf180mcu-pdk, Apache-2.0; the ngspice models live
under libraries/gf180mcu_fd_pr/latest/models/ngspice/ -- the exact leaf file
names are recorded in FETCH.md as VERIFY-ON-FETCH because the repo's `latest`
is a git symlink the read-only contents API does not traverse)
----------------------------------------------------------------------------
    harness kind   gf180 device     3.3 V core
    ------------   --------------   ----------
    NM             nfet_03v3        NMOS
    PM             pfet_03v3        PMOS

gf180 primitive FETs are SUBCIRCUITS (nfet_03v3 wraps the BSIM core with
parasitics), instantiated as `X` calls with W/L/nf in metres -- same shape as
sky130. Supply 3.3 V. 5 V flavours (nfet_05v0) exist; the 3.3 V core is the
default RF/analog device.

BIPOLAR: gf180 has npn_10p00x10p00 / vpnp devices but they are not RF --
bjt_models() returns None (generic Gummel-Poon fallback).
"""


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

    expected_files = [
        {"path": "libraries/gf180mcu_fd_pr/latest/models/ngspice/design.ngspice",
         "role": "top include (selects sm141064 typical corner)",
         "sha256": "TODO", "size_bytes": "TODO"},
        {"path": "libraries/gf180mcu_fd_pr/latest/models/ngspice/sm141064.ngspice",
         "role": "nfet_03v3/pfet_03v3 device subckts",
         "sha256": "TODO", "size_bytes": "TODO",
         "note": "leaf names VERIFY-ON-FETCH (latest is a git symlink)"},
    ]

    MOS_SUBCKT = {"NM": "nfet_03v3", "PM": "pfet_03v3"}

    def model_includes(self):
        raise NotImplementedError(
            "gf180mcu model files not fetched -- see lna/pdk/FETCH.md. Once "
            "fetched this returns e.g. ['.include "
            "<root>/libraries/gf180mcu_fd_pr/latest/models/ngspice/"
            "design.ngspice'].")

    def mos_line(self, name, nd, ng, ns, nb, kind, wexpr, lexpr, fingers_expr):
        """gf180 primitive FET = subcircuit => `X` call; ` NF={...}` -> ` nf={...}`."""
        subckt = self.MOS_SUBCKT[kind]
        nf = fingers_expr.replace(" NF=", " nf=") if fingers_expr else ""
        return (f"X{name} {nd} {ng} {ns} {nb} {subckt} "
                f"w={wexpr} l={lexpr}{nf}")

    def bjt_models(self):
        return None


ADAPTER = Gf180McuAdapter()

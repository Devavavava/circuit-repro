"""sky130 -- SkyWater 130 nm open PDK adapter (STAGED).

Full device-mapping table below, written from the public sky130 documentation
(google/skywater-pdk + the efabless sky130_fd_pr primitive-device library, both
Apache-2.0). model_includes() raises NotImplementedError until the primitive
model files are fetched (see lna/pdk/FETCH.md); get_pdk("sky130") still returns
this adapter so a spec can name it and receive a precise "not fetched" error.

DEVICE MAPPING
--------------
sky130 primitive FETs are SUBCIRCUITS, not bare BSIM `.model` cards: the model
library defines `sky130_fd_pr__nfet_01v8` / `pfet_01v8` as `.subckt`s (they wrap
the BSIM4 core with parasitic diodes, binning, and mismatch), so an instance is
an `X` call with W/L/nf as subckt parameters, NOT an `M` card. That is the
central difference from bptm45 and why mos_line() emits `X...`.

    harness kind   sky130 device (1.8 V core)      instantiation
    ------------   ----------------------------    ----------------------------
    NM             sky130_fd_pr__nfet_01v8         X<name> d g s b nfet_01v8 ...
    PM             sky130_fd_pr__pfet_01v8         X<name> d g s b pfet_01v8 ...

W/L are passed as subckt parameters in METRES with explicit units
(`w=5e-6 l=0.15e-6`); `nf` is the finger count (the subckt takes it directly, so
the harness's ` NF={...}` fragment maps to ` nf={...}`). Supply is 1.8 V (the
01v8 core device). Higher-voltage flavours (nfet_03v3_nvt, nfet_g5v0d10v5)
exist but the RF/LNA target is the 1.8 V core.

BIPOLAR: sky130 ships NPN/PNP (sky130_fd_pr__npn_05v5_w1u00l1u00 etc.) but they
are low-fT lateral/vertical devices, not RF SiGe -- bjt_models() returns None
(fall back to the generic Gummel-Poon set) rather than claim an RF bipolar this
process does not really offer.

CORNER: the model library is included via a corner `.lib` (typical =
`sky130.lib.spice` section `tt`). model_includes() will emit that `.lib ... tt`
line once the files land; the manifest below records the expected file.
"""


class Sky130Adapter(object):
    name = "sky130"
    vdd = 1.8
    device_ranges = {
        "W": (0.42e-6, 100e-6),     # nfet_01v8 min W 0.42 um; RF widths to 100 um
        "L": (0.15e-6, 0.15e-6),    # 0.15 um drawn (min for 01v8), pinned
        "R": (50.0, 50e3),
        "C": (1e-15, 20e-12),
        "L_ind": (0.3e-9, 20e-9),
    }
    notes = ("SkyWater 130 nm (Apache-2.0). Primitive FETs are SUBCIRCUITS "
             "(sky130_fd_pr__nfet_01v8/pfet_01v8) => X-instantiation with a "
             "corner .lib include; 1.8 V core. Most battle-tested open PDK with "
             "ngspice. STAGED: model files not fetched (see FETCH.md).")

    # Expected model files on the box once fetched (relative to the PDK root the
    # fetch lands under). sha/size are TODO -- filled after the approved fetch.
    expected_files = [
        {"path": "sky130A/libs.tech/ngspice/sky130.lib.spice",
         "role": "corner selector (.lib ... tt) -- top include",
         "sha256": "TODO", "size_bytes": "TODO"},
        {"path": "sky130A/libs.tech/ngspice/sky130_fd_pr__nfet_01v8__tt.corner.spice",
         "role": "nfet_01v8 tt subckt", "sha256": "TODO", "size_bytes": "TODO"},
        {"path": "sky130A/libs.tech/ngspice/sky130_fd_pr__pfet_01v8__tt.corner.spice",
         "role": "pfet_01v8 tt subckt", "sha256": "TODO", "size_bytes": "TODO"},
    ]

    # MOS device names by harness kind -- the mapping table, usable for docs/tests
    # even before the files exist.
    MOS_SUBCKT = {"NM": "sky130_fd_pr__nfet_01v8",
                  "PM": "sky130_fd_pr__pfet_01v8"}

    def model_includes(self):
        raise NotImplementedError(
            "sky130 model files not fetched -- see lna/pdk/FETCH.md. "
            "Once fetched this returns e.g. "
            "['.lib <root>/sky130A/libs.tech/ngspice/sky130.lib.spice tt'].")

    def mos_line(self, name, nd, ng, ns, nb, kind, wexpr, lexpr, fingers_expr):
        """sky130 primitive FET = subcircuit => `X` call. Verified device names,
        emitted even while the models are unfetched so the mapping is testable.

        `fingers_expr` arrives as ` NF={...}` (harness convention); sky130's
        subckt takes `nf`, so it is re-expressed as ` nf={...}`."""
        subckt = self.MOS_SUBCKT[kind]
        nf = fingers_expr.replace(" NF=", " nf=") if fingers_expr else ""
        return (f"X{name} {nd} {ng} {ns} {nb} {subckt} "
                f"w={wexpr} l={lexpr}{nf}")

    def bjt_models(self):
        return None


ADAPTER = Sky130Adapter()

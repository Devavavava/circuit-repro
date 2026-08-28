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
import os


class Sky130Adapter(object):
    name = "sky130"
    vdd = 1.8
    device_ranges = {
        "W": (0.42e-6, 100e-6),     # nfet_01v8 min W 0.42 um; RF widths to 100 um
        "L": (0.15e-6, 0.15e-6),    # 0.15 um drawn (min for 01v8), pinned
        "R": (50.0, 50e3),
        "C": (1e-15, 20e-12),
        "L_ind": (0.3e-9, 20e-9),
        "VB": (0.1, 1.8),           # gate-bias box (V); nfet_01v8 Vth ~0.7
    }
    notes = ("SkyWater 130 nm (Apache-2.0). Primitive FETs are SUBCIRCUITS "
             "(sky130_fd_pr__nfet_01v8/pfet_01v8) => X-instantiation with a "
             "corner .lib include; 1.8 V core. Most battle-tested open PDK with "
             "ngspice. STAGED: model files not fetched (see FETCH.md).")

    # FETCHED 2026-08-27 (user-approved). Files under
    # <pdk_root>/sky130/sky130_fd_pr/, from efabless/skywater-pdk-libs-sky130_fd_pr
    # @ 1232782c (Apache-2.0). sky130.lib.min.spice is a thin new wrapper (see
    # FETCH.md) that includes ONLY the two 1.8 V core FET cells; each *__tt.pm3
    # already carries the full .subckt + BSIM4 .model cards self-contained.
    CORNER_REL = "sky130_fd_pr/models/sky130.lib.min.spice"
    CORNER_SECTION = "tt"
    expected_files = [
        {"path": "sky130_fd_pr/models/sky130.lib.min.spice",
         "role": "trimmed corner selector (.lib ... tt) -- nfet_01v8+pfet_01v8 only",
         "sha256": "6bfa6e4b4ed34dbc6933433f398ff682e6055cce1f142b8acb1f58c241824865",
         "size_bytes": 1334},
        {"path": "sky130_fd_pr/cells/nfet_01v8/sky130_fd_pr__nfet_01v8__tt.pm3.spice",
         "role": "nfet_01v8 tt subckt + BSIM4 binned models",
         "sha256": "459eca963a134574cf7c842ad6d3814e7e0752bfb5de8e581c2f483534b5ad06",
         "size_bytes": 1137294},
        {"path": "sky130_fd_pr/cells/pfet_01v8/sky130_fd_pr__pfet_01v8__tt.pm3.spice",
         "role": "pfet_01v8 tt subckt + BSIM4 binned models",
         "sha256": "c943246ce012ea3db2777e3f4633ddccdfee7c8f1bf4dca79af9f7ff17b3d51f",
         "size_bytes": 809553},
    ]

    # MOS device names by harness kind -- the mapping table, usable for docs/tests
    # even before the files exist.
    MOS_SUBCKT = {"NM": "sky130_fd_pr__nfet_01v8",
                  "PM": "sky130_fd_pr__pfet_01v8"}

    def model_includes(self):
        """Emit the single `.lib <corner> tt` line. The BSIM4 models are binned
        by W/L in METRES (bins run 0.15 um .. 100 um), so a sky130 spec must
        supply W/L in metres; mos_line() passes them through verbatim."""
        from . import pdk_root
        root = pdk_root(self.name)
        if root is None:
            raise NotImplementedError(
                "sky130 model files not fetched -- see lna/pdk/FETCH.md. "
                "Once fetched this returns "
                "['.lib <root>/sky130_fd_pr/models/sky130.lib.min.spice tt'].")
        corner = os.path.join(root, self.CORNER_REL).replace(os.sep, "/")
        return [f'.lib "{corner}" {self.CORNER_SECTION}']

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

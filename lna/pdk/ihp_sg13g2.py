"""ihp_sg13g2 -- IHP SG13G2 130 nm SiGe BiCMOS open PDK adapter (STAGED).

The highest-RF-value target of the three: SG13G2 is a 130 nm BiCMOS process
whose headline device is a 250 GHz-fT SiGe:C HBT (npn13G2), exactly the device
class the harness's generic Gummel-Poon NPN was standing in for. The corpus
already contains ingested IHP circuits (to_spice's BJT_MODELS note cites IHP's
open SG13G2 GPS_LNA), so this adapter closes the loop between an ingested
topology and its real silicon models.

model_includes() raises NotImplementedError until the model files are fetched
(see lna/pdk/FETCH.md). get_pdk("ihp_sg13g2") still returns this adapter.

DEVICE MAPPING (from IHP-Open-PDK ihp-sg13g2/libs.tech/ngspice/models, verified
present read-only: sg13g2_moslv_mod.lib, sg13g2_hbt_mod.lib, ...)
----------------------------------------------------------------------------
    harness kind   SG13G2 device            model type
    ------------   ----------------------   -------------------------------
    NM             sg13_lv_nmos             PSP 103 (low-voltage core NMOS)
    PM             sg13_lv_pmos             PSP 103 (low-voltage core PMOS)
    NPN            npn13G2                  SiGe HBT (HICUM/L2)
    PNP            (none -- SG13G2 has no vertical PNP; PNP topologies
                    fall back to the generic Gummel-Poon card)

The MOS devices are SUBCIRCUITS in the IHP libs (sg13_lv_nmos wraps the PSP
core), so mos_line() emits `X` calls with w/l/ng (ng = finger/gate count) in
metres, matching the IHP ngspice usage.

OSDI / OpenVAF REQUIREMENT (load-bearing)  -- MOS ONLY
------------------------------------------------------
CONTRADICTS the earlier staging note: only the PSP MOS is a Verilog-A/OSDI
model. The `npn13G2` SiGe HBT is a NATIVE ngspice VBIC card (`.model ... npn`,
a `Q`-device) -- NOT HICUM/L2, NOT OSDI. So the HBT needs no compile step and
runs on stock ngspice; only the MOS needs OSDI.

The PSP MOS `.model` cards (in sg13g2_moslv_parm.lib) are typed `psp103va` and
`pspnqs103va`; those model types are registered by loading psp103.osdi and
psp103_nqs.osdi (compiled from libs.tech/verilog-a/psp103/*.va with OpenVAF,
`-D__NGSPICE__`). ngspice-47 on this box HAS OSDI (KLU build; `osdi_enabled`).

OSDI LOAD ORDER (important): an `.osdi` cannot be `.include`d (it is a binary),
and the `osdi <file>` command must run BEFORE the netlist is parsed so the model
types exist when the `.model` cards are read. In batch mode the working pattern
is a `.control` block that runs `osdi <file>` first, then `source <netlist>`,
then the analysis -- so the OSDI paths are exposed separately via osdi_files();
model_includes() returns only the text `.lib` lines. The IHP smoke
(lna/ref/check_pdk_live.py) drives ngspice this way.
"""
import os


class IhpSg13g2Adapter(object):
    name = "ihp_sg13g2"
    vdd = 1.5    # SG13G2 low-voltage core rail (sg13_lv_* devices)
    device_ranges = {
        "W": (0.15e-6, 100e-6),
        "L": (0.13e-6, 0.13e-6),    # 130 nm core, pinned
        "R": (50.0, 50e3),
        "C": (1e-15, 20e-12),
        "L_ind": (0.1e-9, 20e-9),   # SG13G2 offers good RF spiral inductors
    }
    notes = ("IHP SG13G2 130 nm SiGe BiCMOS (Apache-2.0). npn13G2 SiGe HBT "
             "(~250 GHz fT) + PSP-103 sg13_lv_nmos/pmos. Highest RF value: real "
             "SiGe HBT, and the corpus already carries ingested IHP circuits. "
             "Requires OSDI/OpenVAF-compiled .osdi (ngspice-47 has OSDI). "
             "STAGED: model files not fetched + .osdi not compiled (see FETCH.md).")

    # FETCHED 2026-08-27 (user-approved). Files under
    # <pdk_root>/ihp_sg13g2/libs.tech/, from IHP-GmbH/IHP-Open-PDK @ 331c0048
    # (Apache-2.0). The .osdi are compiled on-box from the verilog-a/psp103/*.va
    # with OpenVAF 23.5.0 (static, -D__NGSPICE__).
    MODELS_REL = "libs.tech/ngspice/models"
    OSDI_REL = "libs.tech/ngspice/osdi"
    MOS_CORNER = "cornerMOSlv.lib"      # section mos_tt -> pulls mod + parm libs
    MOS_SECTION = "mos_tt"
    HBT_CORNER = "cornerHBT.lib"        # section hbt_typ -> pulls hbt_mod lib
    HBT_SECTION = "hbt_typ"
    OSDI_MODULES = ["psp103.osdi", "psp103_nqs.osdi"]
    expected_files = [
        {"path": "libs.tech/ngspice/models/cornerMOSlv.lib",
         "role": "MOS lv corner selector (.lib ... mos_tt)",
         "sha256": "03d505847c880d233b341be115a1e5460edf4d8e9b3e8a7df791a52fa4455d67",
         "size_bytes": 21645},
        {"path": "libs.tech/ngspice/models/sg13g2_moslv_mod.lib",
         "role": "sg13_lv_nmos/pmos PSP subckts (.include'd by the corner)",
         "sha256": "84ec57080b9dd4666417f05db6f7b34c8dd3f12118929f9b308018613bece16e",
         "size_bytes": 10452},
        {"path": "libs.tech/ngspice/models/sg13g2_moslv_parm.lib",
         "role": "PSP .model cards (psp103va/pspnqs103va) -- needs the .osdi",
         "sha256": "cbf10b8453a18bb70b8ad0d6e40faa0937338e699b5460947a94900db6c92a6e",
         "size_bytes": 94408},
        {"path": "libs.tech/ngspice/models/cornerHBT.lib",
         "role": "HBT corner selector (.lib ... hbt_typ)",
         "sha256": "bae3d705445de8d6b8de4aa798a0e3e5e7cab617d6495d9c56473bc5377de462",
         "size_bytes": 3975},
        {"path": "libs.tech/ngspice/models/sg13g2_hbt_mod.lib",
         "role": "npn13G2 SiGe HBT (native ngspice VBIC, NO OSDI)",
         "sha256": "ae9288f885dd30fab24b07ed1e7e02e69eac9154022a0a6da576985183b0bd79",
         "size_bytes": 20057},
        {"path": "libs.tech/ngspice/osdi/psp103.osdi",
         "role": "compiled PSP103 (registers psp103va), OpenVAF 23.5.0",
         "sha256": "8f482e761c450609c9255eb20b83978db6799450fa3cc7ae2e1dc6ca247ee61d",
         "size_bytes": 730712},
        {"path": "libs.tech/ngspice/osdi/psp103_nqs.osdi",
         "role": "compiled PSP103 NQS (registers pspnqs103va), OpenVAF 23.5.0",
         "sha256": "c42217715d6bd0abba42f83ad6f657700f02d185aad502a9426641261404c9dd",
         "size_bytes": 1047568},
    ]

    MOS_SUBCKT = {"NM": "sg13_lv_nmos", "PM": "sg13_lv_pmos"}
    # Only the NPN is a real SG13G2 device; PNP has no vertical counterpart here.
    HBT_MODEL = {"NPN": "npn13G2"}

    def _root(self):
        from . import pdk_root
        return pdk_root(self.name)

    def osdi_files(self):
        """Absolute paths of the compiled .osdi that must be loaded (via the
        `osdi` command, in a .control block, BEFORE the netlist is sourced) so
        the PSP `psp103va`/`pspnqs103va` model types exist. Empty list if the
        PDK is not fetched -- callers gate on this."""
        root = self._root()
        if root is None:
            return []
        return [os.path.join(root, self.OSDI_REL, m).replace(os.sep, "/")
                for m in self.OSDI_MODULES]

    def model_includes(self):
        """The `.lib` lines for MOS (mos_tt) and HBT (hbt_typ). These reference
        PSP `.model` cards whose model type comes from the .osdi in osdi_files()
        -- load those first (see class docstring). W/L are in METRES; the PSP
        core is pinned at the 130 nm drawn length."""
        root = self._root()
        if root is None:
            raise NotImplementedError(
                "ihp_sg13g2 model files not fetched (and .osdi not compiled) -- "
                "see lna/pdk/FETCH.md. Once ready model_includes() returns the "
                "['.lib <root>/.../cornerMOSlv.lib mos_tt', '.lib "
                "<root>/.../cornerHBT.lib hbt_typ'] pair and osdi_files() the "
                "two psp103*.osdi paths.")
        mdir = os.path.join(root, self.MODELS_REL)
        mos = os.path.join(mdir, self.MOS_CORNER).replace(os.sep, "/")
        hbt = os.path.join(mdir, self.HBT_CORNER).replace(os.sep, "/")
        return [f'.lib "{mos}" {self.MOS_SECTION}',
                f'.lib "{hbt}" {self.HBT_SECTION}']

    def mos_line(self, name, nd, ng, ns, nb, kind, wexpr, lexpr, fingers_expr):
        """SG13G2 lv MOS = PSP subcircuit => `X` call. `fingers_expr` (` NF={...}`)
        maps to IHP's ` ng={...}` gate-count parameter."""
        subckt = self.MOS_SUBCKT[kind]
        ng_p = fingers_expr.replace(" NF=", " ng=") if fingers_expr else ""
        return (f"X{name} {nd} {ng} {ns} {nb} {subckt} "
                f"w={wexpr} l={lexpr}{ng_p}")

    def bjt_models(self):
        """None -> to_spice falls back to the generic Gummel-Poon set. The REAL
        npn13G2 substitution is a model_includes()-fetched .lib device, wired in
        the same wave as the fetch (a bipolar emission change is a to_spice
        concern gated on the files existing); staged here as HBT_MODEL for the
        mapping. PNP has no SG13G2 device, so the generic PNP always applies."""
        return None


ADAPTER = IhpSg13g2Adapter()

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

OSDI / OpenVAF REQUIREMENT (load-bearing)
-----------------------------------------
SG13G2's PSP MOS and HICUM/L2 HBT are Verilog-A compact models. ngspice runs
them through OSDI: the .va sources must be compiled to a .osdi shared object
with OpenVAF, then loaded with `pre_osdi <path>.osdi` before the device cards.
ngspice-47 on this box HAS OSDI support (built with the KLU solver; osdi is a
standard build-in), so the only missing piece is the compiled .osdi -- which is
a fetch+compile step, not a simulator limitation. FETCH.md carries the exact
OpenVAF compile recipe. model_includes() will emit the `pre_osdi` line(s) plus
the `.lib ... mos_tt`/`hbt_tt` includes once both the .osdi and the .lib files
exist.
"""


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

    expected_files = [
        {"path": "ihp-sg13g2/libs.tech/ngspice/models/cornerMOSlv.lib",
         "role": "MOS lv corner selector (.lib ... mos_tt)",
         "sha256": "TODO", "size_bytes": "TODO"},
        {"path": "ihp-sg13g2/libs.tech/ngspice/models/sg13g2_moslv_mod.lib",
         "role": "sg13_lv_nmos/pmos PSP subckts",
         "sha256": "TODO", "size_bytes": "TODO"},
        {"path": "ihp-sg13g2/libs.tech/ngspice/models/cornerHBT.lib",
         "role": "HBT corner selector (.lib ... hbt_tt)",
         "sha256": "TODO", "size_bytes": "TODO"},
        {"path": "ihp-sg13g2/libs.tech/ngspice/models/sg13g2_hbt_mod.lib",
         "role": "npn13G2 SiGe HBT (HICUM/L2)",
         "sha256": "TODO", "size_bytes": "TODO"},
        {"path": "ihp-sg13g2/libs.tech/verilog-a/*.va -> psp103.osdi, hicumL2.osdi",
         "role": "Verilog-A compact-model sources, compiled with OpenVAF",
         "sha256": "TODO (of the compiled .osdi)", "size_bytes": "TODO"},
    ]

    MOS_SUBCKT = {"NM": "sg13_lv_nmos", "PM": "sg13_lv_pmos"}
    # Only the NPN is a real SG13G2 device; PNP has no vertical counterpart here.
    HBT_MODEL = {"NPN": "npn13G2"}

    def model_includes(self):
        raise NotImplementedError(
            "ihp_sg13g2 model files not fetched (and .osdi not compiled) -- see "
            "lna/pdk/FETCH.md. Once ready this returns e.g. ['pre_osdi "
            "<root>/psp103.osdi', 'pre_osdi <root>/hicumL2.osdi', '.lib "
            "<root>/.../cornerMOSlv.lib mos_tt', '.lib <root>/.../cornerHBT.lib "
            "hbt_tt'].")

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

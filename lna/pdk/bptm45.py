"""bptm45 -- the CURRENT 45 nm flow, refactored into a PDK adapter.

This adapter is a REFACTOR, not a new process: it reproduces exactly what
to_spice.py already emitted before the PDK abstraction existed. It is the
byte-identity anchor -- lna/ref/check_pdk.py renders a reference topology with
and without this adapter explicitly passed and asserts the two decks are
byte-for-byte equal.

Process: AutoCkt's BPTM 45 nm bulk BSIM4 card
(AutoCkt/.../spice_models/45nm_bulk.txt), models `nmos` / `pmos` (both `level
54`, rgatemod=1 so gate-electrode resistance is real -- which is why the harness
emits a multi-finger NF, see to_spice.W_FINGER). Bulk MOS => `M` cards. Supply
1.1 V (wifi24.yaml's vdd, and to_spice.Netlist's own default). Bipolars are the
generic hand-written Gummel-Poon cards (to_spice.BJT_MODELS) -- this process has
no vendor bipolar, so bjt_models() returns None to keep to_spice's fallback.

The include-path resolution is the EXISTING machinery: extract.resolve_models
walks LNA_DEPS_ROOT -> this checkout -> the main checkout -> ancestors -> the
baked literal, so a worktree with no upstream clone still finds the card in the
main checkout. This adapter's model_includes() emits the SAME literal path
to_spice.DEFAULT_MODELS used (with os.sep -> '/'); host resolution happens later
in extract.body_of()/rewrite_includes(), unchanged, so the emitted text is
identical to today's.
"""
import os


class Bptm45Adapter(object):
    name = "bptm45"
    vdd = 1.1
    # Sane W/L/R/C/L box for this 45 nm process, in SI units -- used only when a
    # spec supplies no `sizing:` block. These mirror wifi24.yaml's sizing ranges
    # (the primary bring-up spec) so a bptm45 design with no sizing block boxes
    # exactly like the real specs do. L is pinned at the drawn 45 nm by default
    # (the harness fixes channel length; classify_params emits pL=45n), but a
    # range is given for completeness.
    device_ranges = {
        "W": (1e-6, 200e-6),        # 1..200 um, wifi24 w_um
        "L": (45e-9, 45e-9),        # drawn length, fixed at 45 nm
        "R": (50.0, 20e3),          # wifi24 r_ohm
        "C": (50e-15, 10e-12),      # wifi24 c_f
        "L_ind": (0.3e-9, 12e-9),   # wifi24 topology l_min..l_max (inductor L)
    }
    notes = ("BPTM 45 nm bulk BSIM4 (AutoCkt 45nm_bulk.txt), models nmos/pmos, "
             "1.1 V. The harness's original process; this adapter reproduces the "
             "pre-PDK emitter byte-for-byte. Bipolars: generic Gummel-Poon "
             "(to_spice.BJT_MODELS), illustrative device class only, not a PDK.")

    def __init__(self, models=None):
        # `models` is the literal include path to emit; None => to_spice's own
        # DEFAULT_MODELS constant, imported lazily to avoid an import cycle
        # (to_spice imports pdk indirectly through the Netlist ctor default).
        self._models = models

    def _models_path(self):
        if self._models is not None:
            return self._models
        # import here, not at module top, so `import lna.pdk` never triggers a
        # partially-initialised to_spice import.
        import to_spice
        return to_spice.DEFAULT_MODELS

    def model_includes(self):
        """The single `.include` line to_spice.emit() has always emitted."""
        return [f".include {self._models_path().replace(os.sep, '/')}"]

    def mos_line(self, name, nd, ng, ns, nb, kind, wexpr, lexpr, fingers_expr):
        """Exactly the `M<dev>` line to_spice.emit() built for a bulk MOSFET.

        `fingers_expr` is the already-assembled ` NF={...}` fragment (or "");
        this adapter passes it through verbatim -- BSIM4's NF is a real
        per-instance parameter and is what carries the multi-finger gate-R fix
        (to_spice.W_FINGER / FINDINGS 26)."""
        model = "nmos" if kind == "NM" else "pmos"
        return (f"M{name} {nd} {ng} {ns} {nb} {model} "
                f"W={wexpr} L={lexpr}{fingers_expr}")

    def bjt_models(self):
        """None -> to_spice falls back to its generic Gummel-Poon set. This
        process has no vendor bipolar to substitute."""
        return None


ADAPTER = Bptm45Adapter()

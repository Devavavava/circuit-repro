"""PDK abstraction v0 -- one `pdk:` field in a spec selects a device technology.

The whole harness has, until now, spoken ONE process: AutoCkt's BPTM 45 nm bulk
BSIM4 card (`45nm_bulk.txt`, models `nmos`/`pmos`) plus the hand-written generic
Gummel-Poon bipolar cards in `to_spice.BJT_MODELS`. Every deck `to_spice.py`
emits bakes that choice in three places: the `.include` line, the `nmos`/`pmos`
model names on each `M` card, and the 1.1 V supply default. A second process
means changing all three coherently -- which is exactly what an ADAPTER is for.

An adapter is a small object with a fixed interface; `get_pdk(name)` returns one.
`to_spice.Netlist` takes an optional `pdk=` (default: the bptm45 adapter) and
routes its model include / MOS emission / supply default through it. The default
path is BYTE-IDENTICAL to the pre-PDK emitter (proved by lna/ref/check_pdk.py):
the bptm45 adapter is a *refactor* of what to_spice already did, not a new code
path, so every existing spec and every shipped deck reproduces exactly.

THE ADAPTER INTERFACE
---------------------
Every adapter exposes:

    name            str    -- short id, matches the spec `pdk:` field
    vdd             float  -- default supply rail (V), when the spec omits one
    device_ranges   dict   -- {kind: (lo, hi)} sane W/L/R/C/L box for this
                              process, in SI units, for a sizer that has no
                              spec-supplied sizing block. kinds: W, L, R, C, L.
    notes           str    -- one-paragraph provenance / caveats

    model_includes() -> list[str]
        SPICE `.include`/`.lib` lines (already host-resolved) that must precede
        any device card. Raises NotImplementedError with a pointer to FETCH.md
        for a STAGED adapter whose model files are not on the box yet.

    mos_line(name, nd, ng, ns, nb, kind, wexpr, lexpr, fingers_expr) -> str
        One emitted MOSFET instance line. `kind` is "NM" or "PM" (the harness's
        own device base); the adapter maps it to this process's model/subckt and
        emits either an `M` card (bulk BSIM) or an `X` subcircuit call (sky130 /
        gf180 primitive devices are subckts). `fingers_expr` is an already-built
        ` NF={...}` fragment (or "") -- passed through verbatim by adapters whose
        model takes an NF parameter, dropped by those that do not.

    bjt_models()    -> dict {base: (model_name, card_text)} | None
        Bipolar cards for this process, or None to fall back to
        to_spice.BJT_MODELS (the generic Gummel-Poon set). Only IHP SG13G2
        overrides this today (real SiGe HBT).

Staged adapters (sky130, ihp_sg13g2, gf180mcu) carry the FULL device-mapping
tables from public documentation but raise NotImplementedError from
model_includes() until the model files are fetched -- see lna/pdk/FETCH.md for
the approval-gated fetch plan. get_pdk() still returns them so a spec can name
one and get a precise "not fetched yet" error rather than a KeyError.
"""
import os
import subprocess

from . import bptm45 as _bptm45
from . import gf180mcu as _gf180
from . import ihp_sg13g2 as _ihp
from . import sky130 as _sky130

# ---------------------------------------------------------------- PDK root
# Fetched foundry PDK model files live under a gitignored `<root>/.env/pdks/`
# tree (the same `.env/` the ngspice-47 build sits in). A worktree has no such
# tree of its own -- the models are in the MAIN checkout -- and a Kaggle worker
# mounts them at a dataset path. Both are handled by resolving the root the same
# way extract.resolve_models walks for the 45 nm card: an explicit override
# first (LNA_PDK_ROOT, or LNA_DEPS_ROOT/.env/pdks), then this package's checkout,
# then the git common dir's parent (the main checkout, from a worktree), then
# ancestors. The first candidate that actually contains the named PDK subdir
# wins, so a partially-fetched box degrades to a precise per-PDK "not fetched".
_PKG_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _candidate_roots():
    """Checkout roots to probe for `.env/pdks/`, nearest first -- mirrors
    extract._dep_roots so the two resolvers stay in lockstep."""
    seen, out = set(), []

    def add(p):
        if p and os.path.isdir(p) and p not in seen:
            seen.add(p)
            out.append(p)

    # explicit PDK override (a dir that directly holds <name>/ subdirs)
    add(os.environ.get("LNA_PDK_ROOT"))
    # explicit deps override -> its .env/pdks
    dep = os.environ.get("LNA_DEPS_ROOT")
    if dep:
        add(os.path.join(dep, ".env", "pdks"))
    # this checkout, then the main checkout (from a worktree), then ancestors
    add(os.path.join(_PKG_ROOT, ".env", "pdks"))
    try:
        r = subprocess.run(["git", "rev-parse", "--path-format=absolute",
                            "--git-common-dir"], cwd=_PKG_ROOT,
                           capture_output=True, text=True, timeout=10)
        common = (r.stdout or "").strip()
        if common:
            main = os.path.dirname(os.path.abspath(common))
            add(os.path.join(main, ".env", "pdks"))
    except Exception:                                              # noqa: BLE001
        pass
    p = _PKG_ROOT
    while os.path.dirname(p) != p:
        p = os.path.dirname(p)
        add(os.path.join(p, ".env", "pdks"))
    return out


def pdk_root(name):
    """Absolute path to the fetched-model root for PDK `name`, or None if not
    fetched on this host. `name` is the adapter id (its files live in
    `<root>/<name>/`). Adapters call this from model_includes() and raise a
    FETCH.md-naming NotImplementedError when it returns None."""
    for root in _candidate_roots():
        cand = os.path.join(root, name)
        if os.path.isdir(cand):
            return os.path.abspath(cand)
    return None

# name -> adapter instance. The default (used everywhere the spec omits `pdk:`)
# is bptm45, the current 45 nm flow refactored into adapter form.
_REGISTRY = {
    "bptm45": _bptm45.ADAPTER,
    "sky130": _sky130.ADAPTER,
    "ihp_sg13g2": _ihp.ADAPTER,
    "gf180mcu": _gf180.ADAPTER,
}

DEFAULT_PDK = "bptm45"


def get_pdk(name=None):
    """Return the adapter for `name` (or the default bptm45 adapter for None).

    Raises KeyError with the known names on an unrecognized id -- a typo in a
    spec's `pdk:` field should fail loudly, the same discipline spec._validate
    uses for unknown keys."""
    if name is None:
        return _REGISTRY[DEFAULT_PDK]
    if name not in _REGISTRY:
        raise KeyError(f"unknown pdk {name!r}; known: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def default_pdk():
    """The bptm45 adapter -- the byte-identity anchor. to_spice.Netlist uses this
    when no pdk is passed."""
    return _REGISTRY[DEFAULT_PDK]


def known_pdks():
    return sorted(_REGISTRY)

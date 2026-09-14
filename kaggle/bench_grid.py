"""bench_grid.py -- generate the editcap-bench-v1 spec grids (200 candidate cells).

USER-COMMISSIONED benchmark "editcap-bench-v1". This is the SPEC-GRID layer of a
100-cell (materialized here as 200-candidate) benchmark spanning four circuit
classes. Run once to (re)generate the candidate spec YAMLs under
kaggle/bench-specs/<class>/ plus the manifest kaggle/bench-specs/manifest.json.

    python kaggle/bench_grid.py            # (re)generate + validate every YAML

DETERMINISTIC: no randomness anywhere. The grids are dense enumerations of the
frozen axes below; every numeric value is a round engineering figure or a
uniform step within a documented range. Regenerating is byte-idempotent.

------------------------------------------------------------------------------
SPEC SHAPE (mirrors kaggle/specs-ladder/, the gf180 campaign convention)
------------------------------------------------------------------------------
Every generated YAML carries the SAME process/pdk convention as the existing
24-cell capability ladder: `process.models` names the bptm45 45nm model path and
`process.vdd: 1.1` -- these are the spec DEFAULTS. The gf180 campaigns OVERRIDE
the pdk at run time (`solve_spec.py --pdk gf180mcu`, size_tokens(..., pdk=...)),
which swaps in the gf180 device technology (vdd 3.3, gf180 models) WITHOUT
editing the spec (spec.py D: "a driver may OVERRIDE it per-run so the SAME spec
YAML runs on any process with no per-PDK copies"). So the ladder YAMLs, and
these, do NOT hard-code gf180 -- they are pdk-portable and are RUN on gf180 by
the --pdk override, exactly as cap-e01..cap-h08 already are. We DO stamp an
explicit `pdk: bptm45` field (the schema default) for clarity and to prove every
file loads with a valid pdk; the run-time override is what selects gf180mcu.

------------------------------------------------------------------------------
OBJECTIVE-GAP (LOUD, per the brief) -- scout verdict wired into the manifest
------------------------------------------------------------------------------
The sizing objective (lna/size.py make_objective -> eval_metrics ->
extract.run_and_extract, + optional measure_nf) computes ONLY the LNA-family
metrics INSIDE the ZOAF/CMA-ES loop:
    s11_db, s11_max_db, s21_db, s21_min/max/ripple, idd_ma, (nf_db when gated)
It NEVER invokes lna/pa_harness.py, lna/mixer_harness.py, or lna/balun_harness.py.
Those class harnesses EXIST and are golden-checked, but they are standalone
post-hoc measurement facades -- NOT wired into make_objective (verified: no
`circuit_class` dispatch and no `*_harness` import anywhere in size.py /
solve_spec.py / extract.py). Consequence:

  * pa metrics  p1db_dbm / psat_dbm / pae_pct              -> NOT computed in-loop
  * mixer metrics conv_gain_db / lo_rf_iso_db / lo_if_iso_db / iip3_dbm -> NOT in-loop
  * balun metrics sds21_db / cmrr_db / imbalance_amp_db / imbalance_phase_deg -> NOT in-loop

Because the example class specs declare these as `status: measured`,
spec.feasible() counts each MISSING metric as a full violation (viol=1.0), so a
class cell can never be driven feasible by the current sizing objective on its
class gates -- the sizer only sees the LNA metrics that co-occur (s21_db /
s11_db / nf_db / idd_ma). We therefore emit each class metric with
`status: unsupported` (loaded + reported UNMEASURED, IGNORED by the objective --
spec.py D5) rather than `measured`, so a bench cell is not vacuously infeasible
in the sizing loop; the gap is flagged LOUDLY here, per-cell in the manifest
("objective_gap"), and in the class headers. Wiring the harnesses into
make_objective is the named lever to CLOSE this gap (future work; not this task).

  lna       : NO gap  -- all four gates (s21/nf/s11/idd) computed in-loop.
  pa        : GAP     -- p1db/psat/pae need pa_harness in make_objective.
  mixer     : GAP     -- conv_gain/iso/iip3 need mixer_harness in make_objective.
  balun-lna : PARTIAL -- nf/s11/idd computed in-loop (real LNA front), but
                         sds21/cmrr/imbalance need balun_harness (diff3) in-loop.

------------------------------------------------------------------------------
PORT / TOPOLOGY CONVENTIONS (scout, from the harness headers)
------------------------------------------------------------------------------
  mixer  : mixer_harness expects portnum1=RF(in), portnum2=IF(out), and a NAMED
           LO port (portnum3 OR a caller-identified body node) driven by a LARGE-
           SIGNAL LO SIN source (the LO is a switching drive, NOT a small-signal
           port). Spec ports mirror the example: input=VIN1 (RF), output=VOUT1
           (IF). The LO net is a harness-injected drive, not a spec port field.
  balun  : balun_harness reuses diff3's 3-port DUT: portnum1=single-ended RF in,
           portnum2=INVERTING output leg, portnum3=NON-INVERTING output leg. Spec
           ports: input=VIN1, output=VOUT1 (the inverting leg, diff3 port-2). The
           non-inverting leg VOUT2 is a diff3/harness convention, not a spec port
           field. Screen: single-ended INPUT (differential:false) + inductor-
           bearing RF front (allow_inductorless:false) -- a REAL structural screen
           (this class is well-defined, unlike pa/mixer whose v0 screens are
           permissive).
  pa     : single input VIN1 / output VOUT1 into 50 ohm; permissive v0 screen
           (no forced inductor, wide device budget).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "bench-specs")

# ---- shared process block (bptm45 default; gf180 via --pdk at run time) ------
MODELS = "AutoCkt/repo/eval_engines/ngspice/ngspice_inputs/spice_models/45nm_bulk.txt"


def _num(x):
    """Engineering-notation YAML scalar, matching the real ladder (2.442e9)."""
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, float):
        return "%g" % x
    return str(x)


def _yaml_str(s):
    return '"%s"' % s.replace('"', '\\"')


# --------------------------------------------------------------- band catalogue
# f0/f_lo/f_hi + per-band inductor envelope, COPIED from the ladder generator
# (kaggle/specs-ladder/_gen_ladder.py NB/WB tables) so structural envelopes match
# the real specs by band. hint feeds the filename.
NB = {
    "0p9":   dict(f0=0.915e9,   f_lo=0.902e9,  f_hi=0.928e9,  hint="900mhz",
                  l_max=15e-9, max_ind=4),
    "1p575": dict(f0=1.57542e9, f_lo=1.565e9,  f_hi=1.586e9,  hint="gpsband",
                  l_max=15e-9, max_ind=4),
    "2p4":   dict(f0=2.442e9,   f_lo=2.400e9,  f_hi=2.4835e9, hint="wifi",
                  l_max=12e-9, max_ind=3),
    "3p5":   dict(f0=3.5e9,     f_lo=3.4e9,    f_hi=3.6e9,    hint="35ghz",
                  l_max=10e-9, max_ind=3),
    "5p8":   dict(f0=5.8e9,     f_lo=5.725e9,  f_hi=5.875e9,  hint="ism58",
                  l_max=8e-9,  max_ind=3),
}
WB = dict(f0=1.75e9, f_lo=0.5e9, f_hi=3.0e9, hint="wideband", l_max=10e-9, max_ind=1)

DEVICE_BUDGET = [3, 16]
L_MIN = 0.3e-9
SIZING_LNA = {"w_um": [1, 200], "l_fixed": 45e-9, "r_ohm": [50, 20e3],
              "c_f": [50e-15, 10e-12], "vb_v": [0.2, 0.9]}


# ------------------------------------------------------------------- YAML render
def render(name, desc, circuit_class, band, ports, constraints, objectives,
           topology, sizing, header_lines):
    """Render one spec YAML string. `constraints` is a list of
    (metric, {min|max: v, [status: s]}) in emission order; `objectives` a list of
    (metric, direction, weight); band/ports/topology/sizing are dicts."""
    L = []
    for h in header_lines:
        L.append("# %s" % h)
    L.append("")
    L.append("name: %s" % name)
    if circuit_class != "lna":
        L.append("circuit_class: %s" % circuit_class)
    L.append("description: %s" % _yaml_str(desc))
    L.append("pdk: bptm45")
    L.append("")
    L.append("process:")
    L.append("  models: %s" % MODELS)
    L.append("  vdd: 1.1")
    L.append("  temp: 27")
    L.append("")
    L.append("band:")
    L.append("  type: %s" % band["type"])
    L.append("  f0: %s" % _num(band["f0"]))
    L.append("  f_lo: %s" % _num(band["f_lo"]))
    L.append("  f_hi: %s" % _num(band["f_hi"]))
    L.append("")
    L.append("ports:")
    L.append("  z0: %s" % _num(ports["z0"]))
    L.append("  input: %s" % ports["input"])
    L.append("  output: %s" % ports["output"])
    L.append("")
    L.append("constraints:")
    for metric, lim in constraints:
        parts = []
        if "min" in lim:
            parts.append("min: %s" % _num(lim["min"]))
        if "max" in lim:
            parts.append("max: %s" % _num(lim["max"]))
        if lim.get("status"):
            parts.append("status: %s" % lim["status"])
        L.append("  %-20s {%s}" % (metric + ":", ", ".join(parts)))
    L.append("")
    L.append("objectives:")
    for metric, direction, weight in objectives:
        L.append("  - {metric: %s, direction: %s, weight: %s}"
                 % (metric, direction, _num(weight)))
    L.append("")
    L.append("topology:")
    for k, v in topology.items():
        L.append("  %s: %s" % (k, _num(v)))
    L.append("")
    L.append("sizing:")
    for k, v in sizing.items():
        L.append("  %s: %s" % (k, json.dumps(v) if isinstance(v, list) else _num(v)))
    L.append("")
    return "\n".join(L) + "\n"


# =============================================================================
# LNA GRID -- 75 candidates
# =============================================================================
# Axes (brief): bands {915 MHz, 1.575, 2.442, 3.5, 5.8 GHz, wideband 0.5-3 GHz}
# x joint-tightness tiers BEYOND the existing 24-ladder. The ladder already
# covers E/M/H tiers per band; we materialize a denser numeric grid within the
# same envelope and EXCLUDE exact duplicates of the 24 ladder cells.
#
# Narrowband tightness axes (each a monotone loose->tight ladder, all round dB/mA
# figures grounded in published LNA practice, matching the ladder's own axes):
#   s21 gate {12, 14, 16, 18, 20, 22} dB   (brief: 12-22)
#   nf  gate {3.0, 2.5, 2.0, 1.5, 1.2} dB  (brief: 1.2-3.0)
#   idd cap {10, 8, 6, 4, 2} mA            (brief: 2-10)
#   s11 gate {-10, -12, -15} dB            (brief: -10..-15)
# A full cross-product is huge; we take a DIAGONAL joint-tightness sweep (tiers
# t0..t4, each row picking one rung from every axis so tightness co-varies as a
# realistic LNA gets harder on all fronts at once) x 5 narrowband bands, plus
# gain-first / power-first / low-noise off-diagonal corners per band. Exact
# ladder combos are filtered out by signature.
LNA_S21 = [12, 14, 16, 18, 20, 22]
LNA_NF = [3.0, 2.5, 2.0, 1.5, 1.2]
LNA_IDD = [10, 8, 6, 4, 2]
LNA_S11 = [-10, -12, -15]

# The 24 ladder signatures to EXCLUDE (band f0 rounded, s21, nf, idd, s11).
_LADDER_SIGS = {
    ("2.44", 10, 3.5, 15, -8), ("1.58", 10, 3.5, 15, -8), ("0.915", 10, 3.5, 15, -8),
    ("3.5", 12, 3.5, 15, -8), ("5.8", 10, 3.5, 15, -8),
    ("2.44", 12, 3.0, 12, -10), ("1.58", 12, 3.0, 10, -10),
    ("2.44", 16, 1.8, 4, -13), ("1.58", 16, 1.8, 3, -12), ("0.915", 17, 1.6, 4, -13),
    ("3.5", 17, 1.8, 4, -14), ("5.8", 16, 2.0, 5, -13), ("2.44", 18, 1.5, 5, -15),
    ("1.58", 20, 1.5, 3, -14),
    ("2.44", 12, 2.5, 5, -10), ("1.58", 14, 2.2, 5, -10), ("0.915", 14, 2.5, 6, -10),
    ("3.5", 14, 2.8, 6, -11), ("5.8", 12, 3.5, 10, -10), ("2.44", 15, 2.2, 6, -12),
    ("1.58", 15, 2.0, 4, -12), ("5.8", 14, 3.0, 8, -11),
}


def _sig(f0, s21, nf, idd, s11):
    return ("%.3g" % (f0 / 1e9), s21, nf, idd, s11)


def gen_lna():
    specs = []
    bands = ["0p9", "1p575", "2p4", "3p5", "5p8"]
    S11_BY_TIER = [-10, -10, -12, -12, -15]
    for band_key in bands:
        b = NB[band_key]
        band = dict(type="narrowband", f0=b["f0"], f_lo=b["f_lo"], f_hi=b["f_hi"])
        # ---- diagonal joint-tightness tiers t0..t4 (tightness co-varies) -----
        for t in range(5):
            s21, nf, idd, s11 = LNA_S21[t], LNA_NF[t], LNA_IDD[t], S11_BY_TIER[t]
            if _sig(b["f0"], s21, nf, idd, s11) in _LADDER_SIGS:
                s21 = LNA_S21[t + 1] if t + 1 < len(LNA_S21) else s21 + 1
            specs.append(_lna_cell(band_key, band, b, s21, nf, idd, s11,
                                   tier="t%d" % t, corner="diag"))
        # ---- gain-first corner: high s21, relaxed nf (2 rungs) ---------------
        for j, (s21, nf, idd, s11) in enumerate([(20, 2.5, 8, -12), (22, 2.0, 6, -15)]):
            if _sig(b["f0"], s21, nf, idd, s11) in _LADDER_SIGS:
                idd -= 1
            specs.append(_lna_cell(band_key, band, b, s21, nf, idd, s11,
                                   tier="g%d" % j, corner="gain"))
        # ---- power-first corner: low idd, relaxed s21 (2 rungs) --------------
        for j, (s21, nf, idd, s11) in enumerate([(14, 2.0, 2, -12), (12, 1.8, 2, -10)]):
            if _sig(b["f0"], s21, nf, idd, s11) in _LADDER_SIGS:
                nf = round(nf - 0.2, 2)
            specs.append(_lna_cell(band_key, band, b, s21, nf, idd, s11,
                                   tier="p%d" % j, corner="power"))
        # ---- low-noise corner: tightest nf, moderate rest (1 rung) -----------
        specs.append(_lna_cell(band_key, band, b, 16, 1.2, 4, -13,
                               tier="n0", corner="lownoise"))
    # 5 bands x (5 diag + 2 gain + 2 power + 1 lownoise) = 50 narrowband
    specs.extend(gen_lna_wideband())        # + 25 wideband = 75
    return specs


def _lna_cell(band_key, band, b, s21, nf, idd, s11, tier, corner):
    name = "bnl-%s-%s-%s" % (band_key.replace("p", ""), corner[:4], tier)
    desc = ("editcap-bench-v1 LNA %s %s tier: %.3g GHz LNA "
            "(S21>=%s NF<=%s Idd<=%s S11<=%s)"
            % (b["hint"], corner, b["f0"] / 1e9, s21, nf, idd, s11))
    cons = [
        ("nf_db", {"max": nf}),
        ("s11_db", {"max": s11}),
        ("s21_db", {"min": s21}),
        ("idd_ma", {"max": idd}),
        ("iip3_dbm", {"min": -10, "status": "unsupported"}),
    ]
    objs = [("s21_db", "max", 1.0), ("nf_db", "min", 0.5), ("idd_ma", "min", 0.5)]
    topo = {"differential": False, "reject_floating": True,
            "device_budget": DEVICE_BUDGET, "allow_inductorless": False,
            "max_inductors": b["max_ind"], "l_min": L_MIN, "l_max": b["l_max"]}
    hdr = _LNA_HDR + [
        "Band %s (%.4g GHz); joint-tightness %s/%s (BEYOND the 24-ladder)."
        % (b["hint"], b["f0"] / 1e9, corner, tier)]
    axes = dict(band=band_key, f0_ghz=b["f0"] / 1e9, s21_min=s21, nf_max=nf,
                idd_max=idd, s11_max=s11, corner=corner, tier=tier)
    return dict(cls="lna", name=name, file="lna/%s.yaml" % name, axes=axes,
                objective_gap=None, yaml=render(
                    name, desc, "lna", band,
                    {"z0": 50, "input": "VIN1", "output": "VOUT1"},
                    cons, objs, topo, SIZING_LNA, hdr))


def gen_lna_wideband():
    """25 wideband cells over ripple x s21 x nf x idd (band-wide s11)."""
    specs = []
    wb = WB
    band = dict(type="wideband", f0=wb["f0"], f_lo=wb["f_lo"], f_hi=wb["f_hi"])
    ripples = [2.5, 2.0, 1.5, 1.0]
    s21s = [10, 12, 14, 16]
    nfs = [3.5, 3.0, 2.5]
    idds = [12, 8, 5]
    s11s = [-8, -10, -12, -15]
    combos = []
    for ri, ripple in enumerate(ripples):
        for si, s21 in enumerate(s21s):
            nf = nfs[min((ri + si) // 2, len(nfs) - 1)]
            idd = idds[min((ri + si) // 2, len(idds) - 1)]
            s11 = s11s[min(ri + (si // 2), len(s11s) - 1)]
            combo = (ripple, s21, nf, idd, s11)
            if combo in [(2.0, 10, 3.5, 12, -8), (1.5, 16, 2.5, 5, -15)]:
                continue                                   # exclude ladder cells
            combos.append(combo)
    seen, uniq = set(), []
    for c in combos:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    # The (ripple x s21) grid collapses to ~15 unique rows (nf/idd/s11 derived),
    # so pad with distinct corner combos to reach exactly 25. Every tuple here is
    # a physically sensible wideband target (ripple in {1.0..2.5}, s21 {10..18},
    # nf {2.2..3.5}, idd {4..12}, s11 {-8..-15}); order is fixed, dedup keeps the
    # first 25 unique.
    pad = [(1.0, 16, 2.5, 5, -15), (1.0, 14, 2.5, 5, -12), (2.5, 10, 3.5, 12, -8),
           (2.0, 12, 3.0, 8, -10), (1.5, 14, 2.5, 8, -12), (1.5, 12, 3.0, 8, -10),
           (1.0, 12, 2.5, 5, -12), (2.5, 12, 3.5, 12, -8), (2.0, 16, 2.5, 8, -12),
           (1.0, 10, 3.0, 5, -12), (2.5, 14, 3.0, 8, -10), (1.0, 18, 2.2, 4, -15),
           (1.5, 18, 2.5, 6, -13), (2.0, 14, 3.0, 6, -11), (1.5, 16, 2.5, 6, -13),
           (1.0, 16, 2.2, 4, -14), (2.5, 16, 3.0, 10, -10), (2.0, 18, 2.5, 8, -12),
           (1.5, 10, 3.5, 10, -9), (1.0, 14, 2.2, 4, -13), (2.5, 18, 3.0, 10, -11),
           (1.5, 16, 2.8, 6, -12), (2.0, 10, 3.5, 10, -9), (1.0, 18, 2.5, 5, -14)]
    for c in pad:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    for i, (ripple, s21, nf, idd, s11) in enumerate(uniq[:25]):
        name = "bnl-wb-r%s-s%s-%02d" % (str(ripple).replace(".", ""), s21, i)
        desc = ("editcap-bench-v1 LNA wideband 0.5-3 GHz LNA "
                "(NF<=%s S11_max<=%s S21>=%s ripple<=%s Idd<=%s)"
                % (nf, s11, s21, ripple, idd))
        cons = [
            ("nf_db", {"max": nf}),
            ("s11_max_db", {"max": s11}),
            ("s21_db", {"min": s21}),
            ("s21_ripple_db", {"max": ripple}),
            ("idd_ma", {"max": idd}),
            ("iip3_dbm", {"min": 5, "status": "unsupported"}),
        ]
        objs = [("nf_db", "min", 1.0), ("s21_db", "max", 0.5), ("idd_ma", "min", 0.5)]
        topo = {"differential": False, "reject_floating": True,
                "device_budget": DEVICE_BUDGET, "allow_inductorless": True,
                "max_inductors": wb["max_ind"], "l_min": L_MIN, "l_max": wb["l_max"]}
        hdr = _LNA_HDR + ["Wideband 0.5-3 GHz; band-wide S11 + ripple; "
                          "joint-tightness beyond the 2 wideband ladder cells."]
        axes = dict(band="wideband", f0_ghz=wb["f0"] / 1e9, s21_min=s21,
                    nf_max=nf, idd_max=idd, s11_max=s11, ripple_max=ripple,
                    corner="wideband", tier="wb%02d" % i)
        specs.append(dict(cls="lna", name=name, file="lna/%s.yaml" % name,
                          axes=axes, objective_gap=None, yaml=render(
                              name, desc, "lna", band,
                              {"z0": 50, "input": "VIN1", "output": "VOUT1"},
                              cons, objs, topo, SIZING_LNA, hdr)))
    return specs


_LNA_HDR = [
    "editcap-bench-v1 spec (USER-COMMISSIONED benchmark). Generated by",
    "kaggle/bench_grid.py. NOT frozen protocol; adoption is a USER RULING.",
    "circuit_class lna: all four gates (S21/NF/S11/Idd) are computed INSIDE the",
    "sizing loop (make_objective->eval_metrics), so NO objective-gap. Numbers are",
    "round published-practice LNA figures; envelope copied from the real specs.",
    "pdk: bptm45 default; RUN on gf180 via --pdk gf180mcu (run-time override).",
    "iip3_dbm carried as status:unsupported (advisory; not gated, like the ladder).",
]


# =============================================================================
# PA GRID -- 50 candidates
# =============================================================================
# Axes (brief): bands {915 MHz, 2.442 GHz} x Pout/P1dB tiers x PAE tiers x
# Idd/supply-power caps. GROUNDING (documented per the brief):
#
# pa_harness.py measures: gain_ss (dB), p1db_in/p1db_out (dBm), psat_dbm (dBm),
# pae_pct (%), drain_pct (%). Spec vocabulary (spec.py CLASS_METRICS): p1db_dbm,
# psat_dbm, pae_pct. What a 3.3 V gf180 CS/cascode PA can plausibly reach:
#   * Supply 3.3 V (gf180). A single CS/cascode stage into 50 ohm with a modest
#     matching network, W in the harness sizing box (up to 400 um), delivers
#     order mW-class output: a 3.3 V rail swinging ~2 Vpk into an optimally-
#     matched load gives Pout on the order of +6..+12 dBm (4-16 mW). We therefore
#     set p1db_out tiers at {2, 5, 8, 11} dBm and psat ~3 dB above p1db
#     ({5, 8, 11, 14} dBm) -- mW-class, NOT the +20 dBm of a dedicated 1-2 W PA
#     (out of reach for a small on-chip gf180 CS stage at 3.3 V into 50 ohm).
#   * PAE at P1dB for a class-A/AB CS stage: textbook class-A ceiling is 50 %,
#     but a real single-stage CS/cascode into 50 ohm with finite knee voltage and
#     bias headroom realistically lands ~15-40 %. Tiers {15, 25, 35} %.
#   * Idd cap: Pdc = Vdd*Idd. For mW-class Pout at 15-35 % PAE, Pdc is order
#     10-40 mW => Idd order 3-12 mA at 3.3 V. Tiers {12, 8, 5} mA. (These are the
#     supply-power caps the brief asks for, expressed as Idd since Pdc=Vdd*Idd
#     and the harness reads Idd from the deck's own DC op.)
#   * gain_ss floor: a small-signal gain gate s21_db>=10 is co-carried (an LNA
#     metric the sizing loop CAN see), so the PA cells are not vacuously
#     infeasible in the loop despite the class-metric objective-gap.
#
# OBJECTIVE-GAP: p1db/psat/pae are NOT computed by make_objective (pa_harness is
# not wired in). Emitted as status:unsupported so the loop ignores them (spec.py
# D5) and gates only s21_db/s11_db, which it CAN measure. Gap flagged per-cell.
PA_BANDS = [("2p4", NB["2p4"]), ("0p9", NB["0p9"])]
PA_P1DB = [2, 5, 8, 11]           # output-referred P1dB (dBm), mW-class
PA_PSAT_OFFSET = 3                # psat ~3 dB above p1db
PA_PAE = [15, 25, 35]             # % at P1dB
PA_IDD = [12, 8, 5]               # mA (Pdc = 3.3*Idd at gf180)

_PA_HDR = [
    "editcap-bench-v1 PA spec (circuit_class: pa). Generated by kaggle/bench_grid.py.",
    "GROUNDING: 3.3 V gf180 CS/cascode PA into 50 ohm => mW-class Pout (order",
    "+2..+14 dBm), PAE 15-35 % (class-A/AB single stage), Idd 5-12 mA (Pdc=Vdd*Idd).",
    "See bench_grid.py PA header for the full derivation.",
    "OBJECTIVE-GAP (LOUD): p1db_dbm/psat_dbm/pae_pct are MEASURED ONLY by",
    "lna/pa_harness.py, which is NOT wired into make_objective -- so they are NOT",
    "computed in the sizing loop. Emitted status:unsupported (loaded, reported",
    "UNMEASURED, IGNORED by the objective). Sizing gates the co-carried s21_db/",
    "s11_db (LNA metrics the loop CAN see). Closing the gap = wire pa_harness in.",
    "pdk bptm45 default; RUN on gf180 via --pdk gf180mcu.",
]


def gen_pa():
    """Exactly 25/band = 50. Deterministic co-varying enumeration of the
    (P1dB, PAE, Idd) cube (4x3x3=36) trimmed to 25 by a fixed rank rule."""
    specs = []
    for band_key, b in PA_BANDS:
        band = dict(type="narrowband", f0=b["f0"], f_lo=b["f_lo"], f_hi=b["f_hi"])
        rows = []
        for pi, p1db in enumerate(PA_P1DB):
            for ai, pae in enumerate(PA_PAE):
                for di, idd in enumerate(PA_IDD):
                    # keep the tightness diagonal + one off-diagonal band so the
                    # cube deterministically trims 36 -> 25: drop the 11 rows
                    # where all three indices are strictly interior AND rank is
                    # odd (a fixed, reproducible pruning).
                    rank = pi + ai + di
                    interior = (0 < pi < 3) and (0 < ai < 2) and (0 < di < 2)
                    if interior and rank % 2 == 1:
                        continue
                    rows.append((p1db, pae, idd))
        rows = rows[:25]
        for p1db, pae, idd in rows:
            psat = p1db + PA_PSAT_OFFSET
            name = "bpa-%s-p%s-e%s-i%s" % (band_key.replace("p", ""), p1db, pae, idd)
            desc = ("editcap-bench-v1 PA %s %.3g GHz "
                    "(P1dB>=%s dBm Psat>=%s PAE>=%s%% Idd<=%s mA)"
                    % (b["hint"], b["f0"] / 1e9, p1db, psat, pae, idd))
            cons = [
                ("s21_db", {"min": 10}),
                ("s11_db", {"max": -8}),
                ("p1db_dbm", {"min": p1db, "status": "unsupported"}),
                ("psat_dbm", {"min": psat, "status": "unsupported"}),
                ("pae_pct", {"min": pae, "status": "unsupported"}),
            ]
            objs = [("s21_db", "max", 1.0)]
            topo = {"device_budget": [1, 24], "allow_inductorless": True,
                    "reject_floating": True}
            sizing = {"w_um": [1, 400], "l_fixed": 45e-9, "r_ohm": [10, 20e3],
                      "c_f": [50e-15, 20e-12], "vb_v": [0.2, 1.0]}
            hdr = _PA_HDR + [
                "Band %s (%.4g GHz); P1dB %s dBm, PAE %s%%, Idd %s mA."
                % (b["hint"], b["f0"] / 1e9, p1db, pae, idd)]
            axes = dict(band=band_key, f0_ghz=b["f0"] / 1e9, p1db_dbm=p1db,
                        psat_dbm=psat, pae_pct=pae, idd_ma=idd)
            specs.append(dict(
                cls="pa", name=name, file="pa/%s.yaml" % name, axes=axes,
                objective_gap="p1db_dbm/psat_dbm/pae_pct not computed in "
                "make_objective (pa_harness not wired in); gated in-loop only on "
                "s21_db/s11_db",
                yaml=render(name, desc, "pa", band,
                            {"z0": 50, "input": "VIN1", "output": "VOUT1"},
                            cons, objs, topo, sizing, hdr)))
    return specs


# =============================================================================
# MIXER GRID -- 40 candidates
# =============================================================================
# Axes (brief): RF {915 MHz, 2.442 GHz} x conversion-gain gates {6-15 dB} x
# IIP3 tiers. HARNESS-MEASURABLE metrics ONLY (mixer_harness.py):
#   conv_gain_db, lo_rf_iso_db, lo_if_iso_db, iip3_dbm. (Mixer NF is OUT OF SCOPE
#   v0 -- no PSS/pnoise -- so NO nf_db, matching the example spec.)
# LO convention: harness-injected large-signal SIN drive on a NAMED LO port
# (portnum3 or a body node); NOT a spec-port field. Ports mirror the example:
# input=VIN1 (RF), output=VOUT1 (IF).
#
# OBJECTIVE-GAP: conv_gain/iso/iip3 are NOT computed by make_objective
# (mixer_harness not wired in). Emitted status:unsupported so the loop ignores
# them; the loop can gate NO mixer-specific metric, so a mixer cell is sized as a
# bias/DC structure only until the harness is wired in. Flagged LOUD per-cell.
MIX_BANDS = [("2p4", NB["2p4"]), ("0p9", NB["0p9"])]
MIX_CG = [6, 9, 12, 15]            # conversion-gain gate (dB), brief 6-15
MIX_IIP3 = [-5, 0, 5, 10]          # input-referred IIP3 tiers (dBm)
MIX_LO_RF_ISO = [20, 30, 40]       # LO-RF isolation tiers (dB)

_MIX_HDR = [
    "editcap-bench-v1 mixer spec (circuit_class: mixer). Generated by bench_grid.py.",
    "Down-conversion metrics from lna/mixer_harness.py: conv_gain_db, lo_rf_iso_db,",
    "lo_if_iso_db, iip3_dbm. Mixer NF is OUT OF SCOPE v0 (no PSS/pnoise) -- no nf_db.",
    "LO: harness-injected LARGE-SIGNAL SIN drive on a NAMED LO port (portnum3 or a",
    "body node) -- NOT a spec-port field. Ports: input=VIN1 (RF), output=VOUT1 (IF).",
    "OBJECTIVE-GAP (LOUD): conv_gain/iso/iip3 are MEASURED ONLY by mixer_harness,",
    "NOT wired into make_objective -- NONE is computed in the sizing loop, and the",
    "loop can gate no mixer-specific metric. Emitted status:unsupported. Closing",
    "the gap = wire mixer_harness (LO drive + coherent DFT) into make_objective.",
    "pdk bptm45 default; RUN on gf180 via --pdk gf180mcu.",
]


def gen_mixer():
    specs = []
    for band_key, b in MIX_BANDS:
        band = dict(type="narrowband", f0=b["f0"], f_lo=b["f_lo"], f_hi=b["f_hi"])
        # 4 CG x 4 IIP3 = 16 (iso co-varied on the diagonal) + 4 iso-stress rows
        for cg in MIX_CG:
            for iip3 in MIX_IIP3:
                iso = MIX_LO_RF_ISO[min((MIX_CG.index(cg) + MIX_IIP3.index(iip3)) // 2,
                                        len(MIX_LO_RF_ISO) - 1)]
                specs.append(_mixer_cell(band_key, b, band, cg, iip3, iso))
        for iso in [25, 35, 40, 45]:
            specs.append(_mixer_cell(band_key, b, band, 9, 0, iso, tag="iso"))
    return specs                                       # 2 x (16 + 4) = 40


def _mixer_cell(band_key, b, band, cg, iip3, iso, tag=""):
    lo_if_iso = max(iso - 5, 15)
    suffix = ("-%s" % tag) if tag else ""
    name = "bmx-%s-cg%s-ip%s-iso%s%s" % (band_key.replace("p", ""), cg,
                                         str(iip3).replace("-", "n"), iso, suffix)
    desc = ("editcap-bench-v1 mixer %s %.3g GHz down-mixer "
            "(ConvGain>=%s dB IIP3>=%s dBm LO-RF iso>=%s dB)"
            % (b["hint"], b["f0"] / 1e9, cg, iip3, iso))
    cons = [
        ("conv_gain_db", {"min": cg, "status": "unsupported"}),
        ("lo_rf_iso_db", {"min": iso, "status": "unsupported"}),
        ("lo_if_iso_db", {"min": lo_if_iso, "status": "unsupported"}),
        ("iip3_dbm", {"min": iip3, "status": "unsupported"}),
    ]
    objs = [("conv_gain_db", "max", 1.0), ("iip3_dbm", "max", 0.5)]
    topo = {"device_budget": [3, 24], "allow_inductorless": True,
            "reject_floating": True}
    hdr = _MIX_HDR + ["Band %s (%.4g GHz); ConvGain %s dB, IIP3 %s dBm, iso %s dB."
                      % (b["hint"], b["f0"] / 1e9, cg, iip3, iso)]
    axes = dict(band=band_key, f0_ghz=b["f0"] / 1e9, conv_gain_db=cg,
                iip3_dbm=iip3, lo_rf_iso_db=iso, lo_if_iso_db=lo_if_iso)
    return dict(cls="mixer", name=name, file="mixer/%s.yaml" % name, axes=axes,
                objective_gap="conv_gain_db/lo_rf_iso_db/lo_if_iso_db/iip3_dbm not "
                "computed in make_objective (mixer_harness not wired in); NO mixer "
                "metric is gated in-loop",
                yaml=render(name, desc, "mixer", band,
                            {"z0": 50, "input": "VIN1", "output": "VOUT1"},
                            cons, objs, topo, SIZING_LNA, hdr))


# =============================================================================
# BALUN GRID -- 35 candidates
# =============================================================================
# Axes (brief): bands {915 MHz, 2.442 GHz} x differential-gain x CMRR {20-40 dB}
# x imbalance gates. HARNESS metrics (balun_harness.py, reuses diff3):
#   sds21_db (differential fwd gain), cmrr_db, imbalance_amp_db,
#   imbalance_phase_deg. PLUS real LNA-front metrics nf_db/s11_db/idd_ma which the
#   sizing loop CAN compute (this class has a real single-ended-in structural
#   screen), so a balun cell is PARTIALLY gateable in-loop.
# Port convention: diff3 3-port -- port1 single-ended RF in, port2 INVERTING out
# (spec output=VOUT1), port3 NON-INVERTING out (VOUT2, harness convention).
#
# OBJECTIVE-GAP (PARTIAL): sds21/cmrr/imbalance are MEASURED ONLY by
# balun_harness, NOT in make_objective -> emitted status:unsupported. nf_db/
# s11_db/idd_ma ARE computed in-loop and gated normally. Flagged per-cell.
BAL_BANDS = [("2p4", NB["2p4"]), ("0p9", NB["0p9"])]
BAL_SDS21 = [12, 15, 18]           # differential forward gain (dB)
BAL_CMRR = [20, 30, 40]            # CMRR (dB), brief 20-40
BAL_IMB_AMP = [0.5, 0.3, 0.15]     # amplitude imbalance (dB), tighter->smaller
BAL_IMB_PH = [2.0, 1.0, 0.5]       # phase imbalance (deg)

_BAL_HDR = [
    "editcap-bench-v1 balun spec (circuit_class: balun-lna). Generated by bench_grid.py.",
    "Single-ended-in / differential-out LNA. Metrics from lna/balun_harness.py",
    "(reuses diff3 mixed-mode): sds21_db, cmrr_db, imbalance_amp_db,",
    "imbalance_phase_deg. Ports (diff3 3-port): port1=single-ended RF in (VIN1),",
    "port2=INVERTING out (VOUT1), port3=NON-INVERTING out (VOUT2, harness conv).",
    "OBJECTIVE-GAP (PARTIAL, LOUD): sds21/cmrr/imbalance MEASURED ONLY by",
    "balun_harness (NOT in make_objective) -> status:unsupported. BUT nf_db/s11_db/",
    "idd_ma ARE computed in-loop (real LNA front) and gate normally, so balun cells",
    "are PARTIALLY sizable. Closing gap = wire balun_harness (diff3) into the loop.",
    "Screen: single-ended INPUT (differential:false) + inductor-bearing front.",
    "pdk bptm45 default; RUN on gf180 via --pdk gf180mcu.",
]


def gen_balun():
    specs = []
    for band_key, b in BAL_BANDS:
        band = dict(type="narrowband", f0=b["f0"], f_lo=b["f_lo"], f_hi=b["f_hi"])
        # sds21 x cmrr (9, imbalance tied to cmrr tightness)
        for si, sds21 in enumerate(BAL_SDS21):
            for ci, cmrr in enumerate(BAL_CMRR):
                specs.append(_balun_cell(band_key, b, band, sds21, cmrr,
                                         BAL_IMB_AMP[ci], BAL_IMB_PH[ci]))
        # imbalance-stress rows: fixed sds21=15, cmrr=30, sweep imbalance hard
        for imb_a, imb_p in [(0.4, 1.5), (0.25, 0.8), (0.15, 0.5), (0.1, 0.3)]:
            specs.append(_balun_cell(band_key, b, band, 15, 30, imb_a, imb_p,
                                     tag="imb"))
    # 2 bands x (9 + 4) = 26; add 9 explicit corner rows to reach 35.
    extra = [("2p4", 18, 40, 0.15, 0.5), ("0p9", 18, 40, 0.15, 0.5),
             ("2p4", 12, 25, 0.5, 2.0), ("0p9", 12, 25, 0.5, 2.0),
             ("2p4", 15, 35, 0.2, 0.7), ("0p9", 15, 35, 0.2, 0.7),
             ("2p4", 16, 38, 0.18, 0.6), ("0p9", 16, 38, 0.18, 0.6),
             ("2p4", 14, 33, 0.22, 0.9)]
    for band_key, sds21, cmrr, imb_a, imb_p in extra:
        b = dict(NB[band_key])
        band = dict(type="narrowband", f0=b["f0"], f_lo=b["f_lo"], f_hi=b["f_hi"])
        specs.append(_balun_cell(band_key, b, band, sds21, cmrr, imb_a, imb_p,
                                 tag="x"))
    return specs


def _balun_cell(band_key, b, band, sds21, cmrr, imb_a, imb_p, tag=""):
    suffix = ("-%s" % tag) if tag else ""
    name = "bbl-%s-g%s-c%s-a%s%s" % (band_key.replace("p", ""), sds21, cmrr,
                                     str(imb_a).replace(".", ""), suffix)
    desc = ("editcap-bench-v1 balun %s %.3g GHz single-ended-in/diff-out "
            "(Sds21>=%s CMRR>=%s imbAmp<=%s imbPh<=%s)"
            % (b["hint"], b["f0"] / 1e9, sds21, cmrr, imb_a, imb_p))
    cons = [
        ("sds21_db", {"min": sds21, "status": "unsupported"}),
        ("nf_db", {"max": 3.0}),
        ("s11_db", {"max": -10}),
        ("idd_ma", {"max": 8}),
        ("imbalance_amp_db", {"max": imb_a, "status": "unsupported"}),
        ("imbalance_phase_deg", {"max": imb_p, "status": "unsupported"}),
        ("cmrr_db", {"min": cmrr, "status": "unsupported"}),
    ]
    objs = [("sds21_db", "max", 1.0), ("nf_db", "min", 0.5), ("idd_ma", "min", 0.5)]
    topo = {"differential": False, "reject_floating": True,
            "device_budget": [4, 20], "max_inductors": 4, "l_min": L_MIN,
            "l_max": 12e-9, "allow_inductorless": False}
    hdr = _BAL_HDR + ["Band %s (%.4g GHz); Sds21 %s dB, CMRR %s dB, imb %s dB/%s deg."
                      % (b["hint"], b["f0"] / 1e9, sds21, cmrr, imb_a, imb_p)]
    axes = dict(band=band_key, f0_ghz=b["f0"] / 1e9, sds21_db=sds21, cmrr_db=cmrr,
                imbalance_amp_db=imb_a, imbalance_phase_deg=imb_p)
    return dict(cls="balun-lna", name=name, file="balun/%s.yaml" % name, axes=axes,
                objective_gap="sds21_db/cmrr_db/imbalance_amp_db/imbalance_phase_deg "
                "not computed in make_objective (balun_harness not wired in); "
                "nf_db/s11_db/idd_ma ARE gated in-loop (PARTIAL)",
                yaml=render(name, desc, "balun-lna", band,
                            {"z0": 50, "input": "VIN1", "output": "VOUT1"},
                            cons, objs, topo, SIZING_LNA, hdr))


# =============================================================================
# DRIVER: write files + manifest + validate
# =============================================================================
CLASS_DIRS = {"lna": "lna", "pa": "pa", "mixer": "mixer", "balun-lna": "balun"}
TARGETS = {"lna": 75, "pa": 50, "mixer": 40, "balun-lna": 35}


def build():
    all_specs = gen_lna() + gen_pa() + gen_mixer() + gen_balun()
    for d in set(CLASS_DIRS.values()):
        os.makedirs(os.path.join(OUTDIR, d), exist_ok=True)
    written = []
    for s in all_specs:
        path = os.path.join(OUTDIR, s["file"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(s["yaml"])
        written.append(s)
    manifest = {
        "benchmark": "editcap-bench-v1",
        "generator": "kaggle/bench_grid.py",
        "deterministic": True,
        "pdk_note": "specs default pdk=bptm45; RUN on gf180 via --pdk gf180mcu "
                    "(run-time override, same as the 24-cell capability ladder)",
        "objective_gap_summary": {
            "lna": "none -- s21/nf/s11/idd all computed in make_objective",
            "pa": "p1db_dbm/psat_dbm/pae_pct NOT in make_objective (pa_harness not "
                  "wired in); gated in-loop only on s21_db/s11_db",
            "mixer": "conv_gain_db/lo_rf_iso_db/lo_if_iso_db/iip3_dbm NOT in "
                     "make_objective (mixer_harness not wired in); NO mixer metric "
                     "gated in-loop",
            "balun-lna": "sds21_db/cmrr_db/imbalance_* NOT in make_objective "
                         "(balun_harness not wired in); nf_db/s11_db/idd_ma ARE "
                         "gated in-loop (PARTIAL)",
        },
        "counts": {},
        "cells": [],
    }
    counts = {}
    for s in written:
        counts[s["cls"]] = counts.get(s["cls"], 0) + 1
        manifest["cells"].append({
            "circuit_class": s["cls"],
            "name": s["name"],
            "file": "bench-specs/" + s["file"],
            "axes": s["axes"],
            "objective_gap": s["objective_gap"],
        })
    manifest["counts"] = counts
    with open(os.path.join(OUTDIR, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    return written, counts


def validate(written):
    """Spec.load every generated file; assert counts; return (ok, errs, counts)."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lna"))
    from spec import Spec
    errs = []
    for s in written:
        path = os.path.join(OUTDIR, s["file"])
        try:
            sp = Spec.load(path)
            assert sp.circuit_class == s["cls"], \
                "%s: class %s != %s" % (path, sp.circuit_class, s["cls"])
        except Exception as e:  # noqa: BLE001
            errs.append("%s: %s" % (s["file"], e))
    counts = {}
    for s in written:
        counts[s["cls"]] = counts.get(s["cls"], 0) + 1
    for cls, want in TARGETS.items():
        if counts.get(cls, 0) != want:
            errs.append("COUNT %s: got %d want %d" % (cls, counts.get(cls, 0), want))
    return len(errs) == 0, errs, counts


if __name__ == "__main__":
    written, counts = build()
    ok, errs, vcounts = validate(written)
    print("editcap-bench-v1 spec grid")
    print("  written: %d files under %s" % (len(written), OUTDIR))
    for cls in ("lna", "pa", "mixer", "balun-lna"):
        print("    %-10s %3d  (target %d)" % (cls, vcounts.get(cls, 0), TARGETS[cls]))
    if ok:
        print("  VALIDATE: OK -- all %d specs Spec.load clean; counts match."
              % len(written))
    else:
        print("  VALIDATE: FAILED (%d problems):" % len(errs))
        for e in errs[:50]:
            print("    - %s" % e)
        raise SystemExit(1)

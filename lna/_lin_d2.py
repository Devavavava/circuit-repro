"""WP-LIN D-2 -- the one bounded test-widening: candidate D (current-reuse) and
the isolating input architecture, each with the pre-registered extra device(s),
carried to the screen and (if they survive) real two-tone.

SIDECAR (16-WP-LIN.md D-9; 17-WP-LIN-D2.md law): every read-only harness
(`size.py`, `extract.py`, `iip3.py`, `pgain.py`, `_pgain_mech.py`) is imported
and re-pointed by MODULE attribute, never edited. Reuses rung-0/rung-3 machinery
verbatim (`_lin_baseline`, `_lin_verify`) -- its deck emission, its min-gain S3
builder, its iip3 override pattern.

THE WIDENING IS TEST-SCOPED: the specs' `device_budget: [3,21]` is NOT touched.
The +3 devices (MNMD1 reuse; MNMI1 cascode isolation; MNMI2 front-side
attenuation) are inserted in sidecar space as the user-authorized D-2 allowance
(17-WP-LIN-D2.md S1). The stored topology device count is unchanged; these
inserts live only in the emitted deck, exactly as the D6 switch bank does.

S42.2 / S6.7 node-name discipline: every insert resolves its roles from
`_pgain_mech.resolve_nodes` (structural + cross-checked) and attaches by
resolved role, never by literal node name; each new element is cross-checked by
a second element that must touch it.

Inserted element/param prefixes (disjoint from the topology's own and from the
bias scaffold and from _pgain_mech's MSWG/RSWG/CSWG/VSWG):
    MNMD*/MNMI* (active devices), CCD*/CCI* (AC coupling), RRD*/RRI* (loads/feeds),
    VBD*/VBI* (gate bias sources).  Params: pNMD*W/pNMI*W, pVBD*/pVBI*, etc.

Modes:
  --build-check     emit both widened decks + op-dump every device region (the
                    headroom falsifier for candidate D, PD1)
  --screen          rung-1 screen on both structures at 1.2 V nominal
  --span            the isolating input's match-legal span (PD2) via pgain probe
  --two-tone        real two-tone at D6 min-gain S3, 1.2 V, survivors only
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import extract as E          # noqa: E402
import size as S             # noqa: E402
import iip3 as I3            # noqa: E402
import _pgain_mech as M      # noqa: E402
import _lin_baseline as BL   # noqa: E402
import _lin_verify as V      # noqa: E402
from topology import Topology  # noqa: E402

REPRO = BL.REPRO
OUT = BL.OUT
TOKENS = BL.TOKENS
SIMUL_PARAMS = BL.SIMUL_PARAMS
RECIPE = "wplin-v1"
SOURCE_ARM = "wplin-d2"

BANDS = BL.BANDS                 # {"l5":"dhruva-l5", ...}
F0 = BL.F0
S21_TARGET = {"dhruva-s": 30.0, "dhruva-l1": 25.4,
              "dhruva-l2": 22.3, "dhruva-l5": 22.3}
S11_GATE, IDD_GATE, SPAN_REQ = -10.0, 13.0, 10.6
COARSE = "dhruva-l5"         # band NAME for eval_metrics/spec lookups
COARSE_TAG = "l5"           # tag for F0 (BL.F0 is keyed by tag)
F0_COARSE = F0[COARSE_TAG]

VON, VOFF = 1.1, 0.0             # the deck's own rails (as _pgain_mech)


# ------------------------------------------------------------ substrate
def base_body():
    return BL.base_body()        # (body, sizable, fixed)


def simul_params(vdd="1.2"):
    return BL.simul_params(vdd)


def spec_for(band):
    return S._spec_for_sizing(band)


def _nf(wp):
    return f"NF={{max(1,ceil({wp}/2e-06))}}"


# ============================================================ candidate D
def build_candidate_D(body, params):
    """Current-reuse: MNMD1 stacked under the OUTPUT stage MNM6 so ONE DC branch
    current develops a SECOND transconductance feeding the output node -- the
    textbook stacked-gm / current-reuse cell (S3 row D). No new supply current:
    MNMD1 sits in MNM6's own drain-source path.

    MNM6 today:  drain=outd  gate=g6  source=0   (RR4: VDD->outd, load pR4V)
    After reuse: MNM6 source moves from 0 to a new node `ndreuse`; MNMD1 sits
                 ndreuse--(MNMD1)-->0 carrying MNM6's DC current, its GATE driven
                 by the tank node (the stage's own input, AC-coupled through
                 CCD1) so the reused current develops gm_D into the shared
                 branch. RRD1 sets MNMD1's DC gate bias; the DC current is set by
                 the stack, so Iq(MNM6) is REUSED, not newly drawn.

    Built on the output side, where S45.1's probe map says loading is legal.
    Roles resolved structurally; MNMD1 cross-checked by the re-pointed MNM6 line
    (its source must be the new node) and by CCD1 (must touch the tank + gate).
    """
    r = M.resolve_nodes(body)
    outd, g6, tank = r["outd"], r["g6"], r["tank"]
    out, hit6 = [], 0
    for ln in body.splitlines():
        p = ln.split()
        if p and p[0] == "MNM6":
            if p[3] != "0":
                raise SystemExit("D: MNM6 source is not ground, cannot stack")
            p[3] = "ndreuse"                     # source -> reuse node
            ln, hit6 = " ".join(p), hit6 + 1
        out.append(ln)
    if hit6 != 1:
        raise SystemExit("D: MNM6 source not re-pointed exactly once")
    # MNMD1: drain=ndreuse, gate=ndgate, source=0. Gate AC-coupled to tank
    # (reuse of the stage input), DC-biased by RRD1 from a control source VBD1.
    lines = [
        f"MNMD1 ndreuse ndgate 0 0 nmos W={{pNMD1W}} L=45n {_nf('pNMD1W')}",
        "CCD1 {tank} ndgate {{pCCD1}}".format(tank=tank),
        "RRD1 ndgate nbd1 {pRRD1}",
        "VBD1 nbd1 0 dc {pVBD1}",
    ]
    body2 = "\n".join(out + lines) + "\n"
    # cross-check: CCD1 touches tank and ndgate; MNMD1 drain touches MNM6 source
    e = M._elems(body2)
    assert set(e["CCD1"][:2]) == {tank, "ndgate"}, "D: CCD1 mis-attached"
    assert e["MNMD1"][0] == "ndreuse", "D: MNMD1 drain not on the reuse node"
    # MNM6 element line is `MNM6 <drain> <gate> <source> <bulk> ...`; source is
    # the 3rd node token (index 2 of the post-name tokens)
    assert e["MNM6"][2] == "ndreuse", "D: MNM6 source cross-check"
    # Reuse-device sizing chosen from the build-check headroom sweep: the ONLY
    # builds that keep MNMD1 in SATURATION on this 1.2 V rail are narrow + low
    # gate bias (W<=30 um, VBD1<=0.3); every swing-product-improving build
    # (wider/higher bias) collapses MNMD1 into triode (Vds -> a few mV vs
    # Vdsat -> 100-200 mV). W=30 um / VBD1=0.30 is the max swing-product build
    # that still holds saturation -- and it lands BELOW baseline (54.6 vs
    # 72.9 mV). This is candidate D's headroom wall, measured not argued (PD1).
    extra = {
        "pNMD1W": str(30e-6),     # narrow: the max-swing saturated build
        "pCCD1": str(2e-12),
        "pRRD1": str(10e3),
        "pVBD1": str(0.30),       # low bias: keeps MNMD1 in saturation
    }
    p = dict(params, **extra)
    return body2, p, ["mnmd1"]


# ============================================================ isolating input
def build_isolating_input(body, params, vswg=VOFF):
    """The front-side gain-control structure P4's refutation says needs
    isolation from the C_gd forbidden zone (S45.1).

    MNMI1 -- CASCODE on the combiner CS pair. The CS pair (MNM2/MNM5) drains sit
    on the recombine node `recomb`; we insert MNMI1 in SERIES between the CS pair
    drains and recomb so the drain the C_gd feeds back into is the *cascode
    source*, a low-Z shielded node, while recomb (the tap point) is the cascode
    drain -- high-Z and C_gd-isolated from the input match.

    MNMI2 -- the front-side variable attenuation on the isolated tap: a switched
    shunt device on the cascode drain (recomb), DC-blocked, driven by a pVSWGI2
    control voltage (the D6 mapping's letter: switches driven only by control
    voltages). Because it loads the *isolated* node, it can attenuate without
    spending the input match -- the hypothesis PD2 tests.

    Roles resolved + cross-checked structurally. The CS pair drains are moved to
    `ncas`; MNMI1 ncas..recomb; the recombine-load RR2 stays on recomb, now the
    cascode drain.
    """
    r = M.resolve_nodes(body)
    recomb = r["recomb"]
    # move MNM2/MNM5 drains from recomb to ncas (the cascode source)
    out, hit = [], 0
    for ln in body.splitlines():
        p = ln.split()
        if p and p[0] in ("MNM2", "MNM5"):
            if p[1] != recomb:
                raise SystemExit(f"II: {p[0]} drain is {p[1]}, not recomb")
            p[1] = "ncas"
            ln, hit = " ".join(p), hit + 1
        out.append(ln)
    if hit != 2:
        raise SystemExit(f"II: patched {hit} of 2 CS drains")
    lines = [
        # MNMI1 cascode: drain=recomb (tap), gate=fixed bias, source=ncas
        f"MNMI1 {recomb} ncasg ncas 0 nmos W={{pNMI1W}} L=45n {_nf('pNMI1W')}",
        "RRI1 ncasg nbi1 {pRRI1}",
        "VBI1 nbi1 0 dc {pVBI1}",
        # MNMI2 variable attenuation: DC-blocked shunt on the isolated tap recomb
        "CCI2 {recomb} nii2 {{pCCI2}}".format(recomb=recomb),
        f"MNMI2 nii2 nii2g 0 0 nmos W={{pNMI2W}} L=45n {_nf('pNMI2W')}",
        "RRI2 nii2g nbi2 {pRRI2}",
        "VBI2 nbi2 0 dc {pVSWGI2}",
    ]
    body2 = "\n".join(out + lines) + "\n"
    e = M._elems(body2)
    assert e["MNMI1"][0] == recomb and e["MNMI1"][2] == "ncas", "II: cascode mis-wired"
    assert e["MNM2"][0] == "ncas" and e["MNM5"][0] == "ncas", "II: CS drains not moved"
    assert set(e["CCI2"][:2]) == {recomb, "nii2"}, "II: CCI2 mis-attached"
    # Cascode bias chosen from the build-check headroom sweep: VBI1=0.75, a
    # narrow 30 um cascode is the fair config that keeps MNMI1 in SATURATION on
    # this 1.2 V rail (VBI1>=0.85 collapses it to triode; the CS pair stays
    # sub-threshold regardless -- measured, not assumed).
    extra = {
        "pNMI1W": str(30e-6),     # narrow cascode: the only saturated build
        "pRRI1": str(10e3),
        "pVBI1": str(0.75),       # keeps MNMI1 in saturation (headroom-limited)
        "pCCI2": str(2e-12),
        "pNMI2W": str(50e-6),
        "pRRI2": str(10e3),
        "pVSWGI2": str(vswg),     # the gain-control state variable
    }
    p = dict(params, **extra)
    return body2, p, ["mnmi1", "mnmi2"]


# ============================================================ op / regions
def op_regions(body, params, tag=""):
    cap = {}
    m = S.eval_metrics(body, params, spec_for(COARSE), nf_gated=False,
                       op_capture=cap)
    dev = cap.get("devices", {})
    return m, dev


def z_ac_mag(params, f0):
    R = float(params["pR4V"]); c6 = float(params["pC6V"]); cp2 = 10e-12
    cser = c6 * cp2 / (c6 + cp2); w = 2 * math.pi * f0
    zc = 1.0 / (1j * w * cser); zport = zc + 50.0
    return abs(1.0 / (1.0 / R + 1.0 / zport))


def four_band(body, params, nf=True):
    per = {}
    for b in ("dhruva-s", "dhruva-l1", "dhruva-l2", "dhruva-l5"):
        m = S.eval_metrics(body, params, spec_for(b), nf_gated=nf)
        if m is None:
            return None
        per[b] = m
    return per


def print_regions(dev, names):
    for n in names:
        d = dev.get(n, {})
        print(f"    {n:<7} Id={1e3*(d.get('id') or 0):+8.4f} mA  "
              f"Vds={d.get('vds')}  Vdsat={d.get('vdsat')}  "
              f"Vgs={d.get('vgs')}  Vth={d.get('vth')}  region={d.get('region')}")


# ------------------------------------------------------------ build-check
def cmd_build_check(vdd="1.2"):
    body, sizable, fixed = base_body()
    base = simul_params(vdd)
    result = {"recipe": RECIPE, "source_arm": SOURCE_ARM, "vdd": vdd,
              "diagnosis": "output-swing-current-limit", "structures": {}}
    core = ("mnm1", "mnm2", "mnm3", "mnm4", "mnm5", "mnm6")

    print(f"\n########## D-2 BUILD-CHECK @ pVDD = {vdd} V ##########")

    # baseline op for reference
    bm, bdev = op_regions(body, base)
    print("\n-- baseline (dhruva-simul) core regions --")
    print_regions(bdev, core)
    base_iq = abs(bdev.get("mnm6", {}).get("id", float("nan")))
    base_z = z_ac_mag(base, F0_COARSE)
    print(f"    baseline Iq(MNM6)*|Z_ac| = {base_iq*base_z*1e3:.2f} mV")

    # ---- candidate D ----
    print("\n-- candidate D: current-reuse (MNMD1 stacked under MNM6) --")
    dbody, dparams, dnew = build_candidate_D(body, base)
    dm, ddev = op_regions(dbody, dparams)
    if dm is None:
        print("    SIM FAILED (op)")
        dregions = None
    else:
        print_regions(ddev, list(core) + dnew)
        dregions = {n: ddev.get(n, {}).get("region") for n in list(core) + dnew}
    # emit deck for the record (max + min-gain S3)
    demit = _emit(dbody, dparams, "D", "max", vdd)
    print(f"    emitted {os.path.basename(demit)}")
    result["structures"]["D"] = dict(
        new_devices=dnew, regions=dregions,
        headroom_ok=(dregions is not None and all(
            dregions.get(n) in ("sat", "sub") for n in core)
            and dregions.get("mnmd1") == "sat"),
        deck=os.path.basename(demit),
        iq_z_mv=(abs(ddev.get("mnm6", {}).get("id", 0)) * z_ac_mag(dparams, F0_COARSE) * 1e3
                 if dm is not None else None))

    # ---- isolating input ----
    print("\n-- isolating input (MNMI1 cascode + MNMI2 attenuation) --")
    ibody, iparams, inew = build_isolating_input(body, base, vswg=VOFF)
    im, idev = op_regions(ibody, iparams)
    if im is None:
        print("    SIM FAILED (op)")
        iregions = None
    else:
        print_regions(idev, list(core) + inew)
        iregions = {n: idev.get(n, {}).get("region") for n in list(core) + inew}
    iemit = _emit(ibody, iparams, "II", "max", vdd)
    print(f"    emitted {os.path.basename(iemit)}")
    result["structures"]["II"] = dict(
        new_devices=inew, regions=iregions,
        cascode_sat=(iregions is not None and iregions.get("mnmi1") == "sat"),
        deck=os.path.basename(iemit))

    path = os.path.join(OUT, "_lin_d2_build.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, default=float)
    print(f"\nwrote {path}")
    return result


def _emit(body, params, tag, state, vdd):
    if state == "min":
        body, params = BL.min_gain_body_params(body, params)
    deck = E.build_deck(body, params, F0["l5"], 1.1e9, 2.5e9)
    v = f"{float(vdd):.1f}".replace(".", "p")
    path = os.path.join(REPRO, f"_lin_d2_{tag}_{state}_v{v}.sp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(deck)
    return path


# ------------------------------------------------------------ screen
def _tier_ok(per):
    reasons = []
    bands = ("dhruva-s", "dhruva-l1", "dhruva-l2", "dhruva-l5")
    s11 = max(per[b]["s11_max_db"] for b in bands)
    idd = max(per[b]["idd_ma"] for b in bands)
    if s11 > S11_GATE:
        reasons.append(f"S11 {s11:.3f}>-10")
    if idd > IDD_GATE:
        reasons.append(f"Idd {idd:.3f}>13")
    for b in bands:
        if per[b]["s21_db"] < S21_TARGET[b]:
            reasons.append(f"S21@{b[7:]} {per[b]['s21_db']:.2f}<{S21_TARGET[b]}")
        nf = per[b].get("nf_db")
        nfmax = spec_for(b).constraints["nf_db"]["max"]
        if nf is not None and nf > nfmax:
            reasons.append(f"NF@{b[7:]} {nf:.2f}>{nfmax}")
        if per[b].get("k_min") is not None and per[b]["k_min"] < 1.0:
            reasons.append(f"Kmin@{b[7:]} {per[b]['k_min']:.2f}<1")
    return (len(reasons) == 0), reasons, s11, idd


def cmd_screen(vdd="1.2"):
    body, sizable, fixed = base_body()
    base = simul_params(vdd)
    result = {"recipe": RECIPE, "source_arm": SOURCE_ARM, "vdd": vdd,
              "diagnosis": "output-swing-current-limit", "rows": []}
    core = ("mnm1", "mnm2", "mnm3", "mnm4", "mnm5", "mnm6")

    bper = four_band(body, base)
    bok, _, bs11, bidd = _tier_ok(bper)
    _, bdev = op_regions(body, base)
    base_iqz = abs(bdev.get("mnm6", {}).get("id", 0)) * z_ac_mag(base, F0_COARSE) * 1e3
    print(f"\n########## D-2 SCREEN @ pVDD = {vdd} V ##########")
    print(f"baseline: S11={bs11:.3f} Idd={bidd:.3f} tier_legal={bok} "
          f"Iq*|Z|={base_iqz:.2f} mV")

    def screen_one(label, bfn, kwargs=None):
        kwargs = kwargs or {}
        b2, p2, new = bfn(body, base, **kwargs)
        m, dev = op_regions(b2, p2)
        if m is None:
            print(f"  [{label}] op SIM FAILED");
            result["rows"].append(dict(structure=label, sim="FAILED"))
            return None
        per = four_band(b2, p2, nf=True)
        if per is None:
            print(f"  [{label}] four-band SIM FAILED")
            result["rows"].append(dict(structure=label, sim="FAILED-4band"))
            return None
        ok, reasons, s11, idd = _tier_ok(per)
        regions = {n: dev.get(n, {}).get("region") for n in list(core) + new}
        iq = abs(dev.get("mnm6", {}).get("id", 0))
        iqz = iq * z_ac_mag(p2, F0_COARSE) * 1e3
        all_on = all(regions.get(n) in ("sat", "sub") for n in list(core) + new)
        killed, why = False, []
        if not ok:
            killed = True; why.append("tier-1/2: " + "; ".join(reasons))
        if not all_on:
            off = [n for n in list(core) + new if regions.get(n) not in ("sat", "sub")]
            killed = True; why.append(f"device(s) off/triode: {off}")
        rec = dict(structure=label, new_devices=new, s11_max_db=s11, idd_ma=idd,
                   s21={b[7:]: round(per[b]["s21_db"], 2) for b in
                        ("dhruva-s", "dhruva-l1", "dhruva-l2", "dhruva-l5")},
                   nf_l5=per["dhruva-l5"].get("nf_db"),
                   k_min=min(per[b].get("k_min", 0) for b in
                             ("dhruva-s", "dhruva-l1", "dhruva-l2", "dhruva-l5")),
                   iq_mnm6_ma=iq * 1e3, iq_z_mv=iqz, iq_z_delta_mv=iqz - base_iqz,
                   regions=regions, tier_legal=ok, tier_reasons=reasons,
                   killed=killed, kill_why=why, source_arm=SOURCE_ARM)
        result["rows"].append(rec)
        print(f"  [{label}] S11={s11:.2f} Idd={idd:.2f} "
              f"Iq*Z={iqz:.1f}(dz{iqz-base_iqz:+.1f}) "
              f"S21s={rec['s21']['s']:.1f} NFl5={rec['nf_l5']:.2f} "
              f"-> {'KILL' if killed else 'keep'}"
              + (("  (" + "; ".join(why) + ")") if why else ""))
        return rec

    print("\n-- candidate D: current-reuse --")
    screen_one("D", build_candidate_D)
    print("\n-- isolating input (all-off / max-gain state) --")
    screen_one("II", build_isolating_input, {"vswg": VOFF})

    path = os.path.join(OUT, "_lin_d2_screen.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, default=float)
    print(f"\nwrote {path}")
    return result


# ------------------------------------------------------------ span (PD2)
def cmd_span(vdd="1.2"):
    """The isolating input's match-legal span: sweep the MNMI2 gain-control
    voltage pVSWGI2 over its range, measure S21 (l5 f0) + band-wide S11 at each,
    and report the span between the highest S11-legal state and the lowest
    S11-legal state. The same span the S45.1 walls failed to reach 10.6 dB on."""
    body, sizable, fixed = base_body()
    base = simul_params(vdd)
    print(f"\n########## D-2 ISOLATING-INPUT SPAN @ pVDD = {vdd} V ##########")
    print(f"{'pVSWGI2':>9}{'S21_l5':>10}{'S21_s':>9}{'S11max':>9}"
          f"{'Idd':>8}{'legal':>7}")
    rows = []
    for vg in (0.0, 0.3, 0.5, 0.7, 0.9, 1.1):
        b2, p2, new = build_isolating_input(body, base, vswg=vg)
        per = four_band(b2, p2, nf=False)
        if per is None:
            print(f"{vg:>9.2f}  SIM FAILED")
            continue
        s11 = max(per[b]["s11_max_db"] for b in
                  ("dhruva-s", "dhruva-l1", "dhruva-l2", "dhruva-l5"))
        idd = max(per[b]["idd_ma"] for b in
                  ("dhruva-s", "dhruva-l1", "dhruva-l2", "dhruva-l5"))
        s21_l5 = per["dhruva-l5"]["s21_db"]
        s21_s = per["dhruva-s"]["s21_db"]
        legal = s11 <= S11_GATE
        rows.append(dict(vswg=vg, s21_l5=s21_l5, s21_s=s21_s,
                         s11_max_db=s11, idd_ma=idd, legal=legal))
        print(f"{vg:>9.2f}{s21_l5:>10.3f}{s21_s:>9.3f}{s11:>9.3f}"
              f"{idd:>8.3f}{('yes' if legal else 'NO'):>7}")
    legal_rows = [r for r in rows if r["legal"]]
    if legal_rows:
        s21s = [r["s21_l5"] for r in legal_rows]
        span = max(s21s) - min(s21s)
    else:
        span = 0.0
    reaches = span >= SPAN_REQ
    print("\n" + "=" * 60)
    print(f"  isolating-input match-legal span (l5 f0) = {span:.3f} dB "
          f"({'>= 10.6 -- PD2 FALSIFIED, front-side gain control VIABLE' if reaches else '< 10.6 -- span wall stands'})")
    out = dict(recipe=RECIPE, source_arm=SOURCE_ARM,
               diagnosis="front-end-gain-control-match-wall", vdd=vdd,
               rows=rows, legal_span_db=round(span, 3), reaches_10p6=bool(reaches))
    path = os.path.join(OUT, "_lin_d2_span.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=float)
    print(f"  wrote {path}")
    return out


# ------------------------------------------------------------ two-tone
def _oip3(res):
    return (res["iip3_dbm"] + res["gain_ss"]) if res.get("ok") else None


def measure_widened(bfn, kwargs, state, vdd, pins, bands, replay=3, label=None):
    """Replay-fenced two-tone for a widened structure. Emits its deck, re-points
    iip3 at it + at its own audited S21 (never disabled)."""
    body, sizable, fixed = base_body()
    p0 = simul_params(vdd)
    if state == "min":
        # Build the D6 out-bank S3 min-gain bank FIRST, on the base body (all CS
        # sources grounded -> _pgain_mech's resolve_nodes cross-check passes),
        # THEN apply the widening transform on top. The bank touches only the
        # output drain; the widening's role resolution (outd/tank/recomb) is
        # unaffected, and the CS-source guard that fires if the transform runs
        # first is respected (S42.2 discipline preserved -- structural
        # resolution + cross-check on the banked body).
        body, p0 = BL.min_gain_body_params(body, p0)
    b2, p2, new = bfn(body, p0, **(kwargs or {}))
    deck = E.build_deck(b2, p2, F0["l5"], 1.1e9, 2.5e9)
    stem = f"_lin_d2_tt_{label}_{state}" if label else f"_lin_d2_tt_{state}"
    path = os.path.join(REPRO, f"{stem}.sp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(deck)
    # audited S21 per band on this exact body/params
    ref = {}
    for tag in bands:
        m = S.eval_metrics(b2, p2, spec_for(BANDS[tag]), nf_gated=False)
        if m is None:
            raise SystemExit(f"d2: S21 ref failed {tag}")
        ref[tag] = m["s21_db"]
    I3.S21_REF_DB = dict(ref)
    I3.DESIGNATED = "simul"
    orig = I3.deck_for
    I3.deck_for = lambda tag, sizing=I3.DESIGNATED, _p=path: _p
    I3.private_tmp()
    try:
        reps = []
        for rr in range(replay):
            per = {}
            for tag in bands:
                per[tag] = I3.measure_band(tag, pins, sizing="simul", verbose=(rr == 0))
            reps.append(per)
    finally:
        I3.deck_for = orig

    def gq(res):
        return dict(iip3=res.get("iip3_dbm"), oip3=_oip3(res),
                    gain=res.get("gain_ss"), slope=res.get("slope"))
    spreads = {}
    for tag in bands:
        vals = [gq(rp[tag]) for rp in reps]
        spreads[tag] = {k: (max(v[k] for v in vals) - min(v[k] for v in vals))
                        if all(v[k] is not None for v in vals) else None
                        for k in vals[0]}
    return reps[0], spreads, ref


def cmd_two_tone(which, vdd="1.2", replay=3):
    """Real two-tone at D6 min-gain S3, 1.2 V, four bands, full fences."""
    pins = [-68.0, -64.0, -60.0, -56.0, -52.0]      # §44.3 min-gain window
    builders = {"D": (build_candidate_D, {}),
                "II": (build_isolating_input, {"vswg": VON})}  # min-gain: atten ON
    print(f"\n########## D-2 TWO-TONE @ D6 min-gain S3, {vdd} V ##########")
    out = {"recipe": RECIPE, "source_arm": SOURCE_ARM, "state": "min",
           "vdd": vdd, "diagnosis": "output-swing-current-limit", "candidates": {}}
    for name in which:
        bfn, kw = builders[name]
        print(f"\n===== widened candidate {name} =====")
        first, spreads, ref = measure_widened(bfn, kw, "min", vdd, pins,
                                              list(BANDS), replay, label=name)
        cfg = {}
        for tag in BANDS:
            res = first[tag]
            tgt = res.get("target_dbm")
            passed = bool(res.get("ok") and res.get("iip3_dbm") is not None
                          and tgt is not None and res["iip3_dbm"] >= tgt)
            cfg[tag] = dict(
                iip3_dbm=res.get("iip3_dbm"), oip3_dbm=_oip3(res),
                gain_ss=res.get("gain_ss"), target_dbm=tgt,
                margin_db=(res.get("iip3_dbm") - tgt) if (res.get("iip3_dbm") is not None and tgt is not None) else None,
                slope=res.get("slope"), slope_ok=res.get("slope_ok"),
                d_s21_db=res.get("d_s21_db"), s21_ok=res.get("s21_ok"),
                worst_snr_db=res.get("worst_snr_db"),
                iip3_pt_spread=res.get("iip3_pt_spread"),
                kept=res.get("kept"), ok=res.get("ok"),
                passed=passed, replay_spread=spreads[tag])
            if res.get("ok"):
                print(f"  {tag}: IIP3={res['iip3_dbm']:+.3f} OIP3={_oip3(res):+.3f} "
                      f"G={res['gain_ss']:.2f} tgt={tgt:+.1f} "
                      f"margin={cfg[tag]['margin_db']:+.2f} slope={res['slope']:.3f}"
                      f"{'' if res.get('slope_ok') else '[!]'} "
                      f"{'PASS' if passed else 'FAIL'} "
                      f"replaySpread(iip3)={spreads[tag]['iip3']:.4f}")
            else:
                print(f"  {tag}: NO RESULT ({res.get('why')})")
        n_pass = sum(1 for tag in BANDS if cfg[tag]["passed"])
        out["candidates"][name] = dict(bands=cfg, n_pass=n_pass)
        print(f"  --> {name}: {n_pass}/4 bands pass D5 at the D6 min-gain state")
    path = os.path.join(OUT, "_lin_d2_twotone.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=float)
    print(f"\nwrote {path}")
    return out


def cmd_headroom(vdd="1.2"):
    """The PD1/PD2 headroom fair-chance sweeps, as artefact: candidate D's
    MNMD1 (width x gate bias) and the isolating input's MNMI1 cascode (bias x
    width). This is the measurement that names candidate D's wall: the ONLY
    saturated reuse builds are narrow+low-bias and land BELOW the baseline
    swing product; every swing-improving build collapses to triode -- and even
    in deep triode the product asymptotes at ~72.6 mV, never exceeding the
    72.9 mV baseline, because the output branch current is set by the load
    resistor (RR4), not freed by the stack (the same measured fact that killed
    candidate C in S45.2)."""
    body, _, _ = base_body()
    base = simul_params(vdd)
    core = ("mnm1", "mnm2", "mnm3", "mnm4", "mnm5", "mnm6")
    out = {"recipe": RECIPE, "source_arm": SOURCE_ARM, "vdd": vdd,
           "diagnosis": "output-swing-current-limit",
           "D_sweep": [], "II_sweep": []}
    print(f"\n########## D-2 HEADROOM SWEEPS @ pVDD = {vdd} V ##########")
    print("\n-- candidate D: MNMD1 width x gate bias --")
    print(f"{'W(um)':>7}{'VBD1':>6}{'Vds':>9}{'Vdsat':>9}{'region':>9}"
          f"{'Iq6*Z(mV)':>11}")
    for W in (10e-6, 30e-6, 60e-6, 120e-6, 200e-6):
        for vbd in (0.30, 0.40, 0.50, 0.60):
            b2, p2, _ = build_candidate_D(body, base)
            p2["pNMD1W"] = str(W)
            p2["pVBD1"] = str(vbd)
            m, dev = op_regions(b2, p2)
            if m is None:
                continue
            d = dev.get("mnmd1", {})
            iqz = abs(dev.get("mnm6", {}).get("id", 0)) * \
                z_ac_mag(p2, F0_COARSE) * 1e3
            row = dict(w_um=W * 1e6, vbd1=vbd, vds=d.get("vds"),
                       vdsat=d.get("vdsat"), region=d.get("region"),
                       iq_z_mv=iqz,
                       core_ok=all(dev.get(n, {}).get("region") in
                                   ("sat", "sub") for n in core))
            out["D_sweep"].append(row)
            print(f"{W*1e6:>7.0f}{vbd:>6.2f}{(d.get('vds') or 0):>9.4f}"
                  f"{(d.get('vdsat') or 0):>9.4f}{str(d.get('region')):>9}"
                  f"{iqz:>11.2f}")
    print("\n-- isolating input: MNMI1 cascode bias x width --")
    print(f"{'VBI1':>6}{'W(um)':>7}{'Vds':>9}{'Vdsat':>9}{'region':>9}")
    for vbi in (0.45, 0.55, 0.65, 0.75, 0.85, 0.95):
        for W in (30e-6, 66e-6, 120e-6):
            b2, p2, _ = build_isolating_input(body, base, vswg=VOFF)
            p2["pVBI1"] = str(vbi)
            p2["pNMI1W"] = str(W)
            m, dev = op_regions(b2, p2)
            if m is None:
                continue
            d = dev.get("mnmi1", {})
            row = dict(vbi1=vbi, w_um=W * 1e6, vds=d.get("vds"),
                       vdsat=d.get("vdsat"), region=d.get("region"),
                       mnm2_region=dev.get("mnm2", {}).get("region"),
                       mnm5_region=dev.get("mnm5", {}).get("region"))
            out["II_sweep"].append(row)
            print(f"{vbi:>6.2f}{W*1e6:>7.0f}{(d.get('vds') or 0):>9.4f}"
                  f"{(d.get('vdsat') or 0):>9.4f}{str(d.get('region')):>9}")
    sat_d = [r for r in out["D_sweep"] if r["region"] == "sat"]
    best_sat = max((r["iq_z_mv"] for r in sat_d), default=None)
    out["D_best_saturated_iq_z_mv"] = best_sat
    out["D_max_any_iq_z_mv"] = max((r["iq_z_mv"] for r in out["D_sweep"]),
                                   default=None)
    print(f"\n  D: best SATURATED swing product = {best_sat:.2f} mV; "
          f"max ANY (triode) = {out['D_max_any_iq_z_mv']:.2f} mV; "
          f"baseline = 72.91 mV")
    path = os.path.join(OUT, "_lin_d2_headroom.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=float)
    print(f"  wrote {path}")
    return out


def cmd_mech_check(vdd="1.2", replay=3):
    """The S2.3 mechanism question, measured on the isolating input at l5 f0:
    does FRONT-side attenuation buy IIP3 ~dB-for-dB (S42.6 item 1 read in
    reverse)? Two states: all-off (match-legal max gain) and attenuator-ON
    (the front-side min-gain state -- MATCH-ILLEGAL, S11 ~ -7.2, gate broken;
    measured as a mechanism check ONLY, void for any D5/acceptance claim and
    flagged so). No out-bank: the front-side mechanism IS the gain control
    under test, so state='max' skips the output-side S3 bank."""
    print(f"\n########## D-2 MECH-CHECK (isolating input, l5 f0, {vdd} V) ##########")
    out = {"recipe": RECIPE, "source_arm": SOURCE_ARM, "vdd": vdd,
           "diagnosis": "front-end-gain-control-match-wall",
           "note": "attenuated state is MATCH-ILLEGAL (S11 breaks -10); "
                   "mechanism evidence only, void for D5/acceptance",
           "states": {}}
    for label, vg, pins in (
            ("II_alloff_maxgain", VOFF, [-80.0, -68.0, -56.0, -44.0]),
            ("II_atten_ON", VON, [-68.0, -64.0, -60.0, -56.0, -52.0])):
        first, spreads, ref = measure_widened(
            build_isolating_input, {"vswg": vg}, "max", vdd, pins,
            ["l5"], replay, label=label)
        res = first["l5"]
        out["states"][label] = dict(
            iip3_dbm=res.get("iip3_dbm"), oip3_dbm=_oip3(res),
            gain_ss=res.get("gain_ss"), slope=res.get("slope"),
            slope_ok=res.get("slope_ok"), d_s21_db=res.get("d_s21_db"),
            worst_snr_db=res.get("worst_snr_db"), kept=res.get("kept"),
            ok=res.get("ok"), replay_spread=spreads["l5"])
        if res.get("ok"):
            print(f"  {label:<20} IIP3={res['iip3_dbm']:+.3f} "
                  f"OIP3={_oip3(res):+.3f} G={res['gain_ss']:.2f} "
                  f"slope={res['slope']:.3f} "
                  f"replaySpread={spreads['l5']['iip3']:.4f}")
        else:
            print(f"  {label:<20} NO RESULT ({res.get('why')})")
    a = out["states"].get("II_alloff_maxgain", {})
    b = out["states"].get("II_atten_ON", {})
    if a.get("ok") and b.get("ok"):
        dg = a["gain_ss"] - b["gain_ss"]
        di = b["iip3_dbm"] - a["iip3_dbm"]
        out["delta_gain_db"] = dg
        out["delta_iip3_db"] = di
        print(f"\n  front-side attenuation: dG = {dg:+.2f} dB, "
              f"dIIP3 = {di:+.2f} dB (S2.3 predicts ~dB-for-dB)")
        print("  (attenuated state is MATCH-ILLEGAL -- mechanism evidence only)")
    path = os.path.join(OUT, "_lin_d2_mechcheck.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=float)
    print(f"  wrote {path}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-check", action="store_true")
    ap.add_argument("--screen", action="store_true")
    ap.add_argument("--span", action="store_true")
    ap.add_argument("--two-tone", action="store_true")
    ap.add_argument("--mech-check", action="store_true")
    ap.add_argument("--headroom", action="store_true")
    ap.add_argument("--vdd", default="1.2")
    ap.add_argument("--which", default="D,II")
    ap.add_argument("--replay", type=int, default=3)
    a = ap.parse_args()
    from moves import private_tmp
    private_tmp(os.path.join(OUT, "lin_d2_tmp"))
    if a.build_check:
        cmd_build_check(a.vdd)
    if a.screen:
        cmd_screen(a.vdd)
    if a.span:
        cmd_span(a.vdd)
    if a.two_tone:
        cmd_two_tone([x.strip() for x in a.which.split(",") if x.strip()],
                     a.vdd, a.replay)
    if a.mech_check:
        cmd_mech_check(a.vdd, a.replay)
    if a.headroom:
        cmd_headroom(a.vdd)
    if not (a.build_check or a.screen or a.span or a.two_tone or a.mech_check
            or a.headroom):
        ap.error("one of --build-check/--screen/--span/--two-tone/"
                 "--mech-check/--headroom")


if __name__ == "__main__":
    main()

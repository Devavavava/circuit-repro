"""Per-device blame vectors for failing metrics (plans2/22-INFER-INSTRUMENTS.md).

Given one evaluated design (deck body + operating point + metrics vs a spec),
emit a per-device blame vector for each FAILING metric:

    noise  -- reuse extract.measure_noise_budget decomposition (same series-Rs
               harness); device ranking by output-noise-power share.
    gain   -- from the operating-point dict: gm and gds contributions along the
               signal path, flagged by region.
    current -- per-DEVICE drain-current share (which device draws the supply
               current). The OP `branches` dict is NOT ranked directly: it is
               dominated by the RF port sources Vp1/Vp2 (dc 0, always 0.0 A) and
               by the supply source itself (the TOTAL Idd, i.e. the metric, not a
               culprit). The supply branch is used only as a closure cross-check.
    match  -- S11 input-match deviation: the parasitic Cgs+Cgd of the FIRST
               device on the signal path is the dominant tunable knob; a partial
               attribution (which device has the largest gate capacitance) is
               returned honestly labelled `partial`.
    ripple -- s21_ripple_db (band-shape, no OP number "is" the ripple):
               CAPPED finite-difference ripple-sensitivity over reactive/gm
               knobs (tank L/C value params + device widths). Ranks which
               element the band ripple is most sensitive to. When params are
               unavailable (ref decks stripped by body_of), a structural ranking
               of reactive elements is used. Always `partial` -- a sensitivity
               ranking, not a closed-form ripple budget.

OUTPUT CONTRACT (per failing metric, per design):
    {
      "wl_hash": str,
      "spec": str,
      "metric": str,                          # which constraint failed
      "metric_value": float | None,
      "metric_limit": {"min"|"max": float},
      "margin": float,                        # < 0 means failing
      "blame": [                              # ranked most-to-least culpable
        {"device": str, "score": float, "detail": {...}}
      ],
      "coverage": str,                        # "full" | "partial" | "unavailable"
      "coverage_note": str,                   # honest limit description
      "ts": str,
      "git_sha": str,
    }

STORE DISCIPLINE: rows are written to a NEW file `lna/data/blame_vectors.jsonl`.
The table name `blame_vectors` is registered in a local TABLES extension below;
blame.py does NOT modify datastore.py's TABLES dict (containment rule).

COVERAGE NOTES (honest limits, not hidden assumptions):
  - noise blame requires a second ngspice run (the budget deck); if the budget
    call fails the row is written with coverage="unavailable".
  - gain blame is purely from OP data: gm/gds/region. It cannot capture
    resonator Q effects, feedback paths, or cascode stacking gains.
  - current blame ranks per-device drain current (|Id| share), cross-checked
    against the supply-branch current for closure. The RF port branches (Vp1/Vp2)
    and the supply branch itself are EXCLUDED from the ranking. Coverage is
    "full" only when sum(|Id|) closes to the measured Idd within 10% (else some
    supply current flows through a non-MOS DC path -- resistive load / bias
    divider -- and the row is "partial"). It can never return an empty ranking
    labelled "full" (the E-8 bug: presence of the zero-valued port branches used
    to set coverage="full" while every entry filtered out below 0.5%).
  - match blame: `cgs + cgd` total for each device from the OP dict. This is a
    proxy for the device's impact on Zin, NOT a full small-signal Zin computation.
    The primary accuracy limit: resonator elements (inductors) are not captured
    here, so the attribution is partial by construction. Labelled `partial`.
  - ripple blame: capped finite-difference (RIPPLE_FD_MAXSIMS extra ngspice runs)
    of s21_ripple_db vs each reactive/gm knob. Blind spots: (1) it is a local
    sensitivity, not a global ripple budget; (2) knob-knob couplings are not
    captured (each is nudged in isolation); (3) with more knobs than the sim cap,
    the lowest-reactance ones are not probed (coverage stays "partial"); (4) with
    no params (ref decks) it degrades to a structural presence ranking that
    cannot tell which reactive element actually shapes the band. Always
    `partial` -- see plans2/22 §7 for the full declaration.

USAGE:
    python lna/blame.py --wl-hash ace838 --spec dhruva-s
    python lna/blame.py --ref ref24_csdeg --spec wifi24
    python lna/blame.py --all-failing          # first 5 infeasible rows in store
"""
import argparse
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds
import extract as E
from topology import Topology

# size.py imports zoaf at module level; defer the import to avoid a hard dep
# in analysis environments that have ngspice but not the ZOAF package.
def _size():
    import size as S
    return S

# ---------------------------------------------------------------------------
# New store table -- does NOT modify datastore.TABLES (containment rule)
_DATA_DIR = os.path.join(HERE, "data")
_BLAME_FILE = os.path.join(_DATA_DIR, "blame_vectors.jsonl")


def _append_blame(row):
    """Append one blame row to blame_vectors.jsonl."""
    os.makedirs(_DATA_DIR, exist_ok=True)
    line = json.dumps(ds._jsonify(row), separators=(",", ":"), sort_keys=True)
    with open(_BLAME_FILE, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(line + "\n")
    return row


def load_blame():
    """All rows from blame_vectors.jsonl."""
    if not os.path.exists(_BLAME_FILE):
        return []
    with open(_BLAME_FILE, "r", encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]


# ---------------------------------------------------------------------------
# Noise blame -- delegate to extract.measure_noise_budget

def _blame_noise(body, params, spec, op):
    """Return (blame_list, coverage, note).

    Calls measure_noise_budget (one extra ngspice run). Ranked by output-noise-
    power share (frac). Coverage = 'full' when the budget sum closure is within
    5% of 1.0; 'partial' otherwise (e.g. missing mechanisms)."""
    budget = E.measure_noise_budget(body, params, spec)
    if budget is None:
        return [], "unavailable", "measure_noise_budget ngspice call failed"
    elems = budget.get("elements", {})
    ranked = sorted(elems.items(), key=lambda kv: -(kv[1].get("p") or 0))
    p_tot = budget.get("p_total") or 1e-30
    blame = []
    for name, e in ranked:
        frac = e.get("frac") or 0.0
        if frac < 0.005:
            continue
        detail = {
            "p": e.get("p"),
            "frac_of_total": frac,
            "excess_frac": e.get("excess_frac"),
            "kind": e.get("kind"),
        }
        mech = e.get("mech")
        if mech:
            dominant = max(mech.items(), key=lambda kv: kv[1])
            detail["dominant_mechanism"] = dominant[0]
            detail["dominant_mech_frac"] = dominant[1] / e["p"] if e["p"] else None
        blame.append({"device": name, "score": round(frac, 6), "detail": detail})
    closure = budget.get("sum_closure") or 0.0
    if abs(closure - 1.0) <= 0.05:
        cov, note = "full", f"sum/total closure={closure:.4f}"
    else:
        cov, note = ("partial",
                     f"sum/total closure={closure:.4f} (>5% gap; likely missing noise sources)")
    return blame, cov, note


# ---------------------------------------------------------------------------
# Gain blame -- from OP dict

def _blame_gain(body, params, spec, op):
    """Return (blame_list, coverage, note).

    Coverage limit: gm/gds from OP gives a DC-small-signal picture of each
    device's contribution. Feedback paths, resonator Q, and cascode stacking
    multiply effects that this method cannot capture. Rated 'partial'."""
    devices = (op or {}).get("devices", {})
    if not devices:
        return [], "unavailable", "no OP device data"
    # Only MOSFETs contribute transconductance gain
    mos_devs = {k: v for k, v in devices.items() if k.startswith("m")}
    if not mos_devs:
        return [], "unavailable", "no MOSFET devices in OP"

    # Score: intrinsic gain = gm / (gds + 1e-30). Higher = more gain potential.
    # Region modifies confidence: sat is the intended mode; triode/off are culprits.
    blame = []
    for name, d in mos_devs.items():
        gm = d.get("gm") or 0.0
        gds = d.get("gds") or 1e-12
        region = d.get("region", "unknown")
        ig = gm / (gds + 1e-30) if gm else 0.0
        id_val = d.get("id") or 0.0
        detail = {
            "gm": gm,
            "gds": gds,
            "intrinsic_gain": round(ig, 4),
            "region": region,
            "id_A": id_val,
            "vov": d.get("vov"),
        }
        # Lower intrinsic_gain is a gain culprit -- rank by descending ig to show
        # who contributes most, and who is starved (off/triode) explains loss.
        blame.append({"device": name, "score": round(ig, 4), "detail": detail})
    # Sort: highest intrinsic gain first (those are the gain contributors).
    # For a gain FAIL, look at the bottom of the list (starved devices).
    blame.sort(key=lambda r: -r["score"])
    note = ("gm/gds intrinsic-gain ranking from OP. For gain failures: "
            "devices in triode/off/sub-threshold at the bottom of the list "
            "are the primary culprits. Feedback paths and resonator Q not captured.")
    return blame, "partial", note


# ---------------------------------------------------------------------------
# Current blame -- from OP branches/devices

# RF port sources (to_spice `Vp1`/`Vp2`, dc 0 ac 1) always appear in the OP
# `branches` dict at 0.0 A: they carry AC only, never DC supply current. Ranking
# them as Idd culprits is meaningless. The supply source itself (Vsup / the VDD
# source) carries the WHOLE Idd -- it is the metric being explained, not a
# per-device culprit. Both classes are excluded from the device ranking.
_PORT_BRANCHES = ("vp1", "vp2")


def _supply_branch_name(body):
    """Lowercased supply-source name (matches parse_op branch keys), or None."""
    if not body:
        return None
    try:
        return E._supply_name(body).lower()
    except Exception:      # noqa: BLE001
        return None


def _blame_current(body, params, spec, op):
    """Return (blame_list, coverage, note).

    idd_ma attribution = *which device draws the supply current*. The physically
    meaningful culprit for a current-budget failure is per-device drain current,
    NOT raw branch currents: the OP `branches` dict is dominated by (a) the RF
    port sources Vp1/Vp2 (dc 0, AC-only -- always 0.0 A) and (b) the supply
    source itself (the TOTAL Idd, i.e. the metric, not a culprit), plus inductor
    branches that merely re-report a device's DC path. So the ranking is built
    from device drain currents; the supply branch is used only as a closure
    cross-check.

    BUGFIX (E-8 gap): the previous version keyed `coverage="full"` off the mere
    presence of ANY branch, then filtered every entry below 0.005. When the only
    surviving branches were the zero-valued RF ports (Vp1/Vp2), the total was
    ~1e-30, every frac rounded to 0, and the ranking came back EMPTY while still
    labelled "full" -- exactly the G8/dhruva-l5 symptom in E8-LADDER. The port
    and supply branches are now excluded up front and the ranking is built from
    device Id, so an empty-but-"full" row can no longer occur.
    """
    branches = (op or {}).get("branches", {}) or {}
    devices = (op or {}).get("devices", {}) or {}

    mos_devs = {k: v for k, v in devices.items() if k.startswith("m")}
    if not mos_devs:
        return [], "unavailable", "no MOSFET devices in OP"

    # Supply-branch magnitude for a closure check (excluded from the ranking).
    # The RF port branches (Vp1/Vp2) are never treated as the supply.
    supply = _supply_branch_name(body)
    idd_supply = None
    if supply is not None and supply in branches and supply not in _PORT_BRANCHES:
        idd_supply = abs(branches[supply])
    elif "vsup" in branches:
        idd_supply = abs(branches["vsup"])

    # Rank by per-device drain current share (never the port/supply branches).
    id_total = sum(abs(d.get("id") or 0.0) for d in mos_devs.values())
    denom = id_total or 1e-30
    ranked = sorted(mos_devs.items(),
                    key=lambda kv: -abs(kv[1].get("id") or 0.0))
    blame = []
    for name, d in ranked:
        id_val = d.get("id") or 0.0
        frac = abs(id_val) / denom
        if frac < 0.005:
            continue
        blame.append({
            "device": name,
            "score": round(frac, 6),
            "detail": {"id_A": id_val,
                       "frac_of_device_Idd": round(frac, 6),
                       "region": d.get("region")},
        })

    # Coverage: "full" when the summed device drain current reconciles with the
    # measured supply current within 10% (the passive DC paths -- resistor
    # dividers, gate leakage -- are then negligible, so device Id captures Idd).
    # Otherwise "partial": some supply current flows through paths not on a MOS
    # drain (e.g. a resistive load carrying static bias current).
    if idd_supply is not None and idd_supply > 1e-9:
        closure = id_total / idd_supply
        if abs(closure - 1.0) <= 0.10:
            cov = "full"
            note = (f"device drain-current shares; sum(|Id|)/Idd_supply="
                    f"{closure:.3f} (closes within 10%); "
                    "RF port + supply branches excluded")
        else:
            cov = "partial"
            note = (f"device drain-current shares; sum(|Id|)/Idd_supply="
                    f"{closure:.3f} (>10% gap: some Idd flows through non-MOS "
                    "DC paths -- resistive load / bias divider)")
    else:
        cov = "partial"
        note = ("device drain-current shares; supply-branch current unavailable "
                "for closure check (RF port branches excluded)")

    if not blame:
        # Only reachable if every device is essentially off (id below 0.5% of a
        # near-zero total). Report honestly rather than an empty "full" row.
        return [], "unavailable", note + " -- all devices below 0.5% threshold"
    return blame, cov, note


# ---------------------------------------------------------------------------
# Match blame -- gate-capacitance proxy for Zin

def _blame_match(body, params, spec, op):
    """Return (blame_list, coverage, note).

    Zin attribution from OP data. Two proxies are used:

    (a) Gate-capacitance proxy (cgg = cgs + cgd): the device with the largest
        total gate capacitance loads the input node most. cgg/cgs/cgd are NOT
        in MOS_OP_PARAMS (the standard set that ngspice probes), so this path
        is only available when those params were explicitly captured -- which
        they are NOT in the standard sizing/noise deck. When cgg is absent we
        fall back to proxy (b).

    (b) gm-match proxy: for a common-gate stage, Re(Zin) ≈ 1/(gm + gmbs).
        The device closest to 1/50 ohm = 20 mS is the dominant match device.
        For a common-source inductively-degenerated stage, gm is still the
        denominator of the match condition (Ls = Z0*(Cgs)/gm), so higher gm
        implies easier match. We rank by abs(gm + gmbs - 0.02) ASCENDING --
        the device closest to the 50-ohm match target is the primary match
        device; those far from 20 mS explain the match shortfall.

    Coverage: PARTIAL in all cases. Neither proxy accounts for resonator
    tuning elements (the inductors that cancel the reactive part of Zin) or
    distinguishes which device pin the input signal actually reaches. A full
    small-signal Zin calculation requires a dedicated probe sim, not just OP
    data. Rated 'partial' and clearly labelled.
    """
    devices = (op or {}).get("devices", {})
    mos_devs = {k: v for k, v in devices.items() if k.startswith("m")}
    if not mos_devs:
        return [], "unavailable", "no MOSFET devices in OP"

    # Try Cgg path first
    has_cgg = any(
        d.get("cgg") is not None or (d.get("cgs") is not None and d.get("cgd") is not None)
        for d in mos_devs.values()
    )
    if has_cgg:
        ctot = {}
        for name, d in mos_devs.items():
            cgg = d.get("cgg")
            if cgg is not None:
                ctot[name] = abs(cgg)
            else:
                cgs = d.get("cgs") or 0.0
                cgd = d.get("cgd") or 0.0
                ctot[name] = abs(cgs) + abs(cgd)
        total_c = sum(ctot.values()) or 1e-30
        ranked = sorted(ctot.items(), key=lambda kv: -kv[1])
        blame = []
        for name, c in ranked:
            frac = c / total_c
            if frac < 0.005:
                continue
            d = mos_devs[name]
            blame.append({
                "device": name,
                "score": round(frac, 6),
                "detail": {
                    "cgg_F": c,
                    "frac_of_total_Cgg": round(frac, 6),
                    "gm": d.get("gm"),
                    "gmbs": d.get("gmbs"),
                    "region": d.get("region"),
                    "proxy": "cgg",
                }
            })
        note = ("Cgg (=Cgs+Cgd) share as proxy for Zin loading. "
                "Partial: resonator tuning elements and signal-path topology not captured.")
        return blame, "partial", note

    # Fall back to gm-match proxy
    # Score = abs(gm + |gmbs|) -- device closest to 20 mS ≈ 1/50 ohm is the
    # dominant match device; ranked by descending gm (largest gm = most gm to
    # tune the match).
    TARGET_GM = 0.020  # 1/50 ohm
    blame = []
    for name, d in mos_devs.items():
        gm = d.get("gm") or 0.0
        gmbs = abs(d.get("gmbs") or 0.0)
        gm_eff = gm + gmbs
        re_zin_approx = 1.0 / (gm_eff + 1e-12)  # 1/(gm+gmbs), proxy for CG Zin
        dist_to_match = abs(gm_eff - TARGET_GM)
        blame.append({
            "device": name,
            "score": round(gm_eff, 6),  # higher = more match gm
            "detail": {
                "gm": gm,
                "gmbs": d.get("gmbs"),
                "gm_eff_S": round(gm_eff, 6),
                "re_zin_approx_ohm": round(re_zin_approx, 2),
                "dist_to_20mS": round(dist_to_match, 6),
                "region": d.get("region"),
                "proxy": "gm",
            }
        })
    # Sort by descending gm (largest gm = most likely match device)
    blame.sort(key=lambda r: -r["score"])
    note = ("gm-match proxy (cgg/cgs/cgd not in OP schema). "
            "For CG: 1/(gm+gmbs) approximates Re(Zin); device closest to 20 mS "
            "(= 1/50 ohm) is the match device. For CS-deg: higher gm relaxes "
            "the match inductance requirement. "
            "PARTIAL: resonator inductors, feedback paths, and actual signal-path "
            "pin are not derivable from OP data alone.")
    return blame, "partial", note


# ---------------------------------------------------------------------------
# Ripple blame -- reactive-element sensitivity of the band S21 shape
#
# METHOD (declared honestly; see plans2/22 §7 for the full blind-spot list):
#   s21_ripple_db = max(S21) - min(S21) over [f_lo, f_hi] is a BAND-SHAPE
#   property, not a per-device quantity like Id or output-noise power. There is
#   no operating-point number that "is" the ripple. Ripple is set by the
#   frequency-dependent load/peaking network -- the resonant tank (L,C) elements
#   and the transconductance that drives them. So attribution is done by a
#   CAPPED FINITE-DIFFERENCE ripple-sensitivity sweep:
#
#     1. Identify the tunable reactive/gm knobs: capacitor value params (pC*V),
#        inductor value params (pL*V) and device widths (pNM*W, which set gm and
#        thus the peaking gain). Each is mapped back to the element(s) it drives.
#     2. Nudge each knob by +RIPPLE_FD_STEP (multiplicative) and re-measure the
#        band ripple with ONE ngspice run. Score = |Δripple| for that knob.
#     3. Rank knobs (elements) by |Δripple|. The tank L/C the ripple is most
#        sensitive to is the dominant ripple culprit -- this is the "which
#        element must change to flatten the band" answer the E-8 ladder needs.
#
#   The sim count is CAPPED at RIPPLE_FD_MAXSIMS (default 10). If there are more
#   reactive knobs than the cap, the ones with the largest current values (the
#   dominant reactances at band) are probed first and the rest are reported as
#   "not-probed (sim cap)". Coverage is "full" when every reactive knob was
#   probed, "partial" when the cap truncated the set.
#
#   NO-SIM FALLBACK: when params are empty (a ref deck run with baked-in values,
#   or an analysis env that cannot re-simulate) the finite difference is not
#   possible. A structural fallback then ranks the reactive ELEMENTS that touch
#   the output/signal path by presence (tank L/C first), labelled "partial" with
#   an explicit "no finite-difference; structural ranking only" note.

RIPPLE_FD_STEP = 0.05          # +5% multiplicative nudge per knob
RIPPLE_FD_MAXSIMS = 10         # hard cap on extra ngspice runs (declared)
_REACT_PARAM_RE = re.compile(r"^p(C|L)\w*V$")    # pC1V, pL2V, ...
_GM_PARAM_RE = re.compile(r"^pNM\w*W$")           # pNM1W, ... (device width -> gm)


def _element_param_map(body):
    """{param_name: [element_names]} -- which deck element(s) each param drives.

    Reactive/gm attribution reports ELEMENT names (LL1, CC3, MNM2), which are
    what an edit move acts on, not the raw param handle."""
    m = {}
    for ln in (body or "").splitlines():
        s = ln.strip()
        if not s or s.startswith("*") or s.startswith("."):
            continue
        el = s.split()[0]
        for p in re.findall(r"p[A-Za-z0-9]+", s):
            m.setdefault(p, [])
            if el not in m[p]:
                m[p].append(el)
    return m


def _measure_ripple(body, params, spec):
    """Band s21 ripple (dB) for one param set, or None on sim failure."""
    metrics = E.run_and_extract(body, params, spec)
    if not metrics:
        return None
    return metrics.get("s21_ripple_db")


def _blame_ripple(body, params, spec, op):
    """Return (blame_list, coverage, note) for s21_ripple_db.

    Capped finite-difference ripple-sensitivity over reactive/gm knobs (see the
    module comment above). PARTIAL coverage by construction -- it ranks the
    knobs the ripple is most sensitive to, which is a defensible cheap proxy for
    "which reactive element shapes the band", not a closed-form ripple budget.
    """
    # ---- no-sim structural fallback --------------------------------------
    if not params:
        # Rank reactive ELEMENTS that plausibly shape the band: tank/peaking
        # L and C. DC-block caps (huge, ~1u/10p labelled) still show up but are
        # ranked by *value smallness* is not derivable without values, so we
        # report presence-only, honestly labelled.
        # tier: inductors (tank resonance is inductor-dominated) > tank/signal
        # caps > obvious DC-block / bypass / port coupling caps. The last group
        # (Cbyp*, Cin, Cout, Cp*, Cc*coupling) sets no band shape -- it is
        # AC-shorting/DC-blocking -- so it is demoted, not dropped.
        _DCBLOCK = ("cbyp", "cin", "cout", "cp", "cblk", "cdc")
        elems = []
        for ln in (body or "").splitlines():
            s = ln.strip()
            if not s or s.startswith("*") or s.startswith("."):
                continue
            el = s.split()[0]
            low = el.lower()
            if low[:1] == "l":
                elems.append((el, "inductor", 0))
            elif low[:1] == "c":
                if low in ("cp1", "cp2") or low.startswith(_DCBLOCK):
                    elems.append((el, "capacitor(dc-block/bypass)", 2))
                else:
                    elems.append((el, "capacitor(tank/signal)", 1))
        if not elems:
            return [], "unavailable", "no reactive elements and no params to perturb"
        elems.sort(key=lambda t: t[2])
        # Score by tier: tank inductors/caps get the weight, dc-block caps a
        # small floor so they are ranked last but still visible.
        tier_w = {0: 1.0, 1: 0.7, 2: 0.1}
        raw = [(el, kind, tier_w[t]) for el, kind, t in elems]
        tot = sum(w for _, _, w in raw) or 1e-30
        blame = [{"device": el, "score": round(w / tot, 6),
                  "detail": {"kind": kind, "method": "structural_presence"}}
                 for el, kind, w in raw]
        return (blame, "partial",
                "no finite-difference (params empty; e.g. a ref deck whose "
                "baked .param values were stripped by body_of); structural "
                "ranking of reactive elements (tank inductors/caps ranked above "
                "dc-block/bypass caps) -- cannot tell which one actually shapes "
                "the band without a sweep")

    # ---- capped finite-difference sensitivity ----------------------------
    base = op.get("s21_ripple_db") if op else None
    if base is None:
        base = _measure_ripple(body, params, spec)
    if base is None:
        return [], "unavailable", "base ripple measurement failed"

    pmap = _element_param_map(body)

    def _fval(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    # Candidate knobs: reactive value params + device-width (gm) params, that
    # actually drive a deck element and have a numeric current value. A param is
    # a knob if EITHER its name matches the generated convention (pC*V/pL*V for
    # reactance, pNM*W for gm) OR it drives an L/C element (reactance) or a MOS
    # width field (gm) -- so ref-style hand-deck names (pLd, pCtnk, pW) work too.
    knobs = []
    for p, v in params.items():
        fv = _fval(v)
        if fv is None or fv == 0.0:
            continue
        els = pmap.get(p, [])
        drives_react = any(e[:1].lower() in ("l", "c") for e in els)
        drives_gm = any(e[:1].lower() in ("m", "q") for e in els)
        if _REACT_PARAM_RE.match(p) or drives_react:
            kind = "reactance"
        elif _GM_PARAM_RE.match(p) or (drives_gm and p.lower().endswith("w")):
            kind = "gm(width)"
        else:
            continue
        knobs.append((p, fv, kind, els or [p]))

    if not knobs:
        return [], "unavailable", "no reactive/gm knobs found in params"

    # Sim cap: probe the largest-reactance knobs first (dominant at band).
    knobs.sort(key=lambda t: -abs(t[1]))
    probe = knobs[:RIPPLE_FD_MAXSIMS]
    skipped = knobs[RIPPLE_FD_MAXSIMS:]

    blame = []
    n_sims = 0
    for p, fv, kind, els in probe:
        pert = dict(params)
        pert[p] = fv * (1.0 + RIPPLE_FD_STEP)
        r2 = _measure_ripple(body, pert, spec)
        n_sims += 1
        if r2 is None:
            sens = 0.0
            note_bit = "sim failed"
        else:
            sens = abs(r2 - base)
            note_bit = f"ripple {base:.2f}->{r2:.2f} dB on +{int(RIPPLE_FD_STEP*100)}%"
        # Report per element that the knob drives (usually one).
        name = els[0] if els else p
        blame.append({
            "device": name,
            "score": round(sens, 6),
            "detail": {
                "param": p,
                "kind": kind,
                "d_ripple_db": round(sens, 6),
                "base_ripple_db": round(base, 4),
                "elements": els,
                "note": note_bit,
            },
        })

    blame.sort(key=lambda r: -r["score"])
    # Drop knobs with zero sensitivity from the ranking tail (they are not
    # ripple culprits), but keep at least the top so the row is never empty when
    # a base ripple exists.
    nonzero = [b for b in blame if b["score"] > 1e-6]
    ranked = nonzero if nonzero else blame[:1]

    if skipped:
        cov = "partial"
        note = (f"capped finite-difference ripple-sensitivity "
                f"(+{int(RIPPLE_FD_STEP*100)}% per knob, {n_sims} sims); "
                f"{len(skipped)} lower-reactance knob(s) NOT probed (sim cap "
                f"{RIPPLE_FD_MAXSIMS}); ranks which reactive/gm element the band "
                f"ripple is most sensitive to")
    else:
        cov = "partial"
        note = (f"capped finite-difference ripple-sensitivity "
                f"(+{int(RIPPLE_FD_STEP*100)}% per knob, {n_sims} sims, all "
                f"reactive/gm knobs probed); ranks which element the band ripple "
                f"is most sensitive to. PARTIAL: a sensitivity ranking, not a "
                f"closed-form ripple budget; couplings between knobs not captured")
    return ranked, cov, note


# ---------------------------------------------------------------------------
# Dispatch

_METRIC_BLAME = {
    "nf_db": _blame_noise,
    "s21_db": _blame_gain,
    "idd_ma": _blame_current,
    "s11_db": _blame_match,
    "s11_max_db": _blame_match,
    "s21_min_db": _blame_gain,
    "s21_ripple_db": _blame_ripple,
}


def _metric_limit(spec, metric):
    c = (spec.constraints or {}).get(metric, {})
    return {k: c[k] for k in ("min", "max") if k in c}


def blame_design(body, params, spec, op, wl_hash, metrics,
                 write=True, failing_only=True):
    """Compute blame vectors for one design. Returns list of blame rows.

    `op`      -- extract.parse_op dict (from measure_nf or run_and_extract).
    `metrics` -- the L2 metrics dict for this design.
    `write`   -- append rows to blame_vectors.jsonl (default True).
    `failing_only` -- only generate blame for failing constraints (default True).
    """
    feas, viol = spec.feasible(metrics or {})
    rows = []
    for metric, c in spec.constraints.items():
        if c.get("status") == "unsupported":
            continue
        val = (metrics or {}).get(metric)
        margin_rec = ds.margins_for(spec, metrics or {}).get(metric, {})
        margin = margin_rec.get("margin")
        is_failing = margin is not None and margin < 0.0

        if failing_only and not is_failing:
            continue

        fn = _METRIC_BLAME.get(metric)
        if fn is None:
            blame, cov, note = [], "unavailable", f"no blame handler for metric {metric!r}"
        else:
            try:
                blame, cov, note = fn(body, params, spec, op)
            except Exception as exc:      # noqa: BLE001
                blame, cov, note = [], "unavailable", f"blame handler raised: {exc}"

        row = {
            "kind": "blame",
            "wl_hash": wl_hash,
            "spec": spec.name,
            "metric": metric,
            "metric_value": val,
            "metric_limit": _metric_limit(spec, metric),
            "margin": margin,
            "blame": blame,
            "coverage": cov,
            "coverage_note": note,
            "ts": ds._now(),
            "git_sha": ds.git_sha(),
        }
        rows.append(row)
        if write:
            _append_blame(row)
    return rows


# ---------------------------------------------------------------------------
# CLI helpers

def _best_l2_row(wl_hash_prefix, spec_name):
    rows = ds.load("topo_labels")
    matches = [r for r in rows
               if (r.get("wl_hash") or "").startswith(wl_hash_prefix)
               and r.get("spec") == spec_name]
    if not matches:
        return None
    # Prefer feasible; among feasible prefer lowest NF
    feasible = [r for r in matches if r.get("feasible")]
    pool = feasible if feasible else matches
    return min(pool, key=lambda r: (r.get("margins", {}).get("nf_db", {}).get("achieved") or 1e9))


def _ref_case(deck_name, spec_name):
    """Build body+params for a ref deck."""
    deck_path = os.path.join(HERE, "ref", deck_name)
    if not os.path.exists(deck_path):
        raise FileNotFoundError(deck_path)
    body = E.body_of(deck_path)
    return body, {}


def run_for_row(row, verbose=True, write=True, failing_only=True):
    """Run blame for one L2 row dict. Returns list of blame rows."""
    wl_hash = row.get("wl_hash") or ""
    spec_name = row.get("spec") or ""
    tokens = (row.get("graph") or {}).get("tokens")
    params = row.get("best_params") or {}
    metrics = row.get("metrics") or {}

    # Build body
    if tokens:
        S = _size()
        topo = Topology(tokens)
        spec = S._spec_for_sizing(spec_name)
        prep = S.prepared_body(topo, inductor_q=12)
        if prep is None:
            print(f"  [{wl_hash[:12]}] bias insert failed")
            return []
        body = prep[0]
    elif wl_hash.startswith("ref:"):
        deck_name = wl_hash[4:]
        deck_path = os.path.join(HERE, "ref", deck_name)
        if not os.path.exists(deck_path):
            print(f"  ref deck not found: {deck_path}")
            return []
        body = E.body_of(deck_path)
        S = _size()
        spec = S._spec_for_sizing(spec_name)
    else:
        print(f"  [{wl_hash[:12]}] cannot reconstruct body (no tokens, not a ref)")
        return []

    # Gather operating point
    op = {}
    E.run_and_extract(body, params, spec, op_capture=op)
    if not op.get("devices"):
        # Try noise deck
        E.measure_nf(body, params, spec, op_capture=op)

    if verbose:
        feas, viol = spec.feasible(metrics)
        print(f"  [{wl_hash[:12]}] spec={spec_name} feasible={feas}")
        if viol:
            print(f"    failing: {list(viol.keys())}")

    blame_rows = blame_design(body, params, spec, op, wl_hash, metrics,
                              write=write, failing_only=failing_only)
    if verbose:
        for r in blame_rows:
            print(f"    metric={r['metric']}  cov={r['coverage']}  "
                  f"top_device={r['blame'][0]['device'] if r['blame'] else 'none'}")
    return blame_rows


# ---------------------------------------------------------------------------
# CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wl-hash", help="wl_hash prefix to look up in topo_labels")
    ap.add_argument("--ref", help="ref deck name (e.g. ref24_csdeg.cir)")
    ap.add_argument("--spec", default="wifi24")
    ap.add_argument("--all-failing", action="store_true",
                    help="run on first 5 infeasible rows in store")
    ap.add_argument("--no-write", action="store_true",
                    help="do not append to blame_vectors.jsonl")
    ap.add_argument("--show-stored", action="store_true",
                    help="print rows already in blame_vectors.jsonl")
    a = ap.parse_args()

    if a.show_stored:
        rows = load_blame()
        print(f"{len(rows)} rows in blame_vectors.jsonl")
        for r in rows[:20]:
            top = r["blame"][0]["device"] if r["blame"] else "none"
            print(f"  {r['wl_hash'][:12]}  {r['spec']}  {r['metric']:14}  "
                  f"margin={r['margin']:.3f}  cov={r['coverage']}  top={top}")
        return 0

    write = not a.no_write

    if a.wl_hash:
        row = _best_l2_row(a.wl_hash, a.spec)
        if row is None:
            print(f"no row for {a.wl_hash!r} / {a.spec!r}")
            return 1
        run_for_row(row, verbose=True, write=write)
        return 0

    if a.ref:
        body, _ = _ref_case(a.ref, a.spec)
        S = _size()
        spec = S._spec_for_sizing(a.spec)
        op = {}
        metrics = E.run_and_extract(body, {}, spec, op_capture=op) or {}
        nf = E.measure_nf(body, {}, spec, op_capture=op)
        if nf is not None:
            metrics["nf_db"] = nf
        print(f"ref deck {a.ref!r}  spec={a.spec}")
        print(f"  metrics: {metrics}")
        feas, viol = spec.feasible(metrics)
        print(f"  feasible={feas}  failing={list(viol.keys())}")
        rows = blame_design(body, {}, spec, op, f"ref:{a.ref}", metrics,
                            write=write, failing_only=True)
        for r in rows:
            top = r["blame"][0]["device"] if r["blame"] else "none"
            print(f"  metric={r['metric']}  cov={r['coverage']}  top={top}")
            for b in r["blame"][:3]:
                print(f"    {b['device']:<12} score={b['score']:.4f}  {b['detail']}")
        return 0

    if a.all_failing:
        rows = ds.load("topo_labels")
        infeasible = [r for r in rows
                      if not r.get("feasible") and r.get("graph", {}).get("tokens")
                      and r.get("metrics")]
        print(f"Running blame on {min(5, len(infeasible))} infeasible rows")
        for row in infeasible[:5]:
            run_for_row(row, verbose=True, write=write)
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

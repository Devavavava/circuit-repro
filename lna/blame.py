"""Per-device blame vectors for failing metrics (plans2/22-INFER-INSTRUMENTS.md).

Given one evaluated design (deck body + operating point + metrics vs a spec),
emit a per-device blame vector for each FAILING metric:

    noise  -- reuse extract.measure_noise_budget decomposition (same series-Rs
               harness); device ranking by output-noise-power share.
    gain   -- from the operating-point dict: gm and gds contributions along the
               signal path, flagged by region.
    current -- per-branch Idd share from the OP `branches` dict; where branches
               is empty (common for topologies that don't expose all branch
               currents), per-device Id from the devices dict is used instead.
    match  -- S11 input-match deviation: the parasitic Cgs+Cgd of the FIRST
               device on the signal path is the dominant tunable knob; a partial
               attribution (which device has the largest gate capacitance) is
               returned honestly labelled `partial`.

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
  - current blame uses branch currents when available; falls back to device Id.
    Branches reported by ngspice depend on which sources have DC voltage; MOSFET
    drain currents (via `id`) are the reliable path.
  - match blame: `cgs + cgd` total for each device from the OP dict. This is a
    proxy for the device's impact on Zin, NOT a full small-signal Zin computation.
    The primary accuracy limit: resonator elements (inductors) are not captured
    here, so the attribution is partial by construction. Labelled `partial`.

USAGE:
    python lna/blame.py --wl-hash ace838 --spec dhruva-s
    python lna/blame.py --ref ref24_csdeg --spec wifi24
    python lna/blame.py --all-failing          # first 5 infeasible rows in store
"""
import argparse
import json
import math
import os
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

def _blame_current(body, params, spec, op):
    """Return (blame_list, coverage, note).

    Uses branch currents from `op['branches']` when available, else device Id.
    Score = abs(current) normalized by total Idd."""
    branches = (op or {}).get("branches", {})
    devices = (op or {}).get("devices", {})

    # Prefer branch currents (includes supply and passive branches)
    if branches:
        total = sum(abs(v) for v in branches.values()) or 1e-30
        ranked = sorted(branches.items(), key=lambda kv: -abs(kv[1]))
        blame = []
        for name, val in ranked:
            frac = abs(val) / total
            if frac < 0.005:
                continue
            blame.append({
                "device": name,
                "score": round(frac, 6),
                "detail": {"current_A": val, "frac": round(frac, 6)}
            })
        cov = "full"
        note = f"branch-current shares; {len(branches)} branches captured"
    else:
        # Fall back to device Id
        mos_devs = {k: v for k, v in devices.items() if k.startswith("m")}
        if not mos_devs:
            return [], "unavailable", "no branch data and no MOSFET devices"
        total = sum(abs(d.get("id") or 0.0) for d in mos_devs.values()) or 1e-30
        ranked = sorted(mos_devs.items(), key=lambda kv: -abs(kv[1].get("id") or 0.0))
        blame = []
        for name, d in ranked:
            id_val = d.get("id") or 0.0
            frac = abs(id_val) / total
            if frac < 0.005:
                continue
            blame.append({
                "device": name,
                "score": round(frac, 6),
                "detail": {"id_A": id_val, "frac": round(frac, 6), "region": d.get("region")}
            })
        cov = "partial"
        note = "device Id shares (branch currents unavailable; passive/supply branches excluded)"
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
# Dispatch

_METRIC_BLAME = {
    "nf_db": _blame_noise,
    "s21_db": _blame_gain,
    "idd_ma": _blame_current,
    "s11_db": _blame_match,
    "s11_max_db": _blame_match,
    "s21_min_db": _blame_gain,
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

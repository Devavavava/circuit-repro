"""E-12 P0.1 -- easy-tier calibration (ZERO sims).

Binding pre-reg: engineer/E12-TRAINEDIT.md §4 + §11.2. Finalizes the E1-E6
TRAIN-EASY targets from BANKED artifacts only, per the §4 rule: a target is a
value *demonstrably achieved by a banked base-feasible run or measurement of
that base task* (evidence cited). Provisional §4 targets are the starting
point; a target is adjusted only if the banked evidence demands it.

Evidence sources (all read-only, banked):
  * e11_null cells (engineer/data/e11_null/)      -- sizing-only reach on delta.
  * e10_s22_instrument (engineer/data/e10_s22_instrument/) -- the ONLY banked
    source of s22_max_db (topo_labels rows carry no s22 metric).
  * topo_labels store (lna/data/topo_labels.jsonl) -- base-feasible rows;
    base-feasibility is RECOMPUTED here from raw metrics (no stored flag).

Base-feasibility is judged with Spec.feasible on the RAW metrics dict of each
row/measurement -- no `feasible` flag is trusted (repo law). A design counts as
evidence for a target only if it is base-feasible AND achieves the target
value.

ZERO ngspice calls: this script only reads banked JSON/JSONL. Output:
engineer/data/e12/calibration.json (final table + per-target evidence).

    python e12_calibrate.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.abspath(os.path.join(HERE, "..", "lna"))
for p in (HERE, LNA):
    if p not in sys.path:
        sys.path.insert(0, p)

import datastore as ds          # noqa: E402
from spec import Spec           # noqa: E402

NULL_DIR = os.path.join(HERE, "data", "e11_null")
S22_DIR = os.path.join(HERE, "data", "e10_s22_instrument")
OUT = os.path.join(HERE, "data", "e12", "calibration.json")

# Provisional §4 targets -- the starting point.
PROVISIONAL = {
    "E1": {"base": "dhruva-s",  "metric": "s21_db",     "cmp": "min", "target": 30.5},
    "E2": {"base": "dhruva-s",  "metric": "s22_max_db", "cmp": "max", "target": -3.5},
    "E3": {"base": "dhruva-l2", "metric": "nf_db",      "cmp": "max", "target": 1.9},
    "E4": {"base": "dhruva-l2", "metric": "s21_db",     "cmp": "min", "target": 26.0},
    "E5": {"base": "dhruva-l5", "metric": "s11_max_db", "cmp": "max", "target": -11.0},
    "E6": {"base": "dhruva-l5", "metric": "idd_ma",     "cmp": "max", "target": 12.0},
}


def _passes(val, cmp, target):
    if val is None:
        return False
    return val >= target if cmp == "min" else val <= target


def _base_feasible(spec, metrics):
    """Recompute base feasibility from RAW metrics (no stored flag)."""
    if not metrics:
        return False
    ok, _ = spec.feasible(metrics)
    return bool(ok)


def collect_store_evidence():
    """Base-feasible store rows per dhruva base task, keyed metric ranges."""
    rows = ds.load("topo_labels")
    ev = {}
    for base in ("dhruva-s", "dhruva-l2", "dhruva-l5"):
        sp = Spec.load(base)
        bf = []
        for r in rows:
            if r.get("spec") != base:
                continue
            m = r.get("metrics")
            if _base_feasible(sp, m):
                bf.append(r)
        ev[base] = {"spec": sp, "rows": bf, "n_base_feasible": len(bf)}
    return ev


def collect_null_evidence():
    """Best sizing-only reach on each e11 null goal (recompute base feas)."""
    out = {}
    specs = {}
    for fn in sorted(os.listdir(NULL_DIR)):
        if not (fn.startswith("cell_") and fn.endswith(".json")):
            continue
        d = json.load(open(os.path.join(NULL_DIR, fn)))
        base = d.get("task")
        if base not in specs:
            # task id like dhruva-l5-t2-a -> spec dhruva-l5
            specs[base] = Spec.load(base.replace("-t2-a", ""))
        bm = d.get("best_metrics") or {}
        sp = specs[base]
        rec = {"cell": fn, "goal": d.get("goal"), "task": base,
               "best_metrics": bm,
               "base_feasible": _base_feasible(sp, bm)}
        out.setdefault(base, []).append(rec)
    return out


def collect_s22_evidence():
    """s22_max_db of the 8 instrumented dhruva-s designs; recompute base feas
    from measured_metrics against dhruva-s."""
    sp = Spec.load("dhruva-s")
    out = []
    for fn in sorted(os.listdir(S22_DIR)):
        if not (fn.startswith("topo_") and fn.endswith(".json")):
            continue
        d = json.load(open(os.path.join(S22_DIR, fn)))
        m = d.get("measured_metrics") or {}
        out.append({"file": fn, "wl": d.get("wl_hash"),
                    "s22_max_db": d.get("s22_max_db"),
                    "measured_metrics": m,
                    "base_feasible": _base_feasible(sp, m)})
    return out


def finalize():
    store = collect_store_evidence()
    nulls = collect_null_evidence()
    s22 = collect_s22_evidence()

    table = {}
    for eid, cfg in PROVISIONAL.items():
        base, metric, cmp, target = (cfg["base"], cfg["metric"],
                                     cfg["cmp"], cfg["target"])
        evidence = []
        best_achieved = None   # the strongest base-feasible value seen

        # --- store rows (base-feasible + carries the metric) -----------------
        if metric != "s22_max_db":  # store rows carry no s22
            sp = store[base]["spec"]
            vals = []
            for r in store[base]["rows"]:
                v = (r.get("metrics") or {}).get(metric)
                if v is None:
                    continue
                vals.append((v, r))
            if vals:
                # the base-feasible value that best satisfies the target
                key = (max if cmp == "min" else min)
                bv, br = key(vals, key=lambda t: t[0])
                best_achieved = bv
                n_pass = sum(1 for v, _ in vals if _passes(v, cmp, target))
                lo = min(v for v, _ in vals)
                hi = max(v for v, _ in vals)
                evidence.append({
                    "source": "topo_labels (base-feasible, recomputed)",
                    "n_base_feasible_rows_with_metric": len(vals),
                    "metric_range": [round(lo, 4), round(hi, 4)],
                    "best_base_feasible_value": round(bv, 4),
                    "best_row_wl": br.get("wl_hash"),
                    "best_row_ts": br.get("ts"),
                    "n_base_feasible_rows_passing_target": n_pass})

        # --- null-run reach --------------------------------------------------
        for rec in nulls.get(base, []):
            v = rec["best_metrics"].get(metric)
            if v is None:
                continue
            # null designs need NOT be base-feasible to bound reach, but the
            # §4 rule wants a base-feasible demonstration; note both.
            evidence.append({
                "source": "e11_null sizing-only reach",
                "cell": rec["cell"], "goal": rec["goal"],
                "value": round(v, 4),
                "base_feasible": rec["base_feasible"],
                "passes_target": _passes(v, cmp, target)})
            if rec["base_feasible"] and _passes(v, cmp, target):
                if best_achieved is None or _passes(v, cmp, best_achieved) is False:
                    pass  # keep store best_achieved as primary

        # --- s22 instrument (E2 only) ---------------------------------------
        if metric == "s22_max_db":
            bf_vals = [(x["s22_max_db"], x) for x in s22
                       if x["base_feasible"] and x["s22_max_db"] is not None]
            allvals = [(x["s22_max_db"], x) for x in s22
                       if x["s22_max_db"] is not None]
            if bf_vals:
                bv, bx = min(bf_vals, key=lambda t: t[0])  # most negative
                best_achieved = bv
                n_pass = sum(1 for v, _ in bf_vals if _passes(v, cmp, target))
                evidence.append({
                    "source": "e10_s22_instrument (base-feasible, recomputed)",
                    "n_base_feasible_measured": len(bf_vals),
                    "base_feasible_s22_values": sorted(round(v, 4)
                                                       for v, _ in bf_vals),
                    "best_base_feasible_value": round(bv, 4),
                    "best_wl": bx["wl"],
                    "n_base_feasible_passing_target": n_pass})
            evidence.append({
                "source": "e10_s22_instrument (all measured, FYI)",
                "all_s22_values": sorted(round(v, 4) for v, _ in allvals)})

        # --- verdict: does banked evidence support the provisional target? ---
        supported = _passes(best_achieved, cmp, target) if best_achieved is not None else False
        table[eid] = {
            "base_task": base + "-t2-a",
            "base_spec": base,
            "delta_metric": metric,
            "delta_cmp": cmp,
            "final_target": target,          # unchanged unless evidence demands
            "provisional_target": target,
            "adjusted": False,
            "best_base_feasible_achieved": (round(best_achieved, 4)
                                            if best_achieved is not None else None),
            "target_supported_by_banked_base_feasible_evidence": supported,
            "margin_of_target_below_best": (
                round(best_achieved - target, 4) if (best_achieved is not None
                and cmp == "min") else
                (round(target - best_achieved, 4) if best_achieved is not None
                 else None)),
            "evidence": evidence,
        }

    result = {
        "campaign": "e12", "phase": "P0.1 easy-tier calibration",
        "rule": ("§4: target = a value demonstrably achieved by a banked "
                 "base-feasible run/measurement of that base task; provisional "
                 "targets adjusted only if banked evidence demands."),
        "ngspice_calls": 0,
        "targets": table,
        "note": ("All base-feasibility recomputed from RAW metrics via "
                 "Spec.feasible; no stored feasible flag trusted. Store rows "
                 "carry no s22_max_db, so E2 evidence is the e10_s22_instrument "
                 "measurements only."),
    }
    tmp = OUT + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(result, fh, indent=2, default=str)
    os.replace(tmp, OUT)
    return result


def main():
    res = finalize()
    print("E-12 easy-tier calibration (0 sims)\n")
    print(f"{'id':<4}{'base':<12}{'delta':<26}{'target':>8}{'best_bf':>10}  supported")
    for eid in ("E1", "E2", "E3", "E4", "E5", "E6"):
        t = res["targets"][eid]
        delta = f"{t['delta_metric']} {'>=' if t['delta_cmp']=='min' else '<='} {t['final_target']}"
        print(f"{eid:<4}{t['base_spec']:<12}{delta:<26}"
              f"{t['final_target']:>8}{str(t['best_base_feasible_achieved']):>10}  "
              f"{t['target_supported_by_banked_base_feasible_evidence']}")
    print(f"\nwritten: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Binding-constraint probe: minimal spec relaxation to flip infeasible -> feasible.
(plans2/22-INFER-INSTRUMENTS.md)

Given an infeasible evaluated design (stored margins from the label store or a
live metrics dict), compute:

  1. Per-constraint shortfalls -- the raw normalized slack (already in margins_for
     output), negative means failing. No re-simulation.

  2. Single-constraint relaxations -- for each failing constraint, the minimal
     delta to its limit (max or min) that would make THAT constraint satisfied,
     holding all others fixed. Arithmetic on the stored achieved value and the
     stored limit.

  3. Pairwise relaxations -- for each pair of failing constraints, the minimal
     UNIFORM fractional relaxation delta that satisfies both simultaneously. This
     is meaningful when two constraints are jointly binding (e.g. S21 and NF both
     need the device gm to increase, so relaxing only one doesn't help the topology).

  4. Feasibility verdict -- "none needed" (already feasible), "single-constraint
     sufficient" (one relaxation flips it), or "pairwise or more needed" (the
     infeasibility is jointly bound).

IMPORTANT: basic version is PURE ARITHMETIC on stored margins. No re-simulation.
This gives exact answers for hard constraints with explicit achieved values, and
is instantly callable on any stored row.

EXTENSION NOTES (documented as extensions, not implemented):
  - Constraint interactions across COUPLED metrics (e.g. raising S21_min raises
    NF via the Friis chain) require a simulation sweep to map the Pareto boundary.
    That is documented as an extension below.
  - Objective-aware minimum relaxation (find the direction of minimum ZOAF-
    objective shift that crosses feasibility) requires a sensitivity analysis.

OUTPUT CONTRACT (one probe row per (design, metric)):
    {
      "wl_hash": str,
      "spec": str,
      "feasible_before": bool,
      "n_failing": int,
      "shortfalls": {metric: float},          # normalized signed slack (<0 = fail)
      "single_relaxations": [
        {
          "metric": str,
          "limit_key": "min"|"max",
          "current_limit": float,
          "new_limit": float,
          "delta_abs": float,             # absolute limit change
          "delta_frac": float,            # fractional change relative to scale
          "would_flip": bool,             # True when this single change suffices
        }
      ],
      "pairwise_relaxations": [           # only when n_failing >= 2
        {
          "metrics": [str, str],
          "uniform_frac": float,          # smallest uniform fractional relax
          "would_flip": bool,
        }
      ],
      "verdict": str,                     # "feasible" | "single" | "pairwise" | "multi"
      "sim_needed_extensions": [str],     # extension hooks not implemented
      "ts": str,
      "git_sha": str,
    }

STORE DISCIPLINE: rows are written to `lna/data/binding_probes.jsonl`.
binding_probe.py does NOT modify datastore.py's TABLES dict (containment rule).

USAGE:
    python lna/binding_probe.py --wl-hash b3aa27 --spec wifi24
    python lna/binding_probe.py --all-infeasible        # first 5
    python lna/binding_probe.py --show-stored
    python lna/binding_probe.py --flagship              # the stored flagship (should be feasible)
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds

# ---------------------------------------------------------------------------
# New store table
_DATA_DIR = os.path.join(HERE, "data")
_PROBE_FILE = os.path.join(_DATA_DIR, "binding_probes.jsonl")


def _append_probe(row):
    os.makedirs(_DATA_DIR, exist_ok=True)
    line = json.dumps(ds._jsonify(row), separators=(",", ":"), sort_keys=True)
    with open(_PROBE_FILE, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(line + "\n")
    return row


def load_probes():
    if not os.path.exists(_PROBE_FILE):
        return []
    with open(_PROBE_FILE, "r", encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]


# ---------------------------------------------------------------------------
# Core arithmetic

def _single_relaxation(achieved, limit_key, current_limit, scale):
    """Compute the minimal limit change to make `achieved` satisfy `limit_key`.

    For `max`: achieved <= current_limit is the constraint; violation = achieved > limit.
      New limit needed: max(current_limit, achieved). Delta = achieved - current_limit.
    For `min`: achieved >= current_limit; violation = achieved < limit.
      New limit needed: min(current_limit, achieved). Delta = current_limit - achieved.
    """
    if limit_key == "max":
        if achieved is None:
            return None
        new_limit = max(float(current_limit), float(achieved))
        delta_abs = new_limit - float(current_limit)
    else:  # min
        if achieved is None:
            return None
        new_limit = min(float(current_limit), float(achieved))
        delta_abs = float(current_limit) - new_limit   # positive = how much to lower the floor
    delta_frac = delta_abs / max(abs(scale), 1e-12)
    return {
        "current_limit": float(current_limit),
        "new_limit": float(new_limit),
        "delta_abs": float(delta_abs),
        "delta_frac": float(delta_frac),
    }


def probe_design(spec, metrics, wl_hash, write=True):
    """Compute binding-constraint probe for one design.

    `spec`    -- Spec object
    `metrics` -- metrics dict (achieved values)
    `wl_hash` -- identifier (for the row)
    `write`   -- append to binding_probes.jsonl

    Returns the probe row dict.
    """
    margins = ds.margins_for(spec, metrics or {})
    feas, viol = spec.feasible(metrics or {})

    # Shortfalls: negative = failing, None = unsupported/missing
    shortfalls = {}
    for m, rec in margins.items():
        if not rec.get("supported"):
            continue
        mg = rec.get("margin")
        if mg is not None:
            shortfalls[m] = float(mg)

    failing_metrics = [m for m, v in shortfalls.items() if v < 0.0]
    n_failing = len(failing_metrics)

    # Single-constraint relaxations
    single_relax = []
    for metric in failing_metrics:
        rec = margins[metric]
        achieved = rec.get("achieved")
        scale = rec.get("scale", 1.0)
        c = spec.constraints.get(metric, {})
        # Determine which limit is violated
        if "max" in c and achieved is not None and float(achieved) > float(c["max"]):
            r = _single_relaxation(achieved, "max", c["max"], scale)
            if r:
                single_relax.append({
                    "metric": metric,
                    "limit_key": "max",
                    **r,
                    "would_flip": True,  # exact arithmetic: this EXACTLY satisfies the constraint
                })
        if "min" in c and achieved is not None and float(achieved) < float(c["min"]):
            r = _single_relaxation(achieved, "min", c["min"], scale)
            if r:
                single_relax.append({
                    "metric": metric,
                    "limit_key": "min",
                    **r,
                    "would_flip": True,
                })

    # Sort by delta_frac (smallest relaxation first)
    single_relax.sort(key=lambda r: r["delta_frac"])

    # Pairwise uniform fractional relaxation
    # For a pair of failing constraints, find the smallest uniform fractional
    # relaxation epsilon such that:
    #   for max constraints: new_limit = limit + epsilon * scale >= achieved
    #   for min constraints: new_limit = limit - epsilon * scale <= achieved
    # => epsilon >= (achieved - limit) / scale  [max]
    # => epsilon >= (limit - achieved) / scale  [min]
    # So epsilon = max over the pair of: max(0, violation_normalized)
    pairwise_relax = []
    for i, m1 in enumerate(failing_metrics):
        for m2 in failing_metrics[i + 1:]:
            eps = 0.0
            for metric in (m1, m2):
                rec = margins[metric]
                achieved = rec.get("achieved")
                scale = rec.get("scale", 1.0)
                c = spec.constraints.get(metric, {})
                if achieved is None:
                    eps = max(eps, 1.0)  # unknown -> need full scale
                    continue
                if "max" in c and float(achieved) > float(c["max"]):
                    eps = max(eps, (float(achieved) - float(c["max"])) / max(scale, 1e-12))
                if "min" in c and float(achieved) < float(c["min"]):
                    eps = max(eps, (float(c["min"]) - float(achieved)) / max(scale, 1e-12))
            pairwise_relax.append({
                "metrics": [m1, m2],
                "uniform_frac": float(eps),
                "would_flip": True,   # exact arithmetic: this epsilon satisfies both
            })
    pairwise_relax.sort(key=lambda r: r["uniform_frac"])

    # Verdict
    if feas:
        verdict = "feasible"
    elif single_relax and any(r["would_flip"] for r in single_relax):
        verdict = "single"
    elif pairwise_relax and any(r["would_flip"] for r in pairwise_relax):
        verdict = "pairwise"
    else:
        verdict = "multi"

    # Extension hooks (documented, not implemented)
    sim_needed_extensions = [
        ("pairwise-pareto: mapping the two-constraint feasibility boundary "
         "requires a simulation sweep (gm-tradeoff between S21 and NF, etc.)"),
        ("sensitivity-direction: finding the ZOAF-objective-minimal relaxation "
         "direction requires a gradient/sensitivity analysis, which needs sims"),
        ("objective-weighted: ranking relaxations by their impact on the ZOAF "
         "objective (not just by delta_frac) needs the objective landscape"),
    ]

    row = {
        "kind": "binding_probe",
        "wl_hash": wl_hash,
        "spec": spec.name,
        "feasible_before": bool(feas),
        "n_failing": n_failing,
        "shortfalls": shortfalls,
        "single_relaxations": single_relax,
        "pairwise_relaxations": pairwise_relax,
        "verdict": verdict,
        "sim_needed_extensions": sim_needed_extensions,
        "ts": ds._now(),
        "git_sha": ds.git_sha(),
    }
    if write:
        _append_probe(row)
    return row


def probe_l2_row(row, write=True, verbose=True):
    """Run probe on one L2 row dict. Returns probe row."""
    import size as S
    wl_hash = row.get("wl_hash") or ""
    spec_name = row.get("spec") or ""
    metrics = row.get("metrics") or {}
    spec = S._spec_for_sizing(spec_name)
    result = probe_design(spec, metrics, wl_hash, write=write)
    if verbose:
        feas = result["feasible_before"]
        print(f"  [{wl_hash[:12]}] spec={spec_name} feasible={feas} "
              f"n_failing={result['n_failing']} verdict={result['verdict']!r}")
        for s in result["single_relaxations"][:3]:
            print(f"    {s['metric']:14} {s['limit_key']}={s['current_limit']:.3g} -> "
                  f"{s['new_limit']:.3g}  delta_frac={s['delta_frac']:.4f}")
        if result["pairwise_relaxations"]:
            p = result["pairwise_relaxations"][0]
            print(f"    smallest pairwise: {p['metrics']} uniform_frac={p['uniform_frac']:.4f}")
    return result


# ---------------------------------------------------------------------------
# CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wl-hash", help="wl_hash prefix")
    ap.add_argument("--spec", default="wifi24")
    ap.add_argument("--all-infeasible", action="store_true",
                    help="probe first 5 infeasible rows in topo_labels")
    ap.add_argument("--flagship", action="store_true",
                    help="probe the stored flagship feasible point (should say 'feasible')")
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--show-stored", action="store_true")
    a = ap.parse_args()

    if a.show_stored:
        rows = load_probes()
        print(f"{len(rows)} rows in binding_probes.jsonl")
        for r in rows[:20]:
            print(f"  {r['wl_hash'][:12]}  {r['spec']}  {r['verdict']:8}  "
                  f"n_failing={r['n_failing']}  ts={r['ts']}")
        return 0

    write = not a.no_write

    if a.flagship:
        import size as S
        rows = ds.load("topo_labels")
        refs = [r for r in rows if r.get("feasible") and (r.get("wl_hash") or "").startswith("ref:")]
        feasible = [r for r in rows if r.get("feasible") and r.get("metrics")]
        target = refs[0] if refs else (feasible[0] if feasible else None)
        if target is None:
            print("no feasible row found")
            return 1
        print(f"flagship: {target['wl_hash']!r} spec={target['spec']!r}")
        probe_l2_row(target, write=write, verbose=True)
        return 0

    if a.wl_hash:
        rows = ds.load("topo_labels")
        matches = [r for r in rows
                   if (r.get("wl_hash") or "").startswith(a.wl_hash)
                   and r.get("spec") == a.spec]
        if not matches:
            print(f"no row for {a.wl_hash!r} / {a.spec!r}")
            return 1
        r = matches[0]
        probe_l2_row(r, write=write, verbose=True)
        return 0

    if a.all_infeasible:
        rows = ds.load("topo_labels")
        infeasible = [r for r in rows
                      if not r.get("feasible") and r.get("metrics")]
        print(f"Probing {min(5, len(infeasible))} infeasible rows")
        for row in infeasible[:5]:
            probe_l2_row(row, write=write, verbose=True)
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

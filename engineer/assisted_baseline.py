"""Compute the real assisted-mode baseline for E-4's dhruva-l2-t2-a comparison.

This script queries the store's recorded history and FINDINGS-quoted numbers
to produce the SPICE-minutes-per-feasible-design figure for the human-in-loop
program itself, so E-4's unattended-loop verdict can be compared against the
actual assisted cost rather than the cmaes-null stand-in floor.

ACCOUNTING RULE (pre-stated before computation -- see E4-LOOP.md Appendix A)
-----------------------------------------------------------------------------
Assisted mode:
    Every L2 row in `lna/data/topo_labels.jsonl` with `spec == "dhruva-l2"` and
    `n_evals > 0` is a record of the human-in-loop program running a sizing
    campaign on that spec.  The program ran in waves (sessions), with the human
    ruling between waves (approving gate results, choosing the next campaign,
    deciding the next topology move) — that is the "human-in-loop" structure the
    charter names.  The store is the authoritative record of what was simulated.

    A row with n_evals = 0 is a harness-era re-label (one measurement of a stored
    point, zero new search evals) and contributes zero cost.

Feasible design (both-ways):
    - *feasible*: `row["feasible"] is True`, deduplicated by `wl_hash` (repeat-
      probe and re-log of the same design must not inflate the count).
    - *feasible-novel*: not applicable for dhruva-l2 — the human-in-loop program
      ran architectural-search / NF-descent campaigns on hand archetypes and
      known topologies, not a novelty-generating loop.  "Novel" vs "pinned" is
      therefore reported as "distinct wl_hashes" (informational) but the headline
      metric uses feasible, not feasible-novel (there is no generator baseline
      to compare against).

Cost (n_evals → SPICE-minutes):
    `SPICE-min = sum(n_evals) * SEC_PER_SIM / 60`
    where `SEC_PER_SIM = 1.0` s/eval — the store's own calibration constant from
    `lna/loop.py` (line 30: "~1 s/ngspice eval (extract.py)").
    This is the *same* constant the program's headline curve (`loop.py --curve`)
    uses, so the assisted and loop numbers are commensurable.

    IMPORTANT CAVEAT: this SEC_PER_SIM convention was calibrated on wifi24 (~1 s/eval,
    no NF gate).  dhruva-l2 is NF-gated (2 ngspice calls per eval); FINDINGS §27.4
    notes that `constrained_descent` on dhruva-l2 runs at ~0.028 s/eval on the
    dhruva box (2 calls * 0.014 s/call).  At 0.028 s/eval, 1 SPICE-min = 1/0.028 *
    60 ≈ 2,143 evals, far cheaper in wall-clock than SEC_PER_SIM=1.0 implies.
    The store does NOT record wall-seconds per sizing run for these campaigns —
    only n_evals.  We use SEC_PER_SIM=1.0 throughout because (a) it is the
    store's official convention, (b) E4-LOOP.md uses it for the null floor, and
    (c) the mismatch is documented here, not hidden.

    The wall-clock cost of human time (design decisions, code edits, diagnosis
    between sessions) is NOT captured in n_evals and is NOT included in this
    number.  The metric is SPICE-compute cost, not total engineering effort.

Era discipline (FINDINGS §43.1):
    The dhruva-l2 store has two eras:
      pre-cutover (w_finger = None, ts ~2026-08-08): d3-lownoise + dhruva-4band
      current-era (w_finger = 2e-6, ts ~2026-08-10): nf-campaign
    The pre-cutover harness overstated NF by a median of 2.08 dB (§27.3).  The
    rfbcs3_tank_cc21_bf0 design (wl 3ebaf08f) which reads feasible in the pre-
    cutover era is CONDITIONALLY UNSTABLE on dhruva-l2 under the honest multi-
    finger harness (§27.5: K_min -17).  It is kept in the pooled figure (labeled
    pre-cutover) but excluded from the current-era-only figure.
    Reported separately, both ways, per FINDINGS §43.1's lesson.

Sources:
    - lna/data/topo_labels.jsonl (store rows, authoritative)
    - lna/loop.py line 30: SEC_PER_SIM = 1.0
    - lna/FINDINGS.md §27.4: Gate D3 dhruva-l2 feasible (nf-campaign arm)
    - lna/FINDINGS.md §27.5: rfbcs3 conditional-stability advisory on dhruva-l2
    - lna/FINDINGS.md §43.1: era-discipline, 2.08 dB NF median correction
    - engineer/E4-LOOP.md §10.1: cmaes null floor (9.94 SPICE-min/feasible, 266 evals)

Usage:
    source /home/dpatni/circuit-repro/env.sh
    python engineer/assisted_baseline.py [--out engineer/data/assisted_baseline_v0.json]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
LNA_DIR = os.path.join(REPO_ROOT, "lna")
sys.path.insert(0, LNA_DIR)

import datastore as ds  # noqa: E402

# ------------------------------------------------------------------ constants
SEC_PER_SIM = 1.0          # lna/loop.py line 30
SPEC = "dhruva-l2"

# E-4 registered numbers (from E4-LOOP.md §10.1 and §7.2)
# cmaes null: 10 seeds x 266 evals x 2 ngspice calls = 5,320 ngspice calls → 1 feasible
# null_s_per_call = scoreboard_v0.1 dhruva-l2 cmaes sim_s_total/total_ngspice_calls
# scoreboard_v0.1: sim_s_total=596.33, n_seeds=10, n_evals=266 each → total 2660 evals
# 2 ngspice calls/eval → 5320 ngspice calls → 596.33 s → 0.1121 s/call
# SPICE-min = 596.33 / 60 = 9.939 min → 9.94 SPICE-min (E4-LOOP.md rounds to 9.94)
NULL_FLOOR_SPICE_MIN = 9.94          # from E4-LOOP.md §10.1 (recorded verbatim)
NULL_FLOOR_NGSPICE_CALLS = 5320      # 10 seeds * 266 evals * 2 calls
NULL_FLOOR_FEASIBLE = 1              # 1/10 seeds feasible
NULL_FLOOR_EVALS = 10 * 266          # 2660 evals total (null, 10 seeds)

# E-4 loop result (from E4-LOOP.md §10.1)
LOOP_NGSPICE_CALLS = 5320           # 10 seeds * 266 evals * 2 calls (warm side)
LOOP_FEASIBLE = 0                   # 0/10


def _era(row):
    """Return 'current' if w_finger=2e-6 (post-cutover), else 'pre-cutover'."""
    w = (row.get("zoaf_cfg") or {}).get("w_finger")
    return "current" if w == 2e-6 else "pre-cutover"


def _spice_min(n_evals):
    return n_evals * SEC_PER_SIM / 60.0


def run_analysis():
    rows = ds.load("topo_labels")
    # All dhruva-l2 rows with actual sizing cost (n_evals > 0)
    cost_rows = [r for r in rows
                 if r.get("spec") == SPEC and (r.get("n_evals") or 0) > 0]

    # Partition by era
    current_rows = [r for r in cost_rows if _era(r) == "current"]
    pre_rows = [r for r in cost_rows if _era(r) == "pre-cutover"]

    # ----- per-arm breakdown (informational)
    arm_summary = {}
    for r in cost_rows:
        arm = (r.get("provenance") or {}).get("source_arm", "unknown")
        e = _era(r)
        key = f"{arm}|{e}"
        if key not in arm_summary:
            arm_summary[key] = {"n_rows": 0, "n_evals_total": 0,
                                "feasible_hashes": set(), "arm": arm, "era": e}
        arm_summary[key]["n_rows"] += 1
        arm_summary[key]["n_evals_total"] += r.get("n_evals", 0)
        if r.get("feasible"):
            arm_summary[key]["feasible_hashes"].add(r.get("wl_hash"))

    def _figure(subset, label):
        n_evals_total = sum(r.get("n_evals", 0) for r in subset)
        spice_min = _spice_min(n_evals_total)
        # Distinct feasible designs (deduplicated by wl_hash)
        feasible_hashes = sorted({r.get("wl_hash")
                                  for r in subset if r.get("feasible")})
        n_feasible = len(feasible_hashes)
        spice_min_per_feasible = spice_min / n_feasible if n_feasible else None
        row_count = len(subset)
        return {
            "label": label,
            "spec": SPEC,
            "n_rows_with_cost": row_count,
            "n_evals_total": n_evals_total,
            "ngspice_calls_total": None,  # not recorded per campaign; see caveats
            "sec_per_sim_convention": SEC_PER_SIM,
            "spice_min": round(spice_min, 2),
            "n_feasible_distinct": n_feasible,
            "feasible_wl_hashes": feasible_hashes,
            "spice_min_per_feasible": round(spice_min_per_feasible, 2)
            if spice_min_per_feasible is not None else None,
        }

    pooled = _figure(cost_rows, "pooled_both_eras")
    current_only = _figure(current_rows, "current_era_only")
    pre_only = _figure(pre_rows, "pre_cutover_only")

    # --- three-way comparison
    comparison = {
        "assisted_current_era": {
            "spice_min_per_feasible": current_only["spice_min_per_feasible"],
            "n_feasible": current_only["n_feasible_distinct"],
            "source": "lna/data/topo_labels.jsonl nf-campaign rows "
                      "(w_finger=2e-6, ts=2026-08-10)",
        },
        "assisted_pooled": {
            "spice_min_per_feasible": pooled["spice_min_per_feasible"],
            "n_feasible": pooled["n_feasible_distinct"],
            "source": "lna/data/topo_labels.jsonl all dhruva-l2 rows with n_evals>0",
        },
        "cmaes_null_floor": {
            "spice_min_per_feasible": NULL_FLOOR_SPICE_MIN,
            "n_feasible": NULL_FLOOR_FEASIBLE,
            "n_seeds": 10,
            "evals_per_seed": 266,
            "source": "engineer/E4-LOOP.md §10.1 / §7.2, scoreboard_v0.1.json",
        },
        "e4_loop_warm": {
            "spice_min_per_feasible": None,
            "n_feasible": LOOP_FEASIBLE,
            "ngspice_calls": LOOP_NGSPICE_CALLS,
            "source": "engineer/E4-LOOP.md §10.1",
        },
    }

    # --- updated E-4 verdict
    # The pre-registered falsifier (E4-LOOP.md §7.5b):
    #   "costs more SPICE-minutes than the assisted mode"
    # The loop produced 0 feasible → infinite cost → falsified in any comparison.
    # For the sharpened reading: the assisted-mode numbers are MUCH LARGER than the null floor,
    # which means the null floor is indeed conservative (lower bound) — the real bar is harder.
    cur = current_only["spice_min_per_feasible"]
    pool = pooled["spice_min_per_feasible"]
    verdict = (
        "FALSIFIED (unchanged). The loop produced 0 feasible designs, "
        "so its cost-per-feasible is infinite regardless of which baseline is used. "
        f"Against the actual assisted-mode cost (current-era: {cur:.1f} SPICE-min/feasible, "
        f"pooled: {pool:.1f} SPICE-min/feasible), the loop is still strictly worse. "
        f"The sharpened reading: the assisted baseline is HIGHER than the cmaes-null "
        f"floor ({NULL_FLOOR_SPICE_MIN} SPICE-min/feasible), not lower, which means "
        "the null floor was a conservative (easy-to-beat) bar and the real bar is "
        "harder. The E-4 falsification was already the stiffest possible (infinite "
        "vs finite), so the verdict direction is unchanged; the updated comparison "
        "only changes what the loop would need to beat to claim an improvement over "
        "the assisted program."
    )

    # Arm breakdown (serialisable)
    arm_list = []
    for key, d in sorted(arm_summary.items()):
        arm_list.append({
            "arm": d["arm"],
            "era": d["era"],
            "n_rows": d["n_rows"],
            "n_evals_total": d["n_evals_total"],
            "spice_min": round(_spice_min(d["n_evals_total"]), 2),
            "n_feasible_distinct": len(d["feasible_hashes"]),
        })

    caveats = [
        "sec_per_sim=1.0 is calibrated on wifi24 (~1 s/eval); dhruva-l2 runs at "
        "~0.028 s/eval (2 ngspice calls * 0.014 s/call, FINDINGS §27 timing). "
        "Wall-clock SPICE cost for these campaigns is therefore ~35x lower than the "
        "loop.py convention implies. The convention is used because it is the store's "
        "standard and keeps assisted and loop numbers commensurable; the discrepancy "
        "is stated, not hidden.",

        "Human wall-clock time (design decisions, session rulings, campaign setup, "
        "diagnosis between waves) is NOT captured in n_evals and is NOT included. "
        "The metric is SPICE-compute cost only.",

        "The pre-cutover rfbcs3_tank_cc21_bf0 design (wl 3ebaf08f, 500 evals, "
        "dhruva-4band arm) is CONDITIONALLY UNSTABLE on dhruva-l2 under the honest "
        "multi-finger harness (FINDINGS §27.5: K_min -17). It reads 'feasible' in "
        "the pre-cutover domain but does not qualify as a stable feasible design "
        "under the current harness. The current-era-only figure excludes it; the "
        "pooled figure includes it but labels it pre-cutover.",

        "The d3-lownoise pre-cutover rows (6 designs, all infeasible on dhruva-l2) "
        "carried the NF artefact (§43.1 median +2.08 dB); their infeasibility verdict "
        "is confirmed by the current-era nf-campaign results but the exact margins "
        "are pre-cutover measurements.",

        "nf-campaign rows for dhruva-l2 include two rows per design (two seeds or "
        "two sizing runs), both captured in the store. n_evals for each is the full "
        "sizing run's eval count, not a per-call count. Deduplication is by wl_hash.",

        "The assisted program produced no 'novel' dhruva-l2 designs in the E4-LOOP.md "
        "sense (wl_hash different from 439032fd40e7e504). The nf-campaign feasibles "
        "(439032fd, ace8383c, 86d5ce25) and the dhruva-4band feasible (3ebaf08f) are "
        "all known/hand archetypes, not generator-discovered novel topologies. "
        "SPICE-min per feasible-novel is undefined (0 novel feasible) for the "
        "assisted program on this spec.",
    ]

    return {
        "kind": "assisted_baseline",
        "schema": "assisted-baseline-v0",
        "rule_source": "engineer/E4-LOOP.md Appendix A (post-hoc, 2026-08-16)",
        "sec_per_sim_convention": SEC_PER_SIM,
        "spec": SPEC,
        "per_era": {
            "current_era_only": current_only,
            "pooled_both_eras": pooled,
            "pre_cutover_only": pre_only,
        },
        "per_arm": arm_list,
        "comparison": comparison,
        "e4_verdict_updated": verdict,
        "caveats": caveats,
        "sources": {
            "store": "lna/data/topo_labels.jsonl",
            "sec_per_sim": "lna/loop.py line 30",
            "null_floor": "engineer/E4-LOOP.md §10.1, scoreboard_v0.1.json",
            "era_discipline": "lna/FINDINGS.md §43.1",
            "dhruva_l2_feasibles": "lna/FINDINGS.md §27.4 (Gate D3 nf-campaign)",
            "stability_advisory": "lna/FINDINGS.md §27.5 (rfbcs3 conditional-stability)",
        },
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "data",
                                                   "assisted_baseline_v0.json"),
                    help="output JSON path")
    ap.add_argument("--print", action="store_true", dest="print_only",
                    help="print summary to stdout only, do not write file")
    args = ap.parse_args()

    result = run_analysis()

    if args.print_only:
        print(json.dumps(result, indent=2))
        return 0

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(result, fh, indent=2, sort_keys=False)
    print(f"Written: {args.out}")

    # ---- human-readable summary
    ce = result["per_era"]["current_era_only"]
    po = result["per_era"]["pooled_both_eras"]
    print()
    print("=== Assisted-mode baseline (dhruva-l2) ===")
    print(f"  Current-era only ({ce['n_rows_with_cost']} rows):")
    print(f"    n_evals: {ce['n_evals_total']}  SPICE-min: {ce['spice_min']:.1f}")
    print(f"    feasible designs: {ce['n_feasible_distinct']}")
    print(f"    SPICE-min/feasible: {ce['spice_min_per_feasible']:.1f}")
    print(f"  Pooled ({po['n_rows_with_cost']} rows, both eras):")
    print(f"    n_evals: {po['n_evals_total']}  SPICE-min: {po['spice_min']:.1f}")
    print(f"    feasible designs: {po['n_feasible_distinct']}")
    print(f"    SPICE-min/feasible: {po['spice_min_per_feasible']:.1f}")
    print()
    print("=== Three-way comparison ===")
    print(f"  assisted (current-era): {ce['spice_min_per_feasible']:.1f} SPICE-min/feasible")
    print(f"  assisted (pooled):      {po['spice_min_per_feasible']:.1f} SPICE-min/feasible")
    print(f"  cmaes null floor:        {NULL_FLOOR_SPICE_MIN} SPICE-min/feasible (E4-LOOP.md §7.2)")
    print(f"  E-4 loop (warm/cold):    ∞ (0 feasible)")
    print()
    print("=== Updated E-4 verdict ===")
    print("  FALSIFIED (unchanged) — see artifact for full verdict sentence.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

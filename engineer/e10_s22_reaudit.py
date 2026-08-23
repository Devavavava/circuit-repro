"""E10 G2'' re-audit under the UNCHANGED pre-declared rule (E10-GAPAUDIT.md
AMENDMENT A.1). Extended spec = dhruva-s base + s22_max_db <= -10. The best single
point = complete measured row minimizing total normalized violation over the
extended spec. NEAR-MISS iff it fails <=2 objectives AND each failing objective's
raw gap is within its per-metric threshold (S22 threshold = 2.0 dB); else HOPELESS.

Uses the already-written per-topology measurement JSONs. No new sims.
"""
import sys, os, json, glob
HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "data", "e10_s22_instrument")

THRESH = {"s11_max_db": 2.0, "s22_max_db": 2.0, "s21_db": 2.0,
          "s21_ripple_db": 1.5, "nf_db": 0.5, "idd_ma": 1.5}


def total_violation(tbl):
    return sum(max(0.0, -r["margin"]) for r in tbl if r["margin"] is not None)


def main():
    docs = [json.load(open(f)) for f in sorted(glob.glob(OUTDIR + "/topo_*.json"))]
    # best single point = complete row minimizing total normalized violation
    # over the extended spec (E10 A.1 rule 4). All 8 rows are complete on the
    # extended spec (s22_max_db now measured on every one).
    docs.sort(key=lambda d: total_violation(d["extended_spec_table"]))
    best = docs[0]
    tbl = best["extended_spec_table"]
    fails = [r for r in tbl if not r["pass"]]
    n_fail = len(fails)

    within = all(r["raw_gap"] is not None and r["raw_gap"] <= THRESH[r["metric"]]
                 for r in fails)
    verdict = ("NEAR-MISS" if (n_fail <= 2 and within and n_fail > 0)
               else ("SOLVED-IN-STORE" if n_fail == 0 else "HOPELESS"))

    print(f"G2'' best single point (min total ext-spec violation): "
          f"rank {best['rank']} wl {best['wl_hash']}")
    print(f"  total normalized violation = "
          f"{total_violation(tbl):.4f}, failing objectives = {n_fail}")
    print(f"  {'metric':<14}{'target':<16}{'achieved':>12}{'margin':>10}"
          f"{'raw_gap':>10}{'thr':>7}  pass")
    for r in tbl:
        tgt = ("<=%.4g" % r["target"]["max"] if "max" in r["target"]
               else ">=%.4g" % r["target"]["min"])
        ach = "MISSING" if r["achieved"] is None else "%.4f" % r["achieved"]
        mg = "--" if r["margin"] is None else "%+.4f" % r["margin"]
        rg = "--" if r["raw_gap"] is None else "%.4f" % r["raw_gap"]
        print(f"  {r['metric']:<14}{tgt:<16}{ach:>12}{mg:>10}{rg:>10}"
              f"{THRESH[r['metric']]:>7}  {'ok' if r['pass'] else 'FAIL'}")
    print(f"\n  VERDICT: G2'' = {verdict}")
    print(f"  (rule: fails {n_fail} obj (<=2) AND each raw gap within threshold "
          f"= {within})")

    audit = {
        "goal": "G2'' = dhruva-s + s22_max_db <= -10 dB",
        "rule": "NEAR-MISS iff best single measured point fails <=2 objectives "
                "AND each failing objective raw gap within per-metric threshold "
                "(S22=2.0 dB); else HOPELESS. Best single point = complete "
                "measured row minimizing total normalized ext-spec violation.",
        "best_single_point": {"rank": best["rank"], "wl_hash": best["wl_hash"],
                              "row_ts": best["row_ts"],
                              "provenance": best["provenance"]},
        "total_normalized_violation": total_violation(tbl),
        "n_failing_objectives": n_fail,
        "failing_within_threshold": within,
        "per_objective_table": tbl,
        "thresholds": THRESH,
        "verdict": verdict,
        "prior_verdict_E10_amendment": "HOPELESS-BLIND (s22_max_db 0/1059 "
            "recorded; every candidate incomplete)",
        "change": "The blind bar is lifted: s22_max_db is now measured on the "
                  "store's best base-spec-passing topologies. Re-audited under "
                  "the unchanged pre-declared rule.",
        "all_topologies_measured": [
            {"rank": d["rank"], "wl_hash": d["wl_hash"],
             "s22_max_db": d["s22_max_db"],
             "n_failing_objectives": d["n_failing_objectives"],
             "total_violation": total_violation(d["extended_spec_table"])}
            for d in sorted(docs, key=lambda x: x["rank"])],
    }
    with open(os.path.join(OUTDIR, "_reaudit_verdict.json"), "w") as fh:
        json.dump(audit, fh, indent=2)
    print("\nwrote _reaudit_verdict.json")


if __name__ == "__main__":
    main()

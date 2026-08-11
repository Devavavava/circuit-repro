"""WP-OUTCOME step 5 -- the funnel table (plans2/11 section 5.2).

Aggregates the sized results per arm and ends in the program's own currency:
near-feasible and feasible-novel per SPICE-minute, accounted the way
`loop.spice_curve` does (n_evals x SEC_PER_SIM / 60), with wall-clock beside it.

    python lna/_out_report.py --pool lna/out/_o/pool.json \
        --rank lna/out/_o/rank.json --sized lna/out/_o/sized_a.json ... \
        --gen lna/out/_o/gen_stats.json
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import loop as LP                                                 # noqa: E402

ORDER = ["P5V7", "OUT-U", "OUT-C", "OUT-S"]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pool", required=True)
    ap.add_argument("--rank")
    ap.add_argument("--sized", nargs="+", required=True)
    ap.add_argument("--gen")
    ap.add_argument("--out", default=os.path.join(HERE, "out", "_o", "funnel.json"))
    a = ap.parse_args()

    pool = json.load(open(a.pool, encoding="utf-8"))
    res = {}
    for p in a.sized:
        for r in json.load(open(p, encoding="utf-8"))["results"]:
            res[(r["arm"], r["idx"])] = r
    gen = json.load(open(a.gen, encoding="utf-8")) if a.gen else {}

    rows = {}
    for arm in ORDER:
        rs = [r for (ar, _), r in res.items() if ar == arm]
        ok = [r for r in rs if r.get("ok")]
        viols = sorted(r["viol"] for r in ok)
        n_ev = sum(r.get("n_evals") or 0 for r in rs)
        smin = n_ev * LP.SEC_PER_SIM / 60.0
        near = sum(1 for r in ok if r["near"])
        feas = sum(1 for r in ok if r["feasible"])
        ps = pool["per_arm"].get(arm, {})
        g = gen.get("wifi24|%s" % arm, {})
        rows[arm] = {
            "n_samples": ps.get("n_files"), "l0": ps.get("l0_pass"),
            "ndl": g.get("ndl"), "copies_pct": g.get("copies_pct"),
            "med_nn": g.get("median_nn"), "ind_ratio": g.get("ind_ratio"),
            "novel": ps.get("novel"), "wl_distinct": ps.get("wl_distinct_novel"),
            "qualifying": ps.get("qualifying"),
            "port_src_rate": ps.get("port_src_rate_of_distinct"),
            "sized": len(rs), "ok": len(ok), "feasible": feas, "near": near,
            "best_viol": viols[0] if viols else None,
            "med_viol": viols[len(viols) // 2] if viols else None,
            "n_evals": n_ev, "spice_min": round(smin, 1),
            "wall_min": round(sum(r.get("secs") or 0 for r in rs) / 60.0, 1),
            "near_per_spice_min": round(near / smin, 4) if smin else None,
            "feas_per_spice_min": round(feas / smin, 4) if smin else None,
            "mean_dev_qualifying": None,
        }
        devs = [c["n_dev"] for c in pool["candidates"] if c["arm"] == arm]
        if devs:
            rows[arm]["mean_dev_qualifying"] = round(sum(devs) / len(devs), 2)

    hdr = ("arm", "n", "L0", "NDL", "novel", "WLdist", "qual", "sized", "ok",
           "feas", "near", "bestviol", "medviol", "SPICEmin", "near/min")
    print("%-7s %4s %4s %4s %6s %6s %5s %5s %4s %4s %4s %9s %8s %8s %8s" % hdr)
    for arm in ORDER:
        r = rows[arm]
        def f(x, w, d=3):
            return ("%*.*f" % (w, d, x)) if isinstance(x, float) else "%*s" % (w, x if x is not None else "-")
        print("%-7s %4s %4s %4s %6s %6s %5s %5s %4s %4s %4s %s %s %8s %s"
              % (arm, r["n_samples"], r["l0"], r["ndl"], r["novel"],
                 r["wl_distinct"], r["qualifying"], r["sized"], r["ok"],
                 r["feasible"], r["near"], f(r["best_viol"], 9),
                 f(r["med_viol"], 8), r["spice_min"],
                 f(r["near_per_spice_min"], 8, 4)))
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"pool": a.pool, "rank": a.rank, "sized": a.sized,
                   "rows": rows}, fh, indent=2, sort_keys=True)
    print("wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

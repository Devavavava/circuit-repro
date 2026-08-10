"""What is reachable if the devices are laid out like real RF devices?

Phase 1 measured that 26-40% of the EXCESS noise on the dhruva designs is BSIM4
gate-electrode resistance, because every MOSFET is emitted single-finger
(`rgatemod=1`, `rshg=0.4`, `ngcon=1`, and no `NF=` on the instance line). Simply
adding fingers to an already-sized design is not a fair answer: it also changes
the input match (measured: s11_max -10.00 -> -8.32 at 2 fingers), because the
gate resistance was part of what the matched design was matched to.

So this RE-SIZES at a fixed finger count -- same topology, same spec, same
`constrained_descent` under the same tier-1 trust region -- and reports what NF
is reachable when the match is restored.

⚠ THIS ADOPTS NOTHING. Finger count is a harness-fidelity parameter of exactly
the same class as `inductor_q` and `device_budget`; changing it would move every
NF label in the store, and it must not be changed in order to close a gate. This
is a measurement to hand to that decision, and `to_spice.py` (which would carry
the change) is owned by the ingestion track.

    python lna/_nf_fingers_resize.py --fingers 4 --spec dhruva-l5
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import size as S                  # noqa: E402
from topology import Topology     # noqa: E402
from _nf_fingers import best_row, with_fingers   # noqa: E402

TIER1 = ("s11_max_db", "s21_db", "idd_ma")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default="dhruva-l5")
    ap.add_argument("--hashes", default="439032,998ff3,6f0d08")
    ap.add_argument("--fingers", default="1,4,8")
    ap.add_argument("--seeds", default="0,1")
    ap.add_argument("--budget", type=int, default=1200)
    ap.add_argument("--out")
    a = ap.parse_args()

    spec = S._spec_for_sizing(a.spec)
    keep = {n: {k: c[k] for k in ("min", "max") if k in c}
            for n, c in spec.constraints.items() if n in TIER1}
    tgt = (spec.constraints.get("nf_db") or {}).get("max")
    print(f"re-size under a tier-1 trust region vs {a.spec} (NF target {tgt}) "
          f"at fixed gate-finger counts\n")
    print(f"{'design':<15}{'fing':>5}{'seed':>5}{'S11*':>8}{'S21':>8}{'Idd':>7}"
          f"{'NF':>7}{'K_min':>9}  tier-1")
    res = []
    for hp in a.hashes.split(","):
        r = best_row(hp, a.spec)
        if r is None:
            print(f"{hp:<15}  (no {a.spec} row)")
            continue
        topo = Topology(r["graph"]["tokens"])
        base = S.prepared_body(topo, inductor_q=12)
        if base is None:
            continue
        for n in [int(x) for x in a.fingers.split(",")]:
            prep = (base[0] if n == 1 else with_fingers(base[0], n), base[1], base[2])
            for seed in [int(x) for x in a.seeds.split(",")]:
                out = S.constrained_descent(
                    topo, spec, r["best_params"], target=("nf_db", "min"),
                    keep=keep, budget=a.budget, seed=seed,
                    jitter=(0.12 if seed else 0.0), prepared=prep)
                if out is None or out.get("metrics") is None:
                    print(f"{r['wl_hash'][:12]:<15}{n:>5}{seed:>5}   descent failed")
                    continue
                m = out["metrics"]
                _, viol = spec.feasible(m)
                t1 = all(k not in viol for k in TIER1)
                print(f"{r['wl_hash'][:12]:<15}{n:>5}{seed:>5}{m['s11_max_db']:>8.2f}"
                      f"{m['s21_db']:>8.2f}{m['idd_ma']:>7.2f}{m['nf_db']:>7.3f}"
                      f"{m['k_min']:>9.4g}  {t1}"
                      f"{'   ** NF TARGET MET **' if t1 and m['nf_db'] <= tgt else ''}",
                      flush=True)
                res.append({"wl_hash": r["wl_hash"], "fingers": n, "seed": seed,
                            "metrics": m, "tier1_ok": t1,
                            "best_params": out["best_params"], "spec": a.spec})
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1, default=str)
        print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()

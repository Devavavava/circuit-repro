"""Stage 2 goldens + regime max:M runs (seed 1, 2,500 evals each; resumable on exact tags).

  golden-<circuit>       margin mode at GOLDEN_SPECS[circuit]           (every library circuit + witness)
  max-<R>-<circuit>      max:M under regime R's hard constraints         (witness of R + all of F1)

The max-<R> rows for F1 are a PREVIEW of Stage 3's frontier step (one seed, not the D0
protocol). Usage: goldens.py [golden|max|all] [procs]
"""
import json
import os
import sys

import s2common as C


def jobs(which):
    out = []
    if which in ("golden", "all"):
        for n in C.CIRCUITS:
            out.append(dict(tag="golden-" + n, circuit=n, spec=C.GOLDEN_SPECS[n],
                            objective="margin", seed=1, evals=2500))
    if which in ("max", "all"):
        for w, reg in C.WITNESS_REGIME.items():
            R = C.REGIMES[reg]
            for n in [w] + list(C.LIB):
                out.append(dict(tag="max-%s-%s" % (reg, n), circuit=n, spec=R["spec"],
                                objective="max:" + R["M"], seed=1, evals=2500))
    return out


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    procs = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    recs = C.run_jobs(jobs(which), procs)
    table = {r["job"]["tag"]: dict(r["summary"], spec=r["job"]["spec"]["name"],
                                   objective=r["job"]["objective"]) for r in recs}
    p = os.path.join(C.RESULTS, "table_%s.json" % which)
    with open(p, "w") as fh:
        json.dump(table, fh, indent=1, sort_keys=True, default=str)
    print("wrote", p)


if __name__ == "__main__":
    main()

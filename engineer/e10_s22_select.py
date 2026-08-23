"""E10 G2'' instrument-first: select top-8 distinct dhruva-s topologies by worst
base-spec normalized margin, recomputed strictly from raw metrics (flags never
trusted, complete rows only). Read-only over lna/. Prints the selection; no sims.
"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from env import _bind_runtime_deps
_bind_runtime_deps()
import datastore as ds
from spec import Spec

SPEC = "dhruva-s"
# base-spec supported hard constraints (iip3 is status:unsupported -> excluded)
spec = Spec.load(SPEC)
BASE = {k: c for k, c in spec.constraints.items()
        if c.get("status") != "unsupported"}


def norm_margin(name, val):
    c = BASE[name]
    scale = abs(c.get("max") if "max" in c else c.get("min")) or 1.0
    slacks = []
    if "max" in c:
        slacks.append((c["max"] - val) / scale)
    if "min" in c:
        slacks.append((val - c["min"]) / scale)
    return min(slacks)


def base_eval(metrics):
    """Return (complete, worst_margin, per_metric) recomputed from raw metrics."""
    per = {}
    complete = True
    worst = float("inf")
    for name in BASE:
        val = (metrics or {}).get(name)
        if val is None:
            complete = False
            per[name] = None
            continue
        m = norm_margin(name, val)
        per[name] = m
        worst = min(worst, m)
    return complete, (worst if complete else None), per


def main():
    rows = [r for r in ds.load("topo_labels") if r.get("spec") == SPEC]
    print(f"dhruva-s rows: {len(rows)}")
    scored = []
    for r in rows:
        complete, worst, per = base_eval(r.get("metrics"))
        if not complete:
            continue
        # only rows that PASS the full base spec (worst margin >= 0)
        if worst < 0:
            continue
        scored.append((worst, r, per))
    print(f"complete + base-spec-passing rows: {len(scored)}")
    scored.sort(key=lambda t: t[0], reverse=True)
    # top 8 DISTINCT wl_hash, keeping each topology's best row
    seen = set()
    picks = []
    for worst, r, per in scored:
        wl = r.get("wl_hash")
        if wl in seen:
            continue
        seen.add(wl)
        picks.append((worst, r, per))
        if len(picks) == 8:
            break
    print(f"\nTop {len(picks)} distinct topologies by worst base-spec margin:")
    out = []
    for i, (worst, r, per) in enumerate(picks, 1):
        m = r.get("metrics")
        prov = r.get("provenance") or {}
        cfg = r.get("zoaf_cfg") or {}
        print(f"{i}. wl={r['wl_hash']} worst_margin={worst:+.4f} ts={r['ts']}")
        print(f"   recipe={cfg.get('recipe')} era_source_arm={prov.get('source_arm')} "
              f"archetype={prov.get('archetype')}")
        print("   per-metric margins: " +
              "  ".join(f"{k}={v:+.4f}" for k, v in per.items()))
        print("   raw: " + "  ".join(f"{k}={m.get(k)}" for k in BASE))
        out.append({"rank": i, "wl_hash": r["wl_hash"], "ts": r["ts"],
                    "worst_base_margin": worst, "per_metric_margin": per,
                    "recipe": cfg.get("recipe"),
                    "provenance": prov, "n_evals": r.get("n_evals")})
    os.makedirs(os.path.join(HERE, "data", "e10_s22_instrument"), exist_ok=True)
    with open(os.path.join(HERE, "data", "e10_s22_instrument",
                           "_selection.json"), "w") as fh:
        json.dump({"spec": SPEC, "base_constraints": BASE, "picks": out},
                  fh, indent=2)
    print("\nwrote _selection.json")


if __name__ == "__main__":
    main()

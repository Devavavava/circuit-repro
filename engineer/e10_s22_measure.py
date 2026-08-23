"""E10 G2'' instrument-first: measure s22_max_db on the 8 selected dhruva-s
topologies by reconstructing each recorded sizing (best_params) and evaluating it
under the dhruva-s spec/band. NO re-optimization, NO search. The best (rank-1,
verdict-relevant) topology is measured 3x to confirm a 0.0000 replay-fence spread.

Every ngspice invocation is counted (env.ngspice_calls: 2/eval because dhruva-s
gates NF). Writes one JSON per topology under data/e10_s22_instrument/.
Read-only over lna/.
"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from env import _bind_runtime_deps, Env, Task
_bind_runtime_deps()
import datastore as ds
from spec import Spec

SPEC = "dhruva-s"
OUTDIR = os.path.join(HERE, "data", "e10_s22_instrument")
S22_LIMIT = -10.0            # G2'' delta
S22_THRESH = 2.0             # near-miss raw-gap threshold for S11/S22 (E10 §1)

spec = Spec.load(SPEC)
BASE = {k: c for k, c in spec.constraints.items()
        if c.get("status") != "unsupported"}
EXT = dict(BASE)
EXT["s22_max_db"] = {"max": S22_LIMIT}


def norm_margin(c, val):
    scale = abs(c.get("max") if "max" in c else c.get("min")) or 1.0
    slacks = []
    if "max" in c:
        slacks.append((c["max"] - val) / scale)
    if "min" in c:
        slacks.append((val - c["min"]) / scale)
    return min(slacks)


def raw_gap(c, val):
    """Natural-unit shortfall on a failing metric (positive number)."""
    if "max" in c and val > c["max"]:
        return val - c["max"]
    if "min" in c and val < c["min"]:
        return c["min"] - val
    return 0.0


def ext_table(metrics):
    rows = []
    n_fail = 0
    for name, c in EXT.items():
        val = metrics.get(name)
        if val is None:
            rows.append({"metric": name, "target": c, "achieved": None,
                         "margin": None, "pass": False, "raw_gap": None,
                         "missing": True})
            n_fail += 1
            continue
        m = norm_margin(c, val)
        ok = m >= 0
        rows.append({"metric": name, "target": c, "achieved": val,
                     "margin": m, "pass": ok,
                     "raw_gap": (0.0 if ok else raw_gap(c, val)),
                     "missing": False})
        if not ok:
            n_fail += 1
    return rows, n_fail


def measure(row, repeats=1):
    wl, ts = row["wl_hash"], row["ts"]
    t = Task(f"e10-{wl[:8]}", SPEC, wl, budget=repeats + 1, seed=1, tier=2,
             ref_ts=ts, ref_evals=row.get("n_evals"), era="current")
    env = Env(t, logger=None)
    bp = row.get("best_params")
    results = []
    for _ in range(repeats):
        out = env.evaluate(params=bp)
        results.append(out["metrics"])
    return env, results


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    sel = json.load(open(os.path.join(OUTDIR, "_selection.json")))
    all_rows = [r for r in ds.load("topo_labels") if r.get("spec") == SPEC]
    by_key = {(r["wl_hash"], r["ts"]): r for r in all_rows}

    total_ngspice = 0
    summary = []
    for pick in sel["picks"]:
        row = by_key[(pick["wl_hash"], pick["ts"])]
        rank = pick["rank"]
        is_best = (rank == 1)
        reps = 3 if is_best else 1
        env, results = measure(row, repeats=reps)
        total_ngspice += env.ngspice_calls
        metrics = results[0]
        s22vals = [r.get("s22_max_db") for r in results]
        spread = (max(s22vals) - min(s22vals)) if is_best else 0.0
        tbl, n_fail = ext_table(metrics)
        cfg = row.get("zoaf_cfg") or {}
        doc = {
            "goal": "G2'' = dhruva-s + s22_max_db <= -10 dB",
            "rank": rank,
            "wl_hash": pick["wl_hash"],
            "row_ts": pick["ts"],
            "verdict_relevant_best_single_point": is_best,
            "provenance": {
                "recipe": cfg.get("recipe"),
                "seed": cfg.get("seed"),
                "inductor_q": cfg.get("inductor_q"),
                "source_arm": (row.get("provenance") or {}).get("source_arm"),
                "archetype": (row.get("provenance") or {}).get("archetype"),
                "n_evals": row.get("n_evals"),
                "git_sha": row.get("git_sha"),
                "era": "current",
            },
            "reconstruction": "recorded best_params (exact stored sizing); "
                              "no re-optimization",
            "measured_metrics": metrics,
            "s22_max_db": metrics.get("s22_max_db"),
            "base_worst_margin_recorded": pick["worst_base_margin"],
            "extended_spec_table": tbl,
            "n_failing_objectives": n_fail,
            "harness_stamp": env.harness(),
            "replay_fence": {
                "repeats": reps,
                "s22_max_db_values": s22vals,
                "spread": spread,
            },
            "ngspice_calls_this_topology": env.ngspice_calls,
        }
        with open(os.path.join(OUTDIR, f"topo_{rank:02d}_{pick['wl_hash'][:8]}.json"),
                  "w") as fh:
            json.dump(doc, fh, indent=2)
        summary.append({"rank": rank, "wl": pick["wl_hash"],
                        "s22_max_db": metrics.get("s22_max_db"),
                        "n_fail": n_fail, "ngspice": env.ngspice_calls,
                        "spread": spread if is_best else None})
        print(f"rank {rank} wl={pick['wl_hash']}: s22_max_db="
              f"{metrics.get('s22_max_db'):+.4f}  n_fail={n_fail}  "
              f"ngspice={env.ngspice_calls}"
              + (f"  replay_spread={spread:.4f}" if is_best else ""))

    with open(os.path.join(OUTDIR, "_summary.json"), "w") as fh:
        json.dump({"total_ngspice_calls": total_ngspice,
                   "topologies": summary}, fh, indent=2)
    print(f"\nTOTAL ngspice invocations (measurement): {total_ngspice}")
    print("wrote per-topology JSON + _summary.json")


if __name__ == "__main__":
    main()

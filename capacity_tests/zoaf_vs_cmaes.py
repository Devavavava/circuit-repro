"""ZOAF vs CMA-ES, head to head, on a varied set of (topology, spec) tasks.

Refreshes the FINDINGS S43.2 comparison (CMA-ES beat ZOAF 4/5 vs 1/5) on a
deliberately varied grid so the read is not dominated by one easy/hard corner:

    6 topologies (8 -> 20 devices)  x  9 specs  x  5 seeds

Both optimizers run through null_sizer's own budget counter on the SAME objective,
deck and box, at a MATCHED budget per cell: ZOAF runs at its natural schedule, and
CMA-ES is matched to ZOAF's exact eval count for that cell (the S43.2 method). One
eval = 1 ngspice call (2 when the spec gates NF), identical for both arms.

Read-only: uses `make_objective` with no op_sink and never writes the label store.
Imports the MAIN checkout's lna/ (via $LNA_DEPS_ROOT) so data + the ZOAF clone
resolve even from a worktree.

    source env.sh
    python capacity_tests/zoaf_vs_cmaes.py --seeds 5 --workers 24
    python capacity_tests/zoaf_vs_cmaes.py --aggregate-only --out <file.jsonl>
"""
import argparse
import json
import os
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor

ROOT = os.environ.get("LNA_DEPS_ROOT") or os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "lna"))
sys.path.insert(0, os.path.join(ROOT, "misc", "ZOAF"))

import null_sizer as N          # noqa: E402
import size as S                # noqa: E402

# 6 topologies spanning the device-count range, picked from the store.
TOPOS = [
    "d6c0e6fc6dc1adaa",   # 8 devices, 1 inductor
    "5fa89b4737cdf8cc",   # 10, 2
    "1403690fcd12173e",   # 12, 3
    "baea72246df87313",   # 14, 3
    "182aa0c736e801a4",   # 16, 2
    "ace8383c2fa68d03",   # 20, 2  (the flagship core)
]
# existing specs (legacy-lna5 dropped: no sizing block) + the 6 capacity-ladder
# specs, so the comparison spans varied bands and can't be fooled by overtraining.
SPECS = ["wifi24", "dhruva-s", "dhruva-l1", "dhruva-l2", "dhruva-l5",
         "gps-l1", "wideband-sdr", "ism58",
         "easy1g", "n78-35", "sub900", "wb05-2", "unii55", "xband8"]

# The 6 ladder specs live in THIS worktree, not the main checkout whose lna/ code
# we import. Spec.load accepts a path, and the worktree's specs dir holds every
# spec, so we resolve spec names to their worktree paths.
WT_SPECS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "lna", "specs")


def spec_id(name):
    p = os.path.join(WT_SPECS, name + ".yaml")
    return p if os.path.exists(p) else name


ZOAF_CAP = 1200          # bound ZOAF's natural budget so a cell can't run away
INDUCTOR_Q = 12          # the honest post-cutover deck for every cell

_TOKEN_ROWS = {}         # wl_hash -> a store row carrying that topology's tokens


def load_token_rows():
    store = os.path.join(ROOT, "lna", "data", "topo_labels.jsonl")
    want = set(TOPOS)
    for line in open(store):
        r = json.loads(line)
        wl = r.get("wl_hash")
        if wl in want and wl not in _TOKEN_ROWS:
            g = r.get("graph") or {}
            if g.get("tokens"):
                _TOKEN_ROWS[wl] = r
        if len(_TOKEN_ROWS) == len(want):
            break
    missing = want - set(_TOKEN_ROWS)
    if missing:
        sys.exit(f"no token rows for {missing}")


def run_arm(task, algo, budget, seed, cfg):
    points = []
    obj, names, decode, _ = S.make_objective(
        task["body"], task["spec"], task["sizable"], task["fixed"], points=points)
    bud = N._Budget(obj, budget, points)
    t0 = time.time()
    try:
        if algo == "cmaes":
            N.run_cmaes(bud, len(names), seed)
        elif algo == "zoaf":
            N.run_zoaf_ref(bud, names, seed, cfg)
    except N._BudgetOut:
        pass
    bx, bm = bud.best()
    feas = bool(task["spec"].feasible(bm)[0]) if bm else False
    return {"feasible": feas, "best_obj": round(bud.best_f, 5),
            "n_evals": bud.n, "evals_to_best": bud.best_i,
            "n_sim_fail": bud.n_fail, "wall_s": round(time.time() - t0, 2)}


def run_cell(args):
    # Nothing may escape: an uncaught exception in a worker aborts the whole pool.
    wl, spec_name, seed = args
    try:
        task = N.build_task(wl, spec_id(spec_name), inductor_q=INDUCTOR_Q,
                            row=_TOKEN_ROWS[wl])
        cfg = task["cfg"]
        z = run_arm(task, "zoaf", ZOAF_CAP, seed, cfg)    # natural (capped) budget
        c = run_arm(task, "cmaes", z["n_evals"], seed, cfg)  # matched to ZOAF
        return {"wl": wl, "spec": spec_name, "seed": seed,
                "n_devices": task["topo"].n_devices, "d": len(task["sizable"]),
                "nf_gated": task["nf_gated"], "budget": z["n_evals"],
                "zoaf": z, "cmaes": c}
    except BaseException as e:                        # SystemExit if not sizable
        return {"wl": wl, "spec": spec_name, "seed": seed,
                "skip": f"{type(e).__name__}: {str(e)[:90]}"}


def aggregate(rows):
    cells = [r for r in rows if "skip" not in r]
    skips = [r for r in rows if "skip" in r]
    print(f"\n=== ZOAF vs CMA-ES — {len(cells)} cells "
          f"({len(skips)} skipped: not sizable) ===")
    zf = sum(r["zoaf"]["feasible"] for r in cells)
    cf = sum(r["cmaes"]["feasible"] for r in cells)
    print(f"feasible cells:  ZOAF {zf}/{len(cells)}   CMA-ES {cf}/{len(cells)}")

    both = only_z = only_c = neither = 0
    z_better = c_better = tie = 0
    for r in cells:
        fz, fc = r["zoaf"]["feasible"], r["cmaes"]["feasible"]
        both += fz and fc
        only_z += fz and not fc
        only_c += fc and not fz
        neither += not fz and not fc
        oz, oc = r["zoaf"]["best_obj"], r["cmaes"]["best_obj"]
        if abs(oz - oc) < 1e-6:
            tie += 1
        elif oc < oz:
            c_better += 1
        else:
            z_better += 1
    print(f"head-to-head feasibility:  both {both}  only-ZOAF {only_z}  "
          f"only-CMA-ES {only_c}  neither {neither}")
    print(f"better best_obj (lower):   CMA-ES {c_better}  ZOAF {z_better}  tie {tie}")

    def med(arm, key):
        vs = [r[arm][key] for r in cells if r[arm][key] is not None]
        return round(statistics.median(vs), 4) if vs else None
    print(f"median best_obj:  ZOAF {med('zoaf','best_obj')}  "
          f"CMA-ES {med('cmaes','best_obj')}")

    print("\nper-spec feasible-rate (ZOAF / CMA-ES):")
    for sp in SPECS:
        sub = [r for r in cells if r["spec"] == sp]
        if not sub:
            continue
        print(f"  {sp:<14} {sum(r['zoaf']['feasible'] for r in sub)}/{len(sub)}"
              f"   {sum(r['cmaes']['feasible'] for r in sub)}/{len(sub)}")
    print("\nper-topology feasible-rate (ZOAF / CMA-ES):")
    for wl in TOPOS:
        sub = [r for r in cells if r["wl"] == wl]
        if not sub:
            continue
        nd = sub[0]["n_devices"]
        print(f"  {wl[:12]} ({nd:>2}dev) {sum(r['zoaf']['feasible'] for r in sub)}"
              f"/{len(sub)}   {sum(r['cmaes']['feasible'] for r in sub)}/{len(sub)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--specs", nargs="*", default=SPECS)
    ap.add_argument("--topos", nargs="*", default=TOPOS)
    ap.add_argument("--out", default="capacity_tests/results/zoaf_vs_cmaes.jsonl")
    ap.add_argument("--aggregate-only", action="store_true")
    args = ap.parse_args()

    if args.aggregate_only:
        rows = [json.loads(l) for l in open(args.out)]
        aggregate(rows)
        return 0

    load_token_rows()
    cells = [(wl, sp, seed) for wl in args.topos for sp in args.specs
             for seed in range(1, args.seeds + 1)]
    print(f"cells: {len(cells)}  ({len(args.topos)} topos x {len(args.specs)} "
          f"specs x {args.seeds} seeds), workers={args.workers}")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    rows = []
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as ex, \
            open(args.out, "w") as fh:
        for i, r in enumerate(ex.map(run_cell, cells), 1):
            rows.append(r)
            fh.write(json.dumps(r) + "\n")
            fh.flush()
            if i % 20 == 0 or i == len(cells):
                print(f"  {i}/{len(cells)} cells  ({time.time()-t0:.0f}s)")
    print(f"done in {time.time()-t0:.0f}s -> {args.out}")
    aggregate(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())

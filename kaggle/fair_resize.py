"""Fair-budget re-size of the editcap-v1 baseline edits.

The baseline gave each AI edit only a BASE size (2x300=600 evals; the single
best per cell escalated to 3x600=1800), while the ANCHOR it is compared against
was sized by the null-filter at 3 seeds x 1200 = 3600 evals. So a "best_edit
worst-margin worse than anchor" result confounds two things: a genuinely worse
topology, versus a fine topology that was simply under-optimised.

This tool removes that confound: it re-sizes each smoke-passing edit at the
ANCHOR's exact budget (seeds (1,2,3) x 1200, best-over-seeds, same smoke_run
engine, same worst-margin convention as build_editcap_lib_v1) and reports, per
cell, whether the AI's fix -- given an equal shot -- now beats the broken anchor
or reaches feasibility.

Read-only on tracked code; writes only its own JSON report. Run under env.sh.
"""
import argparse
import glob
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "lna"))
sys.path.insert(0, os.path.join(REPO, "kaggle"))
sys.path.insert(0, os.path.join(REPO, "kaggle", "loop"))

CAMP = os.path.join(REPO, "kaggle", "campaigns", "editcap-v1-baseline")
LIBS = [os.path.join(REPO, "kaggle", d) for d in
        ("editcap-lib-v1a", "editcap-lib-v1b", "editcap-lib-v1")]
PDK = "gf180mcu"
SEEDS = (1, 2, 3)
BUDGET = 1200            # per seed -> 3x1200 = 3600 evals, matches the anchor


def _spec_path(cell):
    for lib in LIBS:
        p = os.path.join(lib, cell, "spec.yaml")
        if os.path.exists(p):
            return p
    return None


def _adj_dir(cell, arm):
    for b in ("batch-a", "batch-b"):
        d = os.path.join(CAMP, b, "adjudication", cell, arm)
        if os.path.isdir(d):
            return d
    return None


def _margins_for(spec, metrics):
    """Per-gated-constraint normalized margin (negative == failing); returns
    (margins_dict, worst=[name, margin]). IDENTICAL rule to build_editcap_lib_v1
    so the number is directly comparable to the stored anchor_worst_margin."""
    out, worst = {}, None
    for name, c in (spec.constraints or {}).items():
        if c.get("status") == "unsupported":
            continue
        ach = metrics.get(name)
        supported = ach is not None
        margin = None
        if supported:
            scale = spec._scale(c)
            if "min" in c:
                margin = (ach - c["min"]) / scale
            elif "max" in c:
                margin = (c["max"] - ach) / scale
        out[name] = {"achieved": ach, "margin": margin, "supported": supported}
        if margin is not None and (worst is None or margin < worst[1]):
            worst = [name, margin]
    return out, worst


def _resize_one(args):
    """Worker: re-size ONE edit at the full anchor budget over all seeds.
    Returns a dict summarising the best-over-seeds outcome."""
    cell, arm, edit_index, edit_path = args
    import proposal as P
    import bench_anchor_prep as PREP
    from spec import Spec

    spec_path = _spec_path(cell)
    text = open(edit_path, encoding="utf-8").read()
    info = P.round_trip(text)
    if not info.get("ok"):
        return {"cell": cell, "arm": arm, "edit": edit_index,
                "error": "round_trip: %s" % info.get("error")}
    tokens = info["tokens"]
    spec = Spec.load(spec_path)

    best = None            # (worst_margin_value, worst_name, feasible, seed, metrics)
    per_seed = []
    for seed in SEEDS:
        try:
            res = PREP.smoke_run(list(tokens), spec_path, seed, BUDGET, PDK)
        except Exception as e:                                  # noqa: BLE001
            per_seed.append({"seed": seed, "error": repr(e)})
            continue
        if res is None:
            per_seed.append({"seed": seed, "not_sizable": True})
            continue
        mg, worst = _margins_for(spec, res.get("metrics") or {})
        wm = worst[1] if worst else None
        feas = bool(res.get("feasible"))
        per_seed.append({"seed": seed, "feasible": feas,
                         "worst_margin": worst, "n_sim_fail": res.get("n_sim_fail")})
        key = wm if wm is not None else -1e9
        if best is None or feas > best[2] or (feas == best[2] and key > best[0]):
            best = (key, (worst[0] if worst else None), feas, seed,
                    res.get("metrics"))
    if best is None:
        return {"cell": cell, "arm": arm, "edit": edit_index,
                "error": "no sizable seed", "per_seed": per_seed}
    return {"cell": cell, "arm": arm, "edit": edit_index,
            "fair_worst_margin": [best[1], best[0]] if best[0] > -1e9 else None,
            "fair_feasible": best[2], "best_seed": best[3],
            "fair_metrics": best[4], "per_seed": per_seed}


def _targets(arm, scope):
    """Build the (cell, arm, edit_index, path) work-list.
    scope='best' -> the escalated best edit per cell; 'all' -> every
    smoke-passing edit."""
    rows = {}
    for f in glob.glob(os.path.join(CAMP, "batch-*", "results-%s.jsonl" % arm)):
        for ln in open(f):
            ln = ln.strip()
            if ln:
                r = json.loads(ln)
                rows[r["spec"]] = r
    work = []
    for cell, r in rows.items():
        adj = _adj_dir(cell, arm)
        if adj is None:
            continue
        if scope == "best":
            bi = r.get("best_edit_index")
            if bi is None:
                continue
            idxs = [bi]
        else:
            idxs = []
            for m in glob.glob(os.path.join(adj, "edit*.meta.json")):
                meta = json.load(open(m))
                if meta.get("fence_outcome") == "smoke_pass":
                    idxs.append(meta["index"])
        for bi in idxs:
            p = os.path.join(adj, "edit%d.net" % bi)
            if os.path.exists(p):
                work.append((cell, arm, bi, p))
    return work, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="B")
    ap.add_argument("--scope", choices=("best", "all"), default="best")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default=os.path.join(CAMP, "fair-resize-B-best.json"))
    args = ap.parse_args()

    work, rows = _targets(args.arm, args.scope)
    print("fair-resize: arm=%s scope=%s targets=%d budget=%dx%d=%d evals/edit"
          % (args.arm, args.scope, len(work), len(SEEDS), BUDGET,
             len(SEEDS) * BUDGET), flush=True)

    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_resize_one, w): w for w in work}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            results.append(r)
            tag = ("feasible!" if r.get("fair_feasible")
                   else (r.get("fair_worst_margin") or r.get("error")))
            print("  [%d/%d] %-22s edit%s -> %s"
                  % (i, len(work), r["cell"], r["edit"], tag), flush=True)

    # fold in the anchor + baseline numbers for the comparison
    def wm(x):
        return x[1] if isinstance(x, (list, tuple)) else None
    # keep the best fair edit per cell
    per_cell = {}
    for r in results:
        c = r["cell"]
        cur = per_cell.get(c)
        rv = wm(r.get("fair_worst_margin"))
        if cur is None:
            per_cell[c] = r
        else:
            better = (r.get("fair_feasible"), rv if rv is not None else -1e9)
            prev = (cur.get("fair_feasible"), wm(cur.get("fair_worst_margin"))
                    if wm(cur.get("fair_worst_margin")) is not None else -1e9)
            if better > prev:
                per_cell[c] = r
    report = {"arm": args.arm, "scope": args.scope, "budget_evals": len(SEEDS) * BUDGET,
              "cells": {}}
    for c, r in per_cell.items():
        row = rows.get(c, {})
        report["cells"][c] = {
            "anchor_worst_margin": row.get("anchor_worst_margin"),
            "baseline_best_edit_worst_margin": row.get("best_edit_worst_margin"),
            "fair_worst_margin": r.get("fair_worst_margin"),
            "fair_feasible": r.get("fair_feasible"),
            "edit": r.get("edit"), "best_seed": r.get("best_seed"),
            "error": r.get("error"),
        }
    with open(args.out, "w") as fh:
        json.dump(report, fh, indent=1, default=float)
    print("\nwrote", args.out, flush=True)


if __name__ == "__main__":
    main()

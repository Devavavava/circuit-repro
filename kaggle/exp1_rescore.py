"""Experiment 1 (local sizing half): DETERMINISTIC re-score of the editcap-v1
baseline.

Now that gf180 sizing is deterministic (MC pinned to the typical corner, commit
49ab2b9f), re-size at the anchor's full budget (seeds 1,2,3 x 1200 = 3600 evals):
  - every smoke-passing ARM-B edit (from the baseline adjudication AND the
    empties-rerun adjudication -> all 53 cells' edits), and
  - every cell's ANCHOR (the null-filter's anchor numbers were computed under the
    OLD random-corner regime, so re-size the anchor here too for an apples-to-
    apples deterministic comparison).

Best-over-seeds worst-margin per target (seeds now explore optimizer starts, not
sim noise). Output: per-cell {anchor_fair, best_edit_fair, delta, feasible}.

Read-only on tracked code; writes only its own JSON. Run under env.sh.
NOTE: uses the edits we already HAVE (baseline arm-B @3072 tokens + empties-rerun
@8192). A fully-clean all-53 @8192 LLM re-run is the separate Kaggle step.
"""
import argparse
import glob
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (REPO, os.path.join(REPO, "lna"), os.path.join(REPO, "kaggle"),
          os.path.join(REPO, "kaggle", "loop")):
    sys.path.insert(0, p)

CAMP = os.path.join(REPO, "kaggle", "campaigns", "editcap-v1-baseline")
LIBS = [os.path.join(REPO, "kaggle", d) for d in
        ("editcap-lib-v1a", "editcap-lib-v1b", "editcap-lib-v1")]
ADJ_DIRS = [os.path.join(CAMP, "batch-a", "adjudication"),
            os.path.join(CAMP, "batch-b", "adjudication"),
            os.path.join(CAMP, "empties-rerun", "adjudication")]
PDK = "gf180mcu"
SEEDS = (1, 2, 3)
BUDGET = 1200


def _spec_path(cell):
    for lib in LIBS:
        p = os.path.join(lib, cell, "spec.yaml")
        if os.path.exists(p):
            return p
    return None


def _anchor_net(cell):
    for lib in LIBS:
        p = os.path.join(lib, cell, "anchor.net")
        if os.path.exists(p):
            return p
    return None


def _all_cells():
    cells = set()
    for lib in LIBS:
        for d in glob.glob(os.path.join(lib, "*", "spec.yaml")):
            cells.add(os.path.basename(os.path.dirname(d)))
    return sorted(cells)


def _smoke_edits(cell, arm="B"):
    """Every smoke-passing edit .net for this cell/arm, from any adjudication
    archive (baseline batch-a/b or empties-rerun)."""
    out = []
    for base in ADJ_DIRS:
        d = os.path.join(base, cell, arm)
        if not os.path.isdir(d):
            continue
        for meta in glob.glob(os.path.join(d, "edit*.meta.json")):
            try:
                m = json.load(open(meta))
            except Exception:                                   # noqa: BLE001
                continue
            if m.get("fence_outcome") == "smoke_pass":
                net = os.path.join(d, "edit%d.net" % m["index"])
                if os.path.exists(net):
                    out.append(net)
    return out


def _margins_for(spec, metrics):
    out, worst = {}, None
    for name, c in (spec.constraints or {}).items():
        if c.get("status") == "unsupported":
            continue
        ach = metrics.get(name)
        if ach is None:
            out[name] = {"achieved": None, "margin": None, "supported": False}
            continue
        scale = spec._scale(c)
        margin = ((ach - c["min"]) / scale if "min" in c
                  else (c["max"] - ach) / scale if "max" in c else None)
        out[name] = {"achieved": ach, "margin": margin, "supported": True}
        if margin is not None and (worst is None or margin < worst[1]):
            worst = [name, margin]
    return out, worst


def _resize(args):
    """Size ONE netlist at all seeds, best-over-seeds. kind in {anchor, edit}."""
    cell, kind, path = args
    import proposal as P
    import bench_anchor_prep as PREP
    from spec import Spec
    spec_path = _spec_path(cell)
    info = P.round_trip(open(path, encoding="utf-8").read())
    if not info.get("ok"):
        return {"cell": cell, "kind": kind, "path": path,
                "error": "round_trip: %s" % info.get("error")}
    tokens = info["tokens"]
    spec = Spec.load(spec_path)
    best = None
    for seed in SEEDS:
        try:
            res = PREP.smoke_run(list(tokens), spec_path, seed, BUDGET, PDK)
        except Exception as e:                                  # noqa: BLE001
            continue
        if res is None:
            continue
        _mg, worst = _margins_for(spec, res.get("metrics") or {})
        wm = worst[1] if worst else None
        feas = bool(res.get("feasible"))
        key = wm if wm is not None else -1e9
        if best is None or feas > best[0] or (feas == best[0] and key > best[1]):
            best = (feas, key, worst, seed)
    if best is None:
        return {"cell": cell, "kind": kind, "path": path, "error": "no sizable seed"}
    return {"cell": cell, "kind": kind,
            "feasible": best[0],
            "worst_margin": best[2],
            "best_seed": best[3]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default=os.path.join(CAMP, "exp1-rescore.json"))
    args = ap.parse_args()

    cells = _all_cells()
    targets = []
    per_cell_edits = {}
    for c in cells:
        if _anchor_net(c):
            targets.append((c, "anchor", _anchor_net(c)))
        edits = _smoke_edits(c, "B")
        per_cell_edits[c] = edits
        for e in edits:
            targets.append((c, "edit", e))
    print("exp1 re-score: %d cells, %d targets (%d anchors + %d edits), "
          "det MC-off, %dx%d=%d evals each"
          % (len(cells), len(targets), sum(1 for t in targets if t[1] == "anchor"),
             sum(1 for t in targets if t[1] == "edit"),
             len(SEEDS), BUDGET, len(SEEDS) * BUDGET), flush=True)

    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_resize, t): t for t in targets}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            results.append(r)
            wm = r.get("worst_margin")
            tag = ("feasible" if r.get("feasible")
                   else (("%.3f" % wm[1]) if isinstance(wm, (list, tuple)) else r.get("error")))
            print("  [%d/%d] %-22s %-6s -> %s"
                  % (i, len(targets), r["cell"], r["kind"], tag), flush=True)

    # fold: per-cell anchor (deterministic) vs best edit (best over the cell's edits)
    def wmv(r):
        w = r.get("worst_margin")
        return w[1] if isinstance(w, (list, tuple)) else None
    report = {"budget_evals": len(SEEDS) * BUDGET, "mc": "off (typical corner)",
              "cells": {}}
    by_cell = {}
    for r in results:
        by_cell.setdefault(r["cell"], []).append(r)
    for c, rs in by_cell.items():
        anch = next((r for r in rs if r["kind"] == "anchor"), None)
        edits = [r for r in rs if r["kind"] == "edit" and "worst_margin" in r]
        best_edit = None
        for r in edits:
            if best_edit is None:
                best_edit = r
            else:
                a = (r.get("feasible"), wmv(r) if wmv(r) is not None else -1e9)
                b = (best_edit.get("feasible"), wmv(best_edit) if wmv(best_edit) is not None else -1e9)
                if a > b:
                    best_edit = r
        report["cells"][c] = {
            "n_edits": len(per_cell_edits.get(c, [])),
            "anchor_feasible": (anch or {}).get("feasible"),
            "anchor_worst_margin": (anch or {}).get("worst_margin"),
            "best_edit_feasible": (best_edit or {}).get("feasible"),
            "best_edit_worst_margin": (best_edit or {}).get("worst_margin"),
        }
    with open(args.out, "w") as fh:
        json.dump(report, fh, indent=1, default=float)
    print("\nwrote", args.out, flush=True)


if __name__ == "__main__":
    main()
